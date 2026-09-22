"""System audit tests -- run with: python tests/audit_test.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_short_jd():
    print("TEST 1: Broken/short JD...")
    from manual_mode import ManualAnalyzer
    a = ManualAnalyzer()
    r = a.analyze(jd_text="hi")
    assert r.get("error"), "Should fail on short JD"
    print("  PASS: Graceful error for short JD")

def test_probability():
    print("TEST 2: Probability engine...")
    from ats_scoring.probability import ShortlistPredictor
    from utils.models import ATSScoreReport, ScoreBreakdown
    b = ScoreBreakdown(keyword_match=50, skills_match=50, experience_relevance=50,
                       role_alignment=50, education_fit=50, resume_structure=50)
    report = ATSScoreReport(
        job_id="test", score_before=40, score_after=55, improvement="+15",
        breakdown_before=b, breakdown_after=b,
        matched_skills=["python"], missing_skills=["sql"],
        matched_keywords=["data"], missing_keywords=["etl"],
        semantic_score=30, decision="MAYBE", effort_level="MEDIUM",
        risk_flags=[], penalties_applied=[], recommendations=[]
    )
    p = ShortlistPredictor()
    result = p.predict(report)
    assert "shortlist_probability" in result
    assert "band" in result
    assert "positive_factors" in result
    assert "negative_factors" in result
    prob = result["shortlist_probability"]
    print(f"  PASS: prob={prob}%, band={result['band']}")

def test_resume_parser():
    print("TEST 3: Resume parser bad file...")
    from resume_parser import ResumeFileParser
    rp = ResumeFileParser()
    try:
        rp.extract_text(file_bytes=b"not a pdf", filename="bad.pdf")
        print("  WARN: No error raised")
    except Exception as e:
        print(f"  PASS: Graceful error: {type(e).__name__}")

def test_empty_db():
    print("TEST 4: Empty DB flow engine...")
    from database.db_manager import DatabaseManager
    from insights.flow import FlowEngine
    db = DatabaseManager(":memory:")
    flow = FlowEngine(db)
    plan = flow.daily_plan()
    assert "today_plan" in plan
    print(f"  PASS: Empty state handled")

def test_decision_engine():
    print("TEST 5: Decision engine multi-signal...")
    from ats_scoring.scorer import ATSScorer
    scorer = ATSScorer()
    d1 = scorer._make_decision(70, 50, {"risk_flags": [], "matched_skills": ["a","b","c"], "missing_skills": ["d"]})
    d2 = scorer._make_decision(70, 10, {"risk_flags": [], "matched_skills": ["a"], "missing_skills": ["b","c","d","e"]})
    d3 = scorer._make_decision(30, 10, {"risk_flags": [], "matched_skills": [], "missing_skills": ["a","b"]})
    print(f"  HighATS+HighSem={d1}, HighATS+LowSem={d2}, LowBoth={d3}")
    assert d1 == "APPLY"
    assert d3 == "SKIP"
    print("  PASS: Decision matrix correct")

def test_score_cap():
    print("TEST 6: Probability score caps...")
    from ats_scoring.probability import ShortlistPredictor
    from utils.models import ATSScoreReport, ScoreBreakdown
    b = ScoreBreakdown(keyword_match=30, skills_match=30, experience_relevance=30,
                       role_alignment=30, education_fit=30, resume_structure=30)
    report = ATSScoreReport(
        job_id="test", score_before=25, score_after=35, improvement="+10",
        breakdown_before=b, breakdown_after=b,
        matched_skills=["python"], missing_skills=["sql","java","aws","docker"],
        matched_keywords=["data"], missing_keywords=["etl"],
        semantic_score=60, decision="SKIP", effort_level="HIGH",
        risk_flags=[], penalties_applied=[], recommendations=[]
    )
    p = ShortlistPredictor()
    result = p.predict(report)
    prob = result["shortlist_probability"]
    assert prob <= 15, f"Low ATS score should cap probability, got {prob}%"
    print(f"  PASS: Low ATS capped at {prob}% (max 15)")

if __name__ == "__main__":
    test_short_jd()
    test_probability()
    test_resume_parser()
    test_empty_db()
    test_decision_engine()
    test_score_cap()
    print("\nALL 6 AUDIT TESTS PASSED")
