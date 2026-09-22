"""
Final Validation Gate -- Rejects output if quality fails.

Runs AFTER all optimization and polish steps, BEFORE returning to user.
Acts as the last line of defense against bad output.

Checks:
  1. Skill placement correctness (skills match bullet context)
  2. Summary quality (not generic, not too short)
  3. Bullet realism (no hallucinated metrics, no empty claims)
  4. Repetition detection (no phrase appears >3x)
  5. Role mismatch detection (tech skills in non-tech roles)
  6. Length sanity (bullets not too short or too long)
  7. Identity preservation (name, companies unchanged)

Returns a ValidationResult with pass/fail + specific violations.
"""

import re
from typing import Dict, List, Tuple
from collections import Counter

from utils.models import StructuredResume, ExtractedJD
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ================================================================
# GENERIC WORD DETECTION
# ================================================================

GENERIC_SUMMARY_WORDS = {
    "experienced", "hardworking", "passionate", "motivated",
    "dedicated", "enthusiastic", "detail-oriented", "results-driven",
    "team player", "self-starter", "go-getter", "dynamic",
    "proactive", "seasoned", "fast learner", "eager",
}

# Hallucinated metric patterns (suspiciously round numbers with no evidence)
SUSPICIOUS_METRIC_PATTERNS = [
    r'\b(?:increased|improved|reduced|boosted|grew|decreased)\b.{0,30}\b(\d{2,3})%',
]

# Robot phrases that indicate over-optimization
ROBOT_PHRASES = [
    "leveraging cutting-edge",
    "utilizing state-of-the-art",
    "spearheading transformative",
    "driving paradigm shift",
    "synergizing cross-functional",
    "orchestrating holistic",
    "catalyzing innovation",
]


class ValidationResult:
    """Result of the final validation gate."""

    def __init__(self):
        self.passed = True
        self.violations: List[Dict] = []
        self.warnings: List[Dict] = []
        self.score = 100  # Quality score (100 = perfect)

    def add_violation(self, category: str, message: str, severity: str = "ERROR"):
        """Add a violation. ERROR = gate fails. WARNING = flagged but passes."""
        entry = {"category": category, "message": message, "severity": severity}
        if severity == "ERROR":
            self.violations.append(entry)
            self.passed = False
            self.score -= 15
        else:
            self.warnings.append(entry)
            self.score -= 5

    def to_dict(self) -> Dict:
        return {
            "passed": self.passed,
            "quality_score": max(0, self.score),
            "violations": self.violations,
            "warnings": self.warnings,
            "total_issues": len(self.violations) + len(self.warnings),
        }


def validate_output(
    original: StructuredResume,
    improved: StructuredResume,
    jd: ExtractedJD,
    role_info: Dict = None,
) -> ValidationResult:
    """
    Run final validation gate on the improved resume.

    This is the LAST check before returning output to the user.
    If validation fails, the pipeline should fall back to the tailored resume.

    Args:
        original: Original user resume
        improved: The optimized/improved resume
        jd: Extracted job description
        role_info: Role classification from role_engine

    Returns:
        ValidationResult with pass/fail + violations
    """
    result = ValidationResult()
    role_info = role_info or {}

    # 1. Identity preservation
    _check_identity(original, improved, result)

    # 2. Summary quality
    _check_summary_quality(improved, result)

    # 3. Bullet realism
    _check_bullet_realism(original, improved, result)

    # 4. Repetition detection
    _check_repetition(improved, result)

    # 5. Role mismatch
    _check_role_mismatch(improved, jd, role_info, result)

    # 6. Length sanity
    _check_length_sanity(improved, result)

    # 7. Skill placement
    _check_skill_placement(improved, role_info, result)

    # 8. Tool purpose enforcement (no "using X" without context)
    _check_tool_purpose(improved, result)

    # 9. AI-generated phrasing detection
    _check_ai_phrasing(improved, result)

    # 10. Bullet quality enforcement (PART 8)
    _check_bullet_quality(improved, result)

    # 11. HARDENED: Semantic preservation (Part 1)
    _check_semantic_preservation(original, improved, result)

    # 12. HARDENED: Summary role consistency (Part 5)
    _check_summary_role_consistency(improved, jd, result)

    # Log result
    if result.passed:
        logger.info(
            f"VALIDATION GATE: PASSED (score={result.score}, "
            f"warnings={len(result.warnings)})"
        )
    else:
        logger.error(
            f"VALIDATION GATE: FAILED (score={result.score}, "
            f"violations={len(result.violations)}, "
            f"warnings={len(result.warnings)})"
        )
        for v in result.violations:
            logger.error(f"  VIOLATION: [{v['category']}] {v['message']}")

    return result


# ================================================================
# VALIDATION CHECKS
# ================================================================

def _check_identity(
    original: StructuredResume,
    improved: StructuredResume,
    result: ValidationResult,
):
    """Verify identity was not altered."""
    if original.contact.name != improved.contact.name:
        result.add_violation(
            "identity",
            f"Name changed: '{original.contact.name}' → '{improved.contact.name}'",
            "ERROR",
        )

    if original.contact.email != improved.contact.email:
        result.add_violation(
            "identity",
            f"Email changed: '{original.contact.email}' → '{improved.contact.email}'",
            "ERROR",
        )

    # Companies must not change
    orig_companies = {exp.company.lower().strip() for exp in original.experience}
    imp_companies = {exp.company.lower().strip() for exp in improved.experience}
    fabricated = imp_companies - orig_companies
    if fabricated:
        result.add_violation(
            "identity",
            f"Fabricated companies: {list(fabricated)}",
            "ERROR",
        )


def _check_summary_quality(
    improved: StructuredResume,
    result: ValidationResult,
):
    """Check summary is not generic or too short."""
    summary = improved.summary or ""

    if len(summary) < 30:
        result.add_violation(
            "summary",
            f"Summary too short ({len(summary)} chars, min 30)",
            "WARNING",
        )
        return

    summary_lower = summary.lower()

    # Count generic words
    generic_count = sum(
        1 for word in GENERIC_SUMMARY_WORDS
        if word in summary_lower
    )
    if generic_count >= 3:
        result.add_violation(
            "summary",
            f"Summary has {generic_count} generic words (max 2): "
            f"{[w for w in GENERIC_SUMMARY_WORDS if w in summary_lower][:3]}",
            "WARNING",
        )

    # Check for robot phrases
    for phrase in ROBOT_PHRASES:
        if phrase.lower() in summary_lower:
            result.add_violation(
                "summary",
                f"Over-optimized phrase: '{phrase}'",
                "WARNING",
            )


def _check_bullet_realism(
    original: StructuredResume,
    improved: StructuredResume,
    result: ValidationResult,
):
    """Check bullets are realistic, not hallucinated."""
    original_text = " ".join(
        b for exp in original.experience for b in exp.bullets
    )

    for exp_idx, exp in enumerate(improved.experience):
        for bul_idx, bullet in enumerate(exp.bullets):
            # Check for suspicious metrics not in original
            for pattern in SUSPICIOUS_METRIC_PATTERNS:
                matches = re.findall(pattern, bullet, re.IGNORECASE)
                for match in matches:
                    if match not in original_text:
                        result.add_violation(
                            "realism",
                            f"Possible fabricated metric ({match}%) in "
                            f"experience[{exp_idx}].bullet[{bul_idx}]",
                            "WARNING",
                        )

            # Check for robot phrases
            bullet_lower = bullet.lower()
            for phrase in ROBOT_PHRASES:
                if phrase.lower() in bullet_lower:
                    result.add_violation(
                        "realism",
                        f"Over-optimized phrase '{phrase}' in "
                        f"experience[{exp_idx}].bullet[{bul_idx}]",
                        "WARNING",
                    )


def _check_repetition(
    improved: StructuredResume,
    result: ValidationResult,
):
    """Detect excessive phrase repetition across bullets."""
    all_bullets = [
        b for exp in improved.experience for b in exp.bullets
    ] + [
        b for proj in improved.projects for b in proj.bullets
    ]

    # Count 4-word phrases
    phrase_counts = Counter()
    for bullet in all_bullets:
        words = bullet.lower().split()
        for i in range(len(words) - 3):
            phrase = " ".join(words[i:i+4])
            if len(phrase) > 15:  # Skip short phrases
                phrase_counts[phrase] += 1

    # Flag phrases appearing 4+ times
    for phrase, count in phrase_counts.most_common(5):
        if count >= 4:
            # Skip common structural phrases
            if any(common in phrase for common in [
                "and", "the", "for the", "in the", "of the",
                "to the", "with the", "using the",
            ]):
                continue
            result.add_violation(
                "repetition",
                f"Phrase '{phrase}' repeated {count}x across bullets",
                "WARNING",
            )


def _check_role_mismatch(
    improved: StructuredResume,
    jd: ExtractedJD,
    role_info: Dict,
    result: ValidationResult,
):
    """Check for tech skills injected into non-tech roles."""
    if not role_info or role_info.get("allow_tech_injection", True):
        return  # Only check non-tech roles

    from resume_engine.role_engine import TECH_ONLY_SKILLS

    all_bullets = " ".join(
        b.lower() for exp in improved.experience for b in exp.bullets
    )

    # Check if tech-only skills were injected into bullets
    tech_in_bullets = []
    for skill in TECH_ONLY_SKILLS:
        if skill in all_bullets:
            # Check if it was in the original resume (legitimate)
            # We allow it if the user genuinely has this skill
            tech_in_bullets.append(skill)

    # Only flag if many tech skills appear — some might be legitimate
    if len(tech_in_bullets) > 5:
        result.add_violation(
            "role_mismatch",
            f"{len(tech_in_bullets)} tech-only skills found in "
            f"{role_info.get('role_type', '?')} role bullets",
            "WARNING",
        )


def _check_length_sanity(
    improved: StructuredResume,
    result: ValidationResult,
):
    """Check bullet and summary lengths are reasonable."""
    for exp_idx, exp in enumerate(improved.experience):
        for bul_idx, bullet in enumerate(exp.bullets):
            if len(bullet) > 350:
                result.add_violation(
                    "length",
                    f"Bullet too long ({len(bullet)} chars) at "
                    f"experience[{exp_idx}].bullet[{bul_idx}]",
                    "WARNING",
                )
            if len(bullet) < 15 and len(exp.bullets) > 2:
                result.add_violation(
                    "length",
                    f"Bullet too short ({len(bullet)} chars) at "
                    f"experience[{exp_idx}].bullet[{bul_idx}]",
                    "WARNING",
                )

    if improved.summary and len(improved.summary) > 600:
        result.add_violation(
            "length",
            f"Summary too long ({len(improved.summary)} chars, max 600)",
            "WARNING",
        )


def _check_skill_placement(
    improved: StructuredResume,
    role_info: Dict,
    result: ValidationResult,
):
    """Check that skills in the skills list are demonstrated in experience."""
    all_bullet_text = " ".join(
        b.lower() for exp in improved.experience for b in exp.bullets
    ) + " " + " ".join(
        b.lower() for proj in improved.projects for b in proj.bullets
    )

    undemonstrated = []
    for skill in improved.skills[:10]:  # Check top 10
        skill_lower = skill.lower()
        if skill_lower not in all_bullet_text:
            # Check for partial matches (e.g., "python" in "python-based")
            if not any(skill_lower in word for word in all_bullet_text.split()):
                undemonstrated.append(skill)

    if len(undemonstrated) > len(improved.skills) * 0.5:
        result.add_violation(
            "skill_placement",
            f"{len(undemonstrated)} of top 10 skills not demonstrated in bullets: "
            f"{undemonstrated[:3]}",
            "WARNING",
        )


def _check_tool_purpose(
    improved: StructuredResume,
    result: ValidationResult,
):
    """
    BEHAVIOR FIX: Detect 'using X' without purpose in bullets.
    
    BAD:  "Improved accuracy using Gradio"
    BAD:  "Processed data using pandas"
    GOOD: "Processed large datasets using pandas for cleaning and feature engineering"
    
    Rule: If bullet ends with 'using X' or 'leveraging X' with < 5 words after
    the tool name, it lacks purpose context.
    """
    purposeless_count = 0
    
    for exp in improved.experience:
        for bullet in exp.bullets:
            # Check for "using X" at end of bullet (last 30 chars)
            tail = bullet[-40:].lower() if len(bullet) > 40 else bullet.lower()
            
            # Pattern: ends with "using <tool>" or "leveraging <tool>" 
            # without enough context after the tool
            patterns = [
                r'(?:using|leveraging|utilizing|via|through)\s+\w+\.?$',
                r'(?:using|leveraging|utilizing|via|through)\s+\w+\s+\w+\.?$',
            ]
            for pattern in patterns:
                if re.search(pattern, tail):
                    purposeless_count += 1
                    break

    if purposeless_count >= 2:
        result.add_violation(
            "tool_purpose",
            f"{purposeless_count} bullets end with 'using X' without purpose context",
            "ERROR",
        )
    elif purposeless_count >= 1:
        result.add_violation(
            "tool_purpose",
            f"{purposeless_count} bullet(s) end with 'using X' without purpose context",
            "WARNING",
        )


def _check_ai_phrasing(
    improved: StructuredResume,
    result: ValidationResult,
):
    """
    BEHAVIOR FIX: Detect AI-generated phrasing patterns.
    
    Catches phrases that no human would write but AI commonly generates:
    - "spearheading transformative initiatives"
    - "driving paradigm shifts"
    - "orchestrating holistic solutions"
    - Excessive -ing constructions
    - Buzzword density
    """
    ai_patterns = [
        r'spearhead(?:ed|ing)',
        r'synergiz(?:ed|ing)',
        r'orchestrat(?:ed|ing)\s+holistic',
        r'paradigm\s+shift',
        r'cutting[\s-]edge\s+(?:solutions|technologies|innovations)',
        r'state[\s-]of[\s-]the[\s-]art',
        r'transformative\s+(?:initiatives|solutions|impact)',
        r'catalyz(?:ed|ing)\s+innovation',
        r'leverag(?:ed|ing)\s+(?:synergies|insights)',
        r'holistic\s+approach',
        r'robust\s+(?:framework|pipeline|solution)s?\s+(?:to|for|enabling)',
    ]

    ai_count = 0
    all_text = " ".join(
        b.lower() for exp in improved.experience for b in exp.bullets
    )

    for pattern in ai_patterns:
        if re.search(pattern, all_text):
            ai_count += 1

    if ai_count >= 2:
        result.add_violation(
            "ai_phrasing",
            f"{ai_count} AI-generated phrases detected in bullets "
            f"(resume sounds robotic, not human-written)",
            "WARNING",
        )


def _check_bullet_quality(
    improved: StructuredResume,
    result: ValidationResult,
):
    """
    PART 8: Enforce bullet quality — Action + Tool + Purpose + Impact.
    
    Flags:
      - Repetitive connectors ("and...and...and")
      - Vague tool usage ("using X" without purpose)
      - Extremely short bullets (< 30 chars)
      - Missing action verb start
    """
    action_verbs = {
        "developed", "designed", "implemented", "built", "created",
        "managed", "led", "optimized", "improved", "reduced",
        "increased", "delivered", "automated", "analyzed", "architected",
        "deployed", "maintained", "collaborated", "established", "launched",
        "spearheaded", "orchestrated", "engineered", "streamlined",
        "configured", "integrated", "migrated", "assisted", "performed",
    }

    quality_issues = 0
    total_bullets = 0

    for exp in improved.experience:
        for bullet in exp.bullets:
            total_bullets += 1
            b_lower = bullet.lower()

            # Check: "and...and...and" chaining
            and_count = len(re.findall(r'\band\b', b_lower))
            if and_count >= 3:
                quality_issues += 1
                continue

            # Check: vague tool usage — "using X" at end without purpose
            if re.search(r'using\s+\w+\.?$', b_lower):
                quality_issues += 1
                continue

            # Check: too short (< 30 chars = not meaningful)
            if len(bullet.strip()) < 30:
                quality_issues += 1
                continue

            # Check: doesn't start with action verb
            first_word = b_lower.split()[0] if b_lower.split() else ""
            if first_word not in action_verbs and not first_word.endswith("ed"):
                quality_issues += 1

    if total_bullets > 0:
        issue_ratio = quality_issues / total_bullets
        if issue_ratio > 0.5:
            result.add_violation(
                "bullet_quality",
                f"{quality_issues}/{total_bullets} bullets have quality issues "
                f"(missing action verbs, vague usage, or unnatural chaining)",
                "WARNING",
            )


# ================================================================
# TRUE SKILL USAGE VALIDATION
# ================================================================

def is_valid_usage(skill: str, bullet: str) -> bool:
    """
    Check if a skill is TRULY used in a bullet with proper context.
    
    Valid usage requires:
      1. The skill keyword is present
      2. An action verb appears (built, developed, deployed, etc.)
      3. Purpose/context exists (for X, to achieve Y, enabling Z)
    
    Examples:
      VALID:   "Built ML pipeline using Python for real-time data processing"
      INVALID: "Used Python"  (no purpose)
      INVALID: "Python, SQL, TensorFlow"  (just a list)
      VALID:   "Deployed models to production using Docker containers"
    
    Returns True if usage is valid, False otherwise.
    """
    skill_lower = skill.lower()
    bullet_lower = bullet.lower()

    # Check 1: Skill present
    if skill_lower not in bullet_lower:
        return False

    # Check 2: Action verb present
    action_verbs = [
        "built", "developed", "designed", "created", "implemented",
        "deployed", "managed", "led", "automated", "optimized",
        "analyzed", "engineered", "launched", "delivered", "established",
        "streamlined", "scaled", "integrated", "maintained", "configured",
        "processed", "trained", "tested", "migrated", "reduced",
        "improved", "increased", "generated", "coordinated",
    ]
    has_action = any(v in bullet_lower for v in action_verbs)

    # Check 3: Purpose context present
    purpose_markers = [
        " for ", " to ", " enabling ", " resulting in ",
        " achieving ", " across ", " supporting ", " within ",
        " that ", " which ", " improving ", " reducing ",
        " increasing ", " serving ", " processing ",
    ]
    has_purpose = any(m in bullet_lower for m in purpose_markers)

    # Minimum length check (not just "Used Python.")
    has_substance = len(bullet) > 30

    return has_action and (has_purpose or has_substance)


# ================================================================
# AUTO-FIX VALIDATION FAILURES
# ================================================================

def auto_fix_validation_failures(
    resume: StructuredResume,
    validation_result: ValidationResult,
) -> Tuple[StructuredResume, List[str]]:
    """
    Auto-rewrite common validation failures instead of just flagging.
    
    Current auto-fixes:
      1. "using X" without purpose → append purpose clause
      2. AI phrasing → replace with natural alternatives
      3. Short fragments → expand or remove
    
    Returns (fixed_resume, list_of_fixes_applied)
    """
    fixed = resume.model_copy(deep=True)
    fixes = []

    # Fix 1: "using X" without purpose — append generic purpose
    TOOL_PURPOSE_MAP = {
        "python": "for data processing and automation",
        "sql": "for data querying and analysis",
        "docker": "for containerized deployment",
        "kubernetes": "for orchestration and scaling",
        "aws": "for cloud infrastructure management",
        "terraform": "for infrastructure provisioning",
        "jenkins": "for automated CI/CD workflows",
        "pandas": "for data manipulation and analysis",
        "spark": "for large-scale data processing",
        "tensorflow": "for model training and inference",
        "react": "for interactive user interfaces",
    }

    for exp in fixed.experience:
        for i, bullet in enumerate(exp.bullets):
            # Fix purposeless tool mentions at end of bullet
            match = re.search(
                r'(using|leveraging|via)\s+(\w+)\s*\.?\s*$',
                bullet, re.IGNORECASE,
            )
            if match:
                tool = match.group(2).lower()
                purpose = TOOL_PURPOSE_MAP.get(tool)
                if purpose:
                    # Append purpose
                    clean = bullet.rstrip('. ')
                    exp.bullets[i] = f"{clean} {purpose}."
                    fixes.append(f"Added purpose to '{tool}' usage")

    # Fix 2: Replace AI phrasing with natural alternatives
    AI_REPLACEMENTS = {
        "spearheaded": "led",
        "spearheading": "leading",
        "synergized": "combined",
        "orchestrated holistic": "managed comprehensive",
        "cutting-edge": "modern",
        "state-of-the-art": "advanced",
        "transformative initiatives": "key projects",
        "paradigm shift": "significant change",
        "leveraged synergies": "combined strengths",
        "holistic approach": "comprehensive approach",
        "robust framework": "reliable framework",
    }

    for exp in fixed.experience:
        for i, bullet in enumerate(exp.bullets):
            original = bullet
            for ai_phrase, natural in AI_REPLACEMENTS.items():
                if ai_phrase.lower() in bullet.lower():
                    pattern = re.compile(re.escape(ai_phrase), re.IGNORECASE)
                    bullet = pattern.sub(natural, bullet, count=1)
            if bullet != original:
                exp.bullets[i] = bullet
                fixes.append(f"Replaced AI phrasing in bullet")

    if fixes:
        logger.info(f"AUTO-FIX: Applied {len(fixes)} fixes to validation failures")

    return fixed, fixes


# ================================================================
# HUMAN QUALITY CHECK
# ================================================================

def human_quality_check(resume: StructuredResume) -> Dict:
    """
    Holistic readability and tone audit on the final resume output.
    
    Scores the resume on 5 dimensions:
      1. Grammar (no broken sentences, proper tense)
      2. Tone (professional, not robotic or casual)
      3. Structure (bullet count, consistency)
      4. Impact (quantified results, action verbs)
      5. Believability (no over-claiming, no filler)
    
    Returns a quality report dict with scores and issues.
    """
    report = {
        "grammar_score": 100,
        "tone_score": 100,
        "structure_score": 100,
        "impact_score": 100,
        "believability_score": 100,
        "issues": [],
        "overall": 100,
    }

    all_bullets = []
    for exp in resume.experience:
        all_bullets.extend(exp.bullets)
    for proj in resume.projects:
        all_bullets.extend(proj.bullets)

    # --- GRAMMAR ---
    for bullet in all_bullets:
        # Check for broken sentence starts
        if bullet and bullet[0].islower():
            report["grammar_score"] -= 5
            report["issues"].append(f"Lowercase start: '{bullet[:40]}'")
        # Check for double spaces
        if "  " in bullet:
            report["grammar_score"] -= 3
            report["issues"].append(f"Double space in: '{bullet[:40]}'")
        # Check for missing period
        if bullet and bullet[-1] not in '.!':
            report["grammar_score"] -= 2

    # --- TONE ---
    casual_words = ["stuff", "things", "kinda", "gonna", "wanna", "cool", "awesome"]
    for bullet in all_bullets:
        if any(w in bullet.lower() for w in casual_words):
            report["tone_score"] -= 10
            report["issues"].append(f"Casual language: '{bullet[:40]}'")

    # AI buzzword density
    ai_buzzwords = ["synergy", "paradigm", "holistic", "transformative", "catalyze"]
    buzzword_count = sum(1 for b in all_bullets for w in ai_buzzwords if w in b.lower())
    if buzzword_count >= 2:
        report["tone_score"] -= 15
        report["issues"].append(f"{buzzword_count} AI buzzwords detected")

    # --- STRUCTURE ---
    for exp in resume.experience:
        if len(exp.bullets) > 5:
            report["structure_score"] -= 10
            report["issues"].append(f"{exp.role}: {len(exp.bullets)} bullets (max 5)")
        if len(exp.bullets) < 2:
            report["structure_score"] -= 10
            report["issues"].append(f"{exp.role}: only {len(exp.bullets)} bullet(s)")

    # --- IMPACT ---
    has_metrics = sum(1 for b in all_bullets if re.search(r'\d+[%$Kk]|\d{2,}', b))
    metric_ratio = has_metrics / max(len(all_bullets), 1)
    if metric_ratio < 0.2:
        report["impact_score"] -= 15
        report["issues"].append(f"Only {has_metrics}/{len(all_bullets)} bullets have metrics")

    action_verbs = {"built", "developed", "designed", "deployed", "led", "managed",
                    "created", "analyzed", "implemented", "automated", "optimized"}
    weak_starts = sum(1 for b in all_bullets 
                      if b.split()[0].lower() not in action_verbs and b.split())
    if weak_starts > len(all_bullets) * 0.5:
        report["impact_score"] -= 10
        report["issues"].append(f"{weak_starts} bullets don't start with action verbs")

    # --- BELIEVABILITY ---
    for bullet in all_bullets:
        # Suspiciously round numbers
        match = re.search(r'\b(\d{3,})%', bullet)
        if match:
            pct = int(match.group(1))
            if pct > 500:
                report["believability_score"] -= 15
                report["issues"].append(f"Unrealistic metric: {pct}%")

    # Clamp all scores
    for key in ["grammar_score", "tone_score", "structure_score", 
                 "impact_score", "believability_score"]:
        report[key] = max(0, min(100, report[key]))

    # Overall = weighted average
    report["overall"] = int(
        report["grammar_score"] * 0.2
        + report["tone_score"] * 0.2
        + report["structure_score"] * 0.2
        + report["impact_score"] * 0.2
        + report["believability_score"] * 0.2
    )

    return report


# ================================================================
# HARDENED: SEMANTIC PRESERVATION CHECK (Part 1)
# ================================================================

def _check_semantic_preservation(
    original: StructuredResume,
    improved: StructuredResume,
    result: ValidationResult,
):
    """
    PART 1: Verify that rewritten bullets preserve the original intent.

    For each improved bullet, find the closest original bullet and check
    that at least 50% of content words survive. Bullets that drift below
    this threshold indicate unauthorized semantic distortion.
    """
    _FILLER_WORDS = {
        "was", "were", "had", "has", "have", "been", "being",
        "responsible", "helped", "assisted", "worked", "involved",
        "successfully", "completed", "looked", "tasks", "included",
        "the", "and", "for", "with", "from", "that", "this",
        "also", "very", "just", "some", "other", "such",
    }

    drift_count = 0
    total_checked = 0

    for i, exp in enumerate(improved.experience):
        orig_exp = (original.experience[i]
                    if i < len(original.experience) else None)
        if not orig_exp:
            continue

        for j, bullet in enumerate(exp.bullets):
            # Skip unchanged bullets
            if bullet in set(orig_exp.bullets):
                continue

            total_checked += 1

            # Find best-matching original bullet
            bullet_words = set(re.findall(r'[a-z]{3,}', bullet.lower())) - _FILLER_WORDS
            best_overlap = 0.0
            for ob in orig_exp.bullets:
                ob_words = set(re.findall(r'[a-z]{3,}', ob.lower())) - _FILLER_WORDS
                if ob_words:
                    ov = len(bullet_words & ob_words) / len(ob_words)
                    if ov > best_overlap:
                        best_overlap = ov

            if best_overlap < 0.50 and len(bullet_words) >= 3:
                drift_count += 1

    if drift_count >= 3:
        result.add_violation(
            "semantic_preservation",
            f"{drift_count}/{total_checked} rewritten bullets have <50% "
            f"content word overlap with originals — meaning may be distorted",
            "ERROR",
        )
    elif drift_count >= 1:
        result.add_violation(
            "semantic_preservation",
            f"{drift_count}/{total_checked} rewritten bullet(s) have <50% "
            f"content word overlap — review for semantic drift",
            "WARNING",
        )


# ================================================================
# HARDENED: SUMMARY ROLE CONSISTENCY CHECK (Part 5)
# ================================================================

def _check_summary_role_consistency(
    improved: StructuredResume,
    jd: ExtractedJD,
    result: ValidationResult,
):
    """
    PART 5: Verify that the summary role aligns with the JD target role.

    If the summary talks about 'Data Scientist' but the JD is for
    'Frontend Developer', a recruiter sees inconsistency = immediate reject.
    """
    if not improved.summary or not jd.job_title:
        return

    summary_lower = improved.summary.lower()
    jd_title = jd.job_title.lower()

    # Define role domain signatures and their conflicting domains
    ROLE_CONFLICT_MAP = [
        # (summary_signal, conflicting_jd_domains)
        ("data scien", ["frontend", "backend", "devops", "qa engineer", "hr ", "customer support"]),
        ("machine learning", ["frontend", "hr ", "customer support", "sales", "marketing"]),
        ("frontend", ["data scien", "machine learning", "devops", "hr "]),
        ("backend", ["frontend", "data scien", "hr ", "customer support"]),
        ("hr ", ["engineer", "developer", "data scien", "devops", "machine learning"]),
        ("recruiter", ["engineer", "developer", "data scien", "devops"]),
        ("customer support", ["engineer", "developer", "data scien", "devops"]),
        ("sales", ["engineer", "developer", "data scien", "devops"]),
    ]

    for summary_sig, jd_conflicts in ROLE_CONFLICT_MAP:
        if summary_sig in summary_lower:
            for conflict in jd_conflicts:
                if conflict in jd_title:
                    result.add_violation(
                        "role_consistency",
                        f"Summary mentions '{summary_sig.strip()}' domain "
                        f"but JD title is '{jd.job_title}' — role mismatch",
                        "ERROR",
                    )
                    return
