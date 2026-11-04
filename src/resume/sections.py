"""Single source of truth for the German (Berlin-style) Lebenslauf: labels and date formats.

The project only produces one format: a German tabular Lebenslauf with English body text.
Headings and labels are German (that is the *format*), everything the candidate or the
tailoring engine writes stays English (that is the *language*).

Markdown, DOCX and PDF all render from ``src/resume/layout.py``, which pulls its labels
from here, so the three formats can never drift apart.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict

# --------------------------------------------------------------------------- #
# Section headings (order is defined in layout.py)
# --------------------------------------------------------------------------- #

SECTIONS: Dict[str, str] = {
    "document_title": "Lebenslauf",
    "personal_data": "Persönliche Daten",
    "summary": "Kurzprofil",
    "experience": "Berufserfahrung",
    "education": "Ausbildung",
    "projects": "Projekte",
    "certifications": "Weiterbildung & Zertifikate",
    "skills": "Kenntnisse",
    "languages": "Sprachkenntnisse",
}

# Row labels and wrapper text used inside sections and the cover note
LABELS: Dict[str, str] = {
    "address": "Anschrift",
    "location": "Wohnort",
    "phone": "Telefon",
    "email": "E-Mail",
    "date_of_birth": "Geburtsdatum",
    "place_of_birth": "Geburtsort",
    "nationality": "Staatsangehörigkeit",
    "work_permit": "Arbeitserlaubnis",
    "linkedin": "LinkedIn",
    "portfolio": "Portfolio",
    "github": "GitHub",
    "skills_expertise": "Fachkenntnisse",
    "skills_tools": "Tools & Plattformen",
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
}


def get_sections() -> Dict[str, str]:
    """Return the section heading map."""
    return SECTIONS


def get_sub_labels() -> Dict[str, str]:
    """Return the row label / wrapper text map."""
    return LABELS


# --------------------------------------------------------------------------- #
# Date formatting (German conventions)
# --------------------------------------------------------------------------- #

_MONTHS_DE = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)

_MONTH_ABBR_EN = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def today_date() -> str:
    """Current date in German long form, e.g. '04. November 2026'."""
    now = datetime.now()
    return f"{now.day:02d}. {_MONTHS_DE[now.month - 1]} {now.year}"


def format_month(part: str) -> str:
    """Normalize one date to 'MM/YYYY' (or 'YYYY'). Unknown shapes and 'Present' pass through.

    Handles '2026-07', '2026-07-15', 'Jul 2026', 'July 2026', '07/2026' and bare '2026'.
    """
    part = (part or "").strip()
    if not part:
        return part

    # ISO 'YYYY-MM-DD'
    if len(part) >= 10 and part[4] == "-" and part[7] == "-" and part[:4].isdigit():
        year, month = part[:4], part[5:7]
        if month.isdigit() and 1 <= int(month) <= 12:
            return f"{month}/{year}"
    # ISO 'YYYY-MM'
    if len(part) == 7 and part[4] == "-" and part[:4].isdigit() and part[5:7].isdigit():
        return f"{part[5:7]}/{part[:4]}"
    # 'Mon YYYY' / 'Month YYYY' (English)
    pieces = part.split()
    if len(pieces) == 2 and pieces[1].isdigit() and len(pieces[1]) == 4:
        for idx, abbr in enumerate(_MONTH_ABBR_EN, start=1):
            if pieces[0].lower().startswith(abbr.lower()):
                return f"{idx:02d}/{pieces[1]}"
    return part


def format_period(period: str) -> str:
    """Normalize 'start - end' to German CV style, e.g. '07/2026 – 10/2026'."""
    if not period:
        return period
    parts = [p.strip() for p in period.replace("–", "-").replace("—", "-").split(" - ")]
    if len(parts) == 1:
        return format_month(parts[0])
    if len(parts) != 2:
        return period
    return f"{format_month(parts[0])} – {format_month(parts[1])}"


def format_birth_date(value: str) -> str:
    """Format an ISO birth date as German 'DD.MM.YYYY'. Anything else passes through."""
    value = (value or "").strip()
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return value
