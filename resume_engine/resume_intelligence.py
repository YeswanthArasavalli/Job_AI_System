"""
Resume Intelligence -- Detects resume type and adapts optimization strategy.

Identifies:
  - EXPERIENCED: 3+ years, consistent career progression
  - SWITCHER: Changing domains (e.g., teacher → data science)
  - FRESHER: 0-1 years, academic-heavy resume
  - GAP: Employment gaps > 1 year
  - OVERQUALIFIED: Senior applying to junior roles
  - ACADEMIC: PhD/research-heavy, limited industry experience

This classification feeds into the improver to select appropriate strategies:
  - FRESHER → emphasize projects + education, don't penalize short bullets
  - SWITCHER → highlight transferable skills, bridge language
  - EXPERIENCED → standard optimization, emphasize depth
  - GAP → strategy to address gaps positively
  - OVERQUALIFIED → tailor down without losing credibility
  - ACADEMIC → translate research into industry language
"""

import re
from typing import Dict, List, Optional, Tuple

from utils.models import StructuredResume, ExtractedJD
from utils.logger import setup_logger

logger = setup_logger(__name__)


def detect_resume_type(
    resume: StructuredResume,
    jd: Optional[ExtractedJD] = None,
) -> Dict:
    """
    Classify resume type for strategy adaptation.

    Returns:
        {
            "type": "EXPERIENCED",
            "confidence": 0.9,
            "years_estimated": 5,
            "flags": ["career_progression", "domain_consistent"],
            "strategy_hints": [
                "Standard optimization — emphasize depth and recent role",
                "Focus on keyword alignment in most recent experience",
            ],
        }
    """
    years = _estimate_total_years(resume)
    exp_count = len(resume.experience)
    edu_count = len(resume.education)
    project_count = len(resume.projects) if resume.projects else 0
    has_phd = _has_advanced_degree(resume)
    has_gap = _detect_employment_gap(resume)
    is_switching = _detect_domain_switch(resume, jd) if jd else False

    # Classification logic
    if years <= 1 and exp_count <= 1:
        rtype = "FRESHER"
        confidence = 0.9 if project_count > 0 else 0.7
        flags = ["limited_experience"]
        if project_count > 0:
            flags.append("has_projects")
        if edu_count > 0:
            flags.append("education_heavy")
        strategy = [
            "Emphasize projects, education, and certifications",
            "Don't penalize short experience bullets — focus on potential",
            "Highlight academic achievements and relevant coursework",
        ]

    elif is_switching:
        rtype = "SWITCHER"
        confidence = 0.85
        flags = ["domain_switch", "transferable_skills"]
        strategy = [
            "Highlight transferable skills (communication, analysis, problem-solving)",
            "Bridge language: reframe past experience in target domain terms",
            "Emphasize certifications, bootcamp projects, and self-learning",
            "Don't hide past domain — position it as unique perspective",
        ]

    elif has_phd and exp_count <= 2:
        rtype = "ACADEMIC"
        confidence = 0.8
        flags = ["research_heavy", "limited_industry"]
        strategy = [
            "Translate research outcomes into business impact language",
            "Highlight publications/papers as evidence of domain expertise",
            "Convert academic methodologies into industry-relevant skills",
        ]

    elif has_gap:
        rtype = "GAP"
        confidence = 0.75
        flags = ["employment_gap"]
        strategy = [
            "Focus on most recent role — don't draw attention to gaps",
            "Highlight any freelance, consulting, or volunteer work during gap",
            "Emphasize skill currency (certifications, projects during gap)",
        ]

    elif years >= 10 and jd and _is_junior_role(jd):
        rtype = "OVERQUALIFIED"
        confidence = 0.7
        flags = ["senior_applying_junior"]
        strategy = [
            "Tailor down to role level — avoid intimidating language",
            "Focus on relevant skills, not seniority",
            "Show genuine interest in the role domain",
        ]

    else:
        rtype = "EXPERIENCED"
        confidence = 0.9
        flags = []
        if _has_career_progression(resume):
            flags.append("career_progression")
        if exp_count >= 3:
            flags.append("deep_experience")
        strategy = [
            "Standard optimization — keyword alignment + depth enhancement",
            "Focus on most recent 2 roles for ATS relevance",
            "Quantify achievements where possible",
        ]

    result = {
        "type": rtype,
        "confidence": confidence,
        "years_estimated": years,
        "experience_count": exp_count,
        "flags": flags,
        "strategy_hints": strategy,
    }

    logger.info(
        f"Resume type: {rtype} (confidence={confidence:.2f}, "
        f"years={years}, exp={exp_count})"
    )

    return result


# ================================================================
# PRIVATE HELPERS
# ================================================================

def _estimate_total_years(resume: StructuredResume) -> int:
    """Estimate total years of experience."""
    if not resume.experience:
        return 0

    years = 0
    for exp in resume.experience:
        duration = exp.duration.lower() if exp.duration else ""

        # Try to parse year ranges
        year_match = re.findall(r'(\d{4})', duration)
        if len(year_match) >= 2:
            try:
                start = int(year_match[0])
                end = int(year_match[-1])
                years += max(0, end - start)
                continue
            except ValueError:
                pass

        # Handle "Present" / "Current"
        if "present" in duration or "current" in duration:
            year_match = re.findall(r'(\d{4})', duration)
            if year_match:
                try:
                    start = int(year_match[0])
                    years += max(0, 2026 - start)
                    continue
                except ValueError:
                    pass

        # Fallback: estimate 2 years per entry
        years += 2

    return years


def _has_advanced_degree(resume: StructuredResume) -> bool:
    """Check if resume has PhD or Master's degree."""
    for edu in resume.education:
        degree_lower = (edu.degree or "").lower()
        if any(d in degree_lower for d in ["phd", "ph.d", "doctorate", "doctor of"]):
            return True
        if "master" in degree_lower or "m.s." in degree_lower or "m.tech" in degree_lower:
            return True
    return False


def _detect_employment_gap(resume: StructuredResume) -> bool:
    """Detect if there's a gap > 1 year between experience entries."""
    if len(resume.experience) < 2:
        return False

    end_years = []
    start_years = []

    for exp in resume.experience:
        duration = exp.duration.lower() if exp.duration else ""
        years = re.findall(r'(\d{4})', duration)
        if len(years) >= 2:
            try:
                start_years.append(int(years[0]))
                end_years.append(int(years[-1]))
            except ValueError:
                pass

    if len(end_years) < 2:
        return False

    # Sort by start year descending
    pairs = sorted(zip(start_years, end_years), reverse=True)

    # Check for gaps between consecutive entries
    for i in range(len(pairs) - 1):
        current_start = pairs[i][0]
        prev_end = pairs[i + 1][1]
        gap = current_start - prev_end
        if gap > 1:
            return True

    return False


def _detect_domain_switch(
    resume: StructuredResume, jd: ExtractedJD
) -> bool:
    """Detect if resume domain differs significantly from JD domain."""
    # Build resume skill set
    resume_skills = {s.lower() for s in resume.skills}
    resume_bullets = " ".join(
        b.lower() for exp in resume.experience for b in exp.bullets
    )

    # Build JD skill set
    jd_skills = {s.lower() for s in jd.required_skills}

    if not jd_skills:
        return False

    # Check overlap
    overlap = resume_skills & jd_skills
    overlap_ratio = len(overlap) / max(len(jd_skills), 1)

    # Also check if resume roles sound different from JD title
    resume_roles = {exp.role.lower() for exp in resume.experience}
    jd_title = (jd.job_title or "").lower()

    # Domain cluster check
    tech_signals = {"engineer", "developer", "software", "data", "ml"}
    non_tech_signals = {"teacher", "nurse", "accountant", "manager", "sales"}

    resume_is_tech = any(
        s in " ".join(resume_roles)
        for s in tech_signals
    )
    jd_is_tech = any(s in jd_title for s in tech_signals)

    # Different tech-status = likely switching
    if resume_is_tech != jd_is_tech and overlap_ratio < 0.3:
        return True

    # Very low skill overlap = likely switching
    if overlap_ratio < 0.15 and len(jd_skills) >= 3:
        return True

    return False


def _is_junior_role(jd: ExtractedJD) -> bool:
    """Check if JD is for a junior/entry-level role."""
    title = (jd.job_title or "").lower()
    junior_signals = [
        "junior", "entry", "associate", "intern",
        "graduate", "trainee", "assistant",
    ]
    return any(s in title for s in junior_signals)


def _has_career_progression(resume: StructuredResume) -> bool:
    """Check if resume shows career progression (growing responsibility)."""
    if len(resume.experience) < 2:
        return False

    senior_signals = ["senior", "lead", "principal", "manager", "director", "head"]
    junior_signals = ["junior", "intern", "associate", "trainee", "entry"]

    roles = [exp.role.lower() for exp in resume.experience]

    # Most recent should be more senior than oldest
    recent_senior = any(s in roles[0] for s in senior_signals)
    oldest_junior = any(s in roles[-1] for s in junior_signals)

    return recent_senior or oldest_junior
