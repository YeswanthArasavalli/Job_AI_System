"""
Feedback Loop Engine -- Learns patterns from processed jobs.

Analyzes all completed jobs to detect:
  - Recurring skill gaps (what you're consistently missing)
  - Common penalty patterns (what keeps hurting your score)
  - Resume weakness trends (which dimensions underperform)
  - Score trajectory over time (are you improving?)

Pure analytics over SQLite data. No LLM calls.
"""

from collections import Counter
from typing import Dict, List, Tuple

from database.db_manager import DatabaseManager
from utils.logger import setup_logger

logger = setup_logger(__name__)


class FeedbackEngine:
    """
    Learns from processed job history to identify recurring patterns.

    Usage:
        engine = FeedbackEngine(db)
        feedback = engine.analyze()
        print(feedback["top_missing_skills"])
    """

    def __init__(self, db: DatabaseManager):
        self.db = db

    def analyze(self) -> dict:
        """
        Run full feedback analysis across all completed jobs.

        Returns:
            Dict with skill gaps, failure patterns, weakness trends,
            score trajectory, and actionable insights.
        """
        jobs = self.db.list_jobs(status="completed")

        if len(jobs) < 1:
            return {"error": "Need at least 1 completed job for analysis"}

        # Collect raw data
        missing_skills: List[str] = []
        missing_keywords: List[str] = []
        penalties: List[str] = []
        risk_flags: List[str] = []
        decisions = {"APPLY": 0, "MAYBE": 0, "SKIP": 0}
        scores_before: List[float] = []
        scores_after: List[float] = []
        dimension_scores = {
            "keyword_match": [],
            "skills_match": [],
            "experience_relevance": [],
            "role_alignment": [],
            "education_fit": [],
            "resume_structure": [],
        }
        effort_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        companies_by_decision: Dict[str, List[str]] = {"APPLY": [], "MAYBE": [], "SKIP": []}

        for job in jobs:
            r = job.ats_report
            if not r:
                continue

            missing_skills.extend(r.missing_skills)
            missing_keywords.extend(r.missing_keywords)
            penalties.extend(r.penalties_applied)
            risk_flags.extend(r.risk_flags)
            decisions[r.decision] = decisions.get(r.decision, 0) + 1
            scores_before.append(r.score_before)
            scores_after.append(r.score_after)
            effort_counts[r.effort_level] = effort_counts.get(r.effort_level, 0) + 1
            companies_by_decision.setdefault(r.decision, []).append(job.company or "?")

            b = r.breakdown_after
            dimension_scores["keyword_match"].append(b.keyword_match)
            dimension_scores["skills_match"].append(b.skills_match)
            dimension_scores["experience_relevance"].append(b.experience_relevance)
            dimension_scores["role_alignment"].append(b.role_alignment)
            dimension_scores["education_fit"].append(b.education_fit)
            dimension_scores["resume_structure"].append(b.resume_structure)

        # === Analysis ===

        # 1. Top missing skills (what you keep lacking)
        skill_freq = Counter(self._normalize(missing_skills))
        top_missing = skill_freq.most_common(10)

        # 2. Top missing keywords
        kw_freq = Counter(self._normalize(missing_keywords))
        top_missing_kw = kw_freq.most_common(10)

        # 3. Most common penalties
        penalty_freq = Counter(self._clean_penalties(penalties))
        common_penalties = penalty_freq.most_common(5)

        # 4. Resume weakness trends (lowest-scoring dimensions)
        dim_avgs = {}
        for dim, scores in dimension_scores.items():
            if scores:
                dim_avgs[dim] = round(sum(scores) / len(scores), 1)
        weaknesses = sorted(dim_avgs.items(), key=lambda x: x[1])

        # 5. Score trajectory
        avg_before = round(sum(scores_before) / len(scores_before), 1) if scores_before else 0
        avg_after = round(sum(scores_after) / len(scores_after), 1) if scores_after else 0
        avg_improvement = round(avg_after - avg_before, 1)

        # 6. Consistency check (how much do scores vary?)
        if len(scores_after) > 1:
            mean = sum(scores_after) / len(scores_after)
            variance = sum((s - mean) ** 2 for s in scores_after) / len(scores_after)
            std_dev = variance ** 0.5
        else:
            std_dev = 0

        return {
            "total_jobs_analyzed": len(jobs),
            "top_missing_skills": top_missing,
            "top_missing_keywords": top_missing_kw,
            "most_common_penalties": common_penalties,
            "resume_weakness_trends": weaknesses[:3],
            "dimension_averages": dim_avgs,
            "decisions": decisions,
            "effort_distribution": effort_counts,
            "score_trajectory": {
                "avg_before": avg_before,
                "avg_after": avg_after,
                "avg_improvement": avg_improvement,
                "score_consistency": round(std_dev, 1),
            },
            "companies_by_decision": companies_by_decision,
        }

    def print_report(self):
        """Print a formatted feedback report."""
        data = self.analyze()

        if "error" in data:
            print(f"\n  {data['error']}\n")
            return

        print("\n" + "=" * 60)
        print("🧠  CAREER FEEDBACK REPORT")
        print("=" * 60)

        # Score trajectory
        t = data["score_trajectory"]
        print(f"\n  -- Score Performance -------------------")
        print(f"  Avg Before Tailoring:  {t['avg_before']}/100")
        print(f"  Avg After Tailoring:   {t['avg_after']}/100")
        print(f"  Avg Improvement:       +{t['avg_improvement']}")
        print(f"  Score Consistency:     std={t['score_consistency']} (lower=more consistent)")

        # Decisions
        d = data["decisions"]
        total = sum(d.values())
        print(f"\n  -- Decision Breakdown ({total} jobs) ------")
        print(f"  ✅ APPLY: {d.get('APPLY', 0)}  |  🟡 MAYBE: {d.get('MAYBE', 0)}  |  ❌ SKIP: {d.get('SKIP', 0)}")

        # Top skill gaps
        print(f"\n  -- Your Recurring Skill Gaps -----------")
        for skill, count in data["top_missing_skills"][:7]:
            bar = "█" * min(count * 3, 20)
            print(f"  [!]️  {skill:<30s} {bar} (x{count})")

        # Weakest dimensions
        print(f"\n  -- Weakest Resume Dimensions ----------")
        for dim, avg in data["resume_weakness_trends"]:
            label = dim.replace("_", " ").title()
            print(f"  📉 {label:<30s} avg: {avg}/100")

        # Common penalties
        if data["most_common_penalties"]:
            print(f"\n  -- Most Common Penalties --------------")
            for penalty, count in data["most_common_penalties"]:
                print(f"  🚩 {penalty} (x{count})")

        print("\n" + "=" * 60 + "\n")

    @staticmethod
    def _normalize(items: List[str]) -> List[str]:
        """Normalize items for consistent counting."""
        result = []
        for item in items:
            cleaned = item.lower().strip()
            if len(cleaned) > 3 and len(cleaned.split()) <= 8:
                result.append(cleaned)
        return result

    @staticmethod
    def _clean_penalties(penalties: List[str]) -> List[str]:
        """Clean penalty strings for grouping (remove variable numbers)."""
        import re
        result = []
        for p in penalties:
            # Remove specific numbers: "Keyword stuffing detected (-4)" -> "Keyword stuffing detected"
            cleaned = re.sub(r'\s*\(-?\d+\.?\d*\)', '', p).strip()
            if cleaned:
                result.append(cleaned)
        return result
