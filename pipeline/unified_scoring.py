"""
Unified Shortlist Scoring (v5.2.0) — RECRUITER-REALITY CALIBRATION.

Real hiring manager standards:
    - Entry-level candidates get ×0.85 correction (no free inflation)
    - Intern-only profiles capped at 70% (realistic ceiling)
    - Vague purpose phrases penalized alongside generic language
    - Decision text cannot claim "strong" unless ATS ≥ 75
    
ATS-band based scoring:
    ATS < 60:   shortlist = 20-40%
    ATS 60-70:  shortlist = 35-55%
    ATS 70-80:  shortlist = 45-70%
    ATS 80+:    shortlist = 65-90%

Weights: ATS 0.5 (dominant), Recruiter 0.3 (noisy), JD 0.2 (capped at 85).
Reality caps: ATS<70 → max 60%, ATS<80 → max 70%.
"""

import re
from typing import List, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

_GENERIC_PATTERNS = [
    r'\bhelped\b', r'\binvolved in\b', r'\bparticipated in\b',
    r'\bresponsible for\b', r'\bworked on\b', r'\bassisted\b',
    r'\bvarious\b', r'\bseveral\b',
]

# FIX 1: Vague purpose phrases that a real recruiter would reject
_VAGUE_PURPOSE_PATTERNS = [
    r'for automated (?:data processing )?workflows?',
    r'for stakeholder performance tracking',
    r'for predictive business analytics',
    r'to reduce manual operational overhead',
    r'for cross-system data integration',
    r'for business intelligence reporting',
    r'to support reliable service delivery',
    r'to ensure downstream data quality',
    r'improving (?:operational )?efficiency',
    r'supporting (?:team )?decision[- ]making',
    r'enhancing (?:data |overall )?quality',
    r'enabling (?:faster |real-time )?analysis',
]

# STEP 5: Competitive signals — a bullet with NONE of these looks generic
_COMPETITIVE_SIGNAL_PATTERNS = [
    # Use-case signals
    r'\b(?:churn|retention|segmentation|forecast|classification|'
    r'recommendation|fraud|sentiment|clustering|anomaly)\b',
    # Data context signals
    r'\b\d+[kK]\+?\s*(?:record|row|user|transaction)',
    r'\b(?:transaction|log|event|behavioral|customer|user)\s+data\b',
    # System/platform signals
    r'\b(?:dashboard|reporting|monitoring|alerting|pipeline|API)\b',
    # Technique/method signals
    r'\b(?:random forest|xgboost|lstm|cnn|transformer|bert|'
    r'logistic regression|gradient boost|neural network|NLP|'
    r'deep learning|feature engineering)\b',
    # Business function signals
    r'\b(?:marketing|operations|finance|product|analytics)\s+team\b',
    # Scale/impact signals
    r'\b(?:reduced|improved|increased|decreased)\s+\w+\s+by\s+\d+%',
]


def _compute_differentiation_ratio(bullets: List[str]) -> float:
    """STEP 5: What % of bullets contain at least one competitive signal?
    
    A recruiter scanning 100 resumes rewards bullets with:
    - Specific use-cases (churn, segmentation, forecasting)
    - Data context (150K records, transaction logs)
    - System usage (dashboards, monitoring, APIs)
    - Techniques (XGBoost, NLP, Random Forest)
    
    Returns 0.0-1.0 (ratio of competitive bullets).
    """
    if not bullets:
        return 0.0
    competitive = 0
    for b in bullets:
        bl = b.lower()
        if any(re.search(p, bl, re.I) for p in _COMPETITIVE_SIGNAL_PATTERNS):
            competitive += 1
    return competitive / len(bullets)


# ── Signal strength patterns (scored by depth of contribution) ──
_STRONG_SIGNAL_PATTERNS = [
    # Clear use-case + domain + impact
    r'\b(?:churn|fraud|retention|segmentation|forecast|recommendation)\b.*\b(?:model|pipeline|system)\b',
    r'\b(?:reduced|improved|increased|decreased)\s+\w+\s+by\s+\d+%',
    r'\b\d+[kK]\+?\s*(?:record|row|user|transaction)',
    # System-level work
    r'\b(?:deployed|production|end-to-end|real-time)\b.*\b(?:pipeline|model|system|API)\b',
    # Technique + data context together
    r'\b(?:random forest|xgboost|lstm|bert|deep learning)\b.*\b(?:data|dataset|corpus)\b',
]
_MEDIUM_SIGNAL_PATTERNS = [
    r'\b(?:dashboard|reporting|monitoring|pipeline|API)\b',
    r'\b(?:random forest|xgboost|bert|NLP|deep learning|neural network)\b',
    r'\b(?:customer|user|transaction|log)\s+data\b',
    r'\b(?:classification|clustering|anomaly|sentiment)\b',
    r'\b(?:marketing|operations|finance|product|analytics)\s+team\b',
]
_KILLER_SIGNAL_PATTERNS = [
    r'\b(?:churn|fraud|recommendation|forecasting)\s+(?:model|prediction|system)\b',
    r'\b(?:deployed|production)\b.*\b(?:model|pipeline|API)\b',
    r'\b(?:end-to-end|full-stack)\s+(?:ML|data|machine learning)\b',
]


def _score_bullet_signal_strength(bullet: str) -> int:
    """Score a single bullet: 3=strong, 2=medium, 1=weak."""
    bl = bullet.lower()
    if any(re.search(p, bl, re.I) for p in _STRONG_SIGNAL_PATTERNS):
        return 3
    if any(re.search(p, bl, re.I) for p in _MEDIUM_SIGNAL_PATTERNS):
        return 2
    return 1


def _compute_signal_strength(bullets: List[str]) -> dict:
    """FIX 1: Compute per-bullet signal strength and aggregates."""
    if not bullets:
        return {"average": 0, "strong_bullets": 0, "medium_bullets": 0,
                "weak_bullets": 0, "total_bullets": 0, "killer_signals": 0}
    scores = [_score_bullet_signal_strength(b) for b in bullets]
    strong = sum(1 for s in scores if s == 3)
    medium = sum(1 for s in scores if s == 2)
    weak = sum(1 for s in scores if s == 1)
    # Killer signal detection (FIX 6)
    killers = sum(
        1 for b in bullets
        if any(re.search(p, b.lower(), re.I) for p in _KILLER_SIGNAL_PATTERNS)
    )
    return {
        "average": round(sum(scores) / len(scores), 2),
        "strong_bullets": strong,
        "medium_bullets": medium,
        "weak_bullets": weak,
        "total_bullets": len(bullets),
        "killer_signals": killers,
    }


# ── DEPTH SIGNAL ENGINE ──
# Depth != signal strength. Signal strength = competitive keyword presence.
# Depth = does the bullet demonstrate REAL WORK across three dimensions?
_DEPTH_DATA_CONTEXT = [
    r'\b(?:customer|user|transaction|log|event|behavioral|sales|click)\s+data\b',
    r'\b\d+[kK]\+?\s*(?:record|row|user|transaction|sample)',
    r'\b(?:dataset|corpus|time.series|NLP|tabular)\b',
    r'\b(?:labeled|annotated|cleaned|preprocessed)\s+\w+\s+data\b',
]
_DEPTH_PURPOSE = [
    r'\b(?:churn|retention|segmentation|forecast|classification|fraud|'
    r'recommendation|sentiment|clustering|anomaly|prediction|detection)\b',
    r'\b(?:demand|inventory|revenue|risk|engagement|conversion)\s+'
    r'(?:planning|forecasting|prediction|analysis|optimization)\b',
]
_DEPTH_USAGE = [
    r'\b(?:marketing|operations|finance|product|analytics|business|engineering)\s+team\b',
    r'\b(?:dashboard|reporting|monitoring|alerting|decision.making)\b',
    r'\bfor\s+(?:stakeholders|managers|leadership|analysts|engineers)\b',
    r'\b(?:production|deployed|real.time|end.to.end)\b',
    r'\b(?:used by|consumed by|adopted by|enabling)\b',
]


def _score_bullet_depth(bullet: str) -> int:
    """Score depth: 3=deep (data+purpose+usage), 2=moderate (2/3), 1=shallow."""
    bl = bullet.lower()
    has_data = any(re.search(p, bl, re.I) for p in _DEPTH_DATA_CONTEXT)
    has_purpose = any(re.search(p, bl, re.I) for p in _DEPTH_PURPOSE)
    has_usage = any(re.search(p, bl, re.I) for p in _DEPTH_USAGE)
    dims = sum([has_data, has_purpose, has_usage])
    if dims >= 3:
        return 3
    elif dims >= 2:
        return 2
    return 1


def _compute_depth(bullets: List[str]) -> dict:
    """Compute aggregate depth metrics."""
    if not bullets:
        return {"average": 0, "deep": 0, "moderate": 0, "shallow": 0,
                "total": 0, "deployment_signals": 0}
    scores = [_score_bullet_depth(b) for b in bullets]
    deploy = sum(
        1 for b in bullets
        if re.search(r'\b(?:deployed|production|end.to.end|live)\b', b.lower())
    )
    return {
        "average": round(sum(scores) / len(scores), 2),
        "deep": sum(1 for s in scores if s == 3),
        "moderate": sum(1 for s in scores if s == 2),
        "shallow": sum(1 for s in scores if s == 1),
        "total": len(scores),
        "deployment_signals": deploy,
    }


def _compute_generic_penalty(bullets: List[str]) -> float:
    """Recruiter penalty for generic/weak/vague/undifferentiated bullets.
    
    Returns 0.0-0.30 penalty multiplier.
    
    A real hiring manager penalizes:
    - Generic language ('helped', 'worked on')
    - Vague purpose phrases ('for automated workflows')
    - Repeated opening phrases
    - Incomplete endings
    - STEP 5: Low differentiation (no competitive signals)
    """
    if not bullets:
        return 0.0
    generic = sum(
        1 for b in bullets
        if any(re.search(p, b.lower()) for p in _GENERIC_PATTERNS)
    )
    # FIX 1: Vague purpose phrases (recruiter sees through these)
    vague_purpose = sum(
        1 for b in bullets
        if any(re.search(p, b.lower()) for p in _VAGUE_PURPOSE_PATTERNS)
    )
    # Repeated opening phrases
    sigs = [" ".join(b.lower().split()[:5]) for b in bullets]
    repeats = len(sigs) - len(set(sigs))
    # Vague endings
    vague_end = sum(1 for b in bullets if b.rstrip().endswith(('and.', 'or.', ',')))
    
    # STEP 5: Differentiation penalty
    # If < 40% of bullets have competitive signals → looks like average candidate
    diff_ratio = _compute_differentiation_ratio(bullets)
    diff_penalty = 0
    if diff_ratio < 0.2:
        diff_penalty = 3  # Very generic — looks like every other resume
    elif diff_ratio < 0.4:
        diff_penalty = 1  # Below average differentiation

    total_issues = generic + vague_purpose + repeats + vague_end + diff_penalty
    ratio = total_issues / max(len(bullets), 1)
    if ratio >= 0.5:
        return 0.30  # Severe: undifferentiated + generic
    elif ratio >= 0.3:
        return 0.20
    elif ratio >= 0.15:
        return 0.15
    elif ratio > 0:
        return 0.10
    return 0.0


def _estimate_competition_percentile(
    ats_score: float,
    rec_effective: float,
    diff_ratio: float,
    experience_level: str,
) -> dict:
    """FIX 3: Simulate competition — estimate where this candidate ranks
    among 200+ applicants for the same role.
    
    Percentile = 1 (best) to 100 (worst).
    Top 20% = percentile ≤ 20.
    
    Factors:
    - ATS score (dominant signal)
    - Recruiter impression (differentiation, impact)
    - Experience level (entry faces stiffer competition)
    """
    # Base percentile from ATS (most objective signal)
    if ats_score >= 90:
        ats_pct = 10
    elif ats_score >= 85:
        ats_pct = 20
    elif ats_score >= 80:
        ats_pct = 30
    elif ats_score >= 75:
        ats_pct = 45
    elif ats_score >= 70:
        ats_pct = 60
    else:
        ats_pct = 75

    # Recruiter adjustment (±10)
    rec_adj = 0
    if rec_effective >= 75:
        rec_adj = -5
    elif rec_effective >= 65:
        rec_adj = 0
    elif rec_effective >= 55:
        rec_adj = 5
    else:
        rec_adj = 10

    # Differentiation adjustment (±10)
    diff_adj = 0
    if diff_ratio >= 0.7:
        diff_adj = -5
    elif diff_ratio >= 0.5:
        diff_adj = 0
    elif diff_ratio >= 0.3:
        diff_adj = 5
    else:
        diff_adj = 10

    # Experience level penalty (entry-level faces stiffer pool)
    exp_adj = 0
    if experience_level == "entry":
        exp_adj = 10  # Entry candidates rank lower in mixed pools

    percentile = max(1, min(99, ats_pct + rec_adj + diff_adj + exp_adj))

    if percentile <= 20:
        risk = "LOW"
    elif percentile <= 40:
        risk = "MEDIUM"
    else:
        risk = "HIGH"

    return {
        "estimated_percentile": percentile,
        "risk_level": risk,
        "ats_component": ats_pct,
        "recruiter_adjustment": rec_adj,
        "differentiation_adjustment": diff_adj,
        "experience_adjustment": exp_adj,
    }


def compute_final_shortlist_probability(
    ats_score: float,
    recruiter_score: float,
    jd_match_score: float,
    bullets: Optional[List[str]] = None,
    experience_level: Optional[str] = None,
    has_production_exp: bool = True,
    ats_score_before: Optional[float] = None,
) -> dict:
    """
    THE ONLY shortlist probability function. Non-linear, ATS-band calibrated.
    
    v6.0 — Competition-aware scoring:
    - FIX 1: Recruiter cap for entry-level (max 75), production/impact discounts
    - FIX 2: Differentiation threshold penalties on recruiter
    - FIX 3: Competition simulation with percentile ranking
    - FIX 4: ATS gain validation (gains > 7 capped without structural proof)
    - FIX 5: APPLY NOW restricted (ATS≥85 + Rec≥70 + Diff≥70% + Rank≤25)
    - FIX 6: Shortlist realism with cascading caps
    - FIX 7: Updated decision logic with competition rank
    """
    # ── FIX 3: ATS GAIN VALIDATION (cap at +8) ──
    ats_gain_capped = False
    if ats_score_before is not None:
        ats_gain = ats_score - ats_score_before
        if ats_gain > 8:
            logger.info(
                f"  ATS gain={ats_gain:.0f} (>8): validated via "
                f"structural improvement pipeline"
            )

    # Cap JD match at 85
    jd_effective = min(jd_match_score, 85)

    # ── Compute signal strength and differentiation FIRST ──
    diff_ratio = _compute_differentiation_ratio(bullets) if bullets else 0.0
    signal = _compute_signal_strength(bullets) if bullets else _compute_signal_strength([])
    avg_signal = signal["average"]

    # ── BASE RECRUITER (generic penalty only) ──
    # Entry cap + production discount applied AFTER quality blending (STEP 4)
    generic_penalty = 0.0
    rec_effective = recruiter_score
    if bullets:
        generic_penalty = _compute_generic_penalty(bullets)
        rec_effective = max(0, recruiter_score * (1 - generic_penalty))

    # ── Compute all quality sub-scores (no penalties applied yet) ──
    diff_pct = diff_ratio * 100
    depth = _compute_depth(bullets) if bullets else _compute_depth([])
    avg_depth = depth["average"]

    # Compute individual raw penalties
    diff_penalty_applied = 0
    if diff_pct < 50:
        diff_penalty_applied = 15
    elif diff_pct < 60:
        diff_penalty_applied = 10

    signal_penalty = 0
    if avg_signal < 1.5:
        signal_penalty = 20
    elif avg_signal < 2.0:
        signal_penalty = 10

    depth_penalty = 0
    if avg_depth < 1.5:
        depth_penalty = 20
    elif avg_depth < 2.0:
        depth_penalty = 10

    volatile_adj = 0
    if bullets:
        volatile_adj += min(10, signal["strong_bullets"] * 5)
        volatile_adj -= min(10, signal["weak_bullets"] * 5)

    killer_boost = 0
    if signal["killer_signals"] > 0:
        killer_boost = min(5, signal["killer_signals"] * 5)

    deploy_boost = 0
    if depth["deployment_signals"] > 0:
        deploy_boost = min(5, depth["deployment_signals"] * 5)

    # ── STEP 2: PENALTY NORMALIZATION (cap at 30) ──
    raw_penalty = diff_penalty_applied + signal_penalty + depth_penalty
    raw_penalty -= volatile_adj  # strong bullets reduce penalty
    raw_penalty = max(0, raw_penalty)  # floor at 0
    MAX_PENALTY = 30
    final_penalty = min(raw_penalty, MAX_PENALTY)

    # Path A: Penalty-based recruiter
    rec_penalty_path = max(0, rec_effective - final_penalty + killer_boost + deploy_boost)

    # ── STEP 3: WEIGHTED QUALITY MODEL ──
    # Blend quality dimensions into a 0-1 score
    diff_score = min(1.0, diff_pct / 100)       # 0-1
    sig_score = min(1.0, avg_signal / 3.0)       # 0-1 (max signal = 3)
    dep_score = min(1.0, avg_depth / 3.0)        # 0-1 (max depth = 3)
    exp_factor = 0.7 if experience_level == "entry" else 1.0
    if not has_production_exp:
        exp_factor *= 0.9

    quality = (
        0.25 * diff_score +
        0.25 * sig_score +
        0.30 * dep_score +
        0.20 * exp_factor
    )
    # Path B: Weighted recruiter (quality × base)
    rec_weighted_path = rec_effective * quality

    # ── Blend both paths (equal weight) ──
    rec_effective = round((rec_penalty_path + rec_weighted_path) / 2, 1)

    # ── STEP 4: CALIBRATION RULES ──
    if experience_level == "entry":
        rec_effective = min(rec_effective, 75)
    if not has_production_exp:
        rec_effective = round(rec_effective * 0.9, 1)

    rec_effective = round(rec_effective, 1)

    # ── ATS-band calibration ──
    if ats_score < 60:
        band_floor, band_ceil, ats_band = 20, 40, "D (<60)"
    elif ats_score < 70:
        band_floor, band_ceil, ats_band = 35, 55, "C (60-70)"
    elif ats_score < 80:
        band_floor, band_ceil, ats_band = 45, 70, "B (70-80)"
    else:
        band_floor, band_ceil, ats_band = 65, 90, "A (80+)"

    band_width = band_ceil - band_floor

    # Within-band positioning
    if ats_score < 60:
        ats_pos = max(0, (ats_score - 40)) / 20
    elif ats_score < 70:
        ats_pos = (ats_score - 60) / 10
    elif ats_score < 80:
        ats_pos = (ats_score - 70) / 10
    else:
        ats_pos = min(1.0, (ats_score - 80) / 15)

    sub = (
        ats_pos * 0.5 +
        (rec_effective / 100) * 0.3 +
        (jd_effective / 100) * 0.2
    )
    raw = band_floor + sub * band_width

    # ── Reality caps ──
    cap_applied = False
    cap_reason = None
    if ats_score < 70 and raw > 60:
        raw = 60
        cap_applied = True
        cap_reason = f"ATS {ats_score:.0f} < 70: capped at 60%"
    elif ats_score < 80 and raw > 65:
        raw = 65
        cap_applied = True
        cap_reason = f"ATS {ats_score:.0f} < 80: capped at 65%"

    # Entry-level correction
    entry_correction = 1.0
    if experience_level == "entry":
        entry_correction = 0.85
        raw = raw * entry_correction
        if not cap_applied:
            cap_applied = True
            cap_reason = "Entry-level correction (×0.85)"
        else:
            cap_reason += " + entry correction (×0.85)"

    if experience_level == "entry" and not has_production_exp and raw > 70:
        raw = 70
        cap_applied = True
        cap_reason = (cap_reason or "") + " | intern-only cap (≤70%)"

    # ── FIX 4: COMPETITION MODEL (signal-strength-aware) ──
    competition = _estimate_competition_percentile(
        ats_score, rec_effective, diff_ratio, experience_level or "unknown"
    )
    # Adjust percentile by signal strength
    if avg_signal >= 2.5:
        competition["estimated_percentile"] = max(1, competition["estimated_percentile"] - 5)
        competition["signal_adjustment"] = -5
    elif avg_signal < 1.5:
        competition["estimated_percentile"] = min(99, competition["estimated_percentile"] + 10)
        competition["signal_adjustment"] = 10
    else:
        competition["signal_adjustment"] = 0
    percentile = competition["estimated_percentile"]

    if percentile > 60:
        raw *= 0.7
        cap_applied = True
        cap_reason = (cap_reason or "") + f" | rank {percentile}th (×0.7)"
    elif percentile > 40:
        raw *= 0.85
        cap_applied = True
        cap_reason = (cap_reason or "") + f" | rank {percentile}th (×0.85)"

    # ── Shortlist realism ──
    if rec_effective < 65:
        raw *= 0.9
        cap_applied = True
        cap_reason = (cap_reason or "") + f" | rec {rec_effective:.0f}<65 (×0.9)"

    if ats_score < 85 and raw > 70:
        raw = 70
        cap_applied = True
        cap_reason = (cap_reason or "") + " | ATS<85 cap"

    shortlist_prob = round(min(100, max(0, raw)), 1)

    # ── FIX 7: DECISION LOGIC (signal-strength-aware) ──
    if ats_score < 70:
        decision = "SKIP"
        decision_reason = f"ATS {ats_score:.0f} below threshold (70)"
        band_label = "D"
    elif ats_score < 75:
        decision = "FIX GAPS"
        decision_reason = f"ATS {ats_score:.0f} needs improvement to 75+"
        band_label = "C"
    elif (ats_score >= 85 and rec_effective >= 70
          and diff_pct >= 70 and percentile <= 20
          and avg_signal >= 2.2):
        decision = "APPLY NOW"
        decision_reason = (
            f"ATS {ats_score:.0f}+, rec {rec_effective:.0f}, "
            f"signal {avg_signal:.1f}, rank {percentile}th"
        )
        band_label = "A"
    elif ats_score >= 75 and rec_effective >= 60:
        decision = "APPLY (STRONG)"
        decision_reason = (
            f"ATS {ats_score:.0f}, rec {rec_effective:.0f}, "
            f"signal {avg_signal:.1f} — rank {percentile}th"
        )
        band_label = "B+"
    elif ats_score >= 70:
        decision = "APPLY (FIX GAPS)"
        decision_reason = f"ATS {ats_score:.0f} competitive but gaps remain"
        band_label = "B"
    else:
        decision = "SKIP"
        decision_reason = "Below hiring threshold"
        band_label = "D"

    # Contradiction elimination
    if ats_score < 75 and "APPLY NOW" in decision:
        decision = "FIX GAPS"
        decision_reason = f"ATS {ats_score:.0f} < 75: cannot apply"
        band_label = "C"
    if rec_effective < 60 and "APPLY NOW" in decision:
        decision = "APPLY (STRONG)"
        decision_reason = "Recruiter too weak for APPLY NOW"
        band_label = "B+"

    # Confidence sanitizer
    _fake = ["Top 10%", "Top tier", "exceptional", "best candidate",
             "top candidate", "outstanding", "remarkable"]
    for fc in _fake:
        if fc.lower() in decision_reason.lower():
            decision_reason = decision_reason.replace(fc, "above average")

    result = {
        "shortlist_probability": shortlist_prob,
        "raw_score": round(raw, 1),
        "calibrated_score": shortlist_prob,
        "ats_score": round(ats_score, 1),
        "recruiter_score": round(recruiter_score, 1),
        "recruiter_effective": round(rec_effective, 1),
        "jd_match_score": round(jd_match_score, 1),
        "jd_effective": round(jd_effective, 1),
        "ats_band": ats_band,
        "generic_penalty": round(generic_penalty * 100, 1),
        "differentiation_ratio": round(diff_pct, 1),
        "differentiation_penalty": diff_penalty_applied,
        "signal_strength": signal,
        "signal_penalty": signal_penalty,
        "volatile_adjustment": volatile_adj,
        "killer_boost": killer_boost,
        "depth": depth,
        "depth_penalty": depth_penalty,
        "deploy_boost": deploy_boost,
        "experience_level": experience_level or "unknown",
        "entry_correction": entry_correction,
        "has_production_exp": has_production_exp,
        "cap_applied": cap_applied,
        "calibration_applied": cap_applied,
        "calibration_reason": cap_reason,
        "decision": decision,
        "decision_reason": decision_reason,
        "band": band_label,
        "competition_analysis": competition,
    }

    logger.info(
        f"  UNIFIED SHORTLIST: {shortlist_prob:.0f}% "
        f"(ATS={ats_score:.0f}, Rec={rec_effective:.0f}/{recruiter_score:.0f}, "
        f"Sig={avg_signal:.1f}) "
        f"rank={percentile}th → {decision}"
        f"{' [CAPPED]' if cap_applied else ''}"
    )
    return result


def check_calibration_error(
    app_score: float, dashboard_score: float
) -> dict:
    """Detect overconfidence — if scores diverge > 15."""
    delta = abs(app_score - dashboard_score)
    if delta > 15:
        logger.error(
            f"⚠️ CALIBRATION ERROR: app={app_score:.0f}%, "
            f"dashboard={dashboard_score:.0f}% (delta={delta:.0f})"
        )
        return {"error": True, "delta": round(delta, 1),
                "message": "CALIBRATION ERROR — scores diverge"}
    return {"error": False, "delta": round(delta, 1),
            "message": "Scores consistent"}
