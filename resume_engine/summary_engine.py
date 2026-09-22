"""
Professional Summary Engine -- Generates role-aware, recruiter-grade summaries.

BEHAVIOR FIX: Replaced template-based generation with evidence-based generation.
Summary is now built from WHAT THE CANDIDATE ACTUALLY DOES in their bullets,
not from generic templates.

Structure:
  [Role Identity] + [What candidate actually does] + [Where they create impact] + [Proof (tools/projects)]

Rules:
  - NO generic words ("experienced", "hardworking", "passionate")
  - MUST include specialization relevant to the JD
  - MUST include actual tools/skills from the resume
  - MUST include impact/outcome language derived from RESUME EVIDENCE
  - Role-aware tone (tech vs. operations vs. customer, etc.)
"""

import re
from typing import Dict, List, Optional, Set

from utils.logger import setup_logger

logger = setup_logger(__name__)


# ================================================================
# GENERIC WORD BLOCKLIST (never use in summaries)
# ================================================================

GENERIC_BLOCKLIST = {
    "experienced", "hardworking", "passionate", "passion", "motivated",
    "dedicated", "enthusiastic", "detail-oriented", "results-driven",
    "team player", "self-starter", "go-getter", "dynamic",
    "proactive", "seasoned", "strong communicator", "fast learner",
    "eager", "ambitious", "innovative thinker", "proven track record",
    "seeking", "looking for",
}


# ================================================================
# EVIDENCE EXTRACTORS — What does this person ACTUALLY do?
# ================================================================

def _extract_action_evidence(resume) -> List[str]:
    """
    Extract WHAT the candidate actually does from their experience bullets.
    Returns a list of evidence phrases like:
      "building ML pipelines", "deploying models to production",
      "managing cross-functional teams"
    """
    evidence = []

    # Map past tense verbs to gerund form for summary use
    VERB_TO_GERUND = {
        "built": "building", "developed": "developing", "designed": "designing",
        "created": "creating", "architected": "architecting",
        "implemented": "implementing", "deployed": "deploying",
        "managed": "managing", "led": "leading", "drove": "driving",
        "automated": "automating", "optimized": "optimizing",
        "analyzed": "analyzing", "engineered": "engineering",
        "launched": "launching", "delivered": "delivering",
        "established": "establishing", "streamlined": "streamlining",
        "scaled": "scaling", "integrated": "integrating",
        "maintained": "maintaining", "coordinated": "coordinating",
        "facilitated": "facilitating", "trained": "training",
        "mentored": "mentoring", "processed": "processing",
    }

    verb_pattern = '|'.join(VERB_TO_GERUND.keys())
    # Capture VERB + OBJECT as a full phrase
    action_regex = re.compile(
        rf'({verb_pattern})\s+(.{{8,50}}?)(?:\.|,|using|leveraging|resulting|which|that|to\s)',
        re.IGNORECASE,
    )

    all_bullets = []
    for exp in resume.experience:
        all_bullets.extend(exp.bullets)
    for proj in resume.projects:
        all_bullets.extend(proj.bullets)

    for bullet in all_bullets:
        for match in action_regex.finditer(bullet.lower().strip()):
            verb = match.group(1).strip()
            obj = match.group(2).strip().rstrip(',.')
            gerund = VERB_TO_GERUND.get(verb, verb + "ing")
            phrase = f"{gerund} {obj}"
            if 12 < len(phrase) < 65:
                evidence.append(phrase)

    # Deduplicate by first word similarity
    seen_starts = set()
    unique = []
    for e in evidence:
        start = e.split()[0] if e else ""
        if start not in seen_starts:
            seen_starts.add(start)
            unique.append(e)

    return unique[:4]  # Top 4 evidence phrases


def _extract_impact_evidence(resume) -> List[str]:
    """
    Extract quantified impact from resume bullets.
    Returns phrases like "92% accuracy", "10K+ users", "30% cost reduction"
    """
    impacts = []

    all_bullets = " ".join(
        b for exp in resume.experience for b in exp.bullets
    ) + " " + " ".join(
        b for proj in resume.projects for b in proj.bullets
    )

    # Find quantified results
    patterns = [
        r'(\d+[%x])\s+(?:accuracy|improvement|reduction|increase|growth|decrease)',
        r'(\d+[Kk+]+)\s+(?:users|requests|transactions|records|events|customers)',
        r'(?:reduced|improved|increased|boosted|grew|decreased|cut)\s+.{0,20}?by\s+(\d+[%]?)',
        r'serving\s+(\d+[Kk+]+)',
        r'\$(\d+[MmKk]+)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, all_bullets, re.IGNORECASE)
        impacts.extend(matches[:2])

    return impacts[:3]


def _extract_scale(resume) -> str:
    """
    Extract scale indicators from resume bullets.
    Returns phrases like "50M+ records", "10K+ users", "$2M+ budget".
    """
    all_bullets = " ".join(
        b for exp in resume.experience for b in exp.bullets
    ) + " " + " ".join(
        b for proj in resume.projects for b in proj.bullets
    )

    scale_patterns = [
        r'(\d+[MmBb]\+?\s*(?:records|rows|data\s*points|events|transactions))',
        r'(\d+[Kk]\+?\s*(?:users|customers|requests|clients|api|events))',
        r'(\$\d+[MmKkBb]\+?\s*(?:revenue|budget|savings|cost)?)',
        r'(\d+\+?\s*(?:microservices|services|applications|servers|clusters|regions))',
    ]

    for pattern in scale_patterns:
        match = re.search(pattern, all_bullets, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return ""


def _format_impact(impact_evidence: List[str]) -> str:
    """
    Format raw impact evidence into a natural summary clause.
    
    Input: ["92%", "40%", "$2M"]
    Output: "achieving 92% accuracy and 40% performance improvement"
    """
    if not impact_evidence:
        return ""

    # Take top 1-2 impacts
    formatted = []
    for item in impact_evidence[:2]:
        item_str = str(item)
        if "$" in item_str:
            formatted.append(f"driving {item_str} in business value")
        elif "%" in item_str:
            formatted.append(f"achieving {item_str} improvement")
        elif "K" in item_str.upper() or "M" in item_str.upper():
            formatted.append(f"processing {item_str} records")
        else:
            formatted.append(f"delivering {item_str}")

    if formatted:
        return " and ".join(formatted)
    return "delivering measurable results"


def _extract_tools_actually_used(resume, role_info: Dict, matched_skills: List[str]) -> List[str]:
    """
    Extract tools/skills that are ACTUALLY USED in bullets (not just listed).
    """
    all_bullet_text = " ".join(
        b.lower() for exp in resume.experience for b in exp.bullets
    ) + " " + " ".join(
        b.lower() for proj in resume.projects for b in proj.bullets
    )

    # Check matched skills against bullets
    used_tools = []
    for skill in matched_skills:
        if skill.lower() in all_bullet_text:
            used_tools.append(skill)

    # Also check resume skills list
    if len(used_tools) < 3:
        for skill in resume.skills[:8]:
            if skill.lower() in all_bullet_text and skill not in used_tools:
                used_tools.append(skill)

    # Filter tech-only tools for non-tech roles
    allow_tech = role_info.get("allow_tech_injection", True)
    if not allow_tech:
        from resume_engine.role_engine import TECH_ONLY_SKILLS
        used_tools = [t for t in used_tools if t.lower() not in TECH_ONLY_SKILLS]

    return used_tools[:5]


# ================================================================
# MAIN FUNCTION
# ================================================================

def generate_professional_summary(
    resume,       # StructuredResume
    role_info: Dict,
    jd_keywords: List[str] = None,
    matched_skills: List[str] = None,
) -> str:
    """
    Generate an evidence-based professional summary.

    BEHAVIOR: Extracts what the candidate ACTUALLY does from their
    bullets, not from generic templates. Output reads like a human
    wrote it because it's built from real resume content.

    Structure:
      [Role Identity] + [What candidate actually does]
      + [Where they create impact] + [Proof (tools)]

    Args:
        resume: StructuredResume object
        role_info: Output from classify_role()
        jd_keywords: JD keywords for alignment
        matched_skills: Skills that match JD

    Returns:
        Professional summary string (150-400 chars)
    """
    role_type = role_info.get("role_type", "analytical")
    jd_keywords = jd_keywords or []
    matched_skills = matched_skills or []

    # 1. Role identity (from resume, not template)
    title = _extract_title(resume, role_type)

    # 2. Experience framing
    years = _estimate_years(resume)

    # 3. What do they ACTUALLY do? (from bullets)
    action_evidence = _extract_action_evidence(resume)

    # 4. Tools ACTUALLY used (verified in bullets)
    tools_used = _extract_tools_actually_used(resume, role_info, matched_skills)

    # 5. Impact evidence (from quantified metrics in bullets)
    impact_evidence = _extract_impact_evidence(resume)

    # 6. Specialization alignment (from JD + resume overlap)
    specialization = _extract_specialization(resume, role_type, jd_keywords)

    # --- BUILD EVIDENCE-BASED SUMMARY ---
    # Formula: [Role] + [Specialization] + [Scale] + [Impact] + [Tools]

    parts = []

    # Part 1: Role identity + years + specialization
    if years == "entry-level" or years == "emerging":
        role_part = f"{title}"
    else:
        role_part = f"{title} with {years} of experience"

    if specialization:
        role_part += f" in {specialization}"
    parts.append(role_part)

    # Part 2: Scale + what they do (from evidence)
    if action_evidence:
        # Pick the 2 most descriptive actions
        top_actions = action_evidence[:2]
        action_phrase = " and ".join(top_actions)
        # Extract scale metrics (e.g., "500K+ records", "10K+ users")
        scale_text = _extract_scale(resume)
        if scale_text:
            parts.append(f"specializing in {action_phrase} at scale ({scale_text})")
        else:
            parts.append(f"specializing in {action_phrase}")

    # Part 3: Tools actually used (max 3 for clean summary)
    if tools_used:
        tool_str = _format_tool_list(tools_used[:3])
        parts.append(f"using {tool_str}")

    # Part 4: Impact (use REAL metrics, not templates)
    if impact_evidence:
        # Format top impact metric into the summary
        impact_str = _format_impact(impact_evidence)
        if impact_str:
            parts.append(impact_str)
        else:
            parts.append("delivering measurable results")
    elif action_evidence:
        # No metrics — use domain-appropriate impact language
        domain_impact = _get_domain_impact(role_type)
        parts.append(domain_impact)

    # --- ASSEMBLE ---
    summary = ", ".join(parts) + "."

    # Fix grammar: capitalize first letter, remove double commas
    summary = summary[0].upper() + summary[1:]
    summary = re.sub(r',\s*,', ',', summary)
    summary = re.sub(r'\s+', ' ', summary).strip()

    # Clean generic words
    summary = _clean_generic_words(summary)

    # PART 5 FIX: Summary de-spamming — reduce comma density
    # If summary has >5 commas, split into 2 sentences at midpoint
    if summary.count(',') > 5:
        comma_positions = [m.start() for m in re.finditer(r',', summary)]
        mid_comma = comma_positions[len(comma_positions) // 2]
        # Find the best split point (nearest "using", "with", "specializing", or "delivering")
        split_keywords = [' using ', ' with ', ' specializing ', ' delivering ', ' achieving ']
        best_split = mid_comma
        for kw in split_keywords:
            pos = summary.find(kw, mid_comma - 30)
            if 0 < pos < len(summary) - 20:
                best_split = pos
                break
        if best_split != mid_comma:
            part1 = summary[:best_split].rstrip(', ') + '.'
            part2 = summary[best_split:].lstrip(', ')
            part2 = part2[0].upper() + part2[1:] if part2 else ''
            if not part2.endswith('.'):
                part2 = part2.rstrip() + '.'
            summary = part1 + ' ' + part2

    # Length guard
    if len(summary) > 500:
        summary = summary[:497] + "."
    if len(summary) < 80 and tools_used:
        summary = summary.rstrip('.')
        summary += f", with core expertise in {_format_tool_list(tools_used)}."

    logger.info(
        f"Summary generated: {len(summary)} chars, role={role_type}, "
        f"evidence={len(action_evidence)} actions, {len(tools_used)} tools, "
        f"{len(impact_evidence)} metrics"
    )

    return summary


def should_replace_summary(existing_summary: str) -> bool:
    """
    Check if existing summary is generic/weak and should be replaced.

    Returns True if summary contains generic words or is too short.
    """
    if not existing_summary or len(existing_summary) < 50:
        return True

    summary_lower = existing_summary.lower()

    # Check for generic words
    generic_count = sum(
        1 for word in GENERIC_BLOCKLIST
        if word in summary_lower
    )
    if generic_count >= 2:
        return True

    # Check for weak starts
    weak_starts = [
        "i am ", "i have ", "i'm ", "my name is ",
        "a highly", "a dedicated", "a motivated",
        "an experienced", "a passionate", "experienced ",
        "passionate ", "dedicated ", "motivated ", "hardworking ",
    ]
    if any(summary_lower.startswith(w) for w in weak_starts):
        return True

    # Check if summary has NO tool/skill mentions (too vague)
    tech_signals = [
        "python", "sql", "excel", "data", "machine learning",
        "analytics", "management", "development", "engineering",
        "design", "sales", "marketing",
    ]
    has_substance = any(s in summary_lower for s in tech_signals)
    if not has_substance and len(existing_summary) < 150:
        return True

    return False


# ================================================================
# PRIVATE HELPERS
# ================================================================

def _extract_title(resume, role_type: str) -> str:
    """Extract or infer professional title."""
    # Use resume title if it exists and isn't generic
    if resume.title and len(resume.title) > 3:
        title = resume.title.strip()
        # Remove generic prefixes
        for prefix in ["a ", "an ", "the "]:
            if title.lower().startswith(prefix):
                title = title[len(prefix):]
        return title.strip().title()

    # Infer from most recent role
    if resume.experience:
        return resume.experience[0].role.strip().title()

    # Fallback by role type
    FALLBACK_TITLES = {
        "technical": "Software Engineer",
        "data": "Data Professional",
        "analytical": "Business Analyst",
        "operations": "Operations Professional",
        "customer": "Sales Professional",
        "hr": "HR Professional",
        "management": "Manager",
        "creative": "Creative Professional",
        "trades": "Skilled Technician",
    }
    return FALLBACK_TITLES.get(role_type, "Professional")


def _estimate_years(resume) -> str:
    """Estimate years of experience from resume."""
    if not resume.experience:
        return "emerging"

    # Try to parse durations
    total_years = 0
    for exp in resume.experience:
        duration = exp.duration.lower()
        year_match = re.findall(r'(\d{4})', duration)
        if len(year_match) >= 2:
            try:
                start = int(year_match[0])
                end = int(year_match[-1])
                total_years += max(0, end - start)
            except ValueError:
                pass
        elif "present" in duration or "current" in duration:
            year_match = re.findall(r'(\d{4})', duration)
            if year_match:
                try:
                    start = int(year_match[0])
                    total_years += max(0, 2026 - start)
                except ValueError:
                    pass

    if total_years == 0:
        total_years = len(resume.experience) * 2

    if total_years <= 1:
        return "entry-level"
    elif total_years <= 3:
        return f"{total_years}+ years"
    else:
        return f"{total_years}+ years"


def _extract_specialization(
    resume, role_type: str, jd_keywords: List[str]
) -> str:
    """Extract specialization from JD keywords + resume content."""
    SPECIALIZATION_KEYWORDS = {
        "technical": [
            "distributed systems", "cloud-native", "microservices",
            "full-stack development", "backend development",
            "frontend development", "platform engineering",
            "infrastructure automation", "API development",
        ],
        "data": [
            "machine learning", "predictive analytics", "NLP",
            "computer vision", "data engineering", "ETL pipelines",
            "statistical modeling", "deep learning",
            "business intelligence", "data visualization",
        ],
        "analytical": [
            "business analysis", "financial modeling", "market research",
            "strategic consulting", "process optimization",
            "risk analysis", "data-driven decision making",
        ],
        "operations": [
            "supply chain management", "process optimization",
            "logistics coordination", "inventory management",
            "quality assurance", "production planning",
        ],
        "customer": [
            "B2B sales", "account management", "customer retention",
            "business development", "client relationship management",
            "revenue growth", "customer success",
        ],
        "hr": [
            "talent acquisition", "employee engagement",
            "performance management", "organizational development",
            "compensation and benefits", "workforce planning",
        ],
        "management": [
            "cross-functional team leadership", "P&L management",
            "strategic planning", "organizational transformation",
            "product strategy", "operational excellence",
        ],
        "creative": [
            "brand strategy", "content creation", "visual design",
            "user experience", "digital marketing",
            "campaign management", "storytelling",
        ],
        "trades": [
            "preventive maintenance", "equipment repair",
            "system diagnostics", "safety compliance",
            "installation and commissioning", "field service",
        ],
    }

    role_specs = SPECIALIZATION_KEYWORDS.get(role_type, [])
    jd_lower = " ".join(jd_keywords).lower()

    # Find matching specializations
    matches = []
    for spec in role_specs:
        if spec.lower() in jd_lower:
            matches.append(spec)

    if matches:
        return matches[0]

    # Fallback: best JD keyword
    if jd_keywords:
        for kw in jd_keywords[:5]:
            if len(kw) > 5 and " " in kw:
                return kw

    # Fallback from resume bullets
    if resume.experience:
        bullets = " ".join(resume.experience[0].bullets).lower()
        for spec in role_specs:
            if spec.lower() in bullets:
                return spec

    return role_specs[0] if role_specs else ""


def _format_tool_list(tools: List[str]) -> str:
    """Format a tool list for natural English."""
    if not tools:
        return ""
    if len(tools) == 1:
        return tools[0]
    elif len(tools) == 2:
        return f"{tools[0]} and {tools[1]}"
    else:
        return ", ".join(tools[:-1]) + f", and {tools[-1]}"


def _get_domain_impact(role_type: str) -> str:
    """Get domain-appropriate impact phrase (not a canned template)."""
    impacts = {
        "technical": "focused on production reliability and scalability",
        "data": "focused on translating data into business outcomes",
        "analytical": "focused on driving data-informed decisions",
        "operations": "focused on operational efficiency and cost optimization",
        "customer": "focused on revenue growth and client satisfaction",
        "hr": "focused on building high-performing teams",
        "management": "focused on cross-functional execution and team growth",
        "creative": "focused on brand impact and audience engagement",
        "trades": "focused on quality workmanship and safety standards",
    }
    return impacts.get(role_type, "focused on delivering measurable impact")


def _clean_generic_words(summary: str) -> str:
    """Remove generic words that might have leaked in."""
    for word in GENERIC_BLOCKLIST:
        summary = re.sub(
            rf'\b{re.escape(word)}\b', '', summary, flags=re.IGNORECASE
        )
    summary = re.sub(r'\s+', ' ', summary).strip()
    return summary
