"""Template rendering for the German Markdown resume and cover note."""

from __future__ import annotations

from typing import Any, Dict
from jinja2 import Environment, FileSystemLoader
from src.config import PROJECT_ROOT
from src.models.job import ParsedJob
from src.models.profile import CandidateProfile
from src.models.resume import TailoredResume
from src.resume.layout import Entry, build_layout
from src.resume.sections import get_sub_labels, today_date

TEMPLATES_DIR = PROJECT_ROOT / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _md_cell(entry: Entry) -> str:
    """Right-hand table cell for one entry: heading, detail, text and bullets joined by <br>."""
    lines = []
    if entry.heading:
        lines.append(f"**{_md_escape(entry.heading)}**")
    if entry.detail:
        lines.append(_md_escape(entry.detail))
    if entry.text:
        lines.append(_md_escape(entry.text))
    lines.extend(f"• {_md_escape(b)}" for b in entry.bullets)
    return "<br>".join(lines)


jinja_env.filters["md_cell"] = _md_cell
jinja_env.filters["md_escape"] = _md_escape


def render_markdown_resume(candidate: CandidateProfile, tailored: TailoredResume) -> str:
    """Render the German tabular Lebenslauf as Markdown."""
    template = jinja_env.get_template("resume.md.j2")
    return template.render(layout=build_layout(candidate, tailored))


def render_cover_note(candidate: CandidateProfile, job: ParsedJob, cover_note: Dict[str, Any]) -> str:
    """Render the German-wrapped cover note (Anschreiben) with an English body."""
    template = jinja_env.get_template("cover-note.md.j2")
    return template.render(
        candidate=candidate,
        job=job,
        cover_note=cover_note,
        sublabels=get_sub_labels(),
        today_date=today_date(),
    )
