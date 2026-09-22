"""
Job Pipeline — Intelligent Job Discovery + Application + Daily Pipeline.

Takes a batch of job listings, processes each through the intelligence
engine, ranks them, and generates a daily application plan.

This is the BATCH LAYER — sits on top of the single-job intelligence engine.

Pipeline flow:
  Jobs → Intake → JD Processing → Intelligence → Decision Gate →
  Resume Strategy → Ranking → Daily Plan → Output

RULES:
  - NO auto-apply (always manual via link)
  - NO resume for skipped jobs
  - NO hallucinated JD data
  - NO inflated probabilities
"""

import re
import copy
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from utils.models import StructuredResume, ExtractedJD
from utils.logger import setup_logger
from pipeline.hiring_simulation import (
    compute_targeting_score,
    diagnose_root_cause,
    generate_pre_application_gate,
    predict_rejection_reasons,
    generate_resume_variants,
    generate_ab_strategy,
    compute_variant_performance,
)

logger = setup_logger(__name__)

# ================================================================
# DATA PATH
# ================================================================

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_PIPELINE_LOG = os.path.join(_DATA_DIR, "job_pipeline_log.json")


# ================================================================
# STEP 1 — JOB INTAKE
# ================================================================

@dataclass
class JobListing:
    """Single job listing from any source."""
    company: str
    role: str
    job_description: str
    apply_link: str = ""
    salary: str = ""
    source: str = ""  # e.g., "linkedin", "indeed", "manual"
    job_id: str = ""

    def __post_init__(self):
        if not self.job_id:
            # Generate deterministic ID from company + role
            raw = f"{self.company}_{self.role}".lower().strip()
            self.job_id = re.sub(r'[^a-z0-9]+', '_', raw)[:60]


def intake_jobs(raw_jobs: List[Dict]) -> List[JobListing]:
    """
    STEP 1: Intake and validate job listings.
    
    Discards:
      - Duplicate jobs (same company + role)
      - Incomplete listings (no company or JD)
      - Very short JDs (< 50 chars)
    """
    seen_ids = set()
    valid = []
    
    for j in raw_jobs:
        company = (j.get("company") or "").strip()
        role = (j.get("role") or j.get("title") or "").strip()
        jd = (j.get("job_description") or j.get("jd") or j.get("description") or "").strip()
        
        # Validation
        if not company or not jd:
            logger.info(f"  Skipped: missing company or JD — {company or '?'}")
            continue
        if len(jd) < 50:
            logger.info(f"  Skipped: JD too short ({len(jd)} chars) — {company}")
            continue
        
        listing = JobListing(
            company=company,
            role=role or "Unknown Role",
            job_description=jd,
            apply_link=(j.get("apply_link") or j.get("url") or "").strip(),
            salary=(j.get("salary") or "").strip(),
            source=(j.get("source") or "").strip(),
        )
        
        # Dedup
        if listing.job_id in seen_ids:
            logger.info(f"  Skipped: duplicate — {company} / {role}")
            continue
        
        seen_ids.add(listing.job_id)
        valid.append(listing)
    
    logger.info(f"JOB INTAKE: {len(valid)}/{len(raw_jobs)} jobs passed validation")
    return valid


# ================================================================
# STEP 2 — JD PROCESSING
# ================================================================

def process_jd(listing: JobListing) -> ExtractedJD:
    """
    STEP 2: Clean and structure job description.
    
    Extracts:
      - Required/preferred skills
      - Responsibilities
      - Experience years
      - Domain classification
    """
    jd_text = listing.job_description
    
    # Extract skills (look for common patterns)
    skill_patterns = [
        r'(?:required|must have|essential)[\s:]*(.+?)(?:\n\n|\Z)',
        r'(?:skills|requirements|qualifications)[\s:]*(.+?)(?:\n\n|\Z)',
    ]
    
    skills_raw = []
    for pattern in skill_patterns:
        match = re.search(pattern, jd_text, re.I | re.DOTALL)
        if match:
            text = match.group(1)
            # Split by bullet points, commas, or newlines
            items = re.split(r'[•\-\n,;]+', text)
            skills_raw.extend(item.strip() for item in items if len(item.strip()) > 2)
    
    # If no structured skills found, extract tool/tech keywords
    _KNOWN_SKILLS = {
        "python", "sql", "java", "javascript", "react", "node", "aws", "azure",
        "gcp", "docker", "kubernetes", "terraform", "spark", "kafka", "airflow",
        "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy", "tableau",
        "power bi", "excel", "git", "ci/cd", "rest", "graphql", "mongodb",
        "postgresql", "mysql", "redis", "elasticsearch", "machine learning",
        "deep learning", "nlp", "computer vision", "data analysis", "etl",
        "data pipeline", "microservice", "agile", "scrum",
    }
    
    found_skills = []
    jd_lower = jd_text.lower()
    for skill in _KNOWN_SKILLS:
        if skill in jd_lower:
            found_skills.append(skill.title() if len(skill) > 3 else skill.upper())
    
    # Extract responsibilities
    resp_patterns = [
        r'(?:responsibilities|what you\'ll do|you will)[\s:]*(.+?)(?:\n\n|\Z)',
    ]
    responsibilities = []
    for pattern in resp_patterns:
        match = re.search(pattern, jd_text, re.I | re.DOTALL)
        if match:
            items = re.split(r'[•\-\n]+', match.group(1))
            responsibilities.extend(
                item.strip() for item in items
                if len(item.strip()) > 15
            )
    
    # Extract experience years
    exp_years = None
    exp_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', jd_lower)
    if exp_match:
        exp_years = int(exp_match.group(1))
    
    # Use skills_raw if found, otherwise fall back to keyword extraction
    required_skills = skills_raw[:15] if skills_raw else found_skills[:15]
    
    return ExtractedJD(
        job_title=listing.role,
        company=listing.company,
        required_skills=required_skills,
        preferred_skills=[],
        keywords=[s.lower() for s in required_skills],
        responsibilities=responsibilities[:10],
        required_experience_years=exp_years,
        raw_text=jd_text,
    )


# ================================================================
# STEP 3+4 — INTELLIGENCE + DECISION GATE
# ================================================================

def evaluate_job(
    listing: JobListing,
    jd: ExtractedJD,
    resume: StructuredResume,
    history: List[Dict] = None,
) -> Dict:
    """
    STEP 3+4: Run intelligence engine + decision gate for a single job.
    
    Returns complete evaluation with decision.
    """
    history = history or []
    
    # Run ATS scoring (lightweight — just skill matching)
    resume_skills_lower = {s.lower() for s in resume.skills}
    jd_skills_lower = {s.lower() for s in jd.required_skills}
    
    matched = [s for s in jd.required_skills if s.lower() in resume_skills_lower]
    missing = [s for s in jd.required_skills if s.lower() not in resume_skills_lower]
    
    # Compute a lightweight ATS-like score
    total_skills = len(jd.required_skills)
    if total_skills > 0:
        skill_ratio = len(matched) / total_skills
    else:
        skill_ratio = 0.5
    ats_estimate = round(skill_ratio * 100 * 0.7 + 30)  # 30-100 range
    
    # Targeting score
    targeting = compute_targeting_score(resume, jd, matched, missing)
    
    # Build a lightweight hiring sim dict for diagnosis
    hiring_sim = {
        "shortlist_probability": min(100, targeting["total_score"] * 0.8),
        "layers": {"recruiter": {"score": targeting["total_score"]}},
    }
    
    # Root cause
    diagnosis = diagnose_root_cause(ats_estimate, targeting, hiring_sim, history)
    
    # Pre-application gate
    gate = generate_pre_application_gate(ats_estimate, targeting, hiring_sim, diagnosis)
    
    # Rejection prediction
    rejection = predict_rejection_reasons(resume, jd, hiring_sim, targeting, matched, missing)
    
    # Decision gate (STEP 4)
    shortlist_prob = gate["shortlist_probability"]
    if shortlist_prob < 40:
        decision = "SKIP"
        decision_emoji = "⏭️"
    elif shortlist_prob < 60:
        decision = "APPLY_FIX_GAPS"
        decision_emoji = "🟡"
    else:
        decision = "APPLY_NOW"
        decision_emoji = "🟢"
    
    return {
        "job_id": listing.job_id,
        "company": listing.company,
        "role": listing.role,
        "apply_link": listing.apply_link,
        "salary": listing.salary,
        "decision": decision,
        "decision_emoji": decision_emoji,
        "shortlist_probability": round(shortlist_prob, 1),
        "jd_match_score": targeting["total_score"],
        "confidence_score": gate["confidence_score"],
        "root_cause": diagnosis["primary_cause"],
        "top_risk": rejection["risks"][0]["risk"] if rejection["risks"] else "None identified",
        "top_risk_fix": rejection["risks"][0].get("fix", "") if rejection["risks"] else "",
        "matched_skills": matched,
        "missing_skills": missing,
        "ats_estimate": ats_estimate,
        "targeting": targeting,
        "diagnosis": diagnosis,
        "gate": gate,
        "rejection": rejection,
    }


# ================================================================
# STEP 5 — RESUME STRATEGY (only for non-skipped jobs)
# ================================================================

def assign_resume_strategy(
    evaluation: Dict,
    resume: StructuredResume,
    jd: ExtractedJD,
    history: List[Dict] = None,
) -> Dict:
    """
    STEP 5: Select optimal resume variant for this job.
    
    Only runs for jobs with decision != SKIP.
    """
    if evaluation["decision"] == "SKIP":
        evaluation["variant"] = None
        evaluation["variant_name"] = "N/A"
        return evaluation
    
    history = history or []
    
    # Generate variants
    hiring_sim = {
        "shortlist_probability": evaluation["shortlist_probability"],
    }
    variants = generate_resume_variants(
        resume, jd, hiring_sim, evaluation["targeting"],
        evaluation["matched_skills"],
    )
    
    # Select best variant based on A/B strategy
    ab = generate_ab_strategy(variants, history)
    
    # Map recommendation to mode
    primary_name = ab.get("primary", "Balanced")
    selected = next((v for v in variants if v["name"] == primary_name), variants[0])
    
    evaluation["variant"] = selected
    evaluation["variant_name"] = selected["name"]
    evaluation["variant_mode"] = selected["mode"]
    evaluation["all_variants"] = variants
    evaluation["ab_strategy"] = ab
    
    return evaluation


# ================================================================
# STEP 6 — JOB RANKING ENGINE
# ================================================================

def rank_jobs(evaluations: List[Dict]) -> List[Dict]:
    """
    STEP 6: Rank all jobs by composite score.
    
    job_score = 0.40 * shortlist_probability
             + 0.30 * jd_match_score
             + 0.20 * confidence_score
             + 0.10 * salary_bonus
    """
    for ev in evaluations:
        # Salary bonus (simple: if salary exists and seems high)
        salary_bonus = 10 if ev.get("salary") else 0
        
        ev["job_score"] = round(
            ev["shortlist_probability"] * 0.40 +
            ev["jd_match_score"] * 0.30 +
            ev["confidence_score"] * 0.20 +
            salary_bonus * 0.10,
            1,
        )
    
    # Sort by job_score descending
    evaluations.sort(key=lambda e: e["job_score"], reverse=True)
    
    # Assign rank
    for i, ev in enumerate(evaluations, 1):
        ev["rank"] = i
    
    return evaluations


# ================================================================
# STEP 7 — DAILY APPLICATION PIPELINE
# ================================================================

def generate_daily_plan(
    ranked_jobs: List[Dict],
    max_applications: int = 8,
) -> Dict:
    """
    STEP 7: Generate today's application plan.
    
    Selects top 5-10 jobs with:
      - 2-3 APPLY_NOW
      - 2-3 APPLY_FIX_GAPS
      - No duplicate companies
      - No SKIP jobs
    """
    apply_now = []
    fix_gaps = []
    skipped = []
    seen_companies = set()
    
    for ev in ranked_jobs:
        company_key = ev["company"].lower().strip()
        
        # Skip duplicates
        if company_key in seen_companies:
            continue
        
        if ev["decision"] == "APPLY_NOW":
            if len(apply_now) < 4:
                apply_now.append(ev)
                seen_companies.add(company_key)
        elif ev["decision"] == "APPLY_FIX_GAPS":
            if len(fix_gaps) < 4:
                fix_gaps.append(ev)
                seen_companies.add(company_key)
        else:
            skipped.append(ev)
        
        # Cap total
        if len(apply_now) + len(fix_gaps) >= max_applications:
            break
    
    today_plan = apply_now + fix_gaps
    
    # Determine focus domain
    if today_plan:
        causes = [j["root_cause"] for j in today_plan]
        primary_issue = max(set(causes), key=causes.count)
    else:
        primary_issue = "NO_JOBS"
    
    # Best variant for today
    variants_used = [j.get("variant_name", "Balanced") for j in today_plan if j.get("variant_name")]
    best_variant = max(set(variants_used), key=variants_used.count) if variants_used else "Balanced"
    
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_evaluated": len(ranked_jobs),
        "apply_now": apply_now,
        "fix_gaps": fix_gaps,
        "skipped_count": len(skipped),
        "today_count": len(today_plan),
        "focus_issue": primary_issue,
        "best_variant": best_variant,
        "plan": today_plan,
    }


# ================================================================
# STEP 10 — TRACKING SYSTEM
# ================================================================

def save_pipeline_log(plan: Dict):
    """Save daily pipeline log to disk."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    
    # Load existing logs
    logs = []
    if os.path.exists(_PIPELINE_LOG):
        try:
            with open(_PIPELINE_LOG, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []
    
    # Add today's plan (simplified for storage)
    log_entry = {
        "date": plan["date"],
        "total_evaluated": plan["total_evaluated"],
        "today_count": plan["today_count"],
        "skipped_count": plan["skipped_count"],
        "best_variant": plan["best_variant"],
        "jobs": [
            {
                "company": j["company"],
                "role": j["role"],
                "decision": j["decision"],
                "shortlist_probability": j["shortlist_probability"],
                "jd_match_score": j["jd_match_score"],
                "variant": j.get("variant_name", "?"),
                "status": "applied",
            }
            for j in plan["plan"]
        ],
    }
    
    logs.append(log_entry)
    
    with open(_PIPELINE_LOG, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Pipeline log saved: {plan['today_count']} jobs for {plan['date']}")


# ================================================================
# MASTER ORCHESTRATOR — RUN DAILY PIPELINE
# ================================================================

def run_daily_pipeline(
    raw_jobs: List[Dict],
    resume: StructuredResume,
    history: List[Dict] = None,
    max_applications: int = 8,
) -> Dict:
    """
    Master function: runs the complete daily job pipeline.
    
    Steps:
      1. Intake → validate and dedup jobs
      2. JD Processing → extract skills, responsibilities
      3. Intelligence → targeting, diagnosis, gate
      4. Decision → APPLY_NOW / FIX_GAPS / SKIP
      5. Strategy → select resume variant
      6. Ranking → sort by composite score
      7. Daily Plan → select top 5-10 for today
    
    Returns complete pipeline output for UI rendering.
    """
    history = history or []
    logger.info(f"DAILY PIPELINE — Starting with {len(raw_jobs)} raw jobs")
    
    # Step 1: Intake
    listings = intake_jobs(raw_jobs)
    
    # Step 2+3+4: Process, Evaluate, Decide
    evaluations = []
    for listing in listings:
        jd = process_jd(listing)
        evaluation = evaluate_job(listing, jd, resume, history)
        evaluation = assign_resume_strategy(evaluation, resume, jd, history)
        evaluations.append(evaluation)
    
    # Step 6: Rank
    ranked = rank_jobs(evaluations)
    
    # Step 7: Daily Plan
    plan = generate_daily_plan(ranked, max_applications)
    
    # Step 10: Save log
    save_pipeline_log(plan)
    
    # Summary stats
    apply_now_count = len([e for e in evaluations if e["decision"] == "APPLY_NOW"])
    fix_count = len([e for e in evaluations if e["decision"] == "APPLY_FIX_GAPS"])
    skip_count = len([e for e in evaluations if e["decision"] == "SKIP"])
    
    logger.info(
        f"  Results: {apply_now_count} APPLY NOW, {fix_count} FIX GAPS, "
        f"{skip_count} SKIP — Today: {plan['today_count']} jobs"
    )
    
    return {
        "all_evaluations": ranked,
        "plan": plan,
        "summary": {
            "total_input": len(raw_jobs),
            "total_valid": len(listings),
            "apply_now": apply_now_count,
            "fix_gaps": fix_count,
            "skip": skip_count,
            "today_applications": plan["today_count"],
            "best_variant": plan["best_variant"],
            "focus_issue": plan["focus_issue"],
        },
    }
