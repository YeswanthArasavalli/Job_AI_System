# System Stabilization Report

**8/8 tests passing | 4 files refactored | 1 new module | ~150 lines of duplicate code eliminated**

---

## Architecture: Before vs After

### Before (3 duplicate pipelines):
```
manual_mode.py   → inline naturalize → inline score → inline improve → inline guardrail
controller.py    → inline naturalize → inline score → inline improve → inline guardrail  
main.py          → (no naturalize!) → inline score → inline improve → inline guardrail
```

### After (single source of truth):
```
pipeline/core.py → run_full_pipeline()    ← THE ONLY PIPELINE
    ↑                ↑                ↑
manual_mode.py   controller.py    main.py
```

---

## Part 1-4: Single Source of Truth

### New file: `pipeline/core.py`

```python
def run_full_pipeline(original, tailored, extracted_jd, scorer, job_id) -> PipelineResult:
    # Step 1: Identity validation
    # Step 2: Naturalize
    # Step 3: ATS Score
    # Step 4: Improve
    # Step 5: Score guardrail
    # Step 6: Final identity check
    return PipelineResult(original, tailored, improved, extracted_jd, ats_report, readability)
```

### All entry points refactored:

| File | Before | After |
|------|--------|-------|
| `manual_mode.py` | 67 lines inline | `run_full_pipeline()` (3 lines) |
| `controller.py` | 52 lines inline | `run_full_pipeline()` (3 lines) |
| `main.py` | 39 lines inline (no naturalize!) | `run_full_pipeline()` (3 lines) |

### Bugs fixed by unification:
- `main.py` was **missing naturalization** entirely — now gets it automatically
- Naturalizer field name handling was inconsistent — now unified
- Score guardrail logic was slightly different in each file — now identical

---

## Part 5: Identity + Data Integrity

Built into `run_full_pipeline()`:

```python
# At start:
if tailored.contact.name != original.contact.name:
    tailored.contact = original.contact.model_copy(deep=True)

# At end:
if improved.contact.name != original.contact.name:
    improved.contact = original.contact.model_copy(deep=True)
```

---

## Part 6: Scoring Consistency

- Empty resume → `0.0` (not ~19)
- Keyword stuffing → length-normalized (no false positives)
- Score guardrail → revert if improved score < tailored score

---

## Part 7: Cache Sanity

```
data/cache/*.json → ALL DELETED
```

New sessions will generate fresh caches with the fixed prompts.

---

## Part 8: Dashboard Fix

Dashboard calls `ManualAnalyzer.analyze()` which calls `run_full_pipeline()`.
No direct LLM calls, no sample resume bypass, no alternate paths.

---

## Part 9: Failure Safety

Built into `run_full_pipeline()`:

| Step | Failure behavior |
|------|-----------------|
| Identity validation | Forces original contact (continues) |
| Naturalization | Skips with warning (continues) |
| ATS Scoring | Raises exception (stops pipeline) |
| Improvement | Falls back to tailored (continues) |
| Score guardrail | Reverts to tailored (continues) |

---

## Part 10: Logging

```
PIPELINE CORE — Starting for job manual_analysis
  Resume: Yeswanth Arasavalli
  JD: Senior Data Scientist @ Analytics Corp
  Readability: 91/100
  ATS Score: 19.4 → 47.7 (+28)
  Improvement validated: 47.7 → 48.2
PIPELINE CORE — Complete for manual_analysis
```

---

## Part 11: Tests (8/8 passing)

| # | Test | Status |
|---|------|--------|
| 1 | Single pipeline function exists | ✅ |
| 2 | Identity preserved through pipeline | ✅ |
| 3 | Score never decreases after improvement | ✅ |
| 4 | Empty resume scores 0.0 | ✅ |
| 5 | Deterministic output (within tolerance) | ✅ |
| 6 | No "Arjun Mehta" sample data leakage | ✅ |
| 7 | ManualAnalyzer uses run_full_pipeline | ✅ |
| 8 | PipelineController uses run_full_pipeline | ✅ |

---

## Part 12: Sample Data Leakage

- `data/master_resume.json` still contains "Arjun Mehta" (sample data)
- This is only used when user selects "Use master resume" in the dashboard
- When user **uploads** a PDF/DOCX, their resume is parsed by LLM (fixed earlier)
- `run_full_pipeline()` prevents any identity from changing after input

---

## Files Changed

| File | Change |
|------|--------|
| **NEW** `pipeline/core.py` | Single source of truth pipeline (145 lines) |
| `manual_mode.py` | Replaced 67 lines inline with `run_full_pipeline()` |
| `pipeline/controller.py` | Replaced 52 lines inline with `run_full_pipeline()` |
| `main.py` | Replaced 39 lines inline with `run_full_pipeline()` |
| `data/cache/*.json` | All cleared |
| **NEW** `tests/stabilization_test.py` | 8 comprehensive tests |
