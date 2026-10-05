"""Job Sources and Ingestion Manager."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request
from src.ingest.normalizer import normalize_job_text, compute_content_hash
from src.models.job import JobRecord

logger = logging.getLogger(__name__)


class IngestionManager:
    """Manages ingestion of jobs from manual text, files, URLs, and exports."""

    @staticmethod
    def from_text(
        text: str,
        title: str = "Target Marketing Role",
        company: str = "Target Company",
        url: str = "",
        source: str = "manual_paste",
    ) -> JobRecord:
        """Create a JobRecord from raw pasted job description text."""
        cleaned_text = normalize_job_text(text)
        return JobRecord(
            job_id="",
            source=source,
            url=url,
            title=title,
            company=company,
            location="",
            description_raw=cleaned_text,
            content_hash=compute_content_hash(cleaned_text),
            source_evidence="User pasted job text",
        )

    @classmethod
    def from_file(cls, file_path: Path) -> List[JobRecord]:
        """Ingest job(s) from a local file (JSON, Markdown, TXT, or CSV)."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        ext = path.suffix.lower()

        if ext == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [JobRecord.from_dict(item) for item in data]
            elif isinstance(data, dict):
                return [JobRecord.from_dict(data)]
            else:
                raise ValueError("JSON file must contain an object or a list of objects.")

        elif ext in [".txt", ".md"]:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            cleaned = normalize_job_text(content)
            title = path.stem.replace("-", " ").replace("_", " ").title()
            return [
                JobRecord(
                    job_id="",
                    source="file_import",
                    url=str(path),
                    title=title,
                    company="Exported Job Listing",
                    location="",
                    description_raw=cleaned,
                    content_hash=compute_content_hash(cleaned),
                    source_evidence=f"Imported from {path.name}",
                )
            ]

        elif ext == ".csv":
            jobs = []
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    desc = row.get("description", "") or row.get("job_description", "")
                    title = row.get("title", "") or row.get("job_title", "Marketing Specialist")
                    company = row.get("company", "") or row.get("company_name", "Company")
                    url = row.get("url", "") or row.get("job_url", "")
                    cleaned = normalize_job_text(desc)
                    jobs.append(
                        JobRecord(
                            job_id="",
                            source="csv_import",
                            url=url,
                            title=title,
                            company=company,
                            location=row.get("location", ""),
                            description_raw=cleaned,
                            content_hash=compute_content_hash(cleaned),
                            source_evidence=f"Imported from CSV row",
                        )
                    )
            return jobs

        else:
            raise ValueError(f"Unsupported file format: {ext}. Supported: .json, .txt, .md, .csv")

    @classmethod
    def from_url(cls, url: str) -> JobRecord:
        """Fetch and ingest job text from a public job URL."""
        parsed_url = urllib.parse.urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Invalid URL: {url}")

        source_platform = "naukri" if "naukri.com" in parsed_url.netloc else "web_url"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                html_content = response.read().decode(charset, errors="ignore")
        except Exception as e:
            logger.warning(f"Could not automatically fetch URL {url}: {e}")
            return JobRecord(
                job_id="",
                source=source_platform,
                url=url,
                title="Job from URL (Review Required)",
                company="External Employer",
                location="",
                description_raw=f"Job listing fetched from {url}. (Direct fetch encountered: {e}. Please paste job text if behind login).",
                source_evidence=f"Attempted fetch from {url}",
            )

        cleaned_text = normalize_job_text(html_content)

        return JobRecord(
            job_id="",
            source=source_platform,
            url=url,
            title="Imported Marketing Role",
            company="Employer via " + parsed_url.netloc,
            location="",
            description_raw=cleaned_text,
            content_hash=compute_content_hash(cleaned_text),
            source_evidence=f"Publicly fetched from {url}",
        )
