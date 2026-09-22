"""
Autonomous Career Agent (v4.2) — Decision + Exploration + Learning.

Enhancements over v4.1:
  1. Diversity-based exploration — min 2 jobs, adjacent domain fallback
  2. Exploration budget — 20-30% of weekly apps
  3. Learning updates — domain weight boosting on success
  4. Interview action loop — weaknesses → concrete tasks
  5. Momentum protection — force apply after 3 days inactivity

Philosophy: Drive user behavior, don't just advise.
"""

from datetime import datetime, timedelta
from typing import List, Dict
from utils.logger import setup_logger
from pipeline.precision_engine import (
    compute_dynamic_precision, soft_calibrate, correct_precision,
    check_hard_stop, check_recovery, compute_personalized_thresholds,
    generate_decisive_strategy,
)
from pipeline.career_intelligence import (
    assess_market_competition, analyze_interview_readiness,
)

logger = setup_logger(__name__)

MAX_EXPLORE_PER_WEEK = 2
MIN_WEEKLY_APPS = 3
TARGET_WEEKLY_APPS = 5
MIN_SELECTED_JOBS = 2
EXPLORATION_BUDGET_PCT = 0.25  # 20-30%
INACTIVITY_DAYS = 3

# Adjacent domain map for diversity exploration
ADJACENT_DOMAINS = {
    "data scientist": ["data analyst", "ml engineer", "data engineer"],
    "data analyst": ["bi analyst", "data scientist", "analytics engineer"],
    "ml engineer": ["data scientist", "software engineer", "data engineer"],
    "software engineer": ["backend developer", "ml engineer", "devops"],
    "devops": ["software engineer", "cloud engineer", "sre"],
    "qa engineer": ["software engineer", "test automation", "sdet"],
}


# ================================================================
# PART 1+2 — AUTONOMOUS JOB SELECTION + STRATEGY
# ================================================================

def select_jobs_autonomously(
    evaluations: List[Dict],
    history: List[Dict],
    max_daily: int = 7,
    weekly_count: int = 0,
) -> Dict:
    """
    Autonomously filter and rank jobs using calibrated scores.
    v4.2: Ensures min 2 selected + adjacent domain diversity.
    """
    dynamic = compute_dynamic_precision(history)
    pf = dynamic["factor"]
    domain_weights = compute_domain_weights(history)

    selected = []
    skipped = []

    for ev in evaluations:
        prob = ev.get("shortlist_probability", 0)
        match_score = ev.get("jd_match_score", 0)
        root_cause = ev.get("root_cause", "UNKNOWN")

        # Apply domain weight boost
        role_key = (ev.get("role") or "").lower()
        domain_boost = domain_weights.get(role_key, 0)

        cal = soft_calibrate(prob, pf, root_cause)
        calibrated = cal["calibrated"] + domain_boost

        ev["calibrated_probability"] = round(calibrated, 1)
        ev["precision_factor"] = pf
        ev["domain_boost"] = domain_boost

        if calibrated >= 45:
            _assign_variant(ev, calibrated, match_score)
            selected.append(ev)
        else:
            ev["skip_reason"] = f"Calibrated probability {calibrated:.0f}% too low"
            skipped.append(ev)

    selected.sort(key=lambda x: x["calibrated_probability"], reverse=True)

    # v4.2: Diversity — ensure minimum 2 jobs
    if len(selected) < MIN_SELECTED_JOBS and skipped:
        # Pull best skipped job as exploration candidate
        skipped.sort(key=lambda x: x.get("calibrated_probability", 0), reverse=True)
        for candidate in skipped[:]:
            if candidate.get("calibrated_probability", 0) >= 25:  # floor for diversity
                _assign_variant(candidate, candidate["calibrated_probability"], 0)
                candidate["selection_reason"] = "diversity_fill"
                selected.append(candidate)
                skipped.remove(candidate)
                if len(selected) >= MIN_SELECTED_JOBS:
                    break

    # v4.2: Adjacent domain injection
    selected_domains = set((j.get("role") or "").lower() for j in selected)
    if len(selected_domains) == 1 and skipped:
        primary = list(selected_domains)[0]
        adjacent = ADJACENT_DOMAINS.get(primary, [])
        for candidate in skipped[:]:
            cand_role = (candidate.get("role") or "").lower()
            if any(adj in cand_role for adj in adjacent) and candidate.get("calibrated_probability", 0) >= 25:
                _assign_variant(candidate, candidate["calibrated_probability"], 0)
                candidate["selection_reason"] = "adjacent_domain"
                selected.append(candidate)
                skipped.remove(candidate)
                break

    selected = selected[:max_daily]

    return {
        "selected": selected,
        "skipped": skipped,
        "count": len(selected),
        "precision_factor": pf,
        "domain_weights": domain_weights,
    }


def _assign_variant(ev: Dict, calibrated: float, match_score: float):
    """Assign resume variant to a job evaluation."""
    if calibrated >= 65:
        ev["auto_variant"] = "impact"
        ev["auto_reason"] = "Strong match — lead with impact"
    elif match_score >= 70:
        ev["auto_variant"] = "specialized"
        ev["auto_reason"] = "High JD match — specialize for this role"
    else:
        ev["auto_variant"] = "balanced"
        ev["auto_reason"] = "Moderate fit — safe balanced approach"


# ================================================================
# PART 3 — MANDATORY ACTION ENGINE
# ================================================================

def generate_mandatory_plan(
    selection: Dict,
    history: List[Dict],
    user_progress: Dict = None,
    weekly_count: int = 0,
) -> Dict:
    """
    Generate MANDATORY actions — not suggestions.
    """
    user_progress = user_progress or {}
    strategy = generate_decisive_strategy(history)
    actions = []

    # APPLY actions
    for job in selection["selected"][:5]:
        actions.append({
            "type": "APPLY",
            "emoji": "📨",
            "target": f"{job['company']} — {job['role']}",
            "variant": job.get("auto_variant", "balanced"),
            "probability": job["calibrated_probability"],
        })

    # SKIP directives
    for s in strategy.get("stop", [])[:2]:
        actions.append({
            "type": "STOP",
            "emoji": "🚫",
            "target": s["role"],
            "reason": s["reason"],
        })

    # BUILD if stagnant
    projects = user_progress.get("projects_completed", [])
    skills = user_progress.get("skills_learned", [])
    if not projects and len(history) >= 10:
        actions.append({
            "type": "BUILD",
            "emoji": "🔨",
            "target": "1 real project in your target domain",
            "reason": "No projects detected — this is blocking your progress",
        })

    # THROUGHPUT warning
    if weekly_count < MIN_WEEKLY_APPS:
        actions.append({
            "type": "INCREASE",
            "emoji": "📈",
            "target": f"Apply to {MIN_WEEKLY_APPS - weekly_count} more jobs this week",
            "reason": f"Only {weekly_count} apps this week (minimum: {MIN_WEEKLY_APPS})",
        })

    return {
        "actions": actions,
        "total": len(actions),
        "apply_count": len([a for a in actions if a["type"] == "APPLY"]),
        "has_critical": any(a["type"] in ("STOP", "BUILD") for a in actions),
    }


# ================================================================
# EXPLORATION ENGINE — CONFIDENCE BANDS
# ================================================================

def classify_confidence_band(
    calibrated_probability: float,
    weekly_count: int = 0,
    recent_explorations: int = 0,
    root_cause: str = "UNKNOWN",
) -> Dict:
    """
    Confidence band classification with exploration support.

    <30  → BLOCK
    30-45 → EXPLORE (max 2/week)
    45-60 → WARNING
    >60  → APPLY
    """
    if calibrated_probability < 30:
        decision = "BLOCK"
        emoji = "🚫"
        reason = f"{calibrated_probability:.0f}% — too low even for exploration"
    elif calibrated_probability < 45:
        # Exploration logic
        can_explore = (
            recent_explorations < MAX_EXPLORE_PER_WEEK
            and weekly_count < TARGET_WEEKLY_APPS
        )
        if can_explore:
            decision = "EXPLORE"
            emoji = "🧪"
            reason = (
                f"{calibrated_probability:.0f}% — experiment apply "
                f"({recent_explorations}/{MAX_EXPLORE_PER_WEEK} explorations used)"
            )
        else:
            decision = "BLOCK"
            emoji = "🚫"
            reason = f"Exploration limit reached ({recent_explorations}/{MAX_EXPLORE_PER_WEEK})"
    elif calibrated_probability < 60:
        decision = "WARNING"
        emoji = "⚠️"
        reason = f"{calibrated_probability:.0f}% — apply with caution, fix gaps first"
    else:
        decision = "APPLY"
        emoji = "✅"
        reason = f"{calibrated_probability:.0f}% — strong fit, apply now"

    return {
        "decision": decision,
        "emoji": emoji,
        "reason": reason,
        "calibrated_probability": round(calibrated_probability, 1),
    }


# ================================================================
# THROUGHPUT ENGINE
# ================================================================

def enforce_throughput(
    weekly_count: int,
    thresholds: Dict,
) -> Dict:
    """
    Ensure minimum application throughput.
    Relaxes thresholds if weekly count is too low.
    """
    if weekly_count >= TARGET_WEEKLY_APPS:
        return {
            "status": "ON_TRACK",
            "adjustment": None,
            "message": f"Good pace: {weekly_count} apps this week.",
        }
    elif weekly_count >= MIN_WEEKLY_APPS:
        return {
            "status": "ACCEPTABLE",
            "adjustment": None,
            "message": f"{weekly_count} apps — consider 1-2 more for optimal coverage.",
        }
    else:
        # Relax thresholds to allow more applications
        relaxed = {
            "block": max(thresholds["block"] - 5, 25),
            "warn": max(thresholds["warn"] - 5, 40),
            "allow": max(thresholds["allow"] - 5, 40),
            "adjustment": "relaxed_throughput",
        }
        return {
            "status": "LOW",
            "adjustment": relaxed,
            "message": (
                f"Only {weekly_count} apps this week — thresholds relaxed by 5% "
                f"to maintain momentum."
            ),
        }


# ================================================================
# INTERVIEW WEAKNESS ENGINE
# ================================================================

def identify_interview_weaknesses(
    candidate_skills: List[str],
    jd_skills: List[str],
    role: str,
) -> Dict:
    """
    Identify TOP failure points for interviews.
    Specific questions the user will likely fail.
    """
    gaps = set(s.lower() for s in jd_skills) - set(s.lower() for s in candidate_skills)
    role_lower = role.lower()

    failure_points = []

    # Technical gaps → specific questions
    for skill in list(gaps)[:3]:
        if skill in ("spark", "pyspark"):
            failure_points.append({
                "topic": "Distributed Computing",
                "question": "How would you process 1TB of data that doesn't fit in memory?",
                "weakness": "No Spark/distributed computing experience",
            })
        elif skill in ("kubernetes", "k8s"):
            failure_points.append({
                "topic": "Container Orchestration",
                "question": "How do you deploy and scale a model serving endpoint?",
                "weakness": "No Kubernetes experience",
            })
        elif skill in ("mlops",):
            failure_points.append({
                "topic": "ML Operations",
                "question": "How do you monitor model drift in production?",
                "weakness": "No MLOps pipeline experience",
            })
        elif skill in ("tensorflow", "tf"):
            failure_points.append({
                "topic": "Deep Learning Framework",
                "question": "Compare eager vs graph execution. When would you use each?",
                "weakness": "Only familiar with PyTorch, not TensorFlow",
            })
        else:
            failure_points.append({
                "topic": skill.title(),
                "question": f"Explain your experience with {skill} in a production context",
                "weakness": f"No demonstrable {skill} experience",
            })

    # Role-specific behavioral failures
    if "data" in role_lower:
        failure_points.append({
            "topic": "Model Evaluation",
            "question": "Your model has 95% accuracy but stakeholders say it's useless. Why?",
            "weakness": "Class imbalance / metric selection depth",
        })
    elif "software" in role_lower or "engineer" in role_lower:
        failure_points.append({
            "topic": "System Design",
            "question": "Design a system that handles 10K requests/second with <100ms latency",
            "weakness": "Scaling and architecture knowledge depth",
        })

    # v4.2: Convert weaknesses → actionable tasks
    tasks = []
    for fp in failure_points[:3]:
        tasks.append({
            "task": f"Study: {fp['topic']}",
            "action": f"Build a mini-project demonstrating {fp['topic'].lower()}",
            "timeline": "3-5 days",
            "proof": f"Add to portfolio with README explaining your approach",
        })

    return {
        "failure_points": failure_points[:5],
        "total_gaps": len(gaps),
        "critical_count": len(failure_points),
        "action_tasks": tasks,
    }


# ================================================================
# v4.2 — DOMAIN WEIGHT LEARNING
# ================================================================

def compute_domain_weights(history: List[Dict]) -> Dict:
    """
    Boost domain weights based on historical success.
    Domains with higher shortlist rates get a probability boost.
    """
    domain_stats = {}
    for h in history:
        role = (h.get("role") or "").lower()
        if role not in domain_stats:
            domain_stats[role] = {"total": 0, "shortlisted": 0}
        domain_stats[role]["total"] += 1
        if h.get("status") == "shortlisted":
            domain_stats[role]["shortlisted"] += 1

    weights = {}
    for role, stats in domain_stats.items():
        if stats["total"] >= 2:
            rate = stats["shortlisted"] / stats["total"]
            # Boost: up to +8% for proven domains, -3% for failing ones
            if rate > 0.3:
                weights[role] = 8
            elif rate > 0.1:
                weights[role] = 4
            elif stats["total"] >= 3 and stats["shortlisted"] == 0:
                weights[role] = -3

    return weights


# ================================================================
# v4.2 — EXPLORATION BUDGET
# ================================================================

def compute_exploration_budget(weekly_count: int, target: int = TARGET_WEEKLY_APPS) -> Dict:
    """
    20-30% of weekly applications reserved for exploration.
    """
    budget = max(1, int(target * EXPLORATION_BUDGET_PCT))
    remaining = max(0, budget)  # reset weekly

    return {
        "budget": budget,
        "remaining": remaining,
        "target_apps": target,
        "message": f"{budget} exploration slots available this week (of {target} total)",
    }


# ================================================================
# v4.2 — MOMENTUM PROTECTION
# ================================================================

def check_momentum(history: List[Dict], last_activity_date: str = None) -> Dict:
    """
    Force apply if inactivity > 3 days.
    """
    if last_activity_date:
        try:
            last = datetime.fromisoformat(last_activity_date.replace("Z", "+00:00"))
        except Exception:
            last = datetime.now()
    elif history:
        # Use last history entry date
        last_entry = history[-1]
        date_str = last_entry.get("created_at") or last_entry.get("date", "")
        try:
            last = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            last = datetime.now()
    else:
        last = datetime.now()

    now = datetime.now(last.tzinfo) if last.tzinfo else datetime.now()
    days_inactive = (now - last).days

    if days_inactive >= INACTIVITY_DAYS:
        return {
            "momentum_lost": True,
            "days_inactive": days_inactive,
            "status": "FORCE_APPLY",
            "emoji": "🚨",
            "message": (
                f"Momentum lost — {days_inactive} days without activity. "
                f"Apply to at least 2 jobs TODAY, even borderline ones."
            ),
        }
    elif days_inactive >= 2:
        return {
            "momentum_lost": False,
            "days_inactive": days_inactive,
            "status": "WARNING",
            "emoji": "⚠️",
            "message": f"{days_inactive} days since last activity — apply tomorrow.",
        }
    else:
        return {
            "momentum_lost": False,
            "days_inactive": days_inactive,
            "status": "ACTIVE",
            "emoji": "✅",
            "message": "Active — keep going.",
        }


# ================================================================
# MASTER ORCHESTRATOR (v4.2)
# ================================================================

def run_autonomous_agent(
    evaluations: List[Dict] = None,
    history: List[Dict] = None,
    user_progress: Dict = None,
    weekly_count: int = 0,
    recent_explorations: int = 0,
    candidate_skills: List[str] = None,
    jd_skills: List[str] = None,
    role: str = "",
    experience_level: str = "1-3 yrs",
    last_activity_date: str = None,
) -> Dict:
    """
    Run the complete autonomous career agent (v4.2).
    """
    evaluations = evaluations or []
    history = history or []
    user_progress = user_progress or {}
    candidate_skills = candidate_skills or []
    jd_skills = jd_skills or []

    # v4.2: Momentum check
    momentum = check_momentum(history, last_activity_date)

    # Autonomous job selection (v4.2: diversity + domain weights)
    selection = select_jobs_autonomously(evaluations, history, weekly_count=weekly_count)

    # v4.2: If momentum lost, force-relax selection
    if momentum["momentum_lost"] and selection["count"] < 2 and selection["skipped"]:
        for candidate in selection["skipped"][:]:
            if candidate.get("calibrated_probability", 0) >= 20:
                _assign_variant(candidate, candidate["calibrated_probability"], 0)
                candidate["selection_reason"] = "momentum_force"
                selection["selected"].append(candidate)
                selection["skipped"].remove(candidate)
                selection["count"] += 1
                if selection["count"] >= 2:
                    break

    # Mandatory action plan
    plan = generate_mandatory_plan(selection, history, user_progress, weekly_count)

    # v4.2: Add momentum action if needed
    if momentum["momentum_lost"]:
        plan["actions"].insert(0, {
            "type": "URGENT",
            "emoji": "🚨",
            "target": "Apply to 2+ jobs TODAY",
            "reason": momentum["message"],
        })
        plan["total"] += 1
        plan["has_critical"] = True

    # Throughput + exploration budget
    thresholds = compute_personalized_thresholds(history)
    throughput = enforce_throughput(weekly_count, thresholds)
    exploration = compute_exploration_budget(weekly_count)

    # Interview weaknesses + action tasks
    interview = None
    if role and jd_skills:
        interview = identify_interview_weaknesses(candidate_skills, jd_skills, role)

    # Trajectory
    resolved = [h for h in history if h.get("status") in ("shortlisted", "rejected")]
    shortlisted = len([h for h in resolved if h["status"] == "shortlisted"])
    total = len(resolved)
    rate = (shortlisted / total * 100) if total else 0

    if rate >= 15:
        stage = "STRONG — maintain and optimize"
    elif rate >= 8:
        stage = "ON_TRACK — keep improving"
    elif rate >= 3:
        stage = "BUILDING — focus on quality applications"
    else:
        stage = "EARLY — build skills and apply strategically"

    return {
        "selection": selection,
        "plan": plan,
        "throughput": throughput,
        "exploration_budget": exploration,
        "momentum": momentum,
        "interview_weaknesses": interview,
        "trajectory": {
            "stage": stage,
            "shortlist_rate": round(rate, 1),
            "total_resolved": total,
        },
        "summary": {
            "jobs_selected": selection["count"],
            "actions": plan["total"],
            "throughput": throughput["status"],
            "momentum": momentum["status"],
            "stage": stage,
        },
    }
