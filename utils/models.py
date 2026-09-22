"""
Pydantic data models -- the single source of truth for all structured data
flowing through the system.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# Resume Models
# ============================================================


class ContactInfo(BaseModel):
    """Candidate contact information."""
    name: str
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    portfolio: str = ""


class ExperienceEntry(BaseModel):
    """Single work experience block."""
    role: str
    company: str
    duration: str
    location: str = ""
    bullets: List[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    """Single education block."""
    degree: str
    institution: str
    year: str = ""
    gpa: str = ""
    details: str = ""


class ProjectEntry(BaseModel):
    """Single project block."""
    name: str
    description: str = ""
    technologies: List[str] = Field(default_factory=list)
    bullets: List[str] = Field(default_factory=list)


class CertificationEntry(BaseModel):
    """Single certification."""
    name: str
    issuer: str = ""
    year: str = ""


class StructuredResume(BaseModel):
    """
    Full structured resume in canonical JSON form.
    This is the schema the LLM must produce, and what the
    ATS scorer and PDF generator consume.
    """
    contact: ContactInfo
    title: str = ""
    summary: str = ""
    skills: List[str] = Field(default_factory=list)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    education: List[EducationEntry] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)
    certifications: List[CertificationEntry] = Field(default_factory=list)
    version: int = 1  # Resume version for tracking iterations


# ============================================================
# Job Description Models
# ============================================================


class ExtractedJD(BaseModel):
    """Parsed job description fields (extracted by LLM or scraper)."""
    job_title: str = ""
    company: str = ""
    location: str = ""
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    required_experience_years: Optional[int] = None
    education_requirements: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    raw_text: str = ""


# ============================================================
# ATS Scoring Models (Phase 2 -- defined here for contract)
# ============================================================


class ScoreBreakdown(BaseModel):
    """Detailed ATS score breakdown."""
    keyword_match: float = 0.0
    skills_match: float = 0.0
    experience_relevance: float = 0.0
    role_alignment: float = 0.0
    education_fit: float = 0.0
    resume_structure: float = 0.0


class ATSScoreReport(BaseModel):
    """Full ATS scoring report for a single resume ↔ JD pair."""
    job_id: str = ""
    score_before: float = 0.0
    score_after: float = 0.0
    improvement: str = "+0"
    breakdown_before: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    breakdown_after: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    matched_keywords: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    confidence_level: str = "MEDIUM"  # HIGH / MEDIUM / LOW
    risk_flags: List[str] = Field(default_factory=list)
    penalties_applied: List[str] = Field(default_factory=list)
    decision: str = "APPLY_WITH_FIXES"  # DO_NOT_APPLY / IMPROVE / APPLY_WITH_FIXES / APPLY
    semantic_score: float = 0.0  # TF-IDF cosine similarity (0-100)
    raw_semantic_score: float = 0.0  # Phase 4: pre-adjustment semantic measurement
    semantic_adjustments: List[str] = Field(default_factory=list)  # Phase 4: disclosed policy adjustments
    effort_level: str = "MEDIUM"  # LOW / MEDIUM / HIGH -- effort needed to match
    shortlist_probability: dict = Field(default_factory=dict)  # Probability engine output
    role_fit: dict = Field(default_factory=dict)  # Role fit assessment (Part 8)


# ============================================================
# Pipeline Models
# ============================================================


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobRecord(BaseModel):
    """A single job scraped and processed through the pipeline."""
    job_id: str
    platform: str = ""
    url: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    raw_jd: str = ""
    extracted_jd: Optional[ExtractedJD] = None
    original_resume: Optional[StructuredResume] = None
    tailored_resume: Optional[StructuredResume] = None
    ats_report: Optional[ATSScoreReport] = None
    pdf_path: str = ""
    status: ProcessingStatus = ProcessingStatus.PENDING
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
