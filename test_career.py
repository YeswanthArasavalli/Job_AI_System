"""Test Career Intelligence Layer (v4.0)."""
import logging
logging.disable(logging.WARNING)
from pipeline.career_intelligence import run_career_intelligence

history = [
    {"company": "Google", "role": "Data Scientist", "ats_score": 72, "status": "rejected"},
    {"company": "Amazon", "role": "Data Scientist", "ats_score": 68, "status": "rejected"},
    {"company": "Startup A", "role": "Data Analyst", "ats_score": 81, "status": "shortlisted"},
    {"company": "Meta", "role": "Data Scientist", "ats_score": 65, "status": "rejected"},
    {"company": "MS", "role": "ML Engineer", "ats_score": 70, "status": "rejected"},
    {"company": "SC", "role": "Data Analyst", "ats_score": 75, "status": "shortlisted"},
    {"company": "IBM", "role": "Data Scientist", "ats_score": 62, "status": "rejected"},
    {"company": "Oracle", "role": "DevOps", "ats_score": 45, "status": "rejected"},
]

result = run_career_intelligence(
    history=history,
    user_progress={
        "skills_learned": ["Docker"],
        "projects_completed": ["ML Pipeline"],
        "github_links": ["github.com/user/ml-pipeline"],
        "resume_updated": True,
    },
    role="Data Scientist",
    experience_level="1-3 yrs",
    candidate_skills=["Python", "SQL", "Pandas", "Scikit-learn", "PyTorch"],
    jd_skills=["Python", "SQL", "Spark", "Kubernetes", "MLOps", "TensorFlow"],
)

print("=" * 60)
print("CAREER INTELLIGENCE v4.0")
print("=" * 60)

# Execution
e = result["execution"]
print(f"\n📋 EXECUTION: {e['readiness']} (score: {e['execution_score']}/100)")
print(f"  {e['message']}")
for g in e["remaining_gaps"]:
    print(f"  ❌ {g}")
for f in e["quality_flags"]:
    print(f"  ⚠️ {f}")

# Market
m = result["market"]
print(f"\n🌍 MARKET: {m['competition_level']} competition (factor: {m['competition_factor']})")
print(f"  Density: {m['applicant_density']}")
print(f"  Skill coverage: {m['skill_coverage']}%")
for a in m["positioning_advice"]:
    print(f"  → {a}")

# Interview
i = result["interview"]
print(f"\n🎤 INTERVIEW: {i['readiness']} (score: {i['conversion_score']})")
print(f"  Matched: {i['matched_skills']} | Gaps: {i['gap_skills']}")
for r in i["risks"]:
    print(f"  [{r['severity']}] {r['area']}: {r['detail']}")
for t in i["key_topics"][:3]:
    print(f"  📚 {t}")

# Pipeline
p = result["pipeline"]
print(f"\n📊 PIPELINE BOTTLENECK: {p['bottleneck']}")
print(f"  {p['bottleneck_detail']}")
r = p["pipeline_rates"]
print(f"  Apps: {r['applications']} → Shortlisted: {r['shortlisted']} ({r['shortlist_rate']}%)")
if p["trajectory"]:
    print(f"  ⏱️ {p['trajectory']['message']}")
for step in p["career_plan"]:
    print(f"  {step}")

print(f"\n✅ CAREER INTELLIGENCE COMPLETE")
