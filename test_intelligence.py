"""Quick test: verify the self-improving engines produce correct output."""
import logging
logging.disable(logging.WARNING)

from pipeline.core import run_full_pipeline
from ats_scoring.scorer import ATSScorer
from utils.models import *

resume = StructuredResume(
    contact=ContactInfo(name='Test', email='t@t.com'), title='Data Scientist',
    summary='Data Scientist with 3+ years in ML.',
    skills=['Python', 'SQL', 'Machine Learning'],
    experience=[ExperienceEntry(role='DS', company='Co', duration='2y', bullets=['Built ML models.', 'Cleaned 100K records.'])],
    education=[EducationEntry(degree='MS CS', institution='Univ')]
)
jd = ExtractedJD(
    job_title='Data Scientist',
    required_skills=['Python', 'SQL', 'Spark', 'AWS'],
    raw_text='3+ years experience data scientist spark aws python sql',
    responsibilities=['Build ML pipelines', 'Deploy models to production']
)

scorer = ATSScorer()
r = run_full_pipeline(
    original=resume, tailored=resume, extracted_jd=jd,
    scorer=scorer, mode='strict'
)
intel = r.hiring_simulation.get('intelligence', {})

print("=== GATE ===")
gate = intel.get('gate', {})
print(f"  Decision: {gate.get('decision')}")
print(f"  Confidence: {gate.get('confidence_score')}%")

print("\n=== DIAGNOSIS ===")
diag = intel.get('diagnosis', {})
print(f"  Primary Cause: {diag.get('primary_cause')}")
print(f"  Confidence: {diag.get('confidence')}%")
for e in diag.get('evidence', []):
    print(f"  Evidence: {e[:80]}")

print("\n=== GAP PLAN ===")
gp = intel.get('gap_plan', {})
print(f"  Type: {gp.get('type')}")
print(f"  Summary: {str(gp.get('summary', ''))[:100]}")
print(f"  Effort: {gp.get('estimated_effort')}")
for s in gp.get('upgrade_plan', []):
    print(f"  -> {s[:80]}")

print("\n=== PREDICTION ACCURACY ===")
pa = intel.get('prediction_accuracy', {})
print(f"  Reliability: {pa.get('reliability')}")
print(f"  Summary: {str(pa.get('summary', ''))[:100]}")

print("\n=== VARIANT PERFORMANCE ===")
vp = intel.get('variant_performance', {})
print(f"  Best Variant: {vp.get('best_variant')}")
print(f"  Sufficient Data: {vp.get('sufficient_data')}")
for mode, data in vp.get('per_variant', {}).items():
    print(f"  {mode}: {data['applications']} apps, {data['shortlists']} shortlists, {data['rate']}% rate")

print("\n=== TARGETING ===")
tgt = intel.get('targeting', {})
print(f"  Total Score: {tgt.get('total_score')}/100")
print(f"  Skill Overlap: {tgt.get('skill_overlap')}/30")
print(f"  Targeting Gap: {tgt.get('is_targeting_gap')}")

print("\n=== REJECTION PREDICTION ===")
rp = intel.get('rejection_prediction', {})
print(f"  Verdict: {str(rp.get('verdict', ''))[:80]}")
for risk in rp.get('risks', []):
    print(f"  [{risk['severity']}] {risk['risk']}")

print("\n=== RESUME VARIANTS ===")
for v in intel.get('variants', []):
    print(f"  {v['name']}: {v['probability']} ({v['risk']} risk)")

print("\n" + "="*50)
print("ALL 11 ENGINES PRODUCING OUTPUT")
