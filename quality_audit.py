"""OUTPUT QUALITY AUDIT: Inspect every bullet transformation for quality issues."""
import sys, copy, re
sys.path.insert(0, '.')

from utils.models import *
from ats_scoring.scorer import ATSScorer
from pipeline.core import run_full_pipeline

resume = StructuredResume(
    contact=ContactInfo(name='Yeswanth', email='m@g.com'), title='Data Scientist',
    summary='Data Analyst / Data Scientist with an MS in Data Analytics and hands-on experience across analytics, machine learning, and applied AI.',
    skills=['Python', 'SQL', 'R', 'Data Analysis', 'KPI Reporting', 'Business Metrics',
            'Stakeholder Reporting', 'Statistical Analysis', 'Machine Learning',
            'Feature Engineering', 'Model Evaluation', 'Pandas', 'NumPy', 'Scikit-learn',
            'PyTorch', 'Natural Language Processing', 'Deep Learning', 'Computer Vision',
            'Power BI', 'Tableau', 'Excel', 'ETL Pipelines', 'Data Pipelines',
            'Data Cleaning', 'Data Validation', 'AWS', 'Azure', 'GCP',
            'Model Deployment', 'Streamlit', 'Gradio'],
    experience=[
        ExperienceEntry(role='AI Data Annotation', company='Telus', duration='Feb 2024 - Present',
            bullets=['Labeled large-scale NLP and CV datasets for model training.',
                     'Optimized prompts to improve AI output precision.']),
        ExperienceEntry(role='DS Intern', company='Postulate', duration='Jan 2024 - Feb 2024',
            bullets=['Cleaned 150K+ NLP records, improving quality by 30%.',
                     'Built forecasting models improving accuracy by 22%.',
                     'Developed Tableau dashboards for metrics.']),
        ExperienceEntry(role='DA Intern', company='Edunet', duration='Jul 2023 - Jan 2024',
            bullets=['Built Python and SQL data pipelines reducing latency by 25%.',
                     'Developed random forest models for customer segmentation.',
                     'Designed Power BI dashboards for KPIs.']),
        ExperienceEntry(role='DS Intern', company='PHN', duration='Apr 2023 - Jul 2023',
            bullets=['Automated ETL workflows for log datasets.',
                     'Built dashboards reducing reporting by 40%.',
                     'Applied statistical modeling in R.']),
    ],
    education=[EducationEntry(degree='Masters in CS (Big Data Analytics)', institution='Central Univ')],
    projects=[
        ProjectEntry(name='Image', description='CV', technologies=['EfficientNet', 'Streamlit'],
            bullets=['Built DL pipeline for 200 categories.', 'Deployed Streamlit app.']),
        ProjectEntry(name='NLP', description='NLP', technologies=['DistilBERT', 'Gradio', 'Hugging Face'],
            bullets=['94% accuracy with DistilBERT.', 'Deployed Gradio and HF Spaces.']),
        ProjectEntry(name='LSTM', description='LSTM', technologies=['LSTM', 'Python'],
            bullets=['LSTM model, 87% accuracy.']),
        ProjectEntry(name='Emotion', description='NLP', technologies=['NLP'],
            bullets=['24% engagement increase.']),
    ],
)

jd = ExtractedJD(
    job_title='Data Scientist', company='TechCorp',
    required_skills=['Python', 'SQL', 'Machine Learning', 'Data Analysis', 'Pandas',
                     'Scikit-learn', 'Deep Learning', 'NLP'],
    preferred_skills=['PyTorch', 'TensorFlow', 'AWS', 'Tableau', 'Power BI'],
    keywords=['data science', 'machine learning', 'nlp', 'data pipelines',
              'model deployment', 'analytics', 'dashboards'],
    responsibilities=['Build ML models', 'Analyze data', 'Create dashboards',
                      'Deploy models to production'],
    required_experience_years=2, raw_text='Data Scientist at TechCorp'
)

scorer = ATSScorer()
r = run_full_pipeline(resume, copy.deepcopy(resume), jd, scorer, 'audit', mode='strict')

# Audit each bullet
print("=" * 80)
print("  BULLET-BY-BULLET QUALITY AUDIT")
print("=" * 80)

issues = []
orig_bullets = [b for e in resume.experience for b in e.bullets]
imp_bullets = [b for e in r.improved.experience for b in e.bullets]

for i, (ob, ib) in enumerate(zip(orig_bullets, imp_bullets)):
    changed = ob != ib
    bullet_issues = []
    
    # Check 1: Trailing fragments
    frag_patterns = [r'\b(and|using|for|with|to|in|by)\.\s*$', r'\w+-\.\s*$']
    for fp in frag_patterns:
        if re.search(fp, ib, re.I):
            bullet_issues.append(f"TRAILING FRAGMENT: ends with '{re.search(fp, ib).group()}'")
    
    # Check 2: Broken tokens
    if re.search(r'\w+-\s', ib) and not re.search(r'\w+-\w+', ib):
        bullet_issues.append("BROKEN TOKEN: hyphen followed by space")
    
    # Check 3: Incomplete sentence
    if not ib.strip()[-1] in '.!?':
        bullet_issues.append("INCOMPLETE: no ending punctuation")
    
    # Check 4: Too short
    if len(ib.strip()) < 20:
        bullet_issues.append(f"TOO SHORT: {len(ib)} chars")
    
    # Check 5: Awkward keyword stuffing
    if re.search(r'(?:leveraging|utilizing)\s+\w+(?:\s+and\s+\w+){3,}', ib, re.I):
        bullet_issues.append("KEYWORD STUFFING: too many tools chained")
    
    # Check 6: Double spaces
    if '  ' in ib:
        bullet_issues.append("DOUBLE SPACE")
    
    # Check 7: Starts with action verb
    first_word = ib.strip().split()[0] if ib.strip() else ""
    action_verbs = ['built', 'developed', 'designed', 'created', 'implemented', 'automated',
                    'optimized', 'analyzed', 'led', 'managed', 'deployed', 'engineered',
                    'architected', 'established', 'streamlined', 'reduced', 'improved',
                    'cleaned', 'labeled', 'applied', 'trained', 'integrated', 'configured']
    if first_word.lower() not in action_verbs and changed:
        bullet_issues.append(f"WEAK START: '{first_word}' (not a strong action verb)")
    
    # Check 8: Word count sanity
    word_count = len(ib.split())
    if word_count > 30:
        bullet_issues.append(f"TOO LONG: {word_count} words")
    
    status = "CHANGED" if changed else "KEPT"
    marker = "🔴" if bullet_issues else ("🟡" if changed else "⚪")
    
    print(f"\n{marker} Bullet {i+1} [{status}]")
    if changed:
        print(f"  BEFORE: {ob}")
        print(f"  AFTER:  {ib}")
    else:
        print(f"  TEXT:   {ib}")
    
    for issue in bullet_issues:
        print(f"  ❌ {issue}")
        issues.append((i+1, issue))

# Summary
print(f"\n{'=' * 80}")
print(f"  SUMMARY: {r.ats_report.score_before} → {r.ats_report.score_after}")
print(f"  Summary text: {r.improved.summary[:100]}...")
print(f"\n  Issues found: {len(issues)}")
for idx, issue in issues:
    print(f"    Bullet {idx}: {issue}")

# Check summary quality
summ = r.improved.summary or ""
summ_issues = []
if len(summ) < 50:
    summ_issues.append("TOO SHORT")
if summ.count(',') > 6:
    summ_issues.append(f"TOO MANY COMMAS ({summ.count(',')})")
if re.search(r'\b(utilizing|leveraging)\b', summ, re.I):
    summ_issues.append("BUZZWORD: 'utilizing/leveraging'")
if not summ.strip()[-1] in '.!?':
    summ_issues.append("INCOMPLETE ENDING")

print(f"\n  Summary issues: {len(summ_issues)}")
for si in summ_issues:
    print(f"    ❌ {si}")

print(f"{'=' * 80}")
