"""German (Berlin-style) tabular Lebenslauf layout, shared by the Markdown, DOCX and PDF renderers.

A German CV is a reverse-chronological table: dates (or a label) in a narrow left column,
the content in a wide right column. This module turns the candidate profile and the tailored
resume into that structure once, so all three output formats show identical content.

Section order:
    Persönliche Daten, Kurzprofil, Berufserfahrung, Ausbildung, Projekte,
    Weiterbildung & Zertifikate, Kenntnisse, Sprachkenntnisse
followed by place, date and name (the German "Ort, Datum, Unterschrift" closing).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from src.config import PROJECT_ROOT
from src.models.profile import CandidateProfile
from src.models.resume import TailoredResume
from src.resume.sections import (
    LABELS,
    SECTIONS,
    format_birth_date,
    format_month,
    format_period,
    today_date,
)
from src.resume.skill_utils import dedupe_skills

logger = logging.getLogger(__name__)

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png"}


@dataclass
class Entry:
    """One row of the CV table. An empty ``left`` means the entry spans the full width."""

    left: str = ""
    heading: str = ""
    detail: str = ""
    text: str = ""
    bullets: List[str] = field(default_factory=list)


@dataclass
class Section:
    key: str
    title: str
    entries: List[Entry]


@dataclass
class Layout:
    title: str
    name: str
    headline: str
    photo: Optional[Path]
    sections: List[Section]
    place: str
    date: str


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_NUMBER = re.compile(r"(?<![A-Za-z])\d[\d,.]*")


def _numbers(text: str) -> set:
    return {m.group(0).rstrip(".,") for m in _NUMBER.finditer(text)}


def is_covered(statement: str, bullets: List[str]) -> bool:
    """True when most of the statement's figures already appear in the given bullets.

    Used to avoid printing the same achievement twice (once as a role bullet, once as a
    project). Statements without figures are never treated as covered.
    """
    wanted = _numbers(statement)
    if not wanted:
        return False
    present = _numbers(" ".join(bullets))
    return sum(1 for n in wanted if n in present) / len(wanted) >= 0.5


def resolve_photo(candidate: CandidateProfile) -> Optional[Path]:
    """Return the photo path if one is configured and the file really exists."""
    if not candidate.photo:
        return None
    path = Path(candidate.photo)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if path.suffix.lower() not in PHOTO_SUFFIXES:
        logger.warning("Photo '%s' ignored: use a .jpg or .png file.", candidate.photo)
        return None
    if not path.exists():
        logger.warning("Photo '%s' not found, rendering without photo.", candidate.photo)
        return None
    return path


def signature_place(candidate: CandidateProfile) -> str:
    """City for the closing line: first part of the address, else of the location."""
    # An address such as "Musterstraße 1, 10115 Berlin" -> the part that follows the postcode
    for part in candidate.address.split(","):
        match = re.match(r"\s*\d{4,5}\s+(.+)", part)
        if match:
            return match.group(1).strip()
    source = candidate.address or candidate.contact.location or candidate.location
    return source.split(",")[0].strip()


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #

def _personal_entries(candidate: CandidateProfile) -> List[Entry]:
    c = candidate.contact
    rows: List[Tuple[str, str]] = []
    if candidate.address:
        rows.append((LABELS["address"], candidate.address))
    elif c.location:
        rows.append((LABELS["location"], c.location))
    rows.append((LABELS["phone"], c.phone))
    rows.append((LABELS["email"], c.email))
    if candidate.date_of_birth:
        rows.append((LABELS["date_of_birth"], format_birth_date(candidate.date_of_birth)))
    if candidate.place_of_birth:
        rows.append((LABELS["place_of_birth"], candidate.place_of_birth))
    if candidate.nationality:
        rows.append((LABELS["nationality"], candidate.nationality))
    if candidate.work_authorization:
        rows.append((LABELS["work_permit"], candidate.work_authorization))
    rows.append((LABELS["linkedin"], c.linkedin))
    rows.append((LABELS["portfolio"], c.portfolio))
    rows.append((LABELS["github"], c.github))
    return [Entry(left=label, text=value) for label, value in rows if value]


def _experience_entries(tailored: TailoredResume) -> List[Entry]:
    return [
        Entry(
            left=format_period(role.period),
            heading=role.title,
            detail=", ".join(p for p in (role.company, role.location) if p),
            bullets=list(role.bullets),
        )
        for role in tailored.experience
    ]


def _education_entries(candidate: CandidateProfile) -> List[Entry]:
    entries = []
    for edu in candidate.education:
        years = " – ".join(str(y) for y in (edu.start_year, edu.end_year) if y)
        grade = f"Grade: {edu.grade}" if edu.grade else ""
        entries.append(Entry(left=years, heading=edu.degree, detail=edu.institution, text=grade))
    return entries


def _project_entries(candidate: CandidateProfile, tailored: TailoredResume) -> List[Entry]:
    """Achievements that are not already part of a role's bullets (side projects, tools built)."""
    role_bullets = [b for role in tailored.experience for b in role.bullets]
    return [
        Entry(left=ach.time_period, heading=ach.metric, text=ach.statement)
        for ach in candidate.achievements
        if not is_covered(ach.statement, role_bullets)
    ]


def _certification_entries(candidate: CandidateProfile) -> List[Entry]:
    return [
        Entry(left=format_month(cert.date), heading=cert.name, detail=cert.issuer)
        for cert in candidate.certifications
    ]


def _skill_entries(candidate: CandidateProfile, tailored: TailoredResume) -> List[Entry]:
    expertise = dedupe_skills(tailored.skills or candidate.skills, also_covered_by=candidate.tools)
    entries = []
    if expertise:
        entries.append(Entry(left=LABELS["skills_expertise"], text=", ".join(expertise)))
    if candidate.tools:
        entries.append(Entry(left=LABELS["skills_tools"], text=", ".join(candidate.tools)))
    return entries


def _language_entries(candidate: CandidateProfile) -> List[Entry]:
    return [
        Entry(left=lang.get("language", ""), text=lang.get("level", ""))
        for lang in candidate.languages
        if lang.get("language")
    ]


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def build_layout(candidate: CandidateProfile, tailored: TailoredResume) -> Layout:
    """Assemble the full German CV structure. Sections without content are left out."""
    summary_entries = [Entry(text=tailored.summary)] if tailored.summary else []

    ordered = [
        ("personal_data", _personal_entries(candidate)),
        ("summary", summary_entries),
        ("experience", _experience_entries(tailored)),
        ("education", _education_entries(candidate)),
        ("projects", _project_entries(candidate, tailored)),
        ("certifications", _certification_entries(candidate)),
        ("skills", _skill_entries(candidate, tailored)),
        ("languages", _language_entries(candidate)),
    ]
    sections = [Section(key=key, title=SECTIONS[key], entries=entries) for key, entries in ordered if entries]

    return Layout(
        title=SECTIONS["document_title"],
        name=candidate.full_name,
        headline=candidate.headline,
        photo=resolve_photo(candidate),
        sections=sections,
        place=signature_place(candidate),
        date=today_date(),
    )
