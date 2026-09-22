"""
Job Monitor — Continuous Job Monitoring + Smart Alerts + Weekly Optimization.

Sits on top of the Daily Pipeline (v3.1) and adds:
  - Smart alert filtering (only high-value opportunities)
  - Priority classification (HIGH / MEDIUM / LOW)
  - Weekly performance analysis with trend tracking
  - Adaptive strategy updates based on real outcomes

RULES:
  - DO NOT alert all jobs (quality > quantity)
  - DO NOT notify low-probability roles
  - DO NOT auto-apply
  - Prioritize quality over volume
"""

import re
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from utils.models import StructuredResume, ExtractedJD
from utils.logger import setup_logger
from pipeline.job_pipeline import (
    intake_jobs, process_jd, evaluate_job, assign_resume_strategy,
    rank_jobs, JobListing,
)
from pipeline.hiring_simulation import (
    compute_variant_performance,
    compute_performance_metrics,
    analyze_application_feedback,
)

logger = setup_logger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_ALERT_LOG = os.path.join(_DATA_DIR, "alert_log.json")
_WEEKLY_LOG = os.path.join(_DATA_DIR, "weekly_reports.json")


# ================================================================
# PART 1+2 — CONTINUOUS MONITORING + SMART ALERT FILTERING
# ================================================================

def filter_alerts(
    evaluations: List[Dict],
    history: List[Dict] = None,
) -> List[Dict]:
    """
    Filter evaluations into smart alerts.
    
    ONLY triggers alerts if:
      - shortlist_probability >= 60% (APPLY NOW)
      - OR shortlist_probability >= 50% AND jd_match >= 80
    
    Suppresses:
      - Low-probability jobs
      - Companies already applied to recently
      - Repeated low-performing domains
    """
    history = history or []
    
    # Build suppression lists
    recent_companies = set()
    for h in history[-30:]:  # last 30 applications
        company = (h.get("company") or "").lower().strip()
        if company:
            recent_companies.add(company)
    
    # Find failing domains (domains with 0% shortlist rate in last 10 apps)
    domain_failures = set()
    domain_stats = {}
    for h in history[-20:]:
        domain = (h.get("role") or "").lower()
        if domain not in domain_stats:
            domain_stats[domain] = {"total": 0, "shortlisted": 0}
        domain_stats[domain]["total"] += 1
        if h.get("status") == "shortlisted":
            domain_stats[domain]["shortlisted"] += 1
    
    for domain, stats in domain_stats.items():
        if stats["total"] >= 3 and stats["shortlisted"] == 0:
            domain_failures.add(domain)
    
    alerts = []
    suppressed = []
    
    for ev in evaluations:
        prob = ev["shortlist_probability"]
        match = ev["jd_match_score"]
        company_lower = ev["company"].lower().strip()
        
        # Suppression checks
        if company_lower in recent_companies:
            ev["suppressed_reason"] = "Recently applied to this company"
            suppressed.append(ev)
            continue
        
        # Alert threshold check
        is_alert = (
            prob >= 60
            or (prob >= 50 and match >= 80)
        )
        
        if not is_alert:
            ev["suppressed_reason"] = f"Below threshold (prob={prob}%, match={match})"
            suppressed.append(ev)
            continue
        
        alerts.append(ev)
    
    logger.info(
        f"ALERT FILTER: {len(alerts)} alerts from {len(evaluations)} jobs "
        f"({len(suppressed)} suppressed)"
    )
    
    return alerts


# ================================================================
# PART 3 — PRIORITY ALERT SYSTEM
# ================================================================

def classify_alerts(alerts: List[Dict]) -> Dict:
    """
    Classify alerts into priority tiers.
    
    🔥 HIGH: APPLY NOW (prob >= 70%)
    ⚡ MEDIUM: APPLY FIX GAPS (prob 50-70%)
    🧊 LOW: borderline (prob 40-50%)
    """
    high = []
    medium = []
    low = []
    
    for alert in alerts:
        prob = alert["shortlist_probability"]
        
        if prob >= 70:
            alert["priority"] = "HIGH"
            alert["priority_emoji"] = "🔥"
            alert["priority_reason"] = "Strong match — apply immediately"
            high.append(alert)
        elif prob >= 50:
            alert["priority"] = "MEDIUM"
            alert["priority_emoji"] = "⚡"
            alert["priority_reason"] = "Good fit — fix gaps then apply"
            medium.append(alert)
        else:
            alert["priority"] = "LOW"
            alert["priority_emoji"] = "🧊"
            alert["priority_reason"] = "Borderline — apply if no better options"
            low.append(alert)
    
    return {
        "high": high,
        "medium": medium,
        "low": low,
        "total_alerts": len(alerts),
        "summary": (
            f"{len(high)} HIGH priority, {len(medium)} MEDIUM, {len(low)} LOW"
        ),
    }


# ================================================================
# PART 5 — DAILY APPLICATION SUGGESTION
# ================================================================

def generate_daily_suggestion(
    classified: Dict,
    max_suggestions: int = 7,
) -> Dict:
    """
    Generate today's top application suggestions from alerts.
    
    Distribution:
      - 2-3 HIGH priority (APPLY NOW)
      - 2-3 MEDIUM priority (FIX GAPS)
      - 0-1 LOW (optional filler)
    """
    suggestions = []
    seen_companies = set()
    
    # Take HIGH first (max 3)
    for alert in classified["high"][:3]:
        company_key = alert["company"].lower()
        if company_key not in seen_companies:
            suggestions.append(alert)
            seen_companies.add(company_key)
    
    # Then MEDIUM (max 3)
    for alert in classified["medium"][:3]:
        company_key = alert["company"].lower()
        if company_key not in seen_companies:
            suggestions.append(alert)
            seen_companies.add(company_key)
    
    # Fill with LOW if needed
    if len(suggestions) < max_suggestions:
        for alert in classified["low"][:2]:
            company_key = alert["company"].lower()
            if company_key not in seen_companies:
                suggestions.append(alert)
                seen_companies.add(company_key)
    
    suggestions = suggestions[:max_suggestions]
    
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "suggestions": suggestions,
        "count": len(suggestions),
        "high_count": len([s for s in suggestions if s.get("priority") == "HIGH"]),
        "medium_count": len([s for s in suggestions if s.get("priority") == "MEDIUM"]),
    }


# ================================================================
# PART 6+7 — WEEKLY OPTIMIZATION ENGINE
# ================================================================

def generate_weekly_report(history: List[Dict]) -> Dict:
    """
    Analyze the past week's performance and generate optimization insights.
    
    Returns:
      - weekly_stats: applications, shortlists, rate
      - trend: improving / declining / stable
      - what_works: patterns from successful applications
      - what_fails: patterns from rejections
      - best_variant: highest-performing resume variant
      - best_domains: highest-success role types
      - avoid_list: roles/domains to deprioritize
      - next_week_plan: specific recommendations
    """
    if not history:
        return {
            "weekly_stats": {"applications": 0, "shortlisted": 0, "rejected": 0, "rate": 0, "prev_week_rate": 0},
            "trend": "insufficient_data",
            "trend_emoji": "📊",
            "what_works": [],
            "what_fails": [],
            "best_variant": "balanced",
            "variant_performance": {},
            "best_domains": [],
            "avoid_list": [],
            "next_week_plan": ["Start applying to build baseline data"],
            "summary": "No application data yet. Start applying to build insights.",
        }
    
    # Split into this week and previous week
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    
    this_week = []
    prev_week = []
    
    for h in history:
        try:
            created = h.get("created_at") or h.get("date", "")
            if created:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            else:
                dt = now  # assume recent
        except Exception:
            dt = now
        
        if dt >= week_ago:
            this_week.append(h)
        elif dt >= two_weeks_ago:
            prev_week.append(h)
    
    # If no date-based split possible, use last N entries
    if not this_week and not prev_week:
        mid = len(history) // 2
        this_week = history[mid:]
        prev_week = history[:mid]
    
    # Weekly stats
    tw_total = len(this_week)
    tw_shortlisted = len([h for h in this_week if h.get("status") == "shortlisted"])
    tw_rejected = len([h for h in this_week if h.get("status") == "rejected"])
    tw_rate = (tw_shortlisted / tw_total * 100) if tw_total > 0 else 0
    
    pw_total = len(prev_week)
    pw_shortlisted = len([h for h in prev_week if h.get("status") == "shortlisted"])
    pw_rate = (pw_shortlisted / pw_total * 100) if pw_total > 0 else 0
    
    # Trend
    if tw_total < 2 or pw_total < 2:
        trend = "insufficient_data"
    elif tw_rate > pw_rate + 2:
        trend = "improving"
    elif tw_rate < pw_rate - 2:
        trend = "declining"
    else:
        trend = "stable"
    
    # What works (from shortlisted applications)
    what_works = []
    shortlisted_modes = [h.get("mode", "strict") for h in history if h.get("status") == "shortlisted"]
    if shortlisted_modes:
        best_mode = max(set(shortlisted_modes), key=shortlisted_modes.count)
        what_works.append(f"'{best_mode}' mode has highest shortlist rate")
    
    shortlisted_scores = [h.get("ats_score", 0) for h in history if h.get("status") == "shortlisted"]
    if shortlisted_scores:
        avg_score = sum(shortlisted_scores) / len(shortlisted_scores)
        what_works.append(f"Shortlisted apps have avg ATS score of {avg_score:.0f}")
    
    # What fails (from rejected applications)
    what_fails = []
    rejected_roles = [h.get("role", "?") for h in history if h.get("status") == "rejected"]
    if rejected_roles:
        common_reject = max(set(rejected_roles), key=rejected_roles.count) if len(rejected_roles) > 1 else rejected_roles[0]
        what_fails.append(f"Most rejections from '{common_reject}' type roles")
    
    rejected_scores = [h.get("ats_score", 0) for h in history if h.get("status") == "rejected"]
    if rejected_scores:
        avg_reject = sum(rejected_scores) / len(rejected_scores)
        what_fails.append(f"Rejected apps avg score: {avg_reject:.0f}")
    
    # Best variant
    variant_perf = compute_variant_performance(history)
    best_variant = variant_perf.get("best_variant") or "balanced"
    
    # Best domains (roles with highest shortlist rate)
    role_stats = {}
    for h in history:
        role = (h.get("role") or "unknown").lower()
        # Normalize role to domain
        if any(k in role for k in ["data", "analytics", "ml", "machine learning"]):
            domain = "data"
        elif any(k in role for k in ["software", "developer", "engineer", "backend", "frontend"]):
            domain = "software"
        elif any(k in role for k in ["qa", "test", "quality"]):
            domain = "qa"
        else:
            domain = "other"
        
        if domain not in role_stats:
            role_stats[domain] = {"total": 0, "shortlisted": 0}
        role_stats[domain]["total"] += 1
        if h.get("status") == "shortlisted":
            role_stats[domain]["shortlisted"] += 1
    
    best_domains = []
    avoid_list = []
    for domain, stats in sorted(role_stats.items(), key=lambda x: x[1]["total"], reverse=True):
        rate = (stats["shortlisted"] / stats["total"] * 100) if stats["total"] > 0 else 0
        if rate > 0:
            best_domains.append(f"{domain} ({rate:.0f}% success, {stats['total']} apps)")
        elif stats["total"] >= 3:
            avoid_list.append(f"{domain} ({stats['total']} apps, 0 shortlists)")
    
    # Next week plan
    next_week_plan = []
    
    if trend == "declining":
        next_week_plan.append("SHIFT strategy — current approach is losing effectiveness")
    
    if best_domains:
        next_week_plan.append(f"Focus on {best_domains[0].split(' (')[0]} roles — highest success rate")
    
    if best_variant != "balanced":
        next_week_plan.append(f"Use '{best_variant}' mode — proven higher shortlist rate")
    else:
        next_week_plan.append("Continue with 'balanced' mode (default proven strategy)")
    
    if avoid_list:
        next_week_plan.append(f"Avoid {avoid_list[0].split(' (')[0]} roles — zero success so far")
    
    if tw_rate < 8:
        next_week_plan.append("Apply to fewer but better-matched jobs (target 5-7/week)")
    
    if not next_week_plan:
        next_week_plan.append("Maintain current strategy — performance is stable")
    
    summary = (
        f"Week: {tw_total} applications, {tw_shortlisted} shortlisted ({tw_rate:.0f}%). "
        f"Trend: {trend}. "
        f"{'Keep it up!' if trend == 'improving' else 'See recommendations below.'}"
    )
    
    return {
        "weekly_stats": {
            "applications": tw_total,
            "shortlisted": tw_shortlisted,
            "rejected": tw_rejected,
            "rate": round(tw_rate, 1),
            "prev_week_rate": round(pw_rate, 1),
        },
        "trend": trend,
        "trend_emoji": {"improving": "📈", "stable": "➡️", "declining": "📉", "insufficient_data": "📊"}.get(trend, "📊"),
        "what_works": what_works,
        "what_fails": what_fails,
        "best_variant": best_variant,
        "variant_performance": variant_perf,
        "best_domains": best_domains,
        "avoid_list": avoid_list,
        "next_week_plan": next_week_plan[:5],
        "summary": summary,
    }


# ================================================================
# PART 8 — ADAPTIVE STRATEGY UPDATE
# ================================================================

def compute_adaptive_strategy(weekly_report: Dict, history: List[Dict]) -> Dict:
    """
    Generate adaptive strategy updates based on weekly performance.
    
    Returns recommended adjustments to:
      - Mode selection
      - Domain targeting
      - Application volume
      - Alert thresholds
    """
    trend = weekly_report["trend"]
    rate = weekly_report["weekly_stats"]["rate"]
    best_variant = weekly_report["best_variant"]
    
    adjustments = []
    
    # Mode adjustment
    if best_variant and best_variant != "balanced":
        adjustments.append({
            "type": "mode",
            "current": "balanced",
            "recommended": best_variant,
            "reason": f"'{best_variant}' has higher shortlist rate",
        })
    
    # Volume adjustment
    total_apps = len(history)
    shortlisted = len([h for h in history if h.get("status") == "shortlisted"])
    overall_rate = (shortlisted / total_apps * 100) if total_apps > 0 else 0
    
    if overall_rate < 5 and total_apps > 10:
        adjustments.append({
            "type": "volume",
            "current": "high volume",
            "recommended": "reduce to 5-7 quality applications/week",
            "reason": f"Low success rate ({overall_rate:.0f}%) suggests quality > quantity",
        })
    elif overall_rate >= 15:
        adjustments.append({
            "type": "volume",
            "current": "current volume",
            "recommended": "maintain or slightly increase",
            "reason": f"Strong success rate ({overall_rate:.0f}%) — keep going",
        })
    
    # Threshold adjustment
    if trend == "declining":
        adjustments.append({
            "type": "threshold",
            "current": "40% minimum",
            "recommended": "raise to 50% minimum",
            "reason": "Declining trend — be more selective",
        })
    elif trend == "improving" and rate >= 12:
        adjustments.append({
            "type": "threshold",
            "current": "40% minimum",
            "recommended": "can lower to 35% for stretch roles",
            "reason": "Strong upward trend — can afford to experiment",
        })
    
    # Domain focus
    if weekly_report["avoid_list"]:
        adjustments.append({
            "type": "domain",
            "current": "all domains",
            "recommended": f"deprioritize {weekly_report['avoid_list'][0].split(' (')[0]}",
            "reason": "Zero success in this domain",
        })
    
    return {
        "adjustments": adjustments,
        "overall_direction": (
            "EXPAND" if trend == "improving" and rate >= 10
            else "MAINTAIN" if trend == "stable"
            else "TIGHTEN"
        ),
        "confidence": (
            "high" if total_apps >= 20
            else "moderate" if total_apps >= 10
            else "low"
        ),
    }


# ================================================================
# MASTER ORCHESTRATOR — RUN MONITORING CYCLE
# ================================================================

def run_monitoring_cycle(
    raw_jobs: List[Dict],
    resume: StructuredResume,
    history: List[Dict] = None,
) -> Dict:
    """
    Run a complete monitoring cycle.
    
    Steps:
      1. Intake + evaluate all jobs
      2. Filter for alerts (smart thresholds)
      3. Classify alerts (HIGH/MEDIUM/LOW)
      4. Generate daily suggestion
      5. Generate weekly report (if enough data)
      6. Compute adaptive strategy
    
    Returns complete monitoring output.
    """
    history = history or []
    logger.info(f"MONITOR CYCLE — {len(raw_jobs)} jobs, {len(history)} history entries")
    
    # Step 1: Intake + evaluate
    listings = intake_jobs(raw_jobs)
    evaluations = []
    for listing in listings:
        jd = process_jd(listing)
        ev = evaluate_job(listing, jd, resume, history)
        ev = assign_resume_strategy(ev, resume, jd, history)
        evaluations.append(ev)
    
    evaluations = rank_jobs(evaluations)
    
    # Step 2: Smart alert filtering
    alerts = filter_alerts(evaluations, history)
    
    # Step 3: Priority classification
    classified = classify_alerts(alerts)
    
    # Step 4: Daily suggestion
    daily = generate_daily_suggestion(classified)
    
    # Step 5: Weekly report
    weekly = generate_weekly_report(history)
    
    # Step 6: Adaptive strategy
    strategy = compute_adaptive_strategy(weekly, history)
    
    # Save alert log
    _save_alert_log(classified, daily)
    
    logger.info(
        f"  Alerts: {classified['total_alerts']} ({classified['summary']}) | "
        f"Today: {daily['count']} suggestions | "
        f"Weekly trend: {weekly['trend']}"
    )
    
    return {
        "all_evaluations": evaluations,
        "alerts": classified,
        "daily_suggestion": daily,
        "weekly_report": weekly,
        "adaptive_strategy": strategy,
        "summary": {
            "total_jobs": len(raw_jobs),
            "valid_jobs": len(listings),
            "total_alerts": classified["total_alerts"],
            "high_priority": len(classified["high"]),
            "medium_priority": len(classified["medium"]),
            "daily_suggestions": daily["count"],
            "weekly_trend": weekly["trend"],
            "strategy_direction": strategy["overall_direction"],
        },
    }


def _save_alert_log(classified: Dict, daily: Dict):
    """Persist alert log."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    
    logs = []
    if os.path.exists(_ALERT_LOG):
        try:
            with open(_ALERT_LOG, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = []
    
    entry = {
        "date": datetime.now().isoformat(),
        "total_alerts": classified["total_alerts"],
        "high": len(classified["high"]),
        "medium": len(classified["medium"]),
        "low": len(classified["low"]),
        "daily_count": daily["count"],
    }
    logs.append(entry)
    
    with open(_ALERT_LOG, "w", encoding="utf-8") as f:
        json.dump(logs[-100:], f, indent=2)  # keep last 100 entries
