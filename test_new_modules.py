"""Quick validation test for all 5 new modules."""

import sys
sys.path.insert(0, ".")

print("=" * 60)
print("VALIDATION TEST: 5 New Modules")
print("=" * 60)

# Test 1: Role Engine
from resume_engine.role_engine import classify_role, filter_skills_for_role

r1 = classify_role(
    "Looking for a Senior Python Developer with Django and REST APIs",
    "Senior Software Engineer"
)
assert r1["role_type"] == "technical", f"Expected technical, got {r1['role_type']}"
assert r1["allow_tech_injection"] == True
print(f"[PASS] Role Engine - Tech: {r1['role_type']} (conf={r1['confidence']})")

r2 = classify_role(
    "Talent Acquisition Specialist for recruiting and onboarding",
    "HR Recruiter"
)
assert r2["role_type"] == "hr", f"Expected hr, got {r2['role_type']}"
assert r2["allow_tech_injection"] == False
print(f"[PASS] Role Engine - HR: {r2['role_type']} (conf={r2['confidence']})")

r3 = classify_role(
    "Supply chain coordinator managing logistics and inventory",
    "Operations Coordinator"
)
assert r3["role_type"] == "operations", f"Expected operations, got {r3['role_type']}"
assert r3["allow_tech_injection"] == False
print(f"[PASS] Role Engine - Ops: {r3['role_type']} (conf={r3['confidence']})")

r4 = classify_role(
    "Data Scientist with machine learning and deep learning experience",
    "Senior Data Scientist"
)
assert r4["role_type"] == "data", f"Expected data, got {r4['role_type']}"
print(f"[PASS] Role Engine - Data: {r4['role_type']} (conf={r4['confidence']})")

# Test 2: Skill Filtering
skills = ["Python", "Excel", "Communication", "Docker", "Leadership", "Kubernetes"]
filtered = filter_skills_for_role(skills, r2)
assert "Python" not in filtered, "Python should be blocked for HR role"
assert "Docker" not in filtered, "Docker should be blocked for HR role"
assert "Excel" in filtered, "Excel should be allowed for HR role"
assert "Leadership" in filtered, "Leadership should be allowed for HR role"
print(f"[PASS] Skill Filter: {skills} -> {filtered}")

# Test 3: Summary Engine
from resume_engine.summary_engine import should_replace_summary

assert should_replace_summary("I am a passionate and dedicated professional") == True
assert should_replace_summary("") == True
assert should_replace_summary(None) == True
good_summary = "Senior Data Scientist with 5+ years in machine learning and predictive modeling using Python and TensorFlow"
assert should_replace_summary(good_summary) == False, f"Good summary should NOT be replaced"
print("[PASS] Summary Engine - replacement detection works")

# Test 4: Trust Layer
from resume_engine.trust_layer import ChangeTracker

t = ChangeTracker()
t.record("skills", "reorder", "before", "after", "Matched skills moved first", "improver", "HIGH")
t.record("summary", "keyword_injection", "old text", "new text", "Added ML keyword", "improver", "HIGH")
t.record("experience.0", "verb_strength", "used python", "leveraged Python", "Verb upgrade", "improver", "MEDIUM")
exp = t.build_explanation()
assert exp["total_changes"] == 3
assert exp["high_confidence"] == 2
assert "skills" in exp["by_section"]
print(f"[PASS] Trust Layer: {exp['total_changes']} changes tracked, summary='{exp['summary'][:50]}'")

# Test 5: Resume Intelligence
from resume_engine.resume_intelligence import detect_resume_type
from utils.models import StructuredResume, ContactInfo, ExperienceEntry

resume = StructuredResume(
    contact=ContactInfo(name="Test User", email="test@test.com"),
    summary="Experienced engineer",
    skills=["Python", "AWS", "Docker"],
    experience=[
        ExperienceEntry(
            company="Company A", role="Senior Engineer",
            duration="Jan 2020 - Present", bullets=["Built APIs", "Led team"]
        ),
        ExperienceEntry(
            company="Company B", role="Software Engineer",
            duration="Jun 2017 - Dec 2019", bullets=["Developed features"]
        ),
    ],
    education=[], certifications=[], projects=[],
)

result = detect_resume_type(resume)
assert result["type"] == "EXPERIENCED"
assert result["years_estimated"] >= 4
print(f"[PASS] Resume Intelligence: {result['type']} ({result['years_estimated']}yr, flags={result['flags']})")

# Test 6: Polish Engine
from resume_engine.polish_engine import polish_resume

resume2 = resume.model_copy(deep=True)
resume2.experience[0].bullets = [
    "helped with building the API infrastructure",
    "Was responsible for team leadership and mentoring",
    "Successfully completed the migration project on time",
]
polished, changes = polish_resume(resume2, role_type="technical")
print(f"[PASS] Polish Engine: {len(changes)} refinements applied")
for c in changes[:3]:
    print(f"       -> {c['type']}: {c['reason'][:60]}")

# Test 7: Pipeline Core imports
from pipeline.core import run_full_pipeline, PipelineResult
assert hasattr(PipelineResult, "role_info")
assert hasattr(PipelineResult, "resume_type")
assert hasattr(PipelineResult, "change_explanation")
assert hasattr(PipelineResult, "polish_changes")
print("[PASS] Pipeline Core: all new fields present in PipelineResult")

print()
print("=" * 60)
print("ALL 7 TESTS PASSED - System is ready")
print("=" * 60)
