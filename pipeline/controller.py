"""
Pipeline Controller v2 -- Resilient, parallel, intelligent orchestrator.

Upgrades over v1:
  - JD pre-processing (clean/normalize before LLM)
  - Parallel batch processing (ThreadPoolExecutor)
  - Thread-safe database access
  - Exponential backoff retry
  - Job ranking + insights integration
  - State machine with proper transitions
"""

import hashlib
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from resume_engine.engine import ResumeEngine
from resume_engine.formatter import format_resume_text
from resume_engine.parser import resume_to_json_string
from resume_engine.naturalizer import ResumeNaturalizer
from ats_scoring.scorer import ATSScorer
from ats_scoring.report_formatter import format_ats_report
from jd_processor.processor import JDProcessor
from pdf_generator.generator import PDFResumeGenerator
from database.db_manager import DatabaseManager
from insights.ranker import JobRanker
from utils.config_loader import load_config, AppConfig
from utils.logger import setup_logger
from utils.models import (
    JobRecord,
    ProcessingStatus,
    StructuredResume,
)

logger = setup_logger(__name__)


class PipelineController:
    """
    Master orchestrator for the full Job AI System pipeline.

    Usage:
        controller = PipelineController()

        # Single job
        controller.process_single(job_description="...", job_id="custom_001")

        # Parallel batch
        controller.process_scraped_jobs(jobs, parallel=True, max_workers=3)

        # Retry failed
        controller.retry_failed()

        # Rankings & insights
        controller.print_rankings()
        controller.print_insights()
    """

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or load_config()
        self.engine = ResumeEngine(config=self.config)
        self.scorer = ATSScorer(config=self.config)
        self.jd_processor = JDProcessor()
        self.pdf_gen = PDFResumeGenerator()
        self.db = DatabaseManager(self.config.database.path)
        self.ranker = JobRanker(self.db)
        self.naturalizer = ResumeNaturalizer()

        self.master_resume_path = self.config.resume_engine.master_resume_path
        self.output_dir = self.config.resume_engine.output_dir

        # Thread safety for database writes
        self._db_lock = threading.Lock()

        logger.info("PipelineController v2 initialized")

    # ================================================================
    # Single Job Processing
    # ================================================================

    def process_single(
        self,
        job_description: str,
        job_id: str = "",
        title: str = "",
        company: str = "",
        url: str = "",
        platform: str = "manual",
    ) -> Optional[JobRecord]:
        """
        Process a single job description through the full pipeline.

        Returns the completed JobRecord, or None on failure.
        """
        if not job_id:
            job_id = f"manual_{hashlib.md5(job_description.encode()).hexdigest()[:10]}"

        logger.info(f"{'=' * 60}")
        logger.info(f"PIPELINE -- Processing job: {job_id}")
        logger.info(f"{'=' * 60}")

        # Create initial record
        record = JobRecord(
            job_id=job_id,
            platform=platform,
            url=url,
            title=title,
            company=company,
            raw_jd=job_description,
            status=ProcessingStatus.PROCESSING,
        )

        try:
            # -- Step 0: Pre-process JD -----------------------
            processed_jd = self.jd_processor.process(job_description)
            clean_jd = processed_jd.cleaned_text
            logger.info(
                f"  JD quality: {processed_jd.quality_score:.0f}% | "
                f"{len(processed_jd.skills_required)} skills detected"
            )

            # -- Step 1: Run Resume Engine --------------------
            original, tailored, extracted_jd = self.engine.process(
                master_resume_path=self.master_resume_path,
                job_description=clean_jd,
            )

            record.extracted_jd = extracted_jd
            record.original_resume = original
            record.tailored_resume = tailored

            # Update title/company from extracted JD if not provided
            if not record.title and extracted_jd.job_title:
                record.title = extracted_jd.job_title
            if not record.company and extracted_jd.company:
                record.company = extracted_jd.company

            # -- Step 1b-2.5: Run unified pipeline -------------
            from pipeline.core import run_full_pipeline
            pipeline_result = run_full_pipeline(
                original=original,
                tailored=tailored,
                extracted_jd=extracted_jd,
                scorer=self.scorer,
                job_id=job_id,
            )
            ats_report = pipeline_result.ats_report
            improved = pipeline_result.improved
            record.ats_report = ats_report

            # -- Step 3: Generate PDF from IMPROVED resume -----
            company_safe = re.sub(r'[^\w\s-]', '', record.company or "unknown").strip()
            company_safe = re.sub(r'\s+', '_', company_safe)
            role_safe = re.sub(r'[^\w\s-]', '', record.title or "unknown").strip()
            role_safe = re.sub(r'\s+', '_', role_safe)
            pdf_filename = f"resume_{company_safe}_{role_safe}.pdf"

            pdf_path = self.pdf_gen.generate(improved, filename=pdf_filename)
            record.pdf_path = pdf_path

            # -- Step 4: Save to database (thread-safe) -------
            record.status = ProcessingStatus.COMPLETED
            with self._db_lock:
                self.db.save_job(record)
                self.db.save_resume_version(job_id, 0, original, ats_report.score_before)
                self.db.save_resume_version(job_id, 1, tailored, ats_report.score_after)
                self.db.save_resume_version(job_id, 2, improved, ats_report.score_after)

            # -- Step 5: Save files ---------------------------
            self._save_output_files(record, improved, extracted_jd, ats_report)

            logger.info(
                f"PIPELINE -- Job {job_id} completed | "
                f"Score: {ats_report.score_before} -> {ats_report.score_after} "
                f"({ats_report.improvement}) | Decision: {ats_report.decision}"
            )

            return record

        except Exception as e:
            logger.error(f"PIPELINE -- Job {job_id} failed: {e}")
            record.status = ProcessingStatus.FAILED
            with self._db_lock:
                self.db.save_job(record)
                self.db.update_status(job_id, ProcessingStatus.FAILED, str(e))
            return None

    # ================================================================
    # Batch Processing (Sequential)
    # ================================================================

    def process_scraped_jobs(
        self,
        scraped_jobs: list,
        parallel: bool = False,
        max_workers: int = 2,
    ) -> dict:
        """
        Process a batch of scraped jobs.

        Args:
            scraped_jobs: List of ScrapedJob objects.
            parallel: If True, use thread pool for parallel processing.
            max_workers: Number of parallel workers (only if parallel=True).
        """
        # Filter out already-processed and empty JDs
        jobs_to_process = []
        skipped = 0

        for scraped in scraped_jobs:
            if self.db.job_exists(scraped.job_id):
                existing = self.db.get_job(scraped.job_id)
                if existing and existing.status == ProcessingStatus.COMPLETED:
                    logger.info(f"Skipping already-processed: {scraped.job_id}")
                    skipped += 1
                    continue

            if len(scraped.raw_jd.strip()) < 50:
                logger.warning(f"Skipping short JD: {scraped.job_id}")
                skipped += 1
                continue

            jobs_to_process.append(scraped)

        total = len(jobs_to_process)
        logger.info(f"PIPELINE -- Batch: {total} to process, {skipped} skipped")

        if parallel and total > 1:
            return self._process_parallel(jobs_to_process, max_workers, skipped)
        else:
            return self._process_sequential(jobs_to_process, skipped)

    def _process_sequential(self, jobs: list, skipped: int) -> dict:
        """Process jobs one at a time."""
        completed = 0
        failed = 0

        for i, scraped in enumerate(jobs):
            print(f"\n{'-' * 40}")
            print(f"  [{i + 1}/{len(jobs)}] {scraped.title} @ {scraped.company}")
            print(f"{'-' * 40}")

            result = self._process_with_retry(scraped)
            if result:
                completed += 1
            else:
                failed += 1

            if i < len(jobs) - 1:
                time.sleep(1)

        summary = {
            "total": len(jobs) + skipped,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
        }
        logger.info(f"PIPELINE -- Batch complete: {summary}")
        return summary

    # ================================================================
    # Parallel Processing (Task 6)
    # ================================================================

    def _process_parallel(self, jobs: list, max_workers: int, skipped: int) -> dict:
        """Process jobs in parallel using ThreadPoolExecutor."""
        completed = 0
        failed = 0

        logger.info(f"PIPELINE -- Parallel mode: {max_workers} workers")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_job = {}
            for scraped in jobs:
                future = executor.submit(self._process_with_retry, scraped)
                future_to_job[future] = scraped

            for future in as_completed(future_to_job):
                scraped = future_to_job[future]
                try:
                    result = future.result()
                    if result:
                        completed += 1
                        print(f"  [OK] {scraped.title} @ {scraped.company}")
                    else:
                        failed += 1
                        print(f"  [FAIL] {scraped.title} @ {scraped.company}")
                except Exception as e:
                    failed += 1
                    logger.error(f"Parallel job failed: {scraped.job_id}: {e}")

        summary = {
            "total": len(jobs) + skipped,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
        }
        logger.info(f"PIPELINE -- Parallel batch complete: {summary}")
        return summary

    # ================================================================
    # Retry with Exponential Backoff (Task 5)
    # ================================================================

    def _process_with_retry(self, scraped, max_retries: int = 2) -> Optional[JobRecord]:
        """Process a single scraped job with exponential backoff retry."""
        for attempt in range(1, max_retries + 1):
            result = self.process_single(
                job_description=scraped.raw_jd,
                job_id=scraped.job_id,
                title=scraped.title,
                company=scraped.company,
                url=scraped.url,
                platform=scraped.platform,
            )

            if result:
                return result

            if attempt < max_retries:
                wait = 2 ** attempt  # 2s, 4s
                logger.info(f"Retry {attempt}/{max_retries} for {scraped.job_id} in {wait}s")
                time.sleep(wait)

        return None

    def retry_failed(self) -> dict:
        """Re-process all failed jobs with backoff."""
        failed_jobs = self.db.list_jobs(status="failed")
        logger.info(f"Retrying {len(failed_jobs)} failed jobs")

        completed = 0
        still_failed = 0

        for job in failed_jobs:
            if not job.raw_jd:
                still_failed += 1
                continue

            # Create a mock scraped job for retry
            class _MockScraped:
                pass

            mock = _MockScraped()
            mock.raw_jd = job.raw_jd
            mock.job_id = job.job_id
            mock.title = job.title
            mock.company = job.company
            mock.url = job.url
            mock.platform = job.platform

            result = self._process_with_retry(mock, max_retries=3)
            if result:
                completed += 1
            else:
                still_failed += 1

        return {"retried": len(failed_jobs), "completed": completed, "still_failed": still_failed}

    # ================================================================
    # Rankings & Insights
    # ================================================================

    def print_rankings(self):
        """Print job rankings."""
        self.ranker.print_rankings()

    def print_insights(self):
        """Print market insights."""
        self.ranker.print_insights()

    def print_stats(self):
        """Print pipeline statistics."""
        stats = self.db.get_stats()

        print("\n" + "=" * 50)
        print("📊  PIPELINE STATISTICS")
        print("=" * 50)
        print(f"  Total Jobs:       {stats['total_jobs']}")
        print(f"  Completed:        {stats['completed']}")
        print(f"  Pending:          {stats['pending']}")
        print(f"  Failed:           {stats['failed']}")
        print(f"  Avg Score Before: {stats['avg_score_before']}")
        print(f"  Avg Score After:  {stats['avg_score_after']}")
        print(f"  Avg Improvement:  +{stats['avg_improvement']}")
        print("=" * 50 + "\n")

    def list_completed_jobs(self):
        """List all completed jobs with scores."""
        jobs = self.db.list_jobs(status="completed")

        if not jobs:
            print("\n  No completed jobs yet.\n")
            return

        print(f"\n{'-' * 90}")
        print(f"  {'Job ID':<15s} {'Title':<25s} {'Company':<15s} {'Before':>7s} {'After':>7s} {'Δ':>5s} {'Decision':<8s}")
        print(f"{'-' * 90}")

        for job in jobs:
            title = (job.title or "?")[:24]
            company = (job.company or "?")[:14]
            before = job.ats_report.score_before if job.ats_report else 0
            after = job.ats_report.score_after if job.ats_report else 0
            imp = job.ats_report.improvement if job.ats_report else "+0"
            dec = job.ats_report.decision if job.ats_report else "?"
            print(f"  {job.job_id:<15s} {title:<25s} {company:<15s} {before:>7.1f} {after:>7.1f} {imp:>5s} {dec:<8s}")

        print(f"{'-' * 90}\n")

    # ================================================================
    # File Output
    # ================================================================

    def _save_output_files(self, record, tailored, extracted_jd, ats_report):
        """Save all output files for a processed job."""
        job_dir = os.path.join(self.output_dir, record.job_id)
        os.makedirs(job_dir, exist_ok=True)

        with open(os.path.join(job_dir, "tailored_resume.json"), "w", encoding="utf-8") as f:
            f.write(resume_to_json_string(tailored))

        with open(os.path.join(job_dir, "tailored_resume.txt"), "w", encoding="utf-8") as f:
            f.write(format_resume_text(tailored))

        with open(os.path.join(job_dir, "extracted_jd.json"), "w", encoding="utf-8") as f:
            f.write(extracted_jd.model_dump_json(indent=2))

        with open(os.path.join(job_dir, "ats_report.json"), "w", encoding="utf-8") as f:
            f.write(ats_report.model_dump_json(indent=2))

        with open(os.path.join(job_dir, "ats_report.txt"), "w", encoding="utf-8") as f:
            f.write(format_ats_report(ats_report))

        logger.info(f"Output files saved: {job_dir}/")

    def close(self):
        """Clean up resources."""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
