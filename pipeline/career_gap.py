"""Career-Gap & Evidence Evaluation (Phase 6D, spec sections 45-46).

Composes EXISTING detectors — nothing here re-scores and gap detection is
NOT rebuilt (spec: "Career-gap detection already exists. Do NOT rebuild it."):
  - career continuity: resume_intelligence flag already surfaced on the
    pipeline result as resume_type["flags"] == "employment_gap";
  - evidence categories: the 6B decision-explanation statuses, extended to
    the six spec categories (Unknown fallback, Transferable Evidence via the
    existing ats_scoring synonym engine);
  - proof strength: content_quality.score_proof_strength per demonstrating
    bullet;
  - presentation guidance: resume_type["strategy_hints"] (existing output);
  - capability gaps: hiring_simulation["gaps"] verbatim.

Honesty contract: a detected gap has NO invented explanation. The candidate
provides none in structured data, so the field reads "explanation
unavailable". Missing evidence never proves inability (spec section 46).
"""
import logging
import re
from typing import Dict, List

from ats_scoring.synonyms import are_synonyms, get_synonyms
from pipeline.content_quality import score_proof_strength

logger = logging.getLogger(__name__)

# Spec 6D evidence categories
STRONGLY_SUPPORTED = "STRONGLY_SUPPORTED"
PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
TRANSFERABLE_EVIDENCE = "TRANSFERABLE_EVIDENCE"
MISSING_EVIDENCE = "MISSING_EVIDENCE"
EXPLICITLY_MISSING = "EXPLICITLY_MISSING"
UNKNOWN = "UNKNOWN"

_CATEGORIES = (STRONGLY_SUPPORTED, PARTIALLY_SUPPORTED, TRANSFERABLE_EVIDENCE,
               MISSING_EVIDENCE, EXPLICITLY_MISSING, UNKNOWN)

# 6B -> 6D rename; UNKNOWN is the explicit fallback for anything unmapped.
_6B_TO_6D = {
    "STRONG": STRONGLY_SUPPORTED,
    "PARTIAL": TRANSFERABLE_EVIDENCE,   # "related evidence (transferable)"
    "MISSING_EVIDENCE": MISSING_EVIDENCE,
    "EXPLICITLY_MISSING": EXPLICITLY_MISSING,
}

# What each category honestly means (spec section 46 distinction: weak
# evidence vs. capability-not-establishable; never "candidate truly lacks").
CATEGORY_MEANING = {
    STRONGLY_SUPPORTED: "listed and demonstrated in experience/projects",
    PARTIALLY_SUPPORTED: "demonstrated in bullets but not listed as a skill",
    TRANSFERABLE_EVIDENCE: ("related/synonym evidence present; "
                            "may have capability but direct evidence is weak"),
    MISSING_EVIDENCE: ("listed in skills section only; "
                       "capability may exist but is not evidenced"),
    EXPLICITLY_MISSING: ("no evidence anywhere; capability cannot be "
                         "established from this resume (absence of evidence, "
                         "not proof of absence)"),
    UNKNOWN: "status could not be determined from available inputs",
}


def _bullet_index(resume) -> List[Dict]:
    """Every experience/project bullet once, with proof strength attached."""
    rows = []
    for e in resume.experience:
        for b in e.bullets:
            rows.append({"text": b, "lower": b.lower(),
                         "proof": score_proof_strength(b)})
    for p in getattr(resume, "projects", None) or []:
        for b in p.bullets:
            rows.append({"text": b, "lower": b.lower(),
                         "proof": score_proof_strength(b)})
    return rows


def _gap_years(resume) -> float:
    """Year-granularity duration of the largest between-role gap, computed
    from the SAME duration strings the existing detector parses. Only called
    after the existing flag reports a gap; presentation layer, not detection."""
    pairs = []
    for exp in resume.experience:
        years = re.findall(r"\d{4}", (exp.duration or "").lower())
        if len(years) >= 2:
            try:
                pairs.append((int(years[0]), int(years[-1])))
            except ValueError:
                pass
    pairs.sort(reverse=True)
    best = 0
    for i in range(len(pairs) - 1):
        gap = pairs[i][0] - pairs[i + 1][1]
        if gap > best:
            best = gap
    return float(best)


def _evidence_category(item: Dict, bullets: List[Dict],
                       resume_skill_set) -> Dict:
    """Map one 6B evidence item into the 6D taxonomy + proof detail."""
    skill = item["skill"]
    sl = skill.lower()
    status = _6B_TO_6D.get(item.get("status", ""), UNKNOWN)

    demonstrated = [{"bullet": r["text"], "proof_strength": r["proof"]}
                    for r in bullets if sl in r["lower"]][:3]

    entry = {"skill": skill, "category": status,
             "meaning": CATEGORY_MEANING[status],
             "confidence": item.get("confidence", "LOW"),
             "demonstrated_by": demonstrated}

    if status in (MISSING_EVIDENCE, EXPLICITLY_MISSING, UNKNOWN):
        # Transferable check via the EXISTING synonym engine only: a listed
        # synonym, or a synonym term appearing in a bullet. Capped at
        # TRANSFERABLE_EVIDENCE — never promoted to supported.
        via = [s for s in resume_skill_set
               if s.lower() != sl and are_synonyms(skill, s)]
        if not via:
            syns = {t for t in get_synonyms(sl)} - {sl}
            via = [r["text"] for r in bullets
                   if any(t in r["lower"].split() for t in syns)][:2]
        if via:
            entry["category"] = TRANSFERABLE_EVIDENCE
            entry["meaning"] = CATEGORY_MEANING[TRANSFERABLE_EVIDENCE]
            entry["transferable_via"] = via
    return entry


def evaluate_career_gaps(resume, pipeline_result, explanation: Dict) -> Dict:
    """Unified gap + evidence view over signals the pipeline ALREADY produced.

    `explanation` is the 6B decision_explanation dict — passed in, never
    rebuilt here, so the two layers can never disagree.
    """
    exp = explanation or {}
    evidence = [_evidence_category(item, _bullet_index(resume),
                                   set(resume.skills or []))
                for item in exp.get("evidence", [])]
    counts = {c: 0 for c in _CATEGORIES}
    for e in evidence:
        counts[e["category"]] += 1

    # --- career continuity (existing flag; §45 five evaluation fields) ----
    rt = getattr(pipeline_result, "resume_type", None) or {}
    gap_detected = "employment_gap" in (rt.get("flags") or [])
    if gap_detected:
        continuity = {
            "gap_detected": True,
            "gap_duration_years": _gap_years(resume),
            "duration_basis": "year-granularity heuristic on duration strings",
            "evidence_around_gap": [
                {"role": e.role, "company": e.company, "duration": e.duration}
                for e in resume.experience],
            # §45: candidate provides no explanation in structured data —
            # never invent one ("candidate left employment because X" forbidden).
            "explanation": "explanation unavailable",
            "explanation_unavailable": True,
            "presentation_guidance": rt.get("strategy_hints", []),
        }
    else:
        continuity = {"gap_detected": False,
                      "explanation_unavailable": False,
                      "presentation_guidance": []}

    # --- decision impact (read from the decision already made, not re-made)
    blocking = {b.lower() for b in exp.get("blocking_gaps", [])}
    gap_skills_blocking = [e["skill"] for e in evidence
                           if e["skill"].lower() in blocking
                           and e["category"] in (MISSING_EVIDENCE,
                                                 EXPLICITLY_MISSING,
                                                 TRANSFERABLE_EVIDENCE,
                                                 UNKNOWN)]
    decision_impact = {
        "decision": exp.get("decision", ""),
        "evidence_gaps_in_blocking": gap_skills_blocking,
        "effect": ("weak-evidence skills appear among blocking gaps"
                   if gap_skills_blocking else
                   "no blocking gap attributable to evidence status"),
    }

    # --- hiring_simulation gap list, verbatim (no re-scoring) -------------
    gaps = list((getattr(pipeline_result, "hiring_simulation", None) or {})
                .get("gaps") or [])

    limitations = [
        "Evidence categories are keyword/synonym heuristics, not verified skill possession",
        "Absence of resume evidence is not proof the candidate lacks a skill (spec 46)",
        "Employment-gap detection is the existing >1-year year-granularity heuristic",
        "Gap explanations are never inferred; candidate-provided context is absent",
        "No outcome data or calibration feeds this evaluation",
    ]

    return {
        "evidence": evidence,
        "category_counts": counts,
        "career_continuity": continuity,
        "decision_impact": decision_impact,
        "capability_gaps": gaps,
        "limitations": limitations,
    }
