# Sreejita Hiring Engine

## Independent Goal Cross-Check, Architecture Review & Final Completion Roadmap

Date: 2026-09-22 (Asia/Calcutta). Mode: AUDIT + ARCHITECTURE + ROADMAP ONLY — no repository modification performed in this phase.
Inputs: current repository `D:\Projects\job_ai_system_v6\job_ai_system`, the prior forensic audit (`SREEJITA_FORENSIC_AUDIT.md`), the intended product goal (this phase's specification), and the live runtime (re-verified today).
Evidence discipline: every verdict below cites file:line or an executed command. Previous findings were re-verified, not inherited. Two prior-audit conclusions were **contradicted** during cross-check and are corrected in §5.

---

### 1. Executive Product Verdict

- **What Sreejita actually is today:** a local-first, Ollama-powered resume/ATS decision-support tool with two divergent Streamlit surfaces (a candidate decision UI and a job-tracking dashboard), a deterministic core pipeline, real truth-protection machinery, and SQLite persistence. It reliably produces ATS before/after scores, gap lists, improved resumes (in LLM mode), shortlist-band estimates, and APPLY/FIX-GAPS/SKIP guidance.
- **What it successfully does:** end-to-end analysis in ~0.3s deterministic mode and ~25s LLM mode (both executed); deterministic output (hash-identical runs); zero metric fabrication observed on adversarial input; graceful Ollama-loss behavior; mode logic that genuinely differs; persistent job/analysis storage.
- **What it does not yet do:** present one consistent answer from both UIs (reproduced divergence: ATS-after 63.7 vs 75.3); produce honest test results (24/40, runner exits 0 on failure); measure semantics without managed floors (`scorer.py:223`); compute shortlist from one canonical source; learn from outcomes; extract structured JD fields like company/location/seniority; run ingestion.
- **Previous forensic findings:** still valid overall (re-verified today: 24/40, floor, multi-site shortlist, analytics-only learning, no git). **Two findings corrected** — career-gap detection and proof-strength scoring exist (§5).
- **Biggest current risks:** (1) two-engine divergence silently undermines user trust; (2) false-green runner lets regressions ship; (3) score-improvement can regress (66.6→60.7) and validation does not block it; (4) PII in-tree with an unrotated 15 MB log; (5) probability-like numbers presented without heuristic labeling.
- **Current maturity level:** Level 1 (Core Functional Completion) **partial**, Level 2–5 not started (§47 levels of the spec). Not production-ready; not beta-ready until P0/P1 gates pass.

### 2. What Sreejita Actually Is Today

Three entry stacks over shared pydantic models:
- `app.py` (candidate decision UI) → `resume_parser` + `pipeline/core.run_full_pipeline` + `ats_scoring.scorer` (app.py:19-25). No-LLM-capable; LLM improves quality when present.
- `dashboard.py` (job intelligence cockpit) → `database` + `learning` + `insights` + `export` + `manual_mode` (dashboard.py:11-20); manual path adds LLM parse/tailor (`manual_mode.py:105-148, 232-233`).
- `main.py` (CLI: LLM parse → tailor → score → PDF; not executed in audit — writes artifacts).
Persistence: SQLite (`data/job_ai_system.db`; jobs, resume_versions, analysis_results, application_events, ingested_jobs — db_manager.py:65-141) plus fragmented JSON stores (data/insights, behavior_state, cache) and a 15 MB unrotated log. No API, no queue, no packaging metadata (no pyproject.toml), **not a git repository** (re-verified today).

### 3. What Sreejita Is Supposed To Become

Per the product goal: one trustworthy Resume Intelligence + Hiring Simulation + Career Decision Support + Application Intelligence + Outcome Learning system — candidate understanding, JD understanding, evidence-based alignment, truth-preserving improvement, transparently heuristic hiring simulation, APPLY/FIX-GAPS/SKIP decisions, application tracking, and (only when data justifies) calibrated learning. TRUST > SCORE INFLATION is the governing principle.

### 4. Product Goal Cross-Check

Core journey target vs reality:

| Journey stage | Today | Status |
|---|---|---|
| Resume + JD input | VERIFIED (text/PDF/DOCX parsers; executed) | COMPLETE-enough for core |
| Candidate understanding | PARTIAL — parse/skills/experience/projects OK; evidence tiers exist (`content_quality.py:148`) but no strength-labeled output surfaced to users | PARTIAL |
| JD understanding | PARTIAL — skills/responsibilities/education/domain keywords extracted; company/location/seniority/employment-type/salary NOT structured (processor.py:92-105 only strips them as noise) | PARTIAL |
| Alignment/evidence matching | PARTIAL — exact/missing skill matching + proof-strength signal; no transferable-match class, no credibility-risk class | PARTIAL |
| Truthful improvement | PARTIAL — guards live (identity check core.py:1037-1085, quality gate, truth engine); no per-change ledger exposed; regression (66.6→60.7) undetected by gate | PARTIAL |
| Hiring simulation + decision | VERIFIED as implemented; heuristic (personas executed: Amazon MAYBE 47, Google MAYBE 50, Microsoft PASS 41); decision explanations present but terse | PARTIAL |
| Application decision | VERIFIED (APPLY/FIX GAPS/SKIP observed) | COMPLETE-enough |
| Persistence | PARTIAL — SQLite for dashboard surface; app-path persistence not observed | PARTIAL |
| Tracking → Outcome → Learning | Storage + analytics only; no adaptation loop | MISSING (deferred by design below) |

### 5. Previous Forensic Audit Verification

Cross-checked against the current repository (fresh execution today where listed):

| Previous Finding | Evidence (today) | Verdict | Severity | Roadmap Impact |
|---|---|---|---|---|
| 24/40 tests, "ISSUES FOUND", exit 0 | Re-executed today: identical 24/40, same 2 failures (66.6→60.7; 2.8≠0), exit 0 | STILL VALID | P0 | Roadmap Phase 1 |
| False-green runner (fixed "8/8", exit 0 on failure) | tests/run_all.py source + today's run | STILL VALID | P0 | Phase 1 |
| Semantic score floor (scorer.py) | `Semantic floor applied` at scorer.py:223 today | STILL VALID | P1 | Phase 3 |
| Multiple shortlist sites | 6 `shortlist_probability` assignment occurrences (incl. core.py:1950-51 "reference vs final" comments) | STILL VALID | P1 | Phase 3 |
| app/dashboard parity broken | Prior executed probe (63.7 vs 75.3; 23.4 vs 31.4); code paths unchanged today | STILL VALID (execution evidence) | P0 | Phase 2 |
| Heuristic shortlist presented as probability | hiring_simulation.py:855; no benchmark data in-tree | STILL VALID | P1 | Phase 7 relabeling |
| Learning = analytics only | feedback.py "Pure analytics…No LLM"; no consumer in scoring path | STILL VALID | — | Phase 8 (schema now, learning deferred) |
| Determinism holds | 3× identical no-LLM runs (hash bebf2636…), 2× identical LLM runs | STILL VALID | — | preserved as invariant |
| Truth protection works | guards live; zero invented metrics observed | STILL VALID | — | centralize in Phase 4 |
| Ollama healthy, both referenced models respond | `ollama list` today: same 6 models | STILL VALID | — | Phase 9 gateway |
| Career-gap intelligence MISSING | **CONTRADICTED** — `resume_intelligence.py:196 _detect_employment_gap` + "employment_gap" flag | CORRECTED: detection exists; recovery-strategy intelligence missing | P2 | Phase 11 |
| Evidence-strength machinery MISSING | **CONTRADICTED** — `content_quality.py:148 score_proof_strength`, consumed at core.py:1489 | CORRECTED: exists and wired; not surfaced as user-facing evidence labels | P2 | Phase 4/11 |
| test_truth.py crashes (cp1252) | prior run exit 1 UnicodeEncodeError | STILL VALID | P1 | Phase 1 |
| PII in tree; 15 MB log; no .env/secrets | verified in audit; unchanged assumption re-checked today (files still present) | STILL VALID | P2 | Phase 10 |
| Not a git repository | re-verified today | STILL VALID | P0 | Phase 0 |

### 6. Current Architecture Assessment

Layered reality: two UI stacks + one shared deterministic core (`pipeline/core`) + a 222 KB improver + overlapping rewrite modules + heuristic simulation + SQLite + JSON sprawl. Dependency direction is mostly sane (UIs → core → models), but the dashboard path wraps the core in `manual_mode` with different preprocessing/LLM behavior, and scoring mutations (floors, dampening, post-hoc probability overwrite) live inside `ats_scoring.scorer` rather than as explicit contract fields. Large monoliths (core 100 KB, hiring_simulation 105 KB, improver 222 KB) are functional; per spec §44 they are NOT refactor targets unless they block correctness — they block it only at the scoring-contract and mode-policy seams.

### 7. Target Architecture

```text
UI Layer (app.py primary; dashboard.py tracking/admin; CLI optional)
        ↓  one call, one contract
Application Service (thin: parse → canonical engine → AnalysisResult)
        ↓
CANONICAL INTELLIGENCE ENGINE  (pipeline/core remains canonical, §9)
   Candidate Intel → JD Intel → Alignment → Improvement → Truth Gate
        ↓
Scoring Engine (pure functions; explicit adjustment fields)
        ↓
Hiring Simulation (labeled heuristics) → Decision Engine (explained)
        ↓
Persistence (SQLite authoritative; JSON = exports/caches only)
Cross-cutting: LLM Gateway · Evaluation/Golden Harness · Observability · Config · Security
```

Every layer has one owner, one source of truth, an explicit failure behavior, and a validation boundary. Learning layer: schema-ready, execution deferred (§20).

### 8. Capability-by-Capability Gap Matrix

Status vocabulary: COMPLETE / PARTIAL / MISSING / BROKEN / NOT REQUIRED NOW. Priority: P0–P4.

| # | Capability | Goal | Current | Evidence | Status | Required Work | Priority |
|---|---|---|---|---|---|---|---|
| 1 | Resume ingestion (text) | robust parse | executed OK | E2E | COMPLETE | — | — |
| 2 | PDF parsing | robust | pdfplumber wired | imports; not executed on real PDF | PARTIAL | fixture tests | P2 |
| 3 | DOCX parsing | robust | python-docx wired | same | PARTIAL | fixture tests | P2 |
| 4 | Candidate intelligence | evidence-labeled profile | parse OK; proof-strength internal only | content_quality.py:148 | PARTIAL | surface evidence labels | P2 |
| 5 | JD parsing | structured fields | skills/resp/education OK | E2E | PARTIAL | add company/location/seniority/type | P1 |
| 6 | JD intelligence | full §6.2 set | salary etc. treated as noise | processor.py:92-105 | PARTIAL | extend model + extraction | P1 |
| 7 | Role detection | reliable | role_engine + JD title | E2E ("Senior Data Analyst") | PARTIAL | golden-set validation | P2 |
| 8 | Domain detection | generalizes | education-domain keywords only | processor.py:487-514 | PARTIAL | domain layer via golden set | P2 |
| 9 | Seniority detection | differentiate expectations | title + years parsed | E2E | PARTIAL | seniority policy table | P2 |
| 10 | Skill extraction | reliable | executed | E2E | COMPLETE | — | — |
| 11 | Skill normalization | canonical forms | partial (lower/multiword) | E2E | PARTIAL | normalization table | P2 |
| 12 | Skill equivalence | synonyms/abbrev | TF-IDF lexical only; no sentence-transformers | requirements comment | MISSING | equivalence map (deterministic) | P2 |
| 13 | Skill→evidence mapping | claims vs proof | proof-strength fn exists | content_quality.py:148 | PARTIAL | wire into outputs | P2 |
| 14 | Strength detection | surfaced | internal | core.py:1489 | PARTIAL | expose | P2 |
| 15 | Weakness detection | surfaced | gaps/risk_flags in trace | E2E trace_keys | COMPLETE | — | — |
| 16 | Genuine gap detection | true vs evidence gaps | "listed but not demonstrated" executed | hiring_sim output | PARTIAL | split true-gap vs evidence-gap classes | P2 |
| 17 | Career-gap intelligence | detect + honest strategy | detection exists | resume_intelligence.py:196 | PARTIAL | add presentation guidance | P2 |
| 18 | Project intelligence | classify/leverage | ProjectEntry first-class | models.py | PARTIAL | relevance classification | P3 |
| 19 | Experience intelligence | depth/relevance | experience_relevance 0.25 | config.yaml | PARTIAL | seniority-aware scoring | P2 |
| 20 | ATS scoring | meaningful alignment | weighted lexical + guards | scorer.py | PARTIAL | contract + explicit adjustments | P0 |
| 21 | Semantic similarity | true semantics | TF-IDF proxy + floors | scorer.py:223 | PARTIAL | explicit adjustment fields | P0 |
| 22 | ATS optimization | structural gains | multi-pass, targets | core.py:591-601 | PARTIAL | regression fix + governance | P0 |
| 23 | Keyword optimization | honest | injection w/ evidence guard | core.py:1079-1085 | PARTIAL | ledger | P1 |
| 24 | Resume rewriting | quality | LLM path good; fast path rough | E2E bullets | PARTIAL | naturalizer in fast path | P2 |
| 25 | Summary rewriting | quality | executed good | E2E partB | COMPLETE | — | — |
| 26 | Bullet rewriting | quality | mixed ("Sql queries when needed.") | E2E | PARTIAL | quality gate strengthening | P2 |
| 27 | Truth protection | centralized gate | guards in core + truth_engine | core.py:1037+ | PARTIAL | single chokepoint | P0 |
| 28 | Fabrication detection | robust | executed (0 fake) | E2E partD | COMPLETE | regression tests | P1 |
| 29 | Metric protection | robust | executed | E2E | COMPLETE | regression tests | P1 |
| 30 | Identity protection | robust | identity_ok executed | E2E partB | COMPLETE | adversarial tests | P1 |
| 31 | Employer/title/date protection | robust | no corruption observed | E2E | PARTIAL | adversarial suite | P1 |
| 32 | Recruiter simulation | labeled heuristic | personas executed | hiring_sim | COMPLETE (as heuristic) | labeling + docs | P2 |
| 33 | Hiring-manager simulation | signals | within personas | same | PARTIAL | fold into 32 | P3 |
| 34 | Hiring signal analysis | explained | persona reasons printed | executed | PARTIAL | structured reasons | P2 |
| 35 | Shortlist estimation | one canonical source | 6 occurrences / 3 sites | grep today | BROKEN (fragmented) | single source | P0 |
| 36 | APPLY/FIX/SKIP decision | explainable | executed | E2E | PARTIAL | explanation contract | P2 |
| 37 | Explanation engine | per-output reasons | partial (penalties list) | trace_keys | PARTIAL | unified explanation field | P2 |
| 38 | Resume variants | alternatives | absent | — | MISSING | defer (P4) | P4 |
| 39 | Strict mode | policy-driven | target 85/3 passes | core.py:598-601 | PARTIAL | full policy table | P1 |
| 40 | Balanced mode | policy-driven | 78/65, 2 passes | core.py:594-597 | PARTIAL | same | P1 |
| 41 | Conservative mode | grammar-only | executed branch | improver.py:426-488 | PARTIAL | same + convergence check | P1 |
| 42 | App UI | primary product | boots, works | health check | COMPLETE | — | — |
| 43 | Dashboard UI | tracking surface | boots, works | health check | COMPLETE | — | — |
| 44 | App/dashboard parity | one result | DIVERGED (63.7 vs 75.3) | executed probe | BROKEN | unify | P0 |
| 45 | Job ingestion | adapter + normalized | Playwright LinkedIn exists | scraper/ | NOT REQUIRED NOW (ToS risk) | defer; manual/file input | P4 |
| 46 | Job ranking | explainable | ranker present | insights/ | PARTIAL | exercise with data | P3 |
| 47 | Application tracking | persist journey | schema exists | db_manager.py:131 | PARTIAL | wire app-path writes | P2 |
| 48 | Outcome tracking | recorded+used | schema, no loop | feedback.py | PARTIAL | outcome schema + capture | P2 |
| 49 | Feedback analytics | honest stats | executed design | feedback.py | COMPLETE (as analytics) | — | — |
| 50 | Actual learning | validated adaptation | absent | §25 spec | DEFERRED (explicit) | schema only | P4 |
| 51 | Calibration | data-gated | absent | — | DEFERRED | — | P4 |
| 52 | Model evaluation | golden harness | absent | — | MISSING | Phase 6 | P1 |
| 53 | Ollama integration | healthy | verified | model tests | COMPLETE | — | — |
| 54 | LLM fallback | safe | rule-based fallback executed | manual_mode.py:144-148 | PARTIAL | failure matrix | P1 |
| 55 | Deterministic execution | verified | hash-identical | E2E | COMPLETE | keep invariant | — |
| 56 | Observability | useful logs | 15 MB unrotated; UI disables logging | app.py:18 | PARTIAL | rotation + scrubbing | P2 |
| 57 | Security | no secrets; safe uploads | sweep clean | audit | PARTIAL | upload/input hardening | P2 |
| 58 | Privacy | PII governed | PII in tree | data/ | PARTIAL | data-dir policy | P2 |
| 59 | Persistence | one authority | fragmented | data/*json | PARTIAL | SQLite authoritative | P1 |
| 60 | API | not required now | none | audit | NOT REQUIRED NOW | — | P4 |
| 61 | Background jobs | not required | none | audit | NOT REQUIRED NOW | — | P4 |
| 62 | Testing | truthful suites | 24/40 + false-green runner | run_all | BROKEN | Phase 1 | P0 |
| 63 | E2E testing | journey-level | custom scripts only | tests/ | MISSING | harness + fixtures | P1 |
| 64 | Packaging | installable | none (no pyproject) | audit | MISSING | pyproject + entry points | P1 |
| 65 | Deployment | in scope? | local-first | — | NOT REQUIRED NOW | — | P4 |
| 66 | Documentation | matches reality | inflated claims | *_report.md | BROKEN (docs) | sync after fixes | P2 |

### 9. Critical Architectural Decisions

| Decision | Current State | Option A | Option B | Evidence | Recommended Direction | Reason |
|---|---|---|---|---|---|---|
| Canonical engine | core.py used by both stacks (app direct, dashboard via manual_mode) | Keep pipeline/core canonical + thin service wrapper | Build new clean engine | Both paths already converge on run_full_pipeline; trace contract exists | **A** — controlled seam refactor only | Least-risk convergence; preserves executed behavior |
| App vs dashboard | divergent wrappers | Two UIs, one engine + one AnalysisResult contract | Two separate products | Divergence is wrapper-caused (LLM usage + preprocessing), not fundamental | **A** — app.py = PRIMARY product UI; dashboard = tracking/admin over same engine | Product goal is one candidate journey; §11 of spec |
| Score ownership | mutations inside scorer (floors/dampen) + post-hoc shortlist | Pure scoring module: Raw + ExplicitAdjustment = Reported | Keep opaque in-place mutation | scorer.py:223-258; 3 shortlist sites | **A** | Transparency is a core product principle |
| Persistence | SQLite + JSON sprawl | SQLite authoritative; JSON=exports/cache | Files authoritative | db_manager tables; JSON stores observed | **A** | Single queryable truth; JSON kept as exports |
| LLM gateway | scattered calls (engine._call_llm_with_json_retry etc.) | One gateway module (registry/routing/timeout/retry/validation/fallback) | Per-module clients | multiple call sites; fallback exists once | **A** | Failure contract must be uniform (§28-29) |
| Job ingestion | Playwright LinkedIn, never run | Defer live scraping; manual/file JD input + adapter seam | Make scraping core | ToS/anti-bot risk; zero executed evidence | **A — defer** | Not required for core value; legal risk |
| API/queues | none | Defer until multi-user/SaaS | Build now | single-user local product | **A — defer** | Spec §40/§65: no features before foundation |
| Learning | analytics only | Deferred; outcome schema now, adaptation gated later | Auto-learning now | no outcome data | **A** | §25: controlled learning only, data-gated |
| Shortlist terminology | "probability" | Rename output to fit-estimate fields, keep % out of prose | Keep probability wording | no empirical basis | **A** | §18: heuristics must not masquerade as probabilities |

### 10. Product Principles That Must Be Locked

1. TRUST > SCORE INFLATION (no floors presented as measurements; adjustments explicit).
2. One engine, one result contract, everywhere.
3. Every heuristic number is labeled as an estimate (shortlist/fit, personas, confidence).
4. No fabricated content ever; every injected keyword has in-resume evidence.
5. A change to a resume is auditable: original → modified → reason → evidence → risk.
6. Improvement must never silently regress the system's own evaluation (explicit, explained tradeoffs only).
7. Deterministic mode is a first-class product mode, not a degraded fallback.
8. No features before foundations (spec §65).

### 11. P0/P1/P2/P3 Prioritization

- **P0 (BLOCKING):** git+packaging truth; test-runner honesty; app/dashboard unification on one contract; shortlist single-source; score-regression fix (66.6→60.7); no-experience leak (2.8≠0).
- **P1 (CRITICAL):** scoring contract (raw vs adjusted fields); truth-gate centralization; JD structured fields; LLM gateway + failure matrix; golden dataset + evaluation harness; mode-policy table; packaging.
- **P2 (IMPORTANT):** evidence labels surfaced; career-gap guidance; project relevance; decision explanations; persistence unification; outcome schema; privacy/log hygiene; docs synchronization; E2E/adversarial suites.
- **P3 (ENHANCEMENT):** job ranking exercise; variant UX; project-type taxonomy; hiring-manager persona depth.
- **P4 (FUTURE):** API, queues, live ingestion, variants, auto-learning/calibration, SaaS hardening.

### 12. Final Dependency Graph

```text
Repository Truth (git init, packaging, freeze discipline)  [P0]
      ↓
Test Truth (runner honesty, encoding fix, per-test accounting)  [P0]
      ↓
Golden Fixtures (evaluation harness seed)  [P1]
      ↓
Execution-Path Unification (canonical engine + AnalysisResult)  [P0]
      ↓
Canonical Scoring (single sources; explicit adjustments; regression fix)  [P0/P1]
      ↓
Truth Gate Centralization (change ledger)  [P1]
      ↓
Core Intelligence Upgrades (JD fields, seniority, equivalence)  [P1/P2]
      ↓
Safe Improvement (modes policy, naturalizer in fast path)  [P1/P2]
      ↓
Hiring Simulation & Decision (labeling, explanations)  [P2]
      ↓
Persistence Unification + Outcome Schema  [P2]
      ↓
LLM Gateway & Failure Matrix  [P1]
      ↓
UI/Reporting Sync + Docs Truth  [P2]
      ↓
Security/Privacy/Observability  [P2]
      ↓
E2E / Adversarial / Performance  [P2]
      ↓
Final Certification (gates A–K)  [P1 gate]
(SaaS/ingestion/learning remain P4, outside this roadmap's critical path)
```

### 13. Complete Roadmap

**PHASE 0 — Repository Truth** (P0). Objective: make change discipline possible. Current: no git, no pyproject, root sprawl. Work: `git init` + .gitignore (venv, data PII, logs, cache, _audit_tmp); pyproject.toml with entry points; docs directory for reports. Deliverables: versioned repo, installable package. Acceptance: `pip install -e .` works; first commit contains unmodified baseline. Risks: PII committed — mitigation: .gitignore BEFORE first commit. Rollback: none needed (additive). Exit gate: fresh clone → install → `streamlit run app.py` boots.

**PHASE 1 — Test Infrastructure Truth** (P0). Objective: trustworthy gates. Work: rewrite tests/run_all.py (real per-test discovery/accounting, non-zero exit on failure, suite-type labels); fix test_truth.py encoding (ASCII output or UTF-8-safe print); classify suites (unit/integration/model-dependent). Affected: tests/run_all.py, test_truth.py. Acceptance: deliberately broken assertion → runner exits ≠0 and reports truthful counts; test_truth executes its body. Rollback: keep old runner as run_all_legacy.py during transition. Complexity: S.

**PHASE 2 — Execution-Path Unification** (P0). Objective: one engine behind all surfaces. Work: Application Service module exposing `analyze(resume, jd, mode, config) -> AnalysisResult` (pydantic) calling canonical core; app.py and manual_mode/dashboard path consume it; LLM usage becomes a mode/quality knob, not a different engine. Affected: app.py, dashboard.py, manual_mode.py, new service module. Acceptance: on the golden-fixture set, app-path vs dashboard-path ATS-after delta ≤ 0.1 and identical decisions (dashboard may ADD depth, never contradict). Dependencies: Phase 1 (gates), fixtures (min set from Phase 6 seed). Rollback: keep old wrappers behind a flag. Complexity: M.

**PHASE 3 — Canonical Scoring Architecture** (P0/P1). Objective: scoring means what it says. Work: (a) extract pure scoring functions; (b) reported semantic = Raw + ExplicitAdjustment (floor becomes named adjustment with its own field); (c) single shortlist source (deprecate scorer.py:337 path → core contract); (d) fix improvement regression 66.6→60.7 via before/after governance (accept only if no-dimension-worse or explicitly explained tradeoff, per spec §14 — NO artificial floor/cap); (e) fix no-experience 0-score leak. Acceptance: run_all ≥38/40; regression tests for both fixed bugs; golden set shows zero unexplained deltas. Rollback: git milestone. Complexity: M-L.

**PHASE 4 — Truth Gate Centralization** (P1). Objective: one chokepoint, auditable changes. Work: single TruthGate validating every rewrite (identity, metrics, evidence for injected skills); change ledger entries {original, modified, reason, evidence, risk} surfaced in UI; surface proof-strength labels (content_quality.py:148) in outputs. Acceptance: adversarial fixtures (invented metric, unsupported tech, project→employment swap) blocked with explanation; ledger present for every changed bullet. Complexity: M.

**PHASE 5 — LLM Gateway & Failure Matrix** (P1). Objective: uniform LLM behavior. Work: gateway module (model registry from config, task routing, timeout, retry, JSON validation, deterministic fallback, observability); port existing call sites; implement spec §29 failure matrix tests (unavailable, missing model, timeout, malformed, empty, partial; DB unavailable; empty/malformed/oversized inputs). Acceptance: matrix green; no silent degradation; user-visible explanations. Complexity: M.

**PHASE 6 — Golden Dataset & Evaluation Harness** (P1). Objective: measurable product truth. Work: synthetic-labeled fixture set (10 candidate types × 12–15 roles incl. business/customer domains); harness measures parse/role/alignment/ATS/semantic/evidence/rewrite/truth/decision/latency/failure per fixture; wired into CI-style gate. Acceptance: harness runs in <5 min deterministic mode; baseline report committed. Complexity: M.

**PHASE 7 — Modes, Simulation & Decision Integrity** (P2). Objective: labeled, explainable judgments. Work: mode-policy table (targets/passes/limits per mode in config, not code); rename shortlist output to fit-estimate terminology; structured decision explanations (why APPLY/FIX/SKIP); persona outputs labeled "heuristic simulation". Acceptance: mode differences reproduce via policy; no unlabeled probability anywhere; decisions carry reasons. Complexity: M.

**PHASE 8 — Persistence & Outcome Intelligence** (P2). Objective: one authority + future-proof outcomes. Work: route app-path writes to SQLite; consolidate JSON stores to exports/caches; outcome capture schema (application → status → outcome) with feature-snapshot for future calibration. Acceptance: single SQLite source for analyses; outcome rows writable from UI; learning execution stays deferred. Complexity: M.

**PHASE 9 — Core Intelligence Upgrades** (P1/P2). Objective: deeper understanding without brittleness. Work: JD structured fields (company/location/seniority/employment-type; salary optional); skill normalization + deterministic equivalence map; seniority expectation policy; evidence-gap vs true-gap classes; career-gap presentation guidance (building on resume_intelligence.py). Acceptance: golden-set gains documented; no role-specific hardcoding explosion (spec §24). Complexity: L.

**PHASE 10 — Security/Privacy/Observability** (P2). Work: PII out of repo (data dir policy), log rotation effective + scrubbing, upload validation, JD prompt-injection sanitization, UI logging reconsidered. Acceptance: no PII in tracked files; log ≤ configured size; injection fixtures neutralized. Complexity: M.

**PHASE 11 — E2E/Adversarial/Performance + Certification** (P2). Work: journey E2E (UI-level), adversarial suite (spec §31/§32), performance baselines (deterministic <1s; LLM <30s; failure timeouts bounded), docs synchronized, run Gates A–K. Acceptance: all applicable gates pass; certification report. Complexity: M.

**Deferred (spec §57):** API, queues/workers, live LinkedIn ingestion, resume variants, autonomous learning/calibration, multi-provider routing, SaaS infra. Deferred for dependency/scope reasons, not difficulty.

### 14. Detailed Work Packages (selected P0/P1)

```text
ID: SHE-P0-01 Title: Git + packaging baseline. Priority: P0.
Problem: no VCS, no installable package → no milestones/rollback.
Evidence: git rev-parse fails today; pyproject absent.
Change: git init + .gitignore(data/,logs/,.venv,_audit_tmp,__pycache__) then pyproject.toml.
Validation: fresh clone install + boot. Rollback: n/a (additive).

ID: SHE-P0-02 Title: Honest test runner. Priority: P0.
Problem: fixed 8/8 accounting; exit 0 on 16 failures (observed today).
Evidence: tests/run_all.py source + executed run.
Change: per-test discovery, truthful counts, non-zero exit on failure.
Validation: seeded failure flips exit code. Rollback: legacy runner kept.

ID: SHE-P0-03 Title: Canonical analyze() service + parity. Priority: P0.
Problem: same input → 63.7 vs 75.3 across surfaces.
Evidence: executed parity probe (audit2_parity_results.json).
Change: one ApplicationService; both UIs consume AnalysisResult.
Validation: fixture parity delta ≤0.1; decisions identical. Rollback: legacy flag.

ID: SHE-P0-04 Title: Shortlist single source. Priority: P0.
Problem: 6 assignment occurrences / 3 sites incl. post-hoc overwrite.
Evidence: repo grep today; core.py:1950-51 comments.
Change: one pure function owns fit-estimate; others read.
Validation: grep shows single write-site; golden set unchanged outputs pre/post refactor.

ID: SHE-P0-05 Title: Improvement-regression fix. Priority: P0.
Problem: improvement loop can lower score 66.6→60.7, undetected.
Evidence: Intelligence suite failure (reproduced today).
Change: before/after governance policy in pipeline (accept if no dimension worse OR explained tradeoff), per spec §14; no artificial floors.
Validation: Intelligence suite green; regression test added.

ID: SHE-P0-06 Title: No-experience scoring leak. Priority: P0.
Problem: zero-experience resume scores 2.8 (expected 0 by own hardening test).
Evidence: Hardening suite failure (reproduced today).
Change: correct experience-term handling in scorer (not a cap hack).
Validation: Hardening suite green; regression test added.

ID: SHE-P1-01 Title: Scoring contract (Raw + ExplicitAdjustment). Priority: P1.
Problem: semantic floor at scorer.py:223 silently rewrites the measured signal.
Change: reported = raw + named adjustments (own fields); UI discloses.
Validation: fixture shows raw vs reported; dampening documented.

ID: SHE-P1-02 Title: Truth gate + change ledger. Priority: P1. (Phase 4)
ID: SHE-P1-03 Title: LLM gateway + §29 failure matrix. Priority: P1. (Phase 5)
ID: SHE-P1-04 Title: Golden dataset + harness. Priority: P1. (Phase 6)
ID: SHE-P1-05 Title: JD structured fields + seniority policy. Priority: P1. (Phase 9)
ID: SHE-P1-06 Title: test_truth encoding fix (fold into SHE-P0-02). Priority: P1.
ID: SHE-P1-07 Title: pyproject entry points + install (fold into SHE-P0-01). Priority: P1.
```

### 15. Acceptance Criteria (measurable DONE)

- **Parity:** both UI surfaces invoke the same `analyze()` and return identical structured `AnalysisResult` for identical inputs across the golden suite — numeric tolerance 0.1, decisions identical.
- **Runner truth:** runner exit code ≠0 when any test fails; counts equal discovered test functions; no fixed denominators.
- **Scoring:** every reported signal has a documented formula; every adjustment is a named field; zero hidden mutations (verified by golden-diff harness).
- **Regression:** the two reproduced defects have regression tests that fail-first, then pass.
- **Truth:** adversarial fixtures (fabricated metric/tech/employment-swap/identity-change) are blocked with explanations; ledger covers 100% of changed bullets.
- **Failure:** §29 matrix fully green; no silent degradation.
- **Modes:** behavior differences trace to config policy table; convergence on strong resumes documented, not accidental.
- **Estimates:** zero unlabeled probability terms in UI or reports.
- **Persistence:** SQLite sole authority for jobs/analyses/outcomes; JSON only under exports/ or cache/.
- **Performance:** deterministic pipeline <1s p95 on golden set; LLM mode <30s p95; bounded failure timeouts.

### 16. Testing & Certification Strategy

Layers: unit (scoring/guards/normalization) → integration (parse→analyze→persist; Ollama optional) → E2E (UI journey) → regression (every fixed defect) → adversarial (§31 list) → determinism (hash checks) → performance. Certification = Gates A–K (spec §55) executed on the golden harness; Gate C explicitly includes "no hidden floors/caps" via the adjustment-field audit.

### 17. Ollama / LLM Strategy

Keep local-only Ollama; registry = installed models verified today (llama3.2:3b, qwen2.5-coder:3b primary/fast; granite4.2:3b avoid for latency 47.9s; nomic-embed for embeddings if semantic upgrade later); gateway owns routing/retry/timeout/validation/fallback; deterministic path remains fully functional alone. Model swap procedure documented (config-driven, verified by gateway health check) — directly addressing the user's mid-audit model change: code references only the two installed models, so **no model-reference change is required now**, and after the gateway exists, swaps are config-only.

### 18. Security & Privacy Strategy

PII stays local by product design; policy: PII never in git (gitignore data/), logs scrubbed + rotated, uploads size/type-validated, JD/resume content treated as untrusted input at the LLM boundary (sanitization layer), no external transmission of candidate data (already true — Ollama local). Exposure is currently actual (files in tree), not merely theoretical.

### 19. Data / Persistence Strategy

SQLite authoritative for: candidate profile, resumes, JDs, analyses, improved resumes, applications, outcomes, calibration snapshots, audit/trace. Filesystem: exports (PDF/DOCX/JSON), caches (regenerable), logs. No data in code tree at commit time.

### 20. Learning & Calibration Strategy

Deferred execution, designed schema now: outcome rows + feature snapshots + variant/strategy tags captured from Phase 8. Learning activates only when: minimum sample sizes met, validation harness shows calibration beats baseline, versioned strategy with rollback + human approval. Until then the product says: "analytics, not learning" (honest labeling per spec §25).

### 21. Production Strategy

Local-first distribution: packaged install (pyproject + entry points), Ollama as a documented dependency, no server deployment in current scope. SaaS is Level 4 and out of scope until Levels 1–3 gates pass (spec §66 separation).

### 22. Final Definition of DONE

Per subsystem: implementation + execution + correctness (golden harness) + failure handling (§29 matrix) + regression protection + truthful docs. "DONE" for the product = Levels 1–3 complete and Gates A–I passing; Level 4 (SaaS) and Level 5 (learning) explicitly out of current DONE.

### 23. Final Completion Checklist

```text
[ ] Architecture unified (one analyze() service; app=primary UI)
[ ] One canonical pipeline; no divergent execution paths
[ ] App/dashboard parity ≤0.1 on golden fixtures
[ ] Canonical input/result contracts (pydantic AnalysisResult)
[ ] Truth gate centralized; change ledger complete
[ ] ATS scoring validated; adjustments explicit (raw vs reported)
[ ] Semantic metric validated (floor → named adjustment)
[ ] Shortlist centralized (single write-site)
[ ] Heuristic estimates labeled everywhere
[ ] Three modes validated via policy table
[ ] Resume/JD/skill→evidence intelligence complete (P1/P2 scope)
[ ] Career-gap + project intelligence (detection exists → guidance added)
[ ] Seniority intelligence complete
[ ] Domain generalization validated on golden set
[ ] Recruiter simulation labeled; decision engine explained
[ ] Application + outcome tracking persisted (SQLite)
[ ] Learning/calibration: explicitly DEFERRED with schema ready
[ ] LLM gateway centralized; failure matrix green
[ ] Deterministic fallback validated (already true — keep)
[ ] Security/privacy validated (PII out of tree, logs, sanitization)
[ ] Persistence unified (SQLite authoritative)
[ ] Testing truthful (runner honest, counts real)
[ ] Regression suite covers both reproduced defects + all future fixes
[ ] Golden dataset established (≥10 candidate types × ≥12 roles)
[ ] E2E + adversarial validated
[ ] Determinism validated (hash checks in CI-style gate)
[ ] Performance baselines met
[ ] Packaging complete (pip install -e ., entry points)
[ ] Documentation synchronized with reality
[ ] Final certification (Gates A–I) passed
```

### 24. Risks and Things We Must NOT Build Yet

Do NOT build: API/queues (no multi-user need), live scraping (ToS/anti-bot + not core), autonomous learning (no data), resume variants (post-core), microservices/SaaS infra (Level 4), new LLM providers (local-first principle). Risks: refactor regressions (mitigate: golden harness before unification); mode-policy loosening score integrity (mitigate: Gate C); PII leak on git init (mitigate: gitignore-first); scope creep into Level 4 (mitigate: gate discipline).

### 25. Final Roadmap Summary

- **NOW (first 5–10 actions):** git init + gitignore + pyproject (SHE-P0-01); honest runner + encoding fix (SHE-P0-02); golden-fixture seed; canonical analyze() + parity (SHE-P0-03); shortlist single source (SHE-P0-04); regression fix (SHE-P0-05); no-experience fix (SHE-P0-06); scoring contract (SHE-P1-01).
- **NEXT:** truth gate + ledger; LLM gateway + failure matrix; JD fields + seniority; golden harness full; modes policy table.
- **LATER:** persistence unification + outcome schema; privacy/log hygiene; explanations; evidence labels; domain expansion; E2E/adversarial/perf; docs truth.
- **FINAL (definition of complete):** Levels 1–3 done, Gates A–I pass, checklist §23 fully checked — a trustworthy local hiring decision-support system; API/SaaS/learning remain explicitly future levels.

### 26. Final Product Verdict

**Sreejita Hiring Engine is** a local-first, privacy-preserving resume intelligence and hiring decision-support application that helps a genuinely capable candidate understand how well their real qualifications align with a specific job, improve the truthful presentation of that qualification, and decide — with explained, clearly-labeled heuristic reasoning — whether to apply, fix gaps first, or skip; it tracks applications and outcomes so that, only when sufficient real outcome data exists, its fit estimates may later be calibrated.

- **Inputs:** resume (text/PDF/DOCX), JD (paste/file; scraped sources deferred), mode, preferences.
- **Processing:** candidate intelligence → JD intelligence → evidence-based alignment → truth-preserving improvement → transparent scoring → labeled hiring simulation → explained decision → persistence.
- **Outputs:** analysis report, improved resume with auditable change ledger, fit estimate (labeled heuristic), decision with reasons, tracked application record.
- **Guarantees:** no fabrication; no silent score manipulation; one engine everywhere; deterministic mode always available; graceful LLM failure; local-only data.
- **Non-guarantees:** no interview/shortlist promises; no reproduction of any employer's actual ATS or hiring process; no statistically validated probabilities until real outcome data enables calibration.
- **Target users:** the individual job seeker (fresher to senior, career switchers, gap-having candidates). Recruiters/employers/enterprise: out of scope.
- **Core differentiator:** trust discipline — auditable, evidence-backed, honestly-labeled decision support instead of score-inflation theater.
- **Final architecture:** as §7 (canonical engine + gateway + truth gate + single scoring + SQLite + labeled simulation).
- **Final maturity level at roadmap completion:** Level 3 (Product Readiness), with Level 4 (SaaS) and Level 5 (calibrated learning) explicitly deferred and schema-ready.

### 67 (spec). Final Question — answered precisely

**If this roadmap is followed in order and every exit gate passes, Sreejita will reliably do what it cannot today:** give the same truthful answer from every surface; fail loudly instead of passing falsely; improve resumes without ever silently regressing them; show raw vs adjusted signals; explain every APPLY/FIX-GAPS/SKIP recommendation; keep every number honestly labeled; survive every LLM failure mode safely; and run as an installable, version-controlled product with a regression-proven core.

**What would still remain impossible to guarantee even after completion:** whether any specific employer shortlists or hires the candidate. Real outcomes depend on employer behavior, recruiters, external proprietary ATS systems, candidate quality, market conditions, competition, timing, geography, role availability, and internal company processes — factors outside this system. The roadmap deliberately builds the strongest trustworthy decision-support system possible, not a manufactured guarantee of employment.

---

*No repository files were modified in this phase. This report + prior deliverables are the only additive artifacts.*
