"""
Weekly Insights — Weekly Performance + Adaptive Strategy.

Streamlit page showing weekly optimization insights,
adaptive strategy recommendations, and trend analysis.
"""

import json
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.job_monitor import generate_weekly_report, compute_adaptive_strategy

st.set_page_config(page_title="Weekly Insights", page_icon="📊", layout="wide")


def load_job_history():
    hist_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "job_history.json")
    if os.path.exists(hist_path):
        try:
            with open(hist_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def main():
    st.markdown("# 📊 Weekly Performance & Strategy")
    st.markdown("Track your hiring progress and get adaptive strategy recommendations.")
    
    history = load_job_history()
    
    if not history:
        st.info("No application history yet. Start using the Career Decision Engine to build data.")
        return
    
    # Generate weekly report
    weekly = generate_weekly_report(history)
    strategy = compute_adaptive_strategy(weekly, history)
    
    # ============================================
    # WEEKLY STATS
    # ============================================
    st.markdown("## 📅 This Week's Performance")
    
    stats = weekly["weekly_stats"]
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Applications", stats["applications"])
    mc2.metric("Shortlisted", stats["shortlisted"])
    mc3.metric("Rejected", stats["rejected"])
    mc4.metric(
        "Shortlist Rate",
        f"{stats['rate']}%",
        f"{stats['rate'] - stats['prev_week_rate']:+.0f}% vs last week"
        if stats["prev_week_rate"] > 0 else None,
    )
    
    # Trend
    trend_emoji = weekly["trend_emoji"]
    trend_label = weekly["trend"].replace("_", " ").title()
    
    if weekly["trend"] == "improving":
        st.success(f"{trend_emoji} **Trend: {trend_label}** — Your strategy is working!")
    elif weekly["trend"] == "declining":
        st.error(f"{trend_emoji} **Trend: {trend_label}** — Time to adjust strategy")
    elif weekly["trend"] == "stable":
        st.info(f"{trend_emoji} **Trend: {trend_label}** — Consistent performance")
    else:
        st.info(f"{trend_emoji} **Not enough data yet** — Keep applying to build insights")
    
    st.caption(weekly["summary"])
    
    st.markdown("---")
    
    # ============================================
    # WHAT WORKS / WHAT FAILS
    # ============================================
    col_works, col_fails = st.columns(2)
    
    with col_works:
        st.markdown("### 🔥 What's Working")
        if weekly["what_works"]:
            for item in weekly["what_works"]:
                st.markdown(f"✅ {item}")
        else:
            st.caption("Need more shortlist data to identify patterns.")
        
        if weekly["best_domains"]:
            st.markdown("**Best Domains:**")
            for domain in weekly["best_domains"]:
                st.markdown(f"🎯 {domain}")
    
    with col_fails:
        st.markdown("### ⚠️ What's Not Working")
        if weekly["what_fails"]:
            for item in weekly["what_fails"]:
                st.markdown(f"❌ {item}")
        else:
            st.caption("No clear failure patterns yet.")
        
        if weekly["avoid_list"]:
            st.markdown("**Avoid These:**")
            for item in weekly["avoid_list"]:
                st.markdown(f"🚫 {item}")
    
    st.markdown("---")
    
    # ============================================
    # VARIANT PERFORMANCE
    # ============================================
    st.markdown("### 📄 Resume Variant Performance")
    
    vp = weekly.get("variant_performance", {})
    per_variant = vp.get("per_variant", {})
    
    if per_variant:
        vcols = st.columns(len(per_variant))
        for i, (mode, data) in enumerate(per_variant.items()):
            with vcols[i]:
                rate_display = f"{data['rate']}%" if data['resolved'] > 0 else "No data"
                st.metric(
                    mode.title(),
                    rate_display,
                    f"{data['applications']} apps, {data['shortlists']} shortlists",
                )
        
        if vp.get("recommendation"):
            st.caption(f"💡 {vp['recommendation']}")
    else:
        st.caption("No variant data yet.")
    
    st.markdown("---")
    
    # ============================================
    # ADAPTIVE STRATEGY
    # ============================================
    st.markdown("### 🧠 Adaptive Strategy Recommendations")
    
    direction = strategy["overall_direction"]
    direction_emoji = {"EXPAND": "🚀", "MAINTAIN": "➡️", "TIGHTEN": "🔒"}.get(direction, "📊")
    
    st.markdown(f"**Overall Direction: {direction_emoji} {direction}** (confidence: {strategy['confidence']})")
    
    if strategy["adjustments"]:
        for adj in strategy["adjustments"]:
            st.markdown(f"""
            <div style="
                border-left: 3px solid #3b82f6;
                padding: 8px 16px;
                margin: 8px 0;
                background: rgba(59, 130, 246, 0.05);
                border-radius: 4px;
            ">
                <strong>{adj['type'].title()}</strong>: 
                {adj['current']} → <strong>{adj['recommended']}</strong><br/>
                <small>{adj['reason']}</small>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("No adjustments needed — current strategy is performing well.")
    
    st.markdown("---")
    
    # ============================================
    # NEXT WEEK PLAN
    # ============================================
    st.markdown("### 🚀 Next Week's Plan")
    
    for i, step in enumerate(weekly["next_week_plan"], 1):
        st.markdown(f"**{i}.** {step}")


if __name__ == "__main__":
    main()
else:
    main()
