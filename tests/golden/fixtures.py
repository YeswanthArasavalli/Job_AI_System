"""Golden fixtures — synthetic candidates/JDs for hard-invariant evaluation.

Phase 2 (Golden Fixture / Evaluation Foundation). ALL DATA SYNTHETIC (spec §56):
fake names, example.com/test.com emails, 555 phones. No real PII.

Fixture set (spec §21):
  A  strong_aligned          strong candidate, strong JD match
  B  weak_misaligned         weak candidate, demanding JD
  C  no_experience           fresher, zero professional experience
  D  truth_attack            JD demands skills absent from resume
  E  metric_protection       resume contains a quantified achievement
  F  identity_protection     name/employer/title/dates must survive
  G  improvement_regression  the reproduced 66.6 -> 60.7 regression case
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.models import (StructuredResume, ContactInfo, ExperienceEntry,
                          ProjectEntry, EducationEntry, ExtractedJD)


def _resume(**kw):
    base = dict(
        contact=ContactInfo(name="Alex Candidate", email="alex@example.com", phone="555-0100"),
        summary="",
        skills=[], experience=[], projects=[], education=[],
    )
    base.update(kw)
    return StructuredResume(**base)


def fixture_A_strong_aligned():
    resume = _resume(
        summary="Data science graduate with Python and machine learning skills.",
        skills=["Python", "SQL", "Pandas", "Machine Learning", "Tableau"],
        experience=[ExperienceEntry(
            role="Data Analyst Intern", company="TechVista Solutions",
            duration="2023-2024", location="Hyderabad",
            bullets=["Analyzed 100K+ records using Python and Pandas for business insights.",
                     "Built SQL queries to automate monthly reporting workflow.",
                     "Created Tableau dashboards for executive stakeholder reporting."])],
        education=[EducationEntry(degree="MSc Big Data Analytics",
                                  institution="University of London", year="2023")],
        projects=[ProjectEntry(name="Sales Prediction Model",
                               bullets=["Built predictive model using scikit-learn achieving 92% accuracy."])],
    )
    jd = ExtractedJD(
        job_title="Data Scientist", company="Analytics Corp",
        required_skills=["python", "sql", "machine learning"],
        preferred_skills=["tableau"],
        keywords=["data science", "python", "sql", "machine learning", "analytics", "model"],
        responsibilities=["Build predictive models using machine learning techniques",
                          "Analyze large datasets to derive business insights",
                          "Create data visualization dashboards for stakeholders"],
        education_requirements=["Master's in Data Science"], raw_text="Data Scientist role.")
    return resume, jd


def fixture_B_weak_misaligned():
    resume = _resume(
        summary="Customer support agent.",
        skills=["Excel", "PowerPoint"],
        experience=[ExperienceEntry(
            role="Support Associate", company="RetailMart",
            duration="2022-2023", location="Denver",
            bullets=["Answered customer emails daily.", "Made schedules in Excel."])],
    )
    jd = ExtractedJD(
        job_title="Senior Data Scientist", company="Analytics Corp",
        required_skills=["python", "sql", "machine learning", "tensorflow", "spark"],
        preferred_skills=["aws"],
        keywords=["data science", "python", "sql", "machine learning", "model"],
        responsibilities=["Build predictive models using machine learning techniques",
                          "Design distributed data pipelines"],
        required_experience_years=5,
        raw_text="Senior Data Scientist role.")
    return resume, jd


def fixture_C_no_experience():
    resume = _resume(
        summary="Recent graduate with Python skills.",
        skills=["Python"],
    )
    jd = ExtractedJD(
        job_title="Data Scientist", company="Analytics Corp",
        required_skills=["python", "sql", "machine learning", "tensorflow"],
        preferred_skills=["tableau", "spark"],
        keywords=["data science", "python", "sql", "machine learning", "analytics", "model"],
        responsibilities=["Build predictive models using machine learning techniques",
                          "Analyze large datasets to derive business insights",
                          "Create data visualization dashboards for stakeholders",
                          "Write SQL queries for data extraction and transformation"],
        education_requirements=["Master's in Data Science"], raw_text="Data Scientist role.")
    return resume, jd


def fixture_D_truth_attack():
    resume = _resume(
        summary="Backend developer with Python experience.",
        skills=["Python", "Flask"],
        experience=[ExperienceEntry(
            role="Backend Developer", company="WebWorks",
            duration="2022-2024", location="Austin",
            bullets=["Built REST APIs using Python and Flask.",
                     "Wrote unit tests with pytest."])],
    )
    jd = ExtractedJD(
        job_title="Kubernetes Platform Engineer", company="CloudNine",
        required_skills=["kubernetes", "terraform", "go", "aws"],
        preferred_skills=["python"],
        keywords=["kubernetes", "terraform", "go", "aws", "infrastructure"],
        responsibilities=["Manage Kubernetes clusters", "Write Terraform modules"],
        raw_text="Platform Engineer role.")
    return resume, jd


def fixture_E_metric_protection():
    resume = _resume(
        summary="Analyst with quantified achievements.",
        skills=["SQL", "Python"],
        experience=[ExperienceEntry(
            role="Analyst", company="DataCorp",
            duration="2021-2024", location="Boston",
            bullets=["Optimized warehouse queries improving accuracy by 92%.",
                     "Built ETL pipelines processing 150K+ records."])],
    )
    jd = ExtractedJD(
        job_title="Data Engineer", company="Analytics Corp",
        required_skills=["sql", "python", "etl"],
        preferred_skills=[],
        keywords=["sql", "python", "etl", "data", "pipeline"],
        responsibilities=["Build ETL pipelines", "Optimize SQL queries"],
        raw_text="Data Engineer role.")
    return resume, jd


def fixture_F_identity_protection():
    resume = _resume(
        contact=ContactInfo(name="Riley Quinn", email="riley@example.com", phone="555-0133"),
        summary="Marketing analyst.",
        skills=["SQL", "Tableau", "Google Analytics"],
        experience=[ExperienceEntry(
            role="Marketing Analyst", company="BrandHouse Media",
            duration="Mar 2021 - Present", location="Chicago",
            bullets=["Ran weekly reporting for 12 client accounts.",
                     "Built Tableau dashboards for campaign tracking."])],
        education=[EducationEntry(degree="BA Marketing", institution="State College", year="2020")],
    )
    jd = ExtractedJD(
        job_title="Marketing Data Analyst", company="AdScale",
        required_skills=["sql", "tableau"],
        preferred_skills=["google analytics"],
        keywords=["marketing", "sql", "tableau", "analytics", "reporting"],
        responsibilities=["Build campaign dashboards", "Analyze marketing data"],
        raw_text="Marketing Data Analyst role.")
    return resume, jd


def fixture_G_improvement_regression():
    """The reproduced regression fixture (Intelligence suite: 66.6 -> 60.7)."""
    resume = _resume(
        contact=ContactInfo(name="Morgan Lee", email="morgan@example.com", phone="555-0144"),
        summary="MSc Data Science graduate with machine learning project experience.",
        skills=["Python", "SQL", "Pandas", "Machine Learning", "Scikit-learn", "Tableau"],
        experience=[ExperienceEntry(
            role="Data Analyst Intern", company="HealthTech Systems",
            duration="2023-2024", location="London",
            bullets=["Analyzed patient datasets using Python and Pandas to surface treatment trends.",
                     "Automated weekly reporting with SQL, reducing manual effort.",
                     "Created Tableau dashboards viewed by clinical stakeholders."])],
        education=[EducationEntry(degree="MSc Data Science", institution="City University", year="2023")],
        projects=[ProjectEntry(name="Readmission Prediction",
                               bullets=["Trained a scikit-learn model predicting readmissions with 84% accuracy."])],
    )
    jd = ExtractedJD(
        job_title="Junior Data Scientist", company="Analytics Corp",
        required_skills=["python", "sql", "machine learning", "pandas"],
        preferred_skills=["scikit-learn", "tableau"],
        keywords=["data science", "python", "sql", "machine learning", "model", "analytics"],
        responsibilities=["Build predictive models using machine learning techniques",
                          "Analyze large datasets to derive business insights",
                          "Create data visualization dashboards for stakeholders",
                          "Write SQL queries for data extraction and transformation"],
        education_requirements=["Master's in Data Science"], raw_text="Junior Data Scientist role.")
    return resume, jd


FIXTURES = {
    "A_strong_aligned": fixture_A_strong_aligned,
    "B_weak_misaligned": fixture_B_weak_misaligned,
    "C_no_experience": fixture_C_no_experience,
    "D_truth_attack": fixture_D_truth_attack,
    "E_metric_protection": fixture_E_metric_protection,
    "F_identity_protection": fixture_F_identity_protection,
    "G_improvement_regression": fixture_G_improvement_regression,
}
