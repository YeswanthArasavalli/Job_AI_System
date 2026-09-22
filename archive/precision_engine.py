"""
Precision Optimization Engine — Calibration + Discipline + Capability Acceleration.

Addresses the core system weakness: low precision (~40%).
Strategy: predict FEWER but MORE ACCURATE opportunities.

Components:
  1. Precision Correction — stricter gating to reduce false positives
  2. Confidence Calibration — probability * precision_factor
  3. Hard Stop Mode — block roles with repeated CANDIDATE_GAP rejections
  4. Capability Acceleration — actionable upgrade plans (not generic advice)
  5. Decisive Strategy — STOP/FOCUS/USE/AVOID (not passive insights)
  6. Variant Validation — only with sufficient data
  7. Root Cause Reinforcement — outcome-validated

RULES:
  - DO NOT overestimate probability
  - ALWAYS penalize candidate gap
  - ALWAYS enforce discipline
  - DO NOT allow repeated failed applications
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# Thresholds
MIN_VARIANT_DATA = 20
HARD_STOP_THRESHOLD = 3
DEFAULT_PRECISION_FACTOR = 0.6


# ================================================================
# PART 1 — PRECISION CORRECTION ENGINE
# ================================================================

def correct_precision(
    raw_probability: float,
    prediction_level: str,
    root_cause: str,
    confidence_score: float = 50,
) -> Dict:
    """
    Apply stricter gating to reduce false positives.
    
    Rules:
      - If raw_probability < 65: downgrade HIGH → MEDIUM
      - If root_cause == CANDIDATE_GAP: cap at 60%
      - If confidence_score < 40: apply 20% penalty
    """
    adjusted = raw_probability
    adjusted_level = prediction_level
    adjustments = []
    
    # Rule 1: Downgrade HIGH if below 65%
    if prediction_level == "HIGH" and raw_probability < 65:
        adjusted_level = "MEDIUM"
        adjustments.append({
            "rule": "HIGH_DOWNGRADE",
            "reason": f"Probability {raw_probability:.0f}% is below 65% threshold for HIGH",
            "change": "HIGH → MEDIUM",
        })
    
    # Rule 2: Cap probability for CANDIDATE_GAP
    if root_cause == "CANDIDATE_GAP":
        cap = 60
        if adjusted > cap:
            adjustments.append({
                "rule": "GAP_CAP",
                "reason": f"Candidate gap detected — capped from {adjusted:.0f}% to {cap}%",
                "change": f"{adjusted:.0f}% → {cap}%",
            })
            adjusted = min(adjusted, cap)
    
    # Rule 3: Low confidence penalty
    if confidence_score < 40:
        penalty = adjusted * 0.20
        adjusted = adjusted - penalty
        adjustments.append({
            "rule": "LOW_CONFIDENCE",
            "reason": f"Confidence {confidence_score:.0f}% is low — applied 20% penalty",
            "change": f"-{penalty:.0f}%",
        })
    
    return {
        "raw_probability": round(raw_probability, 1),
        "adjusted_probability": round(adjusted, 1),
        "raw_level": prediction_level,
        "adjusted_level": adjusted_level,
        "adjustments": adjustments,
        "was_corrected": len(adjustments) > 0,
    }


# ================================================================
# PART 2 — CONFIDENCE CALIBRATION
# ================================================================

def calibrate_confidence(
    raw_probability: float,
    history: List[Dict],
) -> Dict:
    """
    Calibrate probability using historical precision.
    
    calibrated = raw_probability * precision_factor
    
    Where precision_factor is computed from actual outcomes.
    """
    # Compute precision from history
    resolved = [h for h in history if h.get("status") in ("shortlisted", "rejected")]
    
    if len(resolved) < 5:
        precision_factor = DEFAULT_PRECISION_FACTOR
        source = "default"
    else:
        # Count how many HIGH predictions were actually shortlisted
        high_predicted = [h for h in resolved if h.get("ats_score", 0) >= 70]
        high_correct = [h for h in high_predicted if h["status"] == "shortlisted"]
        
        if high_predicted:
            precision_factor = len(high_correct) / len(high_predicted)
            # Floor at 0.3 to avoid zeroing out
            precision_factor = max(precision_factor, 0.3)
        else:
            precision_factor = DEFAULT_PRECISION_FACTOR
        source = f"computed from {len(resolved)} outcomes"
    
    calibrated = raw_probability * precision_factor
    
    return {
        "raw_probability": round(raw_probability, 1),
        "calibrated_probability": round(calibrated, 1),
        "precision_factor": round(precision_factor, 2),
        "precision_source": source,
        "interpretation": (
            f"System precision is {precision_factor:.0%} — "
            f"your real chance is ~{calibrated:.0f}% (not {raw_probability:.0f}%)"
        ),
    }


# ================================================================
# PART 3 — HARD STOP MODE
# ================================================================

def check_hard_stop(
    role: str,
    root_cause: str,
    history: List[Dict],
) -> Dict:
    """
    Enforce hard stop for roles with repeated CANDIDATE_GAP rejections.
    
    Triggers if:
      - consecutive_rejections >= 3 for this role type
      - AND root_cause == CANDIDATE_GAP
    """
    role_lower = role.lower().strip()
    
    # Count consecutive rejections for this role type
    consecutive = 0
    for h in reversed(history):
        h_role = (h.get("role") or "").lower().strip()
        # Match role by keyword overlap
        if _role_matches(h_role, role_lower):
            if h.get("status") == "rejected":
                consecutive += 1
            elif h.get("status") == "shortlisted":
                break  # streak broken
        # Don't count pending applications
    
    is_blocked = consecutive >= HARD_STOP_THRESHOLD and root_cause == "CANDIDATE_GAP"
    
    if is_blocked:
        return {
            "blocked": True,
            "status": "HARD_STOP",
            "emoji": "🚫",
            "consecutive_rejections": consecutive,
            "message": (
                f"Hard Stop Activated — {consecutive} consecutive rejections "
                f"for '{role}' roles due to capability gap. "
                f"Further applications to this role are blocked until you "
                f"complete the capability upgrade plan below."
            ),
            "unlock_condition": "Complete at least 1 project + learn 2 missing skills",
        }
    elif consecutive >= 2 and root_cause == "CANDIDATE_GAP":
        return {
            "blocked": False,
            "status": "NEAR_STOP",
            "emoji": "⚠️",
            "consecutive_rejections": consecutive,
            "message": (
                f"Warning: {consecutive}/{HARD_STOP_THRESHOLD} rejections for '{role}'. "
                f"One more rejection will trigger Hard Stop."
            ),
            "unlock_condition": None,
        }
    else:
        return {
            "blocked": False,
            "status": "CLEAR",
            "emoji": "✅",
            "consecutive_rejections": consecutive,
            "message": f"No blocking issues for '{role}'.",
            "unlock_condition": None,
        }


def _role_matches(role_a: str, role_b: str) -> bool:
    """Check if two role strings are semantically similar."""
    if not role_a or not role_b:
        return False
    
    # Normalize
    keywords_a = set(role_a.replace("-", " ").split())
    keywords_b = set(role_b.replace("-", " ").split())
    
    # Remove common filler words
    fillers = {"senior", "junior", "lead", "staff", "principal", "ii", "iii", "intern"}
    keywords_a -= fillers
    keywords_b -= fillers
    
    if not keywords_a or not keywords_b:
        return role_a == role_b
    
    overlap = keywords_a & keywords_b
    return len(overlap) >= 1


# ================================================================
# PART 4 — CAPABILITY ACCELERATION ENGINE
# ================================================================

def generate_acceleration_plan(
    root_cause: str,
    missing_skills: List[str],
    role: str,
    domain: str = "data",
) -> Dict:
    """
    Generate SPECIFIC, ACTIONABLE capability upgrade plan.
    
    NOT generic advice — each step is concrete and measurable.
    """
    if root_cause != "CANDIDATE_GAP":
        return {
            "type": root_cause,
            "applicable": False,
            "message": f"Root cause is {root_cause} — capability acceleration not the primary fix.",
            "steps": [],
        }
    
    # Domain-specific project templates
    project_templates = {
        "data": {
            "type": "End-to-End Data Pipeline",
            "description": (
                "Build a complete data pipeline that ingests real data, "
                "transforms it, stores it, and produces a dashboard or model output"
            ),
            "example": "COVID data pipeline → PostgreSQL → Tableau dashboard with daily refresh",
            "skills_demonstrated": ["ETL", "SQL", "Data Modeling", "Visualization"],
        },
        "software": {
            "type": "Production API + Frontend",
            "description": (
                "Build a REST API with authentication, connected to a database, "
                "with a simple frontend consuming the API"
            ),
            "example": "Task management API (FastAPI + PostgreSQL + React frontend)",
            "skills_demonstrated": ["REST APIs", "Database Design", "Frontend", "Deployment"],
        },
        "ml": {
            "type": "ML Model → Production",
            "description": (
                "Train a model on real data, evaluate properly, "
                "deploy as API endpoint with monitoring"
            ),
            "example": "Sentiment classifier → FastAPI → Docker → AWS deployment",
            "skills_demonstrated": ["ML", "Model Evaluation", "API", "Deployment"],
        },
    }
    
    # Select template
    domain_key = "data"
    if any(k in domain.lower() for k in ["software", "backend", "frontend", "web"]):
        domain_key = "software"
    elif any(k in domain.lower() for k in ["ml", "machine", "deep", "ai"]):
        domain_key = "ml"
    
    template = project_templates.get(domain_key, project_templates["data"])
    
    # Build steps
    steps = []
    
    # Step 1: Build project
    steps.append({
        "action": "BUILD",
        "title": f"Build 1 {template['type']} project",
        "detail": template["description"],
        "example": template["example"],
        "outcome": "Publishable on GitHub with README + demo",
        "timeline": "1-2 weeks",
    })
    
    # Step 2: Learn missing skills
    top_skills = missing_skills[:3] if missing_skills else ["See JD requirements"]
    steps.append({
        "action": "LEARN",
        "title": f"Learn: {', '.join(top_skills)}",
        "detail": (
            f"Hands-on tutorials (NOT courses). "
            f"Build something with each skill. "
            f"Document what you built."
        ),
        "example": f"Complete 1 mini-project per skill using {', '.join(top_skills[:2])}",
        "outcome": "Working code demonstrating each skill",
        "timeline": "1 week per skill",
    })
    
    # Step 3: Prove with measurable output
    steps.append({
        "action": "PROVE",
        "title": "Create measurable proof of capability",
        "detail": (
            f"Your project must show: quantified results, "
            f"clean code, documentation, and real-world applicability"
        ),
        "example": "README with: problem → approach → results (with numbers)",
        "outcome": "Portfolio-ready project with metrics",
        "timeline": "2-3 days (polish phase)",
    })
    
    # Step 4: Update resume
    steps.append({
        "action": "UPDATE",
        "title": "Update resume bullets to reflect new capabilities",
        "detail": (
            f"Add project as new experience entry with quantified outcomes. "
            f"Incorporate newly learned skills into skills section."
        ),
        "example": f"'Built {template['type'].lower()} processing X records with Y% accuracy'",
        "outcome": "Resume reflects genuine new capabilities",
        "timeline": "1 day",
    })
    
    # Total timeline
    total_weeks = 2 + len(top_skills)
    
    return {
        "type": "CAPABILITY_ACCELERATION",
        "applicable": True,
        "role_targeted": role,
        "domain": domain_key,
        "missing_skills": top_skills,
        "steps": steps,
        "total_timeline": f"{total_weeks}-{total_weeks + 2} weeks",
        "message": (
            f"To reach shortlist level for '{role}', you must complete "
            f"{len(steps)} steps over {total_weeks}-{total_weeks + 2} weeks. "
            f"This is a real investment — but it converts CANDIDATE_GAP "
            f"into genuine qualification."
        ),
    }


# ================================================================
# PART 5 — DECISIVE STRATEGY ENGINE
# ================================================================

def generate_decisive_strategy(history: List[Dict]) -> Dict:
    """
    Generate DECISIVE actions — STOP/FOCUS/USE/AVOID.
    
    Not passive insights. Concrete directives.
    """
    if len(history) < 5:
        return {
            "stop": [],
            "focus": [],
            "use": "balanced",
            "avoid": [],
            "summary": "Build more application data before strategy optimization.",
        }
    
    # STOP: roles with 3+ rejections and 0 shortlists
    role_stats = {}
    for h in history:
        role = h.get("role", "unknown")
        if role not in role_stats:
            role_stats[role] = {"total": 0, "shortlisted": 0, "rejected": 0}
        role_stats[role]["total"] += 1
        if h.get("status") == "shortlisted":
            role_stats[role]["shortlisted"] += 1
        elif h.get("status") == "rejected":
            role_stats[role]["rejected"] += 1
    
    stop = []
    focus = []
    
    for role, stats in role_stats.items():
        if stats["rejected"] >= 3 and stats["shortlisted"] == 0:
            stop.append({
                "role": role,
                "rejections": stats["rejected"],
                "reason": f"{stats['rejected']} rejections, 0 shortlists — systematic mismatch",
            })
        elif stats["shortlisted"] > 0:
            rate = stats["shortlisted"] / stats["total"] * 100
            focus.append({
                "role": role,
                "success_rate": round(rate, 0),
                "shortlists": stats["shortlisted"],
                "reason": f"{rate:.0f}% success rate — proven fit",
            })
    
    # Sort focus by success rate
    focus.sort(key=lambda x: x["success_rate"], reverse=True)
    
    # USE: best variant
    mode_stats = {}
    for h in history:
        mode = h.get("mode", "strict")
        if mode not in mode_stats:
            mode_stats[mode] = {"total": 0, "shortlisted": 0}
        mode_stats[mode]["total"] += 1
        if h.get("status") == "shortlisted":
            mode_stats[mode]["shortlisted"] += 1
    
    best_mode = "balanced"
    best_rate = 0
    for mode, stats in mode_stats.items():
        if stats["total"] >= 3:
            rate = stats["shortlisted"] / stats["total"] * 100
            if rate > best_rate:
                best_rate = rate
                best_mode = mode
    
    # AVOID: patterns from recent failures
    avoid = []
    recent_rejected = [h for h in history[-10:] if h.get("status") == "rejected"]
    
    if len(recent_rejected) >= 5:
        low_score_apps = [h for h in recent_rejected if h.get("ats_score", 0) < 55]
        if len(low_score_apps) >= 3:
            avoid.append({
                "pattern": "Applying to low-match jobs (ATS < 55)",
                "count": len(low_score_apps),
                "reason": "These are time wasters — skip them",
            })
    
    return {
        "stop": stop[:3],
        "focus": focus[:3],
        "use": best_mode,
        "use_rate": round(best_rate, 0),
        "avoid": avoid[:3],
        "summary": (
            f"STOP: {len(stop)} role types. "
            f"FOCUS: {len(focus)} proven roles. "
            f"USE: '{best_mode}' mode ({best_rate:.0f}% success)."
        ),
    }


# ================================================================
# PART 6 — VARIANT PERFORMANCE VALIDATION
# ================================================================

def validate_variant_performance(history: List[Dict]) -> Dict:
    """
    Validate variant performance ONLY with sufficient data.
    
    Requires >= MIN_VARIANT_DATA total applications.
    """
    total = len(history)
    
    if total < MIN_VARIANT_DATA:
        return {
            "sufficient_data": False,
            "total_applications": total,
            "required": MIN_VARIANT_DATA,
            "message": f"Need {MIN_VARIANT_DATA - total} more applications for variant analysis.",
            "best_variant": None,
            "worst_variant": None,
            "confidence": "none",
        }
    
    # Compute per-variant stats
    variants = {}
    for h in history:
        mode = h.get("mode", "strict")
        if mode not in variants:
            variants[mode] = {"total": 0, "shortlisted": 0, "rejected": 0}
        variants[mode]["total"] += 1
        if h.get("status") == "shortlisted":
            variants[mode]["shortlisted"] += 1
        elif h.get("status") == "rejected":
            variants[mode]["rejected"] += 1
    
    # Compute rates
    variant_rates = {}
    for mode, stats in variants.items():
        resolved = stats["shortlisted"] + stats["rejected"]
        rate = (stats["shortlisted"] / resolved * 100) if resolved > 0 else 0
        variant_rates[mode] = {
            "total": stats["total"],
            "shortlisted": stats["shortlisted"],
            "rejected": stats["rejected"],
            "rate": round(rate, 1),
        }
    
    # Find best/worst
    sorted_variants = sorted(variant_rates.items(), key=lambda x: x[1]["rate"], reverse=True)
    best = sorted_variants[0] if sorted_variants else (None, {})
    worst = sorted_variants[-1] if len(sorted_variants) > 1 else (None, {})
    
    # Confidence based on data volume
    min_per_variant = min(v["total"] for v in variant_rates.values()) if variant_rates else 0
    confidence = (
        "high" if min_per_variant >= 10
        else "moderate" if min_per_variant >= 5
        else "low"
    )
    
    return {
        "sufficient_data": True,
        "total_applications": total,
        "variants": variant_rates,
        "best_variant": best[0],
        "best_rate": best[1].get("rate", 0),
        "worst_variant": worst[0],
        "worst_rate": worst[1].get("rate", 0),
        "confidence": confidence,
        "message": (
            f"Best: '{best[0]}' ({best[1].get('rate', 0)}%), "
            f"Worst: '{worst[0]}' ({worst[1].get('rate', 0)}%). "
            f"Confidence: {confidence}."
        ),
    }


# ================================================================
# PART 7 — ROOT CAUSE REINFORCEMENT
# ================================================================

def reinforce_root_cause(
    predicted_cause: str,
    history: List[Dict],
) -> Dict:
    """
    Validate/reinforce root cause using REAL outcomes.
    
    Rules:
      - Repeated HIGH → rejected → confirms CANDIDATE_GAP
      - Consistent LOW → rejected → confirms targeting correctness
      - Mixed results → RESUME_GAP likely
    """
    resolved = [h for h in history if h.get("status") in ("shortlisted", "rejected")]
    
    if len(resolved) < 5:
        return {
            "validated": False,
            "predicted_cause": predicted_cause,
            "reinforced_cause": predicted_cause,
            "confidence": 0,
            "message": "Insufficient data — using predicted root cause.",
        }
    
    high_rejected = len([h for h in resolved if h.get("ats_score", 0) >= 70 and h["status"] == "rejected"])
    high_total = len([h for h in resolved if h.get("ats_score", 0) >= 70])
    total_shortlisted = len([h for h in resolved if h["status"] == "shortlisted"])
    shortlist_rate = total_shortlisted / len(resolved) * 100
    
    # Determine reinforced cause
    if high_rejected >= 3 and high_total >= 4:
        reinforced = "CANDIDATE_GAP"
        confidence = 90
        evidence = f"{high_rejected}/{high_total} high-score apps rejected — skills don't match"
    elif shortlist_rate == 0 and len(resolved) >= 8:
        reinforced = "CANDIDATE_GAP"
        confidence = 95
        evidence = f"0/{len(resolved)} shortlisted — fundamental capability issue"
    elif 0 < shortlist_rate < 8:
        reinforced = "RESUME_GAP"
        confidence = 70
        evidence = f"Low but non-zero success ({shortlist_rate:.0f}%) — resume optimization can help"
    elif shortlist_rate >= 8:
        reinforced = "TARGETING_GAP" if shortlist_rate < 15 else "NONE"
        confidence = 60
        evidence = f"Decent success ({shortlist_rate:.0f}%) — refine targeting for better results"
    else:
        reinforced = predicted_cause
        confidence = 50
        evidence = "Mixed signals — maintaining predicted cause"
    
    # Check if reinforcement agrees with prediction
    agrees = reinforced == predicted_cause
    
    return {
        "validated": True,
        "predicted_cause": predicted_cause,
        "reinforced_cause": reinforced,
        "agrees_with_prediction": agrees,
        "confidence": confidence,
        "evidence": evidence,
        "message": (
            f"Root cause {'CONFIRMED' if agrees else 'CORRECTED'}: "
            f"{reinforced} (confidence: {confidence}%)"
        ),
    }


# ================================================================
# v3.5 — DYNAMIC PRECISION FACTOR
# ================================================================

def compute_dynamic_precision(history: List[Dict], window: int = 20) -> Dict:
    """
    Rolling precision factor from last N resolved HIGH predictions.
    Bounded: max(0.4, min(0.75, rolling_precision)).
    """
    resolved = [h for h in history if h.get("status") in ("shortlisted", "rejected")]
    recent = resolved[-window:] if len(resolved) > window else resolved

    if len(recent) < 5:
        return {"factor": DEFAULT_PRECISION_FACTOR, "source": "default", "window": 0}

    high = [h for h in recent if h.get("ats_score", 0) >= 70]
    if not high:
        return {"factor": DEFAULT_PRECISION_FACTOR, "source": "no_high", "window": len(recent)}

    correct = len([h for h in high if h["status"] == "shortlisted"])
    raw = correct / len(high)
    bounded = max(0.4, min(0.75, raw))

    return {
        "factor": round(bounded, 2),
        "raw": round(raw, 2),
        "source": f"rolling_{len(recent)}",
        "window": len(recent),
        "high_count": len(high),
        "high_correct": correct,
    }


# ================================================================
# v3.5 — SOFT CALIBRATION ENGINE
# ================================================================

def soft_calibrate(raw_probability: float, precision_factor: float, root_cause: str) -> Dict:
    """
    Soft calibration: preserves borderline opportunities.
    HIGH signals (>70) use strict factor; borderline gets +0.1 boost.
    Gap-aware: CANDIDATE_GAP capped at 60.
    """
    if raw_probability > 70:
        calibrated = raw_probability * precision_factor
        method = "strict"
    else:
        calibrated = raw_probability * min(precision_factor + 0.1, 0.85)
        method = "soft_boost"

    if root_cause == "CANDIDATE_GAP":
        calibrated = min(calibrated, 60)
        method += "+gap_cap"

    return {
        "raw": round(raw_probability, 1),
        "calibrated": round(calibrated, 1),
        "precision_factor": precision_factor,
        "method": method,
    }


# ================================================================
# v3.5 — RECOVERY MODE
# ================================================================

def check_recovery(
    role: str,
    hard_stop: Dict,
    user_progress: Dict = None,
) -> Dict:
    """
    Allow re-entry into blocked roles after capability improvement.
    Downgrades HARD_STOP → WARNING if progress detected.
    """
    user_progress = user_progress or {}
    skills = user_progress.get("skills_learned", [])
    projects = user_progress.get("projects_completed", [])

    has_progress = len(skills) >= 2 or len(projects) >= 1

    if not hard_stop.get("blocked"):
        return {
            "recovery_active": False,
            "status": hard_stop.get("status", "CLEAR"),
            "message": hard_stop.get("message", ""),
        }

    if has_progress:
        evidence = []
        if skills:
            evidence.append(f"Skills: {', '.join(skills[:3])}")
        if projects:
            evidence.append(f"Projects: {', '.join(projects[:2])}")

        return {
            "recovery_active": True,
            "status": "RECOVERY",
            "emoji": "🔓",
            "original_status": "HARD_STOP",
            "message": (
                f"Recovery Mode — Hard Stop downgraded to Warning. "
                f"Progress detected: {'; '.join(evidence)}. "
                f"You may apply with caution."
            ),
            "evidence": evidence,
        }

    return {
        "recovery_active": False,
        "status": "HARD_STOP",
        "emoji": "🚫",
        "message": hard_stop["message"],
    }


# ================================================================
# v3.5 — PERSONALIZED THRESHOLDS
# ================================================================

def compute_personalized_thresholds(history: List[Dict]) -> Dict:
    """
    Adapt decision thresholds based on user's track record.
    Improving users get slightly looser gates; declining users get tighter.
    """
    resolved = [h for h in history if h.get("status") in ("shortlisted", "rejected")]

    if len(resolved) < 8:
        return {"block": 40, "warn": 55, "allow": 55, "adjustment": "default"}

    mid = len(resolved) // 2
    first_rate = sum(1 for h in resolved[:mid] if h["status"] == "shortlisted") / mid * 100
    second_rate = sum(1 for h in resolved[mid:] if h["status"] == "shortlisted") / (len(resolved) - mid) * 100

    if second_rate > first_rate + 3:
        return {"block": 35, "warn": 50, "allow": 50, "adjustment": "relaxed"}
    elif second_rate < first_rate - 3:
        return {"block": 45, "warn": 60, "allow": 60, "adjustment": "tightened"}
    return {"block": 40, "warn": 55, "allow": 55, "adjustment": "default"}


# ================================================================
# MASTER ORCHESTRATOR (v3.5)
# ================================================================

def run_precision_optimization(
    raw_probability: float,
    prediction_level: str,
    root_cause: str,
    role: str,
    confidence_score: float = 50,
    missing_skills: List[str] = None,
    domain: str = "data",
    history: List[Dict] = None,
    user_progress: Dict = None,
) -> Dict:
    """
    Run the complete precision + dynamic calibration cycle (v3.5).
    """
    history = history or []
    missing_skills = missing_skills or []
    user_progress = user_progress or {}

    # Part 1: Precision correction (static rules)
    correction = correct_precision(
        raw_probability, prediction_level, root_cause, confidence_score
    )

    # v3.5: Dynamic precision factor
    dynamic = compute_dynamic_precision(history)

    # v3.5: Soft calibration (replaces static calibrate_confidence)
    calibration = soft_calibrate(
        correction["adjusted_probability"], dynamic["factor"], root_cause
    )

    # Part 3: Hard stop check
    hard_stop = check_hard_stop(role, root_cause, history)

    # v3.5: Recovery mode
    recovery = check_recovery(role, hard_stop, user_progress)

    # v3.5: Personalized thresholds
    thresholds = compute_personalized_thresholds(history)

    # Part 4-7: existing engines
    acceleration = generate_acceleration_plan(root_cause, missing_skills, role, domain)
    strategy = generate_decisive_strategy(history)
    variant_validation = validate_variant_performance(history)
    reinforcement = reinforce_root_cause(root_cause, history)

    # Final decision using personalized thresholds + recovery
    final_prob = calibration["calibrated"]
    is_blocked = hard_stop["blocked"] and not recovery["recovery_active"]

    if is_blocked:
        app_decision, app_emoji = "BLOCKED", "🚫"
        app_reason = hard_stop["message"]
    elif recovery["recovery_active"]:
        app_decision, app_emoji = "WARNING", "🔓"
        app_reason = recovery["message"]
    elif final_prob < thresholds["block"]:
        app_decision, app_emoji = "BLOCKED", "🚫"
        app_reason = f"Calibrated probability ({final_prob:.0f}%) below {thresholds['block']}% threshold."
    elif final_prob < thresholds["warn"]:
        app_decision, app_emoji = "WARNING", "⚠️"
        app_reason = f"Calibrated probability ({final_prob:.0f}%) — fix gaps first."
    else:
        app_decision, app_emoji = "ALLOWED", "✅"
        app_reason = f"Calibrated probability ({final_prob:.0f}%) — good to apply."

    return {
        "precision_correction": correction,
        "dynamic_precision": dynamic,
        "confidence_calibration": {
            "raw_probability": calibration["raw"],
            "calibrated_probability": calibration["calibrated"],
            "precision_factor": dynamic["factor"],
            "precision_source": dynamic["source"],
            "method": calibration["method"],
            "interpretation": (
                f"Dynamic precision {dynamic['factor']:.0%} — "
                f"real chance ~{calibration['calibrated']:.0f}% (not {raw_probability:.0f}%)"
            ),
        },
        "hard_stop": hard_stop,
        "recovery": recovery,
        "personalized_thresholds": thresholds,
        "capability_acceleration": acceleration,
        "decisive_strategy": strategy,
        "variant_validation": variant_validation,
        "root_cause_reinforcement": reinforcement,
        "application_decision": {
            "decision": app_decision,
            "emoji": app_emoji,
            "reason": app_reason,
            "final_probability": round(final_prob, 1),
        },
        "summary": {
            "raw_probability": round(raw_probability, 1),
            "calibrated_probability": round(final_prob, 1),
            "precision_factor": dynamic["factor"],
            "decision": app_decision,
            "root_cause": reinforcement["reinforced_cause"],
            "hard_stop_active": is_blocked,
            "recovery_active": recovery["recovery_active"],
            "threshold_adjustment": thresholds["adjustment"],
        },
    }
