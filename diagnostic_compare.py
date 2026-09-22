"""
DIAGNOSTIC: Compare app.py vs dashboard.py output for SAME input.
Proves whether they produce identical improved resumes.
"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
import logging
logging.disable(logging.WARNING)

from pipeline.core import run_full_pipeline
from ats_scoring.scorer import ATSScorer
from resume_engine.formatter import format_resume_text
from resume_engine.validation_gate import human_quality_check
from utils.models import *

# === SAME INPUT FOR BOTH PATHS ===
resume = StructuredResume(
    contact=ContactInfo(name='Priya Sharma', email='priya@email.com'),
    title='Data Scientist',
    summary='Passionate data scientist with experience in various machine learning projects and tools.',
    skills=['Python', 'TensorFlow', 'SQL', 'Machine Learning', 'NLP', 'Docker', 'Pandas', 'AWS'],
    experience=[
        ExperienceEntry(company='TechCorp', role='Data Scientist', duration='2021-2024',
            bullets=[
                'Built predictive models for customer churn reducing attrition by 15%.',
                'Analyzed large datasets of 500K+ records to identify business trends.',
                'Developed ETL pipelines processing daily transaction data.',
                'Created dashboards for stakeholder reporting using Tableau.',
            ]),
        ExperienceEntry(company='DataWorks', role='ML Engineer', duration='2019-2021',
            bullets=[
                'Trained deep learning models for image classification achieving 94% accuracy.',
                'Deployed models to production using Docker containers on AWS.',
                'Built data preprocessing pipelines using Python and Pandas.',
            ]),
    ],
    projects=[ProjectEntry(name='NLP Chatbot', bullets=['Built NLP-based chatbot achieving 92% intent accuracy.'])],
    education=[EducationEntry(degree='M.S. Computer Science', institution='IIT Delhi', year='2019')]
)
jd = ExtractedJD(
    job_title='Senior Data Scientist', company='Google',
    required_skills=['Python', 'Machine Learning', 'Deep Learning', 'SQL', 'TensorFlow', 'NLP', 'Docker'],
    preferred_skills=['AWS', 'Kubernetes', 'Spark'],
    keywords=['machine learning', 'deep learning', 'nlp', 'tensorflow', 'python', 'sql',
              'data pipelines', 'model deployment', 'a/b testing', 'mlops'],
    responsibilities=['Deploy ML models at scale', 'Build data pipelines', 'Lead ML research'],
    required_experience_years=5, raw_text='Senior Data Scientist at Google'
)

scorer = ATSScorer()

print("=" * 70)
print("DIAGNOSTIC: app.py vs dashboard.py OUTPUT COMPARISON")
print("=" * 70)

# === PATH 1: app.py path (tailored=resume, no LLM) ===
print("\n--- PATH 1: app.py (tailored=resume) ---")
r1 = run_full_pipeline(
    original=resume,
    tailored=resume,  # app.py passes tailored=resume
    extracted_jd=jd,
    scorer=scorer,
    job_id="app_analysis",
    mode="strict",
)

# === PATH 2: dashboard.py path (tailored=resume.model_copy) ===
print("\n--- PATH 2: dashboard.py (tailored=resume.model_copy) ---")
r2 = run_full_pipeline(
    original=resume,
    tailored=resume.model_copy(deep=True),  # manual_mode makes a deep copy
    extracted_jd=jd,
    scorer=scorer,
    job_id="manual_analysis",
    mode="strict",
)

# === COMPARE OUTPUTS ===
print("\n" + "=" * 70)
print("RESULTS COMPARISON")
print("=" * 70)

print(f"\nScore: app={r1.ats_report.score_after} | dashboard={r2.ats_report.score_after}")

# Compare bullets
b1 = [b for e in r1.improved.experience for b in e.bullets]
b2 = [b for e in r2.improved.experience for b in e.bullets]

print(f"Bullet count: app={len(b1)} | dashboard={len(b2)}")

identical = 0
different = 0
for i, (a, b) in enumerate(zip(b1, b2)):
    if a == b:
        identical += 1
    else:
        different += 1
        print(f"\n  DIFF bullet[{i}]:")
        print(f"    APP:  {a[:120]}")
        print(f"    DASH: {b[:120]}")

print(f"\nBullets: {identical} identical, {different} different")

# Compare summaries
s1 = r1.improved.summary or ""
s2 = r2.improved.summary or ""
print(f"\nSummary match: {s1 == s2}")
if s1 != s2:
    print(f"  APP:  {s1[:150]}")
    print(f"  DASH: {s2[:150]}")

# === QUALITY CHECKS ON DASHBOARD OUTPUT ===
print("\n" + "=" * 70)
print("DASHBOARD OUTPUT QUALITY AUDIT")
print("=" * 70)

hq = human_quality_check(r2.improved)
print(f"\nHuman Quality: {hq['overall']}/100")
print(f"  Grammar: {hq['grammar_score']}  Tone: {hq['tone_score']}  Structure: {hq['structure_score']}")

# Check for ALL 6 bug classes
issues = []

for i, b in enumerate(b2):
    bl = b.lower()

    # 1. SEMANTIC CORRUPTION — check overlap with original
    orig_bullets = [ob for e in resume.experience for ob in e.bullets]
    if i < len(orig_bullets):
        orig = orig_bullets[i]
        orig_words = set(re.findall(r'[a-z]{3,}', orig.lower()))
        new_words = set(re.findall(r'[a-z]{3,}', bl))
        if orig_words:
            overlap = len(orig_words & new_words) / len(orig_words)
            if overlap < 0.50:
                issues.append(f"  SEMANTIC DRIFT [{i}] ({overlap:.0%}): {b[:80]}")

    # 2. FAKE TOOL INJECTION — bare "using/leveraging X" at end
    if re.search(r'(?:using|leveraging|utilizing|applying)\s+\w+\s*\.?\s*$', bl):
        # Check for purpose AFTER the tool mention
        after_tool = bl.split('using')[-1] if 'using' in bl else ''
        has_purpose_after = re.search(r'(?:for|to|enabling|improving|reducing|achieving)\s+\w', after_tool)
        # Also check for purpose BEFORE the tool mention (e.g., "for reporting using Tableau")
        before_tool = bl.rsplit('using', 1)[0] if 'using' in bl else ''
        has_purpose_before = re.search(r'(?:for|to)\s+\w+\s+\w+\s*$', before_tool.rstrip())
        if not has_purpose_after and not has_purpose_before:
            issues.append(f"  BARE TOOL [{i}]: {b[-80:]}")

    # 3. BROKEN GRAMMAR
    if b.count('(') != b.count(')'):
        issues.append(f"  BROKEN PARENS [{i}]: {b[:80]}")
    words = b.split()
    for k in range(len(words)-1):
        if words[k].lower() == words[k+1].lower() and words[k].lower() not in {'and', 'the', 'to'}:
            issues.append(f"  DUPLICATE TOKEN [{i}]: '{words[k]}' in: {b[:80]}")

    # 4. KEYWORD STUFFING
    inject_count = sum(1 for m in [", using ", ", applying ", ", utilizing ", ", leveraging "] if m in bl)
    if inject_count > 1:
        issues.append(f"  KEYWORD STUFFING [{i}] ({inject_count} injections): {b[:80]}")
    if b.count(',') > 3:
        issues.append(f"  COMMA STUFFING [{i}] ({b.count(',')} commas): {b[:80]}")

    # 5. AI PHRASING
    for phrase in ["spearheading", "synergizing", "holistic approach", "paradigm shift",
                   "cutting-edge", "catalyzing", "leveraging synergies"]:
        if phrase in bl:
            issues.append(f"  AI PHRASE [{i}]: '{phrase}' in: {b[:60]}")

# 6. ROLE DISTORTION — check if summary role matches JD
summary = (r2.improved.summary or "").lower()
if "data scien" not in summary and "machine learning" not in summary:
    issues.append(f"  ROLE DRIFT: Summary doesn't mention data science/ML")

if issues:
    print(f"\nISSUES FOUND ({len(issues)}):")
    for iss in issues:
        print(f"  {iss}")
else:
    print(f"\nALL QUALITY CHECKS PASSED - NO ISSUES FOUND")

# === TEXT OUTPUT (what dashboard actually delivers) ===
print("\n" + "=" * 70)
print("DASHBOARD TEXT OUTPUT (format_resume_text)")
print("=" * 70)
text_output = format_resume_text(r2.improved)
# Show just the experience section
lines = text_output.split('\n')
in_exp = False
for line in lines:
    if 'PROFESSIONAL EXPERIENCE' in line:
        in_exp = True
    elif 'PROJECTS' in line or 'EDUCATION' in line:
        in_exp = False
    if in_exp:
        print(line)

print("\n" + "=" * 70)
print(f"VERDICT: {'PASS - IDENTICAL QUALITY' if not issues and different == 0 else 'ISSUES DETECTED - SEE ABOVE'}")
print("=" * 70)
