# PHASE_5_CHANGELOG — Trust Governance & Hardening (Sreejita Hiring Engine)

Date: 2026-09-22. Companion to PHASE_5_IMPLEMENTATION_REPORT.md (evidence) and
docs/architecture/TRUTH_GOVERNANCE.md + MODE_POLICY.md + EXECUTION_PATH.md.

## SHE-P5-00 | Phase 4 Closure | Mode-policy test closure
File(s): test_integrity.py, docs/architecture/MODE_POLICY.md (new)
Verified Problem: CHECK 6 asserted an artificial numerical separation
(strict - balanced >= 1.0). Phase-5 spec section 6/49 forbids artificial
gaps; Phase-4 report had deferred the item.
Classification: Outcome B — implementation correct (modes are behavioral
policies: targets/passes/limits), test contract wrong; ambiguity documented.
Before: false failure reported as product defect (strict=69.9 balanced=69.9).
After: CHECK 6 verifies in-bounds results and absence of artificial
separation; policy differences documented in MODE_POLICY.md.
Tests: test_integrity.py 7/7 PASS. Risk: none (test contract correction).
Rollback: git. Checkpoint: phase4-final-freeze (544297a).

## SHE-P5-01 | Phase 5A | Central Truth Gate
File(s): pipeline/truth_gate.py (NEW), pipeline/core.py (trust section delegates)
Verified Problem: trust rules were distributed across core.py trust section,
validation_gate identity checks, and quality_gate content checks with no
single enforcement boundary (spec sections 12-16).
Before: 5+ overlapping mechanisms (identity checked in two places, fake-skill
rules inline, metric rule local to quality_gate).
After: pipeline/truth_gate.py is THE authoritative boundary
(validate_candidate_representation + check_metrics -> TruthVerdict). core.py
PART 8 delegates and executes only the prescribed revert actions (identity
restore, skills restore, fabricated-metric bullet reverts). Intermediate
validators remain subordinate — no second truth engine.
Tests: tests/test_truth_gate.py 12/12 (identity x6, employment inflation,
unsupported skill, compound expansion, evidence-grounded skill, metric
fabrication/preservation). Risk: low (delegation, no behavior change on
golden fixtures). Rollback: git. Checkpoint: phase5-trust-governance.

## SHE-P5-02 | Phase 5B | Change ledger evidence + verdict stamping
File(s): resume_engine/trust_layer.py (ChangeRecord fields), pipeline/core.py
Verified Problem: ledger lacked evidence_source and per-record validation
state; rejected changes were not distinguishable in the ledger.
Before: {section, type, before, after, reason, rule, confidence}.
After: + evidence_source (ORIGINAL_RESUME / CANDIDATE_EVIDENCE /
NOT_APPLICABLE) and validation (PENDING / PASS / REJECTED, stamped from the
Truth Gate verdict); rejected records carry violations as reason.
Tests: golden harness (91/91) + truth-gate suite. Risk: low (backwards-
compatible defaults). Rollback: git.

## SHE-P5-03 | Phase 5C | LLM failure matrix + output boundary
File(s): utils/ollama_client.py (+validate_llm_output), tests/test_llm_failure_matrix.py (NEW)
Verified Problem: failure behavior existed implicitly (timeout thread-join,
retry backoff, single fallback probe in audits) but no executed matrix; raw
LLM output had no schema/content boundary.
After: validate_llm_output enforces EMPTY -> PARSE -> SCHEMA stages
(markdown-fence tolerant, required-fields + extra-fields policy). Executed
matrix: 13/13 scenarios (unavailable, refused, timeout, empty, whitespace,
malformed JSON, non-object, missing field, extra-fields default+strict,
fenced JSON, hallucinated skills -> Truth Gate rejection, deterministic
fallback completes).
Tests: tests/test_llm_failure_matrix.py exit 0 (mock transport + live
deterministic path). Risk: low. Rollback: git.

## SHE-P5-04 | Phase 5D | Mode policy formalization
File(s): docs/architecture/MODE_POLICY.md (NEW)
Verified Problem: mode semantics lived only in code comments.
After: policy table from actual code (targets/passes/limits/summary/polish/
shortlist-loop/conservative-guard), decision implications, explicit
no-artificial-separation statement, truth constraints (mode-independent).
Tests: integrity CHECK 6 + v6 suites. Risk: none. Rollback: git.

## SHE-P5-05 | Phase 5E | Packaging
File(s): pyproject.toml (NEW), main.py (+cli_entry), .gitignore (egg-info)
Verified Problem: no machine-readable version, no install contract, project
import depended on working directory.
After: sreejita-hiring-engine v6.0.0, requires-python >=3.11, deps mirroring
requirements.txt (kept), setuptools packages.find, console script
`sreejita` -> main:cli_entry.
Tests: pip install -e . exit 0; version() == 6.0.0; import-from-elsewhere OK;
entry point registered. Note: first install failed on setuptools strict
schema (inline packages table) — fixed to [tool.setuptools.packages.find].
Risk: low. Rollback: git.

## SHE-P5-06 | Phase 5F | CLI convergence
File(s): main.py (analysis path), tests/test_cli_canonical.py (NEW)
Verified Problem: main.py called run_full_pipeline directly (legacy path,
bypassed the canonical service).
After: CLI -> pipeline.service.analyze_tailored (same engine as app +
dashboard); CLI retains presentation only (PDF/JSON output unchanged).
Tests: tests/test_cli_canonical.py — architecture assertions + parity:
app=83.2/59.7 == cli=83.2/59.7 EQUIVALENT (incl. pipeline_hash). Risk: low.
Rollback: git.

## SHE-P5-07 | Phase 5G | PII / log hygiene
File(s): pipeline/core.py (candidate/JD log refs), tests/test_privacy.py (NEW)
Verified Problem: operational logs emitted candidate name and JD
title/company at INFO (unsafe in shared logs).
After: SHA-256 8-hex refs (candidate_id / job_ref) replace raw fields;
file-handler DEBUG detail preserved for controlled debugging; rotation
verified (5MB x 3, Windows-safe handler).
Tests: tests/test_privacy.py — synthetic Riley fixture through full
pipeline; 123 log lines; name/email/phone/employer/secret hits: NONE;
rotating handler present. Risk: low. Rollback: git.

## SHE-P5-08 | Phase 5H | Governance observability
File(s): pipeline/core.py (trace fields), docs/architecture/EXECUTION_PATH.md
After: pipeline_trace includes engine="pipeline.core",
deterministic_engine=true, version="6.0.0" alongside existing
hash/mode/scores/raw_semantic_score/semantic_adjustments/attempts. No
framework added (spec section 42).
Tests: golden + suite green. Risk: none. Rollback: git.

## SHE-P5-09 | Runner integrity hardening (discovered during Phase 5)
File(s): tests/run_all.py
Verified Problem: script-style suites (no test_* functions) executed during
module import and their sys.exit codes were swallowed by discover() — a
failing script suite could pass silently.
After: SystemExit codes honored as the suite verdict; exit-less script
modules counted as one executed check; verified via injected exit-1 probe
driver (produced a FAIL signal) and a full green run.
Tests: full suite 73/73 exit 0. Risk: none. Rollback: git.

## Intentionally deferred (Phase 6+ or user-approved ops)
- egg-info index cleanup: `git rm -r --cached
  sreejita_hiring_engine.egg-info` requires user-approved elevated op
  (Safety Guard timeout x3); .gitignore already excludes future artifacts.
- Mode-policy config externalization; ledger UI panel; prompt-injection
  red-team framework; docs-truth sweep of ~40 legacy *_report.md files.