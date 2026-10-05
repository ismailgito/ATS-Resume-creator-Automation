"""Unit tests for Validation and ATS Quality Gate."""

import pytest
from src.config import load_candidate_profile, PROJECT_ROOT
from src.ingest.job_sources import IngestionManager
from src.models.profile import CandidateProfile
from src.parse.job_parser import JobParser
from src.resume.tailor import ResumeTailor
from src.score.scorer import MatchScorer
from src.validate.validator import ResumeValidator


@pytest.fixture
def candidate():
    data = load_candidate_profile(PROJECT_ROOT / "data/candidate-profile.json")
    return CandidateProfile.from_dict(data)


@pytest.fixture
def valid_tailored(candidate):
    sample = PROJECT_ROOT / "data/sample-jobs/01-perf-mktg-manager.json"
    job = IngestionManager.from_file(sample)[0]
    parsed = JobParser().parse(job)
    report = MatchScorer().score(parsed, candidate)
    tailored, _ = ResumeTailor().tailor(parsed, candidate, report)
    return tailored


def test_validator_passes_on_valid_resume(candidate, valid_tailored):
    validator = ResumeValidator()
    report = validator.validate(candidate, valid_tailored)
    assert report.passed is True
    assert len(report.factuality_errors) == 0
    assert len(report.missing_sections) == 0


def test_validator_catches_unverified_employer(candidate, valid_tailored):
    validator = ResumeValidator()
    # Inject fabricated employer
    valid_tailored.experience[0].company = "Fake Global Unicorn Inc."
    report = validator.validate(candidate, valid_tailored)
    assert report.passed is False
    assert any("Fake Global Unicorn Inc." in err for err in report.factuality_errors)


def test_validator_catches_negative_constraint_violation(candidate, valid_tailored):
    validator = ResumeValidator()
    # Candidate profile strictly prohibits claiming Salesforce Marketing Cloud
    valid_tailored.skills.append("Salesforce Marketing Cloud")
    report = validator.validate(candidate, valid_tailored)
    assert report.passed is False
    assert any("Salesforce Marketing Cloud" in err for err in report.factuality_errors)
