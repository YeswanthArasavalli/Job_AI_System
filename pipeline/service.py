"""Canonical Application Service (Phase 3 - Execution-Path Convergence).

ONE application-level analysis entry point for every surface:

    result = analyze_resume(resume_text=..., jd_text=..., mode=...)   # raw-text path
    result = analyze(original, jd, mode=...)                          # structured path

Surfaces (app.py, dashboard.py via manual_mode, CLI) MUST call this service.
UI layers must not reimplement analysis/scoring logic.

The service is a THIN wrapper: it owns input normalization and output
packaging only. All intelligence lives in pipeline.core.run_full_pipeline.
"""
import copy
import logging
import re
from typing import Optional, Union

from utils.config_loader import load_config, AppConfig
from utils.logger import setup_logger
from utils.models import ContactInfo, ExtractedJD, ExperienceEntry, StructuredResume
from ats_scoring.scorer import ATSScorer
from pipeline.core import run_full_pipeline, evaluate_resume_quality

logger = setup_logger(__name__)


# ---------------------------------------------------------------------------
# JD construction (shared by every surface; was previously duplicated between
# app.py's inline regexes and manual_mode's engine.analyze_jd)
# ---------------------------------------------------------------------------

def build_jd(jd_text: str, config: Optional[AppConfig] = None) -> ExtractedJD:
    """Normalize raw JD text into the canonical ExtractedJD contract.

    Uses jd_processor for skills/responsibilities, plus deterministic
    regexes for title/company/experience years (single shared implementation).
    """
    from jd_processor.processor import JDProcessor
    if config is None:
        config = load_config()

    normalized = " ".join(jd_text.split())
    processed = JDProcessor().process(normalized)

    title = ""
    m = re.match(r"^(.{5,80})$", normalized.strip().split("\n")[0])
    if m:
        title = m.group(1).strip()
    company = ""
    cm = re.search(r'(?:at|@|--)\s+([A-Z][A-Za-z\s&]+)', normalized[:200])
    if cm:
        company = cm.group(1).strip()
    exp_years = None
    em = re.search(r"(\d+)\+?\s*(?:years?|yrs?)", normalized.lower())
    if em:
        exp_years = int(em.group(1))

    return ExtractedJD(
        job_title=title,
        company=company,
        required_skills=processed.skills_required,
        preferred_skills=processed.skills_preferred,
        keywords=[s.lower() for s in
                  processed.skills_required + processed.skills_preferred + processed.tools],
        responsibilities=processed.responsibilities[:10],
        required_experience_years=exp_years,
        raw_text=jd_text,
    )


# ---------------------------------------------------------------------------
# Canonical analysis
# ---------------------------------------------------------------------------

def analyze(
    original: StructuredResume,
    jd: ExtractedJD,
    mode: str = "strict",
    job_id: str = "canonical_analysis",
    config: Optional[AppConfig] = None,
):
    """Run the canonical analysis and return the pipeline PipelineResult.

    This is THE analysis entry point. Every product surface consumes the
    returned PipelineResult (single result contract). No surface may
    recompute scores or shortlist values from raw resume data.
    """
    if config is None:
        config = load_config()

    # STATELESS guarantees (previously only in manual_mode):
    try:
        from resume_engine.engine import ResumeEngine as _RE
        _RE.clear_cache()
    except Exception:
        pass
    try:
        from ats_scoring.semantic_matcher import SemanticMatcher
        SemanticMatcher._embedding_cache = {}
    except Exception:
        pass

    scorer = ATSScorer(config)
    return run_full_pipeline(
        original=original,
        tailored=original.model_copy(deep=True),
        extracted_jd=jd,
        scorer=scorer,
        job_id=job_id,
        mode=mode,
    )


def analyze_resume(
    resume: Union[str, StructuredResume],
    jd_text: str,
    mode: str = "strict",
    job_id: str = "canonical_analysis",
    config: Optional[AppConfig] = None,
) -> dict:
    """Full-text convenience entry point -> canonical result dict.

    Returns a surface-neutral dict built ONLY from PipelineResult fields
    (plus parsing), so app.py / dashboard / CLI render identical values.
    """
    if config is None:
        config = load_config()

    if len((jd_text or "").strip()) < 20:
        return {"success": False, "error": "JD text is too short. Provide a full job description."}

    # --- candidate ingestion (text or structured) ---
    if isinstance(resume, StructuredResume):
        structured = resume
    else:
        from resume_parser.rule_based_parser import RuleBasedResumeParser
        data = RuleBasedResumeParser().parse(resume)
        structured = StructuredResume(
            contact=ContactInfo(**{k: (data.get("contact") or {}).get(k, "")
                                   for k in ("name", "email", "phone")}),
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            skills=data.get("skills", []),
            experience=[_exp(e) for e in data.get("experience", [])],
            projects=data.get("projects", []),
            education=data.get("education", []),
        )

    jd = build_jd(jd_text, config)
    result = analyze(structured, jd, mode=mode, job_id=job_id, config=config)
    payload = package_result(result, mode)
    payload["candidate"] = structured
    payload["jd"] = jd
    return payload


def _exp(e):
    from utils.models import ExperienceEntry
    return e if isinstance(e, ExperienceEntry) else ExperienceEntry(**e)


def analyze_tailored(
    original: StructuredResume,
    tailored: StructuredResume,
    jd: ExtractedJD,
    mode: str = "strict",
    job_id: str = "canonical_analysis",
    config: Optional[AppConfig] = None,
    scorer: Optional[ATSScorer] = None,
):
    """Canonical analysis with an explicit tailored base.

    Surfaces that pre-tailor the resume through the LLM engine (dashboard path)
    pass that tailored resume here so tailoring depth is preserved while all
    scoring/shortlist/truth remain canonical. Surfaces without an LLM-tailored
    base use analyze() (tailored = deep copy of original).
    """
    if config is None:
        config = load_config()
    try:
        from resume_engine.engine import ResumeEngine as _RE
        _RE.clear_cache()
    except Exception:
        pass
    try:
        from ats_scoring.semantic_matcher import SemanticMatcher
        SemanticMatcher._embedding_cache = {}
    except Exception:
        pass

    scorer = scorer or ATSScorer(config)
    return run_full_pipeline(
        original=original,
        tailored=tailored,
        extracted_jd=jd,
        scorer=scorer,
        job_id=job_id,
        mode=mode,
    )

def package_result(result, mode: str) -> dict:
    """Package PipelineResult into the canonical surface-neutral dict.

    Every value is read from PipelineResult / ats_report fields.
    No surface may add its own scoring here.
    """
    ats = result.ats_report
    improved_text_bullets = [b for e in result.improved.experience for b in e.bullets]
    tailored_text_bullets = [b for e in result.tailored.experience for b in e.bullets]
    text_changed = improved_text_bullets != tailored_text_bullets
    delta = ats.score_after - ats.score_before
    if delta > 0 or text_changed:
        status = "IMPROVED"
    else:
        status = "NO_CHANGE"
    return {
        "success": True,
        "mode": mode,
        "scores": {
            "before": ats.score_before,
            "after": ats.score_after,
            "improvement": ats.improvement,
            "semantic": ats.semantic_score,
        },
        "status": status,
        "decision": ats.decision,
        "effort": ats.effort_level,
        "matched_skills": ats.matched_skills,
        "missing_skills": ats.missing_skills,
        "recommendations": ats.recommendations,
        "risk_flags": ats.risk_flags,
        "readability": result.readability,
        "breakdown_before": ats.breakdown_before.model_dump(),
        "breakdown_after": ats.breakdown_after.model_dump(),
        "improved_resume_json": result.improved.model_dump(),
        "tailored_resume_json": result.tailored.model_dump(),
        "jd_info": {
            "title": result.extracted_jd.job_title,
            "company": result.extracted_jd.company,
            "required_skills": result.extracted_jd.required_skills,
            "keywords": result.extracted_jd.keywords,
        },
        # canonical shortlist (the ONLY display values)
        "shortlist_probability": result.shortlist_probability,
        "shortlist_band": result.shortlist_band,
        "shortlist_decision": result.shortlist_decision,
        "shortlist_decision_reason": result.shortlist_decision_reason,
        "pipeline_result": result,
        "pipeline_trace": result.pipeline_trace,
        "pipeline_hash": result.pipeline_hash,
        "validation_result": result.validation_result,
        "change_explanation": result.change_explanation,
    }
