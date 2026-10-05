"""Job Ingestion and Parsed Job Data Models."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class JobRecord:
    """Raw ingested job record."""
    job_id: str
    source: str
    url: str
    title: str
    company: str
    location: str
    description_raw: str
    employment_type: str = "Full Time"
    experience_min: Optional[float] = None
    experience_max: Optional[float] = None
    salary: Optional[str] = None
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    content_hash: str = ""
    source_evidence: str = ""

    def __post_init__(self):
        if not self.content_hash:
            raw = f"{self.title}_{self.company}_{self.description_raw}"
            self.content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if not self.job_id:
            raw_id = f"{self.source}_{self.url}_{self.title}_{self.company}"
            self.job_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JobRecord:
        return cls(
            job_id=data.get("job_id", ""),
            source=data.get("source", "manual"),
            url=data.get("url", ""),
            title=data.get("title", "Untitled Role"),
            company=data.get("company", "Unknown Company"),
            location=data.get("location", ""),
            description_raw=data.get("description_raw", ""),
            employment_type=data.get("employment_type", "Full Time"),
            experience_min=data.get("experience_min"),
            experience_max=data.get("experience_max"),
            salary=data.get("salary"),
            discovered_at=data.get("discovered_at", datetime.now(timezone.utc).isoformat()),
            content_hash=data.get("content_hash", ""),
            source_evidence=data.get("source_evidence", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "source": self.source,
            "url": self.url,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "employment_type": self.employment_type,
            "experience_min": self.experience_min,
            "experience_max": self.experience_max,
            "salary": self.salary,
            "description_raw": self.description_raw,
            "discovered_at": self.discovered_at,
            "content_hash": self.content_hash,
            "source_evidence": self.source_evidence,
        }


@dataclass
class ParsedJob:
    """Normalized and parsed job representation."""
    job_id: str
    title: str
    company: str
    location: str
    employment_type: str
    experience_min: Optional[float]
    experience_max: Optional[float]
    salary: Optional[str]
    must_have_skills: List[str] = field(default_factory=list)
    nice_to_have_skills: List[str] = field(default_factory=list)
    platforms_and_tools: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    education_requirements: List[str] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    uncertainties: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], job_id: str = "") -> ParsedJob:
        return cls(
            job_id=data.get("job_id", job_id),
            title=data.get("title", ""),
            company=data.get("company", ""),
            location=data.get("location", ""),
            employment_type=data.get("employment_type", "Full Time"),
            experience_min=data.get("experience_min"),
            experience_max=data.get("experience_max"),
            salary=data.get("salary"),
            must_have_skills=data.get("must_have_skills", []),
            nice_to_have_skills=data.get("nice_to_have_skills", []),
            platforms_and_tools=data.get("platforms_and_tools", []),
            responsibilities=data.get("responsibilities", []),
            education_requirements=data.get("education_requirements", []),
            certifications=data.get("certifications", []),
            keywords=data.get("keywords", []),
            uncertainties=data.get("uncertainties", []),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "employment_type": self.employment_type,
            "experience_min": self.experience_min,
            "experience_max": self.experience_max,
            "salary": self.salary,
            "must_have_skills": self.must_have_skills,
            "nice_to_have_skills": self.nice_to_have_skills,
            "platforms_and_tools": self.platforms_and_tools,
            "responsibilities": self.responsibilities,
            "education_requirements": self.education_requirements,
            "certifications": self.certifications,
            "keywords": self.keywords,
            "uncertainties": self.uncertainties,
        }
