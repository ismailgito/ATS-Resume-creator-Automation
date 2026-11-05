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

# ---------------------------------------------------------------------------
# MODULE-LEVEL FALLBACK CONSTANTS
# These are used only if `config/scoring.yaml` does not define a `domain`
# block at all (e.g. very old config files). They match the defaults shipped
# for the marketing profile. All live values are loaded from scoring.yaml at
# MatchScorer.__init__ time — do NOT add profession-specific logic here.
# ---------------------------------------------------------------------------
_DEFAULT_CANDIDATE_TITLE_TOKENS: Set[str] = {
    "marketing", "performance", "digital", "growth", "paid", "ppc", "sea",
    "sem", "media", "acquisition", "cro", "analytics", "content", "seo",
    "social", "brand", "ecommerce", "martech",
}
_DEFAULT_OUT_OF_DOMAIN_TOKENS: Set[str] = {
    "engineer", "developer", "programmer", "architect", "devops", "sre",
    "backend", "frontend", "fullstack", "infrastructure", "data", "scientist",
    "ml", "machine", "learning", "nlp", "ai", "java", "golang", "kubernetes",
    "cloud", "security", "mechanical", "electrical", "civil", "firmware", "embedded",
}
_DEFAULT_OUT_OF_DOMAIN_SKILLS: Set[str] = {
    "python", "javascript", "typescript", "java", "golang", "c++", "rust",
    "sql", "nosql", "rest api", "rest apis", "fastapi", "django", "flask",
    "react", "node.js", "nodejs", "llm", "rag", "vector database",
    "vector databases", "pinecone", "chroma", "faiss", "langchain", "openai",
    "gemini api", "claude", "prompt engineering", "prompt", "embedding",
    "docker", "kubernetes", "aws", "gcp", "azure", "terraform",
    "machine learning", "deep learning", "pytorch", "tensorflow",
    "git", "version control",
}


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

        # ------------------------------------------------------------------
        # Domain config — loaded from scoring.yaml `domain:` block.
        # Falls back to marketing defaults so old config files keep working.
        # ------------------------------------------------------------------
        domain_cfg = self.scoring_config.get("domain", {})

        self.candidate_domain_label: str = domain_cfg.get(
            "candidate_domain", "Marketing"
        )
        self.candidate_title_tokens: Set[str] = set(
            t.lower() for t in domain_cfg.get(
                "candidate_title_tokens", list(_DEFAULT_CANDIDATE_TITLE_TOKENS)
            )
        )
        self.out_of_domain_tokens: Set[str] = set(
            t.lower() for t in domain_cfg.get(
                "out_of_domain_tokens", list(_DEFAULT_OUT_OF_DOMAIN_TOKENS)
            )
        )
        self.out_of_domain_skills: Set[str] = set(
            s.lower() for s in domain_cfg.get(
                "out_of_domain_skills", list(_DEFAULT_OUT_OF_DOMAIN_SKILLS)
            )
        )
        self.achievement_keywords: List[str] = [
            k.lower() for k in domain_cfg.get(
                "achievement_keywords",
                ["roas", "cpl", "cac", "google", "meta", "ga4", "gtm", "cro",
                 "ads", "seo", "acquisition", "campaign", "conversion", "paid"],
            )
        ]
        self.out_of_domain_achievement_keywords: List[str] = [
            k.lower() for k in domain_cfg.get(
                "out_of_domain_achievement_keywords",
                ["python", "llm", "rag", "api", "docker", "deploy", "model", "prompt"],
            )
        ]
        self.industry_keywords: List[str] = [
            k.lower() for k in domain_cfg.get(
                "industry_keywords",
                ["ecommerce", "e-commerce", "d2c", "b2b", "saas", "fintech",
                 "edtech", "agency", "tech", "growth", "software"],
            )
        ]

        logger.debug(
            "MatchScorer domain: '%s' | %d candidate tokens | %d out-of-domain tokens",
            self.candidate_domain_label,
            len(self.candidate_title_tokens),
            len(self.out_of_domain_tokens),
        )

    def _detect_job_domain(self, job: ParsedJob) -> str:
        """Classify the job into 'in_domain', 'out_of_domain', or 'mixed'.

        Uses candidate_title_tokens and out_of_domain_tokens from scoring.yaml.
        Returns one of: 'in_domain' | 'out_of_domain' | 'mixed'
        """
        title_tokens = set(re.findall(r"[a-z0-9]+", job.title.lower()))
        has_out = bool(self.out_of_domain_tokens.intersection(title_tokens))
        has_in  = bool(self.candidate_title_tokens.intersection(title_tokens))

        if has_out and not has_in:
            return "out_of_domain"
        if has_out and has_in:
            return "mixed"
        return "in_domain"

    def _count_domain_skill_mismatches(
        self, required_skills: List[str], candidate: CandidateProfile
    ) -> Tuple[int, int]:
        """Return (ood_required_count, ood_missing_count) for out-of-domain skills.

        Uses out_of_domain_skills set from scoring.yaml.
        """
        candidate_corpus = " ".join(s.lower() for s in (candidate.skills + candidate.tools))
        ood_required = 0
        ood_missing = 0
        for skill in required_skills:
            skill_l = skill.lower()
            is_ood = any(t in skill_l or skill_l in t for t in self.out_of_domain_skills)
            if is_ood:
                ood_required += 1
                if skill_l not in candidate_corpus and not any(
                    t in candidate_corpus for t in self.out_of_domain_skills
                    if t in skill_l or skill_l in t
                ):
                    ood_missing += 1
        return ood_required, ood_missing

    def score(self, job: ParsedJob, candidate: CandidateProfile) -> MatchReport:
        """Score a parsed job against candidate profile facts."""
        matched_reqs: List[str] = []
        missing_reqs: List[str] = []
        uncertain_reqs: List[str] = list(job.uncertainties)
        negative_flags: List[str] = []

        # Determine job domain before scoring to enable domain-aware logic
        job_domain = self._detect_job_domain(job)
        logger.debug("Job domain detected: %s for title '%s'", job_domain, job.title)

        # 1. Title Fit (20%)
        title_score = self._score_title(job.title, candidate, job_domain)

        # 2. Required Skills Fit (25%)
        skills_score, matched_skills, missing_skills = self._score_skills(
            job.must_have_skills, candidate, job_domain
        )
        matched_reqs.extend(matched_skills)
        missing_reqs.extend(missing_skills)

        # 3. Platform & Tools Fit (15%)
        tools_score, matched_tools, missing_tools = self._score_tools(
            job.platforms_and_tools, candidate, job_domain
        )
        matched_reqs.extend(matched_tools)
        missing_reqs.extend(missing_tools)

        # 4. Experience Fit (15%)
        exp_score = self._score_experience(job.experience_min, job.experience_max, candidate.experience_years)
        if job.experience_min is not None and job.experience_min > candidate.experience_years:
            missing_reqs.append(f"Requires {job.experience_min}+ yrs experience (Candidate has {candidate.experience_years} yrs)")

        # 5. Industry Fit (10%)
        industry_score = self._score_industry(job, candidate, job_domain)

        # 6. Location / Work Mode Fit (5%)
        loc_score = self._score_location(job.location, candidate)

        # 7. Achievement Relevance (10%)
        ach_score = self._score_achievements(job, candidate, job_domain)

        # 8. Check Negative Constraints
        negative_flags = self._check_negative_constraints(job, candidate)

        # --- Out-of-domain hard penalty --------------------------------
        # If the job is classified as out_of_domain AND the candidate is missing
        # the majority of the required out-of-domain skills, flag it.
        if job_domain == "out_of_domain":
            ood_req, ood_missing = self._count_domain_skill_mismatches(
                job.must_have_skills, candidate
            )
            if ood_req > 0:
                ood_miss_ratio = ood_missing / ood_req
                if ood_miss_ratio >= 0.5:
                    negative_flags.append(
                        f"Domain mismatch: Role requires out-of-domain skills; "
                        f"candidate is missing {ood_missing}/{ood_req} core skills "
                        f"outside their '{self.candidate_domain_label}' background."
                    )
                    logger.info(
                        "Out-of-domain mismatch flagged for '%s': %d/%d skills missing.",
                        job.title, ood_missing, ood_req,
                    )
            else:
                negative_flags.append(
                    f"Domain mismatch: Job title '{job.title}' is outside candidate's "
                    f"'{self.candidate_domain_label}' domain."
                )

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

    def _score_title(self, job_title: str, candidate: CandidateProfile, job_domain: str = "marketing") -> float:
        """Score job title alignment with candidate target roles.

        Engineering-domain titles receive a hard cap of 20 (the minimum) because
        the candidate is a marketer, not an engineer.
        """
        jt = job_title.lower()
        title_tokens = set(re.findall(r"\w+", jt))

        # Pure out-of-domain title (e.g. AI Engineer, Software Architect) gets 0.0
        if job_domain == "out_of_domain":
            logger.debug("Title score capped at 0.0 — out-of-domain title: '%s'", job_title)
            return 0.0

        # Check for completely irrelevant non-domain tokens
        if bool(self.out_of_domain_tokens.intersection(title_tokens)) and job_domain != "mixed":
            return 0.0

        # Combine candidate target roles and target config roles
        target_roles = list(candidate.target_roles) + self.target_config.get("target_roles", [])

        # Direct exact or substring match with target roles
        for role in target_roles:
            r_lower = role.lower()
            if r_lower in jt or jt in r_lower:
                return 100.0

        # Partial token match for marketing roles
        marketing_tokens = {
            "performance", "digital", "growth", "paid", "ppc", "sea",
            "media", "acquisition", "sem", "marketing", "analytics", "cro",
            "trainee", "associate", "specialist", "assistant"
        }
        overlap = marketing_tokens.intersection(title_tokens)

        if len(overlap) >= 2:
            return 90.0
        elif len(overlap) == 1:
            return 60.0
        return 20.0

    def _score_skills(
        self, required_skills: List[str], candidate: CandidateProfile, job_domain: str = "marketing"
    ) -> Tuple[float, List[str], List[str]]:
        """Score required skills match against candidate skills and tools.

        Matching rules:
        - Direct exact match  → confirmed match
        - Synonym group match → confirmed match
        - Substring match     → only allowed when the candidate token is >= 4 chars
                                AND the matched candidate token is not a generic
                                English word (prevents "lead" matching "LLM lead gen").
        - For engineering-domain jobs: purely technical skills (Python, RAG, etc.)
          are NEVER matched via substring against marketing terms.
        """
        if not required_skills:
            return 80.0, [], []

        matched = []
        missing = []
        candidate_corpus = [s.lower() for s in (candidate.skills + candidate.tools)]

        # Tokens that are too short or too generic to serve as substring evidence
        _SKIP_SUBSTRING_TOKENS: Set[str] = {
            "ads", "api", "ai", "ml", "it", "bi", "crm", "seo", "cro", "ppc",
            "sea", "sem", "b2b", "d2c", "ga4", "gtm", "ui", "ux",
        }

        for skill in required_skills:
            skill_l = skill.lower()

            # 1. Direct match
            if skill_l in candidate_corpus:
                matched.append(skill)
                continue

            # 2. Synonym group check (highest confidence after direct match)
            synonym_hit = False
            for _group, syns in self.synonyms.items():
                syns_lower = [s.lower() for s in syns]
                if skill_l in syns_lower:
                    if any(s in candidate_corpus for s in syns_lower):
                        matched.append(skill)
                        synonym_hit = True
                        break
                    # Partial candidate-token match within synonym group
                    if any(
                        any(s in ct or ct in s for ct in candidate_corpus if len(ct) >= 4 and ct not in _SKIP_SUBSTRING_TOKENS)
                        for s in syns_lower
                    ):
                        matched.append(skill)
                        synonym_hit = True
                        break
            if synonym_hit:
                continue

            # 3. Substring match — guarded to avoid false positives
            #    For out-of-domain jobs, skip substring matching for out-of-domain skills.
            if job_domain == "out_of_domain" and any(t in skill_l or skill_l in t for t in self.out_of_domain_skills):
                # Only an exact corpus match counts; substring would be misleading.
                missing.append(skill)
                continue

            substring_hit = False
            for c in candidate_corpus:
                # Reject trivially short or generic tokens
                if len(c) < 4 or c in _SKIP_SUBSTRING_TOKENS:
                    continue
                if skill_l in c or c in skill_l:
                    substring_hit = True
                    break
            if substring_hit:
                matched.append(skill)
            else:
                missing.append(skill)

        match_ratio = len(matched) / len(required_skills)
        return match_ratio * 100.0, matched, missing

    def _score_tools(
        self, required_tools: List[str], candidate: CandidateProfile, job_domain: str = "marketing"
    ) -> Tuple[float, List[str], List[str]]:
        """Score platform & tools match against candidate tools registry.

        When no tools are listed in the JD:
        - Marketing domain: default 85 (tools are often implied by skills)
        - Engineering domain: default 40 (absence of tool data is suspicious;
          don't hand out a free pass for a specialised engineering role).
        """
        if not required_tools:
            default = 20.0 if job_domain == "out_of_domain" else 85.0
            return default, [], []

        matched = []
        missing = []
        candidate_tools_lower = [t.lower() for t in candidate.tools]

        for tool in required_tools:
            tool_l = tool.lower()
            is_matched = False

            if tool_l in candidate_tools_lower:
                matched.append(tool)
                continue

            # Synonym check (exact synonym match only)
            for _group, syns in self.synonyms.items():
                syns_lower = [s.lower() for s in syns]
                if tool_l in syns_lower:
                    if any(t in candidate_tools_lower for t in syns_lower):
                        matched.append(tool)
                        is_matched = True
                        break
            if is_matched:
                continue

            # Substring check — out-of-domain tech tools are not substring-matched
            if job_domain == "out_of_domain" and any(t in tool_l or tool_l in t for t in self.out_of_domain_skills):
                missing.append(tool)
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
                return max(0.0, 100.0 - (diff * 25.0))
            if candidate_years > exp_max:
                diff = candidate_years - exp_max
                return max(50.0, 100.0 - (diff * 15.0))

        if exp_min is not None:
            if candidate_years >= exp_min:
                return 100.0
            diff = exp_min - candidate_years
            return max(0.0, 100.0 - (diff * 25.0))

        return 85.0

    def _score_industry(self, job: ParsedJob, candidate: CandidateProfile, job_domain: str = "marketing") -> float:
        """Score industry relevance (B2C, D2C, B2B SaaS, Agency).

        Engineering-domain roles cap industry score at 50 — the industry may
        be tech but the *function* is not the candidate's domain.
        """
        jt_desc = f"{job.title} {job.company} {' '.join(job.responsibilities)}".lower()
        relevant_domains = ["ecommerce", "e-commerce", "d2c", "b2b", "saas", "fintech", "edtech", "agency", "tech", "growth", "software"]
        matches = [d for d in relevant_domains if d in jt_desc]

        if job_domain == "out_of_domain":
            # Cap at 40 — out-of-domain role doesn't fit candidate background.
            return 40.0

        if matches:
            return 95.0
        return 75.0

    def _score_location(self, job_loc: str, candidate: CandidateProfile) -> float:
        """Score location and remote / hybrid fit according to preferred target locations."""
        if not job_loc:
            return 85.0
        loc_l = job_loc.lower()

        # Remote / hybrid work modes always achieve top score
        if "remote" in loc_l or "hybrid" in loc_l:
            return 100.0

        # Match preferred cities from target config
        pref_cities = [c.lower() for c in self.target_config.get("location_preferences", {}).get("preferred_cities", [])]
        if not pref_cities:
            pref_cities = [
                "berlin", "munich", "hamburg", "düsseldorf", "cologne", "stuttgart",
                "frankfurt", "karlsruhe", "mannheim", "bengaluru", "mumbai"
            ]

        # Top target cities (Berlin, Munich, Hamburg, etc.) or candidate location match
        if any(c in loc_l for c in pref_cities):
            return 100.0

        # Preferred country matches (Germany / Deutschland)
        pref_countries = [c.lower() for c in self.target_config.get("location_preferences", {}).get("preferred_countries", ["germany", "deutschland"])]
        if any(cnt in loc_l for cnt in pref_countries):
            return 95.0

        # Also support Bengaluru / Mumbai / India from existing samples or candidate origin
        if any(c in loc_l for c in ["bengaluru", "bangalore", "chennai", "mumbai", "india"]):
            return 90.0

        return 65.0

    def _score_achievements(self, job: ParsedJob, candidate: CandidateProfile, job_domain: str = "marketing") -> float:
        """Score relevance of candidate achievements to required job outcomes.

        Uses two separate keyword sets:
        - marketing_terms: relevant to marketing / performance roles
        - engineering_terms: relevant to engineering / AI roles

        For engineering-domain jobs the candidate's marketing achievements
        are unlikely to match engineering keywords, so the base is lowered to
        50 and no bonus is awarded for incidental keyword overlaps on generic
        words like 'lead' or 'n8n'.
        """
        all_job_text = f"{' '.join(job.must_have_skills)} {' '.join(job.platforms_and_tools)} {' '.join(job.responsibilities)}".lower()

        if job_domain == "out_of_domain":
            # For out-of-domain roles, only match against out-of-domain keywords
            # so marketer achievements don't accidentally cross-match.
            relevant_count = 0
            for ach in candidate.achievements:
                ach_text = f"{ach.statement} {ach.metric}".lower()
                if any(k in ach_text and k in all_job_text for k in self.out_of_domain_achievement_keywords):
                    relevant_count += 1
            ratio = relevant_count / max(1, len(candidate.achievements))
            # Base 20 for out-of-domain — achievements in other disciplines don't transfer
            return min(100.0, 20.0 + (ratio * 30.0))

        # Marketing domain — original logic with specific marketing keywords
        marketing_terms = [
            "roas", "cpl", "cac", "google", "meta", "ga4", "gtm", "scale",
            "cro", "ads", "seo", "acquisition", "campaign", "clarity",
            "conversion", "funnel", "paid", "landing page", "a/b",
        ]
        relevant_count = 0
        for ach in candidate.achievements:
            ach_text = f"{ach.statement} {ach.metric}".lower()
            if any(k in ach_text and k in all_job_text for k in marketing_terms):
                relevant_count += 1
        ratio = relevant_count / max(1, len(candidate.achievements))
        return min(100.0, 70.0 + (ratio * 30.0))

    def _check_negative_constraints(self, job: ParsedJob, candidate: CandidateProfile) -> List[str]:
        """Check whether the job strictly demands prohibited / unheld skills."""
        flags = []
        job_full_text = f"{job.title} {' '.join(job.must_have_skills)} {' '.join(job.platforms_and_tools)} {' '.join(job.responsibilities)} {' '.join(job.keywords)}".lower()

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

        # Fluent German requirement check
        if any("fluent german" in c.lower() or "german" in c.lower() for c in candidate.negative_constraints):
            german_c2_tokens = ["fluent german", "c1 german", "c2 german", "verhandlungssichere deutschkenntnisse", "deutsch fließend"]
            if any(tok in job_full_text for tok in german_c2_tokens):
                flags.append("Violates constraint: Job requires fluent/native German, but candidate is beginner (A1)")

        return flags
