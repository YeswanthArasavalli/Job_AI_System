"""Test Bullet Rewriter — Strong bullet generation."""
import logging
logging.disable(logging.WARNING)
from pipeline.bullet_rewriter import rewrite_bullet, rewrite_all_bullets, _score_bullet

print("=" * 65)
print("BULLET REWRITER TEST")
print("=" * 65)

skills = ["Python", "SQL", "TensorFlow", "scikit-learn", "Pandas", "PostgreSQL"]

# ── Part 1: Weak bullets → Strong bullets ──
print("\n📝 WEAK → STRONG REWRITES:")
weak_bullets = [
    "Worked on churn prediction model",
    "Did data processing",
    "Helped with building the dashboard",
    "Used Python for data analysis",
    "Was responsible for database management",
    "Set up automated testing",
    "Looked at data to find problems",
    "Handled deployment of services",
    "Made an API for the team",
    "Ran experiments on different models",
]
for b in weak_bullets:
    r = rewrite_bullet(b, skills)
    status = "✅" if r["accepted"] else "❌"
    print(f"\n  {status} Score: {r['quality_score']}/10")
    print(f"     IN:  {r['original']}")
    print(f"     OUT: {r['rewritten']}")
    print(f"     Why: {r['improvement_reason']}")

# ── Part 2: Already strong bullets (should stay mostly unchanged) ──
print("\n\n💪 ALREADY STRONG (should preserve):")
strong_bullets = [
    "Built end-to-end data pipeline using Python and SQL, improving data availability for analytics teams.",
    "Developed predictive churn model using scikit-learn, enabling proactive customer retention.",
    "Designed interactive dashboard using Tableau to provide executives with real-time KPIs.",
]
for b in strong_bullets:
    r = rewrite_bullet(b, skills)
    changed = "CHANGED" if r["rewritten"] != r["original"] else "KEPT"
    print(f"  [{changed}] Score: {r['quality_score']}/10 — {b[:60]}")

# ── Part 3: Edge cases ──
print("\n\n⚠️ EDGE CASES:")
edges = [
    ("Too short", "Data work"),
    ("Fragment", "processing and modeling"),
    ("Already perfect", "Led migration of 500K records to PostgreSQL, reducing query latency and improving data access."),
]
for label, b in edges:
    r = rewrite_bullet(b, skills)
    status = "✅" if r["accepted"] else "❌"
    print(f"  {label:18s}: {status} score={r['quality_score']}/10 — {r['rewritten'][:65]}")

# ── Part 4: Batch rewrite ──
print("\n\n📊 BATCH REWRITE:")
all_bullets = [
    "Worked on data pipeline using Python",
    "Did model training for classification",
    "Helped with report generation",
    "Built automated ETL process for data warehouse",
    "Used SQL for complex data queries",
    "Was responsible for production deployments",
    "Created data visualization dashboards",
    "Handled API development and testing",
]
batch = rewrite_all_bullets(all_bullets, skills)
print(f"  Accepted: {batch['accepted']}/{len(all_bullets)}")
print(f"  Rejected: {batch['rejected']}")
print(f"  Avg Score: {batch['avg_score']}/10")
print(f"\n  Final bullets:")
for i, b in enumerate(batch["final_bullets"]):
    r = batch["results"][i]
    tag = "✅" if r["accepted"] else "⏸️"
    print(f"    {tag} [{r['quality_score']}] {b}")

# ── Part 5: Outcome variety check ──
print("\n\n🎯 OUTCOME VARIETY CHECK:")
data_bullets = [
    "Worked on data ingestion pipeline",
    "Did data preprocessing",
    "Handled data cleaning tasks",
    "Managed database operations",
]
results = rewrite_all_bullets(data_bullets, skills)
outcomes_used = set()
for r in results["results"]:
    # Extract outcome portion
    if "," in r["rewritten"]:
        outcome = r["rewritten"].rsplit(",", 1)[-1].strip()
        outcomes_used.add(outcome)
print(f"  {len(data_bullets)} data bullets → {len(outcomes_used)} unique outcomes")
for o in outcomes_used:
    print(f"    • {o}")

# ── Part 6: No tool injection check ──
print("\n\n🔒 TRUTH CONSTRAINT CHECK:")
r1 = rewrite_bullet("Did data processing", ["Python"])
print(f"  Original: 'Did data processing'")
print(f"  Rewrite:  '{r1['rewritten']}'")
# Check no new tools were added
has_new_tool = any(t in r1["rewritten"].lower() for t in
    ["aws", "azure", "docker", "kubernetes", "spark", "kafka"])
print(f"  New tools injected: {'YES ❌' if has_new_tool else 'NO ✅'}")

print(f"\n✅ BULLET REWRITER TEST COMPLETE")
