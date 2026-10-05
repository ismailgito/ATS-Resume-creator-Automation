"""Command Line Interface for ATS Resume Automation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from src.config import AppSettings, PROJECT_ROOT
from src.ingest.job_sources import IngestionManager
from src.pipeline import ResumeAutomationPipeline
from src.tracker.analytics import format_report_markdown, generate_tracking_report
from src.tracker.db import ApplicationTrackerDB


def cmd_check_env(args):
    """Check credentials and system configuration status."""
    settings = AppSettings()
    status = settings.credential_status()

    print("\n" + "=" * 65)
    print("       ATS RESUME AUTOMATION - SYSTEM & CREDENTIAL STATUS       ")
    print("=" * 65)
    print(f"Project Directory : {PROJECT_ROOT}")
    print(f"Candidate Profile : {settings.candidate_profile_path} ({'Found' if settings.candidate_profile_path.exists() else 'Missing'})")
    print(f"Database URL      : {settings.database_url}")
    print(f"Current LLM Mode  : {settings.llm_provider.upper()}")
    print("-" * 65)
    print("CREDENTIALS STATUS:")
    for cred, is_set in status.items():
        symbol = "[OK] Configured" if is_set else "[--] Not configured (Offline mode ready)"
        print(f"  * {cred.replace('_', ' ').title():<22}: {symbol}")

    print("-" * 65)
    if settings.has_llm_credentials():
        print(">> Status: Live LLM provider is ACTIVE and ready.")
    else:
        print(">> Status: Running in DETERMINISTIC OFFLINE MODE.")
        print("   The system functions immediately with deterministic rules & templates.")
        print("   To enable live LLM generation, paste your keys in '.env' at any time.")
    print("=" * 65 + "\n")


def cmd_run_sample(args):
    """Run pipeline against one or all sample job fixtures."""
    pipeline = ResumeAutomationPipeline()
    samples_dir = PROJECT_ROOT / "data/sample-jobs"

    if args.sample == "all":
        files = sorted(samples_dir.glob("*.json"))
    else:
        target = samples_dir / args.sample
        if not target.exists() and not args.sample.endswith(".json"):
            target = samples_dir / f"{args.sample}.json"
        if not target.exists():
            print(f"Error: Sample fixture '{args.sample}' not found in {samples_dir}")
            sys.exit(1)
        files = [target]

    print(f"\nProcessing {len(files)} sample job(s)...")

    for f in files:
        print("\n" + "-" * 60)
        print(f"Running sample: {f.name}")
        jobs = IngestionManager.from_file(f)
        for job in jobs:
            match_report, review_pkg = pipeline.process_job(job, force_generate=args.force)

            print(f"Job Title       : {job.title}")
            print(f"Company         : {job.company}")
            print(f"Match Score     : {match_report.overall_score}/100")
            print(f"Recommendation  : {match_report.recommendation.upper()}")
            print(f"Reason          : {match_report.reason}")

            if match_report.negative_constraint_flags:
                print(f"NEGATIVE FLAGS  : {match_report.negative_constraint_flags}")

            if review_pkg:
                print(f"Review Package  : {review_pkg.application_id}")
                print(f"Output Folder   : {review_pkg.output_directory}")
                print(f"  * Markdown    : {Path(review_pkg.resume_md_path).name}")
                print(f"  * DOCX        : {Path(review_pkg.resume_docx_path).name}")
                print(f"  * PDF         : {Path(review_pkg.resume_pdf_path).name}")
                print(f"  * Cover Note  : {Path(review_pkg.cover_note_path).name}")
                print(f"  * Status      : {review_pkg.status.upper()}")
            else:
                print(">> Score did not meet generation threshold. No package generated.")


def cmd_ingest(args):
    """Ingest a job from text, file, or URL."""
    pipeline = ResumeAutomationPipeline()

    if args.file:
        jobs = IngestionManager.from_file(Path(args.file))
    elif args.url:
        jobs = [IngestionManager.from_url(args.url)]
    elif args.text:
        jobs = [IngestionManager.from_text(args.text, title=args.title or "Target Role", company=args.company or "Company")]
    else:
        print("Error: Specify --file, --url, or --text")
        sys.exit(1)

    for job in jobs:
        print(f"\nIngesting and evaluating job: {job.title} at {job.company}...")
        report, pkg = pipeline.process_job(job, force_generate=args.force)

        print(f"Match Score    : {report.overall_score}/100 ({report.recommendation.upper()})")
        print(f"Reason         : {report.reason}")
        if pkg:
            print(f"Review Package Generated at: {pkg.output_directory}")
            print(f"PDF Resume: {pkg.resume_pdf_path}")
            print(f"DOCX Resume: {pkg.resume_docx_path}")
            print("\nNext step: Run 'python -m src.cli review' to inspect or approve this application.")


def cmd_review(args):
    """Display pending applications for human review."""
    db = ApplicationTrackerDB()
    apps = db.list_applications(limit=25)

    if not apps:
        print("\nNo applications currently in review queue.")
        print("Run 'python -m src.cli run-sample 01-perf-mktg-manager' or ingest a job first.")
        return

    print("\n" + "=" * 70)
    print("                     APPLICATION REVIEW QUEUE                        ")
    print("=" * 70)

    for i, app in enumerate(apps, 1):
        print(f"[{i}] App ID     : {app['application_id']}")
        print(f"    Job Title  : {app.get('job_title', 'Untitled')}")
        print(f"    Company    : {app.get('company', 'Unknown')}")
        print(f"    Match Score: {app.get('match_score', 0)}/100")
        print(f"    Status     : {app.get('status', 'unknown')}")
        print(f"    Decision   : {app.get('user_decision', 'pending')}")
        print(f"    Location   : {app.get('output_directory', '')}")
        print("-" * 70)


def cmd_decide(args):
    """Record user decision for an application."""
    db = ApplicationTrackerDB()
    success = db.update_decision(args.application_id, args.decision, notes=args.notes or "")
    if success:
        print(f"Updated application '{args.application_id}' decision to '{args.decision}'.")
    else:
        print(f"Error: Application '{args.application_id}' not found.")


def cmd_report(args):
    """Generate pipeline and skill gap report."""
    db = ApplicationTrackerDB()
    report = generate_tracking_report(db)
    print("\n" + format_report_markdown(report) + "\n")


def main():
    parser = argparse.ArgumentParser(description="ATS Resume Automation for Performance & Digital Marketing")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # check-env
    subparsers.add_parser("check-env", help="Check system and credential status")

    # run-sample
    p_sample = subparsers.add_parser("run-sample", help="Run sample job fixture")
    p_sample.add_argument("sample", nargs="?", default="01-perf-mktg-manager", help="Sample filename or 'all'")
    p_sample.add_argument("--force", action="store_true", help="Force resume generation regardless of score")

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="Ingest and score a job")
    p_ingest.add_argument("--file", help="Path to job file (JSON, TXT, MD, CSV)")
    p_ingest.add_argument("--url", help="Job listing URL")
    p_ingest.add_argument("--text", help="Raw job description text")
    p_ingest.add_argument("--title", help="Job title (for raw text)")
    p_ingest.add_argument("--company", help="Company name (for raw text)")
    p_ingest.add_argument("--force", action="store_true", help="Force resume generation regardless of score")

    # review
    subparsers.add_parser("review", help="List review queue")

    # decide
    p_decide = subparsers.add_parser("decide", help="Record review decision")
    p_decide.add_argument("application_id", help="Application ID")
    p_decide.add_argument("decision", choices=["apply", "applied", "save", "reject"], help="Decision")
    p_decide.add_argument("--notes", help="Optional review notes")

    # report
    subparsers.add_parser("report", help="View tracking and skill gap report")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "check-env": cmd_check_env,
        "run-sample": cmd_run_sample,
        "ingest": cmd_ingest,
        "review": cmd_review,
        "decide": cmd_decide,
        "report": cmd_report,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
