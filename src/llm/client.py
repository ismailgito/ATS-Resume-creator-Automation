"""LLM Provider Interface and Fallback Implementations."""

from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
import requests
from src.config import AppSettings
from src.llm.guard import LLMUsageGuard, classify_error, get_guard

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
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
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
        resp = requests.post(self.base_url, headers=headers, json=payload, timeout=60)
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

        # Extract actual job text if wrapped in prompt template
        m_job = re.search(r"JOB TEXT:\s*(.*)", text, re.DOTALL | re.IGNORECASE)
        job_content = m_job.group(1).strip() if m_job else text.strip()
        if not job_content or len(job_content) < 30:
            return {
                "title": "",
                "company": "",
                "location": "",
                "employment_type": "",
                "experience_min": None,
                "experience_max": None,
                "salary": None,
                "must_have_skills": [],
                "nice_to_have_skills": [],
                "platforms_and_tools": [],
                "responsibilities": [],
                "education_requirements": [],
                "certifications": [],
                "keywords": [],
                "uncertainties": ["Empty or unparseable job description"],
            }

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
            "Salesforce Marketing Cloud", "Marketo", "DV360", "The Trade Desk", "HubSpot", "Java", "Spring Boot",
            "Python", "FastAPI", "Docker", "Kubernetes", "AWS", "GCP", "RAG", "LLM", "LangChain", "Git"
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
            "must_have_skills": found_skills[:6] if found_skills else [],
            "nice_to_have_skills": found_skills[6:12] if len(found_skills) > 6 else [],
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
        # Offline mode has no model to write with. Returning nothing makes ResumeTailor use its
        # own job-aware, fact-based builders instead of a canned job-independent text.
        return {}

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
        # Same reason as _mock_tailor_resume: ResumeTailor builds the offline cover note itself.
        return {}


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


class FallbackLLMClient(BaseLLMClient):
    """Live LLM with automatic fallback to the offline engine when the usage limit is hit.

    * Limit or credit exhausted (HTTP 402/429 with quota wording): the guard is tripped, this
      call is answered offline, and so is every later call that day, so the resume in progress
      and all pending ones are still produced.
    * Short rate limit (HTTP 429): retried a couple of times, honouring Retry-After.
    * Any other failure is re-raised so the caller's own per-call fallback applies; after a few
      in a row the LLM is skipped for the rest of the run.
    """

    RETRY_DELAYS = (2.0, 6.0)
    MAX_RETRY_AFTER = 30.0

    def __init__(
        self,
        live: BaseLLMClient,
        offline: BaseLLMClient,
        guard: LLMUsageGuard,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.live = live
        self.offline = offline
        self.guard = guard
        self._sleep = sleep

    def _offline(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        self.guard.note_offline_call()
        return self.offline.generate_json(system_prompt, user_prompt)

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if not self.guard.llm_available():
            return self._offline(system_prompt, user_prompt)

        attempt = 0
        while True:
            try:
                result = self.live.generate_json(system_prompt, user_prompt)
            except Exception as exc:  # noqa: BLE001
                kind, detail = classify_error(exc)
                if kind == "limit_soft" and attempt < len(self.RETRY_DELAYS):
                    self._sleep(self._retry_delay(exc, self.RETRY_DELAYS[attempt]))
                    attempt += 1
                    continue
                if kind in ("limit_hard", "limit_soft"):
                    self.guard.trip(detail)
                    return self._offline(system_prompt, user_prompt)
                self.guard.record_failure(detail)
                raise
            self.guard.record_success()
            return result

    def _retry_delay(self, exc: BaseException, default: float) -> float:
        header = getattr(getattr(exc, "response", None), "headers", None) or {}
        try:
            return min(float(header.get("Retry-After", default)), self.MAX_RETRY_AFTER)
        except (TypeError, ValueError):
            return default


def _build_live_client(cfg: AppSettings) -> Optional[BaseLLMClient]:
    """Create the live provider client for the configured credentials, or None if there are none."""
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

    return None


def get_llm_client(settings: Optional[AppSettings] = None) -> BaseLLMClient:
    """Factory: live LLM wrapped with automatic offline fallback, or the offline engine alone."""
    cfg = settings or AppSettings()
    live = _build_live_client(cfg)

    if live is None:
        logger.info("No active external LLM credentials configured. Running in high-fidelity OFFLINE deterministic mode.")
        return OfflineDeterministicLLMClient()

    if not cfg.llm_auto_fallback:
        return live
    return FallbackLLMClient(live, OfflineDeterministicLLMClient(), get_guard(cfg))
