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
from src.resume.layout import build_layout
from src.resume.pdf_builder import build_pdf_resume
from src.resume.tailor import ResumeTailor
from src.score.scorer import MatchScorer
from src.validate.human_tone import find_ai_tells


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

    # 2. Markdown Rendering (German Lebenslauf is the only format)
    md = render_markdown_resume(candidate, tailored)
    assert candidate.full_name in md
    assert candidate.contact.email in md
    for heading in (
        "# Lebenslauf",
        "## Persönliche Daten",
        "## Kurzprofil",
        "## Berufserfahrung",
        "## Ausbildung",
        "## Weiterbildung & Zertifikate",
        "## Kenntnisse",
        "## Sprachkenntnisse",
    ):
        assert heading in md, heading
    # Classic US headings must never appear
    assert "## Professional Summary" not in md
    assert "## Professional Experience" not in md
    assert "Key Achievements" not in md

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


def test_resume_style_env_var_is_ignored(candidate, sample_job_and_report, monkeypatch):
    """The project only produces the German format; the old RESUME_STYLE=us switch is gone."""
    monkeypatch.setenv("RESUME_STYLE", "us")
    parsed, report = sample_job_and_report
    tailored, cover_note = ResumeTailor().tailor(parsed, candidate, report)

    md = render_markdown_resume(candidate, tailored)
    assert "# Lebenslauf" in md
    assert "## Professional Summary" not in md
    assert "Anschreiben" in render_cover_note(candidate, parsed, cover_note)


def test_berlin_layout_structure(candidate, sample_job_and_report):
    parsed, report = sample_job_and_report
    tailored, _ = ResumeTailor().tailor(parsed, candidate, report)
    layout = build_layout(candidate, tailored)

    keys = [section.key for section in layout.sections]
    assert keys == [
        "personal_data", "summary", "experience", "education",
        "projects", "certifications", "skills", "languages",
    ]

    # Date column: German MM/YYYY ranges, newest role first
    experience = next(s for s in layout.sections if s.key == "experience")
    assert experience.entries[0].left == "07/2026 – 10/2026"
    assert experience.entries[1].left == "08/2023 – 11/2023"
    assert experience.entries[0].heading == "Digital Marketing Intern"
    assert experience.entries[0].detail.startswith("IntoAEC")

    # Closing: place, German date, name
    assert layout.place == "Chennai"
    assert layout.name == candidate.full_name


def test_markdown_is_a_two_column_table_with_closing_line(candidate, sample_job_and_report):
    parsed, report = sample_job_and_report
    tailored, _ = ResumeTailor().tailor(parsed, candidate, report)
    md = render_markdown_resume(candidate, tailored)

    assert "|:--|:--|" in md
    assert "| 07/2026 – 10/2026 |" in md
    assert "| Telefon |" in md
    assert "| German | A1" in md
    # "Ort, Datum" + name at the end
    assert md.rstrip().splitlines()[-1] == candidate.full_name
    assert "Chennai, " in md


def test_projects_do_not_repeat_role_bullets(candidate, sample_job_and_report):
    """Achievements already told in the IntoAEC bullets must not come back as a second section."""
    parsed, report = sample_job_and_report
    tailored, _ = ResumeTailor().tailor(parsed, candidate, report)
    projects = next(s for s in build_layout(candidate, tailored).sections if s.key == "projects")

    headings = " ".join(e.heading for e in projects.entries)
    assert "competitor ad scraping" in headings
    assert "Next.js" in headings
    assert "warm CPL" not in headings


def test_offline_text_reads_human(candidate, sample_job_and_report):
    parsed, report = sample_job_and_report
    tailored, cover_note = ResumeTailor().tailor(parsed, candidate, report)

    assert find_ai_tells(tailored.summary) == []
    assert find_ai_tells(cover_note["body"]) == []
    for role in tailored.experience:
        for bullet in role.bullets:
            assert find_ai_tells(bullet) == []

    # No near-duplicate skills like "Google Ads" + "Google Ads (SEA)" + "SEA"
    lowered = [s.lower() for s in tailored.skills]
    assert not ("sea" in lowered and "google ads (sea)" in lowered)
    assert len(set(lowered)) == len(lowered)

    # Cover note is job specific and in the first person
    assert parsed.title in cover_note["body"]
    assert parsed.company in cover_note["body"]
    assert cover_note["subject"] == f"Bewerbung als {parsed.title} - {parsed.company}"


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


def test_market_customisation_recipe_from_readme(candidate, sample_job_and_report, monkeypatch, tmp_path):
    """README section 18, Step 3: English headings, no title, 'Jun 2022' dates must render everywhere."""
    from src.resume import layout as layout_module
    from src.resume import sections as sections_module

    english = {
        "document_title": "",
        "personal_data": "Contact",
        "summary": "Professional Summary",
        "experience": "Professional Experience",
        "education": "Education",
        "projects": "Projects",
        "certifications": "Certifications",
        "skills": "Skills",
        "languages": "Languages",
    }
    for key, value in english.items():
        monkeypatch.setitem(sections_module.SECTIONS, key, value)

    def format_month(part):
        part = (part or "").strip()
        if len(part) >= 7 and part[4] == "-" and part[:4].isdigit() and part[5:7].isdigit():
            if 1 <= int(part[5:7]) <= 12:
                return f"{sections_module._MONTH_ABBR_EN[int(part[5:7]) - 1]} {part[:4]}"
        return part

    monkeypatch.setattr(sections_module, "format_month", format_month)
    monkeypatch.setattr(layout_module, "format_month", format_month)
    monkeypatch.setattr(layout_module, "format_period", lambda p: " – ".join(format_month(x.strip()) for x in p.split(" - ")))

    parsed, report = sample_job_and_report
    tailored, _ = ResumeTailor().tailor(parsed, candidate, report)

    md = render_markdown_resume(candidate, tailored)
    assert "## Professional Summary" in md
    assert "## Professional Experience" in md
    assert "| Jul 2026 – Oct 2026 |" in md
    assert "Lebenslauf" not in md
    assert not md.startswith("# \n") and "\n# \n" not in md

    build_docx_resume(candidate, tailored, tmp_path / "us.docx")
    build_pdf_resume(candidate, tailored, tmp_path / "us.pdf")
    assert (tmp_path / "us.docx").stat().st_size > 5000
    assert (tmp_path / "us.pdf").stat().st_size > 1000
