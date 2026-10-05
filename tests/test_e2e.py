"""End-to-End Pipeline Acceptance Test."""

import pytest
from pathlib import Path
from src.config import PROJECT_ROOT
from src.ingest.job_sources import IngestionManager
from src.pipeline import ResumeAutomationPipeline


def test_full_pipeline_end_to_end():
    pipeline = ResumeAutomationPipeline()
    sample_file = PROJECT_ROOT / "data/sample-jobs/01-perf-mktg-manager.json"

    jobs = IngestionManager.from_file(sample_file)
    assert len(jobs) == 1

    report, review_pkg = pipeline.process_job(jobs[0], force_generate=True)

    # 1. Match report verification
    assert report.overall_score >= 80.0
    assert report.recommendation == "apply_review"

    # 2. Review package verification
    assert review_pkg is not None
    assert Path(review_pkg.resume_md_path).exists()
    assert Path(review_pkg.resume_docx_path).exists()
    assert Path(review_pkg.resume_pdf_path).exists()
    assert Path(review_pkg.cover_note_path).exists()
    assert Path(review_pkg.match_report_path).exists()
    assert Path(review_pkg.validation_report_path).exists()
    assert Path(review_pkg.change_log_path).exists()

    # 3. File sizes positive and non-empty
    assert Path(review_pkg.resume_docx_path).stat().st_size > 1000
    assert Path(review_pkg.resume_pdf_path).stat().st_size > 1000

    # 4. Status is review ready
    assert review_pkg.status == "review_ready"
