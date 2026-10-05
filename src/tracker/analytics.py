"""Analytics and Progress Reporting."""

from __future__ import annotations

import collections
import json
from typing import Any, Dict
from src.tracker.db import ApplicationTrackerDB


def generate_tracking_report(db: ApplicationTrackerDB) -> Dict[str, Any]:
    """Generate structured summary analytics from tracker database."""
    apps = db.list_applications(limit=200)

    total_apps = len(apps)
    status_counts = collections.Counter(a.get("status", "unknown") for a in apps)
    decisions = collections.Counter(a.get("user_decision", "pending") for a in apps)

    scores = [a.get("match_score", 0.0) for a in apps]
    avg_score = round(sum(scores) / max(1, len(scores)), 1)
    high_fit_count = sum(1 for s in scores if s >= 80.0)
    medium_fit_count = sum(1 for s in scores if 65.0 <= s < 80.0)
    low_fit_count = sum(1 for s in scores if s < 65.0)

    # Missing skill analysis from match_reports
    missing_skills_counter = collections.Counter()
    all_missing_lists = db.get_all_missing_requirements()
    for req_list in all_missing_lists:
        for r in req_list:
            missing_skills_counter[r] += 1

    return {
        "total_jobs_tracked": total_apps,
        "average_match_score": avg_score,
        "high_fit_jobs": high_fit_count,
        "medium_fit_jobs": medium_fit_count,
        "low_fit_jobs": low_fit_count,
        "status_breakdown": dict(status_counts),
        "decision_breakdown": dict(decisions),
        "top_missing_skills": missing_skills_counter.most_common(10),
    }


def format_report_markdown(report: Dict[str, Any]) -> str:
    """Format analytics report as markdown."""
    lines = [
        "# ATS Resume Automation - Performance & Pipeline Report",
        "",
        f"- **Total Tracked Applications:** {report['total_jobs_tracked']}",
        f"- **Average Match Score:** {report['average_match_score']}/100",
        f"- **Strong Fit Jobs (>= 80%):** {report['high_fit_jobs']}",
        f"- **Medium Fit Jobs (65-79%):** {report['medium_fit_jobs']}",
        f"- **Low Fit Jobs (< 65%):** {report['low_fit_jobs']}",
        "",
        "## Pipeline Status Breakdown",
    ]
    for status, count in report["status_breakdown"].items():
        lines.append(f"- **{status.replace('_', ' ').title()}:** {count}")

    lines.append("")
    lines.append("## Common Missing Requirements (Skill Gaps)")
    if report["top_missing_skills"]:
        for skill, count in report["top_missing_skills"]:
            lines.append(f"- {skill}: appeared in {count} job descriptions")
    else:
        lines.append("- No persistent skill gaps detected.")

    return "\n".join(lines)
