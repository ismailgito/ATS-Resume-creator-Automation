"""SQLite Database Application Tracker."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.config import AppSettings, PROJECT_ROOT
from src.models.job import JobRecord
from src.models.resume import ReviewPackage
from src.models.score import MatchReport


class ApplicationTrackerDB:
    """Manages SQLite storage for jobs, match scores, applications, and status."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path:
            self.db_path = db_path
        else:
            settings = AppSettings()
            db_url = settings.database_url
            if db_url.startswith("sqlite:///"):
                rel_path = db_url.replace("sqlite:///", "")
                self.db_path = PROJECT_ROOT / rel_path
            else:
                self.db_path = PROJECT_ROOT / "ats_tracker.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Jobs table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    source TEXT,
                    url TEXT,
                    title TEXT,
                    company TEXT,
                    location TEXT,
                    employment_type TEXT,
                    experience_min REAL,
                    experience_max REAL,
                    salary TEXT,
                    description_raw TEXT,
                    content_hash TEXT,
                    discovered_at TEXT
                )
                """
            )
            # Match reports table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS match_reports (
                    job_id TEXT PRIMARY KEY,
                    overall_score REAL,
                    score_breakdown_json TEXT,
                    matched_reqs_json TEXT,
                    missing_reqs_json TEXT,
                    recommendation TEXT,
                    reason TEXT,
                    created_at TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs (job_id)
                )
                """
            )
            # Applications table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    application_id TEXT PRIMARY KEY,
                    job_id TEXT,
                    resume_version TEXT,
                    match_score REAL,
                    status TEXT,
                    user_decision TEXT,
                    output_directory TEXT,
                    notes TEXT,
                    discovered_at TEXT,
                    submitted_at TEXT,
                    outcome TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs (job_id)
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def save_job(self, job: JobRecord) -> bool:
        """Insert or ignore job record."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO jobs (
                    job_id, source, url, title, company, location,
                    employment_type, experience_min, experience_max,
                    salary, description_raw, content_hash, discovered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.source,
                    job.url,
                    job.title,
                    job.company,
                    job.location,
                    job.employment_type,
                    job.experience_min,
                    job.experience_max,
                    job.salary,
                    job.description_raw,
                    job.content_hash,
                    job.discovered_at,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def save_match_report(self, report: MatchReport) -> None:
        """Insert or replace match report."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO match_reports (
                    job_id, overall_score, score_breakdown_json,
                    matched_reqs_json, missing_reqs_json, recommendation,
                    reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.job_id,
                    report.overall_score,
                    json.dumps(report.score_breakdown.to_dict()),
                    json.dumps(report.matched_requirements),
                    json.dumps(report.missing_requirements),
                    report.recommendation,
                    report.reason,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def save_application(self, pkg: ReviewPackage) -> None:
        """Save or update application review package."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO applications (
                    application_id, job_id, resume_version, match_score,
                    status, user_decision, output_directory, notes,
                    discovered_at, submitted_at, outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pkg.application_id,
                    pkg.job_id,
                    Path(pkg.resume_docx_path).stem,
                    pkg.match_score,
                    pkg.status,
                    "pending",
                    pkg.output_directory,
                    pkg.recommendation,
                    datetime.now(timezone.utc).isoformat(),
                    None,
                    None,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def update_decision(self, application_id: str, decision: str, notes: str = "") -> bool:
        """Update user decision ('apply', 'save', 'reject', 'applied_manually')."""
        status_map = {
            "apply": "approved_for_manual_apply",
            "applied": "applied_manually",
            "save": "saved_in_queue",
            "reject": "rejected_by_user",
        }
        new_status = status_map.get(decision.lower(), decision)
        submitted_at = datetime.now(timezone.utc).isoformat() if decision.lower() in ["applied", "applied_manually"] else None

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE applications
                SET user_decision = ?,
                    status = ?,
                    notes = CASE
                        WHEN notes IS NULL OR notes = '' THEN ?
                        WHEN ? = '' THEN notes
                        ELSE notes || ' | ' || ?
                    END,
                    submitted_at = coalesce(?, submitted_at)
                WHERE application_id = ?
                """,
                (decision, new_status, notes, notes, notes, submitted_at, application_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def list_applications(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List tracked applications with job details."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT a.*, j.title as job_title, j.company as company, j.url as source_url
                FROM applications a
                LEFT JOIN jobs j ON a.job_id = j.job_id
                ORDER BY a.match_score DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_application(self, application_id: str) -> Optional[Dict[str, Any]]:
        """Get single application details."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT a.*, j.title as job_title, j.company as company, j.url as source_url, j.description_raw
                FROM applications a
                LEFT JOIN jobs j ON a.job_id = j.job_id
                WHERE a.application_id = ?
                """,
                (application_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
