"""Unit tests for SQLite Database Tracker."""

import pytest
import tempfile
from pathlib import Path
from src.models.job import JobRecord
from src.tracker.db import ApplicationTrackerDB


def test_tracker_db_crud():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_tracker.db"
        db = ApplicationTrackerDB(db_path=db_path)

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

        # 2. Update user decision
        conn = db._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO applications (application_id, job_id, resume_version, match_score, status, user_decision)
                VALUES ('app-123', 'test_job_123', 'res-v1', 88.5, 'review_ready', 'pending')
                """
            )
            conn.commit()
        finally:
            conn.close()

        updated = db.update_decision("app-123", "apply", notes="Approved for manual submission on Naukri")
        assert updated is True

        app = db.get_application("app-123")
        assert app is not None
        assert app["user_decision"] == "apply"
        assert app["status"] == "approved_for_manual_apply"
        assert "Approved for manual submission" in app["notes"]
