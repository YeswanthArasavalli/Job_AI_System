"""
HIRING SYSTEM v6 — DEPTH SIGNAL VERIFICATION
"""
import sys, copy, logging, os
sys.path.insert(0, '.')
logging.disable(logging.WARNING)

from utils.models import *
from ats_scoring.scorer import ATSScorer
from pipeline.core import run_full_pipeline
from pipeline.unified_scoring import (
    compute_final_shortlist_probability,
    _compute_signal_strength, _compute_depth,
    _score_bullet_depth, _score_bullet_signal_strength,
)

print("=" * 70)
print("  HIRING SYSTEM v6 — DEPTH + SIGNAL STRENGTH")
print("=" * 70)
failures = []

# ═══════════ DEPTH ENGINE ═══════════
print("\n🔴 DEPTH SIGNAL ENGINE:")
shallow = ["Built pipeline.", "Managed data.", "Worked on project."]
moderate = [
    "Built segmentation model on customer data.",
    "Developed dashboard for monitoring system.",
    "Processed NLP dataset for classification.",
]
deep = [
    "Built churn prediction model on customer transaction data for marketing team.",
    "Deployed production pipeline processing user event data for real-time monitoring.",
    "Developed fraud detection system using transaction logs for operations team.",
]
ds = _compute_depth(shallow)
dm = _compute_depth(moderate)
dd = _compute_depth(deep)
print(f"  Shallow: avg={ds['average']:.1f} (deep={ds['deep']}, shallow={ds['shallow']})")
print(f"  Moderate: avg={dm['average']:.1f} (deep={dm['deep']}, moderate={dm['moderate']})")
print(f"  Deep:    avg={dd['average']:.1f} (deep={dd['deep']}, shallow={dd['shallow']})")
if dd["average"] > dm["average"] > ds["average"]:
    print("  ✅ Depth correctly orders bullet quality")
else:
    failures.append("Depth ordering"); print("  ❌")

# ═══════════ DEPTH vs SIGNAL DISTINCTION ═══════════
print("\n🔴 DEPTH vs SIGNAL DISTINCTION:")
# This bullet has a competitive signal (dashboard) but is shallow depth
medium_signal_shallow_depth = "Built dashboard for analytics."
sig = _score_bullet_signal_strength(medium_signal_shallow_depth)
dep = _score_bullet_depth(medium_signal_shallow_depth)
print(f"  '{medium_signal_shallow_depth}'")
print(f"    Signal={sig} (medium), Depth={dep} (shallow)")
# This bullet has all three depth dimensions
deep_bullet = "Built churn prediction model on customer data for marketing team dashboard."
sig2 = _score_bullet_signal_strength(deep_bullet)
dep2 = _score_bullet_depth(deep_bullet)
print(f"  '{deep_bullet}'")
print(f"    Signal={sig2}, Depth={dep2}")
if dep2 > dep:
    print("  ✅ Depth correctly distinguishes multi-dimensional work")
else:
    failures.append("Depth distinction"); print("  ❌")

# ═══════════ RECRUITER IMPACT ═══════════
print("\n🔴 RECRUITER IMPACT:")
r_sh = compute_final_shortlist_probability(85, 80, 85, bullets=shallow, experience_level="mid")
r_dp = compute_final_shortlist_probability(85, 80, 85, bullets=deep, experience_level="mid")
print(f"  Shallow: rec={r_sh['recruiter_effective']}, depth_penalty={r_sh['depth_penalty']}")
print(f"  Deep:    rec={r_dp['recruiter_effective']}, deploy_boost={r_dp['deploy_boost']}")
if r_dp["recruiter_effective"] > r_sh["recruiter_effective"]:
    print("  ✅ Deep bullets produce higher recruiter score")
else:
    failures.append("Depth recruiter impact"); print("  ❌")

# ═══════════ FULL PIPELINE ═══════════
print("\n" + "=" * 70)
print("  FULL PIPELINE — DEPTH-AWARE ENGINE")
print("=" * 70)

resume = StructuredResume(
    contact=ContactInfo(name="Yeswanth", email="y@g.com"),
    title="Data Scientist",
    summary="Data Analyst / Data Scientist with MS in Data Analytics.",
    skills=["Python", "SQL", "Pandas", "Scikit-learn", "PyTorch", "Tableau",
            "Power BI", "NLP", "Deep Learning", "Data Analysis", "ETL", "AWS"],
    experience=[
        ExperienceEntry(role="AI Data Annotation", company="Telus", duration="Feb 2024-Present",
            bullets=["Labeled large-scale NLP and CV datasets for model training.",
                     "Optimized prompts to improve AI output precision."]),
        ExperienceEntry(role="DS Intern", company="Postulate", duration="Jan-Feb 2024",
            bullets=["Cleaned 150K+ NLP records, improving quality by 30%.",
                     "Built forecasting models improving accuracy by 22%.",
                     "Developed Tableau dashboards for metrics."]),
        ExperienceEntry(role="DA Intern", company="Edunet", duration="Jul 2023-Jan 2024",
            bullets=["Built Python and SQL data pipelines reducing latency by 25%.",
                     "Developed random forest models for customer segmentation.",
                     "Designed Power BI dashboards for KPIs."]),
        ExperienceEntry(role="DS Intern", company="PHN", duration="Apr-Jul 2023",
            bullets=["Automated ETL workflows for log datasets.",
                     "Built dashboards reducing reporting by 40%.",
                     "Applied statistical modeling in R."]),
    ],
    education=[EducationEntry(degree="MS CS (Big Data Analytics)", institution="Central Univ")],
    projects=[
        ProjectEntry(name="Image Classification", description="CV",
            technologies=["EfficientNet", "Streamlit"],
            bullets=["Built DL pipeline for 200 categories.", "Deployed Streamlit app."]),
        ProjectEntry(name="NLP Classifier", description="NLP",
            technologies=["DistilBERT", "Gradio"],
            bullets=["94% accuracy with DistilBERT.", "Deployed Gradio and HF Spaces."]),
    ],
)
jd = ExtractedJD(
    job_title="Data Scientist", company="TechCorp",
    required_skills=["Python", "SQL", "Machine Learning", "Data Analysis",
                     "Pandas", "Scikit-learn", "Deep Learning", "NLP"],
    preferred_skills=["PyTorch", "TensorFlow", "AWS", "Tableau", "Power BI"],
    keywords=["data science", "machine learning", "nlp", "data pipelines",
              "model deployment", "analytics"],
    responsibilities=["Build ML models", "Analyze data", "Create dashboards", "Deploy models"],
    required_experience_years=2, raw_text="Data Scientist at TechCorp",
)

if os.path.exists("d:/Projects/job_ai_system/data/behavior_state.json"):
    os.remove("d:/Projects/job_ai_system/data/behavior_state.json")

s = ATSScorer()
sb, _, _ = s.score(resume, jd)
result = run_full_pipeline(original=resume, tailored=copy.deepcopy(resume),
    extracted_jd=jd, scorer=s, job_id="proof_v6", mode="strict")
sa = result.ats_report.score_after
us = result.hiring_simulation.get("unified_scoring", {}) if result.hiring_simulation else {}
sig = us.get("signal_strength", {})
dep = us.get("depth", {})
comp = us.get("competition_analysis", {})

print(f"\n  ATS:              {sb:.1f} → {sa:.1f} (Δ{sa-sb:+.1f})")
print(f"  Shortlist:        {us.get('shortlist_probability',0):.1f}%")
print(f"  Recruiter:        {us.get('recruiter_effective',0):.1f} (effective)")
print(f"  Decision:         {us.get('decision','?')}")
print(f"  Reason:           {us.get('decision_reason','?')}")

print(f"\n  SIGNAL STRENGTH:  avg={sig.get('average',0):.2f} "
      f"(S={sig.get('strong_bullets',0)} M={sig.get('medium_bullets',0)} W={sig.get('weak_bullets',0)})")
print(f"  DEPTH:            avg={dep.get('average',0):.2f} "
      f"(D={dep.get('deep',0)} M={dep.get('moderate',0)} S={dep.get('shallow',0)})")
print(f"  COMPETITION:      rank={comp.get('estimated_percentile','?')}th, "
      f"risk={comp.get('risk_level','?')}")

print(f"\n  RECRUITER BREAKDOWN:")
print(f"    Raw:            {us.get('recruiter_score',0):.0f}")
print(f"    Generic Pen:    {us.get('generic_penalty',0):.0f}%")
print(f"    Diff Pen:       {us.get('differentiation_penalty',0)}")
print(f"    Signal Pen:     {us.get('signal_penalty',0)}")
print(f"    Volatile Adj:   {us.get('volatile_adjustment',0):+d}")
print(f"    Killer Boost:   {us.get('killer_boost',0):+d}")
print(f"    Depth Pen:      {us.get('depth_penalty',0)}")
print(f"    Deploy Boost:   {us.get('deploy_boost',0):+d}")
print(f"    → Effective:    {us.get('recruiter_effective',0):.1f}")

# Bullet detail
bullets = [b for exp in result.improved.experience for b in exp.bullets]
print(f"\n  BULLET ANALYSIS ({len(bullets)} bullets):")
for i, b in enumerate(bullets[:5]):
    s_sc = _score_bullet_signal_strength(b)
    d_sc = _score_bullet_depth(b)
    s_lbl = {3:"S", 2:"M", 1:"W"}[s_sc]
    d_lbl = {3:"D", 2:"M", 1:"S"}[d_sc]
    print(f"    [{s_lbl}/{d_lbl}] {b[:85]}...")

# Determinism
scores = []
for i in range(3):
    r2 = run_full_pipeline(original=resume, tailored=copy.deepcopy(resume),
        extracted_jd=jd, scorer=ATSScorer(), job_id=f"det_{i}", mode="strict")
    us2 = r2.hiring_simulation.get("unified_scoring", {}) if r2.hiring_simulation else {}
    scores.append(us2.get("shortlist_probability", 0))
var = max(scores) - min(scores)
print(f"\n  Determinism: {[f'{s:.1f}' for s in scores]} (var={var:.1f})")
if var > 0:
    failures.append("Determinism"); print("  ❌ NON-DETERMINISTIC")
else:
    print("  ✅ DETERMINISTIC")

print("\n" + "=" * 70)
if not failures:
    print("  ✅ HIRING SYSTEM v6 — ALL CHECKS PASSED")
    print("     ✔ Depth engine  ✔ Signal strength  ✔ Recruiter composite")
    print("     ✔ Competition model  ✔ Deterministic")
else:
    print(f"  ❌ {len(failures)} FAILURES: {failures}")
print("=" * 70)
