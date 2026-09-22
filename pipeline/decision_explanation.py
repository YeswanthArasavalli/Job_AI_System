"""Decision Explanation Engine (Phase 6B).

Structured, evidence-grounded explanations for hiring-simulation results and
application decisions. NO post-hoc LLM generation (spec section 35): every
explanation is assembled from actual structured decision inputs (scores,
signals, gaps, evidence, Truth Gate verdicts) produced by the canonical
pipeline.

Terminology contract (spec section 31):
  The fit number is a HEURISTIC "Fit Estimate", never an empirical
  probability. Every explanation carries the limitation statement.

Classification vocabulary for signals (spec section 31):
  FACT / MEASURED_SIGNAL / HEURISTIC / POLICY_RULE / LLM_DERIVED
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

LIMITATIONS = [
    "Heuristic simulation, not an empirical hiring probability",
    "No proprietary employer hiring process is modeled",
    "No recruiter behavioral dataset behind the signals",
    "Candidate evidence limited to resume content",
    "JD may not capture the full hiring context",
    "Competition is estimated, not observed",
]


@dataclass
class EvidenceItem:
    """A single evidence-backed claim about the candidate."""
    skill: str
    status: str          # STRONG / PARTIAL / MISSING_EVIDENCE / EXPLICITLY_MISSING / UNKNOWN
    proof: str           # where the evidence comes from (or "" if none)
    confidence: str      # HIGH / MEDIUM / LOW

    def to_dict(self) -> Dict:
        return {"skill": self.skill, "status": self.status,
                "proof": self.proof, "confidence": self.confidence}


@dataclass
class DecisionExplanation:
    """Spec section 33 contract."""
    decision: str
    why: str
    supporting_strengths: List[str] = field(default_factory=list)
    blocking_gaps: List[str] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)
    evidence_gaps: List[str] = field(default_factory=list)
    evidence: List[EvidenceItem] = field(default_factory=list)
    positive_signals: List[str] = field(default_factory=list)
    negative_signals: List[str] = field(default_factory=list)
    heuristic_factors: List[str] = field(default_factory=list)
    fit_estimate: Optional[float] = None
    fit_basis: str = "heuristic alignment model"
    truth_result: str = "UNKNOWN"
    recommended_next_action: str = ""
    limitations: List[str] = field(default_factory=lambda: list(LIMITATIONS))

    def to_dict(self) -> Dict:
        return {
            "decision": self.decision,
            "why": self.why,
            "supporting_strengths": self.supporting_strengths,
            "blocking_gaps": self.blocking_gaps,
            "missing_requirements": self.missing_requirements,
            "evidence_gaps": self.evidence_gaps,
            "evidence": [e.to_dict() for e in self.evidence],
            "positive_signals": self.positive_signals,
            "negative_signals": self.negative_signals,
            "heuristic_factors": self.heuristic_factors,
            "fit_estimate": self.fit_estimate,
            "fit_basis": self.fit_basis,
            "truth_result": self.truth_result,
            "recommended_next_action": self.recommended_next_action,
            "limitations": self.limitations,
        }


def build_decision_explanation(
    decision: str,
    decision_reason: str,
    ats_report,
    pipeline_result,
    original,
    jd,
) -> DecisionExplanation:
    """Assemble the structured explanation from canonical pipeline outputs.

    Every field is derived from actual inputs; nothing is generated after the
    fact and nothing is invented (spec sections 32-35, 55).
    """
    hiring = getattr(pipeline_result, "hiring_simulation", None) or {}
    trace = getattr(pipeline_result, "pipeline_trace", None) or {}
    original_skills = {s.lower() for s in (original.skills or [])}

    # --- evidence classification per JD-required skill (spec section 46) ---
    evidence: List[EvidenceItem] = []
    bullet_text = " ".join(
        b.lower() for e in original.experience for b in e.bullets
    ) + " " + " ".join(
        b.lower() for p in original.projects for b in p.bullets
    )
    project_text = " ".join(
        t.lower() for p in original.projects for t in (p.technologies or [])
    )
    for skill in (jd.required_skills or [])[:10]:
        sl = skill.lower()
        if sl in original_skills:
            if sl in bullet_text or sl in project_text:
                evidence.append(EvidenceItem(
                    skill=skill, status="STRONG",
                    proof="listed + demonstrated in experience/projects",
                    confidence="HIGH"))
            else:
                evidence.append(EvidenceItem(
                    skill=skill, status="MISSING_EVIDENCE",
                    proof="listed in skills section only",
                    confidence="MEDIUM"))
        elif any(part in bullet_text for part in sl.split() if len(part) > 3):
            evidence.append(EvidenceItem(
                skill=skill, status="PARTIAL",
                proof="related evidence in bullets (transferable)",
                confidence="MEDIUM"))
        else:
            evidence.append(EvidenceItem(
                skill=skill, status="EXPLICITLY_MISSING",
                proof="", confidence="HIGH"))

    strong = [e for e in evidence if e.status == "STRONG"]
    missing_ev = [e for e in evidence if e.status == "MISSING_EVIDENCE"]
    explicit = [e for e in evidence if e.status == "EXPLICITLY_MISSING"]

    # --- signals straight from the simulation trace (measured/heuristic) ---
    positive_signals: List[str] = []
    negative_signals: List[str] = []
    heuristic_factors: List[str] = []
    rec_layer = (hiring.get("layers") or {}).get("recruiter", {})
    for sig in (rec_layer.get("signals") or [])[:5]:
        positive_signals.append(f"[MEASURED_SIGNAL] {sig}")
    for risk in (hiring.get("risks") or [])[:4]:
        negative_signals.append(f"[MEASURED_SIGNAL] {risk}")
    if trace.get("semantic_adjustments"):
        for adj in trace["semantic_adjustments"]:
            heuristic_factors.append(f"[POLICY_RULE] semantic: {adj}")
    if trace.get("score_cap_reason"):
        heuristic_factors.append(f"[POLICY_RULE] cap: {trace['score_cap_reason']}")
    if trace.get("experience_level") == "entry":
        heuristic_factors.append("[POLICY_RULE] entry-level correction applied")
    competitive = (hiring.get("competitive") or {})
    if competitive.get("competitive_level"):
        heuristic_factors.append(
            f"[HEURISTIC] competition model: {competitive.get('competitive_level')} "
            f"({competitive.get('differentiator_count', 0)} differentiators)")

    # --- blocking gaps drive the "why" (decision traceability, section 34) ---
    blocking = [m for m in (ats_report.missing_skills or []) if m.lower() not in original_skills]
    why = decision_reason
    if blocking:
        why += f". Blocking requirements without candidate evidence: {', '.join(blocking[:4])}"
    if not hiring.get("layers", {}).get("hiring_manager", {}).get("pass", True) \
            and "APPLY" in decision:
        why += ". Hiring-manager layer not fully passed (heuristic)."

    # --- recommended next action (policy-derived, no invention) ---
    if "SKIP" in decision:
        action = "Do not apply to this role; target roles matching existing evidence."
    elif "FIX" in decision or "GAPS" in decision:
        if missing_ev:
            action = ("Add demonstrated-usage bullets for: "
                      + ", ".join(e.skill for e in missing_ev[:3]) + ".")
        elif blocking:
            action = "Acquire or evidence the missing requirements before applying."
        else:
            action = "Strengthen existing evidence, then apply."
    else:
        action = "Apply; address listed gaps opportunistically."

    truth = "PASS" if not (getattr(pipeline_result, "validation_result", None)
                           and not pipeline_result.validation_result.get("passed")) else "FAILED"

    return DecisionExplanation(
        decision=decision,
        why=why,
        supporting_strengths=[e.skill for e in strong[:6]],
        blocking_gaps=blocking[:5],
        missing_requirements=list(ats_report.missing_skills or [])[:6],
        evidence_gaps=[e.skill for e in missing_ev[:5]],
        evidence=evidence,
        positive_signals=positive_signals,
        negative_signals=negative_signals,
        heuristic_factors=heuristic_factors,
        fit_estimate=getattr(pipeline_result, "shortlist_probability", None),
        truth_result=truth,
        recommended_next_action=action,
    )
