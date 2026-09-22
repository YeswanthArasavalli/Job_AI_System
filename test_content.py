"""Test Content Quality Engine v4.5 — Recruiter-Level Impact."""
import logging
logging.disable(logging.WARNING)
from pipeline.content_quality import (
    score_signal_strength, score_proof_strength, score_jd_alignment,
    check_lifecycle_coverage, check_ats_optimization,
    validate_rewrite_quality, should_accept_rewrite, generate_bullet_debug,
)

role = "Data Scientist"
jd_skills = ["Python", "SQL", "Spark", "Kubernetes", "MLOps", "TensorFlow", "Pandas"]

# Weak bullets (before)
originals = [
    "Worked on data processing tasks for the team",
    "Helped with building machine learning models",
    "Was responsible for database management and queries",
    "Used Python to analyze data and create reports",
    "Developed automated ETL pipeline using Python and SQL, reducing processing time by 40%",
]

# Strong bullets (after rewrite)
improved = [
    "Built end-to-end data pipeline using Python and SQL, processing 2M+ records daily for 3 teams",
    "Developed predictive ML models using scikit-learn and TensorFlow, achieving 92% accuracy on customer classification",
    "Optimized PostgreSQL queries across production database, reducing query latency by 35% for real-time dashboards",
    "Analyzed customer behavior data using Python and Pandas, enabling data-driven product decisions for stakeholders",
    "Developed automated ETL pipeline using Python and SQL, reducing processing time by 40%",
]

print("=" * 65)
print("CONTENT QUALITY ENGINE v4.5 — RECRUITER-LEVEL")
print("=" * 65)

# 1. Signal + Proof + Alignment per bullet
print("\n📊 MULTI-DIMENSIONAL SCORING:")
for orig, imp in zip(originals, improved):
    s1 = score_signal_strength(orig, jd_skills)
    s2 = score_signal_strength(imp, jd_skills)
    p1 = score_proof_strength(orig)
    p2 = score_proof_strength(imp)
    a1 = score_jd_alignment(orig, jd_skills, role)
    a2 = score_jd_alignment(imp, jd_skills, role)
    changed = "✅" if orig != imp else "="
    print(f"  {changed} Signal {s1['total']:2d}→{s2['total']:2d} | Proof {p1['total']:2d}→{p2['total']:2d} | Align {a1['total']:2d}→{a2['total']:2d} | {imp[:50]}...")

# 2. Combined score gate
print("\n🎯 COMBINED SCORE GATE:")
for orig, imp in zip(originals, improved):
    debug = generate_bullet_debug(orig, imp, jd_skills, role)
    if debug["changed"]:
        gate = should_accept_rewrite(debug)
        status = "✅ ACCEPT" if gate["accept"] else "❌ REJECT"
        print(f"  {status} (+{debug['combined_delta']:.0f}) | {debug['reason']}")

# 3. Lifecycle
print("\n🔄 LIFECYCLE COVERAGE:")
lc = check_lifecycle_coverage(improved, role)
print(f"  {lc['message']}")
print(f"  Covered: {', '.join(lc['covered'])}")
if lc["missing"]:
    print(f"  Missing: {', '.join(lc['missing'])}")

# 4. ATS optimization
print("\n🔍 ATS OPTIMIZATION:")
ats = check_ats_optimization(improved, jd_skills)
print(f"  {ats['message']}")
print(f"  Present: {', '.join(ats['present'][:5])}")
if ats["missing"]:
    print(f"  Missing: {', '.join(ats['missing'])}")

# 5. Full validation
print("\n📋 FULL VALIDATION:")
result = validate_rewrite_quality(originals, improved, jd_skills, role)
d = result["deltas"]
print(f"  Signal: +{d['signal']} | Proof: +{d['proof']} | Align: +{d['align']} | Keywords: +{d['keyword']}")
print(f"  Quality: {result['quality_report']['pass_rate']}% pass rate")
print(f"  Acceptance: {result['acceptance_report']['message']}")
print(f"  {result['summary']}")

print(f"\n✅ v4.5 RECRUITER-LEVEL ENGINE COMPLETE")
