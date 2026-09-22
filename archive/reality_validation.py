"""
Reality Validation Engine — Prediction Verification + User Discipline + Self-Correction.

The FINAL TRUST LAYER that ensures:
  1. Predictions match reality (accuracy tracking)
  2. Users don't waste effort on low-probability jobs (discipline)
  3. System corrects itself when predictions drift (self-correction)
  4. No false confidence is ever shown (truthfulness)

RULES:
  - DO NOT allow blind applying
  - DO NOT show insights without sufficient data
  - DO NOT assume improvement without evidence
  - ALWAYS enforce discipline
"""

import re
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from utils.logger import setup_logger

logger = setup_logger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_PROGRESS_FILE = os.path.join(_DATA_DIR, "capability_progress.json")

# Minimum thresholds before showing insights
MIN_APPLICATIONS = 15
MIN_VARIANT_DATA = 20
MIN_RESOLVED = 5


# ================================================================
# PART 1 — PREDICTION VALIDATION ENGINE
# ================================================================

def validate_predictions(history: List[Dict]) -> Dict:
    """
    Compare predicted outcomes vs actual outcomes.
    
    Uses ATS score as the prediction signal:
      - Score >= 70 → predicted HIGH (shortlist)
      - Score 55-69 → predicted MEDIUM
      - Score < 55  → predicted LOW (reject)
    
    Returns confusion matrix + accuracy/precision/recall.
    """
    resolved = [
        h for h in history
        if h.get("status") in ("shortlisted", "rejected")
    ]
    
    if len(resolved) < 2:
        return {
            "sufficient_data": False,
            "total_resolved": len(resolved),
            "message": f"Need at least 2 resolved applications. You have {len(resolved)}.",
            "accuracy": None,
            "precision": None,
            "recall": None,
        }
    
    # Classify predictions
    true_pos = 0   # predicted HIGH, actually shortlisted
    false_pos = 0  # predicted HIGH, actually rejected
    true_neg = 0   # predicted LOW, actually rejected
    false_neg = 0  # predicted LOW, actually shortlisted
    
    high_total = 0
    high_shortlisted = 0
    low_total = 0
    low_rejected = 0
    
    mismatch_cases = []
    
    for h in resolved:
        score = h.get("ats_score", 50)
        actual = h.get("status")
        
        if score >= 70:
            predicted_level = "HIGH"
            high_total += 1
            if actual == "shortlisted":
                true_pos += 1
                high_shortlisted += 1
            else:
                false_pos += 1
                mismatch_cases.append({
                    "company": h.get("company", "?"),
                    "role": h.get("role", "?"),
                    "score": score,
                    "predicted": "HIGH",
                    "actual": "rejected",
                    "type": "over_prediction",
                    "insight": "System was too optimistic — likely competition or hidden gap",
                })
        elif score >= 55:
            predicted_level = "MEDIUM"
            if actual == "shortlisted":
                true_pos += 1
            else:
                true_neg += 1
        else:
            predicted_level = "LOW"
            low_total += 1
            if actual == "rejected":
                true_neg += 1
                low_rejected += 1
            else:
                false_neg += 1
                mismatch_cases.append({
                    "company": h.get("company", "?"),
                    "role": h.get("role", "?"),
                    "score": score,
                    "predicted": "LOW",
                    "actual": "shortlisted",
                    "type": "under_prediction",
                    "insight": "System underestimated — resume has strengths not captured by ATS score",
                })
    
    total = true_pos + false_pos + true_neg + false_neg
    accuracy = ((true_pos + true_neg) / total * 100) if total > 0 else 0
    precision = (true_pos / (true_pos + false_pos) * 100) if (true_pos + false_pos) > 0 else 0
    recall = (true_pos / (true_pos + false_neg) * 100) if (true_pos + false_neg) > 0 else 0
    
    high_conversion = (high_shortlisted / high_total * 100) if high_total > 0 else 0
    low_rejection_rate = (low_rejected / low_total * 100) if low_total > 0 else 0
    
    return {
        "sufficient_data": len(resolved) >= MIN_RESOLVED,
        "total_resolved": len(resolved),
        "accuracy": round(accuracy, 1),
        "precision": round(precision, 1),
        "recall": round(recall, 1),
        "confusion_matrix": {
            "true_positives": true_pos,
            "false_positives": false_pos,
            "true_negatives": true_neg,
            "false_negatives": false_neg,
        },
        "high_conversion_rate": round(high_conversion, 1),
        "low_rejection_rate": round(low_rejection_rate, 1),
        "high_total": high_total,
        "low_total": low_total,
        "mismatch_cases": mismatch_cases[:5],
        "message": (
            f"Accuracy: {accuracy:.0f}% across {len(resolved)} resolved applications."
            if len(resolved) >= MIN_RESOLVED
            else f"Collecting data: {len(resolved)}/{MIN_RESOLVED} resolved applications needed."
        ),
    }


# ================================================================
# PART 2 — PREDICTION vs REALITY ANALYSIS
# ================================================================

def analyze_prediction_reality_gap(validation: Dict) -> Dict:
    """
    Determine if predictions align with reality.
    
    Flags:
      - System inconsistency (HIGH predictions failing)
      - Under-prediction (LOW predictions succeeding)
      - Correction recommendations
    """
    if not validation.get("sufficient_data"):
        return {
            "alignment": "insufficient_data",
            "issues": [],
            "corrections": [],
            "summary": "Not enough data to assess prediction alignment.",
        }
    
    issues = []
    corrections = []
    
    high_rate = validation["high_conversion_rate"]
    low_rate = validation["low_rejection_rate"]
    accuracy = validation["accuracy"]
    
    # Issue 1: HIGH predictions not converting
    if high_rate < 30 and validation["high_total"] >= 3:
        issues.append({
            "type": "over_prediction",
            "severity": "HIGH",
            "detail": f"HIGH predictions only convert at {high_rate:.0f}% — system is too optimistic",
        })
        corrections.append({
            "action": "Raise HIGH threshold from 70 to 75",
            "reason": "Too many false positives in HIGH tier",
        })
    
    # Issue 2: LOW predictions not accurate
    if low_rate < 70 and validation["low_total"] >= 3:
        issues.append({
            "type": "under_prediction",
            "severity": "MEDIUM",
            "detail": f"LOW predictions only {low_rate:.0f}% accurate — missing hidden strengths",
        })
        corrections.append({
            "action": "Lower LOW threshold from 55 to 50",
            "reason": "System undervalues some resume strengths",
        })
    
    # Issue 3: Overall accuracy too low
    if accuracy < 50:
        issues.append({
            "type": "systemic",
            "severity": "HIGH",
            "detail": f"Overall accuracy {accuracy:.0f}% — predictions are unreliable",
        })
        corrections.append({
            "action": "Recalibrate scoring weights based on outcome data",
            "reason": "Fundamental scoring model needs adjustment",
        })
    
    # Determine alignment status
    if not issues:
        alignment = "aligned"
        summary = f"Predictions are well-aligned with reality (accuracy: {accuracy:.0f}%)."
    elif any(i["severity"] == "HIGH" for i in issues):
        alignment = "misaligned"
        summary = f"Significant prediction gaps detected. {len(issues)} issues to address."
    else:
        alignment = "minor_drift"
        summary = f"Minor prediction drift. {len(issues)} issues noted."
    
    return {
        "alignment": alignment,
        "issues": issues,
        "corrections": corrections,
        "summary": summary,
    }


# ================================================================
# PART 3 — HARD APPLICATION CONTROL
# ================================================================

def enforce_application_control(probability: float, history: List[Dict] = None) -> Dict:
    """
    Enforce strict application discipline.
    
    < 40%  → BLOCKED (waste of effort)
    40-60% → WARNING (fix gaps first)
    > 60%  → ALLOWED
    """
    history = history or []
    
    if probability < 40:
        return {
            "allowed": False,
            "status": "BLOCKED",
            "emoji": "🚫",
            "message": (
                f"Application blocked — {probability:.0f}% probability is too low. "
                f"This would waste your effort. Fix gaps first or target different roles."
            ),
            "severity": "critical",
        }
    elif probability < 60:
        # Check if user has been repeatedly applying to low-probability jobs
        recent_low = sum(
            1 for h in history[-10:]
            if h.get("ats_score", 0) < 60 and h.get("status") == "rejected"
        )
        
        extra_warning = ""
        if recent_low >= 3:
            extra_warning = (
                f" WARNING: {recent_low} of your last 10 applications were "
                f"low-probability and got rejected. Be more selective."
            )
        
        return {
            "allowed": True,
            "status": "WARNING",
            "emoji": "⚠️",
            "message": (
                f"Proceed with caution — {probability:.0f}% probability. "
                f"Fix identified gaps before applying.{extra_warning}"
            ),
            "severity": "warning",
        }
    else:
        return {
            "allowed": True,
            "status": "ALLOWED",
            "emoji": "✅",
            "message": f"Good to apply — {probability:.0f}% probability indicates strong fit.",
            "severity": "clear",
        }


# ================================================================
# PART 4+5 — DATA THRESHOLD GATES
# ================================================================

def check_data_thresholds(history: List[Dict]) -> Dict:
    """
    Check if there's enough data for reliable insights.
    
    Returns gate status for each insight type.
    """
    total = len(history)
    resolved = len([h for h in history if h.get("status") in ("shortlisted", "rejected")])
    
    # Count variant usage
    variant_counts = {}
    for h in history:
        mode = h.get("mode", "strict")
        variant_counts[mode] = variant_counts.get(mode, 0) + 1
    
    return {
        "total_applications": total,
        "resolved_applications": resolved,
        "prediction_insights": resolved >= MIN_RESOLVED,
        "variant_insights": total >= MIN_VARIANT_DATA,
        "weekly_insights": total >= 5,
        "trend_insights": resolved >= 8,
        "gates": {
            "prediction_accuracy": {
                "unlocked": resolved >= MIN_RESOLVED,
                "current": resolved,
                "required": MIN_RESOLVED,
                "message": (
                    "✅ Prediction accuracy available"
                    if resolved >= MIN_RESOLVED
                    else f"🔒 Need {MIN_RESOLVED - resolved} more resolved applications"
                ),
            },
            "variant_performance": {
                "unlocked": total >= MIN_VARIANT_DATA,
                "current": total,
                "required": MIN_VARIANT_DATA,
                "message": (
                    "✅ Variant analysis available"
                    if total >= MIN_VARIANT_DATA
                    else f"🔒 Need {MIN_VARIANT_DATA - total} more applications"
                ),
            },
            "trend_analysis": {
                "unlocked": resolved >= 8,
                "current": resolved,
                "required": 8,
                "message": (
                    "✅ Trend analysis available"
                    if resolved >= 8
                    else f"🔒 Need {8 - resolved} more resolved applications"
                ),
            },
        },
        "variant_counts": variant_counts,
    }


# ================================================================
# PART 6 — CAPABILITY PROGRESS TRACKER
# ================================================================

def track_capability_progress(
    history: List[Dict],
    user_progress: Dict = None,
) -> Dict:
    """
    Track whether the user is actually improving.
    
    Evaluates:
      - Score trend over time
      - New skills demonstrated in resumes
      - Match rate improvement
    
    user_progress (optional):
      - skills_learned: ["Docker", "Spark"]
      - projects_completed: ["ML Pipeline"]
      - certifications: ["AWS Certified"]
    """
    user_progress = user_progress or {}
    
    if len(history) < 5:
        return {
            "status": "insufficient_data",
            "improving": None,
            "score_trend": None,
            "evidence": [],
            "message": "Need at least 5 applications to assess progress.",
        }
    
    # Score trend: compare first half vs second half
    scores = [h.get("ats_score", 0) for h in history if h.get("ats_score")]
    
    if len(scores) >= 4:
        mid = len(scores) // 2
        first_half_avg = sum(scores[:mid]) / mid
        second_half_avg = sum(scores[mid:]) / (len(scores) - mid)
        score_delta = second_half_avg - first_half_avg
    else:
        first_half_avg = 0
        second_half_avg = 0
        score_delta = 0
    
    # Shortlist rate trend
    resolved = [h for h in history if h.get("status") in ("shortlisted", "rejected")]
    if len(resolved) >= 4:
        mid_r = len(resolved) // 2
        first_rate = sum(1 for h in resolved[:mid_r] if h["status"] == "shortlisted") / mid_r * 100
        second_rate = sum(1 for h in resolved[mid_r:] if h["status"] == "shortlisted") / (len(resolved) - mid_r) * 100
        rate_delta = second_rate - first_rate
    else:
        first_rate = 0
        second_rate = 0
        rate_delta = 0
    
    # Build evidence
    evidence = []
    
    if score_delta > 3:
        evidence.append(f"ATS scores improving: {first_half_avg:.0f} → {second_half_avg:.0f} (+{score_delta:.0f})")
    elif score_delta < -3:
        evidence.append(f"ATS scores declining: {first_half_avg:.0f} → {second_half_avg:.0f} ({score_delta:.0f})")
    
    if rate_delta > 0:
        evidence.append(f"Shortlist rate improving: {first_rate:.0f}% → {second_rate:.0f}%")
    elif rate_delta < 0 and first_rate > 0:
        evidence.append(f"Shortlist rate declining: {first_rate:.0f}% → {second_rate:.0f}%")
    
    # User-reported progress
    skills_learned = user_progress.get("skills_learned", [])
    projects = user_progress.get("projects_completed", [])
    
    if skills_learned:
        evidence.append(f"New skills added: {', '.join(skills_learned[:3])}")
    if projects:
        evidence.append(f"Projects completed: {', '.join(projects[:3])}")
    
    # Determine status
    improvement_signals = 0
    if score_delta > 3:
        improvement_signals += 1
    if rate_delta > 0:
        improvement_signals += 1
    if skills_learned:
        improvement_signals += 1
    if projects:
        improvement_signals += 1
    
    if improvement_signals >= 2:
        status = "improving"
        improving = True
        message = "✅ Capability improving — higher shortlist potential detected."
    elif improvement_signals == 1:
        status = "slight_improvement"
        improving = True
        message = "📈 Slight improvement detected. Keep building skills and projects."
    elif score_delta < -5 or rate_delta < -5:
        status = "declining"
        improving = False
        message = "⚠️ Performance declining — review targeting strategy and resume quality."
    else:
        status = "stagnant"
        improving = False
        message = "⚠️ No real improvement detected — candidate gap persists. Build new skills."
    
    return {
        "status": status,
        "improving": improving,
        "score_trend": {
            "first_half": round(first_half_avg, 1),
            "second_half": round(second_half_avg, 1),
            "delta": round(score_delta, 1),
        },
        "rate_trend": {
            "first_half": round(first_rate, 1),
            "second_half": round(second_rate, 1),
            "delta": round(rate_delta, 1),
        },
        "evidence": evidence,
        "message": message,
    }


# ================================================================
# PART 7 — MANDATORY ACTION ENGINE
# ================================================================

def generate_mandatory_actions(
    validation: Dict,
    reality_gap: Dict,
    capability: Dict,
    history: List[Dict],
) -> Dict:
    """
    Generate MANDATORY actions — not suggestions, requirements.
    
    Forces discipline in application strategy.
    """
    actions = []
    
    # Action 1: Stop applying to failing patterns
    rejected_roles = {}
    for h in history:
        if h.get("status") == "rejected":
            role = h.get("role", "unknown")
            rejected_roles[role] = rejected_roles.get(role, 0) + 1
    
    for role, count in rejected_roles.items():
        if count >= 3:
            actions.append({
                "type": "STOP",
                "priority": "CRITICAL",
                "action": f"Stop applying to '{role}' roles — {count} consecutive rejections",
                "reason": "Pattern indicates systematic mismatch",
            })
    
    # Action 2: Fix capability gap
    if capability.get("status") == "stagnant" and len(history) >= 10:
        actions.append({
            "type": "BUILD",
            "priority": "HIGH",
            "action": "Build 1 new project demonstrating missing skills before next application batch",
            "reason": "No improvement detected — resume changes alone won't help",
        })
    
    # Action 3: Use best variant
    modes = {}
    for h in history:
        if h.get("status") == "shortlisted":
            mode = h.get("mode", "strict")
            modes[mode] = modes.get(mode, 0) + 1
    
    if modes:
        best_mode = max(modes, key=modes.get)
        actions.append({
            "type": "USE",
            "priority": "MEDIUM",
            "action": f"Use '{best_mode}' mode for all applications — proven highest success",
            "reason": f"{modes[best_mode]} shortlists with this mode",
        })
    
    # Action 4: Prediction correction
    if reality_gap.get("alignment") == "misaligned":
        actions.append({
            "type": "RECALIBRATE",
            "priority": "HIGH",
            "action": "System predictions are drifting — apply only to 65%+ probability jobs this week",
            "reason": "Predictions don't match reality; be more selective while system recalibrates",
        })
    
    # Action 5: Data collection
    thresholds = check_data_thresholds(history)
    if not thresholds["prediction_insights"]:
        actions.append({
            "type": "TRACK",
            "priority": "MEDIUM",
            "action": f"Update {MIN_RESOLVED - thresholds['resolved_applications']} more application statuses",
            "reason": "System needs outcome data to improve predictions",
        })
    
    return {
        "actions": actions[:6],
        "total_actions": len(actions),
        "has_critical": any(a["priority"] == "CRITICAL" for a in actions),
    }


# ================================================================
# PART 9 — ROOT CAUSE VALIDATION (outcome-based)
# ================================================================

def validate_root_cause(history: List[Dict]) -> Dict:
    """
    Validate root cause diagnosis using REAL outcomes, not predictions.
    
    If user gets shortlisted at low-score jobs → resume/targeting isn't the issue
    If user never gets shortlisted despite high scores → candidate gap confirmed
    """
    resolved = [h for h in history if h.get("status") in ("shortlisted", "rejected")]
    
    if len(resolved) < 5:
        return {
            "validated_cause": "insufficient_data",
            "confidence": 0,
            "evidence": [],
            "message": "Need more resolved applications to validate root cause.",
        }
    
    shortlisted = [h for h in resolved if h["status"] == "shortlisted"]
    rejected = [h for h in resolved if h["status"] == "rejected"]
    
    shortlist_rate = len(shortlisted) / len(resolved) * 100
    
    # High scores but rejected → CANDIDATE GAP
    high_score_rejected = [h for h in rejected if h.get("ats_score", 0) >= 70]
    
    # Low scores but shortlisted → system under-predicting
    low_score_shortlisted = [h for h in shortlisted if h.get("ats_score", 0) < 60]
    
    evidence = []
    
    if len(high_score_rejected) >= 3:
        validated_cause = "CANDIDATE_GAP"
        confidence = 85
        evidence.append(
            f"{len(high_score_rejected)} high-score applications rejected — "
            f"resume looks good but skills/experience don't pass interview scrutiny"
        )
    elif shortlist_rate == 0 and len(resolved) >= 8:
        validated_cause = "CANDIDATE_GAP"
        confidence = 90
        evidence.append(f"0/{len(resolved)} shortlisted — fundamental capability issue")
    elif shortlist_rate > 0 and shortlist_rate < 5:
        # Check if rejections cluster around certain role types
        rejection_roles = set(h.get("role", "").lower() for h in rejected[:10])
        shortlist_roles = set(h.get("role", "").lower() for h in shortlisted)
        
        if rejection_roles and not rejection_roles.intersection(shortlist_roles):
            validated_cause = "TARGETING_GAP"
            confidence = 75
            evidence.append("Shortlists come from different role types than rejections")
        else:
            validated_cause = "RESUME_GAP"
            confidence = 70
            evidence.append(f"Low but non-zero success ({shortlist_rate:.0f}%) — resume optimization can help")
    elif shortlist_rate >= 5:
        validated_cause = "RESUME_GAP"
        confidence = 65
        evidence.append(f"Moderate success ({shortlist_rate:.0f}%) — fine-tuning resume will help more")
    else:
        validated_cause = "CANDIDATE_GAP"
        confidence = 60
        evidence.append("Unable to determine clear pattern — likely a mix of factors")
    
    if low_score_shortlisted:
        evidence.append(
            f"{len(low_score_shortlisted)} shortlists at low ATS scores — "
            f"system may be undervaluing your strengths"
        )
    
    return {
        "validated_cause": validated_cause,
        "confidence": confidence,
        "evidence": evidence,
        "shortlist_rate": round(shortlist_rate, 1),
        "message": f"Validated root cause: {validated_cause} (confidence: {confidence}%)",
    }


# ================================================================
# PART 10 — SYSTEM SELF-CORRECTION
# ================================================================

def compute_self_corrections(
    validation: Dict,
    reality_gap: Dict,
    history: List[Dict],
) -> Dict:
    """
    Determine if system needs to adjust its own parameters.
    
    Only triggers if there's sufficient data AND persistent mismatch.
    """
    corrections = []
    
    if not validation.get("sufficient_data"):
        return {
            "corrections": [],
            "needs_correction": False,
            "message": "Not enough data for self-correction yet.",
        }
    
    accuracy = validation.get("accuracy", 0)
    
    # Correction 1: Threshold adjustment
    if accuracy < 60:
        fp = validation["confusion_matrix"]["false_positives"]
        fn = validation["confusion_matrix"]["false_negatives"]
        
        if fp > fn:
            corrections.append({
                "parameter": "high_threshold",
                "current": 70,
                "recommended": 75,
                "reason": f"Too many false positives ({fp}) — raise bar for HIGH predictions",
            })
        elif fn > fp:
            corrections.append({
                "parameter": "low_threshold",
                "current": 55,
                "recommended": 50,
                "reason": f"Too many false negatives ({fn}) — lower bar for LOW predictions",
            })
    
    # Correction 2: Application gate
    high_rate = validation.get("high_conversion_rate", 0)
    if high_rate < 20 and validation.get("high_total", 0) >= 5:
        corrections.append({
            "parameter": "application_gate",
            "current": "40% minimum",
            "recommended": "55% minimum",
            "reason": f"Even HIGH predictions only convert at {high_rate:.0f}% — be more selective",
        })
    
    return {
        "corrections": corrections,
        "needs_correction": len(corrections) > 0,
        "message": (
            f"{len(corrections)} corrections recommended"
            if corrections
            else "System is well-calibrated — no corrections needed"
        ),
    }


# ================================================================
# MASTER ORCHESTRATOR
# ================================================================

def run_reality_validation(
    history: List[Dict],
    user_progress: Dict = None,
    current_probability: float = None,
) -> Dict:
    """
    Run the complete reality validation cycle.
    
    Returns comprehensive validation report with:
      - Prediction accuracy
      - Reality alignment
      - Application control
      - Root cause validation
      - Capability progress
      - Mandatory actions
      - Self-corrections
    """
    user_progress = user_progress or {}
    
    # Part 1: Prediction validation
    validation = validate_predictions(history)
    
    # Part 2: Reality gap analysis
    reality_gap = analyze_prediction_reality_gap(validation)
    
    # Part 3: Application control (if current probability given)
    app_control = None
    if current_probability is not None:
        app_control = enforce_application_control(current_probability, history)
    
    # Part 4+5: Data thresholds
    thresholds = check_data_thresholds(history)
    
    # Part 6: Capability progress
    capability = track_capability_progress(history, user_progress)
    
    # Part 7: Mandatory actions
    mandatory = generate_mandatory_actions(validation, reality_gap, capability, history)
    
    # Part 9: Root cause validation
    root_cause = validate_root_cause(history)
    
    # Part 10: Self-correction
    corrections = compute_self_corrections(validation, reality_gap, history)
    
    return {
        "prediction_accuracy": validation,
        "reality_alignment": reality_gap,
        "application_control": app_control,
        "data_thresholds": thresholds,
        "capability_progress": capability,
        "mandatory_actions": mandatory,
        "root_cause_validated": root_cause,
        "self_corrections": corrections,
        "system_health": (
            "HEALTHY" if reality_gap["alignment"] == "aligned"
            else "NEEDS_ATTENTION" if reality_gap["alignment"] == "minor_drift"
            else "CRITICAL" if reality_gap["alignment"] == "misaligned"
            else "BUILDING_DATA"
        ),
    }
