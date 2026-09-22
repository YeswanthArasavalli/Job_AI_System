"""
Database Manager -- SQLite storage for all pipeline data.

Stores:
  - Job records (scraped metadata + JD)
  - Resume versions (original, tailored v1, v2, etc.)
  - ATS scores per version
  - Processing status and timestamps

Design:
  - SQLite for zero-config local storage
  - JSON serialization for complex objects (resumes, JDs, reports)
  - Idempotent -- re-processing same job updates rather than duplicates
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import List, Optional

from utils.logger import setup_logger
from utils.models import (
    ATSScoreReport,
    ExtractedJD,
    JobRecord,
    ProcessingStatus,
    StructuredResume,
)

logger = setup_logger(__name__)


class DatabaseManager:
    """
    SQLite database manager for the Job AI System.

    Usage:
        db = DatabaseManager("data/job_ai_system.db")
        db.save_job(job_record)
        job = db.get_job("job_123")
        jobs = db.list_jobs(status="pending")
    """

    def __init__(self, db_path: str = "data/job_ai_system.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info(f"Database initialized: {db_path}")

    def _create_tables(self):
        """Create all tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                platform TEXT DEFAULT '',
                url TEXT DEFAULT '',
                title TEXT DEFAULT '',
                company TEXT DEFAULT '',
                location TEXT DEFAULT '',
                raw_jd TEXT DEFAULT '',
                extracted_jd_json TEXT DEFAULT '',
                original_resume_json TEXT DEFAULT '',
                tailored_resume_json TEXT DEFAULT '',
                ats_report_json TEXT DEFAULT '',
                pdf_path TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                score_before REAL DEFAULT 0,
                score_after REAL DEFAULT 0,
                improvement TEXT DEFAULT '+0',
                resume_version INTEGER DEFAULT 1,
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT '',
                error_message TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS resume_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                resume_json TEXT NOT NULL,
                score REAL DEFAULT 0,
                created_at TEXT DEFAULT '',
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
            CREATE INDEX IF NOT EXISTS idx_resume_versions_job ON resume_versions(job_id);
        """)
        self.conn.commit()

    # ================================================================
    # Job CRUD
    # ================================================================

    def save_job(self, record: JobRecord) -> None:
        """Insert or update a job record."""
        now = datetime.now().isoformat()

        extracted_jd_json = record.extracted_jd.model_dump_json() if record.extracted_jd else ""
        original_json = record.original_resume.model_dump_json() if record.original_resume else ""
        tailored_json = record.tailored_resume.model_dump_json() if record.tailored_resume else ""
        ats_json = record.ats_report.model_dump_json() if record.ats_report else ""

        score_before = record.ats_report.score_before if record.ats_report else 0
        score_after = record.ats_report.score_after if record.ats_report else 0
        improvement = record.ats_report.improvement if record.ats_report else "+0"

        self.conn.execute("""
            INSERT INTO jobs (
                job_id, platform, url, title, company, location,
                raw_jd, extracted_jd_json, original_resume_json,
                tailored_resume_json, ats_report_json, pdf_path,
                status, score_before, score_after, improvement,
                resume_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                title=excluded.title,
                company=excluded.company,
                location=excluded.location,
                raw_jd=excluded.raw_jd,
                extracted_jd_json=excluded.extracted_jd_json,
                original_resume_json=excluded.original_resume_json,
                tailored_resume_json=excluded.tailored_resume_json,
                ats_report_json=excluded.ats_report_json,
                pdf_path=excluded.pdf_path,
                status=excluded.status,
                score_before=excluded.score_before,
                score_after=excluded.score_after,
                improvement=excluded.improvement,
                resume_version=excluded.resume_version,
                updated_at=excluded.updated_at
        """, (
            record.job_id, record.platform, record.url,
            record.title, record.company, record.location,
            record.raw_jd, extracted_jd_json, original_json,
            tailored_json, ats_json, record.pdf_path,
            record.status.value, score_before, score_after,
            improvement, 1, record.created_at, now,
        ))
        self.conn.commit()
        logger.info(f"Job saved: {record.job_id} ({record.title} @ {record.company})")

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        """Retrieve a single job record by ID."""
        row = self.conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()

        if not row:
            return None

        return self._row_to_job_record(row)

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[JobRecord]:
        """List job records, optionally filtered by status."""
        if status:
            rows = self.conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()

        return [self._row_to_job_record(row) for row in rows]

    def update_status(self, job_id: str, status: ProcessingStatus, error: str = "") -> None:
        """Update the processing status of a job."""
        now = datetime.now().isoformat()
        self.conn.execute(
            "UPDATE jobs SET status = ?, error_message = ?, updated_at = ? WHERE job_id = ?",
            (status.value, error, now, job_id)
        )
        self.conn.commit()

    def job_exists(self, job_id: str) -> bool:
        """Check if a job_id already exists in the database."""
        row = self.conn.execute(
            "SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        return row is not None

    # ================================================================
    # Resume Versioning
    # ================================================================

    def save_resume_version(
        self,
        job_id: str,
        version: int,
        resume: StructuredResume,
        score: float = 0,
    ) -> None:
        """Save a resume version for a specific job."""
        now = datetime.now().isoformat()
        self.conn.execute(
            """INSERT INTO resume_versions (job_id, version, resume_json, score, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (job_id, version, resume.model_dump_json(), score, now)
        )
        self.conn.commit()
        logger.debug(f"Resume version {version} saved for job {job_id}")

    def get_resume_versions(self, job_id: str) -> List[dict]:
        """Get all resume versions for a job."""
        rows = self.conn.execute(
            "SELECT version, resume_json, score, created_at FROM resume_versions WHERE job_id = ? ORDER BY version",
            (job_id,)
        ).fetchall()

        return [
            {
                "version": row["version"],
                "resume": StructuredResume(**json.loads(row["resume_json"])),
                "score": row["score"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # ================================================================
    # Statistics
    # ================================================================

    def get_stats(self) -> dict:
        """Get summary statistics."""
        total = self.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        completed = self.conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'completed'"
        ).fetchone()[0]
        pending = self.conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'pending'"
        ).fetchone()[0]
        failed = self.conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'failed'"
        ).fetchone()[0]

        avg_before = self.conn.execute(
            "SELECT AVG(score_before) FROM jobs WHERE status = 'completed'"
        ).fetchone()[0] or 0
        avg_after = self.conn.execute(
            "SELECT AVG(score_after) FROM jobs WHERE status = 'completed'"
        ).fetchone()[0] or 0

        return {
            "total_jobs": total,
            "completed": completed,
            "pending": pending,
            "failed": failed,
            "avg_score_before": round(avg_before, 1),
            "avg_score_after": round(avg_after, 1),
            "avg_improvement": round(avg_after - avg_before, 1),
        }

    # ================================================================
    # Helpers
    # ================================================================

    def _row_to_job_record(self, row: sqlite3.Row) -> JobRecord:
        """Convert a database row to a JobRecord."""
        extracted_jd = None
        if row["extracted_jd_json"]:
            try:
                extracted_jd = ExtractedJD(**json.loads(row["extracted_jd_json"]))
            except Exception:
                pass

        original_resume = None
        if row["original_resume_json"]:
            try:
                original_resume = StructuredResume(**json.loads(row["original_resume_json"]))
            except Exception:
                pass

        tailored_resume = None
        if row["tailored_resume_json"]:
            try:
                tailored_resume = StructuredResume(**json.loads(row["tailored_resume_json"]))
            except Exception:
                pass

        ats_report = None
        if row["ats_report_json"]:
            try:
                ats_report = ATSScoreReport(**json.loads(row["ats_report_json"]))
            except Exception:
                pass

        return JobRecord(
            job_id=row["job_id"],
            platform=row["platform"],
            url=row["url"],
            title=row["title"],
            company=row["company"],
            location=row["location"],
            raw_jd=row["raw_jd"],
            extracted_jd=extracted_jd,
            original_resume=original_resume,
            tailored_resume=tailored_resume,
            ats_report=ats_report,
            pdf_path=row["pdf_path"],
            status=ProcessingStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def close(self):
        """Close the database connection."""
        self.conn.close()
        logger.info("Database connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
