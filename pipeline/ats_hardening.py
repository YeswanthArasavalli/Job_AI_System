"""
ATS Hardening Engine (v4.8) — Real Parsing + Stable Learning + Clear Decisions.

Fixes 5 critical issues in the ATS pipeline:
  1. Real ATS parsing validation (not theoretical coverage)
  2. Keyword learning stability (anti-overfitting with confidence scaling)
  3. Unknown keyword → capability plan (growth, not fake signaling)
  4. Defensibility check (interview-safe only)
  5. Final decision engine (APPLY NOW / APPLY FIX / SKIP)

Philosophy: "Will ATS parse this? Can candidate defend it? Will it work?"
"""

import re
import math
from typing import List, Dict
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ================================================================
# PART 1 — REAL ATS PARSING SIMULATION
# ================================================================

def simulate_ats_parser(resume_text: str, jd_keywords: List[str]) -> Dict:
    """
    Simulate how a real ATS parses a resume.

    Rules:
      - Only count keywords that appear in clean sentence context
      - Ignore duplicates (count each keyword once)
      - Penalize keyword stuffing (>3 mentions)
      - Require proper word boundaries

    Returns both theoretical and real coverage.
    """
    text_lower = resume_text.lower()
    jd_lower = [kw.lower() for kw in jd_keywords]
    jd_set = set(jd_lower)

    # Theoretical: simple substring match
    theoretical_matched = {kw for kw in jd_set if kw in text_lower}
    theoretical_coverage = len(theoretical_matched) / max(len(jd_set), 1) * 100

    # Real: ATS-grade parsing
    parsed_keywords = set()
    stuffed_keywords = set()

    for kw in jd_set:
        # Word boundary match (real ATS uses tokenization)
        pattern = rf'\b{re.escape(kw)}\b'
        matches = re.findall(pattern, text_lower)

        if not matches:
            continue

        # Count occurrences
        count = len(matches)

        # Stuffing check: >3 exact mentions is suspicious
        if count > 3:
            stuffed_keywords.add(kw)
            continue

        # Context check: keyword must appear in a sentence-like structure
        # (not just a bare list of comma-separated keywords)
        in_sentence = False
        for m in re.finditer(pattern, text_lower):
            start = max(m.start() - 30, 0)
            end = min(m.end() + 30, len(text_lower))
            context = text_lower[start:end]
            # Has verb or preposition nearby = sentence context
            if re.search(r'\b(?:using|with|built|developed|managed|analyzed|deployed|via|for|in)\b', context):
                in_sentence = True
                break

        if in_sentence:
            parsed_keywords.add(kw)
        elif count == 1:
            # Single mention without context — still counts for ATS
            # but at reduced confidence
            parsed_keywords.add(kw)

    real_coverage = len(parsed_keywords) / max(len(jd_set), 1) * 100

    return {
        "theoretical_coverage": round(theoretical_coverage, 1),
        "real_coverage": round(real_coverage, 1),
        "parsed_keywords": sorted(parsed_keywords),
        "stuffed_keywords": sorted(stuffed_keywords),
        "missing_keywords": sorted(jd_set - parsed_keywords - stuffed_keywords),
        "parsed_count": len(parsed_keywords),
        "total_keywords": len(jd_set),
    }


# ================================================================
# PART 2 — KEYWORD LEARNING STABILITY (ANTI-OVERFITTING)
# ================================================================

def compute_stable_keyword_weights(outcomes: List[Dict]) -> Dict:
    """
    Compute keyword weights with confidence scaling to prevent overfitting.

    confidence = min(1.0, application_count / 5)
    effective_weight = base_weight * confidence

    Prevents 1/1 = 100% bias from early data.
    """
    keyword_stats = {}
    for outcome in outcomes:
        for kw in outcome.get("keywords_used", []):
            kw_lower = kw.lower()
            if kw_lower not in keyword_stats:
                keyword_stats[kw_lower] = {"total": 0, "success": 0}
            keyword_stats[kw_lower]["total"] += 1
            if outcome.get("success"):
                keyword_stats[kw_lower]["success"] += 1

    weights = {}
    adjustments = {}

    for kw, stats in keyword_stats.items():
        total = stats["total"]
        success = stats["success"]

        # Base weight = success rate
        base_rate = success / max(total, 1) * 100

        # Confidence factor: requires 5+ samples for full weight
        confidence = min(1.0, total / 5)

        # Effective weight (dampened by confidence)
        effective_rate = base_rate * confidence

        # Status
        if confidence < 0.4:
            status = "INSUFFICIENT_DATA"
        elif effective_rate > 40:
            status = "HIGH"
        elif effective_rate > 15:
            status = "MEDIUM"
        else:
            status = "LOW"

        weights[kw] = {
            "base_rate": round(base_rate, 1),
            "confidence": round(confidence, 2),
            "effective_rate": round(effective_rate, 1),
            "total": total,
            "success": success,
            "status": status,
        }

        if confidence < 1.0:
            adjustments[kw] = {
                "original": round(base_rate, 1),
                "adjusted": round(effective_rate, 1),
                "reason": f"Low confidence ({total}/5 samples)",
            }

    # Sort by effective rate
    sorted_weights = dict(sorted(weights.items(), key=lambda x: x[1]["effective_rate"], reverse=True))

    return {
        "keyword_weights": sorted_weights,
        "confidence_adjustments": adjustments,
        "stable_top": [k for k, v in sorted_weights.items()
                       if v["status"] == "HIGH" and v["confidence"] >= 0.6][:5],
        "unstable_keywords": [k for k, v in sorted_weights.items()
                              if v["status"] == "INSUFFICIENT_DATA"],
    }


# ================================================================
# PART 3 — CAPABILITY GAP PLAN
# ================================================================

def generate_capability_plan(missing_unknown: List[str]) -> List[Dict]:
    """
    Convert unknown missing keywords into actionable capability plans.
    DO NOT inject these into resume — build skills first.
    """
    if not missing_unknown:
        return []

    # Skill → learning path mapping
    _SKILL_PATHS = {
        "kubernetes": {
            "action": "Learn container orchestration basics",
            "resource": "Kubernetes official tutorial + local minikube setup",
            "project": "Deploy a Flask ML API on Kubernetes",
            "timeline": "1-2 weeks",
        },
        "mlops": {
            "action": "Learn ML pipeline automation",
            "resource": "MLflow + DVC tutorials, Made With ML course",
            "project": "Build end-to-end ML pipeline with experiment tracking",
            "timeline": "2-3 weeks",
        },
        "spark": {
            "action": "Learn distributed data processing",
            "resource": "PySpark documentation + Databricks free tier",
            "project": "Process 1GB+ dataset with PySpark transformations",
            "timeline": "1-2 weeks",
        },
        "terraform": {
            "action": "Learn Infrastructure as Code",
            "resource": "Terraform getting started guide + AWS free tier",
            "project": "Provision a basic AWS infrastructure with Terraform",
            "timeline": "1 week",
        },
        "aws": {
            "action": "Learn cloud fundamentals",
            "resource": "AWS Cloud Practitioner path + free tier labs",
            "project": "Deploy a data pipeline on AWS (S3 + Lambda + Glue)",
            "timeline": "2-3 weeks",
        },
        "docker": {
            "action": "Learn containerization",
            "resource": "Docker official getting started",
            "project": "Containerize an existing Python application",
            "timeline": "3-5 days",
        },
    }

    plans = []
    for skill in missing_unknown:
        skill_lower = skill.lower()
        if skill_lower in _SKILL_PATHS:
            path = _SKILL_PATHS[skill_lower]
            plans.append({
                "skill": skill,
                "action": path["action"],
                "resource": path["resource"],
                "project": path["project"],
                "timeline": path["timeline"],
                "status": "NOT_STARTED",
            })
        else:
            plans.append({
                "skill": skill,
                "action": f"Learn {skill} fundamentals",
                "resource": f"Official {skill} documentation + online tutorials",
                "project": f"Build a small project demonstrating {skill} usage",
                "timeline": "1-2 weeks",
                "status": "NOT_STARTED",
            })

    return plans


# ================================================================
# PART 4 — DEFENSIBILITY CHECK
# ================================================================

def check_defensibility(
    keywords_to_inject: List[str],
    candidate_skills: List[str],
    experience_bullets: List[str],
) -> Dict:
    """
    For each keyword injection, verify the candidate can defend it in interview.

    Safe: keyword is in candidate_skills OR logically inferable from experience.
    Unsafe: keyword added without evidence.
    """
    candidate_lower = set(s.lower() for s in candidate_skills)
    exp_text = " ".join(b.lower() for b in experience_bullets)
    safe = []
    rejected = []

    # Inference map: if experience mentions X, then Y is defensible
    _INFERENCE_MAP = {
        "python": ["pandas", "numpy", "scikit-learn", "flask", "fastapi"],
        "sql": ["postgresql", "mysql", "database"],
        "machine learning": ["scikit-learn", "tensorflow", "pytorch", "model"],
        "data pipeline": ["etl", "airflow", "data processing"],
        "cloud": ["aws", "gcp", "azure"],
        "deployment": ["docker", "ci/cd"],
    }

    inferable = set()
    for concept, related in _INFERENCE_MAP.items():
        if concept in exp_text:
            inferable.update(related)

    for kw in keywords_to_inject:
        kw_lower = kw.lower()

        # Direct skill match
        if kw_lower in candidate_lower:
            safe.append({
                "keyword": kw,
                "reason": "In candidate skills",
                "interview_ready": True,
            })
        # Inferable from experience
        elif kw_lower in inferable:
            safe.append({
                "keyword": kw,
                "reason": "Inferable from experience",
                "interview_ready": True,
            })
        # In experience text directly
        elif kw_lower in exp_text:
            safe.append({
                "keyword": kw,
                "reason": "Mentioned in experience",
                "interview_ready": True,
            })
        else:
            rejected.append({
                "keyword": kw,
                "reason": "Cannot defend in interview — no evidence",
                "interview_ready": False,
            })

    return {
        "safe_keywords": safe,
        "rejected_keywords": rejected,
        "safe_count": len(safe),
        "rejected_count": len(rejected),
        "all_safe": len(rejected) == 0,
    }


# ================================================================
# PART 5 — FINAL DECISION ENGINE
# ================================================================

def compute_final_decision(
    real_coverage: float,
    shortlist_probability: float = 0,
    recruiter_score: float = 0,
) -> Dict:
    """
    Clear APPLY / FIX / SKIP decision based on real ATS + recruiter data.

    APPLY NOW:   probability ≥ 65 AND coverage ≥ 70
    APPLY (FIX): probability 40-65 OR coverage 50-70
    SKIP:        probability < 40 AND coverage < 50
    """
    # Combine signals
    if shortlist_probability >= 65 and real_coverage >= 70:
        decision = "APPLY NOW"
        reason = (
            f"Strong match — {real_coverage:.0f}% ATS coverage, "
            f"{shortlist_probability:.0f}% shortlist probability"
        )
        confidence = min(90, (shortlist_probability + real_coverage) / 2)
    elif shortlist_probability >= 40 or real_coverage >= 50:
        decision = "APPLY (FIX GAPS)"
        gaps = []
        if real_coverage < 70:
            gaps.append(f"ATS coverage {real_coverage:.0f}% < 70%")
        if shortlist_probability < 65:
            gaps.append(f"probability {shortlist_probability:.0f}% < 65%")
        reason = f"Competitive but needs work — {', '.join(gaps)}"
        confidence = min(70, (shortlist_probability + real_coverage) / 2)
    else:
        decision = "SKIP"
        reason = (
            f"Low match — {real_coverage:.0f}% ATS coverage, "
            f"{shortlist_probability:.0f}% shortlist probability"
        )
        confidence = max(20, 100 - (shortlist_probability + real_coverage) / 2)

    return {
        "final": decision,
        "reason": reason,
        "confidence": round(confidence),
    }


# ================================================================
# MASTER ORCHESTRATOR
# ================================================================

def run_ats_hardening(
    jd_keywords: List[str],
    resume_bullets: List[str],
    candidate_skills: List[str],
    outcomes: List[Dict] = None,
    shortlist_probability: float = 0,
    recruiter_score: float = 0,
) -> Dict:
    """
    Run the complete ATS hardening pipeline (v4.8).
    """
    outcomes = outcomes or []
    resume_text = " ".join(resume_bullets)

    # 1. Real ATS parsing
    ats = simulate_ats_parser(resume_text, jd_keywords)

    # 2. Stable keyword learning
    learning = compute_stable_keyword_weights(outcomes) if outcomes else {
        "keyword_weights": {}, "confidence_adjustments": {},
        "stable_top": [], "unstable_keywords": [],
    }

    # 3. Capability plan for unknown keywords
    from pipeline.ats_optimizer import analyze_keyword_gaps
    gaps = analyze_keyword_gaps(jd_keywords, resume_text, candidate_skills)
    capability_plan = generate_capability_plan(gaps["missing_unknown"])

    # 4. Defensibility check on injectable keywords
    defensibility = check_defensibility(
        gaps["missing_injectable"], candidate_skills, resume_bullets
    )

    # 5. Final decision
    decision = compute_final_decision(
        ats["real_coverage"], shortlist_probability, recruiter_score
    )

    return {
        "ats": {
            "theoretical_coverage": ats["theoretical_coverage"],
            "real_coverage": ats["real_coverage"],
            "parsed_keywords": ats["parsed_keywords"],
            "missing_keywords": ats["missing_keywords"],
            "stuffed_keywords": ats["stuffed_keywords"],
        },
        "learning": {
            "keyword_weights": {
                k: {"effective_rate": v["effective_rate"], "confidence": v["confidence"], "status": v["status"]}
                for k, v in list(learning["keyword_weights"].items())[:8]
            },
            "confidence_adjustments": learning["confidence_adjustments"],
            "stable_top": learning["stable_top"],
            "unstable": learning["unstable_keywords"],
        },
        "capability_plan": capability_plan,
        "defensibility_check": {
            "safe_keywords": [s["keyword"] for s in defensibility["safe_keywords"]],
            "rejected_keywords": [r["keyword"] for r in defensibility["rejected_keywords"]],
            "details": defensibility,
        },
        "decision": decision,
    }
