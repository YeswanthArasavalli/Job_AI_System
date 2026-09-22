"""Debug: check if hiring_simulation is attached."""
import sys, copy, logging
sys.path.insert(0, '.')

from utils.models import *
from ats_scoring.scorer import ATSScorer
from pipeline.core import run_full_pipeline

resume = StructuredResume(
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
    projects=[ProjectEntry(name='NLP Chatbot', technologies=['Python','BERT'], bullets=['Built NLP-based chatbot using BERT achieving 92% intent accuracy.'])],
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
r = run_full_pipeline(resume, copy.deepcopy(resume), jd, scorer, 'test', mode='strict')

print(f"Type of hiring_simulation: {type(r.hiring_simulation)}")
print(f"hiring_simulation is None: {r.hiring_simulation is None}")
if r.hiring_simulation:
    print(f"Keys: {list(r.hiring_simulation.keys())}")
    interp = r.hiring_simulation.get('interpretation')
    print(f"interpretation: {interp is not None}")
    if interp:
        print(f"  headline: {interp.get('headline')}")
        print(f"  decision: {interp.get('decision', {}).get('decision')}")
else:
    print("  No hiring simulation data!")
