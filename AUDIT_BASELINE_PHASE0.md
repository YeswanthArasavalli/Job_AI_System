# AUDIT_BASELINE_PHASE0 — Repository Truth / Baseline Freeze

Date: 2026-09-22. Executor: AutoCoder (controlled implementation, Phases 0-4).

## Repository

- Root: D:\Projects\job_ai_system_v6\job_ai_system
- Identity: "Sreejita Hiring Engine" / "Job AI System" / "Career Decision Engine" (three in-tree names; README is authoritative product name: Job AI System)
- Version markers: CHANGELOG_v6.md (v6-era); no package version defined (no pyproject.toml) — version inconsistency risk noted; no fix applied (safe-change rule)
- Git: WAS absent; initialized this phase. Baseline commit 05def05 (185 files, 70,590 insertions), tag `phase0-baseline`. .gitignore excludes .venv/, data/ (real PII: master_resume.json + job_ai_system.db), logs/, output/, _audit_tmp/, graphify-out/, .code-review-graph/, __pycache__. PII scan of 131 tracked candidates: 33 name/email hits, ALL synthetic fixtures (@e.com/@email.com/test.com domains, 555 phones) — no real PII committed.
- Working tree after baseline: CLEAN (git status: 0 entries)
- Entry points: app.py (Streamlit candidate UI), dashboard.py (Streamlit cockpit), main.py (CLI), manual_mode.py (ManualAnalyzer, used by dashboard), pages/1-3 (dashboard multipage), tests/run_all.py (test harness)

## Environment

- OS: Windows 10.0.26200 x64; PowerShell; git 2.55.0.windows.2
- Python: 3.14.6 (repo .venv, 66 packages; NO pytest — custom script-style suites)
- Dependency manager: requirements.txt only (pip). Install path: `.venv\Scripts\python.exe -m pip install -r requirements.txt`
- Ollama: 0.34.2 @ localhost:11434. Installed (ollama list, verified today): granite4.2:3b, deepseek-r1:1.5b, lfm2.5-thinking:latest, nomic-embed-text-v2-moe:latest, llama3.2:3b, qwen2.5-coder:3b
- Configured vs installed vs used: config.yaml -> qwen2.5-coder:3b (INSTALLED, responds 6.1s); utils/config_loader.py:15 default -> llama3.2:3b (INSTALLED, responds 13.0s). Dual source of truth documented; both healthy. LLM connectivity already centralized in utils/ollama_client.py (single import site outside tests).
- Database: SQLite data/job_ai_system.db (tables: jobs, resume_versions, analysis_results, application_events, ingested_jobs)

## Test baseline (as found, old runner)

- Old runner tests/run_all.py: 5 hardcoded suites, prints fixed "8/8" per suite (count inferred from suite exit code), TOTAL: 24/40, grade "ISSUES FOUND", process EXIT CODE 0 (false-green)
- Reproduced failures (stable across 3 runs on 2026-09-21/22):
  1. Intelligence suite: "Score decreased: 66.6 -> 60.7" (improvement regression; reproduced in isolation: pipeline returned improved artifact re-scores 60.7 vs tailored 66.6 while ats_report.score_after reported 67.7 — reported-vs-artifact divergence CONFIRMED)
  2. Hardening suite: "No-experience resume should score 0, got 2.8" (isolated: impact_score defaults 30.0 and skill_demonstration defaults 40.0 with ZERO experience bullets — fabricated-evidence baselines at scorer.py:1129-1130 and :1048-1049)
  3. test_truth.py: UnicodeEncodeError (cp1252 console vs emoji prints) — crashes before assertions; contains NO assert statements (diagnostic script)
- Other suites: Stabilization 8/8 PASS, Ollama 8/8 PASS (model-dependent), Determinism 8/8 PASS
- tests/v6_system_tests.py: unittest-style (10 classes) — NOT in old runner's suite list

## Runtime baseline workflow (synthetic fixture, deterministic mode, executed)

Fixture: synthetic MSc data-analyst resume (Alex Candidate) + Data Scientist JD. Command: _audit_tmp/phase0_baseline_workflow.py (venv python). Results:
- ats_before 75.0, ats_after 76.1 (reported), semantic 50.0 (floor applied: raw 40.7 -> 50, overlap=10)
- decision APPLY, shortlist_probability 39.5 band B+ APPLY (STRONG)
- validation_passed true; missing spark/tensorflow; pipeline_hash 33f466f1f8447bf1
- INDEPENDENT re-score of returned artifact: tailored 75.0, improved 68.5 → **reported 76.1 != artifact 68.5** (defect #1 mechanism reproduced at baseline)
- Known issues at baseline: (1) score/report divergence post-selection mutations; (2) no-experience fabricated baselines; (3) semantic floor opaque; (4) shortlist computed in raw predictor + unified layer + mirrors; (5) false-green runner; (6) encoding crash in test_truth.py

## Golden baseline

- Fixture set: created in tests/golden/ (Phase 2): A strong-aligned, B weak, C no-experience, D truth-attack, E metric-protection, F identity-protection, G improvement-regression. Synthetic data only.

## PHASE 0 STATUS: PASS

Repository: git initialized, baseline 05def05, clean tree
Version: v6-era, no package version (documented, not invented)
Commit: 05def05 (tag phase0-baseline)
Environment: Python 3.14.6 venv / Ollama 0.34.2 / 6 models verified
Installation: pip install -r requirements.txt into .venv
Test command: python tests/run_all.py (Phase 1 replaces runner)
Main workflow: executed (see Runtime baseline)
Golden baseline: tests/golden (Phase 2)
Known issues: 6 documented above
