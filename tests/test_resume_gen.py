"""Unit tests for Resume and Document Generation."""

import pytest
from pathlib import Path
import tempfile
from src.config import load_candidate_profile, PROJECT_ROOT
from src.ingest.job_sources import IngestionManager
from src.models.profile import CandidateProfile
from src.parse.job_parser import JobParser
from src.resume.docx_builder import build_docx_resume
from src.resume.generator import render_cover_note, render_markdown_resume
from src.resume.pdf_builder import build_pdf_resume
from src.resume.tailor import ResumeTailor
from src.score.scorer import MatchScorer


@pytest.fixture
def candidate():
    data = load_candidate_profile(PROJECT_ROOT / "data/candidate-profile.json")
    return CandidateProfile.from_dict(data)


@pytest.fixture
def sample_job_and_report(candidate):
    sample = PROJECT_ROOT / "data/sample-jobs/01-perf-mktg-manager.json"
    job = IngestionManager.from_file(sample)[0]
    parsed = JobParser().parse(job)
    report = MatchScorer().score(parsed, candidate)
    return parsed, report


def test_resume_tailoring_and_rendering(candidate, sample_job_and_report):
    parsed, report = sample_job_and_report
    tailor = ResumeTailor()
    tailored, cover_note = tailor.tailor(parsed, candidate, report)

    # 1. Check Tailored Resume structure
    assert tailored.candidate_id == candidate.candidate_id
    assert len(tailored.skills) >= 3
    assert len(tailored.experience) >= 1
    assert "Mohamed" in candidate.full_name or "Ismail" in candidate.full_name

    # 2. Markdown Rendering (German Lebenslauf style is the default)
    md = render_markdown_resume(candidate, tailored)
    assert candidate.full_name in md
    assert candidate.contact.email in md
    assert "## Kurzprofil" in md
    assert "## Kenntnisse & Fähigkeiten" in md
    assert "## Berufserfahrung" in md
    assert "## Persönliche Daten" in md
    assert "# Lebenslauf" in md
    # US/international headings must NOT appear in the default (de) output
    assert "## Professional Summary" not in md
    assert "## Professional Experience" not in md

    # 3. Cover Note Rendering
    cover_md = render_cover_note(candidate, parsed, cover_note)
    assert candidate.full_name in cover_md
    assert parsed.company in cover_md

    # 4. DOCX and PDF Document Generation
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        docx_path = tmp_path / "test_resume.docx"
        build_docx_resume(candidate, tailored, docx_path)
        assert docx_path.exists()
        assert docx_path.stat().st_size > 5000  # valid docx file size

        pdf_path = tmp_path / "test_resume.pdf"
        build_pdf_resume(candidate, tailored, pdf_path)
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 1000  # valid pdf file size


def test_us_style_switch(candidate, sample_job_and_report, monkeypatch):
    """RESUME_STYLE=us must restore the classic English headings and layout."""
    monkeypatch.setenv("RESUME_STYLE", "us")
    parsed, report = sample_job_and_report
    tailor = ResumeTailor()
    tailored, cover_note = tailor.tailor(parsed, candidate, report)

    md = render_markdown_resume(candidate, tailored)
    assert "## Professional Summary" in md
    assert "## Core Competencies & Skills" in md
    assert "## Professional Experience" in md
    # German-only elements must be absent in us mode
    assert "# Lebenslauf" not in md
    assert "## Persönliche Daten" not in md
    assert "## Kurzprofil" not in md

    cover_md = render_cover_note(candidate, parsed, cover_note)
    assert "Anschreiben" not in cover_md
    assert "Application Cover Note" in cover_md


def test_de_cover_note_wrapper(candidate, sample_job_and_report):
    """Default style must render the German Anschreiben wrapper with English body."""
    parsed, report = sample_job_and_report
    tailor = ResumeTailor()
    tailored, cover_note = tailor.tailor(parsed, candidate, report)

    cover_md = render_cover_note(candidate, parsed, cover_note)
    assert "Anschreiben" in cover_md
    assert "Sehr geehrte Damen und Herren" in cover_md
    assert "Mit freundlichen Grüßen" in cover_md
    assert "Betreff" in cover_md
    # Body content stays English
    assert "Dear Hiring Team" not in cover_md
