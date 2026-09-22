from pipeline.bullet_rewriter import rewrite_bullet
tests = [
    "Built data pipeline, utilizing Python and SQL.",
    "Developed models, leveraging TensorFlow and PyTorch.",
    "Analyzed data, applying Pandas and NumPy.",
    "Normal bullet without template phrases.",
]
print("TEMPLATE PHRASE REMOVAL TEST:")
all_ok = True
for b in tests:
    r = rewrite_bullet(b)
    rw = r["rewritten"]
    has_template = any(w in rw.lower() for w in ["utilizing", "leveraging"])
    # "applying" in original is OK — only flag if it was a template pattern
    if "utilizing" in b.lower() or "leveraging" in b.lower():
        status = "❌ STILL HAS" if has_template else "✅ CLEANED"
        if has_template: all_ok = False
    else:
        status = "✅ OK"
    print(f"  {status}")
    print(f"    IN:  {b}")
    print(f"    OUT: {rw}")
    print(f"    Why: {r['improvement_reason']}")
    print()

# Decision threshold test
print("DECISION THRESHOLD TEST (aligned with calibration):")
from pipeline.unified_scoring import compute_final_shortlist_probability
cases = [
    (55, 50, 60, "SKIP"),                # ATS band D → shortlist ~33 → SKIP
    (65, 60, 70, "SKIP"),                # ATS band C → shortlist ~46 → <60 → SKIP
    (75, 70, 80, "APPLY (FIX GAPS)"),    # ATS band B → shortlist ~61 → FIX GAPS
    (82, 75, 85, "APPLY NOW"),           # ATS band A → shortlist ≥75 + rec≥60 → APPLY
    (80, 40, 80, "APPLY (FIX GAPS)"),    # ATS band A but rec<60 → FIX GAPS
    (85, 80, 90, "APPLY NOW"),           # ATS band A → strong → APPLY
]
for ats, rec, jd, expected in cases:
    r = compute_final_shortlist_probability(ats, rec, jd)
    ok = r["decision"] == expected
    s = "✅" if ok else "❌"
    if not ok: all_ok = False
    print(f"  {s} ATS={ats}, Rec={rec} → {r['decision']:20s} ({r['shortlist_probability']:.0f}%) expected={expected}")

print()
if all_ok:
    print("✅ ALL TESTS PASSED")
else:
    print("❌ SOME TESTS FAILED")
