"""Test Adaptive Engine (v5.0)."""
import logging
logging.disable(logging.WARNING)
from pipeline.adaptive_engine import (
    generate_recovery_plan, check_exploration_band,
    recruiter_boost_rewrite, compute_delta,
    check_job_fit_override, compute_adaptive_decision,
    run_adaptive_engine,
)

jd_keywords = ["Python", "SQL", "Spark", "Kubernetes", "MLOps",
                "TensorFlow", "Pandas", "Docker", "Airflow", "PostgreSQL"]
jd_skills = ["Python", "SQL", "TensorFlow", "Pandas", "Spark"]
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
print("ADAPTIVE ENGINE v5.0")
print("=" * 65)

# Part 1: Recovery plan
print("\n🔄 RECOVERY PLAN (after SKIP):")
recovery = generate_recovery_plan(
    missing_keywords=["Spark", "Kubernetes", "MLOps"],
    bullets=bullets, signal_scores=[30, 25, 20, 35, 40],
    proof_scores=[5, 8, 3, 6, 10], jd_skills=jd_skills, role="Data Scientist",
)
for step in recovery["steps"]:
    print(f"  → {step}")
print(f"  Missing: {recovery['top_missing_keywords']}")
print(f"  Project: {recovery['project_idea']}")
print(f"  Priority: {recovery['priority']}")

# Part 2: Exploration band
print("\n🧪 EXPLORATION BAND:")
for cov in [42, 38, 55, 25]:
    exp = check_exploration_band(cov)
    status = "✅ ENABLED" if exp["enabled"] else "❌ disabled"
    print(f"  {cov}% → {status} ({exp['reason'][:50]})")

# Part 3: Recruiter boost
print("\n💪 RECRUITER BOOST MODE:")
weak_bullets = [
    "worked on data pipeline development",
    "responsible for model training and evaluation",
    "helped with deploying services to cloud",
    "involved in dashboard reporting",
]
for wb in weak_bullets:
    result = recruiter_boost_rewrite(wb)
    if result["changed"]:
        print(f"  ❌ {result['original']}")
        print(f"  ✅ {result['improved']}")
        print(f"     Changes: {', '.join(result['changes'])}")
        print()

# Part 4: Delta tracking
print("📊 DELTA TRACKING:")
delta = compute_delta(
    old_scores={"signal": 30, "proof": 6, "alignment": 9, "recruiter": 44, "coverage": 38},
    new_scores={"signal": 38, "proof": 8, "alignment": 14, "recruiter": 56, "coverage": 45},
)
print(f"  Total delta: {delta['total_delta']}")
for dim, val in delta["dimensions"].items():
    print(f"    {dim}: {val:+.1f}")
esc = delta["escalation"]
print(f"  Escalation: {'NEEDED' if esc['needed'] else 'OK'} — {esc['reason']}")

# Part 5: Job-fit override
print("\n🎯 JOB-FIT OVERRIDE:")
tests = [
    (["Python", "SQL", "Pandas", "TensorFlow"], 42, "SKIP", "Strong fit low ATS"),
    (["Python"], 42, "SKIP", "Weak fit low ATS"),
    (["Python", "SQL", "Pandas"], 55, "APPLY (FIX GAPS)", "Good fit ok ATS"),
]
for skills, cov, dec, label in tests:
    fit = check_job_fit_override(skills, jd_skills, cov, dec)
    print(f"  {label:25s}: overlap={fit['skill_overlap']}% "
          f"override={'✅' if fit['override_triggered'] else '❌'} → {fit['new_decision']}")

# Part 6: Adaptive decision
print("\n📋 ADAPTIVE DECISION ENGINE:")
scenarios = [
    (75, 70, 65, "Strong match"),
    (55, 55, 45, "Partial + weak recruiter"),
    (40, 35, 30, "Exploration band"),
    (25, 20, 15, "Hard skip"),
    (42, 30, 25, "Fit override"),
]
for cov, prob, rec, label in scenarios:
    d = compute_adaptive_decision(cov, prob, rec, candidate_skills, jd_skills)
    print(f"  {label:22s}: {d['final']:22s} (base={d['base_decision']}, conf={d['confidence']}%)")
    if d["modifiers"]:
        for m in d["modifiers"]:
            print(f"    ↳ {m}")

# Part 7: Full orchestration
print("\n📊 FULL ADAPTIVE ENGINE (weak candidate):")
full = run_adaptive_engine(
    bullets=bullets, jd_keywords=jd_keywords, jd_skills=jd_skills,
    candidate_skills=candidate_skills,
    missing_keywords=["Spark", "Kubernetes", "MLOps"],
    role="Data Scientist", real_coverage=38, shortlist_prob=40,
    recruiter_avg=44, signal_scores=[30, 25, 20, 35, 40],
    proof_scores=[5, 8, 3, 6, 10], align_scores=[9, 12, 5, 8, 15],
)
d = full["decision"]
print(f"  Decision: {d['final']} ({d['confidence']}% conf)")
print(f"  Reason: {d['reason']}")
print(f"  Signals: {d['signals']}")
if d["modifiers"]:
    for m in d["modifiers"]:
        print(f"  Modifier: {m}")
if full["recovery_plan"]:
    print(f"  Recovery: {len(full['recovery_plan']['steps'])} steps")
    for s in full["recovery_plan"]["steps"]:
        print(f"    → {s}")
exp = full["exploration"]
print(f"  Exploration: {'ON' if exp['enabled'] else 'OFF'} ({exp['reason'][:50]})")
dt = full["delta"]
print(f"  Delta: {dt['total_delta']} ({', '.join(f'{k}:{v:+.0f}' for k,v in dt['dimensions'].items())})")
imp = full["improvements"]
print(f"  Boosted: {imp['bullets_boosted']} bullets")

# Strong candidate test
print("\n📊 FULL ADAPTIVE ENGINE (strong candidate):")
strong = run_adaptive_engine(
    bullets=bullets, jd_keywords=jd_keywords, jd_skills=jd_skills,
    candidate_skills=candidate_skills, role="Data Scientist",
    real_coverage=72, shortlist_prob=68, recruiter_avg=65,
)
d = strong["decision"]
print(f"  Decision: {d['final']} ({d['confidence']}% conf)")
print(f"  Recovery: {'YES' if strong['recovery_plan'] else 'NONE'}")

print(f"\n✅ ADAPTIVE ENGINE v5.0 COMPLETE")
