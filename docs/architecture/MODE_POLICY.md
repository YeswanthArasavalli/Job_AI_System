# MODE_POLICY — Strict / Balanced / Conservative

Status: CURRENT (Phase 5D formalization). Source of truth: pipeline/core.py
(mode branch), resume_engine/improver.py (mode branches). This document
describes actual implemented behavior — no aspirational semantics.

## Policy table (from code)

| Aspect | STRICT | BALANCED | CONSERVATIVE |
|---|---|---|---|
| Purpose | Maximum ATS compatibility subject to truth constraints | Meaningful optimization + strong recruiter readability | Minimal semantic change, maximum preservation |
| Optimization target | baseline>=50: 85.0 else 70.0 (core.py:598-603) | 78.0 if baseline>=50 else 65.0 (core.py:594-597) | baseline + 5 (core.py:591-593) |
| Max improvement passes | 3 (4 if weak baseline) | 2 | 1 |
| Bullet length limits | bullet<=200 / suffix<=80 (improver.py:1140,1166) | bullet<=160 / suffix<=60 | same as balanced |
| Summary engine | ALWAYS regenerate (force_summary, core.py:923) | only if weak | only if weak |
| Polish engine | runs when score>=75 (core.py:966) | not run | not run |
| Shortlist enhancement loop | enabled | enabled | disabled (core.py:1641) |
| Grammar/verb-only guard | off | off | ON — grammar+verb fixes only, 95% structure preserved (improver.py:426-488) |
| Truth constraints | identical across modes (Truth Gate is mode-independent) | same | same |

## Decision implications

Shortlist/fit estimation consumes post-optimization signals; mode changes
which artifact is produced, hence indirectly the estimate. The DECISION
contract (APPLY/FIX GAPS/SKIP bands) is mode-independent.

## No artificial separation

Modes differ by optimization policy, NOT by score arithmetic. No mode
multiplier, floor, or cap exists anywhere in the scoring path. A strong
resume may legitimately converge to similar end scores across modes
(observed: strict=69.9, balanced=69.9, conservative=69.8 on the integrity
fixture). Regression contract: tests/test_integrity.py CHECK 6 verifies
in-bounds results and absence of artificial separation — it is NOT a
numerical-gap test (corrected Phase 5, spec §6 Outcome B).

## Truth constraints (mode-independent)

Identity (name/email), employers, titles, dates, education are immutable in
every mode (pipeline/truth_gate.py). Fabricated skills/metrics/employment are
rejected in every mode. Artifact-truth reconciliation applies in every mode.