"""Job Parsing Engine with Rule-based & LLM Extraction."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional
from src.config import AppSettings, load_yaml_config
from src.llm.client import BaseLLMClient, get_llm_client
from src.llm.prompts import load_prompt_template, render_prompt
from src.models.job import JobRecord, ParsedJob

logger = logging.getLogger(__name__)


class JobParser:
    """Parses raw job descriptions into structured ParsedJob objects."""

    def __init__(self, llm_client: Optional[BaseLLMClient] = None, settings: Optional[AppSettings] = None):
        self.settings = settings or AppSettings()
        self.llm = llm_client or get_llm_client(self.settings)
        self.scoring_config = load_yaml_config(self.settings.scoring_config_path)
        self.synonyms = self.scoring_config.get("synonyms", {})

    def parse(self, job_record: JobRecord) -> ParsedJob:
        """Parse raw job record into structured ParsedJob."""
        # 1. Rule-based extraction as baseline
        rule_extracted = self._rule_based_extract(job_record)

        # 2. LLM extraction for semantic understanding
        try:
            prompt_template = load_prompt_template("parse-job")
            system_prompt = (
                "You are a structured job-description parser. Extract only information "
                "supported by the supplied job text. Do not infer missing details. Return valid JSON."
            )
            user_prompt = render_prompt(prompt_template, {"job_text": job_record.description_raw})
            llm_result = self.llm.generate_json(system_prompt, user_prompt)
        except Exception as e:
            logger.warning(f"LLM parsing failed, using rule-based extraction: {e}")
            llm_result = {}

        # 3. Merge extractions cleanly
        parsed = self._merge_extractions(job_record, rule_extracted, llm_result)
        return parsed

    def _rule_based_extract(self, job: JobRecord) -> Dict[str, Any]:
        """Deterministic regex and keyword-based extraction."""
        text = job.description_raw

        # Experience extraction
        exp_min = job.experience_min
        exp_max = job.experience_max
        if exp_min is None:
            m = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years?|yrs?)", text, re.IGNORECASE)
            if m:
                exp_min = float(m.group(1))
                exp_max = float(m.group(2))
            else:
                m_single = re.search(r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s*)?experience", text, re.IGNORECASE)
                if m_single:
                    exp_min = float(m_single.group(1))

        # Skill detection through synonym mapping
        detected_skills = set()
        detected_tools = set()

        for group_name, syn_list in self.synonyms.items():
            for syn in syn_list:
                pattern = r"\b" + re.escape(syn) + r"\b"
                if re.search(pattern, text, re.IGNORECASE):
                    detected_skills.add(syn.title())
                    if group_name in ["google_ads", "meta_ads", "ga4", "gtm", "looker_studio", "linkedin_ads"]:
                        detected_tools.add(syn.title())

        # Standard marketing keywords
        catalog = [
            "Shopify", "Unbounce", "Hotjar", "Klaviyo", "AppsFlyer", "SEMrush", "A/B Testing",
            "CRO", "Performance Marketing", "Paid Search", "Paid Social", "Funnel Analysis",
            "ROAS Optimization", "CAC", "Salesforce Marketing Cloud", "Marketo", "DV360", "The Trade Desk", "Java", "Spring Boot"
        ]
        for item in catalog:
            if re.search(r"\b" + re.escape(item) + r"\b", text, re.IGNORECASE):
                detected_skills.add(item)
                if item not in ["Performance Marketing", "Paid Search", "Paid Social", "Funnel Analysis", "A/B Testing", "CRO", "ROAS Optimization"]:
                    detected_tools.add(item)

        return {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "employment_type": job.employment_type,
            "experience_min": exp_min,
            "experience_max": exp_max,
            "salary": job.salary,
            "must_have_skills": list(detected_skills),
            "platforms_and_tools": list(detected_tools),
            "uncertainties": [] if exp_min is not None else ["Experience requirement not explicitly specified in job text"],
        }

    def _merge_extractions(self, job: JobRecord, rule: Dict[str, Any], llm: Dict[str, Any]) -> ParsedJob:
        """Merge rule-based and LLM extractions safely."""
        # Preserve specific job title if already known
        title = job.title if job.title and job.title not in ["Untitled Role", "Target Marketing Role"] else (llm.get("title") or rule.get("title") or job.title)
        company = job.company if job.company and job.company not in ["Unknown Company", "Target Company"] else (llm.get("company") or rule.get("company") or job.company)
        location = job.location or llm.get("location") or rule.get("location") or ""
        employment_type = job.employment_type or llm.get("employment_type") or rule.get("employment_type") or "Full Time"

        exp_min = job.experience_min if job.experience_min is not None else (llm.get("experience_min") if llm.get("experience_min") is not None else rule.get("experience_min"))
        exp_max = job.experience_max if job.experience_max is not None else (llm.get("experience_max") if llm.get("experience_max") is not None else rule.get("experience_max"))
        salary = job.salary or llm.get("salary") or rule.get("salary")

        # Combine skills cleanly
        must_skills = list(dict.fromkeys((rule.get("must_have_skills", []) + llm.get("must_have_skills", []))))
        nice_skills = list(dict.fromkeys(llm.get("nice_to_have_skills", [])))
        tools = list(dict.fromkeys((rule.get("platforms_and_tools", []) + llm.get("platforms_and_tools", []))))
        responsibilities = llm.get("responsibilities", []) or [f"Execute and scale campaigns for {title}."]
        uncertainties = list(dict.fromkeys((rule.get("uncertainties", []) + llm.get("uncertainties", []))))

        return ParsedJob(
            job_id=job.job_id,
            title=title,
            company=company,
            location=location,
            employment_type=employment_type,
            experience_min=exp_min,
            experience_max=exp_max,
            salary=salary,
            must_have_skills=must_skills,
            nice_to_have_skills=nice_skills,
            platforms_and_tools=tools,
            responsibilities=responsibilities,
            education_requirements=llm.get("education_requirements", []),
            certifications=llm.get("certifications", []),
            keywords=list(dict.fromkeys(must_skills + tools)),
            uncertainties=uncertainties,
        )
