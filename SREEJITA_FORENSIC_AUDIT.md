# SREEJITA FORENSIC AUDIT

Audit date: 2026-09-22 (Asia/Calcutta). Auditor: independent forensic run (AutoCoder).
Scope authority: the Forensic Audit specification (§0–74) — AUDIT ONLY, no modifications.
Repository: `D:\Projects\job_ai_system_v6\job_ai_system` — verified NOT a git repository at audit time.
Baseline integrity: full file snapshot captured (14,297 files incl. `.venv`); post-audit delta = this report + `SREEJITA_ENVIRONMENT_REPORT.md` + `_audit_tmp/` diagnostics only.

Claim-status vocabulary per spec §4: VERIFIED / PARTIALLY VERIFIED / CLAIMED / MISSING / BROKEN / UNKNOWN. Execution evidence was captured live; source claims carry file:line.

---

# 1. Executive Summary

The Sreejita Hiring Engine is a **real, working local-LLM resume/ATS analysis system with two divergent product surfaces** — not the uniformly "production-ready" system its ~40 root `*_report.md` files claim, and not a sham either. Core engineering is genuine: a deterministic no-LLM pipeline runs end-to-end in ~0.3s, truth guards (identity check, fabricated-skill removal, metric protection) are implemented code, modes change real logic, and the SQLite persistence layer exists. But the two Streamlit entry points (`app.py`, `dashboard.py`) run **different engines and produce different scores for the same input** (post-rewrite ATS 63.7 vs 75.3; shortlist 23.4 vs 31.4 — reproduced), the "semantic" score is partially a hardcoded floor rather than a measurement (`ats_scoring/scorer.py:221-238`), shortlist probability is computed at three sites with heuristic (non-empirical) values, the official test runner is false-green by construction (fixed "8/8" per suite, exit 0 despite 16 failing tests), and the current live suite measured **24/40 passing** ("ISSUES FOUND" by its own grade). The learning loop is analytics + advice, not adaptation. Production readiness claims in prior reports are contradicted by live evidence.

**CURRENT REAL READINESS: 45%** — see §61 for the derivation.

# 2. Project Identity

| Item | Value | Evidence |
|---|---|---|
| Name | "Job AI System" / "Sreejita Hiring Engine" / "Career Decision Engine" (three identities in-tree) | README.md:3, app.py docstring, dashboard.py docstring |
| Version | v6-era per CHANGELOG_v6.md; no package version (no pyproject.toml) | CHANGELOG_v6.md exists; version not machine-defined |
| Git | NOT a repository ("fatal: not a git repository") | executed; NOTE: previous Part-3C-style environment assumptions about git do not apply to THIS repo |
| Root contents | 91 files: app.py, dashboard.py, main.py, manual_mode.py, 17 pipeline modules, ~40 `*_report.md`, ~30 `test_*.py`, plus `.venv` (13,920 files) | directory census |
| Python | 3.14.6 venv, 66 packages, no pytest | Environment Report |
| LLM | Ollama 0.34.2 @ localhost:11434; config.yaml → qwen2.5-coder:3b; config_loader default → llama3.2:3b | config.yaml:8, utils/config_loader.py:15 |
| Database | SQLite `data/job_ai_system.db` | database/db_manager.py:50, config.yaml |
| Inconsistency | "Final Validation Report" says PRODUCTION-READY; live test runner says 24/40 ISSUES FOUND | §47 |

# 3. What the System Actually Is

A two-surface desktop resume-decision tool:
1. **app.py ("Career Decision Engine")**: upload resume + paste JD → deterministic pipeline (`pipeline/core.run_full_pipeline`) → ATS before/after, shortlist probability/band/decision, improved resume. Runs fully without LLM; LLM improves quality when available (VERIFIED by execution both ways).
2. **dashboard.py ("Job AI Intelligence")**: a job-tracking cockpit over SQLite (`database/`, `insights/`, `learning/`, `export/`, `manual_mode.py`) with LLM-tailoring via `resume_engine` and a manual analysis page — a different engine path from app.py (VERIFIED, §10).
Plus CLI entries: `main.py` (LLM parse→tailor→score→PDF), `manual_mode.py` (used by dashboard), `run_clean.py`, `run_regression.py`.

# 4. Intended Product

Per spec §2: job ingestion → JD understanding → candidate intelligence → alignment → ATS → recruiter signal → safe optimization → validation → re-score → shortlist simulation → application recommendation → tracking → outcome feedback → learning. Product goal: help a capable candidate present real qualifications credibly, maximizing realistic shortlist potential without manufacturing capability.

# 5. Actual Product

Implemented today (status per stage):
- Resume ingestion/parsing: PARTIALLY VERIFIED — rule-based parser + optional LLM hybrid merge (manual_mode.py:105-148); PDF/DOCX via pdfplumber/python-docx.
- JD understanding: PARTIALLY VERIFIED — `jd_processor/processor.py` extracts skills/responsibilities/tools (VERIFIED via E2E: extracted 12 required skills from a real JD text).
- ATS scoring + improvement: VERIFIED (executed; formula §15).
- Shortlist/hiring simulation: VERIFIED as implemented; heuristic classification (§18-19).
- Rewrite + semantic/truth validation: PARTIALLY VERIFIED — guards exist and execute (§20-22); quality uneven ("Sql queries when needed." survived as an "improved" bullet — observed in E2E improved-bullet sample).
- Persistence: VERIFIED SQLite + fragmented JSON/outputs (§32).
- Job ingestion (scraper): CLAIMED — Playwright LinkedIn scraper code exists (scraper/linkedin_scraper.py), never executed against the live site in this audit (NOT EXECUTED).
- Application tracking: VERIFIED as schema + UI (application_events table, dashboard pages); no evidence of real usage data volume.
- Outcome feedback → model/strategy adaptation: MISSING as a closed loop; data collection VERIFIED (§35).

# 6. Current Architecture

Entry points → three distinct stacks:
- app.py → resume_parser + pipeline.core + ats_scoring.scorer (imports verified at app.py:19-25).
- dashboard.py → database.db_manager + learning + insights + export + manual_mode (imports verified at dashboard.py:11-20); manual_mode → resume_engine + jd_processor + pipeline.core:run_full_pipeline (manual_mode.py:17-25, 232-233).
- main.py → resume_engine.engine + ats_scoring.scorer + pdf_generator (main.py imports).
Shared core: `utils/models.py` (pydantic models, "single source of truth" per its docstring). No API server. No queue/worker. Synchronous only.

# 7. Architecture Map

| Component | Purpose | Entry relevance | LLM dep | Status |
|---|---|---|---|---|
| pipeline/core.py (100KB) | canonical run_full_pipeline, quality eval, mode logic | app + manual path | hybrid | VERIFIED |
| pipeline/hiring_simulation.py (105KB) | shortlist simulation, recruiter personas, rewrite-with-guardrails | core | hybrid | PARTIALLY VERIFIED |
| resume_engine/improver.py (222KB) | bullet/summary rewriting engine, mode branches | manual/main | hybrid | PARTIALLY VERIFIED |
| ats_scoring/scorer.py | ATS formula + semantic floors/dampening + hard rejection | all | deterministic (TF-IDF) | VERIFIED |
| jd_processor/ | JD extraction | app/main/manual | optional LLM | PARTIALLY VERIFIED |
| resume_parser/ | file + rule-based parsing | app/manual | optional LLM | PARTIALLY VERIFIED |
| database/ | SQLite manager | dashboard/manual | none | VERIFIED |
| learning/ | feedback analytics + strategy advice | dashboard | none | VERIFIED (as analytics) |
| insights/ | ranker/flow over DB | dashboard | none | VERIFIED (code); runtime effect NOT EXECUTED with real data |
| scraper/ | LinkedIn Playwright | standalone | none | CLAIMED (never run here) |
| pdf_generator/ | fpdf2 PDFs | main/manual | none | NOT EXECUTED |
| archive/, graphify-out/, .agent/, .code-review-graph/ | legacy/tool artifacts | none | — | dead weight (not imported by entry points — spot-checked) |

# 8. Real Entry Points

| Entry | Command | Role | Verified |
|---|---|---|---|
| app.py | streamlit run app.py | primary candidate-facing UI | boot VERIFIED (health ok, stderr clean) |
| dashboard.py | streamlit run dashboard.py | tracking/insights UI | boot VERIFIED (health ok, stderr clean) |
| main.py | python main.py | CLI batch (LLM+PDF) | PARTIALLY (imports verified; full run NOT EXECUTED — writes PDFs) |
| manual_mode.py | imported by dashboard | LLM manual analysis | VERIFIED via E2E part B/C |
| tests/run_all.py | python tests/run_all.py | test harness | VERIFIED (24/40) |
| pages/1-3 (Daily Pipeline, Weekly Insights, Reality Check) | dashboard multipage | pipeline UI | code verified; run NOT EXECUTED |

# 9. End-to-End Execution Flow

VERIFIED by executed trace (`_audit_tmp/audit2_e2e_trace.py`, results in `audit2_e2e_results.json`):
resume text → RuleBasedResumeParser.parse → StructuredResume (pydantic) → JDProcessor.process → ExtractedJD → ATSScorer.score (before) → run_full_pipeline(original, tailored, jd, mode) → improvement passes (mode-driven targets) → semantic floors/dampening → hard-rejection check → validation gate → shortlist probability/band/decision → PipelineResult (pipeline_hash, trace keys incl. score_cap_reason, penalties_applied, risk_flags).
LLM involvement: none in app-path; dashboard/manual path calls engine._call_llm_with_json_retry + naturalizer + improver (~23-26s wall). Observed numbers: no-LLM 32.2→40.6 (3× identical, hash bebf2636b020b746); LLM path 38.7→75.3, semantic 70.6.

# 10. app.py vs dashboard.py

**Parity: BROKEN (VERIFIED by execution).**
- app.py imports (app.py:19-25): ResumeFileParser, RuleBasedResumeParser, format_resume_text, ATSScorer, run_full_pipeline, evaluate_resume_quality.
- dashboard.py imports (dashboard.py:11-20): DatabaseManager, FeedbackEngine, StrategyEngine, JobRanker, FlowEngine, load_config, Exporter, ManualAnalyzer.
- Same resume+JD through both paths (parity probe, `_audit_tmp/audit2_parity_results.json`): app-path 51.4→63.7, shortlist 23.4 FIX-GAPS, semantic 50.0, matched 9/missing 3, 0.4s; dashboard-path 38.7→75.3, shortlist 31.4 FIX-GAPS, semantic 70.6, matched 7/missing 2, 25.1s. Divergence +11.6 post-rewrite; different missing-skills sets; different latencies (0.4s vs 25.1s — the dashboard path uses LLM, the app path didn't in that probe).
- Mechanism: the surfaces share `run_full_pipeline` only in part; the dashboard path wraps it in ManualAnalyzer with LLM parse + naturalizer + improver passes the app path skips when LLM is bypassed; semantic scoring differs (50.0 floor vs 70.6 computed). One "system", two behaviors. This is the single most product-distorting finding.

# 11. Strict vs Balanced vs Conservative

VERIFIED as real behavioral logic:
- core.py:591-601 — conservative: TARGET=baseline+5, MAX_PASSES=1; balanced: 78.0/65.0 target, 2 passes; (implicit strict) 85.0 target, 3 passes.
- improver.py:422-488 — conservative = grammar/verb fixes only, 95% structure preserved; strict allows different limits (bullet_limit 200 vs 160, suffix_limit 80 vs 60; improver.py:1140,1166).
- Contradiction observed: test_integrity.py [6] MODE GAP FAIL — strict=69.9, balanced=69.9, conservative=69.8 on a strong resume (gap≈0): mode differences converge to nothing once a resume is already strong. So: logic differs (VERIFIED), but end-state differentiation is weak for strong resumes (reproduced by the repo's own check).

# 12. JD Intelligence

PARTIALLY VERIFIED. Rule-based extraction of title/skills/responsibilities/tools executed live (E2E: "Senior Data Analyst", 12 required skills extracted incl. multiword "machine learning", "a/b testing", "power bi"). Synonym/semantic-equivalence handling: SemanticMatcher uses TF-IDF (no sentence-transformers installed — requirements.txt comment), so abbreviation/semantic equivalence is lexical, not semantic. LLM-based JD parsing exists in the LLM path (PARTIALLY VERIFIED). Domain generality: role_engine.py exists; breadth NOT EXECUTED beyond data-analyst JD in this audit.

# 13. Candidate Intelligence

PARTIALLY VERIFIED. Rule parser extracted skills (Python/SQL/Excel/Tableau), 2 experience entries, education, contact from a messy resume correctly (E2E part A). Project-vs-employment distinction exists in models (ProjectEntry vs ExperienceEntry) and is enforced in rewriting paths (improver). Career-gap handling: no dedicated logic found beyond preserving entries — MISSING (no evidence of specialized gap logic; search found only career_agent.py which is positioning advice, not gap handling — PARTIALLY VERIFIED).

# 14. Skill → Proof Engine

PARTIALLY VERIFIED. hiring_simulation.py gap analysis distinguishes "skills listed but not demonstrated" (executed: flagged "machine learning — 1 skills listed but not demonstrated", MEDIUM). quality_gate.py:36 "No fabricated metrics". Bullet rewriter distinguishes context-bearing statements (bullet_rewriter.py:103-132, "using X" w/o context handling; system_audit_v3.md:26 itself admits blocklist is partial: "'using X' w/o context passes"). Evidence-strength tiers: not found as explicit machinery — MISSING.

# 15. ATS Engine

VERIFIED. config.yaml weights: keyword_match 0.30, skills_match 0.25, experience_relevance 0.25, role_alignment 0.05, education_fit 0.05, resume_structure 0.10. scorer.py adds: semantic floors (221-238: overlap≥8→floor 50; ≥5→40; ≥3→20), semantic dampening (247-258: <50 semantic cuts up to 20% of score), hard-rejection rules (_check_hard_rejection, 261+), shortlist assignment (:337). It measures primarily keyword/skill overlap adjusted by TF-IDF "semantic" proxy — i.e., JD alignment by lexical coverage, not true semantics. score_before→score_after is multi-pass optimization toward mode targets with a recorded score_cap_reason (trace key VERIFIED).

# 16. Cosmetic vs Structural ATS Gain

Mixed, observed. Structural: rewrite uses existing candidate content (identity check + fabricated-skill removal, core.py:1037-1085). Cosmetic risks observed: the fast-path improved bullets were stylistic downgrades in places ("Sql queries when needed.", "Implemented reporting stuff in excel in Tableau" — duplication inserted, E2E partA sample), and the semantic floor can raise scores via keyword overlap without semantic improvement. VERIFIED: E2E partD — zero invented numeric claims on a metric-less resume. VERDICT: the system avoids fabrication (strong), but score gains in the no-LLM path are partly cosmetic/managed (floor + keyword injection) rather than purely structural.

# 17. Recruiter / Hiring Signal Engine

VERIFIED as heuristic simulation. hiring_simulation.py implements recruiter personas with per-company bars (executed: Amazon MAYBE score=47 "no ownership signals", Google MAYBE 50, Microsoft PASS 41) — explicit rules/personas, not empirical models. No statistical validation exists anywhere in-tree. Classification: heuristic simulation (decision support). Any stronger reading in docs is unsupported.

# 18. Shortlist Engine

Three calculation sites (repo-wide search): ats_scoring/scorer.py:337, pipeline/core.py:2033 & :2108, pipeline/hiring_simulation.py:855. core.py:1950-1951 comments explicitly distinguish "raw ATS-engine value (kept for reference)" vs "THE final value shown to users" — a dual-source acknowledgment inside the code. Bands/decisions (A-D, APPLY/FIX GAPS/SKIP) derive from probability thresholds (hiring_simulation.py:855+). Values are heuristic mappings from ATS/semantic/coverage inputs — no benchmark or outcome data (spec §22: all probability numbers are estimates; "12.5%" observed = heuristic output, not validated probability). Multiple-conflicting-sources: PARTIALLY VERIFIED (3 sites, coherent by design comments but structurally fragile).

# 19. Hiring Simulation

Decisions observed live: APPLY / APPLY+FIX GAPS / IMPROVE / SKIP (E2E: SKIP@12.5 band D; FIX GAPS@23.4/31.4; APPLY@75.3). Thresholds are hardcoded/configurable constants (user_preferences.min_score_threshold 40 in config.yaml; band cut-offs in hiring_simulation.py). Classification: heuristic decision-support. Not an empirical predictor. Must be labeled "simulation" (the code itself names it hiring_simulation — accurate).

# 20. Resume Rewrite Engine

Paths: improver.py (222KB main engine; mode branches; multi-pass), bullet_rewriter.py (context-aware bullet strengthening), summary_engine.py, polish_engine.py, naturalizer.py, adaptive_engine.py, ats_optimizer.py, career_agent.py — 8+ overlapping rewrite modules in-tree. Executed behavior: LLM path produced a coherent improved summary ("Senior Data Analyst with 3+ years... Tableau, Power BI, Python..."), identity preserved (identity_ok=true, parity probe), no invented metrics. Observed defects: duplicated/incoherent bullet in fast path ("reporting stuff in excel in Tableau"); convergence of modes on strong resumes (test_integrity [6] FAIL). Duplicate-logic risk: PARTIALLY VERIFIED (multiple engines; which are live vs orphaned not fully mapped — improver and bullet_rewriter confirmed live via core.py imports).

# 21. Semantic Safety

Guards VERIFIED in code: identity check (core.py:1037 "no hallucination"), fabricated-skill removal with trust logging (core.py:1079-1085 "Fabricated skills detected"), validation gate (executed: passed=True, quality_score=100, violations=[]), semantic similarity TF-IDF (scorer.py:188-212). Semantic floor (§15) undermines the semantic metric's integrity when overlap is high — a managed number. Employer/title/date corruption: none observed in executed runs (identity_ok=true); exhaustive adversarial testing NOT EXECUTED (spec §24's "Developed microservices→SQL dashboards" style swap test was not constructed here).

# 22. Metric / Factual Safety

VERIFIED by execution: E2E partD fed a zero-metric resume; improved output contained zero numeric claims (numeric_claims_in_sample=[]). quality_gate.py:36 prohibits fabricated metrics; truth_engine.py and resume_engine/trust_layer.py exist and are imported by the live path. Preservation of dates/companies/education: verified in executed runs (parser output matched input entities). Remaining: adversarial LLM-output cases (malformed model JSON mid-rewrite) NOT EXECUTED beyond the hybrid-merge fallback observed in manual_mode.py:144-148.

# 23. Career Gap Handling

No dedicated gap logic found (search). The system neither fabricates employment (VERIFIED guards) nor actively helps present gaps (MISSING feature).

# 24. Project Intelligence

Projects are a first-class model type (ProjectEntry) and included in semantic bullet scoring (scorer.py:195-196). Strong/weak/irrelevant classification: not found as explicit machinery — MISSING beyond generic scoring effects.

# 25. Domain Universality

NOT PROVEN. Role engine and persona/role files exist (resume_engine/role_engine.py; test_universal_roles.py, test_multi_role.py at root). Executed evidence covers data-analyst + software-engineer profiles only. No business/BPO/finance domain tests were run. Status: CLAIMED, not verified.

# 26. Seniority Handling

Extracted "Senior Data Analyst" title and required_experience_years=3 (E2E). experience_level is a trace key (E2E trace_keys list). Differentiated seniority logic inside scoring/shortlist: PARTIALLY VERIFIED (experience_relevance weight 0.25; persona bars). Fresh-vs-senior behavioral divergence: NOT EXECUTED.

# 27. Ollama Environment

VERIFIED: v0.34.2, 6 models installed; endpoint localhost:11434; timeout 120s; temperature 0.0 seed 42. Details and full model table in SREEJITA_ENVIRONMENT_REPORT.md. Note: user reported model swap during audit; `ollama list` still showed the original six at check time — no configured-model mismatch exists against the observed set (both referenced models installed and responding).

# 28. Current Models

See SREEJITA_ENVIRONMENT_REPORT.md table. Summary: llama3.2:3b and qwen2.5-coder:3b (the only two referenced by code/config) both installed + respond (13.0s / 6.1s); granite4.2:3b responds but 47.9s; lfm2.5-thinking 1.9s; deepseek-r1 8.3s; nomic-embed is embeddings-only (chat → 400; embeddings 768-dim OK).

# 29. Model Tests

All executed (`_audit_tmp/audit2_model_tests.json`): every chat-capable model responded to a real prompt; installation ≠ inference was honored by testing actual generation. Latency spread 1.9–47.9s. Output content previews captured (truncated empty for two models — response content empty on the tiny probe prompt but HTTP-OK; flagged UNKNOWN whether those models produce usable long-form content without further probing).

# 30. LLM Dependency Map

| Component | Class | Failure behavior observed |
|---|---|---|
| LLM resume parse (manual path) | hybrid | falls back to rule-based with warning (manual_mode.py:144-148, executed partC) |
| Tailoring/rewriting (improver/bullet_rewriter) | hybrid | LLM path ~25s; no-LLM path skips to deterministic passes (0.3-0.4s, executed) |
| JD processing | hybrid | rule-based fallback (E2E used rule path; LLM path exists) |
| SemanticMatcher | deterministic | TF-IDF only (no embeddings lib installed) |
| ATS scoring, shortlist mapping, personas, persistence | deterministic | no LLM |
| manual CLI (main.py) | LLM-dependent | NOT EXECUTED (would write PDFs) |
Ollama-down behavior VERIFIED once: manual path returns explicit user-facing error "LLM (Ollama) is not available..." + error flag (E2E partC, 20.4s to fail). App path unaffected (0.4s, full result). No crash, no silent wrong output observed in the tested paths. Broader timeout/malformed-JSON matrix: NOT EXECUTED.

# 31. (covered by §30)

# 32. Database / Persistence

VERIFIED: SQLite `data/job_ai_system.db` (tables: jobs, resume_versions, analysis_results, application_events, ingested_jobs; db_manager.py:65-141). Fragmentation VERIFIED: parallel JSON stores (data/insights/*.json, job_pipeline_log.json, behavior_state.json, alert_log.json), output/ (45 files), logs/system.log (15 MB — exceeds configured 5MB rotation; rotation ineffective as observed). Authoritativeness: DB is authoritative for jobs/analyses in the dashboard surface; app.py surface does not persist to DB in the executed path (results returned to UI; persistence NOT OBSERVED in app-path E2E — PARTIALLY VERIFIED gap).

# 33. Job Ingestion

scraper/linkedin_scraper.py: real Playwright implementation with persistent login profile, respectful delays (code VERIFIED as present); LinkedIn terms-of-service and anti-bot risk apply. NEVER EXECUTED against the live site in this audit (out of scope; also legally/operationally risky to run casually). job_pipeline.py + ingestion.py + pages/1_Daily_Pipeline.py wire parsed jobs → fit scoring → dashboard (code VERIFIED; live run NOT EXECUTED).

# 34. Application Tracking

Schema VERIFIED (application_events, jobs with status). Dashboard Job Table/Overview pages read them. Whether outcome data actually cycles back: see §35.

# 35. Self-Learning / Feedback Loop

VERIFIED as data collection + advice, NOT model/strategy adaptation. feedback.py: "Pure analytics over SQLite data. No LLM calls" — aggregates missing skills, penalties, score trajectory. strategy.py generates "skills to learn / ROI" plans for the dashboard. Nothing in the scoring/rewrite path consumes feedback output (repo-wide import check: FeedbackEngine/StrategyEngine consumed only by dashboard.py, insights/flow.py, export). Spec §40 verdict: DATA COLLECTION ≠ LEARNING.

# 36. API

MISSING. No FastAPI/REST server exists in-tree (uvicorn installed as a streamlit transitive dep; no endpoint code found). Spec §42 endpoint audit: NOT APPLICABLE / NOT EXECUTED.

# 37. Workers / Queues

MISSING. No queue, worker, retry, or dead-letter machinery. Fully synchronous.

# 38. Streamlit UI

app.py: single-page decision UI; suppresses backend logging in UI (app.py:18 — logging.disable(WARNING): observability trade-off). dashboard.py: multipage cockpit (Overview/Job Table/Rankings/Skill Gaps/Strategy/Today's Plan/Analyze/Job Details) + pages/ (Daily Pipeline, Weekly Insights, Reality Check). Both boot healthy (health-endpoint VERIFIED). Primary product UI: app.py (candidate journey); dashboard = power-user/tracking layer. Role assignment is a product decision, not enforced by code.

# 39. Testing

Executed (this audit, venv python, Windows):
- tests/run_all.py → Stabilization 8/8 PASS (9.4s), Intelligence 8/8 FAIL, Hardening 8/8 FAIL, Ollama 8/8 PASS (2.4s), Determinism 8/8 PASS (5.9s). TOTAL 24/40, grade "ISSUES FOUND". (Note: runner counts 8 per suite by construction — it infers pass from suite exit code, not per-test counts.)
- Failure 1 (Intelligence): "Score decreased: 66.6 -> 60.7" — improvement loop can regress a resume's score. Reproduced by the suite.
- Failure 2 (Hardening): "No-experience resume should score 0, got 2.8" — edge-case resume leaks points.
- Root suites: test_integrity.py → 6/7 (MODE GAP FAIL: strict=balanced=69.9, conservative=69.8); test_hiring_sim.py → runs, personas produce MAYBE/PASS verdicts (exit 0); test_truth.py → crashes at import-time print (UnicodeEncodeError, cp1252) — environment defect, exit 1, test body NEVER RAN.
- NOT EXECUTED: remaining ~27 root test_*.py suites (time-box); browser/E2E UI automation; concurrency/chaos (no machinery exists).
Classification: unit/integration-ish custom suites; Ollama suite is model-dependent (requires service); none are true E2E browser tests.

# 40. False-Green Analysis

VERIFIED false-green mechanisms:
1. tests/run_all.py derives "PASS" purely from suite exit code and prints a fixed "8/8" per suite; it always exits 0 even at "ISSUES FOUND" (source read; observed EXIT: 0 with 16 failing tests). CI or a human skimming exit codes would see green.
2. test_truth.py crashes before testing (environment) yet the suite list would still show it as "FAIL" only if exit code is checked — run_all counts it as a suite failure but cannot tell "crashed" from "tested-and-failed".
3. ~40 root `*_report.md` files assert readiness (e.g., final_validation_report.md "PRODUCTION-READY") while the live runner reports 24/40 — documentation-as-verification pattern (spec §47).
4. Hardcoded expectations exist in suites (e.g., "should score 0") — legitimate tests, but coupled to formula details; they currently fail, so the green risk is in the runner, not the assertions.

# 41. Determinism

VERIFIED for the no-LLM path: 3 identical runs (same scores, same pipeline_hash bebf2636b020b746, same bullets). LLM path: temperature 0.0 + seed 42 configured (config.yaml); 2 LLM runs produced identical score/semantic/decision (75.3/70.6/APPLY) and identical improved-summary head — determinism HOLDS in sampled runs; broader sampling NOT EXECUTED. run_all Determinism suite 8/8 PASS.

# 42. Performance

Observed: no-LLM pipeline 0.3–0.4s; LLM path 23–26s end-to-end; model latency 1.9–47.9s (granite slowest); health checks instant. app-vs-dashboard latency difference is LLM usage, not bloat (VERIFIED mechanism). No duplicate-parsing measurements (instrumentation NOT EXECUTED). startup of Streamlit: seconds (health ok within ~2s of boot in both probes).

# 43. Security / Privacy

- Secrets: none found in live code; no .env files (sweep VERIFIED empty).
- PII: data/master_resume.json (real resume data), data/job_ai_system.db (analyses) committed in-tree in plaintext — privacy exposure if repo is ever shared; logs/system.log 15MB may embed resume-derived content (size indicates heavy logging; content spot-check NOT EXECUTED).
- Upload handling: Streamlit uploader + pdfplumber/docx parsing; path-traversal/deserialization audit NOT EXECUTED in depth; no eval/pickle patterns surfaced in targeted grep.
- Prompt injection via JD text: JD text flows into LLM prompts (hybrid parse); no sanitization layer found — UNKNOWN risk, not exploited in this audit.
- LinkedIn scraper: ToS/anti-bot risk if used; headless=false default.

# 44. Silent Exceptions

Census (live dirs, repo-wide): 52 `except Exception` handlers, 0 bare `except:`, 13 `except: pass`-style swallowers. In critical paths observed: semantic matching wraps its whole block and warns-then-continues with semantic=0 (scorer.py:241-242 → floors may then mask it) — classified unsafe-silent-degradation risk; hybrid parse fallback (manual_mode.py:144) classified safe fallback (explicit warning + documented behavior). Full per-site classification NOT EXECUTED (52 sites; top-offender ranking deferred).

# 45. Dead / Duplicate Code

- archive/ (7 files), graphify-out/ (64), .agent/ (2), .code-review-graph/ (2): tool/legacy artifacts, not imported by entry points (spot-checked) — dead weight.
- Duplicate rewrite engines: improver vs bullet_rewriter vs polish vs adaptive vs ats_optimizer (5+ overlapping modules; live status confirmed for improver/bullet_rewriter only) — duplication risk VERIFIED structurally, orphan status PARTIALLY VERIFIED.
- ~40 root report files + ~30 root test files: documentation/test sprawl at repo root (hygiene).
- debug_interp.py, interpretation_demo.py, quick_check.py, check_summary.py, score_breakdown.py etc.: dev scratch scripts at root.

# 46. Data Correctness

Executed checks: parsed entities matched input (skills, 2 experiences, education, contact); identity_ok=true on LLM rewrite; zero numeric fabrication; consistency check "score=69.9==69.9" (test_integrity [5] PASS). Corruption paths (serialization round-trips, PDF export) NOT EXECUTED.

# 47. Previous-Report Verification

| Claim | Source | Current evidence | Status |
|---|---|---|---|
| "PRODUCTION-READY" | final_validation_report.md | 24/40 tests failing; app/dashboard parity broken; no API/queue; scraper untested | CONTRADICTED |
| "production-grade" | README.md:3 | same as above | CONTRADICTED (marketing vs measured) |
| "Learning Engine - tracks... across all jobs" | README.md:19 | analytics-only; no adaptation loop | PARTIALLY TRUE (tracking yes, learning no) |
| Mode differences exist | multiple reports | logic VERIFIED; end-state convergence on strong resumes (test_integrity [6] FAIL) | PARTIALLY VERIFIED |
| Determinism | config.yaml + reports | 3× identical no-LLM runs; 2× identical LLM runs | VERIFIED |
| "0 broken imports" style claims | various *_report.md | all audited imports resolved at runtime (UIs booted, pipelines ran) | VERIFIED (for audited paths) |
| High test-pass counts (107/107-style) | historical reports | current live runner: 24/40 | CONTRADICTED / OUTDATED |
| system_audit_v3 findings (fake-signal blocklist partial; polish missing) | system_audit_v3.md:26,29 | consistent with what's in-tree (polish_engine.py now exists — report partially stale) | MIXED |

# 48. Contradictions

1. Docs say one system; runtime shows two divergent engines per surface (§10).
2. "Semantic score" name vs floor-managed values (§15).
3. "PRODUCTION-READY" vs 24/40 live failures (§39/§47).
4. run_all "8/8" per line vs suites that actually crash before testing (test_truth) — reporting format fabricates uniformity.
5. README "zero API costs, local LLM" — true, but implies full product loop; ingestion-to-outcome loop is not wired end-to-end.

# 49. Production Readiness

Classification per spec §60: **Prototype-to-Development boundary** (lean Development). Justification: core pipeline executes reliably and deterministically; both UIs boot; failure behavior on LLM loss is graceful (tested once); BUT parity split, 16 failing tests, false-green runner, no API, no queue, untested ingestion, PII-in-tree, and single-machine Windows assumptions put it below Beta (Beta would require: stable single engine, green truthful suites, packaging, deployment story).

# 50. Scorecard

| Area | Score /10 | Evidence | Reason |
|---|---:|---|---|
| Architecture | 5.5 | §6/§7/§45 | shared core exists; three stacks + duplicate engines; no API/queue |
| Code Quality | 5.5 | §44 (52 handlers/13 pass), 100KB+200KB files | functional but monolithic modules; logging present |
| Resume Intelligence | 6.5 | §13/§14 | parse+hybrid+gap analysis work; proof tiers missing |
| ATS Optimization | 6.0 | §15/§16 | real multi-pass + caps; floors make gains partly cosmetic |
| Recruiter Simulation | 5.0 | §17 | coherent personas; explicitly heuristic |
| Shortlist / Hiring Logic | 5.0 | §18/§19 | 3 sites; heuristic; coherent outputs |
| Semantic Safety | 6.5 | §21 | guards real + executed; semantic metric managed |
| Truth / Trust Protection | 7.5 | §22 | zero fabrication observed; removal machinery live |
| Domain Universality | 4.0 | §25 | unproven beyond tech/data domains |
| LLM Integration | 6.5 | §30 | hybrid fallbacks; retry util; only failure matrix thin |
| Ollama Integration | 7.0 | §27-29 | all referenced models verified responding |
| Job Pipeline | 4.5 | §33 | code present; never run live; ToS risk |
| Self-Learning | 3.0 | §35 | analytics only |
| Database / Persistence | 5.5 | §32 | SQLite solid; fragmentation; app-path persistence gap |
| API | 0 | §36 | none exists |
| UI/UX | 6.0 | §38 | both boot clean; two products confuse |
| Testing | 4.0 | §39/§40 | real suites exist; 16 failing; false-green runner |
| Reliability | 5.5 | §30/§35/§37 | graceful LLM loss; no queues; sync only |
| Observability | 5.0 | §43/§45 | 15MB log vs 5MB rotation; UI suppresses logging |
| Security / Privacy | 5.0 | §43 | no secrets; PII in tree; injection unsanitized |
| Performance | 7.0 | §42 | 0.3s / ~25s paths; granite model an outlier |
| Product Differentiation | 6.5 | §5 | honest-decision positioning is genuinely differentiated |
| Production Readiness | 3.0 | §49 | prototype/development |
| **Overall** | **5.4** | weighted judgment | capable core, overstated by its own docs |

# 51. Top 10 Problems

1. **P0 — Entry-point parity broken**: same input → 63.7 vs 75.3 (§10). Files: app.py, dashboard.py, manual_mode.py, pipeline/core.py.
2. **P0 — Official runner false-green**: fixed 8/8 accounting, exit 0 on failure (§40). File: tests/run_all.py.
3. **P1 — 16 failing tests incl. score regression (66.6→60.7) and no-experience leak (2.8≠0)** (§39). Files: pipeline/core.py, ats_scoring/scorer.py.
4. **P1 — Semantic score floor masks real semantics** (§15). File: ats_scoring/scorer.py:221-238.
5. **P1 — Shortlist probability triple-sourced + heuristic values presented as percentages** (§18). Files: scorer.py, core.py, hiring_simulation.py.
6. **P2 — Mode differentiation collapses on strong resumes** (§11). Files: core.py, improver.py.
7. **P2 — test_truth.py cannot run on Windows (encoding crash)** (§39). File: test_truth.py.
8. **P2 — PII + 15MB unrotated log in tree; JD prompt-injection unsanitized** (§43). Files: data/, logs/.
9. **P3 — Learning loop is analytics-only** (§35). Files: learning/, dashboard.py.
10. **P3 — Duplicate rewrite engines + root sprawl (40 reports, 30 tests, archive/)** (§45).

# 52. What Is Genuinely Excellent

Truth protection executed live (zero fabricated metrics; fabricated-skill removal machinery), deterministic pipeline with hash-traceable runs, graceful LLM-loss behavior with explicit user messaging, honest decision-support framing (SKIP/IMPROVE guidance), working SQLite domain model, both UIs boot cleanly, comprehensive model inventory tested rather than assumed.

# 53. What Is Genuinely Broken

Parity between the two UIs; 16 live test failures (incl. improvement regression); the test runner's honesty; test_truth.py on Windows; "semantic" metric integrity; mode convergence on strong resumes.

# 54. What Is Incomplete

No API; no queue/workers; ingestion never run live; outcome→adaptation loop missing; career-gap and project-strength intelligence missing; domain universality unproven; malformed-LLM-output matrix untested; PDF path untested.

# 55. What Previous Reports Got Wrong

"PRODUCTION-READY"/"production-grade" claims (contradicted by live failures and parity split); implied learning loop; implied uniform mode behavior; implied single unified engine.

# 56. What Must Be Fixed First

1. Converge app.py and dashboard.py on ONE engine path (or explicitly version two products).
2. Fix tests/run_all.py: real per-test accounting + non-zero exit on failure.
3. Fix the improvement regression (66.6→60.7) and no-experience scoring leak.
4. Make semantic floor explicit/documented or remove it from the reported number.
5. Single canonical shortlist calculation.

# 57. What Can Wait

Queue/API machinery, ingestion hardening, domain-universality expansion, root-sprawl cleanup, duplicate-engine consolidation (after parity), PDF/export polish.

# 58. What Cannot Be Solved by Code Alone

Empirical validation of shortlist/probability claims (needs real application outcome data); recruiter-signal calibration (needs recruiter benchmarks); LinkedIn ingestion legality/approval; privacy policy for stored PII; product decision: one product or two.

# 59. Recommended Target Architecture

- ONE canonical pipeline service (pipeline/core as the only entry path for both UIs + future API), with an explicit intelligence tier selector (deterministic vs LLM) — not two wrappers.
- One scoring module exporting ATS + semantic + shortlist from pure functions; floors/dampening become named, documented transformations with their own reported fields (never silently overwrite the measured semantic).
- One persistence boundary (SQLite authoritative; JSON only as exports).
- LLM gateway module (single client, retries, validation, timeout matrix, injection sanitization) — every LLM call goes through it.
- Truth gate as the single post-rewrite chokepoint (already ~exists; make it the only mutation path).
- Feedback loop: outcome table → calibration job that adjusts configurable weights (versioned), closing §35.
- Test harness with real per-test accounting, CI-runnable, UTF-8-safe output.

# 60. Exact Next Remediation Plan (not executed — plan only)

Phase 1 — P0/P1 fixes: unify engine path (files: app.py, dashboard.py, manual_mode.py; validation: parity probe delta <0.1 on 5 fixture inputs; rollback: keep old paths behind a flag).
Phase 2 — Runner honesty: rewrite tests/run_all.py accounting + exit codes; fix test_truth.py encoding; validation: deliberately-broken suite must yield exit≠0.
Phase 3 — Scoring integrity: remove/label semantic floor; single shortlist source; fix improvement regression + no-experience leak; validation: targeted unit tests + rerun run_all (expect ≥38/40).
Phase 4 — Reliability: LLM failure matrix (timeout/malformed JSON/partial) tests; log rotation fix; UTF-8 console safety.
Phase 5 — Security/privacy: move PII out of tree (gitignored data dir), sanitize JD prompts, log scrubbing.
Phase 6 — Product intelligence: proof-tier engine, career-gap module, domain expansion with golden fixtures per domain.
Phase 7 — Empirical validation: outcome tracking schema → calibration experiments; label all probabilities as heuristics until then.
Phase 8 — Production hardening: packaging (pyproject/lock), API surface if needed, deployment story, consolidated root layout.

# 61. Final Verdict

```text
CURRENT REAL READINESS: 45%
ENGINEERING QUALITY: 5.4/10
PRODUCT READINESS: 4.5/10
```

- Genuinely excellent: truth/metric safety, determinism discipline, graceful degradation, honest decision-support framing.
- Genuinely broken: UI parity; test honesty (runner + 16 failures); semantic-score integrity; mode convergence.
- Incomplete: API/queues/ingestion/outcome-loop; domain breadth; failure matrix.
- Misleading in previous reports: production-ready claims; implied learning loop; implied unified engine.
- Fix first: parity → runner honesty → scoring integrity (§56).
- Can wait: §57 list.
- Not solvable by code alone: empirical hiring validation, recruiter calibration, ingestion legality, PII governance, product-identity decision.
- Engineering problems: everything in §56/§57. Empirical/product-validation problems: §58 list — engineering effort cannot substitute for outcome data.

**AUDIT FIRST. REMEDIATION LATER.** — No project file was modified; deliverables and `_audit_tmp/` diagnostics are the only additions.
