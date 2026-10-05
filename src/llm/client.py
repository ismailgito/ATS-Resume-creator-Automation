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
        resp = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=60)
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
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt + "\n\nProvide the response strictly as valid JSON."},
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
        }
        resp = requests.post(f"{self.base_url}/messages", headers=headers, json=payload, timeout=60)
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
        if "score the job against the candidate profile" in prompt_lower or "candidate profile:" in prompt_lower and "parsed job:" in prompt_lower:
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
            "location": "Bengaluru / Remote",
            "employment_type": "Full Time",
            "experience_min": exp_min,
            "experience_max": exp_max,
            "salary": None,
            "must_have_skills": found_skills[:4] if found_skills else ["Digital Marketing"],
            "nice_to_have_skills": found_skills[4:8] if len(found_skills) > 4 else [],
            "platforms_and_tools": found_skills,
            "responsibilities": [
                "Execute and optimize paid acquisition campaigns.",
                "Track and report ROAS and CAC metrics.",
                "Conduct A/B creative tests and landing page optimization."
            ],
            "education_requirements": ["Bachelor's Degree"],
            "certifications": [],
            "keywords": found_skills,
            "uncertainties": []
        }

    def _mock_score_job(self, user_prompt: str) -> Dict[str, Any]:
        return {
            "overall_score": 82.5,
            "score_breakdown": {
                "title_role_fit": 18.0,
                "required_skills": 22.5,
                "platform_tools": 13.5,
                "experience_fit": 14.0,
                "industry_fit": 8.5,
                "location_fit": 4.5,
                "achievement_relevance": 8.5
            },
            "matched_requirements": ["Google Ads", "Meta Ads", "GA4", "GTM", "ROAS Optimization"],
            "missing_requirements": [],
            "uncertain_requirements": [],
            "recommendation": "apply_review",
            "reason": "Strong match with candidate's 2.5-year performance marketing background and paid advertising track record."
        }

    def _mock_tailor_resume(self, user_prompt: str) -> Dict[str, Any]:
        return {
            "summary": (
                "Data-driven Performance Marketing Specialist with 2.5 years of experience executing full-funnel "
                "acquisition strategies across Google Ads and Meta Ads Manager. Scaled monthly ad spends to INR 25L+ "
                "while improving blended ROAS to 3.8x. Proven expertise in GA4 server-side tracking, GTM, and rapid A/B testing."
            ),
            "skills": [
                "Performance Marketing",
                "Google Ads (Search & PMax)",
                "Meta Ads Manager",
                "Conversion Rate Optimization (CRO)",
                "GA4 & GTM Server-Side Tracking",
                "A/B Testing & Funnel Analysis",
                "Looker Studio Reporting"
            ],
            "experience": [
                {
                    "company": "Klarity Digital Media",
                    "title": "Performance Marketing Specialist",
                    "location": "Bengaluru, India",
                    "period": "2024-03 - Present",
                    "bullets": [
                        "Scaled Google and Meta advertising budgets from INR 8L/month to INR 25L/month while improving blended ROAS from 2.6x to 3.8x.",
                        "Decreased customer acquisition cost (CAC) by 32% through search query sculpting and high-intent PMax asset group redesign.",
                        "Architected server-side GA4 and GTM tracking setup, capturing 18% previously unrecorded conversions via Meta CAPI.",
                        "Formulated and executed account-level Google Ads (Search, Performance Max) and Meta Ads (Advantage+ Shopping, Retargeting) strategies."
                    ]
                },
                {
                    "company": "Nexus Growth Labs",
                    "title": "Digital Marketing Associate",
                    "location": "Bengaluru, India",
                    "period": "2023-01 - 2024-02",
                    "bullets": [
                        "Managed daily keyword bidding, ad copy drafting, and negative keyword pruning across Google Search accounts.",
                        "Optimized INR 5L/month Meta advertising spend targeting tiered lookalike and interest audiences.",
                        "Conducted landing page heat map audits in Hotjar, generating recommendations that lifted signup rate by 14%."
                    ]
                }
            ],
            "education": [
                {
                    "institution": "Visvesvaraya Technological University",
                    "degree": "Bachelor of Engineering (B.E.) in Information Science",
                    "period": "2018 - 2022"
                }
            ],
            "certifications": [
                {"name": "Google Ads Search Certification", "issuer": "Google Skillshop", "date": "2024-05"},
                {"name": "Google Ads Measurement Certification", "issuer": "Google Skillshop", "date": "2024-06"},
                {"name": "Meta Certified Digital Marketing Associate", "issuer": "Meta Blueprint", "date": "2024-01"}
            ],
            "gap_list": [],
            "change_log": [
                "Emphasized verified ROAS scale (3.8x) and CAC reduction (32%) for target role requirements.",
                "Promoted GA4 and GTM technical tracking achievements to match analytics specifications.",
                "Reordered bullets to lead with highest business-impact metrics."
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
        return {
            "subject": "Application for Performance Marketing Role - Aarav Sharma",
            "body": (
                "I am excited to apply for this performance marketing position. Over the past 2.5 years, "
                "I have managed cumulative monthly advertising budgets exceeding INR 25 Lakhs across Google Ads "
                "and Meta Ads Manager, scaling revenue by 140% while driving blended ROAS to 3.8x. "
                "My experience with technical web analytics—specifically GA4 server-side containers and GTM—combined "
                "with continuous A/B testing aligns directly with your acquisition targets. "
                "I look forward to discussing how I can deliver measurable growth for your campaigns."
            ),
            "claims_used": [
                "2.5 years experience in Performance Marketing",
                "Managed monthly ad spend exceeding INR 25L on Google & Meta Ads",
                "Scaled revenue 140% at 3.8x ROAS",
                "Server-side GA4 and GTM implementation"
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
