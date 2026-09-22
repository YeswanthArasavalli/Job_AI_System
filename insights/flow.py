"""
Flow Engine -- Generates daily actionable plans for the user.

Combines job data, feedback, and strategy into a prioritized
"today's plan" with specific actions, priority jobs, and skip list.
"""

from typing import Dict, List

from database.db_manager import DatabaseManager
from learning.feedback import FeedbackEngine
from learning.strategy import StrategyEngine
from utils.logger import setup_logger

logger = setup_logger(__name__)


class FlowEngine:
    """
    Generates guided user action plans.

    Usage:
        flow = FlowEngine(db)
        plan = flow.daily_plan()
    """

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.feedback = FeedbackEngine(db)
        self.strategy = StrategyEngine(self.feedback)

    def daily_plan(self) -> dict:
        """
        Generate today's action plan.

        Returns:
            Dict with today_plan, priority_jobs, skip_jobs, stats.
        """
        jobs = self.db.list_jobs(status="completed")
        feedback_data = self.feedback.analyze()
        strategy_data = self.strategy.generate()

        if not jobs:
            return {
                "today_plan": ["No jobs processed yet. Run the pipeline first!"],
                "priority_jobs": [],
                "skip_jobs": [],
                "stats": {},
            }

        # Categorize jobs
        apply_jobs = []
        maybe_jobs = []
        skip_jobs = []

        for job in jobs:
            r = job.ats_report
            if not r:
                continue

            job_summary = {
                "job_id": job.job_id,
                "title": job.title or "Unknown",
                "company": job.company or "Unknown",
                "score": r.score_after,
                "decision": r.decision,
                "effort": r.effort_level,
                "probability": r.shortlist_probability.get("shortlist_probability", 0) if r.shortlist_probability else 0,
                "missing_skills": r.missing_skills[:3],
            }

            if r.decision == "APPLY":
                apply_jobs.append(job_summary)
            elif r.decision == "MAYBE":
                maybe_jobs.append(job_summary)
            else:
                skip_jobs.append(job_summary)

        # Sort by probability (highest first)
        apply_jobs.sort(key=lambda j: j["probability"], reverse=True)
        maybe_jobs.sort(key=lambda j: j["probability"], reverse=True)

        # Build action plan
        actions = []

        # Action 1: Apply to high-match jobs
        if apply_jobs:
            count = len(apply_jobs)
            top = apply_jobs[0]
            actions.append(
                f"Apply to {count} high-match job(s) -- "
                f"best: {top['title']} @ {top['company']} ({top['probability']}% probability)"
            )

        # Action 2: Review MAYBE jobs
        convertible = [j for j in maybe_jobs if j["effort"] == "LOW"]
        if convertible:
            actions.append(
                f"Review {len(convertible)} MAYBE job(s) with LOW effort -- "
                f"small resume tweaks could convert to APPLY"
            )

        # Action 3: Skill improvement
        if "error" not in strategy_data:
            top_skills = strategy_data.get("skills_to_learn", [])
            if top_skills:
                best = top_skills[0]
                actions.append(
                    f"Improve: {best['skill']} -- "
                    f"affects {best.get('impacts_pct', '?')}% of jobs "
                    f"(~{best.get('est_time', '?')})"
                )

        # Action 4: Quick wins
        if "error" not in strategy_data:
            quick_wins = strategy_data.get("quick_wins", [])
            if quick_wins:
                actions.append(f"Quick win: {quick_wins[0]}")

        # Action 5: Resume section fix
        if "error" not in feedback_data:
            weak = feedback_data.get("weakest_dimensions", [])
            if weak:
                worst = weak[0]
                actions.append(
                    f"Strengthen resume section: {worst[0]} (avg: {worst[1]:.0f}/100)"
                )

        # Fallback
        if not actions:
            actions.append("Run the pipeline on new job descriptions to build your profile")

        # Next best action
        next_action = actions[0] if actions else "No pending actions"

        return {
            "today_plan": actions[:5],
            "next_best_action": next_action,
            "priority_jobs": apply_jobs[:5],
            "maybe_jobs": maybe_jobs[:5],
            "skip_jobs": [{"title": j["title"], "company": j["company"], "reason": f"Score {j['score']}"} for j in skip_jobs[:3]],
            "stats": {
                "total_jobs": len(jobs),
                "apply_count": len(apply_jobs),
                "maybe_count": len(maybe_jobs),
                "skip_count": len(skip_jobs),
                "avg_probability": round(
                    sum(j["probability"] for j in apply_jobs + maybe_jobs) /
                    max(len(apply_jobs) + len(maybe_jobs), 1), 1
                ),
            },
        }
