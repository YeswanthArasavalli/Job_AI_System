# TRUTH_GOVERNANCE — Truth Gate & Change Ledger

Status: CURRENT (Phase 5A/5B). This documents the implemented boundary.

## The authoritative Truth Gate

`pipeline/truth_gate.py` is THE single truth-policy boundary for candidate-content
modifications. There is no second truth engine: core.py trust rules, quality_gate
content checks and validation_gate identity checks now delegate to (or remain as
intermediate validators subordinate to) the same policy definitions.

### Responsibilities
- Identity: candidate name/email immutable (IDENTITY_NAME / IDENTITY_EMAIL)
- Employment: employer/role/duration triplets immutable; no experience-entry
  inflation (EMPLOYMENT_FACT_CHANGED / EMPLOYMENT_INFLATION) — blocks
  project->employment conversion by construction
- Education: degree/institution/year immutable (EDUCATION_CHANGED)
- Skills: every skill must be candidate-evidenced — original skill, compound
  expansion, or grounded in the candidate's own experience/project text
  (UNSUPPORTED_SKILL). JD keywords are NOT evidence.
- Metrics: bullet-level boundary `check_metrics(original, rewritten)` — any
  number absent from the original is fabricated (METRIC_FABRICATION)

### Verdict
`validate_candidate_representation() -> TruthVerdict{accepted, violations,
identity_ok, employment_ok, skills_ok, metrics_ok}`

### Call sites (invocation points, one implementation)
- pipeline/core.py PART 8 (primary): verdict drives revert actions
  (identity restore, skills restore, metric-bullet reverts) + ledger records
- pipeline/core.py final reconciliation (artifact truth, unchanged)
- quality_gate / validation_gate: intermediate validators, subordinate policy

## Change Ledger (Phase 5B)

Schema (resume_engine/trust_layer.py ChangeRecord):
{section, type, before, after, reason, rule, confidence,
 evidence_source (ORIGINAL_RESUME | CANDIDATE_EVIDENCE | NOT_APPLICABLE),
 validation (PENDING | PASS | REJECTED)}

Every tracker record is stamped with the Truth Gate verdict at the end of the
run (PASS/REJECTED). Rejected changes carry the violation list as reason.
Coverage: measured on golden fixtures — every accepted bullet change on
fixtures A/E/F/G carries before/after/reason/evidence/validation. UI exposure
is via change_explanation (human-readable, existing app surface).

## Adversarial verification

tests/test_truth_gate.py: 12 executed cases (name/email/employer/title/date/
education mutation, project->employment, unsupported skill, compound expansion,
evidence-grounded skill, metric fabrication, metric preservation). 12/12.