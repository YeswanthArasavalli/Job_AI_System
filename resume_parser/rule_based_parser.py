"""
Rule-Based Resume Parser -- Robust fallback when LLM is unavailable.

Extracts structured resume data from raw text using regex patterns and
section detection heuristics. Handles:
  - Contact info (name, email, phone, LinkedIn)
  - Education (degree, institution, dates)
  - Experience (role, company, dates, bullets)
  - Projects (name, description, technologies, bullets)
  - Skills (comma-separated, tech keyword detection)

DESIGN: This is a FALLBACK parser. The LLM parser is primary.
When LLM fails, this ensures the resume is never empty/incomplete.
"""

import re
from typing import List, Dict, Optional, Tuple
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ================================================================
# SECTION HEADERS (case-insensitive patterns)
# ================================================================

_SECTION_PATTERNS = {
    "education": re.compile(
        r"^(?:education|academic|qualifications?|degrees?)\s*$", re.IGNORECASE
    ),
    "experience": re.compile(
        r"^(?:experience|work\s*experience|employment|professional\s*experience|"
        r"work\s*history|career|positions?)\s*$", re.IGNORECASE
    ),
    "projects": re.compile(
        r"^(?:projects?|personal\s*projects?|academic\s*projects?|"
        r"key\s*projects?|selected\s*projects?)\s*$", re.IGNORECASE
    ),
    "skills": re.compile(
        r"^(?:skills?|technical\s*skills?|core\s*competencies|"
        r"technologies|tech\s*stack|tools?)\s*$", re.IGNORECASE
    ),
    "summary": re.compile(
        r"^(?:summary|profile|objective|about|about\s*me|"
        r"professional\s*summary|career\s*summary)\s*$", re.IGNORECASE
    ),
    "certifications": re.compile(
        r"^(?:certifications?|certificates?|licenses?|accreditations?)\s*$",
        re.IGNORECASE
    ),
}

# ================================================================
# KNOWN TECH SKILLS (for text scanning)
# ================================================================

_KNOWN_SKILLS = [
    # Languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "r", "scala", "kotlin", "swift", "ruby", "php", "perl", "matlab",
    # Data / ML
    "sql", "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch",
    "keras", "xgboost", "lightgbm", "opencv", "nltk", "spacy",
    "hugging face", "transformers", "lstm", "bert", "gpt",
    # Cloud / DevOps
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
    "jenkins", "ci/cd", "git", "github", "gitlab", "linux",
    # Databases
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "cassandra", "dynamodb", "sqlite",
    # Frameworks / Tools
    "react", "angular", "vue", "node.js", "flask", "django", "fastapi",
    "spring", "express", ".net",
    # Data / BI
    "tableau", "power bi", "excel", "spark", "hadoop", "airflow",
    "kafka", "snowflake", "databricks", "dbt",
    # General
    "machine learning", "deep learning", "nlp", "computer vision",
    "data analysis", "data engineering", "etl", "data pipeline",
    "rest api", "microservices", "agile", "scrum",
    "streamlit", "gradio",
]

# ================================================================
# REGEX PATTERNS
# ================================================================

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
_LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w-]+", re.IGNORECASE)

# Date patterns: "Jan 2023", "2023-01", "2023", "Present"
_DATE_RE = re.compile(
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s*\d{4}|"
    r"\d{4}\s*[-–]\s*(?:Present|Current|\d{4})|"
    r"\d{1,2}/\d{4}",
    re.IGNORECASE
)

# Date range: "Jan 2023 - Present", "2020 – 2023"
_DATE_RANGE_RE = re.compile(
    r"("
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s*\d{4}"
    r"|(?:\d{1,2}/\d{4})"
    r"|(?:\d{4})"
    r")"
    r"\s*[-–—to]+\s*"
    r"("
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s*\d{4}"
    r"|Present|Current"
    r"|(?:\d{1,2}/\d{4})"
    r"|(?:\d{4})"
    r")",
    re.IGNORECASE
)

# Degree patterns
_DEGREE_RE = re.compile(
    r"(?:Bachelor|Master|B\.?S\.?c?|M\.?S\.?c?|B\.?A\.?|M\.?A\.?|"
    r"B\.?Tech|M\.?Tech|B\.?E\.?|M\.?E\.?|Ph\.?D\.?|MBA|"
    r"Associate|Diploma|Certificate)\s*"
    r"(?:of\s+(?:Science|Arts|Engineering|Technology|Business))?\s*"
    r"(?:in\s+)?",
    re.IGNORECASE
)

# Bullet markers
_BULLET_RE = re.compile(r"^[\-\*\u2022\u25CF\u25CB\u2023\u2043\u25AA]\s*")


class RuleBasedResumeParser:
    """
    Extract structured resume data from raw text using heuristics.
    
    Usage:
        parser = RuleBasedResumeParser()
        data = parser.parse(raw_text)
    """

    def parse(self, text: str) -> dict:
        """
        Parse raw resume text into structured dict compatible with StructuredResume.
        
        Returns dict with keys: contact, summary, skills, experience,
        education, projects, certifications.
        """
        lines = [l.rstrip() for l in text.split("\n")]
        sections = self._detect_sections(lines)
        
        contact = self._extract_contact(text, lines)
        summary = self._extract_summary(sections, text)
        skills = self._extract_skills(sections, text)
        experience = self._extract_experience(sections)
        education = self._extract_education(sections, text)
        projects = self._extract_projects(sections)
        certifications = self._extract_certifications(sections)
        
        result = {
            "contact": contact,
            "title": "",
            "summary": summary,
            "skills": skills,
            "experience": experience,
            "education": education,
            "projects": projects,
            "certifications": certifications,
        }
        
        logger.info(
            f"Rule-based parse: {contact.get('name', '?')} | "
            f"{len(skills)} skills | {len(experience)} exp | "
            f"{len(education)} edu | {len(projects)} proj"
        )
        return result

    def merge_with_llm(self, llm_data: dict, rule_data: dict) -> dict:
        """
        Merge LLM output with rule-based output.
        LLM is primary; rule-based fills gaps.
        """
        merged = dict(llm_data)
        
        # Fill missing contact fields
        llm_contact = merged.get("contact", {})
        rule_contact = rule_data.get("contact", {})
        if not llm_contact.get("name") and rule_contact.get("name"):
            llm_contact["name"] = rule_contact["name"]
        if not llm_contact.get("email") and rule_contact.get("email"):
            llm_contact["email"] = rule_contact["email"]
        merged["contact"] = llm_contact
        
        # Fill missing skills
        llm_skills = merged.get("skills", [])
        rule_skills = rule_data.get("skills", [])
        if len(llm_skills) < 3 and rule_skills:
            # LLM missed skills — use rule-based
            existing = {s.lower() for s in llm_skills}
            for s in rule_skills:
                if s.lower() not in existing:
                    llm_skills.append(s)
                    existing.add(s.lower())
            merged["skills"] = llm_skills
        
        # Fill missing education
        llm_edu = merged.get("education", [])
        rule_edu = rule_data.get("education", [])
        if not llm_edu and rule_edu:
            merged["education"] = rule_edu
        
        # Fill missing experience
        llm_exp = merged.get("experience", [])
        rule_exp = rule_data.get("experience", [])
        if not llm_exp and rule_exp:
            merged["experience"] = rule_exp
        
        # Fill missing projects
        llm_proj = merged.get("projects", [])
        rule_proj = rule_data.get("projects", [])
        if not llm_proj and rule_proj:
            merged["projects"] = rule_proj
        
        # Fill missing summary
        if not merged.get("summary") and rule_data.get("summary"):
            merged["summary"] = rule_data["summary"]
        
        return merged

    # ================================================================
    # SECTION DETECTION
    # ================================================================

    def _detect_sections(self, lines: List[str]) -> Dict[str, List[str]]:
        """Split text into named sections based on header detection."""
        sections: Dict[str, List[str]] = {}
        current_section = "header"
        sections[current_section] = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current_section in sections:
                    sections[current_section].append("")
                continue
            
            # Check if this line is a section header
            # Headers are typically: ALL CAPS, short, or match known patterns
            is_header = False
            matched_section = None
            
            clean = re.sub(r"^[:\-\|#=]+\s*", "", stripped).strip()
            clean = re.sub(r"\s*[:\-\|#=]+$", "", clean).strip()
            
            for section_name, pattern in _SECTION_PATTERNS.items():
                if pattern.match(clean):
                    is_header = True
                    matched_section = section_name
                    break
            
            # Also detect ALL CAPS headers (e.g., "EDUCATION", "EXPERIENCE")
            if not is_header and stripped.isupper() and len(stripped) < 40:
                clean_upper = clean.lower()
                for section_name, pattern in _SECTION_PATTERNS.items():
                    if pattern.match(clean_upper):
                        is_header = True
                        matched_section = section_name
                        break
            
            if is_header and matched_section:
                current_section = matched_section
                if current_section not in sections:
                    sections[current_section] = []
            else:
                if current_section not in sections:
                    sections[current_section] = []
                sections[current_section].append(line)
        
        return sections

    # ================================================================
    # CONTACT EXTRACTION
    # ================================================================

    def _extract_contact(self, text: str, lines: List[str]) -> dict:
        """Extract name, email, phone, LinkedIn."""
        email_match = _EMAIL_RE.search(text)
        phone_match = _PHONE_RE.search(text)
        linkedin_match = _LINKEDIN_RE.search(text)
        
        # Name: typically the first non-empty, non-email line
        name = ""
        for line in lines[:5]:
            stripped = line.strip()
            if (stripped and not _EMAIL_RE.search(stripped) and
                not _PHONE_RE.search(stripped) and
                len(stripped) < 60 and
                not any(stripped.lower().startswith(w) for w in 
                        ["http", "www", "linkedin", "github", "phone", "email"])):
                name = stripped
                break
        
        return {
            "name": name,
            "email": email_match.group(0) if email_match else "",
            "phone": phone_match.group(0) if phone_match else "",
            "linkedin": linkedin_match.group(0) if linkedin_match else "",
            "location": "",
        }

    # ================================================================
    # SUMMARY EXTRACTION
    # ================================================================

    def _extract_summary(self, sections: dict, full_text: str) -> str:
        """Extract professional summary."""
        if "summary" in sections:
            lines = [l for l in sections["summary"] if l.strip()]
            return " ".join(lines)[:500]
        
        # Fallback: use first paragraph-like block from header
        if "header" in sections:
            lines = [l for l in sections["header"] if l.strip()]
            # Skip contact lines, look for paragraph text
            for i, line in enumerate(lines):
                if (len(line) > 50 and not _EMAIL_RE.search(line) and
                    not _PHONE_RE.search(line)):
                    return line[:500]
        
        return ""

    # ================================================================
    # SKILLS EXTRACTION
    # ================================================================

    def _extract_skills(self, sections: dict, full_text: str) -> List[str]:
        """Extract skills from skills section + text scanning."""
        skills = []
        seen = set()
        
        # From skills section (comma/pipe/bullet separated)
        if "skills" in sections:
            section_text = " ".join(l for l in sections["skills"] if l.strip())
            # Split by common delimiters
            raw = re.split(r"[,|•·\u2022\u25CF]+", section_text)
            for item in raw:
                clean = item.strip().strip("-").strip("*").strip()
                # Remove category labels like "Languages:", "Tools:"
                clean = re.sub(r"^[A-Za-z\s]+:\s*", "", clean).strip()
                if clean and 1 < len(clean) < 40:
                    if clean.lower() not in seen:
                        skills.append(clean)
                        seen.add(clean.lower())
        
        # Scan full text for known skills (catch skills missed by section parsing)
        text_lower = full_text.lower()
        for skill in _KNOWN_SKILLS:
            if skill.lower() not in seen and skill.lower() in text_lower:
                # Verify it's a real occurrence (not substring of another word)
                pattern = re.compile(r"\b" + re.escape(skill) + r"\b", re.IGNORECASE)
                if pattern.search(full_text):
                    skills.append(skill.title() if len(skill) > 3 else skill.upper())
                    seen.add(skill.lower())
        
        return skills[:25]

    # ================================================================
    # EXPERIENCE EXTRACTION
    # ================================================================

    def _extract_experience(self, sections: dict) -> List[dict]:
        """Extract experience entries with role, company, dates, bullets."""
        if "experience" not in sections:
            return []
        
        lines = sections["experience"]
        entries = []
        current_entry = None
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            # Check if this line has a date range (likely a new entry header)
            date_match = _DATE_RANGE_RE.search(stripped)
            is_bullet = bool(_BULLET_RE.match(stripped))
            
            if date_match and not is_bullet:
                # Start new entry
                if current_entry:
                    entries.append(current_entry)
                
                duration = f"{date_match.group(1)} - {date_match.group(2)}"
                # Extract role and company from the non-date part
                header = _DATE_RANGE_RE.sub("", stripped).strip()
                header = re.sub(r"[|\-–—]+$", "", header).strip()
                header = re.sub(r"^[|\-–—]+", "", header).strip()
                
                role, company = self._split_role_company(header)
                
                current_entry = {
                    "role": role,
                    "company": company,
                    "duration": duration,
                    "bullets": [],
                }
            elif is_bullet and current_entry:
                bullet_text = _BULLET_RE.sub("", stripped).strip()
                if len(bullet_text) > 10:
                    current_entry["bullets"].append(bullet_text)
            elif current_entry and len(stripped) > 15:
                # Could be a continuation bullet without marker
                if (stripped[0].isupper() and
                    any(stripped.lower().startswith(v) for v in
                        ["built", "developed", "designed", "managed", "led",
                         "created", "implemented", "analyzed", "optimized",
                         "improved", "automated", "deployed", "established",
                         "maintained", "collaborated", "conducted", "reduced",
                         "increased", "achieved", "spearheaded", "delivered"])):
                    current_entry["bullets"].append(stripped)
            elif not current_entry and not is_bullet:
                # First line might be a role/company without date
                role, company = self._split_role_company(stripped)
                if role:
                    current_entry = {
                        "role": role,
                        "company": company,
                        "duration": "",
                        "bullets": [],
                    }
        
        if current_entry:
            entries.append(current_entry)
        
        return entries

    def _split_role_company(self, text: str) -> Tuple[str, str]:
        """Split 'Software Engineer at Google' into (role, company)."""
        # Try common separators
        for sep in [" at ", " @ ", " - ", " | ", ", "]:
            if sep in text:
                parts = text.split(sep, 1)
                return parts[0].strip(), parts[1].strip()
        return text.strip(), ""

    # ================================================================
    # EDUCATION EXTRACTION
    # ================================================================

    def _extract_education(self, sections: dict, full_text: str) -> List[dict]:
        """Extract education entries."""
        entries = []
        
        if "education" in sections:
            lines = [l for l in sections["education"] if l.strip()]
            current = None
            
            for line in lines:
                stripped = line.strip()
                # Check for degree keywords
                degree_match = _DEGREE_RE.search(stripped)
                if degree_match:
                    if current:
                        entries.append(current)
                    # Extract the full degree line
                    current = {
                        "degree": stripped,
                        "institution": "",
                        "year": "",
                        "details": "",
                    }
                    # Look for year
                    year_match = re.search(r"\b(20\d{2}|19\d{2})\b", stripped)
                    if year_match:
                        current["year"] = year_match.group(1)
                elif current:
                    # Could be institution name or details
                    if ("university" in stripped.lower() or
                        "institute" in stripped.lower() or
                        "college" in stripped.lower() or
                        "school" in stripped.lower()):
                        current["institution"] = stripped
                    elif not current["institution"] and len(stripped) > 5:
                        current["institution"] = stripped
                    else:
                        current["details"] = (
                            current.get("details", "") + " " + stripped
                        ).strip()
                elif not current:
                    # First line might be institution
                    if ("university" in stripped.lower() or
                        "institute" in stripped.lower() or
                        "college" in stripped.lower()):
                        current = {
                            "degree": "",
                            "institution": stripped,
                            "year": "",
                            "details": "",
                        }
                        year_match = re.search(r"\b(20\d{2}|19\d{2})\b", stripped)
                        if year_match:
                            current["year"] = year_match.group(1)
            
            if current:
                entries.append(current)
        
        # Fallback: scan full text for degree patterns
        if not entries:
            for degree_kw in ["master", "bachelor", "b.s", "m.s", "ph.d", "mba"]:
                idx = full_text.lower().find(degree_kw)
                if idx >= 0:
                    # Extract surrounding context
                    start = max(0, full_text.rfind("\n", 0, idx))
                    end = full_text.find("\n", idx + len(degree_kw))
                    if end == -1:
                        end = min(idx + 200, len(full_text))
                    context = full_text[start:end].strip()
                    entries.append({
                        "degree": context[:120],
                        "institution": "",
                        "year": "",
                        "details": "",
                    })
                    break
        
        return entries

    # ================================================================
    # PROJECTS EXTRACTION
    # ================================================================

    def _extract_projects(self, sections: dict) -> List[dict]:
        """Extract project entries."""
        if "projects" not in sections:
            return []
        
        lines = sections["projects"]
        projects = []
        current = None
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            is_bullet = bool(_BULLET_RE.match(stripped))
            
            if not is_bullet and len(stripped) < 80:
                # Likely a project name/header
                if current:
                    projects.append(current)
                
                # Extract technologies from parentheses or brackets
                tech_match = re.search(r"[\(\[](.+?)[\)\]]", stripped)
                techs = []
                if tech_match:
                    techs = [t.strip() for t in tech_match.group(1).split(",")]
                
                name = re.sub(r"[\(\[].*?[\)\]]", "", stripped).strip()
                name = re.sub(r"\s*[-–—|]+\s*$", "", name).strip()
                
                current = {
                    "name": name,
                    "description": "",
                    "technologies": techs,
                    "bullets": [],
                    "url": "",
                }
            elif is_bullet and current:
                bullet_text = _BULLET_RE.sub("", stripped).strip()
                if len(bullet_text) > 10:
                    current["bullets"].append(bullet_text)
            elif current and len(stripped) > 15:
                # Description or continuation
                if not current["description"]:
                    current["description"] = stripped
                else:
                    current["bullets"].append(stripped)
        
        if current:
            projects.append(current)
        
        return projects

    # ================================================================
    # CERTIFICATIONS EXTRACTION
    # ================================================================

    def _extract_certifications(self, sections: dict) -> List[dict]:
        """Extract certification entries."""
        if "certifications" not in sections:
            return []
        
        certs = []
        for line in sections["certifications"]:
            stripped = line.strip()
            if not stripped:
                continue
            cleaned = _BULLET_RE.sub("", stripped).strip()
            if len(cleaned) > 5:
                certs.append({
                    "name": cleaned,
                    "issuer": "",
                    "date": "",
                })
        
        return certs
