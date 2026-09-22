"""
Universal Role Engine -- Classifies job roles and adapts system behavior.

Makes the system universally applicable to ANY role type:
  - Technical (engineer, developer, data scientist)
  - Analytical (analyst, consultant, researcher)
  - Operations (logistics, supply chain, admin)
  - Customer (sales, support, account management)
  - HR (recruiting, people ops, training)
  - Management (director, VP, C-suite)
  - Creative (designer, writer, marketing)
  - Trades (mechanic, electrician, technician)

HARD RULES:
  - NEVER inject tech skills into non-tech roles
  - NEVER assume projects exist
  - ALWAYS adapt bullet style to role type
"""

import re
from typing import Dict, List, Optional, Set, Tuple

from utils.logger import setup_logger

logger = setup_logger(__name__)


# ================================================================
# ROLE TYPE DEFINITIONS
# ================================================================

ROLE_TYPES = {
    "technical": {
        "signals": [
            "software", "engineer", "developer", "backend", "frontend",
            "full stack", "fullstack", "devops", "sre", "platform",
            "infrastructure", "cloud", "mobile", "ios", "android",
            "embedded", "firmware", "system", "architect",
        ],
        "skill_style": "technical",      # Use tool names + frameworks
        "bullet_style": "action_tool",   # Action + Tool + Context + Impact
        "summary_tone": "technical",     # "Engineer specializing in..."
        "allow_tech_injection": True,
    },
    "data": {
        "signals": [
            "data scientist", "data engineer", "data analyst",
            "machine learning", "ml engineer", "ai engineer",
            "deep learning", "nlp", "computer vision",
            "analytics", "business intelligence", "bi developer",
            "statistician", "research scientist",
        ],
        "skill_style": "technical",
        "bullet_style": "action_tool",
        "summary_tone": "analytical",  # "Data Scientist specializing in..."
        "allow_tech_injection": True,
    },
    "analytical": {
        "signals": [
            "analyst", "business analyst", "financial analyst",
            "consultant", "strategy", "research", "insights",
            "operations analyst", "quantitative", "actuary",
        ],
        "skill_style": "tools_and_methods",   # Tools + methodologies
        "bullet_style": "action_outcome",     # Action + Outcome
        "summary_tone": "analytical",
        "allow_tech_injection": True,  # Can mention Excel, SQL, etc.
    },
    "operations": {
        "signals": [
            "operations", "logistics", "supply chain", "warehouse",
            "procurement", "inventory", "production", "manufacturing",
            "quality assurance", "qa", "qa engineer", "qa analyst",
            "test engineer", "automation tester", "sdet",
            "process", "coordinator",
            "dispatch", "fleet", "distribution",
        ],
        "skill_style": "process",       # Process + efficiency focused
        "bullet_style": "action_metric",  # Action + Metric
        "summary_tone": "operational",
        "allow_tech_injection": False,
    },
    "customer": {
        "signals": [
            "sales", "account", "customer", "client", "relationship",
            "business development", "bdr", "sdr", "account executive",
            "customer success", "support", "service", "retail",
            "hospitality", "call center", "bpo",
        ],
        "skill_style": "interpersonal",   # Communication + relationship
        "bullet_style": "action_result",   # Action + Business Result
        "summary_tone": "customer",
        "allow_tech_injection": False,
    },
    "hr": {
        "signals": [
            "human resources", "hr", "recruiter", "recruiting",
            "talent acquisition", "people operations", "hrbp",
            "compensation", "benefits", "training", "learning",
            "organizational development", "employee relations",
            "payroll", "workforce",
        ],
        "skill_style": "people",         # People + compliance
        "bullet_style": "action_impact",  # Action + People Impact
        "summary_tone": "people",
        "allow_tech_injection": False,
    },
    "management": {
        "signals": [
            "manager", "director", "vp", "vice president", "head of",
            "lead", "principal", "chief", "cto", "ceo", "coo", "cfo",
            "program manager", "product manager", "project manager",
            "general manager", "team lead",
        ],
        "skill_style": "leadership",     # Leadership + strategy
        "bullet_style": "action_scale",   # Action + Scale + Business Outcome
        "summary_tone": "leadership",
        "allow_tech_injection": False,  # Unless detected as tech manager
    },
    "creative": {
        "signals": [
            "designer", "ux", "ui", "graphic", "visual", "creative",
            "content", "copywriter", "writer", "editor", "journalist",
            "marketing", "brand", "social media", "communications",
            "photographer", "video", "animator",
        ],
        "skill_style": "creative",       # Tools + portfolio
        "bullet_style": "action_outcome",
        "summary_tone": "creative",
        "allow_tech_injection": False,
    },
    "trades": {
        "signals": [
            "mechanic", "electrician", "plumber", "technician",
            "hvac", "welder", "carpenter", "installer", "maintenance",
            "repair", "field service", "construction", "foreman",
            "machinist", "operator",
        ],
        "skill_style": "certifications",  # Certifications + equipment
        "bullet_style": "action_metric",
        "summary_tone": "trades",
        "allow_tech_injection": False,
    },
}

# Composite signals: when a JD mentions BOTH tech AND management
HYBRID_OVERRIDES = {
    ("management", "technical"): "technical",   # Tech lead → technical
    ("management", "data"): "data",             # DS manager → data
}


def classify_role(jd_text: str, job_title: str = "") -> Dict:
    """
    Classify a job into a role type based on JD text and title.

    Returns:
        {
            "role_type": "technical",
            "confidence": 0.85,
            "skill_style": "technical",
            "bullet_style": "action_tool",
            "summary_tone": "technical",
            "allow_tech_injection": True,
            "secondary_type": "management",  # if hybrid
        }
    """
    combined = f"{job_title} {jd_text}".lower()

    # Score each role type
    scores = {}
    for role_type, config in ROLE_TYPES.items():
        score = 0
        for signal in config["signals"]:
            # Exact match in title gets 3x weight
            if signal in job_title.lower():
                score += 3
            elif signal in combined:
                score += 1
        scores[role_type] = score

    if not any(scores.values()):
        # Default to generic if nothing matches
        logger.info("Role classification: no strong signals, defaulting to 'analytical'")
        return _build_role_result("analytical", 0.3)

    # Sort by score descending
    sorted_roles = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_role = sorted_roles[0]
    secondary_role = sorted_roles[1] if len(sorted_roles) > 1 else None

    # Confidence = proportional to signal strength
    max_possible = len(ROLE_TYPES[top_role[0]]["signals"]) * 3
    confidence = min(top_role[1] / max(max_possible * 0.3, 1), 1.0)

    # Check for hybrid roles
    secondary_type = None
    if secondary_role and secondary_role[1] > 0:
        secondary_type = secondary_role[0]
        # Apply hybrid overrides
        hybrid_key = (top_role[0], secondary_type)
        if hybrid_key in HYBRID_OVERRIDES:
            actual_type = HYBRID_OVERRIDES[hybrid_key]
            logger.info(
                f"Hybrid role detected: {top_role[0]}+{secondary_type} → {actual_type}"
            )
            return _build_role_result(actual_type, confidence, secondary_type)

    logger.info(
        f"Role classified: {top_role[0]} (confidence={confidence:.2f}, "
        f"score={top_role[1]}, secondary={secondary_type})"
    )

    result = _build_role_result(top_role[0], confidence, secondary_type)
    
    # QA/Test roles: enable tech injection even though classified as operations.
    # QA Engineers use Selenium, Python, Jenkins, etc. — these should not be blocked.
    if result["role_type"] == "operations":
        qa_signals = ["qa", "test", "sdet", "automation tester", "quality assurance"]
        if any(sig in combined for sig in qa_signals):
            result["allow_tech_injection"] = True
            logger.info("QA role detected within operations — tech injection enabled")
    
    return result


def _build_role_result(
    role_type: str, confidence: float, secondary_type: str = None
) -> Dict:
    """Build the role classification result dict."""
    config = ROLE_TYPES.get(role_type, ROLE_TYPES["analytical"])
    return {
        "role_type": role_type,
        "confidence": round(confidence, 2),
        "skill_style": config["skill_style"],
        "bullet_style": config["bullet_style"],
        "summary_tone": config["summary_tone"],
        "allow_tech_injection": config["allow_tech_injection"],
        "secondary_type": secondary_type,
    }


# ================================================================
# ROLE-AWARE SKILL FILTERING
# ================================================================

# Skills that should NEVER be injected for non-tech roles
TECH_ONLY_SKILLS = {
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "react", "angular", "vue", "django", "flask", "fastapi", "spring",
    "node.js", "express", "docker", "kubernetes", "terraform",
    "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
    "spark", "hadoop", "kafka", "airflow", "redis", "mongodb",
    "postgresql", "mysql", "elasticsearch",
    "aws", "gcp", "azure", "ci/cd", "jenkins", "github actions",
    "machine learning", "deep learning", "nlp", "computer vision",
    "microservices", "graphql", "rest api",
}

# Skills safe for ANY role
UNIVERSAL_SKILLS = {
    "excel", "powerpoint", "word", "google workspace", "outlook",
    "communication", "leadership", "teamwork", "problem solving",
    "project management", "time management", "data analysis",
    "presentation", "microsoft office", "crm", "erp", "sap",
    "sql", "tableau", "power bi",  # Analytical tools cross boundaries
}


def filter_skills_for_role(
    skills: List[str], role_info: Dict
) -> List[str]:
    """
    Filter skills list to only include role-appropriate skills.
    Prevents tech skills from being injected into non-tech roles.
    """
    if role_info.get("allow_tech_injection", True):
        return skills  # Tech roles: all skills allowed

    # Non-tech: filter out pure tech skills
    filtered = []
    for skill in skills:
        skill_lower = skill.lower().strip()
        if skill_lower in TECH_ONLY_SKILLS:
            continue  # Block tech-only skills
        filtered.append(skill)

    if len(filtered) < len(skills):
        blocked = len(skills) - len(filtered)
        logger.info(
            f"Role filter: blocked {blocked} tech-only skills for "
            f"{role_info['role_type']} role"
        )

    return filtered


def get_role_action_verbs(role_type: str) -> List[str]:
    """Get role-appropriate strong action verbs for bullet generation."""
    ROLE_VERBS = {
        "technical": [
            "Architected", "Engineered", "Developed", "Implemented",
            "Optimized", "Deployed", "Automated", "Designed",
            "Built", "Integrated", "Refactored", "Scaled",
        ],
        "data": [
            "Analyzed", "Modeled", "Predicted", "Quantified",
            "Engineered", "Developed", "Optimized", "Discovered",
            "Visualized", "Automated", "Built", "Processed",
        ],
        "analytical": [
            "Analyzed", "Evaluated", "Assessed", "Researched",
            "Identified", "Quantified", "Forecasted", "Recommended",
            "Synthesized", "Modeled", "Measured", "Benchmarked",
        ],
        "operations": [
            "Streamlined", "Optimized", "Coordinated", "Managed",
            "Reduced", "Improved", "Implemented", "Monitored",
            "Scheduled", "Standardized", "Established", "Maintained",
        ],
        "customer": [
            "Generated", "Exceeded", "Cultivated", "Negotiated",
            "Closed", "Retained", "Expanded", "Resolved",
            "Delivered", "Managed", "Developed", "Secured",
        ],
        "hr": [
            "Recruited", "Onboarded", "Developed", "Facilitated",
            "Designed", "Implemented", "Managed", "Resolved",
            "Coordinated", "Administered", "Led", "Streamlined",
        ],
        "management": [
            "Led", "Directed", "Drove", "Spearheaded",
            "Orchestrated", "Launched", "Transformed", "Scaled",
            "Mentored", "Established", "Championed", "Delivered",
        ],
        "creative": [
            "Designed", "Created", "Crafted", "Produced",
            "Developed", "Conceptualized", "Directed", "Launched",
            "Curated", "Executed", "Delivered", "Reimagined",
        ],
        "trades": [
            "Repaired", "Installed", "Maintained", "Inspected",
            "Diagnosed", "Calibrated", "Serviced", "Operated",
            "Assembled", "Fabricated", "Tested", "Troubleshot",
        ],
    }
    return ROLE_VERBS.get(role_type, ROLE_VERBS["analytical"])
