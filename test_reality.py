"""Test the Reality Validation Engine."""
import logging
logging.disable(logging.WARNING)

from pipeline.reality_validation import run_reality_validation, enforce_application_control

# Simulate a realistic history with mixed outcomes
history = [
    {"company": "Google", "role": "Data Scientist", "ats_score": 72, "status": "rejected", "mode": "strict"},
    {"company": "Amazon", "role": "ML Engineer", "ats_score": 68, "status": "rejected", "mode": "balanced"},
    {"company": "Startup A", "role": "Data Analyst", "ats_score": 81, "status": "shortlisted", "mode": "balanced"},
    {"company": "Meta", "role": "Data Scientist", "ats_score": 65, "status": "rejected", "mode": "strict"},
    {"company": "Microsoft", "role": "ML Engineer", "ats_score": 70, "status": "rejected", "mode": "balanced"},
    {"company": "Startup B", "role": "BI Analyst", "ats_score": 58, "status": "rejected", "mode": "conservative"},
    {"company": "Startup C", "role": "Data Analyst", "ats_score": 75, "status": "shortlisted", "mode": "balanced"},
    {"company": "IBM", "role": "Data Scientist", "ats_score": 62, "status": "rejected", "mode": "strict"},
    {"company": "Oracle", "role": "DevOps", "ats_score": 45, "status": "rejected", "mode": "strict"},
    {"company": "Startup D", "role": "Data Analyst", "ats_score": 78, "status": "rejected", "mode": "balanced"},
]

print("=" * 60)
print("REALITY VALIDATION ENGINE TEST")
print("=" * 60)

result = run_reality_validation(
    history,
    user_progress={"skills_learned": ["Docker"], "projects_completed": []},
    current_probability=35.0,
)

# System Health
print(f"\n🏥 SYSTEM HEALTH: {result['system_health']}")

# Prediction Accuracy
pa = result["prediction_accuracy"]
print(f"\n📊 PREDICTION ACCURACY:")
print(f"  Accuracy: {pa['accuracy']}%")
print(f"  Precision: {pa['precision']}%")
print(f"  Recall: {pa['recall']}%")
print(f"  HIGH → Shortlisted: {pa['high_conversion_rate']}% ({pa['high_total']} predictions)")
print(f"  LOW → Rejected: {pa['low_rejection_rate']}% ({pa['low_total']} predictions)")
print(f"  Resolved: {pa['total_resolved']}")

# Reality Alignment
ra = result["reality_alignment"]
print(f"\n📈 REALITY ALIGNMENT: {ra['alignment']}")
print(f"  {ra['summary']}")
for issue in ra.get("issues", []):
    print(f"  [{issue['severity']}] {issue['detail']}")

# Application Control
ac = result["application_control"]
if ac:
    print(f"\n🚫 APPLICATION CONTROL:")
    print(f"  {ac['emoji']} {ac['status']}: {ac['message']}")

# Root Cause
rc = result["root_cause_validated"]
print(f"\n🧠 VALIDATED ROOT CAUSE: {rc['validated_cause']} (confidence: {rc['confidence']}%)")
for ev in rc["evidence"]:
    print(f"  • {ev}")

# Capability
cap = result["capability_progress"]
print(f"\n📈 CAPABILITY: {cap['status']}")
print(f"  {cap['message']}")
for ev in cap.get("evidence", []):
    print(f"  • {ev}")

# Mandatory Actions
ma = result["mandatory_actions"]
print(f"\n🔥 MANDATORY ACTIONS ({ma['total_actions']}):")
for a in ma["actions"]:
    print(f"  [{a['priority']}] {a['type']}: {a['action']}")

# Self-Corrections
sc = result["self_corrections"]
print(f"\n⚙️ SELF-CORRECTIONS: {'Needed' if sc['needs_correction'] else 'None needed'}")
for c in sc.get("corrections", []):
    print(f"  {c['parameter']}: {c['current']} → {c['recommended']}")

# Test application control at different probabilities
print(f"\n🚦 APPLICATION CONTROL GATES:")
for prob in [25, 42, 65, 80]:
    ctrl = enforce_application_control(prob)
    print(f"  {prob}%: {ctrl['emoji']} {ctrl['status']}")

print(f"\n✅ REALITY VALIDATION COMPLETE")
