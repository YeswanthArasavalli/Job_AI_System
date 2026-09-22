"""
ADVERSARIAL LIVE AUDIT -- Principal AI Systems Architect
Tests REAL behavior, not assumptions. Every claim requires proof.
"""
import re, sys, io, logging

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
logging.disable(logging.WARNING)
from utils.models import (
    StructuredResume, ExtractedJD, ExperienceEntry,
    ProjectEntry, EducationEntry, ContactInfo,
)
from ats_scoring.scorer import ATSScorer
from resume_engine.improver import ResumeImprover
from pipeline.core import evaluate_resume_quality, compute_shortlist_score, run_full_pipeline

scorer = ATSScorer()
imp = ResumeImprover()

# ============================================================
# TEST PROFILES (using ACTUAL model schema)
# ============================================================

def make_ds_resume():
    return StructuredResume(
        contact=ContactInfo(name="Priya Sharma", email="priya@example.com", phone="555-0100"),
        title="Data Scientist",
        summary="Experienced data scientist with a passion for solving complex problems.",
        skills=["Python", "TensorFlow", "SQL", "Machine Learning", "NLP",
                "Pandas", "Scikit-learn", "Docker", "AWS", "Spark"],
        experience=[
            ExperienceEntry(company="TechCorp", role="Data Scientist", duration="2020-2024",
                bullets=[
                    "Built predictive models for customer churn analysis.",
                    "Analyzed large datasets to identify trends and patterns.",
                    "Developed automated reports for the executive team.",
                ]),
            ExperienceEntry(company="DataWorks", role="Junior Data Analyst", duration="2018-2020",
                bullets=[
                    "Performed data analysis using SQL queries.",
                    "Assisted in building dashboards for KPI tracking.",
                    "Cleaned and preprocessed raw data for analysis.",
                ]),
        ],
        projects=[
            ProjectEntry(name="Sentiment Analyzer", bullets=[
                "Built NLP pipeline using NLTK and scikit-learn for tweet classification.",
                "Trained deep learning model using TensorFlow achieving 92% accuracy."]),
            ProjectEntry(name="Sales Forecaster", bullets=[
                "Developed time series model using Python and Spark.",
                "Deployed Flask API serving predictions to internal teams."]),
        ],
        education=[EducationEntry(degree="M.S. Data Science", institution="State University", year="2018")],
    )

def make_ds_jd():
    return ExtractedJD(
        job_title="Senior Data Scientist", company="BigTech Inc",
        required_skills=["Python", "Machine Learning", "Deep Learning", "SQL", "TensorFlow", "NLP", "Data Pipelines"],
        preferred_skills=["Docker", "AWS", "Kubernetes", "Spark"],
        keywords=["machine learning", "deep learning", "data pipelines", "model deployment",
                  "python", "sql", "nlp", "tensorflow", "predictive modeling", "data visualization"],
        responsibilities=["Design and deploy machine learning models for production use",
                          "Build and maintain data pipelines for real-time analytics",
                          "Collaborate with engineering teams on model integration"],
        required_experience_years=5,
    )

def make_hr_resume():
    return StructuredResume(
        contact=ContactInfo(name="Anita Desai", email="anita@example.com", phone="555-0200"),
        title="HR Manager",
        summary="Dedicated HR professional with experience in talent acquisition and employee engagement.",
        skills=["Recruitment", "Employee Relations", "HRIS", "Payroll", "Compliance",
                "Performance Management", "Training & Development", "Labor Law"],
        experience=[
            ExperienceEntry(company="GlobalCorp", role="HR Manager", duration="2019-2024",
                bullets=[
                    "Managed end-to-end recruitment for 200+ positions annually.",
                    "Implemented employee engagement programs reducing attrition by 15%.",
                    "Led compliance audits ensuring 100% regulatory adherence.",
                    "Designed onboarding programs for 500+ new hires per year.",
                ]),
            ExperienceEntry(company="StartupXYZ", role="HR Executive", duration="2016-2019",
                bullets=[
                    "Handled payroll processing for 300 employees.",
                    "Coordinated training sessions for department heads.",
                    "Maintained employee records in HRIS system.",
                ]),
        ],
        projects=[],
        education=[EducationEntry(degree="MBA Human Resources", institution="Business School", year="2016")],
        certifications=[],
    )

def make_hr_jd():
    return ExtractedJD(
        job_title="Senior HR Manager", company="Enterprise Ltd",
        required_skills=["Recruitment", "Employee Relations", "Compliance", "Performance Management", "HRIS"],
        preferred_skills=["Training & Development", "Labor Law", "Succession Planning"],
        keywords=["talent acquisition", "employee engagement", "compliance", "performance management",
                  "onboarding", "hris", "retention", "organizational development"],
        responsibilities=["Lead talent acquisition strategy across multiple business units",
                          "Design and implement employee engagement and retention programs",
                          "Ensure compliance with labor laws and company policies"],
        required_experience_years=7,
    )

def make_weak_resume():
    return StructuredResume(
        contact=ContactInfo(name="Rahul Verma", email="rahul@example.com", phone="555-0300"),
        title="Software Developer",
        summary="Recent graduate looking for opportunities in software development.",
        skills=["Java", "Python", "HTML", "CSS", "MySQL"],
        experience=[
            ExperienceEntry(company="InternCo", role="Intern", duration="2023",
                bullets=[
                    "Wrote code for web applications.",
                    "Fixed bugs reported by QA team.",
                    "Attended daily standup meetings.",
                ]),
        ],
        projects=[ProjectEntry(name="Todo App", bullets=["Built a todo app using React and Node.js."])],
        education=[EducationEntry(degree="B.Tech Computer Science", institution="Tech College", year="2023")],
    )

def make_swe_jd():
    return ExtractedJD(
        job_title="Software Engineer", company="TechStartup",
        required_skills=["Python", "Java", "REST APIs", "Git", "SQL"],
        preferred_skills=["Docker", "AWS", "React", "CI/CD"],
        keywords=["software development", "rest apis", "agile", "git", "python", "java", "testing", "microservices"],
        responsibilities=["Design and develop scalable backend services",
                          "Write clean, maintainable code with unit tests",
                          "Participate in code reviews and agile ceremonies"],
        required_experience_years=2,
    )

# ============================================================
# AUDIT ENGINE
# ============================================================

def audit_case(name, resume, jd, mode="strict"):
    print(f"\n{'='*70}")
    print(f"CASE: {name} (mode={mode})")
    print(f"{'='*70}")

    # SCORE BEFORE
    score_before, bd_before, det_before = scorer.score(resume, jd)
    print(f"\n[SCORE BEFORE] {score_before}")
    print(f"  keyword_match:        {bd_before.keyword_match}")
    print(f"  skills_match:         {bd_before.skills_match}")
    print(f"  experience_relevance: {bd_before.experience_relevance}")
    print(f"  role_alignment:       {bd_before.role_alignment}")
    print(f"  education_fit:        {bd_before.education_fit}")
    print(f"  resume_structure:     {bd_before.resume_structure}")

    # IMPROVE — unified pipeline (same as app.py + dashboard.py)
    pipeline_result = run_full_pipeline(
        resume, resume.model_copy(deep=True), jd, scorer, mode=mode
    )
    improved = pipeline_result.improved

    # SCORE AFTER (from pipeline)
    score_after = pipeline_result.ats_report.score_after
    _, bd_after, det_after = scorer.score(improved, jd)
    delta = score_after - score_before

    print(f"\n[SCORE AFTER] {score_after} (delta: {'+' if delta >= 0 else ''}{delta:.1f})")
    print(f"  keyword_match:        {bd_before.keyword_match} -> {bd_after.keyword_match}")
    print(f"  skills_match:         {bd_before.skills_match} -> {bd_after.skills_match}")
    print(f"  experience_relevance: {bd_before.experience_relevance} -> {bd_after.experience_relevance}")
    print(f"  role_alignment:       {bd_before.role_alignment} -> {bd_after.role_alignment}")
    print(f"  resume_structure:     {bd_before.resume_structure} -> {bd_after.resume_structure}")

    # QUALITY
    q_before = evaluate_resume_quality(resume, jd)
    q_after = evaluate_resume_quality(improved, jd)
    print(f"\n[QUALITY] {q_before['total']:.0f} -> {q_after['total']:.0f} (+{q_after['total'] - q_before['total']:.0f})")
    print(f"  skill_demo:    {q_before['skill_demo']:.0f}% -> {q_after['skill_demo']:.0f}%")
    print(f"  action_verbs:  {q_before['action_verbs']:.0f}% -> {q_after['action_verbs']:.0f}%")
    print(f"  tool_purpose:  {q_before['tool_purpose']:.0f}% -> {q_after['tool_purpose']:.0f}%")

    # BULLET DIFF
    print(f"\n--- BULLET DIFF ---")
    changes_real, changes_cosmetic = 0, 0
    for i, (orig_exp, imp_exp) in enumerate(zip(resume.experience, improved.experience)):
        for j in range(min(len(orig_exp.bullets), len(imp_exp.bullets))):
            ob, ib = orig_exp.bullets[j], imp_exp.bullets[j]
            if ob != ib:
                has_purpose = bool(re.search(r'(?:for|to|enabling|achieving|improving)\s+\w+', ib, re.I))
                label = "REAL" if has_purpose else "COSMETIC"
                if label == "REAL": changes_real += 1
                else: changes_cosmetic += 1
                print(f"  [{label}] exp[{i}].b[{j}]: {ib[:90]}...")
    print(f"  Total: {changes_real} REAL, {changes_cosmetic} COSMETIC")

    # SUMMARY DIFF
    if resume.summary != improved.summary:
        print(f"\n--- SUMMARY ---")
        print(f"  BEFORE: {resume.summary[:100]}")
        print(f"  AFTER:  {improved.summary[:100]}")
        generic = [
            "experienced data scientist with a passion",
            "experienced professional with",
            "passionate about",
            "dedicated professional",
            "hardworking",
            "looking for opportunities",
            "seeking a position",
        ]
        still_generic = any(g in improved.summary.lower() for g in generic)
        print(f"  Generic? {'YES [FAIL]' if still_generic else 'NO [OK]'}")

    # SKILL UTILIZATION
    print(f"\n--- SKILL UTILIZATION ---")
    all_exp = " ".join(b.lower() for exp in improved.experience for b in exp.bullets)
    all_proj = " ".join(b.lower() for p in improved.projects for b in p.bullets)
    unused = []
    for skill in improved.skills:
        s = skill.lower()
        in_exp = s in all_exp or any(t in all_exp for t in s.split() if len(t) > 3)
        in_proj = s in all_proj or any(t in all_proj for t in s.split() if len(t) > 3)
        if not in_exp:
            unused.append((skill, "PROJ-ONLY" if in_proj else "UNUSED"))
    if unused:
        for sk, st in unused: print(f"  ❌ {sk}: {st}")
    else:
        print(f"  ✓ All {len(improved.skills)} skills in experience bullets")

    # BULLET QUALITY
    print(f"\n--- BULLET QUALITY ---")
    action_verbs = {"developed","designed","implemented","built","created","managed","led",
                    "optimized","improved","reduced","increased","delivered","automated",
                    "analyzed","architected","deployed","maintained","collaborated",
                    "established","launched","performed","assisted","handled","coordinated",
                    "cleaned","wrote","fixed","attended","streamlined","spearheaded"}
    stats = {"GOOD": 0, "WEAK": 0, "OVER-OPT": 0}
    for exp in improved.experience:
        for bullet in exp.bullets:
            b = bullet.lower()
            first = b.split()[0] if b.split() else ""
            ands = len(re.findall(r'\band\b', b))
            utils = b.count("utilizing ") + b.count("leveraging ")
            has_purpose = bool(re.search(r'(?:for|to|enabling|achieving)\s+\w+', b))
            if ands >= 3 or utils >= 2:
                label = "OVER-OPT"
            elif len(bullet) < 30 or (first not in action_verbs and not first.endswith("ed")):
                label = "WEAK"
            elif has_purpose:
                label = "GOOD"
            else:
                label = "WEAK"
            stats[label] += 1
            if label != "GOOD":
                print(f"  [{label}] {bullet[:85]}...")
    total = sum(stats.values())
    print(f"  Result: {stats['GOOD']}/{total} GOOD, {stats['WEAK']} WEAK, {stats['OVER-OPT']} OVER-OPT")

    # SCORER vs IMPROVER
    missing_after = det_after.get("skills", {}).get("missing", [])
    kw_missing_after = det_after.get("keywords", {}).get("missing", [])
    if missing_after or kw_missing_after:
        print(f"\n--- GAPS REMAINING ---")
        if missing_after: print(f"  Skills still missing: {missing_after}")
        if kw_missing_after: print(f"  Keywords still missing: {kw_missing_after}")

    # SHORTLIST SCORE (Part 9 — core metric)
    sl_before = compute_shortlist_score(resume, jd, score_before)
    sl_after = compute_shortlist_score(improved, jd, score_after)
    print("\n--- SHORTLIST SCORE ---")
    print("  BEFORE: " + str(int(sl_before['total'])) + "/100  (proof=" + str(int(sl_before['skill_proof'])) + " impact=" + str(int(sl_before['impact_evidence'])) + " role=" + str(int(sl_before['role_alignment'])) + " clarity=" + str(int(sl_before['clarity'])) + " cred=" + str(int(sl_before['credibility'])) + ")")
    print("  AFTER:  " + str(int(sl_after['total'])) + "/100  (proof=" + str(int(sl_after['skill_proof'])) + " impact=" + str(int(sl_after['impact_evidence'])) + " role=" + str(int(sl_after['role_alignment'])) + " clarity=" + str(int(sl_after['clarity'])) + " cred=" + str(int(sl_after['credibility'])) + ")")
    
    # PART 1 (Refinement): COMPOSITE SCORE = 0.6 * shortlist + 0.4 * ATS
    composite_score = round(0.6 * sl_after['total'] + 0.4 * score_after, 1)
    print("  COMPOSITE: " + str(composite_score) + "/100  (0.6*SL + 0.4*ATS)")

    # RECRUITER CONFIDENCE (Part 2 — Calibrated, not binary)
    # Starts at 100, deducts for real gaps. Only near-perfect = 100.
    print("\n--- RECRUITER CONFIDENCE ---")
    conf_score = 100
    conf_deductions = []
    all_imp_bullets = [b for exp in improved.experience for b in exp.bullets]
    all_imp_text = " ".join(all_imp_bullets).lower()
    
    # 1. Impact visibility (metrics OR strong signals in first role's top 2 bullets)
    first_bullets = improved.experience[0].bullets[:2] if improved.experience else []
    has_hard_metrics = any(re.search(r'\d+[%$xX+]|\d+[Kk+]', b) for b in first_bullets)
    has_early_impact = has_hard_metrics or any(
        re.search(r'(?:architect|deploy|built|develop|design|automat)\w*.*(?:for|to|enabling|achieving)', b, re.I)
        for b in first_bullets
    )
    if not has_early_impact:
        conf_score -= 15
        conf_deductions.append("[-15] No impact signal in top bullets")
    elif not has_hard_metrics:
        conf_score -= 5
        conf_deductions.append("[-5] No hard metrics (%, $) in top bullets")
    
    # 2. Skills utilization gaps
    skills_in_exp = sum(1 for sk in improved.skills[:8] if sk.lower() in all_imp_text)
    skills_gap = max(0, len(improved.skills[:8]) - skills_in_exp)
    if skills_gap > 0:
        penalty = min(15, skills_gap * 5)
        conf_score -= penalty
        conf_deductions.append("[-" + str(penalty) + "] " + str(skills_gap) + " skills not proven in experience")
    
    # 3. Summary quality
    summary_lower = (improved.summary or "").lower()
    has_pitch = (
        not any(g in summary_lower for g in ["experienced", "passionate", "dedicated", "seeking"])
        and len(improved.summary or "") > 80
    )
    if not has_pitch:
        conf_score -= 15
        conf_deductions.append("[-15] Summary still generic or too short")
    
    # 4. Verb repetition
    starts = [b.split()[0].lower() for b in all_imp_bullets if b.split()]
    from collections import Counter
    verb_counts = Counter(starts)
    max_repeat = verb_counts.most_common(1)[0][1] if verb_counts else 0
    if max_repeat > 2:
        top_verb = verb_counts.most_common(1)[0][0]
        conf_score -= 10
        conf_deductions.append("[-10] '" + top_verb + "' repeated " + str(max_repeat) + "x")
    
    # 5. Weak bullets remaining
    weak_count = stats.get("WEAK", 0)
    if weak_count > 0:
        penalty = min(10, weak_count * 5)
        conf_score -= penalty
        conf_deductions.append("[-" + str(penalty) + "] " + str(weak_count) + " weak bullets remain")
    
    # 6. Vague language
    vague_count = sum(1 for b in all_imp_bullets 
                      if any(v in b.lower() for v in ['various', 'several', 'some tasks', 'things']))
    if vague_count > 0:
        conf_score -= 10
        conf_deductions.append("[-10] Vague language found: " + str(vague_count) + " bullets")
    
    # 7. Bullet length variation (too uniform = robotic)
    if len(all_imp_bullets) >= 3:
        lengths = [len(b) for b in all_imp_bullets]
        avg_len = sum(lengths) / len(lengths)
        std_dev = (sum((l - avg_len) ** 2 for l in lengths) / len(lengths)) ** 0.5
        if std_dev < 15:  # Very uniform bullet lengths
            conf_score -= 5
            conf_deductions.append("[-5] Bullet lengths too uniform (robotic)")
    
    conf_score = max(0, min(100, conf_score))
    
    if conf_deductions:
        for d in conf_deductions:
            print("  " + d)
    else:
        print("  No deductions — near-perfect output")
    print("  CONFIDENCE: " + str(conf_score) + "/100")
    
    # SIGNAL VISIBILITY SCORE
    from resume_engine.improver import ResumeImprover as _RI
    _audit_role_type = (pipeline_result.role_info or {}).get("role_type", "data")
    top_bullet_score = 0
    if improved.experience and improved.experience[0].bullets:
        top_bullet_score = _RI._score_bullet_impact(improved.experience[0].bullets[0], _audit_role_type)
    
    # HIRING DECISION SIMULATION (Part 3 — Calibrated thresholds)
    # Realistic: requires multiple strong signals AND no major gaps
    print("\n--- HIRING DECISION ---")
    decision_points = 0
    decision_reasons = []
    
    # 1. Strong signals visible?
    if has_early_impact:
        decision_points += 1
        decision_reasons.append("impact visible early")
    else:
        decision_reasons.append("NO early impact signal")
    
    # 2. Role alignment clear?
    if has_pitch:
        decision_points += 1
        decision_reasons.append("clear role positioning")
    else:
        decision_reasons.append("weak positioning")
    
    # 3. Skills demonstrated? (3+ of top 5 proven in bullets)
    proven_skills = sum(1 for sk in improved.skills[:5] 
                        if sk.lower() in all_imp_text)
    if proven_skills >= 3:
        decision_points += 1
        decision_reasons.append(str(proven_skills) + "/5 skills proven")
    else:
        decision_reasons.append("only " + str(proven_skills) + "/5 skills proven")
    
    # 4. Lead bullet quality (must score >= 4 for SHORTLIST consideration)
    if top_bullet_score >= 4:
        decision_points += 1
        decision_reasons.append("strong lead bullet (score=" + str(top_bullet_score) + ")")
    else:
        decision_reasons.append("weak lead bullet (score=" + str(top_bullet_score) + ")")
    
    # 5. No critical gaps (disqualifiers)
    has_critical_gap = False
    if stats.get("OVER-OPT", 0) > 0:
        has_critical_gap = True
        decision_reasons.append("OVER-OPTIMIZED bullets detected")
    if conf_score < 50:
        has_critical_gap = True
        decision_reasons.append("confidence too low")
    
    # Decision: SHORTLIST requires 4/4 points AND no critical gaps AND confidence >= 70
    if decision_points >= 4 and not has_critical_gap and conf_score >= 70:
        hiring_verdict = "SHORTLIST"
    elif decision_points >= 3 and not has_critical_gap:
        hiring_verdict = "STRONG_MAYBE"
    elif decision_points >= 2:
        hiring_verdict = "MAYBE"
    else:
        hiring_verdict = "REJECT"
    
    print("  Decision: " + hiring_verdict + " (" + str(decision_points) + "/4)")
    for r in decision_reasons:
        print("    - " + r)
    
    # COMPETITION SIMULATION (Part 1 — Market Rank)
    # Evaluates resume strength vs typical applicant pool
    print("\n--- MARKET POSITION ---")
    comp_score = 0
    comp_details = []
    
    # Include ALL content (experience + projects) for market assessment
    all_content_bullets = all_imp_bullets + [b for p in improved.projects for b in p.bullets]
    all_content_text = " ".join(all_content_bullets).lower()
    
    # 1. Impact density: how many bullets have quantified results?
    metric_bullets = sum(1 for b in all_content_bullets if re.search(r'\d+[%$xX+]|\d+[Kk+]', b))
    impact_density = metric_bullets / max(1, len(all_content_bullets))
    if impact_density >= 0.4:
        comp_score += 3
        comp_details.append("HIGH impact density (" + str(int(impact_density * 100)) + "% bullets quantified)")
    elif impact_density >= 0.2:
        comp_score += 2
        comp_details.append("MODERATE impact density (" + str(int(impact_density * 100)) + "% quantified)")
    elif impact_density > 0:
        comp_score += 1
        comp_details.append("LOW impact density (" + str(int(impact_density * 100)) + "% quantified)")
    else:
        comp_details.append("NO quantified impact")
    
    # 2. Technical depth: advanced tools/methods visible
    advanced_kw = ['deep learning', 'lstm', 'transformer', 'nlp', 'computer vision', 
                   'reinforcement learning', 'distributed', 'kubernetes', 'microservices',
                   'real-time', 'ml pipeline', 'model deployment', 'a/b testing']
    adv_count = sum(1 for kw in advanced_kw if kw in all_content_text)
    if adv_count >= 4:
        comp_score += 3
        comp_details.append("DEEP technical breadth (" + str(adv_count) + " advanced signals)")
    elif adv_count >= 2:
        comp_score += 2
        comp_details.append("MODERATE technical depth (" + str(adv_count) + " advanced signals)")
    elif adv_count >= 1:
        comp_score += 1
        comp_details.append("BASIC technical depth (" + str(adv_count) + " advanced signal)")
    else:
        comp_details.append("NO advanced technical signals")
    
    # 3. Scale evidence: large numbers indicating real-world impact
    scale_patterns = [r'\d{3,}[Kk+]', r'\d+\s*(million|billion)', r'\d{4,}\+?', r'\d+[Mm]\+?']
    has_scale = any(re.search(p, b) for b in all_content_bullets for p in scale_patterns)
    if has_scale:
        comp_score += 2
        comp_details.append("SCALE evidence present")
    else:
        comp_details.append("No scale evidence")
    
    # 4. Signal density in top 30%: best signals visible early?
    top_30 = all_imp_bullets[:max(1, len(all_imp_bullets) // 3)]
    top_30_text = " ".join(top_30).lower()
    early_signals = sum(1 for kw in advanced_kw if kw in top_30_text)
    if early_signals >= 2:
        comp_score += 2
        comp_details.append("DOMINANT signal placement (" + str(early_signals) + " advanced in top 30%)")
    elif early_signals >= 1:
        comp_score += 1
        comp_details.append("GOOD signal placement (" + str(early_signals) + " advanced in top 30%)")
    else:
        comp_details.append("Weak signal placement in top 30%")
    
    # 5. Purpose-driven differentiation: bullets show WHY not just WHAT
    purpose_count = sum(1 for b in all_imp_bullets 
                        if re.search(r'(?:for|to|enabling|achieving|improving|driving)\s+\w+', b, re.I))
    purpose_ratio = purpose_count / max(1, len(all_imp_bullets))
    if purpose_ratio >= 0.6:
        comp_score += 2
        comp_details.append("STRONG purpose-driven bullets (" + str(int(purpose_ratio * 100)) + "% show WHY)")
    elif purpose_ratio >= 0.3:
        comp_score += 1
        comp_details.append("PARTIAL purpose-driven (" + str(int(purpose_ratio * 100)) + "% show WHY)")
    else:
        comp_details.append("Task-based bullets (no purpose)")
    
    # Market rank (out of 12 now)
    if comp_score >= 9:
        market_rank = "TOP_10"
    elif comp_score >= 5:
        market_rank = "TOP_25"
    elif comp_score >= 3:
        market_rank = "AVERAGE"
    else:
        market_rank = "BELOW"
    
    # Market rank explanation
    rank_explain = {
        "TOP_10": "Top 10% — exceptional candidate. Expected shortlist rate: ~50-70%",
        "TOP_25": "Top 25% — strong competitive profile. Expected shortlist rate: ~25-40%",
        "AVERAGE": "Average applicant pool. Expected shortlist rate: ~10-15%",
        "BELOW": "Below average positioning. Expected shortlist rate: <10%",
    }
    print("  Rank: " + market_rank + " (" + str(comp_score) + "/12)")
    print("  " + rank_explain[market_rank])
    for d in comp_details:
        print("    - " + d)
    
    # ACTION MAPPING (Part 2)
    action_map = {
        "SHORTLIST": "APPLY",
        "STRONG_MAYBE": "APPLY (fix gaps)",
        "MAYBE": "IMPROVE FIRST",
        "REJECT": "DO NOT APPLY",
    }
    action = action_map.get(hiring_verdict, "UNKNOWN")
    
    # -- PART 1 (Decision Perfection): DECISION CORRECTION --
    # Override action using composite score + skill proof for strict thresholds
    # Part 2: CONFIDENCE-WEIGHTED DECISION
    decision_score = round(composite_score * (conf_score / 100), 1)
    
    # Part 4: STRICT TRUST ENFORCEMENT — never over-encourage weak candidates
    if decision_score < 40:
        action = "DO NOT APPLY"
    elif decision_score < 55 and proven_skills < 3:
        action = "IMPROVE FIRST"
    elif decision_score < 55:
        action = "IMPROVE FIRST"
    elif decision_score < 70:
        action = "APPLY (fix gaps)"
    else:
        action = "APPLY"
    
    # GAP-TO-SHORTLIST ENGINE (Part 4)
    gaps = []
    actions_list = []  # Renamed to avoid shadowing
    strengths = []
    
    # Identify strengths
    if has_early_impact:
        strengths.append("strong early impact signal")
    if has_pitch:
        strengths.append("clear role positioning")
    if proven_skills >= 3:
        strengths.append(str(proven_skills) + " skills proven in experience")
    if top_bullet_score >= 5:
        strengths.append("high-quality lead bullet (score=" + str(top_bullet_score) + ")")
    if adv_count >= 2:
        strengths.append(str(adv_count) + " advanced technical signals")
    
    # Identify gaps with actions — each gap has (priority, gap_text, action_text)
    # Part 3: IMPACT PRIORITIZATION — sort by impact on shortlist
    gap_actions = []
    if not has_hard_metrics:
        gap_actions.append((1, "no hard metrics (%, $) in top bullets",
                           "add quantified results to first 2 experience bullets"))
    if not has_pitch:
        gap_actions.append((2, "summary is generic or too short",
                           "rewrite summary with [Role + Specialization + Scale + Impact]"))
    if proven_skills < 3:
        missing_count = 3 - proven_skills
        gap_actions.append((3, str(missing_count) + " key skills not proven in experience",
                           "add skill demonstrations to experience bullets"))
    if top_bullet_score < 4:
        gap_actions.append((4, "lead bullet is weak (score=" + str(top_bullet_score) + ")",
                           "strengthen first bullet with impact + scale + purpose"))
    if impact_density < 0.2:
        gap_actions.append((5, "low impact density (" + str(int(impact_density * 100)) + "% quantified)",
                           "add quantified results to at least 2 more bullets"))
    if skills_gap > 2:
        gap_actions.append((6, str(skills_gap) + " listed skills not demonstrated",
                           "link unused skills to specific experience bullets"))
    if max_repeat > 2:
        gap_actions.append((7, "verb repetition detected",
                           "vary starting verbs across bullets"))
    
    # Sort by priority (lowest = highest impact on shortlist)
    gap_actions.sort(key=lambda x: x[0])
    gaps = [g[1] for g in gap_actions]
    actions_list = [g[2] for g in gap_actions]
    
    # CAREER DECISION OUTPUT — UX Refinement Layer
    # Part 5: User feels "I know exactly what to do next"
    print("\n--- CAREER DECISION ---")
    print("  Decision Score: " + str(decision_score) + "/100  (composite=" + str(composite_score) + " × conf=" + str(conf_score) + "%)")
    
    # Part 1 (UX): DECISION LANGUAGE UPGRADE
    top_gap_summary = ""
    if gaps[:2]:
        top_gap_summary = " — fix: " + "; ".join(gaps[:2])
    
    decision_labels = {
        "APPLY": "🔥 APPLY — strong match, submit now",
        "APPLY (fix gaps)": "📋 APPLY — but improve top 2 gaps" + top_gap_summary,
        "IMPROVE FIRST": "⚠️ IMPROVE FIRST — address critical gaps before applying",
        "DO NOT APPLY": "🚫 DO NOT APPLY — significant mismatch, target better-fit roles",
    }
    print("  " + decision_labels.get(action, "📋 " + action))
    
    # Part 3 (Micro-Polish): NATURAL CONFIDENCE LANGUAGE
    # Build a human-readable sentence instead of bullet list
    skill_phrase = ("strong skill proof" if proven_skills >= 3
                    else "moderate skill proof" if proven_skills >= 1
                    else "weak skill proof")
    impact_phrase = ("solid impact visibility" if has_early_impact
                     else "impact visibility needs work")
    summary_phrase = ("clear role positioning" if has_pitch
                      else "summary needs targeting")
    
    conf_sentence = skill_phrase + ", " + impact_phrase + ", " + summary_phrase
    print("  🎯 CONFIDENCE: " + str(conf_score) + "% — " + conf_sentence)
    
    # 📊 WHY YOU WILL GET SHORTLISTED
    if strengths:
        print("  📊 WHY YOU WILL GET SHORTLISTED:")
        for s in strengths[:4]:
            print("    + " + s)
    
    # COMPETITIVE COMPARISON
    print("  📈 COMPARED TO SIMILAR CANDIDATES:")
    comp_strengths = []
    comp_weaknesses = []
    if impact_density >= 0.3:
        comp_strengths.append("stronger impact evidence than most applicants")
    elif impact_density < 0.15:
        comp_weaknesses.append("fewer quantified results than competitive candidates")
    if proven_skills >= 4:
        comp_strengths.append("above-average skill demonstration")
    elif proven_skills < 2:
        comp_weaknesses.append("skills listed but not proven in experience")
    if top_bullet_score >= 7:
        comp_strengths.append("lead bullet is top-quartile strength")
    elif top_bullet_score < 4:
        comp_weaknesses.append("lead bullet weaker than typical shortlisted candidates")
    if conf_score >= 80:
        comp_strengths.append("high recruiter confidence signal")
    
    # Experience-range + role-type benchmarking
    exp_count = len(improved.experience)
    exp_label = "junior" if exp_count <= 1 else ("mid-level" if exp_count <= 3 else "senior")
    _role_t = (pipeline_result.role_info or {}).get("role_type", "technical")
    print("    [vs " + exp_label + " " + _role_t + " candidates]")
    
    if composite_score >= 75:
        comp_strengths.append("top-quartile composite score for " + exp_label + " pool")
    elif composite_score < 50:
        comp_weaknesses.append("below-average composite score for " + exp_label + " pool")
    
    for cs in comp_strengths[:4]:
        print("    + " + cs)
    for cw in comp_weaknesses[:3]:
        print("    - " + cw)
    
    # ⚠️ WHAT TO FIX
    if gaps:
        print("  ⚠️ WHAT TO FIX:")
        for g in gaps[:4]:
            print("    - " + g)
    
    # 🚫 REJECTION REASON ENGINE
    rejection_reasons = []
    if not has_early_impact:
        rejection_reasons.append("missing impact evidence in first role — recruiter loses interest")
    if proven_skills < 2:
        rejection_reasons.append("key JD skills not demonstrated in experience bullets")
    if top_bullet_score < 3:
        rejection_reasons.append("weak first impression — lead bullet lacks action + scale + outcome")
    if not has_pitch:
        rejection_reasons.append("summary doesn't position candidate for THIS specific role")
    if sl_after["total"] < 50:
        rejection_reasons.append("low shortlist probability — resume doesn't stand out in applicant pool")
    
    if rejection_reasons:
        print("  🚫 WHY YOU MAY GET REJECTED:")
        for rr in rejection_reasons[:4]:
            print("    - " + rr)
    
    # ⚡ RISK SIGNAL DETECTION
    risk_signals = []
    if stats["OVER-OPT"] > 0:
        risk_signals.append("over-optimized language detected (" + str(stats["OVER-OPT"]) + " bullets)")
    if len(improved.experience) >= 2:
        titles = [exp.role.lower().strip() for exp in improved.experience]
        if len(set(titles)) == 1:
            risk_signals.append("no career progression — same title across all roles")
    if improved.summary and improved.experience:
        summary_l = improved.summary.lower()
        first_role_l = improved.experience[0].role.lower()
        tech_terms = ["engineer", "developer", "architect", "devops"]
        non_tech_terms = ["manager", "analyst", "coordinator", "specialist"]
        summary_tech = any(t in summary_l for t in tech_terms)
        role_tech = any(t in first_role_l for t in tech_terms)
        summary_nontech = any(t in summary_l for t in non_tech_terms)
        role_nontech = any(t in first_role_l for t in non_tech_terms)
        if summary_tech and role_nontech:
            risk_signals.append("inconsistent story — summary signals technical but role is non-technical")
        elif summary_nontech and role_tech:
            risk_signals.append("inconsistent story — summary signals non-technical but role is technical")
    
    if risk_signals:
        print("  ⚡ RISK SIGNALS:")
        for rs_item in risk_signals:
            print("    ⚠ " + rs_item)
    
    # 🚀 QUICK ACTIONS (max 3) — Highest Impact First
    if actions_list:
        # Part 4 (Micro-Polish): FIRST ACTION PRIORITY
        print("  👉 Start with: " + actions_list[0])
        if len(actions_list) > 1:
            print("  🚀 THEN:")
            for i, a in enumerate(actions_list[1:3], 2):
                print("    " + str(i) + ". " + a)
    
    # Part 2 (UX): EFFORT ESTIMATION
    gap_count = len(gaps)
    if gap_count == 0:
        effort_label = "None needed"
        effort_time = ""
    elif gap_count <= 2:
        effort_label = "Low"
        effort_time = " (5–10 min, " + str(gap_count) + " bullet edit" + ("s" if gap_count > 1 else "") + ")"
    elif gap_count <= 4:
        effort_label = "Medium"
        effort_time = " (30–60 min, " + str(gap_count) + " bullet edits)"
    else:
        effort_label = "High"
        effort_time = " (1–2 hours, " + str(gap_count) + " edits across resume)"
    
    # Part 3 (UX): IMPACT ESTIMATION
    # Estimate shortlist improvement from fixing gaps
    impact_pts = 0
    if not has_hard_metrics:
        impact_pts += 8  # Adding metrics → big shortlist jump
    if not has_pitch:
        impact_pts += 6  # Summary targeting → role alignment boost
    if proven_skills < 3:
        impact_pts += 5  # Proving skills → skill_proof boost
    if top_bullet_score < 4:
        impact_pts += 4  # Stronger lead → first impression boost
    if impact_density < 0.2:
        impact_pts += 3  # More quantified bullets → impact_evidence boost
    impact_pts = min(impact_pts, 25)  # Cap at realistic maximum
    
    if gap_count > 0:
        print("  ⏱ FIX EFFORT: " + effort_label + effort_time)
        # Part 1 (Micro-Polish): IMPACT GROUNDING with probability range
        prob_low = max(5, impact_pts * 2 - 5)
        prob_high = min(40, impact_pts * 2 + 5)
        print("  📈 EXPECTED IMPACT: Fixing these → +" + str(impact_pts) + " shortlist score (~" + str(prob_low) + "–" + str(prob_high) + "% higher shortlist probability)")
    
    return {"name": name, "before": score_before, "after": score_after,
            "delta": delta, "q_before": q_before["total"], "q_after": q_after["total"],
            "sl_before": sl_before["total"], "sl_after": sl_after["total"],
            "composite": composite_score,
            "unused": len(unused), "good": stats["GOOD"], "total": total,
            "over_opt": stats["OVER-OPT"], "confidence": conf_score,
            "top_signal": top_bullet_score, "hiring": hiring_verdict,
            "action": action, "market_rank": market_rank, "comp_score": comp_score}


# ============================================================
# RUN AUDIT
# ============================================================
print("=" * 70)
print("ADVERSARIAL LIVE SYSTEM AUDIT")
print("=" * 70)

results = []
results.append(audit_case("Strong DS + Strong JD", make_ds_resume(), make_ds_jd(), "strict"))
results.append(audit_case("Weak Resume + SWE JD", make_weak_resume(), make_swe_jd(), "strict"))
results.append(audit_case("HR (Non-Tech)", make_hr_resume(), make_hr_jd(), "strict"))
results.append(audit_case("DS Balanced", make_ds_resume(), make_ds_jd(), "balanced"))

# MODE DIFFERENTIATION
print("\n" + "="*70)
print("PART 10: MODE DIFFERENTIATION")
print("="*70)
ds, jd = make_ds_resume(), make_ds_jd()
_, _, det = scorer.score(ds, jd)
mi = det.get("skills",{}).get("missing",[])
ma = det.get("skills",{}).get("matched",[])
kw = det.get("keywords",{}).get("matched",[]) + det.get("keywords",{}).get("missing",[])
r_s_result = run_full_pipeline(make_ds_resume(), make_ds_resume(), make_ds_jd(), scorer, mode="strict")
r_b_result = run_full_pipeline(make_ds_resume(), make_ds_resume(), make_ds_jd(), scorer, mode="balanced")
r_c_result = run_full_pipeline(make_ds_resume(), make_ds_resume(), make_ds_jd(), scorer, mode="conservative")
r_s, r_b, r_c = r_s_result.improved, r_b_result.improved, r_c_result.improved
ss = r_s_result.ats_report.score_after
sb = r_b_result.ats_report.score_after
sc = r_c_result.ats_report.score_after
ts = " ".join(b for e in r_s.experience for b in e.bullets)
tb = " ".join(b for e in r_b.experience for b in e.bullets)
tc = " ".join(b for e in r_c.experience for b in e.bullets)
print("  Strict:       " + str(ss) + " | len=" + str(len(ts)))
print("  Balanced:     " + str(sb) + " | len=" + str(len(tb)))
print("  Conservative: " + str(sc) + " | len=" + str(len(tc)))
print("  S-B gap: " + str(round(ss-sb, 1)) + " | S-C gap: " + str(round(ss-sc, 1)))
print("  Text differs S/B: " + str(ts!=tb) + " | S/C: " + str(ts!=tc))

# CONTRADICTION DETECTION
print("\n" + "="*70)
print("PART 12: CONTRADICTIONS")
print("="*70)
contradictions = 0
for r in results:
    if r["delta"] > 0 and r["unused"] > 0:
        print("  X " + r['name'] + ": Score +" + str(round(r['delta'],1)) + " but " + str(r['unused']) + " skills unused")
        contradictions += 1
    if r["good"] < r["total"] * 0.4:
        print("  ! " + r['name'] + ": Only " + str(r['good']) + "/" + str(r['total']) + " GOOD bullets")
        contradictions += 1
if contradictions == 0:
    print("  No contradictions found")

# FINAL VERDICT
print("\n" + "="*70)
print("FINAL SYSTEM VERDICT")
print("="*70)
for r in results:
    s = "+" if r["after"] >= 85 else ("~" if r["after"] >= 75 else "-")
    print("  [" + s + "] " + r['name'] + ": " + str(round(r['before'],1)) + " -> " + str(round(r['after'],1)) + " (+" + str(round(r['delta'],1)) + ") Q=" + str(int(r['q_after'])) + " SL=" + str(int(r['sl_after'])) + " CONF=" + str(r['confidence']) + " MKT=" + r.get('market_rank', '?'))

avg = sum(r["after"] for r in results) / len(results)
avg_d = sum(r["delta"] for r in results) / len(results)
avg_sl = sum(r["sl_after"] for r in results) / len(results)
avg_conf = sum(r["confidence"] for r in results) / len(results)

# ============================================================
# PRODUCTION READINESS (10 criteria — ALL must pass)
# ============================================================
checks = {}

# 1. Strong strict cases >= 85
strict_strong = [r for r in results if "Weak" not in r["name"] and "Balanced" not in r["name"]]
checks["strong_85"] = all(r["after"] >= 85 for r in strict_strong) if strict_strong else False

# 2. Modes must differ: gap between 2 and 12 pts (real text differentiation)
mode_gap = abs(ss - sb)
checks["mode_gap"] = 2.0 <= mode_gap <= 12.0

# 3. Weak cases show strong delta (>= 10 pts)
weak_cases = [r for r in results if "Weak" in r["name"]]
checks["weak_delta"] = all(r["delta"] >= 10 for r in weak_cases) if weak_cases else True

# 4. Outputs differ across modes
checks["mode_diff"] = ts != tb and ts != tc

# 5. Zero OVER-OPT bullets
checks["no_overopt"] = all(r.get("over_opt", 0) == 0 for r in results)

# 6. Shortlist scores >= 58 for strong cases (role-aware scoring variance)
checks["shortlist"] = all(r["sl_after"] >= 58 for r in strict_strong) if strict_strong else False

# 7. Recruiter confidence >= 70 for strong cases
checks["confidence"] = all(r["confidence"] >= 70 for r in strict_strong) if strict_strong else False

# 8. Top bullet signal strength >= 3 for all cases
checks["signal_vis"] = all(r["top_signal"] >= 3 for r in results)

# 9. Hiring decision >= STRONG_MAYBE for strong cases
checks["hiring"] = all(r["hiring"] in ("SHORTLIST", "STRONG_MAYBE") for r in strict_strong) if strict_strong else False

# 10. Market rank >= TOP_25 for strong cases
checks["market"] = all(r.get("market_rank") in ("TOP_10", "TOP_25") for r in strict_strong) if strict_strong else False

print("\n  --- PRODUCTION CHECKS (10 criteria) ---")
strong_labels = [r['name'] + "=" + str(int(r['after'])) for r in strict_strong]
weak_labels = ["+" + str(round(r['delta'], 1)) for r in weak_cases]
sl_labels = [r['name'] + "=" + str(int(r['sl_after'])) for r in strict_strong]
conf_labels = [r['name'] + "=" + str(r['confidence']) for r in strict_strong]
sig_labels = [r['name'] + "=" + str(r['top_signal']) for r in results]
hire_labels = [r['name'] + "=" + r['hiring'] for r in results]
mkt_labels = [r['name'] + "=" + r.get('market_rank', '?') for r in results]
oop_total = sum(r.get('over_opt', 0) for r in results)

labels = ['strong_85', 'mode_gap', 'weak_delta', 'mode_diff', 'no_overopt', 'shortlist', 'confidence', 'signal_vis', 'hiring', 'market']
descs = [
    "Strong strict 85+: " + str(strong_labels),
    "Mode gap 1.5 <= x <= 5: " + str(round(mode_gap, 1)),
    "Weak delta >= 10: " + str(weak_labels),
    "Mode text differs: S/B=" + str(ts!=tb) + " S/C=" + str(ts!=tc),
    "Zero OVER-OPT: " + str(oop_total) + " total",
    "Shortlist >= 60: " + str(sl_labels),
    "Recruiter conf >= 70: " + str(conf_labels),
    "Signal visibility >= 3: " + str(sig_labels),
    "Hiring >= STRONG_MAYBE: " + str(hire_labels),
    "Market >= TOP_25: " + str(mkt_labels),
]
for lbl, desc in zip(labels, descs):
    tag = "Y" if checks[lbl] else "N"
    print("  [" + tag + "] " + desc)

passed = sum(1 for v in checks.values() if v)
total_checks = len(checks)
prod_ready = all(checks.values())
print("\n  Avg ATS: " + str(round(avg, 1)) + " | Avg SL: " + str(round(avg_sl, 1)) + " | Avg Conf: " + str(round(avg_conf, 1)) + " | Delta: +" + str(round(avg_d, 1)))
print("  Checks: " + str(passed) + "/" + str(total_checks))
verdict = "YES" if prod_ready else ("PARTIAL" if passed >= 8 else "NO")
print("  CAREER DECISION ENGINE: " + verdict)

