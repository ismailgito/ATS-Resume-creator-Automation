"""Comprehensive Quality Gate and ATS Resume Validator."""

from __future__ import annotations

import collections
import re
from typing import List, Optional
from src.config import AppSettings, load_yaml_config
from src.models.profile import CandidateProfile
from src.models.resume import TailoredResume, ValidationReport
from src.validate.fact_checker import FactChecker


class ResumeValidator:
    """Automated ATS and quality gate for tailored resumes."""

    def __init__(self, settings: Optional[AppSettings] = None):
        self.settings = settings or AppSettings()
        self.policy_config = load_yaml_config(self.settings.policy_config_path)

    def validate(self, candidate: CandidateProfile, tailored: TailoredResume) -> ValidationReport:
        """Run all quality, ATS, and factuality checks."""
        factuality_errors, unsupported_claims = FactChecker.audit(candidate, tailored)
        ats_warnings: List[str] = []
        keyword_stuffing_warnings: List[str] = []
        missing_sections: List[str] = []
        readability_warnings: List[str] = []
        required_fixes: List[str] = []

        # 1. Check Mandatory Sections
        if not tailored.summary or len(tailored.summary.strip()) < 50:
            missing_sections.append("Professional Summary is missing or too short (< 50 chars).")

        if not tailored.skills or len(tailored.skills) < 3:
            missing_sections.append("Core Competencies & Skills section has fewer than 3 skills.")

        if not tailored.experience:
            missing_sections.append("Professional Experience section is empty.")

        if not candidate.education:
            missing_sections.append("Education section is missing.")

        # 2. Check Contact Details
        if not candidate.contact.email or "@" not in candidate.contact.email:
            required_fixes.append("Valid candidate email is missing from contact details.")
        if not candidate.contact.phone:
            required_fixes.append("Candidate phone number is missing from contact details.")

        # 3. Readability & Bullet Length
        for role in tailored.experience:
            for b in role.bullets:
                if len(b) > 400:
                    readability_warnings.append(f"Bullet point in {role.company} exceeds 400 characters (may reduce ATS readability).")
                if len(b) < 15:
                    readability_warnings.append(f"Bullet point in {role.company} is too brief (< 15 chars).")

        # 4. Keyword Stuffing Detector
        combined_text = (
            f"{tailored.summary} {' '.join(tailored.skills)} "
            f"{' '.join([' '.join(r.bullets) for r in tailored.experience])}"
        ).lower()
        words = re.findall(r"\b[a-z]{3,}\b", combined_text)
        stopwords = {"and", "the", "for", "with", "across", "from", "that", "this", "our", "all", "via", "while"}
        content_words = [w for w in words if w not in stopwords]
        counts = collections.Counter(content_words)

        for word, count in counts.items():
            if count >= 12:
                keyword_stuffing_warnings.append(f"Word '{word}' repeats {count} times (possible keyword stuffing).")

        # 5. Format & Layout Warnings
        if "{{" in combined_text or "}}" in combined_text:
            ats_warnings.append("Raw template syntax detected in text output.")

        # Aggregate required fixes
        required_fixes.extend(factuality_errors)
        required_fixes.extend(missing_sections)

        passed = len(factuality_errors) == 0 and len(missing_sections) == 0 and len(required_fixes) == 0

        return ValidationReport(
            resume_version_id=tailored.resume_version_id,
            job_id=tailored.job_id,
            passed=passed,
            factuality_errors=factuality_errors,
            unsupported_claims=unsupported_claims,
            ats_warnings=ats_warnings,
            keyword_stuffing_warnings=keyword_stuffing_warnings,
            missing_sections=missing_sections,
            readability_warnings=readability_warnings,
            required_fixes=required_fixes,
        )
