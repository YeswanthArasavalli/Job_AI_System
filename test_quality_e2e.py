"""
END-TO-END QUALITY VALIDATION — FINAL LAYER
Tests with: strong resume, weak resume, non-tech resume, messy resume.

Validates HIRING-QUALITY output across the full pipeline.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from utils.models import *
from resume_engine.summary_engine import generate_professional_summary, should_replace_summary
from resume_engine.polish_engine import polish_resume
from resume_engine.improver import ResumeImprover
from resume_engine.validation_gate import validate_output, ValidationResult

passed = 0
failed = 0
total = 0

def check(name, condition, detail=""):
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} -- {detail}")

# ================================================================
# RESUME 1: STRONG DATA SCIENTIST
# ================================================================
def build_strong():
    return StructuredResume(
        contact=ContactInfo(name="Jane Chen", email="jane@co.com", phone="555-1234", location="NYC"),
        title="Senior Data Scientist",
        summary="Experienced data scientist passionate about ML.",
        skills=["Python", "TensorFlow", "SQL", "Spark", "NLP", "Docker", "AWS"],
        experience=[
            ExperienceEntry(role="Senior Data Scientist", company="BigTech", duration="2021-Present",
                bullets=[
                    "Built end-to-end ML pipeline processing 50M+ records daily using Spark and TensorFlow.",
                    "Deployed NLP models to production serving 10K+ API requests per minute on AWS.",
                    "Reduced model inference latency by 40% through architecture optimization.",
                    "Led team of 4 data scientists in developing recommendation engine.",
                ]),
            ExperienceEntry(role="Data Scientist", company="StartupCo", duration="2018-2021",
                bullets=[
                    "Developed customer churn prediction model with 92% accuracy using scikit-learn.",
                    "Automated ETL pipeline reducing data processing time from 4 hours to 20 minutes.",
                    "Created real-time dashboards for executive team using Python and Plotly.",
                ]),
        ],
        projects=[ProjectEntry(name="NLP Classifier", description="Text", technologies=["Python"],
            bullets=["Built multi-class text classifier with 95% F1 score."])],
        education=[EducationEntry(institution="MIT", degree="M.S. Computer Science", year="2018", details="ML focus")],
    )

# ================================================================
# RESUME 2: WEAK FRESHER
# ================================================================
def build_weak():
    return StructuredResume(
        contact=ContactInfo(name="Bob Smith", email="bob@mail.com", phone="555", location="LA"),
        title="Software Developer",
        summary="I am a hardworking and passionate software developer looking for opportunities.",
        skills=["Java", "Python", "HTML", "CSS", "MySQL"],
        experience=[
            ExperienceEntry(role="Intern", company="SmallCo", duration="2023-2024",
                bullets=[
                    "Helped with bug fixes.",
                    "Attended daily standups.",
                    "Assisted in testing.",
                    "Learned Java.",
                ]),
        ],
        projects=[ProjectEntry(name="Todo App", description="Web app", technologies=["Python"],
            bullets=["Made a todo app using Flask."])],
        education=[EducationEntry(institution="State University", degree="B.S. CS", year="2024", details="")],
    )

# ================================================================
# RESUME 3: NON-TECH (Marketing Manager)
# ================================================================
def build_nontech():
    return StructuredResume(
        contact=ContactInfo(name="Sarah Williams", email="sarah@co.com", phone="555", location="Chicago"),
        title="Marketing Manager",
        summary="Dedicated marketing professional with experience in digital campaigns.",
        skills=["Digital Marketing", "SEO", "Google Analytics", "Content Strategy", "CRM", "Hubspot"],
        experience=[
            ExperienceEntry(role="Marketing Manager", company="BrandCo", duration="2020-Present",
                bullets=[
                    "Was responsible for managing a team of 8 marketing specialists.",
                    "Worked on increasing organic traffic by 150% through SEO optimization.",
                    "Had to manage a $2M annual marketing budget across 5 channels.",
                    "Participated in launching 3 successful product campaigns reaching 1M+ users.",
                    "Successfully completed rebranding initiative for the company.",
                    "Helped with social media management.",
                ]),
        ],
        projects=[], education=[EducationEntry(institution="NYU", degree="MBA", year="2020", details="Marketing")],
    )

# ================================================================
# RESUME 4: MESSY (mixed tenses, first person, fragments)
# ================================================================
def build_messy():
    return StructuredResume(
        contact=ContactInfo(name="Mike Davis", email="mike@mail.com", phone="555", location="Austin"),
        title="DevOps Engineer",
        summary="I have been working as a DevOps engineer for several years now.",
        skills=["Kubernetes", "Docker", "AWS", "Terraform", "Jenkins", "Python", "Linux"],
        experience=[
            ExperienceEntry(role="DevOps Engineer", company="CloudCorp", duration="2021-Present",
                bullets=[
                    "Was in charge of maintaining production Kubernetes clusters serving 99.9% uptime.",
                    "I configured CI/CD pipelines using Jenkins and GitLab CI.",
                    "Worked on migrating legacy systems to AWS cloud infrastructure.",
                    "Tasks included monitoring server performance.",
                    "Successfully managed to reduce deployment time from 2 hours to 15 minutes.",
                    "Assisted with infrastructure as code using Terraform.",
                    "Attended sprint planning meetings.",
                    "Also helped with on-call rotations.",
                ]),
        ],
        projects=[], education=[EducationEntry(institution="UT Austin", degree="B.S. CS", year="2021", details="")],
    )


print("=" * 70)
print("  END-TO-END QUALITY VALIDATION — FINAL LAYER")
print("=" * 70)


# ================================================================
# TEST 1: STRONG RESUME
# ================================================================
print("\n" + "=" * 50)
print("  RESUME 1: STRONG DATA SCIENTIST")
print("=" * 50)

resume = build_strong()
role_info = {"role_type": "data", "allow_tech_injection": True}
jd_kw = ["machine learning", "NLP", "spark", "deep learning"]
matched = ["Python", "TensorFlow", "SQL", "Spark", "NLP"]

summary = generate_professional_summary(resume, role_info, jd_kw, matched)
print(f"\n  Summary: {summary}")
check("Summary > 100 chars", len(summary) > 100)
check("No generic words in summary", all(w not in summary.lower() for w in ["experienced", "passionate", "hardworking"]))
check("Contains real tools", any(t.lower() in summary.lower() for t in ["python", "tensorflow", "spark"]))

polished, changes = polish_resume(resume.model_copy(deep=True), "data")
print(f"\n  Polish changes: {len(changes)}")
for exp in polished.experience:
    print(f"  [{exp.role}] ({len(exp.bullets)} bullets)")
    for b in exp.bullets:
        print(f"    - {b[:80]}")
check("Strong resume mostly preserved (< 5 verb changes)", sum(1 for c in changes if c["type"] == "verb_strength") < 5)
check("Bullets <= 5 per role", all(len(e.bullets) <= 5 for e in polished.experience))


# ================================================================
# TEST 2: WEAK FRESHER
# ================================================================
print("\n" + "=" * 50)
print("  RESUME 2: WEAK FRESHER")
print("=" * 50)

resume = build_weak()
role_info = {"role_type": "technical", "allow_tech_injection": True}

summary = generate_professional_summary(resume, role_info, ["java", "python"], ["Java", "Python"])
print(f"\n  Summary: {summary}")
check("Weak summary gets replaced", should_replace_summary(
    "I am a hardworking and passionate software developer looking for opportunities."))
check("New summary has no 'passionate'", "passionate" not in summary.lower())

polished, changes = polish_resume(resume.model_copy(deep=True), "technical")
print(f"\n  Polish changes: {len(changes)}")
for exp in polished.experience:
    print(f"  [{exp.role}] ({len(exp.bullets)} bullets)")
    for b in exp.bullets:
        print(f"    - {b[:80]}")
# Weak bullets should be removed
all_bullets = [b for e in polished.experience for b in e.bullets]
check("'Attended daily standups' removed", not any("attended" in b.lower() for b in all_bullets))
check("'Learned Java' removed or transformed", not any(b.lower() == "learned java." for b in all_bullets))
check("All remaining bullets > 10 chars", all(len(b) > 10 for b in all_bullets))


# ================================================================
# TEST 3: NON-TECH MARKETING
# ================================================================
print("\n" + "=" * 50)
print("  RESUME 3: NON-TECH MARKETING")
print("=" * 50)

resume = build_nontech()
role_info = {"role_type": "business", "allow_tech_injection": False}

summary = generate_professional_summary(resume, role_info, ["marketing", "SEO", "campaigns"], ["Digital Marketing", "SEO"])
print(f"\n  Summary: {summary}")

polished, changes = polish_resume(resume.model_copy(deep=True), "business")
print(f"\n  Polish changes: {len(changes)}")
for exp in polished.experience:
    print(f"  [{exp.role}] ({len(exp.bullets)} bullets)")
    for b in exp.bullets:
        print(f"    - {b[:80]}")
all_bullets = [b for e in polished.experience for b in e.bullets]
check("'Was responsible for managing' --> 'Managed'", any(b.startswith("Managed") for b in all_bullets))
check("'Had to manage' --> 'Managed'", any("managed" in b.lower() for b in all_bullets))
check("'Helped with social media' removed or improved", not any("helped with" in b.lower() for b in all_bullets))
check("Max 5 bullets", all(len(e.bullets) <= 5 for e in polished.experience))
check("Impact preserved (150%, $2M, 1M+)", 
    any("150%" in b for b in all_bullets) or any("$2m" in b.lower() for b in all_bullets))


# ================================================================
# TEST 4: MESSY DEVOPS
# ================================================================
print("\n" + "=" * 50)
print("  RESUME 4: MESSY DEVOPS")
print("=" * 50)

resume = build_messy()
role_info = {"role_type": "technical", "allow_tech_injection": True}

summary = generate_professional_summary(resume, role_info, ["kubernetes", "aws", "terraform"], ["Kubernetes", "Docker", "AWS"])
print(f"\n  Summary: {summary}")
check("No 'I have been' in summary", "i have been" not in summary.lower())

polished, changes = polish_resume(resume.model_copy(deep=True), "technical")
print(f"\n  Polish changes: {len(changes)}")
for exp in polished.experience:
    print(f"  [{exp.role}] ({len(exp.bullets)} bullets)")
    for b in exp.bullets:
        print(f"    - {b[:80]}")
all_bullets = [b for e in polished.experience for b in e.bullets]
check("8 bullets --> max 5", all(len(e.bullets) <= 5 for e in polished.experience))
check("'Tasks included' removed", not any("tasks included" in b.lower() for b in all_bullets))
check("'Attended sprint' removed", not any("attended" in b.lower() for b in all_bullets))
check("'Also helped' removed", not any("also helped" in b.lower() for b in all_bullets))
check("No bullet starts with 'I '", not any(b.startswith("I ") for b in all_bullets))
check("99.9% uptime preserved", any("99.9%" in b for b in all_bullets))
check("15 minutes metric preserved", any("15 min" in b.lower() for b in all_bullets))


# ================================================================
# TEST 5: MODE DIFFERENTIATION (Strict vs Balanced vs Conservative)
# ================================================================
print("\n" + "=" * 50)
print("  TEST 5: MODE DIFFERENTIATION")
print("=" * 50)

resume = build_strong()
improver = ResumeImprover()
jd_kw = ["machine learning", "NLP", "deep learning", "spark"]
matched = ["Python", "TensorFlow", "SQL", "Spark"]
missing = ["Kubernetes"]
recs = ["MUST: Add Kubernetes experience"]

strict = improver.improve(resume.model_copy(deep=True), jd_kw, matched, missing, recs, mode="strict")
balanced = improver.improve(resume.model_copy(deep=True), jd_kw, matched, missing, recs, mode="balanced")

# Compare FULL output: bullets + summary + skills
strict_full = " ".join(b for e in strict.experience for b in e.bullets) + " " + (strict.summary or "")
balanced_full = " ".join(b for e in balanced.experience for b in e.bullets) + " " + (balanced.summary or "")

check("Strict != Balanced text", strict_full != balanced_full)
# Strict should have more keyword mentions (it does pipeline framing + verb amplification)
strict_kw_count = sum(1 for kw in jd_kw if kw.lower() in strict_full.lower())
balanced_kw_count = sum(1 for kw in jd_kw if kw.lower() in balanced_full.lower())
check("Strict has >= balanced keyword density", strict_kw_count >= balanced_kw_count,
      f"strict={strict_kw_count}, balanced={balanced_kw_count}")


# ================================================================
# TEST 6: TRUE SKILL USAGE VALIDATION
# ================================================================
print("\n" + "=" * 50)
print("  TEST 6: SKILL USAGE VALIDATION")
print("=" * 50)

from resume_engine.validation_gate import is_valid_usage, auto_fix_validation_failures, human_quality_check

check("Valid: full context",
    is_valid_usage("Python", "Built ML pipeline using Python for real-time data processing."))
check("Invalid: too short",
    not is_valid_usage("Python", "Used Python."))
check("Invalid: skill not present",
    not is_valid_usage("Kubernetes", "Built ML pipeline using Python."))
check("Valid: action + substance",
    is_valid_usage("Docker", "Deployed models to production using Docker containers across 3 environments."))
check("Invalid: just a list",
    not is_valid_usage("SQL", "SQL, Python, TensorFlow"))


# ================================================================
# TEST 7: AUTO-FIX VALIDATION FAILURES
# ================================================================
print("\n" + "=" * 50)
print("  TEST 7: AUTO-FIX")
print("=" * 50)

fix_resume = StructuredResume(
    contact=ContactInfo(name="Test", email="t@t.com", phone="555", location="NY"),
    title="Engineer", summary="Test.", skills=["Python"],
    experience=[ExperienceEntry(role="Eng", company="Co", duration="2024",
        bullets=[
            "Processed data using Python.",
            "Spearheaded the migration to cloud.",
            "Built API for the frontend team.",
        ])],
    projects=[], education=[],
)
vr = ValidationResult()
fixed, fixes = auto_fix_validation_failures(fix_resume, vr)
fixed_bullets = [b for e in fixed.experience for b in e.bullets]
check("Auto-fix appends purpose to 'using Python'",
    any("for data processing" in b for b in fixed_bullets))
check("Auto-fix replaces 'spearheaded' --> 'led'",
    any("led" in b.lower() for b in fixed_bullets) and
    not any("spearheaded" in b.lower() for b in fixed_bullets))
check("Auto-fix preserves clean bullets",
    any("Built API" in b for b in fixed_bullets))


# ================================================================
# TEST 8: HUMAN QUALITY CHECK
# ================================================================
print("\n" + "=" * 50)
print("  TEST 8: HUMAN QUALITY CHECK")
print("=" * 50)

# Good resume should score high
good = build_strong()
good_polished, _ = polish_resume(good.model_copy(deep=True), "data")
good_report = human_quality_check(good_polished)
print(f"  Good resume score: {good_report['overall']}")
check("Good resume overall >= 70", good_report["overall"] >= 70)
check("Good resume grammar >= 80", good_report["grammar_score"] >= 80)
check("Good resume structure >= 80", good_report["structure_score"] >= 80)

# Messy resume (pre-polish) should score lower
messy = build_messy()
messy_report = human_quality_check(messy)
print(f"  Messy resume (raw) score: {messy_report['overall']}")

# Messy resume (post-polish) should score better
messy_polished, _ = polish_resume(messy.model_copy(deep=True), "technical")
messy_polished_report = human_quality_check(messy_polished)
print(f"  Messy resume (polished) score: {messy_polished_report['overall']}")
check("Polish improves quality score", messy_polished_report["overall"] >= messy_report["overall"])


# ================================================================
# FINAL VERDICT
# ================================================================
print("\n" + "=" * 70)
if failed == 0:
    print(f"  [PASS] ALL {total} END-TO-END QUALITY TESTS PASSED")
    print(f"  System produces HIRING-QUALITY output.")
else:
    print(f"  [WARN] {passed}/{total} passed, {failed} FAILED")
print(f"  Passed: {passed} | Failed: {failed}")
print("=" * 70)
