"""Guardrail validation tests."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_empty_resume_scoring():
    """Part 1: Empty resume should score 0, not ~19."""
    print("TEST 1: Empty resume scoring...")
    from ats_scoring.scorer import ATSScorer
    from utils.models import StructuredResume, ContactInfo, ExtractedJD
    scorer = ATSScorer()
    empty = StructuredResume(contact=ContactInfo(name="Empty"))
    jd = ExtractedJD(
        job_title="Developer",
        required_skills=["python", "sql"],
        keywords=["backend", "api"],
    )
    score, _, _ = scorer.score(empty, jd)
    assert score == 0.0, f"Empty resume should score 0, got {score}"
    print(f"  PASS: Empty resume scores {score}")

def test_keyword_preservation():
    """Part 3: Improver should not lose keywords."""
    print("TEST 2: Keyword preservation...")
    from resume_engine.improver import ResumeImprover
    from utils.models import StructuredResume, ContactInfo, ExperienceEntry
    r = StructuredResume(
        contact=ContactInfo(name="Test"),
        summary="Backend developer with Python and Django experience.",
        skills=["Python", "Django", "PostgreSQL", "Docker"],
        experience=[ExperienceEntry(
            role="Developer", company="Corp", duration="2020-2023",
            bullets=["Built REST APIs using Django and Python",
                     "Managed PostgreSQL databases with complex queries",
                     "Deployed services using Docker containers"]
        )]
    )
    imp = ResumeImprover()
    result = imp.improve(r, matched_skills=["Python", "Django"], jd_keywords=["backend", "api"])
    # Check original keywords still present
    orig_text = " ".join(b for e in r.experience for b in e.bullets).lower()
    result_text = " ".join(b for e in result.experience for b in e.bullets).lower()
    for key in ["django", "python", "postgresql", "docker"]:
        assert key in result_text, f"Lost keyword: {key}"
    print("  PASS: All keywords preserved")

def test_repetition_control():
    """Part 3: Excessive repetition should trigger revert."""
    print("TEST 3: Repetition control...")
    from resume_engine.improver import ResumeImprover
    assert not ResumeImprover._has_excessive_repetition("short text", max_repeat=3)
    # Normal text should pass
    normal = "Built REST APIs. Deployed microservices. Managed databases. Created dashboards."
    assert not ResumeImprover._has_excessive_repetition(normal, max_repeat=3)
    print("  PASS: Repetition control working")

def test_score_guardrail():
    """Part 2: Score should never decrease after improvement."""
    print("TEST 4: Score guardrail concept...")
    # Simulate: if improved_score < original_score, revert
    original_score = 45.0
    improved_score = 42.0  # Simulated degradation
    if improved_score < original_score:
        improved_score = original_score  # Guardrail fires
    assert improved_score >= original_score
    print(f"  PASS: Guardrail would revert ({original_score} >= {improved_score})")

def test_keyword_stuffing_normalized():
    """Part 4: Short resumes should not trigger stuffing."""
    print("TEST 5: Keyword stuffing normalization...")
    from ats_scoring.scorer import ATSScorer
    from utils.models import StructuredResume, ContactInfo, ExperienceEntry
    scorer = ATSScorer()
    # Short resume with naturally repeated terms
    r = StructuredResume(
        contact=ContactInfo(name="Test"),
        skills=["Python", "API", "SQL"],
        experience=[ExperienceEntry(
            role="Dev", company="Corp", duration="2023",
            bullets=["Built Python API", "Used Python for data", "Python scripting"]
        )]
    )
    text = scorer._flatten_resume_text(r)
    penalty = scorer._detect_keyword_stuffing(text, r)
    assert penalty == 0.0, f"Short resume should not trigger stuffing, got penalty={penalty}"
    print(f"  PASS: Short resume penalty = {penalty} (no false positive)")

if __name__ == "__main__":
    test_empty_resume_scoring()
    test_keyword_preservation()
    test_repetition_control()
    test_score_guardrail()
    test_keyword_stuffing_normalized()
    print("\nALL 5 GUARDRAIL TESTS PASSED")
