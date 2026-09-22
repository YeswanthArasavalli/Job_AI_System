"""Test Optimization Engine (v4.9)."""
import logging
logging.disable(logging.WARNING)
from pipeline.optimization_engine import (
    assess_ats_status, iterative_ats_optimization,
    assess_recruiter_strength, compute_strict_decision,
    improve_bullet_phrasing, strengthen_project_bullet,
    add_safe_impact, run_optimization_engine,
)
from pipeline.ats_hardening import simulate_ats_parser

jd_keywords = ["Python", "SQL", "Spark", "Kubernetes", "MLOps",
                "TensorFlow", "Pandas", "Docker", "Airflow", "PostgreSQL"]
jd_skills = ["Python", "SQL", "TensorFlow", "Pandas"]
candidate_skills = ["Python", "SQL", "Pandas", "scikit-learn", "Docker",
                    "PostgreSQL", "TensorFlow", "Airflow"]
bullets = [
    "Built data processing pipeline using Python and SQL",
    "Developed predictive ML models using TensorFlow",
    "Managed PostgreSQL databases and optimized query performance",
    "Analyzed data using Python and Pandas",
    "Developed automated ETL pipeline using Airflow and Docker",
]

print("=" * 65)
print("OPTIMIZATION ENGINE v4.9")
print("=" * 65)

# Part 1: ATS status
print("\n📡 ATS COVERAGE ENFORCEMENT:")
for cov in [75, 55, 35, 20]:
    s = assess_ats_status(cov)
    print(f"  {cov}% → {s['status']:12s} action={s['action']}")

# Part 2: Iterative ATS loop
print("\n🔄 ITERATIVE ATS OPTIMIZATION:")
ats = iterative_ats_optimization(
    bullets=bullets, jd_keywords=jd_keywords,
    candidate_skills=candidate_skills,
    simulate_ats_fn=simulate_ats_parser,
    max_attempts=3, target_coverage=70.0,
)
print(f"  Initial: {ats['initial_coverage']:.0f}%")
print(f"  Final:   {ats['final_coverage']:.0f}%")
print(f"  Attempts: {ats['attempts']}")
print(f"  Status: {ats['status']}")
print(f"  Added: {', '.join(ats['keywords_added']) if ats['keywords_added'] else 'none'}")
for t in ats["coverage_trace"]:
    injected = t.get("injected", [])
    print(f"    Attempt {t['attempt']}: {t['coverage']:.0f}% ({t['parsed']} parsed)"
          + (f" +{', '.join(injected)}" if injected else ""))

# Part 3: Recruiter assessment
print("\n🎯 RECRUITER ASSESSMENT:")
for score in [72, 55, 42, 28]:
    r = assess_recruiter_strength(score)
    print(f"  score={score} → {r['assessment']:10s} grade={r['grade']}")

# Part 4: Decision engine
print("\n📋 STRICT DECISION ENGINE:")
tests = [
    (75, 70, 65, "Strong match"),
    (55, 55, 50, "Partial match"),
    (60, 45, 40, "Below threshold"),
    (30, 25, 20, "ATS block"),
]
for cov, prob, rec, label in tests:
    d = compute_strict_decision(cov, prob, rec)
    print(f"  {label:18s}: {d['final']:20s} ({d['confidence']}% conf)")
    print(f"    Signals: {d['signals']}")

# Part 5: Bullet improvement
print("\n✏️ CAPABILITY-AWARE IMPROVEMENT:")
weak_bullets = [
    "worked on data processing",
    "helped with model training",
    "made a dashboard for reporting",
]
for wb in weak_bullets:
    result = improve_bullet_phrasing(wb, jd_skills)
    if result["changed"]:
        print(f"  ❌ {result['original']}")
        print(f"  ✅ {result['improved']}")

# Part 6: Fresher project
print("\n🎓 FRESHER PROJECT STRENGTHENING:")
proj_bullets = [
    "did ML project for churn prediction",
    "created sentiment analysis model",
]
proj_tools = [["XGBoost", "Python", "Pandas"], ["BERT", "Python"]]
for i, pb in enumerate(proj_bullets):
    result = strengthen_project_bullet(pb, proj_tools[i])
    if result["changed"]:
        print(f"  ❌ {result['original']}")
        print(f"  ✅ {result['improved']}")

# Part 7: Safe impact
print("\n💪 SAFE IMPACT ENHANCEMENT:")
no_impact = [
    "Built automated data pipeline",
    "Trained classification model using XGBoost",
]
for b in no_impact:
    result = add_safe_impact(b)
    if result["changed"]:
        print(f"  ❌ {b}")
        print(f"  ✅ {result['improved']}")

# Part 8: Full orchestration
print("\n📊 FULL OPTIMIZATION ENGINE:")
full = run_optimization_engine(
    bullets=bullets, jd_keywords=jd_keywords, jd_skills=jd_skills,
    candidate_skills=candidate_skills, role="Data Scientist",
    is_fresher=False, shortlist_prob=62, recruiter_avg=48,
)
a = full["ats"]
print(f"  ATS: {a['initial_coverage']:.0f}% → {a['real_coverage']:.0f}% ({a['attempts']} attempts, {a['status']})")
r = full["recruiter"]
print(f"  Recruiter: {r['score']} ({r['assessment']}, grade {r['grade']})")
d = full["decision"]
print(f"  Decision: {d['final']} — {d['reason']}")
print(f"  Signals: {d['signals']}")
imp = full["improvements"]
print(f"  Improvements: {imp['bullets_enhanced']} bullets, {imp['impact_added']} impacts, {len(imp['keywords_added'])} keywords")

# Fresher test
print("\n📊 FRESHER OPTIMIZATION:")
fresher = run_optimization_engine(
    bullets=["Worked on data analysis", "Made prediction model"],
    jd_keywords=["Python", "SQL", "Pandas", "scikit-learn"],
    jd_skills=["Python", "SQL"],
    candidate_skills=["Python", "SQL", "Pandas", "scikit-learn"],
    role="Data Analyst", is_fresher=True,
    project_bullets=proj_bullets, project_tools=proj_tools,
    shortlist_prob=35, recruiter_avg=30,
)
print(f"  ATS: {fresher['ats']['initial_coverage']:.0f}% → {fresher['ats']['real_coverage']:.0f}%")
print(f"  Decision: {fresher['decision']['final']}")
print(f"  Improvements: {fresher['improvements']}")

print(f"\n✅ OPTIMIZATION ENGINE v4.9 COMPLETE")
