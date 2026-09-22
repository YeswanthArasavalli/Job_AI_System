"""
Behavior Engine (v5.1.1) — Budget + Recovery + Impact + Override + Reward.

v5.1 base:
  1. Exploration budget control (cap EXPERIMENT APPLY usage)
  2. Recovery enforcement (penalize non-action after SKIP/FIX)
  3. Impact upgrade layer (recruiter boost with business context)
  4. Minimum throughput guarantee (prevent passivity)

v5.1.1 patch:
  5. Soft override (anti-friction — user can override without breaking trust)
  6. Progress tracking (recovery execution awareness)
  7. Reward loop (reduce penalty when user improves)
  8. Graduated penalty control (anti-over-strictness)

Philosophy: "Guide + Enforce + but NEVER block completely."
"""

import os
import json
import re
import time
from typing import List, Dict, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Persistent state file
_STATE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_STATE_FILE = os.path.join(_STATE_DIR, "behavior_state.json")


def _load_state() -> Dict:
    """Load persistent behavior state."""
    try:
        if os.path.exists(_STATE_FILE):
            with open(_STATE_FILE, "r") as f:
                state = json.load(f)
            # Reset weekly counters if week changed
            current_week = time.strftime("%Y-W%W")
            if state.get("week") != current_week:
                state["week"] = current_week
                state["exploration_used"] = 0
                state["weekly_applications"] = 0
                _save_state(state)
            return state
    except Exception:
        pass
    return {
        "week": time.strftime("%Y-W%W"),
        "exploration_used": 0,
        "exploration_budget": 5,
        "weekly_applications": 0,
        "recovery_pending": {},
        "last_decision": None,
        "progress_score": 0,
        "prev_progress_score": 0,
        "override_count": 0,
    }


def _save_state(state: Dict):
    """Save persistent behavior state."""
    try:
        os.makedirs(_STATE_DIR, exist_ok=True)
        with open(_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


# ================================================================
# PART 1 — EXPLORATION BUDGET CONTROL
# ================================================================

def check_exploration_budget(
    state: Dict,
    max_weekly: int = 20,
) -> Dict:
    """
    Enforce exploration budget: max 25% of weekly applications.
    Prevents mass application spam via EXPERIMENT APPLY.
    """
    budget = max(1, int(0.25 * max(max_weekly, state.get("weekly_applications", 0) + 5)))
    used = state.get("exploration_used", 0)
    remaining = max(0, budget - used)

    return {
        "budget": budget,
        "used": used,
        "remaining": remaining,
        "allowed": remaining > 0,
        "message": (
            f"Exploration: {used}/{budget} used ({remaining} remaining)"
            if remaining > 0
            else f"Exploration budget exhausted ({used}/{budget})"
        ),
    }


def consume_exploration(state: Dict) -> Dict:
    """Consume one exploration credit."""
    state["exploration_used"] = state.get("exploration_used", 0) + 1
    _save_state(state)
    return state


# ================================================================
# PART 2 — RECOVERY ENFORCEMENT
# ================================================================

def check_recovery_enforcement(
    state: Dict,
    current_bullets: List[str] = None,
    current_keywords: List[str] = None,
) -> Dict:
    """
    Enforce recovery actions from previous SKIP/FIX decisions.
    Penalizes if user hasn't improved before re-applying.
    """
    pending = state.get("recovery_pending", {})
    if not pending:
        return {
            "enforced": False,
            "penalty": 0,
            "actions_completed": [],
            "actions_missing": [],
            "message": "No recovery actions pending",
        }

    current_bullets = current_bullets or []
    current_keywords = current_keywords or []
    bullets_text = " ".join(current_bullets).lower()

    # Check which actions were completed
    completed = []
    missing = []

    # Check keywords added
    required_keywords = pending.get("keywords_to_add", [])
    keywords_added = [kw for kw in required_keywords if kw.lower() in bullets_text]
    if keywords_added:
        completed.append(f"Keywords added: {', '.join(keywords_added)}")
    elif required_keywords:
        missing.append(f"Keywords missing: {', '.join(required_keywords[:3])}")

    # Check if bullets improved (signal: action verbs present)
    action_count = len(re.findall(
        r'\b(?:built|developed|designed|optimized|implemented|created|led|managed)\b',
        bullets_text, re.I
    ))
    if action_count >= 3:
        completed.append(f"Bullet quality improved ({action_count} action verbs)")
    else:
        missing.append("Bullets need stronger action verbs")

    # Check project addition
    project_signals = len(re.findall(
        r'\b(?:project|portfolio|github|deployed|end.to.end)\b',
        bullets_text, re.I
    ))
    if project_signals >= 1:
        completed.append("Project signals detected")
    elif pending.get("project_required", False):
        missing.append("Add/expand project aligned to JD")

    # Calculate progress score (v5.1.1)
    completion_rate = len(completed) / max(len(completed) + len(missing), 1)
    progress_score = round(completion_rate * 100)

    # v5.1.1: GRADUATED PENALTY CONTROL (anti-over-strictness)
    # progress_score == 0 → full penalty (25%)
    # 0 < progress_score < 50 → moderate (10-20%)
    # progress_score >= 50 → minimal (0-10%)
    if progress_score == 0:
        penalty = 25
    elif progress_score < 50:
        penalty = 20 - int(progress_score * 0.2)  # 20 → 10 as progress grows
    elif progress_score < 75:
        penalty = 10 - int((progress_score - 50) * 0.2)  # 10 → 5
    else:
        penalty = max(0, 5 - int((progress_score - 75) * 0.2))  # 5 → 0

    return {
        "enforced": penalty > 0,
        "penalty": penalty,
        "progress_score": progress_score,
        "completion_rate": progress_score,
        "actions_completed": completed,
        "actions_missing": missing,
        "message": (
            f"Recovery {progress_score}% complete — "
            f"{len(missing)} actions still needed"
        ) if missing else "Recovery complete",
    }


def set_recovery_pending(state: Dict, missing_keywords: List[str], project_required: bool = False):
    """Set recovery requirements for next application."""
    state["recovery_pending"] = {
        "keywords_to_add": missing_keywords[:5],
        "project_required": project_required,
        "set_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _save_state(state)


def clear_recovery(state: Dict):
    """Clear recovery after successful completion."""
    state["recovery_pending"] = {}
    _save_state(state)


# ================================================================
# PART 3 — IMPACT UPGRADE LAYER
# ================================================================

def upgrade_bullet_impact(bullet: str) -> Dict:
    """
    Add business context and safe impact to bullet.
    Links work → outcome for recruiter clarity.
    NO fake metrics. MUST remain interview-defensible.
    """
    original = bullet
    improved = bullet
    changes = []

    # Step 1: Strengthen verbs
    _VERB_MAP = [
        (r'\b[Bb]uilt\b(?!\s+and)', 'Built'),
        (r'\b[Ww]orked on\b', 'Developed'),
        (r'\b[Rr]esponsible for\b', 'Led'),
        (r'\b[Hh]andled\b', 'Managed'),
        (r'\b[Dd]id\b', 'Executed'),
        (r'\b[Uu]sed\b', 'Leveraged'),
    ]
    for pattern, replacement in _VERB_MAP:
        if re.search(pattern, improved):
            improved = re.sub(pattern, replacement, improved, count=1)
            changes.append(f"verb_strengthen")

    # Step 2: Add business context if just technical
    has_context = bool(re.search(
        r'\b(?:to\s+(?:enable|support|improve|drive|enhance|ensure|reduce|increase)|'
        r'enabling|supporting|improving|for\s+(?:faster|better|real-time))\b',
        improved, re.I
    ))

    if not has_context and len(improved) < 130:
        b_lower = improved.lower()
        if any(w in b_lower for w in ["pipeline", "etl", "data process"]):
            improved = improved.rstrip('.') + " to enable faster analytics and improve data availability."
            changes.append("context: analytics enablement")
        elif any(w in b_lower for w in ["model", "predict", "ml", "train"]):
            improved = improved.rstrip('.') + " to support data-driven business decisions."
            changes.append("context: business decisions")
        elif any(w in b_lower for w in ["dashboard", "visual", "report"]):
            improved = improved.rstrip('.') + " to provide stakeholders with actionable insights."
            changes.append("context: stakeholder insights")
        elif any(w in b_lower for w in ["api", "service", "deploy"]):
            improved = improved.rstrip('.') + " to ensure reliable service delivery."
            changes.append("context: service reliability")
        elif any(w in b_lower for w in ["database", "sql", "query"]):
            improved = improved.rstrip('.') + " to support efficient data retrieval."
            changes.append("context: data retrieval")
        elif any(w in b_lower for w in ["automat", "script", "workflow"]):
            improved = improved.rstrip('.') + " to reduce manual effort and improve consistency."
            changes.append("context: automation benefit")

    return {
        "original": original,
        "improved": improved,
        "changed": improved != original,
        "changes": changes,
    }


def apply_impact_upgrades(bullets: List[str], recruiter_avg: float) -> Dict:
    """
    Apply impact upgrades to all bullets if recruiter score is weak.
    Trigger: recruiter_avg < 55.
    """
    if recruiter_avg >= 55:
        return {
            "applied": False,
            "reason": f"Recruiter score {recruiter_avg:.0f} ≥ 55, no upgrade needed",
            "bullets_improved": [],
            "original_bullets": bullets,
            "upgraded_bullets": bullets,
        }

    upgraded = []
    improvements = []
    for b in bullets:
        result = upgrade_bullet_impact(b)
        upgraded.append(result["improved"])
        if result["changed"]:
            improvements.append({
                "before": result["original"][:70],
                "after": result["improved"][:70],
                "changes": result["changes"],
            })

    return {
        "applied": True,
        "reason": f"Recruiter score {recruiter_avg:.0f} < 55, impact upgrade applied",
        "bullets_improved": improvements,
        "original_bullets": bullets,
        "upgraded_bullets": upgraded,
    }


# ================================================================
# PART 4 — MINIMUM THROUGHPUT GUARANTEE
# ================================================================

def check_throughput_guard(state: Dict, min_weekly: int = 3) -> Dict:
    """
    Ensure system doesn't become too passive.
    If weekly applications < 3, force exploration.
    """
    weekly = state.get("weekly_applications", 0)
    below_minimum = weekly < min_weekly

    return {
        "forced": below_minimum,
        "weekly_applications": weekly,
        "minimum": min_weekly,
        "deficit": max(0, min_weekly - weekly),
        "message": (
            f"Throughput guard: {weekly}/{min_weekly} weekly apps — forcing exploration"
            if below_minimum
            else f"Throughput OK: {weekly}/{min_weekly} weekly apps"
        ),
    }


def record_application(state: Dict):
    """Record an application for throughput tracking."""
    state["weekly_applications"] = state.get("weekly_applications", 0) + 1
    _save_state(state)


# ================================================================
# PART 5 — SOFT OVERRIDE (v5.1.1 — Anti-Friction Layer)
# ================================================================

def apply_soft_override(decision_final: str, confidence: int, state: Dict) -> Dict:
    """
    Allow user to override system decisions safely.
    Does NOT change scores, inflate probability, or mark as APPLY NOW.
    Tags application as 'override' and reduces confidence.
    """
    original = decision_final
    override_confidence = max(15, confidence - 15)  # Reduce by 15%
    state["override_count"] = state.get("override_count", 0) + 1
    _save_state(state)

    return {
        "override_used": True,
        "original_decision": original,
        "final_decision": "USER_OVERRIDE_APPLY",
        "confidence": override_confidence,
        "override_message": (
            "⚠️ You chose to apply despite system recommendation. "
            "Scores unchanged. Application tagged as override."
        ),
        "override_count": state["override_count"],
    }


# ================================================================
# PART 6 — REWARD LOOP (v5.1.1)
# ================================================================

def compute_reward(state: Dict, current_progress: int) -> Dict:
    """
    Reward user when progress_score increases.
    Reduces penalty, increases confidence.
    """
    prev = state.get("prev_progress_score", 0)
    delta = current_progress - prev

    reward = {
        "applied": False,
        "penalty_reduction": 0,
        "confidence_boost": 0,
        "progress_delta": delta,
        "message": "",
    }

    if delta > 0:
        # Reward proportional to improvement
        if delta >= 30:
            reward["penalty_reduction"] = 15
            reward["confidence_boost"] = 10
            reward["message"] = f"Strong improvement (+{delta}%) — penalty reduced, confidence boosted"
        elif delta >= 15:
            reward["penalty_reduction"] = 10
            reward["confidence_boost"] = 7
            reward["message"] = f"Good improvement (+{delta}%) — penalty reduced"
        else:
            reward["penalty_reduction"] = 5
            reward["confidence_boost"] = 5
            reward["message"] = f"Progress detected (+{delta}%) — small reward applied"
        reward["applied"] = True
    elif delta == 0 and prev > 0:
        reward["message"] = "No change since last run"
    else:
        reward["message"] = "No progress yet"

    # Update state for next comparison
    state["prev_progress_score"] = current_progress
    state["progress_score"] = current_progress
    _save_state(state)

    return reward


# ================================================================
# PART 7 — BEHAVIORAL DECISION MODIFIER (updated for v5.1.1)
# ================================================================

def apply_behavior_modifiers(
    decision: Dict,
    state: Dict,
    bullets: List[str] = None,
    missing_keywords: List[str] = None,
    recruiter_avg: float = 0,
    user_override: bool = False,
) -> Dict:
    """
    Apply all behavioral modifiers to the base adaptive decision.

    Modifiers (in order):
      1. Exploration budget cap
      2. Recovery enforcement (with graduated penalty)
      3. Progress reward (v5.1.1)
      4. Impact upgrade check
      5. Throughput guard
      6. Soft override (v5.1.1)
    """
    bullets = bullets or []
    missing_keywords = missing_keywords or []
    final = decision.get("final", "SKIP")
    confidence = decision.get("confidence", 50)
    modifiers = list(decision.get("modifiers", []))

    # 1. Exploration budget
    budget = check_exploration_budget(state)
    if final == "EXPERIMENT APPLY" and not budget["allowed"]:
        final = "SKIP"
        confidence = max(20, confidence - 20)
        modifiers.append(f"Exploration budget exhausted ({budget['used']}/{budget['budget']})")

    # 2. Recovery enforcement (with graduated penalty — v5.1.1)
    recovery = check_recovery_enforcement(state, bullets)
    if recovery["enforced"]:
        if final == "APPLY NOW":
            final = "APPLY (FIX GAPS)"
            modifiers.append(
                f"Downgraded: recovery {recovery['progress_score']}% complete"
            )
        confidence = max(15, confidence - recovery["penalty"])

    # 3. Reward loop (v5.1.1) — reward improvement, reduce penalty
    progress = recovery.get("progress_score", 0)
    reward = compute_reward(state, progress)
    if reward["applied"]:
        confidence = min(95, confidence + reward["confidence_boost"])
        modifiers.append(f"Reward: {reward['message']}")
        # If reward earned, allow upgrade from FIX → keep FIX (don't downgrade further)

    # 4. Impact upgrade (assessment only — actual bullet rewrite is separate)
    impact_needed = recruiter_avg < 55

    # 5. Throughput guard
    throughput = check_throughput_guard(state)
    if throughput["forced"] and final == "SKIP":
        final = "EXPERIMENT APPLY"
        confidence = min(35, confidence)
        modifiers.append(f"Throughput guard: {throughput['deficit']} more apps needed this week")

    # Record exploration
    if final == "EXPERIMENT APPLY":
        if budget["allowed"]:
            consume_exploration(state)
        else:
            final = "SKIP"
            modifiers.append("Exploration budget blocked")

    # 6. Soft override (v5.1.1)
    override_info = None
    if user_override and final in ("SKIP", "APPLY (FIX GAPS)", "EXPERIMENT APPLY"):
        override_info = apply_soft_override(final, confidence, state)
        final = "USER_OVERRIDE_APPLY"
        confidence = override_info["confidence"]
        modifiers.append(f"User override: {override_info['original_decision']} → {final}")

    # Set recovery for next time if not applied
    if final in ("SKIP", "APPLY (FIX GAPS)", "EXPERIMENT APPLY") and missing_keywords:
        set_recovery_pending(state, missing_keywords, project_required=(final == "SKIP"))
    elif final in ("APPLY NOW", "USER_OVERRIDE_APPLY"):
        clear_recovery(state)

    # Record application
    if final in ("APPLY NOW", "APPLY (FIX GAPS)", "EXPERIMENT APPLY", "USER_OVERRIDE_APPLY"):
        record_application(state)

    return {
        "final": final,
        "confidence": confidence,
        "reason": decision.get("reason", ""),
        "signals": decision.get("signals", {}),
        "modifiers": modifiers,
        "behavior_control": {
            "exploration_used": state.get("exploration_used", 0),
            "exploration_budget": budget["budget"],
            "exploration_remaining": budget["remaining"],
            "recovery_enforced": recovery["enforced"],
            "recovery_completion": recovery.get("progress_score", 0) if recovery["enforced"] else 100,
            "throughput_forced": throughput["forced"],
            "weekly_applications": state.get("weekly_applications", 0),
            "impact_upgrade_needed": impact_needed,
            "override_used": override_info is not None,
            "override_message": override_info["override_message"] if override_info else None,
            "progress_score": progress,
            "progress_delta": reward["progress_delta"],
            "reward_applied": reward["applied"],
        },
        "recovery_status": {
            "actions_completed": recovery["actions_completed"],
            "actions_missing": recovery["actions_missing"],
        },
    }


# ================================================================
# MASTER ORCHESTRATOR
# ================================================================

def run_behavior_engine(
    decision: Dict,
    bullets: List[str],
    missing_keywords: List[str] = None,
    recruiter_avg: float = 0,
    user_override: bool = False,
) -> Dict:
    """
    Run the complete behavior engine (v5.1.1).
    Budget + Recovery + Impact + Throughput + Override + Reward.
    """
    missing_keywords = missing_keywords or []

    logger.info("BEHAVIOR ENGINE v5.1.1 — Starting")

    # Load persistent state
    state = _load_state()
    state["last_decision"] = decision.get("final", "UNKNOWN")

    # Apply impact upgrades
    impact = apply_impact_upgrades(bullets, recruiter_avg)
    if impact["applied"]:
        logger.info(
            f"  [v5.1.1] Impact upgrade: {len(impact['bullets_improved'])} bullets enhanced"
        )

    # Apply behavioral modifiers (including override + reward)
    modified = apply_behavior_modifiers(
        decision, state, bullets, missing_keywords, recruiter_avg,
        user_override=user_override,
    )

    logger.info(
        f"  [v5.1.1] Decision: {modified['final']} (conf={modified['confidence']}%)"
    )
    bc = modified["behavior_control"]
    logger.info(
        f"  [v5.1.1] Budget: {bc['exploration_used']}/{bc['exploration_budget']}, "
        f"Apps: {bc['weekly_applications']}, "
        f"Recovery: {'ENFORCED' if bc['recovery_enforced'] else 'OK'}, "
        f"Throughput: {'FORCED' if bc['throughput_forced'] else 'OK'}"
    )
    if bc.get("override_used"):
        logger.info(f"  [v5.1.1] Override: {bc['override_message']}")
    if bc.get("reward_applied"):
        logger.info(f"  [v5.1.1] Reward applied (progress delta={bc['progress_delta']:+d}%)")
    if modified["modifiers"]:
        for m in modified["modifiers"]:
            logger.info(f"    Modifier: {m}")

    # Save state
    _save_state(state)

    logger.info("BEHAVIOR ENGINE v5.1.1 — Complete")

    return {
        "decision": {
            "final": modified["final"],
            "confidence": modified["confidence"],
            "reason": modified["reason"],
            "signals": modified["signals"],
            "modifiers": modified["modifiers"],
        },
        "behavior_control": modified["behavior_control"],
        "impact_upgrade": {
            "applied": impact["applied"],
            "bullets_improved": impact["bullets_improved"][:3],
        },
        "recovery_status": modified["recovery_status"],
        "upgraded_bullets": impact["upgraded_bullets"],
    }
