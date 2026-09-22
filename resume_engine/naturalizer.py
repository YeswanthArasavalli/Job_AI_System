"""
Resume Naturalizer -- Makes LLM-tailored resumes sound human-written.

Transforms robotic phrases into natural language while preserving:
  - All keywords (ATS-critical)
  - Skills section (untouched)
  - Structure (same JSON format)
  - Truth (no fabrication)

Only modifies: summary + experience bullets.
"""

import re
# import random  -- removed for determinism (always use first option)
from typing import Dict, List

from utils.logger import setup_logger

logger = setup_logger(__name__)


class ResumeNaturalizer:
    """
    Post-processes tailored resume JSON to sound more human-written.

    Usage:
        naturalizer = ResumeNaturalizer()
        result = naturalizer.naturalize(resume_json)
        print(result["readability_score"])
    """

    # Robotic phrases -> better alternatives (multiple options for variety)
    _ROBOTIC_REPLACEMENTS = {
        r"^Responsible for\s+": [
            "", "Led ", "Drove ", "Oversaw ",
        ],
        r"^Worked on\s+": [
            "", "Contributed to ", "Delivered ", "Shipped ",
        ],
        r"^Utilized\s+": [
            "Applied ", "Leveraged ", "Used ", "Employed ",
        ],
        r"^Assisted in\s+": [
            "Supported ", "Helped deliver ", "Contributed to ",
        ],
        r"^Involved in\s+": [
            "Played key role in ", "Contributed to ", "Participated in ",
        ],
        r"^Tasked with\s+": [
            "", "Handled ", "Managed ",
        ],
        r"^Helped to\s+": [
            "Enabled ", "Facilitated ", "Supported ",
        ],
        r"^Was responsible for\s+": [
            "Owned ", "Led ", "Managed ",
        ],
        r"^Worked closely with\s+": [
            "Partnered with ", "Collaborated with ", "Teamed up with ",
        ],
        r"^Successfully\s+": [
            "",  # Remove "Successfully" -- let achievements speak
        ],
    }

    # Overused verbs -> varied alternatives
    _VERB_VARIANTS = {
        "managed": ["led", "directed", "oversaw", "coordinated"],
        "developed": ["built", "created", "engineered", "designed"],
        "implemented": ["deployed", "launched", "rolled out", "introduced"],
        "improved": ["enhanced", "boosted", "elevated", "strengthened"],
        "created": ["built", "designed", "crafted", "established"],
        "maintained": ["sustained", "managed", "supported", "kept running"],
        "analyzed": ["studied", "examined", "evaluated", "assessed"],
        "designed": ["architected", "planned", "blueprinted", "shaped"],
    }

    def naturalize(self, resume: dict) -> dict:
        """
        Naturalize a resume JSON. Modifies summary and experience bullets only.

        Args:
            resume: Tailored resume as dict.

        Returns:
            Same structure with naturalized text + readability_score.
        """
        if not resume:
            return resume

        issues_found = 0
        issues_fixed = 0

        # 1. Naturalize summary
        if "summary" in resume and resume["summary"]:
            original = resume["summary"]
            resume["summary"] = self._naturalize_text(original)
            if resume["summary"] != original:
                issues_fixed += 1

        # 2. Naturalize experience bullets
        if "experience" in resume:
            for exp in resume["experience"]:
                # Support both 'bullets' (current model) and 'responsibilities' (legacy)
                bullet_key = "bullets" if "bullets" in exp else "responsibilities" if "responsibilities" in exp else None
                if bullet_key:
                    new_bullets = []
                    seen_verbs = set()

                    for bullet in exp[bullet_key]:
                        issues_found += 1
                        # Remove robotic phrases
                        cleaned = self._remove_robotic(bullet)
                        # Vary verbs
                        cleaned = self._vary_verbs(cleaned, seen_verbs)
                        # Track starting verb
                        first_word = cleaned.split()[0].lower() if cleaned.split() else ""
                        seen_verbs.add(first_word)

                        if cleaned != bullet:
                            issues_fixed += 1
                        new_bullets.append(cleaned)

                    exp[bullet_key] = new_bullets

        # 3. Compute readability score
        all_text = self._extract_all_text(resume)
        readability = self._compute_readability(all_text, issues_found, issues_fixed)
        resume["readability_score"] = readability

        logger.info(f"Naturalized resume: {issues_fixed}/{issues_found} bullets improved, readability={readability}")
        return resume

    def _remove_robotic(self, text: str) -> str:
        """Remove robotic sentence starters."""
        for pattern, replacements in self._ROBOTIC_REPLACEMENTS.items():
            if re.match(pattern, text, re.IGNORECASE):
                replacement = replacements[0]  # deterministic: always first
                text = re.sub(pattern, replacement, text, count=1, flags=re.IGNORECASE)
                # Capitalize first letter
                if text and text[0].islower():
                    text = text[0].upper() + text[1:]
                break
        return text

    def _vary_verbs(self, text: str, seen_verbs: set) -> str:
        """Replace repeated starting verbs with alternatives."""
        words = text.split()
        if not words:
            return text

        first_word = words[0].lower().rstrip("ed").rstrip("d")

        # Check if this verb was already used
        if first_word in seen_verbs or words[0].lower() in seen_verbs:
            for verb, alternatives in self._VERB_VARIANTS.items():
                if words[0].lower() == verb or words[0].lower().startswith(verb[:4]):
                    new_verb = alternatives[0]  # deterministic: always first
                    # Match capitalization
                    if words[0][0].isupper():
                        new_verb = new_verb.capitalize()
                    words[0] = new_verb
                    break

        return " ".join(words)

    def _naturalize_text(self, text: str) -> str:
        """Clean up a freeform text block (like summary)."""
        # Remove robotic phrases
        text = self._remove_robotic(text)

        # Remove filler words
        filler = [
            "in order to", "as well as also", "in addition to also",
            "a highly motivated", "a results-driven", "a detail-oriented",
        ]
        for f in filler:
            text = text.replace(f, "")

        # Clean double spaces
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_all_text(self, resume: dict) -> str:
        """Extract all readable text from resume for scoring."""
        parts = []
        if resume.get("summary"):
            parts.append(resume["summary"])
        for exp in resume.get("experience", []):
            # Support both field names
            bullets = exp.get("bullets", []) or exp.get("responsibilities", [])
            for bullet in bullets:
                parts.append(bullet)
        return " ".join(parts)

    def _compute_readability(self, text: str, total: int, fixed: int) -> int:
        """
        Compute readability score 0-100.

        Factors:
          - Variety of sentence starters (30%)
          - Average sentence length balance (30%)
          - Absence of robotic phrases (40%)
        """
        if not text:
            return 50

        sentences = re.split(r'[.!?\n]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        if not sentences:
            return 50

        # 1. Starter variety (unique first words / total sentences)
        starters = [s.split()[0].lower() for s in sentences if s.split()]
        unique_ratio = len(set(starters)) / max(len(starters), 1)
        variety_score = min(unique_ratio * 100, 100)

        # 2. Sentence length balance (ideal: 10-25 words)
        lengths = [len(s.split()) for s in sentences]
        avg_len = sum(lengths) / max(len(lengths), 1)
        if 10 <= avg_len <= 25:
            length_score = 100
        elif avg_len < 5 or avg_len > 40:
            length_score = 30
        else:
            length_score = 70

        # 3. Robotic phrase absence
        robotic_count = 0
        for pattern in self._ROBOTIC_REPLACEMENTS:
            for sentence in sentences:
                if re.match(pattern, sentence, re.IGNORECASE):
                    robotic_count += 1
        robotic_score = max(0, 100 - robotic_count * 15)

        final = int(variety_score * 0.3 + length_score * 0.3 + robotic_score * 0.4)
        return min(max(final, 0), 100)
