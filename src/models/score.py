"""Deterministic Match Scoring Data Models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ScoreBreakdown:
    title_role_fit: float
    required_skills: float
    platform_tools: float
    experience_fit: float
    industry_fit: float
    location_fit: float
    achievement_relevance: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "title_role_fit": round(self.title_role_fit, 2),
            "required_skills": round(self.required_skills, 2),
            "platform_tools": round(self.platform_tools, 2),
            "experience_fit": round(self.experience_fit, 2),
            "industry_fit": round(self.industry_fit, 2),
            "location_fit": round(self.location_fit, 2),
            "achievement_relevance": round(self.achievement_relevance, 2),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ScoreBreakdown:
        return cls(
            title_role_fit=float(data.get("title_role_fit", 0.0)),
            required_skills=float(data.get("required_skills", 0.0)),
            platform_tools=float(data.get("platform_tools", 0.0)),
            experience_fit=float(data.get("experience_fit", 0.0)),
            industry_fit=float(data.get("industry_fit", 0.0)),
            location_fit=float(data.get("location_fit", 0.0)),
            achievement_relevance=float(data.get("achievement_relevance", 0.0)),
        )


@dataclass
class MatchReport:
    job_id: str
    overall_score: float
    score_breakdown: ScoreBreakdown
    matched_requirements: List[str] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)
    uncertain_requirements: List[str] = field(default_factory=list)
    negative_constraint_flags: List[str] = field(default_factory=list)
    recommendation: str = "review"  # "apply_review", "save", "reject"
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "overall_score": round(self.overall_score, 1),
            "score_breakdown": self.score_breakdown.to_dict(),
            "matched_requirements": self.matched_requirements,
            "missing_requirements": self.missing_requirements,
            "uncertain_requirements": self.uncertain_requirements,
            "negative_constraint_flags": self.negative_constraint_flags,
            "recommendation": self.recommendation,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MatchReport:
        return cls(
            job_id=data.get("job_id", ""),
            overall_score=float(data.get("overall_score", 0.0)),
            score_breakdown=ScoreBreakdown.from_dict(data.get("score_breakdown", {})),
            matched_requirements=data.get("matched_requirements", []),
            missing_requirements=data.get("missing_requirements", []),
            uncertain_requirements=data.get("uncertain_requirements", []),
            negative_constraint_flags=data.get("negative_constraint_flags", []),
            recommendation=data.get("recommendation", "save"),
            reason=data.get("reason", ""),
        )
