"""
Reality Check — Prediction Validation + Discipline + Self-Correction.

Streamlit page showing system verification, prediction accuracy,
and mandatory action enforcement.
"""

import json
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.reality_validation import run_reality_validation, check_data_thresholds

st.set_page_config(page_title="Reality Check", page_icon="🔍", layout="wide")


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
    st.markdown("# 🔍 Reality Check — System Verification")
    st.markdown("Are predictions matching reality? Is the system actually helping?")
    
    history = load_job_history()
    
    if not history:
        st.info("No application history yet. Start using the system to build verification data.")
        return
    
    # Optional: user progress input
    with st.sidebar:
        st.markdown("### 📈 Your Progress")
        skills_input = st.text_input(
            "New skills learned",
            placeholder="Docker, Spark, AWS",
            help="Comma-separated list of skills you've learned recently",
        )
        projects_input = st.text_input(
            "Projects completed",
            placeholder="ML Pipeline, Dashboard App",
        )
        
        user_progress = {}
        if skills_input:
            user_progress["skills_learned"] = [s.strip() for s in skills_input.split(",")]
        if projects_input:
            user_progress["projects_completed"] = [p.strip() for p in projects_input.split(",")]
    
    # Run validation
    result = run_reality_validation(history, user_progress)
    
    # ============================================
    # SYSTEM HEALTH BANNER
    # ============================================
    health = result["system_health"]
    health_config = {
        "HEALTHY": ("success", "🟢 System Healthy — Predictions align with reality"),
        "NEEDS_ATTENTION": ("warning", "🟡 Needs Attention — Minor prediction drift detected"),
        "CRITICAL": ("error", "🔴 Critical — Significant prediction mismatch"),
        "BUILDING_DATA": ("info", "📊 Building Data — Collecting outcomes to validate predictions"),
    }
    
    alert_type, alert_msg = health_config.get(health, ("info", "📊 Status Unknown"))
    getattr(st, alert_type)(alert_msg)
    
    # ============================================
    # DATA THRESHOLDS
    # ============================================
    thresholds = result["data_thresholds"]
    
    st.markdown("### 🔒 Insight Gates")
    gc1, gc2, gc3 = st.columns(3)
    for col, (gate_name, gate) in zip(
        [gc1, gc2, gc3],
        thresholds["gates"].items()
    ):
        with col:
            st.markdown(gate["message"])
            if not gate["unlocked"]:
                progress = gate["current"] / gate["required"]
                st.progress(min(progress, 1.0))
    
    st.markdown("---")
    
    # ============================================
    # PREDICTION ACCURACY
    # ============================================
    st.markdown("### 📊 Prediction Accuracy")
    
    pa = result["prediction_accuracy"]
    if pa.get("accuracy") is not None:
        pa_cols = st.columns(4)
        pa_cols[0].metric("Accuracy", f"{pa['accuracy']}%")
        pa_cols[1].metric("Precision", f"{pa['precision']}%")
        pa_cols[2].metric("Recall", f"{pa['recall']}%")
        pa_cols[3].metric("Resolved", f"{pa['total_resolved']} apps")
        
        # Conversion rates
        cr1, cr2 = st.columns(2)
        cr1.metric("HIGH → Shortlisted", f"{pa['high_conversion_rate']}%", f"of {pa['high_total']} HIGH predictions")
        cr2.metric("LOW → Rejected", f"{pa['low_rejection_rate']}%", f"of {pa['low_total']} LOW predictions")
        
        # Mismatch cases
        if pa.get("mismatch_cases"):
            with st.expander(f"⚠️ Mismatch Cases ({len(pa['mismatch_cases'])})"):
                for case in pa["mismatch_cases"]:
                    icon = "📈" if case["type"] == "under_prediction" else "📉"
                    st.markdown(
                        f"{icon} **{case['company']}** — {case['role']} | "
                        f"Predicted: {case['predicted']} | Actual: {case['actual']}"
                    )
                    st.caption(f"  {case['insight']}")
    else:
        st.caption(pa["message"])
    
    st.markdown("---")
    
    # ============================================
    # REALITY ALIGNMENT
    # ============================================
    ra = result["reality_alignment"]
    
    st.markdown("### 📈 Reality Alignment")
    
    align_emoji = {"aligned": "✅", "minor_drift": "🟡", "misaligned": "🔴"}.get(
        ra["alignment"], "📊"
    )
    st.markdown(f"{align_emoji} **{ra['alignment'].replace('_', ' ').title()}** — {ra['summary']}")
    
    if ra.get("issues"):
        for issue in ra["issues"]:
            sev_color = {"HIGH": "🔴", "MEDIUM": "🟡"}.get(issue["severity"], "⚪")
            st.markdown(f"{sev_color} **{issue['type'].replace('_', ' ').title()}**: {issue['detail']}")
    
    if ra.get("corrections"):
        for corr in ra["corrections"]:
            st.caption(f"🔧 {corr['action']} — {corr['reason']}")
    
    st.markdown("---")
    
    # ============================================
    # ROOT CAUSE (VALIDATED)
    # ============================================
    rc = result["root_cause_validated"]
    
    st.markdown("### 🧠 Root Cause (Outcome-Validated)")
    
    cause = rc["validated_cause"]
    cause_emoji = {
        "CANDIDATE_GAP": "📚", "RESUME_GAP": "📝", "TARGETING_GAP": "🎯"
    }.get(cause, "❓")
    
    st.metric("Validated Root Cause", f"{cause_emoji} {cause.replace('_', ' ')}", f"Confidence: {rc['confidence']}%")
    
    for ev in rc.get("evidence", []):
        st.caption(f"• {ev}")
    
    st.markdown("---")
    
    # ============================================
    # CAPABILITY PROGRESS
    # ============================================
    cap = result["capability_progress"]
    
    st.markdown("### 📈 Capability Progress")
    
    if cap["improving"] is True:
        st.success(cap["message"])
    elif cap["improving"] is False:
        st.warning(cap["message"])
    else:
        st.info(cap["message"])
    
    if cap.get("score_trend") and cap["score_trend"]["delta"] != 0:
        tc1, tc2 = st.columns(2)
        tc1.metric(
            "ATS Score Trend",
            f"{cap['score_trend']['second_half']}",
            f"{cap['score_trend']['delta']:+.1f} vs earlier",
        )
        if cap.get("rate_trend"):
            tc2.metric(
                "Shortlist Rate Trend",
                f"{cap['rate_trend']['second_half']}%",
                f"{cap['rate_trend']['delta']:+.1f}% vs earlier",
            )
    
    if cap.get("evidence"):
        for ev in cap["evidence"]:
            st.caption(f"• {ev}")
    
    st.markdown("---")
    
    # ============================================
    # MANDATORY ACTIONS
    # ============================================
    ma = result["mandatory_actions"]
    
    if ma["actions"]:
        st.markdown("### 🔥 Mandatory Actions")
        
        if ma["has_critical"]:
            st.error("⚠️ **Critical actions require immediate attention**")
        
        for action in ma["actions"]:
            priority_emoji = {
                "CRITICAL": "🚨", "HIGH": "🔴", "MEDIUM": "🟡"
            }.get(action["priority"], "⚪")
            
            type_emoji = {
                "STOP": "🚫", "BUILD": "🔨", "USE": "📄",
                "RECALIBRATE": "🔧", "TRACK": "📊",
            }.get(action["type"], "➡️")
            
            st.markdown(f"""
            <div style="
                border-left: 3px solid {'#ef4444' if action['priority'] == 'CRITICAL' else '#f59e0b' if action['priority'] == 'HIGH' else '#3b82f6'};
                padding: 8px 16px;
                margin: 8px 0;
                background: rgba(0,0,0,0.02);
                border-radius: 4px;
            ">
                {priority_emoji} {type_emoji} <strong>{action['action']}</strong><br/>
                <small style="opacity: 0.7;">{action['reason']}</small>
            </div>
            """, unsafe_allow_html=True)
    
    # ============================================
    # SELF-CORRECTIONS
    # ============================================
    sc = result["self_corrections"]
    
    if sc.get("needs_correction"):
        st.markdown("---")
        st.markdown("### ⚙️ System Self-Corrections")
        st.caption("These adjustments will be applied automatically to improve predictions.")
        
        for corr in sc["corrections"]:
            st.markdown(
                f"🔧 **{corr['parameter']}**: {corr['current']} → **{corr['recommended']}**"
            )
            st.caption(f"  {corr['reason']}")


if __name__ == "__main__":
    main()
else:
    main()
