"""Human quality validation — tests REAL output quality, not just scores."""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
import logging
logging.disable(logging.WARNING)

from pipeline.core import run_full_pipeline
from ats_scoring.scorer import ATSScorer
from resume_engine.validation_gate import human_quality_check
from utils.models import *

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
print("=== HUMAN QUALITY VALIDATION ===\n")

for mode in ['strict', 'balanced', 'conservative']:
    r = run_full_pipeline(resume, resume.model_copy(deep=True), jd, scorer, mode=mode)
    improved = r.improved
    hq = human_quality_check(improved)

    print(f"--- MODE: {mode.upper()} ---")
    print(f"  ATS Score: {r.ats_report.score_after}")
    print(f"  Human Quality: {hq['overall']}/100")
    print(f"    Grammar: {hq['grammar_score']}  Tone: {hq['tone_score']}  "
          f"Structure: {hq['structure_score']}  Impact: {hq['impact_score']}  "
          f"Believability: {hq['believability_score']}")

    # Check bullet quality
    bullets = [b for e in improved.experience for b in e.bullets]
    issues = []
    for b in bullets:
        bl = b.lower()
        # Bare tool usage (ends with "using X.")
        if re.search(r'(?:using|leveraging|utilizing)\s+\w+\s*\.\s*$', bl) and \
           not re.search(r'(?:using|leveraging|utilizing)\s+\w+\s+(?:for|to|enabling|across|in)\s', bl):
            issues.append(f"  BARE TOOL: {b[-60:]}")
        # Tool stacking
        tool_count = sum(1 for m in [", using ", ", applying ", ", utilizing ", ", leveraging "]
                         if m in bl)
        if tool_count > 1:
            issues.append(f"  TOOL STACK: {b[:80]}")
        # >3 commas
        if b.count(',') > 3:
            issues.append(f"  COMMA STUFFED: {b[:80]}")
        # AI phrasing
        for phrase in ["spearheading", "synergizing", "holistic approach", "paradigm shift",
                       "cutting-edge solutions", "catalyzing innovation"]:
            if phrase in bl:
                issues.append(f"  AI PHRASE: '{phrase}' in {b[:60]}")

    if issues:
        print(f"  BULLET ISSUES ({len(issues)}):")
        for iss in issues[:5]:
            print(f"    {iss}")
    else:
        print(f"  BULLET QUALITY: CLEAN ({len(bullets)} bullets)")

    # Show summary
    print(f"  Summary ({len(improved.summary or '')} chars): {(improved.summary or '')[:120]}...")

    # Show first 3 bullets
    print(f"  Top bullets:")
    for b in bullets[:3]:
        print(f"    • {b[:120]}")
    print()

# Cross-mode differentiation
print("--- MODE DIFFERENTIATION ---")
rs = run_full_pipeline(resume, resume.model_copy(deep=True), jd, scorer, mode='strict')
rb = run_full_pipeline(resume, resume.model_copy(deep=True), jd, scorer, mode='balanced')
rc = run_full_pipeline(resume, resume.model_copy(deep=True), jd, scorer, mode='conservative')

bs = [b for e in rs.improved.experience for b in e.bullets]
bb = [b for e in rb.improved.experience for b in e.bullets]
bc = [b for e in rc.improved.experience for b in e.bullets]

text_diff = sum(1 for a, b in zip(bs, bb) if a != b)
print(f"  Strict vs Balanced: {text_diff}/{len(bs)} bullets differ")
print(f"  Score gap: strict={rs.ats_report.score_after} balanced={rb.ats_report.score_after} "
      f"conservative={rc.ats_report.score_after}")
print(f"  Summary diff: {rs.improved.summary != rb.improved.summary}")

all_clean = True
for mode_name, result in [("strict", rs), ("balanced", rb), ("conservative", rc)]:
    for e in result.improved.experience:
        for b in e.bullets:
            if b.count(',') > 3:
                all_clean = False
            if b.lower().count("utilizing ") > 1 or b.lower().count("leveraging ") > 1:
                all_clean = False

print(f"\n  ALL BULLETS CLEAN: {'PASS' if all_clean else 'FAIL'}")
print(f"  MODE GAP: {'PASS' if abs(rs.ats_report.score_after - rb.ats_report.score_after) >= 1.0 else 'FAIL'}")
print(f"  TEXT DIFFERS: {'PASS' if text_diff > 0 else 'FAIL'}")
