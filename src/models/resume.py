"""Tailored Resume and Validation Report Models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ResumeRole:
    company: str
    title: str
    location: str
    period: str
    bullets: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company": self.company,
            "title": self.title,
            "location": self.location,
            "period": self.period,
            "bullets": self.bullets,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ResumeRole:
        return cls(
            company=data.get("company", ""),
            title=data.get("title", ""),
            location=data.get("location", ""),
            period=data.get("period", ""),
            bullets=data.get("bullets", []),
        )


@dataclass
class TailoredResume:
    resume_version_id: str
    candidate_id: str
    job_id: str
    summary: str
    skills: List[str]
    experience: List[ResumeRole]
    education: List[Dict[str, Any]]
    certifications: List[Dict[str, Any]]
    gap_list: List[str] = field(default_factory=list)
    change_log: List[str] = field(default_factory=list)
    factuality_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resume_version_id": self.resume_version_id,
            "candidate_id": self.candidate_id,
            "job_id": self.job_id,
            "summary": self.summary,
            "skills": self.skills,
            "experience": [e.to_dict() for e in self.experience],
            "education": self.education,
            "certifications": self.certifications,
            "gap_list": self.gap_list,
            "change_log": self.change_log,
            "factuality_notes": self.factuality_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TailoredResume:
        return cls(
            resume_version_id=data.get("resume_version_id", ""),
            candidate_id=data.get("candidate_id", ""),
            job_id=data.get("job_id", ""),
            summary=data.get("summary", ""),
            skills=data.get("skills", []),
            experience=[ResumeRole.from_dict(r) for r in data.get("experience", [])],
            education=data.get("education", []),
            certifications=data.get("certifications", []),
            gap_list=data.get("gap_list", []),
            change_log=data.get("change_log", []),
            factuality_notes=data.get("factuality_notes", []),
        )


@dataclass
class ValidationReport:
    resume_version_id: str
    job_id: str
    passed: bool
    factuality_errors: List[str] = field(default_factory=list)
    unsupported_claims: List[str] = field(default_factory=list)
    ats_warnings: List[str] = field(default_factory=list)
    keyword_stuffing_warnings: List[str] = field(default_factory=list)
    missing_sections: List[str] = field(default_factory=list)
    readability_warnings: List[str] = field(default_factory=list)
    required_fixes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resume_version_id": self.resume_version_id,
            "job_id": self.job_id,
            "passed": self.passed,
            "factuality_errors": self.factuality_errors,
            "unsupported_claims": self.unsupported_claims,
            "ats_warnings": self.ats_warnings,
            "keyword_stuffing_warnings": self.keyword_stuffing_warnings,
            "missing_sections": self.missing_sections,
            "readability_warnings": self.readability_warnings,
            "required_fixes": self.required_fixes,
        }


@dataclass
class ReviewPackage:
    application_id: str
    job_id: str
    job_title: str
    company: str
    source_url: str
    match_score: float
    recommendation: str
    output_directory: str
    resume_md_path: str
    resume_docx_path: str
    resume_pdf_path: str
    cover_note_path: str
    match_report_path: str
    validation_report_path: str
    change_log_path: str
    status: str = "review_pending"  # "review_pending", "approved", "rejected", "applied_manually"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "application_id": self.application_id,
            "job_id": self.job_id,
            "job_title": self.job_title,
            "company": self.company,
            "source_url": self.source_url,
            "match_score": self.match_score,
            "recommendation": self.recommendation,
            "output_directory": self.output_directory,
            "resume_md_path": self.resume_md_path,
            "resume_docx_path": self.resume_docx_path,
            "resume_pdf_path": self.resume_pdf_path,
            "cover_note_path": self.cover_note_path,
            "match_report_path": self.match_report_path,
            "validation_report_path": self.validation_report_path,
            "change_log_path": self.change_log_path,
            "status": self.status,
        }
