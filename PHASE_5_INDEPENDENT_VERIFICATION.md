# Sreejita Hiring Engine

## Phase 5 Independent Verification

Date: 2026-09-22. Verifier: AutoCoder (independent of the Phase 5 implementer turn).
Mode: STAGE A - VERIFICATION ONLY. Zero repository modifications performed.
Method: every claim re-executed against the repository at c45a90b (master).

### 1. Executive Verdict

**PHASE 5 CERTIFIED - PHASE 6 READY.**

All critical Phase 5 claims were independently reproduced by execution: truthful
suite (73/73, exit 0), golden harness (91/91, exit 0), Truth Gate (12/12),
LLM failure matrix (13/13), integrity (7/7), privacy (PASS), packaging (fresh
venv, v6.0.0, non-CWD import), CLI parity (EQUIVALENT), artifact-score
divergence (eliminated - reported == artifact on fixtures A and G),
UI boot (both healthy). Findings are non-blocking and recorded in section 19.
Entry gate (spec section 22): all 16 items verified.

### 2. Phase 5 Claims Verified

| Claim | Independent result | Verdict |
|---|---|---|
| 73/73 suite, exit 0 | Discovered 73 / Executed 73 / Passed 73 / Failed 0 / Errors 0 / Exit 0 (re-executed) | VERIFIED |
| 91/91 golden | 91 passed / 0 failed, all 7 fixtures OK, exit 0 | VERIFIED |
| 12/12 Truth Gate | exit 0 re-executed | VERIFIED |
| 13/13 LLM matrix | exit 0 re-executed | VERIFIED |
| 7/7 integrity | ALL CHECKS PASS re-executed | VERIFIED |
| CLI parity PASS | test_cli_canonical exit 0 | VERIFIED |
| PII test PASS | re-executed: NONE hits | VERIFIED |
| pip install -e . PASS | fresh venv (TEMP, setuptools bootstrapped): exit 0, version 6.0.0 | VERIFIED (upgraded evidence) |
| import-from-elsewhere PASS | os.chdir outside repo + import pipeline.service OK | VERIFIED |
| App/Dashboard boot | health endpoints OK (ports 8541/8542) | VERIFIED |

### 3. Claims Not Verified

- None material. Two caveats recorded in section 19 (D-1 residual PII in
  secondary INFO logs; D-2 golden-count methodology note).

### 4. Git / Release State

- Branch master @ c45a90b (tree clean). Tags: phase0-baseline,
  phase-1-test-truth, phase-3-canonical-engine, phase-4-scoring-integrity,
  phase4-final-freeze, phase5-trust-governance.
- egg-info: 6 metadata files tracked in index (cosmetic; gitignore now
  excludes future builds; index cleanup requires user-approved op - deferred).
- Version: 6.0.0 (pyproject) - authoritative, consistent with CHANGELOG_v6 era.

### 5. Test Truth

Runner inspected + executed: dynamic discovery (73 rows = 66 per-test + 7
suite rows for script suites); SystemExit codes honored (probe driver proven
in Phase 5); failures propagate to exit 1; categories truthful; Ollama suite
subprocess-gated. No false-green mechanism found (probe-verified earlier,
re-inspected now).

### 6. Golden Evaluation

91 = sum of individual check() assertions across 7 fixtures (13 universal
invariants + fixture-specific + determinism per fixture). Not a suite-row
count; each check is one assertion. Fixtures A-G all OK with per-fixture
determinism (repeat pipeline_hash + bullet equality). Verified by reading
run_golden.py and re-executing.

### 7. Truth Governance

pipeline/truth_gate.py holds the policy definitions (6 violation-type hits,
single definition site). Duplicate scan: core.py hits are verdict consumers
(revert actions), test files are test fixtures - no conflicting policy
definitions. Subordinate validators (quality_gate, validation_gate) remain as
invoked validators. Single-authoritative-boundary requirement: MET.

### 8. Change Ledger

ChangeRecord carries section/type/before/after/reason/rule/confidence/
evidence_source/validation; verdict stamping PASS/REJECTED verified in core.py
wiring and golden evidence (fixtures A/E/F/G all carry metadata).

### 9. LLM Reliability

validate_llm_output (EMPTY -> PARSE -> SCHEMA) inspected; matrix 13/13
re-executed (live dead-port client for unavailable/refused, slow-transport
mock for timeout, content fixtures for parse/schema cases, Truth Gate for
hallucinated skills, canonical service for deterministic fallback).
Malformed/incomplete responses cannot become apparent successes: they fail
closed with stage + error.

### 10. Ollama Environment

ollama 0.34.2 (via `ollama --version`; note: `ollama version` subcommand does
not exist in 0.34.2 - reported as-is). 6 models installed (unchanged set);
configured qwen2.5-coder:3b + default llama3.2:3b both installed; both
responded in Phase 0-4 execution evidence; nomic-embed is embeddings-only.

### 11. Mode Policy

MODE_POLICY.md matches code (core.py:591-603, improver.py:422-488, 1140-1166,
core.py:923/966/1641). Integrity CHECK 6 (behavioral contract) PASS.
No artificial arithmetic separation found in scoring path.

### 12. Packaging

Fresh TEMP venv: python -m venv (bootstrapped from repo venv python - system
python lacks venv module), pip install setuptools wheel (py3.14 no longer
bundles setuptools - recorded), pip install -e . -> exit 0, version 6.0.0,
import-outside-repo OK. Primary dev venv install also previously verified.

### 13. CLI Convergence

main.py: analyze_tailored in source, no direct run_full_pipeline call
(verified by grep + test). Parity (fixture A via service vs CLI path):
scores/shortlist/hash identical (re-executed in Stage A: 83.2/59.7).

### 14. Privacy / Logging

Privacy test re-executed PASS (no name/email/phone/employer/secret in 123
captured log lines; rotation handler 5MB x3 present). Residual finding D-1:
engine.py:112,194 and manual_mode.py:228-229,258 still log candidate name at
INFO (secondary surfaces; main pipeline path is hash-refed). Non-blocking;
scheduled as Phase 6 hardening item.

### 15. Observability

pipeline_trace fields verified in source (core.py:2132-2136) and in golden
execution artifacts: engine, deterministic_engine, version, raw_semantic_score,
semantic_adjustments. Values derive from actual execution (not defaults).

### 16. Historical Bug Verification

- 18.1 artifact-score divergence: independently re-scored returned artifacts -
  A: reported 83.2 == actual 83.2; G: reported 77.9 == actual 77.9. RESOLVED.
- 18.2 no-experience: golden C green incl. no_fabricated_exp_credit (impact 0,
  demo 0 for empty history); hardening test_2 green. RESOLVED.
- 18.3 shortlist writers: canonical writer = core.py:2162 (PipelineResult);
  1964/65/2047 = trace/mirror of canonical; hiring_simulation.py:855 = raw
  internal reference (consumed only as simulation input); test writer =
  test-only. No production duplicate writer. RESOLVED.

### 17. Duplicate Intelligence Map

| Signal | Canonical owner | Other writers | Production? | Risk |
|---|---|---|---|---|
| ATS score | ats_scoring/scorer.py | core.py reconciliation (same formula re-score) | core = final authority | LOW |
| semantic_score | scorer.compare (raw + adjustments) | core mirror in trace | display uses reported field | LOW |
| shortlist/band/decision | pipeline.unified_scoring via core.py:2162 | hiring_sim raw value (reference), ats_report mirror (compat) | display = PipelineResult only | LOW |
| decision (ATS-level) | scorer.compare | unified layer overrides to canonical bands | documented | LOW |
| fit/probability naming | PipelineResult fields | UI labels (app.py display strings) | labels present | MEDIUM (naming still "probability" in places) |

### 18. Product Capability Matrix

| Capability | Implemented | Verified | Quality | Remaining Gap |
|---|---|---|---|---|
| Resume ingestion | YES | YES (executed) | Good | PDF/DOCX fixtures thin |
| JD intelligence | YES | YES | Good | structured company/seniority fields |
| Candidate intelligence | YES | YES | Good | evidence labels not user-facing |
| ATS/alignment | YES | YES | Good | lexical semantics (TF-IDF) |
| Truth Gate | YES | YES (12/12) | Strong | LLM prompt-level defense |
| Safe improvement | YES | YES | Good | fast-path naturalness |
| Artifact truth | YES | YES (A/G ==) | Strong | none |
| Hiring simulation | YES | YES (executed) | Fair | explanation UX (Phase 6 scope) |
| Decision | YES | YES | Fair | structured explanation (Phase 6 scope) |
| Persistence | YES | YES | Adequate | app-path writes (Phase 6E schema work) |
| Outcome tracking | Schema partial | Schema inspected | n/a | outcome model (Phase 6E) |
| Learning | Deferred | N/A | n/a | by design |

### 19. Remaining P0/P1/P2/P3/P4 Issues

- P2 D-1: residual candidate-name INFO logs (engine.py:112,194;
  manual_mode.py:228,229,258) - Phase 6 hygiene item.
- P3 D-2: golden 91 counting is assertion-level (documented); one earlier
  report line said "92/92" during Phase 4 pre-fix state - methodology now
  explicit in run_golden.py.
- P3 D-3: `ollama version` subcommand does not exist (0.34.2 uses
  `ollama --version`).
- P4: egg-info index cleanup pending user-approved op; "probability" naming
  in some UI labels.

### 20. Phase 6 Readiness

Entry gate (spec section 22): 16/16 items verified individually this Stage A.
READY.

### 21. Required Phase 6 Scope

Per spec sections 26-28: 6A simulation transparency; 6B decision explanation
engine; 6C golden expansion (10 archetypes x 12-15 role categories);
6D career-gap/evidence evaluation; 6E outcome-schema readiness; 6F
evaluation/calibration-readiness infrastructure. Learning firewalled.

### 22. Explicitly Deferred Work

All section-28 prohibitions (learning/calibration/scraping/API/queues/SaaS/
multi-provider etc.); egg-info index cleanup; ledger UI depth; prompt-level
injection defense.

### 23. Final Evidence

Executed this Stage A (all exit codes recorded): suite 73/73 (0); golden
91/91 (0); truth gate 12/12 (0); LLM matrix 13/13 (0); integrity 7/7 (0);
privacy (0); divergence probes A/G (match=True x2); fresh-venv install (0);
UI boots (True x2). Git state section 4. No repository modification performed
in Stage A.