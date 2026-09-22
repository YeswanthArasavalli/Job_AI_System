"""
app_db_patch.py

Drop-in patch to wire app.py analysis results to the database
instead of job_history.json.

HOW TO APPLY:
  In app.py, replace the add_to_history() call at the bottom of main()
  with save_analysis_to_db(). Also replace load_job_history() / save_job_history()
  calls in the sidebar with the db-backed versions.

  Or import this module in app.py and call the functions directly.

  This patch does NOT change the analysis logic — it only changes persistence.
"""

import json
import os
from datetime import datetime
from typing import Optional

from database.db_manager_v2 import DatabaseManager
from utils.logger import setup_logger

logger = setup_logger(__name__)

_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "job_ai_system.db")
_db: Optional[DatabaseManager] = None


def _get_db() -> DatabaseManager:
    """Lazy singleton DB connection."""
    global _db
    if _db is None:
        _db = DatabaseManager(_DB_PATH)
    return _db


# ================================================================
# DROP-IN REPLACEMENTS for app.py's JSON functions
# ================================================================

def load_job_history():
    """
    Replacement for app.py load_job_history().
    Reads from database instead of job_history.json.
    Returns same list-of-dicts format for UI compatibility.
    """
    try:
        db = _get_db()
        results = db.list_analysis_results(limit=200)
        # Convert to the format app.py sidebar expects:
        # {company, role, decision, market_rank, ats_score, mode, status, date}
        return [
            {
                "id": r["id"],
                "company": r["company"],
                "role": r["role"],
                "decision": r["decision"],
                "market_rank": _prob_to_market_rank(r.get("shortlist_probability", 0)),
                "ats_score": r.get("ats_score_after", 0),
                "mode": r.get("optimization_mode", "balanced"),
                "status": r.get("application_status", "saved"),
                "date": r.get("created_at", ""),
                # Extended fields (not shown by old UI but available)
                "shortlist_probability": r.get("shortlist_probability", 0),
                "shortlist_band": r.get("shortlist_band", ""),
            }
            for r in results
        ]
    except Exception as e:
        logger.error(f"load_job_history from db failed: {e}")
        # Fallback to JSON if DB fails
        return _load_json_history()


def save_analysis_to_db(
    company: str,
    role: str,
    decision: str,
    result: dict,
    jd: object,
    original_resume: object,
    improved_resume: object,
    mode: str,
) -> Optional[int]:
    """
    Replacement for app.py add_to_history().
    Saves full analysis result to database.
    Returns the new analysis_id (use for status updates).

    Args:
        company, role, decision: Basic job info
        result: The full result dict from run_analysis()
        jd: ExtractedJD object
        original_resume: StructuredResume (before optimization)
        improved_resume: StructuredResume (after optimization)
        mode: optimization mode
    """
    try:
        db = _get_db()
        pipeline_result = result.get("pipeline_result")

        analysis = {
            "company": company,
            "role": role,
            "location": getattr(jd, "location", ""),
            "source_platform": "manual",
            "jd_text": getattr(jd, "raw_text", ""),
            "ats_score_before": result.get("score_before", 0),
            "ats_score_after": result.get("score_after", 0),
            "shortlist_probability": result.get("shortlist_probability") or 0,
            "shortlist_band": getattr(pipeline_result, "shortlist_band", ""),
            "decision": decision,
            "decision_reason": getattr(pipeline_result, "decision_reason", ""),
            "recruiter_score": _extract_recruiter_score(result),
            "original_resume_json": original_resume.model_dump_json() if original_resume else "",
            "optimized_resume_json": improved_resume.model_dump_json() if improved_resume else "",
            "rewrite_summary": _build_rewrite_summary(result),
            "missing_skills": result.get("missing_skills", []),
            "matched_skills": result.get("matched_skills", []),
            "optimization_mode": mode,
            "analysis_hash": getattr(pipeline_result, "pipeline_hash", ""),
        }

        analysis_id = db.save_analysis_result(analysis)
        logger.info(f"Analysis saved to DB: id={analysis_id} {company} — {role}")
        return analysis_id

    except Exception as e:
        logger.error(f"save_analysis_to_db failed: {e}")
        # Fallback: save to JSON so we don't lose data
        _save_json_history_fallback(company, role, decision, result, mode)
        return None


def update_application_status_in_db(analysis_id: int, new_status: str, note: str = "") -> bool:
    """
    Update application lifecycle status in DB.
    Called when user changes status in the UI sidebar.
    """
    try:
        db = _get_db()
        db.update_application_status(analysis_id, new_status, note)
        return True
    except Exception as e:
        logger.error(f"update_application_status_in_db failed: {e}")
        return False


def get_analytics_summary() -> dict:
    """Get aggregate analytics for sidebar performance display."""
    try:
        return _get_db().get_analytics_summary()
    except Exception as e:
        logger.error(f"get_analytics_summary failed: {e}")
        return {
            "total_analyses": 0, "total_applied": 0,
            "shortlisted": 0, "rejected": 0,
            "shortlist_rate": 0, "avg_ats_score": 0,
            "avg_shortlist_probability": 0,
        }


# ================================================================
# HELPERS
# ================================================================

def _prob_to_market_rank(prob: float) -> str:
    """Convert shortlist probability to market rank label."""
    if prob >= 55:
        return "TOP_10"
    elif prob >= 35:
        return "TOP_25"
    elif prob >= 18:
        return "AVERAGE"
    else:
        return "BELOW"


def _extract_recruiter_score(result: dict) -> float:
    """Extract recruiter layer score from hiring simulation."""
    hiring_sim = result.get("hiring_simulation", {})
    if isinstance(hiring_sim, dict):
        return hiring_sim.get("layers", {}).get("recruiter", {}).get("score", 0)
    return 0


def _build_rewrite_summary(result: dict) -> str:
    """Build a short rewrite summary from diffs."""
    diffs = result.get("diffs", [])
    if not diffs:
        return "No bullets rewritten"
    return f"{len(diffs)} bullet(s) improved; ATS delta: +{result.get('delta', 0):.0f} pts"


# ================================================================
# JSON FALLBACKS (if DB fails)
# ================================================================

_JSON_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "data", "job_history.json")


def _load_json_history():
    if os.path.exists(_JSON_HISTORY_FILE):
        try:
            with open(_JSON_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_json_history_fallback(company, role, decision, result, mode):
    history = _load_json_history()
    history.append({
        "company": company, "role": role, "decision": decision,
        "market_rank": result.get("market_rank", "BELOW"),
        "ats_score": round(result.get("score_after", 0), 1),
        "mode": mode, "status": "saved",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    os.makedirs(os.path.dirname(_JSON_HISTORY_FILE), exist_ok=True)
    with open(_JSON_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
