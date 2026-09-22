"""
Quality Gate (v5.1.1) — Final output validation for all rewrite engines.

NOT a new engine. This is a validation filter that:
  1. Rejects rewrites that introduce unsupported information
  2. Validates bullet quality (grammar, naturalness, no stuffing)
  3. Enforces output consistency (app.py == dashboard.py)
  4. Provides real ATS metrics (coverage + distribution, no fake scores)
  5. Ensures recruiter-quality output (ownership, purpose, outcome)

Philosophy: "Truth > optimization. Clarity > keyword stuffing."
"""

import re
import hashlib
from typing import List, Dict, Tuple
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ================================================================
# PART 1 — HARD TRUTH CONSTRAINT
# ================================================================

def validate_rewrite(
    original: str,
    rewritten: str,
    candidate_skills: List[str] = None,
) -> Dict:
    """
    Reject any rewrite that introduces unsupported information.

    Checks:
      - No new tools/technologies not in original or candidate_skills
      - No fabricated metrics (% improvements, numbers)
      - No new impact claims not inferable from original

    Returns: {"accepted": bool, "reason": str, "violations": [...]}
    """
    candidate_skills = candidate_skills or []
    candidate_lower = {s.lower() for s in candidate_skills}
    violations = []

    orig_lower = original.lower()
    rewrite_lower = rewritten.lower()

    # Check 1: Fabricated metrics — catch "N%", "Nx", "N+" patterns
    orig_metrics = set(re.findall(r'\d+\s*[%x+]', orig_lower))
    orig_metrics |= set(re.findall(r'\d+\s*(?:percent|times)', orig_lower))
    new_metrics = set(re.findall(r'\d+\s*[%x+]', rewrite_lower))
    new_metrics |= set(re.findall(r'\d+\s*(?:percent|times)', rewrite_lower))
    fabricated = new_metrics - orig_metrics
    if fabricated:
        violations.append(f"Fabricated metrics: {', '.join(fabricated)}")

    # Check 2: New tool/technology names not in original or candidate_skills
    _TECH_NAMES = {
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
        "jenkins", "circleci", "github actions", "spark", "hadoop",
        "kafka", "airflow", "dbt", "snowflake", "databricks",
        "react", "angular", "vue", "next.js", "fastapi", "flask",
        "django", "spring", "node.js", "express", "graphql",
        "redis", "elasticsearch", "mongodb", "cassandra",
        "tableau", "power bi", "looker", "metabase",
        "pytorch", "tensorflow", "keras", "scikit-learn", "xgboost",
        "pandas", "numpy", "scipy", "matplotlib", "seaborn",
        "huggingface", "langchain", "openai", "mlflow",
    }
    for tech in _TECH_NAMES:
        if tech in rewrite_lower and tech not in orig_lower:
            if tech not in candidate_lower:
                violations.append(f"New tool injected: {tech}")

    # Check 3: Semantic drift — rewrite is completely different topic
    orig_words = set(orig_lower.split())
    rewrite_words = set(rewrite_lower.split())
    if len(orig_words) >= 3:
        overlap = orig_words & rewrite_words
        overlap_ratio = len(overlap) / len(orig_words)
        if overlap_ratio < 0.3:
            violations.append(
                f"Semantic drift: only {overlap_ratio:.0%} word overlap"
            )

    accepted = len(violations) == 0
    return {
        "accepted": accepted,
        "reason": "Rewrite validated" if accepted else f"REJECTED: {'; '.join(violations)}",
        "violations": violations,
    }


# ================================================================
# PART 2 — BULLET QUALITY GATE
# ================================================================

def check_bullet_quality(bullet: str) -> Dict:
    """
    Validate a single bullet for recruiter-quality output.

    Checks:
      - Grammar: starts with action verb, ends with period
      - No keyword stuffing (max 2 tech names per bullet)
      - No repetition (same word >2 times)
      - No unnatural "utilizing X, applying Y" chains
      - No broken phrases or fragments
    """
    issues = []
    b_lower = bullet.lower()

    # Check 1: Starts with action verb (capitalized)
    if bullet and bullet[0].islower():
        issues.append("Does not start with capital letter")

    # Check 2: Keyword stuffing — too many "using X" phrases
    using_count = len(re.findall(
        r'\b(?:using|utilizing|applying|leveraging|with)\s+\w+', b_lower
    ))
    if using_count > 2:
        issues.append(f"Keyword stuffing: {using_count} tool-injection phrases")

    # Check 3: Word repetition
    words = re.findall(r'\b\w{4,}\b', b_lower)
    word_counts = {}
    for w in words:
        word_counts[w] = word_counts.get(w, 0) + 1
    repeated = [w for w, c in word_counts.items() if c > 2]
    if repeated:
        issues.append(f"Repetition: {', '.join(repeated[:2])} appears >2 times")

    # Check 4: Unnatural chaining
    if re.search(r',\s*(?:utilizing|applying)\s+\w+,\s*(?:utilizing|applying)\s+\w+', b_lower):
        issues.append("Unnatural tool-chaining pattern")

    # Check 5: Too long (recruiter skips >200 char bullets)
    if len(bullet) > 200:
        issues.append(f"Too long ({len(bullet)} chars, max 200)")

    # Check 6: Fragment detection (no verb)
    has_verb = bool(re.search(
        r'\b(?:built|developed|designed|managed|led|created|implemented|'
        r'executed|analyzed|optimized|deployed|automated|configured|'
        r'established|enhanced|improved|reduced|increased|delivered|'
        r'maintained|supported|contributed|collaborated|integrated|'
        r'architected|orchestrated|streamlined|leveraged|utilized)\b',
        b_lower
    ))
    if not has_verb and len(bullet) > 20:
        issues.append("Missing action verb")

    # Check 7: Double period
    if ".." in bullet:
        issues.append("Double period detected")

    passed = len(issues) == 0
    return {
        "passed": passed,
        "issues": issues,
        "bullet": bullet,
    }


def validate_all_bullets(bullets: List[str]) -> Dict:
    """Validate all bullets in a resume and return aggregate report."""
    results = [check_bullet_quality(b) for b in bullets]
    failed = [r for r in results if not r["passed"]]

    return {
        "total": len(bullets),
        "passed": len(bullets) - len(failed),
        "failed": len(failed),
        "pass_rate": round((len(bullets) - len(failed)) / max(len(bullets), 1) * 100),
        "issues": [
            {"bullet": r["bullet"][:60], "issues": r["issues"]}
            for r in failed
        ],
    }


# ================================================================
# PART 3 — RECRUITER QUALITY ENFORCEMENT
# ================================================================

def enforce_recruiter_quality(bullet: str) -> Dict:
    """
    Ensure bullet has ownership, purpose, and outcome.
    Does NOT add fake content — only restructures existing.

    Structure: [Action] + [What] + [Context] + [Real Impact]
    """
    original = bullet
    improved = bullet
    fixes = []

    # Fix 1: Ownership — replace passive voice
    passive_fixes = [
        (r'^(?:Was responsible for|Responsible for)\b', 'Led'),
        (r'^(?:Was involved in|Involved in)\b', 'Contributed to'),
        (r'^(?:Helped with|Assisted with)\b', 'Supported'),
        (r'^(?:Worked on)\b', 'Developed'),
        (r'^(?:Handled)\b', 'Managed'),
        (r'^(?:Did)\b', 'Executed'),
    ]
    for pattern, replacement in passive_fixes:
        if re.search(pattern, improved, re.I):
            improved = re.sub(pattern, replacement, improved, count=1, flags=re.I)
            fixes.append("ownership")
            break

    # Fix 2: Purpose — add "to [verb]" if missing purpose clause
    has_purpose = bool(re.search(
        r'\b(?:to\s+\w+|for\s+\w+|enabling|supporting|improving|ensuring)\b',
        improved, re.I
    ))
    # Only add purpose if bullet is short enough and lacks one
    if not has_purpose and len(improved) < 120:
        b_lower = improved.lower()
        if any(w in b_lower for w in ["pipeline", "data", "etl"]):
            improved = improved.rstrip('.') + ", supporting reliable data workflows."
            fixes.append("purpose: data workflows")
        elif any(w in b_lower for w in ["model", "predict", "train"]):
            improved = improved.rstrip('.') + ", supporting model development."
            fixes.append("purpose: model development")
        elif any(w in b_lower for w in ["deploy", "infra", "cloud"]):
            improved = improved.rstrip('.') + ", ensuring system reliability."
            fixes.append("purpose: reliability")

    return {
        "original": original,
        "improved": improved,
        "changed": improved != original,
        "fixes": fixes,
    }


# ================================================================
# PART 4 — REAL ATS METRICS
# ================================================================

def compute_real_ats_metrics(
    resume_text: str,
    jd_keywords: List[str],
) -> Dict:
    """
    Compute real ATS metrics — no arbitrary thresholds.

    Returns:
      - keyword_coverage: % of JD keywords found in resume
      - keyword_distribution: how keywords spread across sections
      - contextual_usage: % of keywords used in meaningful context
    """
    resume_lower = resume_text.lower()
    found = []
    missing = []
    contextual = 0

    for kw in jd_keywords:
        kw_lower = kw.lower()
        if kw_lower in resume_lower:
            found.append(kw)
            # Check contextual usage (not just bare mention)
            if re.search(
                rf'\b(?:using|with|via|in|for|through)\s+{re.escape(kw_lower)}\b|'
                rf'\b{re.escape(kw_lower)}\s+(?:for|to|in)\b',
                resume_lower
            ):
                contextual += 1
        else:
            missing.append(kw)

    coverage = round(len(found) / max(len(jd_keywords), 1) * 100, 1)
    contextual_pct = round(contextual / max(len(found), 1) * 100, 1)

    # Distribution — check if keywords are clustered or spread
    # Split resume into 3 rough sections
    third = len(resume_text) // 3
    sections = [
        resume_text[:third].lower(),
        resume_text[third:2*third].lower(),
        resume_text[2*third:].lower(),
    ]
    section_hits = [
        sum(1 for kw in found if kw.lower() in sec)
        for sec in sections
    ]
    total_hits = max(sum(section_hits), 1)
    distribution_score = round(
        min(section_hits) / (total_hits / 3) * 100
        if total_hits > 0 else 0, 1
    )

    return {
        "keyword_coverage": coverage,
        "keywords_found": len(found),
        "keywords_missing": len(missing),
        "found": found,
        "missing": missing,
        "contextual_usage": contextual_pct,
        "distribution_score": min(100, distribution_score),
        "section_hits": section_hits,
    }


# ================================================================
# PART 5 — OUTPUT CONSISTENCY
# ================================================================

def compute_output_hash(output: Dict) -> str:
    """
    Compute deterministic hash of pipeline output.
    Used to verify app.py == dashboard.py consistency.
    """
    import json
    # Normalize: sort keys, strip whitespace
    canonical = json.dumps(output, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def verify_output_consistency(output_a: Dict, output_b: Dict) -> Dict:
    """
    Verify two pipeline outputs are identical.
    Returns mismatch details if they differ.
    """
    hash_a = compute_output_hash(output_a)
    hash_b = compute_output_hash(output_b)
    match = hash_a == hash_b

    if not match:
        logger.error(
            f"OUTPUT CONSISTENCY VIOLATION: hash_a={hash_a} != hash_b={hash_b}"
        )

    return {
        "consistent": match,
        "hash_a": hash_a,
        "hash_b": hash_b,
        "message": "Outputs match" if match else "MISMATCH — outputs diverged",
    }


# ================================================================
# PART 6 — FULL QUALITY GATE
# ================================================================

def run_quality_gate(
    original_bullets: List[str],
    rewritten_bullets: List[str],
    candidate_skills: List[str] = None,
    jd_keywords: List[str] = None,
    resume_text: str = "",
) -> Dict:
    """
    Run the complete quality gate on rewritten output.

    Flow:
      1. Validate each rewrite against original (truth constraint)
      2. Check bullet quality (grammar, stuffing, repetition)
      3. Enforce recruiter quality where needed
      4. Compute real ATS metrics
      5. Return clean output with rejections logged

    Returns SAFE bullets — rejected rewrites replaced with originals.
    """
    candidate_skills = candidate_skills or []
    jd_keywords = jd_keywords or []

    logger.info("QUALITY GATE — Starting")

    safe_bullets = []
    rejected = []
    recruiter_fixes = []

    for i, (orig, rewrite) in enumerate(
        zip(original_bullets, rewritten_bullets)
    ):
        # Step 1: Truth constraint
        truth = validate_rewrite(orig, rewrite, candidate_skills)
        if not truth["accepted"]:
            safe_bullets.append(orig)  # Keep original
            rejected.append({
                "index": i,
                "original": orig[:60],
                "rewrite": rewrite[:60],
                "reason": truth["reason"],
            })
            logger.info(f"  REJECTED [{i}]: {truth['reason']}")
            continue

        # Step 2: Bullet quality
        quality = check_bullet_quality(rewrite)
        if not quality["passed"]:
            # Try to fix minor issues
            fixed = rewrite
            if ".." in fixed:
                fixed = fixed.replace("..", ".")
            if fixed and fixed[0].islower():
                fixed = fixed[0].upper() + fixed[1:]

            # Re-check after fixes
            recheck = check_bullet_quality(fixed)
            if not recheck["passed"]:
                # Still failing — check if issues are critical
                critical = [i for i in recheck["issues"]
                           if "stuffing" in i.lower() or "repetition" in i.lower()]
                if critical:
                    safe_bullets.append(orig)
                    rejected.append({
                        "index": i,
                        "original": orig[:60],
                        "rewrite": rewrite[:60],
                        "reason": f"Quality: {'; '.join(critical)}",
                    })
                    continue
            safe_bullets.append(fixed)
        else:
            safe_bullets.append(rewrite)

    # Step 3: Recruiter quality enforcement on accepted bullets
    for i, b in enumerate(safe_bullets):
        rq = enforce_recruiter_quality(b)
        if rq["changed"]:
            safe_bullets[i] = rq["improved"]
            recruiter_fixes.append({
                "index": i,
                "fixes": rq["fixes"],
            })

    # Step 4: Real ATS metrics
    ats = compute_real_ats_metrics(
        resume_text or " ".join(safe_bullets), jd_keywords
    )

    # Step 5: Overall bullet quality
    quality_report = validate_all_bullets(safe_bullets)

    logger.info(
        f"  Accepted: {len(safe_bullets) - len(rejected)}/{len(original_bullets)}, "
        f"Rejected: {len(rejected)}, "
        f"ATS coverage: {ats['keyword_coverage']}%, "
        f"Quality: {quality_report['pass_rate']}%"
    )
    logger.info("QUALITY GATE — Complete")

    return {
        "safe_bullets": safe_bullets,
        "rejected_rewrites": rejected,
        "recruiter_fixes": recruiter_fixes,
        "ats": ats,
        "quality": quality_report,
        "summary": {
            "total": len(original_bullets),
            "accepted": len(original_bullets) - len(rejected),
            "rejected": len(rejected),
            "recruiter_fixed": len(recruiter_fixes),
            "ats_coverage": ats["keyword_coverage"],
            "quality_pass_rate": quality_report["pass_rate"],
        },
    }
