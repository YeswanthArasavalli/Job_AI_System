"""Truth Gate adversarial tests (Phase 5A / spec section 45)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.models import (StructuredResume, ContactInfo, ExperienceEntry,
                          ProjectEntry, EducationEntry)
from pipeline.truth_gate import (validate_candidate_representation,
                                 check_metrics, TruthVerdict)

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, cond, detail))
    print(f"  {'PASS' if cond else 'FAIL'} {name} {detail}")


def base_resume():
    return StructuredResume(
        contact=ContactInfo(name="Alex Candidate", email="alex@example.com", phone="555-0100"),
        summary="Analyst.",
        skills=["Python", "SQL"],
        experience=[ExperienceEntry(
            role="Analyst", company="DataCorp", duration="2021-2024", location="Boston",
            bullets=["Built ETL pipelines processing 150K+ records."])],
        education=[EducationEntry(degree="BSc", institution="State College", year="2020")],
        projects=[ProjectEntry(name="P", bullets=["Used Python for scraping."])],
    )


# 1. identity: name change rejected
mod = base_resume(); mod.contact.name = "Someone Else"
v = validate_candidate_representation(base_resume(), mod)
check("identity_name_rejected", not v.accepted and "IDENTITY_NAME" in v.violations, v.violations)

# 2. identity: email change rejected
mod = base_resume(); mod.contact.email = "other@x.com"
v = validate_candidate_representation(base_resume(), mod)
check("identity_email_rejected", not v.accepted and "IDENTITY_EMAIL" in v.violations)

# 3. employer change rejected
mod = base_resume(); mod.experience[0].company = "OtherCorp"
v = validate_candidate_representation(base_resume(), mod)
check("employer_change_rejected", any(v.startswith("EMPLOYMENT_FACT_CHANGED") for v in v.violations))

# 4. title change rejected
mod = base_resume(); mod.experience[0].role = "Senior Engineer"
v = validate_candidate_representation(base_resume(), mod)
check("title_change_rejected", any("EMPLOYMENT_FACT_CHANGED" in x for x in v.violations))

# 5. date change rejected
mod = base_resume(); mod.experience[0].duration = "2020-2024"
v = validate_candidate_representation(base_resume(), mod)
check("date_change_rejected", any("EMPLOYMENT_FACT_CHANGED" in x for x in v.violations))

# 6. education change rejected
mod = base_resume(); mod.education[0].year = "2021"
v = validate_candidate_representation(base_resume(), mod)
check("education_change_rejected", "EDUCATION_CHANGED" in v.violations)

# 7. project -> employment conversion rejected (experience entry added)
mod = base_resume()
from utils.models import ExperienceEntry as EE
mod.experience.append(EE(role="Developer", company="WebWorks", duration="2022", bullets=["x"]))
v = validate_candidate_representation(base_resume(), mod)
check("project_to_employment_rejected", any("EMPLOYMENT_INFLATION" in x for x in v.violations))

# 8. unsupported skill rejected
mod = base_resume(); mod.skills = mod.skills + ["Kubernetes"]
v = validate_candidate_representation(base_resume(), mod, original_skills=["Python", "SQL"])
check("unsupported_skill_rejected", any("UNSUPPORTED_SKILL" in x for x in v.violations))

# 9. compound expansion accepted (python -> python (pandas))
mod = base_resume(); mod.skills = mod.skills + ["Python (pandas, numpy)"]
v = validate_candidate_representation(base_resume(), mod, original_skills=["Python", "SQL"])
check("compound_expansion_accepted", v.accepted and v.skills_ok, v.violations)

# 10. evidence-grounded skill accepted (grounded in project bullet text)
mod = base_resume(); mod.skills = mod.skills + ["Scraping"]
v = validate_candidate_representation(base_resume(), mod, original_skills=["Python", "SQL"])
check("evidence_grounded_skill_accepted", v.accepted, v.violations)

# 11. metric fabrication rejected
viol = check_metrics(["Built pipelines processing 150K+ records."],
                     ["Built pipelines processing 150K+ records, improving accuracy by 45%."])
check("metric_fabrication_rejected", len(viol) == 1 and "METRIC_FABRICATION" in viol[0], viol)

# 12. metric preservation accepted
viol = check_metrics(["Improved speed by 3x and accuracy by 92%."],
                     ["Improved speed by 3x, achieving 92% accuracy."])
check("metric_preservation_accepted", viol == [], viol)

failed = [r for r in RESULTS if not r[1]]
print(f"\nTruth Gate: {len(RESULTS)-len(failed)}/{len(RESULTS)} passed")
sys.exit(1 if failed else 0)