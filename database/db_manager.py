"""
Database Manager — Extended Schema (v2.0)

Extended from v1 to support the full product vision:
  - salary fields (salary_min, salary_max, salary_currency)
  - shortlist_probability as a queryable column (not buried in JSON)
  - application_status lifecycle (saved → applied → shortlisted → rejected → offer)
  - optimized_resume as a separate addressable column
  - ingested_jobs table for pipeline/ingestion.py output
  - application_events table for lifecycle tracking

All v1 APIs are preserved. New APIs added below the separator.
Migration: calling _create_tables() on an existing DB is safe (IF NOT EXISTS).
For the new columns, a migration helper _migrate_v1_to_v2() runs automatically.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

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
        db.save_job(job_record)                          # existing API
        db.save_analysis_result(analysis_dict)           # new API
        db.update_application_status(job_id, "applied") # new API
        jobs = db.list_jobs(status="pending")            # existing API
    """

    def __init__(self, db_path: str = "data/job_ai_system.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent reads
        self._create_tables()
        self._migrate_v1_to_v2()
        logger.info(f"Database initialized: {db_path}")

    # ================================================================
    # TABLE CREATION
    # ================================================================

    def _create_tables(self):
        """Create all tables if they don't exist (idempotent)."""
        self.conn.executescript("""
            -- Core jobs table (v1 schema — do not alter columns here)
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

            -- Resume version tracking
            CREATE TABLE IF NOT EXISTS resume_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                resume_json TEXT NOT NULL,
                score REAL DEFAULT 0,
                created_at TEXT DEFAULT '',
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            );

            -- Analysis results from app.py (replaces job_history.json)
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT DEFAULT '',
                company TEXT DEFAULT '',
                role TEXT DEFAULT '',
                location TEXT DEFAULT '',
                salary_min INTEGER DEFAULT NULL,
                salary_max INTEGER DEFAULT NULL,
                salary_currency TEXT DEFAULT '',
                source_platform TEXT DEFAULT '',
                jd_text TEXT DEFAULT '',
                ats_score_before REAL DEFAULT 0,
                ats_score_after REAL DEFAULT 0,
                shortlist_probability REAL DEFAULT 0,
                shortlist_band TEXT DEFAULT '',
                decision TEXT DEFAULT '',
                decision_reason TEXT DEFAULT '',
                recruiter_score REAL DEFAULT 0,
                original_resume_json TEXT DEFAULT '',
                optimized_resume_json TEXT DEFAULT '',
                rewrite_summary TEXT DEFAULT '',
                missing_skills_json TEXT DEFAULT '',
                matched_skills_json TEXT DEFAULT '',
                application_status TEXT DEFAULT 'saved',
                optimization_mode TEXT DEFAULT 'balanced',
                analysis_hash TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            );

            -- Application lifecycle events
            CREATE TABLE IF NOT EXISTS application_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                FOREIGN KEY (analysis_id) REFERENCES analysis_results(id)
            );

            -- Ingested jobs from pipeline/ingestion.py (screened, not yet fully analyzed)
            CREATE TABLE IF NOT EXISTS ingested_jobs (
                job_id TEXT PRIMARY KEY,
                source TEXT DEFAULT '',
                url TEXT DEFAULT '',
                title TEXT DEFAULT '',
                company TEXT DEFAULT '',
                location TEXT DEFAULT '',
                salary_min INTEGER DEFAULT NULL,
                salary_max INTEGER DEFAULT NULL,
                salary_currency TEXT DEFAULT '',
                raw_jd TEXT DEFAULT '',
                ats_score REAL DEFAULT 0,
                missing_skills_json TEXT DEFAULT '',
                matched_skills_json TEXT DEFAULT '',
                status TEXT DEFAULT 'screened',
                ingested_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            );

            -- Indexes
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
            CREATE INDEX IF NOT EXISTS idx_resume_versions_job ON resume_versions(job_id);
            CREATE INDEX IF NOT EXISTS idx_analysis_company ON analysis_results(company);
            CREATE INDEX IF NOT EXISTS idx_analysis_status ON analysis_results(application_status);
            CREATE INDEX IF NOT EXISTS idx_analysis_shortlist ON analysis_results(shortlist_probability);
            CREATE INDEX IF NOT EXISTS idx_ingested_source ON ingested_jobs(source);
            CREATE INDEX IF NOT EXISTS idx_ingested_ats ON ingested_jobs(ats_score);
        """)
        self.conn.commit()

    def _migrate_v1_to_v2(self):
        """
        Add v2 columns to existing jobs table without breaking v1 data.
        Safe to run on both fresh and existing databases.
        """
        v2_columns = {
            "shortlist_probability": "REAL DEFAULT 0",
            "shortlist_band": "TEXT DEFAULT ''",
            "decision": "TEXT DEFAULT ''",
            "application_status": "TEXT DEFAULT 'saved'",
            "salary_min": "INTEGER DEFAULT NULL",
            "salary_max": "INTEGER DEFAULT NULL",
            "salary_currency": "TEXT DEFAULT ''",
            "optimized_resume_json": "TEXT DEFAULT ''",
            "rewrite_summary": "TEXT DEFAULT ''",
        }
        existing = {
            row[1] for row in
            self.conn.execute("PRAGMA table_info(jobs)").fetchall()
        }
        for col, typedef in v2_columns.items():
            if col not in existing:
                self.conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {typedef}")
                logger.info(f"[db_migration] added column: jobs.{col}")
        self.conn.commit()

    # ================================================================
    # V1 API — unchanged for backward compatibility
    # ================================================================

    def save_job(self, record: JobRecord) -> None:
        """Insert or update a job record (v1 API)."""
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
                title=excluded.title, company=excluded.company,
                location=excluded.location, raw_jd=excluded.raw_jd,
                extracted_jd_json=excluded.extracted_jd_json,
                original_resume_json=excluded.original_resume_json,
                tailored_resume_json=excluded.tailored_resume_json,
                ats_report_json=excluded.ats_report_json,
                pdf_path=excluded.pdf_path, status=excluded.status,
                score_before=excluded.score_before, score_after=excluded.score_after,
                improvement=excluded.improvement,
                resume_version=excluded.resume_version, updated_at=excluded.updated_at
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

    def get_job(self, job_id: str) -> Optional[dict]:
        """
        Retrieve a job record by ID.
        Returns dict (not JobRecord) for flexibility. Use _row_to_job_record() if needed.
        """
        row = self.conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_jobs(self, status: Optional[str] = None, limit: int = 100) -> List[JobRecord]:
        """List job records, optionally filtered by status (v1 API)."""
        if status:
            rows = self.conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_job_record(row) for row in rows]

    def update_status(self, job_id: str, status: ProcessingStatus, error: str = "") -> None:
        """Update processing status (v1 API)."""
        now = datetime.now().isoformat()
        self.conn.execute(
            "UPDATE jobs SET status = ?, error_message = ?, updated_at = ? WHERE job_id = ?",
            (status.value, error, now, job_id)
        )
        self.conn.commit()

    def job_exists(self, job_id: str) -> bool:
        """Check if job_id exists (v1 API)."""
        row = self.conn.execute(
            "SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        return row is not None

    def save_resume_version(
        self, job_id: str, version: int, resume: StructuredResume, score: float = 0
    ) -> None:
        """Save a resume version (v1 API)."""
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT INTO resume_versions (job_id, version, resume_json, score, created_at) VALUES (?, ?, ?, ?, ?)",
            (job_id, version, resume.model_dump_json(), score, now)
        )
        self.conn.commit()

    def get_resume_versions(self, job_id: str) -> List[dict]:
        """Get all resume versions for a job (v1 API)."""
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

    def get_stats(self) -> dict:
        """Get summary statistics (v1 API)."""
        total = self.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        completed = self.conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'completed'").fetchone()[0]
        pending = self.conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'pending'").fetchone()[0]
        failed = self.conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'failed'").fetchone()[0]
        avg_before = self.conn.execute("SELECT AVG(score_before) FROM jobs WHERE status = 'completed'").fetchone()[0] or 0
        avg_after = self.conn.execute("SELECT AVG(score_after) FROM jobs WHERE status = 'completed'").fetchone()[0] or 0
        return {
            "total_jobs": total, "completed": completed,
            "pending": pending, "failed": failed,
            "avg_score_before": round(avg_before, 1),
            "avg_score_after": round(avg_after, 1),
            "avg_improvement": round(avg_after - avg_before, 1),
        }

    # ================================================================
    # V2 API — analysis results (replaces job_history.json)
    # ================================================================

    def save_analysis_result(self, analysis: dict) -> int:
        """
        Save a complete analysis result from app.py.
        Returns the new row ID.

        analysis dict keys:
            company, role, location, salary_min, salary_max, salary_currency,
            source_platform, jd_text, ats_score_before, ats_score_after,
            shortlist_probability, shortlist_band, decision, decision_reason,
            recruiter_score, original_resume_json, optimized_resume_json,
            rewrite_summary, missing_skills, matched_skills,
            optimization_mode, analysis_hash
        """
        now = datetime.now().isoformat()
        cursor = self.conn.execute("""
            INSERT INTO analysis_results (
                job_id, company, role, location,
                salary_min, salary_max, salary_currency, source_platform,
                jd_text, ats_score_before, ats_score_after,
                shortlist_probability, shortlist_band, decision, decision_reason,
                recruiter_score, original_resume_json, optimized_resume_json,
                rewrite_summary, missing_skills_json, matched_skills_json,
                application_status, optimization_mode, analysis_hash,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            analysis.get("job_id", ""),
            analysis.get("company", "Unknown"),
            analysis.get("role", "Unknown Role"),
            analysis.get("location", ""),
            analysis.get("salary_min"),
            analysis.get("salary_max"),
            analysis.get("salary_currency", ""),
            analysis.get("source_platform", "manual"),
            analysis.get("jd_text", ""),
            analysis.get("ats_score_before", 0),
            analysis.get("ats_score_after", 0),
            analysis.get("shortlist_probability", 0),
            analysis.get("shortlist_band", ""),
            analysis.get("decision", ""),
            analysis.get("decision_reason", ""),
            analysis.get("recruiter_score", 0),
            analysis.get("original_resume_json", ""),
            analysis.get("optimized_resume_json", ""),
            analysis.get("rewrite_summary", ""),
            json.dumps(analysis.get("missing_skills", [])),
            json.dumps(analysis.get("matched_skills", [])),
            "saved",
            analysis.get("optimization_mode", "balanced"),
            analysis.get("analysis_hash", ""),
            now,
            now,
        ))
        self.conn.commit()
        new_id = cursor.lastrowid
        logger.info(f"Analysis saved: id={new_id} {analysis.get('company')} — {analysis.get('role')}")
        return new_id

    def update_application_status(
        self,
        analysis_id: int,
        new_status: str,
        note: str = "",
    ) -> None:
        """
        Update application lifecycle status.

        Valid statuses: saved | optimized | applied | shortlisted | rejected | interview | offer

        Also records an event in application_events for timeline tracking.
        """
        valid_statuses = {"saved", "optimized", "applied", "shortlisted", "rejected", "interview", "offer"}
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status}. Must be one of {valid_statuses}")

        now = datetime.now().isoformat()
        self.conn.execute(
            "UPDATE analysis_results SET application_status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, analysis_id)
        )
        self.conn.execute(
            "INSERT INTO application_events (analysis_id, event_type, note, created_at) VALUES (?, ?, ?, ?)",
            (analysis_id, new_status, note, now)
        )
        self.conn.commit()
        logger.info(f"Status updated: analysis_id={analysis_id} → {new_status}")

    def list_analysis_results(
        self,
        status: Optional[str] = None,
        min_shortlist: float = 0,
        limit: int = 50,
    ) -> List[dict]:
        """
        List analysis results with optional filters.
        Returns dicts with all columns.
        """
        query = "SELECT * FROM analysis_results WHERE shortlist_probability >= ?"
        params: list = [min_shortlist]

        if status:
            query += " AND application_status = ?"
            params.append(status)

        query += " ORDER BY shortlist_probability DESC, created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            r = dict(row)
            # Deserialize JSON fields
            r["missing_skills"] = json.loads(r.get("missing_skills_json") or "[]")
            r["matched_skills"] = json.loads(r.get("matched_skills_json") or "[]")
            results.append(r)
        return results

    def get_application_history(self, analysis_id: int) -> List[dict]:
        """Get full event history for an application."""
        rows = self.conn.execute(
            "SELECT event_type, note, created_at FROM application_events WHERE analysis_id = ? ORDER BY created_at",
            (analysis_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_analytics_summary(self) -> dict:
        """
        Aggregate analytics for performance dashboard.
        Shows real outcomes for learning from past applications.
        """
        total = self.conn.execute("SELECT COUNT(*) FROM analysis_results").fetchone()[0]
        shortlisted = self.conn.execute(
            "SELECT COUNT(*) FROM analysis_results WHERE application_status = 'shortlisted'"
        ).fetchone()[0]
        rejected = self.conn.execute(
            "SELECT COUNT(*) FROM analysis_results WHERE application_status = 'rejected'"
        ).fetchone()[0]
        applied = self.conn.execute(
            "SELECT COUNT(*) FROM analysis_results WHERE application_status IN ('applied','shortlisted','rejected','interview','offer')"
        ).fetchone()[0]
        avg_ats = self.conn.execute(
            "SELECT AVG(ats_score_after) FROM analysis_results WHERE ats_score_after > 0"
        ).fetchone()[0] or 0
        avg_shortlist_prob = self.conn.execute(
            "SELECT AVG(shortlist_probability) FROM analysis_results WHERE shortlist_probability > 0"
        ).fetchone()[0] or 0

        # Shortlist rate (applications that resulted in shortlisting)
        shortlist_rate = (shortlisted / max(applied, 1)) * 100 if applied else 0

        return {
            "total_analyses": total,
            "total_applied": applied,
            "shortlisted": shortlisted,
            "rejected": rejected,
            "shortlist_rate": round(shortlist_rate, 1),
            "avg_ats_score": round(avg_ats, 1),
            "avg_shortlist_probability": round(avg_shortlist_prob, 1),
        }

    # ================================================================
    # V2 API — ingested jobs (from pipeline/ingestion.py)
    # ================================================================

    def save_ingested_job(self, job: dict) -> None:
        """
        Save a job from the ingestion pipeline.
        Called by IngestionPipeline after quick ATS screening.
        """
        now = datetime.now().isoformat()
        self.conn.execute("""
            INSERT INTO ingested_jobs (
                job_id, source, url, title, company, location,
                salary_min, salary_max, salary_currency,
                raw_jd, ats_score, missing_skills_json, matched_skills_json,
                status, ingested_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(job_id) DO UPDATE SET
                ats_score=excluded.ats_score,
                status=excluded.status,
                updated_at=excluded.updated_at
        """, (
            job["job_id"], job.get("source", ""), job.get("url", ""),
            job.get("title", ""), job.get("company", ""), job.get("location", ""),
            job.get("salary_min"), job.get("salary_max"), job.get("salary_currency", ""),
            job.get("raw_jd", ""),
            job.get("ats_score", 0),
            json.dumps(job.get("missing_skills", [])),
            json.dumps(job.get("matched_skills", [])),
            job.get("status", "screened"),
            job.get("ingested_at", now),
            now,
        ))
        self.conn.commit()

    def list_ingested_jobs(
        self,
        min_ats: float = 0,
        source: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """List ingested jobs sorted by ATS score."""
        query = "SELECT * FROM ingested_jobs WHERE ats_score >= ?"
        params: list = [min_ats]
        if source:
            query += " AND source = ?"
            params.append(source)
        query += " ORDER BY ats_score DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            r = dict(row)
            r["missing_skills"] = json.loads(r.get("missing_skills_json") or "[]")
            r["matched_skills"] = json.loads(r.get("matched_skills_json") or "[]")
            results.append(r)
        return results

    # ================================================================
    # HELPERS
    # ================================================================

    def _row_to_job_record(self, row) -> JobRecord:
        """Convert a database row to a JobRecord (v1 compat)."""
        def _safe_parse(model_class, json_str):
            try:
                return model_class(**json.loads(json_str)) if json_str else None
            except Exception:
                return None

        return JobRecord(
            job_id=row["job_id"],
            platform=row["platform"],
            url=row["url"],
            title=row["title"],
            company=row["company"],
            location=row["location"],
            raw_jd=row["raw_jd"],
            extracted_jd=_safe_parse(ExtractedJD, row["extracted_jd_json"]),
            original_resume=_safe_parse(StructuredResume, row["original_resume_json"]),
            tailored_resume=_safe_parse(StructuredResume, row["tailored_resume_json"]),
            ats_report=_safe_parse(ATSScoreReport, row["ats_report_json"]),
            pdf_path=row["pdf_path"],
            status=ProcessingStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def close(self):
        self.conn.close()
        logger.info("Database connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
