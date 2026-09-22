"""CLI canonical-service parity test (Phase 5F / spec section 35)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import inspect
from tests.golden.fixtures import fixture_A_strong_aligned
from pipeline.service import analyze, analyze_tailored

# 1. Architecture: main.py consumes the canonical service
src = open("main.py", encoding="utf-8").read()
print("  main.py uses analyze_tailored:", "analyze_tailored" in src)
print("  main.py has no direct run_full_pipeline:", "run_full_pipeline(" not in src)
assert "analyze_tailored" in src, "CLI not routed through canonical service"
assert "run_full_pipeline(" not in src, "CLI still bypasses the service"

# 2. Result parity: service (app path) vs analyze_tailored (CLI path)
r, jd = fixture_A_strong_aligned()
app_res = analyze(r, jd, mode="strict", job_id="parity_cli_app")
cli_res = analyze_tailored(r, r.model_copy(deep=True), jd, mode="strict", job_id="parity_cli_cli")
same = (app_res.ats_report.score_after == cli_res.ats_report.score_after
        and app_res.shortlist_probability == cli_res.shortlist_probability
        and app_res.pipeline_hash == cli_res.pipeline_hash)
print(f"  parity: app={app_res.ats_report.score_after}/{app_res.shortlist_probability} "
      f"cli={cli_res.ats_report.score_after}/{cli_res.shortlist_probability} -> {'EQUIVALENT' if same else 'DIVERGED'}")
assert same, "CLI result diverged from canonical service"

print("CLI parity: PASS")