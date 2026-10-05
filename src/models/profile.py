"""Candidate Profile and Fact Registry Data Models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ContactInfo:
    email: str
    phone: str
    location: str
    linkedin: str = ""
    portfolio: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ContactInfo:
        return cls(
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            location=data.get("location", ""),
            linkedin=data.get("linkedin", ""),
            portfolio=data.get("portfolio", ""),
        )


@dataclass
class Achievement:
    id: str
    statement: str
    metric: str
    time_period: str
    evidence: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Achievement:
        return cls(
            id=data.get("id", ""),
            statement=data.get("statement", ""),
            metric=data.get("metric", ""),
            time_period=data.get("time_period", ""),
            evidence=data.get("evidence", ""),
        )


@dataclass
class Employment:
    company: str
    title: str
    location: str
    start_date: str
    end_date: str
    is_current: bool = False
    responsibilities: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Employment:
        return cls(
            company=data.get("company", ""),
            title=data.get("title", ""),
            location=data.get("location", ""),
            start_date=data.get("start_date", ""),
            end_date=data.get("end_date", ""),
            is_current=data.get("is_current", False),
            responsibilities=data.get("responsibilities", []),
        )


@dataclass
class Education:
    institution: str
    degree: str
    start_year: int
    end_year: int
    grade: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Education:
        return cls(
            institution=data.get("institution", ""),
            degree=data.get("degree", ""),
            start_year=data.get("start_year", 0),
            end_year=data.get("end_year", 0),
            grade=data.get("grade", ""),
        )


@dataclass
class Certification:
    name: str
    issuer: str
    date: str
    url: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Certification:
        return cls(
            name=data.get("name", ""),
            issuer=data.get("issuer", ""),
            date=data.get("date", ""),
            url=data.get("url", ""),
        )


@dataclass
class CandidateProfile:
    candidate_id: str
    full_name: str
    headline: str
    contact: ContactInfo
    target_roles: List[str]
    experience_years: float
    location: str
    work_authorization: str
    summary_facts: List[str]
    skills: List[str]
    tools: List[str]
    achievements: List[Achievement]
    employment: List[Employment]
    education: List[Education]
    certifications: List[Certification]
    links: List[Dict[str, str]] = field(default_factory=list)
    negative_constraints: List[str] = field(default_factory=list)
    notice_period_days: int = 30
    current_ctc_lpa: Optional[float] = None
    expected_ctc_lpa: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CandidateProfile:
        return cls(
            candidate_id=data.get("candidate_id", "cand-default"),
            full_name=data.get("full_name", ""),
            headline=data.get("headline", ""),
            contact=ContactInfo.from_dict(data.get("contact", {})),
            target_roles=data.get("target_roles", []),
            experience_years=float(data.get("experience_years", 0.0)),
            location=data.get("location", ""),
            work_authorization=data.get("work_authorization", ""),
            summary_facts=data.get("summary_facts", []),
            skills=data.get("skills", []),
            tools=data.get("tools", []),
            achievements=[Achievement.from_dict(a) for a in data.get("achievements", [])],
            employment=[Employment.from_dict(e) for e in data.get("employment", [])],
            education=[Education.from_dict(ed) for ed in data.get("education", [])],
            certifications=[Certification.from_dict(c) for c in data.get("certifications", [])],
            links=data.get("links", []),
            negative_constraints=data.get("negative_constraints", []),
            notice_period_days=data.get("notice_period_days", 30),
            current_ctc_lpa=data.get("current_ctc_lpa"),
            expected_ctc_lpa=data.get("expected_ctc_lpa"),
        )

    def to_fact_registry(self) -> Dict[str, Any]:
        """Convert candidate facts into an auditable registry."""
        return {
            "full_name": self.full_name,
            "experience_years": self.experience_years,
            "employers": [e.company for e in self.employment],
            "roles": [e.title for e in self.employment],
            "skills": self.skills,
            "tools": self.tools,
            "certifications": [c.name for c in self.certifications],
            "achievement_metrics": [a.metric for a in self.achievements],
            "negative_constraints": self.negative_constraints,
        }
