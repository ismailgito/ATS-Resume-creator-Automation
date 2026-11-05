"""Unit tests for Match Scorer."""

import pytest
from src.config import load_candidate_profile, PROJECT_ROOT
from src.ingest.job_sources import IngestionManager
from src.models.profile import CandidateProfile
from src.parse.job_parser import JobParser
from src.score.scorer import MatchScorer


@pytest.fixture
def candidate():
    data = load_candidate_profile(PROJECT_ROOT / "data/candidate-profile.json")
    return CandidateProfile.from_dict(data)


@pytest.fixture
def scorer():
    return MatchScorer()


@pytest.fixture
def parser():
    return JobParser()


def test_scorer_high_fit_role(candidate, scorer, parser):
    sample = PROJECT_ROOT / "data/sample-jobs/01-perf-mktg-manager.json"
    job = IngestionManager.from_file(sample)[0]
    parsed = parser.parse(job)
    report = scorer.score(parsed, candidate)

    assert report.overall_score >= 80.0
    assert report.recommendation == "apply_review"
    assert "Google Ads" in report.matched_requirements or any("google" in m.lower() for m in report.matched_requirements)


def test_scorer_irrelevant_role_rejected(candidate, scorer, parser):
    sample = PROJECT_ROOT / "data/sample-jobs/04-irrelevant-role.json"
    job = IngestionManager.from_file(sample)[0]
    parsed = parser.parse(job)
    report = scorer.score(parsed, candidate)

    assert report.overall_score < 40.0
    assert report.recommendation == "reject"


def test_scorer_triggers_negative_constraints(candidate, scorer, parser):
    sample = PROJECT_ROOT / "data/sample-jobs/06-conflicting-role.json"
    job = IngestionManager.from_file(sample)[0]
    parsed = parser.parse(job)
    report = scorer.score(parsed, candidate)

    assert len(report.negative_constraint_flags) > 0
    assert report.recommendation == "reject"
    flags_text = " ".join(report.negative_constraint_flags).lower()
    assert "salesforce" in flags_text or "dv360" in flags_text or "seniority" in flags_text


def test_scoring_weights_sum_to_one(scorer):
    total_weights = sum(scorer.weights.values())
    assert abs(total_weights - 1.0) < 0.001


def test_scorer_ai_engineer_role_rejected(candidate, scorer, parser):
    jd_text = (
        "We are hiring an AI Engineer with 1-3 years of experience to build and deploy LLM-powered applications. "
        "Required Skills: Python, REST APIs, Prompt engineering, RAG pipelines, Vector databases, LLM APIs. "
        "Preferred Skills: n8n, LangChain, Docker, FastAPI."
    )
    job = IngestionManager.from_text(jd_text, title="AI Engineer", company="Tech Solution")
    parsed = parser.parse(job)
    report = scorer.score(parsed, candidate)

    assert report.overall_score < 40.0
    assert report.recommendation == "reject"
    assert any("Domain mismatch" in flag for flag in report.negative_constraint_flags)


def test_scorer_empty_job_rejected(candidate, scorer, parser):
    job = IngestionManager.from_text("", title="Empty Role", company="Empty Co")
    parsed = parser.parse(job)
    report = scorer.score(parsed, candidate)
    assert report.overall_score == 0.0
    assert report.recommendation == "reject"
    assert any("Empty or unparseable" in flag for flag in report.negative_constraint_flags)


def test_scorer_dynamic_negative_constraints(candidate, scorer, parser):
    candidate.negative_constraints.append("Do NOT claim HubSpot")
    jd = "Seeking a growth marketer with Google Ads and HubSpot experience."
    job = IngestionManager.from_text(jd, title="Growth Specialist", company="Test Co")
    parsed = parser.parse(job)
    report = scorer.score(parsed, candidate)
    assert report.recommendation == "reject"
    assert any("hubspot" in flag.lower() for flag in report.negative_constraint_flags)
