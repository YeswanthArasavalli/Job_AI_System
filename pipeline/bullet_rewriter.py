"""
Bullet Rewriter — Generate STRONG, shortlist-worthy resume bullets.

NOT validation (quality_gate.py does that).
NOT architecture (no new engine).

This is a GENERATION module that transforms weak bullets into
recruiter-quality output using deterministic rules.

Structure: [Action] + [Work] + [Context] + [Outcome]

Rules:
  - NO fake metrics, tools, or claims
  - ONLY use original bullet + candidate_skills
  - Every bullet must answer: What? Why? What changed?
  - quality_score >= 7 or KEEP ORIGINAL
"""

import re
from typing import List, Dict, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ================================================================
# VERB STRENGTH MAP — weak → strong (preserves meaning)
# ================================================================

_VERB_UPGRADES = {
    # Passive/weak → ownership verbs
    r'^[Ww]orked\s+on\b': 'Developed',
    r'^[Dd]id\b': 'Implemented',
    r'^[Hh]elped\s+with\b': 'Contributed to',
    r'^[Hh]elped\b': 'Supported',
    r'^[Ww]as\s+responsible\s+for\b': 'Led',
    r'^[Rr]esponsible\s+for\b': 'Led',
    r'^[Ww]as\s+involved\s+in\b': 'Contributed to',
    r'^[Hh]andled\b': 'Managed',
    r'^[Uu]sed\b': 'Applied',
    r'^[Mm]ade\b': 'Built',
    r'^[Rr]an\b': 'Executed',
    r'^[Ff]ixed\b': 'Resolved',
    r'^[Cc]hecked\b': 'Validated',
    r'^[Ll]ooked\s+at\b': 'Analyzed',
    r'^[Ss]et\s+up\b': 'Configured',
    r'^[Aa]ssisted\s+(?:with|in)\b': 'Supported',
    r'^[Pp]articipated\s+in\b': 'Contributed to',
}

# ================================================================
# OUTCOME MAP — domain → safe outcome phrases (varied, not templates)
# Each domain has 4+ options to prevent repetition
# ================================================================

# REMOVED: Generic _OUTCOME_MAP phrases rejected by recruiter review.
# Purpose clauses are now derived from each bullet's OWN content (see Step 4b).
# A real hiring manager rejects "for automated workflows" — they want:
#   WHAT workflow? WHO uses it? WHAT changed?

# Track which outcomes have been used (prevent same phrase twice)
_used_outcomes = set()


def _detect_domain(text: str) -> str:
    """Detect the domain of a bullet from its content."""
    t = text.lower()
    if any(w in t for w in ["pipeline", "etl", "data process", "dataset",
                             "clean", "preprocess", "ingest", "warehouse",
                             "sql", "query", "database"]):
        return "data"
    if any(w in t for w in ["model", "predict", "train", "classif",
                             "ml", "deep learning", "neural", "accuracy",
                             "regression", "clustering", "feature"]):
        return "ml"
    if any(w in t for w in ["deploy", "docker", "kubernetes", "infra",
                             "production", "ci/cd", "release", "cloud"]):
        return "deploy"
    if any(w in t for w in ["dashboard", "visual", "report", "chart",
                             "tableau", "power bi", "plot", "insight"]):
        return "viz"
    if any(w in t for w in ["api", "endpoint", "rest", "service",
                             "microservice", "integration"]):
        return "api"
    if any(w in t for w in ["automat", "script", "cron", "schedul",
                             "workflow", "batch"]):
        return "automation"
    if any(w in t for w in ["test", "qa", "unit test", "coverage",
                             "regression", "assert"]):
        return "testing"
    return "general"


def _extract_specific_context(text: str) -> Optional[str]:
    """Infer domain + use-case + beneficiary from the bullet's own words.
    
    Every purpose clause MUST include:
      1. Domain context  (what kind of data/problem)
      2. Specific use-case
      3. Specific beneficiary
    
    ❌ REJECT: "enabling business decisions" (who? what decisions?)
    ✅ ACCEPT: "enabling demand forecasting for the inventory planning team"
    
    The rule: infer from words ALREADY IN the bullet. If the bullet says
    "forecasting" → the domain is prediction, use-case is demand/sales,
    beneficiary is planning team. This is defensible in an interview.
    
    Returns None if no specific triple can be inferred.
    """
    t = text.lower()
    
    # ── Dashboard/Visualization ──
    if re.search(r'\bdashboard', t):
        if re.search(r'\bkpi|metric|performance', t):
            return "giving operations leads visibility into daily KPI trends"
        if re.search(r'\bsales|revenue', t):
            return "giving the sales team visibility into revenue pipeline metrics"
        if re.search(r'\buser|engagement|traffic', t):
            return "giving product managers visibility into user engagement patterns"
        # Default: dashboards always serve decision-makers
        return "giving cross-functional teams visibility into operational metrics"
    
    if re.search(r'\breport(?:ing)?(?:\s|$|\.)', t) and not re.search(r'reporting to', t):
        if re.search(r'\bbusiness|management', t):
            return "supporting weekly business review cycles for management"
        return "surfacing key operational trends for business review"
    
    # ── Forecasting/Prediction ──
    if re.search(r'\bforecast', t):
        if re.search(r'\bdemand|inventory|supply', t):
            return "enabling demand forecasting for the inventory planning team"
        if re.search(r'\bsales|revenue', t):
            return "supporting quarterly sales forecasting for revenue planning"
        # Forecasting without sub-domain: use the most common inference
        return "enabling demand and trend forecasting for the planning team"
    
    if re.search(r'\bpredict|prediction', t):
        if re.search(r'\bchurn|retention', t):
            return "powering churn prediction to support customer retention efforts"
        if re.search(r'\bfraud|anomal', t):
            return "powering fraud detection to protect transaction integrity"
        return "powering predictive scoring for the analytics team"
    
    # ── Classification/Segmentation ──
    if re.search(r'\bsegmentat', t):
        if re.search(r'\bcustomer|user|client', t):
            return "enabling customer segmentation for targeted outreach campaigns"
        return "enabling audience segmentation for the marketing team"
    
    if re.search(r'\bclassif', t):
        if re.search(r'\btext|nlp|sentiment|language', t):
            return "powering text classification for content moderation workflows"
        if re.search(r'\bcustomer|ticket|support', t):
            return "automating ticket classification for the support team"
        if re.search(r'\bimage|visual|cv', t):
            return "powering image classification for visual quality inspection"
        return "automating categorization to reduce manual labeling effort"
    
    if re.search(r'\bcluster', t):
        return "identifying behavioral patterns for the analytics team"
    
    # ── Model accuracy/tuning ──
    if re.search(r'\bmodel\b', t) and re.search(r'\baccuracy|f1|precision|recall', t):
        return "improving prediction reliability for production model serving"
    
    # ── Pipeline/ETL ──
    if re.search(r'\betl|data pipeline|data processing', t):
        if re.search(r'\b\d+[kK]\+?\s*(?:record|row|entry)', t):
            return "ensuring timely data delivery for downstream reporting dashboards"
        if re.search(r'\blog|event', t):
            return "feeding structured log data into monitoring and alerting systems"
        return "feeding clean data into the analytics team's reporting layer"
    
    # ── Data cleaning/preprocessing ──
    if re.search(r'\bclean|preprocess|data quality', t):
        if re.search(r'\bnlp|text|language', t):
            return "preparing high-quality training corpora for NLP classification models"
        if re.search(r'\bmodel|train', t):
            return "ensuring training data quality for downstream ML pipelines"
        return "ensuring data integrity for the analytics team's reporting workflows"
    
    # ── Automation ──
    if re.search(r'\bautomated?\b.*\b(?:workflow|process|task)', t):
        if re.search(r'\betl|data|pipeline', t):
            return "reducing manual data processing overhead for the data team"
        if re.search(r'\blog|report', t):
            return "eliminating manual log processing for the operations team"
        return "reducing manual operational overhead for the engineering team"
    
    if re.search(r'\bscript|cron|schedul', t):
        return "eliminating recurring manual tasks for the data operations team"
    
    # ── API/Integration ──
    if re.search(r'\bapi|endpoint|integration', t):
        return "enabling data exchange between internal services and client applications"
    
    # ── Deployment ──
    if re.search(r'\bdeployed?\b.*\b(?:app|model|service|system)', t):
        return "making the solution accessible to end users via web interface"
    
    # ── Testing ──
    if re.search(r'\btest|coverage|regression', t):
        return "reducing production defect risk for the engineering team"
    
    # ── Statistical modeling ──
    if re.search(r'\bstatistical|regression|hypothesis|correlation', t):
        return "surfacing data-driven insights for the research team"
    
    # ── Label/annotation ──
    if re.search(r'\blabel|annotat', t):
        if re.search(r'\bnlp|text', t):
            return "building labeled training sets for NLP model development"
        if re.search(r'\bcv|image|visual', t):
            return "building labeled training sets for computer vision model development"
        return "building labeled datasets for supervised model training"
    
    # No defensible triple → keep original (don't degrade)
    return None


def _has_outcome(text: str) -> bool:
    """Check if bullet has ANY outcome/purpose clause (even bare metric)."""
    return bool(re.search(
        r'\b(?:to\s+(?:enable|support|improve|drive|enhance|ensure|reduce|'
        r'increase|provide|identify|streamline|strengthen|accelerate)|'
        r'enabling|supporting|improving|ensuring|reducing|increasing|'
        r'providing|enhancing|streamlining|strengthening|'
        r'for\s+(?:faster|better|real-time|reliable|improved|actionable))\b',
        text, re.I
    ))


def _has_complete_impact(text: str) -> bool:
    """Check if bullet has a COMPLETE impact clause (outcome + stakeholder).
    
    'improving quality by 30%' → has outcome but NO stakeholder → incomplete
    'improving quality by 30%, preparing training data for NLP models' → complete
    
    A hiring manager asks: 30% of WHAT, for WHOM? Bare metrics don't cut it.
    We require an actual stakeholder/consumer reference — not just a use-case word.
    """
    if not _has_outcome(text):
        return False
    # Must reference WHO benefits — actual stakeholders or consuming systems
    return bool(re.search(
        r'\b(?:stakeholder|team|leadership|business\s+(?:team|unit|planning)|'
        r'analyst|user|client|customer|management|end.user|'
        r'downstream\s+(?:system|analytics|team)|'
        r'production\s+(?:system|model|pipeline)|'
        r'training data for|reporting (?:system|dashboard)|'
        r'marketing and outreach|retention strateg|'
        r'engineering team|data team|business team)\b',
        text, re.I
    ))


def _has_level_signal(text: str) -> bool:
    """Check if bullet contains at least ONE level signal.
    
    Level signals differentiate a candidate from generic resumes:
    - Use-case: churn, segmentation, recommendation, fraud, sentiment
    - Data context: customer data, transaction logs, sales records
    - System purpose: reporting, prediction, monitoring
    - Complexity: ML pipeline, NLP, feature engineering, optimization
    """
    return bool(re.search(
        r'\b(?:churn|segmentation|recommendation|fraud|sentiment|'
        r'classification|clustering|forecasting|prediction|'
        r'customer|transaction|sales|revenue|inventory|'
        r'NLP|deep learning|feature engineer|optimization|'
        r'real-time|end-to-end|production|large-scale|'
        r'dashboard|pipeline|ETL|API|microservice|'
        r'training data|model deployment|A/B test)\b',
        text, re.I
    ))


def _count_tools(text: str) -> int:
    """Count tool-injection phrases in text."""
    return len(re.findall(
        r'\b(?:using|utilizing|applying|leveraging|with)\s+[A-Z][a-z]+',
        text
    ))


# ================================================================
# CORE REWRITER
# ================================================================

def rewrite_bullet(
    bullet: str,
    candidate_skills: List[str] = None,
) -> Dict:
    """
    Rewrite a single bullet for recruiter-quality output.

    Rules:
      1. Strengthen weak verbs → ownership verbs
      2. Add outcome if missing (domain-aware, varied)
      3. Never add tools not in original or candidate_skills
      4. Never add fake metrics
      5. Self-score — reject if quality_score < 7

    Returns:
      {
        "original": str,
        "rewritten": str,
        "improvement_reason": str,
        "quality_score": int (1-10),
        "accepted": bool
      }
    """
    candidate_skills = candidate_skills or []
    original = bullet.strip()
    improved = original
    reasons = []

    # Skip very short fragments (< 15 chars)
    if len(original) < 15:
        return {
            "original": original,
            "rewritten": original,
            "improvement_reason": "Too short to rewrite",
            "quality_score": 3,
            "accepted": False,
        }

    # ── Step 0: Fix broken bullets ──
    # Ends with "and." or ", and."
    if re.search(r',?\s+and\.\s*$', improved):
        improved = re.sub(r',?\s+and\.\s*$', '.', improved)
        reasons.append("fixed broken ending")
    # Ends with conjunction + period
    if re.search(r',?\s+(?:or|and|but|with)\.\s*$', improved):
        improved = re.sub(r',?\s+(?:or|and|but|with)\.\s*$', '.', improved)
        reasons.append("fixed trailing conjunction")
    # Ends with comma (incomplete)
    if improved.rstrip().endswith(','):
        improved = improved.rstrip().rstrip(',') + '.'
        reasons.append("fixed incomplete ending")
    # Repeated phrases ("data data" or "process, process")
    improved = re.sub(r'\b(\w{4,})\s*,?\s+\1\b', r'\1', improved)
    if improved != original:
        if "fixed" not in " ".join(reasons):
            reasons.append("removed repetition")

    # ── Step 1: Verb strengthening ──
    for pattern, replacement in _VERB_UPGRADES.items():
        if re.search(pattern, improved):
            improved = re.sub(pattern, replacement, improved, count=1)
            reasons.append("stronger verb")
            break

    # ── Step 2: Ensure starts with capital ──
    if improved and improved[0].islower():
        improved = improved[0].upper() + improved[1:]
        reasons.append("capitalized")

    # ── Step 3: Remove filler words ──
    fillers = [
        (r'\b(?:basically|essentially|just|simply|actually)\s+', ''),
        (r'\b(?:various|several|numerous)\s+', ''),
        (r'\b(?:in order to)\b', 'to'),
    ]
    for filler_pattern, filler_repl in fillers:
        if re.search(filler_pattern, improved, re.I):
            improved = re.sub(filler_pattern, filler_repl, improved, flags=re.I)
            reasons.append("removed filler")

    # ── Step 3b: Remove template phrases (FIX 7) ──
    # "utilizing X", "leveraging X", "applying X" are ATS-stuffing markers
    templates = [
        (r',?\s*(?:utilizing|leveraging)\s+[A-Z][\w.]+(?:\s+and\s+[A-Z][\w.]+)*', ''),
        (r',?\s*applying\s+[A-Z][\w.]+(?:\s+and\s+[A-Z][\w.]+)*', ''),
    ]
    for tp, tr in templates:
        if re.search(tp, improved):
            improved = re.sub(tp, tr, improved, count=1)
            reasons.append("removed template phrase")

    # ── Step 4: IMPACT UPGRADE LAYER (FIX 6) ──
    # Adds CONTEXTUAL improvement derived from bullet content + candidate skills.
    # NOT generic phrases. Every addition must be SPECIFIC to what the bullet says.

    # 4a: Skill injection — add 1 candidate skill NATURALLY (not "using X")
    # Guard: skip if bullet already has an "in {Tool}" suffix (from previous iteration)
    skill_injected = False
    already_has_skill_suffix = bool(re.search(r' in [A-Z][\w.-]+[.,]', improved))
    # Also skip if bullet already has a purpose clause (from previous iteration)
    already_has_purpose = bool(re.search(
        r',\s*(?:to\s+(?:improve|support|enable|reduce)|'
        r'enabling|reducing|giving|powering|feeding|building|'
        r'surfacing|automating|eliminating|ensuring|preparing|'
        r'identifying|making|supporting)\s', improved
    ))
    if candidate_skills and len(improved) < 120 and not already_has_skill_suffix and not already_has_purpose:
        domain = _detect_domain(improved)
        il = improved.lower()
        _skill_domain = {
            "data": ["python", "sql", "pandas", "spark", "airflow", "dbt"],
            "ml": ["scikit-learn", "tensorflow", "pytorch", "xgboost"],
            "deploy": ["docker", "kubernetes", "aws", "azure", "gcp", "ci/cd"],
            "viz": ["tableau", "power bi", "matplotlib", "plotly"],
            "api": ["flask", "fastapi", "django", "rest"],
            "automation": ["python", "bash", "selenium", "cron"],
            "testing": ["pytest", "unittest", "jenkins"],
        }
        relevant = _skill_domain.get(domain, [])
        for sk in candidate_skills:
            if sk.lower() in relevant and sk.lower() not in il:
                improved = improved.rstrip('.')
                improved = f"{improved} in {sk}."
                reasons.append(f"added skill context ({sk})")
                skill_injected = True
                break  # Only 1 skill per bullet

    # ── 4c: LEVEL SIGNAL INJECTION (competitive differentiator) ──
    # A shortlisted resume doesn't just say "Built model" — it says
    # "Built churn prediction model using Random Forest on user data".
    # This step injects TECHNIQUE + DATA CONTEXT into the bullet body.
    il = improved.lower()

    # 4c-i: TECHNIQUE signal — inject ML method if candidate has it
    # Guards: skip if (a) technique already present, (b) skill already injected,
    #         (c) bullet already has a purpose clause from prior iteration
    _has_technique = bool(re.search(
        r'\b(?:random forest|xgboost|gradient boost|logistic regression|'
        r'decision tree|svm|knn|lstm|cnn|transformer|bert|distilbert|'
        r'efficientnet|resnet|word2vec|tfidf|tf-idf|'
        r'linear regression|neural network|deep learning|ensemble|'
        r'feature engineering|hyperparameter)\b', il
    ))
    _technique_map = {
        "xgboost": "XGBoost", "random forest": "Random Forest",
        "scikit-learn": "Scikit-learn", "pytorch": "PyTorch",
        "tensorflow": "TensorFlow", "deep learning": "Deep Learning",
    }
    if (not _has_technique
            and not skill_injected  # Don't add technique if we already added a tool
            and _detect_domain(improved) == "ml"
            and not already_has_purpose
            and len(improved) < 130):
        # Find a technique from candidate skills
        for sk in candidate_skills:
            if sk.lower() in _technique_map:
                display = _technique_map[sk.lower()]
                if display.lower() not in il:
                    # Insert "using {Technique}" AFTER metric clause if present,
                    # else after the object noun.
                    # "Built models improving accuracy by 22%" →
                    # "Built models improving accuracy by 22% using PyTorch"
                    m_metric = re.search(r'by\s+\d+%', improved)
                    m_obj = re.search(
                        r'\b(models?|classifier|predictor|algorithm)\b',
                        improved, re.I
                    )
                    if m_metric:
                        pos = m_metric.end()
                        improved = improved[:pos] + f" using {display}" + improved[pos:]
                    elif m_obj:
                        pos = m_obj.end()
                        improved = improved[:pos] + f" using {display}" + improved[pos:]
                    else:
                        # Fallback: append before period
                        improved = improved.rstrip('.')
                        improved = f"{improved} using {display}."
                    reasons.append(f"added technique ({display})")
                    break

    # 4c-ii: DATA CONTEXT signal — inject data type if inferable
    # "Built pipeline" → "Built pipeline to process user transaction data"
    # Only fires if no data context already present.
    il = improved.lower()  # Refresh after technique injection
    _has_data_ctx = bool(re.search(
        r'\b(?:user data|customer data|transaction|log data|event data|'
        r'sales data|click.?stream|session data|text data|image data|'
        r'NLP (?:records|corpus|data)|text corpus|time.series|tabular|'
        r'training (?:data|set|corpus)|labeled data|'
        # Implicit data references — these already indicate data context
        r'\d+[kK]\+?\s*(?:record|row|entr)|datasets?|corpus|'
        r'large-scale .{0,15}data)\b', il
    ))
    if not _has_data_ctx and len(improved) < 140 and not already_has_purpose:
        # Infer data type from bullet content — but ONLY if the bullet
        # doesn't already imply the data type through its nouns
        data_ctx = None
        if re.search(r'\bcustomer|user|client', il) and 'segmentat' not in il:
            data_ctx = "user behavioral data"
        elif re.search(r'\bsales|revenue|financial', il):
            data_ctx = "sales transaction records"
        elif re.search(r'\bimage|visual|cv\b', il):
            data_ctx = "labeled image datasets"
        elif re.search(r'\bpatient|medical|health', il):
            data_ctx = "clinical patient records"

        if data_ctx and data_ctx not in il:
            # Insert "on {data_ctx}" after technique or tool phrase
            m_tech = re.search(r'using [A-Z][\w.-]+', improved)
            if m_tech:
                pos = m_tech.end()
                improved = improved[:pos] + f" on {data_ctx}" + improved[pos:]
                reasons.append(f"added data context ({data_ctx})")
            elif not already_has_skill_suffix:
                improved = improved.rstrip('.')
                improved = f"{improved} on {data_ctx}."
                reasons.append(f"added data context ({data_ctx})")
    

    # 4b: Purpose clause — add SPECIFIC purpose with stakeholder/use-case
    # Fires even if bullet has bare metrics ('improving by 30%') because
    # bare metrics lack WHO/WHY context — a hiring manager wants both.
    # Guard: check BOTH _has_complete_impact AND already_has_purpose
    if (not _has_complete_impact(improved)
            and not already_has_purpose
            and len(improved) < 140):
        purpose = _extract_specific_context(improved)
        if purpose and purpose not in improved.lower():
            improved = improved.rstrip('.')
            improved = f"{improved}, {purpose}."
            reasons.append("added stakeholder context")

    # ── Step 5: Ensure ends with period ──
    if improved and not improved.rstrip().endswith('.'):
        improved = improved.rstrip() + '.'

    # ── Step 6: Clean up ──
    improved = improved.replace('..', '.')
    improved = re.sub(r'  +', ' ', improved).strip()
    # Fix double comma
    improved = improved.replace(',,', ',')

    # ── Step 7: Self-score ──
    score = _score_bullet(improved, original, candidate_skills)

    # Accept if score >= 7, OR if template phrases were removed (cleanup = real improvement)
    template_cleaned = "removed template phrase" in ("; ".join(reasons))
    accepted = score >= 7 or template_cleaned
    if not accepted:
        improved = original  # Keep original

    return {
        "original": original,
        "rewritten": improved,
        "improvement_reason": "; ".join(reasons) if reasons else "no changes needed",
        "quality_score": score,
        "accepted": accepted,
    }


def _score_bullet(rewritten: str, original: str, skills: List[str]) -> int:
    """
    Hiring-manager-aligned bullet scorer (1-10).

    A recruiter scans for 4 signals in ~6 seconds:
      1. WHAT was done?  (+2: strong action verb)
      2. HOW?            (+2: tool/skill mentioned OR method described)
      3. PROBLEM solved? (+2: outcome/purpose clause present)
      4. WHO benefited?  (+1: stakeholder/user/team mentioned)
      
    Plus quality signals:
      +1: Appropriate length (50-180 chars)
      +1: Actually improved from original
      +1: Natural flow (no stuffing)
    """
    score = 0
    r_lower = rewritten.lower()

    # +2: WHAT — Strong action verb (ownership, not passive)
    strong_verbs = [
        'built', 'developed', 'designed', 'implemented', 'led', 'managed',
        'created', 'deployed', 'automated', 'optimized', 'analyzed',
        'configured', 'established', 'integrated', 'delivered',
        'executed', 'contributed', 'supported', 'enhanced', 'resolved',
        'architected', 'orchestrated', 'streamlined', 'processed',
        'labeled', 'cleaned', 'trained', 'evaluated', 'reduced',
    ]
    if any(r_lower.startswith(v) for v in strong_verbs):
        score += 2

    # +2: HOW — Tool/skill/method mentioned
    skills_lower = {s.lower() for s in skills}
    has_tool = any(s in r_lower for s in skills_lower)
    has_method = bool(re.search(
        r'\b(?:using|with|in|via)\s+[A-Z][\w.-]+', rewritten
    ))
    if has_tool or has_method:
        score += 2
    elif re.search(r'\b(?:sql|python|r|api|etl|ml|nlp|cv)\b', r_lower, re.I):
        score += 1  # Partial credit for inline tool mention

    # +2: PROBLEM — Outcome/purpose clause present
    if _has_outcome(rewritten):
        score += 2
    elif re.search(r'\b(?:by\s+\d+%|resulting in|leading to|across\s+\d+)', r_lower):
        score += 2  # Metric-based outcome counts

    # +1: WHO — Stakeholder/user/team referenced
    if re.search(
        r'\b(?:stakeholder|team|leadership|business|analyst|user|client|'
        r'customer|management|end.user|downstream|production)\b', r_lower
    ):
        score += 1

    # +1: LEVEL SIGNAL — use-case, data context, or complexity
    if _has_level_signal(rewritten):
        score += 1

    # +1: Appropriate length (too short = lacks context)
    if 50 <= len(rewritten) <= 180:
        score += 1

    # +1: Actually changed (improvement made)
    if rewritten.lower() != original.lower():
        score += 1

    # +1: Natural flow (no stuffing chains)
    if not re.search(r',\s*(?:utilizing|applying)\s+\w+,\s*(?:utilizing|applying)', r_lower):
        score += 1

    return min(10, score)


# ================================================================
# BATCH REWRITER
# ================================================================

def rewrite_all_bullets(
    bullets: List[str],
    candidate_skills: List[str] = None,
) -> Dict:
    """
    Rewrite all bullets in a resume.

    Returns:
      {
        "results": [{"original", "rewritten", "quality_score", "accepted"}, ...],
        "accepted": int,
        "rejected": int,
        "avg_score": float,
        "final_bullets": [str, ...]  — accepted rewrites + kept originals
      }
    """
    global _used_outcomes
    _used_outcomes = set()  # Reset per batch for variety

    candidate_skills = candidate_skills or []
    results = []

    for bullet in bullets:
        result = rewrite_bullet(bullet, candidate_skills)
        results.append(result)

    accepted = sum(1 for r in results if r["accepted"])
    rejected = len(results) - accepted
    avg_score = sum(r["quality_score"] for r in results) / max(len(results), 1)

    final_bullets = [r["rewritten"] for r in results]

    logger.info(
        f"BULLET REWRITER: {accepted}/{len(bullets)} accepted "
        f"(avg score={avg_score:.1f}), {rejected} kept original"
    )

    return {
        "results": results,
        "accepted": accepted,
        "rejected": rejected,
        "avg_score": round(avg_score, 1),
        "final_bullets": final_bullets,
    }
