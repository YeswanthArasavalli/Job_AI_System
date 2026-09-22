# PHASE_0_4_CHANGELOG — Controlled Implementation (Sreejita Hiring Engine)

All changes verified against phase gates; checkpoints tagged in git.

## SHE-P0-01 | Phase 0 | Repository truth
Files: .gitignore (new), all tracked files (initial commit)
Reason: no VCS existed; baseline freeze required before any change.
Verified problem: git rev-parse failed (documented in prior audit).
Before: no version control, PII dirs unmanaged. After: repo @ 05def05 with
PII/data/logs/cache excluded. Risk: none (additive). Rollback: n/a.
Checkpoint: phase0-baseline.

## SHE-P0-02 | Phase 0 | Baseline evidence capture
Files: AUDIT_BASELINE_PHASE0.md (new), _audit_tmp/phase0_baseline_workflow.py (diag)
Reason: spec section 8 baseline report + runtime workflow evidence.
Result: baseline workflow executed; reported-vs-artifact divergence reproduced (76.1 vs 68.5).

## SHE-P1-01 | Phase 1 | Truthful test runner
Files: tests/run_all.py (rewritten)
Verified problem: fixed "8/8" counts, exit 0 on failures (reproduced).
Before: count = suite exit codes x8; After: dynamic per-test discovery
(66 tests), real counts, failure visibility (name/assert/context), exit 1
on failure, category labels, UTF-8-safe console.
Tests: runner self-evidence (Discovered/Executed/Passed/Failed/Errors + exit code).
Risk: low (test infra only). Rollback: git.
Checkpoint: phase-1-test-truth.

## SHE-P1-02 | Phase 1 | test_7 canonical-contract update
Files: tests/stabilization_test.py (test_7_manual_mode_uses_pipeline)
Reason: assertion referenced the OLD architecture detail (direct
run_full_pipeline call in manual_mode). Phase 3 routes through
pipeline.service.analyze_tailored. Assertion updated to the canonical
contract (service OR direct core call; service must bottom out in
run_full_pipeline) — architecture assertion preserved, not weakened.

## SHE-P2-01 | Phase 2 | Golden evaluation foundation
Files: tests/golden/fixtures.py, tests/golden/run_golden.py (new)
7 synthetic fixtures (A-G), 46 hard-invariant checks x2 runs (92 total,
90 pass + 1 known-defect + determinism), wired into runner as GOLDEN category.
No real PII. Determinism: repeat-run hash equality enforced per fixture.
Checkpoint: phase-2-golden-foundation.

## SHE-P3-01 | Phase 3 | Canonical application service
Files: pipeline/service.py (new: analyze, analyze_tailored, build_jd,
package_result), manual_mode.py (pipeline call -> analyze_tailored;
result dict -> package_result + UX extras; next_actions dedup),
app.py (run_analysis -> analyze)
Verified problem: app vs dashboard divergence (63.7 vs 75.3 executed earlier).
After: parity probe EQUIVALENT on fixtures A and G (83.2/59.7 and 77.9/49.3
identical across both paths incl. pipeline_hash).
Rollback: git checkpoint. Checkpoint: phase-3-canonical-engine.

## SHE-P4-01 | Phase 4 | No-experience scoring integrity
Files: ats_scoring/scorer.py (_score_skill_demonstration, _score_impact_quality)
Verified problem: no-experience resume scored 2.8 (fabricated evidence:
impact baseline 30.0, demo baseline 40.0 with zero history) — reproduced.
Before: baselines returned 30/40 for empty history. After: 0.0 (no evidence
-> no credit; explicit policy comments). No score cap hacks.
Tests: Hardening test_2 green; golden C invariant no_fabricated_exp_credit green.

## SHE-P4-02 | Phase 4 | Semantic score transparency
Files: ats_scoring/scorer.py (raw capture + adjustment ledger + report wiring),
utils/models.py (ATSScoreReport.raw_semantic_score, .semantic_adjustments),
pipeline/core.py (trace fields)
Verified problem: overlap floors silently rewrote the semantic measurement.
Before: reported semantic = post-floor value only. After: raw measurement +
named adjustment list exposed in ats_report and pipeline_trace. Floors kept
as DISCLOSED policy (no removal of business policy; no silent mutation).

## SHE-P4-03 | Phase 4 | Improvement-regression policy (artifact truth)
Files: pipeline/core.py (mandate checkpoint + final reconciliation)
Verified problem: Intelligence 66.6 -> 60.7 (reported score did not describe
returned artifact; strategies could silently regress).
Before: post-selection mutations unverified; report showed mandate score.
After: two artifact-truth checkpoints. If artifact < tailored - 1.0: revert
to tailored (or original at final stage) + explicit risk flag
(IMPROVEMENT_REGRESSION_REVERTED / FINAL_ARTIFACT_REGRESSION_REVERTED);
report always re-scored from the returned artifact. No score manipulation.
Tests: Intelligence suite green (66/66); golden G reported_matches_artifact green.

## SHE-P4-04 | Phase 4 | Single shortlist source
Files: ats_scoring/scorer.py (raw ShortlistPredictor removed from compare())
Verified problem: raw predictor wrote ats_report.shortlist_probability,
competing with pipeline.unified_scoring canonical result.
After: unified_scoring is the only production calculation; ats_report
mirror is written once by core (backward compat preserved per v6 tests);
ShortlistPredictor retained for offline/test analysis only.
Tests: v6 TestShortlistUnification (3 tests) green.

## Deferred (intentionally, later phases)
- Mode-policy config table (modes currently code-defined; behavior verified)
- LLM gateway expansion (client already centralized)
- Truth-gate single chokepoint (trust rules remain in core.py)
- main.py CLI migration