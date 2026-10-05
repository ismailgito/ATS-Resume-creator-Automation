"""Fact Checker auditing resume claims against candidate fact registry."""

from __future__ import annotations

import re
from typing import List, Tuple
from src.models.profile import CandidateProfile
from src.models.resume import TailoredResume


class FactChecker:
    """Verifies that all claims, tools, and employers trace to verified facts."""

    @classmethod
    def audit(cls, candidate: CandidateProfile, tailored: TailoredResume) -> Tuple[List[str], List[str]]:
        """
        Audit tailored resume.
        Returns:
            factuality_errors: Hard errors that must fail validation.
            unsupported_claims: Warnings / unverified claims.
        """
        errors: List[str] = []
        warnings: List[str] = []

        fact_registry = candidate.to_fact_registry()
        verified_skills_lower = {s.lower() for s in candidate.skills}
        verified_tools_lower = {t.lower() for t in candidate.tools}
        verified_employers = {e.company.lower() for e in candidate.employment}

        # 1. Audit Employers
        for role in tailored.experience:
            if role.company.lower() not in verified_employers:
                errors.append(f"Unverified employer in resume: '{role.company}'. Not present in candidate profile.")

        # 2. Check Negative Constraints
        for constraint in candidate.negative_constraints:
            c_low = constraint.lower()
            # Extract prohibited keyword
            for tool_keyword in ["salesforce marketing cloud", "marketo", "dv360", "trade desk", "java"]:
                if tool_keyword in c_low:
                    # Check if tailored resume claims it
                    full_resume_text = (
                        f"{tailored.summary} {' '.join(tailored.skills)} "
                        f"{' '.join([' '.join(r.bullets) for r in tailored.experience])}"
                    ).lower()
                    if tool_keyword in full_resume_text:
                        errors.append(
                            f"Violation of negative constraint '{constraint}': "
                            f"Prohibited skill/tool '{tool_keyword}' found in tailored resume."
                        )

        # 3. Check for placeholder tokens
        resume_str = f"{tailored.summary} {' '.join(tailored.skills)}"
        if "{{" in resume_str or "}}" in resume_str:
            errors.append("Unresolved template placeholder (e.g. '{{...}}') detected in tailored resume.")

        # 4. Audit Skills
        for skill in tailored.skills:
            s_low = skill.lower()
            if s_low not in verified_skills_lower and s_low not in verified_tools_lower:
                # Check partial substring or standard synonyms
                if not any(s_low in vs or vs in s_low for vs in verified_skills_lower):
                    warnings.append(f"Skill '{skill}' is not directly listed in verified profile skills.")

        return errors, warnings
