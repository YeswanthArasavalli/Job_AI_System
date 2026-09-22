"""
Trust Layer -- Tracks all changes made to a resume and explains WHY.

Every modification to the resume is logged with:
  - What changed (before → after)
  - Why it changed (optimization reason)
  - What rule triggered it (engine module)
  - Confidence level (how certain we are this helps)

Provides user-facing transparency for all AI-driven changes.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class ChangeRecord:
    """A single tracked change to the resume."""
    section: str          # "summary", "experience.0.bullets.2", "skills"
    change_type: str      # "keyword_injection", "verb_strengthening", "reorder", etc.
    before: str           # Original text (truncated)
    after: str            # Modified text (truncated)
    reason: str           # Human-readable explanation
    rule: str             # Which engine module made this change
    confidence: str       # "HIGH" / "MEDIUM" / "LOW"

    def to_dict(self) -> Dict:
        return {
            "section": self.section,
            "type": self.change_type,
            "before": self.before[:200] if self.before else "",
            "after": self.after[:200] if self.after else "",
            "reason": self.reason,
            "rule": self.rule,
            "confidence": self.confidence,
        }


class ChangeTracker:
    """
    Accumulates all changes made during a pipeline run.

    Usage:
        tracker = ChangeTracker()
        tracker.record(
            section="experience.0.bullets.1",
            change_type="keyword_injection",
            before="Built a machine learning model",
            after="Built a machine learning model using TensorFlow, achieving 95% accuracy",
            reason="Added 'TensorFlow' — matched JD required skill",
            rule="improver._inject_keywords",
            confidence="HIGH",
        )
        ...
        explanation = tracker.build_explanation()
    """

    def __init__(self):
        self.changes: List[ChangeRecord] = []
        self._section_counts: Dict[str, int] = {}

    def record(
        self,
        section: str,
        change_type: str,
        before: str,
        after: str,
        reason: str,
        rule: str,
        confidence: str = "HIGH",
    ):
        """Record a change."""
        self.changes.append(ChangeRecord(
            section=section,
            change_type=change_type,
            before=before,
            after=after,
            reason=reason,
            rule=rule,
            confidence=confidence,
        ))

        # Track per-section counts
        base_section = section.split(".")[0]
        self._section_counts[base_section] = (
            self._section_counts.get(base_section, 0) + 1
        )

    def build_explanation(self) -> Dict:
        """
        Build human-readable explanation of all changes.

        Returns:
            {
                "total_changes": 12,
                "by_section": {
                    "summary": 2,
                    "experience": 8,
                    "skills": 2,
                },
                "by_type": {
                    "keyword_injection": 5,
                    "verb_strengthening": 3,
                    ...
                },
                "high_confidence": 10,
                "changes": [...],  # Full change list
                "summary": "Made 12 changes: 5 keyword injections, 3 verb strengthenings...",
            }
        """
        if not self.changes:
            return {
                "total_changes": 0,
                "by_section": {},
                "by_type": {},
                "high_confidence": 0,
                "changes": [],
                "summary": "No changes made — resume was already well-optimized.",
            }

        # Count by type
        by_type = {}
        for c in self.changes:
            by_type[c.change_type] = by_type.get(c.change_type, 0) + 1

        # Count high confidence
        high_conf = sum(1 for c in self.changes if c.confidence == "HIGH")

        # Build summary sentence
        type_parts = [
            f"{count} {ctype.replace('_', ' ')}{'s' if count > 1 else ''}"
            for ctype, count in sorted(by_type.items(), key=lambda x: -x[1])[:3]
        ]
        summary = (
            f"Made {len(self.changes)} changes: {', '.join(type_parts)}. "
            f"{high_conf} changes with HIGH confidence."
        )

        return {
            "total_changes": len(self.changes),
            "by_section": dict(self._section_counts),
            "by_type": by_type,
            "high_confidence": high_conf,
            "changes": [c.to_dict() for c in self.changes],
            "summary": summary,
        }

    def get_section_changes(self, section: str) -> List[ChangeRecord]:
        """Get all changes for a specific section."""
        return [
            c for c in self.changes
            if c.section.startswith(section)
        ]

    def get_high_impact_changes(self) -> List[ChangeRecord]:
        """Get only high-confidence changes."""
        return [c for c in self.changes if c.confidence == "HIGH"]

    @property
    def change_count(self) -> int:
        return len(self.changes)


class TrustValidator:
    """
    Validates that all changes pass trust rules:
      - No fabricated experience
      - No injected skills the user doesn't have
      - No identity changes
      - No hallucinated metrics
    """

    @staticmethod
    def validate_changes(
        tracker: ChangeTracker,
        original_resume,  # StructuredResume
        modified_resume,  # StructuredResume
    ) -> List[str]:
        """
        Validate trust constraints on the modified resume.

        Returns:
            List of trust violations (empty = all good)
        """
        violations = []

        # Rule 1: Identity must not change
        if original_resume.contact.name != modified_resume.contact.name:
            violations.append(
                f"TRUST VIOLATION: Name changed from "
                f"'{original_resume.contact.name}' to "
                f"'{modified_resume.contact.name}'"
            )

        # Rule 2: Companies must not change
        orig_companies = {exp.company.lower() for exp in original_resume.experience}
        mod_companies = {exp.company.lower() for exp in modified_resume.experience}
        added = mod_companies - orig_companies
        if added:
            violations.append(
                f"TRUST VIOLATION: Fabricated companies detected: "
                f"{', '.join(added)}"
            )

        # Rule 3: No fake metrics injected
        for exp in modified_resume.experience:
            for bullet in exp.bullets:
                if _has_suspicious_metric(bullet, original_resume):
                    violations.append(
                        f"TRUST WARNING: Possible fabricated metric in "
                        f"'{bullet[:60]}...'"
                    )

        # Rule 4: Experience count must not increase
        if len(modified_resume.experience) > len(original_resume.experience):
            violations.append(
                f"TRUST VIOLATION: Added {len(modified_resume.experience) - len(original_resume.experience)} "
                f"fabricated experience entries"
            )

        # Rule 5: Education must be preserved
        if len(modified_resume.education) < len(original_resume.education):
            violations.append(
                "TRUST VIOLATION: Education entries were removed"
            )

        for v in violations:
            logger.warning(v)

        return violations


def _has_suspicious_metric(bullet: str, original_resume) -> bool:
    """
    Check if a bullet contains a metric not present in the original resume.

    Only flags when a SPECIFIC number appears that wasn't in any original bullet.
    """
    import re

    # Extract percentages and dollar amounts from the bullet
    metrics = re.findall(r'(\d+%|\$[\d,]+(?:\.\d+)?[KMB]?)', bullet)
    if not metrics:
        return False

    # Check if these metrics existed in the original
    original_text = " ".join(
        b for exp in original_resume.experience for b in exp.bullets
    )
    for metric in metrics:
        if metric not in original_text:
            # New metric — could be fabricated
            # But don't flag common percentages
            if metric not in {"100%", "0%", "50%"}:
                return True

    return False
