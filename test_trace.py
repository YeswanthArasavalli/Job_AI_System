"""Trace each rewrite call input and output for bullet[0]."""
import sys, copy, logging
sys.path.insert(0, '.')
logging.disable(logging.WARNING)

from utils.models import *
from ats_scoring.scorer import ATSScorer
import pipeline.bullet_rewriter as bw

_orig = bw.rewrite_all_bullets
call_n = [0]
def traced(bullets, skills):
    call_n[0] += 1
    n = call_n[0]
    print(f"\n--- REWRITE CALL #{n} ---")
    for i, b in enumerate(bullets):
        print(f"  INPUT [{i}]: {b}")
    r = _orig(bullets, skills)
    for i, b in enumerate(r["final_bullets"]):
        changed = " ✦" if b != bullets[i] else ""
        has_dbl = " ❌" if "in in" in b else ""
        bare_in = " ⚠️BARE-IN" if b.endswith(" in.") else ""
        print(f"  OUTPUT[{i}]: {b}{changed}{has_dbl}{bare_in}")
    return r

bw.rewrite_all_bullets = traced
import pipeline.core as pc
pc.rewrite_all_bullets = traced

resume = StructuredResume(
    contact=ContactInfo(name="Y", email="y@g.com"),
    title="Data Scientist",
    summary="Data Analyst with Python, SQL experience in analytics and ML.",
    skills=["Python", "SQL", "Pandas", "Scikit-learn"],
    experience=[
        ExperienceEntry(role="DS Intern", company="Post", duration="2024",
            bullets=["Cleaned 150K+ NLP records, improving quality by 30%."]),
    ],
    projects=[],
)
jd = ExtractedJD(
    job_title="Data Scientist", company="TC",
    required_skills=["Python", "SQL", "Pandas", "Scikit-learn"],
    preferred_skills=[],
    keywords=["data science", "nlp"],
    raw_text="DS at TC",
)

import os
if os.path.exists("d:/Projects/job_ai_system/data/behavior_state.json"):
    os.remove("d:/Projects/job_ai_system/data/behavior_state.json")

s = ATSScorer()
r = pc.run_full_pipeline(original=resume, tailored=copy.deepcopy(resume),
    extracted_jd=jd, scorer=s, job_id="trace", mode="strict")

print(f"\nTOTAL CALLS: {call_n[0]}")
print("FINAL:")
for exp in r.improved.experience:
    for b in exp.bullets:
        flag = "❌" if "in in" in b else ("⚠️" if " in." in b else "✅")
        print(f"  {flag} {b}")
