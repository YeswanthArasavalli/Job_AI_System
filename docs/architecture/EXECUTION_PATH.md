# EXECUTION_PATH — Canonical Architecture (Phase 3)

Status: CURRENT (as implemented in Phase 0-4, 2026-09-22). PLANNED items are marked.

## Entry points

| Surface | Path | Role |
|---|---|---|
| app.py (Streamlit) | run_analysis() -> pipeline.service.analyze() | PRIMARY product UI (candidate decision) |
| dashboard.py (Streamlit) | ManualAnalyzer.analyze() -> pipeline.service.analyze_tailored() | tracking/insights UI; core analysis via canonical service |
| CLI main.py | legacy direct engine path (PLANNED: migrate to service) | batch |
| pages/1-3 | dashboard multipage (tracking/pipeline) | secondary |

## Canonical analysis flow

pipeline.service.analyze / analyze_tailored
  -> stateless cache reset (ResumeEngine, SemanticMatcher)
  -> ATSScorer(config)
  -> pipeline.core.run_full_pipeline
       -> fingerprint (input-only, deterministic)
       -> role classify -> naturalize -> improvement passes (mode policy)
       -> truth rules (identity/fake-skills/score-consistency)
       -> validation gate -> hiring simulation -> shortlist loop
       -> PHASE 4 artifact-truth checkpoints (mandate + final reconciliation)
       -> unified shortlist (pipeline.unified_scoring = THE canonical source)
       -> PipelineResult (single result contract)

## Result contract

PipelineResult (pydantic dataclass in pipeline/core.py):
original, tailored, improved, extracted_jd, ats_report, readability,
target_plan, score_limit, pipeline_hash, role_fit, why_not_90, role_info,
resume_type, change_explanation, polish_changes, validation_result,
quality_score, hiring_simulation, content_intelligence,
shortlist_probability/band/decision/reason/unified (CANONICAL),
pipeline_trace (auditability).

Service-layer dict (pipeline.service.package_result) exposes the same values
surface-neutrally; manual_mode adds dashboard UX extras (next_actions, PDF,
back-compat aliases) WITHOUT recomputation.

## Scoring ownership (Phase 4)

- ATS score: ats_scoring.scorer (pure formula + disclosed policy adjustments)
- Semantic: raw TF-IDF measurement preserved in ats_report.raw_semantic_score;
  overlap floors recorded in ats_report.semantic_adjustments; reported
  semantic_score = raw + disclosed adjustments.
- Shortlist/fit: pipeline.unified_scoring.compute_final_shortlist_probability
  is THE only production calculation. ats_scoring.probability.ShortlistPredictor
  is offline/test-only (removed from compare() hot path).
- Artifact truth: reported score_after always describes the returned improved
  artifact (mandate checkpoint + final reconciliation; regression reverts with
  explicit risk flags IMPROVEMENT_REGRESSION_REVERTED /
  FINAL_ARTIFACT_REGRESSION_REVERTED).

## Known future consolidation (PLANNED, later phases)

- main.py CLI migration to service
- LLM gateway (single client semantics already centralized in utils/ollama_client.py)
- Truth-gate centralization beyond current core.py trust rules