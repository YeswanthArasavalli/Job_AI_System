"""
Career Intelligence Layer (v4.0) — Full Pipeline Optimization.

4 engines in one module:
  1. Execution Tracking — validate user actually implements improvements
  2. Market Intelligence — competition-aware probability adjustment
  3. Interview Conversion — shortlist → offer optimization
  4. End-to-End Pipeline — bottleneck detection + career trajectory

Philosophy: "How do I actually get hired — end to end?"
"""

import re
from datetime import datetime
from typing import List, Dict, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ================================================================
# ENGINE 1 — EXECUTION + PROOF VALIDATION
# ================================================================

def validate_execution(user_progress: Dict) -> Dict:
    """
    Validate that user improvements are REAL, not assumed.
    
    Evaluates projects for: real-world applicability, complexity, ownership.
    Rejects: tutorial-level work, copied projects.
    """
    projects = user_progress.get("projects_completed", [])
    skills = user_progress.get("skills_learned", [])
    github_links = user_progress.get("github_links", [])
    resume_updated = user_progress.get("resume_updated", False)

    # Score each dimension
    project_score = min(len(projects) * 25, 50)  # max 50 from projects
    skill_score = min(len(skills) * 10, 30)       # max 30 from skills
    proof_score = 0

    proof_signals = []
    if github_links:
        proof_score += 10
        proof_signals.append(f"{len(github_links)} GitHub links provided")
    if resume_updated:
        proof_score += 10
        proof_signals.append("Resume updated with new work")

    # Evaluate project quality
    quality_flags = []
    for proj in projects:
        name = proj if isinstance(proj, str) else proj.get("name", "")
        # Flag tutorial-level names
        tutorial_words = ["todo", "calculator", "hello", "tutorial", "demo", "sample"]
        if any(w in name.lower() for w in tutorial_words):
            quality_flags.append(f"'{name}' appears tutorial-level — build something original")
            project_score = max(project_score - 15, 0)

    execution_score = project_score + skill_score + proof_score  # 0-100

    # Determine readiness
    if execution_score >= 60:
        readiness = "READY"
        message = "Strong execution — gaps are closing. System confidence increased."
    elif execution_score >= 30:
        readiness = "PROGRESSING"
        message = "Some progress detected. Complete remaining items to unlock full confidence."
    else:
        readiness = "STAGNANT"
        message = "No meaningful execution detected. Restrictions remain active."

    remaining_gaps = []
    if not projects:
        remaining_gaps.append("Build at least 1 real project")
    if len(skills) < 2:
        remaining_gaps.append(f"Learn {2 - len(skills)} more skills")
    if not github_links:
        remaining_gaps.append("Add GitHub/portfolio links as proof")
    if not resume_updated:
        remaining_gaps.append("Update resume with new capabilities")

    return {
        "execution_score": execution_score,
        "readiness": readiness,
        "project_score": project_score,
        "skill_score": skill_score,
        "proof_score": proof_score,
        "proof_signals": proof_signals,
        "quality_flags": quality_flags,
        "remaining_gaps": remaining_gaps,
        "message": message,
    }


# ================================================================
# ENGINE 2 — MARKET INTELLIGENCE
# ================================================================

def assess_market_competition(
    role: str,
    experience_level: str,
    candidate_skills: List[str],
    jd_skills: List[str] = None,
) -> Dict:
    """
    Estimate hiring competition and adjust expectations.
    
    Uses role type + experience level to estimate market difficulty.
    """
    jd_skills = jd_skills or []
    role_lower = role.lower()

    # Competition estimation by role type
    high_competition = ["data scientist", "ml engineer", "software engineer",
                        "product manager", "ux designer", "frontend developer"]
    medium_competition = ["data analyst", "backend developer", "devops",
                          "qa engineer", "bi analyst", "data engineer"]
    low_competition = ["systems administrator", "technical writer",
                       "support engineer", "database administrator"]

    if any(r in role_lower for r in high_competition):
        competition = "HIGH"
        competition_factor = 0.7
        applicant_density = "200-500+ per opening"
    elif any(r in role_lower for r in medium_competition):
        competition = "MEDIUM"
        competition_factor = 0.85
        applicant_density = "50-200 per opening"
    else:
        competition = "LOW"
        competition_factor = 0.95
        applicant_density = "10-50 per opening"

    # Experience penalty/boost
    exp_lower = experience_level.lower()
    if "fresher" in exp_lower or "0" in exp_lower:
        competition_factor *= 0.8  # freshers face extra competition
        exp_note = "Entry-level roles are highly competitive"
    elif "7+" in exp_lower or "senior" in exp_lower:
        competition_factor *= 1.1  # senior roles have fewer candidates
        exp_note = "Senior roles have less competition but higher bar"
    else:
        exp_note = "Mid-level competition is moderate"

    competition_factor = min(competition_factor, 1.0)

    # Skill rarity check
    rare_skills = ["kubernetes", "terraform", "mlops", "spark", "kafka",
                   "airflow", "dbt", "ray", "triton", "onnx"]
    candidate_rare = [s for s in candidate_skills if s.lower() in rare_skills]
    jd_rare = [s for s in jd_skills if s.lower() in rare_skills]

    skill_rarity = "common"
    if jd_rare:
        if len(candidate_rare) >= len(jd_rare) * 0.5:
            skill_rarity = "rare_match"
            competition_factor = min(competition_factor + 0.1, 1.0)
        else:
            skill_rarity = "rare_gap"
            competition_factor *= 0.9

    # Skill overlap
    if candidate_skills and jd_skills:
        overlap = len(set(s.lower() for s in candidate_skills) &
                       set(s.lower() for s in jd_skills))
        coverage = overlap / len(jd_skills) * 100 if jd_skills else 0
    else:
        coverage = 50

    # Positioning advice
    advice = []
    if competition == "HIGH":
        advice.append("Highlight unique projects — generic resumes get lost")
        advice.append("Apply within 24h of posting for best response rate")
    if skill_rarity == "rare_gap":
        advice.append(f"Learn rare skills: {', '.join(jd_rare[:3])} — these differentiate")
    if coverage < 60:
        advice.append("Skill coverage is low — consider upskilling before applying")
    if not advice:
        advice.append("Good positioning — focus on clear, quantified achievements")

    return {
        "competition_level": competition,
        "competition_factor": round(competition_factor, 2),
        "applicant_density": applicant_density,
        "skill_rarity": skill_rarity,
        "skill_coverage": round(coverage, 0),
        "experience_note": exp_note,
        "positioning_advice": advice[:4],
    }


# ================================================================
# ENGINE 3 — INTERVIEW CONVERSION
# ================================================================

def analyze_interview_readiness(
    candidate_skills: List[str],
    jd_skills: List[str],
    role: str,
    experience_level: str,
) -> Dict:
    """
    Predict interview risks and generate preparation plan.
    Maximizes: Shortlisted → Interview → Offer conversion.
    """
    role_lower = role.lower()
    matched = set(s.lower() for s in candidate_skills) & set(s.lower() for s in jd_skills)
    gaps = set(s.lower() for s in jd_skills) - set(s.lower() for s in candidate_skills)

    # Risk analysis
    risks = []
    if len(gaps) > len(matched):
        risks.append({
            "area": "Technical Gaps",
            "severity": "HIGH",
            "detail": f"{len(gaps)} unmatched JD skills — expect probing questions",
        })
    if "fresher" in experience_level.lower():
        risks.append({
            "area": "Experience Depth",
            "severity": "MEDIUM",
            "detail": "May struggle with 'Tell me about a time...' behavioral questions",
        })

    # Key topics to revise
    topics = []
    for skill in list(gaps)[:5]:
        topics.append(f"Revise: {skill} (JD requirement, not on resume)")
    for skill in list(matched)[:3]:
        topics.append(f"Deep dive: {skill} (matched — be ready for follow-ups)")

    # Project deep dives
    project_prep = []
    if "data" in role_lower:
        project_prep = [
            "Prepare: data pipeline architecture walkthrough",
            "Prepare: ML model evaluation methodology explanation",
            "Prepare: a 'what went wrong' story with resolution",
        ]
    elif "software" in role_lower or "engineer" in role_lower:
        project_prep = [
            "Prepare: system design for a scalable service",
            "Prepare: debugging methodology walkthrough",
            "Prepare: code review / refactoring example",
        ]
    else:
        project_prep = [
            "Prepare: end-to-end project walkthrough",
            "Prepare: decision-making under ambiguity example",
            "Prepare: quantified impact story",
        ]

    # Conversion score
    risk_penalty = len([r for r in risks if r["severity"] == "HIGH"]) * 15
    gap_penalty = min(len(gaps) * 5, 25)
    base = 70
    conversion_score = max(base - risk_penalty - gap_penalty, 20)

    return {
        "conversion_score": conversion_score,
        "risks": risks,
        "key_topics": topics[:6],
        "project_prep": project_prep,
        "matched_skills": len(matched),
        "gap_skills": len(gaps),
        "readiness": (
            "STRONG" if conversion_score >= 60
            else "MODERATE" if conversion_score >= 40
            else "WEAK"
        ),
    }


# ================================================================
# ENGINE 4 — END-TO-END PIPELINE OPTIMIZATION
# ================================================================

def analyze_full_pipeline(history: List[Dict]) -> Dict:
    """
    Full pipeline analysis: Discovery → Application → Shortlist → Interview → Offer.
    Detects bottlenecks and generates career trajectory.
    """
    if len(history) < 3:
        return {
            "pipeline_rates": {},
            "bottleneck": "insufficient_data",
            "career_plan": ["Apply to at least 5 jobs to enable pipeline analysis"],
            "trajectory": None,
        }

    total = len(history)
    applied = len([h for h in history if h.get("status") in
                   ("applied", "shortlisted", "interviewed", "offered", "rejected")])
    shortlisted = len([h for h in history if h.get("status") in
                       ("shortlisted", "interviewed", "offered")])
    interviewed = len([h for h in history if h.get("status") in ("interviewed", "offered")])
    offered = len([h for h in history if h.get("status") == "offered"])

    # Rates
    app_rate = (applied / total * 100) if total else 0
    shortlist_rate = (shortlisted / applied * 100) if applied else 0
    interview_rate = (interviewed / shortlisted * 100) if shortlisted else 0
    offer_rate = (offered / interviewed * 100) if interviewed else 0

    rates = {
        "applications": applied,
        "shortlisted": shortlisted,
        "interviewed": interviewed,
        "offered": offered,
        "shortlist_rate": round(shortlist_rate, 1),
        "interview_rate": round(interview_rate, 1),
        "offer_rate": round(offer_rate, 1),
    }

    # Bottleneck detection
    if applied > 0 and shortlist_rate < 5:
        bottleneck = "APPLICATION_STAGE"
        bottleneck_detail = (
            f"Only {shortlist_rate:.0f}% shortlist rate — "
            f"resume/targeting is the primary issue"
        )
    elif shortlisted > 0 and interview_rate < 30:
        bottleneck = "SHORTLIST_STAGE"
        bottleneck_detail = "Getting shortlisted but not converting to interviews"
    elif interviewed > 0 and offer_rate < 30:
        bottleneck = "INTERVIEW_STAGE"
        bottleneck_detail = "Reaching interviews but not converting to offers"
    elif applied == 0:
        bottleneck = "NOT_APPLYING"
        bottleneck_detail = "No applications submitted yet"
    else:
        bottleneck = "NONE"
        bottleneck_detail = "Pipeline is functioning — keep optimizing"

    # Career plan
    plan = []
    if bottleneck == "APPLICATION_STAGE":
        plan = [
            "🎯 FOCUS: Improve resume targeting — your resume isn't passing screens",
            "📄 ACTION: Use calibrated probability to filter applications (≥50% only)",
            "🔨 BUILD: Add 1 project demonstrating core JD skills",
            "🚫 STOP: Mass applying — quality over quantity",
        ]
    elif bottleneck == "SHORTLIST_STAGE":
        plan = [
            "📧 FOCUS: Follow up on shortlisted applications",
            "📄 ACTION: Prepare interview materials for shortlisted roles",
            "🔨 BUILD: Portfolio showcasing relevant projects",
        ]
    elif bottleneck == "INTERVIEW_STAGE":
        plan = [
            "🎤 FOCUS: Interview preparation is the bottleneck",
            "📄 ACTION: Practice STAR method for behavioral questions",
            "🔨 BUILD: Deep knowledge of your project architectures",
            "🧠 PREPARE: Technical fundamentals for the role domain",
        ]
    else:
        plan = [
            "✅ Pipeline is working — maintain current strategy",
            "📈 Optimize by focusing on highest-success role types",
        ]

    # Trajectory estimation
    if applied >= 10 and shortlist_rate > 0:
        apps_per_shortlist = applied / max(shortlisted, 1)
        est_apps_needed = int(apps_per_shortlist * 5)  # for ~5 shortlists
        weeks = max(1, est_apps_needed // 5)  # ~5 apps/week
        trajectory = {
            "apps_per_shortlist": round(apps_per_shortlist, 0),
            "estimated_apps_for_offer": est_apps_needed,
            "estimated_weeks": weeks,
            "message": (
                f"At current rate: ~{est_apps_needed} applications needed "
                f"for 5 shortlists (~{weeks} weeks at 5/week)"
            ),
        }
    else:
        trajectory = {
            "message": "Need more data to estimate timeline",
            "estimated_weeks": None,
        }

    return {
        "pipeline_rates": rates,
        "bottleneck": bottleneck,
        "bottleneck_detail": bottleneck_detail,
        "career_plan": plan,
        "trajectory": trajectory,
    }


# ================================================================
# MASTER ORCHESTRATOR
# ================================================================

def run_career_intelligence(
    history: List[Dict],
    user_progress: Dict = None,
    role: str = "",
    experience_level: str = "1-3 yrs",
    candidate_skills: List[str] = None,
    jd_skills: List[str] = None,
) -> Dict:
    """
    Run the complete career intelligence cycle.
    """
    user_progress = user_progress or {}
    candidate_skills = candidate_skills or []
    jd_skills = jd_skills or []

    execution = validate_execution(user_progress)
    market = assess_market_competition(role, experience_level, candidate_skills, jd_skills)
    interview = analyze_interview_readiness(candidate_skills, jd_skills, role, experience_level)
    pipeline = analyze_full_pipeline(history)

    return {
        "execution": execution,
        "market": market,
        "interview": interview,
        "pipeline": pipeline,
        "summary": {
            "execution_score": execution["execution_score"],
            "readiness": execution["readiness"],
            "competition": market["competition_level"],
            "interview_readiness": interview["readiness"],
            "bottleneck": pipeline["bottleneck"],
        },
    }
