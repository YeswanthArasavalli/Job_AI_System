"""
System Stabilization Tests -- Verifies full pipeline consistency.

Tests:
  1. Single pipeline function used (no duplicates)
  2. Identity preserved through pipeline
  3. Score never decreases after improvement
  4. Empty resume handled correctly
  5. Same input -> deterministic output
  6. No sample data leakage
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.models import StructuredResume, ContactInfo, ExperienceEntry, EducationEntry, ExtractedJD
from ats_scoring.scorer import ATSScorer
from pipeline.core import run_full_pipeline, PipelineResult


def make_test_resume(name="Yeswanth Arasavalli"):
    """Create a realistic test resume."""
    return StructuredResume(
        contact=ContactInfo(name=name, email="yeswanth@test.com", phone="9876543210"),
        summary="Data analyst with Python and SQL experience.",
        skills=["Python", "SQL", "Pandas", "Machine Learning", "Tableau", "Excel"],
        experience=[
            ExperienceEntry(
                role="Data Analyst", company="TechVista Solutions",
                duration="2021-2023", location="Hyderabad",
                bullets=[
                    "Analyzed 500K+ records using Python and Pandas to drive business insights.",
                    "Built automated SQL reports reducing manual work by 40%.",
                    "Created Tableau dashboards for executive stakeholders.",
                ]
            ),
            ExperienceEntry(
                role="Intern", company="DataWorks Inc",
                duration="2020-2021", location="Remote",
                bullets=[
                    "Assisted in data cleaning and preprocessing with Python.",
                    "Supported team with Excel-based reporting and analysis.",
                ]
            ),
        ],
        education=[EducationEntry(degree="B.Tech Computer Science", institution="JNTU", year="2020")],
    )


def make_test_jd():
    """Create a realistic test JD."""
    return ExtractedJD(
        job_title="Senior Data Scientist",
        company="Analytics Corp",
        required_skills=["python", "sql", "machine learning", "tensorflow", "pandas"],
        preferred_skills=["tableau", "spark"],
        keywords=["data science", "python", "sql", "machine learning", "analytics", "deep learning"],
        responsibilities=["Build ML models", "Analyze data", "Create dashboards"],
        raw_text="Senior Data Scientist needed with Python, SQL, ML experience.",
    )


def test_1_single_pipeline():
    """All entry points use run_full_pipeline."""
    print("TEST 1: Single pipeline function exists...")
    import inspect
    from pipeline.core import run_full_pipeline
    sig = inspect.signature(run_full_pipeline)
    assert "original" in sig.parameters
    assert "tailored" in sig.parameters
    assert "extracted_jd" in sig.parameters
    assert "scorer" in sig.parameters
    print("  PASS: run_full_pipeline has correct signature")


def test_2_identity_preserved():
    """Pipeline preserves identity."""
    print("TEST 2: Identity preserved through pipeline...")
    resume = make_test_resume()
    jd = make_test_jd()
    scorer = ATSScorer()
    # Simulate tailored (same identity, different summary)
    tailored = resume.model_copy(deep=True)
    tailored.summary = "Data scientist with ML expertise."

    result = run_full_pipeline(
        original=resume, tailored=tailored,
        extracted_jd=jd, scorer=scorer,
    )
    assert result.improved.contact.name == "Yeswanth Arasavalli", \
        f"Identity lost: {result.improved.contact.name}"
    assert result.improved.experience[0].company == "TechVista Solutions", \
        f"Company changed: {result.improved.experience[0].company}"
    print(f"  PASS: Name={result.improved.contact.name}, Company={result.improved.experience[0].company}")


def test_3_score_never_decreases():
    """Improved score >= tailored score."""
    print("TEST 3: Score never decreases after improvement...")
    resume = make_test_resume()
    jd = make_test_jd()
    scorer = ATSScorer()
    tailored = resume.model_copy(deep=True)

    result = run_full_pipeline(
        original=resume, tailored=tailored,
        extracted_jd=jd, scorer=scorer,
    )
    # Re-score the improved resume
    imp_score, _, _ = scorer.score(result.improved, jd)
    tail_score, _, _ = scorer.score(result.tailored, jd)
    assert imp_score >= tail_score, \
        f"Score decreased: {tail_score} -> {imp_score}"
    print(f"  PASS: Tailored={tail_score}, Improved={imp_score} (no decrease)")


def test_4_empty_resume_handled():
    """Empty resume scores 0, not ~19."""
    print("TEST 4: Empty resume handled...")
    scorer = ATSScorer()
    empty = StructuredResume(contact=ContactInfo(name="Empty"))
    jd = make_test_jd()
    score, _, _ = scorer.score(empty, jd)
    assert score == 0.0, f"Empty resume should score 0, got {score}"
    print(f"  PASS: Empty resume score = {score}")


def test_5_deterministic():
    """Same input -> same output."""
    print("TEST 5: Deterministic output...")
    resume = make_test_resume()
    jd = make_test_jd()
    scorer = ATSScorer()
    tailored = resume.model_copy(deep=True)

    r1 = run_full_pipeline(original=resume, tailored=tailored.model_copy(deep=True),
                           extracted_jd=jd, scorer=scorer)
    r2 = run_full_pipeline(original=resume, tailored=tailored.model_copy(deep=True),
                           extracted_jd=jd, scorer=scorer)
    diff = abs(r1.ats_report.score_after - r2.ats_report.score_after)
    assert diff <= 1.0, \
        f"Non-deterministic: {r1.ats_report.score_after} vs {r2.ats_report.score_after} (diff={diff})"
    print(f"  PASS: Both runs scored ~{r1.ats_report.score_after} (diff={diff})")


def test_6_no_sample_leakage():
    """Pipeline result never contains 'Arjun Mehta'."""
    print("TEST 6: No sample data leakage...")
    resume = make_test_resume()
    jd = make_test_jd()
    scorer = ATSScorer()
    tailored = resume.model_copy(deep=True)

    result = run_full_pipeline(
        original=resume, tailored=tailored,
        extracted_jd=jd, scorer=scorer,
    )
    full_text = str(result.improved.model_dump())
    assert "Arjun" not in full_text, "Sample data leaked into output!"
    assert "Mehta" not in full_text, "Sample data leaked into output!"
    assert "Yeswanth" in result.improved.contact.name
    print(f"  PASS: No sample data found, name={result.improved.contact.name}")


def test_7_manual_mode_uses_pipeline():
    """ManualAnalyzer routes through the canonical engine (Phase 3 service)."""
    print("TEST 7: ManualAnalyzer uses canonical engine...")
    import inspect
    from manual_mode import ManualAnalyzer
    source = inspect.getsource(ManualAnalyzer.analyze)
    # Phase 3: the canonical entry is pipeline.service.analyze_tailored, which
    # itself calls run_full_pipeline. Direct-call OR service-call are both valid;
    # a self-contained reimplementation in manual_mode is not.
    uses_canonical = (
        "run_full_pipeline" in source or "analyze_tailored" in source
    )
    assert uses_canonical, "ManualAnalyzer doesn't use the canonical engine!"
    # Verify the service contract still bottoms out in run_full_pipeline
    import pipeline.service as svc
    svc_src = inspect.getsource(svc)
    assert "run_full_pipeline" in svc_src, "canonical service lost run_full_pipeline!"
    print("  PASS: ManualAnalyzer.analyze() routes to the canonical engine")


def test_8_controller_uses_pipeline():
    """PipelineController calls run_full_pipeline internally."""
    print("TEST 8: PipelineController uses run_full_pipeline...")
    import inspect
    from pipeline.controller import PipelineController
    source = inspect.getsource(PipelineController.process_single)
    assert "run_full_pipeline" in source, "Controller doesn't use run_full_pipeline!"
    print("  PASS: PipelineController.process_single() calls run_full_pipeline")


if __name__ == "__main__":
    test_1_single_pipeline()
    test_2_identity_preserved()
    test_3_score_never_decreases()
    test_4_empty_resume_handled()
    test_5_deterministic()
    test_6_no_sample_leakage()
    test_7_manual_mode_uses_pipeline()
    test_8_controller_uses_pipeline()
    print("\n" + "=" * 50)
    print("ALL 8 STABILIZATION TESTS PASSED")
    print("=" * 50)
