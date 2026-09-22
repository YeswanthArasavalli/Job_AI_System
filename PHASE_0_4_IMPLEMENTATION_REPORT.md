# Sreejita Hiring Engine

## Phase 0–4 Controlled Implementation Report

Date: 2026-09-22. Executor: AutoCoder (native implementation; zcode_run provider unavailable).
Scope: exactly Phases 0-4 of the approved roadmap. STOP after Phase 4 honored.

### 1. Executive Summary

Implemented: repository truth (git + PII-safe baseline), truthful test
infrastructure (66 dynamically discovered tests, real counts, non-zero exit),
golden evaluation foundation (7 synthetic fixtures, 92 hard-invariant checks,
per-fixture determinism), canonical engine convergence (pipeline.service;
app + dashboard both route through it; parity PROVEN equivalent), and scoring
integrity (no-experience fabricated-evidence fix, semantic raw-vs-adjustment
disclosure, artifact-truth checkpoints for improvement regression, single
shortlist source).

Final state: **66/66 tests pass, exit code 0** (was 24/40 with false-green
exit 0). Golden: 91/92 checks green (the one remaining failure was the
no-experience defect, now fixed; current golden run: all green except none —
see section 11). Both Streamlit UIs boot healthy after changes. Parity probe:
app == dashboard on fixtures A and G (scores, shortlist, decision, hash).

Phase gates: 0 PASS, 1 PASS, 2 PASS, 3 PASS, 4 PASS.

### 2. Baseline Before Changes

- Git: absent (verified `git rev-parse` fatal). Working tree: 91 root files, PII dirs unmanaged.
- Environment: Python 3.14.6 (.venv, 66 pkgs), Ollama 0.34.2, 6 models (llama3.2:3b + qwen2.5-coder:3b configured & responding; details AUDIT_BASELINE_PHASE0.md).
- Tests (old runner): fixed "8/8" per suite, TOTAL 24/40, exit 0 on failure.
  Failures: Intelligence "Score decreased: 66.6 -> 60.7"; Hardening "No-experience resume should score 0, got 2.8"; test_truth.py crashed on cp1252 encoding before its (assert-free) body.
- Main workflow: executed; reported ats_after 76.1 vs independent artifact re-score 68.5 (report/artifact divergence reproduced).
- Known defects: score divergence; no-experience fabricated baselines; opaque semantic floor; multi-site shortlist; false-green runner; encoding crash.

### 3. Phase 0 — Repository Truth

Changes: `git init`; `.gitignore` (data/, logs/, output/, .venv/, _audit_tmp/,
graphify-out/, .code-review-graph/, __pycache__/) BEFORE first commit; PII
scan of 131 tracked candidates (33 hits, all synthetic fixtures — no real PII
committed); baseline commit.
Evidence: commit `05def05` (185 files, 70,590 insertions), tag `phase0-baseline`,
working tree clean. Environment + packaging documented in
AUDIT_BASELINE_PHASE0.md. Version: v6-era per CHANGELOG_v6.md; no package
version existed; none invented (safe-change rule). Baseline workflow executed
(synthetic fixture): ats 75.0->76.1, shortlist 39.5 B+, validation passed,
hash 33f466f1f8447bf1; divergence 76.1-vs-68.5 recorded.

### 4. Phase 1 — Test Infrastructure Truth

Old behavior: 5 hardcoded suites; counts = suite exit code x 8; exit 0 always.
New behavior: tests/run_all.py rewritten — dynamic discovery of test_*
functions AND unittest TestCases (incl. v6_system_tests.py which the old
runner never ran), real per-test results, failure visibility (test name,
assertion, context), category labels (REGRESSION/DETERMINISM/OLLAMA/GOLDEN/
INTEGRATION/DIAGNOSTIC), UTF-8-safe stdout, exit 1 on any failure/error,
--category filter. encoding: stdout reconfigured; rich logging noise isolated
to subprocess suites.
Executed: Discovered 66, Executed 66, Passed 64, Failed 2, Errors 0, Exit 1
(truthful red baseline). Known product failures preserved: improvement
regression + no-experience scoring (both subsequently fixed in Phase 4).
test_truth.py: classified DIAGNOSTIC (no asserts in file — it is a quality-gate
demo script); runs now that stdout is UTF-8; NOT counted as a gate.
test_7_manual_mode_uses_pipeline: assertion updated to the Phase 3 canonical
contract (architecture assertion preserved).

### 5. Phase 2 — Golden Fixture Foundation

Fixtures (tests/golden/fixtures.py, ALL synthetic):
A_strong_aligned, B_weak_misaligned, C_no_experience, D_truth_attack,
E_metric_protection, F_identity_protection, G_improvement_regression.
Hard invariants (tests/golden/run_golden.py): schema validity, signal bounds,
identity (name/email/employers/roles/durations/degrees), no fake employment
conversion, decision contract, trace presence, per-fixture specifics
(alignment floor, gap detection, no-invented-skills, no-fabricated-experience
credit, unsupported-skill claims, metric preservation + no invented numbers,
exact identity preservation), deterministic repeat (pipeline_hash + bullet
equality).
Results: 92 checks total across 2 runs; pre-Phase-4 baseline showed exactly
one failure — no_fabricated_exp_credit (the known defect, captured as a
failing invariant), all others green including determinism on all 7 fixtures.
Checkpoint: phase-1-test-truth (contains Phase 2 files; see section 19 note).

### 6. Phase 3 — Canonical Engine

- pipeline/service.py (NEW): build_jd (shared JD normalization),
  analyze (text/structured -> canonical), analyze_tailored (LLM-tailored base
  honored for the dashboard), package_result (single surface-neutral result
  packaging). Stateless cache resets moved into the service.
- manual_mode.py: pipeline invocation -> analyze_tailored (LLM tailoring depth
  preserved); hand-rolled result dict -> package_result + dashboard UX extras
  (next_actions, PDF, back-compat aliases) with NO recomputation.
- app.py: run_analysis -> service.analyze (display enrichment derived from
  PipelineResult only).
- pipeline/core.py remains THE intelligence engine (unchanged role; service is
  a thin wrapper — per "use existing service" rule).
- Duplicate-path removal: dashboard no longer assembles its own scores/decisions.

### 7. App/Dashboard Parity (executed evidence)

Same resume + JD + configuration + mode (strict), golden fixtures A and G:

```
Fixture A: App:     ATS=83.2  Shortlist=59.7  (canonical service)
           Dashboard: ATS=83.2  Shortlist=59.7  -> EQUIVALENT
Fixture G: App:     ATS=77.9  Shortlist=49.3
           Dashboard: ATS=77.9  Shortlist=49.3  -> EQUIVALENT
```

v6 parity tests (TestAppDashboardParity) green; test_manual_analyzer_uses_same_pipeline green.
Note: the dashboard may STILL show different numbers if the user selects an
LLM tailoring mode in its UI (tailored base differs by design and is now the
documented analyze_tailored contract); with identical inputs the engine is one.

### 8. Phase 4 — Scoring Integrity

- No-experience: _score_skill_demonstration and _score_impact_quality return
  0.0 with no history (was 40.0/30.0 fabricated baselines). Policy: no
  professional experience -> no professional-experience evidence. Executed:
  fixture C total 0.0 (impact 0.0, demo 0.0). Hardening test_2 green.
- Semantic: raw TF-IDF measurement preserved (raw_semantic_score); overlap
  floors kept as policy but recorded as named adjustments
  (semantic_adjustments, e.g. "overlap floor (overlap=10): +9.3") in
  ats_report AND pipeline_trace. Reported = raw + disclosed. No policy removed.
- Improvement regression (artifact truth): two checkpoints in core.py.
  Mandate checkpoint: after ATS-mandate strategies, re-score the artifact; if
  artifact < tailored - 1.0 -> revert to tailored + risk flag
  IMPROVEMENT_REGRESSION_REVERTED. Final reconciliation: before return,
  re-score the artifact once; report describes the artifact; if artifact <
  original - 1.0 -> revert to original + FINAL_ARTIFACT_REGRESSION_REVERTED.
  Executed: Intelligence suite green; fixture G reported == artifact (77.9).
  No `score = max(score, X)` manipulation introduced anywhere.
- Shortlist single source: raw ShortlistPredictor removed from
  scorer.compare(); pipeline.unified_scoring is the only production
  calculation (mirrored to ats_report.shortlist_probability by core for
  backward compat; v6 TestShortlistUnification green: 3/3).
- Mode behavior: untouched product logic; modes verified via existing suites
  (determinism + v6) — strict/balanced/conservative targets remain in
  core.py; config-table refactor deferred (changelog).

### 9. Scoring Evidence (representative, executed)

```
No-experience fixture C:        total=0.0  impact=0.0  demo=0.0          (was 2.8 / 30.0 / 40.0)
Semantic (fixture A):           raw=40.7 -> reported 50.0 with
                                semantic_adjustments=['overlap floor (overlap=10): +9.3']
Improvement regression (G):     artifact 77.9 == reported 77.9; no flags (no regression on this fixture post-fix)
Baseline divergence (pre-fix):  reported 76.1 vs artifact 68.5 -> mechanism eliminated by reconciliation
```

### 10. Tests

```
Discovered: 66   Executed: 66   Passed: 66   Failed: 0   Errors: 0   Exit code: 0
(runner: tests/run_all.py; includes 26 previously-unrun v6 unittest cases,
 golden harness, parity; Ollama suite subprocess-gated, green)
```

### 11. Golden Fixtures

```
Fixture count: 7 (A-G)
Hard invariants: 46 per full pass x 2 (determinism repeat)
Passed: 92/92 in final state
Known issues: none outstanding at Phase 4 gate
```

### 12. Reproduced Existing Defects

FIXED: (1) reported-score/artifact divergence (mandate checkpoint + final
reconciliation). (2) no-experience fabricated baselines (0.0 policy).
(3) false-green runner (truthful runner). (4) opaque semantic floor
(raw+adjustments disclosure). (5) duplicate shortlist calculation (single
source). (6) test_truth.py encoding crash (stdout UTF-8; also classified
assert-free diagnostic). (7) app/dashboard divergence (canonical service;
parity proven).
INTENTIONALLY DEFERRED: mode-gap convergence on strong resumes
(test_integrity.py [6] FAIL remains; behavior is policy-correct per spec §49
— not an artificial-gap problem); main.py CLI migration; LLM gateway
expansion; truth-gate single chokepoint; PII/log hygiene; packaging
(pyproject) — all later roadmap phases.

### 13. Remaining P0/P1 Issues

- Mode-policy config table (P2; modes are code-defined but verified).
- pyproject.toml packaging (P1; install path currently documented manually).
- Dashboard LLM-mode UX: when users tailor via LLM, tailored base differs
  from app path by contract (documented in EXECUTION_PATH.md).

### 14. Known Technical Debt

Rich logging emits cp1252 console noise in redirected runs (cosmetic, tests
unaffected); ~40 root *_report.md files are historical claims (not synced —
docs truth is a later phase); manual_mode retains back-compat aliases.

### 15. Files Changed

```
.gitignore (new)                     tests/golden/fixtures.py (new)
AUDIT_BASELINE_PHASE0.md (new)       tests/golden/run_golden.py (new)
PHASE_0_4_CHANGELOG.md (new)         tests/run_all.py (rewritten)
docs/architecture/EXECUTION_PATH.md  tests/stabilization_test.py (test_7)
pipeline/service.py (new, 254 ln)    utils/models.py (+2 fields)
pipeline/core.py (+66: checkpoints, trace fields)
ats_scoring/scorer.py (fixes 1a/1b/2a-2d/5)
manual_mode.py (canonical routing)   app.py (canonical routing)
_this report
```

### 16. Architectural Decisions

ADR-style records live in docs/architecture/EXECUTION_PATH.md: canonical
engine = pipeline.core (kept); canonical service = pipeline.service; result
contract = PipelineResult + package_result; score ownership = scorer (formula)
+ disclosed adjustments; shortlist ownership = unified_scoring; artifact-truth
policy = revert-with-flag (never score manipulation).

### 17. Regression Verification

After every phase: full truthful suite run. Sequence: 64/66 (baseline red,
truthful) -> 65/66 (runner self-bug fixed) -> 66/66 after Phase 4 fixes ->
66/66 after shortlist consolidation (final, exit 0). Golden: 91/92 -> 92/92.
UI boot checks: app.py + dashboard.py healthy post-change. test_integrity.py:
6/7 unchanged (mode-gap deferred item; not a Phase 0-4 scope defect).

### 18. Phase Gate Results

```
Phase 0: PASS   (baseline 05def05, PII-safe, documented)
Phase 1: PASS   (truthful runner; real counts; exit codes correct)
Phase 2: PASS   (7 fixtures; 92 invariant checks; determinism enforced)
Phase 3: PASS   (one canonical engine; parity EQUIVALENT proven)
Phase 4: PASS   (scoring integrity + single shortlist source; 66/66 green)
STOP: honored — no Phase 5+ work performed.
```

### 19. Git Checkpoints

```
05def05  phase0-baseline (tag: phase0-baseline)
1f47a4e  phase-1-test-truth (tags: phase-1-test-truth, phase-3-canonical-engine,
         phase-4-scoring-integrity — all phase changes were committed after
         their respective gates passed; per-phase intermediate commits were not
         created because verification completed per-phase before the single
         implementation commit. History is append-only; no rewrites.)
```

### 20. Final Verification Evidence

- Truthful suite: Discovered 66 / Executed 66 / Passed 66 / Failed 0 / Errors 0 / Exit 0.
- Golden harness: 92/92 invariant checks (incl. per-fixture determinism).
- Parity probes: fixtures A + G equivalent across app/dashboard paths (incl. pipeline_hash equality).
- UI boot: app.py :8521 health OK; dashboard.py :8522 health OK (post-change).
- Ollama: models verified (config references installed + responding).
- test_integrity.py: 6/7 (mode-gap item = deferred policy, documented).
- Working tree clean at final commit; all artifacts accounted for.

### 21. Recommended Phase 5 Scope (NOT implemented)

Truth-gate centralization into a single chokepoint with a complete change
ledger surfaced in UI; LLM gateway expansion (failure-matrix tests for
timeout/malformed/empty/partial outputs); mode-policy config table;
pyproject packaging + entry points; PII/log hygiene (rotation effective,
scrubbing); main.py CLI migration to the canonical service.