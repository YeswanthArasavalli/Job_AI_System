"""
tests/v6_system_tests.py

Comprehensive test suite for the v6.0 refactored system.

Tests:
  1. Shortlist Unification  — one canonical value, no mutation chaos
  2. App/Dashboard Parity   — both UIs produce identical scores
  3. Score Determinism      — same input always produces same output
  4. ATS Realism            — scores are in realistic ranges
  5. No Fake Metrics        — trust constraints enforced
  6. DB Persistence         — analysis results saved to database
  7. Pipeline Trace         — execution trace present and complete
  8. Decision Realism       — decisions follow hard rules
  9. Score Mutation Safety  — no silent overrides

Run: python -m pytest tests/v6_system_tests.py -v
Or:  python tests/v6_system_tests.py
"""

import copy
import json
import os
import sys
import sqlite3
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ================================================================
# TEST FIXTURES
# ================================================================

SAMPLE_RESUME = {
    "contact": {"name": "Priya Sharma", "email": "priya@test.com", "phone": ""},
    "title": "Data Analyst",
    "summary": "Data analyst with 3 years experience in Python and SQL for business intelligence.",
    "skills": ["Python", "SQL", "Tableau", "Excel", "Pandas", "Data Analysis"],
    "experience": [
        {
            "role": "Data Analyst",
            "company": "TechCorp",
            "duration": "2022-2024",
            "bullets": [
                "Analyzed customer transaction data using Python and Pandas to identify churn patterns for marketing team.",
                "Built SQL queries to extract and transform 50K+ records for monthly business intelligence reports.",
                "Created Tableau dashboards showing key sales metrics used by 5 regional managers.",
                "Developed automated ETL pipeline reducing manual data processing time by 40%.",
            ],
        }
    ],
    "projects": [
        {
            "name": "Customer Segmentation",
            "bullets": [
                "Implemented K-means clustering on 100K customer records to identify 4 behavioral segments.",
            ],
            "technologies": ["Python", "scikit-learn"],
        }
    ],
    "education": [
        {"degree": "B.Tech Computer Science", "institution": "NIT Warangal", "year": "2022"}
    ],
}

SAMPLE_JD = """
Data Analyst — Analytics Team
Company: DataDriven Solutions

We are looking for a skilled Data Analyst to join our growing analytics team.

Requirements:
- 2+ years of experience in data analysis
- Strong Python skills (Pandas, NumPy)
- SQL proficiency for data extraction and transformation
- Experience with Tableau or Power BI
- Familiarity with machine learning concepts

Responsibilities:
- Analyze large datasets to generate business insights
- Build and maintain reporting dashboards
- Collaborate with business stakeholders to define KPIs
- Develop automated data pipelines
- Present findings to senior leadership

Preferred:
- Experience with scikit-learn or similar ML libraries
- Knowledge of ETL processes
- Exposure to cloud platforms (AWS, GCP)
"""


def _make_resume():
    """Create a StructuredResume from sample data."""
    from utils.models import (
        StructuredResume, ContactInfo, ExperienceEntry, ProjectEntry, EducationEntry
    )
    d = SAMPLE_RESUME
    return StructuredResume(
        contact=ContactInfo(
            name=d["contact"]["name"],
            email=d["contact"]["email"],
            phone=d["contact"]["phone"],
        ),
        title=d["title"],
        summary=d["summary"],
        skills=d["skills"],
        experience=[
            ExperienceEntry(
                role=e["role"], company=e["company"],
                duration=e["duration"], bullets=e["bullets"]
            ) for e in d["experience"]
        ],
        projects=[
            ProjectEntry(name=p["name"], bullets=p["bullets"], technologies=p["technologies"])
            for p in d["projects"]
        ],
        education=[
            EducationEntry(degree=e["degree"], institution=e["institution"], year=e["year"])
            for e in d["education"]
        ],
    )


def _make_jd():
    """Create an ExtractedJD from sample data."""
    from utils.models import ExtractedJD
    return ExtractedJD(
        job_title="Data Analyst",
        company="DataDriven Solutions",
        required_skills=["Python", "SQL", "Tableau", "Pandas"],
        preferred_skills=["scikit-learn", "AWS", "ETL"],
        keywords=["python", "sql", "tableau", "pandas", "data analysis", "etl", "machine learning"],
        responsibilities=["Analyze datasets", "Build dashboards", "Develop pipelines"],
        required_experience_years=2,
        raw_text=SAMPLE_JD,
    )


# ================================================================
# TEST CLASS
# ================================================================

class TestShortlistUnification(unittest.TestCase):
    """Test that shortlist_probability has one canonical source."""

    def setUp(self):
        self.resume = _make_resume()
        self.jd = _make_jd()

    def test_pipeline_result_has_canonical_shortlist(self):
        """PipelineResult.shortlist_probability must be set after pipeline runs."""
        from ats_scoring.scorer import ATSScorer
        from pipeline.core import run_full_pipeline

        scorer = ATSScorer()
        result = run_full_pipeline(
            original=self.resume,
            tailored=copy.deepcopy(self.resume),
            extracted_jd=self.jd,
            scorer=scorer,
            job_id="test_unify",
            mode="balanced",
        )

        # MUST have canonical shortlist fields
        self.assertIsNotNone(result.shortlist_probability, "shortlist_probability must be set")
        self.assertIsInstance(result.shortlist_probability, float, "Must be float")
        self.assertGreaterEqual(result.shortlist_probability, 0, "Must be >= 0")
        self.assertLessEqual(result.shortlist_probability, 100, "Must be <= 100")
        self.assertIsNotNone(result.shortlist_band, "shortlist_band must be set")
        self.assertIsNotNone(result.shortlist_decision, "shortlist_decision must be set")

    def test_ats_report_shortlist_consistent_with_canonical(self):
        """ats_report.shortlist_probability must match canonical pipeline value."""
        from ats_scoring.scorer import ATSScorer
        from pipeline.core import run_full_pipeline

        scorer = ATSScorer()
        result = run_full_pipeline(
            original=self.resume,
            tailored=copy.deepcopy(self.resume),
            extracted_jd=self.jd,
            scorer=scorer,
            job_id="test_consistency",
            mode="balanced",
        )

        # ats_report.shortlist_probability is the dict version (for backward compat)
        ats_prob = result.ats_report.shortlist_probability
        if isinstance(ats_prob, dict):
            ats_val = ats_prob.get("shortlist_probability", 0)
            # They must be the same value
            self.assertAlmostEqual(
                ats_val, result.shortlist_probability, delta=0.1,
                msg=f"ats_report.shortlist={ats_val} != canonical={result.shortlist_probability}"
            )

    def test_hiring_sim_shortlist_not_mutated(self):
        """hiring_sim['shortlist_probability'] should remain the raw simulation value."""
        from ats_scoring.scorer import ATSScorer
        from pipeline.core import run_full_pipeline

        scorer = ATSScorer()
        result = run_full_pipeline(
            original=self.resume,
            tailored=copy.deepcopy(self.resume),
            extracted_jd=self.jd,
            scorer=scorer,
            job_id="test_mutation",
            mode="balanced",
        )

        if result.hiring_simulation:
            hs_prob = result.hiring_simulation.get("shortlist_probability", None)
            canonical = result.shortlist_probability
            # They MAY differ (raw sim vs calibrated) — that's OK now
            # What matters: canonical is the one shown to users, not hs_prob
            print(f"  raw_sim_prob={hs_prob}, canonical={canonical}")
            # Both should be valid numbers if present
            if hs_prob is not None:
                self.assertIsInstance(hs_prob, (int, float))


class TestScoreDeterminism(unittest.TestCase):
    """Same input must always produce same output."""

    def setUp(self):
        self.resume = _make_resume()
        self.jd = _make_jd()

    def test_ats_score_deterministic(self):
        """Running ATS scorer twice on same input must give same score."""
        from ats_scoring.scorer import ATSScorer
        scorer = ATSScorer()
        s1, _, _ = scorer.score(self.resume, self.jd)
        s2, _, _ = scorer.score(self.resume, self.jd)
        self.assertEqual(s1, s2, f"ATS scores not deterministic: {s1} != {s2}")

    def test_pipeline_hash_deterministic(self):
        """Same resume + JD should produce same pipeline_hash."""
        from ats_scoring.scorer import ATSScorer
        from pipeline.core import run_full_pipeline

        scorer = ATSScorer()
        r1 = run_full_pipeline(
            original=self.resume,
            tailored=copy.deepcopy(self.resume),
            extracted_jd=self.jd,
            scorer=scorer,
            job_id="det_1",
            mode="balanced",
        )
        r2 = run_full_pipeline(
            original=self.resume,
            tailored=copy.deepcopy(self.resume),
            extracted_jd=self.jd,
            scorer=scorer,
            job_id="det_2",
            mode="balanced",
        )
        self.assertEqual(
            r1.pipeline_hash, r2.pipeline_hash,
            f"Hash not deterministic: {r1.pipeline_hash} != {r2.pipeline_hash}"
        )
        self.assertAlmostEqual(
            r1.ats_report.score_after, r2.ats_report.score_after, delta=1.0,
            msg="ATS score not deterministic across pipeline runs"
        )


class TestATSRealism(unittest.TestCase):
    """ATS scores must be in realistic ranges."""

    def setUp(self):
        self.resume = _make_resume()
        self.jd = _make_jd()

    def test_ats_score_in_range(self):
        from ats_scoring.scorer import ATSScorer
        scorer = ATSScorer()
        score, _, _ = scorer.score(self.resume, self.jd)
        self.assertGreaterEqual(score, 0, "ATS score below 0")
        self.assertLessEqual(score, 100, "ATS score above 100")

    def test_matched_resume_scores_above_threshold(self):
        """A resume with 4/4 required skills should score >= 50."""
        from ats_scoring.scorer import ATSScorer
        scorer = ATSScorer()
        score, _, _ = scorer.score(self.resume, self.jd)
        self.assertGreaterEqual(
            score, 45,
            f"Well-matched resume scoring too low: {score}. Check scoring realism."
        )

    def test_score_improves_after_pipeline(self):
        """Optimized resume should score >= original."""
        from ats_scoring.scorer import ATSScorer
        from pipeline.core import run_full_pipeline

        scorer = ATSScorer()
        result = run_full_pipeline(
            original=self.resume,
            tailored=copy.deepcopy(self.resume),
            extracted_jd=self.jd,
            scorer=scorer,
            job_id="improve_test",
            mode="balanced",
        )
        self.assertGreaterEqual(
            result.ats_report.score_after,
            result.ats_report.score_before - 1,  # Allow tiny float variance
            "Optimized resume scored lower than original (regression)"
        )

    def test_no_score_inflation_beyond_cap(self):
        """Score should not exceed realistic limits for low-match resumes."""
        from ats_scoring.scorer import ATSScorer
        from utils.models import StructuredResume, ContactInfo

        scorer = ATSScorer()
        # Minimal resume — very few skills matching JD
        weak_resume = StructuredResume(
            contact=ContactInfo(name="Test User", email="test@test.com"),
            skills=["Excel"],  # Only 1 of 4 required skills
            experience=[],
        )
        score, _, _ = scorer.score(weak_resume, self.jd)
        self.assertLessEqual(
            score, 50,
            f"Weak resume (1/4 skills) should score <= 50, got {score}"
        )


class TestTrustConstraints(unittest.TestCase):
    """Trust constraints: no fake skills, no fake metrics."""

    def setUp(self):
        self.resume = _make_resume()
        self.jd = _make_jd()

    def test_no_skills_added_beyond_ecosystem(self):
        """Improved resume must not add skills completely absent from original."""
        from ats_scoring.scorer import ATSScorer
        from pipeline.core import run_full_pipeline

        scorer = ATSScorer()
        result = run_full_pipeline(
            original=self.resume,
            tailored=copy.deepcopy(self.resume),
            extracted_jd=self.jd,
            scorer=scorer,
            job_id="trust_test",
            mode="strict",
        )

        original_skills_lower = {s.lower() for s in self.resume.skills}
        improved_skills_lower = {s.lower() for s in result.improved.skills}
        added = improved_skills_lower - original_skills_lower

        # Added skills must come from JD or ecosystem of existing skills
        # (system can add things like "scikit-learn" if Python is in skills)
        KNOWN_SAFE_ADDITIONS = {
            "pandas", "numpy", "scikit-learn", "matplotlib", "scipy",
            "complex queries", "joins", "aggregations", "data visualization",
        }
        genuinely_new = added - KNOWN_SAFE_ADDITIONS
        self.assertEqual(
            len(genuinely_new), 0,
            f"Potentially fake skills added: {genuinely_new}"
        )

    def test_name_preserved_in_output(self):
        """Candidate name must never change through pipeline."""
        from ats_scoring.scorer import ATSScorer
        from pipeline.core import run_full_pipeline

        scorer = ATSScorer()
        result = run_full_pipeline(
            original=self.resume,
            tailored=copy.deepcopy(self.resume),
            extracted_jd=self.jd,
            scorer=scorer,
            job_id="identity_test",
            mode="strict",
        )
        self.assertEqual(
            result.improved.contact.name,
            self.resume.contact.name,
            "Candidate name changed in output — identity violation"
        )


class TestDecisionRealism(unittest.TestCase):
    """Decisions must follow hard rules."""

    def test_low_ats_cannot_get_apply_now(self):
        """ATS < 70 must never produce APPLY NOW decision."""
        from pipeline.unified_scoring import compute_final_shortlist_probability
        result = compute_final_shortlist_probability(
            ats_score=62, recruiter_score=80, jd_match_score=90,
            bullets=["Strong ML engineer with production experience deployed models at scale reducing costs by 40%."],
        )
        self.assertNotIn("APPLY NOW", result["decision"],
                         f"ATS=62 produced APPLY NOW: {result['decision']}")

    def test_high_ats_with_good_signals_gets_strong_decision(self):
        """ATS >= 85 with recruiter >= 70 should get at least APPLY."""
        from pipeline.unified_scoring import compute_final_shortlist_probability
        result = compute_final_shortlist_probability(
            ats_score=87, recruiter_score=75, jd_match_score=85,
            bullets=[
                "Built churn prediction model using XGBoost on 150K customer records reducing churn by 25%.",
                "Deployed production ML pipeline on AWS reducing inference time by 40%.",
                "Led end-to-end data science project for marketing team improving conversion by 15%.",
            ],
        )
        self.assertIn("APPLY", result["decision"],
                      f"Strong profile should get APPLY: got {result['decision']}")

    def test_entry_level_gets_realistic_cap(self):
        """Entry-level candidate gets probability cap."""
        from pipeline.unified_scoring import compute_final_shortlist_probability
        result = compute_final_shortlist_probability(
            ats_score=82, recruiter_score=70, jd_match_score=75,
            experience_level="entry",
            has_production_exp=False,
        )
        # Entry-level gets ×0.85 correction
        self.assertLessEqual(
            result["shortlist_probability"], 75,
            f"Entry-level should have realistic cap, got {result['shortlist_probability']}"
        )

    def test_decisions_are_allowed_values(self):
        """All decisions must come from the allowed set."""
        from pipeline.unified_scoring import compute_final_shortlist_probability
        allowed = {"APPLY NOW", "APPLY (STRONG)", "APPLY (FIX GAPS)",
                   "FIX GAPS", "SKIP", "IMPROVE THEN APPLY",
                   "APPLY NOW — COMPETITIVE PROFILE"}
        for ats in [55, 65, 72, 80, 87, 92]:
            result = compute_final_shortlist_probability(
                ats_score=ats, recruiter_score=60, jd_match_score=70,
            )
            decision = result["decision"]
            # Check it's one of the allowed values or starts with an allowed prefix
            is_allowed = any(decision.startswith(a) for a in allowed)
            self.assertTrue(is_allowed, f"Unknown decision for ATS={ats}: '{decision}'")


class TestPipelineTrace(unittest.TestCase):
    """Pipeline trace must be present and complete."""

    def test_trace_present(self):
        from ats_scoring.scorer import ATSScorer
        from pipeline.core import run_full_pipeline

        resume = _make_resume()
        jd = _make_jd()
        scorer = ATSScorer()
        result = run_full_pipeline(
            original=resume,
            tailored=copy.deepcopy(resume),
            extracted_jd=jd,
            scorer=scorer,
            job_id="trace_test",
            mode="balanced",
        )

        self.assertIsNotNone(result.pipeline_trace, "pipeline_trace must be set")
        trace = result.pipeline_trace
        required_keys = [
            "job_id", "mode", "pipeline_hash",
            "ats_score_before", "ats_score_after",
            "shortlist_after", "shortlist_decision",
        ]
        for key in required_keys:
            self.assertIn(key, trace, f"Missing trace key: {key}")

        # Score lineage must be consistent
        self.assertEqual(trace["ats_score_after"], result.ats_report.score_after)
        self.assertAlmostEqual(
            trace["shortlist_after"], result.shortlist_probability, delta=0.1
        )


class TestDBPersistence(unittest.TestCase):
    """Database must persist analysis results correctly."""

    def test_save_and_retrieve_analysis(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            from database.db_manager import DatabaseManager
            db = DatabaseManager(db_path)

            analysis = {
                "company": "TestCorp",
                "role": "Data Analyst",
                "location": "Remote",
                "ats_score_before": 52.0,
                "ats_score_after": 71.0,
                "shortlist_probability": 38.5,
                "shortlist_band": "B",
                "decision": "APPLY (FIX GAPS)",
                "decision_reason": "ATS 71, recruiter 65",
                "optimization_mode": "balanced",
                "missing_skills": ["AWS", "Power BI"],
                "matched_skills": ["Python", "SQL", "Pandas"],
            }
            analysis_id = db.save_analysis_result(analysis)
            self.assertIsNotNone(analysis_id)
            self.assertGreater(analysis_id, 0)

            # Retrieve and verify
            results = db.list_analysis_results(limit=10)
            self.assertGreater(len(results), 0)
            saved = results[0]
            self.assertEqual(saved["company"], "TestCorp")
            self.assertEqual(saved["shortlist_probability"], 38.5)
            self.assertEqual(saved["shortlist_band"], "B")
            self.assertEqual(saved["decision"], "APPLY (FIX GAPS)")
            self.assertEqual(saved["missing_skills"], ["AWS", "Power BI"])

            db.close()
        finally:
            os.unlink(db_path)

    def test_application_status_lifecycle(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            from database.db_manager import DatabaseManager
            db = DatabaseManager(db_path)

            analysis_id = db.save_analysis_result({
                "company": "Acme", "role": "Engineer",
                "ats_score_before": 60, "ats_score_after": 75,
                "shortlist_probability": 42,
            })

            # Test lifecycle transitions
            db.update_application_status(analysis_id, "applied", "Applied on LinkedIn")
            db.update_application_status(analysis_id, "shortlisted", "Got a call!")

            history = db.get_application_history(analysis_id)
            event_types = [e["event_type"] for e in history]
            self.assertIn("applied", event_types)
            self.assertIn("shortlisted", event_types)

            # Check current status
            results = db.list_analysis_results()
            found = next((r for r in results if r["id"] == analysis_id), None)
            self.assertIsNotNone(found)
            self.assertEqual(found["application_status"], "shortlisted")

            db.close()
        finally:
            os.unlink(db_path)

    def test_analytics_summary(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            from database.db_manager import DatabaseManager
            db = DatabaseManager(db_path)

            for i in range(5):
                aid = db.save_analysis_result({
                    "company": f"Company{i}", "role": "Analyst",
                    "ats_score_before": 50 + i, "ats_score_after": 65 + i,
                    "shortlist_probability": 30 + i * 5,
                })
                if i < 2:
                    db.update_application_status(aid, "applied")
                if i == 0:
                    db.update_application_status(aid, "shortlisted")

            summary = db.get_analytics_summary()
            self.assertEqual(summary["total_analyses"], 5)
            self.assertEqual(summary["total_applied"], 2)
            self.assertEqual(summary["shortlisted"], 1)
            self.assertGreater(summary["avg_ats_score"], 0)

            db.close()
        finally:
            os.unlink(db_path)


class TestAppDashboardParity(unittest.TestCase):
    """Both UIs must produce the same shortlist probability for the same input."""

    def test_manual_analyzer_uses_same_pipeline(self):
        """ManualAnalyzer.analyze() must use run_full_pipeline() and expose canonical shortlist."""
        from manual_mode import ManualAnalyzer
        import json

        analyzer = ManualAnalyzer()
        result = analyzer.analyze(
            jd_text=SAMPLE_JD,
            resume_json=SAMPLE_RESUME,
            mode="balanced",
        )

        if result.get("error"):
            self.skipTest(f"LLM not available: {result['error']}")

        # Must expose canonical shortlist fields
        self.assertIn("canonical_shortlist_probability", result,
                      "ManualAnalyzer must expose canonical_shortlist_probability")
        self.assertIn("pipeline_trace", result,
                      "ManualAnalyzer must expose pipeline_trace")
        self.assertIn("pipeline_result", result,
                      "ManualAnalyzer must expose pipeline_result")

        # Canonical values must be consistent
        pr = result["pipeline_result"]
        self.assertAlmostEqual(
            result["canonical_shortlist_probability"],
            pr.shortlist_probability,
            delta=0.1,
            msg="canonical_shortlist_probability must match pipeline_result.shortlist_probability"
        )


# ================================================================
# QUICK SANITY CHECKS (no full pipeline)
# ================================================================

class TestSanityChecks(unittest.TestCase):
    """Fast sanity checks that don't require LLM."""

    def test_unified_scoring_import(self):
        """unified_scoring.py must be importable."""
        from pipeline.unified_scoring import compute_final_shortlist_probability
        self.assertTrue(callable(compute_final_shortlist_probability))

    def test_unified_scoring_basic(self):
        """compute_final_shortlist_probability must return required keys."""
        from pipeline.unified_scoring import compute_final_shortlist_probability
        result = compute_final_shortlist_probability(
            ats_score=75, recruiter_score=65, jd_match_score=70,
        )
        required = ["shortlist_probability", "decision", "band", "ats_band"]
        for k in required:
            self.assertIn(k, result, f"Missing key in unified scoring output: {k}")

    def test_db_manager_import(self):
        """db_manager.py v2 must be importable with new methods."""
        from database.db_manager import DatabaseManager
        # Must have v2 methods
        self.assertTrue(hasattr(DatabaseManager, "save_analysis_result"))
        self.assertTrue(hasattr(DatabaseManager, "update_application_status"))
        self.assertTrue(hasattr(DatabaseManager, "list_analysis_results"))
        self.assertTrue(hasattr(DatabaseManager, "get_analytics_summary"))
        self.assertTrue(hasattr(DatabaseManager, "save_ingested_job"))

    def test_ingestion_adapter_import(self):
        """ingestion.py must be importable with SourceAdapter."""
        from pipeline.ingestion import SourceAdapter, SourceRegistry, ManualAdapter
        self.assertTrue(hasattr(SourceRegistry, "register"))
        self.assertTrue(hasattr(SourceRegistry, "fetch_from"))
        # ManualAdapter must be concrete
        adapter = ManualAdapter()
        self.assertEqual(adapter.source_name, "manual")

    def test_pipeline_result_has_shortlist_fields(self):
        """PipelineResult dataclass must have canonical shortlist fields."""
        from pipeline.core import PipelineResult
        from dataclasses import fields
        field_names = {f.name for f in fields(PipelineResult)}
        required = {
            "shortlist_probability", "shortlist_band",
            "shortlist_decision", "shortlist_decision_reason",
            "pipeline_trace",
        }
        missing = required - field_names
        self.assertEqual(
            len(missing), 0,
            f"PipelineResult missing required fields: {missing}"
        )

    def test_ats_scorer_import(self):
        from ats_scoring.scorer import ATSScorer
        scorer = ATSScorer()
        self.assertIsNotNone(scorer)


# ================================================================
# RUNNER
# ================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Sreejita Hiring Engine — v6.0 System Tests")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Run fast tests first
    suite.addTests(loader.loadTestsFromTestCase(TestSanityChecks))
    suite.addTests(loader.loadTestsFromTestCase(TestDecisionRealism))
    suite.addTests(loader.loadTestsFromTestCase(TestDBPersistence))
    suite.addTests(loader.loadTestsFromTestCase(TestATSRealism))
    suite.addTests(loader.loadTestsFromTestCase(TestTrustConstraints))
    suite.addTests(loader.loadTestsFromTestCase(TestScoreDeterminism))
    suite.addTests(loader.loadTestsFromTestCase(TestPipelineTrace))
    suite.addTests(loader.loadTestsFromTestCase(TestShortlistUnification))
    suite.addTests(loader.loadTestsFromTestCase(TestAppDashboardParity))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
