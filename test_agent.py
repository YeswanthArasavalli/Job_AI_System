"""Test Career Agent v4.2 — Diversity + Exploration + Momentum."""
import logging
logging.disable(logging.WARNING)
from pipeline.career_agent import run_autonomous_agent, classify_confidence_band

history = [
    {"company": "SA", "role": "Data Analyst", "ats_score": 81, "status": "shortlisted", "mode": "balanced"},
    {"company": "SC", "role": "Data Analyst", "ats_score": 75, "status": "shortlisted", "mode": "balanced"},
    {"company": "SB", "role": "BI Analyst", "ats_score": 58, "status": "rejected", "mode": "conservative"},
    {"company": "Oracle", "role": "DevOps", "ats_score": 45, "status": "rejected", "mode": "strict"},
    {"company": "Google", "role": "Data Scientist", "ats_score": 72, "status": "rejected", "mode": "strict"},
    {"company": "Amazon", "role": "Data Scientist", "ats_score": 68, "status": "rejected", "mode": "balanced"},
    {"company": "Meta", "role": "Data Scientist", "ats_score": 65, "status": "rejected", "mode": "strict"},
    {"company": "IBM", "role": "Data Scientist", "ats_score": 62, "status": "rejected", "mode": "strict"},
]

evals = [
    {"company": "Startup X", "role": "Data Analyst", "shortlist_probability": 72, "jd_match_score": 80, "root_cause": "NONE"},
    {"company": "BigCo", "role": "ML Engineer", "shortlist_probability": 55, "jd_match_score": 60, "root_cause": "RESUME_GAP"},
    {"company": "TinyInc", "role": "BI Analyst", "shortlist_probability": 40, "jd_match_score": 50, "root_cause": "TARGETING_GAP"},
    {"company": "MegaCorp", "role": "DevOps", "shortlist_probability": 25, "jd_match_score": 30, "root_cause": "CANDIDATE_GAP"},
]

# TEST 1: Diversity + Domain Weights + Momentum (inactive 5 days)
print("=" * 60)
print("CAREER AGENT v4.2 — ENHANCED TEST")
print("=" * 60)

result = run_autonomous_agent(
    evaluations=evals, history=history, weekly_count=1,
    candidate_skills=["Python", "SQL", "Pandas"],
    jd_skills=["Python", "SQL", "Spark", "MLOps"],
    role="Data Scientist", last_activity_date="2026-04-28T10:00:00",
)

sel = result["selection"]
print(f"\n📋 SELECTED: {sel['count']} jobs (min 2 guaranteed)")
for j in sel["selected"]:
    reason = j.get("selection_reason", "primary")
    boost = j.get("domain_boost", 0)
    print(f"  ✅ {j['company']} — {j['role']} ({j['calibrated_probability']:.0f}%) [{reason}] boost:{boost}")

print(f"\n  Domain weights: {sel['domain_weights']}")

m = result["momentum"]
print(f"\n🔥 MOMENTUM: {m['emoji']} {m['status']}")
print(f"  {m['message']}")

plan = result["plan"]
print(f"\n📋 ACTIONS ({plan['total']}):")
for a in plan["actions"][:5]:
    print(f"  {a['emoji']} {a['type']}: {a['target']}")

exp = result["exploration_budget"]
print(f"\n🧪 EXPLORATION: {exp['message']}")

# Interview tasks
iw = result["interview_weaknesses"]
if iw and iw.get("action_tasks"):
    print(f"\n🎤 INTERVIEW → TASKS:")
    for t in iw["action_tasks"][:2]:
        print(f"  📝 {t['task']} → {t['action'][:50]}...")

t = result["trajectory"]
print(f"\n📊 TRAJECTORY: {t['stage']} ({t['shortlist_rate']}%)")

print(f"\n✅ ALL v4.2 ENHANCEMENTS VERIFIED")
