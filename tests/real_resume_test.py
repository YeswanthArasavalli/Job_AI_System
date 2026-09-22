"""Test with the user's EXACT resume and JD to verify 85+ score."""
from utils.models import *
from ats_scoring.scorer import ATSScorer
from resume_engine.improver import ResumeImprover

resume = StructuredResume(
    contact=ContactInfo(name='Yeswanth Arasavalli', email='maneswararasavalli@gmail.com'),
    title='Data Scientist',
    summary='Data Analyst / Data Scientist with an MS in Data Analytics and hands-on experience across analytics, machine learning, and applied AI. Strong background in Python, SQL, ETL pipelines, statistical analysis, and dashboarding to support business decision-making. Delivered measurable impact by improving data processing efficiency, reducing reporting and query latency by 25-40%, improving data quality by 30%, and developing predictive models supporting cost reduction and operational planning (projected $1.15M annual savings).',
    skills=[
        'Python', 'SQL', 'R', 'Data Analysis', 'KPI Reporting', 'Business Metrics',
        'Requirements Analysis', 'Stakeholder Reporting', 'Statistical Analysis',
        'Machine Learning', 'Feature Engineering', 'Model Evaluation',
        'Pandas', 'NumPy', 'Scikit-learn', 'PyTorch',
        'Natural Language Processing', 'Deep Learning', 'Computer Vision',
        'Power BI', 'Tableau', 'Excel',
        'ETL Pipelines', 'Data Pipelines', 'Data Cleaning', 'Data Validation', 'Data Quality Checks',
        'AWS', 'Azure', 'GCP', 'Model Deployment', 'API Integration', 'Streamlit', 'Gradio',
    ],
    experience=[
        ExperienceEntry(
            role='AI Data Annotation Specialist & Prompt Engineer (Freelance)',
            company='Telus International',
            duration='February 2024 - Present',
            bullets=[
                'Labeled, validated, and quality-checked large-scale NLP and Computer Vision datasets to support model training and evaluation.',
                'Designed and iteratively optimized prompts to improve precision, relevance, and consistency of AI-generated outputs, supporting downstream analytics and ML workflows.',
            ]
        ),
        ExperienceEntry(
            role='Data Science Intern',
            company='Postulate IRT',
            duration='January 2024 - February 2024',
            bullets=[
                'Cleaned and processed 150K+ NLP speech records, improving data quality and integrity by 30% to support downstream modeling and analysis.',
                'Built forecasting models for marketing analytics, improving prediction accuracy by 22% and supporting campaign planning decisions.',
                'Developed Tableau dashboards to track performance metrics and present insights for cross-functional stakeholders.',
            ]
        ),
        ExperienceEntry(
            role='Data Analyst Intern',
            company='Edunet Foundation',
            duration='July 2023 - January 2024',
            bullets=[
                'Built Python and SQL-based data pipelines across cloud and on-prem systems to support reporting, analytics, and operational decision-making, reducing query latency by 25%.',
                'Developed decision tree and random forest models for customer segmentation and behavioral analysis.',
                'Designed interactive Power BI dashboards to visualize KPIs, trends, and model outputs for business and stakeholder review.',
            ]
        ),
        ExperienceEntry(
            role='Data Science Intern',
            company='PHN Technology Pvt. Ltd.',
            duration='April 2023 - July 2023',
            bullets=[
                'Automated ETL workflows for large-scale log datasets, improving operational efficiency, data reliability, and reporting readiness.',
                'Built Tableau and Excel dashboards that reduced manual reporting effort by 40% and improved turnaround time for business reports.',
                'Applied statistical modeling techniques in R and deployed models using IBM Watson Studio to support analytical use cases.',
            ]
        ),
    ],
    education=[
        EducationEntry(degree='Masters in Computer Science (Big Data Analytics)', institution='Central University of Rajasthan'),
    ],
    projects=[
        ProjectEntry(
            name='Retail Product Image Recognition System',
            description='Computer Vision, Deep Learning',
            technologies=['EfficientNet', 'Streamlit', 'Python'],
            bullets=[
                'Built a deep learning pipeline to classify ~200 retail SKU categories using the RPC dataset.',
                'Trained an EfficientNet-B0 model with mixed-precision GPU acceleration, achieving 84.9% validation accuracy.',
                'Developed a Streamlit application to deploy trained models for real-time predictions.',
            ]
        ),
        ProjectEntry(
            name='Amazon Food Review Analysis',
            description='NLP',
            technologies=['DistilBERT', 'Gradio', 'Hugging Face Spaces'],
            bullets=[
                'Processed and analyzed 568K+ reviews, converting unstructured text into sentiment labels.',
                'Improved model accuracy from 89% to 94% using fine-tuned DistilBERT.',
                'Deployed a real-time prediction interface using Gradio and Hugging Face Spaces.',
            ]
        ),
        ProjectEntry(
            name='Predictive Maintenance with LSTM',
            description='Time Series',
            technologies=['LSTM', 'Python'],
            bullets=[
                'Built an LSTM-based model to predict machine failures up to two weeks in advance with 87% accuracy.',
                'Projected $1.15M annual cost savings through reduced downtime and proactive maintenance planning.',
            ]
        ),
        ProjectEntry(
            name='Customer Emotion Analytics for Personalization',
            description='Text & Audio NLP',
            technologies=['NLP', 'Python'],
            bullets=[
                'Analyzed customer interaction data across text and audio channels to identify emotional patterns using NLP and signal-processing techniques.',
                'Generated emotion-based insights contributing to a 24% increase in user engagement and 14% revenue uplift.',
            ]
        ),
    ],
)

jd = ExtractedJD(
    job_title='Data Scientist / Machine Learning Engineer',
    company='Analytics Corp',
    required_skills=[
        'advanced proficiency in python',
        'python (pandas, numpy, scikit-learn)',
        'sql',
        'strong foundation in statistical analysis and hypothesis testing',
        'experience with version control (git)',
        'experience with cloud platforms (aws, azure, or gcp)',
        'xgboost',
        'random forest',
        'lstms',
        'distilbert for sentiment analysis',
        'efficientnet for image classification',
        'streamlit',
        'gradio',
        'hugging face spaces',
    ],
    keywords=[
        'data pipeline', 'predictive modeling', 'etl', 'churn prediction',
        'customer segmentation', 'feature engineering', 'model deployment',
        'stakeholder reporting', 'interactive dashboards',
    ],
    responsibilities=[
        'Design and implement ETL pipelines using Python and SQL',
        'Develop and fine-tune machine learning models (XGBoost, Random Forest, LSTMs)',
        'Apply advanced techniques like DistilBERT and EfficientNet',
        'Create interactive dashboards in Power BI or Tableau',
        'Deploy models using Streamlit, Gradio, or Hugging Face Spaces',
    ],
)

# ============================================================
# RUN FULL TEST
# ============================================================
scorer = ATSScorer()
s1, b1, _ = scorer.score(resume, jd)
report = scorer.compare(original=resume, tailored=resume, jd=jd)
improver = ResumeImprover()

# Multi-pass with RE-SCORING
current = resume
best = s1
best_r = resume
missing = report.missing_skills
matched = report.matched_skills
recs = report.recommendations

for p in range(1, 4):
    imp = improver.improve(
        tailored_resume=current,
        matched_skills=matched,
        missing_skills=missing,
        jd_keywords=jd.keywords,
        recommendations=recs,
    )
    sc, _, _ = scorer.score(imp, jd)
    print(f"Pass {p}: {best:.1f} -> {sc:.1f} ({sc-best:+.1f})")
    if sc > best:
        best = sc
        best_r = imp
    if sc >= 85:
        print(f"  TARGET 85+ REACHED!")
        break
    rp = scorer.compare(original=resume, tailored=imp, jd=jd)
    missing = rp.missing_skills
    matched = rp.matched_skills
    recs = rp.recommendations
    current = imp

s2, b2, d2 = scorer.score(best_r, jd)
print()
print("=" * 60)
print(f"FINAL: {s1:.1f} -> {s2:.1f} (+{s2-s1:.1f} pts)")
print("=" * 60)
print(f"  keyword_match: {b1.keyword_match:.0f} -> {b2.keyword_match:.0f}")
print(f"  skills_match:  {b1.skills_match:.0f} -> {b2.skills_match:.0f}")
print(f"  experience:    {b1.experience_relevance:.0f} -> {b2.experience_relevance:.0f}")
print(f"  role_align:    {b1.role_alignment:.0f} -> {b2.role_alignment:.0f}")
print(f"  education:     {b1.education_fit:.0f} -> {b2.education_fit:.0f}")
print(f"  structure:     {b1.resume_structure:.0f} -> {b2.resume_structure:.0f}")
print(f"Skills: {len(resume.skills)} -> {len(best_r.skills)}")
print(f"Missing: {d2.get('skills', {}).get('missing', [])}")

# Determinism
scores = []
for _ in range(3):
    imp2 = improver.improve(tailored_resume=resume, matched_skills=report.matched_skills, missing_skills=report.missing_skills, jd_keywords=jd.keywords, recommendations=report.recommendations)
    sc2, _, _ = scorer.score(imp2, jd)
    scores.append(sc2)
print(f"Determinism: {scores} ({'PASS' if len(set(scores))==1 else 'FAIL'})")
