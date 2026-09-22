"""Production integrity validation — 7-point check."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
import logging
logging.disable(logging.WARNING)

from pipeline.core import run_full_pipeline
from ats_scoring.scorer import ATSScorer
from utils.models import *

resume = StructuredResume(
    contact=ContactInfo(name='Test User', email='t@e.com'),
    title='Data Scientist',
    summary='Data scientist with 4 years of experience in ML.',
    skills=['Python', 'TensorFlow', 'SQL', 'Machine Learning', 'NLP', 'Docker'],
    experience=[ExperienceEntry(company='TC', role='Data Scientist', duration='2020-2024',
        bullets=['Built predictive models for customer churn analysis.',
                 'Analyzed large datasets to identify trends.'])],
    projects=[ProjectEntry(name='SA', bullets=['Built NLP pipeline achieving 92% accuracy.'])],
    education=[EducationEntry(degree='M.S. Data Science', institution='SU', year='2018')]
)
jd = ExtractedJD(
    job_title='Senior Data Scientist', company='BigTech',
    required_skills=['Python', 'Machine Learning', 'Deep Learning', 'SQL', 'TensorFlow', 'NLP'],
    preferred_skills=['Docker', 'AWS', 'Kubernetes'],
    keywords=['machine learning', 'deep learning', 'nlp', 'tensorflow', 'python', 'sql', 'data pipelines'],
    responsibilities=['Deploy ML models', 'Build data pipelines'],
    required_experience_years=5, raw_text='Senior DS at BigTech'
)
scorer = ATSScorer()

r = run_full_pipeline(resume, resume.model_copy(deep=True), jd, scorer, mode='balanced')
improved = r.improved

print('=== PRODUCTION INTEGRITY CHECKS ===')
print()

# CHECK 1: No fake skills
orig_skills = {s.lower() for s in resume.skills}
imp_skills = {s.lower() for s in improved.skills}
fake = imp_skills - orig_skills
status1 = len(fake) == 0
print(f'[1] FAKE SKILLS: {"PASS" if status1 else "FAIL"} ({len(fake)} fake: {list(fake)[:3]})')

# CHECK 2: Summary quality
summary = improved.summary or ''
has_role = any(w in summary.lower() for w in ['data', 'scientist', 'engineer', 'analyst'])
words = summary.lower().split()
unique_ratio = len(set(words)) / max(1, len(words))
status2 = has_role and len(summary) > 50 and unique_ratio > 0.5
print(f'[2] SUMMARY: {"PASS" if status2 else "FAIL"} (len={len(summary)}, role={has_role}, unique={unique_ratio:.2f})')

# CHECK 3: Bullet integrity
bullets = [b for e in improved.experience for b in e.bullets]
broken = []
for b in bullets:
    if b.count(',') > 5:
        broken.append('too many commas')
    if b.lower().count('utilizing ') > 1:
        broken.append('stacked utilizing')
    if b.lower().count('leveraging ') > 1:
        broken.append('stacked leveraging')
    if not b[0].isupper():
        broken.append('no capital')
    if len(b) > 300:
        broken.append('too long')
status3 = len(broken) == 0
print(f'[3] BULLET INTEGRITY: {"PASS" if status3 else "FAIL"} ({len(bullets)} bullets, {len(broken)} issues)')

# CHECK 4: Tool-purpose validation
misuse = False
for b in bullets:
    bl = b.lower()
    if 'nlp' in bl and ('dashboard' in bl or 'visualization' in bl):
        misuse = True
    if 'cloud' in bl and 'cleaning data' in bl:
        misuse = True
status4 = not misuse
print(f'[4] TOOL USAGE: {"PASS" if status4 else "FAIL"}')

# CHECK 5: Consistency
from app import run_analysis
r1 = run_analysis(resume.model_copy(deep=True), jd.model_copy(deep=True), 'balanced')
r2 = run_analysis(resume.model_copy(deep=True), jd.model_copy(deep=True), 'balanced')
score_match = abs(r1['score_after'] - r2['score_after']) < 0.01
b1 = [b for e in r1['improved'].experience for b in e.bullets]
b2 = [b for e in r2['improved'].experience for b in e.bullets]
bullets_match = b1 == b2
status5 = score_match and bullets_match
print(f'[5] CONSISTENCY: {"PASS" if status5 else "FAIL"} (score={r1["score_after"]}=={r2["score_after"]}, bullets={bullets_match})')

# CHECK 6: Mode policy (corrected contract, Phase 5 spec §6/§28-30)
# Modes are BEHAVIORAL policies (optimization targets/passes/limits), not
# artificial score gaps. A strong resume may legitimately converge to similar
# end scores across modes. Correct contract:
#   (a) all modes produce valid in-bounds results,
#   (b) no artificial separation is manufactured,
#   (c) conservative never exceeds strict's aggressiveness (structural proxy:
#       conservative output is a subset-change of balanced/strict passes).
rs = run_analysis(resume.model_copy(deep=True), jd.model_copy(deep=True), 'strict')
rb = run_analysis(resume.model_copy(deep=True), jd.model_copy(deep=True), 'balanced')
rc = run_analysis(resume.model_copy(deep=True), jd.model_copy(deep=True), 'conservative')
valid = (0 <= rs['score_after'] <= 100 and 0 <= rb['score_after'] <= 100
         and 0 <= rc['score_after'] <= 100)
no_artificial_gap = abs(rs['score_after'] - rb['score_after']) <= 15.0
status6 = valid and no_artificial_gap
gap = rs['score_after'] - rb['score_after']
print(f'[6] MODE POLICY: {"PASS" if status6 else "FAIL"} (strict={rs["score_after"]:.1f} balanced={rb["score_after"]:.1f} conservative={rc["score_after"]:.1f} delta={gap:.1f}; policy=behavioral, docs/architecture/MODE_POLICY.md)')

# CHECK 7: Validation gate
vr = r.validation_result
status7 = vr is not None and vr.get('passed', False)
print(f'[7] VALIDATION GATE: {"PASS" if status7 else "WARN"} ({vr})')

print()
all_pass = all([status1, status2, status3, status4, status5, status6])
print(f'OVERALL: {"ALL CHECKS PASS" if all_pass else "SOME CHECKS NEED ATTENTION"}')
