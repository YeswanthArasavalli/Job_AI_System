"""Test Quality Gate — Truth + Quality + ATS + Consistency."""
import logging
logging.disable(logging.WARNING)
from pipeline.quality_gate import (
    validate_rewrite, check_bullet_quality, validate_all_bullets,
    enforce_recruiter_quality, compute_real_ats_metrics,
    compute_output_hash, verify_output_consistency,
    run_quality_gate,
)

print("=" * 65)
print("QUALITY GATE TEST")
print("=" * 65)

# ── Part 1: Truth Constraints ──
print("\n🔒 TRUTH CONSTRAINTS:")
tests = [
    ("Built data pipeline using Python",
     "Built data pipeline using Python and AWS Lambda",
     ["Python"], "Injected AWS Lambda"),
    ("Trained ML model for classification",
     "Trained ML model for classification, improving accuracy by 45%",
     ["Python", "scikit-learn"], "Fabricated metric"),
    ("Developed data processing workflow",
     "Developed data processing workflow, improving data quality",
     ["Python", "SQL"], "Safe rephrase"),
    ("Analyzed sales data",
     "Analyzed sales data to identify trends and support business decisions",
     ["SQL", "Python"], "Safe expansion"),
    ("Built web app",
     "Deployed microservices on Kubernetes with Terraform using GraphQL",
     [], "Complete semantic drift"),
]
for orig, rewrite, skills, label in tests:
    r = validate_rewrite(orig, rewrite, skills)
    status = "✅ ACCEPT" if r["accepted"] else "❌ REJECT"
    print(f"  {label:25s}: {status}")
    if r["violations"]:
        for v in r["violations"]:
            print(f"    → {v}")

# ── Part 2: Bullet Quality ──
print("\n📋 BULLET QUALITY:")
bullets = [
    "Built data pipeline using Python for processing, improving data quality.",
    "worked on data analysis using pandas, utilizing numpy, applying scikit-learn, leveraging tensorflow.",
    "Analyzed data data data data using Python for data processing.",
    "Built pipeline.. deployed services.",
    "data processing and modeling",
    "Developed automated ETL workflow to improve data availability.",
]
for b in bullets:
    r = check_bullet_quality(b)
    status = "✅" if r["passed"] else "❌"
    print(f"  {status} {b[:65]}")
    if r["issues"]:
        for issue in r["issues"]:
            print(f"      → {issue}")

# ── Part 3: Recruiter Quality ──
print("\n👔 RECRUITER QUALITY:")
weak = [
    "Was responsible for data pipeline development",
    "Worked on model training and evaluation",
    "Handled deployment of ML models",
    "Built automated testing framework for CI/CD pipeline",
]
for b in weak:
    r = enforce_recruiter_quality(b)
    if r["changed"]:
        print(f"  ❌ {r['original']}")
        print(f"  ✅ {r['improved']}")
    else:
        print(f"  ✅ {b[:60]} (already good)")

# ── Part 4: Real ATS Metrics ──
print("\n📊 REAL ATS METRICS:")
resume = (
    "Built data pipeline using Python and SQL for processing large datasets. "
    "Developed predictive ML models using TensorFlow and scikit-learn. "
    "Managed PostgreSQL databases and optimized query performance. "
    "Created interactive dashboards using Tableau for stakeholder reporting."
)
jd_kw = ["Python", "SQL", "TensorFlow", "scikit-learn", "Docker",
          "Kubernetes", "Spark", "Tableau", "PostgreSQL", "Airflow"]
ats = compute_real_ats_metrics(resume, jd_kw)
print(f"  Coverage: {ats['keyword_coverage']}% ({ats['keywords_found']}/{ats['keywords_found']+ats['keywords_missing']})")
print(f"  Contextual: {ats['contextual_usage']}%")
print(f"  Distribution: {ats['distribution_score']}")
print(f"  Found: {', '.join(ats['found'])}")
print(f"  Missing: {', '.join(ats['missing'])}")

# ── Part 5: Output Consistency ──
print("\n🔗 OUTPUT CONSISTENCY:")
out_a = {"decision": "APPLY", "score": 72, "bullets": ["a", "b"]}
out_b = {"decision": "APPLY", "score": 72, "bullets": ["a", "b"]}
out_c = {"decision": "SKIP", "score": 72, "bullets": ["a", "b"]}
r1 = verify_output_consistency(out_a, out_b)
r2 = verify_output_consistency(out_a, out_c)
print(f"  Same outputs:  {r1['message']} (hash={r1['hash_a']})")
print(f"  Diff outputs:  {r2['message']}")

# ── Part 6: Full Quality Gate ──
print("\n📊 FULL QUALITY GATE:")
originals = [
    "Built data pipeline using Python",
    "Trained ML model for classification",
    "Analyzed sales data",
    "Handled deployment tasks",
    "Created dashboard for reporting",
]
rewrites = [
    "Built data pipeline using Python, improving data quality.",
    "Trained ML model for classification, improving accuracy by 87%.",
    "Analyzed sales data using AWS Lambda and Kubernetes.",
    "Managed deployment tasks, ensuring system reliability.",
    "Created interactive dashboard for stakeholder reporting.",
]
candidate_skills = ["Python", "SQL", "scikit-learn", "TensorFlow"]
jd_keywords = ["Python", "SQL", "TensorFlow", "Docker", "Kubernetes"]

gate = run_quality_gate(originals, rewrites, candidate_skills, jd_keywords)
s = gate["summary"]
print(f"  Accepted: {s['accepted']}/{s['total']}")
print(f"  Rejected: {s['rejected']}")
print(f"  Recruiter fixed: {s['recruiter_fixed']}")
print(f"  ATS coverage: {s['ats_coverage']}%")
print(f"  Quality rate: {s['quality_pass_rate']}%")
if gate["rejected_rewrites"]:
    print(f"  Rejections:")
    for rej in gate["rejected_rewrites"]:
        print(f"    [{rej['index']}] {rej['reason']}")
print(f"\n  Safe bullets:")
for i, b in enumerate(gate["safe_bullets"]):
    print(f"    {i}: {b}")

print(f"\n✅ QUALITY GATE COMPLETE")
