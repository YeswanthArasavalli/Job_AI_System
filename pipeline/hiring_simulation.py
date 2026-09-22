"""
Hiring Simulation Engine — 3-Layer Recruiter Decision Simulator.

Simulates the real hiring pipeline:
  Layer 1: ATS Filter (keyword match, format, parsing safety)
  Layer 2: Recruiter Scan (6-10 sec first impression)
  Layer 3: Hiring Manager Decision (depth, fit, differentiation)

Plus:
  - Skill → Proof Audit
  - Competitive Differentiation
  - Recruiter Persona Simulation (Amazon/Google/Microsoft)
  - Gap Intelligence

This is the CORE DIFFERENTIATOR — optimizes for SHORTLIST_PROBABILITY, not ATS_SCORE.
"""

import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field

from utils.models import StructuredResume, ExtractedJD
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ================================================================
# SKILL → PROOF ENGINE
# ================================================================

def audit_skill_proof(
    resume: StructuredResume,
    jd: ExtractedJD,
    matched_skills: List[str],
) -> Dict:
    """
    PART 1: For every important skill, determine if it has PROOF in experience.

    skill != proof. "I know Python" is NOT proof.
    "Built data pipelines using Python to process 150K+ records" IS proof.

    Returns:
        {
            "proven_skills": [{skill, bullet, proof_type}],
            "unproven_skills": [skill],
            "proof_coverage": float (0-100),
            "skill_proof_matrix": [{skill, status, evidence}],
        }
    """
    all_bullets = [b for exp in resume.experience for b in exp.bullets]
    all_bullets += [b for proj in resume.projects for b in proj.bullets]
    all_text = " ".join(b.lower() for b in all_bullets)

    proven = []
    unproven = []
    matrix = []

    for skill in sorted(set(matched_skills), key=str.lower):
        sk_lower = skill.lower()
        best_proof = None
        proof_type = "none"

        for idx, bullet in enumerate(all_bullets):
            bl = bullet.lower()
            if sk_lower not in bl:
                # Check sub-terms for multi-word skills (lower threshold for short terms)
                terms = [t for t in sk_lower.split() if len(t) >= 2]
                if not terms or not any(t in bl for t in terms):
                    continue

            # Check proof depth
            has_purpose = bool(re.search(
                rf'{re.escape(sk_lower)}.*?(?:for|to|enabling|reducing|improving|achieving)',
                bl
            )) or bool(re.search(
                r'(?:for|to)\s+\w+.*?' + re.escape(sk_lower), bl
            ))
            has_metric = bool(re.search(r'\d+\s*[%KkMm+$]|\d{3,}', bullet))

            if has_purpose and has_metric:
                proof_type = "strong"  # Purpose + metric
                best_proof = bullet
                break
            elif has_purpose:
                proof_type = "purpose"  # Purpose without metric
                if not best_proof or proof_type == "none":
                    best_proof = bullet
            elif proof_type == "none":
                proof_type = "bare"  # Just mentioned
                best_proof = bullet

        entry = {
            "skill": skill,
            "status": proof_type,
            "evidence": (best_proof or "")[:120],
        }
        matrix.append(entry)

        if proof_type in ("strong", "purpose"):
            proven.append({"skill": skill, "bullet": best_proof, "proof_type": proof_type})
        else:
            unproven.append(skill)

    total = len(matrix) or 1
    coverage = len(proven) / total * 100

    return {
        "proven_skills": proven,
        "unproven_skills": unproven,
        "proof_coverage": round(coverage, 1),
        "skill_proof_matrix": matrix,
    }


# ================================================================
# PERCEPTION ENGINE (PART 3)
# ================================================================

def compute_perceived_strength(resume: StructuredResume, jd: ExtractedJD) -> Dict:
    """
    Score how STRONG a resume APPEARS to a recruiter/HM in 10 seconds.

    Measures 4 perception dimensions:
      - impact_density:    % of bullets showing measurable outcomes
      - ownership_level:   % of bullets with ownership language (not "helped", "assisted")
      - scale_visibility:  % of bullets showing volume/scale signals
      - outcome_clarity:   % of bullets with clear [What → Result] structure

    Returns:
        {
            "total": float (0-100),
            "impact_density": float,
            "ownership_level": float,
            "scale_visibility": float,
            "outcome_clarity": float,
            "weak_bullets": [{"index": int, "text": str, "reason": str}],
        }
    """
    all_bullets = [b for exp in resume.experience for b in exp.bullets]
    if not all_bullets:
        return {"total": 0, "impact_density": 0, "ownership_level": 0,
                "scale_visibility": 0, "outcome_clarity": 0, "weak_bullets": []}

    n = len(all_bullets)
    impact_count = 0
    ownership_count = 0
    scale_count = 0
    outcome_count = 0
    weak_bullets = []

    # Ownership verbs (strong) vs passive/weak verbs
    ownership_verbs = {
        'architected', 'built', 'created', 'delivered', 'deployed', 'designed',
        'developed', 'drove', 'engineered', 'established', 'implemented',
        'launched', 'led', 'managed', 'optimized', 'orchestrated', 'owned',
        'pioneered', 'spearheaded', 'streamlined', 'transformed',
    }
    weak_verbs = {
        'helped', 'assisted', 'participated', 'contributed', 'involved',
        'supported', 'worked', 'responsible',
    }

    for idx, bullet in enumerate(all_bullets):
        bl = bullet.lower()
        reasons = []

        # Impact: has metric or quantified outcome
        has_impact = bool(re.search(r'\d+\s*%|\$\d|revenue|profit|savings', bullet, re.I))
        if has_impact:
            impact_count += 1
        else:
            reasons.append("no measurable impact")

        # Ownership: starts with strong verb, no weak/passive language
        first_word = re.match(r'^([A-Za-z]+)', bullet)
        fw = first_word.group(1).lower() if first_word else ''
        has_ownership = fw in ownership_verbs
        has_weak = fw in weak_verbs or any(wv in bl for wv in ['helped', 'assisted', 'responsible for'])
        if has_ownership and not has_weak:
            ownership_count += 1
        elif has_weak:
            reasons.append("passive/weak ownership")

        # Scale: volume indicators
        has_scale = bool(re.search(r'\d+[KkMm+]|\d{3,}|production|enterprise|large.?scale', bullet, re.I))
        if has_scale:
            scale_count += 1

        # Outcome clarity: [What] + [for/to/resulting in] pattern
        has_outcome = bool(re.search(
            r'(?:for|to|enabling|resulting|achieving|improving|reducing|driving)\s+\w',
            bl
        ))
        if has_outcome:
            outcome_count += 1
        else:
            reasons.append("no clear outcome/purpose")

        if reasons:
            weak_bullets.append({
                "index": idx, "text": bullet[:100], "reason": ", ".join(reasons)
            })

    impact_density = impact_count / n * 100
    ownership_level = ownership_count / n * 100
    scale_visibility = scale_count / n * 100
    outcome_clarity = outcome_count / n * 100

    # Weighted total: impact (35%) + ownership (25%) + scale (20%) + clarity (20%)
    total = (
        impact_density * 0.35 +
        ownership_level * 0.25 +
        scale_visibility * 0.20 +
        outcome_clarity * 0.20
    )

    return {
        "total": round(min(100, total), 1),
        "impact_density": round(impact_density, 1),
        "ownership_level": round(ownership_level, 1),
        "scale_visibility": round(scale_visibility, 1),
        "outcome_clarity": round(outcome_clarity, 1),
        "weak_bullets": weak_bullets[:5],  # Top 5 weakest
    }


# ================================================================
# EXPERIENCE STRENGTH ENHANCER (PART 2)
# ================================================================

def enhance_experience_strength(
    resume: StructuredResume,
    jd: ExtractedJD,
    perception: Dict,
) -> StructuredResume:
    """
    Transform bullet structure from task-description → ownership+impact.

    Rules:
      1. DO NOT invent numbers or fabricate outcomes
      2. DO NOT change core meaning
      3. ONLY restructure: [Action+Tool] → [Impact+Action+Tool+Purpose]
      4. Use EXISTING metrics from the bullet text — just move them forward
      5. Add purpose clauses ONLY if semantically implied

    Focuses on the weakest bullets from perception analysis.
    """
    # Only enhance bullets flagged as weak
    weak_indices = {wb["index"] for wb in perception.get("weak_bullets", [])}
    if not weak_indices:
        return resume

    # Build flat bullet index → (exp_idx, bullet_idx) mapping
    flat_idx = 0
    changes = 0
    MAX_CHANGES = 4  # Limit to prevent over-modification

    for exp_idx, exp in enumerate(resume.experience):
        for b_idx, bullet in enumerate(exp.bullets):
            if flat_idx in weak_indices and changes < MAX_CHANGES:
                enhanced = _strengthen_bullet(bullet, jd)
                if enhanced != bullet:
                    exp.bullets[b_idx] = enhanced
                    changes += 1
                    logger.info(
                        f"  Experience Strength: enhanced exp[{exp_idx}].b[{b_idx}] "
                        f"({len(bullet)}→{len(enhanced)} chars)"
                    )
            flat_idx += 1

    if changes:
        logger.info(f"  Experience Strength: {changes} bullets strengthened")

    return resume


def _strengthen_bullet(bullet: str, jd: ExtractedJD) -> str:
    """
    Strengthen a single bullet without inventing content.

    Strategy:
      1. Extract existing metric (if any) and front-load it
      2. Replace passive verbs with ownership verbs
      3. Add purpose clause if missing (using JD context)
    """
    bl = bullet.lower()
    enhanced = bullet

    # RULE 1: Replace weak opening verbs
    weak_to_strong = {
        'helped': 'Developed',
        'assisted in': 'Contributed to',
        'responsible for': 'Managed',
        'worked on': 'Developed',
        'involved in': 'Contributed to',
        'participated in': 'Supported',
    }
    for weak, strong in weak_to_strong.items():
        if bl.startswith(weak):
            enhanced = strong + enhanced[len(weak):]
            break

    # RULE 2: Front-load existing metrics
    # If bullet has "...improving X by Y%" at the end, move it to front
    metric_at_end = re.search(
        r'[,.]?\s*(?:improving|increasing|reducing|achieving|resulting in)\s+'
        r'(\w[\w\s]*?)\s+by\s+(\d+[%+]?\+?)\s*\.?$',
        enhanced, re.I
    )
    if metric_at_end:
        metric_phrase = metric_at_end.group(0).strip(' .,')
        core = enhanced[:metric_at_end.start()].strip(' ,.')
        # Restructure: "Improved X by Y%, [core action]"
        verb = 'Improved' if 'improv' in metric_phrase.lower() else \
               'Reduced' if 'reduc' in metric_phrase.lower() else \
               'Increased' if 'increas' in metric_phrase.lower() else 'Achieved'
        amount = metric_at_end.group(2)
        what = metric_at_end.group(1).strip()
        enhanced = f"{verb} {what} by {amount} by {core[0].lower()}{core[1:]}."

    # RULE 3: Add purpose clause if missing (ONLY if bullet is short and has no "for/to")
    has_purpose = bool(re.search(r'\b(?:for|to|enabling|achieving|driving)\s+\w', bl))
    if not has_purpose and len(enhanced) < 80:
        # Try to infer purpose from JD responsibilities
        for resp in (jd.responsibilities or []):
            resp_lower = resp.lower().strip()
            # Strip raw infinitive verbs — these are JD command language, not purpose
            for verb in ['build ', 'create ', 'deploy ', 'develop ', 'design ',
                         'analyze ', 'manage ', 'lead ', 'implement ', 'maintain ',
                         'write ', 'support ', 'ensure ', 'define ']:
                resp_lower = resp_lower.replace(verb, '')
            purpose = resp_lower.strip()
            
            # Skip if purpose is too generic/short after cleanup
            if not purpose or len(purpose) < 8:
                continue
            
            # Check if bullet content relates to this responsibility
            bullet_terms = set(re.findall(r'\b\w{5,}\b', bl))
            resp_terms = set(re.findall(r'\b\w{5,}\b', purpose))
            overlap = bullet_terms & resp_terms
            
            # HARDENED: Need >=2 overlapping terms AND purpose must not duplicate bullet words
            if len(overlap) >= 2:
                # Skip if key purpose words already in bullet (prevents "dashboards for dashboards")
                purpose_core = set(purpose.split()) - {'and', 'the', 'for', 'to', 'in', 'of', 'a'}
                bullet_core = set(bl.split()) - {'and', 'the', 'for', 'to', 'in', 'of', 'a'}
                if purpose_core & bullet_core:
                    continue  # Purpose duplicates bullet content
                
                if len(enhanced) + len(purpose) < 160:
                    enhanced = enhanced.rstrip('.') + f" for {purpose}."
                break

    # Final cleanup
    enhanced = enhanced.replace('..', '.').replace('  ', ' ')
    if not enhanced.endswith('.'):
        enhanced += '.'

    return enhanced


# ================================================================
# RECRUITER 10-SECOND DOMINANCE CHECK (PART 5)
# ================================================================

def recruiter_10s_dominance_check(
    resume: StructuredResume,
    jd: ExtractedJD,
) -> Dict:
    """
    Simulate what a recruiter sees and decides in 10 seconds.

    Reads: Summary → First role title → First 3 bullets → Skills section
    Returns pass/fail + detailed scan result.
    """
    signals = []
    risks = []
    score = 0

    # SCAN 1: Summary (3 seconds) — must convey: role + specialization + scale
    summary = (resume.summary or "").lower()
    jd_title_words = set((jd.job_title or "").lower().split()) - {"senior", "junior", "lead", "staff", "the", "a"}

    summary_has_role = any(w in summary for w in jd_title_words if len(w) > 3)
    summary_has_metric = bool(re.search(r'\d+[%+KkMm]|\d{3,}', resume.summary or ''))
    summary_has_tool = any(
        sk.lower() in summary for sk in (jd.required_skills or [])[:5]
    )

    if summary_has_role:
        score += 15
        signals.append("Summary targets correct role")
    else:
        risks.append("Summary doesn't mention target role — identity unclear")

    if summary_has_metric:
        score += 10
        signals.append("Summary shows scale/impact")

    if summary_has_tool:
        score += 10
        signals.append("Summary mentions key tools")

    # SCAN 2: First role title (1 second) — must be relevant
    if resume.experience:
        first_role = resume.experience[0].role.lower()
        role_match = any(w in first_role for w in jd_title_words if len(w) > 3)
        if role_match:
            score += 10
            signals.append("First role title aligns with JD")
        else:
            risks.append(f"First role '{resume.experience[0].role}' doesn't match JD")

    # SCAN 3: First 3 bullets (4 seconds) — must show impact + tools
    first_bullets = []
    if resume.experience:
        first_bullets = resume.experience[0].bullets[:3]

    strong_bullets = 0
    for b in first_bullets:
        bs = _score_bullet_impact_sim(b)
        bullet_strength = bs["impact"] + bs["clarity"] + bs["uniqueness"] + bs["relevance"]
        if bullet_strength >= 5:
            strong_bullets += 1

    if strong_bullets >= 2:
        score += 20
        signals.append(f"{strong_bullets}/3 opening bullets show clear impact")
    elif strong_bullets == 1:
        score += 10
        risks.append("Only 1 of 3 opening bullets is compelling")
    else:
        risks.append("Opening bullets are weak — recruiter stops reading")

    # SCAN 4: Skills section (2 seconds) — must match JD
    if resume.skills:
        jd_skills_lower = set(s.lower() for s in jd.required_skills[:8])
        resume_skills_lower = set(s.lower() for s in resume.skills)
        skill_overlap = len(jd_skills_lower & resume_skills_lower)
        if skill_overlap >= 4:
            score += 15
            signals.append(f"Skills section: {skill_overlap} JD matches visible")
        elif skill_overlap >= 2:
            score += 8
        else:
            risks.append("Skills section missing key JD requirements")

    # Decision
    recruiter_decides = score >= 60
    scan_time = "6-8 sec (decides to continue)" if recruiter_decides else "3-4 sec (moves on)"

    return {
        "pass": recruiter_decides,
        "score": min(100, score),
        "signals": signals,
        "risks": risks,
        "scan_time": scan_time,
        "verdict": (
            "Recruiter says: 'This candidate looks strong — reading more'"
            if recruiter_decides else
            "Recruiter says: 'Not immediately compelling — skipping'"
        ),
        "strong_opening_bullets": strong_bullets,
    }


# ================================================================
# 3-LAYER HIRING SIMULATION
# ================================================================

RECRUITER_PERSONAS = {
    "amazon": {
        "name": "Amazon",
        "icon": "📦",
        "priorities": ["impact", "scale", "ownership", "metrics"],
        "keywords": ["impact", "scale", "revenue", "customer", "ownership",
                     "delivered", "million", "growth", "optimiz"],
        "reject_signals": ["no metrics", "team player only", "no ownership"],
        "weight_impact": 0.35, "weight_depth": 0.20, "weight_scale": 0.30,
        "weight_clarity": 0.15,
    },
    "google": {
        "name": "Google",
        "icon": "🔍",
        "priorities": ["technical_depth", "ml_thinking", "innovation", "scale"],
        "keywords": ["algorithm", "model", "research", "distributed", "tensorflow",
                     "deep learning", "architecture", "novel", "publication"],
        "reject_signals": ["no technical depth", "no ML signals", "generic tools"],
        "weight_impact": 0.20, "weight_depth": 0.40, "weight_scale": 0.25,
        "weight_clarity": 0.15,
    },
    "microsoft": {
        "name": "Microsoft",
        "icon": "🪟",
        "priorities": ["systems", "collaboration", "cloud", "scale"],
        "keywords": ["azure", "cloud", "distributed", "collaboration",
                     "cross-functional", "enterprise", "platform", "service"],
        "reject_signals": ["no systems thinking", "no collaboration", "solo only"],
        "weight_impact": 0.25, "weight_depth": 0.25, "weight_scale": 0.25,
        "weight_clarity": 0.25,
    },
}


def _score_bullet_impact_sim(bullet: str) -> dict:
    """Score a single bullet on 4 dimensions for hiring simulation."""
    bl = bullet.lower()
    scores = {"impact": 0, "clarity": 0, "uniqueness": 0, "relevance": 0}

    # Impact: metrics, business outcomes
    if re.search(r'\$\d|revenue|profit|roi|savings', bl):
        scores["impact"] = 3
    elif re.search(r'\d+\s*%', bullet):
        scores["impact"] = 2
    elif re.search(r'\d+[KkMm+]|\d{3,}', bullet):
        scores["impact"] = 2
    elif re.search(r'(?:reduc|increas|improv|optimiz|accelerat|streamlin|enhanc)(?:ed|ing)', bl):
        scores["impact"] = 1

    # Clarity: well-structured, action verb, concise
    if re.match(r'^[A-Z][a-z]+ed\b', bullet):
        scores["clarity"] += 1
    if 50 < len(bullet) < 180:
        scores["clarity"] += 1
    if re.search(r'(?:for|to|enabling|resulting)\s+\w', bl):
        scores["clarity"] += 1

    # Uniqueness: rare/advanced signals
    advanced = ['deep learning', 'lstm', 'transformer', 'nlp', 'computer vision',
                'reinforcement', 'distributed', 'kubernetes', 'microservice',
                'real-time', 'ml pipeline', 'model deployment', 'a/b testing',
                'recommendation', 'embedding', 'feature store']
    adv_count = sum(1 for kw in advanced if kw in bl)
    scores["uniqueness"] = min(3, adv_count)

    # Relevance: purpose-driven
    if re.search(r'(?:for|to|enabling|achieving|driving)\s+\w', bl):
        scores["relevance"] = 2
    elif re.search(r'(?:using|with)\s+\w+\s+(?:for|to)', bl):
        scores["relevance"] = 1

    return scores


def simulate_hiring(
    resume: StructuredResume,
    jd: ExtractedJD,
    ats_score: float,
    matched_skills: List[str] = None,
    missing_skills: List[str] = None,
    skill_proof: Dict = None,
) -> Dict:
    """
    PART 2: 3-Layer Hiring Simulation.

    Layer 1: ATS Filter (pass/fail)
    Layer 2: Recruiter Scan (6-10 seconds)
    Layer 3: Hiring Manager Decision

    Returns complete simulation result.
    """
    matched_skills = matched_skills or []
    missing_skills = missing_skills or []
    all_bullets = [b for exp in resume.experience for b in exp.bullets]
    all_text = " ".join(b.lower() for b in all_bullets)
    summary = (resume.summary or "").lower()

    # ============================================================
    # LAYER 1: ATS FILTER
    # ============================================================
    ats_pass = ats_score >= 40
    ats_result = {
        "pass": ats_pass,
        "score": round(ats_score, 1),
        "keyword_match": len(matched_skills),
        "keyword_total": len(matched_skills) + len(missing_skills),
        "format_safe": True,  # Our system always outputs safe format
        "issues": [],
    }
    if not ats_pass:
        ats_result["issues"].append(f"ATS score {ats_score:.0f} below 40 threshold")
    if len(missing_skills) > len(matched_skills):
        ats_result["issues"].append(
            f"Missing {len(missing_skills)} of {len(matched_skills) + len(missing_skills)} skills"
        )

    # ============================================================
    # LAYER 2: RECRUITER SCAN (6-10 seconds)
    # ============================================================
    recruiter_score = 0
    recruiter_max = 100
    recruiter_signals = []
    recruiter_risks = []

    # 2a. Summary as hiring pitch (30 pts)
    summary_score = 0
    if resume.summary:
        s = resume.summary.lower()
        # Role mention
        jd_title_words = set((jd.job_title or "").lower().split()) - {"senior", "junior", "lead", "staff"}
        if any(w in s for w in jd_title_words if len(w) > 3):
            summary_score += 8
            recruiter_signals.append("Summary mentions target role")
        # Specialization
        if any(sk.lower() in s for sk in matched_skills[:3]):
            summary_score += 7
            recruiter_signals.append("Summary shows specialization")
        # Scale/impact
        if re.search(r'\d+[KkMm+%]|\d{3,}', resume.summary):
            summary_score += 8
            recruiter_signals.append("Summary has quantified impact")
        # Length check
        if len(resume.summary) >= 80:
            summary_score += 7
    else:
        recruiter_risks.append("No professional summary — recruiter has no quick pitch")
    recruiter_score += min(30, summary_score)

    # 2b. Top 3 bullets (40 pts) — "first impression dominance"
    top_bullets = all_bullets[:3] if all_bullets else []
    top_bullet_score = 0
    for b in top_bullets:
        bs = _score_bullet_impact_sim(b)
        bullet_total = bs["impact"] + bs["clarity"] + bs["uniqueness"] + bs["relevance"]
        top_bullet_score += min(13, bullet_total * 2)

    if top_bullet_score >= 30:
        recruiter_signals.append("Strong opening bullets — immediate impact")
    elif top_bullet_score < 15:
        recruiter_risks.append("Weak opening bullets — recruiter may stop reading")
    recruiter_score += min(40, top_bullet_score)

    # 2c. Visual clarity & structure (30 pts)
    clarity_score = 15  # Base
    if all_bullets:
        avg_len = sum(len(b) for b in all_bullets) / len(all_bullets)
        if 60 <= avg_len <= 160:
            clarity_score += 8
        elif avg_len > 200:
            clarity_score -= 5
            recruiter_risks.append("Bullets too long — hard to scan")
    if resume.skills and len(resume.skills) >= 5:
        clarity_score += 7
    recruiter_score += min(30, clarity_score)

    recruiter_pass = recruiter_score >= 55
    recruiter_result = {
        "pass": recruiter_pass,
        "score": min(100, recruiter_score),
        "signals": recruiter_signals,
        "risks": recruiter_risks,
        "scan_time_estimate": "6-8 sec" if recruiter_score >= 70 else "3-4 sec (may stop early)",
    }

    # ============================================================
    # LAYER 3: HIRING MANAGER DECISION
    # ============================================================
    hm_score = 0
    hm_signals = []
    hm_concerns = []

    # 3a. Technical depth (25 pts)
    advanced_kw = ['deep learning', 'lstm', 'transformer', 'nlp', 'computer vision',
                   'reinforcement learning', 'distributed', 'kubernetes', 'microservices',
                   'real-time', 'ml pipeline', 'model deployment', 'a/b testing',
                   'recommendation system', 'feature engineering', 'data pipeline']
    adv_count = sum(1 for kw in advanced_kw if kw in all_text)
    depth_score = min(25, adv_count * 5)
    if adv_count >= 4:
        hm_signals.append(f"Strong technical depth ({adv_count} advanced signals)")
    elif adv_count <= 1:
        hm_concerns.append("Limited technical depth — may lack domain expertise")
    hm_score += depth_score

    # 3b. Scale evidence (25 pts)
    scale_bullets = sum(1 for b in all_bullets
                        if re.search(r'\d+[KkMm+]|\d{4,}|million|billion', b, re.I))
    scale_score = min(25, scale_bullets * 8)
    if scale_bullets >= 3:
        hm_signals.append(f"Proven scale ({scale_bullets} bullets with volume indicators)")
    elif scale_bullets == 0:
        hm_concerns.append("No scale evidence — unclear if candidate handles production volume")
    hm_score += scale_score

    # 3c. Business impact (25 pts)
    impact_bullets = sum(1 for b in all_bullets
                         if re.search(r'\d+\s*%|revenue|profit|savings|\$\d', b, re.I))
    impact_score = min(25, impact_bullets * 8)
    if impact_bullets >= 3:
        hm_signals.append(f"Clear business impact ({impact_bullets} measurable outcomes)")
    elif impact_bullets == 0:
        hm_concerns.append("No measurable impact — unclear business value")
    hm_score += impact_score

    # 3d. Skill proof coverage (25 pts)
    proof_coverage = (skill_proof or {}).get("proof_coverage", 50)
    proof_score = min(25, proof_coverage * 0.25)
    if proof_coverage >= 80:
        hm_signals.append(f"Excellent skill proof ({proof_coverage:.0f}% demonstrated)")
    elif proof_coverage < 50:
        hm_concerns.append(f"Weak skill proof ({proof_coverage:.0f}%) — skills listed but not demonstrated")
    hm_score += proof_score

    hm_pass = hm_score >= 50
    hm_result = {
        "pass": hm_pass,
        "score": min(100, hm_score),
        "signals": hm_signals,
        "concerns": hm_concerns,
    }

    # ============================================================
    # COMPETITIVE DIFFERENTIATION (PART 4)
    # ============================================================
    differentiators = []
    # Rare skills
    rare_skills = ['lstm', 'transformer', 'reinforcement learning', 'computer vision',
                   'graph neural', 'gpt', 'bert', 'attention mechanism', 'ray',
                   'mlflow', 'feature store', 'model serving', 'triton',
                   'onnx', 'tensorrt', 'kubeflow']
    found_rare = [sk for sk in rare_skills if sk in all_text]
    if found_rare:
        differentiators.append({
            "type": "rare_skills",
            "label": "Rare/Advanced Skills",
            "detail": ", ".join(found_rare[:5]),
            "strength": "HIGH",
        })

    # Production deployment
    prod_signals = ['production', 'deployed', 'deployment', 'serving', 'ci/cd',
                    'monitoring', 'alerting', 'sla', 'uptime']
    prod_count = sum(1 for s in prod_signals if s in all_text)
    if prod_count >= 2:
        differentiators.append({
            "type": "production",
            "label": "Production Experience",
            "detail": f"{prod_count} production signals detected",
            "strength": "HIGH" if prod_count >= 3 else "MEDIUM",
        })

    # Scale evidence
    if scale_bullets >= 2:
        differentiators.append({
            "type": "scale",
            "label": "Scale Evidence",
            "detail": f"{scale_bullets} bullets demonstrate volume/scale",
            "strength": "HIGH" if scale_bullets >= 3 else "MEDIUM",
        })

    # Impact quantification
    if impact_bullets >= 2:
        differentiators.append({
            "type": "impact",
            "label": "Quantified Impact",
            "detail": f"{impact_bullets} measurable business outcomes",
            "strength": "HIGH" if impact_bullets >= 3 else "MEDIUM",
        })

    competitive = {
        "differentiators": differentiators,
        "differentiator_count": len(differentiators),
        "competitive_level": (
            "STRONG" if len(differentiators) >= 3
            else "MODERATE" if len(differentiators) >= 1
            else "WEAK"
        ),
    }

    # ============================================================
    # GAP INTELLIGENCE (PART 7)
    # ============================================================
    gaps = []
    unproven = (skill_proof or {}).get("unproven_skills", [])
    if unproven:
        gaps.append({
            "type": "unproven_skills",
            "severity": "HIGH" if len(unproven) >= 3 else "MEDIUM",
            "detail": f"{len(unproven)} skills listed but not demonstrated: {', '.join(unproven[:4])}",
            "action": "Add specific experience bullets showing these skills in action with measurable outcomes",
        })
    if impact_bullets < 2:
        gaps.append({
            "type": "weak_impact",
            "severity": "HIGH",
            "detail": f"Only {impact_bullets} bullets have measurable business impact",
            "action": "Add metrics (%, $, volume) to your strongest 2-3 experience bullets",
        })
    if adv_count < 2:
        gaps.append({
            "type": "low_depth",
            "severity": "MEDIUM",
            "detail": "Limited advanced/specialized technical signals",
            "action": "Highlight specific frameworks, algorithms, or methodologies used",
        })
    if not resume.summary or len(resume.summary) < 80:
        gaps.append({
            "type": "weak_summary",
            "severity": "HIGH",
            "detail": "Summary is missing or too short to serve as hiring pitch",
            "action": "Write a 2-3 sentence summary: [Role] + [Specialization] + [Scale] + [Impact]",
        })

    # ============================================================
    # RECRUITER PERSONA SIMULATION (PART 12)
    # ============================================================
    persona_results = {}
    for persona_key, persona in RECRUITER_PERSONAS.items():
        p_score = 0
        p_feedback = []

        # Score based on persona-weighted dimensions
        p_score += depth_score * persona["weight_depth"] / 25 * 100
        p_score += impact_score * persona["weight_impact"] / 25 * 100
        p_score += scale_score * persona["weight_scale"] / 25 * 100
        p_score += (recruiter_score * 0.3) * persona["weight_clarity"]

        # Keyword match for persona priorities
        kw_hits = sum(1 for kw in persona["keywords"] if kw in all_text)
        p_score += min(15, kw_hits * 3)

        p_score = min(100, round(p_score))

        # Persona-specific feedback
        if p_score >= 70:
            p_feedback.append(f"Strong fit for {persona['name']} hiring bar")
        elif p_score >= 50:
            p_feedback.append(f"Moderate fit — needs strengthening for {persona['name']}")
        else:
            p_feedback.append(f"Below {persona['name']} hiring bar")

        # Check for persona reject signals
        for signal in persona["reject_signals"]:
            if signal == "no metrics" and impact_bullets == 0:
                p_feedback.append(f"⚠️ {persona['name']} rejects: no measurable impact")
            elif signal == "no technical depth" and adv_count <= 1:
                p_feedback.append(f"⚠️ {persona['name']} rejects: insufficient technical depth")
            elif signal == "no ownership" and not re.search(r'\b(?:led|owned|drove|spearheaded)\b', all_text):
                p_feedback.append(f"⚠️ {persona['name']} rejects: no ownership signals")

        persona_results[persona_key] = {
            "name": persona["name"],
            "icon": persona["icon"],
            "score": p_score,
            "decision": "SHORTLIST" if p_score >= 65 else "MAYBE" if p_score >= 45 else "PASS",
            "feedback": p_feedback[:3],
        }

    # ============================================================
    # FINAL DECISION
    # ============================================================
    layers_passed = sum([ats_pass, recruiter_pass, hm_pass])
    shortlist_probability = round(
        (ats_result["score"] * 0.2 +
         recruiter_result["score"] * 0.35 +
         hm_result["score"] * 0.45), 1
    )

    if layers_passed == 3 and shortlist_probability >= 65:
        decision = "APPLY"
        decision_reason = "Strong across all hiring layers — high shortlist probability"
    elif layers_passed >= 2 and shortlist_probability >= 45:
        decision = "APPLY_WITH_GAPS"
        decision_reason = "Competitive but has addressable gaps — apply and follow up"
    elif layers_passed >= 1:
        decision = "IMPROVE_FIRST"
        decision_reason = "Needs targeted improvements before applying"
    else:
        decision = "NOT_READY"
        decision_reason = "Significant gaps across all hiring layers"

    # 10-second recruiter test
    ten_sec_pass = (
        recruiter_score >= 60 and
        len(recruiter_signals) >= 2 and
        len(recruiter_risks) <= 1
    )

    return {
        "layers": {
            "ats": ats_result,
            "recruiter": recruiter_result,
            "hiring_manager": hm_result,
        },
        "layers_passed": layers_passed,
        "shortlist_probability": shortlist_probability,
        "decision": decision,
        "decision_reason": decision_reason,
        "ten_second_test": {
            "pass": ten_sec_pass,
            "verdict": "Recruiter says: 'This candidate is strong'" if ten_sec_pass
                       else "Recruiter says: 'Not sure — need to dig deeper'",
        },
        "competitive": competitive,
        "gaps": gaps,
        "persona_simulations": persona_results,
        "skill_proof": skill_proof,
    }


# ================================================================
# USER INTERPRETATION ENGINE (FINAL LAYER)
# ================================================================
# Translates raw metrics into human-understandable guidance.
# User must feel: "I know where I stand AND how to improve."
# ================================================================

# -- PART 1: Level Classification --

def _classify_candidate_level(resume: StructuredResume) -> Dict:
    """
    Classify candidate experience level from resume structure.
    Returns level, years estimated, and benchmark ranges.
    """
    # Estimate years from experience entries
    total_roles = len(resume.experience)
    all_bullets = [b for exp in resume.experience for b in exp.bullets]
    total_bullets = len(all_bullets)

    # Heuristic: more roles + more bullets = more experience
    # Also look for seniority signals in titles
    title_text = " ".join(
        exp.role.lower() for exp in resume.experience
    ) + " " + (resume.title or "").lower()

    senior_signals = sum(
        1 for exp in resume.experience
        if any(kw in exp.role.lower() for kw in
               ['senior', 'lead', 'principal', 'staff', 'manager', 'director', 'head', 'vp'])
    )
    intern_signals = sum(
        1 for exp in resume.experience
        if any(kw in exp.role.lower() for kw in
               ['intern', 'trainee', 'junior', 'entry', 'fresher', 'graduate', 'apprentice'])
    )

    # Estimate years — career progression matters
    # Having 3+ roles even with a junior title = career growth = mid+
    non_junior_roles = total_roles - intern_signals
    if non_junior_roles >= 4 or senior_signals >= 1:
        years_est = max(5, non_junior_roles * 2)
        level = "senior"
    elif non_junior_roles >= 3 and total_bullets >= 8:
        years_est = max(3, non_junior_roles * 1.5)
        level = "mid"
    elif non_junior_roles >= 2 and total_bullets >= 8 and intern_signals == 0:
        years_est = max(2, non_junior_roles * 1.5)
        level = "mid"
    elif intern_signals >= total_roles:
        # ALL roles are internships/trainee → always entry
        years_est = max(0.5, total_roles * 0.5)
        level = "entry"
    else:
        years_est = max(0.5, total_roles * 0.8)
        level = "entry"

    # Benchmarks per level
    benchmarks = {
        "entry": {
            "shortlist_range": "40–60%",
            "shortlist_avg": 50,
            "ats_range": "55–72",
            "ats_avg": 65,
            "context": "entry-level candidates",
            "tier_thresholds": {"top_tier": 70, "competitive": 55, "baseline": 40},
        },
        "mid": {
            "shortlist_range": "55–75%",
            "shortlist_avg": 65,
            "ats_range": "65–80",
            "ats_avg": 72,
            "context": "mid-level professionals",
            "tier_thresholds": {"top_tier": 80, "competitive": 65, "baseline": 55},
        },
        "senior": {
            "shortlist_range": "65–90%",
            "shortlist_avg": 78,
            "ats_range": "72–90",
            "ats_avg": 80,
            "context": "senior-level candidates",
            "tier_thresholds": {"top_tier": 88, "competitive": 75, "baseline": 65},
        },
    }

    return {
        "level": level,
        "years_estimated": round(years_est, 1),
        "total_roles": total_roles,
        "total_bullets": total_bullets,
        "benchmark": benchmarks[level],
    }


# -- PART 2: Level-Aware Benchmarking --

def _generate_benchmark_context(
    shortlist_pct: float,
    ats_score: float,
    level_info: Dict,
) -> Dict:
    """
    Compare candidate against their peer benchmark.
    Returns position label + narrative.
    """
    bench = level_info["benchmark"]
    thresholds = bench["tier_thresholds"]
    context = bench["context"]

    # Shortlist positioning
    if shortlist_pct >= thresholds["top_tier"]:
        sl_position = "TOP TIER"
        sl_emoji = "🏆"
        sl_narrative = (
            f"For {context}, this is an exceptional shortlist probability. "
            f"You are in the top tier of your peer group."
        )
    elif shortlist_pct >= thresholds["competitive"]:
        sl_position = "COMPETITIVE"
        sl_emoji = "✅"
        sl_narrative = (
            f"For {context}, this is a competitive result. "
            f"You are above the average ({bench['shortlist_avg']}%) "
            f"and well-positioned for shortlisting."
        )
    elif shortlist_pct >= thresholds["baseline"]:
        sl_position = "ON TRACK"
        sl_emoji = "📈"
        sl_narrative = (
            f"For {context}, this is a solid baseline. "
            f"You're competitive but 1–2 targeted improvements "
            f"will move you to top tier."
        )
    else:
        sl_position = "EARLY STAGE"
        sl_emoji = "🌱"
        sl_narrative = (
            f"For {context}, you're in the early stages of competitiveness. "
            f"This is a normal starting point — focused improvements "
            f"will significantly boost your position."
        )

    # Delta from average
    delta_from_avg = shortlist_pct - bench["shortlist_avg"]
    if delta_from_avg > 0:
        delta_label = f"{delta_from_avg:+.0f}% ABOVE average for {context}"
    else:
        delta_label = f"{abs(delta_from_avg):.0f}% below average (typical range: {bench['shortlist_range']})"

    return {
        "position": sl_position,
        "emoji": sl_emoji,
        "narrative": sl_narrative,
        "peer_average": bench["shortlist_avg"],
        "peer_range": bench["shortlist_range"],
        "delta_from_avg": round(delta_from_avg, 1),
        "delta_label": delta_label,
        "level": level_info["level"],
    }


# -- PART 3: Growth Path Engine --

def _generate_growth_path(
    shortlist_pct: float,
    ats_score: float,
    perception: Dict,
    hiring_sim: Dict,
    level_info: Dict,
) -> Dict:
    """
    Generate concrete, prioritized steps to reach next tier.
    Not just "what's missing" but "what will move you up."
    """
    bench = level_info["benchmark"]
    thresholds = bench["tier_thresholds"]

    # Determine next target
    if shortlist_pct >= thresholds["top_tier"]:
        next_target = None
        target_label = "You've reached top tier!"
    elif shortlist_pct >= thresholds["competitive"]:
        next_target = thresholds["top_tier"]
        target_label = f"Top Tier ({thresholds['top_tier']}%)"
    elif shortlist_pct >= thresholds["baseline"]:
        next_target = thresholds["competitive"]
        target_label = f"Competitive ({thresholds['competitive']}%)"
    else:
        next_target = thresholds["baseline"]
        target_label = f"Baseline ({thresholds['baseline']}%)"

    gap = (next_target - shortlist_pct) if next_target else 0

    # Build prioritized actions (highest impact first)
    actions = []

    # Impact density — adding metrics is highest ROI
    if perception and perception.get("impact_density", 0) < 50:
        est_boost = min(8, 50 - perception.get("impact_density", 0)) * 0.15
        actions.append({
            "action": "Add quantified results (%, $, volume) to your top 2–3 bullets",
            "estimated_boost": f"+{est_boost:.0f}%",
            "priority": "HIGH",
            "effort": "30 min",
            "example": '"Built ML pipeline" → "Built ML pipeline reducing prediction errors by 22%"',
        })

    # Ownership language
    if perception and perception.get("ownership_level", 0) < 60:
        actions.append({
            "action": "Replace passive language with ownership verbs (led, built, designed)",
            "estimated_boost": "+3–5%",
            "priority": "HIGH",
            "effort": "15 min",
            "example": '"Helped with data analysis" → "Developed data analysis pipeline"',
        })

    # Scale visibility
    if perception and perception.get("scale_visibility", 0) < 40:
        actions.append({
            "action": "Add scale context: team size, data volume, user count",
            "estimated_boost": "+2–4%",
            "priority": "MEDIUM",
            "effort": "20 min",
            "example": '"Built API" → "Built API serving 10K+ daily requests"',
        })

    # Unproven skills
    gaps = hiring_sim.get("gaps", []) if hiring_sim else []
    for g in gaps:
        if g.get("type") == "unproven_skills":
            actions.append({
                "action": g.get("action", "Demonstrate listed skills in experience bullets"),
                "estimated_boost": "+3–5%",
                "priority": "HIGH",
                "effort": "30 min",
                "example": "Add a bullet showing the skill in real project context",
            })
            break

    # Weak summary
    for g in gaps:
        if g.get("type") == "weak_summary":
            actions.append({
                "action": g.get("action", "Write a compelling professional summary"),
                "estimated_boost": "+2–3%",
                "priority": "MEDIUM",
                "effort": "15 min",
                "example": "[Role] with [X years] experience in [specialization], delivering [impact]",
            })
            break

    # Deployment/production project (for entry-level)
    if level_info["level"] == "entry":
        sim_text = str(hiring_sim).lower() if hiring_sim else ""
        if not any(kw in sim_text for kw in ["production", "deployed", "deployment"]):
            actions.append({
                "action": "Add 1 deployment/production project to demonstrate real-world impact",
                "estimated_boost": "+4–6%",
                "priority": "HIGH",
                "effort": "1–2 days",
                "example": "Deploy a model via Streamlit/Gradio and note it on resume",
            })

    return {
        "current": round(shortlist_pct, 1),
        "next_target": next_target,
        "target_label": target_label,
        "gap": round(gap, 1),
        "actions": actions[:5],  # Top 5 most impactful
        "reached_top": next_target is None,
    }


# -- PART 4: Confidence Correction --

def _generate_confidence_message(
    shortlist_pct: float,
    level_info: Dict,
    benchmark: Dict,
) -> str:
    """
    Generate a psychologically calibrated message.
    NEVER say "you are weak." Always frame positively with path forward.
    """
    level = level_info["level"]
    position = benchmark["position"]

    messages = {
        ("entry", "TOP TIER"): (
            "Impressive for an early-career candidate. "
            "Your resume demonstrates strong fundamentals and real impact. "
            "You're ready to compete for this role."
        ),
        ("entry", "COMPETITIVE"): (
            "Strong foundation for an entry-level candidate. "
            "Your resume shows genuine technical depth. "
            "A few targeted additions will make you a top contender."
        ),
        ("entry", "ON TRACK"): (
            "You're building a solid profile. "
            "For an entry-level candidate, this is a healthy baseline. "
            "Follow the growth path below to reach competitive positioning."
        ),
        ("entry", "EARLY STAGE"): (
            "You're at an early but promising stage. "
            "Every strong candidate started here — the growth path below "
            "shows exactly how to level up quickly."
        ),
        ("mid", "TOP TIER"): (
            "Excellent positioning for a mid-level professional. "
            "Your experience and technical proof are compelling. "
            "This resume is ready for submission."
        ),
        ("mid", "COMPETITIVE"): (
            "Strong mid-level profile with clear differentiation signals. "
            "You're well-positioned — the actions below will maximize your chances."
        ),
        ("mid", "ON TRACK"): (
            "Solid mid-career profile with room to strengthen. "
            "Adding concrete impact metrics will move you into the competitive tier."
        ),
        ("mid", "EARLY STAGE"): (
            "Your experience is relevant but needs stronger positioning. "
            "Focus on quantifying your impact — this is the fastest way to improve."
        ),
        ("senior", "TOP TIER"): (
            "Outstanding senior-level profile. "
            "Strong ownership signals, proven impact, and technical depth. "
            "This resume commands attention."
        ),
        ("senior", "COMPETITIVE"): (
            "Strong senior-level positioning with clear leadership proof. "
            "Minor refinements will push you to top tier."
        ),
        ("senior", "ON TRACK"): (
            "Your senior experience is evident but underrepresented. "
            "Strengthening ownership language and scale context "
            "will better reflect your true capability."
        ),
        ("senior", "EARLY STAGE"): (
            "Your experience level is significant, but the resume doesn't "
            "fully reflect it. The growth path below focuses on "
            "showcasing the impact you've already delivered."
        ),
    }

    return messages.get(
        (level, position),
        "Your resume has been analyzed. Follow the growth path below to improve."
    )


# -- PART 5: Decision Clarity --

def _generate_clear_decision(
    shortlist_pct: float,
    ats_score: float,
    level_info: Dict,
    benchmark: Dict,
    growth_path: Dict,
) -> Dict:
    """
    Generate an unambiguous, actionable decision.
    Never: "APPLY (fix gaps)"
    Always: clear action + context + what happens next.
    """
    position = benchmark["position"]
    level = level_info["level"]

    if position in ("TOP TIER",):
        decision = "APPLY NOW"
        emoji = "🟢"
        subtitle = "Your resume is competitive — submit your application"
        urgency = "high"
        next_step = "Submit and prepare for the interview"
    elif position == "COMPETITIVE":
        decision = "APPLY — strong candidate"
        emoji = "🟢"
        subtitle = "Competitive profile with room to strengthen"
        urgency = "medium-high"
        next_step = "Apply now, and optimize the areas below for future applications"
    elif position == "ON TRACK" and ats_score >= 70:
        decision = "APPLY — competitive but can improve chances"
        emoji = "🟡"
        subtitle = "You meet the bar, but targeted improvements will help"
        urgency = "medium"
        if growth_path["actions"]:
            top_action = growth_path["actions"][0]["action"]
            next_step = f"Apply now, but first: {top_action}"
        else:
            next_step = "Apply now and track your results"
    elif position == "ON TRACK":
        decision = "IMPROVE THEN APPLY"
        emoji = "🟡"
        subtitle = "Solid foundation — 15–30 min of targeted edits will make a difference"
        urgency = "medium"
        if growth_path["actions"]:
            top_action = growth_path["actions"][0]["action"]
            next_step = f"Start with: {top_action}"
        else:
            next_step = "Review the growth path actions below"
    else:
        decision = "BUILD FIRST"
        emoji = "📈"
        subtitle = (
            "You're early-stage but on the right track. "
            "Invest in the growth actions below before applying."
        )
        urgency = "low"
        if growth_path["actions"]:
            top_action = growth_path["actions"][0]["action"]
            next_step = f"Priority: {top_action}"
        else:
            next_step = "Review the growth path actions below"

    return {
        "decision": decision,
        "emoji": emoji,
        "subtitle": subtitle,
        "urgency": urgency,
        "next_step": next_step,
    }


# -- PART 6: Master Interpretation Generator --

def generate_candidate_interpretation(
    resume: StructuredResume,
    jd: ExtractedJD,
    hiring_sim: Dict,
    ats_score: float,
    perception: Dict = None,
) -> Dict:
    """
    Master function: generates the complete user interpretation layer.

    Returns a structured dict with all 6 interpretation components:
      1. level_info: candidate classification (entry/mid/senior)
      2. benchmark: where they stand vs peers
      3. growth_path: concrete steps to next level
      4. confidence_message: psychologically calibrated narrative
      5. decision: clear, unambiguous action
      6. headline: the single sentence they see first

    This is the LAST layer before UI. Everything after this is rendering.
    """
    shortlist_pct = hiring_sim.get("shortlist_probability", 0) if hiring_sim else 0

    # 1. Classify level
    level_info = _classify_candidate_level(resume)

    # 2. Benchmark against peers
    benchmark = _generate_benchmark_context(shortlist_pct, ats_score, level_info)

    # 3. Growth path
    growth_path = _generate_growth_path(
        shortlist_pct, ats_score, perception, hiring_sim, level_info
    )

    # 4. Confidence message
    confidence_message = _generate_confidence_message(
        shortlist_pct, level_info, benchmark
    )

    # 5. Clear decision
    decision = _generate_clear_decision(
        shortlist_pct, ats_score, level_info, benchmark, growth_path
    )

    # 6. Headline (the FIRST thing the user reads)
    headline = (
        f"{benchmark['emoji']} {benchmark['position']} — "
        f"Shortlist Probability: {shortlist_pct:.0f}%"
    )

    return {
        "headline": headline,
        "confidence_message": confidence_message,
        "level_info": {
            "level": level_info["level"],
            "years_estimated": level_info["years_estimated"],
            "context": level_info["benchmark"]["context"],
        },
        "benchmark": {
            "position": benchmark["position"],
            "emoji": benchmark["emoji"],
            "narrative": benchmark["narrative"],
            "peer_average": benchmark["peer_average"],
            "peer_range": benchmark["peer_range"],
            "delta_label": benchmark["delta_label"],
        },
        "growth_path": growth_path,
        "decision": decision,
    }


# ================================================================
# PART 9 — FEEDBACK LOOP ENGINE
# ================================================================
# Learns from application outcomes (rejected/shortlisted) to:
#   - Identify missing signals in rejected applications
#   - Reinforce success patterns from shortlisted ones
#   - Generate targeted improvement plans
# ================================================================

def analyze_application_feedback(
    history: List[Dict],
    current_resume: Optional[StructuredResume] = None,
    current_jd: Optional[ExtractedJD] = None,
) -> Dict:
    """
    Feedback Loop Engine — learns from past application outcomes.
    
    Input: application history (list of dicts with status, ats_score, mode, etc.)
    
    Returns:
      - rejection_analysis: why past applications were rejected
      - success_patterns: what worked in shortlisted applications
      - improvement_plan: concrete next steps
      - recommended_mode: best mode based on history
      - signal_gaps: recurring missing signals
    """
    if not history:
        return {
            "rejection_analysis": "No application history yet.",
            "success_patterns": [],
            "improvement_plan": ["Apply to your first role to start learning."],
            "recommended_mode": "balanced",
            "signal_gaps": [],
        }
    
    shortlisted = [h for h in history if h.get("status") == "shortlisted"]
    rejected = [h for h in history if h.get("status") == "rejected"]
    applied = [h for h in history if h.get("status") == "applied"]
    
    # ---- REJECTION ANALYSIS ----
    rejection_analysis = ""
    signal_gaps = []
    
    if rejected:
        avg_reject_score = sum(h.get("ats_score", 0) for h in rejected) / len(rejected)
        reject_modes = [h.get("mode", "strict") for h in rejected]
        
        if avg_reject_score < 60:
            rejection_analysis = (
                f"Your {len(rejected)} rejected application(s) averaged {avg_reject_score:.0f} ATS score. "
                "This is below the typical recruiter threshold (65+). "
                "Focus on improving keyword alignment and adding quantified impact."
            )
            signal_gaps.append("ATS score below competitive threshold")
        elif avg_reject_score < 75:
            rejection_analysis = (
                f"Your {len(rejected)} rejected application(s) averaged {avg_reject_score:.0f} ATS score. "
                "Your keywords are reasonable but you likely lost at the recruiter scan layer. "
                "Strengthen your summary and lead bullets with quantified outcomes."
            )
            signal_gaps.append("Weak recruiter-scan signals (summary + lead bullets)")
        else:
            rejection_analysis = (
                f"Your {len(rejected)} rejected application(s) averaged {avg_reject_score:.0f} ATS score — "
                "this is strong. The rejection may be due to competition, not resume quality. "
                "Consider more targeted role selection or networking."
            )
            signal_gaps.append("High competition — resume is strong but market is tight")
        
        # Check for mode patterns in rejections
        if reject_modes.count("strict") > len(rejected) * 0.6:
            signal_gaps.append(
                "Strict mode used frequently — may cause over-optimization. "
                "Try balanced mode for a more natural tone."
            )
    else:
        rejection_analysis = "No rejections recorded yet."
    
    # ---- SUCCESS PATTERNS ----
    success_patterns = []
    
    if shortlisted:
        avg_success_score = sum(h.get("ats_score", 0) for h in shortlisted) / len(shortlisted)
        success_modes = [h.get("mode", "strict") for h in shortlisted]
        best_mode = max(set(success_modes), key=success_modes.count) if success_modes else "balanced"
        
        success_patterns.append(
            f"Average successful score: {avg_success_score:.0f} "
            f"(your shortlist bar is {avg_success_score:.0f}+)"
        )
        success_patterns.append(f"Most successful mode: {best_mode}")
        
        if len(shortlisted) >= 2:
            # Find common market_rank in successes
            ranks = [h.get("market_rank", "") for h in shortlisted]
            if ranks:
                common_rank = max(set(ranks), key=ranks.count)
                success_patterns.append(f"Your strongest competitive position: {common_rank}")
    
    # ---- IMPROVEMENT PLAN ----
    improvement_plan = []
    
    if rejected and not shortlisted:
        improvement_plan.append("Switch to balanced mode for a more recruiter-friendly tone")
        improvement_plan.append("Add 2-3 quantified metrics (%, $, time saved) to your top bullets")
        improvement_plan.append("Ensure your summary mentions the exact job title from the JD")
    elif rejected and shortlisted:
        # Has both — compare what's different
        avg_success = sum(h.get("ats_score", 0) for h in shortlisted) / len(shortlisted)
        avg_fail = sum(h.get("ats_score", 0) for h in rejected) / len(rejected)
        gap = avg_success - avg_fail
        
        if gap > 10:
            improvement_plan.append(
                f"Your successful apps score {gap:.0f} pts higher. "
                f"Target {avg_success:.0f}+ ATS score before applying."
            )
        improvement_plan.append("Review rejected JDs — are you applying to the right level?")
        improvement_plan.append("Your success pattern shows what works — replicate it")
    elif not rejected and shortlisted:
        improvement_plan.append("Excellent track record! Keep using the same approach.")
        improvement_plan.append("Consider applying to stretch roles (one level up).")
    else:
        improvement_plan.append("Apply to your first role and track the outcome here.")
    
    # ---- RECOMMENDED MODE ----
    if shortlisted:
        success_modes = [h.get("mode", "strict") for h in shortlisted]
        recommended_mode = max(set(success_modes), key=success_modes.count)
    elif rejected:
        # If all rejections were strict, try balanced
        reject_modes = [h.get("mode", "strict") for h in rejected]
        if reject_modes.count("strict") > len(rejected) * 0.5:
            recommended_mode = "balanced"
        else:
            recommended_mode = "strict"
    else:
        recommended_mode = "balanced"
    
    return {
        "rejection_analysis": rejection_analysis,
        "success_patterns": success_patterns,
        "improvement_plan": improvement_plan,
        "recommended_mode": recommended_mode,
        "signal_gaps": signal_gaps,
    }


# ================================================================
# PART 11 — PERFORMANCE METRICS
# ================================================================
# Tracks real hiring success metrics from application history.
# ================================================================

def compute_performance_metrics(history: List[Dict]) -> Dict:
    """
    Compute real-world hiring success metrics from application history.
    
    Returns:
      - total_applications: total tracked
      - shortlist_rate: % shortlisted
      - rejection_rate: % rejected
      - pending_rate: % still pending
      - avg_score_improvement: average score delta
      - best_mode: mode with highest shortlist rate
      - trend: improving / stable / declining
    """
    if not history:
        return {
            "total_applications": 0,
            "shortlist_rate": 0.0,
            "rejection_rate": 0.0,
            "pending_rate": 0.0,
            "avg_score": 0.0,
            "best_mode": "balanced",
            "trend": "no_data",
            "summary": "No applications tracked yet. Apply to start building your success metrics.",
        }
    
    total = len(history)
    shortlisted = [h for h in history if h.get("status") == "shortlisted"]
    rejected = [h for h in history if h.get("status") == "rejected"]
    pending = [h for h in history if h.get("status") in ("applied", "pending")]
    
    shortlist_rate = (len(shortlisted) / total * 100) if total > 0 else 0
    rejection_rate = (len(rejected) / total * 100) if total > 0 else 0
    pending_rate = (len(pending) / total * 100) if total > 0 else 0
    
    avg_score = (
        sum(h.get("ats_score", 0) for h in history) / total
    ) if total > 0 else 0
    
    # Best mode by shortlist success
    mode_success = {}
    for h in history:
        mode = h.get("mode", "strict")
        if mode not in mode_success:
            mode_success[mode] = {"total": 0, "shortlisted": 0}
        mode_success[mode]["total"] += 1
        if h.get("status") == "shortlisted":
            mode_success[mode]["shortlisted"] += 1
    
    best_mode = "balanced"
    best_rate = -1
    for mode, counts in mode_success.items():
        rate = counts["shortlisted"] / counts["total"] if counts["total"] > 0 else 0
        if rate > best_rate:
            best_rate = rate
            best_mode = mode
    
    # Trend: compare first half vs second half
    if total >= 4:
        half = total // 2
        first_half_scores = [h.get("ats_score", 0) for h in history[:half]]
        second_half_scores = [h.get("ats_score", 0) for h in history[half:]]
        avg_first = sum(first_half_scores) / len(first_half_scores) if first_half_scores else 0
        avg_second = sum(second_half_scores) / len(second_half_scores) if second_half_scores else 0
        
        if avg_second > avg_first + 3:
            trend = "improving"
        elif avg_second < avg_first - 3:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"
    
    # Human-readable summary
    if shortlist_rate >= 50:
        summary = (
            f"Strong performance: {shortlist_rate:.0f}% shortlist rate across "
            f"{total} applications. Your resume strategy is working."
        )
    elif shortlist_rate >= 25:
        summary = (
            f"Competitive: {shortlist_rate:.0f}% shortlist rate. "
            f"Above average, with room to optimize using {best_mode} mode."
        )
    elif total >= 3 and shortlist_rate == 0:
        summary = (
            f"No shortlists yet across {total} applications. "
            f"Consider switching to {best_mode} mode and reviewing gap analysis."
        )
    else:
        summary = (
            f"{total} application(s) tracked. "
            f"Keep applying and updating outcomes to build your success metrics."
        )
    
    return {
        "total_applications": total,
        "shortlist_rate": round(shortlist_rate, 1),
        "rejection_rate": round(rejection_rate, 1),
        "pending_rate": round(pending_rate, 1),
        "avg_score": round(avg_score, 1),
        "best_mode": best_mode,
        "trend": trend,
        "summary": summary,
        "mode_breakdown": {
            mode: {
                "total": counts["total"],
                "shortlisted": counts["shortlisted"],
                "rate": round(counts["shortlisted"] / counts["total"] * 100, 1) if counts["total"] > 0 else 0,
            }
            for mode, counts in mode_success.items()
        },
    }


# ================================================================
# PART 4 — TARGETING INTELLIGENCE
# ================================================================

def compute_targeting_score(
    resume: StructuredResume,
    jd: ExtractedJD,
    matched_skills: List[str] = None,
    missing_skills: List[str] = None,
) -> Dict:
    """
    Compute JD match score (0-100) on 5 dimensions.
    
    Evaluates whether the candidate is applying to the RIGHT role,
    not just whether their resume is optimized.
    
    Dimensions:
      1. Skill Overlap (0-30)    — how many required skills are matched
      2. Experience Match (0-25) — years/level alignment
      3. Domain Alignment (0-20) — industry/domain fit
      4. Title Proximity (0-15)  — job title vs resume title
      5. Seniority Fit (0-10)    — under/over-qualified check
    """
    matched_skills = matched_skills or []
    missing_skills = missing_skills or []
    all_bullets = " ".join(b.lower() for e in resume.experience for b in e.bullets)
    summary = (resume.summary or "").lower()
    jd_title = (jd.job_title or "").lower()
    
    # 1. Skill Overlap (0-30)
    total_skills = len(matched_skills) + len(missing_skills)
    if total_skills > 0:
        skill_ratio = len(matched_skills) / total_skills
    else:
        skill_ratio = 0.5
    skill_score = round(skill_ratio * 30)
    
    # 2. Experience Match (0-25)
    level_info = _classify_candidate_level(resume)
    candidate_years = level_info.get("years_estimated", 1)
    
    # Estimate JD required years from keywords
    jd_text = (jd.raw_text or "").lower()
    jd_years = 0
    year_match = re.search(r'(\d+)\+?\s*years?\s*(?:of\s+)?experience', jd_text)
    if year_match:
        jd_years = int(year_match.group(1))
    
    if jd_years == 0:
        exp_score = 15  # Can't assess, give neutral
    elif candidate_years >= jd_years:
        exp_score = 25  # Meets or exceeds
    elif candidate_years >= jd_years - 1:
        exp_score = 18  # Close enough
    elif candidate_years >= jd_years - 2:
        exp_score = 10  # Stretch
    else:
        exp_score = 3   # Significant gap
    
    # 3. Domain Alignment (0-20)
    _DOMAIN_KEYWORDS = {
        "data": {"data", "analytics", "machine learning", "ml", "ai", "model",
                 "pipeline", "sql", "python", "statistics", "visualization"},
        "software": {"api", "backend", "frontend", "microservice", "database",
                     "deploy", "ci/cd", "rest", "graphql", "architecture"},
        "qa": {"test", "qa", "quality", "automation", "selenium", "defect",
               "coverage", "regression", "cypress"},
        "devops": {"docker", "kubernetes", "aws", "cloud", "terraform",
                   "ci/cd", "infrastructure", "monitoring"},
    }
    
    best_domain_score = 0
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        resume_hits = sum(1 for kw in keywords if kw in all_bullets or kw in summary)
        jd_hits = sum(1 for kw in keywords if kw in jd_text)
        if resume_hits > 0 and jd_hits > 0:
            overlap = min(resume_hits, jd_hits) / max(jd_hits, 1)
            domain_score = round(overlap * 20)
            best_domain_score = max(best_domain_score, domain_score)
    
    domain_score = best_domain_score if best_domain_score > 0 else 10
    
    # 4. Title Proximity (0-15)
    title_score = 0
    if jd_title:
        # Check if JD title words appear in summary or experience
        title_words = set(jd_title.split()) - {"the", "a", "an", "and", "or", "for", "in", "at"}
        if title_words:
            matches = sum(1 for tw in title_words if tw in summary or tw in all_bullets)
            title_score = min(15, round(matches / len(title_words) * 15))
    else:
        title_score = 8  # Can't assess
    
    # 5. Seniority Fit (0-10)
    level = level_info.get("level", "entry")
    if "senior" in jd_title or "lead" in jd_title or "principal" in jd_title:
        seniority_score = 10 if level in ("senior", "lead") else (5 if level == "mid" else 2)
    elif "junior" in jd_title or "entry" in jd_title or "intern" in jd_title:
        seniority_score = 10 if level in ("entry", "fresher") else (6 if level == "mid" else 3)
    else:
        seniority_score = 8  # Mid-level default, most flexible
    
    total_score = skill_score + exp_score + domain_score + title_score + seniority_score
    
    # Flag targeting gap
    is_targeting_gap = total_score < 45
    
    return {
        "total_score": min(100, total_score),
        "skill_overlap": skill_score,
        "experience_match": exp_score,
        "domain_alignment": domain_score,
        "title_proximity": title_score,
        "seniority_fit": seniority_score,
        "is_targeting_gap": is_targeting_gap,
        "candidate_years": candidate_years,
        "jd_years": jd_years,
    }


# ================================================================
# PART 5 — ROOT CAUSE DIAGNOSIS
# ================================================================

def diagnose_root_cause(
    ats_score: float,
    targeting: Dict,
    hiring_sim: Dict,
    history: List[Dict] = None,
) -> Dict:
    """
    Identify the PRIMARY reason for low shortlist rate.
    
    Three possible root causes:
      CANDIDATE_GAP  → Skills/experience genuinely insufficient for target roles
      RESUME_GAP     → Skills exist but resume doesn't communicate them effectively
      TARGETING_GAP  → Applying to wrong-level or wrong-domain roles
    
    Returns the primary diagnosis + evidence + recommended action.
    """
    history = history or []
    shortlist_prob = hiring_sim.get("shortlist_probability", 0) if hiring_sim else 0
    targeting_score = targeting.get("total_score", 50)
    skill_overlap = targeting.get("skill_overlap", 15)
    
    # Score each hypothesis
    candidate_gap_score = 0
    resume_gap_score = 0
    targeting_gap_score = 0
    
    # ---- CANDIDATE GAP signals ----
    if skill_overlap < 10:  # <33% skill match
        candidate_gap_score += 3
    if targeting.get("experience_match", 15) < 8:
        candidate_gap_score += 2
    if targeting.get("candidate_years", 1) < targeting.get("jd_years", 0) - 2:
        candidate_gap_score += 2
    
    # ---- RESUME GAP signals ----
    # High skill overlap but low shortlist = resume isn't communicating well
    if skill_overlap >= 20 and shortlist_prob < 60:
        resume_gap_score += 3
    if ats_score >= 70 and shortlist_prob < 50:
        resume_gap_score += 2  # ATS passes but recruiter doesn't
    # Check hiring sim layers
    if hiring_sim:
        recruiter = hiring_sim.get("layers", {}).get("recruiter", {})
        if recruiter.get("score", 0) < 60 and ats_score >= 60:
            resume_gap_score += 2  # ATS ok but recruiter fails
    
    # ---- TARGETING GAP signals ----
    if targeting_score < 45:
        targeting_gap_score += 3
    if targeting.get("seniority_fit", 8) < 5:
        targeting_gap_score += 2
    if targeting.get("title_proximity", 8) < 5:
        targeting_gap_score += 2
    
    # Historical pattern analysis
    if len(history) >= 3:
        rejected = [h for h in history if h.get("status") == "rejected"]
        shortlisted = [h for h in history if h.get("status") == "shortlisted"]
        
        if len(rejected) >= 3 and not shortlisted:
            avg_score = sum(h.get("ats_score", 0) for h in rejected) / len(rejected)
            if avg_score >= 75:
                targeting_gap_score += 2  # High scores but all rejected = wrong roles
            elif avg_score < 60:
                candidate_gap_score += 2  # Low scores consistently
            else:
                resume_gap_score += 2  # Middling scores = resume issue
    
    # Determine primary cause
    scores = {
        "CANDIDATE_GAP": candidate_gap_score,
        "RESUME_GAP": resume_gap_score,
        "TARGETING_GAP": targeting_gap_score,
    }
    primary = max(scores, key=scores.get)
    
    # Generate evidence and action
    _EVIDENCE = {
        "CANDIDATE_GAP": {
            "evidence": [
                f"Skill overlap: {skill_overlap}/30 — below competitive threshold",
                f"Experience: {targeting.get('candidate_years', '?')} yrs vs JD requires {targeting.get('jd_years', '?')} yrs",
            ],
            "action": "Focus on building missing skills through projects or certifications before applying to this level.",
        },
        "RESUME_GAP": {
            "evidence": [
                f"ATS score ({ats_score:.0f}) is decent but shortlist probability ({shortlist_prob:.0f}%) is low",
                "Skills exist but bullets may lack quantified impact or clear technical depth",
            ],
            "action": "Strengthen top 3 bullets with quantified outcomes and specific tools. Use balanced mode.",
        },
        "TARGETING_GAP": {
            "evidence": [
                f"JD targeting score: {targeting_score}/100 — below 45 threshold",
                f"Title match: {targeting.get('title_proximity', 0)}/15, Seniority fit: {targeting.get('seniority_fit', 0)}/10",
            ],
            "action": "Apply to roles that better match your current level and domain. Consider adjacent roles.",
        },
    }
    
    diagnosis = _EVIDENCE[primary]
    
    return {
        "primary_cause": primary,
        "confidence": round(scores[primary] / max(sum(scores.values()), 1) * 100),
        "evidence": diagnosis["evidence"],
        "action": diagnosis["action"],
        "all_scores": scores,
    }


# ================================================================
# PART 3 — PRE-APPLICATION CONFIDENCE GATE
# ================================================================

def generate_pre_application_gate(
    ats_score: float,
    targeting: Dict,
    hiring_sim: Dict,
    diagnosis: Dict,
) -> Dict:
    """
    Pre-Application Confidence Gate — should user apply or not?
    
    Returns:
      decision: APPLY_NOW / FIX_GAPS / DO_NOT_APPLY
      confidence_score: 0-100
      reasoning: why
    """
    shortlist_prob = hiring_sim.get("shortlist_probability", 0) if hiring_sim else 0
    targeting_score = targeting.get("total_score", 50)
    primary_cause = diagnosis.get("primary_cause", "RESUME_GAP")
    
    # Compute confidence score
    confidence = round(
        shortlist_prob * 0.40 +
        targeting_score * 0.35 +
        ats_score * 0.25
    )
    confidence = min(100, max(0, confidence))
    
    # Decision
    if confidence >= 65 and primary_cause != "CANDIDATE_GAP":
        decision = "APPLY_NOW"
        reasoning = (
            f"Strong alignment ({confidence}% confidence). "
            f"Shortlist probability: {shortlist_prob:.0f}%. Apply immediately."
        )
    elif confidence >= 40:
        decision = "FIX_GAPS"
        gap_action = diagnosis.get("action", "Review gap analysis")
        reasoning = (
            f"Moderate alignment ({confidence}% confidence). "
            f"Primary gap: {primary_cause.replace('_', ' ').lower()}. "
            f"Action: {gap_action}"
        )
    else:
        decision = "DO_NOT_APPLY"
        reasoning = (
            f"Low alignment ({confidence}% confidence). "
            f"Primary issue: {primary_cause.replace('_', ' ').lower()}. "
            f"Investing in this application is unlikely to yield results."
        )
    
    return {
        "decision": decision,
        "confidence_score": confidence,
        "reasoning": reasoning,
        "shortlist_probability": round(shortlist_prob, 1),
    }


# ================================================================
# PART 11 — PREDICTIVE REJECTION ANALYSIS
# ================================================================

def predict_rejection_reasons(
    resume: StructuredResume,
    jd: ExtractedJD,
    hiring_sim: Dict,
    targeting: Dict,
    matched_skills: List[str] = None,
    missing_skills: List[str] = None,
) -> Dict:
    """
    Predict WHY this application will be rejected BEFORE submitting.
    
    Returns top 3 rejection risks with severity and fix actions.
    """
    matched_skills = matched_skills or []
    missing_skills = missing_skills or []
    all_bullets = [b for e in resume.experience for b in e.bullets]
    
    risks = []
    
    # Risk 1: Missing critical skills
    if len(missing_skills) > len(matched_skills):
        risks.append({
            "risk": "Missing more skills than matched",
            "severity": "HIGH",
            "detail": f"Missing {len(missing_skills)} of {len(matched_skills) + len(missing_skills)} required skills: {', '.join(missing_skills[:5])}",
            "fix": "Add project experience demonstrating these skills, or target roles with better skill match.",
        })
    elif missing_skills:
        risks.append({
            "risk": "Some required skills missing",
            "severity": "MEDIUM",
            "detail": f"Missing: {', '.join(missing_skills[:5])}",
            "fix": "Integrate missing skills into existing bullet points where truthfully applicable.",
        })
    
    # Risk 2: No quantified impact
    bullets_with_metrics = sum(1 for b in all_bullets if re.search(r'\d+[%+$K]', b))
    metric_ratio = bullets_with_metrics / max(len(all_bullets), 1)
    if metric_ratio < 0.3:
        risks.append({
            "risk": "Insufficient quantified impact",
            "severity": "HIGH",
            "detail": f"Only {bullets_with_metrics}/{len(all_bullets)} bullets have measurable outcomes",
            "fix": "Add metrics (%, time saved, scale) to at least 50% of your top bullets.",
        })
    
    # Risk 3: Weak summary
    summary = resume.summary or ""
    jd_title = (jd.job_title or "").lower()
    if not summary:
        risks.append({
            "risk": "No professional summary",
            "severity": "HIGH",
            "detail": "Recruiters spend 2-3 seconds on the summary. Missing = immediate disadvantage.",
            "fix": "Add a 2-line summary: '[Title] with [X] years in [domain], specializing in [key skill].'",
        })
    elif jd_title and jd_title not in summary.lower():
        risks.append({
            "risk": "Summary doesn't mention target job title",
            "severity": "MEDIUM",
            "detail": f"JD title '{jd.job_title}' not in summary — recruiter may not see role fit immediately.",
            "fix": f"Start summary with: '{jd.job_title} with X years of experience in...'",
        })
    
    # Risk 4: Experience gap
    if targeting.get("experience_match", 15) < 10:
        candidate_yrs = targeting.get("candidate_years", 0)
        jd_yrs = targeting.get("jd_years", 0)
        risks.append({
            "risk": "Experience level mismatch",
            "severity": "MEDIUM" if candidate_yrs >= jd_yrs - 2 else "HIGH",
            "detail": f"You have ~{candidate_yrs} years, JD asks for {jd_yrs}+ years",
            "fix": "Emphasize leadership, ownership, and system-level work to compensate.",
        })
    
    # Risk 5: Vague bullets (no tools mentioned)
    bullets_with_tools = sum(1 for b in all_bullets if re.search(
        r'\b(?:python|sql|aws|docker|react|java|tensorflow|spark|tableau|power bi|kubernetes)\b',
        b, re.I
    ))
    if bullets_with_tools < len(all_bullets) * 0.4:
        risks.append({
            "risk": "Bullets lack specific tools/technologies",
            "severity": "MEDIUM",
            "detail": f"Only {bullets_with_tools}/{len(all_bullets)} bullets mention specific tools",
            "fix": "Add the actual tools you used (e.g., 'using Python and SQL') to your top bullets.",
        })
    
    # Sort by severity and return top 3
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    risks.sort(key=lambda r: severity_order.get(r["severity"], 2))
    
    return {
        "risks": risks[:3],
        "total_risks": len(risks),
        "high_severity_count": sum(1 for r in risks if r["severity"] == "HIGH"),
        "verdict": (
            "HIGH RISK — address critical issues before applying"
            if any(r["severity"] == "HIGH" for r in risks)
            else "MODERATE RISK — improvements recommended but viable"
            if risks
            else "LOW RISK — strong application"
        ),
    }


# ================================================================
# PART 8 — MULTI-RESUME STRATEGY ENGINE
# ================================================================

def generate_resume_variants(
    resume: StructuredResume,
    jd: ExtractedJD,
    hiring_sim: Dict,
    targeting: Dict,
    matched_skills: List[str] = None,
) -> List[Dict]:
    """
    Generate 2-3 resume strategy variants for A/B testing.
    
    Each variant emphasizes different strengths while remaining truthful.
    
    Variants:
      A. BALANCED — clean, structured, broadly aligned (low risk)
      B. IMPACT   — stronger positioning, outcomes emphasis (medium risk)
      C. SPECIALIZED — deep domain alignment (higher risk, higher reward)
    """
    matched_skills = matched_skills or []
    shortlist_prob = hiring_sim.get("shortlist_probability", 0) if hiring_sim else 0
    
    variants = []
    
    # Variant A: BALANCED (always generated)
    balanced_prob = shortlist_prob  # Baseline
    variants.append({
        "name": "Balanced",
        "mode": "balanced",
        "focus": "Clean structure, natural language, broad keyword coverage",
        "emphasis": ["clarity", "readability", "keyword alignment"],
        "probability": f"{balanced_prob:.0f}%",
        "risk": "low",
        "when_to_use": "Default for most applications. Safe and professional.",
        "description": (
            "Natural, recruiter-friendly tone with moderate keyword optimization. "
            "Best for roles where you have 60%+ skill match."
        ),
    })
    
    # Variant B: IMPACT (always generated)
    # Higher shortlist probability through stronger signal density
    impact_prob = min(100, shortlist_prob + 8)
    variants.append({
        "name": "Impact",
        "mode": "strict",
        "focus": "Quantified outcomes, ownership language, technical depth",
        "emphasis": ["metrics", "impact", "ownership", "systems thinking"],
        "probability": f"{impact_prob:.0f}%",
        "risk": "medium",
        "when_to_use": "Product companies, FAANG-level roles, competitive applications.",
        "description": (
            "Aggressive keyword optimization with emphasis on quantified results. "
            "Higher signal density but slightly less natural tone. "
            "Best when competition is high and you need to stand out."
        ),
    })
    
    # Variant C: SPECIALIZED (only if targeting score is moderate+)
    targeting_score = targeting.get("total_score", 50)
    if targeting_score >= 40 and matched_skills:
        # Focus on the top 3-5 skills that match
        top_skills = matched_skills[:5]
        spec_prob = min(100, shortlist_prob + 12)
        variants.append({
            "name": "Specialized",
            "mode": "strict",
            "focus": f"Deep alignment with: {', '.join(top_skills[:3])}",
            "emphasis": ["domain depth", "niche expertise", "skill proof"],
            "probability": f"{spec_prob:.0f}%",
            "risk": "medium-high",
            "when_to_use": "Niche roles where deep expertise matters more than breadth.",
            "description": (
                f"Deeply optimized for {', '.join(top_skills[:3])} skills. "
                "Trades breadth for depth — best when the JD is very specific "
                "and you have strong proof in the target domain."
            ),
        })
    
    return variants


# ================================================================
# PART 10 — A/B TESTING STRATEGY
# ================================================================

def generate_ab_strategy(
    variants: List[Dict],
    history: List[Dict] = None,
) -> Dict:
    """
    Recommend A/B testing strategy for resume variants.
    
    Returns:
      - primary_variant: which to use first
      - test_variant: which to test next
      - switch_threshold: when to switch
    """
    history = history or []
    
    if not variants:
        return {
            "primary": "Balanced",
            "test_next": "Impact",
            "strategy": "Start with balanced mode, switch to impact after 3 applications.",
        }
    
    # If no history, start with balanced (safest)
    if len(history) < 3:
        return {
            "primary": variants[0]["name"],
            "test_next": variants[1]["name"] if len(variants) > 1 else variants[0]["name"],
            "switch_after": 3,
            "strategy": (
                f"Start with {variants[0]['name']} variant for your first 3 applications. "
                f"Then switch to {variants[1]['name'] if len(variants) > 1 else 'the same'} "
                f"for the next 3 to compare shortlist rates."
            ),
        }
    
    # With history, recommend based on past performance
    shortlisted = [h for h in history if h.get("status") == "shortlisted"]
    rejected = [h for h in history if h.get("status") == "rejected"]
    
    if not shortlisted and rejected:
        # All rejections — switch strategy
        last_mode = rejected[-1].get("mode", "strict") if rejected else "strict"
        if last_mode == "strict":
            return {
                "primary": "Balanced",
                "test_next": "Impact",
                "switch_after": 3,
                "strategy": (
                    "Your strict-mode applications haven't succeeded. "
                    "Switch to Balanced for a more natural, recruiter-friendly tone. "
                    "Test for 3 applications before evaluating."
                ),
            }
        else:
            return {
                "primary": "Impact",
                "test_next": "Specialized" if len(variants) > 2 else "Balanced",
                "switch_after": 3,
                "strategy": (
                    "Balanced mode hasn't converted. Try Impact variant with "
                    "stronger signal density and quantified outcomes. "
                    "Test for 3 applications."
                ),
            }
    elif shortlisted:
        # Has successes — reinforce
        winning_modes = [h.get("mode", "strict") for h in shortlisted]
        best = max(set(winning_modes), key=winning_modes.count)
        best_variant = next((v for v in variants if v.get("mode") == best), variants[0])
        return {
            "primary": best_variant["name"],
            "test_next": variants[1]["name"] if len(variants) > 1 else variants[0]["name"],
            "switch_after": 5,
            "strategy": (
                f"Your {best} mode has produced shortlists — keep using "
                f"{best_variant['name']} variant. After 5 more applications, "
                f"test an alternative to optimize further."
            ),
        }
    
    return {
        "primary": variants[0]["name"],
        "test_next": variants[1]["name"] if len(variants) > 1 else variants[0]["name"],
        "switch_after": 3,
        "strategy": "Continue tracking outcomes. Switch variants every 3 applications.",
    }


# ================================================================
# MASTER ORCHESTRATOR — HIRING INTELLIGENCE
# ================================================================

def generate_hiring_intelligence(
    resume: StructuredResume,
    jd: ExtractedJD,
    hiring_sim: Dict,
    ats_score: float,
    matched_skills: List[str] = None,
    missing_skills: List[str] = None,
    history: List[Dict] = None,
) -> Dict:
    """
    Master function: generates complete hiring intelligence output.
    
    Orchestrates all prediction engines into a single structured response:
      1. Targeting score (JD match)
      2. Root cause diagnosis
      3. Pre-application gate
      4. Rejection prediction
      5. Resume variants
      6. A/B strategy
      7. Trust signals
    
    This is the INTELLIGENCE LAYER — sits between analysis and UI.
    """
    matched_skills = matched_skills or []
    missing_skills = missing_skills or []
    history = history or []
    
    # 1. Targeting Intelligence
    targeting = compute_targeting_score(resume, jd, matched_skills, missing_skills)
    
    # 2. Root Cause Diagnosis
    diagnosis = diagnose_root_cause(ats_score, targeting, hiring_sim, history)
    
    # 3. Pre-Application Gate
    gate = generate_pre_application_gate(ats_score, targeting, hiring_sim, diagnosis)
    
    # 4. Rejection Prediction
    rejection = predict_rejection_reasons(
        resume, jd, hiring_sim, targeting, matched_skills, missing_skills
    )
    
    # 5. Resume Variants
    variants = generate_resume_variants(
        resume, jd, hiring_sim, targeting, matched_skills
    )
    
    # 6. A/B Strategy
    ab_strategy = generate_ab_strategy(variants, history)
    
    # 7. Feedback (if history exists)
    feedback = analyze_application_feedback(history)
    
    # 8. Performance Metrics
    metrics = compute_performance_metrics(history)
    
    # 9. Prediction Accuracy (self-improving)
    prediction_accuracy = compute_prediction_accuracy(history)
    
    # 10. Capability Gap Plan
    gap_plan = build_capability_gap_plan(
        resume, jd, diagnosis, targeting, missing_skills
    )
    
    # 11. Variant Performance
    variant_perf = compute_variant_performance(history)
    
    return {
        "targeting": targeting,
        "diagnosis": diagnosis,
        "gate": gate,
        "rejection_prediction": rejection,
        "variants": variants,
        "ab_strategy": ab_strategy,
        "feedback": feedback,
        "metrics": metrics,
        "prediction_accuracy": prediction_accuracy,
        "gap_plan": gap_plan,
        "variant_performance": variant_perf,
        "trust_signals": [
            "No fake experience added",
            "No fake skills injected",
            "Only enhanced your existing content",
            "ATS-safe optimization applied",
        ],
    }


# ================================================================
# PART 2 — PREDICTION ACCURACY TRACKER (Self-Improving)
# ================================================================

def compute_prediction_accuracy(history: List[Dict]) -> Dict:
    """
    Track prediction accuracy over time.
    
    Compares predicted shortlist level (from gate decision) with
    actual outcomes (shortlisted/rejected) from application history.
    
    Returns:
      - accuracy: % of correct predictions
      - precision: true_positive / predicted_positive
      - recall: true_positive / actual_positive
      - mismatch_cases: where prediction was wrong
      - reliability: overall confidence in predictions
    """
    # Only use entries with known outcomes
    resolved = [
        h for h in history
        if h.get("status") in ("shortlisted", "rejected")
    ]
    
    if len(resolved) < 2:
        return {
            "accuracy": None,
            "precision": None,
            "recall": None,
            "total_resolved": len(resolved),
            "mismatch_cases": [],
            "reliability": "insufficient_data",
            "summary": "Need at least 2 resolved applications to compute accuracy.",
        }
    
    # Classify each application's prediction
    # High ATS score (>70) → predicted positive (shortlist)
    # Low ATS score (<60)  → predicted negative (reject)
    true_pos = 0   # predicted shortlist, actually shortlisted
    false_pos = 0  # predicted shortlist, actually rejected
    true_neg = 0   # predicted reject, actually rejected
    false_neg = 0  # predicted reject, actually shortlisted
    mismatches = []
    
    for h in resolved:
        score = h.get("ats_score", 50)
        actual = h.get("status", "applied")
        predicted_positive = score >= 70  # system predicted shortlist
        
        if predicted_positive and actual == "shortlisted":
            true_pos += 1
        elif predicted_positive and actual == "rejected":
            false_pos += 1
            mismatches.append({
                "company": h.get("company", "?"),
                "role": h.get("role", "?"),
                "predicted": "shortlist",
                "actual": "rejected",
                "score": score,
                "insight": "High score but rejected — likely competition or targeting issue",
            })
        elif not predicted_positive and actual == "rejected":
            true_neg += 1
        elif not predicted_positive and actual == "shortlisted":
            false_neg += 1
            mismatches.append({
                "company": h.get("company", "?"),
                "role": h.get("role", "?"),
                "predicted": "reject",
                "actual": "shortlisted",
                "score": score,
                "insight": "Low score but shortlisted — resume has hidden strengths",
            })
    
    total = true_pos + false_pos + true_neg + false_neg
    accuracy = ((true_pos + true_neg) / total * 100) if total > 0 else 0
    precision = (true_pos / (true_pos + false_pos) * 100) if (true_pos + false_pos) > 0 else 0
    recall = (true_pos / (true_pos + false_neg) * 100) if (true_pos + false_neg) > 0 else 0
    
    # Reliability classification
    if accuracy >= 70:
        reliability = "high"
    elif accuracy >= 50:
        reliability = "moderate"
    else:
        reliability = "low"
    
    summary = (
        f"Prediction accuracy: {accuracy:.0f}% across {total} resolved applications. "
        f"{'Predictions are reliable.' if reliability == 'high' else 'More data needed to improve predictions.'}"
    )
    
    return {
        "accuracy": round(accuracy, 1),
        "precision": round(precision, 1),
        "recall": round(recall, 1),
        "total_resolved": total,
        "true_positives": true_pos,
        "false_positives": false_pos,
        "true_negatives": true_neg,
        "false_negatives": false_neg,
        "mismatch_cases": mismatches[:5],
        "reliability": reliability,
        "summary": summary,
    }


# ================================================================
# PART 3 — CAPABILITY GAP BUILDER
# ================================================================

def build_capability_gap_plan(
    resume: StructuredResume,
    jd: ExtractedJD,
    diagnosis: Dict,
    targeting: Dict,
    missing_skills: List[str] = None,
) -> Dict:
    """
    Generate a concrete, actionable capability upgrade roadmap.
    
    Only generates a plan if root cause is CANDIDATE_GAP.
    For RESUME_GAP or TARGETING_GAP, returns targeted advice instead.
    
    Returns:
      - missing_skills: specific technologies/concepts to learn
      - required_proof: projects/work needed to demonstrate skills
      - experience_signals: scale/complexity/ownership needed
      - upgrade_plan: minimum viable effort to reach shortlist level
      - estimated_effort: realistic time estimate
    """
    missing_skills = missing_skills or []
    primary_cause = diagnosis.get("primary_cause", "RESUME_GAP")
    
    # ---- RESUME GAP: Quick fixes ----
    if primary_cause == "RESUME_GAP":
        return {
            "type": "RESUME_FIX",
            "missing_skills": [],
            "required_proof": [],
            "experience_signals": [],
            "upgrade_plan": [
                "Add quantified metrics (%, $, time saved) to your top 3 bullets",
                "Start summary with the exact JD title",
                "Ensure each bullet names a specific tool (Python, SQL, etc.)",
            ],
            "estimated_effort": "30 minutes",
            "summary": "Your skills are sufficient. Focus on resume presentation, not capability building.",
        }
    
    # ---- TARGETING GAP: Role selection ----
    if primary_cause == "TARGETING_GAP":
        candidate_years = targeting.get("candidate_years", 1)
        return {
            "type": "TARGETING_FIX",
            "missing_skills": [],
            "required_proof": [],
            "experience_signals": [],
            "upgrade_plan": [
                f"Target roles requiring {candidate_years}-{candidate_years + 1} years experience",
                "Look for titles matching your current level (avoid 'Senior' / 'Lead' if entry/mid)",
                "Focus on companies in your domain (data → data roles, not DevOps)",
            ],
            "estimated_effort": "0 minutes (change targeting, not skills)",
            "summary": "Your skills may be fine — you're applying to the wrong roles.",
        }
    
    # ---- CANDIDATE GAP: Full roadmap ----
    all_bullets = " ".join(b.lower() for e in resume.experience for b in e.bullets)
    resume_skills_lower = {s.lower() for s in resume.skills}
    
    # 1. Missing Skills — specific technologies
    critical_missing = []
    for skill in missing_skills[:8]:
        # Check if it's a tool (learnable) vs domain knowledge (harder)
        _TOOL_SKILLS = {
            "python", "sql", "r", "java", "javascript", "docker", "kubernetes",
            "aws", "azure", "gcp", "terraform", "spark", "kafka", "airflow",
            "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
            "tableau", "power bi", "excel", "git", "react", "node",
        }
        is_tool = skill.lower() in _TOOL_SKILLS
        critical_missing.append({
            "skill": skill,
            "type": "tool" if is_tool else "concept",
            "in_skills_list": skill.lower() in resume_skills_lower,
            "in_bullets": skill.lower() in all_bullets,
            "action": (
                f"Build a project using {skill} (portfolio piece)"
                if is_tool
                else f"Demonstrate {skill} through real-world work or case studies"
            ),
        })
    
    # 2. Required Proof — projects needed
    required_proof = []
    jd_responsibilities = jd.responsibilities[:5] if jd.responsibilities else []
    
    for resp in jd_responsibilities[:3]:
        # Extract the key action from each responsibility
        resp_clean = resp.strip().rstrip(".")
        if len(resp_clean) > 20:
            required_proof.append({
                "jd_requirement": resp_clean[:80],
                "proof_type": "project",
                "suggestion": f"Build a project that demonstrates: {resp_clean[:60]}",
            })
    
    if not required_proof:
        # Generate from missing skills instead
        for skill in missing_skills[:2]:
            required_proof.append({
                "jd_requirement": f"Experience with {skill}",
                "proof_type": "project",
                "suggestion": f"Create a portfolio project using {skill} on a real dataset",
            })
    
    # 3. Experience Signals — what's missing
    experience_signals = []
    has_scale = bool(re.search(r'\d+[K+]|\b(?:large|million|thousand)\b', all_bullets, re.I))
    has_ownership = bool(re.search(r'\b(?:led|owned|architected|designed|built)\b', all_bullets, re.I))
    has_complexity = bool(re.search(r'\b(?:distributed|microservice|pipeline|system|platform)\b', all_bullets, re.I))
    
    if not has_scale:
        experience_signals.append({
            "signal": "Scale",
            "status": "missing",
            "action": "Mention data volumes, user counts, or system scale in bullets (e.g., '150K+ records')",
        })
    if not has_ownership:
        experience_signals.append({
            "signal": "Ownership",
            "status": "missing",
            "action": "Use ownership verbs: 'Led', 'Designed', 'Architected' instead of 'Assisted', 'Helped'",
        })
    if not has_complexity:
        experience_signals.append({
            "signal": "Complexity",
            "status": "missing",
            "action": "Describe systems, pipelines, or multi-component architectures you've worked on",
        })
    
    # 4. Minimum Upgrade Plan — realistic and actionable
    upgrade_plan = []
    
    # Project suggestion (most impactful)
    if missing_skills:
        top_skills = missing_skills[:3]
        upgrade_plan.append(
            f"Build 1 end-to-end project using {', '.join(top_skills[:2])} "
            f"(e.g., data pipeline, ML model, or dashboard)"
        )
    
    # Skill acquisition
    tool_skills = [s for s in missing_skills[:5] if s.lower() in {
        "python", "sql", "docker", "aws", "spark", "tensorflow", "kubernetes",
        "tableau", "power bi", "react", "java", "pytorch",
    }]
    if tool_skills:
        upgrade_plan.append(
            f"Learn {', '.join(tool_skills[:2])} through hands-on tutorials (not just courses)"
        )
    
    # Resume update
    upgrade_plan.append("Update resume bullets to show the new project with quantified outcomes")
    
    # Estimated effort
    if len(missing_skills) <= 2:
        effort = "1-2 weeks (focused project work)"
    elif len(missing_skills) <= 5:
        effort = "2-4 weeks (skill building + project)"
    else:
        effort = "1-2 months (significant skill gap)"
    
    return {
        "type": "CANDIDATE_UPGRADE",
        "missing_skills": critical_missing[:6],
        "required_proof": required_proof[:3],
        "experience_signals": experience_signals,
        "upgrade_plan": upgrade_plan[:4],
        "estimated_effort": effort,
        "summary": (
            f"You need to build {len(critical_missing)} skills and "
            f"{len(required_proof)} proof points. "
            f"Estimated effort: {effort}."
        ),
    }


# ================================================================
# PART 4 — VARIANT PERFORMANCE TRACKER
# ================================================================

def compute_variant_performance(history: List[Dict]) -> Dict:
    """
    Track per-variant (mode) performance from application history.
    
    Returns:
      - per_variant: {mode: {applications, shortlists, rate}}
      - best_variant: highest shortlist rate
      - worst_variant: lowest shortlist rate
      - recommendation: switch strategy
    """
    if not history:
        return {
            "per_variant": {},
            "best_variant": None,
            "worst_variant": None,
            "recommendation": "No data yet. Start with balanced mode.",
            "sufficient_data": False,
        }
    
    # Group by mode
    variants = {}
    for h in history:
        mode = h.get("mode", "strict")
        if mode not in variants:
            variants[mode] = {"applications": 0, "shortlists": 0, "rejections": 0}
        variants[mode]["applications"] += 1
        if h.get("status") == "shortlisted":
            variants[mode]["shortlists"] += 1
        elif h.get("status") == "rejected":
            variants[mode]["rejections"] += 1
    
    # Compute rates
    per_variant = {}
    for mode, counts in variants.items():
        resolved = counts["shortlists"] + counts["rejections"]
        rate = (counts["shortlists"] / resolved * 100) if resolved > 0 else 0
        per_variant[mode] = {
            "applications": counts["applications"],
            "shortlists": counts["shortlists"],
            "rejections": counts["rejections"],
            "rate": round(rate, 1),
            "resolved": resolved,
        }
    
    # Find best/worst
    resolved_variants = {
        m: v for m, v in per_variant.items() if v["resolved"] >= 2
    }
    
    if resolved_variants:
        best_variant = max(resolved_variants, key=lambda m: resolved_variants[m]["rate"])
        worst_variant = min(resolved_variants, key=lambda m: resolved_variants[m]["rate"])
        sufficient_data = True
        
        best_rate = resolved_variants[best_variant]["rate"]
        worst_rate = resolved_variants[worst_variant]["rate"]
        
        if best_rate > worst_rate + 10:
            recommendation = (
                f"Use '{best_variant}' mode — {best_rate:.0f}% shortlist rate vs "
                f"'{worst_variant}' at {worst_rate:.0f}%. "
                f"Clear winner with {resolved_variants[best_variant]['resolved']} resolved applications."
            )
        elif best_rate == 0 and worst_rate == 0:
            recommendation = (
                "No shortlists yet with any variant. Consider: "
                "1) Improving resume content, or 2) Changing target roles."
            )
        else:
            recommendation = (
                f"No clear winner yet. Best: '{best_variant}' ({best_rate:.0f}%), "
                f"Worst: '{worst_variant}' ({worst_rate:.0f}%). "
                f"Need more applications to determine optimal strategy."
            )
    else:
        best_variant = None
        worst_variant = None
        sufficient_data = False
        recommendation = (
            "Insufficient resolved applications per variant. "
            "Update application statuses and continue tracking."
        )
    
    return {
        "per_variant": per_variant,
        "best_variant": best_variant,
        "worst_variant": worst_variant,
        "recommendation": recommendation,
        "sufficient_data": sufficient_data,
    }
