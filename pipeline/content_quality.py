"""
Content Quality Engine (v4.5) — Recruiter-Level Impact Scoring.

Upgrades over v4.4:
  1. Proof Strength Scoring — dataset scale, model complexity, business relevance
  2. JD Alignment Scoring — skill overlap, role-specific language
  3. Role-Specific Rewrite Awareness — pipeline→modeling→deployment→impact
  4. ATS Optimization Check — keyword density, natural placement
  5. Enhanced Output — signal/proof/alignment/ATS deltas
  6. Combined Score Gate — rewrite ONLY if combined improves significantly

Philosophy: "Bullets must be clearly stronger to a hiring manager."
"""

import re
from typing import List, Dict
from utils.logger import setup_logger

logger = setup_logger(__name__)

WEAK_VERBS = {
    "worked", "helped", "did", "made", "used", "got", "put", "tried",
    "was", "had", "involved", "participated", "responsible", "assisted",
    "contributed", "looked", "ran", "handled", "set",
}

STRONG_VERBS = {
    "tier_1": {"built", "developed", "designed", "architected", "engineered",
               "created", "implemented", "established", "launched"},
    "tier_2": {"optimized", "automated", "streamlined", "reduced", "improved",
               "increased", "accelerated", "scaled", "migrated"},
    "tier_3": {"analyzed", "managed", "deployed", "integrated", "configured",
               "delivered", "executed", "maintained", "resolved", "led"},
}

ALL_STRONG = STRONG_VERBS["tier_1"] | STRONG_VERBS["tier_2"] | STRONG_VERBS["tier_3"]

# Role-specific lifecycle stages
ROLE_LIFECYCLE = {
    "data": ["pipeline", "modeling", "deployment", "impact"],
    "ml": ["data ingestion", "training", "evaluation", "serving"],
    "backend": ["architecture", "implementation", "testing", "deployment"],
    "devops": ["infrastructure", "automation", "monitoring", "scaling"],
    "frontend": ["design", "implementation", "testing", "optimization"],
}

# Minimum improvement threshold for rewrite to be accepted
MIN_COMBINED_IMPROVEMENT = 8


# ================================================================
# PART 1 — SIGNAL STRENGTH SCORING (retained from v4.4)
# ================================================================

def score_signal_strength(bullet: str, jd_skills: List[str] = None) -> Dict:
    """
    Score a bullet on 4 dimensions (0-25 each, total 0-100):
      - Clarity: starts with action verb, single sentence
      - Technical Depth: mentions tools/technologies
      - Outcome Visibility: has quantified impact or result
      - Role Alignment: overlaps with JD skills
    """
    jd_skills = jd_skills or []
    b_lower = bullet.lower()
    words = bullet.split()

    # 1. CLARITY (0-25)
    first_word = words[0].lower().rstrip("ed,.:") if words else ""
    starts_with_verb = first_word in ALL_STRONG
    is_single_sentence = bullet.count(".") <= 1
    no_weak_start = first_word not in WEAK_VERBS
    word_count = len(words)
    good_length = 8 <= word_count <= 25

    clarity = 0
    if starts_with_verb:
        clarity += 10
    elif no_weak_start:
        clarity += 5
    if is_single_sentence:
        clarity += 5
    if good_length:
        clarity += 5
    if bullet[0].isupper() if bullet else False:
        clarity += 5

    # 2. TECHNICAL DEPTH (0-25)
    tech_patterns = [
        r'\b(?:Python|SQL|Java|C\+\+|JavaScript|TypeScript|Go|Rust)\b',
        r'\b(?:AWS|GCP|Azure|Docker|Kubernetes|Terraform)\b',
        r'\b(?:Spark|Kafka|Airflow|dbt|PostgreSQL|MongoDB|Redis)\b',
        r'\b(?:React|Django|Flask|FastAPI|Spring|Node\.js)\b',
        r'\b(?:TensorFlow|PyTorch|scikit-learn|Pandas|NumPy)\b',
        r'\b(?:REST|API|CI/CD|ETL|ML|NLP|LLM)\b',
    ]
    tech_count = sum(1 for p in tech_patterns if re.search(p, bullet, re.I))
    has_tool_context = bool(re.search(r'\b(?:using|with|via|leveraging)\s+\w', b_lower))
    depth = min(tech_count * 8, 20) + (5 if has_tool_context else 0)

    # 3. OUTCOME VISIBILITY (0-25)
    has_metric = bool(re.search(r'\d+[%+xX]', bullet))
    has_scale = bool(re.search(r'\d+[KkMm]?\+?\s*(?:users|records|requests|queries|rows|transactions)', b_lower))
    has_result = bool(re.search(
        r'\b(?:improving|reducing|increasing|enabling|achieving|resulting|delivering)\b', b_lower
    ))
    has_purpose = bool(re.search(r'\b(?:for|to|enabling|supporting)\s+\w+', b_lower))

    outcome = 0
    if has_metric:
        outcome += 12
    if has_scale:
        outcome += 8
    if has_result:
        outcome += 5 if not has_metric else 3
    elif has_purpose:
        outcome += 3

    # 4. ROLE ALIGNMENT (0-25)
    if jd_skills:
        jd_lower = set(s.lower() for s in jd_skills)
        matched = sum(1 for s in jd_lower if s in b_lower)
        alignment = min(matched / max(len(jd_lower), 1) * 25, 25)
    else:
        alignment = 10

    total = min(clarity + depth + outcome + alignment, 100)

    return {
        "total": round(total),
        "clarity": round(clarity),
        "depth": round(depth),
        "outcome": round(outcome),
        "alignment": round(alignment),
        "details": {
            "starts_with_verb": starts_with_verb,
            "has_metric": has_metric,
            "has_tool": has_tool_context,
            "tech_count": tech_count,
            "word_count": word_count,
        },
    }


# ================================================================
# v4.5 PART 1 — PROOF STRENGTH SCORING
# ================================================================

def score_proof_strength(bullet: str) -> Dict:
    """
    Score how convincing a bullet is as PROOF of capability (0-100).
    Three dimensions:
      - Dataset Scale (0-35): mentions data volume, user count, system scale
      - Model/System Complexity (0-35): architecture depth, multi-component
      - Business Relevance (0-30): ties to revenue, users, stakeholders
    """
    b_lower = bullet.lower()

    # 1. DATASET SCALE (0-35)
    scale = 0
    # Explicit numbers
    if re.search(r'\d+\s*(?:million|M\b|billion|B\b)', bullet, re.I):
        scale += 25
    elif re.search(r'\d+\s*(?:thousand|K\b)', bullet, re.I):
        scale += 18
    elif re.search(r'\d+\s*(?:TB|GB|PB)', bullet, re.I):
        scale += 20
    elif re.search(r'\d+[KkMm]?\+?\s*(?:records|rows|entries|events|documents|transactions)', b_lower):
        scale += 15
    elif re.search(r'\d+\s*(?:users|customers|clients|teams)', b_lower):
        scale += 12
    # Implicit scale words
    if re.search(r'\b(?:large-scale|enterprise|production|distributed|real-time)\b', b_lower):
        scale += 10
    scale = min(scale, 35)

    # 2. MODEL/SYSTEM COMPLEXITY (0-35)
    complexity = 0
    complexity_markers = [
        (r'\b(?:end-to-end|full-stack|microservice|distributed)\b', 12),
        (r'\b(?:pipeline|workflow|orchestrat|architecture)\b', 8),
        (r'\b(?:model|algorithm|neural|transformer|ensemble)\b', 8),
        (r'\b(?:multi-[a-z]+|cross-[a-z]+)\b', 6),
        (r'\b(?:automated|autonomous|self-[a-z]+)\b', 6),
        (r'\b(?:custom|novel|proprietary)\b', 5),
    ]
    for pattern, score in complexity_markers:
        if re.search(pattern, b_lower):
            complexity += score
    complexity = min(complexity, 35)

    # 3. BUSINESS RELEVANCE (0-30)
    business = 0
    biz_markers = [
        (r'\b(?:revenue|cost|ROI|profit|savings)\b', 15),
        (r'\b(?:stakeholder|executive|leadership|C-suite|VP)\b', 10),
        (r'\b(?:customer|client|user|partner)\b', 8),
        (r'\b(?:decision|strategy|roadmap|KPI|metric)\b', 6),
        (r'\b(?:team|cross-functional|collaboration)\b', 5),
    ]
    for pattern, score in biz_markers:
        if re.search(pattern, b_lower):
            business += score
    business = min(business, 30)

    total = min(scale + complexity + business, 100)

    return {
        "total": round(total),
        "scale": round(scale),
        "complexity": round(complexity),
        "business": round(business),
    }


# ================================================================
# v4.5 PART 2 — JD ALIGNMENT SCORING
# ================================================================

def score_jd_alignment(bullet: str, jd_skills: List[str], role: str = "") -> Dict:
    """
    Score how well a bullet aligns with the JD (0-100).
    Two dimensions:
      - Skill Overlap (0-60): direct keyword matches
      - Role Language (0-40): uses terminology natural for the role
    """
    b_lower = bullet.lower()
    role_lower = role.lower()

    # 1. SKILL OVERLAP (0-60)
    jd_lower = [s.lower() for s in jd_skills]
    matched = [s for s in jd_lower if s in b_lower]
    if jd_lower:
        overlap_pct = len(matched) / len(jd_lower)
    else:
        overlap_pct = 0
    skill_score = min(round(overlap_pct * 60), 60)

    # 2. ROLE LANGUAGE (0-40)
    role_lang = 0
    role_terms = {
        "data scientist": [
            r'\b(?:model|prediction|classification|regression|feature|hypothesis)\b',
            r'\b(?:accuracy|precision|recall|F1|AUC|ROC)\b',
            r'\b(?:experiment|A/B|statistical|correlation)\b',
        ],
        "data analyst": [
            r'\b(?:dashboard|report|visualization|insight|trend|KPI)\b',
            r'\b(?:SQL|query|aggregat|metric|segment)\b',
            r'\b(?:stakeholder|business|decision|analysis)\b',
        ],
        "ml engineer": [
            r'\b(?:training|inference|serving|pipeline|batch|streaming)\b',
            r'\b(?:deploy|container|API|latency|throughput)\b',
            r'\b(?:model|feature|embedding|vector|GPU)\b',
        ],
        "software engineer": [
            r'\b(?:API|endpoint|service|database|cache)\b',
            r'\b(?:scalab|performance|latency|throughput)\b',
            r'\b(?:testing|CI/CD|deploy|monitor)\b',
        ],
        "devops": [
            r'\b(?:infrastructure|terraform|ansible|deploy)\b',
            r'\b(?:container|kubernetes|docker|helm)\b',
            r'\b(?:monitoring|alerting|SLA|uptime)\b',
        ],
    }

    # Find matching role category
    for role_key, patterns in role_terms.items():
        if role_key in role_lower:
            hits = sum(1 for p in patterns if re.search(p, b_lower))
            role_lang = min(hits * 14, 40)
            break
    else:
        # Generic role language check
        generic = [
            r'\b(?:developed|optimized|built|implemented)\b',
            r'\b(?:improving|reducing|increasing|delivering)\b',
        ]
        hits = sum(1 for p in generic if re.search(p, b_lower))
        role_lang = min(hits * 15, 40)

    total = min(skill_score + role_lang, 100)

    return {
        "total": round(total),
        "skill_overlap": skill_score,
        "role_language": role_lang,
        "matched_skills": matched,
        "match_count": len(matched),
    }


# ================================================================
# v4.5 PART 3 — ROLE-SPECIFIC LIFECYCLE CHECK
# ================================================================

def check_lifecycle_coverage(bullets: List[str], role: str = "") -> Dict:
    """
    Check if bullets collectively cover the role lifecycle:
    pipeline → modeling → deployment → impact (for data roles).
    """
    role_lower = role.lower()

    # Determine lifecycle stages
    lifecycle = ROLE_LIFECYCLE.get("data", ROLE_LIFECYCLE["data"])  # default
    for key in ROLE_LIFECYCLE:
        if key in role_lower:
            lifecycle = ROLE_LIFECYCLE[key]
            break

    stage_patterns = {
        "pipeline": r'\b(?:pipeline|ETL|ingestion|data.*processing|extraction|cleaning)\b',
        "data ingestion": r'\b(?:ingest|extract|collect|streaming|batch.*load)\b',
        "modeling": r'\b(?:model|algorithm|training|prediction|classification|regression)\b',
        "training": r'\b(?:train|fine-tun|hyperparameter|epoch|batch.*size)\b',
        "evaluation": r'\b(?:evaluat|accuracy|precision|recall|F1|AUC|validation)\b',
        "deployment": r'\b(?:deploy|production|serving|container|API|endpoint)\b',
        "serving": r'\b(?:serving|inference|endpoint|latency|request)\b',
        "impact": r'\b(?:improv|reduc|increas|enabl|achiev|revenue|cost|user)\b',
        "architecture": r'\b(?:architect|design|system.*design|infrastructure)\b',
        "implementation": r'\b(?:implement|built|develop|created|coded)\b',
        "testing": r'\b(?:test|unit.*test|integration|QA|coverage)\b',
        "automation": r'\b(?:automat|CI/CD|terraform|ansible|script)\b',
        "monitoring": r'\b(?:monitor|alert|log|observ|dashboard|metric)\b',
        "scaling": r'\b(?:scal|performance|throughput|load|capacity)\b',
        "infrastructure": r'\b(?:infrastructure|cloud|AWS|GCP|Azure|server)\b',
        "design": r'\b(?:design|UX|UI|wireframe|prototype|figma)\b',
        "optimization": r'\b(?:optimiz|performance|speed|cache|lazy)\b',
    }

    all_text = " ".join(b.lower() for b in bullets)
    covered = []
    missing = []

    for stage in lifecycle:
        pattern = stage_patterns.get(stage, rf'\b{stage}\b')
        if re.search(pattern, all_text, re.I):
            covered.append(stage)
        else:
            missing.append(stage)

    coverage = len(covered) / max(len(lifecycle), 1) * 100

    return {
        "coverage": round(coverage),
        "covered": covered,
        "missing": missing,
        "lifecycle": lifecycle,
        "message": (
            f"Full lifecycle coverage ({coverage:.0f}%)" if coverage >= 75
            else f"Missing stages: {', '.join(missing)} ({coverage:.0f}%)"
        ),
    }


# ================================================================
# v4.5 PART 4 — ATS OPTIMIZATION CHECK
# ================================================================

def check_ats_optimization(
    bullets: List[str],
    jd_skills: List[str],
) -> Dict:
    """
    Check keyword density and natural placement across all bullets.
    """
    jd_lower = set(s.lower() for s in jd_skills)
    all_text = " ".join(b.lower() for b in bullets)

    # Keyword presence
    present = {s for s in jd_lower if s in all_text}
    missing = jd_lower - present
    coverage = len(present) / max(len(jd_lower), 1) * 100

    # Natural placement (keyword appears with context, not stuffed)
    natural = 0
    stuffed = 0
    for skill in present:
        # Check if skill appears in a natural sentence context
        pattern = rf'\b{re.escape(skill)}\b'
        matches = re.findall(pattern, all_text, re.I)
        if len(matches) <= 3:
            natural += 1
        else:
            stuffed += 1

    return {
        "keyword_coverage": round(coverage),
        "present": sorted(present),
        "missing": sorted(missing),
        "natural_count": natural,
        "stuffed_count": stuffed,
        "message": (
            f"{coverage:.0f}% keyword coverage ({len(present)}/{len(jd_lower)})"
            + (f" — missing: {', '.join(sorted(missing)[:3])}" if missing else "")
        ),
    }


# ================================================================
# CONTENT QUALITY GATE (retained from v4.4)
# ================================================================

def check_content_quality(bullet: str) -> Dict:
    """
    Verify bullet follows [Action] + [What] + [How] + [Impact].
    """
    issues = []
    words = bullet.split()
    b_lower = bullet.lower()

    first_word = words[0].lower().rstrip("ed,.:") if words else ""
    if first_word in WEAK_VERBS:
        issues.append(f"Weak verb '{words[0]}' — replace with strong action verb")

    if len(words) < 4:
        issues.append("Too short — missing [What] component")

    has_how = bool(re.search(r'\b(?:using|with|via|leveraging|through|across)\s+\w', b_lower))
    if not has_how and len(words) < 8:
        issues.append("Missing [How] — add tool/method context")

    has_impact = bool(re.search(
        r'\b(?:improving|reducing|increasing|enabling|achieving|for|to)\s+\w', b_lower
    )) or bool(re.search(r'\d+[%+]', bullet))
    if not has_impact:
        issues.append("Missing [Impact] — add outcome or purpose")

    return {"passes": len(issues) == 0, "issues": issues, "issue_count": len(issues)}


# ================================================================
# ATS IMPROVEMENT CHECK (retained from v4.4)
# ================================================================

def verify_ats_improvement(
    original: str, rewritten: str, jd_skills: List[str] = None,
) -> Dict:
    """Verify rewrite actually improves ATS signal."""
    jd_skills = jd_skills or []
    jd_lower = set(s.lower() for s in jd_skills)

    orig_matches = sum(1 for s in jd_lower if s in original.lower())
    new_matches = sum(1 for s in jd_lower if s in rewritten.lower())
    keyword_delta = new_matches - orig_matches

    orig_has_verb = (original.split()[0].lower().rstrip("ed,.") in ALL_STRONG) if original.split() else False
    new_has_verb = (rewritten.split()[0].lower().rstrip("ed,.") in ALL_STRONG) if rewritten.split() else False
    structure_improved = new_has_verb and not orig_has_verb

    orig_signal = score_signal_strength(original, jd_skills)
    new_signal = score_signal_strength(rewritten, jd_skills)
    signal_delta = new_signal["total"] - orig_signal["total"]

    return {
        "improved": signal_delta > 0 or keyword_delta > 0 or structure_improved,
        "keyword_delta": keyword_delta,
        "signal_delta": signal_delta,
        "structure_improved": structure_improved,
        "orig_signal": orig_signal["total"],
        "new_signal": new_signal["total"],
    }


# ================================================================
# v4.5 ENHANCED DEBUG OUTPUT — All Deltas
# ================================================================

def generate_bullet_debug(
    original: str,
    rewritten: str,
    jd_skills: List[str] = None,
    role: str = "",
) -> Dict:
    """
    Enhanced debug: signal + proof + alignment + ATS deltas.
    """
    jd_skills = jd_skills or []
    same = original.strip() == rewritten.strip()
    if same:
        return {
            "original": original, "rewritten": rewritten,
            "changed": False,
            "reason": "No change — original already strong or rewrite not better",
        }

    # All scores
    ats_check = verify_ats_improvement(original, rewritten, jd_skills)
    quality = check_content_quality(rewritten)

    proof_before = score_proof_strength(original)
    proof_after = score_proof_strength(rewritten)
    proof_delta = proof_after["total"] - proof_before["total"]

    align_before = score_jd_alignment(original, jd_skills, role)
    align_after = score_jd_alignment(rewritten, jd_skills, role)
    align_delta = align_after["total"] - align_before["total"]

    # Combined score (weighted)
    combined_delta = (
        ats_check["signal_delta"] * 0.35
        + proof_delta * 0.25
        + align_delta * 0.25
        + ats_check["keyword_delta"] * 5 * 0.15
    )

    reasons = []
    if ats_check["structure_improved"]:
        reasons.append("Stronger verb")
    if ats_check["keyword_delta"] > 0:
        reasons.append(f"+{ats_check['keyword_delta']} keywords")
    if ats_check["signal_delta"] > 0:
        reasons.append(f"Signal +{ats_check['signal_delta']}")
    if proof_delta > 0:
        reasons.append(f"Proof +{proof_delta}")
    if align_delta > 0:
        reasons.append(f"Align +{align_delta}")
    if not reasons:
        reasons.append("Structural improvement")

    return {
        "original": original,
        "rewritten": rewritten,
        "changed": True,
        "reason": " | ".join(reasons),
        "signal_before": ats_check["orig_signal"],
        "signal_after": ats_check["new_signal"],
        "signal_delta": ats_check["signal_delta"],
        "proof_before": proof_before["total"],
        "proof_after": proof_after["total"],
        "proof_delta": proof_delta,
        "align_before": align_before["total"],
        "align_after": align_after["total"],
        "align_delta": align_delta,
        "keyword_delta": ats_check["keyword_delta"],
        "combined_delta": round(combined_delta, 1),
        "quality_pass": quality["passes"],
        "quality_issues": quality["issues"],
    }


# ================================================================
# v4.5 COMBINED SCORE GATE
# ================================================================

def should_accept_rewrite(debug: Dict) -> Dict:
    """
    Accept rewrite ONLY if combined score improves significantly.
    """
    if not debug.get("changed"):
        return {"accept": False, "reason": "No change"}

    combined = debug.get("combined_delta", 0)
    if combined >= MIN_COMBINED_IMPROVEMENT:
        return {"accept": True, "reason": f"Combined +{combined:.0f} ≥ {MIN_COMBINED_IMPROVEMENT} threshold"}
    else:
        return {"accept": False, "reason": f"Combined +{combined:.0f} < {MIN_COMBINED_IMPROVEMENT} threshold — revert"}


# ================================================================
# UNIFIED OUTPUT (v4.5 enhanced)
# ================================================================

def build_unified_output(
    original_bullets: List[str],
    improved_bullets: List[str],
    jd_skills: List[str] = None,
    role: str = "",
) -> Dict:
    """
    Build consistent output for app.py + dashboard.py.
    v4.5: includes all deltas.
    """
    jd_skills = jd_skills or []
    diffs = []
    totals = {"signal": 0, "proof": 0, "align": 0, "keyword": 0}
    changed_count = 0

    for orig, improved in zip(original_bullets, improved_bullets):
        debug = generate_bullet_debug(orig, improved, jd_skills, role)
        if debug["changed"]:
            diffs.append(debug)
            changed_count += 1
            totals["signal"] += debug.get("signal_delta", 0)
            totals["proof"] += debug.get("proof_delta", 0)
            totals["align"] += debug.get("align_delta", 0)
            totals["keyword"] += debug.get("keyword_delta", 0)

    return {
        "diffs": diffs,
        "total_bullets": len(original_bullets),
        "changed_count": changed_count,
        "deltas": totals,
        "summary": (
            f"{changed_count}/{len(original_bullets)} bullets improved — "
            f"Signal +{totals['signal']}, Proof +{totals['proof']}, "
            f"Align +{totals['align']}, Keywords +{totals['keyword']}"
            if changed_count else "No bullets changed — originals already strong"
        ),
    }


# ================================================================
# MASTER VALIDATOR (v4.5)
# ================================================================

def validate_rewrite_quality(
    original_bullets: List[str],
    improved_bullets: List[str],
    jd_skills: List[str] = None,
    role: str = "",
) -> Dict:
    """
    Full recruiter-level validation of rewrite batch.
    """
    jd_skills = jd_skills or []

    unified = build_unified_output(original_bullets, improved_bullets, jd_skills, role)

    # Quality gate
    quality_pass = sum(1 for d in unified["diffs"] if d.get("quality_pass"))
    quality_fail = sum(1 for d in unified["diffs"] if not d.get("quality_pass"))

    # Combined score gate
    accepted = sum(1 for d in unified["diffs"] if should_accept_rewrite(d)["accept"])
    rejected = unified["changed_count"] - accepted

    # Lifecycle coverage
    lifecycle = check_lifecycle_coverage(improved_bullets, role)

    # ATS optimization
    ats = check_ats_optimization(improved_bullets, jd_skills)

    return {
        "unified_output": unified,
        "quality_report": {
            "pass": quality_pass,
            "fail": quality_fail,
            "pass_rate": round(quality_pass / max(quality_pass + quality_fail, 1) * 100),
        },
        "acceptance_report": {
            "accepted": accepted,
            "rejected": rejected,
            "message": f"{accepted} rewrites accepted, {rejected} below threshold",
        },
        "lifecycle": lifecycle,
        "ats_optimization": ats,
        "deltas": unified["deltas"],
        "summary": unified["summary"],
    }
