"""Template rendering for Markdown resumes and cover notes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from jinja2 import Environment, FileSystemLoader
from src.config import PROJECT_ROOT
from src.models.job import ParsedJob
from src.models.profile import CandidateProfile
from src.models.resume import TailoredResume

TEMPLATES_DIR = PROJECT_ROOT / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_markdown_resume(candidate: CandidateProfile, tailored: TailoredResume) -> str:
    """Render full ATS-compliant Markdown resume from Jinja2 template."""
    template = jinja_env.get_template("resume.md.j2")
    return template.render(
        candidate=candidate,
        tailored=tailored,
        today_date=datetime.now(timezone.utc).strftime("%B %d, %Y"),
    )


def render_cover_note(candidate: CandidateProfile, job: ParsedJob, cover_note: Dict[str, Any]) -> str:
    """Render application cover note from Jinja2 template."""
    template = jinja_env.get_template("cover-note.md.j2")
    return template.render(
        candidate=candidate,
        job=job,
        cover_note=cover_note,
        today_date=datetime.now(timezone.utc).strftime("%B %d, %Y"),
    )
