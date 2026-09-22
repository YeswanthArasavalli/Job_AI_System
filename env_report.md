# SREEJITA ENVIRONMENT REPORT

Audit date: 2026-09-22 (Asia/Calcutta). Auditor: AutoCoder forensic run.
Repository: `D:\Projects\job_ai_system_v6\job_ai_system` — NOT a git repository (verified: `git rev-parse` → "fatal: not a git repository").
Baseline: `_audit_tmp/baseline_files.txt` + `%TEMP%\sreejita_audit\baseline_snapshot.txt` (14,297 files incl. `.venv`).

## System

| Item | Value | Evidence |
|---|---|---|
| OS | Windows 10.0.26200 x64 (MSI host) | runtime |
| Shell | PowerShell | runtime |
| Python (repo venv) | 3.14.6 (MSC v.1944, 64-bit) | `.venv\Scripts\python.exe -c "import sys"` executed |
| Virtual environment | `.venv\` present, 13,920 files | directory census |
| Python (system, irrelevant) | 3.13.12 at `D:\Programs\AutoClaw\resources\python` (no pytest) | executed |
| Dependency manager | none for the project itself: `requirements.txt` only (no lock file, no pyproject.toml) | file inspection |
| pytest | NOT installed in venv (tests are custom runner scripts) | `python -m pytest` → "No module named pytest" |
| venv package count | 66 (incl. streamlit 1.64.0, ollama 0.6.2, pandas 3.0.6, numpy 2.5.3, pydantic 2.13.5, playwright 1.63.0, pdfplumber, python-docx, fpdf2, rich, PyYAML, requests) | `pip list` captured |

`requirements.txt` vs installed: all listed packages present. `sentence-transformers` is commented out ("optional") — consequently `SemanticMatcher` runs on hand-rolled TF-IDF (no scikit-learn in venv). `pandas` is installed but NOT listed in requirements.txt (fresh-install reproducibility gap, observed).

## Ollama

| Item | Value |
|---|---|
| Ollama version | 0.34.2 (`ollama --version` executed) |
| Endpoint | `http://localhost:11434` (config.yaml) |
| Model config sources | `config.yaml:8` → `qwen2.5-coder:3b`; `utils/config_loader.py:15` default → `llama3.2:3b` (dual source of truth; both installed) |

## Model table (all values from live inference tests captured in `_audit_tmp/audit2_model_tests.json`)

| Model | Installed | Responds | Used By | Configured | Role | Problem |
|---|---|---|---|---|---|---|
| llama3.2:3b | YES | YES (13.0s) | fallback default in `utils/config_loader.py:15` | YES (code default) | LLM parse/tailor | none observed |
| qwen2.5-coder:3b | YES | YES (6.1s) | primary per `config.yaml:8` | YES | LLM parse/tailor/rewrite | none observed |
| granite4.2:3b | YES | YES (47.9s — very slow) | NO (not referenced) | NO | none | unused; slowest |
| deepseek-r1:1.5b | YES | YES (8.3s) | NO | NO | none | unused |
| lfm2.5-thinking:latest | YES | YES (1.9s) | NO | NO | none | unused |
| nomic-embed-text-v2-moe | YES | chat: NO (400 "does not support chat") | possibly embeddings | NO | embeddings | chat-incompatible by design; embeddings endpoint OK (768-dim, 6.0s) |

- CRITICAL ENVIRONMENT MISMATCH: none — every model the code references is installed and responds.
- OBSOLETE MODEL REFERENCE: none found in live code (`config.yaml`, `utils/config_loader.py` only).
- Note: user reported swapping models; at audit time `ollama list` still showed the original six. Audit proceeded with the observed set; no code/config model change was required or made.

## Configuration

- `config.yaml`: llm (provider ollama, timeout 120s, temperature 0.0, seed 42), resume_engine paths, ATS weights (keyword 0.30 / skills 0.25 / experience 0.25 / role 0.05 / education 0.05 / structure 0.10), pdf_generator, scraper (platform linkedin, headless false), database path `data/job_ai_system.db`, logging (INFO, `logs/system.log`, 5MB×3 rotation), user preferences (min_score_threshold 40).
- `.env` files: none found. Hardcoded secrets: none found in live code (pattern sweep returned zero hits).

## Database / persistence stores observed

- `data/job_ai_system.db` — SQLite (237,568 bytes), tables: jobs, resume_versions, analysis_results, application_events, ingested_jobs (`database/db_manager.py:65-141`).
- `data/master_resume.json` (3.6 KB, contains personal resume data), `data/insights/*.json` (6), `data/job_pipeline_log.json`, `data/behavior_state.json`, `data/alert_log.json`.
- `output/` — 45 files (resumes/pdfs artifacts). `logs/system.log` — 15,096,932 bytes: EXCEEDS the configured 5 MB rotation cap (rotation not effective as observed).
- `export/` module writes exports; `graphify-out/`, `.agent/`, `.code-review-graph/` are tool artifacts, not product data.

## External services / ports / workers / queues

- Ollama localhost:11434 — the only external dependency used in executed tests. LinkedIn (via Playwright scraper) is coded but NOT exercised (by design; live-site untested).
- Streamlit default ports used during audit: 8511/8512 (health checks only; processes terminated).
- Workers/queues: none (synchronous pipeline). No FastAPI/REST server exists (uvicorn installed but unused by any entry point).

## Runtime constraints

- Windows cp1252 console: `test_truth.py` crashes printing emoji (UnicodeEncodeError) — tests need `PYTHONIOENCODING=utf-8` or ASCII output.
- No pytest; custom runners report per-suite but `tests/run_all.py` exits 0 regardless of failures.
- Ollama latency varies 1.9s–47.9s by model; LLM path full run ≈ 23–26s; no-LLM path ≈ 0.3–0.4s.
