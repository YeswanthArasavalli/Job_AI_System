"""
ATS Scoring Engine -- Rule-based, deterministic, brutally honest.

v2.0 Upgrades:
  - Negative scoring (keyword stuffing, domain mismatch, irrelevant experience)
  - Confidence levels (HIGH / MEDIUM / LOW)
  - Risk flags
  - Harsher penalty curve (ratio^1.8)
  - Tighter skill matching (no false positives from stop words)
  - Dynamic year for experience calculation
  - Keyword stuffing detection

Score Breakdown (weighted):
  - Keyword Match:         30%
  - Skills Match:          25%
  - Experience Relevance:  20%
  - Role Alignment:        10%
  - Education Fit:          5%
  - Resume Structure:      10%

After computing the base score, NEGATIVE PENALTIES are applied.
"""

import re
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from ats_scoring.synonyms import are_synonyms, expand_keywords, get_synonyms
from ats_scoring.probability import ShortlistPredictor
from utils.config_loader import load_config, AppConfig
from utils.logger import setup_logger
from utils.models import (
    ATSScoreReport,
    ExtractedJD,
    ScoreBreakdown,
    StructuredResume,
)

logger = setup_logger(__name__)

# Words to ignore when doing skill matching against compound JD requirements
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "of", "in", "to", "for", "with", "on", "at",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "should", "could", "may", "might",
    "must", "shall", "can", "need", "dare", "ought", "used", "not", "no",
    "strong", "excellent", "good", "great", "solid", "proven", "deep",
    "experience", "proficiency", "knowledge", "familiarity", "understanding",
    "ability", "skills", "skill", "similar", "related", "preferred",
    "required", "minimum", "plus", "nice", "bonus", "ideally",
    "years", "year", "yrs", "role", "tools", "tool",
}


class ATSScorer:
    """
    Rule-based ATS scoring engine with negative scoring.

    Usage:
        scorer = ATSScorer()
        report = scorer.compare(original, tailored, jd, job_id="123")
    """

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or load_config()
        self.weights = self.config.ats_scoring.weights
        logger.info(f"ATSScorer initialized | weights={self.weights}")

    # ================================================================
    # Public API
    # ================================================================

    def score(self, resume: StructuredResume, jd: ExtractedJD) -> Tuple[float, ScoreBreakdown, dict]:
        """
        Score a single resume against a JD.

        Returns:
            (total_score, breakdown, details_dict)
        """
        # Input validation -- prevent scoring empty/invalid resumes
        if not resume.skills and not resume.experience:
            logger.warning("SCORING SKIPPED: Resume has no skills and no experience")
            return 0.0, ScoreBreakdown(), {"keywords": {"matched": [], "missing": []}, "skills": {"matched": [], "missing": []}}

        resume_text = self._flatten_resume_text(resume)

        if len(resume_text.strip()) < 50:
            logger.warning(f"SCORING WARNING: Resume text very short ({len(resume_text)} chars)")

        resume_skills_lower = {s.lower().strip() for s in resume.skills}

        # 1. Keyword Match (30%)
        kw_score, kw_details = self._score_keywords(resume_text, resume_skills_lower, jd)

        # 2. Skills Match (25%)
        skills_score, skills_details = self._score_skills(resume_skills_lower, resume_text, jd)

        # 3. Experience Relevance (20%)
        exp_score, exp_details = self._score_experience(resume, resume_text, jd)

        # 4. Role Alignment (10%)
        role_score, role_details = self._score_role_alignment(resume, jd)

        # 5. Education Fit (5%)
        edu_score, edu_details = self._score_education(resume, jd)

        # 6. Resume Structure (10%)
        struct_score, struct_details = self._score_structure(resume)

        # Build breakdown (before penalties)
        breakdown = ScoreBreakdown(
            keyword_match=round(kw_score, 1),
            skills_match=round(skills_score, 1),
            experience_relevance=round(exp_score, 1),
            role_alignment=round(role_score, 1),
            education_fit=round(edu_score, 1),
            resume_structure=round(struct_score, 1),
        )

        # Weighted total (before penalties)
        base_total = (
            kw_score * self.weights.get("keyword_match", 0.30)
            + skills_score * self.weights.get("skills_match", 0.25)
            + exp_score * self.weights.get("experience_relevance", 0.20)
            + role_score * self.weights.get("role_alignment", 0.10)
            + edu_score * self.weights.get("education_fit", 0.05)
            + struct_score * self.weights.get("resume_structure", 0.10)
        )

        # -- NEGATIVE SCORING ------------------------------
        penalties, penalty_points, risk_flags = self._apply_negative_scoring(
            resume, resume_text, jd, kw_details, skills_details, breakdown
        )

        final_total = max(0, base_total - penalty_points)

        # Apply score caps from critical skill gaps
        for flag in risk_flags:
            if "SCORE_CAPPED" in flag and "SOFT" not in flag:
                final_total = min(final_total, 40.0)
            elif "SCORE_SOFT_CAP" in flag:
                final_total = min(final_total, 60.0)

        final_total = round(final_total, 1)

        details = {
            "keywords": kw_details,
            "skills": skills_details,
            "experience": exp_details,
            "role": role_details,
            "education": edu_details,
            "structure": struct_details,
            "penalties": penalties,
            "risk_flags": risk_flags,
            "base_score": round(base_total, 1),
            "penalty_points": round(penalty_points, 1),
        }

        return final_total, breakdown, details

    def compare(
        self,
        original: StructuredResume,
        tailored: StructuredResume,
        jd: ExtractedJD,
        job_id: str = "",
    ) -> ATSScoreReport:
        """Score both resumes, compute semantic match, apply hard rejections, return decision."""
        from ats_scoring.semantic_matcher import SemanticMatcher

        logger.info("=" * 60)
        logger.info("ATS SCORER -- Scoring original resume...")
        score_before, breakdown_before, details_before = self.score(original, jd)
        logger.info(f"  Original score: {score_before}")

        logger.info("ATS SCORER -- Scoring tailored resume...")
        score_after, breakdown_after, details_after = self.score(tailored, jd)
        logger.info(f"  Tailored score: {score_after}")

        # improvement computed after dampening/rejection below

        matched_kw = sorted(set(details_after["keywords"].get("matched", [])))
        missing_kw = sorted(set(details_after["keywords"].get("missing", [])))
        matched_skills = sorted(set(details_after["skills"].get("matched", [])))
        missing_skills = sorted(set(details_after["skills"].get("missing", [])))

        # -- Semantic Matching (TF-IDF + phrase + embeddings) -
        semantic_score = 0.0
        try:
            matcher = SemanticMatcher()
            resume_bullets = []
            for exp in tailored.experience:
                resume_bullets.extend(exp.bullets)
            for proj in tailored.projects:
                resume_bullets.extend(proj.bullets)

            if jd.responsibilities and resume_bullets:
                semantic_score = matcher.match_responsibilities(
                    jd.responsibilities, resume_bullets
                )
            elif resume_bullets:
                # FALLBACK: When responsibilities=0, compute overall similarity
                # between JD required_skills/keywords text and resume bullets
                jd_text = " ".join(jd.required_skills + jd.keywords)
                resume_text = " ".join(resume_bullets)
                if jd_text.strip():
                    semantic_score = matcher.overall_similarity(jd_text, resume_text)
                    logger.info(
                        f"  Semantic fallback (no responsibilities): "
                        f"overall_similarity = {semantic_score}%"
                    )

            # -- Keyword overlap floor (tiered) ----------------
            kw_overlap = len(set(details_after["keywords"].get("matched", [])))
            skill_overlap = len(set(details_after.get("skills", {}).get("matched", [])))
            total_overlap = kw_overlap + skill_overlap

            # Tiered semantic floor based on overlap strength
            # NEVER allow semantic=0 when real overlap exists
            if total_overlap >= 8 and semantic_score < 50:
                logger.info(
                    f"  Semantic floor applied: {semantic_score}% -> 50% "
                    f"(overlap={total_overlap})"
                )
                semantic_score = 50.0
            elif total_overlap >= 5 and semantic_score < 40:
                logger.info(
                    f"  Semantic floor applied: {semantic_score}% -> 40% "
                    f"(overlap={total_overlap})"
                )
                semantic_score = 40.0
            elif total_overlap >= 3 and semantic_score < 20:
                logger.info(
                    f"  Semantic floor applied: {semantic_score}% -> 20% "
                    f"(overlap={total_overlap})"
                )
                semantic_score = 20.0

            logger.info(f"  Semantic match: {semantic_score}%")
        except Exception as e:
            logger.warning(f"Semantic matching failed: {e}")

        # -- Semantic Dampening -----------------------------
        # If resume bullets don't semantically cover JD responsibilities,
        # the keyword score alone is inflated. Apply dampening.
        if semantic_score > 0 and semantic_score < 50:
            # Linear dampening: 50% semantic -> 0% cut, 0% semantic -> 20% cut
            dampen_factor = 1.0 - (0.20 * (1.0 - semantic_score / 50.0))
            score_after_dampened = score_after * dampen_factor
            dampen_points = score_after - score_after_dampened
            if dampen_points > 1:
                score_after = round(score_after_dampened, 1)
                details_after.setdefault("penalties", [])
                details_after["penalties"].append(
                    f"Semantic dampening (-{dampen_points:.0f}): low responsibility coverage"
                )
                logger.info(f"  Semantic dampening: -{dampen_points:.1f} pts (coverage={semantic_score}%)")

        # -- Hard Rejection Rules --------------------------
        hard_rejection, rejection_reason = self._check_hard_rejection(
            score_after, breakdown_after, details_after, jd, tailored
        )

        if hard_rejection:
            # Cap score for resumes needing significant improvement
            score_after = min(score_after, 50.0)
            details_after.setdefault("risk_flags", [])
            details_after["risk_flags"].append(f"NEEDS_IMPROVEMENT: {rejection_reason}")

        # -- Decision Logic --------------------------------
        decision = self._make_decision(score_after, semantic_score, details_after)

        # -- Effort Estimation -----------------------------
        effort = self._estimate_effort(score_before, score_after, details_after)

        # -- CONSISTENCY ENFORCEMENT -----------------------
        # When no change occurred (tailoring didn't alter score),
        # decision + effort must align.  No contradictions.
        improvement = score_after - score_before
        if abs(improvement) < 1:
            # No meaningful change → decision stays, but effort = LOW
            effort = "LOW"
        elif improvement < 0:
            # Score degraded → flag but don't override decision
            effort = max(effort, "MEDIUM") if effort != "HIGH" else "HIGH"

        # Decision must align with score (4-tier calibrated system)
        if score_after >= 70 and decision in ("IMPROVE", "APPLY_WITH_FIXES"):
            decision = "APPLY"
        elif score_after >= 55 and decision == "IMPROVE":
            decision = "APPLY_WITH_FIXES"
        elif score_after < 40 and decision in ("APPLY", "APPLY_WITH_FIXES"):
            decision = "IMPROVE"

        recommendations = self._generate_recommendations(
            score_after, breakdown_after, details_after, jd, tailored
        )

        confidence = self._calculate_confidence(jd, details_after)
        risk_flags = details_after.get("risk_flags", [])
        penalties_applied = details_after.get("penalties", [])

        # -- Role Fit Assessment (Part 8) -----------------------
        role_fit = self._compute_role_fit(
            score_after, semantic_score, breakdown_after, details_after, jd
        )

        # Compute improvement AFTER all score modifications
        improvement_str = f"+{improvement:.0f}" if improvement >= 0 else f"{improvement:.0f}"

        report = ATSScoreReport(
            job_id=job_id,
            score_before=round(score_before, 1),
            score_after=round(score_after, 1),
            improvement=improvement_str,
            breakdown_before=breakdown_before,
            breakdown_after=breakdown_after,
            matched_keywords=matched_kw,
            missing_keywords=missing_kw,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            recommendations=recommendations,
            confidence_level=confidence,
            risk_flags=risk_flags,
            penalties_applied=penalties_applied,
            decision=decision,
            semantic_score=semantic_score,
            effort_level=effort,
            role_fit=role_fit,
        )

        # Shortlist probability (safe -- never breaks pipeline)
        try:
            predictor = ShortlistPredictor()
            prob = predictor.predict(report)
            report.shortlist_probability = prob
            prob_display = f"{prob['shortlist_probability']}%"
        except Exception as e:
            logger.warning(f"Probability prediction failed: {e}")
            prob_display = "N/A"

        logger.info(
            f"ATS SCORER -- {improvement_str} | "
            f"Decision: {decision} | Probability: {prob_display} | Effort: {effort}"
        )
        logger.info("=" * 60)

        return report

    # ================================================================
    # NEEDS IMPROVEMENT DETECTION (v4 -- career assistant mode)
    # ================================================================

    def _check_hard_rejection(
        self,
        score: float,
        breakdown: ScoreBreakdown,
        details: dict,
        jd: ExtractedJD,
        resume: StructuredResume,
    ) -> Tuple[bool, str]:
        """
        Check if the resume needs significant improvement.
        Returns flags but does NOT hard-reject -- acts as career assistant.
        """
        # Rule 1: Missing >80% of required skills
        missing_skills = details.get("skills", {}).get("missing", [])
        required = [s.lower().strip() for s in jd.required_skills if s.strip()]
        if required:
            required_set = set(required)
            missing_set = set(missing_skills)
            missing_ratio = len(required_set & missing_set) / len(required_set) if required_set else 0
            if missing_ratio > 0.8:
                return True, f"NEEDS_IMPROVEMENT: Missing {missing_ratio:.0%} of required skills"

        # Rule 2: Experience way below requirement
        exp_details = details.get("experience", {})
        resume_years = exp_details.get("resume_years", None)
        required_years = exp_details.get("required_years", None)
        if resume_years is not None and required_years is not None:
            if required_years > 0 and resume_years < required_years * 0.3:
                return True, f"NEEDS_IMPROVEMENT: Experience ({resume_years}yr) below requirement ({required_years}yr)"

        # Rule 3: Complete domain mismatch
        if breakdown.role_alignment < 3 and breakdown.skills_match < 20:
            return True, "NEEDS_IMPROVEMENT: Significant domain gap"

        return False, ""

    # ================================================================
    # DECISION ENGINE (v3)
    # ================================================================

    def _make_decision(self, score: float, semantic_score: float, details: dict) -> str:
        """
        Make 4-tier decision (Part 1 — Decision Calibration).
        
        Tiers:
          DO_NOT_APPLY  — score < 40: fundamentally wrong fit
          IMPROVE       — 40-55: too many gaps, fix first
          APPLY_WITH_FIXES — 55-70: decent fit, specific fixes needed
          APPLY         — 70+: strong fit, apply now
        
        Multi-signal: ATS score + semantic + skill coverage all factor in.
        """
        risk_flags = details.get("risk_flags", [])
        has_needs_improvement = any("NEEDS_IMPROVEMENT" in f for f in risk_flags)

        # User preference: min score threshold
        min_threshold = getattr(self.config, 'user_preferences', None)
        if min_threshold and hasattr(min_threshold, 'min_score_threshold'):
            if min_threshold.min_score_threshold > 0 and score < min_threshold.min_score_threshold:
                return "IMPROVE"

        # Skill coverage signal
        matched = details.get("skills", {}).get("matched", [])
        missing = details.get("skills", {}).get("missing", [])
        total = len(matched) + len(missing)
        skill_coverage = (len(matched) / max(total, 1)) * 100

        # Multi-signal decision matrix
        high_ats = score >= 65
        mid_ats = score >= 45
        low_ats = score < 40
        high_sem = semantic_score >= 45
        mid_sem = semantic_score >= 25
        good_skills = skill_coverage >= 60
        great_skills = skill_coverage >= 70

        # -- TIER 1: DO_NOT_APPLY (fundamental mismatch) --
        if low_ats and not good_skills:
            return "DO_NOT_APPLY"
        if has_needs_improvement and score < 35:
            return "DO_NOT_APPLY"

        # -- TIER 4: APPLY (strong fit) --
        if high_ats and great_skills and not has_needs_improvement:
            return "APPLY"
        if high_ats and (high_sem or good_skills) and not has_needs_improvement:
            return "APPLY"
        if mid_ats and high_sem and good_skills and not has_needs_improvement:
            return "APPLY"

        # -- TIER 3: APPLY_WITH_FIXES (decent fit, specific fixes) --
        if mid_ats and (mid_sem or good_skills):
            return "APPLY_WITH_FIXES"
        if high_ats and not mid_sem:
            return "APPLY_WITH_FIXES"  # High ATS but low semantic

        # -- TIER 2: IMPROVE (too many gaps) --
        return "IMPROVE"

    def _estimate_effort(self, score_before: float, score_after: float, details: dict) -> str:
        """
        Estimate effort needed to make this application competitive.
        LOW = already strong match, MEDIUM = some work needed, HIGH = significant rewrite.
        """
        improvement_needed = 80 - score_after  # Gap to "strong" threshold

        if improvement_needed <= 5:
            return "LOW"
        elif improvement_needed <= 25:
            return "MEDIUM"
        else:
            return "HIGH"

    # ================================================================
    # ROLE FIT ASSESSMENT (Part 8)
    # ================================================================

    def _compute_role_fit(
        self,
        score: float,
        semantic_score: float,
        breakdown: ScoreBreakdown,
        details: dict,
        jd: ExtractedJD,
    ) -> dict:
        """
        Part 8: Compute role fit level with reason.
        Returns {"level": "HIGH/MEDIUM/LOW", "reason": "..."}.
        """
        # Gather signals
        matched = details.get("skills", {}).get("matched", [])
        missing = details.get("skills", {}).get("missing", [])
        total_skills = len(matched) + len(missing)
        skill_coverage = len(matched) / max(total_skills, 1)

        # Determine strengths
        strengths = []
        if skill_coverage >= 0.7:
            strengths.append("strong skill match")
        if breakdown.experience_relevance >= 60:
            strengths.append("relevant experience")
        if breakdown.role_alignment >= 60:
            strengths.append("role alignment")
        if semantic_score >= 40:
            strengths.append("semantic alignment")
        if breakdown.keyword_match >= 60:
            strengths.append("keyword coverage")

        # Compute level
        if score >= 70 and len(strengths) >= 3:
            level = "HIGH"
        elif score >= 50 and len(strengths) >= 2:
            level = "MEDIUM"
        else:
            level = "LOW"

        # Build reason
        if strengths:
            reason = f"{' + '.join(strengths[:3])} alignment"
        else:
            reason = "Significant gaps in skills, experience, or domain match"

        return {"level": level, "reason": reason.capitalize()}

    # ================================================================
    # NEGATIVE SCORING (new)
    # ================================================================

    def _apply_negative_scoring(
        self,
        resume: StructuredResume,
        resume_text: str,
        jd: ExtractedJD,
        kw_details: dict,
        skills_details: dict,
        breakdown: ScoreBreakdown,
    ) -> Tuple[List[str], float, List[str]]:
        """
        Apply negative scoring. Returns (penalty_descriptions, total_penalty_points, risk_flags).
        """
        penalties = []
        risk_flags = []
        total_penalty = 0.0

        # -- 1. Keyword Stuffing Detection ------------------
        stuffing_penalty = self._detect_keyword_stuffing(resume_text, resume)
        if stuffing_penalty > 0:
            penalties.append(f"Keyword stuffing detected (-{stuffing_penalty:.0f})")
            risk_flags.append("KEYWORD_STUFFING: Abnormal keyword repetition detected")
            total_penalty += stuffing_penalty

        # -- 2. Domain Mismatch -----------------------------
        domain_penalty = self._detect_domain_mismatch(resume, jd)
        if domain_penalty > 0:
            penalties.append(f"Domain mismatch (-{domain_penalty:.0f})")
            risk_flags.append("DOMAIN_MISMATCH: Resume domain differs significantly from JD")
            total_penalty += domain_penalty

        # -- 3. Critical Skills Missing ---------------------
        missing_critical = self._check_critical_skills_missing(skills_details, jd)
        if missing_critical > 0:
            penalties.append(f"Critical required skills missing (-{missing_critical:.0f})")
            risk_flags.append("CRITICAL_SKILLS_GAP: Core required skills not found")
            total_penalty += missing_critical

        # -- 3b. Score Capping for skill gaps ---------------
        # If too many required skills are missing, CAP the score
        missing_ratio = self._get_required_missing_ratio(skills_details, jd)
        if missing_ratio > 0.6:
            risk_flags.append(f"SCORE_CAPPED: {missing_ratio:.0%} required skills missing, max score 40")
        elif missing_ratio > 0.4:
            risk_flags.append(f"SCORE_SOFT_CAP: {missing_ratio:.0%} required skills missing, max score 60")

        # -- 4. No Relevant Experience ----------------------
        if breakdown.experience_relevance < 25:
            exp_penalty = 8
            penalties.append(f"Very low experience relevance (-{exp_penalty})")
            risk_flags.append("EXPERIENCE_GAP: Resume experience doesn't match JD responsibilities")
            total_penalty += exp_penalty

        # -- 5. Generic/Vague Resume ------------------------
        vague_penalty = self._detect_vague_resume(resume)
        if vague_penalty > 0:
            penalties.append(f"Generic/vague content detected (-{vague_penalty:.0f})")
            risk_flags.append("VAGUE_CONTENT: Too many generic phrases without specifics")
            total_penalty += vague_penalty

        # -- 6. Experience Utilization (Part 2) ----------------
        # Skills in skills list but NOT in experience bullets = penalty
        util_penalty, util_flag = self._check_experience_utilization(resume, jd)
        if util_penalty > 0:
            penalties.append(f"Skills not demonstrated in experience bullets (-{util_penalty:.0f})")
            risk_flags.append(util_flag)
            total_penalty += util_penalty

        # -- 7. Broken/Incomplete Bullets (v5.1.2) ----------------
        # Real ATS parsers penalize malformed content
        all_exp_bullets = [b for exp in resume.experience for b in exp.bullets]
        broken_count = 0
        incomplete_count = 0
        for b in all_exp_bullets:
            stripped = b.rstrip()
            # Broken: ends with conjunction + period or dangling comma
            if re.search(r',?\s+(?:and|or|but|with)\.\s*$', stripped):
                broken_count += 1
            elif stripped.endswith(','):
                incomplete_count += 1
            # Very short fragments (< 20 chars) are incomplete
            elif len(stripped) < 20:
                incomplete_count += 1
        if broken_count > 0:
            bp = min(10, broken_count * 5)
            penalties.append(f"Broken sentences detected ({broken_count}) (-{bp})")
            risk_flags.append(f"BROKEN_CONTENT: {broken_count} bullets have broken endings")
            total_penalty += bp
        if incomplete_count > 0:
            ip = min(10, incomplete_count * 3)
            penalties.append(f"Incomplete bullets detected ({incomplete_count}) (-{ip})")
            risk_flags.append(f"INCOMPLETE_CONTENT: {incomplete_count} bullets are fragments")
            total_penalty += ip

        # -- 8. Repeated bullet openings -------------------------
        if len(all_exp_bullets) >= 3:
            openings = [" ".join(b.lower().split()[:3]) for b in all_exp_bullets]
            from collections import Counter
            opening_counts = Counter(openings)
            repeat_penalty = sum(
                (c - 2) * 2 for c in opening_counts.values() if c > 2
            )
            if repeat_penalty > 0:
                repeat_penalty = min(8, repeat_penalty)
                penalties.append(f"Repeated bullet openings (-{repeat_penalty})")
                risk_flags.append("REPETITIVE_CONTENT: Multiple bullets start the same way")
                total_penalty += repeat_penalty

        return penalties, total_penalty, risk_flags

    def _check_experience_utilization(
        self, resume: StructuredResume, jd: ExtractedJD
    ) -> Tuple[float, str]:
        """
        Part 2: Check if required skills are demonstrated in experience.
        Skills listed in skills section but NOT mentioned in ANY bullet
        get penalized because ATS systems look for demonstrated usage.
        """
        required = [s.lower().strip() for s in jd.required_skills if s.strip()]
        if not required:
            return 0.0, ""

        # Build all experience text
        all_bullets = " ".join(
            b.lower() for exp in resume.experience for b in exp.bullets
        )
        # Also include project bullets
        all_project_text = " ".join(
            b.lower() for proj in resume.projects for b in proj.bullets
        ) if resume.projects else ""
        combined = all_bullets + " " + all_project_text

        resume_skills = {s.lower() for s in resume.skills}

        # Check how many required skills are (a) in skills list but (b) not in any bullet
        listed_not_demonstrated = []
        for skill in required:
            # Normalize check
            skill_n = self._normalize_skill(skill)
            if skill_n in resume_skills or skill in resume_skills:
                # Skill IS in skills list -- but is it demonstrated?
                if skill not in combined and skill_n not in combined:
                    listed_not_demonstrated.append(skill)

        if not listed_not_demonstrated:
            return 0.0, ""

        ratio = len(listed_not_demonstrated) / len(required)
        if ratio > 0.5:
            penalty = 6
        elif ratio > 0.3:
            penalty = 3
        else:
            penalty = 0

        flag = (
            f"SKILLS_NOT_DEMONSTRATED: {len(listed_not_demonstrated)} required skills "
            f"listed but not shown in experience: {', '.join(listed_not_demonstrated[:3])}"
        )
        return penalty, flag

    def _detect_keyword_stuffing(self, resume_text: str, resume: StructuredResume) -> float:
        """
        Detect abnormal keyword repetition, normalized by resume length.
        Ignores skills section itself (where repetition is natural).
        """
        text_lower = resume_text.lower()
        word_count = len(text_lower.split())
        penalty = 0.0

        # Don't penalize short resumes -- they naturally repeat
        if word_count < 200:
            return 0.0

        # Normalize threshold by resume length
        # A keyword-rich resume with 4+ experience entries naturally repeats terms
        base_threshold = max(6, int(word_count / 80))

        for skill in resume.skills:
            skill_lower = skill.lower()
            if len(skill_lower) < 4:
                continue  # Skip short terms ("sql", "c++", etc.)
            count = text_lower.count(skill_lower)
            if count > base_threshold * 2:
                penalty += 3  # Heavy stuffing (reduced from 5)
            elif count > base_threshold:
                penalty += 1  # Mild stuffing (reduced from 2)

        return min(penalty, 15)  # Cap at 15 points

    def _detect_domain_mismatch(self, resume: StructuredResume, jd: ExtractedJD) -> float:
        """
        Detect domain mismatch WITH transferable skill credit.
        Adjacent domains (backend↔data, data↔ml) get reduced penalty.
        """
        domain_clusters = {
            "frontend": {"react", "angular", "vue", "html", "css", "sass", "javascript", "typescript", "ui", "ux"},
            "backend": {"django", "flask", "fastapi", "spring", "node.js", "express", "rest api", "microservices"},
            "data": {"sql", "pandas", "numpy", "tableau", "power bi", "etl", "data analysis", "statistics", "spark"},
            "ml": {"machine learning", "deep learning", "tensorflow", "pytorch", "nlp", "computer vision", "scikit-learn"},
            "devops": {"docker", "kubernetes", "terraform", "ci/cd", "aws", "gcp", "azure", "jenkins"},
            "mobile": {"swift", "kotlin", "flutter", "react native", "ios", "android"},
        }

        # Transferable skill adjacency -- domains that share significant overlap
        # 0 = no transfer, 1 = strong transfer
        adjacency = {
            ("backend", "data"): 0.6,      # Python, SQL, APIs are shared
            ("backend", "devops"): 0.5,     # Infrastructure knowledge overlaps
            ("backend", "ml"): 0.4,         # Python + data pipelines
            ("data", "ml"): 0.7,            # Heavy overlap (Python, stats, data)
            ("frontend", "mobile"): 0.5,    # UI/UX, JS/TS, React Native
            ("frontend", "backend"): 0.3,   # Full-stack adjacent
            ("devops", "data"): 0.3,        # Cloud + pipeline infra
            ("devops", "ml"): 0.3,          # MLOps overlap
        }

        def get_adjacency(d1: str, d2: str) -> float:
            return adjacency.get((d1, d2), adjacency.get((d2, d1), 0.0))

        # Determine JD domain
        jd_text = " ".join(jd.required_skills + jd.keywords).lower()
        jd_domains = {}
        for domain, keywords in domain_clusters.items():
            matches = sum(1 for kw in keywords if kw in jd_text)
            if matches >= 2:
                jd_domains[domain] = matches

        # Determine resume domain
        resume_skills_text = " ".join(resume.skills).lower()
        resume_text = self._flatten_resume_text(resume).lower()
        resume_domains = {}
        for domain, keywords in domain_clusters.items():
            matches = sum(1 for kw in keywords if kw in resume_skills_text or kw in resume_text)
            if matches >= 2:
                resume_domains[domain] = matches

        if not jd_domains or not resume_domains:
            return 0

        top_jd_domain = max(jd_domains, key=jd_domains.get)

        # Direct match -- no penalty
        if top_jd_domain in resume_domains:
            return 0

        # Check transferable credit from adjacent domains
        jd_set = set(jd_domains.keys())
        resume_set = set(resume_domains.keys())

        if jd_set & resume_set:
            return 2  # Some domain overlap exists

        # No direct overlap -- check adjacency for partial credit
        best_adjacency = 0.0
        for r_domain in resume_set:
            adj = get_adjacency(top_jd_domain, r_domain)
            best_adjacency = max(best_adjacency, adj)

        if best_adjacency >= 0.5:
            return 3   # Strong transferable skills (e.g., backend->data)
        elif best_adjacency >= 0.3:
            return 6   # Moderate transfer (e.g., frontend->backend)
        else:
            return 10  # No meaningful transfer

    def _check_critical_skills_missing(self, skills_details: dict, jd: ExtractedJD) -> float:
        """
        Penalize if >50% of REQUIRED skills are missing.
        Required skills are non-negotiable for most ATS systems.
        """
        missing = skills_details.get("missing", [])
        required = [s.lower().strip() for s in jd.required_skills if s.strip()]

        if not required:
            return 0

        # Count how many missing skills are from the required list
        required_set = set(required)
        missing_set = set(missing)
        missing_required = required_set & missing_set

        ratio = len(missing_required) / len(required_set) if required_set else 0

        if ratio > 0.6:
            return 10  # Majority of required skills missing
        elif ratio > 0.3:
            return 5
        return 0

    def _get_required_missing_ratio(self, skills_details: dict, jd: ExtractedJD) -> float:
        """Get ratio of required skills that are missing (0.0 to 1.0)."""
        missing = skills_details.get("missing", [])
        required = [s.lower().strip() for s in jd.required_skills if s.strip()]
        if not required:
            return 0.0
        required_set = set(required)
        missing_set = set(missing)
        return len(required_set & missing_set) / len(required_set)

    def _detect_vague_resume(self, resume: StructuredResume) -> float:
        """
        Detect overuse of generic phrases without specifics.
        Penalizes buzzword-heavy, metric-light resumes.
        """
        vague_phrases = [
            "responsible for", "worked on", "helped with", "assisted in",
            "involved in", "participated in", "contributed to",
            "various", "multiple", "several", "numerous",
            "team player", "hard worker", "fast learner", "self-motivated",
            "detail-oriented", "results-driven", "go-getter",
        ]

        all_bullets = []
        for exp in resume.experience:
            all_bullets.extend(exp.bullets)
        for proj in resume.projects:
            all_bullets.extend(proj.bullets)

        if not all_bullets:
            return 0

        vague_count = 0
        for bullet in all_bullets:
            bullet_lower = bullet.lower()
            if any(phrase in bullet_lower for phrase in vague_phrases):
                vague_count += 1

        vague_ratio = vague_count / len(all_bullets)

        if vague_ratio > 0.5:
            return 8
        elif vague_ratio > 0.3:
            return 4
        return 0

    # ================================================================
    # Confidence Level
    # ================================================================

    def _calculate_confidence(self, jd: ExtractedJD, details: dict) -> str:
        """
        Calculate confidence level based on JD quality and scoring data availability.

        HIGH: Rich JD with many skills/keywords/responsibilities parsed
        MEDIUM: Adequate JD data
        LOW: Sparse JD or fallback data used
        """
        signals = 0

        if len(jd.required_skills) >= 3:
            signals += 1
        if len(jd.keywords) >= 5:
            signals += 1
        if len(jd.responsibilities) >= 3:
            signals += 1
        if jd.job_title:
            signals += 1
        if jd.required_experience_years is not None:
            signals += 1

        if signals >= 4:
            return "HIGH"
        elif signals >= 2:
            return "MEDIUM"
        else:
            return "LOW"

    # ================================================================
    # Sub-scorers (each returns 0-100)
    # ================================================================

    def _score_keywords(
        self,
        resume_text: str,
        resume_skills_lower: Set[str],
        jd: ExtractedJD,
    ) -> Tuple[float, dict]:
        """Keyword matching: exact, partial, and synonym."""
        jd_keywords = [kw.lower().strip() for kw in jd.keywords if kw.strip()]
        if not jd_keywords:
            return 50.0, {"matched": [], "missing": [], "note": "No keywords in JD"}

        resume_lower = resume_text.lower()
        matched = []
        missing = []

        for kw in jd_keywords:
            if self._keyword_found(kw, resume_lower, resume_skills_lower):
                matched.append(kw)
            else:
                missing.append(kw)

        raw_ratio = len(matched) / len(jd_keywords)
        score = self._apply_penalty_curve(raw_ratio) * 100

        return round(score, 1), {"matched": matched, "missing": missing}

    def _score_skills(
        self,
        resume_skills_lower: Set[str],
        resume_text: str,
        jd: ExtractedJD,
    ) -> Tuple[float, dict]:
        """Skills matching with required (70%) and preferred (30%) weighting."""
        resume_lower = resume_text.lower()

        # Required skills (70%)
        required = [s.lower().strip() for s in jd.required_skills if s.strip()]
        req_matched = []
        req_missing = []
        for skill in required:
            if self._skill_found_strict(skill, resume_skills_lower, resume_lower):
                req_matched.append(skill)
            else:
                req_missing.append(skill)

        req_ratio = len(req_matched) / max(len(required), 1)

        # Preferred skills (30%)
        preferred = [s.lower().strip() for s in jd.preferred_skills if s.strip()]
        pref_matched = []
        pref_missing = []
        for skill in preferred:
            if self._skill_found_strict(skill, resume_skills_lower, resume_lower):
                pref_matched.append(skill)
            else:
                pref_missing.append(skill)

        pref_ratio = len(pref_matched) / max(len(preferred), 1)

        if required and preferred:
            raw_score = (req_ratio * 0.7 + pref_ratio * 0.3) * 100
        elif required:
            raw_score = req_ratio * 100
        elif preferred:
            raw_score = pref_ratio * 100
        else:
            raw_score = 50.0

        score = self._apply_penalty_curve(raw_score / 100) * 100

        all_matched = req_matched + pref_matched
        all_missing = req_missing + pref_missing

        return round(score, 1), {"matched": all_matched, "missing": all_missing}

    def _score_experience(
        self,
        resume: StructuredResume,
        resume_text: str,
        jd: ExtractedJD,
    ) -> Tuple[float, dict]:
        """Experience relevance: years match + responsibility coverage + impact quality."""
        details = {}

        # --- Years of experience (30%) ---
        resume_years = self._estimate_experience_years(resume)
        required_years = jd.required_experience_years

        if required_years and required_years > 0:
            ratio = resume_years / required_years
            if ratio >= 1.0:
                # Meets or exceeds — but slight dampening for massive overqualification
                if ratio > 2.0:
                    years_score = 85.0  # Overqualified: might be flight risk
                else:
                    years_score = 100.0
            else:
                # Nonlinear penalty: ratio^1.5 means small gaps hurt less, big gaps hurt a lot
                years_score = (ratio ** 1.5) * 100.0
            details["resume_years"] = resume_years
            details["required_years"] = required_years
        else:
            years_score = 55.0
            details["note_years"] = "No specific years requirement in JD"

        # --- Responsibility coverage (45%) ---
        responsibilities = [r.lower().strip() for r in jd.responsibilities if r.strip()]
        resume_lower = resume_text.lower()

        if responsibilities:
            matched_resp = []
            for resp in responsibilities:
                key_phrases = self._extract_key_phrases(resp)
                if any(phrase in resume_lower for phrase in key_phrases):
                    matched_resp.append(resp)

            resp_ratio = len(matched_resp) / len(responsibilities)
            resp_score = self._apply_penalty_curve(resp_ratio) * 100
            details["responsibilities_matched"] = len(matched_resp)
            details["responsibilities_total"] = len(responsibilities)
        else:
            resp_score = 45.0
            details["note_resp"] = "No responsibilities listed in JD"

        # --- Impact quality (20%) — business impact scoring ---
        impact_score = self._score_impact_quality(resume)
        details["impact_score"] = round(impact_score, 1)

        # --- Skill demonstration in experience (20%) --- NEW ---
        # Rewards skills that appear in the skills section AND in experience bullets.
        # This is the single most important ATS signal: demonstrating skills through use.
        demo_score = self._score_skill_demonstration(resume, jd)
        details["skill_demonstration"] = round(demo_score, 1)

        score = (
            years_score * 0.25
            + resp_score * 0.35
            + impact_score * 0.20
            + demo_score * 0.20
        )

        return round(score, 1), details

    def _score_skill_demonstration(
        self, resume: StructuredResume, jd: ExtractedJD
    ) -> float:
        """
        Score how well resume skills are demonstrated in experience bullets.
        
        Skills listed in skills section + appearing in bullets = demonstrated.
        Tool-purpose phrasing ('used X for Y') scores higher than bare mentions.
        
        Returns 0-100.
        """
        if not resume.skills or not resume.experience:
            return 40.0  # Baseline

        all_bullets_lower = " ".join(
            b.lower() for exp in resume.experience for b in exp.bullets
        )
        # Also check project bullets (secondary credit)
        all_proj_lower = " ".join(
            b.lower() for proj in resume.projects for b in proj.bullets
        )

        # JD-relevant skills (intersection of resume skills with JD requirements)
        jd_skills = set(s.lower() for s in jd.required_skills + jd.preferred_skills)
        resume_skills = set(s.lower() for s in resume.skills)
        relevant_skills = resume_skills & jd_skills if jd_skills else resume_skills

        if not relevant_skills:
            return 50.0  # No overlap to evaluate

        demonstrated = 0
        purpose_bonus = 0

        # Purpose/context patterns that indicate real usage (not just mention)
        purpose_patterns = [
            r'(?:using|leveraging|utilizing|applying|with)\s+{skill}\s+(?:to|for|in)\b',
            r'{skill}\s+(?:to|for)\s+\w+',
            r'(?:built|developed|designed|implemented|created)\s+.*{skill}',
        ]

        for skill in relevant_skills:
            skill_lower = skill.lower()
            # Check direct mention in experience
            in_exp = skill_lower in all_bullets_lower
            in_proj = skill_lower in all_proj_lower
            # Also check significant terms for multi-word skills
            terms = [t for t in skill_lower.split() if len(t) > 3]
            if not in_exp and terms:
                in_exp = any(t in all_bullets_lower for t in terms)

            if in_exp:
                demonstrated += 1
                # Bonus for purposeful usage (not just bare mention)
                for pattern_template in purpose_patterns:
                    escaped_skill = re.escape(skill_lower)
                    pattern = pattern_template.replace('{skill}', escaped_skill)
                    if re.search(pattern, all_bullets_lower):
                        purpose_bonus += 1
                        break
            elif in_proj:
                demonstrated += 0.5  # Half credit for project-only

        # Calculate scores
        demo_ratio = demonstrated / len(relevant_skills)
        purpose_ratio = purpose_bonus / max(1, demonstrated)

        # Base score from demonstration ratio (0-70 range)
        base = min(70, demo_ratio * 70)
        # Purpose bonus (0-30 range, for tool-purpose phrasing)
        bonus = min(30, purpose_ratio * 30)

        return round(base + bonus, 1)

    def _score_impact_quality(self, resume: StructuredResume) -> float:
        """
        Score resume bullets for business impact quality.
        
        Impact hierarchy (business > technical):
          revenue/sales/growth     → +30 per bullet
          cost_saving/efficiency   → +25 per bullet
          accuracy/quality         → +20 per bullet
          performance/speed        → +15 per bullet
          generic metrics          → +10 per bullet
        
        Returns 0-100 score.
        """
        all_bullets = []
        for exp in resume.experience:
            all_bullets.extend(exp.bullets)
        for proj in resume.projects:
            all_bullets.extend(proj.bullets)

        if not all_bullets:
            return 30.0  # Baseline

        total_impact = 0
        impact_count = 0

        # Impact type patterns (ordered by business value)
        impact_patterns = [
            # Revenue / business growth
            (30, [r'(?:revenue|sales|growth|roi|conversion|profit)',
                  r'\$\d+[KkMmBb]', r'(?:grew|generated|drove)\b.*\d+']),
            # Cost saving / efficiency
            (25, [r'(?:reduced|saved|cut)\s+(?:cost|spend|budget|time)',
                  r'(?:saving|efficiency)\b.*\d+']),
            # Accuracy / quality
            (20, [r'(?:accuracy|precision|recall|f1|auc)\b.*\d+',
                  r'\d+%\s*(?:accuracy|precision)']),
            # Performance / speed
            (15, [r'(?:latency|throughput|uptime|response\s+time)',
                  r'(?:faster|reduced)\b.*(?:\d+%|\d+x)']),
        ]

        for bullet in all_bullets:
            b = bullet.lower()
            bullet_scored = False

            for points, patterns in impact_patterns:
                for pattern in patterns:
                    if re.search(pattern, b):
                        total_impact += points
                        impact_count += 1
                        bullet_scored = True
                        break
                if bullet_scored:
                    break

            # Generic metric (has a number but no typed impact)
            if not bullet_scored and re.search(r'\d+[%$+]|\d{2,}', b):
                total_impact += 10
                impact_count += 1

        # Scale: max score if 4+ impact bullets (diminishing returns)
        if impact_count == 0:
            return 30.0  # No metrics at all
        
        # Average impact per bullet, scaled to 100
        avg_impact = total_impact / impact_count
        # More impact bullets = higher score (up to 4)
        coverage_bonus = min(impact_count / 4.0, 1.0) * 30
        
        score = min(100, avg_impact + coverage_bonus + 20)  # +20 baseline for having any metrics
        return score

    def _score_role_alignment(
        self,
        resume: StructuredResume,
        jd: ExtractedJD,
    ) -> Tuple[float, dict]:
        """Role alignment: title match + seniority level matching."""
        details = {}
        jd_title = jd.job_title.lower().strip()
        resume_title = resume.title.lower().strip()

        if not jd_title:
            return 40.0, {"note": "No job title in JD"}

        # Handle multi-role JD titles: "Data Scientist / ML Engineer"
        # Score against BEST matching sub-title
        jd_subtitles = [t.strip() for t in re.split(r'[/|]|\bor\b', jd_title) if t.strip()]
        if not jd_subtitles:
            jd_subtitles = [jd_title]

        best_score = 0.0
        best_details = {}

        for subtitle in jd_subtitles:
            sub_score, sub_details = self._score_single_title(resume_title, subtitle)
            if sub_score > best_score:
                best_score = sub_score
                best_details = sub_details

        score = best_score
        details.update(best_details)

        # Seniority level check
        jd_level = self._extract_seniority(jd_title)
        resume_level = self._extract_seniority(resume_title)
        if jd_level and resume_level:
            if jd_level == resume_level:
                score = min(score + 10, 100)
                details["seniority_match"] = True
            else:
                score = max(score - 15, 0)
                details["seniority_match"] = False
                details["jd_level"] = jd_level
                details["resume_level"] = resume_level

        return round(score, 1), details

    def _score_single_title(self, resume_title: str, jd_subtitle: str) -> Tuple[float, dict]:
        """Score resume title against a single JD sub-title."""
        details = {}

        if jd_subtitle == resume_title:
            return 100.0, {"title_match": "exact"}

        jd_words = set(self._tokenize(jd_subtitle))
        resume_words = set(self._tokenize(resume_title))
        overlap = jd_words & resume_words
        if overlap:
            ratio = len(overlap) / len(jd_words)
            score = ratio * 80
            details["title_match"] = "partial"
            details["overlapping_words"] = list(overlap)
            return score, details

        # Synonym matching
        synonym_matches = 0
        for jw in jd_words:
            for rw in resume_words:
                if are_synonyms(jw, rw):
                    synonym_matches += 1
                    break
        if synonym_matches > 0:
            ratio = synonym_matches / len(jd_words)
            return ratio * 50, {"title_match": "synonym"}

        return 3.0, {"title_match": "none"}

    def _score_education(
        self,
        resume: StructuredResume,
        jd: ExtractedJD,
    ) -> Tuple[float, dict]:
        """Education fit: degree level + field match + fresher boost."""
        details = {}
        edu_reqs = [r.lower() for r in jd.education_requirements if r.strip()]

        if not edu_reqs:
            return 65.0, {"note": "No specific education requirements in JD"}

        if not resume.education:
            return 5.0, {"note": "No education listed in resume"}

        edu_text = " ".join(
            f"{e.degree} {e.institution} {e.details or ''}".lower()
            for e in resume.education
        )

        # -- Degree Level Parsing (expanded) -----------------
        degree_levels = {
            "phd": 5, "doctorate": 5, "ph.d": 5, "d.phil": 5,
            "master": 4, "mba": 4, "m.tech": 4, "mtech": 4, "m.s.": 4,
            "ms ": 4, "msc": 4, "m.sc": 4, "m.e.": 4, "ma ": 4,
            "pgdiploma": 3, "post graduate diploma": 3,
            "bachelor": 3, "b.tech": 3, "btech": 3, "b.s.": 3, "bs ": 3,
            "bsc": 3, "b.sc": 3, "b.e.": 3, "ba ": 3, "bba": 3, "bca": 3,
            "associate": 2, "diploma": 1,
        }

        resume_level = 0
        for deg, level in degree_levels.items():
            if deg in edu_text:
                resume_level = max(resume_level, level)

        jd_level = 0
        jd_edu_text = " ".join(edu_reqs)
        for deg, level in degree_levels.items():
            if deg in jd_edu_text:
                jd_level = max(jd_level, level)

        details["resume_degree_level"] = resume_level
        details["jd_required_level"] = jd_level

        # -- Domain Extraction (from resume education) --------
        domain_map = {
            "data_science": [
                "data science", "data analytics", "big data", "data engineering",
                "business analytics", "analytics", "data analysis",
            ],
            "cs": [
                "computer science", "computer engineering", "software engineering",
                "computing", "computational", "information technology", "it ",
                "information systems", "cse", "cs ",
            ],
            "statistics": [
                "statistics", "biostatistics", "applied statistics",
                "mathematical statistics", "statistical",
            ],
            "mathematics": [
                "mathematics", "applied mathematics", "math ",
            ],
            "engineering": [
                "electrical engineering", "electronics", "mechanical engineering",
                "engineering", "ece", "eee",
            ],
            "business": [
                "business", "management", "finance", "economics",
                "mba", "bba", "commerce",
            ],
            "physics": ["physics", "applied physics"],
        }

        resume_domains = set()
        for domain, patterns in domain_map.items():
            if any(p in edu_text for p in patterns):
                resume_domains.add(domain)
        details["resume_domains"] = sorted(resume_domains)

        jd_domains = set()
        for domain, patterns in domain_map.items():
            if any(p in jd_edu_text for p in patterns):
                jd_domains.add(domain)
        # Also accept "related field" as any STEM
        if "related field" in jd_edu_text or "related discipline" in jd_edu_text:
            jd_domains |= {"cs", "statistics", "mathematics", "engineering", "data_science"}
        details["jd_accepted_domains"] = sorted(jd_domains)

        # -- Level Scoring ------------------------------------
        score = 0.0
        if jd_level > 0:
            if resume_level >= jd_level:
                score += 55
                details["degree_level_met"] = True
            elif resume_level == jd_level - 1:
                score += 30  # One level below (e.g., bachelors when masters preferred)
                details["degree_level_met"] = "close"
            else:
                score += 10
                details["degree_level_met"] = False
        else:
            score += 35  # JD doesn't specify level

        # -- Domain Scoring -----------------------------------
        if jd_domains and resume_domains:
            domain_overlap = resume_domains & jd_domains
            if domain_overlap:
                score += 40
                details["field_match"] = True
                details["matched_domains"] = sorted(domain_overlap)
            else:
                # Check adjacency (e.g., math is close to data_science)
                adjacent = {
                    "data_science": {"cs", "statistics", "mathematics"},
                    "cs": {"data_science", "engineering", "mathematics"},
                    "statistics": {"data_science", "mathematics"},
                    "mathematics": {"cs", "statistics", "data_science", "physics"},
                    "engineering": {"cs", "physics"},
                    "business": {"data_science"},
                }
                has_adjacent = False
                for rd in resume_domains:
                    adj = adjacent.get(rd, set())
                    if adj & jd_domains:
                        has_adjacent = True
                        break
                if has_adjacent:
                    score += 22
                    details["field_match"] = "adjacent"
                else:
                    score += 8
                    details["field_match"] = False
        elif not jd_domains:
            score += 25
            details["field_match"] = "not_specified"
        else:
            score += 10

        # -- Fresher + Masters Boost (Part 3 critical) --------
        # If candidate has a relevant masters but limited experience,
        # education should compensate for experience gap
        resume_years = self._estimate_experience_years(resume)
        if resume_level >= 4 and resume_years <= 3:  # Masters+ with <=3 years exp
            if resume_domains & (jd_domains or {"cs", "data_science", "statistics"}):
                boost = 10
                score += boost
                details["fresher_masters_boost"] = boost
                logger.info(f"  Education: Fresher+Masters boost +{boost} applied")

        return round(min(score, 100), 1), details

    def _score_structure(self, resume: StructuredResume) -> Tuple[float, dict]:
        """Resume structure and ATS formatting quality."""
        score = 0.0
        details = {}
        penalties = []

        # --- Section completeness (40 points) ---
        sections_present = 0
        total_sections = 6

        if resume.contact and resume.contact.name:
            sections_present += 1
        else:
            penalties.append("Missing contact/name")

        if resume.summary and len(resume.summary) > 20:
            sections_present += 1
        else:
            penalties.append("Missing or too-short summary")

        if resume.skills and len(resume.skills) >= 3:
            sections_present += 1
        else:
            penalties.append("Too few skills listed")

        if resume.experience and len(resume.experience) >= 1:
            sections_present += 1
        else:
            penalties.append("No experience listed")

        if resume.education and len(resume.education) >= 1:
            sections_present += 1
        else:
            penalties.append("No education listed")

        if resume.projects or resume.certifications:
            sections_present += 1
        else:
            penalties.append("No projects or certifications")

        section_score = (sections_present / total_sections) * 40
        score += section_score
        details["sections_present"] = sections_present
        details["total_sections"] = total_sections

        # --- Bullet quality (30 points) ---
        total_bullets = 0
        metric_bullets = 0
        action_verb_bullets = 0

        action_verbs = {
            "developed", "designed", "implemented", "built", "created",
            "managed", "led", "optimized", "improved", "reduced",
            "increased", "delivered", "automated", "analyzed", "architected",
            "deployed", "maintained", "collaborated", "established", "launched",
            "streamlined", "configured", "integrated", "migrated", "mentored",
            "spearheaded", "orchestrated", "engineered", "constructed",
        }
        metric_patterns = [
            r'\d+%', r'\d+x', r'\$\d+', r'\d+k\+?', r'\d+\+',
            r'\d+ (?:users|customers|requests|records|clients|transactions)',
        ]

        for exp in resume.experience:
            for bullet in exp.bullets:
                total_bullets += 1
                bullet_lower = bullet.lower().strip()
                first_word = bullet_lower.split()[0] if bullet_lower.split() else ""
                if first_word in action_verbs:
                    action_verb_bullets += 1
                if any(re.search(p, bullet, re.IGNORECASE) for p in metric_patterns):
                    metric_bullets += 1

        if total_bullets > 0:
            action_ratio = action_verb_bullets / total_bullets
            metric_ratio = metric_bullets / total_bullets
            bullet_score = (action_ratio * 0.4 + metric_ratio * 0.6) * 30
            details["total_bullets"] = total_bullets
            details["action_verb_bullets"] = action_verb_bullets
            details["metric_bullets"] = metric_bullets
        else:
            bullet_score = 0
            penalties.append("No experience bullets found")

        score += bullet_score

        # --- Skills count (15 points) ---
        skill_count = len(resume.skills)
        if 8 <= skill_count <= 15:
            score += 15
        elif 5 <= skill_count < 8:
            score += 10
        elif skill_count > 15:
            score += 6
            penalties.append("Too many skills listed (>15)")
        elif skill_count > 0:
            score += 4
            penalties.append("Very few skills listed")
        else:
            penalties.append("No skills listed")

        # --- Summary quality (15 points) ---
        if resume.summary:
            summary_words = len(resume.summary.split())
            if 30 <= summary_words <= 80:
                score += 15
            elif 20 <= summary_words < 30:
                score += 10
            elif summary_words > 80:
                score += 6
                penalties.append("Summary is too long")
            else:
                score += 4
                penalties.append("Summary is too short")

        details["penalties"] = penalties

        return round(min(score, 100), 1), details

    # ================================================================
    # Matching Helpers (TIGHTENED)
    # ================================================================

    def _keyword_found(self, keyword: str, resume_lower: str, resume_skills: Set[str]) -> bool:
        """Check if a keyword is found via exact, partial, or synonym match."""
        kw = keyword.lower().strip()

        if kw in resume_lower:
            return True

        if kw in resume_skills:
            return True

        synonyms = get_synonyms(kw)
        for syn in synonyms:
            if syn in resume_lower or syn in resume_skills:
                return True

        words = kw.split()
        if len(words) > 1:
            significant_words = [w for w in words if len(w) > 2 and w not in _STOP_WORDS]
            if significant_words and all(w in resume_lower for w in significant_words):
                return True

        return False

    # -- SKILL NORMALIZATION MAP (PART 5) -----------------------
    # Maps common aliases/variants to canonical form for matching
    SKILL_ALIASES = {
        "sklearn": "scikit-learn",
        "scikit learn": "scikit-learn",
        "sci-kit learn": "scikit-learn",
        "python (pandas)": "pandas",
        "python (numpy)": "numpy",
        "python (flask)": "flask",
        "python (django)": "django",
        "python (fastapi)": "fastapi",
        "k8s": "kubernetes",
        "kube": "kubernetes",
        "js": "javascript",
        "ts": "typescript",
        "react.js": "react",
        "reactjs": "react",
        "node": "node.js",
        "nodejs": "node.js",
        "vue": "vue.js",
        "vuejs": "vue.js",
        "next": "next.js",
        "nextjs": "next.js",
        "postgres": "postgresql",
        "pg": "postgresql",
        "mongo": "mongodb",
        "tf": "tensorflow",
        "aws cloud": "aws",
        "amazon web services": "aws",
        "google cloud platform": "gcp",
        "google cloud": "gcp",
        "microsoft azure": "azure",
        "ci cd": "ci/cd",
        "cicd": "ci/cd",
        "rest": "rest api",
        "restful api": "rest api",
        "restful": "rest api",
        "ml": "machine learning",
        "dl": "deep learning",
        "natural language processing": "nlp",
        "power bi": "powerbi",
        "powerbi": "power bi",
        # -- CONCEPT ALIASES (Part 1: concept-level matching) --------
        # Tools that IMPLY a concept (e.g., streamlit implies deployment)
        "streamlit": "deployment",
        "gradio": "deployment",
        "heroku": "deployment",
        "vercel": "deployment",
        "netlify": "deployment",
        "hugging face": "deployment",
        "huggingface": "deployment",
        "flask": "web development",
        "django": "web development",
        "fastapi": "web development",
        # Cloud concept mappings
        "aws": "cloud",
        "azure": "cloud",
        "gcp": "cloud",
        "google cloud": "cloud",
        "amazon web services": "cloud",
        # Dashboard/BI concept mappings
        "tableau": "dashboard",
        "power bi": "dashboard",
        "plotly": "data visualization",
        "matplotlib": "data visualization",
        "seaborn": "data visualization",
        # Data analysis concept mappings
        "pandas": "data analysis",
        "numpy": "data analysis",
        "scipy": "data analysis",
        "excel": "data analysis",
        # ML/AI concept mappings
        "xgboost": "machine learning",
        "lightgbm": "machine learning",
        "random forest": "machine learning",
        "scikit-learn": "machine learning",
        "tensorflow": "deep learning",
        "pytorch": "deep learning",
        "keras": "deep learning",
        # Database concept mappings
        "mysql": "database",
        "postgresql": "database",
        "mongodb": "database",
        "redis": "database",
        "sqlite": "database",
        # Plural/singular forms
        "lstms": "lstm",
        "lstm": "lstm",
        "cnns": "cnn",
        "rnns": "rnn",
        "gans": "gan",
        "apis": "api",
        "llms": "llm",
    }

    # REVERSE concept map: "deployment" → ["streamlit", "gradio", ...]
    # Used so if JD says "deployment" and resume has "streamlit", it matches
    CONCEPT_REVERSE = {}
    for _tool, _concept in SKILL_ALIASES.items():
        if _concept in ("deployment", "cloud", "dashboard", "data visualization",
                         "data analysis", "machine learning", "deep learning",
                         "database", "web development"):
            CONCEPT_REVERSE.setdefault(_concept, set()).add(_tool)

    def _normalize_skill(self, skill: str) -> str:
        """Normalize a skill name to its canonical form."""
        s = skill.lower().strip()
        return self.SKILL_ALIASES.get(s, s)

    def _skill_found_strict(self, skill: str, resume_skills: Set[str], resume_lower: str) -> bool:
        """
        STRICT skill matching with normalization.
        Normalizes aliases before matching (e.g., pandas == python (pandas)).
        """
        skill_lower = skill.lower().strip()
        skill_normalized = self._normalize_skill(skill_lower)

        # Normalize resume skills for comparison
        resume_skills_normalized = {self._normalize_skill(s) for s in resume_skills}

        # Direct match (normalized)
        if skill_normalized in resume_skills_normalized:
            return True
        if skill_normalized in resume_lower:
            return True
        # Also check original form
        if skill_lower in resume_skills:
            return True
        if skill_lower in resume_lower:
            return True

        # Synonym check (on normalized)
        synonyms = get_synonyms(skill_normalized)
        for syn in synonyms:
            syn_n = self._normalize_skill(syn)
            if syn_n in resume_skills_normalized or syn_n in resume_lower:
                return True

        # Extract core technical terms only (filter stop words + short words)
        core_skills = re.findall(r'\b([a-zA-Z+#./]+(?:\.[a-zA-Z]+)?)\b', skill_lower)
        technical_terms = [
            cs for cs in core_skills
            if len(cs) > 2 and cs not in _STOP_WORDS
        ]

        # Require at least 60% of technical terms to match (not just any one)
        if technical_terms:
            matched_count = 0
            for term in technical_terms:
                term_n = self._normalize_skill(term)
                if term_n in resume_skills_normalized or term_n in resume_lower:
                    matched_count += 1
                elif term in resume_skills or term in resume_lower:
                    matched_count += 1
                else:
                    # Check synonyms
                    for syn in get_synonyms(term):
                        if syn in resume_skills or syn in resume_lower:
                            matched_count += 1
                            break

            threshold = max(1, int(len(technical_terms) * 0.6))
            if matched_count >= threshold:
                return True

        # -- CONCEPT REVERSE MATCHING (Part 1) ----------------------
        # If JD says "deployment" and resume has "streamlit", it matches
        # because streamlit implies deployment capability
        if skill_normalized in self.CONCEPT_REVERSE:
            concept_tools = self.CONCEPT_REVERSE[skill_normalized]
            for tool in concept_tools:
                if tool in resume_skills_normalized or tool in resume_lower:
                    return True
                tool_n = self._normalize_skill(tool)
                if tool_n in resume_skills_normalized or tool_n in resume_lower:
                    return True

        # Also check: if skill normalizes to a concept, and that concept's
        # tools are in resume (e.g., skill="cloud computing", concept="cloud")
        for concept, tools in self.CONCEPT_REVERSE.items():
            if concept in skill_normalized or skill_normalized in concept:
                for tool in tools:
                    if tool in resume_skills_normalized or tool in resume_lower:
                        return True

        return False

    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract meaningful phrases from text."""
        phrases = []
        if len(text.split()) <= 5:
            phrases.append(text)
        words = text.split()
        for i in range(len(words)):
            if len(words[i]) > 3 and words[i] not in _STOP_WORDS:
                phrases.append(words[i])
            if i < len(words) - 1:
                bigram = f"{words[i]} {words[i+1]}"
                if len(bigram) > 6:
                    phrases.append(bigram)
        return phrases

    # ================================================================
    # Utility Helpers
    # ================================================================

    @staticmethod
    def _flatten_resume_text(resume: StructuredResume) -> str:
        """Concatenate all resume text into one searchable string."""
        parts = [resume.title, resume.summary, " ".join(resume.skills)]
        for exp in resume.experience:
            parts.extend([exp.role, exp.company])
            parts.extend(exp.bullets)
        for edu in resume.education:
            parts.extend([edu.degree, edu.institution, edu.details])
        for proj in resume.projects:
            parts.extend([proj.name, proj.description])
            parts.extend(proj.technologies)
            parts.extend(proj.bullets)
        for cert in resume.certifications:
            parts.extend([cert.name, cert.issuer])
        return " ".join(p for p in parts if p)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        stop_words = {"a", "an", "the", "and", "or", "of", "in", "to", "for", "with", "on", "at", "is", "are"}
        words = re.findall(r'[a-z0-9#+.]+', text.lower())
        return [w for w in words if w not in stop_words and len(w) > 1]

    @staticmethod
    def _extract_seniority(title: str) -> Optional[str]:
        title_lower = title.lower()
        if any(w in title_lower for w in ["senior", "sr.", "sr ", "lead", "principal", "staff"]):
            return "senior"
        if any(w in title_lower for w in ["junior", "jr.", "jr ", "entry", "associate"]):
            return "junior"
        if any(w in title_lower for w in ["mid", "intermediate"]):
            return "mid"
        if any(w in title_lower for w in ["manager", "director", "head", "vp", "chief"]):
            return "management"
        return "mid"

    @staticmethod
    def _estimate_experience_years(resume: StructuredResume) -> int:
        """Estimate total years using dynamic current date."""
        total_months = 0
        current_year = datetime.now().year
        current_month = datetime.now().month

        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }

        for exp in resume.experience:
            duration = exp.duration.lower()
            pattern = r'(\w{3})\s+(\d{4})\s*[\u2013\-to]+\s*(\w+)\s*(\d{4})?'
            match = re.search(pattern, duration)
            if match:
                start_month = month_map.get(match.group(1)[:3], 1)
                start_year = int(match.group(2))
                end_token = match.group(3).lower()
                if end_token in ("present", "current", "now"):
                    end_month = current_month
                    end_year = current_year
                else:
                    end_month = month_map.get(end_token[:3], 12)
                    end_year = int(match.group(4)) if match.group(4) else start_year
                months = (end_year - start_year) * 12 + (end_month - start_month)
                total_months += max(months, 0)
            else:
                years = re.findall(r'(\d{4})', duration)
                if len(years) >= 2:
                    total_months += (int(years[-1]) - int(years[0])) * 12
                else:
                    total_months += 12
        # Add weighted project experience (each project = ~3 months)
        project_months = len(resume.projects) * 3  # 0.25 years each

        return max((total_months + project_months) // 12, 0)

    @staticmethod
    def _apply_penalty_curve(ratio: float) -> float:
        """
        Penalty curve (v3). ratio^1.5 for fairer high-alignment scoring.

        Mapping:
          0.0  -> 0.0
          0.25 -> 0.13
          0.50 -> 0.35
          0.67 -> 0.55
          0.75 -> 0.65
          0.83 -> 0.77
          0.90 -> 0.85
          1.0  -> 1.0
        """
        if ratio <= 0:
            return 0.0
        if ratio >= 1:
            return 1.0
        return ratio ** 1.5

    # ================================================================
    # Recommendations
    # ================================================================

    def _generate_recommendations(
        self,
        score: float,
        breakdown: ScoreBreakdown,
        details: dict,
        jd: ExtractedJD,
        resume: StructuredResume = None,
    ) -> List[str]:
        recs = []

        # -- Build full presence map for consistency --
        matched_skills_set = {s.lower() for s in details.get("skills", {}).get("matched", [])}
        missing_skills = details.get("skills", {}).get("missing", [])
        required_lower = {s.lower() for s in (jd.required_skills or [])}

        # Build bullet text for usage-vs-presence check
        bullet_text = ""
        if resume:
            bullet_text = " ".join(
                b.lower() for exp in resume.experience for b in exp.bullets
            ) + " " + " ".join(
                b.lower() for proj in resume.projects for b in proj.bullets
            )

        must_have_skills = [s for s in missing_skills if s.lower() in required_lower]
        nice_have_skills = [s for s in missing_skills if s.lower() not in required_lower]

        # Part 9: PRECISE recommendations -- point to specific roles/bullets
        # BEHAVIOR FIX: Check if skill is ALREADY used in bullets before saying "Add"
        if must_have_skills and resume and resume.experience:
            for skill in must_have_skills[:3]:
                skill_lower = skill.lower()
                # Check if skill is already demonstrated in bullets
                already_used = skill_lower in bullet_text
                if not already_used:
                    # Check partial match (e.g. "machine learning" → "ml", "machine")
                    terms = [t for t in skill_lower.split() if len(t) > 3]
                    already_used = any(t in bullet_text for t in terms) if terms else False

                if already_used:
                    # Skill IS used — recommend highlighting, not adding
                    recs.append(
                        f"[SHOULD] Highlight '{skill}' usage more prominently in experience bullets "
                        f"(it appears in text but may lack context or impact)"
                    )
                else:
                    # Skill is truly missing — recommend adding with specific placement
                    best_role = None
                    best_bullet = None
                    for exp in resume.experience:
                        role_text = f"{exp.role} at {exp.company}"
                        for i, bullet in enumerate(exp.bullets):
                            if best_bullet is None or len(bullet) < len(best_bullet):
                                best_role = role_text
                                best_bullet = bullet[:50]
                    if best_role:
                        recs.append(
                            f"[MUST] Demonstrate '{skill}' usage in {best_role} "
                            f"(expand bullet: \"{best_bullet}...\")"
                        )
        elif must_have_skills:
            # Filter out skills already in bullets
            truly_missing = [
                s for s in must_have_skills[:3]
                if s.lower() not in bullet_text
            ]
            if truly_missing:
                recs.append(f"[MUST] Demonstrate required skills in experience bullets: {', '.join(truly_missing)}")

        missing_kw = details.get("keywords", {}).get("missing", [])
        if missing_kw:
            kw_only = [kw for kw in missing_kw if kw.lower() not in {s.lower() for s in missing_skills}][:4]
            if kw_only:
                recs.append(f"[MUST] Integrate missing keywords into bullets: {', '.join(kw_only)}")

        if breakdown.experience_relevance < 40:
            recs.append(
                "[MUST] Rewrite experience bullets to mirror JD responsibilities -- "
                "use the same action verbs and terminology."
            )

        # -- USAGE-BASED SUGGESTIONS (skill present but not in bullets) --
        if resume and not must_have_skills:
            # Find matched skills not demonstrated in experience/project bullets
            for skill in sorted(matched_skills_set):
                # Check if skill or its key terms appear in ANY bullet
                terms = [t for t in skill.split() if len(t) > 2]
                in_bullets = skill in bullet_text
                if not in_bullets and terms:
                    in_bullets = any(t in bullet_text for t in terms if len(t) > 3)
                if not in_bullets and skill in required_lower:
                    recs.append(
                        f"[SHOULD] Highlight '{skill}' usage in experience bullets "
                        f"(currently only in skills section)"
                    )

        # -- SHOULD HAVE (important improvements) -------------
        if nice_have_skills:
            top = nice_have_skills[:3]
            recs.append(f"[SHOULD] Address preferred skill gaps: {', '.join(top)}")

        exp_details = details.get("experience", {})
        if exp_details.get("resume_years", 99) < exp_details.get("required_years", 0):
            recs.append(
                f"[SHOULD] JD requires {exp_details['required_years']}+ years. "
                f"Resume shows ~{exp_details['resume_years']}. "
                "Highlight freelance/contract work or relevant side projects."
            )

        if breakdown.role_alignment < 50:
            recs.append(
                f"[SHOULD] Align resume title to '{jd.job_title}' or a close variant."
            )

        if breakdown.resume_structure < 60:
            struct_details = details.get("structure", {})
            if struct_details.get("metric_bullets", 0) < struct_details.get("total_bullets", 1) * 0.3:
                recs.append(
                    "[SHOULD] Add quantified achievements (%, $, numbers) to at least 50% of bullets."
                )

        # -- NICE TO HAVE (polish) ----------------------------
        struct_details = details.get("structure", {})
        for penalty in struct_details.get("penalties", [])[:2]:
            recs.append(f"[NICE] Structure fix: {penalty}")

        if 50 <= breakdown.experience_relevance < 70:
            recs.append(
                "[NICE] Strengthen experience bullets with more specific metrics and outcomes."
            )

        # Risk-based recommendations (always shown)
        for flag in details.get("risk_flags", []):
            if "KEYWORD_STUFFING" in flag:
                recs.append("[MUST] Reduce keyword repetition -- ATS may flag as manipulation.")
            if "DOMAIN_MISMATCH" in flag:
                recs.append("[MUST] Your background doesn't align with this role's domain. Consider upskilling first.")

        # Score warnings
        if score < 35:
            recs.append(
                "[!] Score is critically low. This resume would be auto-rejected by most ATS systems."
            )
        elif score < 50:
            recs.append(
                "[!] Below ATS threshold. Significant rewriting needed to pass filters."
            )

        # -- TRUST FILTER: discard irrelevant suggestions ------
        recs = self._apply_trust_filter(recs, details)

        return recs

    def _apply_trust_filter(self, recs: List[str], details: dict) -> List[str]:
        """
        Filter out recommendations that:
        1. Reference skills irrelevant to the resume's domain
        2. Contradict matched_skills (consistency rule)
        3. Suggest adding skills already present in skills list
        4. Suggest demonstrating skills already in bullets
        5. Remove duplicates
        """
        # Extract what domains the resume actually covers
        edu_domains = set(details.get("education", {}).get("resume_domains", []))
        matched_skills = {s.lower() for s in details.get("skills", {}).get("matched", [])}
        missing_skills = {s.lower() for s in details.get("skills", {}).get("missing", [])}

        # Build bullet text for usage check
        bullet_text = details.get("_bullet_text", "")

        # Domain clusters: what skills are relevant to which domains
        _DOMAIN_SKILLS = {
            "data_science": {"python", "sql", "pandas", "numpy", "scikit-learn", "tensorflow",
                             "pytorch", "spark", "tableau", "power bi", "r", "statistics"},
            "cs": {"python", "java", "javascript", "typescript", "c++", "go", "rust",
                   "react", "angular", "node.js", "docker", "kubernetes", "aws"},
            "engineering": {"python", "c++", "java", "matlab", "docker", "linux", "aws"},
            "business": {"sql", "excel", "tableau", "power bi", "python", "r"},
        }

        # Build a set of plausible skills for this resume
        plausible_skills = set()
        for domain in edu_domains:
            plausible_skills |= _DOMAIN_SKILLS.get(domain, set())
        plausible_skills |= matched_skills  # All already-matched skills are plausible

        filtered = []
        seen = set()  # Dedup tracker

        for rec in recs:
            rec_lower = rec.lower()

            # DEDUP: skip if we've seen a very similar recommendation
            rec_key = rec_lower[:60]  # Use first 60 chars as dedup key
            if rec_key in seen:
                continue
            seen.add(rec_key)

            # CONSISTENCY: skip "Add X" / "Demonstrate X" if X is already matched
            if any(phrase in rec_lower for phrase in ["[must] add", "[should] add", "[must] demonstrate"]):
                skip = False
                for skill in matched_skills:
                    if len(skill) > 2 and skill in rec_lower:
                        skip = True
                        break
                if skip:
                    continue

            # CONSISTENCY: skip "Highlight X usage" if X is well-demonstrated in bullets
            if "[should] highlight" in rec_lower and bullet_text:
                # Extract the skill being highlighted
                import re as _re
                skill_match = _re.search(r"highlight\s+'([^']+)'", rec_lower)
                if skill_match:
                    highlight_skill = skill_match.group(1)
                    # If skill appears 2+ times in bullets, it's already highlighted
                    if bullet_text.count(highlight_skill) >= 2:
                        continue

            # Domain filter: only for bulk skill recommendations
            if not plausible_skills:
                filtered.append(rec)
                continue

            if "[MUST] Add required skills" in rec or "[SHOULD] Address preferred" in rec:
                # Extract the skills mentioned
                parts = rec.split(": ", 1)
                if len(parts) == 2:
                    mentioned = [s.strip().lower() for s in parts[1].split(",")]
                    relevant = [s for s in mentioned
                                if s in plausible_skills or
                                any(s in cluster for cluster in _DOMAIN_SKILLS.values())]
                    if not relevant:
                        continue
            filtered.append(rec)

        return filtered
