"""Golden fixtures — synthetic candidates/JDs for hard-invariant evaluation.

Phase 2 (Golden Fixture / Evaluation Foundation). ALL DATA SYNTHETIC (spec §56):
fake names, example.com/test.com emails, 555 phones. No real PII.

Fixture set (spec §21 + Phase 6C expansion §38-42):
  A  strong_aligned          strong candidate, strong JD match
  B  weak_misaligned         weak candidate, demanding JD
  C  no_experience           fresher, zero professional experience
  D  truth_attack            JD demands skills absent from resume
  E  metric_protection       resume contains a quantified achievement
  F  identity_protection     name/employer/title/dates must survive
  G  improvement_regression  the reproduced 66.6 -> 60.7 regression case
6C archetypes x role categories (H-Q added, A-G never deleted/modified):
  H  fresh_grad              new grad w/ internship    -> Junior Software Eng
  I  career_switcher         teacher -> analytics      -> Data Analyst
  J  senior_ic               12y distributed systems   -> Staff Software Eng
  K  engineering_manager     IC -> people manager      -> Engineering Manager
  L  data_engineer           dbt/Snowflake stack       -> Analytics Engineer
  M  ml_engineer_gaps        strong ML, infra gaps     -> ML Engineer
  N  business_analyst        stakeholder reporting     -> Business Analyst
  O  devops                  linux/ansible, partial k8 -> Site Reliability Eng
  P  frontend                React/TypeScript          -> Frontend Engineer
  Q  quant_truth_attack      PhD math, no kdb+/scala   -> Quantitative Researcher
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


# ---------------------------------------------------------------------------
# Phase 6C (spec §38-42): 10 candidate archetypes x distinct role categories.
# Honesty invariants only — no brittle numerics, no expectations that could
# force score manipulation (spec §44). ALL SYNTHETIC data.
# ---------------------------------------------------------------------------

def fixture_H_fresh_grad():
    """Archetype: new graduate with one internship -> Junior Software Engineer."""
    resume = _resume(
        contact=ContactInfo(name="Jordan Lee", email="jordan@example.com", phone="555-0201"),
        summary="CS graduate with internship experience building web services.",
        skills=["Python", "Java", "Git", "MySQL"],
        experience=[ExperienceEntry(
            role="Software Engineering Intern", company="StartupWorks",
            duration="May 2024 - Aug 2024", location="Remote",
            bullets=["Built internal REST endpoints in Java used by two teams.",
                     "Wrote Python scripts automating nightly database backups."])],
        education=[EducationEntry(degree="BSc Computer Science",
                                  institution="Riverbend University", year="2024")],
        projects=[ProjectEntry(name="Library Manager",
                               bullets=["Full-stack CRUD app with MySQL and Flask."])],
    )
    jd = ExtractedJD(
        job_title="Junior Software Engineer", company="BuildRight",
        required_skills=["python", "java", "git", "sql"],
        preferred_skills=["docker"], keywords=["software engineer", "java", "python", "sql", "git"],
        responsibilities=["Develop and maintain web services", "Write unit tests"],
        raw_text="Junior SWE role.")
    return resume, jd


def fixture_I_career_switcher():
    """Archetype: teacher retrained in analytics -> Data Analyst.
    Teaching employment must never be recast as analyst employment."""
    resume = _resume(
        contact=ContactInfo(name="Sam Okafor", email="sam@example.com", phone="555-0202"),
        summary="High-school math teacher transitioning into data analytics.",
        skills=["Python", "SQL", "Excel"],
        experience=[ExperienceEntry(
            role="Mathematics Teacher", company="Northside High",
            duration="2019-2024", location="Atlanta",
            bullets=["Tracked student performance across 120 students per term in spreadsheets.",
                     "Designed graded assessments measuring conceptual mastery."])],
        education=[EducationEntry(degree="BA Mathematics",
                                  institution="State University", year="2019")],
        projects=[ProjectEntry(name="Bootcamp Capstone: Retail Churn",
                               bullets=["SQL and Python analysis of a public churn dataset."])],
    )
    jd = ExtractedJD(
        job_title="Data Analyst", company="InsightHub",
        required_skills=["sql", "python", "excel"],
        preferred_skills=["tableau"], keywords=["analyst", "sql", "python", "reporting", "dashboard"],
        responsibilities=["Build recurring reports", "Analyze operational datasets"],
        raw_text="Data Analyst role.")
    return resume, jd


def fixture_J_senior_ic():
    """Archetype: 12-year distributed-systems IC -> Staff Software Engineer."""
    resume = _resume(
        contact=ContactInfo(name="Priya Nair", email="priya@example.com", phone="555-0203"),
        summary="Distributed-systems engineer with twelve years designing low-latency services.",
        skills=["Go", "Kafka", "PostgreSQL", "Kubernetes", "gRPC"],
        experience=[
            ExperienceEntry(role="Senior Software Engineer", company="PayFlow",
                            duration="2016-2024", location="Seattle",
                            bullets=["Designed event-driven settlement pipeline on Kafka handling 40K msg/s.",
                                     "Cut p99 checkout latency 45% by reworking PostgreSQL query patterns."]),
            ExperienceEntry(role="Software Engineer", company="Telco Systems",
                            duration="2012-2016", location="Austin",
                            bullets=["Built gRPC service mesh for provisioning workflows."])],
    )
    jd = ExtractedJD(
        job_title="Staff Software Engineer", company="ScaleBase",
        required_skills=["go", "kubernetes", "distributed systems", "sql"],
        preferred_skills=["kafka"], keywords=["staff engineer", "distributed", "go", "kubernetes"],
        responsibilities=["Own architecture for core services", "Mentor senior engineers"],
        raw_text="Staff SWE role.")
    return resume, jd


def fixture_K_engineering_manager():
    """Archetype: IC who moved into people management -> Engineering Manager."""
    resume = _resume(
        contact=ContactInfo(name="Dana Whitfield", email="dana@example.com", phone="555-0204"),
        summary="Engineering manager with five years leading product teams.",
        skills=["Python", "AWS", "Agile", "Hiring"],
        experience=[
            ExperienceEntry(role="Engineering Manager", company="Cartwheel",
                            duration="2021-2025", location="Denver",
                            bullets=["Led a team of seven backend engineers through two product pivots.",
                                     "Hired six engineers; ran full-loop interviews and onboarding."]),
            ExperienceEntry(role="Senior Backend Engineer", company="Cartwheel",
                            duration="2018-2021", location="Denver",
                            bullets=["Built Python services on AWS serving the checkout domain."])],
    )
    jd = ExtractedJD(
        job_title="Engineering Manager", company="GridPoint",
        required_skills=["people management", "hiring", "python", "cloud"],
        preferred_skills=["agile"], keywords=["manager", "hiring", "lead", "team"],
        responsibilities=["Manage a team of backend engineers", "Own hiring pipeline"],
        raw_text="EM role.")
    return resume, jd


def fixture_L_data_engineer():
    """Archetype: modern analytics-engineering stack -> Analytics Engineer.
    JD also demands Airflow, which is genuinely absent -> must stay reported missing."""
    resume = _resume(
        contact=ContactInfo(name="Marco Silva", email="marco@example.com", phone="555-0205"),
        summary="Analytics engineer modeling warehouse data with dbt and Snowflake.",
        skills=["SQL", "Python", "dbt", "Snowflake"],
        experience=[ExperienceEntry(
            role="Analytics Engineer", company="DataHarbor",
            duration="2021-2025", location="Miami",
            bullets=["Modeled 300+ dbt tests across the core mart layer in Snowflake.",
                     "Migrated legacy SQL reports into version-controlled models."])],
    )
    jd = ExtractedJD(
        job_title="Analytics Engineer", company="WarehouseCo",
        required_skills=["sql", "python", "dbt", "snowflake", "airflow"],
        preferred_skills=["git"], keywords=["analytics engineer", "dbt", "snowflake", "etl"],
        responsibilities=["Own dbt models", "Orchestrate pipelines"],
        raw_text="Analytics Engineer role.")
    return resume, jd


def fixture_M_ml_engineer_gaps():
    """Archetype: strong modeling, weak infra -> ML Engineer (gap-heavy)."""
    resume = _resume(
        contact=ContactInfo(name="Ana Petrova", email="ana@example.com", phone="555-0206"),
        summary="Machine learning practitioner focused on tabular models.",
        skills=["Python", "Scikit-learn", "PyTorch", "Pandas"],
        experience=[ExperienceEntry(
            role="Data Scientist", company="CreditLens",
            duration="2020-2025", location="Boston",
            bullets=["Shipped a PyTorch fraud model reducing chargebacks by 18%.",
                     "Built gradient-boosted risk scores used in production lending."])],
    )
    jd = ExtractedJD(
        job_title="Machine Learning Engineer", company="DeployML",
        required_skills=["python", "pytorch", "kubernetes", "mlops", "aws"],
        preferred_skills=["terraform"], keywords=["ml engineer", "pytorch", "kubernetes", "mlops", "deploy"],
        responsibilities=["Train and deploy production ML models", "Own inference infrastructure"],
        raw_text="MLE role.")
    return resume, jd


def fixture_N_business_analyst():
    """Archetype: stakeholder-facing reporting analyst -> Business Analyst."""
    resume = _resume(
        contact=ContactInfo(name="Tomas Berg", email="tomas@example.com", phone="555-0207"),
        summary="Business analyst bridging operations and stakeholders.",
        skills=["Excel", "Power BI", "SQL", "Requirements Gathering"],
        experience=[ExperienceEntry(
            role="Business Analyst", company="Logistics Plus",
            duration="2020-2025", location="Chicago",
            bullets=["Produced weekly Power BI reports for 40+ store managers.",
                     "Gathered requirements from operations to scope a route-planning tool."])],
    )
    jd = ExtractedJD(
        job_title="Business Analyst", company="OpsValue",
        required_skills=["sql", "excel", "power bi", "stakeholder management"],
        preferred_skills=["tableau"], keywords=["business analyst", "reporting", "requirements", "stakeholder"],
        responsibilities=["Own recurring business reporting", "Elicit requirements"],
        raw_text="BA role.")
    return resume, jd


def fixture_O_devops():
    """Archetype: strong linux/ansible, partial k8s -> Site Reliability Engineer.
    Terraform is JD-only; it must never appear in the candidate's skills."""
    resume = _resume(
        contact=ContactInfo(name="Kenji Sato", email="kenji@example.com", phone="555-0208"),
        summary="Linux operations engineer automating fleets with Ansible.",
        skills=["Linux", "Bash", "Ansible", "Docker"],
        experience=[ExperienceEntry(
            role="Systems Administrator", company="HostWorks",
            duration="2018-2025", location="Portland",
            bullets=["Automated configuration of 900 Linux hosts with Ansible.",
                     "Used kubectl to debug container deployments on shared Kubernetes."])],
    )
    jd = ExtractedJD(
        job_title="Site Reliability Engineer", company="UptimeOne",
        required_skills=["kubernetes", "terraform", "linux", "prometheus"],
        preferred_skills=["python"], keywords=["sre", "kubernetes", "terraform", "monitoring", "linux"],
        responsibilities=["Own infrastructure as code", "Run incident response"],
        raw_text="SRE role.")
    return resume, jd


def fixture_P_frontend():
    """Archetype: product-focused UI engineer -> Frontend Engineer."""
    resume = _resume(
        contact=ContactInfo(name="Elif Demir", email="elif@example.com", phone="555-0209"),
        summary="Frontend engineer shipping accessible React interfaces.",
        skills=["JavaScript", "TypeScript", "React", "CSS", "Accessibility"],
        experience=[ExperienceEntry(
            role="Frontend Engineer", company="PixelRoom",
            duration="2020-2025", location="Remote",
            bullets=["Rebuilt checkout in React + TypeScript, lifting conversion 9%.",
                     "Drove WCAG 2.1 AA compliance across the component library."])],
    )
    jd = ExtractedJD(
        job_title="Frontend Engineer", company="WebCraft",
        required_skills=["react", "typescript", "css"],
        preferred_skills=["next.js"], keywords=["frontend", "react", "typescript", "ui"],
        responsibilities=["Build product UI in React", "Maintain design system"],
        raw_text="Frontend role.")
    return resume, jd


def fixture_Q_quant_truth_attack():
    """Archetype: PhD mathematician with no trading-stack exposure ->
    Quantitative Researcher. JD-only skills must stay honestly missing."""
    resume = _resume(
        contact=ContactInfo(name="Noor Haddad", email="noor@example.com", phone="555-0210"),
        summary="Mathematics PhD researching stochastic processes.",
        skills=["Python", "MATLAB", "Statistical Modeling", "R"],
        experience=[ExperienceEntry(
            role="Postdoctoral Researcher", company="State University Lab",
            duration="2021-2024", location="College Station",
            bullets=["Published two papers on stochastic volatility estimation.",
                     "Modeled option price dynamics with Python and MATLAB."])],
        education=[EducationEntry(degree="PhD Mathematics",
                                  institution="State University", year="2021")],
    )
    jd = ExtractedJD(
        job_title="Quantitative Researcher", company="TradeCore",
        required_skills=["c++", "kdb+", "scala", "statistics"],
        preferred_skills=["python"], keywords=["quant", "research", "trading", "c++", "statistics"],
        responsibilities=["Research alpha signals", "Implement models in C++"],
        raw_text="QR role.")
    return resume, jd


FIXTURES = {
    "A_strong_aligned": fixture_A_strong_aligned,
    "B_weak_misaligned": fixture_B_weak_misaligned,
    "C_no_experience": fixture_C_no_experience,
    "D_truth_attack": fixture_D_truth_attack,
    "E_metric_protection": fixture_E_metric_protection,
    "F_identity_protection": fixture_F_identity_protection,
    "G_improvement_regression": fixture_G_improvement_regression,
    # Phase 6C — 10 archetypes x distinct role categories (never delete A-G)
    "H_fresh_grad": fixture_H_fresh_grad,
    "I_career_switcher": fixture_I_career_switcher,
    "J_senior_ic": fixture_J_senior_ic,
    "K_engineering_manager": fixture_K_engineering_manager,
    "L_data_engineer": fixture_L_data_engineer,
    "M_ml_engineer_gaps": fixture_M_ml_engineer_gaps,
    "N_business_analyst": fixture_N_business_analyst,
    "O_devops": fixture_O_devops,
    "P_frontend": fixture_P_frontend,
    "Q_quant_truth_attack": fixture_Q_quant_truth_attack,
}
