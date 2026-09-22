"""
Job Source Adapter Architecture

Extensible ingestion layer for job listings from multiple sources.

To add a new source:
  1. Subclass SourceAdapter
  2. Implement fetch_jobs()
  3. Register in SourceRegistry

Sources do NOT need to know about each other, the pipeline, or the database.
They produce NormalizedJob objects. Everything downstream is source-agnostic.

Current adapters:
  - LinkedInAdapter   (Playwright-based)
  - ManualAdapter     (paste raw JD text)

Planned:
  - NaukriAdapter
  - IndeedAdapter
  - GreenhouseAdapter (API)
  - LeverAdapter      (API)
  - WorkdayAdapter    (API)
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)


# ================================================================
# NORMALIZED JOB — source-agnostic output of all adapters
# ================================================================

@dataclass
class NormalizedJob:
    """
    Source-agnostic job record produced by all adapters.
    This is the contract between ingestion and the pipeline.
    All adapters must produce this format.
    """
    # Identifiers
    job_id: str              # Deterministic: MD5(source + url or title+company)
    source: str              # "linkedin" | "naukri" | "indeed" | "manual" | etc.
    url: str = ""

    # Job metadata
    title: str = ""
    company: str = ""
    location: str = ""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = ""
    employment_type: str = ""   # full-time | contract | part-time

    # JD content
    raw_jd: str = ""
    posted_date: str = ""

    # Ingestion metadata
    ingested_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    ingestion_status: str = "raw"  # raw | processed | failed


def make_job_id(source: str, unique_key: str) -> str:
    """Create a deterministic job ID from source + unique key."""
    return hashlib.md5(f"{source}:{unique_key}".encode()).hexdigest()[:16]


# ================================================================
# ABSTRACT SOURCE ADAPTER
# ================================================================

class SourceAdapter(ABC):
    """
    Abstract base for all job source adapters.

    Subclasses must implement:
        fetch_jobs(query, location, max_results) -> List[NormalizedJob]

    Adapters should:
        - Handle their own auth / session management
        - Handle rate limiting and retries internally
        - Never raise on individual job failure (skip and log)
        - Return NormalizedJob objects (not source-specific objects)
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique name for this source. Used in job_id generation."""
        ...

    @abstractmethod
    def fetch_jobs(
        self,
        query: str,
        location: str = "",
        max_results: int = 20,
    ) -> List[NormalizedJob]:
        """
        Fetch job listings matching query + location.

        Args:
            query:       Job title or keywords (e.g. "Data Analyst")
            location:    City, country, or remote (e.g. "Bengaluru, India")
            max_results: Maximum number of jobs to return

        Returns:
            List of NormalizedJob objects. May be empty if no results.
        """
        ...

    def test_connection(self) -> bool:
        """
        Test whether the adapter can reach its source.
        Override if the source has a health check endpoint.
        Returns True if reachable, False otherwise.
        """
        return True


# ================================================================
# MANUAL ADAPTER — paste raw JD text
# ================================================================

class ManualAdapter(SourceAdapter):
    """
    Adapter for manually pasted job descriptions.
    Used by the Streamlit UI when a user pastes a JD directly.
    """

    @property
    def source_name(self) -> str:
        return "manual"

    def fetch_jobs(
        self,
        query: str = "",
        location: str = "",
        max_results: int = 1,
    ) -> List[NormalizedJob]:
        # Manual adapter is typically called with pre-built NormalizedJob
        # This is a no-op fetch — use from_raw_jd() instead
        return []

    @staticmethod
    def from_raw_jd(
        raw_jd: str,
        title: str = "",
        company: str = "",
        location: str = "",
    ) -> NormalizedJob:
        """
        Wrap a raw JD paste into a NormalizedJob.
        Used by app.py when the user pastes a JD directly.
        """
        unique_key = hashlib.md5(raw_jd[:500].encode()).hexdigest()
        return NormalizedJob(
            job_id=make_job_id("manual", unique_key),
            source="manual",
            title=title,
            company=company,
            location=location,
            raw_jd=raw_jd,
        )


# ================================================================
# LINKEDIN ADAPTER — wraps existing LinkedInScraper
# ================================================================

class LinkedInAdapter(SourceAdapter):
    """
    LinkedIn job adapter using the existing Playwright-based scraper.
    Wraps scraper/linkedin_scraper.py into the NormalizedJob format.
    """

    @property
    def source_name(self) -> str:
        return "linkedin"

    def __init__(self, headless: bool = False):
        self._headless = headless
        self._scraper = None  # Lazy init (Playwright is heavy)

    def _get_scraper(self):
        if self._scraper is None:
            from scraper.linkedin_scraper import LinkedInScraper
            self._scraper = LinkedInScraper(headless=self._headless)
        return self._scraper

    def fetch_jobs(
        self,
        query: str,
        location: str = "",
        max_results: int = 20,
    ) -> List[NormalizedJob]:
        try:
            scraper = self._get_scraper()
            scraped = scraper.scrape(
                search_query=query,
                location=location,
                max_jobs=max_results,
            )
            return [self._normalize(j) for j in scraped]
        except Exception as e:
            logger.error(f"[LinkedInAdapter] fetch failed: {e}")
            return []

    def _normalize(self, scraped) -> NormalizedJob:
        """Convert ScrapedJob → NormalizedJob."""
        return NormalizedJob(
            job_id=make_job_id("linkedin", scraped.url or scraped.job_id),
            source="linkedin",
            url=scraped.url,
            title=scraped.title,
            company=scraped.company,
            location=scraped.location,
            raw_jd=scraped.raw_jd,
        )


# ================================================================
# GREENHOUSE ADAPTER — API-based (template for API sources)
# ================================================================

class GreenhouseAdapter(SourceAdapter):
    """
    Greenhouse job board API adapter.
    Reads public job listings from a company's Greenhouse board.

    Usage:
        adapter = GreenhouseAdapter(board_token="company-name")
        jobs = adapter.fetch_jobs("Data Engineer")
    """

    GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"

    @property
    def source_name(self) -> str:
        return "greenhouse"

    def __init__(self, board_token: str):
        self._board = board_token

    def fetch_jobs(
        self,
        query: str,
        location: str = "",
        max_results: int = 20,
    ) -> List[NormalizedJob]:
        try:
            import urllib.request, json
            url = self.GREENHOUSE_API.format(board=self._board)
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
            jobs = data.get("jobs", [])
            # Filter by query
            query_lower = query.lower()
            matched = [
                j for j in jobs
                if query_lower in j.get("title", "").lower()
            ][:max_results]
            return [self._normalize(j) for j in matched]
        except Exception as e:
            logger.error(f"[GreenhouseAdapter] fetch failed: {e}")
            return []

    def _normalize(self, job_data: dict) -> NormalizedJob:
        # Extract content from HTML if present
        content = job_data.get("content", "")
        # Strip HTML tags
        raw_jd = re.sub(r"<[^>]+>", " ", content).strip()
        location_parts = job_data.get("location", {})
        return NormalizedJob(
            job_id=make_job_id("greenhouse", str(job_data.get("id", ""))),
            source="greenhouse",
            url=job_data.get("absolute_url", ""),
            title=job_data.get("title", ""),
            company=self._board,
            location=location_parts.get("name", "") if isinstance(location_parts, dict) else "",
            raw_jd=raw_jd,
        )


# ================================================================
# SOURCE REGISTRY — add new sources without touching core code
# ================================================================

class SourceRegistry:
    """
    Registry of all available job source adapters.

    To add a new source:
        registry = SourceRegistry()
        registry.register(MyNewAdapter())

    Thread-safe for reads. Not designed for concurrent writes.
    """

    def __init__(self):
        self._adapters: dict[str, SourceAdapter] = {}
        # Register built-in adapters
        self.register(ManualAdapter())
        logger.info("[SourceRegistry] initialized with built-in adapters")

    def register(self, adapter: SourceAdapter) -> None:
        """Register an adapter. Overwrites if same source_name already registered."""
        self._adapters[adapter.source_name] = adapter
        logger.info(f"[SourceRegistry] registered: {adapter.source_name}")

    def get(self, source_name: str) -> Optional[SourceAdapter]:
        """Get adapter by source name. Returns None if not registered."""
        return self._adapters.get(source_name)

    def list_sources(self) -> List[str]:
        """List all registered source names."""
        return list(self._adapters.keys())

    def fetch_from(
        self,
        source_name: str,
        query: str,
        location: str = "",
        max_results: int = 20,
    ) -> List[NormalizedJob]:
        """Fetch jobs from a named source. Returns [] if source not found."""
        adapter = self.get(source_name)
        if not adapter:
            logger.error(f"[SourceRegistry] unknown source: {source_name}")
            return []
        return adapter.fetch_jobs(query, location, max_results)

    def fetch_from_all(
        self,
        query: str,
        location: str = "",
        max_results_per_source: int = 10,
        sources: Optional[List[str]] = None,
    ) -> List[NormalizedJob]:
        """
        Fetch from multiple sources in parallel (or sequentially as fallback).
        Deduplicates by job_id.
        """
        targets = sources or self.list_sources()
        all_jobs: dict[str, NormalizedJob] = {}

        for source_name in targets:
            try:
                jobs = self.fetch_from(source_name, query, location, max_results_per_source)
                for job in jobs:
                    if job.job_id not in all_jobs:
                        all_jobs[job.job_id] = job
                logger.info(f"[SourceRegistry] {source_name}: {len(jobs)} jobs fetched")
            except Exception as e:
                logger.error(f"[SourceRegistry] {source_name} failed: {e}")

        return list(all_jobs.values())


# ================================================================
# INGESTION PIPELINE — fetch → process → store
# ================================================================

class IngestionPipeline:
    """
    End-to-end job ingestion pipeline.

    Flow:
        1. Fetch raw jobs from source adapters
        2. Process each JD through JDProcessor
        3. Score each job against candidate resume
        4. Store results in database
        5. Return ranked job list

    Usage:
        pipeline = IngestionPipeline(registry, db_manager, candidate_resume, scorer)
        jobs = pipeline.ingest(query="Data Analyst", location="Bengaluru", source="linkedin")
    """

    def __init__(
        self,
        registry: SourceRegistry,
        db_manager,           # database.db_manager.DatabaseManager
        candidate_resume,     # StructuredResume
        scorer,               # ATSScorer
    ):
        self._registry = registry
        self._db = db_manager
        self._resume = candidate_resume
        self._scorer = scorer

    def ingest(
        self,
        query: str,
        location: str = "",
        source: str = "linkedin",
        max_results: int = 20,
    ) -> List[dict]:
        """
        Fetch, process, score, and store jobs.
        Returns list of scored job dicts.
        """
        from jd_processor.processor import JDProcessor
        from utils.models import ExtractedJD, JobRecord

        logger.info(f"[IngestionPipeline] query='{query}' source={source} max={max_results}")
        raw_jobs = self._registry.fetch_from(source, query, location, max_results)
        logger.info(f"[IngestionPipeline] fetched {len(raw_jobs)} raw jobs")

        processor = JDProcessor()
        results = []

        for raw_job in raw_jobs:
            try:
                # Skip if already in database
                existing = self._db.get_job(raw_job.job_id)
                if existing and existing.get("status") == "completed":
                    results.append(existing)
                    continue

                # Process JD
                processed = processor.process(raw_job.raw_jd)
                jd = ExtractedJD(
                    job_title=raw_job.title,
                    company=raw_job.company,
                    location=raw_job.location,
                    required_skills=processed.skills_required,
                    preferred_skills=processed.skills_preferred,
                    keywords=[s.lower() for s in processed.skills_required + processed.tools],
                    responsibilities=processed.responsibilities[:10],
                    raw_text=raw_job.raw_jd,
                )

                # Quick ATS score (not full pipeline — fast screening)
                score, breakdown, details = self._scorer.score(self._resume, jd)
                missing = details.get("skills", {}).get("missing", [])

                job_dict = {
                    "job_id": raw_job.job_id,
                    "source": raw_job.source,
                    "url": raw_job.url,
                    "title": raw_job.title,
                    "company": raw_job.company,
                    "location": raw_job.location,
                    "salary_min": raw_job.salary_min,
                    "salary_max": raw_job.salary_max,
                    "raw_jd": raw_job.raw_jd,
                    "ats_score": round(score, 1),
                    "missing_skills": missing[:10],
                    "matched_skills": details.get("skills", {}).get("matched", [])[:10],
                    "status": "screened",
                    "ingested_at": raw_job.ingested_at,
                }

                # Persist to database
                self._db.save_ingested_job(job_dict)
                results.append(job_dict)
                logger.info(f"[IngestionPipeline] {raw_job.company} '{raw_job.title}': ATS={score:.0f}")

            except Exception as e:
                logger.error(f"[IngestionPipeline] failed for {raw_job.job_id}: {e}")

        # Sort by ATS score descending
        results.sort(key=lambda j: j.get("ats_score", 0), reverse=True)
        logger.info(f"[IngestionPipeline] complete: {len(results)} jobs processed")
        return results


# ================================================================
# DEFAULT REGISTRY — module-level singleton
# ================================================================

_default_registry: Optional[SourceRegistry] = None


def get_registry() -> SourceRegistry:
    """Get or create the default source registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = SourceRegistry()
    return _default_registry
