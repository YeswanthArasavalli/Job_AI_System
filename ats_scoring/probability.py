"""
Shortlist Probability Engine -- Estimates real hiring probability.

ATS score != real shortlist chance. This module combines multiple
signals into a calibrated probability estimate with reasoning.

Factors:
  - ATS score (40%)
  - Semantic alignment (25%)
  - Critical skill coverage (20%)
  - Experience gap penalty (10%)
  - Risk flag deductions (5%)
"""

from typing import Dict, List, Tuple

from utils.logger import setup_logger

logger = setup_logger(__name__)


class ShortlistPredictor:
    """
    Predicts probability of being shortlisted for interview.

    Usage:
        predictor = ShortlistPredictor()
        result = predictor.predict(ats_report)
    """

    def predict(self, report) -> dict:
        """
        Compute shortlist probability from an ATSScoreReport.

        Returns:
            Dict with probability (0-100), confidence, and reasons.
        """
        score = report.score_after
        semantic = report.semantic_score
        matched = report.matched_skills
        missing = report.missing_skills
        risk_flags = report.risk_flags
        penalties = report.penalties_applied
        decision = report.decision

        # === 1. Base signals ===
        ats_signal = min(score / 100, 1.0)        # 0-1
        semantic_signal = min(semantic / 100, 1.0)  # 0-1

        # === 2. Skill coverage ===
        total_skills = len(matched) + len(missing)
        skill_coverage = len(matched) / max(total_skills, 1)

        # === 3. Experience gap detection ===
        exp_penalty = 0.0
        for flag in risk_flags:
            if "experience" in flag.lower() or "years" in flag.lower():
                exp_penalty = 0.15
                break
        for p in penalties:
            if "experience" in p.lower():
                exp_penalty = max(exp_penalty, 0.10)

        # === 4. Risk deductions ===
        risk_deduction = 0.0
        hard_reject = False
        for flag in risk_flags:
            if "NEEDS_IMPROVEMENT" in flag:
                hard_reject = True
                risk_deduction = 0.3
                break
            risk_deduction += 0.03
        risk_deduction = min(risk_deduction, 0.25)

        # === 5. Compute raw probability ===
        if hard_reject:
            raw_prob = 5.0  # Almost zero but not exactly
        else:
            raw_prob = (
                0.40 * ats_signal * 100 +
                0.25 * semantic_signal * 100 +
                0.20 * skill_coverage * 100 +
                0.15 * (1.0 - exp_penalty) * 100
                - risk_deduction * 100
            )

        # Calibrate to realistic range
        calibrated = self._calibrate(raw_prob)

        # Score-based cap: low ATS can't produce high probability
        if score < 40:
            calibrated = min(calibrated, 15)
        elif score < 50:
            calibrated = min(calibrated, 30)
        elif score < 60:
            calibrated = min(calibrated, 45)

        # === 6. Confidence ===
        confidence = self._assess_confidence(
            total_skills, semantic, len(risk_flags), score
        )

        # === 7. Reasons (positive + negative) ===
        positive, negative = self._build_reasons(
            score, semantic, missing, risk_flags, exp_penalty, skill_coverage
        )

        # Confidence band
        if calibrated >= 35:
            band = "STRONG MATCH"
        elif calibrated >= 20:
            band = "COMPETITIVE"
        elif calibrated >= 10:
            band = "POSSIBLE"
        else:
            band = "UNLIKELY"

        result = {
            "shortlist_probability": round(calibrated, 1),
            "raw_score": round(raw_prob, 1),
            "confidence": confidence,
            "band": band,
            "positive_factors": positive,
            "negative_factors": negative,
            "reasons": positive + negative,  # Combined for backward compat
            "signal_breakdown": {
                "ats_contribution": round(ats_signal * 40, 1),
                "semantic_contribution": round(semantic_signal * 25, 1),
                "skill_coverage": round(skill_coverage * 100, 1),
                "experience_penalty": round(exp_penalty * 100, 1),
                "risk_deduction": round(risk_deduction * 100, 1),
            },
        }

        logger.info(
            f"Shortlist probability: {calibrated:.0f}% "
            f"({band}, confidence: {confidence})"
        )
        return result

    def _calibrate(self, raw: float) -> float:
        """
        Map raw score to realistic probability range.
        Most applicants get ~5-20% shortlist rate.
        """
        raw = max(0, min(raw, 100))

        if raw >= 85:
            return 55 + (raw - 85) * 3    # 55-100%
        elif raw >= 70:
            return 30 + (raw - 70) * 1.67  # 30-55%
        elif raw >= 50:
            return 12 + (raw - 50) * 0.9   # 12-30%
        elif raw >= 30:
            return 5 + (raw - 30) * 0.35   # 5-12%
        else:
            return max(1, raw * 0.17)       # 1-5%

    def _assess_confidence(
        self, total_skills: int, semantic: float, risk_count: int, score: float
    ) -> str:
        """Assess confidence in the probability estimate."""
        confidence_score = 0

        # More skills compared = more data = more confident
        if total_skills >= 8:
            confidence_score += 3
        elif total_skills >= 4:
            confidence_score += 2
        else:
            confidence_score += 1

        # Semantic data quality
        if semantic > 30:
            confidence_score += 2
        elif semantic > 10:
            confidence_score += 1

        # Consistent signals (score and semantic agree)
        if (score >= 60 and semantic >= 40) or (score < 40 and semantic < 20):
            confidence_score += 2  # Signals agree
        else:
            confidence_score += 1  # Mixed signals

        if confidence_score >= 6:
            return "HIGH"
        elif confidence_score >= 4:
            return "MEDIUM"
        else:
            return "LOW"

    def _build_reasons(
        self,
        score: float,
        semantic: float,
        missing: list,
        risk_flags: list,
        exp_penalty: float,
        skill_coverage: float,
    ) -> tuple:
        """Build positive and negative factors. Returns (positive, negative)."""
        positive = []
        negative = []

        # Positive signals
        if score >= 75:
            positive.append("Strong ATS score (75+)")
        elif score >= 55:
            positive.append("Moderate ATS score")

        if semantic >= 50:
            positive.append("Good semantic alignment with JD")

        if skill_coverage >= 0.8:
            positive.append("Excellent skill coverage (80%+)")
        elif skill_coverage >= 0.6:
            positive.append("Decent skill coverage (60%+)")

        # Negative signals
        if semantic < 25:
            negative.append("Low semantic alignment -- resume bullets don't match JD responsibilities")

        if skill_coverage < 0.5:
            negative.append(f"Missing {len(missing)} required skills -- weak coverage")

        critical_missing = [s for s in missing if len(s.split()) <= 3]
        if critical_missing:
            top = critical_missing[:3]
            negative.append(f"Missing core skills: {', '.join(top)}")

        if exp_penalty > 0:
            negative.append("Experience gap detected")

        for flag in risk_flags:
            if "NEEDS_IMPROVEMENT" in flag:
                negative.append("Significant improvement needed -- may need resume rework")
                break

        if score < 40:
            negative.append("Score too low for most ATS filters")

        return positive[:3], negative[:3]
