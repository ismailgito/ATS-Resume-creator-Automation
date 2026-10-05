"""Unit tests for Job Parser."""

import pytest
from src.ingest.job_sources import IngestionManager
from src.parse.job_parser import JobParser
from src.config import PROJECT_ROOT


def test_job_parser_extracts_experience_and_tools():
    parser = JobParser()
    text = (
        "Hiring Performance Marketing Executive with 2 to 4 years experience. "
        "Must know Google Ads, Meta Ads, GA4, and Google Tag Manager. "
        "Will manage search campaigns and ROAS optimization."
    )
    job = IngestionManager.from_text(text, title="Performance Marketing Executive", company="TechGrowth")
    parsed = parser.parse(job)

    assert parsed.experience_min == 2.0
    assert parsed.experience_max == 4.0
    skills_lower = [s.lower() for s in parsed.must_have_skills]
    assert any("google ads" in s for s in skills_lower)
    assert any("meta ads" in s or "facebook" in s for s in skills_lower)
    assert any("ga4" in s or "analytics" in s for s in skills_lower)


def test_job_parser_handles_missing_experience_gracefully():
    sample_path = PROJECT_ROOT / "data/sample-jobs/05-missing-exp-role.json"
    jobs = IngestionManager.from_file(sample_path)
    parser = JobParser()
    parsed = parser.parse(jobs[0])

    assert parsed.experience_min is None
    assert len(parsed.uncertainties) > 0
    assert any("Experience" in u for u in parsed.uncertainties)
