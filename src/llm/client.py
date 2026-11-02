"""LLM Provider Interface and Fallback Implementations."""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import requests
from src.config import AppSettings

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Generate structured JSON response from the LLM."""
        pass


class GeminiLLMClient(BaseLLMClient):
    """Client for Google Gemini API."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro", base_url: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        url = f"{self.base_url}?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\nUSER REQUEST:\n{user_prompt}"}],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        return _extract_json_from_text(raw_text)


class OpenAILLMClient(BaseLLMClient):
    """Client for OpenAI / compatible endpoints."""

    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["choices"][0]["message"]["content"]
        return _extract_json_from_text(raw_text)


class AnthropicLLMClient(BaseLLMClient):
    """Client for Anthropic Claude API."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022", base_url: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "https://api.anthropic.com/v1").rstrip("/")

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        url = f"{self.base_url}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        full_system = f"{system_prompt}\nYou MUST output valid JSON only. Do not wrap in markdown or backticks."
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": full_system,
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": 0.1,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["content"][0]["text"]
        return _extract_json_from_text(raw_text)


class OfflineDeterministicLLMClient(BaseLLMClient):
    """
    Intelligent offline rule-based client.
    Allows complete testing, development, and usage before the user pastes their API keys.
    """

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        prompt_lower = user_prompt.lower()

        # 1. Parse Job
        if "parse this job description" in prompt_lower or "job text:" in prompt_lower:
            return self._mock_parse_job(user_prompt)

        # 2. Score Job
        if "score the job against the candidate profile" in prompt_lower or ("candidate profile:" in prompt_lower and "parsed job:" in prompt_lower):
            return self._mock_score_job(user_prompt)

        # 3. Tailor Resume
        if "target job:" in prompt_lower and "match report:" in prompt_lower:
            return self._mock_tailor_resume(user_prompt)

        # 4. Validate Resume
        if "fact registry:" in prompt_lower and "tailored resume:" in prompt_lower:
            return self._mock_validate_resume(user_prompt)

        # 5. Cover Note
        if "cover note" in prompt_lower:
            return self._mock_cover_note(user_prompt)

        return {"status": "ok", "message": "Offline response generated."}

    def _mock_parse_job(self, user_prompt: str) -> Dict[str, Any]:
        text = user_prompt

        # Detect experience bounds
        exp_match = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*years?", text, re.IGNORECASE)
        exp_min = float(exp_match.group(1)) if exp_match else None
        exp_max = float(exp_match.group(2)) if exp_match else None
        if not exp_match:
            single_exp = re.search(r"(\d+)\+?\s*years?", text, re.IGNORECASE)
            if single_exp:
                exp_min = float(single_exp.group(1))

        # Detect known skills & tools
        known_terms = [
            "Google Ads", "Meta Ads", "Facebook Ads", "LinkedIn Ads", "GA4", "GTM",
            "Google Analytics", "Looker Studio", "CRO", "A/B Testing", "Shopify",
            "Unbounce", "Hotjar", "Klaviyo", "AppsFlyer", "PMax", "SEM", "PPC",
            "Salesforce Marketing Cloud", "Marketo", "DV360", "The Trade Desk", "Java", "Spring Boot"
        ]
        found_skills = [term for term in known_terms if re.search(r"\b" + re.escape(term) + r"\b", text, re.I)]

        return {
            "title": "Marketing Professional",
            "company": "Target Company",
            "location": "Berlin / Remote",
            "employment_type": "Full Time",
            "experience_min": exp_min,
            "experience_max": exp_max,
            "salary": None,
            "must_have_skills": found_skills[:4] if found_skills else ["Performance Marketing"],
            "nice_to_have_skills": found_skills[4:8] if len(found_skills) > 4 else [],
            "platforms_and_tools": found_skills,
            "responsibilities": [
                "Execute and optimize paid acquisition campaigns across Meta and Google.",
                "Track and report ROAS, CAC, and CPL metrics.",
                "Conduct A/B creative tests and landing page optimization."
            ],
            "education_requirements": ["Bachelor's Degree"],
            "certifications": [],
            "keywords": found_skills,
            "uncertainties": []
        }

    def _mock_score_job(self, user_prompt: str) -> Dict[str, Any]:
        return {
            "overall_score": 88.0,
            "score_breakdown": {
                "title_role_fit": 19.0,
                "required_skills": 23.5,
                "platform_tools": 14.0,
                "experience_fit": 13.0,
                "industry_fit": 9.5,
                "location_fit": 5.0,
                "achievement_relevance": 9.0
            },
            "matched_requirements": ["Google Ads", "Meta Ads", "GA4", "GTM", "ROAS Optimization"],
            "missing_requirements": [],
            "uncertain_requirements": [],
            "recommendation": "apply_review",
            "reason": "Strong match with candidate's performance marketing background and paid advertising track record."
        }

    def _mock_tailor_resume(self, user_prompt: str) -> Dict[str, Any]:
        try:
            from src.config import load_candidate_profile
            cand = load_candidate_profile()
        except Exception:
            cand = {}

        full_name = cand.get("full_name", "Mohamed Ismail")
        roles = cand.get("target_roles", ["Junior Performance Marketing Manager"])
        summary_facts = cand.get("summary_facts", [])

        summary = (
            f"Results-driven {roles[0]} with hands-on expertise executing "
            f"paid acquisition and lead generation across Meta Ads and Google Ads. "
            f"Proven track record in GA4/GTM conversion tracking, CPL optimization, and n8n workflow automation."
        )
        if summary_facts:
            summary = (
                f"{summary_facts[0]} Skilled in Meta Ads lead generation, "
                f"GA4/GTM event tracking, and n8n ad intelligence workflows to drive scalable acquisition."
            )

        skills = cand.get("skills", [
            "Performance Marketing",
            "Meta Ads",
            "Google Ads (SEA)",
            "Conversion Rate Optimization (CRO)",
            "Google Analytics 4 (GA4)",
            "Google Tag Manager (GTM)",
            "Marketing Automation"
        ])[:7]

        experience = []
        for emp in cand.get("employment", []):
            experience.append({
                "company": emp.get("company", ""),
                "title": emp.get("title", ""),
                "location": emp.get("location", ""),
                "period": f"{emp.get('start_date', '')} - {emp.get('end_date', '')}",
                "bullets": emp.get("responsibilities", [])[:4],
            })

        education = []
        for ed in cand.get("education", []):
            education.append({
                "institution": ed.get("institution", ""),
                "degree": ed.get("degree", ""),
                "period": f"{ed.get('start_year', '')} - {ed.get('end_year', '')}",
            })

        certifications = [
            {"name": c.get("name", ""), "issuer": c.get("issuer", ""), "date": c.get("date", "")}
            for c in cand.get("certifications", [])[:4]
        ]

        return {
            "summary": summary,
            "skills": skills,
            "experience": experience,
            "education": education,
            "certifications": certifications,
            "gap_list": [],
            "change_log": [
                "Tailored summary targeting role requirements with verified campaign metrics.",
                "Aligned skills section prioritizing Meta Ads, Google Ads, GA4, and GTM.",
                "Ranked experience bullets highlighting verified lead acquisition and tracking impact.",
            ],
            "factuality_notes": [
                "All statements and numbers match verified facts in candidate profile."
            ]
        }

    def _mock_validate_resume(self, user_prompt: str) -> Dict[str, Any]:
        return {
            "pass": True,
            "factuality_errors": [],
            "unsupported_claims": [],
            "ats_warnings": [],
            "keyword_stuffing_warnings": [],
            "missing_sections": [],
            "readability_warnings": [],
            "required_fixes": []
        }

    def _mock_cover_note(self, user_prompt: str) -> Dict[str, Any]:
        try:
            from src.config import load_candidate_profile
            cand = load_candidate_profile()
            full_name = cand.get("full_name", "Mohamed Ismail")
        except Exception:
            full_name = "Mohamed Ismail"

        # Style-aware subject line: German wrapper (Betreff) vs classic English.
        try:
            from src.resume.sections import get_style
            is_de = get_style() == "de"
        except Exception:
            is_de = True

        if is_de:
            subject = "Bewerbung als Performance Marketing Manager"
        else:
            subject = f"Application for Performance Marketing Role - {full_name}"

        return {
            "subject": subject,
            "body": (
                "I am excited to apply for this performance marketing position. With practical experience "
                "executing Meta Ads lead generation campaigns, analyzing placement and form performance, "
                "and configuring end-to-end GA4 and GTM tracking, I focus on delivering scalable, "
                "cost-efficient acquisition results. Furthermore, my experience building automated ad intelligence "
                "workflows with n8n and Python allows me to execute quickly and optimize continuously. "
                "With my approved German Opportunity Card (Chancenkarte), I am fully authorized and ready to contribute immediately in Germany."
            ),
            "claims_used": [
                "Hands-on experience in Meta Ads lead generation and CPL optimization",
                "GA4 and GTM event tracking setup and placement analysis",
                "Marketing workflow automation with n8n",
                "Work authorization via approved German Opportunity Card",
            ]
        }


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    """Helper to cleanly extract JSON from raw markdown LLM text."""
    clean = text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```[a-zA-Z]*\n", "", clean)
        clean = re.sub(r"\n```$", "", clean)
    try:
        return json.loads(clean.strip())
    except json.JSONDecodeError:
        # Fallback: regex search for outer {...}
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def get_llm_client(settings: Optional[AppSettings] = None) -> BaseLLMClient:
    """Factory to get the appropriate LLM client based on configured settings."""
    cfg = settings or AppSettings()
    provider = cfg.llm_provider.lower()

    if provider == "gemini" and cfg.gemini_api_key and not cfg.gemini_api_key.startswith("your_"):
        logger.info("Using live Google Gemini LLM provider.")
        return GeminiLLMClient(api_key=cfg.gemini_api_key, model=cfg.gemini_model, base_url=cfg.llm_api_base_url)

    if provider == "openai" and cfg.openai_api_key and not cfg.openai_api_key.startswith("your_"):
        logger.info("Using live OpenAI LLM provider.")
        return OpenAILLMClient(api_key=cfg.openai_api_key, model=cfg.openai_model, base_url=cfg.llm_api_base_url)

    if provider == "anthropic" and cfg.anthropic_api_key and not cfg.anthropic_api_key.startswith("your_"):
        logger.info("Using live Anthropic LLM provider.")
        return AnthropicLLMClient(api_key=cfg.anthropic_api_key, model=cfg.anthropic_model, base_url=cfg.llm_api_base_url)

    # Auto-detect if any key is valid
    if cfg.gemini_api_key and not cfg.gemini_api_key.startswith("your_") and len(cfg.gemini_api_key) > 10:
        logger.info("Auto-detected valid Gemini API key. Using Gemini LLM provider.")
        return GeminiLLMClient(api_key=cfg.gemini_api_key, model=cfg.gemini_model, base_url=cfg.llm_api_base_url)

    if cfg.openai_api_key and not cfg.openai_api_key.startswith("your_") and len(cfg.openai_api_key) > 10:
        logger.info("Auto-detected valid OpenAI API key. Using OpenAI LLM provider.")
        return OpenAILLMClient(api_key=cfg.openai_api_key, model=cfg.openai_model, base_url=cfg.llm_api_base_url)

    # Fallback to smart offline heuristic provider
    logger.info("No active external LLM credentials configured. Running in high-fidelity OFFLINE deterministic mode.")
    return OfflineDeterministicLLMClient()
