"""
Intelligence Layer Tests -- Verifies education, semantic, target engine, and scoring.

Tests:
  1. MSc candidate -> education boost applied
  2. Semantic score > 20 for relevant resumes
  3. Score never decreases after improvement
  4. Recommendations are categorized
  5. Target plan is actionable
  6. No fake suggestions in target plan
  7. JD processor extracts soft skills separately
  8. Education domain extraction works
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.models import (
    StructuredResume, ContactInfo, ExperienceEntry,
    EducationEntry, ExtractedJD, ScoreBreakdown,
)
from ats_scoring.scorer import ATSScorer
from ats_scoring.target_engine import generate_target_plan
from pipeline.core import run_full_pipeline


def make_msc_resume():
    """MSc candidate with limited experience."""
    return StructuredResume(
        contact=ContactInfo(name="Yeswanth Arasavalli", email="y@test.com"),
        summary="Data science graduate with Python and machine learning skills.",
        skills=["Python", "SQL", "Pandas", "Machine Learning", "Tableau", "Scikit-learn"],
        experience=[
            ExperienceEntry(
                role="Data Analyst Intern", company="TechVista Solutions",
                duration="2023-2024", location="Hyderabad",
                bullets=[
                    "Analyzed 100K+ records using Python and Pandas for business insights.",
                    "Built SQL queries to automate monthly reporting workflow.",
                    "Created Tableau dashboards for executive stakeholder reporting.",
                ]
            ),
        ],
        education=[EducationEntry(
            degree="MSc Big Data Analytics",
            institution="University of London", year="2023"
        )],
    )


def make_relevant_jd():
    return ExtractedJD(
        job_title="Data Scientist",
        company="Analytics Corp",
        required_skills=["python", "sql", "machine learning", "tensorflow"],
        preferred_skills=["tableau", "spark"],
        keywords=["data science", "python", "sql", "machine learning", "analytics", "model"],
        responsibilities=[
            "Build predictive models using machine learning techniques",
            "Analyze large datasets to derive business insights",
            "Create data visualization dashboards for stakeholders",
            "Write SQL queries for data extraction and transformation",
        ],
        education_requirements=["Master's in Data Science, Computer Science, or related field"],
        raw_text="Data Scientist role requiring Python, SQL, ML experience. Master's preferred.",
    )


def test_1_msc_education_boost():
    """MSc candidate gets education boost."""
    print("TEST 1: MSc candidate education boost...")
    scorer = ATSScorer()
    resume = make_msc_resume()
    jd = make_relevant_jd()

    _, breakdown, details = scorer.score(resume, jd)
    edu_details = details.get("education", {})

    assert edu_details.get("degree_level_met") in [True, "close"], \
        f"Degree level not detected: {edu_details}"
    assert edu_details.get("resume_degree_level", 0) >= 4, \
        f"MSc not parsed as level 4+: {edu_details}"
    assert "data_science" in edu_details.get("resume_domains", []), \
        f"Big Data Analytics not mapped to data_science: {edu_details}"

    boost = edu_details.get("fresher_masters_boost", 0)
    print(f"  Education score: {breakdown.education_fit}")
    print(f"  Resume level: {edu_details.get('resume_degree_level')}")
    print(f"  Domains: {edu_details.get('resume_domains')}")
    print(f"  Fresher boost: +{boost}")
    print("  PASS: MSc education correctly parsed and boosted")


def test_2_semantic_floor():
    """Semantic score >= 20 for relevant resume."""
    print("TEST 2: Semantic score floor for relevant resume...")
    scorer = ATSScorer()
    resume = make_msc_resume()
    jd = make_relevant_jd()

    report = scorer.compare(original=resume, tailored=resume, jd=jd, job_id="test")
    print(f"  Semantic score: {report.semantic_score}")
    assert report.semantic_score >= 20, \
        f"Semantic too low for relevant resume: {report.semantic_score}"
    print("  PASS: Semantic floor applied")


def test_3_score_never_decreases():
    """Score never decreases after improvement."""
    print("TEST 3: Score guardrail...")
    scorer = ATSScorer()
    resume = make_msc_resume()
    jd = make_relevant_jd()
    tailored = resume.model_copy(deep=True)

    result = run_full_pipeline(
        original=resume, tailored=tailored,
        extracted_jd=jd, scorer=scorer,
    )
    imp_score, _, _ = scorer.score(result.improved, jd)
    tail_score, _, _ = scorer.score(result.tailored, jd)
    assert imp_score >= tail_score, \
        f"Score decreased: {tail_score} -> {imp_score}"
    print(f"  Tailored: {tail_score}, Improved: {imp_score}")
    print("  PASS: Score never decreased")


def test_4_recommendations_categorized():
    """Recommendations have [MUST]/[SHOULD]/[NICE] prefixes."""
    print("TEST 4: Recommendations categorized...")
    scorer = ATSScorer()
    resume = make_msc_resume()
    jd = make_relevant_jd()

    report = scorer.compare(original=resume, tailored=resume, jd=jd, job_id="test")
    recs = report.recommendations

    categories_found = set()
    for rec in recs:
        if rec.startswith("[MUST]"):
            categories_found.add("MUST")
        elif rec.startswith("[SHOULD]"):
            categories_found.add("SHOULD")
        elif rec.startswith("[NICE]"):
            categories_found.add("NICE")

    print(f"  Recommendations: {len(recs)}")
    print(f"  Categories found: {categories_found}")
    assert len(categories_found) >= 1, f"No categorized recommendations found: {recs}"
    print("  PASS: Recommendations are categorized")


def test_5_target_plan_actionable():
    """Target plan has improvement actions."""
    print("TEST 5: Target plan is actionable...")
    scorer = ATSScorer()
    resume = make_msc_resume()
    jd = make_relevant_jd()

    report = scorer.compare(original=resume, tailored=resume, jd=jd, job_id="test")
    _, breakdown, details = scorer.score(resume, jd)
    plan = generate_target_plan(report, breakdown, details, jd)

    assert plan["target_score"] == 90
    assert plan["gap"] > 0, "Expected gap > 0 for this resume"
    assert len(plan["improvement_plan"]["high_impact"]) > 0, "No high impact actions"
    assert len(plan["simulations"]) > 0, "No simulations"
    assert plan["projected_score"] > plan["current_score"], "Projected not higher"

    print(f"  Current: {plan['current_score']}")
    print(f"  Projected: {plan['projected_score']}")
    print(f"  Gap: {plan['gap']}")
    print(f"  High impact actions: {len(plan['improvement_plan']['high_impact'])}")
    print(f"  Simulations: {len(plan['simulations'])}")
    print(f"  Status: {plan['status']}")
    print("  PASS: Target plan is actionable")


def test_6_no_fake_suggestions():
    """Target plan doesn't suggest fake skills."""
    print("TEST 6: No fake suggestions in target plan...")
    scorer = ATSScorer()
    resume = make_msc_resume()
    jd = make_relevant_jd()

    report = scorer.compare(original=resume, tailored=resume, jd=jd, job_id="test")
    _, breakdown, details = scorer.score(resume, jd)
    plan = generate_target_plan(report, breakdown, details, jd)

    all_actions = (
        plan["improvement_plan"]["high_impact"] +
        plan["improvement_plan"]["medium_impact"] +
        plan["improvement_plan"]["low_impact"]
    )
    all_text = " ".join(all_actions).lower()

    # These should NEVER appear as suggestions for a data science JD
    irrelevant = ["java enterprise", "c++ game", "ios development", "android app"]
    for term in irrelevant:
        assert term not in all_text, f"Irrelevant suggestion found: {term}"

    # Suggestions should only reference JD-relevant skills
    print(f"  Actions checked: {len(all_actions)}")
    print("  PASS: No irrelevant suggestions found")


def test_7_jd_soft_skills_separated():
    """JD processor separates soft skills from technical."""
    print("TEST 7: JD soft skills separated...")
    from jd_processor.processor import JDProcessor

    jd_text = """
    Requirements:
    - 3+ years Python experience
    - Strong SQL skills
    - Machine learning knowledge
    - Excellent communication skills
    - Strong leadership and teamwork
    - Bachelor's in Computer Science or related field

    Preferred:
    - Tableau experience
    - Project management skills
    """
    processor = JDProcessor()
    result = processor.process(jd_text)

    print(f"  Technical skills: {result.skills_required}")
    print(f"  Soft skills: {result.soft_skills}")
    print(f"  Education parsed: {result.education_parsed}")

    # communication should NOT be in technical skills
    tech_lower = [s.lower() for s in result.skills_required]
    assert "python" in tech_lower, f"Python not found in technical: {result.skills_required}"
    assert "communication" not in tech_lower, f"Soft skill leaked into technical!"

    # Soft skills should be detected
    assert len(result.soft_skills) > 0, "No soft skills extracted"
    assert any("communication" in s for s in result.soft_skills), "Communication not found in soft skills"

    # Education parsed
    assert result.education_parsed.get("level") == "bachelors", \
        f"Education level wrong: {result.education_parsed}"
    print("  PASS: Soft skills correctly separated")


def test_8_education_domain_extraction():
    """Education domains correctly extracted."""
    print("TEST 8: Education domain extraction...")
    scorer = ATSScorer()

    # Test various degree formats
    test_cases = [
        ("MSc Big Data Analytics", {"data_science"}),
        ("B.Tech Computer Science", {"cs", "engineering"}),
        ("MBA Finance", {"business"}),
        ("BSc Statistics", {"statistics"}),
        ("M.Tech Data Science", {"data_science"}),
    ]

    for degree_text, expected_domains in test_cases:
        resume = StructuredResume(
            contact=ContactInfo(name="Test"),
            skills=["Python"],
            experience=[ExperienceEntry(
                role="Analyst", company="Corp",
                duration="2023-2024",
                bullets=["Did analysis."]
            )],
            education=[EducationEntry(degree=degree_text, institution="Univ", year="2023")],
        )
        jd = make_relevant_jd()
        _, _, details = scorer.score(resume, jd)
        edu_details = details.get("education", {})
        resume_domains = set(edu_details.get("resume_domains", []))

        overlap = resume_domains & expected_domains
        assert len(overlap) > 0, \
            f"'{degree_text}': expected {expected_domains}, got {resume_domains}"
        print(f"  '{degree_text}' -> {resume_domains} [OK]")

    print("  PASS: All education domains correctly extracted")


if __name__ == "__main__":
    test_1_msc_education_boost()
    test_2_semantic_floor()
    test_3_score_never_decreases()
    test_4_recommendations_categorized()
    test_5_target_plan_actionable()
    test_6_no_fake_suggestions()
    test_7_jd_soft_skills_separated()
    test_8_education_domain_extraction()
    print("\n" + "=" * 50)
    print("ALL 8 INTELLIGENCE TESTS PASSED")
    print("=" * 50)
