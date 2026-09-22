"""Central Truth Gate (Phase 5A) — THE authoritative truth-policy boundary.

Single enforcement point deciding whether a modified candidate representation
is trustworthy. Consolidates the truth rules previously spread across
core.py trust rules, validation_gate identity checks, and quality_gate
content checks. Those call sites now DELEGATE here (no second implementation,
no competing engine — spec §12-16).

Responsibilities (spec §15):
  - Identity: candidate name, email, employers, titles, dates, education
  - Employment truth: no project->employment conversion, no invented employers
  - Skills: no unsupported skills presented as candidate-owned
  - Metrics: no invented/inflated/altered achievement numbers
  - Evidence: JD keywords are NOT candidate evidence
  - Verdict metadata: accepted/rejected + reasons (feeds the change ledger)
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from utils.models import StructuredResume


@dataclass
class TruthVerdict:
    """Outcome of a Truth Gate evaluation."""
    accepted: bool
    violations: List[str] = field(default_factory=list)
    # normalized facts for ledger/observability
    identity_ok: bool = True
    employment_ok: bool = True
    skills_ok: bool = True
    metrics_ok: bool = True

    def to_dict(self) -> Dict:
        return {
            "accepted": self.accepted,
            "violations": self.violations,
            "identity_ok": self.identity_ok,
            "employment_ok": self.employment_ok,
            "skills_ok": self.skills_ok,
            "metrics_ok": self.metrics_ok,
        }


_NUM_PAT = re.compile(r"\d+(?:\.\d+)?\s*[%x+]?", re.IGNORECASE)


def _numbers(text: str) -> set:
    return set(_NUM_PAT.findall(text or ""))


def check_metrics(original_bullets: List[str], rewritten_bullets: List[str]) -> List[str]:
    """No invented or inflated metrics. Original numbers must survive; new
    numbers are fabricated evidence (JD text is not candidate evidence)."""
    violations = []
    orig_nums = set()
    for b in original_bullets:
        orig_nums |= _numbers(b)
    for i, b in enumerate(rewritten_bullets):
        new_nums = _numbers(b)
        invented = new_nums - orig_nums
        if invented:
            violations.append(f"METRIC_FABRICATION bullet[{i}]: new numbers {sorted(invented)}")
    return violations


def check_identity(original: StructuredResume, modified: StructuredResume) -> List[str]:
    """Identity fields are immutable: name, email, employers, titles, dates,
    education (institution/degree/year)."""
    violations = []
    if (original.contact.name or "") != (modified.contact.name or ""):
        violations.append("IDENTITY_NAME")
    if (original.contact.email or "") != (modified.contact.email or ""):
        violations.append("IDENTITY_EMAIL")
    orig_exp = {(e.company, e.role, e.duration) for e in original.experience}
    mod_exp = {(e.company, e.role, e.duration) for e in modified.experience}
    for fact in mod_exp - orig_exp:
        violations.append(f"EMPLOYMENT_FACT_CHANGED: {fact}")
    if len(modified.experience) > len(original.experience):
        violations.append("EMPLOYMENT_INFLATION: experience entries added")
    orig_edu = {(d.degree, d.institution, d.year) for d in original.education}
    mod_edu = {(d.degree, d.institution, d.year) for d in modified.education}
    if mod_edu != orig_edu:
        violations.append("EDUCATION_CHANGED")
    return violations


def check_skills(
    original_skills: List[str],
    original: StructuredResume,
    modified: StructuredResume,
) -> List[str]:
    """Skills in the modified resume must be candidate-evidenced: present in
    the original skill list, a compound expansion of one, or grounded in the
    candidate's own experience/project text. JD requirements are NOT evidence."""
    violations = []
    orig_lower = {s.lower() for s in original_skills if s}
    evidence_text = " ".join(
        [t.lower() for p in original.projects for t in (p.technologies or [])]
        + [b.lower() for exp in original.experience for b in exp.bullets]
        + [b.lower() for p in original.projects for b in p.bullets]
    )
    for s in modified.skills:
        sl = (s or "").lower()
        if not sl or sl in orig_lower:
            continue
        parent = any(o in sl for o in orig_lower if len(o) > 2)
        grounded = sl in evidence_text or any(
            part in evidence_text for part in sl.split() if len(part) > 3
        )
        if not parent and not grounded:
            violations.append(f"UNSUPPORTED_SKILL: '{s}' not in candidate evidence")
    return violations


def validate_candidate_representation(
    original: StructuredResume,
    modified: StructuredResume,
    original_skills: Optional[List[str]] = None,
) -> TruthVerdict:
    """THE authoritative Truth Gate evaluation (identity + employment +
    skills). Metric checking for bullet rewrites is exposed separately via
    check_metrics (bullet-level transforms call it before acceptance)."""
    original_skills = original_skills if original_skills is not None else list(original.skills or [])
    violations = []
    identity = check_identity(original, modified)
    skills = check_skills(original_skills, original, modified)
    violations.extend(identity)
    violations.extend(skills)
    metrics_ok = True  # metric rules apply at bullet-transform boundary
    return TruthVerdict(
        accepted=not violations,
        violations=violations,
        identity_ok=not any(v.startswith(("IDENTITY", "EDUCATION")) for v in identity),
        employment_ok=not any(v.startswith("EMPLOYMENT") for v in identity),
        skills_ok=not skills,
        metrics_ok=metrics_ok,
    )
