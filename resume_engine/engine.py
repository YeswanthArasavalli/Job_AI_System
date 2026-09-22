"""
Resume Engine -- the core orchestrator for Phase 1.

Responsibilities:
  1. Load master resume
  2. Analyze job description (extract keywords/skills via LLM)
  3. Tailor resume to JD (via LLM)
  4. Validate and return structured output

Production features:
  - JSON repair + retry on parse failure (re-prompts with explicit error)
  - Content protection (prevents LLM from deleting core experience)
  - Hash-based LLM response caching (deterministic mode)
  - Structured timing metrics
"""

import hashlib
import json
import os
import re
import time
from typing import Optional, Tuple

from utils.ollama_client import check_ollama, call_ollama, get_client

from resume_engine.prompts import (
    build_resume_tailoring_prompt,
    build_jd_analysis_prompt,
)
from resume_engine.parser import (
    load_resume,
    resume_to_json_string,
    parse_llm_resume_output,
    repair_json,
)
from utils.config_loader import load_config, AppConfig
from utils.logger import setup_logger
from utils.models import ExtractedJD, StructuredResume

logger = setup_logger(__name__)

# Cache directory
CACHE_DIR = "data/cache"


class ResumeEngine:
    """
    Core resume tailoring engine.

    Usage:
        engine = ResumeEngine()
        original, tailored, jd_info = engine.process(
            master_resume_path="data/master_resume.json",
            job_description="We are looking for a Senior Python Developer..."
        )
    """

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or load_config()
        self.model = self.config.llm.model
        self.temperature = self.config.llm.temperature
        self.max_retries = self.config.llm.max_retries
        self.timeout = self.config.llm.timeout

        # Ensure cache directory
        os.makedirs(CACHE_DIR, exist_ok=True)

        # Check Ollama connectivity on init
        status = check_ollama(self.config)
        if status["connected"]:
            logger.info(
                f"ResumeEngine initialized | model={self.model} | "
                f"Ollama connected | {len(status['models'])} models"
            )
            if not status["model_available"]:
                logger.warning(
                    f"Configured model '{self.model}' not found in Ollama. "
                    f"Available: {', '.join(status['models'][:5])}"
                )
        else:
            logger.warning(
                f"ResumeEngine initialized | model={self.model} | "
                f"Ollama NOT connected: {status['error']}. "
                f"LLM calls will fail, fallback mode active."
            )

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def process(
        self,
        master_resume_path: str,
        job_description: str,
    ) -> Tuple[StructuredResume, StructuredResume, ExtractedJD]:
        """
        Full Phase 1 pipeline:
          1. Load master resume
          2. Analyze JD -> ExtractedJD
          3. Tailor resume -> StructuredResume (with content protection)

        Returns:
            (original_resume, tailored_resume, extracted_jd)
        """
        pipeline_start = time.time()
        logger.info("=" * 60)
        logger.info("RESUME ENGINE -- Starting pipeline")
        logger.info("=" * 60)

        # Step 1 -- Load master resume
        original_resume = load_resume(master_resume_path)
        logger.info(f"[OK] Master resume loaded: {original_resume.contact.name}")

        # Step 2 -- Analyze JD
        logger.info("Analyzing job description...")
        extracted_jd = self.analyze_jd(job_description)
        logger.info(
            f"[OK] JD analyzed: {extracted_jd.job_title} @ {extracted_jd.company} | "
            f"{len(extracted_jd.required_skills)} required skills | "
            f"{len(extracted_jd.keywords)} keywords"
        )

        # Step 3 -- Tailor resume (with content protection)
        logger.info("Tailoring resume to JD...")
        tailored_resume = self.tailor_resume(original_resume, job_description)

        # Content protection validation
        tailored_resume = self._enforce_content_protection(original_resume, tailored_resume)

        logger.info(
            f"[OK] Resume tailored: {len(tailored_resume.skills)} skills | "
            f"{len(tailored_resume.experience)} experience entries"
        )

        elapsed = time.time() - pipeline_start
        logger.info(f"RESUME ENGINE -- Pipeline complete in {elapsed:.1f}s")
        logger.info("=" * 60)

        return original_resume, tailored_resume, extracted_jd

    def analyze_jd(self, job_description: str) -> ExtractedJD:
        """Extract structured information from a raw job description."""
        messages = build_jd_analysis_prompt(job_description)

        # Check cache
        cache_key = self._cache_key("jd_analysis", job_description)
        cached = self._get_cache(cache_key)
        if cached:
            logger.info("JD analysis loaded from cache")
            try:
                data = json.loads(cached)
                return ExtractedJD(**data, raw_text=job_description)
            except Exception:
                pass  # Cache corrupted, re-generate

        # Try LLM analysis with fail-safe
        try:
            raw_output = self._call_llm_with_json_retry(messages, task="JD Analysis")

            try:
                cleaned = repair_json(raw_output)
                data = json.loads(cleaned)
                result = ExtractedJD(**data, raw_text=job_description)
                self._set_cache(cache_key, cleaned)
                return result
            except (json.JSONDecodeError, ValueError, Exception) as e:
                logger.warning(f"JD analysis parse failed: {e}. Using fallback extraction.")
                return self._fallback_jd_extraction(job_description)

        except RuntimeError as e:
            logger.warning(
                f"LLM unavailable for JD analysis: {e}. "
                f"Falling back to rule-based extraction."
            )
            return self._fallback_jd_extraction(job_description)

    def tailor_resume(
        self,
        original_resume: StructuredResume,
        job_description: str,
    ) -> StructuredResume:
        """Tailor a resume to match a specific job description."""
        resume_json_str = resume_to_json_string(original_resume)
        messages = build_resume_tailoring_prompt(resume_json_str, job_description)

        # -- IDENTITY LOCK: capture before LLM call --------
        locked_contact = original_resume.contact.model_copy(deep=True)
        locked_companies = [exp.company for exp in original_resume.experience]
        locked_roles = [exp.role for exp in original_resume.experience]
        locked_durations = [exp.duration for exp in original_resume.experience]
        locked_education = [edu.model_copy(deep=True) for edu in original_resume.education]
        locked_certs = [cert.model_copy(deep=True) for cert in original_resume.certifications]

        logger.info(f"Identity locked: name={locked_contact.name}, companies={locked_companies}")

        # Check cache
        cache_key = self._cache_key("resume_tailor", resume_json_str + job_description)
        cached = self._get_cache(cache_key)
        if cached:
            logger.info("Tailored resume loaded from cache")
            try:
                tailored = parse_llm_resume_output(cached)
                tailored = self._lock_identity(tailored, locked_contact, locked_companies,
                                                locked_roles, locked_durations,
                                                locked_education, locked_certs)
                return tailored
            except Exception:
                pass  # Cache corrupted, re-generate

        raw_output = self._call_llm_with_json_retry(messages, task="Resume Tailoring")

        try:
            tailored = parse_llm_resume_output(raw_output)

            # -- IDENTITY LOCK: force original identity fields --
            tailored = self._lock_identity(tailored, locked_contact, locked_companies,
                                            locked_roles, locked_durations,
                                            locked_education, locked_certs)

            self._set_cache(cache_key, raw_output)
            return tailored
        except ValueError as e:
            logger.error(f"Resume tailoring parse failed: {e}")
            raise

    @staticmethod
    def _lock_identity(
        tailored: StructuredResume,
        contact: 'ContactInfo',
        companies: list,
        roles: list,
        durations: list,
        education: list,
        certifications: list,
    ) -> StructuredResume:
        """
        Force original identity fields onto the LLM output.
        Detects and logs any identity drift.
        """
        # Force contact info
        if tailored.contact.name != contact.name:
            logger.warning(
                f"IDENTITY DRIFT DETECTED: LLM changed name "
                f"'{contact.name}' -> '{tailored.contact.name}'. Reverting."
            )
        tailored.contact = contact

        # Force company names, roles, and durations back onto experience
        for i, exp in enumerate(tailored.experience):
            if i < len(companies):
                if exp.company != companies[i]:
                    logger.warning(
                        f"FABRICATION DETECTED: LLM changed company "
                        f"'{companies[i]}' -> '{exp.company}'. Reverting."
                    )
                    exp.company = companies[i]
                if exp.role != roles[i]:
                    logger.warning(
                        f"FABRICATION DETECTED: LLM changed role "
                        f"'{roles[i]}' -> '{exp.role}'. Reverting."
                    )
                    exp.role = roles[i]
                if exp.duration != durations[i]:
                    exp.duration = durations[i]

        # Detect fabricated experience entries (more than original)
        if len(tailored.experience) > len(companies):
            extra = len(tailored.experience) - len(companies)
            logger.warning(
                f"FABRICATION DETECTED: LLM added {extra} fake experience entries. Removing."
            )
            tailored.experience = tailored.experience[:len(companies)]

        # Force education and certifications
        tailored.education = education
        tailored.certifications = certifications

        return tailored

    # ----------------------------------------------------------------
    # Content Protection
    # ----------------------------------------------------------------

    def _enforce_content_protection(
        self,
        original: StructuredResume,
        tailored: StructuredResume,
    ) -> StructuredResume:
        """
        Validate that the LLM didn't destructively delete core content.

        Rules:
          1. Must keep at least 50% of experience entries (never drop all)
          2. Must keep ALL education entries
          3. Contact info must be preserved (already enforced earlier)
          4. Must have at least 3 skills
          5. Must have a summary
        """
        issues = []

        # Rule 1: Experience protection
        orig_exp_count = len(original.experience)
        tail_exp_count = len(tailored.experience)
        min_exp = max(1, orig_exp_count // 2)  # At least 50% or 1

        if tail_exp_count < min_exp and orig_exp_count > 0:
            issues.append(
                f"Experience entries dropped from {orig_exp_count} to {tail_exp_count}. "
                f"Restoring missing entries."
            )
            # Restore missing experience (add them back at the end)
            existing_companies = {
                (e.company.lower(), e.role.lower()) for e in tailored.experience
            }
            for exp in original.experience:
                key = (exp.company.lower(), exp.role.lower())
                if key not in existing_companies:
                    tailored.experience.append(exp)
                    existing_companies.add(key)
                    if len(tailored.experience) >= orig_exp_count:
                        break

        # Rule 2: Education must be preserved
        if len(tailored.education) < len(original.education):
            issues.append("Education entries were removed. Restoring.")
            tailored.education = original.education.copy()

        # Rule 3: Minimum skills
        if len(tailored.skills) < 3 and len(original.skills) >= 3:
            issues.append(f"Only {len(tailored.skills)} skills. Merging with original.")
            merged_skills = list(tailored.skills)
            for skill in original.skills:
                if skill not in merged_skills:
                    merged_skills.append(skill)
                if len(merged_skills) >= 8:
                    break
            tailored.skills = merged_skills

        # Rule 4: Summary must exist
        if not tailored.summary or len(tailored.summary) < 20:
            if original.summary and len(original.summary) >= 20:
                issues.append("Summary was removed or too short. Restoring original.")
                tailored.summary = original.summary

        for issue in issues:
            logger.warning(f"Content protection: {issue}")

        return tailored

    # ----------------------------------------------------------------
    # LLM Communication
    # ----------------------------------------------------------------

    def _call_llm_with_json_retry(self, messages: list, task: str = "LLM") -> str:
        """
        Call LLM with JSON-specific retry logic.
        If JSON parse fails, re-prompt with explicit error feedback.
        """
        for attempt in range(1, self.max_retries + 1):
            raw = self._call_llm(messages, task=task, attempt=attempt)

            # Quick JSON validity check
            try:
                repair_json(raw)
                return raw  # Valid JSON, return it
            except ValueError as e:
                if attempt < self.max_retries:
                    logger.warning(
                        f"[{task}] JSON invalid on attempt {attempt}: {e}. "
                        f"Re-prompting with error feedback."
                    )
                    # Add error feedback to messages for next attempt
                    messages = messages + [
                        {"role": "assistant", "content": raw},
                        {
                            "role": "user",
                            "content": (
                                f"ERROR: Your response was not valid JSON. "
                                f"Parse error: {str(e)[:200]}. "
                                f"Please try again. Output ONLY valid JSON, no markdown, "
                                f"no explanation, no code fences."
                            ),
                        },
                    ]
                else:
                    logger.warning(f"[{task}] JSON invalid on final attempt, returning raw.")
                    return raw  # Let the caller handle the error

        return raw  # Satisfy type checker

    def _call_llm(self, messages: list, task: str = "LLM", attempt: int = 1) -> str:
        """
        Call Ollama via centralized connection manager.
        Uses explicit host, retry, and timeout protection.
        """
        return call_ollama(
            messages=messages,
            task=task,
            attempt=attempt,
            config=self.config,
        )

    # ----------------------------------------------------------------
    # Caching
    # ----------------------------------------------------------------

    @staticmethod
    def _cache_key(prefix: str, content: str) -> str:
        """Generate a deterministic cache key from input content."""
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        return f"{prefix}_{content_hash}"

    @staticmethod
    def _get_cache(key: str) -> Optional[str]:
        """Load cached LLM response if it exists."""
        path = os.path.join(CACHE_DIR, f"{key}.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                return None
        return None

    @staticmethod
    def _set_cache(key: str, content: str):
        """Save LLM response to disk cache."""
        path = os.path.join(CACHE_DIR, f"{key}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.debug(f"Cached response: {key}")
        except Exception as e:
            logger.warning(f"Failed to cache response: {e}")

    @staticmethod
    def clear_cache():
        """Clear ALL disk cache for stateless execution."""
        if os.path.exists(CACHE_DIR):
            import glob
            for f in glob.glob(os.path.join(CACHE_DIR, "*.json")):
                try:
                    os.remove(f)
                except Exception:
                    pass
            logger.info("LLM cache cleared for stateless run")

    # ----------------------------------------------------------------
    # Fallback JD extraction
    # ----------------------------------------------------------------

    @staticmethod
    def _fallback_jd_extraction(job_description: str) -> ExtractedJD:
        """
        Rule-based fallback when LLM JD analysis fails.
        Extracts basic info through keyword scanning.
        """
        text_lower = job_description.lower()

        common_skills = [
            "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
            "sql", "nosql", "mongodb", "postgresql", "mysql", "redis", "elasticsearch",
            "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
            "react", "angular", "vue", "node.js", "django", "flask", "fastapi",
            "machine learning", "deep learning", "nlp", "computer vision",
            "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch",
            "git", "ci/cd", "jenkins", "github actions",
            "rest api", "graphql", "microservices",
            "agile", "scrum", "jira",
            "power bi", "tableau", "excel", "spark", "hadoop",
            "linux", "bash", "shell scripting",
            "html", "css", "sass",
        ]

        found_skills = [s for s in common_skills if s in text_lower]

        exp_years = None
        year_patterns = [
            r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)",
            r"(?:experience|exp)\s*(?:of)?\s*(\d+)\+?\s*(?:years?|yrs?)",
        ]
        for pattern in year_patterns:
            match = re.search(pattern, text_lower)
            if match:
                exp_years = int(match.group(1))
                break

        return ExtractedJD(
            required_skills=found_skills,
            keywords=found_skills,
            required_experience_years=exp_years,
            raw_text=job_description,
        )