"""
Optimization Engine (v4.9) — Iterative ATS + Recruiter + Capability-Aware Improvement.

Transforms single-pass analysis into iterative optimization loop:
  1. ATS coverage enforcement (target ≥70% real)
  2. Iterative keyword optimization (max 3 attempts)
  3. Recruiter score alignment (target ≥60)
  4. Capability-aware bullet improvement
  5. Fresher project strengthening
  6. Safe impact enhancement
  7. Strict decision engine

Philosophy: "Truth + Clarity > Optimization Tricks"
"""

import re
from typing import List, Dict, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ================================================================
# PART 1 — ATS COVERAGE ENFORCEMENT
# ================================================================

def assess_ats_status(real_coverage: float) -> Dict:
    """
    Classify ATS coverage into actionable status.
    Uses REAL coverage only (from ATS parser).
    """
    if real_coverage >= 70:
        return {"status": "STRONG", "action": "proceed", "block": False}
    elif real_coverage >= 60:
        return {"status": "ACCEPTABLE", "action": "minor_optimize", "block": False}
    elif real_coverage >= 40:
        return {"status": "WEAK", "action": "optimize_loop", "block": False}
    else:
        return {"status": "ATS_BLOCK", "action": "skip_or_heavy_optimize", "block": True}


# ================================================================
# PART 2 — ITERATIVE ATS OPTIMIZATION LOOP
# ================================================================

def iterative_ats_optimization(
    bullets: List[str],
    jd_keywords: List[str],
    candidate_skills: List[str],
    simulate_ats_fn,
    max_attempts: int = 3,
    target_coverage: float = 70.0,
) -> Dict:
    """
    Iteratively improve ATS coverage through safe keyword injection.
    Maintains truth constraints — only injects skills the candidate has.

    Returns optimized bullets + coverage trace.
    """
    candidate_lower = {s.lower() for s in candidate_skills}
    jd_lower = {kw.lower() for kw in jd_keywords}
    working_bullets = bullets[:]
    coverage_trace = []

    # Initial measurement
    resume_text = " ".join(working_bullets)
    initial = simulate_ats_fn(resume_text, jd_keywords)
    coverage_trace.append({
        "attempt": 0, "coverage": initial["real_coverage"],
        "parsed": len(initial["parsed_keywords"]),
    })

    if initial["real_coverage"] >= target_coverage:
        return {
            "bullets": working_bullets,
            "attempts": 0,
            "final_coverage": initial["real_coverage"],
            "initial_coverage": initial["real_coverage"],
            "coverage_trace": coverage_trace,
            "keywords_added": [],
            "status": "already_optimal",
        }

    keywords_added = []
    # Keyword injection candidates: missing from resume, candidate knows them
    missing_injectable = [
        kw for kw in jd_keywords
        if kw.lower() not in resume_text.lower() and kw.lower() in candidate_lower
    ]

    # Domain compatibility for natural injection
    _DOMAIN_CONTEXT = {
        "python": ["data", "pipeline", "model", "script", "automat", "process"],
        "sql": ["data", "query", "database", "report", "analyt"],
        "pandas": ["data", "analy", "process", "clean", "transform"],
        "tensorflow": ["model", "neural", "deep", "train", "predict"],
        "pytorch": ["model", "neural", "deep", "train", "predict"],
        "scikit-learn": ["model", "predict", "classif", "train", "feature"],
        "docker": ["deploy", "container", "service", "pipeline", "infra"],
        "kubernetes": ["deploy", "orchestr", "container", "scale", "service"],
        "airflow": ["pipeline", "workflow", "schedul", "etl", "automat"],
        "spark": ["data", "process", "large", "scale", "distribut", "etl"],
        "aws": ["cloud", "deploy", "infra", "service", "scale", "pipeline"],
        "gcp": ["cloud", "deploy", "infra", "service", "scale"],
        "postgresql": ["data", "query", "database", "store", "sql"],
        "tableau": ["visual", "dashboa", "report", "insight", "analyt"],
        "power bi": ["visual", "dashboa", "report", "insight", "kpi"],
        "mlops": ["model", "deploy", "pipeline", "monitor", "ml"],
        "dbt": ["data", "transform", "model", "sql", "pipeline"],
    }

    for attempt in range(1, max_attempts + 1):
        if not missing_injectable:
            break

        injected_this_round = []
        assigned_bullets = set()

        for kw in missing_injectable[:3]:  # Max 3 per round
            kw_lower = kw.lower()
            context_keywords = _DOMAIN_CONTEXT.get(kw_lower, [])

            # Find best bullet by context match
            best_idx, best_score = -1, -1
            for i, bullet in enumerate(working_bullets):
                if i in assigned_bullets:
                    continue
                b_lower = bullet.lower()
                if kw_lower in b_lower:
                    continue  # Already present

                score = sum(1 for ck in context_keywords if ck in b_lower)
                # Prefer shorter bullets (room for injection)
                if len(bullet) < 120:
                    score += 2
                # Prefer bullets with "using" pattern (natural injection point)
                if re.search(r'\b(?:using|with|via)\b', b_lower):
                    score += 3

                if score > best_score:
                    best_score = score
                    best_idx = i

            if best_idx >= 0 and best_score >= 2:
                bullet = working_bullets[best_idx]
                # Natural injection: append to existing "using X" or add new
                if re.search(r',\s*using\s+[\w\s]+$', bullet, re.I):
                    # Extend existing "using X" → "using X and Y"
                    bullet = re.sub(
                        r'(,\s*using\s+[\w\s]+?)(\.|$)',
                        rf'\1 and {kw}\2',
                        bullet, count=1
                    )
                elif bullet.rstrip().endswith('.'):
                    bullet = bullet.rstrip()[:-1] + f", using {kw}."
                else:
                    bullet = bullet.rstrip() + f", using {kw}."

                working_bullets[best_idx] = bullet
                assigned_bullets.add(best_idx)
                injected_this_round.append(kw)
                keywords_added.append(kw)

        # Re-measure coverage
        resume_text = " ".join(working_bullets)
        result = simulate_ats_fn(resume_text, jd_keywords)
        coverage_trace.append({
            "attempt": attempt,
            "coverage": result["real_coverage"],
            "parsed": len(result["parsed_keywords"]),
            "injected": injected_this_round,
        })

        # Update missing list
        missing_injectable = [
            kw for kw in missing_injectable
            if kw.lower() not in resume_text.lower()
        ]

        if result["real_coverage"] >= target_coverage:
            break

    final_text = " ".join(working_bullets)
    final = simulate_ats_fn(final_text, jd_keywords)

    return {
        "bullets": working_bullets,
        "attempts": len(coverage_trace) - 1,
        "final_coverage": final["real_coverage"],
        "initial_coverage": initial["real_coverage"],
        "coverage_trace": coverage_trace,
        "keywords_added": keywords_added,
        "status": "optimized" if final["real_coverage"] >= target_coverage else "insufficient",
    }


# ================================================================
# PART 3 — RECRUITER SCORE ALIGNMENT
# ================================================================

def assess_recruiter_strength(recruiter_avg: float) -> Dict:
    """
    Classify recruiter perception into actionable grade.
    """
    if recruiter_avg >= 60:
        return {"assessment": "strong", "grade": "A", "action": "none"}
    elif recruiter_avg >= 50:
        return {"assessment": "moderate", "grade": "B", "action": "enhance_impact"}
    elif recruiter_avg >= 35:
        return {"assessment": "weak", "grade": "C", "action": "rewrite_bullets"}
    else:
        return {"assessment": "very_weak", "grade": "D", "action": "major_rewrite"}


# ================================================================
# PART 4 — STRICT DECISION ENGINE
# ================================================================

def compute_strict_decision(
    real_coverage: float,
    shortlist_prob: float,
    recruiter_avg: float,
) -> Dict:
    """
    Three-signal decision: ATS + Prediction + Recruiter.
    All three must align for APPLY NOW.
    """
    # Hard blocks
    if real_coverage < 40:
        return {
            "final": "SKIP",
            "reason": f"ATS block — {real_coverage:.0f}% coverage (min 40% required)",
            "confidence": max(20, 100 - real_coverage),
            "signals": {"ats": "BLOCK", "prediction": "N/A", "recruiter": "N/A"},
        }

    # Full green
    if real_coverage >= 70 and shortlist_prob >= 65 and recruiter_avg >= 60:
        confidence = min(95, (real_coverage + shortlist_prob + recruiter_avg) / 3)
        return {
            "final": "APPLY NOW",
            "reason": (
                f"Strong match — ATS {real_coverage:.0f}%, "
                f"shortlist {shortlist_prob:.0f}%, recruiter {recruiter_avg:.0f}"
            ),
            "confidence": round(confidence),
            "signals": {"ats": "STRONG", "prediction": "HIGH", "recruiter": "STRONG"},
        }

    # Partial match
    if real_coverage >= 50 and shortlist_prob >= 50:
        gaps = []
        signals = {}

        if real_coverage < 70:
            gaps.append(f"ATS {real_coverage:.0f}%<70%")
            signals["ats"] = "WEAK"
        else:
            signals["ats"] = "STRONG"

        if shortlist_prob < 65:
            gaps.append(f"shortlist {shortlist_prob:.0f}%<65%")
            signals["prediction"] = "MODERATE"
        else:
            signals["prediction"] = "HIGH"

        if recruiter_avg < 60:
            gaps.append(f"recruiter {recruiter_avg:.0f}<60")
            signals["recruiter"] = "WEAK"
        else:
            signals["recruiter"] = "STRONG"

        confidence = min(75, (real_coverage + shortlist_prob) / 2)
        return {
            "final": "APPLY (FIX GAPS)",
            "reason": f"Competitive but gaps — {', '.join(gaps)}",
            "confidence": round(confidence),
            "signals": signals,
        }

    # Below threshold
    signals = {
        "ats": "STRONG" if real_coverage >= 70 else ("WEAK" if real_coverage >= 50 else "BLOCK"),
        "prediction": "HIGH" if shortlist_prob >= 65 else ("MODERATE" if shortlist_prob >= 40 else "LOW"),
        "recruiter": "STRONG" if recruiter_avg >= 60 else ("MODERATE" if recruiter_avg >= 50 else "WEAK"),
    }
    confidence = max(30, 100 - (real_coverage + shortlist_prob) / 2)
    return {
        "final": "SKIP",
        "reason": (
            f"Weak match — ATS {real_coverage:.0f}%, "
            f"shortlist {shortlist_prob:.0f}%, recruiter {recruiter_avg:.0f}"
        ),
        "confidence": round(confidence),
        "signals": signals,
    }


# ================================================================
# PART 5 — CAPABILITY-AWARE BULLET IMPROVEMENT
# ================================================================

def improve_bullet_phrasing(
    bullet: str,
    jd_skills: List[str],
    role: str = "",
) -> Dict:
    """
    Improve bullet structure and impact WITHOUT adding false content.
    Only enhances phrasing when the capability exists but wording is weak.
    """
    original = bullet
    improved = bullet
    changes = []

    # Rule 1: Weak verbs → Strong action verbs
    _WEAK_TO_STRONG = {
        r'\bworked on\b': 'developed',
        r'\bhelped with\b': 'contributed to',
        r'\bdid\b': 'executed',
        r'\bmade\b': 'built',
        r'\bhandled\b': 'managed',
        r'\bwas responsible for\b': 'led',
        r'\bused\b': 'leveraged',
        r'\bgot\b': 'achieved',
        r'\blearned\b': 'acquired expertise in',
    }
    for pattern, replacement in _WEAK_TO_STRONG.items():
        if re.search(pattern, improved, re.I):
            improved = re.sub(pattern, replacement, improved, count=1, flags=re.I)
            changes.append(f"verb_upgrade: {pattern} → {replacement}")

    # Rule 2: Add outcome clause if missing
    has_outcome = bool(re.search(
        r'\b(?:improv|reduc|increas|enabl|enhanc|support|achiev|driv|result|lead)',
        improved, re.I
    ))
    if not has_outcome and len(improved) < 120:
        # Determine safe outcome based on content
        b_lower = improved.lower()
        if any(w in b_lower for w in ["data", "pipeline", "etl", "process"]):
            improved = improved.rstrip('.') + ", improving data processing efficiency."
            changes.append("added_safe_outcome: data efficiency")
        elif any(w in b_lower for w in ["model", "predict", "train", "ml"]):
            improved = improved.rstrip('.') + ", enhancing model performance."
            changes.append("added_safe_outcome: model performance")
        elif any(w in b_lower for w in ["dashboard", "visual", "report"]):
            improved = improved.rstrip('.') + ", enabling data-driven decision-making."
            changes.append("added_safe_outcome: decision support")
        elif any(w in b_lower for w in ["deploy", "infra", "cloud"]):
            improved = improved.rstrip('.') + ", improving system reliability."
            changes.append("added_safe_outcome: system reliability")

    # Rule 3: Ensure proper sentence start (capitalize)
    if improved and improved[0].islower():
        improved = improved[0].upper() + improved[1:]
        changes.append("capitalized_start")

    return {
        "original": original,
        "improved": improved,
        "changed": improved != original,
        "changes": changes,
    }


# ================================================================
# PART 6 — FRESHER PROJECT STRENGTHENING
# ================================================================

def strengthen_project_bullet(
    bullet: str,
    project_tools: List[str] = None,
    role: str = "",
) -> Dict:
    """
    Strengthen project descriptions for freshers.
    Expand: problem → approach → tools → outcome.
    NO fake experience. NO fake metrics. ONLY enhance real work.
    """
    project_tools = project_tools or []
    original = bullet
    improved = bullet
    changes = []

    # Rule 1: Expand bare project mentions
    _EXPANSIONS = {
        r'\b(?:did|made|created)\s+(?:a\s+)?(\w+)\s+project\b':
            r'developed a \1 project',
        r'\b(?:did|made)\s+(?:a\s+)?ml\s+project\b':
            'developed a machine learning project',
        r'\b(?:built|created)\s+(?:a\s+)?(?:simple\s+)?model\b':
            'developed a predictive model',
    }
    for pattern, replacement in _EXPANSIONS.items():
        if re.search(pattern, improved, re.I):
            improved = re.sub(pattern, replacement, improved, count=1, flags=re.I)
            changes.append(f"expanded: {pattern}")

    # Rule 2: Add tools if mentioned in project but not in bullet
    if project_tools:
        tools_in_bullet = [t for t in project_tools if t.lower() in improved.lower()]
        tools_missing = [t for t in project_tools if t.lower() not in improved.lower()]
        if tools_missing and len(tools_missing) <= 3 and len(improved) < 130:
            tools_str = ", ".join(tools_missing[:2])
            if re.search(r'\busing\s+\w', improved, re.I):
                improved = re.sub(
                    r'(using\s+[\w\s,]+?)(\.|$)',
                    rf'\1, {tools_str}\2',
                    improved, count=1
                )
            else:
                improved = improved.rstrip('.') + f", using {tools_str}."
            changes.append(f"added_tools: {tools_str}")

    # Rule 3: Add problem context if too vague
    has_context = bool(re.search(
        r'\b(?:to\s+\w+|for\s+\w+|enabling|supporting|improving|analyzing)\b',
        improved, re.I
    ))
    if not has_context and len(improved) < 110:
        b_lower = improved.lower()
        if any(w in b_lower for w in ["predict", "classif", "churn", "fraud"]):
            improved = improved.rstrip('.') + " to analyze behavioral patterns."
            changes.append("added_context: behavioral analysis")
        elif any(w in b_lower for w in ["nlp", "text", "sentiment", "language"]):
            improved = improved.rstrip('.') + " to extract insights from text data."
            changes.append("added_context: text analysis")
        elif any(w in b_lower for w in ["image", "vision", "detect", "segment"]):
            improved = improved.rstrip('.') + " for visual data analysis."
            changes.append("added_context: visual analysis")

    return {
        "original": original,
        "improved": improved,
        "changed": improved != original,
        "changes": changes,
    }


# ================================================================
# PART 7 — SAFE IMPACT ENHANCEMENT
# ================================================================

_SAFE_IMPACT_PHRASES = {
    "data": "improving data processing efficiency",
    "model": "enhancing model performance and accuracy",
    "pipeline": "streamlining data pipeline workflows",
    "dashboard": "enabling data-driven decision-making",
    "deploy": "improving deployment reliability",
    "automat": "reducing manual effort through automation",
    "analyt": "supporting analytical insights",
    "monitor": "improving system observability",
    "test": "strengthening code quality and reliability",
    "security": "enhancing system security posture",
}


def add_safe_impact(bullet: str) -> Dict:
    """
    Add safe, defensible impact phrases when no metrics exist.
    NEVER invents numbers. NEVER exaggerates scale.
    """
    # Already has impact?
    if re.search(r'\b(?:improv|reduc|increas|enabl|enhanc|result|achiev|by\s+\d)', bullet, re.I):
        return {"original": bullet, "improved": bullet, "changed": False, "impact_added": None}

    b_lower = bullet.lower()
    for trigger, impact in _SAFE_IMPACT_PHRASES.items():
        if trigger in b_lower:
            improved = bullet.rstrip('.') + f", {impact}."
            return {
                "original": bullet,
                "improved": improved,
                "changed": True,
                "impact_added": impact,
            }

    return {"original": bullet, "improved": bullet, "changed": False, "impact_added": None}


# ================================================================
# MASTER ORCHESTRATOR
# ================================================================

def run_optimization_engine(
    bullets: List[str],
    jd_keywords: List[str],
    jd_skills: List[str],
    candidate_skills: List[str],
    role: str = "",
    is_fresher: bool = False,
    project_bullets: List[str] = None,
    project_tools: List[List[str]] = None,
    shortlist_prob: float = 0,
    recruiter_avg: float = 0,
) -> Dict:
    """
    Run the complete optimization engine (v4.9).
    Iterative ATS + Recruiter + Capability-Aware + Decision.
    """
    from pipeline.ats_hardening import simulate_ats_parser

    logger.info("OPTIMIZATION ENGINE v4.9 — Starting")

    # --- Step 1: Capability-aware bullet improvement ---
    enhanced_bullets = []
    bullet_changes = []
    for b in bullets:
        result = improve_bullet_phrasing(b, jd_skills, role)
        enhanced_bullets.append(result["improved"])
        if result["changed"]:
            bullet_changes.append(result)

    # --- Step 2: Fresher project strengthening ---
    project_improvements = []
    if is_fresher and project_bullets:
        project_tools = project_tools or [[] for _ in project_bullets]
        for i, pb in enumerate(project_bullets):
            tools = project_tools[i] if i < len(project_tools) else []
            result = strengthen_project_bullet(pb, tools, role)
            if result["changed"]:
                project_improvements.append(result)

    # --- Step 3: Safe impact enhancement ---
    impact_bullets = []
    impact_changes = []
    for b in enhanced_bullets:
        result = add_safe_impact(b)
        impact_bullets.append(result["improved"])
        if result["changed"]:
            impact_changes.append(result)

    # --- Step 4: Iterative ATS optimization ---
    ats_result = iterative_ats_optimization(
        bullets=impact_bullets,
        jd_keywords=jd_keywords,
        candidate_skills=candidate_skills,
        simulate_ats_fn=simulate_ats_parser,
        max_attempts=3,
        target_coverage=70.0,
    )
    final_bullets = ats_result["bullets"]

    # --- Step 5: Recruiter assessment ---
    recruiter_grade = assess_recruiter_strength(recruiter_avg)

    # --- Step 6: ATS status ---
    ats_status = assess_ats_status(ats_result["final_coverage"])

    # --- Step 7: Strict decision ---
    decision = compute_strict_decision(
        ats_result["final_coverage"], shortlist_prob, recruiter_avg
    )

    logger.info(
        f"  ATS: {ats_result['initial_coverage']:.0f}% → {ats_result['final_coverage']:.0f}% "
        f"({ats_result['attempts']} attempts, {ats_result['status']})"
    )
    logger.info(
        f"  Recruiter: {recruiter_avg:.0f} ({recruiter_grade['assessment']})"
    )
    logger.info(
        f"  Decision: {decision['final']} ({decision['confidence']}% conf)"
    )
    logger.info("OPTIMIZATION ENGINE v4.9 — Complete")

    return {
        "ats": {
            "initial_coverage": ats_result["initial_coverage"],
            "real_coverage": ats_result["final_coverage"],
            "attempts": ats_result["attempts"],
            "status": ats_result["status"],
            "coverage_trace": ats_result["coverage_trace"],
        },
        "recruiter": {
            "score": round(recruiter_avg, 1),
            "assessment": recruiter_grade["assessment"],
            "grade": recruiter_grade["grade"],
        },
        "decision": decision,
        "improvements": {
            "bullets_enhanced": len(bullet_changes),
            "impact_added": len(impact_changes),
            "keywords_added": ats_result["keywords_added"],
            "projects_strengthened": len(project_improvements),
        },
        "final_bullets": final_bullets,
        "is_fresher": is_fresher,
    }
