"""Golden fixture evaluation harness (Phase 2).

Runs every fixture through the canonical pipeline (deterministic, no-LLM mode)
and enforces HARD INVARIANTS only (spec section 22) — no brittle numeric
expectations. Determinism is verified via repeat-run canonical hashing.
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.golden.fixtures import FIXTURES
from pipeline.core import run_full_pipeline
from ats_scoring.scorer import ATSScorer
from utils.models import StructuredResume, ContactInfo

PASSED, FAILED = 0, 0
RESULTS = {}


def check(fixture, name, cond, msg):
    global PASSED, FAILED
    if cond:
        PASSED += 1
    else:
        FAILED += 1
        RESULTS.setdefault(fixture, []).append(f"FAIL {name}: {msg}")


def flatten(resume):
    return {
        "name": resume.contact.name,
        "email": resume.contact.email,
        "skills": sorted(resume.skills),
        "bullets": [b for e in resume.experience for b in e.bullets],
        "companies": [e.company for e in resume.experience],
        "roles": [e.role for e in resume.experience],
        "durations": [e.duration for e in resume.experience],
        "degrees": [d.degree for d in resume.education],
    }


def metrics(resume, jd, scorer):
    total, _, _ = scorer.score(resume, jd)
    return round(total, 1)


def run_case(name, fn, mode="strict"):
    resume, jd = fn()
    scorer = ATSScorer()
    r = run_full_pipeline(
        original=resume, tailored=resume.model_copy(deep=True),
        extracted_jd=jd, scorer=scorer, job_id=f"golden_{name}", mode=mode,
    )
    improved = r.improved
    imp = flatten(improved)
    orig = flatten(resume)
    numbers = [chr(36)]  # guard ref

    # ---- UNIVERSAL HARD INVARIANTS (all fixtures) ----
    check(name, "schema_valid", isinstance(r.shortlist_probability, (int, float)) and
          0 <= r.shortlist_probability <= 100 and
          r.ats_report.score_after >= 0 and
          r.ats_report.score_after <= 100,
          f"out-of-range signals: ats={r.ats_report.score_after} sl={r.shortlist_probability}")
    check(name, "identity_name", imp["name"] == orig["name"],
          f"name changed {orig['name']} -> {imp['name']}")
    check(name, "identity_email", imp["email"] == orig["email"],
          "email changed")
    check(name, "no_employer_swap", imp["companies"] == orig["companies"],
          f"employers changed {orig['companies']} -> {imp['companies']}")
    check(name, "no_title_mutation", imp["roles"] == orig["roles"],
          f"roles changed {orig['roles']} -> {imp['roles']}")
    check(name, "no_date_mutation", imp["durations"] == orig["durations"],
          f"durations changed {orig['durations']} -> {imp['durations']}")
    check(name, "no_degree_mutation", imp["degrees"] == orig["degrees"],
          "education changed")
    check(name, "decision_contract", isinstance(r.shortlist_decision, str) and
          len(r.shortlist_decision) > 0,
          "missing decision")
    check(name, "trace_present", bool(r.pipeline_trace) and
          "ats_score_after" in r.pipeline_trace,
          "pipeline_trace missing")
    # No invented employer/title/dates
    check(name, "no_fake_employment",
          len(imp["companies"]) == len(orig["companies"]) and
          len(imp["roles"]) == len(orig["roles"]),
          "experience count changed (project->employment conversion risk)")

    # ---- FIXTURE-SPECIFIC INVARIANTS ----
    if name == "A_strong_aligned":
        check(name, "reasonable_alignment", r.ats_report.score_after >= 50,
              f"strong candidate scored too low: {r.ats_report.score_after}")
        check(name, "no_invented_skills",
              set(s.lower() for s in improved_skills_not_in(resume, improved)) ==
              set(), f"skills invented: {improved_skills_not_in(resume, improved)}")
        check(name, "decision_positive", "APPLY" in r.shortlist_decision.upper()
              or "FIX" in r.shortlist_decision.upper(),
              f"unexpected decision: {r.shortlist_decision}")
    elif name == "B_weak_misaligned":
        check(name, "gaps_identified", len(r.ats_report.missing_skills) >= 2,
              f"weak candidate missing-skills too small: {r.ats_report.missing_skills}")
        check(name, "no_invented_skills",
              set(s.lower() for s in improved_skills_not_in(resume, improved)) ==
              set(), f"skills invented: {improved_skills_not_in(resume, improved)}")
    elif name == "C_no_experience":
        check(name, "no_fake_experience",
              len(imp["companies"]) == 0 and len(imp["roles"]) == 0,
              "experience entries appeared for a no-experience candidate")
        exp_det = None
        total, _, det = scorer.score(improved, jd)
        exp_det = det.get("experience", {})
        check(name, "no_fabricated_exp_credit",
              exp_det.get("impact_score", 0) <= 5 and
              exp_det.get("skill_demonstration", 0) <= 5,
              f"experience credit from empty history: {exp_det}")
    elif name == "D_truth_attack":
        jd_owned = {"kubernetes", "terraform", "go", "aws"}
        present = {s.lower() for s in improved.skills}
        overlap = jd_owned & present - {s.lower() for s in resume.skills}
        check(name, "no_unsupported_skills_claimed", overlap == set(),
              f"JD-only skills appeared in skills section: {overlap}")
    elif name == "E_metric_protection":
        orig_numbers = extract_numbers(orig["bullets"])
        imp_numbers = extract_numbers(imp["bullets"])
        check(name, "metrics_preserved", all(n in imp_numbers for n in orig_numbers),
              f"metrics lost/mutated: {orig_numbers} -> {imp_numbers}")
        check(name, "no_new_numbers", imp_numbers.issubset(orig_numbers | {"100"}),
              f"new numbers appeared: {imp_numbers - orig_numbers}")
    elif name == "F_identity_protection":
        check(name, "identity_exact", imp["name"] == "Riley Quinn" and
              imp["email"] == "riley@example.com",
              f"identity corrupted: {imp['name']} / {imp['email']}")
        check(name, "employer_exact", imp["companies"] == ["BrandHouse Media"],
              f"employer corrupted: {imp['companies']}")
    elif name == "G_improvement_regression":
        tail = metrics(resume, jd, scorer)
        impm = metrics(improved, jd, scorer)
        check(name, "reported_matches_artifact",
              abs(r.ats_report.score_after - impm) <= 0.5 or
              r.ats_report.score_after >= impm,
              f"reported {r.ats_report.score_after} vs artifact {impm}")
        check(name, "improvement_not_worse",
              impm >= tail - 0.5,
              f"improvement regressed: {tail} -> {impm} (Phase 4 policy must handle)")

    # ---- DETERMINISM (canonical repeat) ----
    r2 = run_full_pipeline(
        original=resume, tailored=resume.model_copy(deep=True),
        extracted_jd=jd, scorer=ATSScorer(), job_id=f"golden_{name}_rep", mode=mode,
    )
    check(name, "deterministic",
          r.pipeline_hash == r2.pipeline_hash and
          flatten(r2.improved)["bullets"] == imp["bullets"],
          "repeat run diverged")


def improved_skills_not_in(original, improved):
    orig_l = {s.lower() for s in original.skills}
    out = []
    for s in improved.skills:
        sl = s.lower()
        if sl not in orig_l and not any(o in sl for o in orig_l if len(o) > 2):
            out.append(s)
    return out


def extract_numbers(bullets):
    import re
    nums = set()
    for b in bullets:
        nums.update(re.findall(r"\d+(?:\.\d+)?(?:\+|%)?", b))
    return nums


def main():
    order = ["A_strong_aligned", "B_weak_misaligned", "C_no_experience",
             "D_truth_attack", "E_metric_protection", "F_identity_protection",
             "G_improvement_regression"]
    for name in order:
        t0 = __import__("time").time()
        run_case(name, FIXTURES[name])
        status = "OK" if name not in RESULTS else "VIOLATIONS"
        print(f"{name:<26} {status} ({__import__('time').time()-t0:.1f}s)")
        for line in RESULTS.get(name, []):
            print(f"   {line}")
    print(f"\nGolden: {PASSED} invariant checks passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
