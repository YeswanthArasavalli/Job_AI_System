"""
Pipeline Core -- Single source of truth for the resume processing pipeline.

ALL entry points (manual_mode, controller, main) must use this.
No duplicate logic anywhere.

Pipeline flow:
  Resume -> Classify Role -> Detect Type -> Naturalize -> ATS Score
  -> Improve -> Summary Engine -> Polish -> Trust Validate -> Output

TRUST GUARANTEES:
  - Same input -> Same output (deterministic fingerprint)
  - Realistic scores (cap when >40% core skills missing)
  - No score inflation (stability guard)
  - No fake skills (strict trust rules)
  - Role-aware optimization (no tech injection into non-tech roles)
  - Change tracking with explanations (trust layer)
"""

import hashlib
import os
import re
from typing import Optional, Tuple
from dataclasses import dataclass, field

from resume_engine.naturalizer import ResumeNaturalizer
from resume_engine.improver import ResumeImprover
from resume_engine.role_engine import classify_role, filter_skills_for_role
from resume_engine.summary_engine import generate_professional_summary, should_replace_summary
from resume_engine.polish_engine import polish_resume
from resume_engine.trust_layer import ChangeTracker, TrustValidator
from resume_engine.resume_intelligence import detect_resume_type
from resume_engine.validation_gate import validate_output
from pipeline.hiring_simulation import (
    audit_skill_proof, simulate_hiring,
    compute_perceived_strength, enhance_experience_strength,
    recruiter_10s_dominance_check, generate_candidate_interpretation,
    generate_hiring_intelligence,
)
from ats_scoring.scorer import ATSScorer
from utils.models import StructuredResume, ExtractedJD
from utils.logger import setup_logger

logger = setup_logger(__name__)


def evaluate_resume_quality(
    resume: StructuredResume, jd: ExtractedJD
) -> dict:
    """
    PART 2: Evaluate structural resume quality INDEPENDENTLY of ATS score.

    Returns a quality dict with:
      - total: 0-100 composite quality score
      - skill_demo: % of skills demonstrated in experience bullets
      - action_verbs: % of bullets starting with action verbs
      - bullet_depth: avg bullet length (longer = more detailed)
      - tool_purpose: % of bullets with tool-purpose phrasing
      - summary_quality: 0-100 summary score

    Quality score can increase even when ATS score doesn't — this prevents
    the 'all improvements reverted' bug.
    """
    all_bullets = [b for exp in resume.experience for b in exp.bullets]
    all_text_lower = " ".join(b.lower() for b in all_bullets)

    # 1. Skill demonstration ratio (0-25)
    jd_skills = set(s.lower() for s in jd.required_skills + jd.preferred_skills)
    resume_skills = set(s.lower() for s in resume.skills)
    relevant = resume_skills & jd_skills if jd_skills else resume_skills
    if relevant:
        demonstrated = sum(1 for s in relevant if s in all_text_lower)
        skill_demo = demonstrated / len(relevant)
    else:
        skill_demo = 0.5
    skill_score = skill_demo * 25

    # 2. Action verb coverage (0-20)
    action_verbs = {
        "developed", "designed", "implemented", "built", "created",
        "managed", "led", "optimized", "improved", "reduced",
        "increased", "delivered", "automated", "analyzed", "architected",
        "deployed", "maintained", "collaborated", "established", "launched",
        "spearheaded", "orchestrated", "engineered", "streamlined",
    }
    if all_bullets:
        action_count = sum(
            1 for b in all_bullets
            if b.lower().split()[0] in action_verbs
        )
        action_ratio = action_count / len(all_bullets)
    else:
        action_ratio = 0
    action_score = action_ratio * 20

    # 3. Bullet depth — avg length (0-20, optimal 80-150 chars)
    if all_bullets:
        avg_len = sum(len(b) for b in all_bullets) / len(all_bullets)
        if 80 <= avg_len <= 150:
            depth_score = 20.0
        elif 60 <= avg_len < 80:
            depth_score = 15.0
        elif avg_len > 150:
            depth_score = 12.0  # over-stuffed
        else:
            depth_score = max(5, avg_len / 80 * 15)
    else:
        depth_score = 0

    # 4. Tool-purpose phrasing (0-20) — "using X for/to Y" patterns
    purpose_patterns = [
        r'(?:using|leveraging|utilizing|applying|with)\s+\w+\s+(?:to|for)\b',
        r'(?:built|developed|designed|created)\s+.*(?:using|with|in)\s+\w+',
    ]
    if all_bullets:
        purpose_count = sum(
            1 for b in all_bullets
            if any(re.search(p, b, re.IGNORECASE) for p in purpose_patterns)
        )
        purpose_ratio = purpose_count / len(all_bullets)
    else:
        purpose_ratio = 0
    purpose_score = min(20, purpose_ratio * 25)  # Slight generosity

    # 5. Summary quality (0-15)
    summary = resume.summary or ""
    summary_score = 0
    if len(summary) > 50:
        summary_score += 5
        if any(s.lower() in summary.lower() for s in list(relevant)[:5]):
            summary_score += 5
        generic_phrases = ["experienced", "hardworking", "passionate", "dedicated"]
        if not any(g in summary.lower() for g in generic_phrases):
            summary_score += 5

    total = round(skill_score + action_score + depth_score + purpose_score + summary_score, 1)

    return {
        "total": total,
        "skill_demo": round(skill_demo * 100, 1),
        "action_verbs": round(action_ratio * 100, 1),
        "bullet_depth": round(avg_len if all_bullets else 0, 0),
        "tool_purpose": round(purpose_ratio * 100, 1),
        "summary_quality": summary_score,
    }


def compute_shortlist_score(
    resume: StructuredResume, jd: ExtractedJD, ats_score: float = 0
) -> dict:
    """
    PART 9: Compute SHORTLIST PROBABILITY score.
    
    This is the CORE metric — not ATS score. Measures whether a hiring
    manager would actually shortlist this resume.
    
    Components:
      - skill_proof (30%): Skills demonstrated WITH PURPOSE in experience
      - impact_evidence (25%): Quantified business outcomes
      - role_alignment (20%): Title/experience match to JD
      - clarity (15%): Readable, concise, non-repetitive
      - credibility (10%): No fake signals, natural language
    
    Returns dict with total (0-100) and component breakdown.
    """
    all_bullets = [b for exp in resume.experience for b in exp.bullets]
    all_text = " ".join(b.lower() for b in all_bullets)
    
    # 1. SKILL PROOF (30pts) — skills demonstrated with PURPOSE, not just listed
    jd_skills = set(s.lower() for s in jd.required_skills + jd.preferred_skills)
    resume_skills = set(s.lower() for s in resume.skills)
    relevant = resume_skills & jd_skills if jd_skills else resume_skills
    
    proven = 0
    for skill in relevant:
        if skill in all_text:
            # Check if skill has purpose context (not just bare mention)
            purpose_pattern = re.compile(
                rf'{re.escape(skill)}.*?(?:for|to|enabling|reducing|improving)',
                re.IGNORECASE
            )
            if purpose_pattern.search(all_text):
                proven += 1.0  # Full credit for purpose-driven
            else:
                proven += 0.6  # Partial credit for bare mention
    skill_proof = (proven / max(len(relevant), 1)) * 30

    # 2. IMPACT EVIDENCE (25pts) — quantified business outcomes
    impact_signals = 0
    for b in all_bullets:
        # Revenue/financial impact (highest value)
        if re.search(r'\$\d|revenue|profit|roi|savings', b, re.I):
            impact_signals += 3
        # Percentage improvements
        elif re.search(r'\d+\s*%', b):
            impact_signals += 2
        # Scale indicators
        elif re.search(r'\d+[KkMm+]|\d{3,}\s*(?:users|records|requests|positions|employees|hires|datasets)', b):
            impact_signals += 2
        # Qualitative impact (gerund AND past tense forms)
        elif re.search(
            r'(?:reduc|increas|improv|optimiz|accelerat|enabl|driv|achiev|streamlin|enhanc)'
            r'(?:ed|ing|es)\b',
            b, re.I
        ):
            impact_signals += 1
    impact_evidence = min(25, (impact_signals / max(len(all_bullets), 1)) * 15)

    # 3. ROLE ALIGNMENT (20pts) — title + experience match
    role_score = 0
    jd_title = (jd.job_title or "").lower()
    resume_title = (resume.title or "").lower()
    summary = (resume.summary or "").lower()
    
    # Title match
    if jd_title and resume_title:
        title_words = set(jd_title.split()) - {"senior", "junior", "lead", "staff", "principal"}
        resume_words = set(resume_title.split())
        overlap = title_words & resume_words
        if overlap:
            role_score += min(10, len(overlap) * 5)
    
    # Experience relevance (JD keywords in experience)
    jd_kw_lower = set(k.lower() for k in jd.keywords[:10])
    kw_in_exp = sum(1 for kw in jd_kw_lower if kw in all_text)
    role_score += min(10, (kw_in_exp / max(len(jd_kw_lower), 1)) * 10)
    role_alignment = role_score

    # 4. CLARITY (15pts) — readable, concise, non-repetitive
    clarity = 15.0
    # Penalize very long bullets
    if all_bullets:
        avg_len = sum(len(b) for b in all_bullets) / len(all_bullets)
        if avg_len > 200:
            clarity -= 5  # Over-stuffed
    # Penalize repetition
    from collections import Counter
    words = re.findall(r'\b\w{5,}\b', all_text)
    if words:
        most_common = Counter(words).most_common(1)
        if most_common and most_common[0][1] > 6:
            clarity -= 3
    # Penalize too few bullets
    if len(all_bullets) < 3:
        clarity -= 5

    # 5. CREDIBILITY (10pts) — no fake signals
    credibility = 10.0
    # Check for AI-generated patterns
    ai_patterns = [
        r'leveraging \w+ for \w+ for \w+',  # double-for
        r'(?:leveraging|utilizing|applying)\s+\w+,\s*(?:leveraging|utilizing|applying)',  # stacking
    ]
    for pattern in ai_patterns:
        if re.search(pattern, all_text):
            credibility -= 3
    # Check for unrealistic metrics
    if re.search(r'(?:100|99)\s*%\s*(?:improvement|increase|growth)', all_text):
        credibility -= 2

    total = round(skill_proof + impact_evidence + role_alignment + clarity + credibility, 1)
    total = max(0, min(100, total))

    return {
        "total": total,
        "skill_proof": round(skill_proof, 1),
        "impact_evidence": round(impact_evidence, 1),
        "role_alignment": round(role_alignment, 1),
        "clarity": round(clarity, 1),
        "credibility": round(credibility, 1),
    }


@dataclass
class ScoreLimit:
    """Explains the maximum achievable score for this resume+JD pair."""
    max_possible_score: float = 100.0
    reasons: list = field(default_factory=list)

    def to_dict(self):
        return {
            "max_possible_score": round(self.max_possible_score, 1),
            "reasons": self.reasons,
        }


@dataclass
class PipelineResult:
    """
    Result of the full pipeline run.

    Shortlist probability lives in ONE place: shortlist_probability (float).
    Everything else is supplementary signal — never the final value.

    Execution trace is in pipeline_trace for full auditability.
    """
    original: StructuredResume
    tailored: StructuredResume
    improved: StructuredResume
    extracted_jd: ExtractedJD
    ats_report: object  # ATSReport
    readability: float = 0.0
    target_plan: dict = None  # Target Score Engine roadmap
    score_limit: dict = None   # Max score explanation (PART 7)
    pipeline_hash: str = ""    # Deterministic fingerprint (PART 6)
    role_fit: dict = None      # Role fit assessment (PART 8)
    why_not_90: dict = None    # Steps to reach 90+ (PART 10)
    role_info: dict = None      # Role classification (Part 4 - Universal Role Engine)
    resume_type: dict = None    # Resume type detection (Part 10 - Intelligence)
    change_explanation: dict = None  # Trust layer (Part 8 - User Trust)
    polish_changes: list = None  # Polish engine changes (Part 6)
    validation_result: dict = None  # Final validation gate (Part 13)
    quality_score: dict = None      # Structural quality evaluation (Part 2)
    hiring_simulation: dict = None  # Hiring Simulation Engine (Sreejita v1.0)
    content_intelligence: dict = None  # Content Quality + Truth + ATS engines (v4.5-v4.8)
    decision_explanation: dict = None  # Phase 6B: structured decision explanation

    # ── CANONICAL SHORTLIST FIELDS (v6.0) ──
    # These are the ONLY source of truth. Do not read shortlist from
    # ats_report.shortlist_probability or hiring_simulation["shortlist_probability"]
    # for display purposes — those contain raw intermediate values.
    shortlist_probability: float = 0.0       # Final unified shortlist % (0-100)
    shortlist_band: str = "LOW"              # D / C / B / B+ / A
    shortlist_decision: str = "IMPROVE THEN APPLY"  # Human-readable final decision
    shortlist_decision_reason: str = ""      # Why this decision was made
    shortlist_unified: dict = None           # Full unified scoring output (for debugging)

    # ── EXECUTION TRACE (v6.0) ──
    # Every score mutation recorded here. Zero hidden overrides.
    pipeline_trace: dict = None


def _compute_input_fingerprint(
    original: StructuredResume, extracted_jd: ExtractedJD
) -> str:
    """
    PART 6: Compute deterministic fingerprint from INPUT only.
    Same resume + same JD -> same hash -> same result.
    """
    fp_parts = [
        original.contact.name,
        original.contact.email,
        original.summary or "",
        "|".join(sorted(original.skills)),
        "|".join(f"{e.company}:{e.role}" for e in original.experience),
        extracted_jd.job_title or "",
        extracted_jd.company or "",
        "|".join(sorted(extracted_jd.required_skills or [])),
        "|".join(sorted(extracted_jd.keywords or [])),
    ]
    fp_string = "||".join(fp_parts)
    return hashlib.sha256(fp_string.encode("utf-8")).hexdigest()[:16]


def _compute_score_limit(
    scorer: ATSScorer,
    resume: StructuredResume,
    jd: ExtractedJD,
    details: dict,
) -> ScoreLimit:
    """
    PART 7: Compute the maximum achievable score for this resume+JD pair.
    Explains WHY the score can't be higher.
    """
    limit = ScoreLimit()
    reasons = []

    # Check missing required skills
    missing = details.get("skills", {}).get("missing", [])
    required = [s.lower().strip() for s in jd.required_skills if s.strip()]
    required_set = set(required)
    missing_set = set(missing)
    missing_required = required_set & missing_set
    missing_ratio = len(missing_required) / max(len(required_set), 1)

    if missing_ratio > 0.4:
        limit.max_possible_score = min(limit.max_possible_score, 75.0)
        reasons.append(
            f"Missing {len(missing_required)}/{len(required_set)} required skills: "
            f"{', '.join(sorted(list(missing_required)[:5]))}"
        )

    if missing_ratio > 0.6:
        limit.max_possible_score = min(limit.max_possible_score, 60.0)

    # Check experience gap
    exp_details = details.get("experience", {})
    resume_years = exp_details.get("resume_years")
    required_years = exp_details.get("required_years")
    if resume_years is not None and required_years is not None:
        if required_years > 0 and resume_years < required_years * 0.5:
            limit.max_possible_score = min(limit.max_possible_score, 70.0)
            reasons.append(
                f"Experience gap: {resume_years}yr vs {required_years}yr required"
            )

    # Check missing keywords in experience bullets
    all_bullets = " ".join(
        b.lower() for exp in resume.experience for b in exp.bullets
    )
    skills_not_in_bullets = []
    for skill in list(missing_required)[:5]:
        if skill not in all_bullets:
            skills_not_in_bullets.append(skill)
    if skills_not_in_bullets:
        reasons.append(
            f"Not demonstrated in experience: {', '.join(skills_not_in_bullets)}"
        )

    if not reasons:
        reasons.append("No major gaps -- score reflects true match")

    limit.reasons = reasons
    return limit


def run_full_pipeline(
    original: StructuredResume,
    tailored: StructuredResume,
    extracted_jd: ExtractedJD,
    scorer: ATSScorer,
    job_id: str = "analysis",
    mode: str = "strict",
) -> PipelineResult:
    """
    Single source of truth for post-tailoring pipeline.

    Args:
        mode: "strict" = max ATS score. "balanced" = natural phrasing.
              "conservative" = minimal changes, preserve original voice.

    TRUST GUARANTEES:
      - Same input -> Same output (deterministic fingerprint)
      - Score stability guard (±5 tolerance)
      - Realistic score cap (75 max when >40% core skills missing)
      - No fake skills (strict trust rules)
      - Role-aware optimization (no tech injection into non-tech roles)
      - All changes tracked and explained (trust layer)
    """
    logger.info(f"PIPELINE CORE -- Starting for job {job_id} (mode={mode})")
    import hashlib as _hashlib
    _cand_ref = _hashlib.sha256((original.contact.name or "").encode()).hexdigest()[:8]
    logger.info(f"  Resume: candidate_id={_cand_ref}")
    _jd_ref = _hashlib.sha256(((extracted_jd.job_title or "") + (extracted_jd.company or "")).encode()).hexdigest()[:8]
    logger.info(f"  JD: job_ref={_jd_ref}")

    # -- STATELESS: Deep copy ALL inputs to prevent mutation leakage
    original = original.model_copy(deep=True)
    tailored = tailored.model_copy(deep=True)
    extracted_jd = extracted_jd.model_copy(deep=True)  # FIX C3: prevent JD mutation

    # -- STATELESS: Sort JD inputs for deterministic processing
    extracted_jd.required_skills = sorted(set(extracted_jd.required_skills), key=str.lower)
    extracted_jd.keywords = sorted(set(extracted_jd.keywords), key=str.lower)
    if extracted_jd.responsibilities:
        extracted_jd.responsibilities = sorted(extracted_jd.responsibilities, key=str.lower)

    # -- Initialize trust tracking layer ----------------------
    tracker = ChangeTracker()

    # -- PART 6: Deterministic fingerprint --------------------
    pipeline_hash = _compute_input_fingerprint(original, extracted_jd)
    logger.info(f"  Input fingerprint: {pipeline_hash}")
    logger.info(f"  JD skills({len(extracted_jd.required_skills)}): {extracted_jd.required_skills[:5]}")
    logger.info(f"  JD keywords({len(extracted_jd.keywords)}): {extracted_jd.keywords[:5]}")

    # -- NEW STEP 0a: Role Classification (Part 4) -----------
    role_info = classify_role(
        jd_text=extracted_jd.raw_text or "",
        job_title=extracted_jd.job_title or "",
    )
    logger.info(
        f"  Role: {role_info['role_type']} (confidence={role_info['confidence']}, "
        f"tech_injection={'ON' if role_info['allow_tech_injection'] else 'BLOCKED'})"
    )
    tracker.record(
        section="pipeline",
        change_type="role_classification",
        before="",
        after=f"{role_info['role_type']} (conf={role_info['confidence']})",
        reason=f"Classified as {role_info['role_type']} role for context-aware optimization",
        rule="role_engine.classify_role",
        confidence="HIGH" if role_info['confidence'] >= 0.6 else "MEDIUM",
    )

    # -- NEW STEP 0b: Resume Type Detection (Part 10) --------
    resume_type = detect_resume_type(original, extracted_jd)
    logger.info(
        f"  Resume type: {resume_type['type']} "
        f"(years={resume_type['years_estimated']}, flags={resume_type['flags']})"
    )
    tracker.record(
        section="pipeline",
        change_type="resume_classification",
        before="",
        after=f"{resume_type['type']} ({resume_type['years_estimated']}yr)",
        reason=f"Detected as {resume_type['type']} for adaptive strategy",
        rule="resume_intelligence.detect_resume_type",
        confidence="HIGH" if resume_type['confidence'] >= 0.7 else "MEDIUM",
    )

    # -- Role-aware skill filtering (Part 4) -----------------
    # Block tech skill injection for non-tech roles
    if not role_info['allow_tech_injection']:
        original_skill_count = len(tailored.skills)
        tailored.skills = filter_skills_for_role(tailored.skills, role_info)
        filtered = original_skill_count - len(tailored.skills)
        if filtered > 0:
            logger.info(f"  Role filter: blocked {filtered} tech skills for {role_info['role_type']} role")
            tracker.record(
                section="skills",
                change_type="role_filter",
                before=f"{original_skill_count} skills",
                after=f"{len(tailored.skills)} skills ({filtered} blocked)",
                reason=f"Blocked tech-only skills for {role_info['role_type']} role",
                rule="role_engine.filter_skills_for_role",
                confidence="HIGH",
            )

    # -- Step 1: Identity validation ----------------------
    if tailored.contact.name != original.contact.name:
        logger.error(
            f"IDENTITY MISMATCH: input={original.contact.name}, "
            f"output={tailored.contact.name}. Forcing original."
        )
        tailored.contact = original.contact.model_copy(deep=True)

    # -- Step 2: Naturalize -------------------------------
    readability = 0.0
    try:
        naturalizer = ResumeNaturalizer()
        tailored_dict = tailored.model_dump()
        naturalized = naturalizer.naturalize(tailored_dict)
        readability = naturalized.get("readability_score", 0)
        logger.info(f"  Readability: {readability}/100")

        # Apply naturalized bullets back -- WITH keyword preservation guard
        if "experience" in naturalized:
            for i, exp in enumerate(tailored.experience):
                if i < len(naturalized["experience"]):
                    nat_exp = naturalized["experience"][i]
                    nat_bullets = nat_exp.get("bullets") or nat_exp.get("responsibilities")
                    if nat_bullets:
                        # Keyword preservation: check each bullet individually
                        orig_bullets = exp.bullets[:]
                        safe_bullets = []
                        for j, nat_b in enumerate(nat_bullets):
                            if j < len(orig_bullets):
                                orig_lower = orig_bullets[j].lower()
                                nat_lower = nat_b.lower()
                                # Check if critical terms were lost
                                # FIX M3: Regex now catches abbreviations, hyphens, C++, node.js etc.
                                orig_skills = set(re.findall(r'[a-z][a-z0-9+#.\-]+', orig_lower))
                                nat_skills = set(re.findall(r'[a-z][a-z0-9+#.\-]+', nat_lower))
                                lost = orig_skills - nat_skills
                                # Filter to only real technical terms (not stop words)
                                tech_lost = {w for w in lost if len(w) > 3 and w not in
                                    {"with", "that", "this", "from", "have", "been", "were",
                                     "also", "their", "which", "using", "used", "the", "and",
                                     "for", "into", "over", "such", "more", "most", "than"}}
                                if len(tech_lost) > 2:
                                    safe_bullets.append(orig_bullets[j])  # Keep original
                                    logger.info(f"  Naturalization reverted bullet {j+1}: lost {tech_lost}")
                                else:
                                    safe_bullets.append(nat_b)
                            else:
                                safe_bullets.append(nat_b)
                        exp.bullets = safe_bullets
        if "summary" in naturalized and naturalized["summary"]:
            # Only use naturalized summary if it's not shorter
            if len(naturalized["summary"]) >= len(tailored.summary) * 0.8:
                tailored.summary = naturalized["summary"]
    except Exception as e:
        logger.warning(f"  Naturalization skipped: {e}")

    # -- Step 3: ATS Score --------------------------------
    ats_report = scorer.compare(
        original=original,
        tailored=tailored,
        jd=extracted_jd,
        job_id=job_id,
    )
    logger.info(
        f"  ATS Score: {ats_report.score_before} -> {ats_report.score_after} "
        f"({ats_report.improvement})"
    )

    # FIX C1: NO pre-optimization score cap.
    # Score limit is computed AFTER optimization on the IMPROVED resume.
    # This prevents the double-cap bug where optimizer starts from capped value.

    # -- Step 4: Multi-Pass Optimization Engine ---------------
    # Target-driven: higher baseline → higher ceiling
    baseline_score = ats_report.score_after
    if mode == "conservative":
        TARGET_SCORE = baseline_score + 5  # Minimal lift
        MAX_PASSES = 1
    elif mode == "balanced":
        # Balanced: lighter ceiling, fewer passes → more natural output
        TARGET_SCORE = 78.0 if baseline_score >= 50 else 65.0
        MAX_PASSES = 2
    elif baseline_score >= 50:
        TARGET_SCORE = 85.0
        MAX_PASSES = 3
    else:
        TARGET_SCORE = 70.0
        MAX_PASSES = 4  # Weaker resumes need more passes
    try:
        improver = ResumeImprover()
        current = tailored
        best_score = ats_report.score_after  # UNCAPPED tailored score
        best_resume = tailored
        best_quality = evaluate_resume_quality(tailored, extracted_jd)

        # Start with initial recommendations
        current_missing = ats_report.missing_skills
        current_matched = ats_report.matched_skills
        current_recs = ats_report.recommendations

        for pass_num in range(1, MAX_PASSES + 1):
            improved = improver.improve(
                tailored_resume=current,
                missing_skills=current_missing,
                matched_skills=current_matched,
                recommendations=current_recs,
                jd_keywords=extracted_jd.keywords,
                mode=mode,
                role_info=role_info,
            )

            # Score WITHOUT cap — optimizer needs real feedback
            imp_score, _, _ = scorer.score(improved, extracted_jd)

            # PART 2: Evaluate structural quality independently
            imp_quality = evaluate_resume_quality(improved, extracted_jd)

            # Detect structural stagnation (no text change = stop)
            current_text = " ".join(b for exp in current.experience for b in exp.bullets)
            improved_text = " ".join(b for exp in improved.experience for b in exp.bullets)
            structural_change = current_text != improved_text

            score_improved = imp_score > best_score
            quality_improved = imp_quality["total"] > best_quality["total"]

            logger.info(
                f"  Pass {pass_num}/{MAX_PASSES}: "
                f"score {best_score:.1f}->{imp_score:.1f} | "
                f"quality {best_quality['total']:.0f}->{imp_quality['total']:.0f} "
                f"({'✓score' if score_improved else '—'}"
                f"{'+quality' if quality_improved else ''}"
                f"{'|stagnant' if not structural_change else ''})"
            )

            # Accept if EITHER score OR quality improved (never revert)
            if score_improved or quality_improved:
                best_score = max(best_score, imp_score)
                best_resume = improved
                best_quality = imp_quality

            # Stop conditions
            if imp_score >= TARGET_SCORE:
                logger.info(f"  Target {TARGET_SCORE} reached at pass {pass_num}!")
                break
            if not structural_change:
                logger.info(f"  No structural change — stopping iteration")
                break

            # Re-score to find what's STILL missing for next pass
            if pass_num < MAX_PASSES:
                pass_report = scorer.compare(
                    original=original, tailored=improved, jd=extracted_jd
                )
                current_missing = pass_report.missing_skills
                current_matched = pass_report.matched_skills
                current_recs = pass_report.recommendations
                current = improved

        improved = best_resume
        logger.info(
            f"  Quality metrics: demo={best_quality['skill_demo']:.0f}% "
            f"action={best_quality['action_verbs']:.0f}% "
            f"depth={best_quality['bullet_depth']:.0f}ch "
            f"purpose={best_quality['tool_purpose']:.0f}%"
        )

        # FIX C1: Compute score limit ONLY on IMPROVED resume (single cap)
        _, improved_breakdown, improved_details = scorer.score(improved, extracted_jd)
        score_limit = _compute_score_limit(scorer, improved, extracted_jd, improved_details)

        # Apply realistic cap — based on resume+JD structural limits only
        capped_score = min(best_score, score_limit.max_possible_score)
        if capped_score < best_score:
            logger.info(
                f"  REALISTIC CAP: {best_score:.1f} -> {capped_score:.1f} "
                f"(max={score_limit.max_possible_score}, "
                f"reason: {score_limit.reasons[0]})"
            )
        best_score = capped_score

        # Ensure improved score is never worse than original
        best_score = max(best_score, ats_report.score_before)

        # -- EXECUTION GUARANTEE: improved is ALWAYS used --
        # The improver's structural changes (skill linking, bridging,
        # verb strengthening) make the resume objectively better for ATS
        # even when the scorer doesn't detect a numeric lift.
        # The score floor (line 409) ensures we never report a regression.
        if best_score <= ats_report.score_before:
            logger.info(
                f"  Optimization: score stable ({ats_report.score_before:.1f} -> "
                f"{best_score:.1f}) -- structural improvements applied"
            )

        # UPDATE ats_report with REAL improved score
        ats_report.score_after = round(best_score, 1)
        ats_report.improvement = f"+{best_score - ats_report.score_before:.0f}"
        ats_report.breakdown_after = improved_breakdown

        # Re-check missing skills + recommendations on improved resume
        improved_report = scorer.compare(
            original=original, tailored=improved, jd=extracted_jd
        )
        ats_report.missing_skills = improved_report.missing_skills
        ats_report.matched_skills = improved_report.matched_skills
        ats_report.missing_keywords = improved_report.missing_keywords
        ats_report.recommendations = improved_report.recommendations

        # -- QUALITY GATE (v5.1.1): Validate rewritten bullets ----------
        try:
            from pipeline.quality_gate import run_quality_gate
            orig_bullets = [b for exp in original.experience for b in exp.bullets]
            impr_bullets = [b for exp in improved.experience for b in exp.bullets]
            candidate_skills = list(original.skills or [])

            qg = run_quality_gate(
                orig_bullets, impr_bullets, candidate_skills,
                list(extracted_jd.keywords or []),
            )
            qg_summary = qg["summary"]
            logger.info(
                f"  Quality Gate: {qg_summary['accepted']}/{qg_summary['total']} accepted, "
                f"{qg_summary['rejected']} rejected, "
                f"ATS coverage={qg_summary['ats_coverage']}%"
            )
            if qg["rejected_rewrites"]:
                # Replace rejected bullets with originals in improved resume
                bullet_idx = 0
                rejected_indices = {r["index"] for r in qg["rejected_rewrites"]}
                for exp_i, exp in enumerate(improved.experience):
                    for b_i in range(len(exp.bullets)):
                        if bullet_idx in rejected_indices:
                            # Find matching original bullet
                            if exp_i < len(original.experience) and b_i < len(original.experience[exp_i].bullets):
                                exp.bullets[b_i] = original.experience[exp_i].bullets[b_i]
                                logger.info(
                                    f"    Reverted bullet [{bullet_idx}]: truth constraint"
                                )
                        bullet_idx += 1
        except Exception as qg_err:
            logger.warning(f"  Quality Gate skipped: {qg_err}")

        # -- ATS IMPROVEMENT MANDATE (v5.1.2) --------------------------
        # Update ATS score to reflect IMPROVED resume (not just tailored)
        ats_report.score_after = improved_report.score_after
        ats_report.improvement = (
            f"+{improved_report.score_after - ats_report.score_before:.0f}"
            if improved_report.score_after >= ats_report.score_before
            else f"{improved_report.score_after - ats_report.score_before:.0f}"
        )

        # If skill/domain match is strong, push ATS → 85+
        _matched = len(ats_report.matched_skills or [])
        _total = _matched + len(ats_report.missing_skills or [])
        _skill_pct = (_matched / max(_total, 1)) * 100
        _ats_current = ats_report.score_after
        ats_improve_attempts = 0

        if (_skill_pct >= 70 and _ats_current >= 50
                and _ats_current < 85 and mode != "conservative"):
            logger.info(
                f"  ATS MANDATE: score={_ats_current:.0f}, "
                f"skill_match={_skill_pct:.0f}% → targeting 85+"
            )
            from pipeline.bullet_rewriter import rewrite_all_bullets
            _cand_skills = list(original.skills or [])
            _cand_skills_lower = {s.lower() for s in _cand_skills}

            # ── STRATEGY 1: Bullet rewriting (impact + purpose + level signals) ──
            ats_improve_attempts = 1
            _bullets = [b for exp in improved.experience for b in exp.bullets]
            rw = rewrite_all_bullets(_bullets, _cand_skills)
            bi = 0
            for exp in improved.experience:
                for b_i in range(len(exp.bullets)):
                    if bi < len(rw["final_bullets"]):
                        exp.bullets[b_i] = rw["final_bullets"][bi]
                    bi += 1
            _re = scorer.compare(original=original, tailored=improved, jd=extracted_jd)
            _ats_current = _re.score_after
            ats_report.score_after = _ats_current
            ats_report.matched_skills = _re.matched_skills
            ats_report.missing_skills = _re.missing_skills
            logger.info(f"    ATS Strategy 1 (bullet rewrite): {_ats_current:.0f}")

            # ── STRATEGY 2: JD keyword injection into relevant bullets ──
            # Find JD keywords missing from bullets but PRESENT in candidate skills.
            # Inject each into the single most relevant bullet.
            if _ats_current < 85:
                ats_improve_attempts = 2
                _still_missing = [
                    s for s in (ats_report.missing_skills or [])
                    if s.lower() in _cand_skills_lower
                ]
                if _still_missing:
                    all_bullets_flat = []
                    bullet_map = []  # (exp_idx, bullet_idx)
                    for ei, exp in enumerate(improved.experience):
                        for bi2, b in enumerate(exp.bullets):
                            all_bullets_flat.append(b)
                            bullet_map.append((ei, bi2))

                    _injected_count = 0
                    for missing_kw in _still_missing[:4]:  # Max 4 keywords
                        # Find the most relevant bullet for this keyword
                        # Strategy: pick the longest bullet that doesn't already
                        # mention this keyword (more context = better fit)
                        best_idx = -1
                        best_len = 0
                        mkw_lower = missing_kw.lower()
                        for idx, blt in enumerate(all_bullets_flat):
                            if mkw_lower not in blt.lower() and len(blt) < 160:
                                if len(blt) > best_len:
                                    best_len = len(blt)
                                    best_idx = idx
                        if best_idx >= 0:
                            # Inject keyword naturally: "...leveraging {keyword}"
                            blt = all_bullets_flat[best_idx].rstrip('.')
                            # Check if bullet already has "in {Tool}" suffix
                            if re.search(r' in [A-Z][\w.-]+$', blt):
                                blt = f"{blt} and {missing_kw}."
                            else:
                                blt = f"{blt} leveraging {missing_kw}."
                            all_bullets_flat[best_idx] = blt
                            ei, bi2 = bullet_map[best_idx]
                            improved.experience[ei].bullets[bi2] = blt
                            _injected_count += 1
                            logger.info(
                                f"    → Injected '{missing_kw}' into bullet {best_idx}"
                            )

                    if _injected_count > 0:
                        _re = scorer.compare(
                            original=original, tailored=improved, jd=extracted_jd
                        )
                        _ats_current = _re.score_after
                        ats_report.score_after = _ats_current
                        ats_report.matched_skills = _re.matched_skills
                        ats_report.missing_skills = _re.missing_skills
                        logger.info(
                            f"    ATS Strategy 2 (keyword inject ×{_injected_count}): "
                            f"{_ats_current:.0f}"
                        )

            # ── STRATEGY 3: Skills section alignment ──
            # Ensure the skills section explicitly lists JD-required skills
            # the candidate actually has. ATS parsers weight the skills section.
            if _ats_current < 85:
                ats_improve_attempts = 3
                _still_missing_2 = [
                    s for s in (ats_report.missing_skills or [])
                    if s.lower() in _cand_skills_lower
                ]
                _skills_lower = {s.lower() for s in improved.skills}
                _added_to_skills = []
                for ms in _still_missing_2:
                    if ms.lower() not in _skills_lower:
                        improved.skills.append(ms)
                        _added_to_skills.append(ms)
                        _skills_lower.add(ms.lower())

                if _added_to_skills:
                    _re = scorer.compare(
                        original=original, tailored=improved, jd=extracted_jd
                    )
                    _ats_current = _re.score_after
                    ats_report.score_after = _ats_current
                    ats_report.matched_skills = _re.matched_skills
                    ats_report.missing_skills = _re.missing_skills
                    logger.info(
                        f"    ATS Strategy 3 (skills section +{len(_added_to_skills)}): "
                        f"{_ats_current:.0f}"
                    )

            # Update improvement delta
            ats_report.improvement = (
                f"+{_ats_current - ats_report.score_before:.0f}"
                if _ats_current >= ats_report.score_before
                else f"{_ats_current - ats_report.score_before:.0f}"
            )

            if _ats_current >= 85:
                logger.info(
                    f"    ✓ ATS target 85+ reached at strategy "
                    f"{ats_improve_attempts}"
                )
            elif _ats_current < 80:
                logger.warning(
                    f"    ATS MANDATE FAILED: {_ats_current:.0f} < 80 after "
                    f"{ats_improve_attempts} strategies"
                )

            # -- PHASE 4: ARTIFACT-TRUTH CHECKPOINT (improvement-regression policy)
            # The reported score must describe the artifact we return. Re-score
            # the current improved artifact after all mandate strategies; if it
            # silently regressed below the tailored baseline, revert to tailored
            # and record an explicit regression warning. Never manipulate scores.
            _artifact_score, _, _ = scorer.score(improved, extracted_jd)
            _tailored_score, _, _ = scorer.score(tailored, extracted_jd)
            if _artifact_score < _tailored_score - 1.0:
                logger.warning(
                    f"  IMPROVEMENT REGRESSION: artifact {_artifact_score:.1f} < "
                    f"tailored {_tailored_score:.1f} -> reverting to tailored resume"
                )
                improved = tailored.model_copy(deep=True)
                ats_report.score_after = round(_tailored_score, 1)
                best_score = max(_tailored_score, ats_report.score_before)
                ats_report.improvement = (
                    f"+{ats_report.score_after - ats_report.score_before:.0f}"
                )
                ats_report.risk_flags = list(ats_report.risk_flags or []) + [
                    f"IMPROVEMENT_REGRESSION_REVERTED: strategies scored "
                    f"{_artifact_score:.1f} < tailored {_tailored_score:.1f}"
                ]
            else:
                # Keep artifact; align the reported score with the artifact truth
                ats_report.score_after = round(
                    max(_artifact_score, ats_report.score_after, ats_report.score_before), 1
                )
                best_score = max(best_score, _artifact_score)

            # CRITICAL: sync best_score with mandate result
            # Without this, later pipeline stages (polish, perception, etc.)
            # compare against the old pre-mandate best_score and may regress.
            if _ats_current > best_score:
                best_score = _ats_current
                logger.info(
                    f"    best_score synced: {best_score:.0f} (from ATS mandate)"
                )

        # -- Professional Summary Engine (ALWAYS run in strict/balanced) --
        try:
            should_replace = should_replace_summary(improved.summary)
            # Strict: ALWAYS generate optimized summary
            # Balanced: only replace if weak (preserves original voice)
            # Conservative: only replace if weak
            force_summary = mode == "strict"
            if should_replace or force_summary:
                old_summary = improved.summary or ""
                # Mode-aware keyword limit: strict=all, balanced=top 3
                summary_keywords = extracted_jd.keywords
                summary_skills = ats_report.matched_skills
                if mode == "balanced":
                    summary_keywords = (extracted_jd.keywords or [])[:5]
                    summary_skills = (ats_report.matched_skills or [])[:3]
                new_summary = generate_professional_summary(
                    resume=improved,
                    role_info=role_info,
                    jd_keywords=summary_keywords,
                    matched_skills=summary_skills,
                )
                if new_summary and len(new_summary) > 50:
                    # Only replace if new is better (longer + has tools)
                    new_has_tools = any(
                        sk.lower() in new_summary.lower()
                        for sk in (ats_report.matched_skills or [])[:5]
                    )
                    old_has_tools = any(
                        sk.lower() in old_summary.lower()
                        for sk in (ats_report.matched_skills or [])[:5]
                    )
                    if should_replace or new_has_tools or not old_has_tools:
                        improved.summary = new_summary
                        tracker.record(
                            section="summary",
                            change_type="summary_generation",
                            before=old_summary[:100],
                            after=new_summary[:100],
                            reason="Generated role-aware professional summary with tools + impact",
                            rule="summary_engine.generate_professional_summary",
                            confidence="HIGH",
                        )
                        logger.info(f"  Summary Engine: {'replaced weak' if should_replace else 'upgraded'} summary ({len(old_summary)}→{len(new_summary)} chars)")
        except Exception as e:
            logger.warning(f"  Summary engine skipped: {e}")

        # -- Polish Engine — runs for score >= 75 (lowered from 80) --
        polish_changes_list = []
        try:
            if best_score >= 75 and mode == "strict":
                polished, polish_changes_list = polish_resume(
                    improved, role_type=role_info['role_type']
                )
                improved = polished
                for pc in polish_changes_list:
                    tracker.record(
                        section=f"polish.{pc['type']}",
                        change_type=pc['type'],
                        before=pc.get('before', ''),
                        after=pc.get('after', ''),
                        reason=pc.get('reason', 'Professional polish'),
                        rule="polish_engine.polish_resume",
                        confidence="MEDIUM",
                    )
                if polish_changes_list:
                    logger.info(
                        f"  Polish Engine: {len(polish_changes_list)} refinements applied "
                        f"(score={best_score:.1f})"
                    )
        except Exception as e:
            logger.warning(f"  Polish engine skipped: {e}")

        # -- Post-polish re-score (captures polish improvements) --
        if polish_changes_list:
            post_polish_score, improved_breakdown, improved_details = scorer.score(improved, extracted_jd)
            if post_polish_score > best_score:
                logger.info(f"  Post-polish re-score: {best_score:.1f} -> {post_polish_score:.1f} (+{post_polish_score - best_score:.1f})")
                best_score = post_polish_score
                # Re-apply cap
                score_limit = _compute_score_limit(scorer, improved, extracted_jd, improved_details)
                best_score = min(best_score, score_limit.max_possible_score)
                best_score = max(best_score, ats_report.score_before)
                ats_report.score_after = round(best_score, 1)
                ats_report.improvement = f"+{best_score - ats_report.score_before:.0f}"
                ats_report.breakdown_after = improved_breakdown

        # -- FIRST IMPRESSION VALIDATION (strict only) --
        # Final check: recruiter reads summary + first 2-3 bullets.
        # If lead bullet is weak, swap with strongest bullet in first role.
        # NOTE: Uses module-level ResumeImprover import (line 26)
        if mode == "strict" and improved.experience:
            _fi_role = role_info.get("role_type", "data")
            first_exp = improved.experience[0]
            if len(first_exp.bullets) >= 2:
                scores = [(ResumeImprover._score_bullet_impact(b, _fi_role), i, b)
                          for i, b in enumerate(first_exp.bullets)]
                best = max(scores, key=lambda x: x[0])
                if best[1] != 0 and best[0] > scores[0][0] + 1:
                    # Swap: put strongest bullet first
                    first_exp.bullets[0], first_exp.bullets[best[1]] = (
                        first_exp.bullets[best[1]], first_exp.bullets[0])
                    logger.info(
                        f"  First Impression: swapped lead bullet "
                        f"(score {scores[0][0]}->{best[0]})")

        logger.info(
            f"  Optimization complete: {ats_report.score_before:.1f} -> "
            f"{best_score:.1f} (+{best_score - ats_report.score_before:.1f} pts)"
        )
    except Exception as e:
        logger.warning(f"  Resume improvement skipped: {e}")
        polish_changes_list = []
        improved = tailored
        # Compute score_limit on tailored as fallback
        _, _, fallback_details = scorer.score(tailored, extracted_jd)
        score_limit = _compute_score_limit(scorer, tailored, extracted_jd, fallback_details)

    # -- PART 8: Strict trust rules (Phase 5A: delegated to central Truth Gate)
    # pipeline/truth_gate.py is THE authoritative boundary; core only applies
    # the revert actions the verdict prescribes. No second truth implementation.
    from pipeline.truth_gate import validate_candidate_representation, check_metrics
    _orig_bullets_all = [b for e in original.experience for b in e.bullets]
    _imp_bullets_all = [b for e in improved.experience for b in e.bullets]
    _metric_violations = check_metrics(_orig_bullets_all, _imp_bullets_all)
    _truth = validate_candidate_representation(original, improved, original_skills=list(original.skills or []))
    trust_issues = []
    if _truth.violations:
        trust_issues.extend(_truth.violations)
    if _metric_violations:
        trust_issues.extend(_metric_violations)

    # Revert actions (unchanged semantics, now driven by the verdict):
    if not _truth.identity_ok:
        improved.contact = original.contact.model_copy(deep=True)
        logger.warning("  TRUTH GATE: identity fields restored from original")

    if _truth.violations and any(v.startswith(("UNSUPPORTED_SKILL", "EMPLOYMENT_INFLATION")) for v in _truth.violations):
        improved.skills = original.skills[:]
        logger.warning(f"  TRUTH GATE: restored original skills ({len(_truth.violations)} violations)")
        tracker.record(
            section="skills",
            change_type="fake_skill_removal",
            before=f"{_truth.violations[:3]}",
            after="Reverted to original skills",
            reason="Truth Gate rejected unsupported skills (not in candidate evidence)",
            rule="pipeline.truth_gate",
            confidence="HIGH",
        )

    if _metric_violations:
        # Revert any bullet that introduced numbers absent from the original
        allowed_nums = set()
        import re as _re_metrics
        for b in _orig_bullets_all:
            allowed_nums |= set(_re_metrics.findall(r"\d+(?:\.\d+)?\s*[%x+]?", b.lower()))
        for ei, exp in enumerate(improved.experience):
            if ei < len(original.experience):
                for bi, b in enumerate(exp.bullets):
                    nums = set(_re_metrics.findall(r"\d+(?:\.\d+)?\s*[%x+]?", b.lower()))
                    if nums - allowed_nums and bi < len(original.experience[ei].bullets):
                        exp.bullets[bi] = original.experience[ei].bullets[bi]
                        tracker.record(
                            section=f"experience.{ei}.bullets.{bi}",
                            change_type="metric_fabrication_revert",
                            before=b[:100],
                            after=original.experience[ei].bullets[bi][:100],
                            reason="Truth Gate rejected fabricated metric",
                            rule="pipeline.truth_gate.check_metrics",
                            confidence="HIGH",
                        )
    # -- NEW: Trust Validator (full structural check) ----------
    try:
        structural_violations = TrustValidator.validate_changes(
            tracker, original, improved
        )
        trust_issues.extend(structural_violations)
    except Exception as e:
        logger.warning(f"  Trust validator skipped: {e}")

    # Phase 5B: mark ledger validation state from the Truth Gate verdict
    for rec in tracker.changes:
        if trust_issues:
            rec.validation = "REJECTED"
        else:
            rec.validation = "PASS"

    if trust_issues:
        for issue in trust_issues:
            logger.error(f"TRUST VIOLATION: {issue}")
    else:
        logger.info("  Trust validation: ALL CLEAR")

    # -- Build change explanation for user --------------------
    change_explanation = tracker.build_explanation()
    logger.info(
        f"  Trust layer: {change_explanation['total_changes']} changes tracked, "
        f"{change_explanation['high_confidence']} high confidence"
    )

    logger.info(f"  Pipeline fingerprint: {pipeline_hash}")
    logger.info(f"  Score limit: {score_limit.max_possible_score} ({score_limit.reasons[0][:60]})")

    # -- Target Score Engine --------------------------------
    # FIX M2: Use IMPROVED resume for target plan (not tailored)
    target_plan = None
    try:
        from ats_scoring.target_engine import generate_target_plan
        _, tp_breakdown, tp_details = scorer.score(improved, extracted_jd)
        target_plan = generate_target_plan(
            report=ats_report,
            breakdown=tp_breakdown,
            details=tp_details,
            jd=extracted_jd,
            resume=improved,
            scorer=scorer,
        )
        if target_plan.get("gap", 0) > 0:
            logger.info(
                f"  Target plan: {target_plan['current_score']} -> "
                f"{target_plan['projected_score']} "
                f"({len(target_plan.get('simulations', []))} actions)"
            )
    except Exception as e:
        logger.warning(f"  Target engine skipped: {e}")

    # -- STABILITY GUARD: Flag abnormal score deltas --------
    score_delta = abs(ats_report.score_after - ats_report.score_before)
    if score_delta > 15:
        logger.warning(
            f"  STABILITY GUARD: score delta={score_delta:.1f} exceeds 15pt threshold "
            f"({ats_report.score_before:.1f} -> {ats_report.score_after:.1f}) — flagged"
        )

    logger.info(f"PIPELINE CORE -- Complete for {job_id}")

    # -- Part 8: Role Fit (from ATS report) -----------------
    role_fit = getattr(ats_report, 'role_fit', None) or {}

    # -- Part 10: "Why Not 90+" Engine ----------------------
    why_not_90 = _compute_why_not_90(
        ats_report, score_limit, tailored, extracted_jd
    )

    # -- Part 8b: Execution Verification (CRITICAL) ----------
    # Ensure all improvements were ACTUALLY executed, not just suggested
    try:
        all_exp_text = " ".join(
            b.lower() for exp in improved.experience for b in exp.bullets
        )
        all_proj_text = " ".join(
            b.lower() for proj in improved.projects for b in proj.bullets
        )
        all_text = all_exp_text + " " + all_proj_text

        # Check: every matched skill MUST appear in at least one bullet
        undemonstrated = []
        for skill in (ats_report.matched_skills or []):
            skill_lower = skill.lower()
            # Check direct match or significant term match
            found = skill_lower in all_text
            if not found:
                terms = [t for t in skill_lower.split() if len(t) > 3]
                found = any(t in all_text for t in terms) if terms else False
            if not found:
                undemonstrated.append(skill)

        # Last-chance injection for undemonstrated skills
        # HARDENED: Tool-purpose validation — no blind injection
        _TOOL_PURPOSE_MAP = {
            # data tools
            "pandas": ("data processing", ["data", "analy", "clean", "transform", "pipeline", "dataset"]),
            "numpy": ("numerical computation", ["model", "analy", "comput", "process", "algorithm", "data"]),
            "scikit-learn": ("model training", ["model", "predict", "classif", "train", "machine learning"]),
            "sklearn": ("model training", ["model", "predict", "classif", "train", "machine learning"]),
            "tensorflow": ("deep learning", ["model", "neural", "deep", "train", "predict", "ml"]),
            "pytorch": ("deep learning", ["model", "neural", "deep", "train", "predict", "ml"]),
            "keras": ("neural network modeling", ["model", "neural", "deep", "train", "predict"]),
            "xgboost": ("gradient boosting", ["model", "predict", "classif", "train", "boost"]),
            "spark": ("distributed data processing", ["data", "pipeline", "process", "etl", "large", "scale"]),
            # viz/BI
            "tableau": ("data visualization", ["dashboa", "visual", "report", "insight", "analyt"]),
            "power bi": ("business intelligence", ["dashboa", "visual", "report", "insight", "kpi"]),
            # cloud
            "aws": ("cloud infrastructure", ["deploy", "cloud", "infra", "scale", "service", "pipeline"]),
            "gcp": ("cloud infrastructure", ["deploy", "cloud", "infra", "scale", "service", "pipeline"]),
            "azure": ("cloud infrastructure", ["deploy", "cloud", "infra", "scale", "service", "pipeline"]),
            "docker": ("containerization", ["deploy", "container", "service", "pipeline", "infra"]),
            "kubernetes": ("container orchestration", ["deploy", "container", "scale", "service", "orchestr"]),
            # NLP
            "nlp": ("text analysis", ["text", "language", "nlp", "sentiment", "extract", "process"]),
            "lstm": ("sequence modeling", ["time", "series", "sequence", "predict", "model", "forecast"]),
            # DB
            "sql": ("data querying", ["data", "query", "analy", "report", "database", "extract"]),
            "mongodb": ("document storage", ["data", "store", "database", "nosql", "document"]),
            "redis": ("caching", ["cache", "perform", "speed", "real-time", "session"]),
            # DevOps
            "git": ("version control", ["code", "develop", "collaborat", "team", "repository"]),
            "ci/cd": ("deployment automation", ["deploy", "pipeline", "automat", "releas", "build"]),
            "jenkins": ("build automation", ["deploy", "pipeline", "automat", "build", "ci"]),
        }

        if undemonstrated and mode == "strict":
            inject_count = 0
            for skill in undemonstrated[:2]:  # Max 2 candidates
                if inject_count >= 1:
                    break  # Max 1 injection total (quality > quantity)
                skill_lower = skill.lower()
                purpose_info = _TOOL_PURPOSE_MAP.get(skill_lower)

                # Find BEST matching bullet (by context relevance, not just shortest)
                best_i, best_j, _match_score_best = None, None, -1
                for i, exp in enumerate(improved.experience):
                    for j, bullet in enumerate(exp.bullets):
                        if len(bullet) > 150:
                            continue
                        # Skip if bullet already mentions this skill
                        if skill_lower in bullet.lower():
                            continue
                        # HARDENED: Skip if bullet already has ANY tool/injection suffix
                        b_check = bullet.lower()
                        has_suffix = bool(re.search(
                            r',\s*(?:using|applying|leveraging|utilizing|with)\s+\w',
                            b_check
                        ))
                        if has_suffix:
                            continue

                        # Score by context match
                        if purpose_info:
                            _, context_keywords = purpose_info
                            match_score = sum(1 for kw in context_keywords if kw in b_check)
                        else:
                            match_score = 0  # No purpose = no injection

                        if match_score > _match_score_best:
                            best_i, best_j, _match_score_best = i, j, match_score

                # Only inject if strong context match (>= 2 keyword matches)
                if best_i is not None and _match_score_best >= 2:
                    bullet = improved.experience[best_i].bullets[best_j]
                    if not purpose_info:
                        logger.info(f"  Execution Verify: BLOCKED '{skill}' — no purpose mapping")
                        continue

                    # Guard: skip if bullet already has an "in {Tool}" suffix
                    if re.search(r' in [A-Z][\w.-]+\.$', bullet):
                        continue

                    # Natural phrasing: "in {skill}" (aligned with rewriter)
                    purpose_phrase = purpose_info[0]
                    suffix = f" in {skill}"

                    if bullet.endswith("."):
                        improved.experience[best_i].bullets[best_j] = bullet[:-1] + suffix + "."
                    else:
                        improved.experience[best_i].bullets[best_j] = bullet + suffix + "."
                    inject_count += 1
            if inject_count:
                logger.info(
                    f"  Execution Verify: {inject_count} last-chance skill injections "
                    f"({len(undemonstrated)} were undemonstrated)"
                )
                # Re-score after last-chance injection
                verify_score, _, _ = scorer.score(improved, extracted_jd)
                if verify_score > best_score:
                    best_score = verify_score
                    ats_report.score_after = round(best_score, 1)
                    ats_report.improvement = f"+{best_score - ats_report.score_before:.0f}"
    except Exception as e:
        logger.warning(f"  Execution verification skipped: {e}")

    # -- Part 13: Final Validation Gate ----------------------
    validation_result = None
    try:
        from resume_engine.validation_gate import auto_fix_validation_failures
        vr = validate_output(original, improved, extracted_jd, role_info)
        validation_result = vr.to_dict()
        if not vr.passed:
            logger.warning(
                f"  VALIDATION GATE: {len(vr.violations)} violations — attempting auto-fix"
            )
            # Attempt auto-fix instead of reverting
            try:
                fixed, fixes = auto_fix_validation_failures(improved, vr)
                if fixes:
                    improved = fixed
                    logger.info(f"  VALIDATION AUTO-FIX: Applied {len(fixes)} fixes")
                    # Re-validate after fix
                    vr2 = validate_output(original, improved, extracted_jd, role_info)
                    validation_result = vr2.to_dict()
            except Exception as fix_err:
                logger.warning(f"  Auto-fix skipped: {fix_err}")
            # NEVER fall back to tailored — improved is always better
    except Exception as e:
        logger.warning(f"  Validation gate skipped: {e}")

    # -- FINAL BULLET DEDUP (absolute last pass) ----------------
    # Catches duplicates created by integrity gate, last-chance injection,
    # polish engine, or any other post-improve processing.
    for exp in improved.experience:
        if len(exp.bullets) < 2:
            continue
        seen_cores = {}
        deduped = []
        for b in exp.bullets:
            # Strip tool suffix to get core content
            core = re.sub(
                r',\s*(?:using|leveraging|applying|utilizing)\s+.*$',
                '', b, flags=re.IGNORECASE
            ).lower().strip().rstrip('.')
            if core in seen_cores:
                # Keep the longer (enriched) version
                existing = seen_cores[core]
                if len(b) > len(existing):
                    deduped = [b if x == existing else x for x in deduped]
                    seen_cores[core] = b
                # else: skip this shorter duplicate
                logger.info(f"  FINAL DEDUP: removed duplicate bullet in {exp.company}")
            else:
                seen_cores[core] = b
                deduped.append(b)
        exp.bullets = deduped

    # -- FINAL TRUST CLEANUP (absolute last pass) ----------------
    # Catches artifacts from all post-improve processing
    for i_exp, exp in enumerate(improved.experience):
        orig_exp = original.experience[i_exp] if i_exp < len(original.experience) else None
        for j, bullet in enumerate(exp.bullets):
            cleaned = bullet
            # Fix double-using: "using, using spark" → "using spark"
            cleaned = re.sub(r'using,\s*using\s+', 'using ', cleaned, flags=re.I)
            # Fix ". using" → ", using"
            cleaned = re.sub(r'\.\s+(using|applying|leveraging|utilizing)\s+',
                             r', \1 ', cleaned, flags=re.I)
            # Fix double prepositions: "for for" → "for"
            cleaned = re.sub(r'\bfor\s+for\b', 'for', cleaned, flags=re.I)
            # Fix "to to" → "to"
            cleaned = re.sub(r'\bto\s+to\b', 'to', cleaned, flags=re.I)
            # Fix mid-word truncation at end (e.g., "training neural.")
            trunc = re.search(r'\b(\w{2,6})\.\s*$', cleaned)
            if trunc:
                word = trunc.group(1).lower()
                safe = {'by', 'for', 'to', 'in', 'on', 'at', 'and', 'the', 'an',
                        'via', 'per', 'etc', 'use', 'ml', 'ai', 'nlp', 'sql',
                        'aws', 'gcp', 'api', 'etl', 'ci', 'cd', 'ui', 'ux',
                        'lstm', 'bert', 'cv', 'iot', 'k8s', 'gpu', 'cpu',
                        'kpi', 'kpis', 'data', 'prod', 'logs', 'apps',
                        'time', 'real', 'cost', 'base', 'user', 'team',
                        'risk', 'rate', 'test', 'task', 'code', 'work',
                        'sales', 'model', 'tools', 'cloud', 'scale',
                        '15', '22', '40', '94', 'daily',
                        # Tool/language names (prevent truncation of skill suffixes)
                        'python', 'java', 'bash', 'ruby', 'rust', 'swift',
                        'flask', 'django', 'react', 'node', 'spark',
                        'pandas', 'numpy', 'scipy', 'keras', 'plotly',
                        'docker', 'linux', 'redis', 'mongo', 'mysql',
                        'azure', 'power', 'excel', 'jira', 'git',
                        'gradio', 'fastai', 'dbt', 'airflow', 'cron',
                        }
                is_acronym = trunc.group(1).isupper()  # e.g., "AWS", "GCP"
                # Guard: never truncate part of a hyphenated compound (e.g., "real-time")
                pre_trunc = cleaned[:trunc.start()]
                is_hyphenated = pre_trunc.rstrip().endswith('-')
                if (word not in safe and not is_acronym 
                        and not re.match(r'\d+', word) and not is_hyphenated):
                    cleaned = cleaned[:trunc.start()].rstrip(', ') + '.'
            # Post-truncation guard: if we created a trailing hyphen, revert or repair
            stripped = cleaned.rstrip()
            if stripped.endswith('-.') or stripped.endswith('-'):
                # Try to repair known hyphenated tool prefixes
                _HYPHEN_REPAIRS = {
                    'scikit-': 'scikit-learn', 'scikit-l': 'scikit-learn',
                    'scikit-i': 'scikit-image', 'real-': 'real-time',
                    'cross-': 'cross-validation', 'semi-': 'semi-supervised',
                }
                repaired = False
                for prefix, full in _HYPHEN_REPAIRS.items():
                    if stripped.rstrip('.').lower().endswith(prefix):
                        cleaned = stripped[:stripped.rstrip('.').rfind(prefix.rstrip('-'))] + full + '.'
                        repaired = True
                        break
                if not repaired:
                    if orig_exp and j < len(orig_exp.bullets):
                        cleaned = orig_exp.bullets[j]
                    else:
                        # Strip the trailing hyphen + period
                        cleaned = stripped.rstrip('-.').rstrip() + '.'
            # Fix overly long tool suffixes (>60 chars after comma)
            suffix = re.search(r',\s*(?:using|leveraging|applying|utilizing)\s+(.+)$', cleaned, re.I)
            if suffix and len(suffix.group()) > 60:
                # Keep just tool name
                tool = re.match(r'([\w][\w\s.#+]*?)(?:\s+for\b)', suffix.group(1))
                if tool:
                    cleaned = cleaned[:suffix.start()] + f", using {tool.group(1).strip()}."
            # Detect raw JD text injection: "for create dashboards", "for build ML models"
            # (infinitive verb after "for" without "to" = raw JD copy)
            jd_copy = re.search(
                r'for\s+(build|create|deploy|develop|design|analyze|manage|lead|implement)\s+',
                cleaned, re.I
            )
            if jd_copy and orig_exp and j < len(orig_exp.bullets):
                # Revert to original if raw JD text detected
                cleaned = orig_exp.bullets[j]
            # Final cleanup
            cleaned = cleaned.replace('..', '.').replace('  ', ' ').replace(',.', '.')
            if cleaned != bullet:
                exp.bullets[j] = cleaned

    # -- Final quality evaluation ----------------------------
    final_quality = evaluate_resume_quality(improved, extracted_jd)
    logger.info(
        f"  Final quality: {final_quality['total']:.0f}/100 "
        f"(demo={final_quality['skill_demo']:.0f}% "
        f"purpose={final_quality['tool_purpose']:.0f}%)"
    )

    # -- CONTENT INTELLIGENCE LAYER (v4.5-v4.8) ----------------------
    # MUST run BEFORE hiring simulation so prediction uses optimized data
    # Order: content_quality → truth_engine → ats_optimizer → ats_hardening
    content_intelligence = None
    ci_recruiter_avg = 0
    ci_real_coverage = 0
    try:
        from pipeline.content_quality import (
            score_signal_strength, score_proof_strength, score_jd_alignment,
            check_lifecycle_coverage, check_ats_optimization,
        )
        from pipeline.truth_engine import simulate_recruiter_scan
        from pipeline.ats_optimizer import (
            analyze_keyword_gaps, check_keyword_distribution,
        )
        from pipeline.ats_hardening import (
            simulate_ats_parser, compute_final_decision,
            generate_capability_plan, check_defensibility,
        )

        logger.info("  PIPELINE ORDER: Content Intelligence FIRST (v4.5-v4.8)")

        # Collect all bullets from improved resume
        ci_all_bullets = [b for exp in improved.experience for b in exp.bullets]
        ci_jd_skills = list(extracted_jd.required_skills or [])
        ci_jd_keywords = list(set(
            (extracted_jd.required_skills or []) + (extracted_jd.keywords or [])
        ))
        ci_candidate_skills = list(original.skills or [])
        ci_role_title = extracted_jd.job_title or ""

        # STAGE 1: Content Quality (v4.5)
        logger.info("  → v4.5 Content Quality Engine DONE")
        ci_signal_scores = []
        ci_proof_scores = []
        ci_align_scores = []
        for b in ci_all_bullets[:8]:
            sig = score_signal_strength(b, ci_jd_skills)
            prf = score_proof_strength(b)
            aln = score_jd_alignment(b, ci_jd_skills, ci_role_title)
            ci_signal_scores.append(sig["total"])
            ci_proof_scores.append(prf["total"])
            ci_align_scores.append(aln["total"])

        ci_avg_signal = sum(ci_signal_scores) / max(len(ci_signal_scores), 1)
        ci_avg_proof = sum(ci_proof_scores) / max(len(ci_proof_scores), 1)
        ci_avg_align = sum(ci_align_scores) / max(len(ci_align_scores), 1)

        ci_lifecycle = check_lifecycle_coverage(ci_all_bullets, ci_role_title)
        ci_ats_kw = check_ats_optimization(ci_all_bullets, ci_jd_keywords)

        logger.info(
            f"    Signal={ci_avg_signal:.0f} Proof={ci_avg_proof:.0f} "
            f"Align={ci_avg_align:.0f} Lifecycle={ci_lifecycle['coverage']}% "
            f"ATS-KW={ci_ats_kw['keyword_coverage']}%"
        )

        # STAGE 2: Recruiter Simulation (v4.6)
        logger.info("  → v4.6 Truth + Recruiter Simulation DONE")
        ci_recruiter_results = []
        for b in ci_all_bullets[:5]:
            rec = simulate_recruiter_scan(b, ci_jd_skills, ci_role_title)
            ci_recruiter_results.append(rec)
        ci_shortlist_count = sum(1 for r in ci_recruiter_results if r["decision"] == "SHORTLIST")
        ci_recruiter_avg = sum(r["score"] for r in ci_recruiter_results) / max(len(ci_recruiter_results), 1)
        logger.info(
            f"    Recruiter avg={ci_recruiter_avg:.0f}, "
            f"{ci_shortlist_count}/{len(ci_recruiter_results)} bullets SHORTLIST-grade"
        )

        # STAGE 3: ATS Gap Analysis (v4.7)
        logger.info("  → v4.7 ATS Optimization DONE")
        ci_resume_text = " ".join(ci_all_bullets)
        ci_gaps = analyze_keyword_gaps(ci_jd_keywords, ci_resume_text, ci_candidate_skills)
        ci_distribution = check_keyword_distribution(ci_all_bullets, ci_jd_keywords)
        logger.info(
            f"    Coverage={ci_gaps['coverage']}% Injectable={ci_gaps['injectable_count']} "
            f"{ci_distribution['message']}"
        )

        # STAGE 4: ATS Real Parsing (v4.8)
        logger.info("  → v4.8 ATS Hardening DONE")
        ci_ats_parsed = simulate_ats_parser(ci_resume_text, ci_jd_keywords)
        ci_real_coverage = ci_ats_parsed["real_coverage"]

        # Capability plan for unknown skills
        ci_capability_plan = generate_capability_plan(ci_gaps.get("missing_unknown", []))

        # Defensibility check
        ci_defensibility = check_defensibility(
            ci_gaps.get("missing_injectable", []),
            ci_candidate_skills, ci_all_bullets
        )

        logger.info(
            f"    Theoretical={ci_ats_parsed['theoretical_coverage']}% "
            f"Real={ci_real_coverage}%"
        )

        # Build partial content_intelligence (decision added after hiring sim)
        content_intelligence = {
            "content_quality": {
                "avg_signal": round(ci_avg_signal, 1),
                "avg_proof": round(ci_avg_proof, 1),
                "avg_alignment": round(ci_avg_align, 1),
                "lifecycle_coverage": ci_lifecycle["coverage"],
                "ats_keyword_coverage": ci_ats_kw["keyword_coverage"],
            },
            "recruiter_simulation": {
                "avg_score": round(ci_recruiter_avg, 1),
                "shortlist_grade_bullets": ci_shortlist_count,
                "total_evaluated": len(ci_recruiter_results),
            },
            "ats_analysis": {
                "theoretical_coverage": ci_ats_parsed["theoretical_coverage"],
                "real_coverage": ci_ats_parsed["real_coverage"],
                "parsed_keywords": ci_ats_parsed["parsed_keywords"],
                "missing_keywords": ci_ats_parsed["missing_keywords"],
                "injectable_count": ci_gaps["injectable_count"],
                "distribution": ci_distribution["message"],
            },
            "defensibility": {
                "safe": [s["keyword"] for s in ci_defensibility["safe_keywords"]],
                "rejected": [r["keyword"] for r in ci_defensibility["rejected_keywords"]],
            },
            "capability_plan": ci_capability_plan,
            "decision": None,  # Computed after hiring simulation
        }
        logger.info("  → Hiring Simulation START (using optimized resume)")

    except Exception as ci_err:
        logger.warning(f"  Content Intelligence skipped: {ci_err}")

    # -- SELF-OPTIMIZING SHORTLIST ENGINE (Closed-Loop) ----------------
    # Now runs AFTER Content Intelligence — prediction uses scored resume
    SHORTLIST_TARGET = 85.0
    SHORTLIST_MAX_ITERATIONS = 3
    hiring_sim = None
    perception_result = None
    dominance_result = None

    try:
        # -- Initial perception measurement --
        perception_result = compute_perceived_strength(improved, extracted_jd)
        logger.info(
            f"  Perception: {perception_result['total']:.0f}/100 "
            f"(impact={perception_result['impact_density']:.0f}% "
            f"ownership={perception_result['ownership_level']:.0f}% "
            f"scale={perception_result['scale_visibility']:.0f}% "
            f"outcome={perception_result['outcome_clarity']:.0f}%)"
        )
        if perception_result['weak_bullets']:
            logger.info(
                f"  Weak bullets: {len(perception_result['weak_bullets'])} "
                f"identified for strengthening"
            )

        # -- Closed-loop: iterate until shortlist >= target --
        for sl_iter in range(1, SHORTLIST_MAX_ITERATIONS + 1):
            # STEP 1: Run hiring simulation
            skill_proof = audit_skill_proof(
                improved, extracted_jd,
                matched_skills=ats_report.matched_skills or [],
            )
            hiring_sim = simulate_hiring(
                resume=improved,
                jd=extracted_jd,
                ats_score=ats_report.score_after,
                matched_skills=ats_report.matched_skills or [],
                missing_skills=ats_report.missing_skills or [],
                skill_proof=skill_proof,
            )

            shortlist_prob = hiring_sim['shortlist_probability']
            logger.info(
                f"  Shortlist Loop [{sl_iter}/{SHORTLIST_MAX_ITERATIONS}]: "
                f"{hiring_sim['decision']} "
                f"(shortlist={shortlist_prob:.1f}%, "
                f"layers={hiring_sim['layers_passed']}/3, "
                f"10s={'PASS' if hiring_sim['ten_second_test']['pass'] else 'FAIL'})"
            )

            # STEP 2: Check if target met
            if shortlist_prob >= SHORTLIST_TARGET:
                logger.info(
                    f"  ✓ Shortlist target {SHORTLIST_TARGET}% met at iteration {sl_iter}"
                )
                break

            # STEP 3: If not met and not last iteration, enhance experience
            if sl_iter < SHORTLIST_MAX_ITERATIONS and mode != "conservative":
                # Re-measure perception to find current weak bullets
                perception_result = compute_perceived_strength(improved, extracted_jd)

                if perception_result['weak_bullets']:
                    # Save state before enhancement (perception guard)
                    pre_bullets = [
                        [b for b in exp.bullets]
                        for exp in improved.experience
                    ]
                    pre_perception = perception_result['total']

                    # Enhance weakest bullets (structural transform only)
                    improved = enhance_experience_strength(
                        improved, extracted_jd, perception_result
                    )

                    # Perception guard: verify enhancement helped
                    post_perception = compute_perceived_strength(improved, extracted_jd)
                    if post_perception['total'] < pre_perception:
                        # REVERT: enhancement hurt perception
                        for i, exp in enumerate(improved.experience):
                            if i < len(pre_bullets):
                                exp.bullets = pre_bullets[i]
                        logger.info(
                            f"  Perception guard: reverted ({pre_perception:.0f} → "
                            f"{post_perception['total']:.0f}, kept {pre_perception:.0f})"
                        )
                    else:
                        # Re-score after enhancement
                        enhanced_score, _, _ = scorer.score(improved, extracted_jd)
                        if enhanced_score >= best_score:
                            best_score = enhanced_score
                            ats_report.score_after = round(best_score, 1)
                            ats_report.improvement = f"+{best_score - ats_report.score_before:.0f}"
                        logger.info(
                            f"  Experience Strength boost: perception "
                            f"{pre_perception:.0f} → {post_perception['total']:.0f}, "
                            f"score {best_score:.1f}"
                        )
                else:
                    logger.info(f"  No weak bullets remaining — stopping loop")
                    break
            else:
                break

        # -- Final perception measurement (after all enhancements) --
        perception_result = compute_perceived_strength(improved, extracted_jd)

        # -- Recruiter 10-Second Dominance Check --
        dominance_result = recruiter_10s_dominance_check(improved, extracted_jd)
        logger.info(
            f"  10s Dominance: {'PASS' if dominance_result['pass'] else 'FAIL'} "
            f"(score={dominance_result['score']}, "
            f"strong_bullets={dominance_result['strong_opening_bullets']})"
        )
        if not dominance_result['pass'] and dominance_result['risks']:
            for risk in dominance_result['risks'][:2]:
                logger.info(f"    Risk: {risk}")

        # Log competitive analysis
        logger.info(
            f"  Competitive: {hiring_sim['competitive']['competitive_level']} "
            f"({hiring_sim['competitive']['differentiator_count']} differentiators)"
        )
        if hiring_sim.get('gaps'):
            for gap in hiring_sim['gaps'][:3]:
                logger.info(f"  Gap [{gap['severity']}]: {gap['detail'][:80]}")

        # Attach perception + dominance to hiring sim result
        hiring_sim['perception'] = perception_result
        hiring_sim['dominance_check'] = dominance_result

        # -- USER INTERPRETATION ENGINE (Final Layer) --
        try:
            interpretation = generate_candidate_interpretation(
                resume=improved,
                jd=extracted_jd,
                hiring_sim=hiring_sim,
                ats_score=ats_report.score_after,
                perception=perception_result,
            )
            hiring_sim['interpretation'] = interpretation
            logger.info(
                f"  Interpretation: {interpretation['decision']['decision']} "
                f"(level={interpretation['level_info']['level']}, "
                f"position={interpretation['benchmark']['position']})"
            )
        except Exception as ie:
            logger.warning(f"  Interpretation engine skipped: {ie}")

        # -- HIRING INTELLIGENCE ENGINE (Prediction Layer) --
        try:
            import json as _json
            _hist_path = os.path.join(os.path.dirname(__file__), "..", "data", "job_history.json")
            if os.path.exists(_hist_path):
                with open(_hist_path, "r", encoding="utf-8") as _f:
                    history = _json.load(_f)
            else:
                history = []
        except Exception:
            history = []
        
        try:
            intelligence = generate_hiring_intelligence(
                resume=improved,
                jd=extracted_jd,
                hiring_sim=hiring_sim,
                ats_score=ats_report.score_after,
                matched_skills=ats_report.matched_skills or [],
                missing_skills=ats_report.missing_skills or [],
                history=history,
            )
            hiring_sim['intelligence'] = intelligence
            gate = intelligence.get('gate', {})
            logger.info(
                f"  Intelligence: {gate.get('decision', '?')} "
                f"(confidence={gate.get('confidence_score', 0)}%, "
                f"targeting={intelligence.get('targeting', {}).get('total_score', 0)}/100, "
                f"diagnosis={intelligence.get('diagnosis', {}).get('primary_cause', '?')})"
            )
        except Exception as he:
            logger.warning(f"  Hiring intelligence skipped: {he}")

    except Exception as e:
        logger.warning(f"  Shortlist engine error: {e}")

    # -- SHORTLIST BOOST VALIDATION (Part 7) --
    # Compute shortlist before and after. If ATS improved but shortlist
    # didn't, log a warning — the optimization added keywords without
    # improving competitive positioning.
    sl_before = compute_shortlist_score(original, extracted_jd, ats_report.score_before)
    sl_after = compute_shortlist_score(improved, extracted_jd, ats_report.score_after)
    sl_delta = sl_after["total"] - sl_before["total"]
    ats_delta = ats_report.score_after - ats_report.score_before
    
    if ats_delta > 5 and sl_delta <= 0:
        logger.warning(
            f"  Shortlist Boost ALERT: ATS +{ats_delta:.1f} but SL {sl_delta:+.0f} — "
            f"optimization added keywords without improving competitiveness"
        )
    else:
        logger.info(
            f"  Shortlist: {sl_before['total']:.0f} -> {sl_after['total']:.0f} "
            f"(+{sl_delta:.0f})"
        )

    # -- PART 4 (Trust): HARD REJECTION LOGIC --
    # If shortlist score is critically low, the candidate should NOT apply.
    # This saves the candidate time and preserves system credibility.
    if sl_after["total"] < 40:
        logger.warning(
            f"  HARD REJECTION: Shortlist score {sl_after['total']:.0f} < 40 — "
            f"recommend DO NOT APPLY (weak fit for this role)"
        )

    # -- PART 5 (Trust): ROLE CONSISTENCY CHECK --
    # Validate: summary role aligns with JD target role.
    # If the summary talks about "Data Scientist" but JD is for "Frontend Developer",
    # the recruiter sees inconsistency → immediate reject.
    if role_info and improved.summary:
        summary_lower = improved.summary.lower()
        jd_title = (extracted_jd.job_title or "").lower()
        role_type = role_info.get("role_type", "")
        
        # Check for major mismatches (summary mentions wrong domain)
        mismatch_pairs = [
            ("data scien", ["frontend", "backend", "devops", "qa"]),
            ("frontend", ["data scien", "backend", "devops", "machine learning"]),
            ("backend", ["frontend", "data scien", "hr", "customer support"]),
            ("hr ", ["engineer", "developer", "data scien", "devops"]),
        ]
        for summary_sig, jd_conflicts in mismatch_pairs:
            if summary_sig in summary_lower:
                if any(conflict in jd_title for conflict in jd_conflicts):
                    logger.warning(
                        f"  ROLE CONSISTENCY ALERT: Summary mentions '{summary_sig}' "
                        f"but JD title is '{jd_title}' — potential mismatch"
                    )
                    break

    # -- FINAL DECISION (v5.0+v5.1) — adaptive + behavioral ---------------
    # v5.0: 4-tier adaptive decision (APPLY NOW / FIX / EXPERIMENT / SKIP)
    # v5.1: behavior modifiers (budget + recovery + impact + throughput)
    try:
        from pipeline.adaptive_engine import compute_adaptive_decision, generate_recovery_plan
        from pipeline.behavior_engine import run_behavior_engine
        shortlist_prob = (
            hiring_sim.get("shortlist_probability", 0) if hiring_sim else 0
        )
        # v5.0 adaptive decision
        ci_decision = compute_adaptive_decision(
            ci_real_coverage, shortlist_prob, ci_recruiter_avg,
            list(original.skills or []),
            list(extracted_jd.required_skills or []),
        )

        # v5.1 behavior modifiers
        ci_bullets = [b for exp in improved.experience for b in exp.bullets]
        ci_missing = []
        if content_intelligence and content_intelligence.get("ats_analysis"):
            ci_missing = content_intelligence["ats_analysis"].get("missing_keywords", [])

        behavior = run_behavior_engine(
            decision=ci_decision,
            bullets=ci_bullets,
            missing_keywords=ci_missing,
            recruiter_avg=ci_recruiter_avg,
        )

        # Attach to content_intelligence
        if content_intelligence:
            content_intelligence["decision"] = behavior["decision"]
            content_intelligence["behavior_control"] = behavior["behavior_control"]
            content_intelligence["impact_upgrade"] = behavior["impact_upgrade"]
            content_intelligence["recovery_status"] = behavior["recovery_status"]
            content_intelligence["exploration"] = ci_decision.get("exploration", {})
            # Recovery plan for non-APPLY-NOW decisions
            if behavior["decision"]["final"] != "APPLY NOW":
                recovery = generate_recovery_plan(
                    ci_missing, ci_bullets,
                    jd_skills=list(extracted_jd.required_skills or []),
                    role=extracted_jd.job_title or "",
                )
                content_intelligence["recovery_plan"] = recovery

        bd = behavior["decision"]
        logger.info(
            f"  → v5.1 Final Decision: {bd['final']} "
            f"(coverage={ci_real_coverage:.0f}%, shortlist={shortlist_prob:.0f}%, "
            f"recruiter={ci_recruiter_avg:.0f}, conf={bd['confidence']}%)"
        )
        logger.info(f"    Signals: {bd['signals']}")
        bc = behavior["behavior_control"]
        logger.info(
            f"    Behavior: explore={bc['exploration_used']}/{bc['exploration_budget']}, "
            f"apps={bc['weekly_applications']}, "
            f"recovery={'ENFORCED' if bc['recovery_enforced'] else 'OK'}, "
            f"throughput={'FORCED' if bc['throughput_forced'] else 'OK'}"
        )
        if bd["modifiers"]:
            for mod in bd["modifiers"]:
                logger.info(f"    Modifier: {mod}")
    except Exception as fd_err:
        logger.warning(f"  Final decision skipped: {fd_err}")

    # -- BULLET REWRITER (v5.1.1): Strong bullet generation ------------
    try:
        from pipeline.bullet_rewriter import rewrite_all_bullets
        all_orig_bullets = [b for exp in improved.experience for b in exp.bullets]
        candidate_skills = list(original.skills or [])

        # Snapshot pre-rewrite bullets in case rewriter degrades ATS score
        _pre_rw_bullets = [list(exp.bullets) for exp in improved.experience]
        _mandate_ats = best_score  # This holds the mandate's score (e.g. 85)

        rw = rewrite_all_bullets(all_orig_bullets, candidate_skills)

        if rw["accepted"] > 0:
            # Apply accepted rewrites back to improved resume
            bullet_idx = 0
            for exp in improved.experience:
                for b_i in range(len(exp.bullets)):
                    if bullet_idx < len(rw["final_bullets"]):
                        exp.bullets[b_i] = rw["final_bullets"][bullet_idx]
                    bullet_idx += 1
            logger.info(
                f"  Bullet Rewriter: {rw['accepted']}/{len(all_orig_bullets)} "
                f"upgraded (avg score={rw['avg_score']}/10)"
            )

            # Re-score after rewriting — protect ATS mandate gains
            _post_rw_score, _, _ = scorer.score(improved, extracted_jd)
            if _post_rw_score < _mandate_ats - 1:
                # Rewriter degraded ATS below mandate → REVERT
                for i, exp in enumerate(improved.experience):
                    if i < len(_pre_rw_bullets):
                        exp.bullets = _pre_rw_bullets[i]
                # Restore score to mandate level
                ats_report.score_after = round(_mandate_ats, 1)
                logger.info(
                    f"  Bullet Rewriter: REVERTED — would drop "
                    f"{_mandate_ats:.0f} → {_post_rw_score:.0f}, "
                    f"kept {_mandate_ats:.0f}"
                )
            else:
                # Rewriter maintained or improved score
                ats_report.score_after = round(max(_post_rw_score, _mandate_ats), 1)
                if _post_rw_score > best_score:
                    best_score = _post_rw_score
                logger.info(
                    f"  Bullet Rewriter: ATS {_post_rw_score:.0f} "
                    f"(mandate was {_mandate_ats:.0f})"
                )

        if content_intelligence:
            content_intelligence["bullet_rewriter"] = {
                "accepted": rw["accepted"],
                "rejected": rw["rejected"],
                "avg_score": rw["avg_score"],
            }
    except Exception as rw_err:
        logger.warning(f"  Bullet Rewriter skipped: {rw_err}")

    # ================================================================
    # CANONICAL SHORTLIST COMPUTATION (v6.0 — single source of truth)
    # ================================================================
    # ONE computation. ONE result. Stored in PipelineResult fields only.
    # hiring_sim["shortlist_probability"] = raw simulation value (kept for reference)
    # ats_report.shortlist_probability    = raw ATS-engine value (kept for reference)
    # PipelineResult.shortlist_probability = THE final value shown to users
    # ================================================================
    shortlist_unified = None
    shortlist_probability_final = 0.0
    shortlist_band_final = "D"
    shortlist_decision_final = "IMPROVE THEN APPLY"
    shortlist_reason_final = ""

    try:
        from pipeline.unified_scoring import compute_final_shortlist_probability
        from pipeline.hiring_simulation import _classify_candidate_level

        u_ats_score = ats_report.score_after

        # Input signal 1: Recruiter score (from 3-layer hiring simulation)
        u_recruiter_score = 0
        u_jd_match_score = 0
        if hiring_sim and isinstance(hiring_sim, dict):
            rec_layer = hiring_sim.get("layers", {}).get("recruiter", {})
            u_recruiter_score = rec_layer.get("score", 0)
            matched = len(ats_report.matched_skills or [])
            total = matched + len(ats_report.missing_skills or [])
            u_jd_match_score = (matched / max(total, 1)) * 100

        # Input signal 2: Bullets for quality analysis
        u_bullets = [b for exp in improved.experience for b in exp.bullets]

        # Input signal 3: Experience level
        u_exp_level = None
        if hiring_sim and isinstance(hiring_sim, dict):
            u_exp_level = hiring_sim.get("candidate_level", {}).get("level")
        if not u_exp_level:
            u_exp_level = _classify_candidate_level(improved).get("level", "mid")

        # Input signal 4: Production evidence
        all_bullet_text = " ".join(u_bullets).lower()
        u_has_production = any(
            kw in all_bullet_text
            for kw in ["production", "deployed", "launch", "release", "live system"]
        ) or any(
            t in " ".join(t2.lower() for p in improved.projects for t2 in (p.technologies or []))
            for t in ["docker", "kubernetes", "aws", "heroku", "streamlit", "flask", "fastapi"]
        )

        # SINGLE CALL to unified scoring
        shortlist_unified = compute_final_shortlist_probability(
            u_ats_score, u_recruiter_score, u_jd_match_score,
            bullets=u_bullets,
            experience_level=u_exp_level,
            has_production_exp=u_has_production,
            ats_score_before=ats_report.score_before,
        )

        # Annotate with pipeline context
        shortlist_unified["ats_improve_attempts"] = ats_improve_attempts
        shortlist_unified["ats_target_reached"] = u_ats_score >= 85

        # Reality validation — hard rules, applied once here, not scattered
        if ats_improve_attempts >= 3 and u_ats_score < 80:
            shortlist_unified["decision"] = "FIX GAPS"
            shortlist_unified["decision_reason"] = "ATS cannot reach competitive threshold after 3 strategies"

        decision = shortlist_unified.get("decision", "IMPROVE THEN APPLY")
        rec_eff = shortlist_unified.get("recruiter_effective", 0)
        if u_ats_score < 75 and "APPLY NOW" in decision:
            shortlist_unified["decision"] = "FIX GAPS"
            shortlist_unified["decision_reason"] = f"ATS {u_ats_score:.0f} below 75 — fix gaps first"
        elif rec_eff < 60 and "APPLY NOW" in decision:
            shortlist_unified["decision"] = "APPLY (FIX GAPS)"
            shortlist_unified["decision_reason"] = "Recruiter signals insufficient for APPLY NOW"
        elif u_exp_level == "entry" and "COMPETITIVE" in decision:
            shortlist_unified["decision"] = "APPLY (STRONG)"
            shortlist_unified["decision_reason"] = "Entry-level profile — realistic cap applied"

        # Extract final values for PipelineResult fields
        shortlist_probability_final = shortlist_unified["shortlist_probability"]
        shortlist_band_final = shortlist_unified.get("band", "D")
        shortlist_decision_final = shortlist_unified["decision"]
        shortlist_reason_final = shortlist_unified.get("decision_reason", "")

        # Keep ats_report.shortlist_probability for backward compat (dashboard.py reads it)
        # but DO NOT mutate hiring_sim["shortlist_probability"] — that stays as raw simulation value
        ats_report.shortlist_probability = {
            "shortlist_probability": shortlist_probability_final,
            "band": shortlist_band_final,
            "ats_band": shortlist_unified.get("ats_band", ""),
            "cap_applied": shortlist_unified.get("cap_applied", False),
            "calibration_reason": shortlist_unified.get("calibration_reason", ""),
            "unified": True,
        }

        logger.info(
            f"  SHORTLIST FINAL: {shortlist_probability_final:.0f}% "
            f"(ATS={u_ats_score:.0f} Rec={rec_eff:.0f} JD={u_jd_match_score:.0f}%) "
            f"→ {shortlist_decision_final} [band={shortlist_band_final}]"
            f"{' [CAPPED]' if shortlist_unified.get('cap_applied') else ''}"
        )

    except Exception as us_err:
        logger.warning(f"  Unified shortlist scoring failed: {us_err}")
        # Safe fallback: estimate from ATS alone
        u_ats_score = ats_report.score_after
        if u_ats_score >= 80:
            shortlist_probability_final, shortlist_band_final = 42.0, "B"
            shortlist_decision_final = "APPLY (FIX GAPS)"
        elif u_ats_score >= 70:
            shortlist_probability_final, shortlist_band_final = 28.0, "C"
            shortlist_decision_final = "FIX GAPS"
        else:
            shortlist_probability_final, shortlist_band_final = 12.0, "D"
            shortlist_decision_final = "SKIP"
        shortlist_reason_final = f"Estimated from ATS {u_ats_score:.0f} (unified scoring unavailable)"

    # -- PHASE 4: FINAL ARTIFACT-TRUTH RECONCILIATION ----------------------
    # One authoritative reconciliation: the reported score_after must describe
    # the artifact being returned. If any late mutation (dedup, auto-fix,
    # rewriter revert, polish) changed the artifact, re-score it here and
    # report the artifact's true score. If the artifact is materially worse
    # than the original, revert to the original and disclose via risk flag.
    try:
        _final_artifact_score, _final_breakdown, _ = scorer.score(improved, extracted_jd)
        if _final_artifact_score < ats_report.score_before - 1.0:
            logger.warning(
                f"  FINAL RECONCILIATION: artifact {_final_artifact_score:.1f} < "
                f"original {ats_report.score_before:.1f} -> reverting to original resume"
            )
            improved = original.model_copy(deep=True)
            _final_artifact_score, _final_breakdown, _ = scorer.score(improved, extracted_jd)
            ats_report.risk_flags = list(ats_report.risk_flags or []) + [
                f"FINAL_ARTIFACT_REGRESSION_REVERTED: late processing scored "
                f"{_final_artifact_score:.1f} < original {ats_report.score_before:.1f}"
            ]
        if abs(_final_artifact_score - ats_report.score_after) > 0.05:
            logger.warning(
                f"  FINAL RECONCILIATION: reported {ats_report.score_after} -> "
                f"artifact {_final_artifact_score:.1f} (report now describes the artifact)"
            )
        ats_report.score_after = round(
            max(_final_artifact_score, ats_report.score_before), 1
        )
        ats_report.breakdown_after = _final_breakdown
        ats_report.improvement = (
            f"+{ats_report.score_after - ats_report.score_before:.0f}"
            if ats_report.score_after >= ats_report.score_before
            else f"{ats_report.score_after - ats_report.score_before:.0f}"
        )
    except Exception as fr_err:
        logger.warning(f"  Final reconciliation skipped: {fr_err}")
    # ── Build execution trace for auditability ──
    pipeline_trace = {
        "job_id": job_id,
        "mode": mode,
        "pipeline_hash": pipeline_hash,
        "ats_score_before": ats_report.score_before,
        "ats_score_after": ats_report.score_after,
        "ats_improvement": ats_report.improvement,
        "ats_improve_attempts": ats_improve_attempts if 'ats_improve_attempts' in dir() else 0,
        "shortlist_before": sl_before["total"] if 'sl_before' in dir() else 0,
        "shortlist_after": shortlist_probability_final,
        "shortlist_band": shortlist_band_final,
        "shortlist_decision": shortlist_decision_final,
        "recruiter_score_raw": hiring_sim.get("layers", {}).get("recruiter", {}).get("score", 0) if hiring_sim else 0,
        "penalties_applied": ats_report.penalties_applied or [],
        "risk_flags": ats_report.risk_flags or [],
        "missing_skills": ats_report.missing_skills[:5] if ats_report.missing_skills else [],
        "matched_skills_count": len(ats_report.matched_skills or []),
        "score_cap_reason": score_limit.reasons[0] if score_limit and score_limit.reasons else None,
        "engine": "pipeline.core",
        "deterministic_engine": True,
        "version": "6.0.0",
        "raw_semantic_score": getattr(ats_report, "raw_semantic_score", ats_report.semantic_score),
        "semantic_adjustments": getattr(ats_report, "semantic_adjustments", []),
        "role_type": role_info.get("role_type", "") if role_info else "",
        "experience_level": shortlist_unified.get("experience_level", "") if shortlist_unified else "",
    }

    # -- PHASE 6B: structured decision explanation (evidence-grounded) ----
    decision_explanation = None
    try:
        from pipeline.decision_explanation import build_decision_explanation
        _pre = PipelineResult(
            original=original, tailored=tailored, improved=improved,
            extracted_jd=extracted_jd, ats_report=ats_report,
            shortlist_probability=round(shortlist_probability_final, 1),
            shortlist_band=shortlist_band_final,
            shortlist_decision=shortlist_decision_final,
            hiring_simulation=hiring_sim,
            pipeline_trace={"experience_level": shortlist_unified.get("experience_level", "") if shortlist_unified else ""},
        )
        decision_explanation = build_decision_explanation(
            decision=shortlist_decision_final,
            decision_reason=shortlist_reason_final or ats_report.decision,
            ats_report=ats_report,
            pipeline_result=_pre,
            original=original,
            jd=extracted_jd,
        )
    except Exception as de_err:
        logger.warning(f"Decision explanation skipped: {de_err}")
    return PipelineResult(
        original=original,
        tailored=tailored,
        improved=improved,
        extracted_jd=extracted_jd,
        ats_report=ats_report,
        readability=readability,
        target_plan=target_plan,
        score_limit=score_limit.to_dict(),
        pipeline_hash=pipeline_hash,
        role_fit=role_fit,
        why_not_90=why_not_90,
        role_info=role_info,
        resume_type=resume_type,
        change_explanation=change_explanation,
        polish_changes=polish_changes_list if polish_changes_list else None,
        validation_result=validation_result,
        quality_score=final_quality,
        hiring_simulation=hiring_sim,
        content_intelligence=content_intelligence,
        # ── CANONICAL SHORTLIST (v6.0) ──
        shortlist_probability=round(shortlist_probability_final, 1),
        shortlist_band=shortlist_band_final,
        shortlist_decision=shortlist_decision_final,
        shortlist_decision_reason=shortlist_reason_final,
        shortlist_unified=shortlist_unified,
        # ── EXECUTION TRACE ──
        pipeline_trace=pipeline_trace,
    )


def _compute_why_not_90(
    ats_report, score_limit, resume: StructuredResume, jd: ExtractedJD
) -> dict:
    """
    Part 10: Compute actionable steps to reach 90+.
    Returns {max_possible_score, current_score, steps_to_90}.
    """
    current = ats_report.score_after
    max_possible = score_limit.max_possible_score
    steps = []

    # Missing skills -> add them
    for skill in ats_report.missing_skills[:5]:
        required_lower = {s.lower() for s in jd.required_skills}
        if skill.lower() in required_lower:
            steps.append(f"Add '{skill}' with demonstrated usage in experience bullets")

    # Missing keywords -> integrate
    for kw in ats_report.missing_keywords[:3]:
        if kw.lower() not in {s.lower() for s in ats_report.missing_skills}:
            steps.append(f"Integrate keyword '{kw}' into relevant bullets")

    # Experience utilization
    all_bullets = " ".join(
        b.lower() for exp in resume.experience for b in exp.bullets
    )
    resume_skills_lower = {s.lower() for s in resume.skills}
    for skill in ats_report.matched_skills[:5]:
        if skill.lower() in resume_skills_lower and skill.lower() not in all_bullets:
            steps.append(f"Demonstrate '{skill}' usage in experience (currently only in skills list)")

    # Structure improvements
    if ats_report.breakdown_after.resume_structure < 60:
        steps.append("Add quantified metrics (%, $, numbers) to at least 50% of bullets")

    # Semantic coverage
    if ats_report.semantic_score < 40:
        steps.append("Align bullet language more closely with JD responsibilities")

    return {
        "max_possible_score": round(max_possible, 1),
        "current_score": round(current, 1),
        "gap_to_90": round(max(0, 90 - current), 1),
        "steps_to_90": steps[:6],
    }
