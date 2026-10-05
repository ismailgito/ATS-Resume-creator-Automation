"""Unit tests for Job Ingestion and Deduplication."""

import pytest
from pathlib import Path
from src.ingest.normalizer import normalize_job_text, compute_content_hash, deduplicate_jobs
from src.ingest.job_sources import IngestionManager
from src.models.job import JobRecord
from src.config import PROJECT_ROOT


def test_normalize_job_text_strips_html_and_excess_whitespace():
    raw_html = "<div class='job'><h1>Performance Marketer</h1><p>Experience: 2+ yrs &amp; GA4</p><script>alert(1)</script></div>"
    cleaned = normalize_job_text(raw_html)
    assert "<div" not in cleaned
    assert "<h1>" not in cleaned
    assert "alert(1)" not in cleaned
    assert "&amp;" not in cleaned
    assert "&" in cleaned
    assert "Performance Marketer" in cleaned
    assert "Experience: 2+ yrs & GA4" in cleaned


def test_compute_content_hash_consistency():
    text1 = "Google Ads Specialist with 2 years experience"
    text2 = "google ads   specialist with 2   years experience"
    hash1 = compute_content_hash(text1)
    hash2 = compute_content_hash(text2)
    assert hash1 == hash2


def test_deduplicate_jobs():
    job1 = JobRecord(
        job_id="j1",
        source="naukri",
        url="https://naukri.com/job-1",
        title="Performance Marketing Specialist",
        company="Alpha Corp",
        location="Bengaluru",
        description_raw="We need a performance marketing specialist.",
    )
    job2 = JobRecord(
        job_id="j2",
        source="naukri",
        url="https://naukri.com/job-1",  # duplicate URL
        title="Performance Marketing Specialist",
        company="Alpha Corp",
        location="Bengaluru",
        description_raw="We need a performance marketing specialist.",
    )
    job3 = JobRecord(
        job_id="j3",
        source="naukri",
        url="https://naukri.com/job-2",
        title="Digital Marketing Lead",
        company="Beta Inc",
        location="Remote",
        description_raw="Digital marketing lead role.",
    )
    unique = deduplicate_jobs([job1, job2, job3])
    assert len(unique) == 2
    assert unique[0].job_id == "j1"
    assert unique[1].job_id == "j3"


def test_ingest_from_json_file():
    sample_path = PROJECT_ROOT / "data/sample-jobs/01-perf-mktg-manager.json"
    jobs = IngestionManager.from_file(sample_path)
    assert len(jobs) == 1
    job = jobs[0]
    assert "Performance Marketing" in job.title
    assert job.experience_min == 2
    assert job.experience_max == 4
