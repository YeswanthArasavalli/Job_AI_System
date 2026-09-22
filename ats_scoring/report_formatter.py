"""
ATS Report Formatter -- rich terminal display for scoring results.
v2.0: Adds confidence level, risk flags, and penalty display.
"""

from utils.models import ATSScoreReport


def format_ats_report(report: ATSScoreReport) -> str:
    """Format an ATSScoreReport into a rich, readable terminal output."""
    lines = []

    lines.append("=" * 60)
    lines.append("📊  ATS SCORING REPORT")
    lines.append("=" * 60)

    if report.job_id:
        lines.append(f"  Job ID: {report.job_id}")

    lines.append(f"  Confidence: {_confidence_badge(report.confidence_level)}")
    lines.append("")

    # --- Score Summary ---
    lines.append("  ┌-----------------------------------------┐")
    lines.append(f"  │  BEFORE Optimization:   {_score_bar(report.score_before)}  {report.score_before:5.1f}/100  │")
    lines.append(f"  │  AFTER  Optimization:   {_score_bar(report.score_after)}  {report.score_after:5.1f}/100  │")
    lines.append(f"  │  Improvement:           {report.improvement:>26s}  │")
    lines.append("  └-----------------------------------------┘")

    # --- ATS Verdict ---
    lines.append("")
    verdict = _get_verdict(report.score_after)
    lines.append(f"  Verdict: {verdict}")

    # --- Decision ---
    lines.append(f"  Decision: {_decision_badge(report.decision)}")
    lines.append(f"  Effort:   {_effort_badge(report.effort_level)}")
    if report.semantic_score > 0:
        lines.append(f"  Semantic: {report.semantic_score:.0f}% responsibility coverage (TF-IDF)")

    # --- Risk Flags ---
    if report.risk_flags:
        lines.append("")
        lines.append("  -- Risk Flags ------------------------------")
        for flag in report.risk_flags:
            lines.append(f"  🚩 {flag}")

    # --- Penalties Applied ---
    if report.penalties_applied:
        lines.append("")
        lines.append("  -- Penalties Applied ------------------------")
        for pen in report.penalties_applied:
            lines.append(f"  ⬇ {pen}")

    # --- Breakdown ---
    lines.append("")
    lines.append("  -- Score Breakdown --------------------------")
    lines.append(f"  {'Category':<25s} {'Before':>8s}  {'After':>8s}  {'Δ':>6s}")
    lines.append(f"  {'-' * 52}")

    b = report.breakdown_before
    a = report.breakdown_after
    _add_breakdown_row(lines, "Keyword Match (30%)", b.keyword_match, a.keyword_match)
    _add_breakdown_row(lines, "Skills Match (25%)", b.skills_match, a.skills_match)
    _add_breakdown_row(lines, "Experience (20%)", b.experience_relevance, a.experience_relevance)
    _add_breakdown_row(lines, "Role Alignment (10%)", b.role_alignment, a.role_alignment)
    _add_breakdown_row(lines, "Education Fit (5%)", b.education_fit, a.education_fit)
    _add_breakdown_row(lines, "Structure (10%)", b.resume_structure, a.resume_structure)

    # --- Keywords ---
    lines.append("")
    lines.append("  -- Keywords --------------------------------")
    if report.matched_keywords:
        lines.append(f"  ✅ Matched ({len(report.matched_keywords)}):")
        for kw in report.matched_keywords:
            lines.append(f"     • {kw}")
    if report.missing_keywords:
        lines.append(f"  ❌ Missing ({len(report.missing_keywords)}):")
        for kw in report.missing_keywords:
            lines.append(f"     • {kw}")

    # --- Skills ---
    lines.append("")
    lines.append("  -- Skills ----------------------------------")
    if report.matched_skills:
        lines.append(f"  ✅ Matched ({len(report.matched_skills)}):")
        for s in report.matched_skills:
            lines.append(f"     • {s}")
    if report.missing_skills:
        lines.append(f"  ❌ Missing ({len(report.missing_skills)}):")
        for s in report.missing_skills:
            lines.append(f"     • {s}")

    # --- Recommendations ---
    if report.recommendations:
        lines.append("")
        lines.append("  -- Recommendations -------------------------")
        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"  {i}. {rec}")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def _score_bar(score: float, width: int = 15) -> str:
    """Generate a visual bar for a score 0-100."""
    filled = int(score / 100 * width)
    empty = width - filled
    if score >= 70:
        char = "█"
    elif score >= 50:
        char = "▓"
    elif score >= 30:
        char = "▒"
    else:
        char = "░"
    return f"[{char * filled}{'·' * empty}]"


def _add_breakdown_row(lines: list, label: str, before: float, after: float):
    delta = after - before
    delta_str = f"+{delta:.0f}" if delta >= 0 else f"{delta:.0f}"
    lines.append(f"  {label:<25s} {before:>7.1f}  {after:>7.1f}  {delta_str:>6s}")


def _get_verdict(score: float) -> str:
    if score >= 80:
        return "🟢 STRONG MATCH -- High chance of passing ATS filters"
    elif score >= 65:
        return "🟡 GOOD MATCH -- Likely to pass most ATS systems"
    elif score >= 50:
        return "🟠 MODERATE -- May pass some ATS filters, improvements needed"
    elif score >= 35:
        return "🔴 WEAK -- Likely filtered out by most ATS systems"
    else:
        return "[!] POOR -- Will almost certainly be auto-rejected"


def _confidence_badge(level: str) -> str:
    badges = {
        "HIGH": "🟢 HIGH -- Rich JD data, score is reliable",
        "MEDIUM": "🟡 MEDIUM -- Adequate JD data, score is reasonably reliable",
        "LOW": "🔴 LOW -- Sparse JD data, score may be inaccurate",
    }
    return badges.get(level, f"⚪ {level}")


def _decision_badge(decision: str) -> str:
    badges = {
        "APPLY": "✅ APPLY -- Strong match, worth applying",
        "MAYBE": "🟡 MAYBE -- Moderate match, consider if interested",
        "SKIP": "❌ SKIP -- Weak match, not recommended",
    }
    return badges.get(decision, f"⚪ {decision}")


def _effort_badge(effort: str) -> str:
    badges = {
        "LOW": "🟢 LOW -- Resume already well-aligned",
        "MEDIUM": "🟡 MEDIUM -- Some customization needed",
        "HIGH": "🔴 HIGH -- Significant rewriting required",
    }
    return badges.get(effort, f"⚪ {effort}")

