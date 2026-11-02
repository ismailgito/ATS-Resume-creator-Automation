"""Single shared source of truth for resume section headings, order, and date formats.

All three renderers (Markdown Jinja2 template, DOCX builder, PDF builder) must pull
section labels from here so the styles can never drift apart again.

Styles:
  - "de": German Lebenslauf format (default) — German section headings, German date
          conventions, optional "Persoenliche Daten" block. Body content stays in the
          language produced by the tailoring engine (English by default).
  - "us": Classic US/international format — the original English section headings.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, Optional

# --------------------------------------------------------------------------- #
# Section labels per style
# --------------------------------------------------------------------------- #

_SECTIONS_DE: Dict[str, str] = {
    "document_title": "Lebenslauf",
    "personal_data": "Persönliche Daten",
    "summary": "Kurzprofil",
    "skills": "Kenntnisse & Fähigkeiten",
    "experience": "Berufserfahrung",
    "achievements": "Erfolge & Wirkung",
    "education": "Ausbildung & Zertifikate",
}

_SECTIONS_US: Dict[str, str] = {
    "document_title": "",
    "personal_data": "",
    "summary": "Professional Summary",
    "skills": "Core Competencies & Skills",
    "experience": "Professional Experience",
    "achievements": "Key Achievements & Impact",
    "education": "Education & Certifications",
}

SECTION_STYLES: Dict[str, Dict[str, str]] = {
    "de": _SECTIONS_DE,
    "us": _SECTIONS_US,
}

# Sub-labels used inside sections (kept consistent across renderers)
SUB_LABELS: Dict[str, Dict[str, str]] = {
    "de": {
        "platforms_tools": "Plattformen & Tools",
        "education": "Ausbildung",
        "certifications": "Zertifikate",
        "evidence_prefix": "",
        "present": "Present",
        "page": "Seite",
        "cover_note_title": "Anschreiben",
        "cover_to": "An",
        "cover_regarding": "Bewerbung als",
        "cover_candidate": "Bewerber",
        "cover_date": "Datum",
        "cover_subject": "Betreff",
        "cover_greeting": "Sehr geehrte Damen und Herren,",
        "cover_closing": "Mit freundlichen Grüßen",
    },
    "us": {
        "platforms_tools": "Platforms & Tools",
        "education": "Education",
        "certifications": "Certifications",
        "evidence_prefix": "Evidence: ",
        "present": "Present",
        "page": "Page",
        "cover_note_title": "Application Cover Note",
        "cover_to": "To",
        "cover_regarding": "Regarding",
        "cover_candidate": "Candidate",
        "cover_date": "Date",
        "cover_subject": "Subject",
        "cover_greeting": "Dear Hiring Team,",
        "cover_closing": "Sincerely",
    },
}


def normalize_style(style: Optional[str]) -> str:
    """Normalize a style string to a supported key ('de' or 'us'). Unknown -> 'de'."""
    if not style:
        return "de"
    value = str(style).strip().lower().replace("_", "-")
    if value in ("us", "en", "en-us", "en-gb", "uk", "us-intl"):
        return "us"
    return "de"


def get_style() -> str:
    """Resolve active style with precedence: RESUME_STYLE env var > policy.yaml > 'de'.

    policy.yaml key: ats_formatting.resume_style (values: 'de' or 'us').
    Falls back to 'de' (German default) on any error.
    """
    env_value = os.getenv("RESUME_STYLE")
    if env_value is not None and env_value.strip():
        return normalize_style(env_value)

    try:
        from src.config import AppSettings, load_yaml_config

        settings = AppSettings()
        if settings.resume_style:
            return normalize_style(settings.resume_style)
        policy = load_yaml_config(settings.policy_config_path)
        raw = (policy.get("ats_formatting") or {}).get("resume_style")
        if raw:
            return normalize_style(raw)
    except Exception:
        pass
    return "de"


def get_sections(style: Optional[str] = None) -> Dict[str, str]:
    """Return the section-label map for the requested (or active) style."""
    return SECTION_STYLES[normalize_style(style) if style else get_style()]


def get_sub_labels(style: Optional[str] = None) -> Dict[str, str]:
    """Return the sub-label map for the requested (or active) style."""
    return SUB_LABELS[normalize_style(style) if style else get_style()]


# --------------------------------------------------------------------------- #
# Date formatting
# --------------------------------------------------------------------------- #

_MONTHS_DE = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)

_MONTH_ABBR_EN = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def today_date(style: Optional[str] = None) -> str:
    """Current date formatted per style: de -> '02. November 2026', us -> 'November 02, 2026'."""
    now = datetime.now()
    active = normalize_style(style) if style else get_style()
    if active == "de":
        return f"{now.day:02d}. {_MONTHS_DE[now.month - 1]} {now.year}"
    return now.strftime("%B %d, %Y")


def format_period(period: str, style: Optional[str] = None) -> str:
    """Normalize a date period string for display.

    Handles common input shapes: '2022-06 - Present', '2022-06-15 - 2024-03-01',
    'Jun 2022 - Present', '2022 - Present'.

    - de: German CV convention 'MM/YYYY' ('06/2022 - Present').
    - us: unchanged input (already English convention, e.g. 'Jun 2022 - Present').
    """
    if not period:
        return period
    active = normalize_style(style) if style else get_style()
    if active != "de":
        return period

    parts = [p.strip() for p in period.split(" - ")]
    if len(parts) != 2:
        return period

    def _de_part(part: str) -> str:
        part = part.strip()
        # ISO 'YYYY-MM-DD'
        if len(part) >= 10 and part[4] == "-" and part[7] == "-" and part[:4].isdigit():
            year, month = part[:4], part[5:7]
            if month.isdigit() and 1 <= int(month) <= 12:
                return f"{month}/{year}"
        # ISO 'YYYY-MM'
        if len(part) == 7 and part[4] == "-" and part[:4].isdigit() and part[5:7].isdigit():
            return f"{part[5:7]}/{part[:4]}"
        # 'Mon YYYY' (English abbreviation)
        for idx, name in enumerate(_MONTH_ABBR_EN, start=1):
            if part.lower().startswith(name.lower()) and len(part) > 4:
                year = part[len(name):].strip()
                if year.isdigit():
                    return f"{idx:02d}/{year}"
        # bare 'YYYY'
        if len(part) == 4 and part.isdigit():
            return part
        # 'Present' and anything else passes through untouched
        return part

    return f"{_de_part(parts[0])} - {_de_part(parts[1])}"
