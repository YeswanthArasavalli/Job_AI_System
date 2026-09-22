"""
ATS Maximization + Outcome Learning Engine (v4.7).

Maximizes real shortlist success by:
  1. JD keyword extraction (skills, tools, concepts)
  2. Keyword gap analysis with prioritization
  3. Contextual keyword injection (truth-constrained)
  4. ATS coverage targeting (70-85%)
  5. Bullet-level keyword distribution
  6. Outcome tracking (resume version → result)
  7. Learning from outcomes (boost/penalize)
  8. Keyword effectiveness model
  9. Variant performance learning
  10. Decision impact estimation

Philosophy: "Will this resume be parsed AND selected?"
"""

import re
from typing import List, Dict, Set
from utils.logger import setup_logger

logger = setup_logger(__name__)

ATS_COVERAGE_MIN = 70
ATS_COVERAGE_MAX = 85


# ================================================================
# PART 1 — JD KEYWORD EXTRACTION
# ================================================================

def extract_jd_keywords(
    required_skills: List[str] = None,
    preferred_skills: List[str] = None,
    jd_text: str = "",
) -> Dict:
    """
    Extract structured keywords from JD into skills, tools, concepts.
    """
    required_skills = required_skills or []
    preferred_skills = preferred_skills or []
    all_skills = set(s.lower() for s in required_skills + preferred_skills)

    # Auto-extract from JD text if provided
    if jd_text:
        tool_patterns = [
            r'\b(Python|SQL|Java|JavaScript|TypeScript|Go|Rust|C\+\+|Scala|R)\b',
            r'\b(AWS|GCP|Azure|Docker|Kubernetes|Terraform|Ansible)\b',
            r'\b(Spark|Kafka|Airflow|dbt|PostgreSQL|MongoDB|Redis|Snowflake)\b',
            r'\b(TensorFlow|PyTorch|scikit-learn|XGBoost|LightGBM|Pandas|NumPy)\b',
            r'\b(Tableau|Power\s*BI|Looker|Excel|Grafana)\b',
            r'\b(React|Django|Flask|FastAPI|Spring|Node\.js)\b',
        ]
        for pattern in tool_patterns:
            for match in re.findall(pattern, jd_text, re.I):
                all_skills.add(match.lower())

        concept_patterns = [
            r'\b(ETL|NLP|computer vision|model monitoring|MLOps|CI/CD)\b',
            r'\b(data pipeline|feature engineering|A/B testing|model deployment)\b',
            r'\b(REST API|microservices|distributed systems|real-time)\b',
        ]
        for pattern in concept_patterns:
            for match in re.findall(pattern, jd_text, re.I):
                all_skills.add(match.lower())

    # Classify
    _TOOLS = {
        "python", "sql", "java", "javascript", "typescript", "go", "rust", "c++",
        "scala", "r", "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
        "spark", "kafka", "airflow", "dbt", "postgresql", "mongodb", "redis",
        "snowflake", "tensorflow", "pytorch", "scikit-learn", "xgboost", "lightgbm",
        "pandas", "numpy", "tableau", "power bi", "looker", "excel", "react",
        "django", "flask", "fastapi", "spring", "node.js", "grafana", "ansible",
    }
    _CONCEPTS = {
        "etl", "nlp", "computer vision", "model monitoring", "mlops", "ci/cd",
        "data pipeline", "feature engineering", "a/b testing", "model deployment",
        "rest api", "microservices", "distributed systems", "real-time",
    }

    skills = set()
    tools = set()
    concepts = set()
    for s in all_skills:
        if s in _TOOLS:
            tools.add(s)
        elif s in _CONCEPTS:
            concepts.add(s)
        else:
            skills.add(s)

    return {
        "skills": sorted(skills),
        "tools": sorted(tools),
        "concepts": sorted(concepts),
        "all": sorted(all_skills),
        "total": len(all_skills),
    }


# ================================================================
# PART 2 — KEYWORD GAP ANALYSIS
# ================================================================

def analyze_keyword_gaps(
    jd_keywords: List[str],
    resume_text: str,
    candidate_skills: List[str] = None,
) -> Dict:
    """
    Find missing keywords and prioritize them.
    """
    candidate_skills = candidate_skills or []
    resume_lower = resume_text.lower()
    candidate_lower = set(s.lower() for s in candidate_skills)

    present = []
    missing_injectable = []  # candidate knows but not in resume
    missing_unknown = []     # candidate doesn't know

    for kw in jd_keywords:
        kw_lower = kw.lower()
        if kw_lower in resume_lower:
            present.append(kw)
        elif kw_lower in candidate_lower:
            missing_injectable.append(kw)
        else:
            missing_unknown.append(kw)

    coverage = len(present) / max(len(jd_keywords), 1) * 100

    return {
        "present": present,
        "missing_injectable": missing_injectable,
        "missing_unknown": missing_unknown,
        "coverage": round(coverage, 1),
        "gap_count": len(missing_injectable) + len(missing_unknown),
        "injectable_count": len(missing_injectable),
    }


# ================================================================
# PART 3 — CONTEXTUAL KEYWORD INJECTION (TRUTH-CONSTRAINED)
# ================================================================

def plan_keyword_injection(
    missing_injectable: List[str],
    bullets: List[str],
    candidate_skills: List[str] = None,
) -> List[Dict]:
    """
    Plan where to inject missing keywords that the candidate actually knows.
    Only injects contextually valid placements.
    Distributes across bullets — avoids clustering in one bullet.
    """
    candidate_skills = candidate_skills or []
    candidate_lower = set(s.lower() for s in candidate_skills)
    injections = []
    assigned_counts = {i: 0 for i in range(len(bullets))}

    # Keyword → bullet domain mapping
    _DOMAIN_MAP = {
        "data": ["python", "sql", "pandas", "numpy", "spark", "dbt", "airflow",
                 "postgresql", "mongodb", "snowflake", "etl", "data pipeline"],
        "ml": ["tensorflow", "pytorch", "scikit-learn", "xgboost", "lightgbm",
               "mlops", "model deployment", "feature engineering"],
        "infra": ["docker", "kubernetes", "terraform", "aws", "gcp", "azure",
                  "ci/cd", "ansible"],
        "viz": ["tableau", "power bi", "looker", "grafana", "excel"],
    }

    for kw in missing_injectable:
        kw_lower = kw.lower()
        if kw_lower not in candidate_lower:
            continue

        # Score each bullet
        bullet_scores = []
        for i, bullet in enumerate(bullets):
            b_lower = bullet.lower()
            score = 0

            # Domain compatibility
            for domain, keywords in _DOMAIN_MAP.items():
                if kw_lower in keywords:
                    if any(dk in b_lower for dk in keywords):
                        score += 10  # Same domain

            # Has "using X" pattern (good injection point)
            if re.search(r'\b(?:using|with|via)\s+\w', b_lower):
                score += 5

            # Prefer bullets without too many tools already
            tool_count = len(re.findall(r'\b(?:and|,)\s+[A-Z]', bullet))
            if tool_count < 2:
                score += 3

            # DISTRIBUTION PENALTY: penalize bullets that already have injections
            score -= assigned_counts[i] * 15

            bullet_scores.append((i, score))

        # Sort by score, pick best
        bullet_scores.sort(key=lambda x: x[1], reverse=True)
        best_idx, best_score = bullet_scores[0] if bullet_scores else (None, -1)

        if best_idx is not None and best_score >= 3:
            assigned_counts[best_idx] += 1
            injections.append({
                "keyword": kw,
                "bullet_idx": best_idx,
                "bullet_preview": bullets[best_idx][:50],
                "method": "contextual_append",
                "confidence": min(max(best_score, 1) * 10, 100),
            })

    return injections


# ================================================================
# PART 4 — ATS COVERAGE TARGETING
# ================================================================

def check_ats_coverage(
    jd_keywords: List[str],
    resume_text: str,
) -> Dict:
    """
    Check if resume meets 70-85% ATS keyword coverage target.
    """
    resume_lower = resume_text.lower()
    matched = [kw for kw in jd_keywords if kw.lower() in resume_lower]
    coverage = len(matched) / max(len(jd_keywords), 1) * 100

    if coverage >= ATS_COVERAGE_MAX:
        status = "OPTIMAL"
        action = "No changes needed — avoid keyword stuffing"
    elif coverage >= ATS_COVERAGE_MIN:
        status = "GOOD"
        action = "Coverage acceptable — minor optimization possible"
    elif coverage >= 50:
        status = "LOW"
        action = "Needs improvement — inject known skills contextually"
    else:
        status = "CRITICAL"
        action = "Major gaps — significant optimization needed"

    return {
        "coverage": round(coverage, 1),
        "status": status,
        "action": action,
        "matched": sorted(matched),
        "matched_count": len(matched),
        "total_keywords": len(jd_keywords),
    }


# ================================================================
# PART 5 — BULLET KEYWORD DISTRIBUTION
# ================================================================

def check_keyword_distribution(
    bullets: List[str],
    jd_keywords: List[str],
) -> Dict:
    """
    Ensure keywords are distributed across bullets, not clustered.
    """
    bullet_hits = []
    for i, bullet in enumerate(bullets):
        b_lower = bullet.lower()
        hits = [kw for kw in jd_keywords if kw.lower() in b_lower]
        bullet_hits.append({"idx": i, "hits": len(hits), "keywords": hits})

    # Check distribution
    total_hits = sum(b["hits"] for b in bullet_hits)
    bullets_with_hits = sum(1 for b in bullet_hits if b["hits"] > 0)
    max_hits = max((b["hits"] for b in bullet_hits), default=0)

    clustered = max_hits > 4 and bullets_with_hits < len(bullets) * 0.4

    return {
        "distribution": bullet_hits,
        "total_hits": total_hits,
        "bullets_with_keywords": bullets_with_hits,
        "total_bullets": len(bullets),
        "clustered": clustered,
        "message": (
            f"Keywords in {bullets_with_hits}/{len(bullets)} bullets"
            + (" — ⚠️ CLUSTERED" if clustered else " — well distributed")
        ),
    }


# ================================================================
# PART 6 — OUTCOME TRACKING
# ================================================================

def log_application_outcome(
    company: str,
    role: str,
    resume_variant: str,
    keywords_used: List[str],
    prediction: float,
    actual_result: str,
    ats_coverage: float = 0,
) -> Dict:
    """
    Create an application outcome log entry.
    """
    return {
        "company": company,
        "role": role,
        "resume_variant": resume_variant,
        "keywords_used": keywords_used,
        "prediction": prediction,
        "actual_result": actual_result,
        "ats_coverage": ats_coverage,
        "success": actual_result == "shortlisted",
    }


# ================================================================
# PART 7+8 — LEARNING FROM OUTCOMES + KEYWORD EFFECTIVENESS
# ================================================================

def compute_keyword_effectiveness(outcomes: List[Dict]) -> Dict:
    """
    Compute per-keyword success rate from application outcomes.
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

    effectiveness = {}
    for kw, stats in keyword_stats.items():
        if stats["total"] >= 2:
            rate = stats["success"] / stats["total"] * 100
            effectiveness[kw] = {
                "rate": round(rate, 1),
                "total": stats["total"],
                "success": stats["success"],
                "status": "HIGH" if rate > 40 else "MEDIUM" if rate > 15 else "LOW",
            }

    # Sort by rate
    sorted_kw = sorted(effectiveness.items(), key=lambda x: x[1]["rate"], reverse=True)

    return {
        "effectiveness": dict(sorted_kw),
        "top_keywords": [k for k, v in sorted_kw[:5] if v["rate"] > 20],
        "weak_keywords": [k for k, v in sorted_kw if v["rate"] < 10 and v["total"] >= 3],
    }


# ================================================================
# PART 9 — VARIANT PERFORMANCE LEARNING
# ================================================================

def compute_variant_performance(outcomes: List[Dict]) -> Dict:
    """
    Track success rate per resume variant (balanced/impact/specialized).
    """
    variant_stats = {}
    for outcome in outcomes:
        variant = outcome.get("resume_variant", "balanced")
        if variant not in variant_stats:
            variant_stats[variant] = {"total": 0, "success": 0}
        variant_stats[variant]["total"] += 1
        if outcome.get("success"):
            variant_stats[variant]["success"] += 1

    performance = {}
    best_variant = "balanced"
    best_rate = 0

    for variant, stats in variant_stats.items():
        rate = stats["success"] / max(stats["total"], 1) * 100
        performance[variant] = {
            "rate": round(rate, 1),
            "total": stats["total"],
            "success": stats["success"],
        }
        if rate > best_rate and stats["total"] >= 2:
            best_rate = rate
            best_variant = variant

    return {
        "performance": performance,
        "best_variant": best_variant,
        "best_rate": round(best_rate, 1),
        "recommendation": f"Use '{best_variant}' variant ({best_rate:.0f}% success rate)",
    }


# ================================================================
# MASTER ORCHESTRATOR
# ================================================================

def run_ats_optimization(
    jd_keywords: List[str] = None,
    resume_bullets: List[str] = None,
    candidate_skills: List[str] = None,
    outcomes: List[Dict] = None,
) -> Dict:
    """
    Run the complete ATS maximization + outcome learning pipeline.
    """
    jd_keywords = jd_keywords or []
    resume_bullets = resume_bullets or []
    candidate_skills = candidate_skills or []
    outcomes = outcomes or []

    resume_text = " ".join(resume_bullets)

    # Gap analysis
    gaps = analyze_keyword_gaps(jd_keywords, resume_text, candidate_skills)

    # Injection plan
    injections = plan_keyword_injection(
        gaps["missing_injectable"], resume_bullets, candidate_skills
    )

    # ATS coverage
    coverage = check_ats_coverage(jd_keywords, resume_text)

    # Distribution
    distribution = check_keyword_distribution(resume_bullets, jd_keywords)

    # Learning (if outcomes available)
    kw_effectiveness = compute_keyword_effectiveness(outcomes) if outcomes else None
    variant_perf = compute_variant_performance(outcomes) if outcomes else None

    # Estimated improvement
    potential_coverage = gaps["coverage"]
    if gaps["injectable_count"] > 0:
        potential_coverage = min(
            (len(gaps["present"]) + gaps["injectable_count"]) / max(len(jd_keywords), 1) * 100,
            ATS_COVERAGE_MAX,
        )

    return {
        "gaps": gaps,
        "injections": injections,
        "coverage": coverage,
        "distribution": distribution,
        "keyword_effectiveness": kw_effectiveness,
        "variant_performance": variant_perf,
        "potential_coverage": round(potential_coverage, 1),
        "summary": {
            "current_coverage": coverage["coverage"],
            "status": coverage["status"],
            "injectable": gaps["injectable_count"],
            "potential": round(potential_coverage, 1),
            "distribution": distribution["message"],
        },
    }
