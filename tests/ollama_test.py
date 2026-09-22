"""
Ollama Integration Test -- Validates LLM connectivity and fail-safe behavior.

Tests:
  1. check_ollama() detects running server
  2. Explicit host client connects successfully
  3. call_ollama() returns valid response
  4. JD analysis works via LLM
  5. JD analysis falls back gracefully when LLM fails
  6. JD processor responsibilities fallback works
  7. Dashboard health check returns correct status
  8. Config model matches available model
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ollama_client import check_ollama, get_client, call_ollama
from utils.config_loader import load_config
from jd_processor.processor import JDProcessor


SAMPLE_JD = """
Senior Data Scientist at TechCorp

We are looking for a Senior Data Scientist to join our team.

Responsibilities:
- Build and deploy machine learning models for production use
- Analyze large datasets to derive actionable business insights
- Develop data pipelines using Python and SQL
- Create dashboards and visualizations using Tableau
- Collaborate with engineering teams to implement ML solutions

Requirements:
- 5+ years of experience in data science or machine learning
- Strong proficiency in Python, SQL, and pandas
- Experience with TensorFlow or PyTorch
- Master's degree in Computer Science, Statistics, or related field
- Excellent communication skills

Preferred:
- Experience with Spark and cloud platforms (AWS/GCP)
- Knowledge of A/B testing and experimentation
"""


def test_1_check_ollama():
    """check_ollama() detects running server."""
    print("TEST 1: check_ollama()...")
    status = check_ollama()
    assert status["connected"], f"Ollama not connected: {status['error']}"
    assert len(status["models"]) > 0, "No models found"
    print(f"  Connected: {status['connected']}")
    print(f"  Models: {len(status['models'])}")
    print(f"  Host: {status['host']}")
    print("  PASS: Ollama detected")


def test_2_explicit_client():
    """Explicit host client connects successfully."""
    print("TEST 2: Explicit host client...")
    config = load_config()
    client = get_client(config)
    models = client.list()
    assert len(models.models) > 0, "No models via explicit client"
    model_names = [m.model for m in models.models]
    print(f"  Client connected to {config.llm.base_url}")
    print(f"  Models: {', '.join(model_names[:5])}...")
    print("  PASS: Explicit client works")


def test_3_call_ollama():
    """call_ollama() returns valid response."""
    print("TEST 3: call_ollama()...")
    messages = [
        {"role": "user", "content": "Reply with exactly: HELLO"}
    ]
    response = call_ollama(messages, task="Test")
    assert len(response) > 0, "Empty response"
    assert "HELLO" in response.upper(), f"Unexpected response: {response[:50]}"
    print(f"  Response: {response.strip()[:60]}")
    print("  PASS: LLM responds correctly")


def test_4_jd_analysis_via_llm():
    """JD analysis works via LLM."""
    print("TEST 4: JD analysis via LLM...")
    from resume_engine.engine import ResumeEngine
    engine = ResumeEngine()
    result = engine.analyze_jd(SAMPLE_JD)
    assert result.required_skills, "No skills extracted"
    assert result.keywords, "No keywords extracted"
    print(f"  Title: {result.job_title}")
    print(f"  Skills: {result.required_skills[:5]}")
    print(f"  Keywords: {len(result.keywords)}")
    print("  PASS: JD analysis works")


def test_5_jd_fallback():
    """JD analysis falls back gracefully."""
    print("TEST 5: JD fallback extraction...")
    from resume_engine.engine import ResumeEngine
    engine = ResumeEngine()
    # Use the fallback directly
    result = engine._fallback_jd_extraction(SAMPLE_JD)
    assert result.required_skills, "Fallback found no skills"
    assert "python" in [s.lower() for s in result.required_skills], "Python not found"
    print(f"  Fallback skills: {result.required_skills[:5]}")
    print("  PASS: Fallback works")


def test_6_responsibilities_fallback():
    """JD processor responsibilities fallback works."""
    print("TEST 6: Responsibilities fallback...")
    processor = JDProcessor()

    # JD without clear section headers
    flat_jd = """
    Data Scientist role. Build ML models for production.
    Analyze datasets to find patterns. Deploy models on AWS.
    Develop Python scripts for data processing.
    Collaborate with product teams on feature development.
    Maintain data pipelines and ensure data quality.
    """
    result = processor.process(flat_jd)
    assert len(result.responsibilities) > 0, (
        f"No responsibilities extracted from flat JD"
    )
    print(f"  Responsibilities found: {len(result.responsibilities)}")
    for r in result.responsibilities[:3]:
        print(f"    - {r[:70]}")
    print("  PASS: Responsibilities fallback works")


def test_7_config_model_match():
    """Config model matches available model."""
    print("TEST 7: Config model match...")
    config = load_config()
    status = check_ollama(config)
    assert status["model_available"], (
        f"Configured model '{config.llm.model}' not found. "
        f"Available: {', '.join(status['models'][:5])}"
    )
    print(f"  Configured: {config.llm.model}")
    print(f"  Available: True")
    print("  PASS: Model matches")


def test_8_full_jd_with_sections():
    """Full JD with section headers extracts responsibilities."""
    print("TEST 8: Full JD with sections...")
    processor = JDProcessor()
    result = processor.process(SAMPLE_JD)
    assert len(result.skills_required) > 0, "No skills"
    assert len(result.responsibilities) > 0, "No responsibilities"
    print(f"  Skills: {len(result.skills_required)}")
    print(f"  Responsibilities: {len(result.responsibilities)}")
    print(f"  Quality: {result.quality_score:.0f}%")
    print("  PASS: Full JD processed")


if __name__ == "__main__":
    test_1_check_ollama()
    test_2_explicit_client()
    test_3_call_ollama()
    test_4_jd_analysis_via_llm()
    test_5_jd_fallback()
    test_6_responsibilities_fallback()
    test_7_config_model_match()
    test_8_full_jd_with_sections()
    print("\n" + "=" * 50)
    print("ALL 8 OLLAMA INTEGRATION TESTS PASSED")
    print("=" * 50)
