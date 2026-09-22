# Sreejita Hiring Engine — v6.0 Changelog & Migration Notes

**Release Date:** May 2026  
**Version:** v6.0 (Architecture Stabilization + Shortlist Unification)  
**Build:** All 27 logic tests passing ✓

---

## What Changed

### PHASE 1 — STABILIZATION (COMPLETE)

#### 1. Shortlist Probability — Single Canonical Source

**Problem:** `shortlist_probability` was computed 7 times across different modules and mutated post-hoc, making it impossible to trace where the final number came from.

**Fix:** One computation, one result, zero mutations.

```
BEFORE (v5.x):
  ShortlistPredictor → compute_shortlist_score() → simulate_hiring()
  → unified_scoring → mutates hiring_sim["shortlist_probability"]
  → mutates ats_report.shortlist_probability
  → UI reads from either source depending on which branch runs

AFTER (v6.0):
  All intermediate engines preserve their own raw values
  ONE canonical block at pipeline end calls compute_final_shortlist_probability()
  Result stored in PipelineResult.shortlist_probability (float)
  PipelineResult.shortlist_band (str)
  PipelineResult.shortlist_decision (str)
  PipelineResult.shortlist_decision_reason (str)
  UI reads ONLY from PipelineResult.shortlist_probability
```

**Files modified:** `pipeline/core.py` (shortlist block at lines 1924+), `app.py`, `dashboard.py`, `manual_mode.py`

#### 2. App.py + Dashboard.py — Unified Execution

**Problem:** `app.py` and `dashboard.py` used different execution paths producing different scores.

**Fix:** Both now read canonical values from `PipelineResult` fields.

- `app.py`: now reads `pipeline_result.shortlist_probability` (not `hiring_sim["shortlist_probability"]`)
- `dashboard.py`: now reads `pipeline_result.shortlist_probability` (not `prob.get("shortlist_probability")`)
- `manual_mode.py`: now exposes `pipeline_result` object and canonical shortlist fields in result dict

**Parity guarantee:** Both UIs call `run_full_pipeline()` → read from same `PipelineResult` → show same values.

#### 3. Database as Source of Truth

**Problem:** `app.py` saved to `job_history.json`. Database was bypassed.

**Fix:** 

New `database/db_manager.py` (v2) extends the schema with:
- `analysis_results` table — replaces `job_history.json` entirely
- `application_events` table — lifecycle tracking (saved → applied → shortlisted → rejected → offer)
- `ingested_jobs` table — for pipeline/ingestion.py screening results
- New columns: `shortlist_probability`, `shortlist_band`, `salary_min/max`, `optimized_resume_json`, `application_status`

`app.py` now calls `save_analysis_to_db()` from `app_db_patch.py` instead of `add_to_history()`.

JSON file preserved as fallback only (if DB write fails).

#### 4. Execution Traceability

**Problem:** No way to trace how a score was computed.

**Fix:** `PipelineResult.pipeline_trace` dict added. Contains:
```python
{
    "job_id", "mode", "pipeline_hash",
    "ats_score_before", "ats_score_after", "ats_improvement",
    "ats_improve_attempts",
    "shortlist_before", "shortlist_after",
    "shortlist_band", "shortlist_decision",
    "recruiter_score_raw",
    "penalties_applied", "risk_flags",
    "missing_skills", "matched_skills_count",
    "score_cap_reason", "role_type", "experience_level"
}
```

#### 5. Score Mutation Chaos — Eliminated

**Before:** `hiring_sim["shortlist_probability"]` was overwritten after being computed. `ats_report.shortlist_probability` was similarly overwritten.

**After:**
- `hiring_sim["shortlist_probability"]` = raw 3-layer simulation value (preserved, not mutated)
- `ats_report.shortlist_probability` = dict version for backward compat (set ONCE at end, has `"unified": True` flag)
- `PipelineResult.shortlist_probability` = THE canonical float shown to users

---

### PHASE 2 — SAFE REFACTORING (COMPLETE)

#### 6. Dead Code — Archived

Moved to `/archive/` (zero functionality lost):
- `pipeline/optimization_engine.py` (590 LOC) — never imported from main flow
- `pipeline/precision_engine.py` (872 LOC) — never imported from main flow
- `pipeline/reality_validation.py` (782 LOC) — never imported from main flow
- `pipeline/career_intelligence.py` (430 LOC) — superseded by hiring_simulation.py
- `pipeline/stability_engine.py` — never imported

**Total dead code removed from active pipeline: ~2,700 lines**

Report clutter archived:
- 9+ `shortlist_engine_report*` files → `/archive/reports/`
- `hardening_report*`, `execution_engine_report*`, `final_validation_report*` → archived

---

### PHASE 4 — INGESTION INFRASTRUCTURE (COMPLETE)

#### 7. Source Adapter Architecture — Built

New file: `pipeline/ingestion.py`

```
SourceAdapter (abstract)
├── ManualAdapter         → wraps paste-JD flow (used by app.py)
├── LinkedInAdapter       → wraps scraper/linkedin_scraper.py
└── GreenhouseAdapter     → public API (template for API-based sources)

SourceRegistry            → register adapters, fetch from any source
IngestionPipeline         → fetch → JD process → ATS screen → DB save
```

To add Naukri, Indeed, Lever, Workday:
```python
class NaukriAdapter(SourceAdapter):
    @property
    def source_name(self): return "naukri"
    def fetch_jobs(self, query, location, max_results): ...

registry.register(NaukriAdapter())
```

---

### PHASE 5 — TEST COVERAGE (COMPLETE)

New test file: `tests/v6_system_tests.py`

Tests covering:
- Shortlist unification (canonical value, no mutation)
- Score determinism (same input → same output)
- ATS realism (realistic ranges, improvement guarantee)
- Trust constraints (no fake skills, name preservation)
- Decision realism (hard rules enforced)
- Pipeline trace presence and completeness
- DB persistence (save, retrieve, lifecycle, analytics)
- App/dashboard parity

**Test results (logic tests, no LLM required): 27/27 passed**

---

## Migration Guide

### Step 1: Apply the updated files

The following files are modified and included in the ZIP:

| File | Change |
|------|--------|
| `pipeline/core.py` | Shortlist unified, PipelineResult extended, trace added |
| `app.py` | Reads canonical shortlist, DB persistence wired |
| `dashboard.py` | Reads canonical shortlist from pipeline_result |
| `manual_mode.py` | Exposes pipeline_result + canonical fields in result dict |
| `database/db_manager.py` | v2 schema with analysis_results, application_events, ingested_jobs |
| `pipeline/ingestion.py` | NEW: SourceAdapter architecture |
| `app_db_patch.py` | NEW: DB persistence helpers for app.py |
| `tests/v6_system_tests.py` | NEW: Comprehensive test suite |

### Step 2: Database migration (automatic)

The new `db_manager.py` auto-migrates on first run:
- Adds new columns to existing `jobs` table (IF NOT EXISTS)
- Creates new tables `analysis_results`, `application_events`, `ingested_jobs`
- Existing data is preserved

No manual SQL required.

### Step 3: Update any code reading shortlist_probability

If you have custom code reading shortlist from hiring_sim or ats_report directly:

```python
# BEFORE (v5.x — unreliable):
shortlist = hiring_sim.get("shortlist_probability")
shortlist = ats_report.shortlist_probability.get("shortlist_probability")

# AFTER (v6.0 — canonical):
shortlist = pipeline_result.shortlist_probability  # float, always set
decision = pipeline_result.shortlist_decision      # str, always set
band = pipeline_result.shortlist_band              # str, always set
```

### Step 4: Register new source adapters (optional)

```python
from pipeline.ingestion import get_registry, LinkedInAdapter

registry = get_registry()
registry.register(LinkedInAdapter(headless=True))

# Now fetch and screen jobs
from pipeline.ingestion import IngestionPipeline
pipeline = IngestionPipeline(registry, db, candidate_resume, scorer)
results = pipeline.ingest("Data Analyst", "Bengaluru", source="linkedin")
```

---

## Remaining Risks

### High Priority

1. **`pipeline/core.py` is still 2,162 lines.** The stage architecture is there as comments and the unified shortlist block is clean, but the optimization loop, naturalization, and content intelligence stages are still inline. Next sprint: extract `stage_optimize()`, `stage_content_intelligence()`, `stage_simulate()` into their own modules.

2. **`resume_engine/improver.py` is 4,975 lines.** Six bullet transformation paths still exist. Consolidation to 2 paths (structural + alignment) is the next major refactor.

3. **`pipeline/__init__.py` imports `PipelineController` which imports `ResumeEngine` which imports `ollama`.** This means importing ANYTHING from `pipeline/` in a test environment without Ollama fails. Fix: add `TYPE_CHECKING` guards or lazy imports in `pipeline/__init__.py`.

### Medium Priority

4. **The `SCORE_CAPPED` hard cap at 40** in `ats_scoring/scorer.py` is too aggressive. A candidate missing 2 of 5 required skills should score 55–65, not 40. Recommend: change to `SCORE_SOFT_CAP` → cap at 55.

5. **`pipeline/controller.py` is a duplicate entry point** that is not used by `app.py` or `dashboard.py`. It should be removed or consolidated with `manual_mode.py`.

6. **`data/job_history.json` is still the fallback** if the DB write fails. The fallback silently fragments history. Consider: fail loudly instead of silently falling back.

### Low Priority

7. **`hiring_simulation.py` is 2,723 lines.** The `simulate_hiring()` function contains the entire 3-layer simulation inline. Extractable as: `_ats_layer()`, `_recruiter_layer()`, `_hiring_manager_layer()`.

8. **The shortlist optimization loop** (`SHORTLIST_MAX_ITERATIONS = 3`) runs the hiring simulation up to 3 times. Each run is expensive. Consider: run once, compute canonical shortlist, never iterate.

---

## Execution Flow (v6.0)

```
User submits (resume + JD)
         │
         ▼
run_full_pipeline()
    │
    ├─ stage 1:  fingerprint + deep copy (deterministic)
    ├─ stage 2:  role classify + resume type detect
    ├─ stage 3:  naturalize (readability pass)
    ├─ stage 4:  multi-pass ATS optimization loop
    │               └─ improver.improve() [up to 3 passes]
    ├─ stage 5:  polish + validate
    ├─ stage 6:  score final (cap + commit)
    ├─ stage 7:  content intelligence (signal, proof, alignment)
    ├─ stage 8:  hiring simulation (ATS→Recruiter→HM layers)
    ├─ stage 9:  bullet rewriter (structural upgrade)
    │
    └─ stage 10: CANONICAL SHORTLIST (ONE computation)
                    └─ compute_final_shortlist_probability()
                            ├─ input: ATS score (from stage 6)
                            ├─ input: recruiter score (from stage 8)
                            ├─ input: JD match ratio
                            ├─ input: bullets (quality analysis)
                            ├─ input: experience level
                            └─ output → PipelineResult.shortlist_probability
                                      → PipelineResult.shortlist_decision
                                      → PipelineResult.shortlist_band
                                      → PipelineResult.pipeline_trace
         │
         ▼
PipelineResult (immutable view)
    │
    ├─ app.py reads: .shortlist_probability, .shortlist_decision, .ats_report
    │                .shortlist_band, .pipeline_trace
    │
    ├─ dashboard.py reads: same fields via ManualAnalyzer → same PipelineResult
    │
    └─ DB save: save_analysis_to_db() → analysis_results table
```

---

## What Was NOT Changed (Preserved)

- ATS scorer logic (`ats_scoring/scorer.py`) — sound, realistic, unchanged
- JD processor (`jd_processor/processor.py`) — fast, rule-based, unchanged
- Trust constraints (`resume_engine/trust_layer.py`) — no fake skills, unchanged
- Hiring simulation 3-layer concept — preserved, only un-mutated
- Quality gate (`pipeline/quality_gate.py`) — preserved
- Recruiter simulation patterns — preserved in `hiring_simulation.py`
- PDF generation — unchanged
- All Streamlit UI layouts — unchanged (only data source fixed)
