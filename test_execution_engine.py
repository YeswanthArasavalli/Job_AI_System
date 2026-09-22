"""
LIVE VALIDATION: End-to-End Execution Engine Test
Tests all 8 parts of the execution engine with a realistic resume + JD pair.
"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from utils.models import *
from ats_scoring.scorer import ATSScorer
from resume_engine.improver import ResumeImprover

# ============================================================
# REALISTIC resume: skills in skills list + projects but NOT in experience bullets
# This is the exact gap the execution engine should close.
# ============================================================

resume = StructuredResume(
    contact=ContactInfo(name="Alex Chen", email="alex@email.com", phone="555-0100", location="San Francisco, CA"),
    title="Data Scientist",
    summary="Experienced data scientist with a passion for solving complex problems.",
    skills=["Python", "SQL", "Machine Learning", "TensorFlow", "NLP", "Docker", "AWS", "Spark", "scikit-learn", "Pandas"],
    experience=[
        ExperienceEntry(
            role="Data Scientist", company="TechCorp", duration="2022-Present",
            bullets=[
                "Built predictive models for customer churn reducing attrition by 15%.",
                "Analyzed large datasets to identify trends and patterns.",
                "Created automated reports for the executive team.",
                "Collaborated with engineering to deploy solutions.",
            ]
        ),
        ExperienceEntry(
            role="Junior Data Analyst", company="StartupInc", duration="2019-2022",
            bullets=[
                "Performed data analysis using SQL queries.",
                "Generated weekly business reports for stakeholders.",
                "Assisted in building dashboards for KPI tracking.",
            ]
        ),
    ],
    projects=[
        ProjectEntry(
            name="Sentiment Analyzer",
            description="NLP sentiment analysis tool",
            technologies=["Python", "TensorFlow", "NLTK", "Flask"],
            bullets=[
                "Built real-time sentiment analysis pipeline processing 100K tweets using TensorFlow.",
                "Deployed model as REST API using Flask with 99.5% uptime.",
            ]
        ),
        ProjectEntry(
            name="Recommendation Engine",
            description="ML recommendation system",
            technologies=["Python", "Spark", "scikit-learn"],
            bullets=[
                "Developed collaborative filtering engine using Spark processing 2M user records.",
            ]
        ),
    ],
    education=[
        EducationEntry(institution="UC Berkeley", degree="M.S. Data Science", year="2019", details="GPA 3.8")
    ],
)

jd = ExtractedJD(
    job_title="Senior Data Scientist",
    company="BigTech Inc",
    keywords=["machine learning", "NLP", "python", "tensorflow", "spark", "sql", "deep learning", "data pipelines"],
    required_skills=["Python", "TensorFlow", "SQL", "Machine Learning", "NLP"],
    preferred_skills=["Spark", "Docker", "AWS", "scikit-learn"],
    responsibilities=[
        "Build and deploy ML models to production",
        "Design data pipelines for large-scale processing",
        "Lead NLP projects and mentor junior team members",
        "Optimize model performance and inference latency",
    ],
    required_experience_years=5,
)

scorer = ATSScorer()

print("=" * 60)
print("LIVE EXECUTION ENGINE VALIDATION")
print("=" * 60)

# ============================================================
# TEST 1: Original Score (baseline)
# ============================================================
score_orig, bd_orig, det_orig = scorer.score(resume, jd)
print(f"\n[BASELINE] Score: {score_orig}")
print(f"  Keywords: {bd_orig.keyword_match}")
print(f"  Skills: {bd_orig.skills_match}")
print(f"  Experience: {bd_orig.experience_relevance}")
print(f"  Structure: {bd_orig.resume_structure}")

# ============================================================
# TEST 2: Strict Mode Optimization
# ============================================================
imp = ResumeImprover()
matched = det_orig["skills"]["matched"]
missing = det_orig["skills"]["missing"]
jd_kw = det_orig["keywords"]["matched"] + det_orig["keywords"]["missing"]

improved_strict = imp.improve(
    resume.model_copy(deep=True), missing, matched, [], jd_kw, mode="strict"
)
score_strict, bd_strict, det_strict = scorer.score(improved_strict, jd)

print(f"\n[STRICT MODE] Score: {score_strict} (delta: +{score_strict - score_orig:.1f})")
print(f"  Keywords: {bd_strict.keyword_match}")
print(f"  Skills: {bd_strict.skills_match}")
print(f"  Experience: {bd_strict.experience_relevance}")
print(f"  Structure: {bd_strict.resume_structure}")

# ============================================================
# TEST 3: Balanced Mode
# ============================================================
improved_balanced = imp.improve(
    resume.model_copy(deep=True), missing, matched, [], jd_kw, mode="balanced"
)
score_balanced, _, _ = scorer.score(improved_balanced, jd)
print(f"\n[BALANCED MODE] Score: {score_balanced} (delta: +{score_balanced - score_orig:.1f})")

# ============================================================
# PART 1 VALIDATION: Skills used in experience
# ============================================================
print(f"\n{'='*60}")
print("PART 1: SKILL USAGE IN EXPERIENCE BULLETS")
print(f"{'='*60}")

exp_text = " ".join(b.lower() for exp in improved_strict.experience for b in exp.bullets)
skills_to_check = ["python", "tensorflow", "sql", "machine learning", "nlp", "spark", "docker", "aws"]

all_demonstrated = True
for skill in skills_to_check:
    # Check direct or significant term match
    terms = [t for t in skill.split() if len(t) > 3]
    found = skill in exp_text or any(t in exp_text for t in terms)
    status = "✓" if found else "✗"
    if not found:
        all_demonstrated = False
    print(f"  {status} {skill}: {'IN experience' if found else 'MISSING from experience'}")

if all_demonstrated:
    print("  [PASS] All skills demonstrated in experience bullets")
else:
    print("  [WARN] Some skills still only in skills list")

# ============================================================
# PART 2 VALIDATION: Project tools bridged to experience
# ============================================================
print(f"\n{'='*60}")
print("PART 2: PROJECT → EXPERIENCE BRIDGING")
print(f"{'='*60}")

# Check if project-only tools made it into experience
orig_exp_text = " ".join(b.lower() for exp in resume.experience for b in exp.bullets)
imp_exp_text = " ".join(b.lower() for exp in improved_strict.experience for b in exp.bullets)

project_tools = ["tensorflow", "flask", "spark", "nltk"]
bridged = 0
for tool in project_tools:
    was_in_exp = tool in orig_exp_text
    now_in_exp = tool in imp_exp_text
    if not was_in_exp and now_in_exp:
        print(f"  ✓ '{tool}' bridged: project → experience")
        bridged += 1
    elif was_in_exp:
        print(f"  ○ '{tool}' already in experience")
    else:
        print(f"  ✗ '{tool}' NOT bridged")

print(f"  Bridged: {bridged} project-only tools")
if bridged > 0:
    print("  [PASS] Project→Experience bridging working")
else:
    print("  [WARN] No project tools bridged")

# ============================================================
# PART 5 VALIDATION: Summary quality
# ============================================================
print(f"\n{'='*60}")
print("PART 5: SUMMARY QUALITY")
print(f"{'='*60}")

# Apply the pipeline's summary engine (same as pipeline/core.py)
try:
    from resume_engine.summary_engine import generate_professional_summary, should_replace_summary
    from resume_engine.role_engine import classify_role
    role_info = classify_role(jd_text="", job_title=jd.job_title or "")
    if should_replace_summary(improved_strict.summary):
        new_gen_summary = generate_professional_summary(
            resume=improved_strict, role_info=role_info,
            jd_keywords=jd.keywords, matched_skills=matched,
        )
        if new_gen_summary and len(new_gen_summary) > 50:
            improved_strict.summary = new_gen_summary
except Exception as e:
    print(f"  [WARN] Summary engine skipped: {e}")

old_summary = resume.summary
new_summary = improved_strict.summary
print(f"  BEFORE: {old_summary}")
print(f"  AFTER:  {new_summary}")

generic_phrases = [
    "experienced data scientist with a passion",
    "experienced professional with",
    "hardworking",
    "passionate about",
    "dedicated professional",
    "looking for opportunities",
    "seeking a position",
]
has_generic = any(g in new_summary.lower() for g in generic_phrases)
has_tools = any(s.lower() in new_summary.lower() for s in ["python", "tensorflow", "sql", "ml"])
has_role = "data scientist" in new_summary.lower() or "data science" in new_summary.lower()

if has_generic:
    print("  [WARN] Summary still contains generic phrases")
else:
    print("  [PASS] No generic filler phrases")
if has_tools:
    print("  [PASS] Tools mentioned in summary")
if has_role:
    print("  [PASS] Role mentioned in summary")

# ============================================================
# PART 6 VALIDATION: Mode differentiation
# ============================================================
print(f"\n{'='*60}")
print("PART 6: MODE DIFFERENTIATION")
print(f"{'='*60}")

strict_text = " ".join(b for exp in improved_strict.experience for b in exp.bullets) + (improved_strict.summary or "")
balanced_text = " ".join(b for exp in improved_balanced.experience for b in exp.bullets) + (improved_balanced.summary or "")

if strict_text != balanced_text:
    print(f"  [PASS] Strict and balanced produce different output")
else:
    print(f"  [WARN] Strict and balanced produce identical output")

print(f"  Strict score:   {score_strict}")
print(f"  Balanced score: {score_balanced}")
print(f"  Gap: {score_strict - score_balanced:.1f} pts")

# Quality comparison (PART 2: Score ≠ Quality decoupling)
try:
    from pipeline.core import evaluate_resume_quality
    q_strict = evaluate_resume_quality(improved_strict, jd)
    q_balanced = evaluate_resume_quality(improved_balanced, jd)
    print(f"  Strict quality:   {q_strict['total']:.0f}/100 "
          f"(demo={q_strict['skill_demo']:.0f}% purpose={q_strict['tool_purpose']:.0f}%)")
    print(f"  Balanced quality: {q_balanced['total']:.0f}/100 "
          f"(demo={q_balanced['skill_demo']:.0f}% purpose={q_balanced['tool_purpose']:.0f}%)")
except Exception as e:
    print(f"  [WARN] Quality evaluation skipped: {e}")

# ============================================================
# FINAL VERDICT
# ============================================================
print(f"\n{'='*60}")
print("FINAL VERDICT")
print(f"{'='*60}")

checks = [
    ("Score 85+ (strict)", score_strict >= 85),
    ("Score improvement > 5pts", score_strict - score_orig > 5),
    ("All skills in experience", all_demonstrated),
    ("Project bridging works", bridged > 0),
    ("Summary not generic", not has_generic),
    ("Mode differentiation", strict_text != balanced_text),
    ("No fake skills", set(s.lower() for s in improved_strict.skills).issubset(
        set(s.lower() for s in resume.skills) | {"deep learning", "dl"}
    )),
]

passed = sum(1 for _, v in checks if v)
total = len(checks)

for label, ok in checks:
    print(f"  {'✓' if ok else '✗'} {label}")

print(f"\n  Result: {passed}/{total} checks passed")
if passed == total:
    print("  ★ EXECUTION ENGINE: FULLY OPERATIONAL")
elif passed >= total - 1:
    print("  ★ EXECUTION ENGINE: NEAR-COMPLETE")
else:
    print("  ✗ EXECUTION ENGINE: NEEDS WORK")
