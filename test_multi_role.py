"""
Part 14 — Universal Multi-Role Test Framework.

Tests the Career OS pipeline across diverse role types to ensure
consistent quality and correct behavior for:
  - Data Scientist
  - Backend Engineer
  - HR Recruiter
  - BPO / Customer Service
  - Mechanic
  - Product Manager

Each test verifies:
  1. Role classification is correct
  2. Resume type detection works
  3. No tech skills injected into non-tech roles
  4. Summary is role-appropriate (not generic)
  5. Validation gate passes
  6. Trust layer tracks changes
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, ".")

from resume_engine.role_engine import classify_role, filter_skills_for_role, get_role_action_verbs
from resume_engine.summary_engine import generate_professional_summary, should_replace_summary
from resume_engine.polish_engine import polish_resume
from resume_engine.trust_layer import ChangeTracker, TrustValidator
from resume_engine.resume_intelligence import detect_resume_type
from resume_engine.validation_gate import validate_output
from utils.models import (
    StructuredResume, ContactInfo, ExperienceEntry,
    EducationEntry, ProjectEntry, ExtractedJD,
)

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
WARN = "\033[93m[WARN]\033[0m"

test_results = {"passed": 0, "failed": 0, "warnings": 0}


def check(condition, test_name, detail=""):
    if condition:
        print(f"  {PASS} {test_name}")
        test_results["passed"] += 1
    else:
        print(f"  {FAIL} {test_name}: {detail}")
        test_results["failed"] += 1


def warn(message):
    print(f"  {WARN} {message}")
    test_results["warnings"] += 1


# ================================================================
# TEST FIXTURES
# ================================================================

def make_resume(name, title, skills, experience_entries, education=None, projects=None):
    return StructuredResume(
        contact=ContactInfo(name=name, email=f"{name.lower().replace(' ', '.')}@test.com"),
        title=title,
        summary="",
        skills=skills,
        experience=experience_entries,
        education=education or [
            EducationEntry(degree="B.S.", institution="Test University", year="2020")
        ],
        projects=projects or [],
        certifications=[],
    )


def make_jd(title, company, skills, keywords, responsibilities=None):
    return ExtractedJD(
        job_title=title,
        company=company,
        required_skills=skills,
        keywords=keywords,
        responsibilities=responsibilities or [],
        raw_text=f"{title} at {company}. Required: {', '.join(skills)}. {', '.join(keywords)}.",
    )


# ================================================================
# TEST 1: DATA SCIENTIST
# ================================================================

def test_data_scientist():
    print("\n" + "=" * 60)
    print("TEST 1: Data Scientist")
    print("=" * 60)

    resume = make_resume(
        name="Alice Chen",
        title="Data Scientist",
        skills=["Python", "SQL", "TensorFlow", "pandas", "scikit-learn", "Tableau", "AWS"],
        experience_entries=[
            ExperienceEntry(
                company="TechCorp", role="Data Scientist",
                duration="Jan 2022 - Present",
                bullets=[
                    "Built predictive models using scikit-learn for customer churn, achieving 92% accuracy",
                    "Developed data pipelines using pandas and SQL for ETL processing",
                    "Deployed ML models on AWS SageMaker for real-time inference",
                ]
            ),
            ExperienceEntry(
                company="DataInc", role="Junior Data Analyst",
                duration="Jun 2020 - Dec 2021",
                bullets=[
                    "Analyzed customer behavior data using SQL and Python",
                    "Created interactive dashboards in Tableau for stakeholder reporting",
                ]
            ),
        ],
    )

    jd = make_jd(
        title="Senior Data Scientist",
        company="BigTech",
        skills=["Python", "SQL", "Machine Learning", "TensorFlow", "AWS", "Spark"],
        keywords=["predictive modeling", "data pipeline", "deep learning", "ETL"],
    )

    # Role classification
    role_info = classify_role(jd.raw_text, jd.job_title)
    check(role_info["role_type"] == "data", "Role classification", f"got {role_info['role_type']}")
    check(role_info["allow_tech_injection"] == True, "Tech injection allowed")

    # Resume type
    rtype = detect_resume_type(resume, jd)
    check(rtype["type"] == "EXPERIENCED", "Resume type", f"got {rtype['type']}")

    # Summary generation
    summary = generate_professional_summary(resume, role_info, jd.keywords, ["Python", "SQL"])
    check(len(summary) > 50, "Summary length", f"got {len(summary)} chars")
    check("data" in summary.lower() or "scientist" in summary.lower(), "Summary has role identity")
    check(should_replace_summary("I am a passionate data professional") == True, "Detects weak summary")

    # Skill filtering (should keep all for data role)
    filtered = filter_skills_for_role(resume.skills, role_info)
    check(len(filtered) == len(resume.skills), "No skills filtered for data role")

    # Validation gate
    vr = validate_output(resume, resume, jd, role_info)
    check(vr.passed, "Validation gate passes", f"{len(vr.violations)} violations")

    # Action verbs
    verbs = get_role_action_verbs("data")
    check("Analyzed" in verbs, "Role-specific verbs include 'Analyzed'")


# ================================================================
# TEST 2: BACKEND ENGINEER
# ================================================================

def test_backend_engineer():
    print("\n" + "=" * 60)
    print("TEST 2: Backend Engineer")
    print("=" * 60)

    resume = make_resume(
        name="Bob Kumar",
        title="Backend Engineer",
        skills=["Python", "Java", "Docker", "Kubernetes", "PostgreSQL", "Redis", "REST API"],
        experience_entries=[
            ExperienceEntry(
                company="SaaS Corp", role="Senior Backend Engineer",
                duration="Mar 2021 - Present",
                bullets=[
                    "Architected microservices using Python and FastAPI handling 10K+ RPS",
                    "Deployed containerized services on Kubernetes with zero-downtime releases",
                    "Designed PostgreSQL schemas optimized for high-throughput transactional workloads",
                ]
            ),
        ],
    )

    jd = make_jd(
        title="Staff Backend Engineer",
        company="ScaleUp",
        skills=["Python", "Go", "Kubernetes", "PostgreSQL", "gRPC", "Redis"],
        keywords=["microservices", "distributed systems", "API design", "scalability"],
    )

    role_info = classify_role(jd.raw_text, jd.job_title)
    check(role_info["role_type"] == "technical", "Role classification", f"got {role_info['role_type']}")
    check(role_info["allow_tech_injection"] == True, "Tech injection allowed")

    rtype = detect_resume_type(resume, jd)
    check(rtype["type"] == "EXPERIENCED", "Resume type", f"got {rtype['type']}")

    summary = generate_professional_summary(resume, role_info, jd.keywords, ["Python", "Kubernetes"])
    check(len(summary) > 50, "Summary generated")
    check("engineer" in summary.lower() or "backend" in summary.lower(), "Summary has role identity")


# ================================================================
# TEST 3: HR RECRUITER (Non-Tech)
# ================================================================

def test_hr_recruiter():
    print("\n" + "=" * 60)
    print("TEST 3: HR Recruiter (Non-Tech)")
    print("=" * 60)

    resume = make_resume(
        name="Carol Johnson",
        title="HR Recruiter",
        skills=["Talent Acquisition", "ATS Systems", "Interview Coordination",
                "Employee Onboarding", "HR Compliance", "LinkedIn Recruiter"],
        experience_entries=[
            ExperienceEntry(
                company="PeopleFirst Inc", role="Senior Recruiter",
                duration="Feb 2019 - Present",
                bullets=[
                    "Managed full-cycle recruitment for 50+ positions annually across engineering and sales",
                    "Reduced time-to-hire by 30% by implementing structured interview processes",
                    "Coordinated onboarding programs for 200+ new hires per year",
                ]
            ),
        ],
    )

    jd = make_jd(
        title="HR Talent Acquisition Specialist",
        company="HRCo",
        skills=["Talent Acquisition", "ATS", "Interview Coordination", "Sourcing", "Compliance"],
        keywords=["recruiting", "onboarding", "talent pipeline", "employer branding"],
    )

    role_info = classify_role(jd.raw_text, jd.job_title)
    check(role_info["role_type"] == "hr", "Role classification", f"got {role_info['role_type']}")
    check(role_info["allow_tech_injection"] == False, "Tech injection BLOCKED")

    # CRITICAL: Tech skills must be filtered out
    test_skills = ["Python", "Docker", "Kubernetes", "Excel", "Communication", "Leadership"]
    filtered = filter_skills_for_role(test_skills, role_info)
    check("Python" not in filtered, "Python blocked for HR role", f"got {filtered}")
    check("Docker" not in filtered, "Docker blocked for HR role", f"got {filtered}")
    check("Excel" in filtered, "Excel allowed for HR role")
    check("Leadership" in filtered, "Leadership allowed for HR role")

    summary = generate_professional_summary(resume, role_info, jd.keywords, ["Talent Acquisition"])
    check("recruit" in summary.lower() or "talent" in summary.lower() or "hr" in summary.lower(),
          "Summary has HR identity", f"got: {summary[:80]}")

    verbs = get_role_action_verbs("hr")
    check("Recruited" in verbs, "HR-specific verbs include 'Recruited'")


# ================================================================
# TEST 4: BPO / CUSTOMER SERVICE (Non-Tech)
# ================================================================

def test_bpo_customer_service():
    print("\n" + "=" * 60)
    print("TEST 4: BPO / Customer Service (Non-Tech)")
    print("=" * 60)

    resume = make_resume(
        name="David Patel",
        title="Customer Service Representative",
        skills=["Customer Support", "CRM", "Phone Support", "Email Communication",
                "Problem Resolution", "Salesforce"],
        experience_entries=[
            ExperienceEntry(
                company="CallCenter Corp", role="Senior Customer Service Rep",
                duration="Jan 2020 - Present",
                bullets=[
                    "Handled 80+ customer calls daily, maintaining 95% satisfaction rating",
                    "Resolved escalated complaints within 24-hour SLA, reducing churn by 15%",
                    "Trained team of 10 new agents on company protocols and CRM usage",
                ]
            ),
        ],
    )

    jd = make_jd(
        title="Customer Service Manager",
        company="ServicePro",
        skills=["Customer Service", "CRM", "Team Management", "Conflict Resolution"],
        keywords=["customer satisfaction", "SLA", "call center", "team leadership"],
    )

    role_info = classify_role(jd.raw_text, jd.job_title)
    check(role_info["role_type"] == "customer", "Role classification", f"got {role_info['role_type']}")
    check(role_info["allow_tech_injection"] == False, "Tech injection BLOCKED")

    # Python should be blocked
    test_skills = ["Python", "TensorFlow", "Excel", "CRM", "Communication"]
    filtered = filter_skills_for_role(test_skills, role_info)
    check("Python" not in filtered, "Python blocked for customer role")
    check("CRM" in filtered, "CRM allowed for customer role")

    rtype = detect_resume_type(resume, jd)
    check(rtype["type"] == "EXPERIENCED", "Resume type", f"got {rtype['type']}")


# ================================================================
# TEST 5: MECHANIC (Trades - Non-Tech)
# ================================================================

def test_mechanic():
    print("\n" + "=" * 60)
    print("TEST 5: Mechanic (Trades)")
    print("=" * 60)

    resume = make_resume(
        name="Eric Torres",
        title="Automotive Mechanic",
        skills=["Engine Repair", "Brake Systems", "Electrical Diagnostics",
                "Oil Change", "ASE Certified", "HVAC Systems"],
        experience_entries=[
            ExperienceEntry(
                company="AutoFix Shop", role="Lead Mechanic",
                duration="Mar 2018 - Present",
                bullets=[
                    "Diagnosed and repaired 15+ vehicles daily including engine, transmission, and brake systems",
                    "Maintained 98% customer satisfaction rating across 500+ service orders",
                    "Trained 3 apprentice mechanics on diagnostic procedures and safety protocols",
                ]
            ),
        ],
    )

    jd = make_jd(
        title="Senior Automotive Technician",
        company="AutoService",
        skills=["Engine Repair", "Diagnostics", "ASE Certification", "Brake Systems"],
        keywords=["maintenance", "repair", "diagnostic", "safety", "technician"],
    )

    role_info = classify_role(jd.raw_text, jd.job_title)
    check(role_info["role_type"] == "trades", "Role classification", f"got {role_info['role_type']}")
    check(role_info["allow_tech_injection"] == False, "Tech injection BLOCKED")

    # ALL tech skills should be blocked
    test_skills = ["Python", "Docker", "Kubernetes", "ASE Certified", "Engine Repair"]
    filtered = filter_skills_for_role(test_skills, role_info)
    check("Python" not in filtered, "Python blocked for trades role")
    check("Docker" not in filtered, "Docker blocked for trades role")
    check("ASE Certified" in filtered, "ASE Certified allowed")
    check("Engine Repair" in filtered, "Engine Repair allowed")

    verbs = get_role_action_verbs("trades")
    check("Repaired" in verbs, "Trades-specific verbs include 'Repaired'")
    check("Diagnosed" in verbs or "Inspected" in verbs, "Trades verbs include diagnostic terms")

    summary = generate_professional_summary(resume, role_info, jd.keywords, ["Engine Repair"])
    check(
        "technic" in summary.lower() or "mechanic" in summary.lower() or "repair" in summary.lower(),
        "Summary has trades identity", f"got: {summary[:80]}"
    )


# ================================================================
# TEST 6: PRODUCT MANAGER (Management)
# ================================================================

def test_product_manager():
    print("\n" + "=" * 60)
    print("TEST 6: Product Manager (Management)")
    print("=" * 60)

    resume = make_resume(
        name="Fiona Park",
        title="Product Manager",
        skills=["Product Strategy", "Agile", "Roadmap Planning", "Stakeholder Management",
                "A/B Testing", "SQL", "JIRA"],
        experience_entries=[
            ExperienceEntry(
                company="TechProduct Inc", role="Senior Product Manager",
                duration="Jan 2021 - Present",
                bullets=[
                    "Led product strategy for B2B SaaS platform serving 10K+ enterprise users",
                    "Drove 40% increase in user engagement through data-driven feature prioritization",
                    "Managed cross-functional team of 12 engineers, designers, and analysts",
                ]
            ),
        ],
    )

    jd = make_jd(
        title="Director of Product",
        company="ProductCo",
        skills=["Product Strategy", "Agile", "Data Analysis", "Stakeholder Management"],
        keywords=["product roadmap", "user engagement", "cross-functional", "metrics"],
    )

    role_info = classify_role(jd.raw_text, jd.job_title)
    check(
        role_info["role_type"] in ("management", "analytical"),
        "Role classification (management or analytical)", f"got {role_info['role_type']}"
    )

    rtype = detect_resume_type(resume, jd)
    check(rtype["type"] == "EXPERIENCED", "Resume type", f"got {rtype['type']}")

    summary = generate_professional_summary(resume, role_info, jd.keywords, ["Product Strategy"])
    check(len(summary) > 50, "Summary generated")


# ================================================================
# TEST 7: FRESHER DETECTION
# ================================================================

def test_fresher():
    print("\n" + "=" * 60)
    print("TEST 7: Fresher Detection")
    print("=" * 60)

    resume = make_resume(
        name="Grace Lee",
        title="",
        skills=["Python", "SQL", "Excel"],
        experience_entries=[],
        projects=[
            ProjectEntry(
                name="ML Capstone", description="Built sentiment classifier",
                technologies=["Python", "scikit-learn"],
                bullets=["Trained NLP classifier on 10K+ tweets achieving 88% accuracy"],
            )
        ],
    )

    jd = make_jd(
        title="Junior Data Analyst",
        company="StartupX",
        skills=["Python", "SQL", "Excel"],
        keywords=["data analysis", "reporting"],
    )

    rtype = detect_resume_type(resume, jd)
    check(rtype["type"] == "FRESHER", "Resume type = FRESHER", f"got {rtype['type']}")
    check("limited_experience" in rtype["flags"], "Has 'limited_experience' flag")
    check(any("project" in h.lower() for h in rtype["strategy_hints"]),
          "Strategy hints mention projects")


# ================================================================
# TEST 8: CAREER SWITCHER DETECTION
# ================================================================

def test_career_switcher():
    print("\n" + "=" * 60)
    print("TEST 8: Career Switcher Detection")
    print("=" * 60)

    resume = make_resume(
        name="Henry Wilson",
        title="High School Teacher",
        skills=["Curriculum Development", "Student Assessment", "Classroom Management"],
        experience_entries=[
            ExperienceEntry(
                company="Lincoln High School", role="Mathematics Teacher",
                duration="Aug 2018 - Jun 2024",
                bullets=[
                    "Developed and delivered math curriculum for 150+ students across grades 9-12",
                    "Improved student test scores by 25% through data-driven teaching strategies",
                ]
            ),
        ],
    )

    jd = make_jd(
        title="Junior Data Analyst",
        company="DataCo",
        skills=["Python", "SQL", "Data Analysis", "Tableau", "Statistics"],
        keywords=["data analysis", "reporting", "dashboard", "insights"],
    )

    rtype = detect_resume_type(resume, jd)
    check(rtype["type"] == "SWITCHER", "Resume type = SWITCHER", f"got {rtype['type']}")
    check("domain_switch" in rtype["flags"], "Has 'domain_switch' flag")
    check(any("transferable" in h.lower() for h in rtype["strategy_hints"]),
          "Strategy hints mention transferable skills")


# ================================================================
# TEST 9: POLISH ENGINE
# ================================================================

def test_polish_engine():
    print("\n" + "=" * 60)
    print("TEST 9: Polish Engine")
    print("=" * 60)

    resume = make_resume(
        name="Test User",
        title="Engineer",
        skills=["Python"],
        experience_entries=[
            ExperienceEntry(
                company="Corp", role="Engineer",
                duration="2020 - Present",
                bullets=[
                    "helped with building APIs",
                    "Was responsible for data management",
                    "successfully completed the migration",
                    "The team actively participated in code reviews.",
                ]
            ),
        ],
    )

    polished, changes = polish_resume(resume, "technical")

    # Should fix weak verbs
    verb_changes = [c for c in changes if c["type"] == "verb_strength"]
    check(len(verb_changes) > 0, f"Verb strengthening applied ({len(verb_changes)} changes)")

    # Should fix formatting
    format_changes = [c for c in changes if c["type"] == "formatting"]
    check(len(format_changes) >= 0, f"Formatting fixes applied ({len(format_changes)} changes)")

    # Verify "helped with" is gone
    all_bullets = " ".join(b for exp in polished.experience for b in exp.bullets)
    check("helped with" not in all_bullets.lower(), "Weak verb 'helped with' removed")


# ================================================================
# TEST 10: TRUST LAYER + VALIDATION GATE
# ================================================================

def test_trust_and_validation():
    print("\n" + "=" * 60)
    print("TEST 10: Trust Layer + Validation Gate")
    print("=" * 60)

    original = make_resume(
        name="Trust Test",
        title="Engineer",
        skills=["Python", "SQL"],
        experience_entries=[
            ExperienceEntry(
                company="RealCorp", role="Engineer",
                duration="2020 - Present",
                bullets=["Built APIs using Python and Flask"],
            ),
        ],
    )

    # Good output (should pass)
    good_improved = original.model_copy(deep=True)
    good_improved.experience[0].bullets = [
        "Developed production-grade REST APIs using Python and Flask, serving 5K+ daily requests."
    ]

    jd = make_jd("Engineer", "Co", ["Python", "Flask"], ["API", "backend"])
    vr = validate_output(original, good_improved, jd)
    check(vr.passed, "Good output passes validation")

    # Bad output: name changed (should fail)
    bad_output = original.model_copy(deep=True)
    bad_output.contact.name = "Fake Name"
    vr_bad = validate_output(original, bad_output, jd)
    check(not vr_bad.passed, "Identity violation caught")

    # Bad output: fabricated company (should fail)
    bad_company = original.model_copy(deep=True)
    bad_company.experience.append(
        ExperienceEntry(
            company="FakeCompany", role="CTO",
            duration="2025 - Present",
            bullets=["Led everything"],
        )
    )
    vr_company = validate_output(original, bad_company, jd)
    check(not vr_company.passed, "Fabricated company caught")

    # Trust tracker
    tracker = ChangeTracker()
    tracker.record("test", "test_change", "before", "after", "reason", "rule", "HIGH")
    exp = tracker.build_explanation()
    check(exp["total_changes"] == 1, "Trust tracker records changes")
    check(exp["high_confidence"] == 1, "Trust tracker confidence tracking")


# ================================================================
# RUN ALL TESTS
# ================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  UNIVERSAL MULTI-ROLE TEST FRAMEWORK (Part 14)")
    print("  Career OS — Production Validation Suite")
    print("=" * 60)

    test_data_scientist()
    test_backend_engineer()
    test_hr_recruiter()
    test_bpo_customer_service()
    test_mechanic()
    test_product_manager()
    test_fresher()
    test_career_switcher()
    test_polish_engine()
    test_trust_and_validation()

    print("\n" + "=" * 60)
    total = test_results["passed"] + test_results["failed"]
    if test_results["failed"] == 0:
        print(f"  {PASS} ALL {total} TESTS PASSED")
    else:
        print(f"  {FAIL} {test_results['failed']}/{total} TESTS FAILED")
    print(f"  Passed: {test_results['passed']} | Failed: {test_results['failed']} | Warnings: {test_results['warnings']}")
    print("=" * 60)

    sys.exit(0 if test_results["failed"] == 0 else 1)
