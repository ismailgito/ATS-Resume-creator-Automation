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
    assert "Aarav" in candidate.full_name

    # 2. Markdown Rendering
    md = render_markdown_resume(candidate, tailored)
    assert candidate.full_name in md
    assert candidate.contact.email in md
    assert "## Professional Summary" in md
    assert "## Core Competencies & Skills" in md
    assert "## Professional Experience" in md

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
