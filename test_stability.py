"""Test Production Stability Engine (v4.3)."""
import logging
logging.disable(logging.WARNING)
from pipeline.stability_engine import run_stability_check, apply_safe_defaults

history = [
    {"company": "SA", "role": "Data Analyst", "ats_score": 81, "status": "shortlisted"},
    {"company": "SC", "role": "Data Analyst", "ats_score": 75, "status": "shortlisted"},
    {"company": "SB", "role": "BI Analyst", "ats_score": 58, "status": "rejected"},
    {"company": "Oracle", "role": "DevOps", "ats_score": 45, "status": "rejected"},
    {"company": "Google", "role": "Data Scientist", "ats_score": 72, "status": "rejected"},
    {"company": "Amazon", "role": "Data Scientist", "ats_score": 68, "status": "rejected"},
    {"company": "Meta", "role": "Data Scientist", "ats_score": 65, "status": "rejected"},
    {"company": "IBM", "role": "Data Scientist", "ats_score": 62, "status": "rejected"},
]

selected = [
    {"company": "X", "role": "Data Analyst", "calibrated_probability": 56, "selection_reason": "primary"},
    {"company": "Y", "role": "ML Engineer", "calibrated_probability": 42, "selection_reason": "diversity_fill"},
    {"company": "Z", "role": "DevOps", "calibrated_probability": 28, "selection_reason": "momentum_force"},
]

evals = [
    {"company": "X", "role": "Data Analyst", "shortlist_probability": 72},
    {"company": "Y", "role": "ML Engineer", "shortlist_probability": 55},
    {"company": "", "role": "Unknown", "shortlist_probability": 30},  # bad data
    {"company": "X", "role": "Data Analyst", "shortlist_probability": 72},  # duplicate
]

exploration_hist = [
    {"role": "BI Analyst", "status": "rejected", "selection_reason": "diversity_fill"},
    {"role": "DevOps", "status": "rejected", "selection_reason": "adjacent_domain"},
]

result = run_stability_check(
    evaluations=evals,
    selected_jobs=selected,
    domain_weights={"data analyst": 8, "data scientist": -3, "ml engineer": 0},
    history=history,
    exploration_history=exploration_hist,
    momentum_active=True,
    current_budget=1,
    agent_output={"selection": {}, "plan": {}, "summary": {}},
)

print("=" * 60)
print("PRODUCTION STABILITY ENGINE v4.3")
print("=" * 60)

s = result["summary"]
print(f"\n📊 Stability: {s['stability']}")
print(f"📉 Drift: {s['drift']}")
print(f"🧠 Learning: {s['learning']}")
print(f"⚠️ Risks: {s['risks']}")
print(f"🗑️ Quality rejected: {s['quality_rejected']}")

dg = result["diversity_guard"]
print(f"\n🛡️ DIVERSITY GUARD: {dg['count_removed']} removed")
for j in dg["rejected_jobs"]:
    print(f"  ❌ {j['company']} ({j.get('guard_rejection','')})")

ws = result["weight_scaling"]
print(f"\n📐 WEIGHT SCALING:")
for d in ws["scaled_weights"]:
    print(f"  {d}: raw={ws['raw_weights'].get(d,0)} → scaled={ws['scaled_weights'][d]} (conf: {ws['confidence_factors'].get(d,0)})")

nl = result["negative_learning"]
if nl["penalties_applied"]:
    print(f"\n📉 NEGATIVE LEARNING: {nl['penalties_applied']}")

ms = result["momentum_safety"]
print(f"\n🛡️ MOMENTUM SAFETY: {ms['removed']} unsafe removed")

et = result["exploration_tuning"]
print(f"\n🧪 EXPLORATION: {et['message']}")

ls = result["learning_stability"]
print(f"\n🧠 STABILITY: {ls['message']} (variance: {ls['variance']})")

dq = result["data_quality"]
print(f"\n📋 DATA QUALITY: {dq['rejected_count']} rejected")
for r in dq["rejected"]:
    print(f"  ❌ {r.get('company','?')}: {r.get('quality_issue','')}")

cd = result["calibration_drift"]
print(f"\n📉 DRIFT: {cd['message']}")

# Safe defaults test
print(f"\n🔒 SAFE DEFAULTS:")
for dec, prob in [("APPLY", 50), ("BLOCKED", 42), ("APPLY", 70)]:
    sd = apply_safe_defaults(dec, prob)
    arrow = "→" if sd["changed"] else "="
    print(f"  {dec} @ {prob}% {arrow} {sd['decision']} ({sd['reason']})")

for flag in result["risk_flags"]:
    print(f"  🚩 {flag}")

print(f"\n✅ STABILITY ENGINE COMPLETE")
