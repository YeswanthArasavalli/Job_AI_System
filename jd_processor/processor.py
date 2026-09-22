"""
JD Intelligence Processor -- Cleans, normalizes, and structures raw job descriptions.

This module runs BEFORE the LLM and provides:
  1. Section detection (requirements, responsibilities, skills, etc.)
  2. Noise removal (company fluff, marketing text, legal boilerplate)
  3. Skill extraction (rule-based, no LLM needed)
  4. Experience/education requirement parsing
  5. Clean text for downstream LLM and ATS scoring

Design: Pure Python, zero dependencies beyond stdlib. Fast and deterministic.
"""

import re
from typing import Dict, List, Optional, Tuple

from utils.logger import setup_logger

logger = setup_logger(__name__)


class ProcessedJD:
    """Structured output of JD processing."""

    def __init__(
        self,
        cleaned_text: str = "",
        sections: Dict[str, str] = None,
        skills_required: List[str] = None,
        skills_preferred: List[str] = None,
        soft_skills: List[str] = None,
        tools: List[str] = None,
        responsibilities: List[str] = None,
        experience_required: str = "",
        education_required: str = "",
        education_parsed: Dict = None,
        noise_removed: List[str] = None,
        quality_score: float = 0.0,
    ):
        self.cleaned_text = cleaned_text
        self.sections = sections or {}
        self.skills_required = skills_required or []
        self.skills_preferred = skills_preferred or []
        self.soft_skills = soft_skills or []
        self.tools = tools or []
        self.responsibilities = responsibilities or []
        self.experience_required = experience_required
        self.education_required = education_required
        self.education_parsed = education_parsed or {}
        self.noise_removed = noise_removed or []
        self.quality_score = quality_score

    def to_dict(self) -> dict:
        return {
            "cleaned_jd": self.cleaned_text,
            "skills_required": self.skills_required,
            "skills_preferred": self.skills_preferred,
            "soft_skills": self.soft_skills,
            "tools": self.tools,
            "responsibilities": self.responsibilities,
            "experience_required": self.experience_required,
            "education_required": self.education_required,
            "education_parsed": self.education_parsed,
            "sections_found": list(self.sections.keys()),
            "quality_score": self.quality_score,
        }


class JDProcessor:
    """
    Intelligent JD processor that cleans and structures raw job descriptions.

    Usage:
        processor = JDProcessor()
        result = processor.process(raw_jd_text)
        print(result.skills_required)
        print(result.cleaned_text)
    """

    # Section header patterns (case-insensitive)
    _SECTION_PATTERNS = {
        "requirements": [
            r"(?:requirements|qualifications|what you.?(?:ll )?need|must have|minimum qualifications|required skills)",
        ],
        "responsibilities": [
            r"(?:responsibilities|what you.?(?:ll )?do|duties|key responsibilities|role|about the role|the role)",
        ],
        "preferred": [
            r"(?:nice to have|preferred|bonus|good to have|additional|desirable|plus|advantageous)",
        ],
        "about": [
            r"(?:about (?:us|the company|the team)|who we are|company (?:overview|description))",
        ],
        "benefits": [
            r"(?:benefits|perks|what we offer|compensation|salary|why join|culture)",
        ],
        "education": [
            r"(?:education|academic|degree|certification)",
        ],
    }

    # Noise patterns to remove
    _NOISE_PATTERNS = [
        r"(?:equal\s+opportunity|eoe|we\s+are\s+an?\s+equal)",
        r"(?:we\s+(?:are|offer)\s+(?:a\s+)?competitive\s+(?:salary|compensation|package))",
        r"(?:apply\s+(?:now|today|here|at))",
        r"(?:learn\s+more\s+at|visit\s+(?:our|us))",
        r"(?:disclaimer|privacy\s+policy|terms\s+(?:of|and)\s+(?:use|conditions))",
        r"(?:follow\s+us\s+on|connect\s+with\s+us)",
        r"(?:©|copyright|all\s+rights\s+reserved)",
        r"(?:job\s+(?:id|code|ref(?:erence)?)\s*[:# ]\s*\S+)",
    ]

    # Tech skill patterns for extraction
    _TECH_SKILLS = [
        # Languages
        "python", "java", "javascript", "typescript", "c\\+\\+", "c#", "go", "golang",
        "rust", "ruby", "php", "swift", "kotlin", "scala", "perl", "r\\b",
        # Frameworks
        "react", "angular", "vue", "node\\.?js", "django", "flask", "fastapi",
        "spring", "spring boot", "express", "next\\.?js", "rails",
        # Data
        "sql", "nosql", "mongodb", "postgresql", "mysql", "redis",
        "elasticsearch", "apache spark", "spark", "hadoop", "airflow",
        "kafka", "dbt", "snowflake", "bigquery", "redshift",
        "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch",
        "power bi", "tableau", "excel", "looker",
        # Cloud/DevOps
        "aws", "azure", "gcp", "google cloud", "docker", "kubernetes",
        "terraform", "jenkins", "ci/cd", "github actions", "gitlab",
        # Concepts
        "machine learning", "deep learning", "nlp", "computer vision",
        "data analysis", "data science", "data engineering",
        "etl", "rest api", "graphql", "microservices",
        "agile", "scrum", "jira", "git",
        "a/b testing", "statistical analysis", "data visualization",
        "linux", "bash",
    ]

    def process(self, raw_jd: str) -> ProcessedJD:
        """
        Process a raw JD text into structured, clean output.

        Args:
            raw_jd: Raw job description text.

        Returns:
            ProcessedJD with cleaned text, extracted skills, etc.
        """
        if not raw_jd or len(raw_jd.strip()) < 20:
            logger.warning("JD too short for processing")
            return ProcessedJD(cleaned_text=raw_jd.strip(), quality_score=0.0)

        logger.info(f"Processing JD ({len(raw_jd)} chars)...")

        # Step 1: Basic cleaning
        cleaned = self._basic_clean(raw_jd)

        # Step 2: Detect sections
        sections = self._detect_sections(cleaned)

        # Step 3: Remove noise
        cleaned, noise_removed = self._remove_noise(cleaned)

        # Step 4: Extract skills
        skills_req, skills_pref = self._extract_skills(cleaned, sections)

        # Step 5: Extract responsibilities
        responsibilities = self._extract_bullet_list(
            sections.get("responsibilities", "")
        )
        # Fallback: if no responsibilities section detected, scan full text
        if not responsibilities:
            responsibilities = self._fallback_extract_responsibilities(cleaned)

        # Step 6: Extract experience requirement
        experience = self._extract_experience(cleaned)

        # Step 7: Extract education requirement
        education = self._extract_education(cleaned)
        education_parsed = self._parse_education_structured(cleaned)

        # Step 8: Extract soft skills & tools (do NOT mix with technical)
        soft_skills = self._extract_soft_skills(cleaned)
        tools = self._extract_tools(cleaned, skills_req + skills_pref)

        # Step 9: Calculate quality score
        quality = self._calculate_quality(sections, skills_req, responsibilities)

        result = ProcessedJD(
            cleaned_text=cleaned,
            sections=sections,
            skills_required=skills_req,
            skills_preferred=skills_pref,
            soft_skills=soft_skills,
            tools=tools,
            responsibilities=responsibilities,
            experience_required=experience,
            education_required=education,
            education_parsed=education_parsed,
            noise_removed=noise_removed,
            quality_score=quality,
        )

        logger.info(
            f"JD processed: {len(skills_req)} required skills, "
            f"{len(responsibilities)} responsibilities, quality={quality:.0f}%"
        )

        return result

    # ================================================================
    # Processing Steps
    # ================================================================

    def _basic_clean(self, text: str) -> str:
        """Basic text normalization."""
        # Normalize whitespace
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\t', ' ', text)
        # Collapse multiple blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Normalize bullet characters
        text = re.sub(r'[\u2022\u25e6\u25cf\u25aa\u25b8\u25ba\u2023\u2043]', '-', text)
        text = re.sub(r'^\s*[******]\s*', '- ', text, flags=re.MULTILINE)
        # Remove excessive spaces
        text = re.sub(r'[ ]{3,}', '  ', text)
        return text.strip()

    def _detect_sections(self, text: str) -> Dict[str, str]:
        """Detect and extract JD sections based on header patterns."""
        sections = {}
        lines = text.split('\n')

        current_section = "intro"
        current_lines = []

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                current_lines.append("")
                continue

            # Check if this line is a section header
            detected = self._match_section_header(line_stripped)
            if detected:
                # Save previous section
                if current_lines:
                    content = '\n'.join(current_lines).strip()
                    if content:
                        sections[current_section] = content

                current_section = detected
                current_lines = []
            else:
                current_lines.append(line)

        # Save last section
        if current_lines:
            content = '\n'.join(current_lines).strip()
            if content:
                sections[current_section] = content

        return sections

    def _match_section_header(self, line: str) -> Optional[str]:
        """Check if a line is a section header."""
        # Clean the line for matching
        clean = re.sub(r'[:;\-\u2013\u2014]$', '', line).strip()
        clean_lower = clean.lower()

        # Skip if line is too long (probably not a header)
        if len(clean) > 80:
            return None

        for section_name, patterns in self._SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, clean_lower):
                    return section_name

        return None

    def _remove_noise(self, text: str) -> Tuple[str, List[str]]:
        """Remove marketing fluff and noise from JD."""
        removed = []
        lines = text.split('\n')
        clean_lines = []

        for line in lines:
            line_lower = line.strip().lower()

            # Skip empty lines
            if not line_lower:
                clean_lines.append(line)
                continue

            # Check noise patterns
            is_noise = False
            for pattern in self._NOISE_PATTERNS:
                if re.search(pattern, line_lower):
                    removed.append(line.strip())
                    is_noise = True
                    break

            if not is_noise:
                clean_lines.append(line)

        return '\n'.join(clean_lines), removed

    def _extract_skills(
        self, text: str, sections: Dict[str, str]
    ) -> Tuple[List[str], List[str]]:
        """Extract required and preferred skills from JD."""
        text_lower = text.lower()

        # Get section-specific text
        req_text = sections.get("requirements", "").lower()
        pref_text = sections.get("preferred", "").lower()

        required = []
        preferred = []
        seen = set()

        for skill_pattern in self._TECH_SKILLS:
            pattern = r'\b' + skill_pattern + r'\b'
            try:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    # Normalize the skill name
                    match = re.search(pattern, text_lower, re.IGNORECASE)
                    skill_name = match.group(0).strip()

                    if skill_name in seen:
                        continue
                    seen.add(skill_name)

                    # Classify as required or preferred
                    if pref_text and re.search(pattern, pref_text, re.IGNORECASE):
                        preferred.append(skill_name)
                    else:
                        required.append(skill_name)
            except re.error:
                continue

        return required, preferred

    def _extract_bullet_list(self, section_text: str) -> List[str]:
        """Extract bullet points from a section."""
        if not section_text:
            return []

        bullets = []
        lines = section_text.split('\n')

        for line in lines:
            stripped = line.strip()
            # Match bullet patterns
            cleaned = re.sub(r'^[\-\*•◦●]\s*', '', stripped)
            cleaned = re.sub(r'^\d+[.)]\s*', '', cleaned)  # Numbered lists

            if cleaned and len(cleaned) > 10:
                bullets.append(cleaned)

        return bullets

    def _extract_experience(self, text: str) -> str:
        """Extract experience requirement."""
        patterns = [
            r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp|work)',
            r'(?:minimum|at\s+least)\s*(\d+)\s*(?:years?|yrs?)',
            r'(\d+)\s*-\s*(\d+)\s*(?:years?|yrs?)',
        ]

        text_lower = text.lower()
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                if match.lastindex == 2:  # Range pattern
                    return f"{match.group(1)}-{match.group(2)} years"
                return f"{match.group(1)}+ years"

        return ""

    def _extract_education(self, text: str) -> str:
        """Extract education requirement."""
        text_lower = text.lower()

        degree_patterns = [
            (r"(?:ph\.?d|doctorate)", "PhD"),
            (r"(?:master'?s?|mba|m\.?s\.?|m\.?tech)", "Master's"),
            (r"(?:bachelor'?s?|b\.?s\.?|b\.?tech|b\.?e\.?)", "Bachelor's"),
        ]

        for pattern, label in degree_patterns:
            if re.search(pattern, text_lower):
                # Try to find the field
                field_match = re.search(
                    pattern + r'[^.]*?(?:in|of)\s+([^,.\n]+)',
                    text_lower
                )
                if field_match:
                    return f"{label} in {field_match.group(1).strip().title()}"
                return label

        return ""

    def _calculate_quality(
        self,
        sections: Dict[str, str],
        skills: List[str],
        responsibilities: List[str],
    ) -> float:
        """
        Rate JD quality (0-100).
        Higher quality = more reliable ATS scoring.
        """
        score = 0.0

        # Has requirements section
        if "requirements" in sections:
            score += 25

        # Has responsibilities section
        if "responsibilities" in sections:
            score += 20

        # Has skills extracted
        if len(skills) >= 3:
            score += 20
        elif len(skills) >= 1:
            score += 10

        # Has responsibilities extracted
        if len(responsibilities) >= 3:
            score += 15
        elif len(responsibilities) >= 1:
            score += 8

        # Reasonable length
        total_text = " ".join(sections.values())
        word_count = len(total_text.split())
        if word_count >= 100:
            score += 10
        elif word_count >= 50:
            score += 5

        # Has preferred section (shows thoroughness)
        if "preferred" in sections:
            score += 10

        return min(score, 100)

    def _extract_soft_skills(self, text: str) -> List[str]:
        """Extract soft skills separately from technical skills."""
        soft_patterns = [
            "communication", "leadership", "teamwork", "problem solving",
            "problem-solving", "critical thinking", "time management",
            "collaboration", "adaptability", "attention to detail",
            "presentation", "mentoring", "stakeholder management",
            "cross-functional", "self-motivated", "interpersonal",
            "analytical thinking", "decision making", "project management",
        ]
        text_lower = text.lower()
        found = []
        for skill in soft_patterns:
            if skill in text_lower and skill not in found:
                found.append(skill)
        return found

    def _extract_tools(self, text: str, already_extracted: List[str]) -> List[str]:
        """Extract tools/platforms that aren't core technical skills."""
        tool_patterns = [
            "jira", "confluence", "slack", "notion", "trello",
            "figma", "sketch", "postman", "swagger",
            "databricks", "datadog", "splunk", "grafana", "prometheus",
            "sagemaker", "mlflow", "weights & biases", "wandb",
            "jupyter", "colab", "vs code", "pycharm",
        ]
        text_lower = text.lower()
        already_lower = {s.lower() for s in already_extracted}
        found = []
        for tool in tool_patterns:
            if tool in text_lower and tool not in already_lower:
                found.append(tool)
        return found

    def _parse_education_structured(self, text: str) -> Dict:
        """Parse education into structured {level, domains} for matching engine."""
        text_lower = text.lower()

        # Detect level
        level = "any"
        level_patterns = [
            (r"(?:ph\.?d|doctorate)", "phd"),
            (r"(?:master|mba|m\.?s\.?|m\.?tech)", "masters"),
            (r"(?:bachelor|b\.?s\.?|b\.?tech|b\.?e\.?)", "bachelors"),
        ]
        for pattern, lbl in level_patterns:
            if re.search(pattern, text_lower):
                level = lbl
                break

        # Detect accepted domains
        domain_keywords = {
            "cs": ["computer science", "software", "computing", "information technology"],
            "data_science": ["data science", "analytics", "big data", "data engineering"],
            "statistics": ["statistics", "statistical", "biostatistics"],
            "mathematics": ["mathematics", "math", "applied math"],
            "engineering": ["engineering", "electrical", "mechanical"],
            "business": ["business", "management", "finance", "economics"],
        }
        domains = []
        for domain, keywords in domain_keywords.items():
            if any(kw in text_lower for kw in keywords):
                domains.append(domain)

        # Check for "or related field"
        if re.search(r"related\s+(?:field|discipline|area)", text_lower):
            if not domains:
                domains = ["cs", "data_science", "statistics", "mathematics"]

        return {"level": level, "domains": domains}

    def _fallback_extract_responsibilities(self, text: str) -> List[str]:
        """
        Fallback: extract responsibilities from full JD text when no
        responsibilities section header is detected.

        Looks for sentences starting with action verbs or bullet patterns.
        """
        responsibilities = []

        # Action verbs that typically start responsibility sentences
        action_verbs = [
            "build", "develop", "design", "implement", "create", "manage",
            "lead", "drive", "analyze", "write", "maintain", "deploy",
            "collaborate", "work with", "ensure", "define", "support",
            "monitor", "optimize", "contribute", "research", "evaluate",
            "conduct", "perform", "coordinate", "deliver", "establish",
            "integrate", "automate", "troubleshoot", "mentor",
        ]

        lines = text.split('\n')
        for line in lines:
            stripped = line.strip()
            # Remove bullet markers
            cleaned = re.sub(r'^[\-\*\u2022\u25E6\u25CF]\s*', '', stripped)
            cleaned = re.sub(r'^\d+[.)]\s*', '', cleaned)

            if not cleaned or len(cleaned) < 15:
                continue

            # Check if line starts with an action verb
            first_word = cleaned.split()[0].lower().rstrip('s').rstrip('ing')
            clean_lower = cleaned.lower()

            is_responsibility = any(
                clean_lower.startswith(verb) for verb in action_verbs
            )

            # Also match bullet-like patterns (short-to-medium lines)
            if not is_responsibility and len(cleaned) < 200:
                is_responsibility = any(
                    verb in clean_lower[:30] for verb in action_verbs
                )

            if is_responsibility:
                responsibilities.append(cleaned)

        if responsibilities:
            logger.info(
                f"Responsibilities fallback: extracted {len(responsibilities)} "
                f"from full text"
            )

        return responsibilities[:15]  # Cap at 15
