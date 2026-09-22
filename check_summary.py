"""Quick check: what summary does the improver produce for the test resume?"""
import sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
for h in logging.root.handlers[:]: logging.root.removeHandler(h)
logging.basicConfig(stream=io.StringIO(), level=logging.CRITICAL)
for n in logging.Logger.manager.loggerDict: logging.getLogger(n).disabled = True

from utils.models import *
from ats_scoring.scorer import ATSScorer
from resume_engine.improver import ResumeImprover

scorer = ATSScorer()
imp = ResumeImprover()

resume = StructuredResume(
    contact=ContactInfo(name="Alex", email="a@e.com", phone="555"),
    title="Data Scientist",
    summary="Experienced data scientist with a passion for solving complex problems.",
    skills=["Python","SQL","Machine Learning","TensorFlow","NLP","Docker","AWS","Spark","scikit-learn","Pandas"],
    experience=[
        ExperienceEntry(role="Data Scientist", company="TC", duration="2022-Present",
            bullets=["Built predictive models for customer churn reducing attrition by 15%.",
                     "Analyzed large datasets to identify trends and patterns.",
                     "Created automated reports for the executive team.",
                     "Collaborated with engineering to deploy solutions."]),
        ExperienceEntry(role="Junior Data Analyst", company="SI", duration="2019-2022",
            bullets=["Performed data analysis using SQL queries.",
                     "Generated weekly business reports for stakeholders.",
                     "Assisted in building dashboards for KPI tracking."]),
    ],
    projects=[
        ProjectEntry(name="Sentiment", description="NLP", technologies=["Python","TensorFlow"],
            bullets=["Built real-time sentiment analysis pipeline processing 100K tweets using TensorFlow.",
                     "Deployed model as REST API using Flask with 99.5% uptime."]),
        ProjectEntry(name="Forecasting", description="TS", technologies=["Python","Spark"],
            bullets=["Developed time-series forecasting model achieving 94% accuracy.",
                     "Processed 5M records using Spark for feature engineering."]),
    ],
    education=[EducationEntry(degree="M.S. Data Science", institution="Stanford", year="2019")],
)

jd = ExtractedJD(
    job_title="Senior Data Scientist", company="BigTech",
    required_skills=["Python","Machine Learning","Deep Learning","SQL","TensorFlow","NLP","Data Pipelines"],
    preferred_skills=["Docker","AWS","Kubernetes","Spark"],
    keywords=["machine learning","deep learning","data pipelines","model deployment",
              "python","sql","nlp","tensorflow","predictive modeling","data visualization"],
    responsibilities=["Design ML models"], required_experience_years=5,
)

_, _, d = scorer.score(resume, jd)
mi = d.get("skills", {}).get("missing", [])
ma = d.get("skills", {}).get("matched", [])
kw = d.get("keywords", {}).get("matched", []) + d.get("keywords", {}).get("missing", [])

strict = imp.improve(resume.model_copy(deep=True), mi, ma, [], kw, mode="strict")
balanced = imp.improve(resume.model_copy(deep=True), mi, ma, [], kw, mode="balanced")

print("STRICT SUMMARY:", strict.summary)
print("BALANCED SUMMARY:", balanced.summary)
print()

# Check generic
generic = ["experienced", "hardworking", "passionate", "dedicated professional"]
for g in generic:
    if g in strict.summary.lower():
        print(f"  GENERIC MATCH: '{g}' in strict summary")
    if g in balanced.summary.lower():
        print(f"  GENERIC MATCH: '{g}' in balanced summary")

# Score comparison
s1, _, _ = scorer.score(strict, jd)
s2, _, _ = scorer.score(balanced, jd)
print(f"\nStrict score: {s1}")
print(f"Balanced score: {s2}")
print(f"Gap: {s1 - s2:.1f}")

# Bullet comparison
st = " ".join(b for e in strict.experience for b in e.bullets)
bt = " ".join(b for e in balanced.experience for b in e.bullets)
print(f"Text differs: {st != bt}")
print(f"Strict text len: {len(st)}")
print(f"Balanced text len: {len(bt)}")
