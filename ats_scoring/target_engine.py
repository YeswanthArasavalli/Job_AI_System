"""
Target Score Engine -- Generates a roadmap to reach 90+ ATS score.

Given a current score and ATS breakdown, produces:
  1. Score gap analysis
  2. Prioritized improvement plan (high/medium/low impact)
  3. Score simulation (REAL scorer, not heuristic)
  4. "Why low" explanation

STRICT RULES:
  - Never suggest fake experience
  - Never suggest irrelevant skills
  - Only suggest real, achievable improvements
"""

from typing import Dict, List, Optional
from utils.models import ATSScoreReport, ScoreBreakdown, ExtractedJD, StructuredResume
from utils.logger import setup_logger

logger = setup_logger(__name__)

TARGET_SCORE = 90


def generate_target_plan(
    report: ATSScoreReport,
    breakdown: ScoreBreakdown,
    details: dict,
    jd: ExtractedJD,
    resume: Optional[StructuredResume] = None,
    scorer=None,
) -> dict:
    """
    Generate a roadmap to reach 90+ score.

    Args:
        report: Full ATS score report
        breakdown: Score breakdown (keyword, skills, etc.)
        details: Scoring details dict
        jd: Extracted JD data
        resume: Current resume (for real simulation)
        scorer: ATSScorer instance (for real simulation)

    Returns:
        dict with current_score, target_score, gap, improvement_plan, simulations, why_low
    """
    current = report.score_after
    gap = max(0, TARGET_SCORE - current)

    if gap <= 0:
        return {
            "current_score": current,
            "target_score": TARGET_SCORE,
            "gap": 0,
            "status": "TARGET_MET",
            "message": "Your resume already meets the target score!",
            "improvement_plan": {},
            "simulations": [],
            "why_low": [],
        }

    # -- Build improvement actions ------------------------
    high_impact = []
    medium_impact = []
    low_impact = []
    simulations = []

    # -- Missing skills analysis (with REAL simulation) ----
    missing_skills = report.missing_skills or []
    if missing_skills:
        top_missing = missing_skills[:5]
        for skill in top_missing[:3]:
            action = f"Add {skill} usage in at least 1 experience or project bullet"
            estimated = _simulate_skill_addition(skill, resume, jd, scorer, current)
            high_impact.append(action)
            simulations.append({
                "action": action,
                "estimated_points": estimated,
                "category": "skills_gap",
                "simulated": resume is not None and scorer is not None,
            })

    # -- Keyword gaps -------------------------------------
    missing_kw = report.missing_keywords or []
    if missing_kw:
        top_kw = [kw for kw in missing_kw if kw.lower() not in {s.lower() for s in missing_skills}][:3]
        if top_kw:
            action = f"Integrate keywords into bullet points: {', '.join(top_kw)}"
            high_impact.append(action)
            simulations.append({
                "action": action,
                "estimated_points": min(len(top_kw) * 3, 10),
                "category": "keyword_gap",
            })

    # -- Experience bullets -------------------------------
    if breakdown.experience_relevance < 50:
        action = "Rewrite experience bullets to mirror JD responsibilities using same action verbs"
        high_impact.append(action)
        simulations.append({
            "action": action,
            "estimated_points": 8,
            "category": "experience_alignment",
        })

    # -- Role alignment -----------------------------------
    if breakdown.role_alignment < 50:
        if jd.job_title:
            action = f"Set resume title to '{jd.job_title}' or close variant"
            medium_impact.append(action)
            simulations.append({
                "action": action,
                "estimated_points": 5,
                "category": "role_alignment",
            })

    # -- Education alignment ------------------------------
    if breakdown.education_fit < 60:
        edu_details = details.get("education", {})
        if edu_details.get("degree_level_met") == False:
            action = "Highlight relevant coursework, certifications, or bootcamps that compensate for degree gap"
            medium_impact.append(action)
            simulations.append({
                "action": action,
                "estimated_points": 5,
                "category": "education",
            })

    # -- Structure improvements ---------------------------
    if breakdown.resume_structure < 70:
        struct_details = details.get("structure", {})
        metric_bullets = struct_details.get("metric_bullets", 0)
        total_bullets = struct_details.get("total_bullets", 1)

        if total_bullets > 0 and metric_bullets / max(total_bullets, 1) < 0.3:
            action = "Add quantified achievements (%, $, numbers) to at least 50% of bullets"
            medium_impact.append(action)
            simulations.append({
                "action": action,
                "estimated_points": 6,
                "category": "structure",
            })

        if struct_details.get("has_summary") is False:
            action = "Add a 2-3 sentence professional summary aligned with the JD"
            medium_impact.append(action)
            simulations.append({
                "action": action,
                "estimated_points": 4,
                "category": "structure",
            })

    # -- Semantic coverage --------------------------------
    if report.semantic_score < 40:
        action = "Align project descriptions with JD responsibilities (use similar phrasing)"
        high_impact.append(action)
        simulations.append({
            "action": action,
            "estimated_points": 7,
            "category": "semantic",
        })

    # -- Low impact (polish) ------------------------------
    low_impact.extend([
        "Ensure consistent formatting (dates, bullet style, spacing)",
        "Remove filler words (various, some, helped with)",
        "Start every bullet with a strong action verb",
    ])

    # -- WHY LOW -- explanation layer ----------------------
    why_low = _explain_low_score(current, breakdown, details, report)

    # -- Estimated achievable score -----------------------
    total_simulated = sum(s["estimated_points"] for s in simulations)
    # Cap projection at realistic ceiling (never promise unreachable scores)
    max_ceiling = TARGET_SCORE  # 90
    if scorer and resume:
        # Use actual score_limit if available from scorer
        try:
            from pipeline.core import _compute_score_limit
            sl = _compute_score_limit(scorer, resume, jd, details)
            max_ceiling = min(max_ceiling, sl.max_possible_score)
        except Exception:
            pass
    projected_score = min(max_ceiling, current + total_simulated)

    # Determine realistic status
    if projected_score >= TARGET_SCORE:
        status = "ACHIEVABLE"
    elif projected_score >= current + 10:
        status = "IMPROVABLE"
    else:
        status = "STRETCH"

    plan = {
        "current_score": current,
        "target_score": TARGET_SCORE,
        "gap": round(gap, 1),
        "projected_score": round(projected_score, 1),
        "status": status,
        "improvement_plan": {
            "high_impact": high_impact,
            "medium_impact": medium_impact,
            "low_impact": low_impact,
        },
        "simulations": simulations,
        "total_simulated_gain": round(total_simulated, 1),
        "why_low": why_low,
    }

    logger.info(
        f"Target plan: {current} -> {projected_score} (gap={gap}, "
        f"simulated_gain={total_simulated}, ceiling={max_ceiling})"
    )

    return plan


def _simulate_skill_addition(
    skill: str,
    resume: Optional[StructuredResume],
    jd: ExtractedJD,
    scorer,
    current_score: float,
) -> int:
    """
    Simulate adding a skill to the resume and return REAL point gain.
    Falls back to heuristic if scorer/resume not available.
    """
    if resume is None or scorer is None:
        # Fallback heuristic
        return _heuristic_skill_points(skill, jd)

    try:
        # Clone resume, add skill, re-score
        simulated = resume.model_copy(deep=True)
        if skill.lower() not in {s.lower() for s in simulated.skills}:
            simulated.skills.append(skill)

        # Also add a bullet mentioning the skill (simulates realistic usage)
        if simulated.experience:
            simulated.experience[0].bullets.append(
                f"Applied {skill} for data-driven analysis and optimization."
            )

        new_score, _, _ = scorer.score(simulated, jd)
        gain = max(0, round(new_score - current_score, 1))
        logger.info(f"  Simulation: +{skill} -> +{gain} pts ({current_score} -> {new_score})")
        return max(gain, 1)  # At least 1 point (skill was missing)
    except Exception as e:
        logger.warning(f"  Simulation failed for {skill}: {e}")
        return _heuristic_skill_points(skill, jd)


def _heuristic_skill_points(skill: str, jd: ExtractedJD) -> int:
    """Fallback heuristic when real simulation isn't possible."""
    skill_lower = skill.lower()
    required_lower = {s.lower() for s in (jd.required_skills or [])}
    if skill_lower in required_lower:
        return 8
    return 4


def _explain_low_score(
    score: float,
    breakdown: ScoreBreakdown,
    details: dict,
    report: ATSScoreReport,
) -> List[str]:
    """Generate human-readable explanations for why the score is low."""
    reasons = []

    if breakdown.keyword_match < 40:
        matched = len(details.get("keywords", {}).get("matched", []))
        total = matched + len(details.get("keywords", {}).get("missing", []))
        reasons.append(
            f"Low keyword coverage: only {matched}/{total} JD keywords found in resume"
        )

    if breakdown.skills_match < 40:
        matched = len(details.get("skills", {}).get("matched", []))
        missing = details.get("skills", {}).get("missing", [])
        if missing:
            reasons.append(
                f"Missing {len(missing)} required skills: {', '.join(missing[:4])}"
            )

    if breakdown.experience_relevance < 40:
        reasons.append(
            "Experience bullets don't align with JD responsibilities -- "
            "consider mirroring the JD's action verbs and terminology"
        )

    if breakdown.role_alignment < 40:
        reasons.append(
            "Resume title/seniority doesn't match the target role"
        )

    if breakdown.education_fit < 40:
        edu_details = details.get("education", {})
        if edu_details.get("degree_level_met") == False:
            reasons.append("Education level doesn't meet JD requirements")
        if edu_details.get("field_match") == False:
            reasons.append("Education field doesn't align with JD domain")

    if report.semantic_score < 30:
        reasons.append(
            "Low semantic match -- resume language is too different from JD "
            "(try using similar phrases and terminology)"
        )

    # Risk flags
    for flag in (report.risk_flags or []):
        if "DOMAIN_MISMATCH" in flag:
            reasons.append("Your domain background doesn't match the target role")
        if "KEYWORD_STUFFING" in flag:
            reasons.append("Keyword repetition detected -- reduce duplication")

    if not reasons:
        reasons.append("Score is within an acceptable range -- minor polish needed")

    return reasons
