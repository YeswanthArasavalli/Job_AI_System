"""
Loads and validates config.yaml into a typed dataclass for safe access.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List

import yaml


@dataclass
class LLMConfig:
    provider: str = "ollama"
    model: str = "llama3.2:3b"
    base_url: str = "http://localhost:11434"
    timeout: int = 120
    temperature: float = 0.0
    top_p: float = 0.9
    seed: int = 42
    max_retries: int = 3


@dataclass
class ResumeEngineConfig:
    master_resume_path: str = "data/master_resume.json"
    output_dir: str = "output/resumes"
    max_skills: int = 15
    max_experience_bullets: int = 5


@dataclass
class ATSScoringConfig:
    weights: Dict[str, float] = field(default_factory=lambda: {
        "keyword_match": 0.30,
        "skills_match": 0.25,
        "experience_relevance": 0.20,
        "role_alignment": 0.10,
        "education_fit": 0.05,
        "resume_structure": 0.10,
    })


@dataclass
class PDFConfig:
    output_dir: str = "output/pdfs"
    font_family: str = "Helvetica"
    font_size: int = 10
    margin: int = 20


@dataclass
class ScraperConfig:
    platform: str = "linkedin"
    max_jobs: int = 25
    headless: bool = False
    login_wait_seconds: int = 60
    scroll_pause: float = 2.0
    user_data_dir: str = "browser_data"


@dataclass
class DatabaseConfig:
    path: str = "data/job_ai_system.db"


@dataclass
class LoggingConfig:
    level: str = "INFO"
    log_file: str = "logs/system.log"
    max_bytes: int = 5_242_880
    backup_count: int = 3


@dataclass
class UserPreferences:
    preferred_roles: List[str] = field(default_factory=list)
    skill_priority: List[str] = field(default_factory=list)
    min_score_threshold: int = 0
    excluded_companies: List[str] = field(default_factory=list)


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    resume_engine: ResumeEngineConfig = field(default_factory=ResumeEngineConfig)
    ats_scoring: ATSScoringConfig = field(default_factory=ATSScoringConfig)
    pdf_generator: PDFConfig = field(default_factory=PDFConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    user_preferences: UserPreferences = field(default_factory=UserPreferences)


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """Load config.yaml and return a typed AppConfig."""

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raw = {}

    llm = LLMConfig(**raw.get("llm", {}))
    resume_engine = ResumeEngineConfig(**raw.get("resume_engine", {}))

    ats_scoring_raw = raw.get("ats_scoring", {})
    ats_scoring = ATSScoringConfig(
        weights=ats_scoring_raw.get("weights", ATSScoringConfig().weights)
    )

    pdf_generator = PDFConfig(**raw.get("pdf_generator", {}))
    scraper = ScraperConfig(**raw.get("scraper", {}))
    database = DatabaseConfig(**raw.get("database", {}))
    logging_cfg = LoggingConfig(**raw.get("logging", {}))
    user_prefs = UserPreferences(**raw.get("user_preferences", {}))

    return AppConfig(
        llm=llm,
        resume_engine=resume_engine,
        ats_scoring=ats_scoring,
        pdf_generator=pdf_generator,
        scraper=scraper,
        database=database,
        logging=logging_cfg,
        user_preferences=user_prefs,
    )
