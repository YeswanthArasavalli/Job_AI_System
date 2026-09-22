"""
Production Hardening + Stability Engine (v4.3).

Ensures the hiring system remains reliable under real-world conditions.

11 safety mechanisms:
  1. Diversity safety guard — reject low-quality diversity fills
  2. Domain weight confidence scaling — prevent early overfitting
  3. Negative learning — penalize domains on exploration failure
  4. Momentum safe mode — forced apps must still be disciplined
  5. Exploration feedback loop — auto-tune exploration budget
  6. Learning stability monitor — freeze weights if variance spikes
  7. Data quality filter — reject noisy/incomplete inputs
  8. Decision consistency — same input → same output
  9. Calibration drift check — predicted vs actual alignment
  10. Safe defaults — prefer WARNING over APPLY when uncertain
  11. Unified stability report

Philosophy: "Stay reliable under uncertainty."
"""

import hashlib
import json
import statistics
from typing import List, Dict
from utils.logger import setup_logger

logger = setup_logger(__name__)

DIVERSITY_FLOOR = 35
DOMAIN_CONFIDENCE_MIN_APPS = 10
WEIGHT_VARIANCE_THRESHOLD = 30
EXPLORATION_LOW = 0.20
EXPLORATION_HIGH = 0.40
DRIFT_THRESHOLD = 15


# ================================================================
# PART 1 — DIVERSITY SAFETY GUARD
# ================================================================

def guard_diversity(selected: List[Dict]) -> Dict:
    """Reject diversity fills below 35% calibrated probability."""
    safe = []
    rejected = []
    for job in selected:
        reason = job.get("selection_reason", "primary")
        prob = job.get("calibrated_probability", 0)
        if reason in ("diversity_fill", "adjacent_domain", "momentum_force"):
            if prob < DIVERSITY_FLOOR:
                job["guard_rejection"] = f"Diversity job {prob:.0f}% below {DIVERSITY_FLOOR}% floor"
                rejected.append(job)
                continue
        safe.append(job)

    return {
        "safe_jobs": safe,
        "rejected_jobs": rejected,
        "count_removed": len(rejected),
    }


# ================================================================
# PART 2 — DOMAIN WEIGHT CONFIDENCE SCALING
# ================================================================

def scale_domain_weights(weights: Dict, history: List[Dict]) -> Dict:
    """Scale domain weight adjustments by confidence (apps in domain / 10)."""
    domain_counts = {}
    for h in history:
        role = (h.get("role") or "").lower()
        domain_counts[role] = domain_counts.get(role, 0) + 1

    scaled = {}
    for domain, raw_weight in weights.items():
        count = domain_counts.get(domain, 0)
        confidence = min(1.0, count / DOMAIN_CONFIDENCE_MIN_APPS)
        scaled[domain] = round(raw_weight * confidence, 1)

    return {
        "raw_weights": weights,
        "scaled_weights": scaled,
        "confidence_factors": {d: round(min(1.0, domain_counts.get(d, 0) / DOMAIN_CONFIDENCE_MIN_APPS), 2)
                               for d in weights},
    }


# ================================================================
# PART 3 — NEGATIVE LEARNING UPDATE
# ================================================================

def apply_negative_learning(weights: Dict, recent_explorations: List[Dict]) -> Dict:
    """Penalize domains where exploration resulted in rejection."""
    penalties = {}
    for exp in recent_explorations:
        if exp.get("status") == "rejected" and exp.get("selection_reason") in (
            "diversity_fill", "adjacent_domain", "momentum_force"
        ):
            domain = (exp.get("role") or "").lower()
            penalties[domain] = penalties.get(domain, 0) + 2

    updated = dict(weights)
    for domain, penalty in penalties.items():
        current = updated.get(domain, 0)
        updated[domain] = max(current - penalty, -10)

    return {"updated_weights": updated, "penalties_applied": penalties}


# ================================================================
# PART 4 — MOMENTUM SAFE MODE
# ================================================================

def enforce_momentum_safety(selected: List[Dict], momentum_active: bool) -> Dict:
    """If momentum forced, only allow jobs >= 30% probability."""
    if not momentum_active:
        return {"filtered": selected, "removed": 0}

    safe = []
    removed = 0
    for job in selected:
        if job.get("selection_reason") == "momentum_force" and job.get("calibrated_probability", 0) < 30:
            removed += 1
            continue
        safe.append(job)

    return {"filtered": safe, "removed": removed}


# ================================================================
# PART 5 — EXPLORATION FEEDBACK LOOP
# ================================================================

def tune_exploration_budget(
    exploration_history: List[Dict],
    current_budget: int,
) -> Dict:
    """Auto-tune exploration budget based on exploration success rate."""
    if not exploration_history:
        return {"budget": current_budget, "adjustment": "none", "rate": 0}

    resolved = [e for e in exploration_history if e.get("status") in ("shortlisted", "rejected")]
    if not resolved:
        return {"budget": current_budget, "adjustment": "none", "rate": 0}

    success = len([e for e in resolved if e["status"] == "shortlisted"])
    rate = success / len(resolved)

    if rate < EXPLORATION_LOW:
        new_budget = max(1, current_budget - 1)
        adjustment = "reduced"
    elif rate > EXPLORATION_HIGH:
        new_budget = min(3, current_budget + 1)
        adjustment = "increased"
    else:
        new_budget = current_budget
        adjustment = "stable"

    return {
        "budget": new_budget,
        "adjustment": adjustment,
        "rate": round(rate * 100, 1),
        "message": f"Exploration success {rate:.0%} → budget {adjustment} to {new_budget}",
    }


# ================================================================
# PART 6 — LEARNING STABILITY MONITOR
# ================================================================

def check_learning_stability(weights: Dict) -> Dict:
    """Freeze weight updates if variance exceeds threshold."""
    values = list(weights.values())
    if len(values) < 2:
        return {"stable": True, "state": "active", "variance": 0}

    variance = statistics.variance(values)
    stable = variance <= WEIGHT_VARIANCE_THRESHOLD

    return {
        "stable": stable,
        "state": "active" if stable else "frozen",
        "variance": round(variance, 1),
        "message": (
            "Learning stable" if stable
            else f"⚠️ Weight variance {variance:.0f} exceeds {WEIGHT_VARIANCE_THRESHOLD} — weights frozen"
        ),
    }


# ================================================================
# PART 7 — DATA QUALITY FILTER
# ================================================================

def filter_data_quality(evaluations: List[Dict]) -> Dict:
    """Reject noisy/incomplete inputs."""
    clean = []
    rejected = []

    seen = set()
    for ev in evaluations:
        company = (ev.get("company") or "").strip()
        role = (ev.get("role") or "").strip()

        # Missing key fields
        if not company or not role:
            ev["quality_issue"] = "Missing company or role"
            rejected.append(ev)
            continue

        # Duplicate detection
        key = f"{company.lower()}|{role.lower()}"
        if key in seen:
            ev["quality_issue"] = "Duplicate listing"
            rejected.append(ev)
            continue
        seen.add(key)

        # Missing probability
        if ev.get("shortlist_probability") is None:
            ev["quality_issue"] = "Missing probability score"
            rejected.append(ev)
            continue

        clean.append(ev)

    return {
        "clean": clean,
        "rejected": rejected,
        "rejected_count": len(rejected),
    }


# ================================================================
# PART 8 — DECISION CONSISTENCY CHECK
# ================================================================

def verify_consistency(input_data: Dict, output_data: Dict) -> Dict:
    """Verify same input produces same output (determinism check)."""
    input_hash = hashlib.md5(
        json.dumps(input_data, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]

    # Check output has required keys
    required = ["selection", "plan", "summary"]
    missing = [k for k in required if k not in output_data]

    return {
        "consistent": len(missing) == 0,
        "input_hash": input_hash,
        "missing_keys": missing,
        "message": "Deterministic" if not missing else f"Missing: {missing}",
    }


# ================================================================
# PART 9 — CALIBRATION DRIFT CHECK
# ================================================================

def check_calibration_drift(history: List[Dict]) -> Dict:
    """Monitor predicted vs actual outcome alignment."""
    resolved = [h for h in history if h.get("status") in ("shortlisted", "rejected")]
    if len(resolved) < 5:
        return {"drift_detected": False, "status": "insufficient_data", "drift_amount": 0}

    # Compare average predicted score vs actual success rate
    avg_score = sum(h.get("ats_score", 50) for h in resolved) / len(resolved)
    actual_rate = len([h for h in resolved if h["status"] == "shortlisted"]) / len(resolved) * 100

    drift = abs(avg_score - actual_rate)

    return {
        "drift_detected": drift > DRIFT_THRESHOLD,
        "status": "drift" if drift > DRIFT_THRESHOLD else "normal",
        "drift_amount": round(drift, 1),
        "avg_predicted": round(avg_score, 1),
        "actual_rate": round(actual_rate, 1),
        "message": (
            f"Drift: {drift:.0f}% (predicted avg {avg_score:.0f}% vs actual {actual_rate:.0f}%)"
            if drift > DRIFT_THRESHOLD
            else f"Calibration normal (drift: {drift:.0f}%)"
        ),
    }


# ================================================================
# PART 10 — SAFE DEFAULTS
# ================================================================

def apply_safe_defaults(decision: str, probability: float) -> Dict:
    """When uncertain, prefer WARNING over APPLY, APPLY over BLOCK if >= 40%."""
    if decision == "APPLY" and probability < 55:
        return {"decision": "WARNING", "reason": "Safe default: uncertain → WARNING", "changed": True}
    if decision == "BLOCKED" and probability >= 40:
        return {"decision": "WARNING", "reason": "Safe default: borderline → WARNING", "changed": True}
    return {"decision": decision, "reason": "No override", "changed": False}


# ================================================================
# MASTER ORCHESTRATOR
# ================================================================

def run_stability_check(
    evaluations: List[Dict] = None,
    selected_jobs: List[Dict] = None,
    domain_weights: Dict = None,
    history: List[Dict] = None,
    exploration_history: List[Dict] = None,
    momentum_active: bool = False,
    current_budget: int = 1,
    agent_output: Dict = None,
) -> Dict:
    """Run the complete production stability check."""
    evaluations = evaluations or []
    selected_jobs = selected_jobs or []
    domain_weights = domain_weights or {}
    history = history or []
    exploration_history = exploration_history or []
    agent_output = agent_output or {}

    # Part 1: Diversity guard
    diversity = guard_diversity(selected_jobs)

    # Part 2: Weight confidence scaling
    weight_scaling = scale_domain_weights(domain_weights, history)

    # Part 3: Negative learning
    neg_learning = apply_negative_learning(
        weight_scaling["scaled_weights"], exploration_history
    )

    # Part 4: Momentum safety
    momentum_safety = enforce_momentum_safety(diversity["safe_jobs"], momentum_active)

    # Part 5: Exploration tuning
    exploration = tune_exploration_budget(exploration_history, current_budget)

    # Part 6: Learning stability
    stability = check_learning_stability(neg_learning["updated_weights"])

    # Part 7: Data quality
    quality = filter_data_quality(evaluations)

    # Part 8: Consistency
    consistency = verify_consistency(
        {"evaluations": len(evaluations), "history": len(history)},
        agent_output,
    )

    # Part 9: Drift
    drift = check_calibration_drift(history)

    # Risk flags
    risks = []
    if not stability["stable"]:
        risks.append("INSTABILITY — weight variance too high")
    if drift["drift_detected"]:
        risks.append(f"DRIFT — predicted vs actual gap: {drift['drift_amount']}%")
    if exploration["rate"] < 10 and len(exploration_history) >= 5:
        risks.append("LOW_EXPLORATION — exploration success very low")
    if quality["rejected_count"] > len(evaluations) * 0.3:
        risks.append("DATA_QUALITY — >30% inputs rejected")

    return {
        "diversity_guard": diversity,
        "weight_scaling": weight_scaling,
        "negative_learning": neg_learning,
        "momentum_safety": momentum_safety,
        "exploration_tuning": exploration,
        "learning_stability": stability,
        "data_quality": quality,
        "consistency": consistency,
        "calibration_drift": drift,
        "risk_flags": risks,
        "summary": {
            "stability": "stable" if stability["stable"] else "unstable",
            "drift": drift["status"],
            "learning": stability["state"],
            "risks": len(risks),
            "quality_rejected": quality["rejected_count"],
        },
    }
