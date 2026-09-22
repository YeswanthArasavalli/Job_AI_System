"""User Interpretation Engine — Evidence Report.
Shows before/after UX for entry-level vs experienced candidates.
"""
import sys, copy, logging, json
sys.path.insert(0, '.')
logging.disable(logging.WARNING)

from utils.models import *
from ats_scoring.scorer import ATSScorer
from pipeline.core import run_full_pipeline

# ==========================================================
# CANDIDATE 1: ENTRY-LEVEL (Yeswanth — intern resume)
# ==========================================================
entry_resume = StructuredResume(
    contact=ContactInfo(name='Yeswanth', email='m@g.com'), title='Data Scientist',
    summary='Data Analyst / Data Scientist with an MS in Data Analytics.',
    skills=['Python', 'SQL', 'Pandas', 'NumPy', 'Scikit-learn', 'Tableau', 'Power BI'],
    experience=[
        ExperienceEntry(role='DS Intern', company='Postulate', duration='Jan 2024 - Feb 2024',
            bullets=['Cleaned 150K+ NLP records, improving quality by 30%.', 'Built forecasting models improving accuracy by 22%.']),
        ExperienceEntry(role='DA Intern', company='Edunet', duration='Jul 2023 - Jan 2024',
            bullets=['Built Python and SQL data pipelines reducing latency by 25%.', 'Developed random forest models for customer segmentation.']),
    ],
    education=[EducationEntry(degree='Masters in CS', institution='Central Univ')],
    projects=[ProjectEntry(name='NLP', technologies=['DistilBERT'], bullets=['94% accuracy with DistilBERT.'])],
)

# ==========================================================
# CANDIDATE 2: EXPERIENCED (Sreejita — ML Engineer)
# ==========================================================
senior_resume = StructuredResume(
    contact=ContactInfo(name='Sreejita Das', email='s@e.com'), title='Machine Learning Engineer',
    summary='Passionate about machine learning and data science.',
    skills=['Python','TensorFlow','PyTorch','SQL','Machine Learning','NLP','Docker','Pandas','AWS','Deep Learning','Scikit-learn'],
    experience=[
        ExperienceEntry(company='TechCorp AI', role='ML Engineer', duration='2022-2024',
            bullets=['Built predictive models for customer churn reducing attrition by 15%.','Developed NLP pipelines for sentiment analysis processing 200K+ reviews.','Deployed machine learning models to production using Docker on AWS.','Created interactive dashboards for business stakeholders using Tableau.']),
        ExperienceEntry(company='DataWorks Inc', role='Data Scientist', duration='2020-2022',
            bullets=['Trained deep learning models for image classification achieving 94% accuracy.','Built ETL data pipelines using Python and Pandas processing 500K records daily.','Implemented recommendation system improving user engagement by 22%.']),
        ExperienceEntry(company='Analytics Labs', role='Junior Data Analyst', duration='2019-2020',
            bullets=['Analyzed sales data to identify revenue trends.','Created automated reports using SQL reducing manual effort by 40%.']),
    ],
    projects=[
        ProjectEntry(name='NLP Chatbot', technologies=['Python','BERT'], bullets=['Built NLP-based chatbot using BERT achieving 92% intent accuracy.']),
    ],
    education=[EducationEntry(degree='M.S. Computer Science', institution='IIT Delhi', year='2019')]
)

jd = ExtractedJD(
    job_title='Senior ML Engineer', company='Google',
    required_skills=['Python','Machine Learning','Deep Learning','TensorFlow','NLP','SQL','Docker','PyTorch'],
    preferred_skills=['AWS','Kubernetes','Spark','Computer Vision','LSTM'],
    keywords=['machine learning','deep learning','nlp','data pipelines','model deployment'],
    responsibilities=['Deploy ML models at scale','Build data pipelines','Develop NLP systems'],
    required_experience_years=5, raw_text='Senior ML Engineer at Google'
)

scorer = ATSScorer()

def show_interpretation(label, resume, jd):
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    r = run_full_pipeline(resume, copy.deepcopy(resume), jd, scorer, 'test', mode='strict')
    hs = r.hiring_simulation or {}
    interp = hs.get('interpretation', {})
    
    if not interp:
        print("  ⚠️ No interpretation data")
        return
    
    # HEADLINE
    print(f"\n  {interp.get('headline', '')}")
    print()
    
    # CONFIDENCE MESSAGE (Part 4)
    print(f"  💬 {interp['confidence_message']}")
    print()
    
    # LEVEL + BENCHMARK (Parts 1 & 2)
    lvl = interp['level_info']
    bench = interp['benchmark']
    print(f"  📊 Level: {lvl['level'].upper()} (~{lvl['years_estimated']} yrs, {lvl['context']})")
    print(f"  {bench['emoji']} Position: {bench['position']}")
    print(f"  📈 {bench['delta_label']}")
    print(f"  📋 {bench['narrative']}")
    print()
    
    # GROWTH PATH (Part 3)
    gp = interp['growth_path']
    if not gp['reached_top']:
        print(f"  🚀 Growth Path → {gp['target_label']}")
        print(f"     Current: {gp['current']}% → Target: {gp['next_target']}% (gap: {gp['gap']:.0f}%)")
        for i, act in enumerate(gp['actions'][:3], 1):
            print(f"     {i}. [{act['priority']}] {act['action']}")
            print(f"        Est. Boost: {act['estimated_boost']} | Effort: {act['effort']}")
            if act.get('example'):
                print(f"        Example: {act['example']}")
    else:
        print(f"  🏆 You've reached top tier!")
    print()
    
    # DECISION (Part 5)
    dec = interp['decision']
    print(f"  {dec['emoji']} DECISION: {dec['decision']}")
    print(f"     {dec['subtitle']}")
    print(f"     👉 Next Step: {dec['next_step']}")
    print()
    
    # RAW METRICS (for comparison)
    print(f"  --- Raw Metrics ---")
    print(f"  ATS Score: {r.ats_report.score_after}")
    print(f"  Shortlist: {hs.get('shortlist_probability', 'N/A')}%")
    perc = hs.get('perception', {})
    if perc:
        print(f"  Perception: {perc.get('total', 'N/A')}/100")

# Run both
show_interpretation("ENTRY-LEVEL CANDIDATE (Intern Resume)", entry_resume, jd)
show_interpretation("EXPERIENCED CANDIDATE (ML Engineer)", senior_resume, jd)

print(f"\n{'='*70}")
print("  ✅ FINAL SUCCESS CONDITION")
print("  User knows: WHERE they stand + HOW to improve")
print(f"{'='*70}")
