"""Quick shortlist check for Sreejita data."""
import sys, copy, logging
sys.path.insert(0, '.')
logging.disable(logging.WARNING)
from utils.models import *
from pipeline.core import run_full_pipeline
from ats_scoring.scorer import ATSScorer
from pipeline.hiring_simulation import compute_perceived_strength, recruiter_10s_dominance_check

resume = StructuredResume(
    contact=ContactInfo(name='Sreejita Das', email='s@e.com'),
    title='Machine Learning Engineer',
    summary='Passionate about machine learning and data science.',
    skills=['Python','TensorFlow','PyTorch','SQL','Machine Learning','NLP','Docker','Pandas','AWS','Deep Learning','Scikit-learn','NumPy','Computer Vision','LSTM','Tableau','Spark'],
    experience=[
        ExperienceEntry(company='TechCorp AI', role='ML Engineer', duration='2022-2024',
            bullets=['Built predictive models for customer churn reducing attrition by 15%.','Developed NLP pipelines for sentiment analysis processing 200K+ reviews.','Deployed machine learning models to production using Docker on AWS.','Created interactive dashboards for business stakeholders using Tableau.']),
        ExperienceEntry(company='DataWorks Inc', role='Data Scientist', duration='2020-2022',
            bullets=['Trained deep learning models for image classification achieving 94% accuracy.','Built ETL data pipelines using Python and Pandas processing 500K records daily.','Implemented recommendation system improving user engagement by 22%.']),
        ExperienceEntry(company='Analytics Labs', role='Junior Data Analyst', duration='2019-2020',
            bullets=['Analyzed sales data to identify revenue trends and seasonal patterns.','Created automated reports using SQL reducing manual effort by 40%.']),
    ],
    projects=[
        ProjectEntry(name='NLP Chatbot', technologies=['Python', 'BERT', 'Flask'],
            bullets=['Built NLP-based chatbot using BERT achieving 92% intent accuracy.','Deployed chatbot to production serving 10K+ daily users.']),
        ProjectEntry(name='Image Classifier', technologies=['PyTorch', 'EfficientNet'],
            bullets=['Developed image classification pipeline using EfficientNet.','Achieved 96% accuracy on custom dataset of 50K images.']),
    ],
    education=[EducationEntry(degree='M.S. Computer Science', institution='IIT Delhi', year='2019')]
)
jd = ExtractedJD(
    job_title='Senior ML Engineer', company='Google',
    required_skills=['Python', 'Machine Learning', 'Deep Learning', 'TensorFlow', 'NLP','SQL', 'Docker', 'PyTorch'],
    preferred_skills=['AWS', 'Kubernetes', 'Spark', 'Computer Vision', 'LSTM'],
    keywords=['machine learning', 'deep learning', 'nlp', 'tensorflow', 'python', 'sql','data pipelines', 'model deployment', 'computer vision', 'mlops','recommendation systems', 'feature engineering'],
    responsibilities=['Deploy ML models at scale', 'Build data pipelines', 'Lead ML research','Develop NLP systems', 'Build recommendation engines'],
    required_experience_years=5, raw_text='Senior ML Engineer at Google building production ML systems'
)
scorer = ATSScorer()

# BEFORE
p0 = compute_perceived_strength(resume, jd)
d0 = recruiter_10s_dominance_check(resume, jd)
s0, _, _ = scorer.score(resume, jd)
print(f"BEFORE: ATS={s0}, Perception={p0['total']}, 10s={'PASS' if d0['pass'] else 'FAIL'}({d0['score']})")

# STRICT
r = run_full_pipeline(resume, copy.deepcopy(resume), jd, scorer, 'test', mode='strict')
hs = r.hiring_simulation or {}
p1 = hs.get('perception', {})
d1 = hs.get('dominance_check', {})
s1, _, _ = scorer.score(r.improved, jd)
print(f"STRICT: ATS={s1}, Shortlist={hs.get('shortlist_probability','N/A')}%, Perception={p1.get('total','N/A')}, 10s={'PASS' if d1.get('pass') else 'FAIL'}({d1.get('score','N/A')})")

# Show transformed bullets
print("\nTransformed bullets (first role):")
for b in r.improved.experience[0].bullets:
    print(f"  * {b}")
