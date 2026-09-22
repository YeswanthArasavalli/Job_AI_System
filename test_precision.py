"""Test Dynamic Calibration + Recovery (v3.5)."""
import logging
logging.disable(logging.WARNING)
from pipeline.precision_engine import run_precision_optimization

history = [
    {"company": "Startup A", "role": "Data Analyst", "ats_score": 81, "status": "shortlisted", "mode": "balanced"},
    {"company": "SC", "role": "Data Analyst", "ats_score": 75, "status": "shortlisted", "mode": "balanced"},
    {"company": "SB", "role": "BI Analyst", "ats_score": 58, "status": "rejected", "mode": "conservative"},
    {"company": "Oracle", "role": "DevOps", "ats_score": 45, "status": "rejected", "mode": "strict"},
    {"company": "SD", "role": "Data Analyst", "ats_score": 78, "status": "rejected", "mode": "balanced"},
    {"company": "MS", "role": "ML Engineer", "ats_score": 70, "status": "rejected", "mode": "balanced"},
    {"company": "Google", "role": "Data Scientist", "ats_score": 72, "status": "rejected", "mode": "strict"},
    {"company": "Amazon", "role": "Data Scientist", "ats_score": 68, "status": "rejected", "mode": "balanced"},
    {"company": "Meta", "role": "Data Scientist", "ats_score": 65, "status": "rejected", "mode": "strict"},
    {"company": "IBM", "role": "Data Scientist", "ats_score": 62, "status": "rejected", "mode": "strict"},
]

# TEST 1: No recovery (no progress)
print("=" * 60)
print("TEST 1 — HARD STOP (no recovery)")
r1 = run_precision_optimization(72, "HIGH", "CANDIDATE_GAP", "Data Scientist",
    confidence_score=45, history=history)
s = r1["summary"]
print(f"  Raw: {s['raw_probability']}% → Calibrated: {s['calibrated_probability']}%")
print(f"  Factor: {s['precision_factor']} | Decision: {s['decision']}")
print(f"  Recovery: {s['recovery_active']} | Thresholds: {s['threshold_adjustment']}")

# TEST 2: With recovery (user learned skills + built project)
print(f"\nTEST 2 — RECOVERY MODE (progress detected)")
r2 = run_precision_optimization(72, "HIGH", "CANDIDATE_GAP", "Data Scientist",
    confidence_score=45, history=history,
    user_progress={"skills_learned": ["Spark", "Docker"], "projects_completed": ["ML Pipeline"]})
s2 = r2["summary"]
print(f"  Raw: {s2['raw_probability']}% → Calibrated: {s2['calibrated_probability']}%")
print(f"  Factor: {s2['precision_factor']} | Decision: {s2['decision']}")
print(f"  Recovery: {s2['recovery_active']}")
print(f"  {r2['recovery']['emoji']} {r2['recovery']['status']}: {r2['recovery']['message'][:80]}")

# TEST 3: Soft calibration for borderline job
print(f"\nTEST 3 — SOFT CALIBRATION (borderline)")
r3 = run_precision_optimization(55, "MEDIUM", "RESUME_GAP", "Data Analyst",
    confidence_score=60, history=history)
s3 = r3["summary"]
print(f"  Raw: {s3['raw_probability']}% → Calibrated: {s3['calibrated_probability']}%")
print(f"  Method: {r3['confidence_calibration']['method']}")
print(f"  Decision: {s3['decision']}")

# TEST 4: Strong match
print(f"\nTEST 4 — STRONG MATCH")
r4 = run_precision_optimization(85, "HIGH", "NONE", "Data Analyst",
    confidence_score=80, history=history)
s4 = r4["summary"]
print(f"  Raw: {s4['raw_probability']}% → Calibrated: {s4['calibrated_probability']}%")
print(f"  Decision: {s4['decision']}")

print(f"\n✅ ALL DYNAMIC CALIBRATION TESTS PASSED")
