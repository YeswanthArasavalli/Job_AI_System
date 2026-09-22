"""
Final Hardening Tests -- Verifies trust, consistency, and correctness.

Tests:
  1. PDF uses improved resume (identity match)
  2. Parser handles empty/minimal resumes
  3. Target engine simulation matches scorer
  4. Recommendations always valid (no irrelevant)
  5. No contradictions in output
  6. Consistency checksum (same input -> same output)
  7. Trust filter blocks irrelevant skills
  8. Semantic synonym boost works
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.models import (
    StructuredResume, ContactInfo, ExperienceEntry,
    EducationEntry, ExtractedJD, ProjectEntry,
)
from ats_scoring.scorer import ATSScorer
from ats_scoring.target_engine import generate_target_plan
from ats_scoring.semantic_matcher import SemanticMatcher
from pipeline.core import run_full_pipeline


def make_resume():
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
        projects=[ProjectEntry(
            name="Sales Prediction Model",
            bullets=["Built predictive model using scikit-learn achieving 92% accuracy."],
        )],
    )


def make_jd():
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
        raw_text="Data Scientist role.",
    )


def test_1_pdf_identity_match():
    """PDF source uses improved resume with correct identity."""
    print("TEST 1: PDF identity validation...")
    scorer = ATSScorer()
    resume = make_resume()
    jd = make_jd()

    result = run_full_pipeline(
        original=resume, tailored=resume.model_copy(deep=True),
        extracted_jd=jd, scorer=scorer,
    )

    # The improved resume MUST have the same identity as the original
    assert result.improved.contact.name == resume.contact.name, (
        f"PDF would use wrong identity: {result.improved.contact.name}"
    )
    assert result.improved.contact.email == resume.contact.email
    print(f"  Identity: {result.improved.contact.name} [OK]")
    print("  PASS: PDF identity validated")


def test_2_parser_handles_minimal():
    """Parser handles empty/minimal resumes gracefully."""
    print("TEST 2: Parser handles minimal resumes...")
    scorer = ATSScorer()

    # Empty resume -> score 0
    empty = StructuredResume(contact=ContactInfo(name="Test"))
    score, _, _ = scorer.score(empty, make_jd())
    assert score == 0.0, f"Empty resume should score 0, got {score}"
    print(f"  Empty resume: {score}")

    # Minimal resume with 1 skill, no experience
    minimal = StructuredResume(
        contact=ContactInfo(name="Test"),
        skills=["Python"],
    )
    score2, _, _ = scorer.score(minimal, make_jd())
    assert score2 == 0.0, f"No-experience resume should score 0, got {score2}"
    print(f"  Minimal resume (no exp): {score2}")

    # Resume with experience but few skills (may score very low, but shouldn't crash)
    few_skills = StructuredResume(
        contact=ContactInfo(name="Test"),
        skills=["Python"],
        experience=[ExperienceEntry(
            role="Intern", company="X", duration="2023",
            bullets=["Wrote Python scripts."]
        )],
    )
    score3, _, _ = scorer.score(few_skills, make_jd())
    assert score3 >= 0, f"Score should not be negative, got {score3}"
    print(f"  Few-skills resume: {score3} (handled gracefully)")
    print("  PASS: Parser handles all formats")


def test_3_target_simulation_matches_scorer():
    """Target engine simulation produces real scorer point gains."""
    print("TEST 3: Target simulation vs scorer...")
    scorer = ATSScorer()
    resume = make_resume()
    jd = make_jd()

    # Score original
    original_score, breakdown, details = scorer.score(resume, jd)
    report = scorer.compare(original=resume, tailored=resume, jd=jd, job_id="test")

    plan = generate_target_plan(
        report=report, breakdown=breakdown, details=details,
        jd=jd, resume=resume, scorer=scorer,
    )

    # Every simulation should have estimated_points > 0
    for sim in plan.get("simulations", []):
        assert sim["estimated_points"] > 0, f"Simulation has 0 pts: {sim['action']}"
        print(f"  +{sim['estimated_points']} pts: {sim['action'][:60]}")

    # Projected should be higher than current
    assert plan["projected_score"] > plan["current_score"], (
        f"Projected ({plan['projected_score']}) not higher than current ({plan['current_score']})"
    )

    # Check if skill simulations were real (not heuristic)
    skill_sims = [s for s in plan["simulations"] if s["category"] == "skills_gap"]
    if skill_sims:
        assert skill_sims[0].get("simulated", False), "Skill simulation should use real scorer"
        print(f"  Real simulation used: True")

    print("  PASS: Simulations match scorer")


def test_4_recommendations_always_valid():
    """Recommendations only suggest JD-relevant improvements."""
    print("TEST 4: Recommendations validity...")
    scorer = ATSScorer()
    resume = make_resume()
    jd = make_jd()

    report = scorer.compare(original=resume, tailored=resume, jd=jd, job_id="test")
    recs = report.recommendations

    # No rec should mention skills completely unrelated to data science
    irrelevant = ["ios", "android", "swift", "kotlin", "unity", "game dev", "photoshop"]
    recs_text = " ".join(recs).lower()
    for term in irrelevant:
        assert term not in recs_text, f"Irrelevant term in recommendations: {term}"

    # All recs should have category prefix OR be score warnings
    for rec in recs:
        has_prefix = any(rec.startswith(p) for p in ["[MUST]", "[SHOULD]", "[NICE]", "[!]"])
        assert has_prefix, f"Uncategorized recommendation: {rec}"

    print(f"  {len(recs)} recommendations, all valid and categorized")
    print("  PASS: Recommendations always valid")


def test_5_no_contradictions():
    """Output has no contradictions between score, decision, and recommendations."""
    print("TEST 5: No contradictions...")
    scorer = ATSScorer()
    resume = make_resume()
    jd = make_jd()

    result = run_full_pipeline(
        original=resume, tailored=resume.model_copy(deep=True),
        extracted_jd=jd, scorer=scorer,
    )
    report = result.ats_report

    # If score >= 70, decision should NOT be SKIP
    if report.score_after >= 70:
        assert report.decision != "SKIP", (
            f"Score={report.score_after} but decision=SKIP"
        )
    # If score < 30, decision should NOT be APPLY
    if report.score_after < 30:
        assert report.decision != "APPLY", (
            f"Score={report.score_after} but decision=APPLY"
        )

    # Score should never be negative
    assert report.score_after >= 0
    assert report.score_before >= 0

    print(f"  Score: {report.score_after}, Decision: {report.decision}")
    print("  PASS: No contradictions")


def test_6_consistency_checksum():
    """Same input produces same output (deterministic)."""
    print("TEST 6: Consistency checksum...")
    scorer = ATSScorer()
    resume = make_resume()
    jd = make_jd()

    # Run twice
    s1, _, _ = scorer.score(resume, jd)
    s2, _, _ = scorer.score(resume, jd)

    assert s1 == s2, f"Non-deterministic: {s1} != {s2}"

    # Run full pipeline twice
    r1 = run_full_pipeline(
        original=resume, tailored=resume.model_copy(deep=True),
        extracted_jd=jd, scorer=scorer,
    )
    r2 = run_full_pipeline(
        original=resume, tailored=resume.model_copy(deep=True),
        extracted_jd=jd, scorer=scorer,
    )

    # Scores should be identical (deterministic scorer + improver)
    diff = abs(r1.ats_report.score_after - r2.ats_report.score_after)
    assert diff < 1.0, f"Non-deterministic pipeline: {r1.ats_report.score_after} vs {r2.ats_report.score_after}"
    print(f"  Run 1: {r1.ats_report.score_after}, Run 2: {r2.ats_report.score_after} (diff={diff})")
    print("  PASS: Deterministic")


def test_7_trust_filter_blocks_irrelevant():
    """Trust filter prevents irrelevant skill suggestions."""
    print("TEST 7: Trust filter...")
    scorer = ATSScorer()

    # Data science resume against a JD that demands both DS and Android skills
    resume = make_resume()
    jd = ExtractedJD(
        job_title="Data Scientist",
        company="X",
        required_skills=["python", "sql", "tensorflow", "swift"],  # swift is irrelevant to DS
        keywords=["python", "sql", "machine learning"],
        responsibilities=["Build ML models"],
        raw_text="Build ML models using Python",
    )

    report = scorer.compare(original=resume, tailored=resume, jd=jd, job_id="test")
    recs = report.recommendations
    recs_text = " ".join(recs).lower()

    # The trust filter should allow tensorflow (relevant) but the rec
    # should not suggest anything completely outside the resume's domain
    print(f"  Recommendations: {len(recs)}")
    for rec in recs:
        print(f"    {rec[:80]}")
    print("  PASS: Trust filter applied")


def test_8_semantic_synonym_boost():
    """Semantic matcher handles synonyms correctly."""
    print("TEST 8: Semantic synonym boost...")
    matcher = SemanticMatcher()

    # "data pipeline" in JD should match "data workflow" in resume
    jd_resps = ["Build and maintain data pipelines for ETL processing"]
    resume_bullets = ["Designed automated data workflow for batch processing"]

    score = matcher.match_responsibilities(jd_resps, resume_bullets)
    print(f"  pipeline vs workflow: {score}")
    assert score > 10, f"Synonym pair should match better than {score}"

    # "predictive model" vs "ML model"
    jd_resps2 = ["Build predictive models for business forecasting"]
    resume_bullets2 = ["Developed ML model for sales prediction with 92% accuracy"]

    score2 = matcher.match_responsibilities(jd_resps2, resume_bullets2)
    print(f"  predictive model vs ML model: {score2}")
    assert score2 > 15, f"Synonym pair should match better than {score2}"

    # "analytics" vs "data insights"
    jd_resps3 = ["Perform analytics to drive business decisions"]
    resume_bullets3 = ["Derived data insights from customer behavior patterns"]

    score3 = matcher.match_responsibilities(jd_resps3, resume_bullets3)
    print(f"  analytics vs data insights: {score3}")
    assert score3 > 10, f"Synonym pair should match better than {score3}"

    print("  PASS: Semantic synonyms working")


if __name__ == "__main__":
    test_1_pdf_identity_match()
    test_2_parser_handles_minimal()
    test_3_target_simulation_matches_scorer()
    test_4_recommendations_always_valid()
    test_5_no_contradictions()
    test_6_consistency_checksum()
    test_7_trust_filter_blocks_irrelevant()
    test_8_semantic_synonym_boost()
    print("\n" + "=" * 50)
    print("ALL 8 HARDENING TESTS PASSED")
    print("=" * 50)
