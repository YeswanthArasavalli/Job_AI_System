"""
AI Job Intelligence Dashboard -- Streamlit UI v2

Launch: streamlit run dashboard.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from database.db_manager import DatabaseManager
from learning.feedback import FeedbackEngine
from learning.strategy import StrategyEngine
from insights.ranker import JobRanker
from insights.flow import FlowEngine
from utils.config_loader import load_config
from export import Exporter
from manual_mode import ManualAnalyzer


st.set_page_config(
    page_title="Job AI Intelligence",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main { padding-top: 1rem; }
    div[data-testid="stSidebar"] { background: #1e1e2e; }
    div[data-testid="stSidebar"] h1 { color: #cdd6f4; }
    div[data-testid="stSidebar"] .stMarkdown { color: #bac2de; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_db():
    config = load_config()
    return DatabaseManager(config.database.path)


def main():
    db = get_db()
    config = load_config()
    feedback = FeedbackEngine(db)
    strategy = StrategyEngine(feedback, config=config)
    ranker = JobRanker(db)
    flow = FlowEngine(db)

    with st.sidebar:
        st.title("🎯 Job AI System")
        st.markdown("---")
        page = st.radio(
            "Navigate",
            ["📊 Overview", "📋 Job Table", "🏆 Rankings", "🧠 Skill Gaps", "🎯 Strategy", "📅 Today's Plan", "📝 Analyze Resume", "🔍 Job Details"],
            label_visibility="collapsed",
        )
        st.markdown("---")
        stats = db.get_stats()
        st.metric("Total Jobs", stats["total_jobs"])
        st.metric("Avg Score", f"{stats['avg_score_after']}/100")
        st.metric("Avg Improvement", f"+{stats['avg_improvement']}")

        # Ollama health indicator
        st.markdown("---")
        try:
            from utils.ollama_client import check_ollama
            ollama_status = check_ollama()
            if ollama_status["connected"]:
                model_ok = ollama_status["model_available"]
                if model_ok:
                    st.success(f"LLM: {ollama_status['configured_model']}")
                else:
                    st.warning(f"LLM: model not found")
            else:
                st.error("LLM: Ollama offline")
        except Exception:
            st.error("LLM: check failed")

        # Export buttons
        st.markdown("---")
        st.markdown("**📦 Export**")
        exporter = Exporter(db)
        if st.button("📄 Export CSV"):
            path = exporter.export_csv()
            st.success(f"Saved: {path}")
        if st.button("📊 Export PDF Report"):
            path = exporter.export_pdf_summary()
            st.success(f"Saved: {path}")
    if page == "📊 Overview":
        render_overview(db, feedback, stats)
    elif page == "📋 Job Table":
        render_job_table(db)
    elif page == "🏆 Rankings":
        render_rankings(ranker)
    elif page == "🧠 Skill Gaps":
        render_skill_gaps(feedback)
    elif page == "🎯 Strategy":
        render_strategy(strategy)
    elif page == "📅 Today's Plan":
        render_todays_plan(flow)
    elif page == "📝 Analyze Resume":
        render_analyze_resume()
    elif page == "🔍 Job Details":
        render_job_details(db)


# ================================================================
# PAGE: Overview
# ================================================================

def render_overview(db, feedback, stats):
    st.title("📊 Dashboard Overview")

    if stats["total_jobs"] == 0:
        st.info("No jobs processed yet. Run `python main.py` to process your first job.")
        return

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Jobs", stats["total_jobs"])
    col2.metric("Completed", stats["completed"])
    col3.metric("Failed", stats["failed"])
    col4.metric("Avg Score", f"{stats['avg_score_after']}")
    col5.metric("Improvement", f"+{stats['avg_improvement']}")

    st.markdown("---")

    data = feedback.analyze()
    if "error" in data:
        return

    col1, col2, col3 = st.columns(3)

    # Decision breakdown
    with col1:
        st.subheader("Decisions")
        decisions = data["decisions"]
        total = max(sum(decisions.values()), 1)
        for dec in ["APPLY", "MAYBE", "SKIP"]:
            count = decisions.get(dec, 0)
            icon = {"APPLY": "✅", "MAYBE": "🟡", "SKIP": "❌"}[dec]
            pct = count / total * 100
            st.markdown(f"**{icon} {dec}**: {count} ({pct:.0f}%)")
            st.progress(pct / 100)

    # Effort
    with col2:
        st.subheader("Effort Required")
        effort = data["effort_distribution"]
        for level in ["LOW", "MEDIUM", "HIGH"]:
            count = effort.get(level, 0)
            icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}[level]
            st.markdown(f"**{icon} {level}**: {count}")

    # Score trajectory
    with col3:
        st.subheader("Score Performance")
        t = data["score_trajectory"]
        st.metric("Avg Before", t["avg_before"])
        st.metric("Avg After", t["avg_after"], f"+{t['avg_improvement']}")
        st.metric("Consistency", f"σ = {t['score_consistency']}")

    # Score dimension bars
    st.markdown("---")
    st.subheader("Score Dimensions (Averages)")
    dims = data["dimension_averages"]
    if dims:
        cols = st.columns(len(dims))
        for i, (dim, avg) in enumerate(dims.items()):
            label = dim.replace("_", " ").title()
            cols[i].metric(label, f"{avg}")
            cols[i].progress(min(avg / 100, 1.0))


# ================================================================
# PAGE: Job Table (NEW)
# ================================================================

def render_job_table(db):
    st.title("📋 All Jobs")

    jobs = db.list_jobs()
    if not jobs:
        st.info("No jobs processed yet.")
        return

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        decision_filter = st.multiselect(
            "Filter by Decision",
            ["APPLY", "MAYBE", "SKIP", "N/A"],
            default=["APPLY", "MAYBE", "SKIP"],
        )
    with col2:
        status_filter = st.multiselect(
            "Filter by Status",
            ["completed", "failed", "pending"],
            default=["completed"],
        )

    # Build table data
    rows = []
    for j in jobs:
        if j.status.value not in status_filter:
            continue

        r = j.ats_report
        decision = r.decision if r else "N/A"
        if decision not in decision_filter:
            continue

        dec_icon = {"APPLY": "✅", "MAYBE": "🟡", "SKIP": "❌"}.get(decision, "⚪")
        rows.append({
            "Job ID": j.job_id,
            "Title": j.title or "--",
            "Company": j.company or "--",
            "Before": r.score_before if r else 0,
            "After": r.score_after if r else 0,
            "Δ": r.improvement if r else "--",
            "Decision": f"{dec_icon} {decision}",
            "Semantic": f"{r.semantic_score}%" if r else "--",
            "Effort": r.effort_level if r else "--",
            "Confidence": r.confidence_level if r else "--",
        })

    if not rows:
        st.info("No jobs match the selected filters.")
        return

    st.dataframe(rows, use_container_width=True, hide_index=True)

    # Score comparison chart
    st.markdown("---")
    st.subheader("📊 Score Before vs After")

    chart_data = []
    for j in jobs:
        if j.ats_report and j.status.value == "completed":
            chart_data.append({
                "Job": f"{j.title or j.job_id}",
                "Before": j.ats_report.score_before,
                "After": j.ats_report.score_after,
            })

    if chart_data:
        import pandas as pd
        df = pd.DataFrame(chart_data)
        st.bar_chart(df.set_index("Job"), horizontal=False)


# ================================================================
# PAGE: Rankings
# ================================================================

def render_rankings(ranker):
    st.title("🏆 Job Rankings")

    rankings = ranker.rank_jobs()
    if not rankings:
        st.info("No completed jobs to rank yet.")
        return

    decision_filter = st.multiselect(
        "Filter by Decision",
        ["APPLY", "MAYBE", "SKIP"],
        default=["APPLY", "MAYBE", "SKIP"],
    )

    filtered = [r for r in rankings if r["decision"] in decision_filter]

    if not filtered:
        st.info("No jobs match the selected filters.")
        return

    for r in filtered:
        dec_icon = {"APPLY": "✅", "MAYBE": "🟡", "SKIP": "❌"}.get(r["decision"], "⚪")
        eff_icon = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(r["effort"], "⚪")

        with st.expander(
            f"#{r['rank']} {dec_icon} {r['title']} @ {r['company']}  |  "
            f"ATS: {r['ats_score']}  |  Composite: {r['composite']}",
            expanded=(r["rank"] <= 3),
        ):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("ATS Score", f"{r['ats_score']}")
            col2.metric("Semantic", f"{r['semantic_score']}%")
            col3.metric("Composite", r["composite"])
            col4.metric("Effort", f"{eff_icon} {r['effort']}")

            if r["missing_skills"]:
                st.markdown("**Missing Skills:** " + ", ".join(f"`{s}`" for s in r["missing_skills"][:5]))

            st.markdown(f"**Improvement:** {r['improvement']}  |  **Confidence:** {r['confidence']}")


# ================================================================
# PAGE: Skill Gaps
# ================================================================

def render_skill_gaps(feedback):
    st.title("🧠 Skill Gap Analysis")

    data = feedback.analyze()
    if "error" in data:
        st.info(data["error"])
        return

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top Missing Skills")
        for skill, count in data["top_missing_skills"][:10]:
            total = max(data["total_jobs_analyzed"], 1)
            st.markdown(f"[!]️ **{skill}** -- missing in {count}/{total} jobs")
            st.progress(min(count / total, 1.0))

    with col2:
        st.subheader("Top Missing Keywords")
        for kw, count in data["top_missing_keywords"][:10]:
            total = max(data["total_jobs_analyzed"], 1)
            st.markdown(f"🔑 **{kw}** -- missing in {count}/{total} jobs")
            st.progress(min(count / total, 1.0))

    st.markdown("---")

    st.subheader("Weakest Resume Dimensions")
    for dim, avg in data["resume_weakness_trends"]:
        label = dim.replace("_", " ").title()
        color = "🔴" if avg < 50 else "🟡" if avg < 70 else "🟢"
        st.markdown(f"{color} **{label}**: {avg}/100")
        st.progress(avg / 100)

    if data["most_common_penalties"]:
        st.markdown("---")
        st.subheader("Most Common Penalties")
        for penalty, count in data["most_common_penalties"]:
            st.markdown(f"🚩 {penalty} (x{count})")


# ================================================================
# PAGE: Strategy
# ================================================================

def render_strategy(strategy):
    st.title("🎯 Career Strategy Plan")

    plan = strategy.generate()
    if "error" in plan:
        st.info(plan["error"])
        return

    if plan["quick_wins"]:
        st.subheader("⚡ Quick Wins (≤2 weeks)")
        for s in plan["quick_wins"]:
            st.success(f"Learn **{s['skill']}** -> {s['impact']} ({s['effort']}, ROI: {s['roi_score']})")

    st.markdown("---")
    st.subheader("📚 Skills to Learn (by ROI)")
    for i, s in enumerate(plan["skills_to_learn"]):
        col1, col2, col3, col4 = st.columns([3, 3, 2, 1])
        col1.markdown(f"**{i+1}. {s['skill']}**")
        col2.markdown(s["impact"])
        col3.markdown(s["effort"])
        col4.markdown(f"**{s['roi_score']}**")

    if plan["projects_to_add"]:
        st.markdown("---")
        st.subheader("🛠️ Suggested Projects")
        for p in plan["projects_to_add"]:
            with st.expander(f"📁 {p['name']}"):
                st.markdown(f"**Skills:** {p['skills']}")
                st.markdown(f"**Impact:** {p['impact']}")
                st.markdown(f"**How:** {p['description']}")

    if plan["sections_to_fix"]:
        st.markdown("---")
        st.subheader("📝 Resume Sections to Fix")
        for s in plan["sections_to_fix"]:
            icon = "🔴" if s["priority"] == "HIGH" else "🟡"
            st.markdown(f"{icon} **{s['section']}** (avg: {s['current_avg']}/100) -> {s['suggestion']}")

    st.markdown("---")
    st.info(f"📅 **Timeline:** {plan['estimated_timeline']}  |  📊 **Apply Rate:** {plan['apply_rate']}%")


# ================================================================
# PAGE: Job Details
# ================================================================

def render_job_details(db):
    st.title("🔍 Job Details")

    jobs = db.list_jobs()
    if not jobs:
        st.info("No jobs processed yet.")
        return

    job_options = {
        f"{j.title or '?'} @ {j.company or '?'} ({j.job_id})": j.job_id
        for j in jobs
    }

    selected_label = st.selectbox("Select Job", list(job_options.keys()))
    selected_id = job_options[selected_label]
    job = db.get_job(selected_id)

    if not job:
        st.error("Job not found")
        return

    status_icons = {"completed": "✅", "failed": "❌", "pending": "⏳", "processing": "⚙️"}
    st.markdown(f"### {status_icons.get(job.status.value, '?')} {job.title} @ {job.company}")

    if job.ats_report:
        r = job.ats_report

        # Score KPIs
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Before", f"{r.score_before}")
        col2.metric("After", f"{r.score_after}", r.improvement)
        col3.metric("Decision", r.decision)
        col4.metric("Semantic", f"{r.semantic_score}%")
        col5.metric("Effort", r.effort_level)

        # Shortlist Probability
        prob_data = r.shortlist_probability
        if prob_data:
            st.markdown("---")
            prob_val = prob_data.get("shortlist_probability", 0)
            prob_conf = prob_data.get("confidence", "?")
            reasons = prob_data.get("reasons", [])

            pc1, pc2 = st.columns([1, 2])
            with pc1:
                color = "green" if prob_val >= 30 else "orange" if prob_val >= 15 else "red"
                st.metric("Shortlist Probability", f"{prob_val}%", f"Confidence: {prob_conf}")
                st.progress(min(prob_val / 100, 1.0))
            with pc2:
                st.markdown("**Why this probability:**")
                for reason in reasons:
                    if "Strong" in reason or "Good" in reason or "Excellent" in reason:
                        st.success(reason)
                    else:
                        st.warning(reason)

        st.markdown("---")

        # Score breakdown comparison
        st.subheader("Score Breakdown (Before -> After)")
        b_before = r.breakdown_before
        b_after = r.breakdown_after
        dims = ["keyword_match", "skills_match", "experience_relevance", "role_alignment", "education_fit", "resume_structure"]
        cols = st.columns(6)
        for i, dim in enumerate(dims):
            label = dim.replace("_", " ").title()
            before_val = getattr(b_before, dim, 0)
            after_val = getattr(b_after, dim, 0)
            delta = after_val - before_val
            delta_str = f"+{delta:.0f}" if delta >= 0 else f"{delta:.0f}"
            cols[i].metric(label, f"{after_val:.0f}", delta_str)

        st.markdown("---")

        # Skills
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("✅ Matched Skills")
            for s in r.matched_skills:
                st.markdown(f"• {s}")
        with col2:
            st.subheader("❌ Missing Skills")
            for s in r.missing_skills:
                st.markdown(f"• {s}")

        if r.risk_flags:
            st.markdown("---")
            st.subheader("🚩 Risk Flags")
            for flag in r.risk_flags:
                st.warning(flag)

        if r.penalties_applied:
            st.markdown("---")
            st.subheader("Penalties Applied")
            for p in r.penalties_applied:
                st.error(p)

        if r.recommendations:
            st.markdown("---")
            st.subheader("💡 Recommendations")
            for rec in r.recommendations:
                st.info(rec)

    if job.raw_jd:
        with st.expander("📄 Raw Job Description"):
            st.text(job.raw_jd[:3000])


# ================================================================
# Page 7: Today's Plan
# ================================================================

def render_todays_plan(flow):
    st.header("📅 Today's Plan")

    plan = flow.daily_plan()

    # Next best action (highlighted)
    nba = plan.get("next_best_action", "")
    if nba:
        st.success(f"**🎯 Next Best Action:** {nba}")

    st.markdown("---")

    # Action items
    st.subheader("📋 Action Items")
    for i, action in enumerate(plan["today_plan"], 1):
        st.markdown(f"**{i}.** {action}")

    st.markdown("---")

    # Priority jobs
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🟢 Priority Jobs")
        if plan["priority_jobs"]:
            for job in plan["priority_jobs"]:
                prob = job.get('probability', 0)
                color = "green" if prob >= 30 else "orange" if prob >= 15 else "red"
                st.markdown(
                    f"**{job['title']}** @ {job['company']}\n\n"
                    f"Score: {job['score']} | Probability: :{color}[{prob}%] | Effort: {job['effort']}"
                )
                if job.get('missing_skills'):
                    st.caption(f"Missing: {', '.join(job['missing_skills'])}")
                st.markdown("---")
        else:
            st.info("No APPLY jobs yet. Process more JDs!")

    with col2:
        st.subheader("🟡 Maybe Jobs (Low Effort)")
        if plan["maybe_jobs"]:
            for job in plan["maybe_jobs"]:
                st.markdown(
                    f"**{job['title']}** @ {job['company']}\n\n"
                    f"Score: {job['score']} | Effort: {job['effort']}"
                )
                st.markdown("---")
        else:
            st.info("No MAYBE jobs")

    # Stats
    s = plan.get("stats", {})
    if s:
        st.markdown("---")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", s.get("total_jobs", 0))
        c2.metric("APPLY", s.get("apply_count", 0))
        c3.metric("MAYBE", s.get("maybe_count", 0))
        c4.metric("Avg Probability", f"{s.get('avg_probability', 0)}%")


# ================================================================
# Page 8: Analyze Resume (Manual Mode)
# ================================================================

def render_analyze_resume():
    st.header("📝 Analyze Resume vs Job Description")
    st.markdown("Upload your resume and paste a job description to get a full analysis.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📄 Resume")
        resume_source = st.radio(
            "Resume source",
            ["Use master resume", "Upload file (PDF/DOCX/JSON)"],
            horizontal=True,
        )

        uploaded_file = None
        resume_json = None
        if resume_source == "Upload file (PDF/DOCX/JSON)":
            uploaded_file = st.file_uploader(
                "Upload resume", type=["json", "pdf", "docx"],
                help="Supported: PDF, DOCX, JSON"
            )
            if uploaded_file:
                st.success(f"Loaded: {uploaded_file.name} ({uploaded_file.size} bytes)")

    with col2:
        st.subheader("📜 Job Description")
        jd_text = st.text_area(
            "Paste job description here",
            height=300,
            placeholder="Paste the full job description..."
        )

    st.markdown("---")

    opt_col1, opt_col2 = st.columns(2)
    with opt_col1:
        generate_pdf = st.checkbox("Generate PDF resume", value=False)
    with opt_col2:
        mode = st.radio(
            "Optimization Mode",
            ["🎯 Strict (Max ATS Score)", "⚖️ Balanced (Recruiter-Friendly)", "🔒 Conservative (Minimal Changes)"],
            horizontal=True,
            help="Strict: max keyword density for ATS. Balanced: natural phrasing. Conservative: preserve original voice.",
        )
        mode_value = "strict" if "Strict" in mode else "conservative" if "Conservative" in mode else "balanced"

    if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
        if not jd_text or len(jd_text.strip()) < 20:
            st.error("Please paste a job description (at least 20 characters).")
            return

        with st.spinner("Running full pipeline... (this may take 30-60 seconds)"):
            analyzer = ManualAnalyzer()

            # Build kwargs based on source
            kwargs = {"jd_text": jd_text, "generate_pdf": generate_pdf, "mode": mode_value}
            if uploaded_file:
                kwargs["resume_file_bytes"] = uploaded_file.getvalue()
                kwargs["resume_filename"] = uploaded_file.name

            result = analyzer.analyze(**kwargs)

        if result.get("error"):
            st.error(f"Analysis failed: {result['error']}")
            return

        st.success("Analysis complete!")
        st.markdown("---")

        # === Scores ===
        scores = result["scores"]
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Score Before", f"{scores['before']}")
        sc2.metric("Score After", f"{scores['after']}", scores['improvement'])
        sc3.metric("Semantic", f"{scores['semantic']}%")
        sc4.metric("Readability", f"{result.get('readability_score', 0)}/100")

        # === Decision + Probability ===
        st.markdown("---")
        prob = result.get("probability", {})
        dc1, dc2, dc3 = st.columns(3)

        # Use canonical pipeline_result shortlist if available (v6.0)
        # ManualAnalyzer returns result dict — we need to surface pipeline_result canonical values
        # pipeline_result is accessed via result["pipeline_result"] if ManualAnalyzer exposes it
        _pipeline_result = result.get("pipeline_result")
        if _pipeline_result and hasattr(_pipeline_result, "shortlist_probability"):
            _canonical_prob = _pipeline_result.shortlist_probability
            _canonical_decision = _pipeline_result.shortlist_decision
            _canonical_band = _pipeline_result.shortlist_band
        else:
            # Fallback to ats_report shortlist_probability (still unified since v6.0)
            _canonical_prob = prob.get("shortlist_probability", 0)
            _canonical_decision = result.get("decision", "UNKNOWN")
            _canonical_band = prob.get("band", "?")

        dc1.metric("Decision", _canonical_decision)
        dc2.metric("Shortlist Probability", f"{_canonical_prob:.0f}%")
        dc3.metric("Band", _canonical_band)

        # Status
        status = result.get("status", "")
        if status:
            st.caption(f"Resume Status: **{status}** | Effort: **{result.get('effort', '?')}**")
            status_msg = result.get("status_message", "")
            if status_msg:
                if status == "NO_CHANGE":
                    st.info(status_msg)
                else:
                    st.success(status_msg)

        # Probability progress
        prob_val = _canonical_prob
        st.progress(min(prob_val / 100, 1.0))

        # Positive / Negative factors
        fc1, fc2 = st.columns(2)
        with fc1:
            st.markdown("**Positive Factors**")
            for f in prob.get("positive_factors", []):
                st.success(f)
            if not prob.get("positive_factors"):
                st.info("No strong positive signals detected")
        with fc2:
            st.markdown("**Areas to Improve**")
            for f in prob.get("negative_factors", []):
                st.warning(f)
            if not prob.get("negative_factors"):
                st.info("No negative signals")

        # === Next Actions (career assistant) ===
        next_actions = result.get("next_actions", [])
        if next_actions:
            st.markdown("---")
            st.subheader("Next Steps")
            for i, action in enumerate(next_actions, 1):
                st.markdown(f"**{i}.** {action}")

        # === Skills ===
        st.markdown("---")
        sk1, sk2 = st.columns(2)
        with sk1:
            st.subheader("Matched Skills")
            matched = result.get("matched_skills", [])
            if matched:
                st.markdown(", ".join(f"`{s}`" for s in matched))
            else:
                st.info("No matched skills")
        with sk2:
            st.subheader("Missing Skills")
            missing = result.get("missing_skills", [])
            if missing:
                st.markdown(", ".join(f"`{s}`" for s in missing))
            else:
                st.success("No missing skills!")

        # === Recommendations ===
        recs = result.get("recommendations", [])
        if recs:
            st.markdown("---")
            st.subheader("Recommendations")
            for rec in recs:
                st.info(rec)

        # === Risk Flags ===
        flags = result.get("risk_flags", [])
        if flags:
            st.subheader("Risk Flags")
            for flag in flags:
                st.warning(flag)

        # === Role Intelligence (Part 4 - Universal Role Engine) ===
        role_info = result.get("role_info")
        resume_type_info = result.get("resume_type")
        if role_info or resume_type_info:
            st.markdown("---")
            st.subheader("🧠 Intelligence Layer")
            ri1, ri2 = st.columns(2)
            with ri1:
                if role_info:
                    role_label = role_info.get('role_type', 'unknown').title()
                    conf = role_info.get('confidence', 0)
                    tech_icon = "✅" if role_info.get('allow_tech_injection') else "🚫"
                    st.metric("Role Classification", role_label)
                    st.progress(min(conf, 1.0))
                    st.caption(
                        f"Confidence: {conf:.0%} | "
                        f"Tech Injection: {tech_icon} | "
                        f"Bullet Style: {role_info.get('bullet_style', '?')}"
                    )
            with ri2:
                if resume_type_info:
                    rtype = resume_type_info.get('type', 'UNKNOWN')
                    years = resume_type_info.get('years_estimated', 0)
                    rtype_icons = {
                        "EXPERIENCED": "👔", "SWITCHER": "🔄", "FRESHER": "🎓",
                        "GAP": "⏸️", "OVERQUALIFIED": "📊", "ACADEMIC": "🔬"
                    }
                    st.metric("Resume Type", f"{rtype_icons.get(rtype, '📄')} {rtype}")
                    st.caption(f"Est. Experience: {years} years")
                    for hint in resume_type_info.get('strategy_hints', [])[:2]:
                        st.info(hint)

        # === Change Explanation (Part 8 - Trust Layer) ===
        change_exp = result.get("change_explanation")
        if change_exp and change_exp.get("total_changes", 0) > 0:
            st.markdown("---")
            st.subheader("🔍 What Changed & Why")
            st.caption(change_exp.get("summary", ""))

            ce1, ce2, ce3 = st.columns(3)
            ce1.metric("Total Changes", change_exp.get("total_changes", 0))
            ce2.metric("High Confidence", change_exp.get("high_confidence", 0))
            by_section = change_exp.get("by_section", {})
            section_str = ", ".join(f"{k}: {v}" for k, v in by_section.items())
            ce3.metric("Sections Modified", len(by_section))

            with st.expander("View All Changes", expanded=False):
                for change in change_exp.get("changes", [])[:15]:
                    conf_icon = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(
                        change.get("confidence", "LOW"), "⚪"
                    )
                    st.markdown(
                        f"{conf_icon} **{change.get('type', '?')}** "
                        f"({change.get('section', '?')})\n\n"
                        f"> {change.get('reason', '')}"
                    )
                    if change.get("before") and change.get("after"):
                        st.caption(f"Before: {change['before'][:80]}")
                        st.caption(f"After: {change['after'][:80]}")
                    st.markdown("---")

        # === Polish Changes (Part 6) ===
        polish = result.get("polish_changes")
        if polish:
            with st.expander(f"✨ Polish Engine ({len(polish)} refinements)"):
                for pc in polish:
                    st.markdown(
                        f"**{pc.get('type', '?')}**: {pc.get('reason', '')}"  
                    )

        # === Validation Gate (Part 13 - Final Quality Check) ===
        val_result = result.get("validation_result")
        if val_result:
            quality = val_result.get("quality_score", 100)
            passed = val_result.get("passed", True)
            violations = val_result.get("violations", [])
            warnings = val_result.get("warnings", [])

            if not passed:
                st.error(f"⚠️ Validation Gate: FAILED (quality={quality}/100, {len(violations)} violations)")
                for v in violations:
                    st.error(f"❌ [{v['category']}] {v['message']}")
            elif warnings:
                st.warning(f"✅ Validation Gate: PASSED with {len(warnings)} warnings (quality={quality}/100)")
                with st.expander("View Warnings"):
                    for w in warnings:
                        st.warning(f"⚠️ [{w['category']}] {w['message']}")
            else:
                st.success(f"✅ Validation Gate: PASSED (quality={quality}/100)")

        # === Target Score Engine (90+ Roadmap) ===
        target_plan = result.get("target_plan")
        if target_plan and target_plan.get("gap", 0) > 0:
            st.markdown("---")
            st.subheader("Target Score Roadmap (Reach 90+)")

            tp1, tp2, tp3 = st.columns(3)
            tp1.metric("Current Score", f"{target_plan['current_score']}")
            tp2.metric("Projected Score", f"{target_plan['projected_score']}")
            tp3.metric("Gap to 90", f"{target_plan['gap']}", delta=f"+{target_plan.get('total_simulated_gain', 0)} achievable")

            # Why Low
            why_low = target_plan.get("why_low", [])
            if why_low:
                with st.expander("Why is my score low?", expanded=True):
                    for reason in why_low:
                        st.error(reason)

            # Improvement Plan
            plan = target_plan.get("improvement_plan", {})
            high = plan.get("high_impact", [])
            medium = plan.get("medium_impact", [])
            low = plan.get("low_impact", [])

            if high:
                st.markdown("**High Impact Actions:**")
                for action in high:
                    st.success(f"[!] {action}")
            if medium:
                st.markdown("**Medium Impact Actions:**")
                for action in medium:
                    st.info(action)
            if low:
                with st.expander("Low Impact (Polish)"):
                    for action in low:
                        st.caption(f"- {action}")

            # Score Simulations
            sims = target_plan.get("simulations", [])
            if sims:
                with st.expander("Score Simulations (Estimated Impact)"):
                    for sim in sims:
                        st.write(f"+{sim['estimated_points']} pts: {sim['action']}")

        # === Download Improved Resume (Recommended) ===
        st.markdown("---")
        st.subheader("Download Improved Resume (Recommended)")
        st.caption("Optimized version with reordered skills, stronger action verbs, and better keyword alignment.")
        import json as _json
        di1, di2, di3 = st.columns(3)
        with di1:
            imp_text = result.get("improved_resume_text", "")
            if imp_text:
                st.download_button(
                    label="Download TXT",
                    data=imp_text,
                    file_name="improved_resume.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key="dl_imp_txt",
                )
        with di2:
            imp_json = result.get("improved_resume_json", {})
            if imp_json:
                st.download_button(
                    label="Download JSON",
                    data=_json.dumps(imp_json, indent=2),
                    file_name="improved_resume.json",
                    mime="application/json",
                    use_container_width=True,
                    key="dl_imp_json",
                )
        with di3:
            pdf_path = result.get("pdf_path")
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="Download PDF",
                        data=f.read(),
                        file_name="improved_resume.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="dl_imp_pdf",
                    )
            elif pdf_path:
                st.info(f"PDF at: {pdf_path}")

        # === Download Tailored Resume ===
        with st.expander("Download Tailored Resume (Raw Alignment)", expanded=False):
            st.caption("Raw LLM-tailored version before optimization.")
            dt1, dt2 = st.columns(2)
            with dt1:
                tail_text = result.get("tailored_resume_text", "")
                if tail_text:
                    st.download_button(
                        label="Download TXT",
                        data=tail_text,
                        file_name="tailored_resume.txt",
                        mime="text/plain",
                        use_container_width=True,
                        key="dl_tail_txt",
                    )
            with dt2:
                tail_json = result.get("tailored_resume_json", {})
                if tail_json:
                    st.download_button(
                        label="Download JSON",
                        data=_json.dumps(tail_json, indent=2),
                        file_name="tailored_resume.json",
                        mime="application/json",
                        use_container_width=True,
                        key="dl_tail_json",
                    )

        # === Resume Previews ===
        st.markdown("---")
        tab1, tab2 = st.tabs(["Improved Resume (Final)", "Tailored Resume (Raw)"])
        with tab1:
            st.text(result.get("improved_resume_text", "No preview available"))
        with tab2:
            st.text(result.get("tailored_resume_text", "No preview available"))


if __name__ == "__main__":
    main()
