"""Verify recommendation consistency: no contradictions."""
import sys; sys.path.insert(0, '.')
from utils.models import *
from ats_scoring.scorer import ATSScorer
from resume_engine.improver import ResumeImprover

resume = StructuredResume(
    contact=ContactInfo(name='Yeswanth', email='m@g.com'), title='Data Scientist',
    summary='Data Analyst / Data Scientist with MS in Data Analytics.',
    skills=['Python', 'SQL', 'R', 'Data Analysis', 'Machine Learning', 'Pandas', 'NumPy', 'Scikit-learn', 'PyTorch', 'NLP', 'Deep Learning', 'Computer Vision', 'Power BI', 'Tableau', 'ETL Pipelines', 'AWS', 'Azure', 'GCP', 'Streamlit', 'Gradio'],
    experience=[
        ExperienceEntry(role='AI Data Annotation', company='Telus', duration='Feb 2024 - Present', bullets=['Labeled large-scale NLP and CV datasets for model training.', 'Optimized prompts to improve AI output precision.']),
        ExperienceEntry(role='DS Intern', company='Postulate', duration='Jan 2024 - Feb 2024', bullets=['Cleaned 150K+ NLP records improving quality by 30%.', 'Built forecasting models improving accuracy by 22%.', 'Developed Tableau dashboards for metrics.']),
        ExperienceEntry(role='DA Intern', company='Edunet', duration='Jul 2023 - Jan 2024', bullets=['Built Python and SQL data pipelines reducing latency by 25%.', 'Developed random forest models for customer segmentation.', 'Designed Power BI dashboards for KPIs.']),
        ExperienceEntry(role='DS Intern', company='PHN', duration='Apr 2023 - Jul 2023', bullets=['Automated ETL workflows for log datasets.', 'Built dashboards reducing reporting by 40%.', 'Applied statistical modeling in R.']),
    ],
    education=[EducationEntry(degree='Masters in CS (Big Data Analytics)', institution='Central Univ')],
    projects=[
        ProjectEntry(name='Image Recognition', description='CV', technologies=['EfficientNet', 'Streamlit'], bullets=['Built deep learning pipeline for 200 categories.', 'Deployed Streamlit app for predictions.']),
        ProjectEntry(name='Food Review NLP', description='NLP', technologies=['DistilBERT', 'Gradio', 'Hugging Face'], bullets=['94% accuracy with DistilBERT.', 'Deployed Gradio and Hugging Face Spaces.']),
        ProjectEntry(name='Predictive Maintenance', description='LSTM', technologies=['LSTM'], bullets=['LSTM model predicting failures with 87% accuracy.']),
        ProjectEntry(name='Emotion Analytics', description='NLP', technologies=['NLP'], bullets=['24% engagement increase.']),
    ],
)
jd = ExtractedJD(job_title='Data Scientist / ML Engineer', company='Corp',
    required_skills=['python', 'python (pandas, numpy, scikit-learn)', 'sql', 'git', 'cloud platforms (aws, azure, or gcp)', 'xgboost', 'random forest', 'lstms', 'distilbert', 'efficientnet', 'streamlit', 'gradio', 'hugging face spaces'],
    keywords=['data pipeline', 'predictive modeling', 'etl', 'churn prediction', 'customer segmentation', 'feature engineering', 'model deployment'],
    responsibilities=['Design ETL pipelines', 'Develop ML models'])

scorer = ATSScorer()
report = scorer.compare(original=resume, tailored=resume, jd=jd)

print("=" * 60)
print("CONSISTENCY CHECK")
print("=" * 60)

# Check 1: No matched skill in missing
matched_set = {s.lower() for s in report.matched_skills}
missing_set = {s.lower() for s in report.missing_skills}
overlap = matched_set & missing_set
print(f"\nMatched ({len(report.matched_skills)}): {sorted(report.matched_skills)[:10]}")
print(f"Missing ({len(report.missing_skills)}): {report.missing_skills}")
print(f"Overlap (MUST BE EMPTY): {overlap}")
assert not overlap, f"FAIL: overlap between matched and missing: {overlap}"

# Check 2: No recommendation says "Add X" for matched skill
print(f"\nRecommendations ({len(report.recommendations)}):")
for i, rec in enumerate(report.recommendations, 1):
    print(f"  {i}. {rec}")
    # Check consistency
    rec_lower = rec.lower()
    if "add" in rec_lower:
        for skill in matched_set:
            if len(skill) > 2 and skill in rec_lower:
                print(f"  ❌ CONTRADICTION: recommends adding '{skill}' which is MATCHED")
                assert False, f"Contradiction: rec says add '{skill}' but it's matched"

print(f"\nScore: {report.score_before} -> {report.score_after}")
print(f"\nALL CONSISTENCY CHECKS PASSED")
