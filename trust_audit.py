"""TRUST AUDIT — Tests authenticity, inflation, and recruiter believability."""
import sys, io, re, copy
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
import logging; logging.disable(logging.WARNING)

from pipeline.core import run_full_pipeline
from ats_scoring.scorer import ATSScorer
from utils.models import *

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
    ],
    education=[EducationEntry(degree='M.S. Computer Science', institution='IIT Delhi', year='2019')]
)
jd = ExtractedJD(
    job_title='Senior ML Engineer', company='Google',
    required_skills=['Python', 'Machine Learning', 'Deep Learning', 'TensorFlow', 'NLP',
                     'SQL', 'Docker', 'PyTorch'],
    preferred_skills=['AWS', 'Kubernetes', 'Spark', 'Computer Vision', 'LSTM'],
    keywords=['machine learning', 'deep learning', 'nlp', 'tensorflow', 'python', 'sql',
              'data pipelines', 'model deployment', 'computer vision', 'mlops'],
    responsibilities=['Deploy ML models at scale', 'Build data pipelines'],
    required_experience_years=5, raw_text='Senior ML Engineer at Google'
)

STRONG_VERBS = {
    'architected', 'spearheaded', 'orchestrated', 'pioneered', 'championed',
    'revolutionized', 'transformed', 'engineered', 'streamlined', 'accelerated',
}
SYNTHETIC_PATTERNS = [
    r'enabling\s+\w+\s+\w+\s+\w+\s+\w+',   # long enabling clause
    r'for\s+\w+\s+\w+\s+\w+\s+\w+\s+\w+',  # overly long purpose clause
    r'(?:scalable|robust|enterprise|production-grade|cutting-edge)\s+\w+\s+\w+',
]

for mode in ['strict', 'balanced', 'conservative']:
    r = run_full_pipeline(original=resume, tailored=copy.deepcopy(resume),
                          extracted_jd=jd, scorer=ATSScorer(), mode=mode)
    improved = r.improved
    all_bullets = [b for exp in improved.experience for b in exp.bullets]
    
    print(f"\n{'='*60}")
    print(f"TRUST AUDIT — {mode.upper()}")
    print(f"{'='*60}")
    
    # 1. Strong verb count per role
    print("\n  [1] Strong Verb Check (max 4 per role):")
    for exp in improved.experience:
        sv_count = 0
        for b in exp.bullets:
            first_word = b.split()[0].lower().rstrip('ed') if b.split() else ''
            if b.split()[0].lower() in STRONG_VERBS:
                sv_count += 1
        status = "PASS" if sv_count <= 4 else "FAIL"
        print(f"    {exp.company}: {sv_count} strong verbs [{status}]")

    # 2. Pattern repetition
    print("\n  [2] Pattern Repetition:")
    patterns_seen = {}
    for b in all_bullets:
        # Extract sentence pattern: VERB + ... + TOOL_PHRASE
        pat = re.sub(r'\b\d+\w*\b', 'NUM', b)
        pat = re.sub(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', 'NOUN', pat)
        first_3 = ' '.join(pat.split()[:3])
        patterns_seen[first_3] = patterns_seen.get(first_3, 0) + 1
    repeated = {k: v for k, v in patterns_seen.items() if v > 2}
    if repeated:
        for k, v in repeated.items():
            print(f"    WARN: Pattern '{k}' repeated {v}x")
    else:
        print(f"    PASS: No excessive pattern repetition")

    # 3. Synthetic language detection
    print("\n  [3] Synthetic Language:")
    synth_count = 0
    for b in all_bullets:
        for pat in SYNTHETIC_PATTERNS:
            if re.search(pat, b.lower()):
                synth_count += 1
                print(f"    FLAG: {b[:70]}...")
                break
    if synth_count == 0:
        print(f"    PASS: No synthetic patterns")
    
    # 4. Metric inflation check
    print("\n  [4] Metric Authenticity:")
    for i_exp, exp in enumerate(improved.experience):
        orig_exp = resume.experience[i_exp] if i_exp < len(resume.experience) else None
        if not orig_exp:
            continue
        orig_text = ' '.join(orig_exp.bullets).lower()
        for b in exp.bullets:
            # Find all metrics in improved bullet
            metrics = re.findall(r'\d+\s*[%KkMm+$]|\d{3,}', b)
            for m in metrics:
                # Check if metric existed in original
                if m not in orig_text:
                    print(f"    FLAG: New metric '{m}' not in original: {b[:60]}")
    
    # 5. Overall trust score
    trust = 100
    if synth_count > 2: trust -= 15
    if repeated: trust -= 10
    if any(b.count(',') > 3 for b in all_bullets): trust -= 5
    print(f"\n  TRUST SCORE: {trust}/100")
    
    # Print bullets for review
    print(f"\n  --- Bullets ({mode}) ---")
    for exp in improved.experience:
        print(f"  {exp.role} @ {exp.company}")
        for b in exp.bullets:
            print(f"    {b}")
