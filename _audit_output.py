"""Audit current output quality — identify human-quality gaps."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from utils.models import *
from resume_engine.summary_engine import generate_professional_summary
from resume_engine.polish_engine import polish_resume

resume = StructuredResume(
    contact=ContactInfo(name="Alex Johnson", email="alex@ex.com", phone="555", location="SF"),
    title="Data Scientist",
    summary="I am a passionate and dedicated data scientist with strong background in Python.",
    skills=["Python", "SQL", "pandas", "scikit-learn", "TensorFlow", "AWS", "NLP", "Docker"],
    experience=[
        ExperienceEntry(role="Data Scientist", company="TechCorp", duration="2022-Present",
            bullets=[
                "Was responsible for building and maintaining the ML pipeline for the recommendation engine.",
                "Helped with data preprocessing and feature engineering tasks using pandas.",
                "Worked on deploying models to production using Docker containers.",
                "I analyzed customer behavior data to find patterns and trends.",
                "Successfully completed a project to improve model accuracy by 15%.",
                "Used Python for scripting.",
                "Attended team meetings.",
            ]),
        ExperienceEntry(role="Junior Analyst", company="DataStart", duration="2020-2022",
            bullets=[
                "Assisted in creating reports for the sales team.",
                "Had to manage data quality issues across multiple databases.",
                "Looked at large datasets to identify anomalies using SQL.",
                "Tasks included data entry.",
            ]),
    ],
    projects=[ProjectEntry(name="Churn Predictor", description="ML", technologies=["Python"],
        bullets=["Built a classification model using scikit-learn with 92% accuracy.", "Processed 50K customer records."])],
    education=[EducationEntry(institution="UC Berkeley", degree="M.S. Data Science", year="2020", details="GPA 3.8")],
)

role_info = {"role_type": "data", "allow_tech_injection": True}

# 1. Summary
summary = generate_professional_summary(resume, role_info, ["machine learning", "NLP", "python"], ["Python", "SQL", "TensorFlow"])
print("=== SUMMARY OUTPUT ===")
print(repr(summary))
print()

# 2. Polish
polished, changes = polish_resume(resume.model_copy(deep=True), "data")
print("=== POLISH OUTPUT ===")
for exp in polished.experience:
    print(f"  [{exp.role} at {exp.company}]")
    for b in exp.bullets:
        print(f"    - {b}")
print(f"\n  Total changes: {len(changes)}")
for c in changes:
    t = c["type"]
    b = c["before"][:45]
    a = c["after"][:45]
    print(f"    [{t}] {b} -> {a}")
