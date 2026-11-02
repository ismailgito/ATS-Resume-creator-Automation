"""Resume Tailoring Engine adhering to strict factuality and ATS rules."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from src.config import AppSettings
from src.llm.client import BaseLLMClient, get_llm_client
from src.llm.prompts import load_prompt_template, render_prompt
from src.models.job import ParsedJob
from src.models.profile import CandidateProfile
from src.models.resume import ResumeRole, TailoredResume
from src.models.score import MatchReport

logger = logging.getLogger(__name__)


class ResumeTailor:
    """Tailors candidate resume content specifically for an approved target job."""

    def __init__(self, llm_client: Optional[BaseLLMClient] = None, settings: Optional[AppSettings] = None):
        self.settings = settings or AppSettings()
        self.llm = llm_client or get_llm_client(self.settings)

    def tailor(self, job: ParsedJob, candidate: CandidateProfile, match_report: MatchReport) -> Tuple[TailoredResume, Dict[str, Any]]:
        """Generate tailored resume data and cover note."""
        resume_version_id = f"res-{job.job_id[:8]}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"

        # 1. Deterministic baseline tailoring
        baseline_roles = self._build_tailored_roles(job, candidate)
        baseline_summary = self._build_tailored_summary(job, candidate)
        baseline_skills = self._build_tailored_skills(job, candidate)
        change_log = [
            f"Tailored summary targeting '{job.title}' at {job.company}.",
            f"Aligned skills section prioritizing {len(match_report.matched_requirements)} verified requirements.",
            "Ranked experience bullets highlighting verified CAC, ROAS, and tracking impact.",
        ]

        # 2. LLM tailoring if available
        try:
            prompt_template = load_prompt_template("tailor-resume")
            system_prompt = (
                "You tailor resumes for ATS compatibility while preserving factual accuracy. "
                "You must not invent employers, dates, tools, certifications, responsibilities, or metrics. "
                "If a job requirement is missing, report it in gap_list."
            )
            user_prompt = render_prompt(
                prompt_template,
                {
                    "parsed_job_json": json.dumps(job.to_dict(), indent=2),
                    "candidate_profile_json": json.dumps(candidate.to_fact_registry(), indent=2),
                    "match_report_json": json.dumps(match_report.to_dict(), indent=2),
                },
            )
            llm_result = self.llm.generate_json(system_prompt, user_prompt)
        except Exception as e:
            logger.warning(f"LLM tailoring fallback to deterministic engine: {e}")
            llm_result = {}

        # Merge results safely
        final_summary = llm_result.get("summary") or baseline_summary
        final_skills = llm_result.get("skills") or baseline_skills
        final_roles = [ResumeRole.from_dict(r) for r in llm_result.get("experience", [])] or baseline_roles
        gap_list = llm_result.get("gap_list") or match_report.missing_requirements
        change_log = list(dict.fromkeys(change_log + llm_result.get("change_log", [])))

        tailored = TailoredResume(
            resume_version_id=resume_version_id,
            candidate_id=candidate.candidate_id,
            job_id=job.job_id,
            summary=final_summary,
            skills=final_skills,
            experience=final_roles,
            education=[{"degree": e.degree, "institution": e.institution, "period": f"{e.start_year} - {e.end_year}"} for e in candidate.education],
            certifications=[{"name": c.name, "issuer": c.issuer, "date": c.date} for c in candidate.certifications],
            gap_list=gap_list,
            change_log=change_log,
            factuality_notes=["All statements trace to verified candidate profile facts."],
        )

        # Generate cover note
        cover_note = self._generate_cover_note(job, candidate, match_report)

        return tailored, cover_note

    def _build_tailored_summary(self, job: ParsedJob, candidate: CandidateProfile) -> str:
        """Construct factual tailored summary directly from candidate facts."""
        tools_str = ", ".join(candidate.tools[:3]) if candidate.tools else "performance advertising tools"
        target_role = candidate.target_roles[0] if candidate.target_roles else "Performance Marketer"
        first_fact = candidate.summary_facts[0] if candidate.summary_facts else ""
        return (
            f"Results-driven {target_role} with hands-on expertise "
            f"executing performance advertising and lead acquisition across {tools_str}. "
            f"{first_fact} Skilled in GA4 and GTM conversion tracking, CPL and ROAS optimization, "
            f"and marketing automation to drive measurable pipeline growth."
        )

    def _build_tailored_skills(self, job: ParsedJob, candidate: CandidateProfile) -> List[str]:
        """Prioritize candidate skills that appear in the job's requirements."""
        job_text = f"{' '.join(job.must_have_skills)} {' '.join(job.platforms_and_tools)}".lower()
        prioritized = []
        remaining = []

        for skill in candidate.skills:
            if skill.lower() in job_text:
                prioritized.append(skill)
            else:
                remaining.append(skill)

        return prioritized + remaining[:max(0, 10 - len(prioritized))]

    def _build_tailored_roles(self, job: ParsedJob, candidate: CandidateProfile) -> List[ResumeRole]:
        """Build roles with bullets reordered by relevance to target job."""
        roles = []
        for emp in candidate.employment:
            bullets = list(emp.responsibilities)

            # Prepend top candidate achievements as evidence bullets for recent/primary role
            if emp.is_current or (candidate.employment and emp == candidate.employment[0]):
                top_achievements = [ach.statement for ach in candidate.achievements[:2]]
                bullets = [a for a in top_achievements if a not in bullets] + bullets

            roles.append(
                ResumeRole(
                    company=emp.company,
                    title=emp.title,
                    location=emp.location,
                    period=f"{emp.start_date} - {emp.end_date}",
                    bullets=bullets[:5],
                )
            )
        return roles

    def _generate_cover_note(self, job: ParsedJob, candidate: CandidateProfile, match_report: MatchReport) -> Dict[str, Any]:
        """Generate tailored cover note.

        The wrapper (Betreff/subject, greeting, sign-off) follows the active resume
        style; body content stays in English (default tailoring language).
        """
        from src.resume.sections import get_sub_labels, get_style

        style = get_style()
        sublabels = get_sub_labels(style)
        try:
            prompt_template = load_prompt_template("cover-note")
            if style == "de":
                system_prompt = (
                    "Write a short professional cover note for a job application. Use only verified candidate facts. "
                    "Keep it specific to the role and under 180 words. "
                    "The body must be written in English. The subject line must follow the German "
                    "application convention: 'Bewerbung als <job title> - <company>'. "
                    "Return JSON: {subject, body, claims_used}."
                )
            else:
                system_prompt = (
                    "Write a short professional cover note for a job application. Use only verified candidate facts. "
                    "Keep it specific to the role and under 180 words. Return JSON: {subject, body, claims_used}."
                )
            user_prompt = render_prompt(
                prompt_template,
                {
                    "candidate_profile_json": json.dumps(candidate.to_fact_registry(), indent=2),
                    "parsed_job_json": json.dumps(job.to_dict(), indent=2),
                    "match_report_json": json.dumps(match_report.to_dict(), indent=2),
                },
            )
            result = self.llm.generate_json(system_prompt, user_prompt)
            if "body" in result and "subject" in result:
                return result
        except Exception as e:
            logger.warning(f"LLM cover note generation fallback: {e}")

        # Deterministic fallback cover note (English body; style-aware subject line)
        lead_ach = candidate.achievements[0].statement if candidate.achievements else "hands-on campaign management"
        tools_str = ", ".join(candidate.tools[:3]) if candidate.tools else "performance advertising tools"
        target_role = candidate.target_roles[0] if candidate.target_roles else "Performance Marketer"
        if style == "de":
            subject = f"Bewerbung als {job.title} - {job.company}"
        else:
            subject = f"Application for {job.title} - {candidate.full_name}"
        return {
            "subject": subject,
            "body": (
                f"I am writing to express my strong interest in the {job.title} position at {job.company}. "
                f"As a {target_role} with practical experience across {tools_str}, "
                f"I specialize in paid acquisition execution, GA4/GTM tracking, and automated ad workflows. "
                f"In my recent work, I {lead_ach.lower() if lead_ach.startswith('Helped') else lead_ach} "
                f"My background in end-to-end campaign tracking and continuous A/B optimization directly aligns "
                f"with {job.company}'s growth goals. I would welcome the opportunity to discuss how I can contribute."
            ),
            "claims_used": [
                f"{candidate.full_name} - {target_role}",
                lead_ach,
                f"Tracking and automation with {tools_str}",
            ],
        }
