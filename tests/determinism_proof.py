"""Determinism proof: 5 runs, same input, must produce identical scores."""
import sys; sys.path.insert(0, '.')
from utils.models import *
from ats_scoring.scorer import ATSScorer
from resume_engine.improver import ResumeImprover

resume = StructuredResume(
    contact=ContactInfo(name='Yeswanth', email='m@g.com'), title='Data Scientist',
    summary='Data Analyst / Data Scientist with an MS in Data Analytics and hands-on experience across analytics, machine learning, and applied AI.',
    skills=['Python', 'SQL', 'R', 'Data Analysis', 'KPI Reporting', 'Business Metrics', 'Stakeholder Reporting', 'Statistical Analysis', 'Machine Learning', 'Feature Engineering', 'Model Evaluation', 'Pandas', 'NumPy', 'Scikit-learn', 'PyTorch', 'Natural Language Processing', 'Deep Learning', 'Computer Vision', 'Power BI', 'Tableau', 'Excel', 'ETL Pipelines', 'Data Pipelines', 'Data Cleaning', 'Data Validation', 'AWS', 'Azure', 'GCP', 'Model Deployment', 'Streamlit', 'Gradio'],
    experience=[
        ExperienceEntry(role='AI Data Annotation', company='Telus', duration='Feb 2024 - Present', bullets=['Labeled large-scale NLP and CV datasets for model training.', 'Optimized prompts to improve AI output precision.']),
        ExperienceEntry(role='DS Intern', company='Postulate', duration='Jan 2024 - Feb 2024', bullets=['Cleaned 150K+ NLP records, improving quality by 30%.', 'Built forecasting models improving accuracy by 22%.', 'Developed Tableau dashboards for metrics.']),
        ExperienceEntry(role='DA Intern', company='Edunet', duration='Jul 2023 - Jan 2024', bullets=['Built Python and SQL data pipelines reducing latency by 25%.', 'Developed random forest models for customer segmentation.', 'Designed Power BI dashboards for KPIs.']),
        ExperienceEntry(role='DS Intern', company='PHN', duration='Apr 2023 - Jul 2023', bullets=['Automated ETL workflows for log datasets.', 'Built dashboards reducing reporting by 40%.', 'Applied statistical modeling in R.']),
    ],
    education=[EducationEntry(degree='Masters in CS (Big Data Analytics)', institution='Central Univ')],
    projects=[
        ProjectEntry(name='Image', description='CV', technologies=['EfficientNet', 'Streamlit'], bullets=['Built DL pipeline for 200 categories.', 'Deployed Streamlit app.']),
        ProjectEntry(name='NLP', description='NLP', technologies=['DistilBERT', 'Gradio', 'Hugging Face'], bullets=['94% accuracy with DistilBERT.', 'Deployed Gradio and HF Spaces.']),
        ProjectEntry(name='LSTM', description='LSTM', technologies=['LSTM', 'Python'], bullets=['LSTM model, 87% accuracy.']),
        ProjectEntry(name='Emotion', description='NLP', technologies=['NLP'], bullets=['24% engagement increase.']),
    ],
)
jd = ExtractedJD(job_title='Data Scientist / Machine Learning Engineer', company='Corp',
    required_skills=['advanced proficiency in python', 'python (pandas, numpy, scikit-learn)', 'sql', 'experience with version control (git)', 'experience with cloud platforms (aws, azure, or gcp)', 'xgboost', 'random forest', 'lstms', 'distilbert for sentiment analysis', 'efficientnet for image classification', 'streamlit', 'gradio', 'hugging face spaces'],
    keywords=['data pipeline', 'predictive modeling', 'etl', 'churn prediction', 'customer segmentation', 'feature engineering', 'model deployment', 'stakeholder reporting', 'interactive dashboards'],
    responsibilities=['Design ETL pipelines', 'Develop ML models'])

scorer = ATSScorer()
s1, _, _ = scorer.score(resume, jd)
report = scorer.compare(original=resume, tailored=resume, jd=jd)

# 5 determinism runs
scores = []
for run in range(1, 6):
    imp = ResumeImprover()
    improved = imp.improve(
        tailored_resume=resume,
        matched_skills=report.matched_skills,
        missing_skills=report.missing_skills,
        jd_keywords=jd.keywords,
        recommendations=report.recommendations,
    )
    s2, _, _ = scorer.score(improved, jd)
    scores.append(s2)
    print(f"Run {run}: {s1:.1f} -> {s2:.1f} (+{s2-s1:.1f})")

print()
variance = max(scores) - min(scores)
status = "PASS" if variance == 0 else "FAIL"
print(f"Scores: {scores}")
print(f"Variance: {variance:.1f}")
print(f"Determinism: {status}")
print(f"Skills: {len(resume.skills)} -> {len(improved.skills)}")
