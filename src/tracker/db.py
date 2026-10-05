"""Supabase PostgreSQL Database Application Tracker."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

from src.config import AppSettings, PROJECT_ROOT
from src.models.job import JobRecord
from src.models.resume import ReviewPackage
from src.models.score import MatchReport

logger = logging.getLogger(__name__)

# Optional psycopg2 import for direct PostgreSQL URI connections
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None


class ApplicationTrackerDB:
    """
    Manages Supabase PostgreSQL storage for jobs, match scores, applications, and status tracking.
    Supports Supabase REST API (via PostgREST/Supabase SDK), direct PostgreSQL connections,
    and ephemeral in-memory fallback for offline test suites.
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        database_url: Optional[str] = None,
        in_memory: bool = False,
    ):
        settings = AppSettings()
        self.supabase_url = supabase_url or settings.supabase_url
        self.supabase_key = supabase_key or settings.supabase_key
        self.database_url = database_url or settings.database_url

        def is_valid_cred(val: Optional[str]) -> bool:
            return bool(val and not val.startswith("your_") and len(val.strip()) > 5)

        self.use_supabase_rest = is_valid_cred(self.supabase_url) and is_valid_cred(self.supabase_key)
        self.use_postgres = bool(self.database_url and ("postgres://" in self.database_url or "postgresql://" in self.database_url))

        if in_memory or (not self.use_supabase_rest and not self.use_postgres):
            self.backend = "memory"
            self._init_memory_db()
        elif self.use_supabase_rest:
            self.backend = "supabase_rest"
            self.supabase_url = self.supabase_url.rstrip("/")
        elif self.use_postgres:
            self.backend = "postgres"
            self._init_postgres_tables()

    def _init_memory_db(self):
        """Initialize in-memory database for offline execution/testing."""
        self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._mem_conn.row_factory = sqlite3.Row
        cursor = self._mem_conn.cursor()
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
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_completion (
                date TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0,
                limit_val INTEGER NOT NULL DEFAULT 10
            )
            """
        )
        self._mem_conn.commit()

    def _init_postgres_tables(self):
        """Initialize PostgreSQL tables in Supabase if using direct connection."""
        if not psycopg2:
            return
        try:
            conn = psycopg2.connect(self.database_url)
            try:
                with conn.cursor() as cursor:
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
                            experience_min NUMERIC,
                            experience_max NUMERIC,
                            salary TEXT,
                            description_raw TEXT,
                            content_hash TEXT,
                            discovered_at TIMESTAMPTZ DEFAULT NOW()
                        );
                        CREATE TABLE IF NOT EXISTS match_reports (
                            job_id TEXT PRIMARY KEY REFERENCES jobs(job_id) ON DELETE CASCADE,
                            overall_score NUMERIC,
                            score_breakdown_json JSONB,
                            matched_reqs_json JSONB,
                            missing_reqs_json JSONB,
                            recommendation TEXT,
                            reason TEXT,
                            created_at TIMESTAMPTZ DEFAULT NOW()
                        );
                        CREATE TABLE IF NOT EXISTS applications (
                            application_id TEXT PRIMARY KEY,
                            job_id TEXT REFERENCES jobs(job_id) ON DELETE CASCADE,
                            resume_version TEXT,
                            match_score NUMERIC,
                            status TEXT,
                            user_decision TEXT DEFAULT 'pending',
                            output_directory TEXT,
                            notes TEXT,
                            discovered_at TIMESTAMPTZ DEFAULT NOW(),
                            submitted_at TIMESTAMPTZ,
                            outcome TEXT
                        );
                        CREATE TABLE IF NOT EXISTS daily_completion (
                            date TEXT PRIMARY KEY,
                            count INTEGER NOT NULL DEFAULT 0,
                            limit_val INTEGER NOT NULL DEFAULT 10
                        );
                        """
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.warning(f"Could not auto-initialize PostgreSQL schema: {e}")

    def _supabase_headers(self, merge: bool = True) -> Dict[str, str]:
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
        }
        if merge:
            headers["Prefer"] = "resolution=merge-duplicates,return=representation"
        return headers

    def save_job(self, job: JobRecord) -> bool:
        """Save raw job record into Supabase."""
        data = {
            "job_id": job.job_id,
            "source": job.source,
            "url": job.url,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "employment_type": job.employment_type,
            "experience_min": job.experience_min,
            "experience_max": job.experience_max,
            "salary": job.salary,
            "description_raw": job.description_raw,
            "content_hash": job.content_hash,
            "discovered_at": job.discovered_at or datetime.now(timezone.utc).isoformat(),
        }

        if self.backend == "supabase_rest":
            url = f"{self.supabase_url}/rest/v1/jobs"
            resp = requests.post(url, json=data, headers=self._supabase_headers(merge=True))
            return resp.status_code in [200, 201, 204]

        if self.backend == "postgres" and psycopg2:
            conn = psycopg2.connect(self.database_url)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO jobs (job_id, source, url, title, company, location, employment_type, experience_min, experience_max, salary, description_raw, content_hash, discovered_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (job_id) DO NOTHING;
                        """,
                        tuple(data.values()),
                    )
                    conn.commit()
                    return cur.rowcount > 0
            finally:
                conn.close()

        # In-memory fallback
        cursor = self._mem_conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO jobs (
                job_id, source, url, title, company, location, employment_type,
                experience_min, experience_max, salary, description_raw, content_hash, discovered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(data.values()),
        )
        self._mem_conn.commit()
        return cursor.rowcount > 0

    def save_match_report(self, report: MatchReport) -> None:
        """Save match report into Supabase."""
        data = {
            "job_id": report.job_id,
            "overall_score": report.overall_score,
            "score_breakdown_json": json.dumps(report.score_breakdown.to_dict()),
            "matched_reqs_json": json.dumps(report.matched_requirements),
            "missing_reqs_json": json.dumps(report.missing_requirements),
            "recommendation": report.recommendation,
            "reason": report.reason,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if self.backend == "supabase_rest":
            url = f"{self.supabase_url}/rest/v1/match_reports"
            requests.post(url, json=data, headers=self._supabase_headers(merge=True))
            return

        if self.backend == "postgres" and psycopg2:
            conn = psycopg2.connect(self.database_url)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO match_reports (job_id, overall_score, score_breakdown_json, matched_reqs_json, missing_reqs_json, recommendation, reason, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (job_id) DO UPDATE SET
                            overall_score = EXCLUDED.overall_score,
                            score_breakdown_json = EXCLUDED.score_breakdown_json,
                            matched_reqs_json = EXCLUDED.matched_reqs_json,
                            missing_reqs_json = EXCLUDED.missing_reqs_json,
                            recommendation = EXCLUDED.recommendation,
                            reason = EXCLUDED.reason,
                            created_at = EXCLUDED.created_at;
                        """,
                        tuple(data.values()),
                    )
                    conn.commit()
                return
            finally:
                conn.close()

        # In-memory fallback
        cursor = self._mem_conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO match_reports (
                job_id, overall_score, score_breakdown_json, matched_reqs_json, missing_reqs_json, recommendation, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(data.values()),
        )
        self._mem_conn.commit()

    def save_application(self, pkg: ReviewPackage) -> None:
        """Save application package into Supabase."""
        data = {
            "application_id": pkg.application_id,
            "job_id": pkg.job_id,
            "resume_version": Path(pkg.resume_docx_path).stem,
            "match_score": pkg.match_score,
            "status": pkg.status,
            "user_decision": "pending",
            "output_directory": pkg.output_directory,
            "notes": pkg.recommendation,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
            "submitted_at": None,
            "outcome": None,
        }

        if self.backend == "supabase_rest":
            url = f"{self.supabase_url}/rest/v1/applications"
            requests.post(url, json=data, headers=self._supabase_headers(merge=True))
            return

        if self.backend == "postgres" and psycopg2:
            conn = psycopg2.connect(self.database_url)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO applications (application_id, job_id, resume_version, match_score, status, user_decision, output_directory, notes, discovered_at, submitted_at, outcome)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (application_id) DO UPDATE SET
                            match_score = EXCLUDED.match_score,
                            status = EXCLUDED.status,
                            output_directory = EXCLUDED.output_directory,
                            notes = EXCLUDED.notes;
                        """,
                        tuple(data.values()),
                    )
                    conn.commit()
                return
            finally:
                conn.close()

        # In-memory fallback
        cursor = self._mem_conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO applications (
                application_id, job_id, resume_version, match_score, status, user_decision, output_directory, notes, discovered_at, submitted_at, outcome
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(data.values()),
        )
        self._mem_conn.commit()

    def update_decision(self, application_id: str, decision: str, notes: str = "") -> bool:
        """Update user decision for an application."""
        status_map = {
            "apply": "approved_for_manual_apply",
            "applied": "applied_manually",
            "save": "saved_in_queue",
            "reject": "rejected_by_user",
        }
        new_status = status_map.get(decision.lower(), decision)
        submitted_at = datetime.now(timezone.utc).isoformat() if decision.lower() in ["applied", "applied_manually"] else None

        if self.backend == "supabase_rest":
            url = f"{self.supabase_url}/rest/v1/applications?application_id=eq.{application_id}"
            update_data = {
                "user_decision": decision,
                "status": new_status,
            }
            if notes:
                update_data["notes"] = notes
            if submitted_at:
                update_data["submitted_at"] = submitted_at
            resp = requests.patch(url, json=update_data, headers=self._supabase_headers(merge=False))
            return resp.status_code in [200, 204]

        if self.backend == "postgres" and psycopg2:
            conn = psycopg2.connect(self.database_url)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE applications
                        SET user_decision = %s, status = %s, notes = COALESCE(%s, notes), submitted_at = COALESCE(%s, submitted_at)
                        WHERE application_id = %s;
                        """,
                        (decision, new_status, notes or None, submitted_at, application_id),
                    )
                    conn.commit()
                    return cur.rowcount > 0
            finally:
                conn.close()

        # In-memory fallback
        cursor = self._mem_conn.cursor()
        cursor.execute(
            """
            UPDATE applications
            SET user_decision = ?, status = ?, notes = ?, submitted_at = coalesce(?, submitted_at)
            WHERE application_id = ?
            """,
            (decision, new_status, notes, submitted_at, application_id),
        )
        self._mem_conn.commit()
        return cursor.rowcount > 0

    def list_applications(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List applications with job details."""
        if self.backend == "supabase_rest":
            url = f"{self.supabase_url}/rest/v1/applications?select=*,jobs(*)&order=match_score.desc&limit={limit}"
            resp = requests.get(url, headers=self._supabase_headers(merge=False))
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data:
                    job = item.pop("jobs", {}) or {}
                    item["job_title"] = job.get("title", "")
                    item["company"] = job.get("company", "")
                    item["source_url"] = job.get("url", "")
                    results.append(item)
                return results
            return []

        if self.backend == "postgres" and psycopg2:
            conn = psycopg2.connect(self.database_url)
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT a.*, j.title as job_title, j.company as company, j.url as source_url
                        FROM applications a
                        LEFT JOIN jobs j ON a.job_id = j.job_id
                        ORDER BY a.match_score DESC
                        LIMIT %s;
                        """,
                        (limit,),
                    )
                    return [dict(r) for r in cur.fetchall()]
            finally:
                conn.close()

        # In-memory fallback
        cursor = self._mem_conn.cursor()
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
        return [dict(r) for r in cursor.fetchall()]

    def get_application(self, application_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a single application."""
        if self.backend == "supabase_rest":
            url = f"{self.supabase_url}/rest/v1/applications?select=*,jobs(*)&application_id=eq.{application_id}"
            resp = requests.get(url, headers=self._supabase_headers(merge=False))
            if resp.status_code == 200 and resp.json():
                item = resp.json()[0]
                job = item.pop("jobs", {}) or {}
                item["job_title"] = job.get("title", "")
                item["company"] = job.get("company", "")
                item["source_url"] = job.get("url", "")
                item["description_raw"] = job.get("description_raw", "")
                return item
            return None

        if self.backend == "postgres" and psycopg2:
            conn = psycopg2.connect(self.database_url)
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT a.*, j.title as job_title, j.company as company, j.url as source_url, j.description_raw
                        FROM applications a
                        LEFT JOIN jobs j ON a.job_id = j.job_id
                        WHERE a.application_id = %s;
                        """,
                        (application_id,),
                    )
                    row = cur.fetchone()
                    return dict(row) if row else None
            finally:
                conn.close()

        # In-memory fallback
        cursor = self._mem_conn.cursor()
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

    def get_all_missing_requirements(self) -> List[List[str]]:
        """Fetch all missing requirement lists from match reports for skill gap analytics."""
        if self.backend == "supabase_rest":
            url = f"{self.supabase_url}/rest/v1/match_reports?select=missing_reqs_json"
            resp = requests.get(url, headers=self._supabase_headers(merge=False))
            if resp.status_code == 200:
                results = []
                for item in resp.json():
                    val = item.get("missing_reqs_json")
                    if isinstance(val, str):
                        try:
                            results.append(json.loads(val))
                        except Exception:
                            pass
                    elif isinstance(val, list):
                        results.append(val)
                return results
            return []

        if self.backend == "postgres" and psycopg2:
            conn = psycopg2.connect(self.database_url)
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT missing_reqs_json FROM match_reports;")
                    results = []
                    for r in cur.fetchall():
                        val = r[0]
                        if isinstance(val, str):
                            try:
                                results.append(json.loads(val))
                            except Exception:
                                pass
                        elif isinstance(val, list):
                            results.append(val)
                    return results
            finally:
                conn.close()

        # In-memory fallback
        cursor = self._mem_conn.cursor()
        cursor.execute("SELECT missing_reqs_json FROM match_reports")
        results = []
        for r in cursor.fetchall():
            try:
                results.append(json.loads(r[0]))
            except Exception:
                pass
        return results

    # ------------------------------------------------------------------
    # Daily completion counter
    # ------------------------------------------------------------------

    def get_today_count(self) -> int:
        """Return the number of successfully completed resumes for today (UTC)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if self.backend == "supabase_rest":
            url = f"{self.supabase_url}/rest/v1/daily_completion?date=eq.{today}&select=count"
            try:
                resp = requests.get(url, headers=self._supabase_headers(merge=False), timeout=10)
                if resp.status_code == 200 and resp.json():
                    return int(resp.json()[0].get("count", 0))
            except Exception as exc:
                logger.warning("Could not fetch daily count from Supabase: %s", exc)
            return 0

        if self.backend == "postgres" and psycopg2:
            try:
                conn = psycopg2.connect(self.database_url)
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT count FROM daily_completion WHERE date = %s;",
                            (today,),
                        )
                        row = cur.fetchone()
                        return int(row[0]) if row else 0
                finally:
                    conn.close()
            except Exception as exc:
                logger.warning("Could not fetch daily count from PostgreSQL: %s", exc)
            return 0

        # In-memory fallback
        cursor = self._mem_conn.cursor()
        cursor.execute("SELECT count FROM daily_completion WHERE date = ?", (today,))
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    def increment_completion(self, daily_limit: int = 10) -> int:
        """Atomically increment today's completion counter.

        Inserts a row for today if one does not exist yet, then increments.
        Returns the updated count *after* increment.  When the count reaches
        *daily_limit* the caller should fire a completion notification.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if self.backend == "supabase_rest":
            # Upsert: insert with count=1 or increment existing count
            upsert_url = f"{self.supabase_url}/rest/v1/daily_completion"
            current = self.get_today_count()
            new_count = current + 1
            payload = {"date": today, "count": new_count, "limit_val": daily_limit}
            try:
                resp = requests.post(
                    upsert_url,
                    json=payload,
                    headers=self._supabase_headers(merge=True),
                    timeout=10,
                )
                if resp.status_code not in (200, 201, 204):
                    logger.warning("Supabase upsert for daily_completion failed: %s", resp.text[:200])
            except Exception as exc:
                logger.warning("Could not increment daily count in Supabase: %s", exc)
            return new_count

        if self.backend == "postgres" and psycopg2:
            try:
                conn = psycopg2.connect(self.database_url)
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO daily_completion (date, count, limit_val)
                            VALUES (%s, 1, %s)
                            ON CONFLICT (date) DO UPDATE
                                SET count = daily_completion.count + 1,
                                    limit_val = EXCLUDED.limit_val
                            RETURNING count;
                            """,
                            (today, daily_limit),
                        )
                        new_count = cur.fetchone()[0]
                        conn.commit()
                        return int(new_count)
                finally:
                    conn.close()
            except Exception as exc:
                logger.warning("Could not increment daily count in PostgreSQL: %s", exc)
                return self.get_today_count()

        # In-memory SQLite fallback (atomic via Python-level GIL for single process)
        cursor = self._mem_conn.cursor()
        cursor.execute(
            """
            INSERT INTO daily_completion (date, count, limit_val)
            VALUES (?, 1, ?)
            ON CONFLICT(date) DO UPDATE SET count = count + 1, limit_val = excluded.limit_val
            """,
            (today, daily_limit),
        )
        self._mem_conn.commit()
        cursor.execute("SELECT count FROM daily_completion WHERE date = ?", (today,))
        return int(cursor.fetchone()[0])
