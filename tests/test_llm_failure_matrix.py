"""LLM Failure Matrix (Phase 5C / spec sections 24, 27, 45).

Executed fault injection against the real client boundary (utils.ollama_client)
with a mocked transport for deterministic fault cases, plus the live
deterministic fallback path. Every scenario is actually executed — no
source-inspection-only claims.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utils.ollama_client as oc
from utils.config_loader import AppConfig

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, cond))
    print(f"  {'PASS' if cond else 'FAIL'} {name} {detail}")


def make_cfg(host="http://127.0.0.1:9", model="ghost:latest", timeout=1, retries=2):
    cfg = AppConfig()
    cfg.llm.base_url = host
    cfg.llm.model = model
    cfg.llm.timeout = timeout
    cfg.llm.max_retries = retries
    return cfg


# ---- 1. model unavailable / connection refused (real socket, dead port) ----
try:
    oc.call_ollama([{"role": "user", "content": "hi"}], task="unavailable",
                   config=make_cfg(timeout=1, retries=1))
    check("model_unavailable_fails_loudly", False, "no exception raised")
except RuntimeError as e:
    check("model_unavailable_fails_loudly", "failed after" in str(e).lower(), str(e)[:80])
except Exception as e:
    check("model_unavailable_fails_loudly", True, f"{type(e).__name__} (bounded)")

# ---- 2. timeout (fake slow transport) ----
class _SlowClient:
    def chat(self, **kw):
        import time as _t
        _t.sleep(2)
        return {"message": {"content": "late"}}

cfg = make_cfg(timeout=1, retries=1)
oc._client = _SlowClient()
try:
    oc.call_ollama([{"role": "user", "content": "hi"}], task="timeout", config=cfg)
    check("timeout_bounded", False, "no exception")
except RuntimeError as e:
    check("timeout_bounded", "timed out" in str(e).lower() or "failed after" in str(e).lower(), str(e)[:80])
finally:
    oc._client = None

# ---- 3. empty response ----
class _EmptyClient:
    def chat(self, **kw):
        return {"message": {"content": ""}}
r = oc.validate_llm_output("")
check("empty_response_detected", r["ok"] is False and r["stage"] == "EMPTY")
r = oc.validate_llm_output("   \n  ")
check("whitespace_response_detected", r["ok"] is False and r["stage"] == "EMPTY")

# ---- 4. malformed JSON ----
r = oc.validate_llm_output("not json at all {")
check("malformed_json_detected", r["ok"] is False and r["stage"] == "PARSE")
r = oc.validate_llm_output("{'single': 'quotes'}")
check("py_style_json_rejected", r["ok"] is False and r["stage"] == "PARSE")

# ---- 5. partial / non-object ----
r = oc.validate_llm_output("[1, 2, 3]")
check("non_object_rejected", r["ok"] is False and r["stage"] == "SCHEMA")

# ---- 6. missing required fields ----
r = oc.validate_llm_output('{"name": "x"}', required_fields=["name", "skills"])
check("missing_field_rejected", r["ok"] is False and r["stage"] == "SCHEMA" and "skills" in r["error"])

# ---- 7. extra fields policy (ignored by default) ----
r = oc.validate_llm_output('{"name": "x", "weird": 1}', required_fields=["name"])
check("extra_fields_ignored_by_default", r["ok"] is True)
r = oc.validate_llm_output('{"name": "x", "weird": 1}', required_fields=["name"], allow_extra_fields=False)
check("extra_fields_rejected_when_strict", r["ok"] is False)

# ---- 8. markdown-fenced JSON accepted ----
r = oc.validate_llm_output('```json\n{"name": "x"}\n```', required_fields=["name"])
check("fenced_json_accepted", r["ok"] is True)

# ---- 9. hallucinated skill -> Truth Gate rejection (content boundary) ----
from utils.models import (StructuredResume, ContactInfo, ExperienceEntry)
from pipeline.truth_gate import validate_candidate_representation
orig = StructuredResume(
    contact=ContactInfo(name="Alex", email="alex@example.com"),
    skills=["Python"],
    experience=[ExperienceEntry(role="Dev", company="C", duration="2023", bullets=["Wrote Python."])],
)
hallu = orig.model_copy(deep=True)
hallu.skills = orig.skills + ["TensorFlow", "Kubernetes"]  # LLM-invented
v = validate_candidate_representation(orig, hallu, original_skills=orig.skills)
check("hallucinated_skills_rejected_by_truth_gate", not v.accepted and
      any("UNSUPPORTED_SKILL" in x for x in v.violations), v.violations[:2])

# ---- 10. deterministic fallback (no-LLM path still completes) ----
from tests.golden.fixtures import fixture_A_strong_aligned
from pipeline.service import analyze
r, jd = fixture_A_strong_aligned()
res = analyze(r, jd, mode="strict", job_id="llmfail_fallback")
ok = (0 <= res.ats_report.score_after <= 100 and res.pipeline_hash)
check("deterministic_fallback_completes", bool(ok), f"ats={res.ats_report.score_after}")

failed = [r0 for r0 in RESULTS if not r0[1]]
print(f"\nLLM failure matrix: {len(RESULTS)-len(failed)}/{len(RESULTS)} passed")
sys.exit(1 if failed else 0)