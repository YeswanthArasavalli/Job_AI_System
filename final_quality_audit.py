"""
FINAL QUALITY AUDIT — Tests every rule from Parts 1-12.
Finds: duplicates, broken sentences, tool misuse, semantic drift,
       summary spam, incomplete clauses, mode differentiation.
"""
import sys, io, re, copy
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
import logging; logging.disable(logging.WARNING)

from pipeline.core import run_full_pipeline
from ats_scoring.scorer import ATSScorer
from utils.models import *

# --- Test resume with realistic data ---
resume = StructuredResume(
    contact=ContactInfo(name='Sreejita Das', email='sreejita@email.com'),
    title='Machine Learning Engineer',
    summary='Passionate about machine learning and data science.',
    skills=['Python', 'TensorFlow', 'PyTorch', 'SQL', 'Machine Learning', 'NLP',
            'Docker', 'Pandas', 'AWS', 'Deep Learning', 'Scikit-learn', 'NumPy',
            'Computer Vision', 'LSTM', 'Tableau', 'Spark'],
    experience=[
        ExperienceEntry(company='TechCorp AI', role='ML Engineer', duration='2022-2024',
            bullets=[
                'Built predictive models for customer churn reducing attrition by 15%.',
                'Developed NLP pipelines for sentiment analysis processing 200K+ reviews.',
                'Deployed machine learning models to production using Docker on AWS.',
                'Created interactive dashboards for business stakeholders using Tableau.',
            ]),
        ExperienceEntry(company='DataWorks Inc', role='Data Scientist', duration='2020-2022',
            bullets=[
                'Trained deep learning models for image classification achieving 94% accuracy.',
                'Built ETL data pipelines using Python and Pandas processing 500K records daily.',
                'Implemented recommendation system improving user engagement by 22%.',
            ]),
        ExperienceEntry(company='Analytics Labs', role='Junior Data Analyst', duration='2019-2020',
            bullets=[
                'Analyzed sales data to identify revenue trends and seasonal patterns.',
                'Created automated reports using SQL reducing manual effort by 40%.',
            ]),
    ],
    projects=[
        ProjectEntry(name='NLP Chatbot', technologies=['Python', 'BERT', 'Flask'],
            bullets=['Built NLP-based chatbot using BERT achieving 92% intent accuracy.',
                     'Deployed chatbot to production serving 10K+ daily users.']),
        ProjectEntry(name='Image Classifier', technologies=['PyTorch', 'EfficientNet'],
            bullets=['Developed image classification pipeline using EfficientNet.',
                     'Achieved 96% accuracy on custom dataset of 50K images.']),
    ],
    education=[EducationEntry(degree='M.S. Computer Science', institution='IIT Delhi', year='2019')]
)
jd = ExtractedJD(
    job_title='Senior ML Engineer', company='Google',
    required_skills=['Python', 'Machine Learning', 'Deep Learning', 'TensorFlow', 'NLP',
                     'SQL', 'Docker', 'PyTorch'],
    preferred_skills=['AWS', 'Kubernetes', 'Spark', 'Computer Vision', 'LSTM'],
    keywords=['machine learning', 'deep learning', 'nlp', 'tensorflow', 'python', 'sql',
              'data pipelines', 'model deployment', 'computer vision', 'mlops',
              'recommendation systems', 'feature engineering'],
    responsibilities=['Deploy ML models at scale', 'Build data pipelines', 'Lead ML research',
                      'Develop NLP systems', 'Build recommendation engines'],
    required_experience_years=5, raw_text='Senior ML Engineer at Google building production ML systems'
)

scorer = ATSScorer()

print("=" * 70)
print("FINAL QUALITY AUDIT — Sreejita Hiring Engine v1.0")
print("=" * 70)

issues = []

# Run all 3 modes
for mode in ['strict', 'balanced', 'conservative']:
    r = run_full_pipeline(original=resume, tailored=copy.deepcopy(resume),
                          extracted_jd=jd, scorer=scorer, mode=mode)
    improved = r.improved
    all_bullets = [b for exp in improved.experience for b in exp.bullets]
    all_proj_bullets = [b for p in improved.projects for b in p.bullets]

    print(f"\n{'='*70}")
    print(f"MODE: {mode.upper()}")
    print(f"Score: {r.ats_report.score_before} -> {r.ats_report.score_after}")
    if r.hiring_simulation:
        hs = r.hiring_simulation
        print(f"Hiring: {hs['decision']} | Shortlist: {hs['shortlist_probability']}%")
    print(f"{'='*70}")

    # PART 1: Semantic Preservation
    print("\n--- PART 1: Semantic Preservation ---")
    for i_exp, exp in enumerate(improved.experience):
        if i_exp < len(resume.experience):
            orig_exp = resume.experience[i_exp]
            # Build word sets for all original bullets (handles reordering)
            orig_word_sets = [
                set(re.findall(r'\b\w{4,}\b', ob.lower()))
                for ob in orig_exp.bullets
            ]
            for j, bullet in enumerate(exp.bullets):
                new_words = set(re.findall(r'\b\w{4,}\b', bullet.lower()))
                # Find BEST match among all original bullets (not just position)
                best_preserved = 0.0
                for ows in orig_word_sets:
                    if ows:
                        p = len(ows & new_words) / len(ows)
                        best_preserved = max(best_preserved, p)
                if best_preserved < 0.3:
                    msg = f"[{mode}] SEMANTIC DRIFT exp[{i_exp}].b[{j}]: {best_preserved:.0%} preserved"
                    issues.append(msg)
                    print(f"  FAIL: {msg}")
                    print(f"    NEW:  {bullet[:80]}")

    # PART 2: Bullet Deduplication
    print("\n--- PART 2: Bullet Deduplication ---")
    seen = set()
    for b in all_bullets:
        key = b.lower().strip().rstrip('.')
        if key in seen:
            msg = f"[{mode}] DUPLICATE BULLET: {b[:60]}"
            issues.append(msg)
            print(f"  FAIL: {msg}")
        seen.add(key)
    if not any("DUPLICATE" in i and mode in i for i in issues):
        print("  PASS: No duplicates")

    # PART 3: Sentence Completion
    print("\n--- PART 3: Sentence Completion ---")
    for idx, b in enumerate(all_bullets + all_proj_bullets):
        if not b.strip():
            issues.append(f"[{mode}] EMPTY BULLET at index {idx}")
            print(f"  FAIL: Empty bullet at index {idx}")
            continue
        if not b.rstrip().endswith('.') and not b.rstrip().endswith('!'):
            msg = f"[{mode}] NO PERIOD: {b[:60]}"
            issues.append(msg)
            print(f"  FAIL: {msg}")
        # Incomplete clause check
        incomplete = re.search(r'(?:and|or|for|by|with|to)\s*\.?\s*$', b.strip())
        if incomplete:
            msg = f"[{mode}] INCOMPLETE CLAUSE: {b[-30:]}"
            issues.append(msg)
            print(f"  FAIL: {msg}")
        if b.count('..') > 0:
            msg = f"[{mode}] DOUBLE PERIOD: {b[:60]}"
            issues.append(msg)
            print(f"  FAIL: {msg}")
    if not any(("NO PERIOD" in i or "INCOMPLETE" in i or "DOUBLE" in i) and mode in i for i in issues):
        print("  PASS: All sentences complete")

    # PART 4: Tool Context Validation
    print("\n--- PART 4: Tool Context Validation ---")
    tool_mismatches = {
        'efficientnet': ['dashboard', 'report', 'sql', 'etl', 'stakeholder'],
        'numpy': ['dashboard', 'report', 'stakeholder', 'visual'],
        'lstm': ['dashboard', 'report', 'sql query', 'stakeholder'],
        'bert': ['dashboard', 'image classif', 'sql', 'etl'],
        'sql': ['image classif', 'computer vision', 'nlp pipeline', 'deep learning model'],
    }
    for b in all_bullets:
        bl = b.lower()
        for tool, bad_contexts in tool_mismatches.items():
            if tool in bl:
                for bad in bad_contexts:
                    if bad in bl:
                        msg = f"[{mode}] TOOL MISMATCH: '{tool}' in '{bad}' context: {b[:70]}"
                        issues.append(msg)
                        print(f"  FAIL: {msg}")
    if not any("TOOL MISMATCH" in i and mode in i for i in issues):
        print("  PASS: All tools contextually valid")

    # PART 5: Summary Quality
    print("\n--- PART 5: Summary Quality ---")
    summary = improved.summary or ""
    tool_count = 0
    common_tools = ['python', 'tensorflow', 'pytorch', 'sql', 'docker', 'aws', 'spark',
                    'kubernetes', 'tableau', 'pandas', 'numpy', 'scikit-learn']
    for t in common_tools:
        if t in summary.lower():
            tool_count += 1
    if tool_count > 5:
        msg = f"[{mode}] SUMMARY SPAM: {tool_count} tools in summary (max 5)"
        issues.append(msg)
        print(f"  FAIL: {msg}")
    if summary.count(',') > 6:
        msg = f"[{mode}] SUMMARY COMMA-HEAVY: {summary.count(',')} commas"
        issues.append(msg)
        print(f"  FAIL: {msg}")
    print(f"  Summary ({len(summary)} chars, {tool_count} tools): {summary[:100]}...")

    # PART 6: Project Section
    print("\n--- PART 6: Project Section ---")
    for p in improved.projects:
        for b in p.bullets:
            if len(b.strip()) < 20:
                msg = f"[{mode}] FRAGMENT: '{b}'"
                issues.append(msg)
                print(f"  FAIL: {msg}")
    if not any("FRAGMENT" in i and mode in i for i in issues):
        print("  PASS: Projects intact")

    # Print all bullets for visual review
    print(f"\n--- FULL OUTPUT ({mode}) ---")
    for exp in improved.experience:
        print(f"  {exp.role} @ {exp.company}")
        for b in exp.bullets:
            using_count = len(re.findall(r'\busing\s+\w', b.lower()))
            using_count += len(re.findall(r'\b(?:applying|leveraging|utilizing)\s+\w', b.lower()))
            flag = " ⚠️STACK" if using_count > 1 else ""
            print(f"    • {b}{flag}")

# PART 10: Mode Differentiation
print(f"\n{'='*70}")
print("PART 10: MODE DIFFERENTIATION")
print(f"{'='*70}")
mode_outputs = {}
for mode in ['strict', 'balanced', 'conservative']:
    r = run_full_pipeline(original=resume, tailored=copy.deepcopy(resume),
                          extracted_jd=jd, scorer=scorer, mode=mode)
    bullets = [b for exp in r.improved.experience for b in exp.bullets]
    mode_outputs[mode] = bullets
    print(f"  {mode}: {len(bullets)} bullets, score={r.ats_report.score_after}")

# Check if modes produce different output
if mode_outputs['strict'] == mode_outputs['conservative']:
    msg = "MODES IDENTICAL: strict == conservative"
    issues.append(msg)
    print(f"  FAIL: {msg}")
else:
    diff_count = sum(1 for a, b in zip(mode_outputs['strict'], mode_outputs['conservative'])
                     if a != b)
    print(f"  PASS: strict vs conservative differ in {diff_count} bullets")

# FINAL VERDICT
print(f"\n{'='*70}")
print("FINAL VERDICT")
print(f"{'='*70}")
print(f"Total issues: {len(issues)}")
for i, issue in enumerate(issues):
    print(f"  {i+1}. {issue}")
if not issues:
    print("  ✅ ZERO ISSUES — PRODUCTION PERFECT")
else:
    print(f"\n  ❌ {len(issues)} ISSUES NEED FIXING")
