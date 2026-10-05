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
