"""
Daily Pipeline — Batch Job Processing + Intelligent Ranking.

Streamlit page for running the Daily Job Pipeline.
Users paste multiple job listings, and the system evaluates,
ranks, and generates a daily application plan.
"""

import json
import streamlit as st
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.models import StructuredResume, ContactInfo, ExperienceEntry, EducationEntry, ProjectEntry
from pipeline.job_pipeline import run_daily_pipeline

st.set_page_config(page_title="Daily Pipeline", page_icon="📅", layout="wide")


def load_job_history():
    """Load application history."""
    hist_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "job_history.json")
    if os.path.exists(hist_path):
        try:
            with open(hist_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def main():
    st.markdown("# 📅 Daily Application Pipeline")
    st.markdown("Paste multiple job listings → Get a ranked, intelligent daily application plan.")
    
    # ============================================
    # INPUT SECTION
    # ============================================
    
    col_input, col_resume = st.columns([2, 1])
    
    with col_input:
        st.markdown("### 📋 Job Listings")
        
        # Sample format
        with st.expander("📋 See JSON format example"):
            st.code('''[
  {
    "company": "Google",
    "role": "Data Scientist",
    "job_description": "Full JD text here...",
    "apply_link": "https://careers.google.com/123",
    "salary": "$150,000"
  },
  {
    "company": "Amazon",
    "role": "ML Engineer",
    "job_description": "Full JD text here...",
    "apply_link": "https://amazon.jobs/456"
  }
]''', language="json")
        
        jobs_json = st.text_area(
            "Paste job listings (JSON array)",
            height=350,
            placeholder='[{"company": "...", "role": "...", "job_description": "..."}]',
        )
    
    with col_resume:
        st.markdown("### 📄 Your Resume")
        
        resume_json = st.file_uploader(
            "Upload resume JSON",
            type=["json"],
            help="Upload the structured resume JSON file.",
        )
        
        # Max applications slider
        max_apps = st.slider("Max applications/day", 3, 15, 8)
        
        st.markdown("---")
        st.markdown("### ⚙️ Pipeline Settings")
        st.caption("• Evaluates each job through the Intelligence Engine")
        st.caption("• Computes targeting score, diagnosis, and gate decision")
        st.caption("• Ranks by composite score (probability + match + confidence)")
        st.caption("• Selects optimal resume variant per job")
    
    # ============================================
    # RUN PIPELINE
    # ============================================
    
    if st.button("🚀 Run Daily Pipeline", type="primary", use_container_width=True):
        # Validate inputs
        if not jobs_json.strip():
            st.error("Please paste job listings in JSON format.")
            return
        
        try:
            raw_jobs = json.loads(jobs_json)
            if not isinstance(raw_jobs, list):
                st.error("Job listings must be a JSON array [].")
                return
            if len(raw_jobs) == 0:
                st.error("No jobs found in the input.")
                return
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")
            return
        
        # Parse resume
        resume = None
        if resume_json:
            try:
                resume_data = json.load(resume_json)
                resume = StructuredResume(**resume_data)
            except Exception as e:
                st.error(f"Could not parse resume JSON: {e}")
                return
        
        if not resume:
            st.error("Please upload your resume JSON file.")
            return
        
        # Run pipeline
        history = load_job_history()
        
        with st.spinner(f"🧠 Processing {len(raw_jobs)} jobs through Intelligence Engine..."):
            result = run_daily_pipeline(raw_jobs, resume, history, max_apps)
        
        # ============================================
        # RESULTS
        # ============================================
        summary = result["summary"]
        plan = result["plan"]
        
        st.markdown("---")
        
        # Summary row
        st.markdown("## 📊 Pipeline Results")
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("📥 Input", summary["total_input"])
        mc2.metric("✅ Valid", summary["total_valid"])
        mc3.metric("🟢 Apply Now", summary["apply_now"])
        mc4.metric("🟡 Fix Gaps", summary["fix_gaps"])
        mc5.metric("⏭️ Skip", summary["skip"])
        
        st.caption(
            f"🎯 Best variant: **{summary['best_variant']}** | "
            f"Focus: **{summary['focus_issue'].replace('_', ' ')}** | "
            f"📅 Today: **{summary['today_applications']}** applications"
        )
        
        st.markdown("---")
        
        # ============================================
        # TODAY'S PLAN
        # ============================================
        if plan["plan"]:
            st.markdown("## 📅 Today's Application Plan")
            
            for i, job in enumerate(plan["plan"], 1):
                emoji = job["decision_emoji"]
                decision_label = job["decision"].replace("_", " ")
                
                # Card styling
                if job["decision"] == "APPLY_NOW":
                    border = "#22c55e"
                    bg = "rgba(34, 197, 94, 0.08)"
                else:
                    border = "#f59e0b"
                    bg = "rgba(245, 158, 11, 0.08)"
                
                st.markdown(f"""
                <div style="
                    border-left: 4px solid {border};
                    background: {bg};
                    border-radius: 8px;
                    padding: 16px 20px;
                    margin: 12px 0;
                ">
                    <h3 style="margin: 0 0 8px 0;">{emoji} {i}. {job['company']} — {job['role']}</h3>
                    <p style="margin: 4px 0;">
                        <strong>{decision_label}</strong> &nbsp;|&nbsp;
                        📊 Prob: <strong>{job['shortlist_probability']}%</strong> &nbsp;|&nbsp;
                        🎯 Match: <strong>{job['jd_match_score']}/100</strong> &nbsp;|&nbsp;
                        📄 Variant: <strong>{job.get('variant_name', '?')}</strong>
                    </p>
                    <p style="margin: 4px 0; opacity: 0.8;">
                        🧠 Root Cause: {job['root_cause'].replace('_', ' ')} &nbsp;|&nbsp;
                        ⚠️ Risk: {job['top_risk']}
                    </p>
                    {f'<p style="margin: 4px 0;">💰 {job["salary"]}</p>' if job.get('salary') else ''}
                </div>
                """, unsafe_allow_html=True)
                
                # Action row
                action_cols = st.columns([2, 2, 1])
                with action_cols[0]:
                    if job.get("apply_link"):
                        st.link_button(f"🔗 Apply at {job['company']}", job['apply_link'])
                    else:
                        st.caption("No apply link provided")
                with action_cols[1]:
                    if job.get("matched_skills"):
                        st.caption(f"✅ {', '.join(job['matched_skills'][:5])}")
                with action_cols[2]:
                    if job.get("missing_skills"):
                        st.caption(f"❌ {', '.join(job['missing_skills'][:3])}")
        else:
            st.warning(
                "⚠️ No jobs passed the quality gate today. "
                "Try different roles or improve your resume first."
            )
        
        # ============================================
        # SKIPPED JOBS
        # ============================================
        skipped = [e for e in result["all_evaluations"] if e["decision"] == "SKIP"]
        if skipped:
            st.markdown("---")
            with st.expander(f"⏭️ Skipped Jobs ({len(skipped)}) — below 40% probability"):
                for job in skipped:
                    st.markdown(
                        f"⏭️ **{job['company']}** — {job['role']} | "
                        f"Prob: {job['shortlist_probability']}% | "
                        f"Match: {job['jd_match_score']}/100 | "
                        f"Cause: {job['root_cause'].replace('_', ' ')}"
                    )
                    if job.get("top_risk_fix"):
                        st.caption(f"  → {job['top_risk_fix'][:100]}")
        
        # ============================================
        # FULL RANKING TABLE
        # ============================================
        st.markdown("---")
        with st.expander("📊 Full Job Ranking (all evaluated jobs)"):
            for ev in result["all_evaluations"]:
                emoji = ev["decision_emoji"]
                st.markdown(
                    f"**#{ev['rank']}** {emoji} **{ev['company']}** — {ev['role']} | "
                    f"Score: **{ev['job_score']}** | "
                    f"Prob: {ev['shortlist_probability']}% | "
                    f"Match: {ev['jd_match_score']}/100 | "
                    f"Decision: {ev['decision'].replace('_', ' ')}"
                )
        
        # Trust badge
        st.markdown("""
        <div style="
            background: rgba(34, 197, 94, 0.05);
            border: 1px solid rgba(34, 197, 94, 0.2);
            border-radius: 8px;
            padding: 12px;
            margin-top: 16px;
            text-align: center;
        ">
            <p>✅ No auto-apply — all applications require manual action via links</p>
            <p>✅ No resume generated for skipped jobs — saves your time</p>
            <p>✅ Predictions based on real skill matching, not inflated scores</p>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
else:
    main()
