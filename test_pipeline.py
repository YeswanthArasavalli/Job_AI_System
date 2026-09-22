"""Test the Job Pipeline with sample job listings."""
import logging
logging.disable(logging.WARNING)

from pipeline.job_pipeline import run_daily_pipeline
from utils.models import *

resume = StructuredResume(
    contact=ContactInfo(name='Yeswanth', email='m@g.com'), title='Data Scientist',
    summary='Data Scientist with 3+ years in ML and analytics.',
    skills=['Python', 'SQL', 'R', 'Machine Learning', 'Pandas', 'NumPy',
            'Scikit-learn', 'PyTorch', 'Tableau', 'Power BI', 'AWS', 'ETL Pipelines',
            'Data Analysis', 'Deep Learning', 'NLP', 'Computer Vision'],
    experience=[
        ExperienceEntry(role='AI Data Annotation', company='Telus', duration='Feb 2024 - Present',
            bullets=['Labeled large-scale NLP and CV datasets for model training.',
                     'Optimized prompts to improve AI output precision.']),
        ExperienceEntry(role='DS Intern', company='Postulate', duration='Jan 2024 - Feb 2024',
            bullets=['Cleaned 150K+ NLP records, improving quality by 30%.',
                     'Built forecasting models improving accuracy by 22%.']),
    ],
    education=[EducationEntry(degree='MS in CS (Big Data Analytics)', institution='Central Univ')]
)

# Sample job listings (simulating what a scraper would produce)
jobs = [
    {
        "company": "Google",
        "role": "Senior Data Scientist",
        "job_description": """Senior Data Scientist at Google. 
        Requirements: 5+ years experience in data science. Python, SQL, TensorFlow, 
        Machine Learning, Deep Learning, NLP. Must have experience with large-scale 
        data pipelines and model deployment. Responsibilities: Build ML models, 
        deploy to production, mentor junior team members.""",
        "apply_link": "https://careers.google.com/123",
        "salary": "$180,000 - $250,000",
    },
    {
        "company": "Startup AI Co",
        "role": "Data Analyst",
        "job_description": """Data Analyst needed. 1-2 years experience.
        Skills: SQL, Python, Excel, Tableau, Power BI, Data Analysis.
        Responsibilities: Build dashboards, analyze metrics, report to stakeholders.
        Nice to have: Machine Learning basics.""",
        "apply_link": "https://startupai.com/apply",
        "salary": "$70,000 - $90,000",
    },
    {
        "company": "Amazon",
        "role": "ML Engineer",
        "job_description": """Machine Learning Engineer. 3+ years experience.
        Required: Python, PyTorch, TensorFlow, AWS, Docker, Kubernetes.
        Deep Learning, Computer Vision, NLP. Experience with CI/CD pipelines.
        Responsibilities: Design and deploy ML systems at scale.""",
        "apply_link": "https://amazon.jobs/456",
    },
    {
        "company": "Local Corp",
        "role": "Junior Python Developer",
        "job_description": """Junior Python Developer. Entry level.
        Skills: Python, Git, REST APIs, Django, PostgreSQL.
        Responsibilities: Build backend services, write unit tests.""",
        "apply_link": "https://localcorp.com/apply",
    },
    {
        "company": "DataViz Inc",
        "role": "BI Analyst",
        "job_description": """BI Analyst. 1-3 years experience.
        Skills: Tableau, Power BI, SQL, Excel, Data Analysis, KPI Reporting.
        Responsibilities: Create dashboards, analyze business metrics, 
        present findings to leadership.""",
        "apply_link": "https://dataviz.com/apply",
        "salary": "$65,000 - $85,000",
    },
    {
        "company": "TechGiant",
        "role": "DevOps Engineer",
        "job_description": """DevOps Engineer. 4+ years experience.
        Skills: Docker, Kubernetes, Terraform, AWS, CI/CD, Linux, Jenkins.
        Responsibilities: Manage cloud infrastructure, automate deployments.""",
    },
    {
        "company": "Invalid Co",
        "role": "",
        "job_description": "short",  # Should be discarded
    },
]

print("=" * 60)
print("DAILY JOB PIPELINE TEST")
print("=" * 60)

result = run_daily_pipeline(jobs, resume, max_applications=5)

print(f"\n📊 SUMMARY")
print(f"  Input: {result['summary']['total_input']} jobs")
print(f"  Valid: {result['summary']['total_valid']} jobs")
print(f"  APPLY NOW: {result['summary']['apply_now']}")
print(f"  FIX GAPS: {result['summary']['fix_gaps']}")
print(f"  SKIP: {result['summary']['skip']}")
print(f"  Today's Plan: {result['summary']['today_applications']} applications")
print(f"  Best Variant: {result['summary']['best_variant']}")

print(f"\n📅 TODAY'S PLAN:")
for i, job in enumerate(result['plan']['plan'], 1):
    emoji = job['decision_emoji']
    print(f"  {i}. {emoji} {job['company']} — {job['role']}")
    print(f"     Decision: {job['decision']} | Prob: {job['shortlist_probability']}% | Match: {job['jd_match_score']}/100")
    print(f"     Root Cause: {job['root_cause']} | Variant: {job.get('variant_name', '?')}")
    print(f"     Risk: {job['top_risk']}")
    if job.get('apply_link'):
        print(f"     Link: {job['apply_link']}")
    print()

print(f"\n⏭️ SKIPPED JOBS:")
skipped = [e for e in result['all_evaluations'] if e['decision'] == 'SKIP']
for job in skipped:
    print(f"  ⏭️ {job['company']} — {job['role']} (prob: {job['shortlist_probability']}%, cause: {job['root_cause']})")

print(f"\n✅ PIPELINE COMPLETE")
