"""Unit tests for Supabase Application Tracker."""

import pytest
from src.models.job import JobRecord
from src.models.resume import ReviewPackage
from src.tracker.db import ApplicationTrackerDB


def test_tracker_db_crud():
    db = ApplicationTrackerDB(in_memory=True)

    # 1. Save Job
    job = JobRecord(
        job_id="test_job_123",
        source="naukri",
        url="https://naukri.com/test-job",
        title="Senior Performance Lead",
        company="Growth Innovators",
        location="Bengaluru",
        description_raw="We need a senior performance marketer with 2+ years experience.",
    )
    saved = db.save_job(job)
    assert saved is True

    # Duplicate job should be ignored safely
    duplicate_saved = db.save_job(job)
    assert duplicate_saved is False

    # 2. Save Application Package
    pkg = ReviewPackage(
        application_id="app-123",
        job_id="test_job_123",
        job_title="Senior Performance Lead",
        company="Growth Innovators",
        source_url="https://naukri.com/test-job",
        match_score=88.5,
        recommendation="apply_review",
        output_directory="outputs/app-123",
        resume_md_path="outputs/app-123/resume.md",
        resume_docx_path="outputs/app-123/res-v1.docx",
        resume_pdf_path="outputs/app-123/resume.pdf",
        cover_note_path="outputs/app-123/cover.md",
        match_report_path="outputs/app-123/match.json",
        validation_report_path="outputs/app-123/validation.json",
        change_log_path="outputs/app-123/change-log.md",
        status="review_ready",
    )
    db.save_application(pkg)

    # 3. Update user decision
    updated = db.update_decision("app-123", "apply", notes="Approved for manual submission on Naukri")
    assert updated is True

    # 4. Fetch application details
    app = db.get_application("app-123")
    assert app is not None
    assert app["user_decision"] == "apply"
    assert app["status"] == "approved_for_manual_apply"
    assert "Approved for manual submission" in app["notes"]
