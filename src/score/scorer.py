"""Deterministic Match Scoring Engine."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from src.config import AppSettings, load_yaml_config
from src.models.job import ParsedJob
from src.models.profile import CandidateProfile
from src.models.score import MatchReport, ScoreBreakdown

logger = logging.getLogger(__name__)


class MatchScorer:
    """Calculates transparent, reproducible match scores against candidate profile."""

    def __init__(self, settings: Optional[AppSettings] = None):
        self.settings = settings or AppSettings()
        self.scoring_config = load_yaml_config(self.settings.scoring_config_path)
        self.target_config = load_yaml_config(self.settings.target_profile_path)
        self.weights = self.scoring_config.get(
            "weights",
            {
                "title_role_fit": 0.20,
                "required_skills": 0.25,
                "platform_tools": 0.15,
                "experience_fit": 0.15,
                "industry_fit": 0.10,
                "location_fit": 0.05,
                "achievement_relevance": 0.10,
            },
        )
        self.synonyms = self.scoring_config.get("synonyms", {})

    def score(self, job: ParsedJob, candidate: CandidateProfile) -> MatchReport:
        """Score a parsed job against candidate profile facts."""
        matched_reqs: List[str] = []
        missing_reqs: List[str] = []
        uncertain_reqs: List[str] = list(job.uncertainties)
        negative_flags: List[str] = []

        # 1. Title Fit (20%)
        title_score = self._score_title(job.title, candidate)

        # 2. Required Skills Fit (25%)
        skills_score, matched_skills, missing_skills = self._score_skills(job.must_have_skills, candidate)
        matched_reqs.extend(matched_skills)
        missing_reqs.extend(missing_skills)

        # 3. Platform & Tools Fit (15%)
        tools_score, matched_tools, missing_tools = self._score_tools(job.platforms_and_tools, candidate)
        matched_reqs.extend(matched_tools)
        missing_reqs.extend(missing_tools)

        # 4. Experience Fit (15%)
        exp_score = self._score_experience(job.experience_min, job.experience_max, candidate.experience_years)
        if job.experience_min is not None and job.experience_min > candidate.experience_years:
            missing_reqs.append(f"Requires {job.experience_min}+ yrs experience (Candidate has {candidate.experience_years} yrs)")

        # 5. Industry Fit (10%)
        industry_score = self._score_industry(job, candidate)

        # 6. Location / Work Mode Fit (5%)
        loc_score = self._score_location(job.location, candidate)

        # 7. Achievement Relevance (10%)
        ach_score = self._score_achievements(job, candidate)

        # 8. Check Negative Constraints
        negative_flags = self._check_negative_constraints(job, candidate)

        # Calculate weighted overall score
        w = self.weights
        overall = (
            title_score * w.get("title_role_fit", 0.20)
            + skills_score * w.get("required_skills", 0.25)
            + tools_score * w.get("platform_tools", 0.15)
            + exp_score * w.get("experience_fit", 0.15)
            + industry_score * w.get("industry_fit", 0.10)
            + loc_score * w.get("location_fit", 0.05)
            + ach_score * w.get("achievement_relevance", 0.10)
        )

        # Penalize for negative constraint violations
        if negative_flags:
            overall = max(0.0, overall - (35.0 * len(negative_flags)))

        # Determine Recommendation
        thresholds = self.scoring_config.get("thresholds", {})
        auto_gen_thresh = thresholds.get("auto_generate_resume", 80.0)
        medium_fit_thresh = thresholds.get("medium_fit_review", 65.0)

        if negative_flags or overall < 50.0:
            recommendation = "reject"
            reason = "Job conflicts with candidate constraints or has low relevance (< 50%)."
            if negative_flags:
                reason += f" Negative flags: {'; '.join(negative_flags)}"
        elif overall >= auto_gen_thresh:
            recommendation = "apply_review"
            reason = f"Strong fit ({round(overall, 1)}/100). Verified skills and experience closely align with role requirements."
        elif overall >= medium_fit_thresh:
            recommendation = "save"
            reason = f"Moderate fit ({round(overall, 1)}/100). Meets core skills with minor gaps in specific tooling or experience."
        else:
            recommendation = "save"
            reason = f"Research queue ({round(overall, 1)}/100). Keep in watch list."

        breakdown = ScoreBreakdown(
            title_role_fit=title_score,
            required_skills=skills_score,
            platform_tools=tools_score,
            experience_fit=exp_score,
            industry_fit=industry_score,
            location_fit=loc_score,
            achievement_relevance=ach_score,
        )

        return MatchReport(
            job_id=job.job_id,
            overall_score=round(overall, 1),
            score_breakdown=breakdown,
            matched_requirements=list(dict.fromkeys(matched_reqs)),
            missing_requirements=list(dict.fromkeys(missing_reqs)),
            uncertain_requirements=list(dict.fromkeys(uncertain_reqs)),
            negative_constraint_flags=negative_flags,
            recommendation=recommendation,
            reason=reason,
        )

    def _score_title(self, job_title: str, candidate: CandidateProfile) -> float:
        """Score job title alignment with candidate target roles."""
        jt = job_title.lower()

        # Check for completely irrelevant roles (software engineer, sales, legal, etc.)
        irrelevant_tokens = {"java", "backend", "frontend", "devops", "kubernetes", "golang", "c++", "mechanical"}
        title_tokens = set(re.findall(r"\w+", jt))
        if irrelevant_tokens.intersection(title_tokens):
            return 0.0

        # Direct exact or substring match with target roles
        for role in candidate.target_roles:
            r_lower = role.lower()
            if r_lower in jt or jt in r_lower:
                return 100.0

        # Partial token match for marketing roles
        marketing_tokens = {"performance", "digital", "growth", "paid", "ppc", "media", "acquisition", "sem", "marketing"}
        overlap = marketing_tokens.intersection(title_tokens)

        if len(overlap) >= 2:
            return 90.0
        elif len(overlap) == 1:
            return 60.0
        return 20.0

    def _score_skills(self, required_skills: List[str], candidate: CandidateProfile) -> Tuple[float, List[str], List[str]]:
        """Score required skills match against candidate skills and tools."""
        if not required_skills:
            return 80.0, [], []

        matched = []
        missing = []
        candidate_corpus = [s.lower() for s in (candidate.skills + candidate.tools)]

        for req in required_skills:
            req_l = req.lower()
            is_matched = False

            # Direct match
            if req_l in candidate_corpus:
                matched.append(req)
                continue

            # Synonym match
            for group, syns in self.synonyms.items():
                syns_lower = [s.lower() for s in syns]
                if req_l in syns_lower:
                    if any(s in candidate_corpus or any(s in c for c in candidate_corpus) for s in syns_lower):
                        matched.append(req)
                        is_matched = True
                        break
            if is_matched:
                continue

            # Substring match
            if any(req_l in c or c in req_l for c in candidate_corpus):
                matched.append(req)
            else:
                missing.append(req)

        match_ratio = len(matched) / len(required_skills)
        return match_ratio * 100.0, matched, missing

    def _score_tools(self, required_tools: List[str], candidate: CandidateProfile) -> Tuple[float, List[str], List[str]]:
        """Score platform and tool alignment."""
        if not required_tools:
            return 85.0, [], []

        matched = []
        missing = []
        candidate_tools_lower = [t.lower() for t in candidate.tools]

        for tool in required_tools:
            tool_l = tool.lower()
            is_matched = False

            if tool_l in candidate_tools_lower:
                matched.append(tool)
                continue

            # Synonym check
            for group, syns in self.synonyms.items():
                syns_lower = [s.lower() for s in syns]
                if tool_l in syns_lower:
                    if any(t in candidate_tools_lower or any(t in ct for ct in candidate_tools_lower) for t in syns_lower):
                        matched.append(tool)
                        is_matched = True
                        break
            if is_matched:
                continue

            if any(tool_l in ct or ct in tool_l for ct in candidate_tools_lower):
                matched.append(tool)
            else:
                missing.append(tool)

        match_ratio = len(matched) / len(required_tools)
        return match_ratio * 100.0, matched, missing

    def _score_experience(self, exp_min: Optional[float], exp_max: Optional[float], candidate_years: float) -> float:
        """Score experience range fit."""
        if exp_min is None and exp_max is None:
            return 85.0

        if exp_min is not None and exp_max is not None:
            if exp_min <= candidate_years <= exp_max:
                return 100.0
            if candidate_years < exp_min:
                diff = exp_min - candidate_years
                return max(0.0, 100.0 - (diff * 30.0))
            if candidate_years > exp_max:
                diff = candidate_years - exp_max
                return max(50.0, 100.0 - (diff * 15.0))

        if exp_min is not None:
            if candidate_years >= exp_min:
                return 100.0
            diff = exp_min - candidate_years
            return max(0.0, 100.0 - (diff * 35.0))

        return 85.0

    def _score_industry(self, job: ParsedJob, candidate: CandidateProfile) -> float:
        """Score industry relevance (B2C, D2C, B2B SaaS)."""
        jt_desc = f"{job.title} {job.company} {' '.join(job.responsibilities)}".lower()
        relevant_domains = ["ecommerce", "e-commerce", "d2c", "b2b", "saas", "fintech", "edtech", "agency", "tech", "growth"]
        matches = [d for d in relevant_domains if d in jt_desc]
        if matches:
            return 95.0
        return 75.0

    def _score_location(self, job_loc: str, candidate: CandidateProfile) -> float:
        """Score location and remote / hybrid fit."""
        if not job_loc:
            return 85.0
        loc_l = job_loc.lower()
        if "remote" in loc_l or "hybrid" in loc_l or "bengaluru" in loc_l or "bangalore" in loc_l:
            return 100.0
        pref_cities = ["mumbai", "delhi", "gurugram", "noida", "pune", "hyderabad"]
        if any(c in loc_l for c in pref_cities):
            return 90.0
        return 65.0

    def _score_achievements(self, job: ParsedJob, candidate: CandidateProfile) -> float:
        """Score relevance of candidate achievements to required job outcomes."""
        all_job_text = f"{' '.join(job.must_have_skills)} {' '.join(job.platforms_and_tools)} {' '.join(job.responsibilities)}".lower()
        relevant_count = 0
        for ach in candidate.achievements:
            ach_text = f"{ach.statement} {ach.metric}".lower()
            if any(k in ach_text and k in all_job_text for k in ["roas", "cac", "google", "meta", "ga4", "gtm", "scale", "cro"]):
                relevant_count += 1
        ratio = relevant_count / max(1, len(candidate.achievements))
        return min(100.0, 70.0 + (ratio * 30.0))

    def _check_negative_constraints(self, job: ParsedJob, candidate: CandidateProfile) -> List[str]:
        """Check whether the job strictly demands prohibited / unheld skills."""
        flags = []
        job_full_text = f"{job.title} {' '.join(job.must_have_skills)} {' '.join(job.platforms_and_tools)}".lower()

        for constraint in candidate.negative_constraints:
            c_lower = constraint.lower()
            if "salesforce" in c_lower and "salesforce" in job_full_text:
                flags.append("Violates constraint: Candidate has never used Salesforce Marketing Cloud")
            if "marketo" in c_lower and "marketo" in job_full_text:
                flags.append("Violates constraint: Candidate has never used Marketo")
            if "dv360" in c_lower and ("dv360" in job_full_text or "display & video 360" in job_full_text):
                flags.append("Violates constraint: Candidate has never used DV360 programmatic platform")
            if "trade desk" in c_lower and "trade desk" in job_full_text:
                flags.append("Violates constraint: Candidate has never used The Trade Desk")

        if job.experience_min and job.experience_min >= 5.0 and candidate.experience_years <= 3.0:
            flags.append(f"Seniority gap: Job requires {job.experience_min}+ yrs experience; candidate has {candidate.experience_years} yrs")

        return flags
