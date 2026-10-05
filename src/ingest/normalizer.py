"""Job Text Normalization and Deduplication."""

from __future__ import annotations

import hashlib
import re
from typing import List, Set
from src.models.job import JobRecord


def normalize_job_text(raw_text: str) -> str:
    """Clean raw job text by removing HTML tags, excess whitespace, and scripts."""
    if not raw_text:
        return ""

    # Remove script and style elements
    text = re.sub(r"<script[^>]*>.*?</script>", " ", raw_text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Normalize HTML entities
    text = text.replace("&amp;", "&").replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")

    # Normalize multiple newlines and spaces
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def compute_content_hash(text: str) -> str:
    """Generate SHA256 hash of normalized text for duplicate detection."""
    clean = re.sub(r"\s+", "", text.lower())
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


def deduplicate_jobs(jobs: List[JobRecord]) -> List[JobRecord]:
    """Deduplicate job records based on URL, company/title, and content hash."""
    seen_urls: Set[str] = set()
    seen_keys: Set[str] = set()
    seen_hashes: Set[str] = set()
    unique_jobs: List[JobRecord] = []

    for job in jobs:
        # Check by URL
        if job.url and job.url in seen_urls:
            continue

        # Check by content hash
        if job.content_hash and job.content_hash in seen_hashes:
            continue

        # Check by company + title key
        key = f"{job.company.strip().lower()}::{job.title.strip().lower()}"
        if key in seen_keys:
            continue

        if job.url:
            seen_urls.add(job.url)
        if job.content_hash:
            seen_hashes.add(job.content_hash)
        seen_keys.add(key)
        unique_jobs.append(job)

    return unique_jobs
