"""
Determinism Test -- Validates score consistency, realism, and trust.

Tests:
  1. Same input -> Same fingerprint (PART 6)
  2. Temperature=0 in config (PART 1)
  3. Improver doesn't add new skills (PART 2)
  4. Score stability guard ±5 (PART 3)
  5. Realistic score cap when >40% missing (PART 4)
  6. Skill normalization (PART 5)
  7. Score limit explanation exists (PART 7)
  8. No fake skills in output (PART 8)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config_loader import load_config
from utils.models import (
    StructuredResume, ContactInfo, ExperienceEntry,
    EducationEntry, ExtractedJD,
)
from ats_scoring.scorer import ATSScorer
from resume_engine.improver import ResumeImprover
from pipeline.core import (
    run_full_pipeline, _compute_input_fingerprint,
    _compute_score_limit, PipelineResult,
)


def _make_resume(**overrides):
    defaults = dict(
        contact=ContactInfo(name="Test User", email="test@test.com"),
        title="Data Scientist",
        summary="Experienced data scientist with Python and ML expertise.",
        skills=["Python", "SQL", "Pandas", "NumPy", "Machine Learning"],
        experience=[ExperienceEntry(
            role="Data Scientist", company="TestCorp", duration="2020-2024",
            bullets=[
                "Built predictive models using Python and scikit-learn.",
                "Analyzed large datasets with SQL and Pandas.",
                "Deployed ML pipelines on AWS.",
            ],
        )],
        education=[EducationEntry(
            degree="MSc Computer Science", institution="Test Univ",
        )],
    )
    defaults.update(overrides)
    return StructuredResume(**defaults)


def _make_jd(**overrides):
    defaults = dict(
        job_title="Senior Data Scientist",
        company="Analytics Corp",
        required_skills=["Python", "SQL", "TensorFlow", "Spark", "Docker",
                         "Kubernetes", "AWS", "Machine Learning"],
        preferred_skills=["Tableau", "Airflow"],
        keywords=["data pipeline", "model deployment", "analytics"],
        responsibilities=["Build ML models", "Analyze data", "Deploy pipelines"],
    )
    defaults.update(overrides)
    return ExtractedJD(**defaults)


def test_1_deterministic_fingerprint():
    """Same input -> Same fingerprint."""
    print("TEST 1: Deterministic fingerprint...")
    resume = _make_resume()
    jd = _make_jd()

    fp1 = _compute_input_fingerprint(resume, jd)
    fp2 = _compute_input_fingerprint(resume, jd)
    fp3 = _compute_input_fingerprint(resume, jd)

    assert fp1 == fp2 == fp3, f"Fingerprints differ: {fp1} vs {fp2} vs {fp3}"

    # Different input -> different fingerprint
    resume2 = _make_resume(skills=["Python", "Java", "C++"])
    fp4 = _compute_input_fingerprint(resume2, jd)
    assert fp4 != fp1, "Different input should produce different fingerprint"

    print(f"  Fingerprint: {fp1} (consistent across 3 runs)")
    print(f"  Different input: {fp4} (correctly different)")
    print("  PASS: Fingerprints are deterministic")


def test_2_temperature_zero():
    """Temperature=0 in config."""
    print("TEST 2: Temperature=0 in config...")
    config = load_config()
    assert config.llm.temperature == 0.0, f"Temperature={config.llm.temperature}, expected 0.0"
    assert config.llm.seed == 42, f"Seed={config.llm.seed}, expected 42"
    assert config.llm.top_p == 0.9, f"top_p={config.llm.top_p}, expected 0.9"
    print(f"  temperature={config.llm.temperature}")
    print(f"  seed={config.llm.seed}")
    print(f"  top_p={config.llm.top_p}")
    print("  PASS: LLM config is deterministic")


def test_3_improver_no_new_skills():
    """Improver doesn't add new skills."""
    print("TEST 3: Improver doesn't add new skills...")
    resume = _make_resume()
    original_skills = set(resume.skills)

    improver = ResumeImprover()
    improved = improver.improve(
        tailored_resume=resume,
        missing_skills=["Docker", "Kubernetes", "TensorFlow"],
        matched_skills=["Python", "SQL"],
        jd_keywords=["data pipeline", "model deployment"],
    )

    improved_skills = set(improved.skills)
    new_skills = improved_skills - original_skills
    assert not new_skills, f"Improver added fake skills: {new_skills}"
    print(f"  Original skills: {len(original_skills)}")
    print(f"  Improved skills: {len(improved_skills)}")
    print(f"  New skills added: 0")
    print("  PASS: No fake skills added")


def test_4_score_stability():
    """Score stability guard ±5."""
    print("TEST 4: Score stability guard...")
    scorer = ATSScorer()
    resume = _make_resume()
    jd = _make_jd()

    # Run pipeline twice
    result1 = run_full_pipeline(resume, resume.model_copy(deep=True), jd, scorer)
    result2 = run_full_pipeline(resume, resume.model_copy(deep=True), jd, scorer)

    score1 = result1.ats_report.score_after
    score2 = result2.ats_report.score_after
    diff = abs(score1 - score2)

    assert diff <= 5, f"Score instability: {score1} vs {score2} (diff={diff})"
    print(f"  Run 1: {score1}")
    print(f"  Run 2: {score2}")
    print(f"  Diff: {diff}")
    print("  PASS: Scores are stable")


def test_5_realistic_cap():
    """Realistic score cap when >40% core skills missing."""
    print("TEST 5: Realistic score cap...")
    scorer = ATSScorer()

    # Resume with very few matching skills
    weak_resume = _make_resume(
        skills=["Python", "Excel"],
        experience=[ExperienceEntry(
            role="Analyst", company="Small Co", duration="2023-2024",
            bullets=["Used Excel for reports."],
        )],
    )

    # JD requiring many skills
    demanding_jd = _make_jd(
        required_skills=["Python", "SQL", "TensorFlow", "Spark", "Docker",
                         "Kubernetes", "AWS", "Airflow", "Tableau", "Kafka"],
    )

    _, _, details = scorer.score(weak_resume, demanding_jd)
    limit = _compute_score_limit(scorer, weak_resume, demanding_jd, details)

    assert limit.max_possible_score <= 75, (
        f"Cap should be ≤75 but is {limit.max_possible_score}"
    )
    assert len(limit.reasons) > 0, "Should have reasons"
    print(f"  Max score: {limit.max_possible_score}")
    print(f"  Reasons: {limit.reasons[0][:70]}")
    print("  PASS: Realistic cap applied")


def test_6_skill_normalization():
    """Skill normalization: pandas == python(pandas), sklearn == scikit-learn."""
    print("TEST 6: Skill normalization...")
    scorer = ATSScorer()

    # Resume has "pandas", JD requires "python (pandas)"
    resume = _make_resume(skills=["Python", "pandas", "sklearn", "k8s", "postgres"])
    resume_skills = {s.lower() for s in resume.skills}
    text = scorer._flatten_resume_text(resume).lower()

    # These should all match through normalization
    test_cases = [
        ("python (pandas)", True),
        ("scikit-learn", True),
        ("kubernetes", True),
        ("postgresql", True),
        ("random_nonexistent_skill", False),
    ]

    for skill, expected in test_cases:
        result = scorer._skill_found_strict(skill, resume_skills, text)
        status = "OK" if result == expected else "FAIL"
        print(f"  '{skill}' -> {result} [{status}]")
        assert result == expected, f"'{skill}' should be {expected} but got {result}"

    print("  PASS: Skill normalization working")


def test_7_score_limit_explanation():
    """Score limit explanation exists in pipeline result."""
    print("TEST 7: Score limit explanation...")
    scorer = ATSScorer()
    resume = _make_resume()
    jd = _make_jd()

    result = run_full_pipeline(resume, resume.model_copy(deep=True), jd, scorer)

    assert result.score_limit is not None, "score_limit missing from result"
    assert "max_possible_score" in result.score_limit, "max_possible_score missing"
    assert "reasons" in result.score_limit, "reasons missing"
    assert len(result.score_limit["reasons"]) > 0, "No reasons provided"

    print(f"  Max score: {result.score_limit['max_possible_score']}")
    print(f"  Reason: {result.score_limit['reasons'][0][:70]}")
    print(f"  Hash: {result.pipeline_hash}")
    print("  PASS: Score limit explanation exists")


def test_8_no_fake_skills_in_output():
    """No fake skills in final output (PART 8)."""
    print("TEST 8: No fake skills in output...")
    scorer = ATSScorer()
    resume = _make_resume()
    jd = _make_jd()

    result = run_full_pipeline(resume, resume.model_copy(deep=True), jd, scorer)

    original_skills_lower = {s.lower() for s in resume.skills}
    output_skills_lower = {s.lower() for s in result.improved.skills}
    fake = output_skills_lower - original_skills_lower

    assert not fake, f"Fake skills in output: {fake}"
    assert result.improved.contact.name == resume.contact.name, "Identity mismatch"

    print(f"  Original: {len(original_skills_lower)} skills")
    print(f"  Output: {len(output_skills_lower)} skills")
    print(f"  Fake: 0")
    print(f"  Identity: {result.improved.contact.name} (preserved)")
    print("  PASS: No fake skills, identity preserved")


if __name__ == "__main__":
    test_1_deterministic_fingerprint()
    test_2_temperature_zero()
    test_3_improver_no_new_skills()
    test_4_score_stability()
    test_5_realistic_cap()
    test_6_skill_normalization()
    test_7_score_limit_explanation()
    test_8_no_fake_skills_in_output()
    print("\n" + "=" * 50)
    print("ALL 8 DETERMINISM TESTS PASSED")
    print("=" * 50)
