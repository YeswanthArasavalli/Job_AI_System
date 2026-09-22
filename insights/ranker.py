"""
Job Ranking & Insight Engine -- Intelligence layer over processed jobs.

Task 3: Rank jobs by match quality, effort, and confidence.
Task 8: Generate market insights (top skills, gaps, trends).

Operates on database data -- no LLM calls, pure analytics.
"""

import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

from database.db_manager import DatabaseManager
from utils.logger import setup_logger
from utils.models import ATSScoreReport, JobRecord, ProcessingStatus

logger = setup_logger(__name__)


class JobRanker:
    """
    Ranks processed jobs by composite score and generates actionable insights.

    Usage:
        ranker = JobRanker(db)
        ranked = ranker.rank_jobs()
        insights = ranker.generate_insights()
        ranker.print_rankings()
        ranker.print_insights()
    """

    def __init__(self, db: DatabaseManager):
        self.db = db

    # ================================================================
    # Job Ranking (Task 3)
    # ================================================================

    def rank_jobs(self) -> List[dict]:
        """
        Rank all completed jobs by composite score.

        Composite = 0.50 * ATS_score + 0.20 * semantic_score + 0.15 * (100 - effort_penalty) + 0.15 * confidence_bonus

        Returns sorted list of ranking dicts.
        """
        jobs = self.db.list_jobs(status="completed")

        if not jobs:
            return []

        rankings = []
        for job in jobs:
            if not job.ats_report:
                continue

            r = job.ats_report

            # Effort penalty
            effort_map = {"LOW": 0, "MEDIUM": 30, "HIGH": 60}
            effort_penalty = effort_map.get(r.effort_level, 30)

            # Confidence bonus
            conf_map = {"HIGH": 100, "MEDIUM": 60, "LOW": 30}
            conf_bonus = conf_map.get(r.confidence_level, 50)

            # Composite score
            composite = (
                r.score_after * 0.50
                + r.semantic_score * 0.20
                + (100 - effort_penalty) * 0.15
                + conf_bonus * 0.15
            )

            rankings.append({
                "job_id": job.job_id,
                "title": job.title or "Unknown",
                "company": job.company or "Unknown",
                "ats_score": r.score_after,
                "semantic_score": r.semantic_score,
                "decision": r.decision,
                "effort": r.effort_level,
                "confidence": r.confidence_level,
                "composite": round(composite, 1),
                "improvement": r.improvement,
                "risk_flags": len(r.risk_flags),
                "missing_skills": r.missing_skills,
                "pdf_path": job.pdf_path,
            })

        # Sort by composite score (descending)
        rankings.sort(key=lambda x: x["composite"], reverse=True)

        # Add rank number
        for i, r in enumerate(rankings):
            r["rank"] = i + 1

        return rankings

    def get_apply_list(self) -> List[dict]:
        """Get only jobs with APPLY decision, ranked."""
        return [r for r in self.rank_jobs() if r["decision"] == "APPLY"]

    def get_maybe_list(self) -> List[dict]:
        """Get MAYBE jobs, ranked."""
        return [r for r in self.rank_jobs() if r["decision"] == "MAYBE"]

    def get_skip_list(self) -> List[dict]:
        """Get SKIP jobs."""
        return [r for r in self.rank_jobs() if r["decision"] == "SKIP"]

    # ================================================================
    # Market Insights (Task 8)
    # ================================================================

    def generate_insights(self) -> dict:
        """
        Generate job market insights from all processed jobs.

        Returns dict with:
          - most_demanded_skills: Top skills across all JDs
          - your_skill_gaps: Skills you're missing most often
          - top_matching_roles: Roles where you score highest
          - weakest_areas: Score dimensions where you underperform
          - market_summary: High-level text summary
        """
        jobs = self.db.list_jobs(status="completed")

        if not jobs:
            return {"error": "No completed jobs to analyze"}

        # Collect data
        all_missing_skills: List[str] = []
        all_matched_skills: List[str] = []
        all_missing_kw: List[str] = []
        all_matched_kw: List[str] = []
        role_scores: Dict[str, List[float]] = {}
        company_scores: Dict[str, float] = {}
        dimension_totals = {
            "keyword_match": [],
            "skills_match": [],
            "experience_relevance": [],
            "role_alignment": [],
            "education_fit": [],
            "resume_structure": [],
        }
        decisions = {"APPLY": 0, "MAYBE": 0, "SKIP": 0}

        for job in jobs:
            if not job.ats_report:
                continue

            r = job.ats_report

            all_missing_skills.extend(r.missing_skills)
            all_matched_skills.extend(r.matched_skills)
            all_missing_kw.extend(r.missing_keywords)
            all_matched_kw.extend(r.matched_keywords)

            # Track scores by role
            role = self._normalize_role(job.title)
            if role:
                role_scores.setdefault(role, []).append(r.score_after)

            # Track by company
            if job.company:
                company_scores[job.company] = r.score_after

            # Track dimension scores
            b = r.breakdown_after
            dimension_totals["keyword_match"].append(b.keyword_match)
            dimension_totals["skills_match"].append(b.skills_match)
            dimension_totals["experience_relevance"].append(b.experience_relevance)
            dimension_totals["role_alignment"].append(b.role_alignment)
            dimension_totals["education_fit"].append(b.education_fit)
            dimension_totals["resume_structure"].append(b.resume_structure)

            decisions[r.decision] = decisions.get(r.decision, 0) + 1

        # === Most Demanded Skills (across all JDs) ===
        all_skills_mentioned = all_matched_skills + all_missing_skills
        skill_freq = Counter(self._normalize_skills(all_skills_mentioned))
        most_demanded = skill_freq.most_common(15)

        # === Your Biggest Skill Gaps ===
        gap_freq = Counter(self._normalize_skills(all_missing_skills))
        biggest_gaps = gap_freq.most_common(10)

        # === Your Strongest Skills ===
        match_freq = Counter(self._normalize_skills(all_matched_skills))
        strongest = match_freq.most_common(10)

        # === Top Matching Roles ===
        top_roles = []
        for role, scores in role_scores.items():
            avg = sum(scores) / len(scores)
            top_roles.append({"role": role, "avg_score": round(avg, 1), "count": len(scores)})
        top_roles.sort(key=lambda x: x["avg_score"], reverse=True)

        # === Weakest Scoring Dimensions ===
        dim_avgs = {}
        for dim, scores in dimension_totals.items():
            if scores:
                dim_avgs[dim] = round(sum(scores) / len(scores), 1)
        weakest = sorted(dim_avgs.items(), key=lambda x: x[1])

        # === Market Summary ===
        total = len(jobs)
        apply_pct = (decisions["APPLY"] / total * 100) if total else 0
        skip_pct = (decisions["SKIP"] / total * 100) if total else 0

        summary_lines = [
            f"Analyzed {total} job listings.",
            f"Match rate: {decisions['APPLY']} APPLY ({apply_pct:.0f}%), "
            f"{decisions['MAYBE']} MAYBE, {decisions['SKIP']} SKIP ({skip_pct:.0f}%).",
        ]

        if biggest_gaps:
            top_gap = biggest_gaps[0][0]
            summary_lines.append(
                f"Your #1 skill gap: '{top_gap}' (missing in {biggest_gaps[0][1]} JDs)."
            )

        if weakest:
            summary_lines.append(
                f"Weakest scoring area: '{weakest[0][0].replace('_', ' ')}' (avg {weakest[0][1]}/100)."
            )

        return {
            "most_demanded_skills": most_demanded,
            "your_skill_gaps": biggest_gaps,
            "your_strengths": strongest,
            "top_matching_roles": top_roles[:5],
            "weakest_dimensions": weakest[:3],
            "dimension_averages": dim_avgs,
            "decisions": decisions,
            "total_jobs": total,
            "market_summary": summary_lines,
        }

    # ================================================================
    # Pretty Printing
    # ================================================================

    def print_rankings(self):
        """Print ranked job list to terminal."""
        rankings = self.rank_jobs()

        if not rankings:
            print("\n  No completed jobs to rank.\n")
            return

        print("\n" + "=" * 90)
        print("🏆  JOB RANKINGS")
        print("=" * 90)
        print(f"  {'#':<4s} {'Title':<25s} {'Company':<15s} {'ATS':>5s} {'Sem':>5s} {'Comp':>6s} {'Decision':<8s} {'Effort':<8s}")
        print(f"  {'-' * 82}")

        for r in rankings:
            dec_icon = {"APPLY": "✅", "MAYBE": "🟡", "SKIP": "❌"}.get(r["decision"], "⚪")
            title = r["title"][:24]
            company = r["company"][:14]
            print(
                f"  {r['rank']:<4d} {title:<25s} {company:<15s} "
                f"{r['ats_score']:>5.1f} {r['semantic_score']:>5.1f} {r['composite']:>6.1f} "
                f"{dec_icon} {r['decision']:<6s} {r['effort']:<8s}"
            )

        print("=" * 90)

        # Summary
        apply_count = sum(1 for r in rankings if r["decision"] == "APPLY")
        maybe_count = sum(1 for r in rankings if r["decision"] == "MAYBE")
        skip_count = sum(1 for r in rankings if r["decision"] == "SKIP")
        print(f"  ✅ APPLY: {apply_count}  |  🟡 MAYBE: {maybe_count}  |  ❌ SKIP: {skip_count}")
        print("=" * 90 + "\n")

    def print_insights(self):
        """Print market insights to terminal."""
        insights = self.generate_insights()

        if "error" in insights:
            print(f"\n  {insights['error']}\n")
            return

        print("\n" + "=" * 60)
        print("🔍  JOB MARKET INSIGHTS")
        print("=" * 60)

        # Summary
        print("\n  -- Summary ---------------------------------")
        for line in insights["market_summary"]:
            print(f"  {line}")

        # Most demanded
        print("\n  -- Most Demanded Skills --------------------")
        for skill, count in insights["most_demanded_skills"][:10]:
            bar = "█" * min(count * 2, 20)
            print(f"  {skill:<30s} {bar} ({count})")

        # Your gaps
        print("\n  -- Your Biggest Skill Gaps -----------------")
        for skill, count in insights["your_skill_gaps"][:7]:
            print(f"  [!]️  {skill:<30s} missing in {count} JDs")

        # Your strengths
        print("\n  -- Your Strongest Skills -------------------")
        for skill, count in insights["your_strengths"][:7]:
            print(f"  ✅ {skill:<30s} matched in {count} JDs")

        # Top matching roles
        if insights["top_matching_roles"]:
            print("\n  -- Best Matching Roles ---------------------")
            for role in insights["top_matching_roles"]:
                print(f"  🎯 {role['role']:<30s} avg: {role['avg_score']:.0f}/100 ({role['count']} jobs)")

        # Weak dimensions
        print("\n  -- Weakest Scoring Areas -------------------")
        for dim, avg in insights["weakest_dimensions"]:
            label = dim.replace("_", " ").title()
            print(f"  📉 {label:<30s} avg: {avg:.0f}/100")

        print("\n" + "=" * 60 + "\n")

    # ================================================================
    # Helpers
    # ================================================================

    @staticmethod
    def _normalize_role(title: str) -> str:
        """Normalize job title for grouping."""
        if not title:
            return ""
        title = title.lower().strip()
        # Remove seniority prefixes
        title = re.sub(r'^(senior|sr\.?|junior|jr\.?|lead|principal|staff|mid-?level?)\s+', '', title)
        # Remove level suffixes
        title = re.sub(r'\s+(i{1,3}|[1-3]|level\s+\d)$', '', title)
        return title.strip().title()

    @staticmethod
    def _normalize_skills(skills: List[str]) -> List[str]:
        """Normalize skill names for consistent counting."""
        normalized = []
        for s in skills:
            s = s.lower().strip()
            # Remove long phrases, keep just the skill
            if len(s.split()) > 5:
                # Try to extract parenthetical content
                match = re.search(r'\(([^)]+)\)', s)
                if match:
                    parts = [p.strip() for p in match.group(1).split(",")]
                    normalized.extend(parts)
                continue
            normalized.append(s)
        return normalized
