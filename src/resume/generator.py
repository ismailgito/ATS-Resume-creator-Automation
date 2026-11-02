"""Template rendering for Markdown resumes and cover notes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
from jinja2 import Environment, FileSystemLoader
from src.config import PROJECT_ROOT
from src.models.job import ParsedJob
from src.models.profile import CandidateProfile
from src.models.resume import TailoredResume
from src.resume.sections import format_period, get_sections, get_style, get_sub_labels, today_date

TEMPLATES_DIR = PROJECT_ROOT / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _formatted_periods(tailored: TailoredResume, style: str) -> Dict[int, str]:
    """Map role index -> period reformatted for the style (non-destructive)."""
    return {idx: format_period(role.period, style) for idx, role in enumerate(tailored.experience)}


def render_markdown_resume(candidate: CandidateProfile, tailored: TailoredResume) -> str:
    """Render full ATS-compliant Markdown resume from Jinja2 template."""
    style = get_style()
    template = jinja_env.get_template("resume.md.j2")
    return template.render(
        candidate=candidate,
        tailored=tailored,
        period_overrides=_formatted_periods(tailored, style),
        style=style,
        sections=get_sections(style),
        sublabels=get_sub_labels(style),
        today_date=today_date(style),
    )


def render_cover_note(candidate: CandidateProfile, job: ParsedJob, cover_note: Dict[str, Any]) -> str:
    """Render application cover note from Jinja2 template."""
    style = get_style()
    template = jinja_env.get_template("cover-note.md.j2")
    return template.render(
        candidate=candidate,
        job=job,
        cover_note=cover_note,
        style=style,
        sections=get_sections(style),
        sublabels=get_sub_labels(style),
        today_date=today_date(style),
    )
