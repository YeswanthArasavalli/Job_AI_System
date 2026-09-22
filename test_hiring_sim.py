"""Test the Hiring Simulation Engine integration."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
import logging; logging.disable(logging.WARNING)

from pipeline.core import run_full_pipeline
from ats_scoring.scorer import ATSScorer
from utils.models import *

resume = StructuredResume(
    contact=ContactInfo(name='Priya Sharma', email='priya@email.com'),
    title='Data Scientist',
    summary='Passionate data scientist with experience in various machine learning projects.',
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

r = run_full_pipeline(original=resume, tailored=resume, extracted_jd=jd, scorer=ATSScorer(), mode='strict')
hs = r.hiring_simulation

print('=' * 60)
print('HIRING SIMULATION ENGINE - RESULTS')
print('=' * 60)

print(f"Decision: {hs['decision']}")
print(f"Reason: {hs['decision_reason']}")
print(f"Shortlist Probability: {hs['shortlist_probability']}%")
print(f"Layers Passed: {hs['layers_passed']}/3")
print()

print('--- Layer 1: ATS Filter ---')
ats = hs['layers']['ats']
print(f"  Pass: {ats['pass']}  Score: {ats['score']}  Keywords: {ats['keyword_match']}/{ats['keyword_total']}")
print()

print('--- Layer 2: Recruiter Scan ---')
rec = hs['layers']['recruiter']
print(f"  Pass: {rec['pass']}  Score: {rec['score']}  Scan: {rec['scan_time_estimate']}")
for s in rec['signals']:
    print(f"    + {s}")
for risk in rec['risks']:
    print(f"    - {risk}")
print()

print('--- Layer 3: Hiring Manager ---')
hm = hs['layers']['hiring_manager']
print(f"  Pass: {hm['pass']}  Score: {hm['score']}")
for s in hm['signals']:
    print(f"    + {s}")
for c in hm['concerns']:
    print(f"    ! {c}")
print()

print('--- 10-Second Test ---')
print(f"  {hs['ten_second_test']['verdict']}")
print()

print('--- Competitive Position ---')
cp = hs['competitive']
print(f"  Level: {cp['competitive_level']} ({cp['differentiator_count']} differentiators)")
for d in cp['differentiators']:
    print(f"    [{d['strength']}] {d['label']}: {d['detail']}")
print()

print('--- Skill Proof Audit ---')
sp = hs['skill_proof']
print(f"  Coverage: {sp['proof_coverage']}%")
print(f"  Proven: {len(sp['proven_skills'])}  Unproven: {len(sp['unproven_skills'])}")
if sp['unproven_skills']:
    print(f"  Unproven: {sp['unproven_skills']}")
print()

print('--- Gaps ---')
for g in hs['gaps']:
    print(f"  [{g['severity']}] {g['detail']}")
    print(f"    Action: {g['action']}")
print()

print('--- Recruiter Personas ---')
for pk, pv in hs['persona_simulations'].items():
    print(f"  {pv['icon']} {pv['name']}: {pv['decision']} (score={pv['score']})")
    for fb in pv['feedback']:
        print(f"    {fb}")
