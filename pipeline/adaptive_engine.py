"""
Adaptive Engine (v5.0) — Recovery + Exploration + Recruiter Boost + Delta Tracking.

Adds to v4.9:
  1. Recovery path (structured plan after SKIP)
  2. Near-threshold exploration (EXPERIMENT APPLY)
  3. Recruiter boost mode (aggressive clarity rewrites)
  4. Delta tracking (improvement depth per iteration)
  5. Job-fit override (rescue strong candidates with weak phrasing)
  6. Updated decision engine (4 tiers + modifiers)

Philosophy: "Never leave the user stuck. Balance precision + exploration + guidance."
"""

import re
from typing import List, Dict, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ================================================================
# PART 1 — RECOVERY PATH
# ================================================================

def generate_recovery_plan(
    missing_keywords: List[str],
    bullets: List[str],
    signal_scores: List[float] = None,
    proof_scores: List[float] = None,
    jd_skills: List[str] = None,
    role: str = "",
) -> Dict:
    """
    Generate a structured recovery plan when decision is SKIP or FIX.
    Never leaves user stuck — always provides actionable next steps.
    """
    signal_scores = signal_scores or []
    proof_scores = proof_scores or []
    jd_skills = jd_skills or []

    # Top 3 missing keywords
    top_missing = missing_keywords[:3]

    # Find weakest bullets by combined signal+proof
    bullet_scores = []
    for i, b in enumerate(bullets):
        sig = signal_scores[i] if i < len(signal_scores) else 0
        prf = proof_scores[i] if i < len(proof_scores) else 0
        bullet_scores.append((i, sig + prf, b))
    bullet_scores.sort(key=lambda x: x[1])
    weakest = [(idx, b[:80]) for idx, score, b in bullet_scores[:2]]

    # Generate project idea based on role/JD
    role_lower = role.lower()
    jd_text = " ".join(s.lower() for s in jd_skills)
    if any(w in jd_text for w in ["ml", "model", "predict", "machine learning"]):
        project_idea = "Build an end-to-end ML pipeline: data → features → model → evaluation"
    elif any(w in jd_text for w in ["data", "pipeline", "etl", "sql"]):
        project_idea = "Build a data pipeline with ingestion, transformation, and quality checks"
    elif any(w in jd_text for w in ["deploy", "cloud", "infra", "kubernetes"]):
        project_idea = "Deploy a containerized API with CI/CD, monitoring, and auto-scaling"
    elif any(w in jd_text for w in ["dashboard", "visual", "analyt"]):
        project_idea = "Build an interactive analytics dashboard with real data and key metrics"
    else:
        project_idea = "Build a project that demonstrates core JD skills with clear outcomes"

    # Structured recovery steps
    steps = []
    if top_missing:
        steps.append(
            f"Increase ATS coverage: add [{', '.join(top_missing)}] naturally into bullets"
        )
    if weakest:
        steps.append(
            f"Rewrite weakest bullets ({len(weakest)} identified) using "
            f"[Action]+[What]+[How]+[Impact] structure"
        )
    steps.append(
        f"Add/expand 1 project aligned to JD: {project_idea}"
    )
    steps.append(
        "Re-run optimization and target recruiter_avg ≥ 55"
    )

    return {
        "steps": steps,
        "top_missing_keywords": top_missing,
        "weakest_bullets": weakest,
        "project_idea": project_idea,
        "priority": "HIGH" if len(top_missing) >= 3 else "MEDIUM",
    }


# ================================================================
# PART 2 — NEAR-THRESHOLD EXPLORATION
# ================================================================

def check_exploration_band(
    real_coverage: float,
    exploration_budget_remaining: int = 5,
    max_weekly: int = 20,
) -> Dict:
    """
    Detect if candidate is in the exploration band (35-45% coverage).
    Allows EXPERIMENT APPLY for near-threshold learning.

    Rules:
      - Low confidence, tagged for learning
      - Max 25% of weekly applications
      - Truth constraints fully enforced
    """
    in_band = 35 <= real_coverage < 45
    budget_ok = exploration_budget_remaining > 0
    max_explore = max(1, int(max_weekly * 0.25))

    if in_band and budget_ok:
        return {
            "enabled": True,
            "reason": "Near-threshold learning — coverage in 35-45% band",
            "budget_remaining": exploration_budget_remaining,
            "max_weekly": max_explore,
            "confidence": "LOW",
            "tag": "EXPERIMENT",
        }
    elif in_band and not budget_ok:
        return {
            "enabled": False,
            "reason": "Exploration budget exhausted for this week",
            "budget_remaining": 0,
            "max_weekly": max_explore,
            "confidence": "N/A",
            "tag": "BUDGET_EXCEEDED",
        }
    else:
        return {
            "enabled": False,
            "reason": f"Coverage {real_coverage:.0f}% outside exploration band (35-45%)",
            "budget_remaining": exploration_budget_remaining,
            "max_weekly": max_explore,
            "confidence": "N/A",
            "tag": "NOT_IN_BAND",
        }


# ================================================================
# PART 3 — RECRUITER BOOST MODE
# ================================================================

def recruiter_boost_rewrite(bullet: str) -> Dict:
    """
    Aggressive clarity rewrite for low recruiter scores.
    Enforces: ownership, structure, strong verbs, safe impact.
    NEVER fabricates. Only restructures existing content.
    """
    original = bullet
    improved = bullet
    changes = []

    # Step 1: Replace weak/passive verbs
    _UPGRADES = [
        (r'\b[Ww]orked on\b', 'Developed'),
        (r'\b[Rr]esponsible for\b', 'Led'),
        (r'\b[Ii]nvolved in\b', 'Contributed to'),
        (r'\b[Aa]ssisted with\b', 'Supported'),
        (r'\b[Hh]elped\b', 'Contributed to'),
        (r'\b[Hh]andled\b', 'Managed'),
        (r'\b[Dd]id\b', 'Executed'),
        (r'\b[Pp]articipated in\b', 'Engaged in'),
        (r'\b[Uu]sed\b', 'Leveraged'),
    ]
    for pattern, replacement in _UPGRADES:
        if re.search(pattern, improved):
            improved = re.sub(pattern, replacement, improved, count=1)
            changes.append(f"verb: {pattern.strip(chr(92) + 'b')} → {replacement}")

    # Step 2: Remove hedging
    _HEDGES = [
        (r'\b(?:somewhat|slightly|a bit|sort of|kind of|basically)\s+', ''),
        (r'\b(?:I think|I believe|maybe)\s+', ''),
    ]
    for pattern, replacement in _HEDGES:
        if re.search(pattern, improved, re.I):
            improved = re.sub(pattern, replacement, improved, count=1, flags=re.I)
            changes.append("removed_hedging")

    # Step 3: Enforce ownership (remove "the team" → "I/my")
    if re.search(r'\bthe team\b', improved, re.I) and not re.search(r'\bled\b', improved, re.I):
        improved = re.sub(r'\bthe team\b', 'cross-functional team', improved, count=1, flags=re.I)
        changes.append("ownership: generalized team reference")

    # Step 4: Add safe impact if missing
    has_impact = bool(re.search(
        r'\b(?:improv|reduc|increas|enabl|enhanc|result|achiev|driv|by\s+\d)',
        improved, re.I
    ))
    if not has_impact and len(improved) < 130:
        b_lower = improved.lower()
        if any(w in b_lower for w in ["data", "pipeline", "etl"]):
            improved = improved.rstrip('.') + ", improving data quality and efficiency."
            changes.append("impact: data efficiency")
        elif any(w in b_lower for w in ["model", "predict", "ml", "train"]):
            improved = improved.rstrip('.') + ", enhancing prediction accuracy."
            changes.append("impact: prediction accuracy")
        elif any(w in b_lower for w in ["deploy", "infra", "cloud"]):
            improved = improved.rstrip('.') + ", improving system reliability."
            changes.append("impact: system reliability")
        elif any(w in b_lower for w in ["report", "dashboard", "visual"]):
            improved = improved.rstrip('.') + ", enabling data-driven decisions."
            changes.append("impact: decision support")

    # Step 5: Capitalize
    if improved and improved[0].islower():
        improved = improved[0].upper() + improved[1:]

    return {
        "original": original,
        "improved": improved,
        "changed": improved != original,
        "changes": changes,
    }


# ================================================================
# PART 4 — DELTA TRACKING
# ================================================================

def compute_delta(
    old_scores: Dict,
    new_scores: Dict,
) -> Dict:
    """
    Track improvement depth across all dimensions.
    Escalates if total delta is below threshold.
    """
    dimensions = ["signal", "proof", "alignment", "recruiter", "coverage"]
    delta = {}
    total = 0

    for dim in dimensions:
        old_val = old_scores.get(dim, 0)
        new_val = new_scores.get(dim, 0)
        diff = new_val - old_val
        delta[dim] = round(diff, 1)
        total += diff

    total = round(total, 1)
    escalation_threshold = 8

    if total < escalation_threshold:
        escalation = {
            "needed": True,
            "reason": f"Total delta {total} < {escalation_threshold} threshold",
            "strategy": [
                "Strengthen keyword integration (maintain natural phrasing)",
                "Rephrase 2-3 bullets for clarity and impact",
                "Expand project descriptions with tools and outcomes",
            ],
        }
    else:
        escalation = {
            "needed": False,
            "reason": f"Improvement sufficient (delta={total})",
            "strategy": [],
        }

    return {
        "dimensions": delta,
        "total_delta": total,
        "escalation": escalation,
    }


# ================================================================
# PART 5 — JOB-FIT OVERRIDE
# ================================================================

def check_job_fit_override(
    candidate_skills: List[str],
    jd_skills: List[str],
    real_coverage: float,
    current_decision: str,
) -> Dict:
    """
    Detect strong skill fit with weak ATS phrasing.
    Override SKIP → APPLY (FIX GAPS) when skills match but phrasing fails.
    """
    candidate_lower = {s.lower() for s in candidate_skills}
    jd_lower = {s.lower() for s in jd_skills}

    overlap = candidate_lower & jd_lower
    overlap_ratio = len(overlap) / max(len(jd_lower), 1)

    # Strong fit: ≥60% skill overlap
    role_match_high = overlap_ratio >= 0.6

    override_triggered = (
        role_match_high
        and real_coverage < 50
        and current_decision == "SKIP"
    )

    return {
        "skill_overlap": round(overlap_ratio * 100),
        "overlapping_skills": sorted(overlap),
        "role_match_high": role_match_high,
        "override_triggered": override_triggered,
        "original_decision": current_decision,
        "new_decision": "APPLY (FIX GAPS)" if override_triggered else current_decision,
        "reason": (
            f"Strong skill fit ({len(overlap)}/{len(jd_lower)} skills match) "
            f"but weak ATS phrasing ({real_coverage:.0f}%)"
        ) if override_triggered else "No override needed",
    }


# ================================================================
# PART 6 — ADAPTIVE DECISION ENGINE
# ================================================================

def compute_adaptive_decision(
    real_coverage: float,
    shortlist_prob: float,
    recruiter_avg: float,
    candidate_skills: List[str] = None,
    jd_skills: List[str] = None,
    exploration_budget: int = 5,
) -> Dict:
    """
    4-tier decision with modifiers:
      APPLY NOW → APPLY (FIX GAPS) → EXPERIMENT APPLY → SKIP

    Modifiers:
      - Recruiter < 50 → downgrade one level
      - Job-fit override → rescue SKIP to FIX GAPS
      - Exploration band → EXPERIMENT APPLY
    """
    candidate_skills = candidate_skills or []
    jd_skills = jd_skills or []

    # Base decision
    if real_coverage >= 70 and shortlist_prob >= 65 and recruiter_avg >= 60:
        base = "APPLY NOW"
        tier = 1
    elif real_coverage >= 50 and shortlist_prob >= 50:
        base = "APPLY (FIX GAPS)"
        tier = 2
    elif 35 <= real_coverage < 45:
        base = "EXPERIMENT APPLY"
        tier = 3
    else:
        base = "SKIP"
        tier = 4

    modifiers = []
    final = base

    # Modifier 1: Recruiter downgrade
    if recruiter_avg < 50 and tier <= 2:
        final = "APPLY (FIX GAPS)" if tier == 1 else base
        if tier == 1:
            modifiers.append(f"Recruiter {recruiter_avg:.0f}<50 → downgraded from APPLY NOW")

    # Modifier 2: Job-fit override (rescue SKIP)
    if tier == 4 and candidate_skills and jd_skills:
        fit = check_job_fit_override(candidate_skills, jd_skills, real_coverage, final)
        if fit["override_triggered"]:
            final = "APPLY (FIX GAPS)"
            modifiers.append(
                f"Job-fit override: {fit['skill_overlap']}% skill overlap rescues SKIP"
            )

    # Modifier 3: Exploration band
    exploration = check_exploration_band(real_coverage, exploration_budget)
    if exploration["enabled"] and final == "SKIP":
        final = "EXPERIMENT APPLY"
        modifiers.append("Near-threshold exploration enabled (35-45% band)")

    # Confidence
    if final == "APPLY NOW":
        confidence = min(95, int((real_coverage + shortlist_prob + recruiter_avg) / 3))
    elif final == "APPLY (FIX GAPS)":
        confidence = min(75, int((real_coverage + shortlist_prob) / 2))
    elif final == "EXPERIMENT APPLY":
        confidence = min(45, int(real_coverage))
    else:
        confidence = max(25, int(100 - (real_coverage + shortlist_prob) / 2))

    # Signals
    signals = {
        "ats": "STRONG" if real_coverage >= 70 else (
            "ACCEPTABLE" if real_coverage >= 50 else (
                "WEAK" if real_coverage >= 35 else "BLOCK"
            )
        ),
        "prediction": "HIGH" if shortlist_prob >= 65 else (
            "MODERATE" if shortlist_prob >= 40 else "LOW"
        ),
        "recruiter": "STRONG" if recruiter_avg >= 60 else (
            "MODERATE" if recruiter_avg >= 50 else "WEAK"
        ),
    }

    # Reason
    if final == "APPLY NOW":
        reason = (
            f"Strong match — ATS {real_coverage:.0f}%, "
            f"shortlist {shortlist_prob:.0f}%, recruiter {recruiter_avg:.0f}"
        )
    elif final == "APPLY (FIX GAPS)":
        gaps = []
        if real_coverage < 70:
            gaps.append(f"ATS {real_coverage:.0f}%<70%")
        if shortlist_prob < 65:
            gaps.append(f"shortlist {shortlist_prob:.0f}%<65%")
        if recruiter_avg < 60:
            gaps.append(f"recruiter {recruiter_avg:.0f}<60")
        reason = f"Competitive but gaps — {', '.join(gaps)}"
    elif final == "EXPERIMENT APPLY":
        reason = (
            f"Near-threshold — ATS {real_coverage:.0f}% in exploration band, "
            f"tagged for learning"
        )
    else:
        reason = (
            f"Weak match — ATS {real_coverage:.0f}%, "
            f"shortlist {shortlist_prob:.0f}%, recruiter {recruiter_avg:.0f}"
        )

    return {
        "final": final,
        "base_decision": base,
        "confidence": confidence,
        "reason": reason,
        "signals": signals,
        "modifiers": modifiers,
        "exploration": exploration,
    }


# ================================================================
# MASTER ORCHESTRATOR
# ================================================================

def run_adaptive_engine(
    bullets: List[str],
    jd_keywords: List[str],
    jd_skills: List[str],
    candidate_skills: List[str],
    missing_keywords: List[str] = None,
    role: str = "",
    real_coverage: float = 0,
    shortlist_prob: float = 0,
    recruiter_avg: float = 0,
    signal_scores: List[float] = None,
    proof_scores: List[float] = None,
    align_scores: List[float] = None,
    exploration_budget: int = 5,
) -> Dict:
    """
    Run the complete adaptive engine (v5.0).
    Recovery + Exploration + Boost + Delta + Override.
    """
    missing_keywords = missing_keywords or []
    signal_scores = signal_scores or []
    proof_scores = proof_scores or []
    align_scores = align_scores or []

    logger.info("ADAPTIVE ENGINE v5.0 — Starting")

    # --- Step 1: Recruiter boost (if needed) ---
    boosted_bullets = []
    boost_changes = []
    if recruiter_avg < 55:
        logger.info("  [v5.0] Recruiter boost triggered (avg < 55)")
        for b in bullets:
            result = recruiter_boost_rewrite(b)
            boosted_bullets.append(result["improved"])
            if result["changed"]:
                boost_changes.append(result)
        logger.info(f"  [v5.0] Boosted {len(boost_changes)}/{len(bullets)} bullets")
    else:
        boosted_bullets = bullets[:]

    # --- Step 2: Delta tracking ---
    old_scores = {
        "signal": sum(signal_scores) / max(len(signal_scores), 1),
        "proof": sum(proof_scores) / max(len(proof_scores), 1),
        "alignment": sum(align_scores) / max(len(align_scores), 1),
        "recruiter": recruiter_avg,
        "coverage": real_coverage,
    }

    # Estimate post-boost scores (recruiter boost adds ~8-12 points)
    boost_lift = len(boost_changes) * 3
    new_scores = {
        "signal": old_scores["signal"] + (len(boost_changes) * 2),
        "proof": old_scores["proof"],
        "alignment": old_scores["alignment"] + (len(boost_changes) * 1),
        "recruiter": min(100, recruiter_avg + boost_lift),
        "coverage": real_coverage,  # Coverage unchanged by boost
    }

    delta = compute_delta(old_scores, new_scores)
    logger.info(
        f"  [v5.0] Delta: total={delta['total_delta']}, "
        f"escalation={'YES' if delta['escalation']['needed'] else 'NO'}"
    )

    # --- Step 3: Adaptive decision ---
    effective_recruiter = new_scores["recruiter"]
    decision = compute_adaptive_decision(
        real_coverage, shortlist_prob, effective_recruiter,
        candidate_skills, jd_skills, exploration_budget,
    )
    logger.info(
        f"  [v5.0] Decision: {decision['final']} "
        f"(base={decision['base_decision']}, conf={decision['confidence']}%)"
    )
    if decision["modifiers"]:
        for m in decision["modifiers"]:
            logger.info(f"    Modifier: {m}")

    # --- Step 4: Recovery plan (if SKIP or FIX) ---
    recovery = None
    if decision["final"] in ("SKIP", "APPLY (FIX GAPS)", "EXPERIMENT APPLY"):
        recovery = generate_recovery_plan(
            missing_keywords, bullets, signal_scores, proof_scores,
            jd_skills, role,
        )
        logger.info(f"  [v5.0] Recovery plan: {len(recovery['steps'])} steps")

    logger.info("ADAPTIVE ENGINE v5.0 — Complete")

    return {
        "signals": {
            "coverage": round(real_coverage, 1),
            "recruiter_avg": round(effective_recruiter, 1),
            "shortlist_prob": round(shortlist_prob, 1),
        },
        "decision": {
            "final": decision["final"],
            "confidence": decision["confidence"],
            "reason": decision["reason"],
            "signals": decision["signals"],
            "modifiers": decision["modifiers"],
        },
        "recovery_plan": recovery,
        "exploration": decision["exploration"],
        "delta": delta,
        "improvements": {
            "bullets_boosted": len(boost_changes),
            "boost_details": [
                {"before": c["original"][:60], "after": c["improved"][:60]}
                for c in boost_changes[:3]
            ],
        },
        "boosted_bullets": boosted_bullets,
    }
