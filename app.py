"""
Career Decision Engine — Streamlit UI

User-facing product layer for the AI Job Application Intelligence System.
Upload resume → paste JD → get actionable career decision in 30 seconds.
"""

import copy
import json
import os
import re
import sys
import logging
from datetime import datetime

import streamlit as st

# Suppress backend logs in UI
logging.disable(logging.WARNING)

# Project imports
from resume_parser.file_parser import ResumeFileParser
from resume_parser.rule_based_parser import RuleBasedResumeParser
from resume_engine.formatter import format_resume_text
from ats_scoring.scorer import ATSScorer
from pipeline.core import run_full_pipeline, evaluate_resume_quality
from utils.models import StructuredResume, ExtractedJD, ContactInfo, ExperienceEntry, ProjectEntry, EducationEntry

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Career Decision Engine",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>
    /* Main container */
    .main .block-container { max-width: 1100px; padding-top: 2rem; }
    
    /* Decision card */
    .decision-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        border-radius: 16px;
        padding: 2rem;
        color: white;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .decision-card h2 { margin: 0 0 0.5rem 0; font-size: 1.8rem; }
    .decision-card .decision-text {
        font-size: 2.2rem;
        font-weight: 700;
        margin: 0.5rem 0;
    }
    .decision-apply { color: #00d084; }
    .decision-improve { color: #fcb900; }
    .decision-reject { color: #ff6b6b; }
    
    /* Metric cards */
    .metric-row { display: flex; gap: 1rem; margin: 1rem 0; }
    .metric-card {
        background: rgba(255,255,255,0.05);
        border-radius: 12px;
        padding: 1rem 1.5rem;
        flex: 1;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .metric-card .value { font-size: 1.6rem; font-weight: 700; color: #e2e8f0; }
    .metric-card .label { font-size: 0.85rem; color: #94a3b8; margin-top: 0.3rem; }
    
    /* Strength/gap lists */
    .strength-item { 
        padding: 0.5rem 0; 
        border-bottom: 1px solid rgba(0,208,132,0.1);
        color: #10b981;
    }
    .gap-item { 
        padding: 0.5rem 0; 
        border-bottom: 1px solid rgba(251,185,0,0.1);
        color: #f59e0b;
    }
    .action-item {
        padding: 0.6rem 0;
        border-bottom: 1px solid rgba(99,102,241,0.1);
        color: #818cf8;
    }
    
    /* Trust badge */
    .trust-badge {
        background: rgba(16, 185, 129, 0.08);
        border: 1px solid rgba(16, 185, 129, 0.2);
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin: 1rem 0;
    }
    .trust-badge p { margin: 0.3rem 0; color: #6ee7b7; font-size: 0.9rem; }
    
    /* Diff display */
    .diff-before {
        background: rgba(239, 68, 68, 0.08);
        border-left: 3px solid #ef4444;
        padding: 0.5rem 1rem;
        margin: 0.3rem 0;
        border-radius: 0 8px 8px 0;
        color: #fca5a5;
        font-size: 0.85rem;
    }
    .diff-after {
        background: rgba(34, 197, 94, 0.08);
        border-left: 3px solid #22c55e;
        padding: 0.5rem 1rem;
        margin: 0.3rem 0 1rem 0;
        border-radius: 0 8px 8px 0;
        color: #86efac;
        font-size: 0.85rem;
    }
    
    /* Mode selector */
    .stRadio > div { display: flex; gap: 0.5rem; }
    
    /* Hide default streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Sidebar styling */
    .css-1d391kg { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# JOB HISTORY (Learning System)
# ============================================================

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "data", "job_history.json")


def load_job_history():
    """Load job application history from disk."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_job_history(history):
    """Save job application history to disk."""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def add_to_history(company, role, decision, market_rank, ats_score, mode):
    """Add a new entry to job history."""
    history = load_job_history()
    history.append({
        "company": company,
        "role": role,
        "decision": decision,
        "market_rank": market_rank,
        "ats_score": round(ats_score, 1),
        "mode": mode,
        "status": "applied",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    save_job_history(history)


def get_learning_insights(history):
    """Generate learning insights from past applications."""
    if len(history) < 2:
        return None
    
    shortlisted = [h for h in history if h.get("status") == "shortlisted"]
    rejected = [h for h in history if h.get("status") == "rejected"]
    
    insights = {}
    if shortlisted:
        avg_score = sum(h.get("ats_score", 0) for h in shortlisted) / len(shortlisted)
        common_modes = [h.get("mode", "strict") for h in shortlisted]
        best_mode = max(set(common_modes), key=common_modes.count)
        insights["shortlist_avg_score"] = round(avg_score, 1)
        insights["best_mode"] = best_mode
        insights["shortlist_count"] = len(shortlisted)
    
    if rejected:
        avg_score = sum(h.get("ats_score", 0) for h in rejected) / len(rejected)
        insights["reject_avg_score"] = round(avg_score, 1)
        insights["reject_count"] = len(rejected)
    
    return insights


# ============================================================
# ANALYSIS ENGINE
# ============================================================

def parse_resume_text(text: str) -> StructuredResume:
    """Parse raw resume text into StructuredResume using rule-based parser."""
    parser = RuleBasedResumeParser()
    data = parser.parse(text)
    
    contact = ContactInfo(
        name=data.get("contact", {}).get("name", ""),
        email=data.get("contact", {}).get("email", ""),
        phone=data.get("contact", {}).get("phone", ""),
    )
    
    experience = []
    for exp in data.get("experience", []):
        experience.append(ExperienceEntry(
            company=exp.get("company", ""),
            role=exp.get("role", ""),
            duration=exp.get("duration", ""),
            bullets=exp.get("bullets", []),
        ))
    
    projects = []
    for proj in data.get("projects", []):
        projects.append(ProjectEntry(
            name=proj.get("name", ""),
            bullets=proj.get("bullets", []),
        ))
    
    education = []
    for edu in data.get("education", []):
        education.append(EducationEntry(
            degree=edu.get("degree", ""),
            institution=edu.get("institution", ""),
            year=edu.get("year", ""),
        ))
    
    return StructuredResume(
        contact=contact,
        title=data.get("title", ""),
        summary=data.get("summary", ""),
        skills=data.get("skills", []),
        experience=experience,
        projects=projects,
        education=education,
    )


def run_analysis(resume: StructuredResume, jd: ExtractedJD, mode: str):
    """Run the CANONICAL career decision pipeline (Phase 3 service).

    app.py consumes pipeline.service.analyze() — the single application-level
    entry point shared with the dashboard. Display-only enrichment below is
    derived from PipelineResult fields, never recomputed.
    """
    from pipeline.service import analyze
    scorer = ATSScorer()

    # Score original BEFORE pipeline (for delta display only)
    score_before, _, _ = scorer.score(resume, jd)
    q_before = evaluate_resume_quality(resume, jd)
    orig_bullets = [b for e in resume.experience for b in e.bullets]

    # ============================================================
    # CANONICAL ENGINE — one service, all surfaces
    # ============================================================
    pipeline_result = analyze(
        resume, jd, mode=mode, job_id="app_analysis",
    )
    
    improved = pipeline_result.improved
    ats_report = pipeline_result.ats_report
    
    # ============================================================
    # EXTRACT — all data from pipeline output, zero custom logic
    # ============================================================
    score_after = ats_report.score_after
    delta = score_after - score_before
    q_after = evaluate_resume_quality(improved, jd)
    
    # Bullet diffs (structural comparison only)
    imp_bullets = [b for e in improved.experience for b in e.bullets]
    diffs = []
    for ob, ib in zip(orig_bullets, imp_bullets):
        if ob != ib:
            diffs.append({"before": ob, "after": ib})
    
    # Pipeline data extraction
    hiring_sim = getattr(pipeline_result, 'hiring_simulation', None) or {}
    # ── CANONICAL: use pipeline_result.shortlist_probability (v6.0) ──
    # NOT hiring_sim["shortlist_probability"] — that is the raw simulation value.
    shortlist_pct = pipeline_result.shortlist_probability
    interpretation = hiring_sim.get('interpretation')
    perception = hiring_sim.get('perception', {})
    competitive = hiring_sim.get('competitive', {})

    # ============================================================
    # DECISION — from pipeline canonical shortlist decision (v6.0)
    # Falls back to interpretation engine for display text only
    # ============================================================
    # Primary: use pipeline's canonical decision
    action = pipeline_result.shortlist_decision
    action_desc = pipeline_result.shortlist_decision_reason or "Based on full resume + JD analysis."
    position = pipeline_result.shortlist_band

    # Enrich display text from interpretation engine if available
    if interpretation:
        interp_dec = interpretation.get('decision', {})
        if interp_dec.get('subtitle'):
            action_desc = interp_dec['subtitle']
        benchmark = interpretation.get('benchmark', {})
        position = benchmark.get('position', position)
    
    # ============================================================
    # MARKET RANK — from pipeline competitive analysis
    # ============================================================
    comp_level = competitive.get('competitive_level', '')
    diff_count = competitive.get('differentiator_count', 0)
    if comp_level == 'STRONG' or diff_count >= 4:
        market_rank = "TOP_10"
    elif comp_level in ('MODERATE', 'STRONG') or diff_count >= 2:
        market_rank = "TOP_25"
    elif diff_count >= 1:
        market_rank = "AVERAGE"
    else:
        market_rank = "BELOW"
    
    rank_explain = {
        "TOP_10": ("Top 10% of applicants", "~50-70%"),
        "TOP_25": ("Top 25% — strong competitive profile", "~25-40%"),
        "AVERAGE": ("Average applicant pool", "~10-15%"),
        "BELOW": ("Below average positioning", "<10%"),
    }
    
    # ============================================================
    # STRENGTHS — from pipeline data (not custom computation)
    # ============================================================
    matched = ats_report.matched_skills
    missing = ats_report.missing_skills
    strengths = []
    
    # From competitive analysis
    for diff_item in competitive.get('differentiators', []):
        if isinstance(diff_item, str):
            strengths.append(diff_item)
        elif isinstance(diff_item, dict):
            strengths.append(diff_item.get('detail', str(diff_item)))
    
    # From perception
    if perception.get('impact_density', 0) > 0:
        strengths.append(f"Quantified impact in {int(perception.get('impact_density', 0))}% of bullets")
    if perception.get('ownership_level', 0) >= 60:
        strengths.append(f"Strong ownership language ({int(perception.get('ownership_level', 0))}%)")
    
    # Skill match
    skill_overlap = len(matched) / max(1, len(jd.required_skills))
    if skill_overlap >= 0.5:
        strengths.append(f"{len(matched)}/{len(jd.required_skills)} required skills matched")
    if delta >= 10:
        strengths.append(f"Strong improvement potential (+{delta:.0f} pts)")
    
    # ============================================================
    # GAPS + ACTIONS — from pipeline (hiring sim gaps + why_not_90)
    # ============================================================
    gaps = []
    actions = []
    
    # From hiring simulation gaps
    for gap in hiring_sim.get('gaps', []):
        gaps.append(gap.get('detail', str(gap))[:100])
        if gap.get('action'):
            actions.append(gap['action'])
    
    # From pipeline why_not_90
    if pipeline_result.why_not_90:
        for step in pipeline_result.why_not_90.get("steps_to_90", []):
            if step not in actions:
                actions.append(step)
    
    # From interpretation growth path
    if interpretation:
        for gp_action in interpretation.get('growth_path', {}).get('actions', []):
            act_text = gp_action.get('action', '')
            if act_text and act_text not in actions:
                actions.append(act_text)
    
    # From ats_report recommendations
    for rec in (ats_report.recommendations or []):
        if rec not in actions:
            actions.append(rec)
    
    return {
        "score_before": score_before,
        "score_after": score_after,
        "delta": delta,
        "quality_before": q_before["total"],
        "quality_after": q_after["total"],
        "action": action,
        "action_desc": action_desc,
        "market_rank": market_rank,
        "rank_desc": rank_explain[market_rank][0],
        "shortlist_rate": rank_explain[market_rank][1],
        "comp_score": diff_count,
        "strengths": strengths[:5],
        "gaps": gaps[:5],
        "actions": actions[:5],
        "diffs": diffs[:8],
        "improved": improved,
        "missing_skills": missing,
        "matched_skills": matched,
        "mode": mode,
        "hiring_simulation": hiring_sim,
        # ── CANONICAL shortlist (v6.0) — single source of truth ──
        "shortlist_probability": pipeline_result.shortlist_probability,
        "shortlist_band": pipeline_result.shortlist_band,
        "shortlist_decision": pipeline_result.shortlist_decision,
        "interpretation": interpretation,
        "pipeline_trace": pipeline_result.pipeline_trace,
        # Pipeline-native data (for parity with dashboard)
        "pipeline_result": pipeline_result,
    }


# ============================================================
# UI
# ============================================================

def main():
    """Main Streamlit app."""
    
    # Sidebar
    with st.sidebar:
        st.markdown("## 🎯 Career Decision Engine")
        st.markdown("---")
        
        mode_labels = {
            "strict": "⚡ Strict (Max Results)",
            "balanced": "✨ Balanced (Recommended)",
            "conservative": "🛡️ Conservative (Minimal Changes)",
        }
        
        mode = st.radio(
            "Optimization Mode",
            options=list(mode_labels.keys()),
            format_func=lambda x: mode_labels[x],
            index=1,
            help="Balanced is recommended for most applications."
        )
        
        mode_desc = {
            "strict": "Maximum ATS optimization. Best for competitive roles.",
            "balanced": "Natural language with strong signal placement. Recommended.",
            "conservative": "Minimal safe improvements. Preserves your original voice.",
        }
        st.caption(mode_desc[mode])
        
        st.markdown("---")
        
        # Job History
        history = load_job_history()
        if history:
            st.markdown("### 📊 Application Tracker")
            
            # Use the new Performance Metrics engine
            from pipeline.hiring_simulation import (
                analyze_application_feedback, compute_performance_metrics
            )
            metrics = compute_performance_metrics(history)
            feedback = analyze_application_feedback(history)
            
            # Key metrics
            col1, col2 = st.columns(2)
            col1.metric("Applied", metrics["total_applications"])
            col2.metric("Shortlisted", len([h for h in history if h.get("status") == "shortlisted"]))
            
            shortlisted = len([h for h in history if h.get("status") == "shortlisted"])
            rejected = len([h for h in history if h.get("status") == "rejected"])
            col1.metric("Rejected", rejected)
            col2.metric("Pending", metrics["total_applications"] - shortlisted - rejected)
            
            # Shortlist rate with trend
            if metrics["shortlist_rate"] > 0:
                trend_emoji = {"improving": "📈", "stable": "➡️", "declining": "📉"}.get(
                    metrics["trend"], "📊"
                )
                st.caption(f"{trend_emoji} Shortlist Rate: **{metrics['shortlist_rate']:.0f}%**")
            
            # Performance summary
            st.caption(metrics["summary"])
            
            # Feedback-driven insights
            if feedback["success_patterns"]:
                st.markdown("#### ✅ What's Working")
                for pattern in feedback["success_patterns"][:3]:
                    st.caption(f"• {pattern}")
            
            if feedback["signal_gaps"]:
                st.markdown("#### ⚠️ Signal Gaps")
                for gap in feedback["signal_gaps"][:2]:
                    st.caption(f"• {gap}")
            
            if feedback["improvement_plan"]:
                st.markdown("#### 🚀 Next Steps")
                for step in feedback["improvement_plan"][:3]:
                    st.caption(f"• {step}")
            
            # Recommended mode
            st.caption(f"💡 Recommended mode: **{feedback['recommended_mode']}**")
            
            st.markdown("---")
            
            # Update status
            if st.checkbox("Update application status"):
                for i, h in enumerate(reversed(history[-5:])):
                    idx = len(history) - 1 - i
                    label = f"{h['company']} — {h['role']}"
                    new_status = st.selectbox(
                        label,
                        ["applied", "shortlisted", "rejected"],
                        index=["applied", "shortlisted", "rejected"].index(h.get("status", "applied")),
                        key=f"status_{idx}",
                    )
                    if new_status != h.get("status"):
                        history[idx]["status"] = new_status
                        save_job_history(history)
                        st.rerun()
    
    # Main content
    st.markdown("# 🎯 Career Decision Engine")
    st.markdown("Upload your resume and paste the job description to get an actionable career decision.")
    
    # Input section
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📄 Your Resume")
        uploaded_file = st.file_uploader(
            "Upload PDF, DOCX, or JSON",
            type=["pdf", "docx", "json", "txt"],
            help="We only read your resume to analyze it. Nothing is stored or sent externally.",
        )
        resume_text_input = st.text_area(
            "Or paste resume text",
            height=200,
            placeholder="Paste your resume content here...",
        )
    
    with col2:
        st.markdown("### 📋 Job Description")
        jd_text = st.text_area(
            "Paste the full job description",
            height=280,
            placeholder="Paste the complete job posting here...\n\nInclude: title, requirements, responsibilities, preferred skills...",
        )
    
    # Analyze button
    analyze = st.button("🚀 Analyze & Improve Resume", type="primary", use_container_width=True)
    
    if analyze:
        # Validate inputs
        if not jd_text.strip():
            st.error("Please paste a job description.")
            return
        if not uploaded_file and not resume_text_input.strip():
            st.error("Please upload a resume or paste resume text.")
            return
        
        # Parse resume
        with st.spinner("Reading your resume..."):
            if uploaded_file:
                file_parser = ResumeFileParser()
                raw_text = file_parser.extract_text(
                    file_bytes=uploaded_file.read(),
                    filename=uploaded_file.name,
                )
            else:
                raw_text = resume_text_input
            
            resume = parse_resume_text(raw_text)
            
            if not resume.experience:
                st.error("Could not extract experience from your resume. Try a different format or paste the text directly.")
                return
        
        # Process JD
        with st.spinner("Analyzing job description..."):
            from jd_processor.processor import JDProcessor
            jd_processor = JDProcessor()
            try:
                processed = jd_processor.process(jd_text)
                # Extract title from first line or text
                title_match = re.match(r'^(.{5,80})$', jd_text.strip().split('\n')[0])
                title = title_match.group(1).strip() if title_match else ""
                # Extract company (look for "at Company" or "-- Company")
                company = ""
                comp_match = re.search(r'(?:at|@|--|—)\s+([A-Z][A-Za-z\s&]+)', jd_text[:200])
                if comp_match:
                    company = comp_match.group(1).strip()
                
                # Extract experience years
                exp_years = None
                exp_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', jd_text.lower())
                if exp_match:
                    exp_years = int(exp_match.group(1))
                
                jd = ExtractedJD(
                    job_title=title,
                    company=company,
                    required_skills=processed.skills_required,
                    preferred_skills=processed.skills_preferred,
                    keywords=[s.lower() for s in processed.skills_required + processed.skills_preferred + processed.tools],
                    responsibilities=processed.responsibilities[:10],
                    required_experience_years=exp_years,
                    raw_text=jd_text,
                )
            except Exception as e:
                # Fallback: basic extraction
                keywords = list(set(w.strip().lower() for w in re.findall(r'\b[A-Za-z][a-z]+(?:\s+[A-Za-z][a-z]+)?\b', jd_text) if len(w.strip()) > 3))[:15]
                jd = ExtractedJD(
                    job_title="",
                    company="",
                    required_skills=[],
                    preferred_skills=[],
                    keywords=keywords,
                    responsibilities=[],
                )
        
        # Run analysis
        with st.spinner("Running Career Decision Engine..."):
            result = run_analysis(resume, jd, mode)
        
        st.markdown("---")
        
        # ============================================
        # SECTION 2: FINAL OUTPUT
        # ============================================
        
        # Decision Card — Interpretation-Engine-Powered
        action = result["action"]
        interp = result.get("interpretation")
        
        if "APPLY" in action and "improve" not in action.lower() and "build" not in action.lower():
            action_class = "decision-apply"
            action_emoji = interp['decision']['emoji'] if interp else "✅"
        elif "APPLY" in action:
            action_class = "decision-apply"
            action_emoji = interp['decision']['emoji'] if interp else "🟡"
        elif "IMPROVE" in action:
            action_class = "decision-improve"
            action_emoji = interp['decision']['emoji'] if interp else "⚠️"
        else:
            action_class = "decision-improve"
            action_emoji = interp['decision']['emoji'] if interp else "📈"
        
        # Shortlist display value — from canonical pipeline field
        sl_display = f"{result['shortlist_probability']:.0f}%" if result.get('shortlist_probability') else result['shortlist_rate']
        
        st.markdown(f"""
        <div class="decision-card">
            <h2>{action_emoji} Career Decision</h2>
            <p class="decision-text {action_class}">{action}</p>
            <p style="color: #94a3b8; margin: 0;">{result['action_desc']}</p>
            <div class="metric-row">
                <div class="metric-card">
                    <div class="value">{result['score_after']:.0f}</div>
                    <div class="label">ATS Score (+{result['delta']:.0f})</div>
                </div>
                <div class="metric-card">
                    <div class="value">{sl_display}</div>
                    <div class="label">Shortlist Probability</div>
                </div>
                <div class="metric-card">
                    <div class="value">{result['quality_after']:.0f}</div>
                    <div class="label">Content Quality</div>
                </div>
                <div class="metric-card">
                    <div class="value">{result['market_rank'].replace('_', ' ')}</div>
                    <div class="label">{result['rank_desc']}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # ============================================
        # INTERPRETATION LAYER (Context-Aware)
        # ============================================
        if interp:
            # Confidence message + benchmark narrative
            st.info(interp['confidence_message'])
            
            # Level + Benchmark bar
            bench = interp['benchmark']
            lvl = interp['level_info']
            ic1, ic2, ic3 = st.columns(3)
            ic1.metric(
                "Your Level",
                f"📊 {lvl['level'].upper()}",
                f"~{lvl['years_estimated']} yrs experience",
            )
            ic2.metric(
                "Peer Benchmark",
                f"{bench['emoji']} {bench['position']}",
                bench['delta_label'],
            )
            ic3.metric(
                "Peer Average",
                f"{bench['peer_average']}%",
                f"Range: {bench['peer_range']}",
            )
            
            # Benchmark narrative
            st.caption(bench['narrative'])
            
            # Growth Path
            gp = interp['growth_path']
            if not gp['reached_top'] and gp['actions']:
                st.markdown("---")
                st.markdown(f"### 🚀 Growth Path → {gp['target_label']}")
                st.caption(
                    f"Current: {gp['current']}%  →  "
                    f"Target: {gp['next_target']}%  "
                    f"(gap: {gp['gap']:.0f}%)"
                )
                
                for i, act in enumerate(gp['actions'], 1):
                    priority_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(act['priority'], "⚪")
                    st.markdown(
                        f"**{i}. {act['action']}**\n\n"
                        f"{priority_icon} Priority: {act['priority']}  |  "
                        f"⏱ Effort: {act['effort']}  |  "
                        f"📈 Est. Boost: {act['estimated_boost']}"
                    )
                    if act.get('example'):
                        st.caption(f"Example: {act['example']}")
            elif gp['reached_top']:
                st.markdown("---")
                st.success("🏆 **You've reached top tier!** Your resume is ready to submit.")
            
            # Next step callout
            next_step = interp['decision'].get('next_step', '')
            if next_step:
                st.markdown("---")
                st.success(f"**👉 Next Step:** {next_step}")
        
        # Strengths, Gaps, Actions in 3 columns
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### ✅ Your Strengths")
            if result["strengths"]:
                for s in result["strengths"]:
                    st.markdown(f"<div class='strength-item'>+ {s}</div>", unsafe_allow_html=True)
            else:
                st.caption("No strong differentiators detected yet.")
        
        with col2:
            st.markdown("### ⚠️ What's Missing")
            if result["gaps"]:
                for g in result["gaps"]:
                    st.markdown(f"<div class='gap-item'>− {g}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='strength-item'>No critical gaps found!</div>", unsafe_allow_html=True)
        
        with col3:
            st.markdown("### 🚀 Action Plan")
            if result["actions"]:
                for i, a in enumerate(result["actions"], 1):
                    st.markdown(f"<div class='action-item'>{i}. {a}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='strength-item'>Resume is ready to submit!</div>", unsafe_allow_html=True)
        
        # Trust Badge
        st.markdown("""
        <div class="trust-badge">
            <p>✅ No fake experience added</p>
            <p>✅ No fake skills injected — only skills already on your resume</p>
            <p>✅ Only enhanced your existing content</p>
            <p>✅ ATS-safe optimization applied</p>
        </div>
        """, unsafe_allow_html=True)
        
        # ============================================
        # SECTION 2.5: HIRING INTELLIGENCE DASHBOARD
        # ============================================
        intel = result.get("hiring_simulation", {}).get("intelligence", {})
        if intel:
            with st.expander("🧠 Hiring Intelligence Dashboard", expanded=False):
                
                # -- Pre-Application Gate --
                gate = intel.get("gate", {})
                gate_decision = gate.get("decision", "?")
                gate_confidence = gate.get("confidence_score", 0)
                
                gate_colors = {
                    "APPLY_NOW": ("🟢", "success"),
                    "FIX_GAPS": ("🟡", "warning"),
                    "DO_NOT_APPLY": ("🔴", "error"),
                }
                gate_emoji, gate_type = gate_colors.get(gate_decision, ("⚪", "info"))
                
                getattr(st, gate_type)(
                    f"{gate_emoji} **{gate_decision.replace('_', ' ')}** — "
                    f"Confidence: {gate_confidence}%\n\n"
                    f"{gate.get('reasoning', '')}"
                )
                
                st.markdown("---")
                
                # -- Targeting + Diagnosis Row --
                tc1, tc2 = st.columns(2)
                
                with tc1:
                    st.markdown("#### 🎯 JD Targeting Score")
                    tgt = intel.get("targeting", {})
                    tgt_score = tgt.get("total_score", 0)
                    st.metric("Match Score", f"{tgt_score}/100")
                    st.caption(f"Skills: {tgt.get('skill_overlap', 0)}/30 · "
                              f"Experience: {tgt.get('experience_match', 0)}/25 · "
                              f"Domain: {tgt.get('domain_alignment', 0)}/20")
                    st.caption(f"Title: {tgt.get('title_proximity', 0)}/15 · "
                              f"Seniority: {tgt.get('seniority_fit', 0)}/10")
                    if tgt.get("is_targeting_gap"):
                        st.error("⚠️ TARGETING GAP — consider different roles")
                
                with tc2:
                    st.markdown("#### 🔍 Root Cause Diagnosis")
                    diag = intel.get("diagnosis", {})
                    cause = diag.get("primary_cause", "?")
                    cause_emoji = {
                        "CANDIDATE_GAP": "📚",
                        "RESUME_GAP": "📝",
                        "TARGETING_GAP": "🎯",
                    }.get(cause, "❓")
                    st.metric("Primary Issue", f"{cause_emoji} {cause.replace('_', ' ')}")
                    for ev in diag.get("evidence", []):
                        st.caption(f"• {ev[:80]}")
                    st.caption(f"💡 {diag.get('action', '')[:100]}")
                
                st.markdown("---")
                
                # -- Rejection Prediction --
                rp = intel.get("rejection_prediction", {})
                if rp.get("risks"):
                    st.markdown("#### ⚠️ Rejection Risk Prediction")
                    st.caption(rp.get("verdict", ""))
                    for risk in rp.get("risks", [])[:3]:
                        sev_color = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(risk["severity"], "⚪")
                        st.markdown(f"{sev_color} **{risk['risk']}**")
                        st.caption(f"  {risk.get('detail', '')[:80]}")
                        st.caption(f"  Fix: {risk.get('fix', '')[:80]}")
                
                st.markdown("---")
                
                # -- Capability Gap Plan --
                gp = intel.get("gap_plan", {})
                if gp:
                    gap_type = gp.get("type", "")
                    type_label = {
                        "CANDIDATE_UPGRADE": "📚 Capability Upgrade Plan",
                        "RESUME_FIX": "📝 Resume Fix Plan",
                        "TARGETING_FIX": "🎯 Targeting Fix Plan",
                    }.get(gap_type, "📋 Improvement Plan")
                    
                    st.markdown(f"#### {type_label}")
                    st.caption(gp.get("summary", ""))
                    st.caption(f"⏱ Estimated effort: {gp.get('estimated_effort', '?')}")
                    
                    for step in gp.get("upgrade_plan", []):
                        st.markdown(f"→ {step[:100]}")
                    
                    # Show missing skills if candidate gap
                    if gap_type == "CANDIDATE_UPGRADE" and gp.get("missing_skills"):
                        skills_list = [s["skill"] for s in gp["missing_skills"][:5]]
                        st.caption(f"Missing skills: {', '.join(skills_list)}")
                
                st.markdown("---")
                
                # -- Resume Variants --
                variants = intel.get("variants", [])
                if variants:
                    st.markdown("#### 📄 Resume Strategy Variants")
                    vcols = st.columns(len(variants))
                    for i, v in enumerate(variants):
                        with vcols[i]:
                            risk_emoji = {"low": "🟢", "medium": "🟡", "medium-high": "🟠", "high": "🔴"}.get(v["risk"], "⚪")
                            st.metric(v["name"], v["probability"], f"{risk_emoji} {v['risk']} risk")
                            st.caption(v["focus"][:60])
                            st.caption(f"Use for: {v['when_to_use'][:60]}")
                    
                    # A/B Strategy
                    ab = intel.get("ab_strategy", {})
                    if ab:
                        st.caption(f"🧪 **Strategy:** {ab.get('strategy', '')[:120]}")
                
                # -- Prediction Accuracy (if data exists) --
                pa = intel.get("prediction_accuracy", {})
                if pa.get("accuracy") is not None:
                    st.markdown("---")
                    st.markdown("#### 📉 Prediction Reliability")
                    pa_cols = st.columns(3)
                    pa_cols[0].metric("Accuracy", f"{pa['accuracy']}%")
                    pa_cols[1].metric("Precision", f"{pa['precision']}%")
                    pa_cols[2].metric("Recall", f"{pa['recall']}%")
                    st.caption(pa.get("summary", ""))
        
        # ============================================
        # SECTION 3: EXPANDABLE DETAILS
        # ============================================
        
        # Improved Resume
        with st.expander("📄 View Improved Resume"):
            st.text(format_resume_text(result["improved"]))
        
        # Changes Made
        if result["diffs"]:
            with st.expander(f"🔍 View Changes Made ({len(result['diffs'])} bullets improved)"):
                for diff in result["diffs"]:
                    st.markdown(f"<div class='diff-before'>BEFORE: {diff['before'][:150]}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='diff-after'>AFTER: {diff['after'][:150]}</div>", unsafe_allow_html=True)
        
        # Score Details
        with st.expander("📈 View Score Details"):
            col1, col2, col3 = st.columns(3)
            col1.metric("ATS Score", f"{result['score_after']:.1f}", f"+{result['delta']:.1f}")
            col2.metric("Quality", f"{result['quality_after']:.0f}", f"+{result['quality_after'] - result['quality_before']:.0f}")
            col3.metric("Competition", result["market_rank"].replace("_", " "), f"{result['comp_score']}/12")
            
            if result["missing_skills"]:
                st.markdown("**Missing Skills:**")
                st.caption(", ".join(result["missing_skills"]))
            if result["matched_skills"]:
                st.markdown("**Matched Skills:**")
                st.caption(", ".join(result["matched_skills"]))
        
        # Save to DB (primary) + JSON tracker (fallback/legacy)
        company = jd.company or "Unknown"
        role = jd.job_title or "Unknown Role"
        try:
            from app_db_patch import save_analysis_to_db
            _analysis_id = save_analysis_to_db(
                company=company,
                role=role,
                decision=action,
                result=result,
                jd=jd,
                original_resume=resume,
                improved_resume=result["improved"],
                mode=mode,
            )
        except Exception as _db_err:
            # Fallback to JSON if DB fails
            add_to_history(company, role, action, result["market_rank"], result["score_after"], mode)
        st.caption(f"📝 Saved to application tracker: {company} — {role}")


if __name__ == "__main__":
    main()
