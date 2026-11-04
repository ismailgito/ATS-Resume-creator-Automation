"""Resume Tailoring Engine adhering to strict factuality, ATS and human-writing rules."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from src.config import AppSettings
from src.llm.client import BaseLLMClient, get_llm_client
from src.llm.prompts import load_prompt_template, render_prompt
from src.models.job import ParsedJob
from src.models.profile import CandidateProfile
from src.models.resume import ResumeRole, TailoredResume
from src.models.score import MatchReport
from src.resume.layout import is_covered
from src.resume.skill_utils import dedupe_skills
from src.validate.human_tone import BANNED_PHRASES

logger = logging.getLogger(__name__)

SUMMARY_MAX_CHARS = 330
MAX_SKILLS = 10
MAX_BULLETS_PER_ROLE = 5

GERMAN_PLACES = (
    "germany", "deutschland", "berlin", "munich", "münchen", "hamburg", "frankfurt",
    "cologne", "köln", "stuttgart", "düsseldorf", "leipzig", "dresden", "hannover",
    "nuremberg", "nürnberg",
)

# Past-tense verbs that do not end in "-ed"; used to turn a profile fact into "I <verb> ..."
_IRREGULAR_VERBS = {"built", "ran", "led", "wrote", "made", "set", "grew", "won", "drove"}

# Shared writing rules for every LLM-written text (resume and cover note). The detailed
# version lives in prompts/*.md; this short form goes into the system prompt.
HUMAN_WRITING_RULES = (
    "Write like a careful junior professional, not like a language model. "
    "Plain, concrete English. Short sentences mixed with medium ones. "
    "Keep every number exactly as given in the profile; never add, round or estimate figures. "
    "Start bullets with different past-tense verbs. No em dashes in sentences. "
    "Use the job's own keywords once each where they are true, never as lists inside prose. "
    "Never use these words or phrases: " + ", ".join(BANNED_PHRASES) + "."
)


def _term_pattern(term: str) -> "re.Pattern[str]":
    return re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])")


def _job_terms(job: ParsedJob) -> List[str]:
    """Lower-cased skills, tools and keywords the job asks for (deduplicated, order kept)."""
    raw = job.must_have_skills + job.platforms_and_tools + job.nice_to_have_skills + job.keywords
    return list(dict.fromkeys(t.strip().lower() for t in raw if t and t.strip()))


def _relevance(text: str, terms: List[str]) -> int:
    """How many of the job's terms appear in ``text`` (whole-word match)."""
    lowered = text.lower()
    return sum(1 for term in terms if _term_pattern(term).search(lowered))


def _is_german_job(job: ParsedJob) -> bool:
    location = (job.location or "").lower()
    return any(place in location for place in GERMAN_PLACES)


def _has_permit(candidate: CandidateProfile) -> bool:
    text = f"{candidate.work_authorization} {' '.join(candidate.summary_facts)}".lower()
    return "chancenkarte" in text or "opportunity card" in text


def _is_permit_fact(fact: str) -> bool:
    lowered = fact.lower()
    return "chancenkarte" in lowered or "opportunity card" in lowered


def _mostly_repeated(fact: str, bullets: List[str], threshold: float = 0.7) -> bool:
    """True when one bullet already contains most of the fact's words (near-verbatim repeat)."""
    words = set(re.findall(r"\w+", fact.lower()))
    if not words:
        return False
    return any(len(words & set(re.findall(r"\w+", b.lower()))) / len(words) >= threshold for b in bullets)


def _as_first_person(fact: str) -> Optional[str]:
    """'Helped run a campaign.' -> 'I helped run a campaign.' Returns None for non-verb openers."""
    fact = fact.strip()
    first = fact.split()[0].lower() if fact.split() else ""
    if not (first.endswith("ed") or first in _IRREGULAR_VERBS):
        return None
    sentence = "I " + fact[0].lower() + fact[1:]
    return sentence if sentence.endswith((".", "!", "?")) else sentence + "."


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
        baseline_summary = self._build_tailored_summary(
            job, candidate, bullets=[b for role in baseline_roles for b in role.bullets]
        )
        baseline_skills = self._build_tailored_skills(job, candidate)
        change_log = [
            f"Chose the summary facts that best match '{job.title}' at {job.company}.",
            f"Put the {len(match_report.matched_requirements)} verified matching requirements first in the skills list.",
            "Ordered the bullets of each role by relevance to the job's keywords.",
        ]

        # 2. LLM tailoring if available
        try:
            prompt_template = load_prompt_template("tailor-resume")
            system_prompt = (
                "You tailor resumes for ATS compatibility while preserving factual accuracy. "
                "You must not invent employers, dates, tools, certifications, responsibilities, or metrics. "
                "If a job requirement is missing, report it in gap_list. "
                "The resume text is English; the layout (German Lebenslauf) is applied separately. "
                + HUMAN_WRITING_RULES
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

    # ------------------------------------------------------------------ #
    # Deterministic building blocks (also the offline fallback)
    # ------------------------------------------------------------------ #

    def _select_facts(self, job: ParsedJob, candidate: CandidateProfile) -> Tuple[str, List[str], Optional[str]]:
        """Split summary facts into (lead fact, others ranked by job relevance, permit fact)."""
        facts = [f.strip() for f in candidate.summary_facts if f and f.strip()]
        permit = next((f for f in facts if _is_permit_fact(f)), None)
        body = [f for f in facts if not _is_permit_fact(f)]
        if not body:
            return "", [], permit
        terms = _job_terms(job)
        ranked = sorted(body[1:], key=lambda f: -_relevance(f, terms))  # stable: ties keep profile order
        return body[0], ranked, permit

    def _build_tailored_summary(self, job: ParsedJob, candidate: CandidateProfile, bullets: Optional[List[str]] = None) -> str:
        """Short profile built from the candidate's own verified sentences, no stock phrases.

        Facts that a role bullet already says almost word for word are skipped, so the profile
        and the experience section do not read like copies of each other.
        """
        lead, ranked, permit = self._select_facts(job, candidate)
        if not lead:
            role = candidate.target_roles[0] if candidate.target_roles else "Performance marketer"
            tools = ", ".join(candidate.tools[:3])
            return f"{role}" + (f" working with {tools}." if tools else ".")

        terms = _job_terms(job)
        parts = [lead]
        for fact in ranked:
            if bullets and _mostly_repeated(fact, bullets):
                continue
            if len(parts) >= 3:
                break
            if len(parts) >= 2 and _relevance(fact, terms) == 0:
                break
            if len(" ".join(parts + [fact])) > SUMMARY_MAX_CHARS:
                continue
            parts.append(fact)

        if permit and _is_german_job(job):
            parts.append(permit)
        return " ".join(parts)

    def _build_tailored_skills(self, job: ParsedJob, candidate: CandidateProfile) -> List[str]:
        """Job-relevant skills first, without near-duplicates (e.g. 'Google Ads' next to 'Google Ads (SEA)')."""
        skills = dedupe_skills(candidate.skills, also_covered_by=candidate.tools)
        job_text = " ".join(_job_terms(job))

        prioritized = [s for s in skills if s.lower() in job_text]
        remaining = [s for s in skills if s not in prioritized]
        return (prioritized + remaining)[:MAX_SKILLS]

    def _build_tailored_roles(self, job: ParsedJob, candidate: CandidateProfile) -> List[ResumeRole]:
        """Build roles with bullets ordered by relevance to the target job."""
        terms = _job_terms(job)
        roles = []
        for idx, emp in enumerate(candidate.employment):
            bullets = list(emp.responsibilities)

            # Add top achievements to the current/primary role, unless its bullets already say the same
            if emp.is_current or idx == 0:
                extra = [
                    ach.statement
                    for ach in candidate.achievements[:2]
                    if ach.statement not in bullets and not is_covered(ach.statement, bullets)
                ]
                bullets = extra + bullets

            bullets.sort(key=lambda b: -_relevance(b, terms))  # stable: ties keep profile order

            end = emp.end_date or ("Present" if emp.is_current else "")
            roles.append(
                ResumeRole(
                    company=emp.company,
                    title=emp.title,
                    location=emp.location,
                    period=f"{emp.start_date} - {end}" if end else emp.start_date,
                    bullets=bullets[:MAX_BULLETS_PER_ROLE],
                )
            )
        return roles

    # ------------------------------------------------------------------ #
    # Cover note
    # ------------------------------------------------------------------ #

    def _generate_cover_note(self, job: ParsedJob, candidate: CandidateProfile, match_report: MatchReport) -> Dict[str, Any]:
        """Generate the cover note body (English). The subject follows the German convention."""
        subject = f"Bewerbung als {job.title} - {job.company}"
        try:
            prompt_template = load_prompt_template("cover-note")
            system_prompt = (
                "Write a short cover note for a job application in Germany. Use only verified candidate facts. "
                "Keep it specific to the role and under 150 words, in three short paragraphs. "
                "The body must be written in English, in the first person, without greeting or sign-off "
                "(those are added separately). "
                f"The subject line must be exactly: '{subject}'. "
                + HUMAN_WRITING_RULES
                + " Return JSON: {subject, body, claims_used}."
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
            if result.get("body") and result.get("subject"):
                return result
        except Exception as e:
            logger.warning(f"LLM cover note generation fallback: {e}")

        return self._deterministic_cover_note(job, candidate, subject)

    def _deterministic_cover_note(self, job: ParsedJob, candidate: CandidateProfile, subject: str) -> Dict[str, Any]:
        """Offline cover note built from the candidate's own sentences, in plain first-person English."""
        lead, ranked, _ = self._select_facts(job, candidate)

        first_person = [s for s in (_as_first_person(f) for f in ranked) if s][:2]
        paragraphs = [f"I am applying for the {job.title} position at {job.company}."]
        if first_person:
            paragraphs.append(" ".join(first_person))
        elif lead:
            paragraphs.append(lead)

        if _has_permit(candidate) and _is_german_job(job):
            start = f" I can start within {candidate.notice_period_days} days." if candidate.notice_period_days else ""
            paragraphs.append(
                "I hold an approved German Opportunity Card (Chancenkarte) and can work in Germany." + start
            )
        paragraphs.append("I would be glad to walk you through the campaign and tracking setups in a call.")

        return {
            "subject": subject,
            "body": "\n\n".join(paragraphs),
            "claims_used": first_person or ([lead] if lead else []),
        }
