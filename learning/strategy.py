"""
Resume Strategy Engine -- Generates actionable career recommendations.

Consumes feedback data to produce specific, prioritized suggestions:
  - Skills to learn (with estimated impact)
  - Projects to add (with type recommendations)
  - Resume sections to strengthen
  - Roles to target vs avoid

No LLM needed -- pure data-driven analysis.
"""

from typing import Dict, List, Tuple

from learning.feedback import FeedbackEngine
from utils.logger import setup_logger

logger = setup_logger(__name__)


class StrategyEngine:
    """
    Generates career improvement strategies from feedback data.

    Usage:
        strategy = StrategyEngine(feedback_engine)
        plan = strategy.generate()
        strategy.print_plan()
    """

    # Skill learning difficulty estimates (weeks to basic proficiency)
    _SKILL_EFFORT = {
        "sql": 2, "python": 4, "pandas": 2, "numpy": 2,
        "react": 4, "typescript": 3, "javascript": 2,
        "docker": 2, "kubernetes": 4, "aws": 4, "gcp": 4, "azure": 4,
        "tableau": 2, "power bi": 2, "excel": 1,
        "git": 1, "ci/cd": 2, "jenkins": 2,
        "machine learning": 8, "deep learning": 10, "tensorflow": 6,
        "pytorch": 6, "nlp": 8, "computer vision": 8,
        "spark": 4, "airflow": 3, "kafka": 4, "etl": 3,
        "node.js": 3, "django": 3, "flask": 2, "fastapi": 2,
        "html": 1, "css": 1, "sass": 1,
        "a/b testing": 2, "statistical analysis": 3,
        "data visualization": 2, "data analysis": 3,
        "rest api": 2, "graphql": 2, "microservices": 4,
        "terraform": 3, "linux": 2, "bash": 1,
        "agile": 1, "scrum": 1, "jira": 1,
    }

    def __init__(self, feedback: FeedbackEngine, config=None):
        self.feedback = feedback
        self.config = config
        self._user_prefs = None
        if config and hasattr(config, 'user_preferences'):
            self._user_prefs = config.user_preferences

    def generate(self) -> dict:
        """
        Generate a prioritized career improvement plan.
        Adapts based on user_preferences from config.

        Returns:
            Dict with skills_to_learn, projects_to_add, sections_to_fix,
            roles_to_target, and estimated_timeline.
        """
        data = self.feedback.analyze()

        if "error" in data:
            return {"error": data["error"]}

        total_jobs = data["total_jobs_analyzed"]
        missing_skills = data["top_missing_skills"]
        weaknesses = data["resume_weakness_trends"]
        dim_avgs = data["dimension_averages"]
        penalties = data["most_common_penalties"]

        # === 1. Skills to learn (prioritized by impact) ===
        skills_plan = []
        priority_skills = set()
        if self._user_prefs and self._user_prefs.skill_priority:
            priority_skills = {s.lower() for s in self._user_prefs.skill_priority}

        for skill, count in missing_skills[:10]:
            impact_pct = round((count / total_jobs) * 100) if total_jobs else 0
            effort_weeks = self._estimate_effort(skill)
            roi = impact_pct / max(effort_weeks, 1)

            # Boost ROI for user-prioritized skills
            if priority_skills and skill.lower() in priority_skills:
                roi *= 1.5

            skills_plan.append({
                "skill": skill,
                "missing_in": count,
                "impacts_pct": impact_pct,
                "impact": f"improves {impact_pct}% of jobs",
                "est_time": f"~{effort_weeks} weeks",
                "effort": f"~{effort_weeks} weeks",
                "roi_score": round(roi, 1),
                "user_priority": skill.lower() in priority_skills if priority_skills else False,
            })

        skills_plan.sort(key=lambda x: x["roi_score"], reverse=True)

        # === 2. Projects to add ===
        projects_plan = self._suggest_projects(missing_skills, weaknesses)

        # === 3. Sections to fix ===
        sections_plan = []
        for dim, avg in weaknesses:
            label = dim.replace("_", " ").title()
            if avg < 50:
                sections_plan.append({
                    "section": label,
                    "current_avg": avg,
                    "priority": "HIGH",
                    "suggestion": self._get_section_fix(dim),
                })
            elif avg < 70:
                sections_plan.append({
                    "section": label,
                    "current_avg": avg,
                    "priority": "MEDIUM",
                    "suggestion": self._get_section_fix(dim),
                })

        # === 4. Roles to target ===
        decisions = data["decisions"]
        apply_rate = decisions.get("APPLY", 0) / total_jobs * 100 if total_jobs else 0

        # === 5. Timeline ===
        top3_skills = skills_plan[:3]
        total_weeks = sum(self._estimate_effort(s["skill"]) for s in top3_skills)

        # === 6. Next best action ===
        next_action = self._compute_next_action(skills_plan, sections_plan, apply_rate)

        quick_wins = [s for s in skills_plan if self._estimate_effort(s["skill"]) <= 2][:3]

        return {
            "skills_to_learn": skills_plan[:7],
            "projects_to_add": projects_plan,
            "sections_to_fix": sections_plan,
            "apply_rate": round(apply_rate, 1),
            "total_jobs": total_jobs,
            "estimated_timeline": f"~{total_weeks} weeks for top 3 skills",
            "quick_wins": quick_wins,
            "next_best_action": next_action,
        }

    def _compute_next_action(self, skills: list, sections: list, apply_rate: float) -> str:
        """Determine the single highest-impact next action."""
        if apply_rate < 30 and sections:
            high_priority = [s for s in sections if s["priority"] == "HIGH"]
            if high_priority:
                return f"Fix resume: {high_priority[0]['section']} -- {high_priority[0]['suggestion']}"

        if skills:
            best = skills[0]
            if best.get("user_priority"):
                return f"Learn {best['skill']} (YOUR priority, ROI: {best['roi_score']}) -- {best['impact']}"
            return f"Learn {best['skill']} (ROI: {best['roi_score']}) -- {best['impact']}"

        return "Run pipeline on more jobs to build profile"

    def print_plan(self):
        """Print formatted strategy plan."""
        plan = self.generate()

        if "error" in plan:
            print(f"\n  {plan['error']}\n")
            return

        print("\n" + "=" * 60)
        print("🎯  CAREER STRATEGY PLAN")
        print("=" * 60)

        # Quick wins
        if plan["quick_wins"]:
            print(f"\n  -- Quick Wins (learn in ≤2 weeks) -----")
            for s in plan["quick_wins"]:
                print(f"  ⚡ Learn {s['skill']:<20s} -> {s['impact']} (ROI: {s['roi_score']})")

        # Skills to learn
        print(f"\n  -- Skills to Learn (by ROI) ------------")
        for i, s in enumerate(plan["skills_to_learn"][:7]):
            icon = "🔥" if s["roi_score"] > 5 else "📚"
            print(f"  {icon} {i+1}. {s['skill']:<22s} {s['impact']:<25s} {s['effort']:<12s} ROI={s['roi_score']}")

        # Projects to add
        if plan["projects_to_add"]:
            print(f"\n  -- Projects to Add ---------------------")
            for p in plan["projects_to_add"]:
                print(f"  🛠️  {p['name']}")
                print(f"      Skills: {p['skills']}  |  Impact: {p['impact']}")

        # Sections to fix
        if plan["sections_to_fix"]:
            print(f"\n  -- Resume Sections to Fix --------------")
            for s in plan["sections_to_fix"]:
                icon = "🔴" if s["priority"] == "HIGH" else "🟡"
                print(f"  {icon} {s['section']:<25s} avg: {s['current_avg']}/100")
                print(f"      -> {s['suggestion']}")

        # Summary
        print(f"\n  -- Summary -----------------------------")
        print(f"  Apply rate: {plan['apply_rate']}% ({plan['total_jobs']} jobs)")
        print(f"  Timeline: {plan['estimated_timeline']}")

        print("\n" + "=" * 60 + "\n")

    # ================================================================
    # Helpers
    # ================================================================

    def _estimate_effort(self, skill: str) -> int:
        """Estimate weeks to learn a skill."""
        skill_lower = skill.lower().strip()
        for key, weeks in self._SKILL_EFFORT.items():
            if key in skill_lower:
                return weeks
        return 3  # Default: 3 weeks

    def _suggest_projects(self, missing_skills: list, weaknesses: list) -> list:
        """Suggest projects based on skill gaps."""
        projects = []
        skill_names = {s[0].lower() for s in missing_skills[:5]}

        # Data project
        data_skills = {"sql", "pandas", "data analysis", "etl", "tableau", "power bi", "spark"}
        if skill_names & data_skills:
            matched = skill_names & data_skills
            projects.append({
                "name": "Data Analysis Portfolio Project",
                "skills": ", ".join(sorted(matched)[:4]),
                "impact": "Boosts data experience + skills score",
                "description": "Build an end-to-end data pipeline: extract data, transform with SQL/Pandas, visualize with Tableau/PowerBI",
            })

        # ML project
        ml_skills = {"machine learning", "deep learning", "tensorflow", "pytorch", "nlp"}
        if skill_names & ml_skills:
            matched = skill_names & ml_skills
            projects.append({
                "name": "ML/AI Side Project",
                "skills": ", ".join(sorted(matched)[:4]),
                "impact": "Fills ML gap + shows practical application",
                "description": "Build a prediction model on a real dataset, deploy as API",
            })

        # Cloud/DevOps project
        cloud_skills = {"aws", "gcp", "azure", "docker", "kubernetes", "terraform"}
        if skill_names & cloud_skills:
            matched = skill_names & cloud_skills
            projects.append({
                "name": "Cloud Deployment Project",
                "skills": ", ".join(sorted(matched)[:4]),
                "impact": "Shows cloud competency + DevOps skills",
                "description": "Containerize an app, deploy with CI/CD to cloud",
            })

        # Frontend project
        fe_skills = {"react", "typescript", "angular", "vue", "next.js"}
        if skill_names & fe_skills:
            matched = skill_names & fe_skills
            projects.append({
                "name": "Modern Frontend Application",
                "skills": ", ".join(sorted(matched)[:4]),
                "impact": "Demonstrates frontend proficiency",
                "description": "Build a responsive SPA with state management and testing",
            })

        return projects[:3]

    @staticmethod
    def _get_section_fix(dimension: str) -> str:
        """Get specific fix suggestion for a weak dimension."""
        fixes = {
            "keyword_match": "Mirror exact phrases from JDs in your summary and bullets",
            "skills_match": "Add missing tech skills to your skills section, verify they're real",
            "experience_relevance": "Rewrite bullets to highlight responsibilities matching target roles",
            "role_alignment": "Update your title/summary to match target role language",
            "education_fit": "Add relevant coursework, certifications, or bootcamps",
            "resume_structure": "Add metrics, quantify achievements, use action verbs",
        }
        return fixes.get(dimension, "Review and strengthen this section")
