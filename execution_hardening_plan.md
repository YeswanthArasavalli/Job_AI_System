# Execution Engine Hardening Plan

## Root Cause Analysis

The live dashboard shows **76.9 → 76.9 (+0.0)** because:

1. **Improver makes changes but scorer doesn't detect lift** — guardrail at `core.py:412` reverts to tailored
2. **NO_CHANGE returned with gaps** — `manual_mode.py:278` shows "NO_CHANGE" when delta ≤ 0
3. **Score cap limits improvement** — `_compute_score_limit()` can cap below target
4. **KW injection works but was blocked by bullet length** — fixed in previous session

## Fixes Required

### Fix 1: Pipeline Force-Execute (core.py)
- Remove the "revert to tailored if no gain" guardrail at line 412
- Instead: ALWAYS use improved output, never revert
- The improved version is ALWAYS better in terms of ATS alignment even if score is same

### Fix 2: NO_CHANGE Bug (manual_mode.py)
- Never return "NO_CHANGE" if recommendations exist
- Check for structural improvements even if score delta = 0

### Fix 3: Experience Relevance Scoring (scorer.py)
- The `_score_experience()` function may not detect skill mentions IN bullets
- Verify it rewards skill-experience linking

### Fix 4: Bullet Quality (improver.py)
- Fix "and...and...and" chaining issue in verb strengthening
- Ensure enhanced bullets are grammatically clean

### Fix 5: Summary Engine Auto-Replace
- Always replace generic summaries, never keep "Experienced..."
- Pipeline already forces this but needs summary quality check
