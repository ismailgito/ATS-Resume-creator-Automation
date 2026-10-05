"""End-to-End ATS Resume Pipeline Orchestrator."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from src.config import AppSettings, load_candidate_profile
from src.ingest.job_sources import IngestionManager
from src.models.job import JobRecord, ParsedJob
from src.models.profile import CandidateProfile
from src.models.resume import ReviewPackage, TailoredResume, ValidationReport
from src.models.score import MatchReport
from src.parse.job_parser import JobParser
from src.resume.docx_builder import build_docx_resume
from src.resume.generator import render_cover_note, render_markdown_resume
from src.resume.pdf_builder import build_pdf_resume
from src.resume.tailor import ResumeTailor
from src.score.scorer import MatchScorer
from src.tracker.db import ApplicationTrackerDB
from src.validate.validator import ResumeValidator

logger = logging.getLogger(__name__)


class ResumeAutomationPipeline:
    """Coordinates ingestion, parsing, scoring, tailoring, validation, and tracking."""

    def __init__(self, settings: Optional[AppSettings] = None):
        self.settings = settings or AppSettings()
        self.db = ApplicationTrackerDB()
        self.parser = JobParser(settings=self.settings)
        self.scorer = MatchScorer(settings=self.settings)
        self.tailor_engine = ResumeTailor(settings=self.settings)
        self.validator = ResumeValidator(settings=self.settings)

    def load_profile(self) -> CandidateProfile:
        """Load candidate profile from configured path."""
        data = load_candidate_profile(self.settings.candidate_profile_path)
        return CandidateProfile.from_dict(data)

    def process_job(
        self,
        job_record: JobRecord,
        candidate: Optional[CandidateProfile] = None,
        force_generate: bool = False,
    ) -> Tuple[MatchReport, Optional[ReviewPackage]]:
        """
        Process a job through the full pipeline:
        Ingest -> Parse -> Score -> (Tailor -> Render -> Validate -> Review Package)
        """
        cand = candidate or self.load_profile()

        # 1. Save raw job record to database
        self.db.save_job(job_record)

        # 2. Parse job
        parsed_job = self.parser.parse(job_record)

        # 3. Deterministic Match Scoring
        match_report = self.scorer.score(parsed_job, cand)
        self.db.save_match_report(match_report)

        min_thresh = self.settings.min_match_score

        # Check if score qualifies for tailoring
        if not force_generate and match_report.overall_score < min_thresh:
            logger.info(
                f"Job '{job_record.title}' scored {match_report.overall_score} (< {min_thresh}). "
                "Skipping resume generation."
            )
            return match_report, None

        # 4. Tailor Resume & Cover Note
        tailored, cover_note_dict = self.tailor_engine.tailor(parsed_job, cand, match_report)

        # 5. Prepare Output Directory (Company Name Format)
        raw_company = (job_record.company or "Company").strip()
        company_slug = re.sub(r'[^\w\s-]', '', raw_company)
        company_slug = re.sub(r'[\s]+', '-', company_slug).strip('-') or "Company"

        app_id = company_slug
        out_dir = self.settings.output_dir / app_id
        if out_dir.exists():
            app_id = f"{company_slug}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            out_dir = self.settings.output_dir / app_id

        out_dir.mkdir(parents=True, exist_ok=True)

        # 6. Render Artifacts (Company Name Formatted Files)
        # Markdown Resume
        md_content = render_markdown_resume(cand, tailored)
        resume_md_path = out_dir / f"{company_slug}_Resume.md"
        with open(resume_md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        # Cover Note
        cover_content = render_cover_note(cand, parsed_job, cover_note_dict)
        cover_note_path = out_dir / f"{company_slug}_Cover-Note.md"
        with open(cover_note_path, "w", encoding="utf-8") as f:
            f.write(cover_content)

        # DOCX Resume
        resume_docx_path = out_dir / f"{company_slug}_Resume.docx"
        build_docx_resume(cand, tailored, resume_docx_path)

        # PDF Resume
        resume_pdf_path = out_dir / f"{company_slug}_Resume.pdf"
        build_pdf_resume(cand, tailored, resume_pdf_path)

        # Match Report JSON
        match_report_path = out_dir / "match-report.json"
        with open(match_report_path, "w", encoding="utf-8") as f:
            json.dump(match_report.to_dict(), f, indent=2)

        # Change Log Markdown
        change_log_path = out_dir / "change-log.md"
        with open(change_log_path, "w", encoding="utf-8") as f:
            f.write(f"# Resume Tailoring Log for {job_record.title} at {job_record.company}\n\n")
            f.write(f"**Version ID:** {tailored.resume_version_id}\n")
            f.write(f"**Match Score:** {match_report.overall_score}/100\n\n")
            f.write("## Adaptations Made:\n")
            for item in tailored.change_log:
                f.write(f"- {item}\n")
            f.write("\n## Identified Skill Gaps:\n")
            if tailored.gap_list:
                for gap in tailored.gap_list:
                    f.write(f"- {gap}\n")
            else:
                f.write("- No significant gaps identified.\n")

        # 7. Validate Resume Quality Gate
        validation_report = self.validator.validate(cand, tailored)
        validation_report_path = out_dir / "validation-report.json"
        with open(validation_report_path, "w", encoding="utf-8") as f:
            json.dump(validation_report.to_dict(), f, indent=2)

        # 8. Create Review Package
        review_pkg = ReviewPackage(
            application_id=app_id,
            job_id=job_record.job_id,
            job_title=job_record.title,
            company=job_record.company,
            source_url=job_record.url,
            match_score=match_report.overall_score,
            recommendation=match_report.recommendation,
            output_directory=str(out_dir),
            resume_md_path=str(resume_md_path),
            resume_docx_path=str(resume_docx_path),
            resume_pdf_path=str(resume_pdf_path),
            cover_note_path=str(cover_note_path),
            match_report_path=str(match_report_path),
            validation_report_path=str(validation_report_path),
            change_log_path=str(change_log_path),
            status="review_ready" if validation_report.passed else "needs_attention",
        )

        # 9. Save in Tracker Database
        self.db.save_application(review_pkg)

        return match_report, review_pkg
