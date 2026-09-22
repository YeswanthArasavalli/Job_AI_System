"""Test the Job Monitor with sample data."""
import logging
logging.disable(logging.WARNING)

from pipeline.job_monitor import run_monitoring_cycle
from utils.models import *

resume = StructuredResume(
    contact=ContactInfo(name='Yeswanth', email='m@g.com'), title='Data Scientist',
    summary='Data Scientist with 3+ years in ML and analytics.',
    skills=['Python', 'SQL', 'R', 'Machine Learning', 'Pandas', 'NumPy',
            'Scikit-learn', 'PyTorch', 'Tableau', 'Power BI', 'AWS', 'ETL Pipelines',
            'Data Analysis', 'Deep Learning', 'NLP', 'Computer Vision'],
    experience=[
        ExperienceEntry(role='AI Data Annotation', company='Telus', duration='2y',
            bullets=['Labeled large-scale NLP and CV datasets.', 'Optimized prompts.']),
        ExperienceEntry(role='DS Intern', company='Postulate', duration='1mo',
            bullets=['Cleaned 150K+ NLP records.', 'Built forecasting models.']),
    ],
    education=[EducationEntry(degree='MS in CS', institution='Central Univ')]
)

jobs = [
    {"company": "Google", "role": "Senior Data Scientist",
     "job_description": "Senior DS. 5+ years. Python, SQL, TensorFlow, ML, NLP. Large-scale data pipelines.",
     "apply_link": "https://google.com/apply", "salary": "$200K"},
    {"company": "Startup AI", "role": "Data Analyst",
     "job_description": "Data Analyst. 1-2 years. SQL, Python, Excel, Tableau, Power BI, Data Analysis.",
     "apply_link": "https://startup.com/apply"},
    {"company": "Amazon", "role": "ML Engineer",
     "job_description": "ML Engineer. 3+ years. Python, PyTorch, AWS, Docker, Deep Learning, NLP.",
     "apply_link": "https://amazon.com/apply"},
    {"company": "DataViz", "role": "BI Analyst",
     "job_description": "BI Analyst. 1-3 years. Tableau, Power BI, SQL, Excel, KPI Reporting.",
     "apply_link": "https://dataviz.com/apply"},
    {"company": "TechGiant", "role": "DevOps Engineer",
     "job_description": "DevOps. 4+ years. Docker, Kubernetes, Terraform, AWS, CI/CD, Linux.",
     "apply_link": "https://tech.com/apply"},
]

result = run_monitoring_cycle(jobs, resume)

print("=" * 60)
print("MONITORING CYCLE RESULTS")
print("=" * 60)

s = result["summary"]
print(f"\n📊 Summary:")
print(f"  Jobs: {s['valid_jobs']}/{s['total_jobs']} valid")
print(f"  Alerts: {s['total_alerts']} ({s['high_priority']} HIGH, {s['medium_priority']} MEDIUM)")
print(f"  Daily suggestions: {s['daily_suggestions']}")
print(f"  Weekly trend: {s['weekly_trend']}")
print(f"  Strategy: {s['strategy_direction']}")

print(f"\n🔔 ALERTS:")
for tier, jobs in [("HIGH", result["alerts"]["high"]), ("MEDIUM", result["alerts"]["medium"])]:
    for j in jobs:
        print(f"  {j['priority_emoji']} [{tier}] {j['company']} — {j['role']} (prob: {j['shortlist_probability']}%)")

print(f"\n📅 TODAY'S SUGGESTIONS:")
for i, s in enumerate(result["daily_suggestion"]["suggestions"], 1):
    print(f"  {i}. {s['priority_emoji']} {s['company']} — {s['role']}")

print(f"\n📊 WEEKLY REPORT:")
wr = result["weekly_report"]
print(f"  {wr['trend_emoji']} Trend: {wr['trend']}")
print(f"  Best variant: {wr['best_variant']}")
for step in wr["next_week_plan"]:
    print(f"  → {step}")

print(f"\n🧠 ADAPTIVE STRATEGY:")
ast = result["adaptive_strategy"]
print(f"  Direction: {ast['overall_direction']} (confidence: {ast['confidence']})")
for adj in ast["adjustments"]:
    print(f"  {adj['type']}: {adj['current']} → {adj['recommended']}")

print(f"\n✅ MONITORING CYCLE COMPLETE")
