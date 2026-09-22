"""
Export Module -- CSV and PDF report generation from completed jobs.

CSV: per-job row with scores and decisions.
PDF: summary report with statistics, top skills, best jobs.
"""

import csv
import os
from datetime import datetime
from typing import List

from database.db_manager import DatabaseManager
from learning.feedback import FeedbackEngine
from utils.logger import setup_logger

logger = setup_logger(__name__)


def _safe_text(text: str) -> str:
    """Strip non-latin1 chars for PDF Helvetica compatibility."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


class Exporter:
    """Export job data to CSV and PDF summary reports."""

    def __init__(self, db: DatabaseManager, output_dir: str = "output/exports"):
        self.db = db
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export_csv(self, filename: str = None) -> str:
        """
        Export all jobs to CSV.

        Returns:
            Path to generated CSV file.
        """
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jobs_export_{ts}.csv"

        filepath = os.path.join(self.output_dir, filename)
        jobs = self.db.list_jobs()

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "job_id", "title", "company", "status",
                "score_before", "score_after", "improvement",
                "decision", "semantic_score", "effort_level",
                "confidence", "matched_skills", "missing_skills",
            ])

            for job in jobs:
                r = job.ats_report
                writer.writerow([
                    job.job_id,
                    job.title or "",
                    job.company or "",
                    job.status.value,
                    r.score_before if r else "",
                    r.score_after if r else "",
                    r.improvement if r else "",
                    r.decision if r else "",
                    r.semantic_score if r else "",
                    r.effort_level if r else "",
                    r.confidence_level if r else "",
                    "; ".join(r.matched_skills) if r else "",
                    "; ".join(r.missing_skills) if r else "",
                ])

        logger.info(f"CSV exported: {filepath} ({len(jobs)} jobs)")
        return filepath

    def export_pdf_summary(self, filename: str = None) -> str:
        """
        Export a PDF summary report.

        Returns:
            Path to generated PDF file.
        """
        try:
            from fpdf import FPDF
        except ImportError:
            logger.error("fpdf2 required for PDF export")
            raise

        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"summary_report_{ts}.pdf"

        filepath = os.path.join(self.output_dir, filename)
        jobs = self.db.list_jobs(status="completed")
        feedback = FeedbackEngine(self.db)
        data = feedback.analyze()

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Title
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 12, "Job AI Intelligence - Summary Report", ln=True, align="C")
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, _safe_text(f"Generated: {datetime.now().strftime('%B %d, %Y %I:%M %p')}"), ln=True, align="C")
        pdf.ln(8)

        # Stats
        stats = self.db.get_stats()
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Overview", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, _safe_text(f"Total Jobs Processed: {stats['total_jobs']}"), ln=True)
        pdf.cell(0, 6, _safe_text(f"Completed: {stats['completed']}  |  Failed: {stats['failed']}"), ln=True)
        pdf.cell(0, 6, _safe_text(f"Average Score (After): {stats['avg_score_after']}/100"), ln=True)
        pdf.cell(0, 6, _safe_text(f"Average Improvement: +{stats['avg_improvement']}"), ln=True)
        pdf.ln(4)

        # Decisions
        if "error" not in data:
            decisions = data["decisions"]
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 8, "Decision Breakdown", ln=True)
            pdf.set_font("Helvetica", "", 10)
            for dec in ["APPLY", "MAYBE", "SKIP"]:
                count = decisions.get(dec, 0)
                pdf.cell(0, 6, _safe_text(f"  {dec}: {count}"), ln=True)
            pdf.ln(4)

            # Top missing skills
            if data["top_missing_skills"]:
                pdf.set_font("Helvetica", "B", 13)
                pdf.cell(0, 8, "Top Missing Skills", ln=True)
                pdf.set_font("Helvetica", "", 10)
                for skill, count in data["top_missing_skills"][:7]:
                    pdf.cell(0, 6, _safe_text(f"  - {skill} (missing in {count} jobs)"), ln=True)
                pdf.ln(4)

        # Best matching jobs
        apply_jobs = [j for j in jobs if j.ats_report and j.ats_report.decision == "APPLY"]
        if apply_jobs:
            apply_jobs.sort(key=lambda j: j.ats_report.score_after, reverse=True)
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 8, "Best Matching Jobs", ln=True)
            pdf.set_font("Helvetica", "", 10)
            for j in apply_jobs[:5]:
                r = j.ats_report
                pdf.cell(0, 6, _safe_text(f"  {j.title} @ {j.company} -- Score: {r.score_after} ({r.improvement})"), ln=True)
            pdf.ln(4)

        # All jobs table
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "All Jobs", ln=True)
        pdf.set_font("Helvetica", "B", 8)
        col_w = [30, 35, 30, 18, 18, 18, 18]
        headers = ["Job ID", "Title", "Company", "Before", "After", "Decision", "Effort"]
        for i, h in enumerate(headers):
            pdf.cell(col_w[i], 6, h, border=1)
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        for j in jobs[:20]:
            r = j.ats_report
            vals = [
                (j.job_id or "")[:15],
                (j.title or "")[:18],
                (j.company or "")[:15],
                str(r.score_before) if r else "-",
                str(r.score_after) if r else "-",
                r.decision if r else "-",
                r.effort_level if r else "-",
            ]
            for i, v in enumerate(vals):
                pdf.cell(col_w[i], 5, _safe_text(v), border=1)
            pdf.ln()

        pdf.output(filepath)
        logger.info(f"PDF summary exported: {filepath}")
        return filepath

    def print_summary(self):
        """Print export summary to console."""
        csv_path = self.export_csv()
        pdf_path = self.export_pdf_summary()
        print(f"\n  CSV exported: {csv_path}")
        print(f"  PDF exported: {pdf_path}\n")
