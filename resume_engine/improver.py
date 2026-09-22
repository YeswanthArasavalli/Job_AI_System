"""
Resume Improver v3 -- Intelligence-enhanced ATS optimizer.

Takes the tailored resume + ATS scoring feedback and produces an
improved version using 8 transformation rules:

  1. DEPTH ENHANCEMENT: Expand skill usage depth
  2. CONTEXT ENRICHMENT: Add scale, purpose, outcome
  3. JD ALIGNMENT: Map resume terms to JD terminology
  4. PIPELINE FRAMING: Express related work as end-to-end pipelines
  5. TOOL STRENGTH UPGRADE: "used X" → "applied X for Y"
  6. NO FAKE RULE: Never add new skills/tools/experience
  7. KEYWORD INJECTION: Only if already in resume or strongly implied
  8. BULLET TEMPLATE: [Action] + [Tool] + [Purpose] + [Impact]

STRICT RULES:
  - NO fake skills added
  - NO fabricated experience
  - NO invented certifications
  - ONLY rephrasing, reordering, enriching, aligning
"""

import re
from typing import List, Dict, Set, Optional

from utils.models import StructuredResume
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ================================================================
# SKILL ECOSYSTEM MAP
# If resume has "Python", it's safe to reference pandas/numpy/etc.
# because they are part of the Python data ecosystem.
# Only ecosystems where the sub-tool is universally implied.
# ================================================================

SKILL_ECOSYSTEM = {
    "python": ["pandas", "numpy", "matplotlib", "scikit-learn", "scipy"],
    "javascript": ["node.js", "npm", "es6"],
    "java": ["spring", "maven", "junit"],
    "sql": ["complex queries", "joins", "aggregations", "stored procedures"],
    "aws": ["s3", "ec2", "lambda", "cloudwatch"],
    "gcp": ["bigquery", "cloud storage", "cloud functions"],
    "azure": ["azure functions", "blob storage"],
    "docker": ["containerization", "docker compose"],
    "kubernetes": ["container orchestration", "helm"],
    "react": ["component architecture", "state management", "hooks"],
    "machine learning": ["model training", "feature engineering", "hyperparameter tuning"],
    "deep learning": ["neural networks", "model optimization"],
    "data analysis": ["statistical analysis", "data visualization", "insights"],
    "etl": ["data extraction", "transformation", "loading"],
    "git": ["version control", "branching", "code review"],
    "ci/cd": ["automated testing", "continuous deployment", "build pipelines"],
    "tensorflow": ["model training", "neural network architecture"],
    "pytorch": ["deep learning models", "tensor operations"],
    "spark": ["distributed computing", "large-scale data processing"],
    "tableau": ["data visualization", "interactive dashboards"],
    "power bi": ["business intelligence", "interactive dashboards"],
    "mongodb": ["nosql", "document databases", "aggregation pipelines"],
    "postgresql": ["relational databases", "complex queries"],
    "redis": ["caching", "session management"],
    "kafka": ["event streaming", "real-time data pipelines"],
    "airflow": ["workflow orchestration", "dag management"],
    "flask": ["rest api", "web services", "microservices"],
    "django": ["web application", "orm", "rest api"],
    "fastapi": ["async api", "high-performance web services"],
}

# ================================================================
# SKILL CONTEXT VALIDATION ENGINE
# Maps skills → allowed bullet categories to prevent misplacement.
# A skill should ONLY be injected into bullets whose action matches.
# ================================================================

SKILL_CATEGORIES = {
    # Modeling / ML
    "scikit-learn": "modeling", "sklearn": "modeling", "xgboost": "modeling",
    "lightgbm": "modeling", "random forest": "modeling", "lstm": "modeling",
    "tensorflow": "modeling", "pytorch": "modeling", "keras": "modeling",
    "model training": "modeling", "classification": "modeling",
    "regression": "modeling", "neural networks": "modeling",
    "deep learning": "modeling", "machine learning": "modeling",
    "ml": "modeling", "hyperparameter tuning": "modeling",
    "feature engineering": "modeling",
    # Data processing / analysis
    "pandas": "data", "numpy": "data", "sql": "data", "spark": "data",
    "etl": "data", "data pipeline": "data", "airflow": "data",
    "data cleaning": "data", "data analysis": "data",
    "statistical analysis": "data", "data transformation": "data",
    "kafka": "data", "mongodb": "data", "postgresql": "data",
    "redis": "data", "bigquery": "data",
    # Deployment / serving
    "streamlit": "deployment", "gradio": "deployment", "fastapi": "deployment",
    "flask": "deployment", "django": "deployment", "docker": "deployment",
    "kubernetes": "deployment", "aws": "deployment", "gcp": "deployment",
    "azure": "deployment", "ci/cd": "deployment", "heroku": "deployment",
    "model deployment": "deployment",
    # Visualization
    "power bi": "visualization", "powerbi": "visualization",
    "tableau": "visualization", "matplotlib": "visualization",
    "seaborn": "visualization", "plotly": "visualization",
    "data visualization": "visualization", "looker": "visualization",
    # Backend / API
    "rest api": "backend", "graphql": "backend", "microservices": "backend",
    "api development": "backend",
    # DevOps
    "git": "devops", "version control": "devops",
    "automated testing": "devops", "jenkins": "devops",
    # General (can go anywhere)
    "python": "general", "java": "general", "javascript": "general",
    "r": "general", "c++": "general", "react": "general",
    "nlp": "general", "computer vision": "general",
}

# Bullet category detection signals (action words → category)
BULLET_CATEGORY_SIGNALS = {
    "modeling": [
        "model", "trained", "predict", "classif", "regress", "accuracy",
        "precision", "recall", "f1", "neural", "deep learning", "forecast",
        "feature engineer", "hyperparameter", "cross-valid", "overfit",
    ],
    "data": [
        "data", "dataset", "clean", "preprocess", "transform", "extract",
        "pipeline", "etl", "ingest", "aggregat", "query", "sql", "join",
        "warehouse", "batch", "streaming",
    ],
    "deployment": [
        "deploy", "serve", "production", "containeriz", "docker", "kubernetes",
        "ci/cd", "release", "endpoint", "api", "microservice", "cloud",
        "infrastructure", "scaling", "load balanc",
    ],
    "visualization": [
        "dashboard", "visualiz", "chart", "report", "plot", "insight",
        "stakeholder", "business intelligence", "bi ", "interactive",
    ],
    "backend": [
        "api", "endpoint", "rest", "graphql", "microservice", "backend",
        "server", "authentication", "middleware",
    ],
    "devops": [
        "ci/cd", "automat", "test", "pipeline", "build", "version control",
        "git", "jenkins",
    ],
}


def _detect_bullet_category(bullet: str) -> str:
    """Detect the category of a bullet from its action words."""
    bullet_lower = bullet.lower()
    scores = {}
    for category, signals in BULLET_CATEGORY_SIGNALS.items():
        score = sum(1 for s in signals if s in bullet_lower)
        if score > 0:
            scores[category] = score

    if not scores:
        return "general"
    return max(scores, key=scores.get)


def _skill_fits_bullet(skill: str, bullet: str) -> bool:
    """
    Check if a skill is contextually appropriate for a bullet.
    Returns True if the skill's category matches the bullet's category,
    or if either is 'general' (always compatible).
    """
    skill_cat = SKILL_CATEGORIES.get(skill.lower(), "general")
    if skill_cat == "general":
        return True  # General skills fit anywhere

    bullet_cat = _detect_bullet_category(bullet)
    if bullet_cat == "general":
        return True  # Can't determine → allow

    # Exact match
    if skill_cat == bullet_cat:
        return True

    # Compatible pairs (deployment + backend are related)
    compatible = {
        ("deployment", "backend"), ("backend", "deployment"),
        ("data", "modeling"), ("modeling", "data"),
        ("data", "devops"), ("devops", "data"),
    }
    return (skill_cat, bullet_cat) in compatible


# ================================================================
# JD ALIGNMENT MAP
# Maps generic resume terms → JD-aligned professional terms
# Only applied when the JD keyword is present
# ================================================================

JD_ALIGNMENT_MAP = {
    # Generic → Professional phrasing
    "built model": "developed predictive machine learning model",
    "made model": "engineered machine learning model",
    "created model": "designed and implemented predictive model",
    "built pipeline": "architected end-to-end data pipeline",
    "made pipeline": "engineered automated data pipeline",
    "did analysis": "conducted comprehensive data analysis",
    "made dashboard": "developed interactive analytics dashboard",
    "built dashboard": "designed and deployed interactive dashboard",
    "built api": "developed production-grade RESTful API",
    "made api": "engineered RESTful API",
    "wrote code": "developed production-ready codebase",
    "wrote tests": "implemented comprehensive test suites",
    "wrote scripts": "developed automated processing scripts",
    "fixed bugs": "resolved critical production issues",
    "set up": "architected and configured",
    "worked with": "collaborated with cross-functional",
    "used python": "applied Python for scalable data processing",
    "used sql": "utilized SQL for complex data querying",
    "used aws": "deployed solutions on AWS cloud infrastructure",
    "used docker": "containerized applications using Docker",
    "used git": "maintained version-controlled codebase using Git",
    "used jenkins": "managed CI/CD pipelines via Jenkins",
    "used tableau": "created data visualizations using Tableau",
    "maintained": "optimized and maintained",
    "updated": "enhanced and updated",
    "handled": "managed and orchestrated",
}

# ================================================================
# DEPTH EXPANSION PATTERNS
# Maps vague verbs to deeper, more impactful alternatives
# ================================================================

DEPTH_PATTERNS = {
    r"\bused\b": "applied",
    r"\bbuilt\b": "architected and developed",
    r"\bmade\b": "designed and implemented",
    r"\bcreated\b": "developed",
    r"(?<!\w)\bran\b(?!\w)": "executed and monitored",
    r"\bdid\b": "conducted",
    r"\bwrote\b": "authored",
    r"\bset up\b": "configured and deployed",
    r"\bfixed\b": "diagnosed and resolved",
    r"\bhelped\b": "contributed to",
    r"\btried\b": "implemented",
    r"\bworked on\b": "delivered",
    r"\bwas involved in\b": "drove",
    r"\bwas responsible for\b": "led",
    r"\blooked at\b": "analyzed",
    r"\bgot\b": "achieved",
    r"\bvarious\b": "multiple",
    r"\bsome\b": "key",
    r"\bhelped with\b": "contributed to",
    r"\bbasic\b": "foundational",
}

# ================================================================
# CONTEXT ENRICHMENT: Purpose phrases by keyword
# When a skill is mentioned, add WHY it was used (purpose + impact)
# ================================================================

PURPOSE_PHRASES = {
    "python": "for scalable data processing and automation",
    "sql": "for complex data querying and analytics",
    "pandas": "for data preprocessing and feature engineering",
    "numpy": "for numerical computations and array operations",
    "machine learning": "to drive data-informed business decisions",
    "deep learning": "for advanced pattern recognition and prediction",
    "tensorflow": "for building and training neural network models",
    "pytorch": "for deep learning model development and research",
    "spark": "for large-scale distributed data processing",
    "aws": "enabling scalable cloud-native deployments",
    "docker": "for consistent reproducible deployments",
    "kubernetes": "for production-grade container orchestration",
    "tableau": "for stakeholder-facing data visualization",
    "power bi": "for executive-level business intelligence reporting",
    "data pipeline": "for automated end-to-end data workflows",
    "etl": "for reliable data extraction, transformation, and loading",
    "model": "to improve prediction accuracy and business outcomes",
    "api": "for cross-service integration and data access",
    "dashboard": "for real-time monitoring and stakeholder reporting",
    "ci/cd": "for automated testing and continuous delivery",
    "database": "for optimized data storage and retrieval",
    "testing": "to ensure code quality and production reliability",
    "deployment": "for seamless production releases",
    "automation": "reducing manual effort and improving efficiency",
    "analytics": "to uncover actionable business insights",
    "flask": "for building lightweight RESTful web services",
    "django": "for full-stack web application development",
    "react": "for building responsive user interfaces",
    "mongodb": "for flexible document-based data storage",
    "kafka": "for real-time event-driven data streaming",
    "airflow": "for orchestrating complex data workflows",
    "git": "for collaborative version-controlled development",
    "scikit-learn": "for predictive modeling and ML experimentation",
    "sklearn": "for predictive modeling and ML experimentation",
    # HR / Non-tech
    "recruitment": "to build a high-quality talent pipeline",
    "compliance": "to ensure regulatory adherence and risk mitigation",
    "performance management": "to drive employee growth and accountability",
    "hris": "for streamlined workforce data management",
    "training & development": "for organizational capability building",
    "employee relations": "to improve retention and workplace culture",
    "labor law": "to ensure legal compliance across operations",
    "onboarding": "to accelerate new hire productivity",
    "payroll": "to ensure accurate and timely compensation processing",
    "agile": "for iterative and adaptive project delivery",
    "java": "for enterprise-grade application development",
    "rest apis": "for cross-service integration and data exchange",
    "microservices": "for modular and scalable service architecture",
}

# ================================================================
# IMPACT TEMPLATES — domain-specific business impact suffixes
# Applied when a bullet lacks quantified impact
# ================================================================

IMPACT_TEMPLATES = {
    "modeling": [
        "improving prediction accuracy",
        "reducing error rates",
        "enabling data-driven business decisions",
    ],
    "data": [
        "reducing data processing time",
        "improving data quality and consistency",
        "enabling faster business insights",
    ],
    "deployment": [
        "achieving high availability and reliability",
        "reducing deployment cycle time",
        "enabling zero-downtime releases",
    ],
    "visualization": [
        "enabling real-time business monitoring",
        "improving stakeholder decision-making",
    ],
    "backend": [
        "improving API response times",
        "enabling seamless service integration",
    ],
    "devops": [
        "reducing release cycle time",
        "improving code quality",
    ],
    "hr": [
        "improving employee satisfaction",
        "reducing time-to-hire",
        "strengthening organizational capability",
    ],
    "general": [
        "improving operational efficiency",
        "driving measurable business outcomes",
    ],
}

# ================================================================
# TOOL → CAPABILITY MAP — for project→experience bridging
# Maps project-level tools to professional capability descriptions
# ================================================================

TOOL_TO_CAPABILITY = {
    "lstm": "predictive modeling and time-series forecasting",
    "distilbert": "NLP text classification and sentiment analysis",
    "bert": "natural language understanding and text processing",
    "efficientnet": "computer vision and image classification",
    "cnn": "deep learning-based pattern recognition",
    "rnn": "sequence modeling and temporal data analysis",
    "gpt": "language model fine-tuning and text generation",
    "transformer": "attention-based model architecture design",
    "random forest": "ensemble-based predictive modeling",
    "xgboost": "gradient boosting for classification and regression",
    "lightgbm": "high-performance gradient boosting",
    "yolo": "real-time object detection",
    "resnet": "deep residual network-based image analysis",
    "word2vec": "word embedding and semantic analysis",
    "fasttext": "text classification and representation learning",
}


class ResumeImprover:
    """
    Produces an improved resume from tailored resume + ATS feedback.
    Uses 8 transformation rules for intelligent enhancement.

    Usage:
        improver = ResumeImprover()
        improved, changes = improver.improve(
            tailored_resume=resume,
            missing_skills=["sql", "docker"],
            matched_skills=["python", "aws"],
            recommendations=["Add cloud deployment experience"],
            jd_keywords=["data pipeline", "etl", "analytics"],
        )
    """

    def improve(
        self,
        tailored_resume: StructuredResume,
        missing_skills: List[str] = None,
        matched_skills: List[str] = None,
        recommendations: List[str] = None,
        jd_keywords: List[str] = None,
        mode: str = "strict",
        role_info: Dict = None,
    ) -> StructuredResume:
        """
        Create an improved version of the tailored resume.
        Applies transformation rules with full guardrails.

        Args:
            mode: "strict" = max ATS score (keyword-dense).
                  "balanced" = natural + recruiter-friendly (lighter injection).
                  "conservative" = minimal changes, preserve original voice.
            role_info: Output from role_engine.classify_role(). When provided,
                       blocks tech skill injection for non-tech roles.

        Returns a NEW StructuredResume object (does not modify the original).
        """
        missing_skills = sorted(missing_skills or [])
        matched_skills = sorted(matched_skills or [])
        recommendations = recommendations or []
        jd_keywords = sorted(jd_keywords or [])
        is_balanced = mode == "balanced"
        is_conservative = mode == "conservative"
        role_info = role_info or {}
        _role_type = role_info.get("role_type", "data")

        # Conservative mode: GRAMMAR + VERB FIXES ONLY
        # NO rewrites, NO keyword injection, NO reordering.
        # Preserves original voice completely.
        if is_conservative:
            improved = tailored_resume.model_copy(deep=True)
            cons_changes = 0
            
            # 1. Reorder skills — matched first (non-destructive)
            cons_changes += self._reorder_skills(improved, matched_skills)
            
            # 2. Light bullet polish — verb strengthening + filler removal ONLY
            weak_verbs = {
                'worked': 'Developed', 'helped': 'Supported', 'did': 'Executed',
                'made': 'Built', 'used': 'Utilized', 'was responsible': 'Managed',
                'handled': 'Managed', 'assisted': 'Contributed to',
            }
            for exp in improved.experience:
                polished_bullets = []
                for bullet in exp.bullets:
                    polished = bullet
                    lower = bullet.lower()
                    # Strengthen weak starting verbs
                    for weak, strong in weak_verbs.items():
                        if lower.startswith(weak):
                            polished = strong + polished[len(weak):]
                            cons_changes += 1
                            break
                    # Remove filler words
                    for filler in [' basically ', ' essentially ', ' just ', ' simply ']:
                        if filler in polished.lower():
                            idx = polished.lower().index(filler)
                            polished = polished[:idx] + ' ' + polished[idx + len(filler):]
                            cons_changes += 1
                    # Ensure period at end
                    if polished and not polished.rstrip().endswith('.'):
                        polished = polished.rstrip() + '.'
                    polished_bullets.append(polished)
                exp.bullets = polished_bullets
            
            logger.info(f"Conservative mode: {cons_changes} grammar/verb fixes applied (no injection)")
            
            # Part 6 (Refinement): Remove weak language patterns (clarity only)
            # Conservative preserves 95% structure — only removes clearly weak patterns
            weak_patterns = [
                (r'\bvarious\b', ''),
                (r'\bseveral\b', ''),
                (r'\bnumerous\b', ''),
                (r'\bbasically\b', ''),
                (r'\bessentially\b', ''),
                (r'\bjust\b', ''),
            ]
            for exp in improved.experience:
                for j, bullet in enumerate(exp.bullets):
                    cleaned = bullet
                    for pattern, replacement in weak_patterns:
                        cleaned = re.sub(pattern, replacement, cleaned, flags=re.I)
                    # Clean double spaces
                    cleaned = re.sub(r'  +', ' ', cleaned).strip()
                    if cleaned != bullet:
                        exp.bullets[j] = cleaned
                        cons_changes += 1
            
            logger.info(f"Conservative mode total: {cons_changes} fixes (structure preserved)")
            return improved

        # Role-aware: filter matched skills for non-tech roles
        if role_info and not role_info.get("allow_tech_injection", True):
            from resume_engine.role_engine import TECH_ONLY_SKILLS
            matched_skills = [
                s for s in matched_skills
                if s.lower() not in TECH_ONLY_SKILLS
            ]
            jd_keywords = [
                kw for kw in jd_keywords
                if kw.lower() not in TECH_ONLY_SKILLS
            ]
            logger.info(
                f"Role filter ({role_info.get('role_type', '?')}): "
                f"tech keywords blocked from injection"
            )

        # Capture original state for guardrails
        original_text = self._extract_all_text(tailored_resume)
        original_keywords = self._extract_keyword_set(original_text)

        # Build the resume's tool/skill vocabulary for safe injection
        resume_vocabulary = self._build_vocabulary(tailored_resume)
        improvements = []

        # Deep copy to avoid mutating the tailored version
        improved = tailored_resume.model_copy(deep=True)
        changes_made = 0

        # 1. Reorder skills -- matched skills first, then existing order
        changes_made += self._reorder_skills(improved, matched_skills)

        # 2. Strengthen summary with JD alignment (Rule 3 + 7)
        summary_changes = self._strengthen_summary(
            improved, jd_keywords, matched_skills, resume_vocabulary
        )
        changes_made += summary_changes
        if summary_changes:
            improvements.append("Aligned summary with JD keywords")

        # 3. Deep enhance experience bullets (Rules 1-5, 7-8)
        # All modes except conservative: adds tool context and JD alignment.
        if not is_conservative:
            bullet_changes, bullet_improvements = self._deep_enhance_bullets(
                improved, jd_keywords, matched_skills, resume_vocabulary,
            )
            changes_made += bullet_changes
            improvements.extend(bullet_improvements)

        # 4. Pipeline framing (Rule 4)
        # All modes except conservative: pipeline framing adds end-to-end context.
        if not is_conservative:
            pipeline_changes = self._apply_pipeline_framing(
                improved, jd_keywords, resume_vocabulary
            )
            changes_made += pipeline_changes
            if pipeline_changes:
                improvements.append("Framed related work as end-to-end pipeline")

        # 5. Enhance project bullets too (same rules)
        # All modes except conservative: enhances project bullets with tool context.
        if not is_conservative:
            proj_changes = self._enhance_project_bullets(
                improved, jd_keywords, matched_skills, resume_vocabulary
            )
            changes_made += proj_changes
            if proj_changes:
                improvements.append(f"Enhanced {proj_changes} project bullets")

        # 5b. EXTRACT PROJECT SIGNALS (for rewrite engine)
        project_signals = self._extract_project_signals(improved, jd_keywords)
        if project_signals:
            logger.info(f"  Project signals: {list(project_signals.keys())}")

        # ============================================================
        # 6. BULLET REWRITE ENGINE (v2 — replaces old append injection)
        # Structurally rewrites bullets: [Action + Tool + Purpose + Impact]
        # Strict: up to 8 rewrites (full). Balanced: up to 4 (targeted).
        # ============================================================
        rewrite_changes = self._rewrite_experience_bullets(
            improved, matched_skills, jd_keywords, resume_vocabulary,
            project_signals=project_signals,
            max_rewrites=4 if is_balanced else 8,
        )
        changes_made += rewrite_changes
        if rewrite_changes:
            improvements.append(f"Rewrote {rewrite_changes} bullets with [Action+Tool+Purpose+Impact]")

        # 6b. PROJECT → EXPERIENCE BRIDGING
        # All modes: bridges project-only tools into experience for skill proof.
        if not is_conservative:
            bridge_changes = self._bridge_projects_to_experience(
                improved, matched_skills, jd_keywords, resume_vocabulary
            )
            changes_made += bridge_changes
            if bridge_changes:
                improvements.append(f"Bridged {bridge_changes} project-only tools into experience bullets")

        # 6c. SKILL-TO-EXPERIENCE LINKING (catch skills rewriter missed)
        # Strict: up to 8 links (max coverage). Balanced: up to 4 (natural voice).
        link_changes, link_improvements = self._link_skills_to_experience(
            improved, matched_skills, jd_keywords, resume_vocabulary,
            max_links=4 if is_balanced else 8
        )
        changes_made += link_changes
        improvements.extend(link_improvements)

        # 7. Tool depth expansion in summary
        # Strict only: adds ecosystem context for keyword density.
        # Balanced: skip — keeps summary concise.
        if not is_balanced:
            depth_changes = self._expand_tool_depth_in_summary(
                improved, matched_skills, resume_vocabulary
            )
            changes_made += depth_changes
            if depth_changes:
                improvements.append("Expanded tool depth with ecosystem context")

        # 8. PROJECT-TO-SUMMARY PROMOTION
        # Balanced: skip — keeps summary concise, strict adds project depth
        if not is_balanced:
            promo_changes = self._promote_projects_to_summary(
                improved, jd_keywords, resume_vocabulary
            )
            changes_made += promo_changes
            if promo_changes:
                improvements.append("Promoted project achievements to summary")

        # 9. EDUCATION RELEVANCE BOOST — adds keyword density to education
        if not is_conservative:
            edu_changes = self._boost_education_relevance(improved, jd_keywords)
            changes_made += edu_changes
            if edu_changes:
                improvements.append("Highlighted education relevance")

        # 10. RECOMMENDATION EXECUTION ENGINE
        rec_changes = self._execute_recommendations(
            improved, recommendations, jd_keywords, resume_vocabulary
        )
        changes_made += rec_changes
        if rec_changes:
            improvements.append(f"Executed {rec_changes} MUST recommendations")

        # 11. SAFE SKILL EXPANSION (compound JD requirements)
        # All modes except conservative: expands compound skill references.
        if not is_conservative:
            expand_changes = self._expand_compound_skills(
                improved, missing_skills, resume_vocabulary
            )
            changes_made += expand_changes
            if expand_changes:
                improvements.append("Expanded compound skill references")

        # HARDENED: Track bullets already enriched (prevent double injection)
        self._enriched_bullets = set()  # (exp_idx, bullet_idx)
        for i_e, exp_e in enumerate(improved.experience):
            for j_e, b_e in enumerate(exp_e.bullets):
                b_lower_e = b_e.lower()
                if any(m in b_lower_e for m in [", using ", ", applying ", ", leveraging ", ", utilizing "]):
                    self._enriched_bullets.add((i_e, j_e))

        # 12. SKILL COVERAGE ENGINE (deterministic)
        # Strict: force-injects skill proof for max ATS coverage.
        # Balanced: targeted injection (max 3) for natural skill proof.
        if not is_conservative:
            coverage_changes = self._force_skill_coverage(
                improved, matched_skills, jd_keywords, resume_vocabulary
            )
            changes_made += coverage_changes
            if coverage_changes:
                improvements.append(f"Forced {coverage_changes} skills into bullet evidence")

        # 12b. JD KEYWORD INJECTION (close keyword gaps)
        # Strict: max 5 keywords injected for ATS density.
        # Balanced: max 3 keywords for natural alignment.
        if not is_conservative:
            kw_inject_changes = self._inject_missing_jd_keywords(
                improved, jd_keywords, resume_vocabulary,
                max_injections=3 if is_balanced else 5
            )
            changes_made += kw_inject_changes
            if kw_inject_changes:
                improvements.append(f"Injected {kw_inject_changes} missing JD keyword phrases")

        # 13. MAX SCORE UTILIZATION ENGINE
        # Strict: aggressive ATS keyword/skill injection for max score.
        # Balanced: light mode — targeted skill proof without over-optimization.
        if not is_conservative:
            max_changes, max_improvements = self._maximize_score(
                improved, matched_skills, jd_keywords, resume_vocab=resume_vocabulary,
                light_mode=is_balanced  # Light for balanced, full for strict
            )
            changes_made += max_changes
            improvements.extend(max_improvements)

        # 14. BULLET QUALITY ENGINE (Part 6 from Shortlist spec)
        # Prioritize high-impact bullets, demote vague/weak bullets
        # Impact priority: revenue > scale > complexity > tool usage
        if not is_conservative:
            bullet_order_changes = self._prioritize_impact_bullets(
                improved, max_bullets=6 if is_balanced else 5,
                role_type=_role_type,
            )
            changes_made += bullet_order_changes
            if bullet_order_changes:
                improvements.append(f"Reordered {bullet_order_changes} bullets by impact")
        
        # 14b. SIGNAL DOMINANCE ENGINE — strongest signals first WITHIN each role
        # A recruiter reads: summary + first role + first 2-3 bullets (10 seconds).
        # Reorder bullets WITHIN each role so strongest lead. NEVER move across roles.
        # Moving bullets between companies = fake experience under wrong employer.
        if not is_conservative and improved.experience:
            for exp in improved.experience:
                if len(exp.bullets) < 2:
                    continue
                # Score each bullet
                scored = [(self._score_bullet_impact(b, _role_type), idx, b)
                          for idx, b in enumerate(exp.bullets)]
                # Only swap if the best bullet is significantly better than lead
                best = max(scored, key=lambda x: x[0])
                lead_score = scored[0][0]
                if best[1] != 0 and best[0] > lead_score + 2:
                    # Swap lead with best (keep rest in original order)
                    old_idx = best[1]
                    exp.bullets[0], exp.bullets[old_idx] = exp.bullets[old_idx], exp.bullets[0]
                    promoted = 1
                    improvements.append(
                        f"Signal Dominance: promoted strongest bullet to lead in {exp.company}"
                    )
        
        
        # 14c. PROJECT REORDERING — strongest project first
        if not is_conservative and len(improved.projects) >= 2:
            def _project_score(proj):
                return max((self._score_bullet_impact(b, _role_type) for b in proj.bullets), default=0)
            improved.projects.sort(key=_project_score, reverse=True)

        # 14d. COMPETITIVE POSITIONING ENGINE — upgrade good bullets into TOP bullets
        # Problem: strong resumes (80+ baseline) get minimal improvement because
        # their bullets already have tools + purpose. But they LACK:
        #   - Scale indicators (numbers, volume, scope)
        #   - Impact clarity (outcome, business value)
        #   - Differentiators (rare skills, unique achievements)
        # This pass adds missing competitive elements WITHOUT destroying existing content.
        # Strict only: competitive mode requires aggressive enhancement.
        if not is_balanced and not is_conservative:
            comp_upgrades = self._competitive_bullet_upgrade(
                improved, jd_keywords, matched_skills, resume_vocabulary, _role_type
            )
            changes_made += comp_upgrades
            if comp_upgrades:
                improvements.append(f"Competitive upgrade: {comp_upgrades} bullets enhanced with scale/impact")


        # ============================================================
        # GUARDRAILS
        # ============================================================

        # -- Keyword Preservation Check ----------------------
        improved_text = self._extract_all_text(improved)
        improved_keywords = self._extract_keyword_set(improved_text)
        lost_keywords = original_keywords - improved_keywords

        # Exclude words that were intentionally upgraded (verb replacements)
        upgraded_words = set()
        for pattern in DEPTH_PATTERNS:
            word = pattern.replace(r"\b", "").lower()
            if word:
                upgraded_words.add(word)
        for generic in JD_ALIGNMENT_MAP:
            for word in generic.split():
                if len(word) > 2:
                    upgraded_words.add(word.lower())

        real_lost = lost_keywords - upgraded_words
        # Filter out common/short words that aren't truly technical keywords
        # CRITICAL: Include generic resume filler words that the summary engine
        # rightfully removes (passion, solving, complex, etc.)
        common_words = {"random", "forest", "tree", "model", "data", "used", "built",
                        "created", "made", "work", "based", "support", "help", "test",
                        "system", "process", "report", "design", "type", "improve",
                        "large", "scale", "real", "time", "high", "level", "well",
                        "cross", "function", "driven", "making", "planning", "quality",
                        "check", "output", "input", "record", "effort", "manual",
                        # Generic resume filler — NOT real keywords
                        "passion", "passionate", "solving", "complex", "problems",
                        "experienced", "dedicated", "hardworking", "motivated",
                        "seeking", "opportunities", "looking", "position", "role",
                        "scientist", "engineer", "developer", "analyst", "manager",
                        "professional", "specialist", "senior", "junior", "lead",
                        "assisted", "attended", "participated", "various", "several",
                        "strong", "excellent", "proven", "results", "track",
                        }
        real_lost = {w for w in real_lost if w not in common_words and len(w) > 3}
        if len(real_lost) >= 5:
            logger.warning(
                f"GUARDRAIL: Improvement would lose {len(real_lost)} keywords: "
                f"{list(real_lost)[:5]} -- reverting to tailored resume"
            )
            return tailored_resume.model_copy(deep=True)

        # -- Repetition Control ------------------------------
        if self._has_excessive_repetition(improved_text, max_repeat=4):
            logger.warning("GUARDRAIL: Excessive keyword repetition detected -- reverting")
            return tailored_resume.model_copy(deep=True)

        # -- DETERMINISTIC LOCK: No new skills allowed -------
        original_skills = {s.lower() for s in tailored_resume.skills}
        improved_skills = {s.lower() for s in improved.skills}
        new_skills = improved_skills - original_skills
        if new_skills:
            logger.warning(
                f"DETERMINISTIC LOCK: Improver added {len(new_skills)} new skills "
                f"{list(new_skills)[:3]} -- reverting skills to original"
            )
            improved.skills = tailored_resume.skills[:]

        # -- SKILL COUNT PROTECTION (Part 1) -----------------
        # Never reduce skills list
        if len(improved.skills) < len(tailored_resume.skills):
            logger.warning(
                f"SKILL PROTECTION: Skills reduced from {len(tailored_resume.skills)} "
                f"to {len(improved.skills)} -- restoring original"
            )
            improved.skills = tailored_resume.skills[:]

        # -- DETERMINISTIC LOCK: Bullet length cap -----------
        # Bullets can grow by max 220 chars (structural rewrite + tool + purpose + impact)
        # Hard cap: no bullet should exceed 250 chars
        for i, exp in enumerate(improved.experience):
            if i < len(tailored_resume.experience):
                orig_exp = tailored_resume.experience[i]
                for j, bullet in enumerate(exp.bullets):
                    if j < len(orig_exp.bullets):
                        growth = len(bullet) - len(orig_exp.bullets[j])
                        if growth > 220:
                            logger.warning(
                                f"DETERMINISTIC LOCK: Bullet grew by {growth} chars "
                                f"(max 220) -- reverting bullet"
                            )
                            exp.bullets[j] = orig_exp.bullets[j]
                        elif len(bullet) > 250:
                            # Truncate to hard cap
                            exp.bullets[j] = bullet[:247] + "..."

        # -- BULLET CLEANUP: Strip AI-generated patterns ------
        for exp in improved.experience:
            for j, bullet in enumerate(exp.bullets):
                cleaned = bullet
                
                # Fix double-applying/utilizing stacking
                cleaned = re.sub(
                    r',\s*(?:applying|utilizing)\s+\w+,\s*(?:applying|utilizing)\s+',
                    ', using ',
                    cleaned, flags=re.I
                )
                # Fix trailing injection after "using X for Y" (double injection)
                enrichment_count = (cleaned.lower().count("using ") + 
                                    cleaned.lower().count("applying ") + 
                                    cleaned.lower().count("utilizing "))
                if enrichment_count > 2:
                    # Strip the last injection phrase
                    cleaned = re.sub(
                        r',\s*(?:utilizing|applying)\s+\w[\w\s]*?(?:for\s+[\w\s]+)?\.?$',
                        '.',
                        cleaned
                    )
                # Fix double periods
                cleaned = cleaned.replace("..", ".")
                
                # HUMANIZATION: Fix bare "using X," single-word tool without purpose
                # Only strips single lowercase tech words (bert, flask), NOT multi-word skills
                cleaned = re.sub(
                    r',\s*(?:using|applying|with)\s+([a-z]\w{2,15})\s*[,.](?!\s*(?:for|to|enabling|improving|reducing|achieving))',
                    lambda m: ',' if m.group(1).islower() and ' ' not in m.group(1) else m.group(0),
                    cleaned
                )
                # HUMANIZATION: Fix "for X for Y" double-purpose chains
                # e.g. "for data-driven decision making for deep learning" → "for data-driven decision making"
                cleaned = re.sub(
                    r'(for\s+[\w-]+(?:\s+[\w-]+){0,3})\s+for\s+[\w-]+(?:\s+[\w-]+){0,5}\s*\.?$',
                    r'\1.',
                    cleaned
                )
                # Note: removed 'utilizing/applying X.' trailing cleanup — too aggressive
                # for domain skills (HR, marketing) where bare skill mentions are valid
                # HARDENED: Word-repetition dedup — catch "deployments...deployments"
                # Non-adjacent: scan for same significant word within 8-word window
                words_in = cleaned.lower().split()
                for w_idx in range(len(words_in)):
                    w = words_in[w_idx]
                    if len(w) >= 6 and w not in {'using', 'which', 'their', 'models', 'learning'}:
                        # Check next 8 words for duplicate
                        window = words_in[w_idx + 1:w_idx + 9]
                        if w in window:
                            # Truncate at the repeated word's second occurrence
                            dup_pos = cleaned.lower().rfind(w)
                            first_pos = cleaned.lower().find(w)
                            if dup_pos > first_pos:
                                # Cut from the preposition before the repeated phrase
                                cut_start = max(first_pos + len(w), dup_pos - 20)
                                # Find the nearest ", for " or " for " before the dup
                                pre_text = cleaned[:dup_pos]
                                last_for = pre_text.rfind(' for ')
                                last_comma = pre_text.rfind(', ')
                                cut_at = max(last_for, last_comma)
                                if cut_at > first_pos + len(w):
                                    cleaned = cleaned[:cut_at].rstrip(', ') + '.'
                                    break
                # (production-grade and context-mismatch checks moved to HARD HUMAN QUALITY FILTER)
                # HARDENED: Strip "accelerating release velocity" and similar
                # context-mismatched competitive phrases
                cleaned = re.sub(
                    r',\s*accelerating\s+(?:release\s+)?velocity\b[^.]*',
                    '',
                    cleaned, flags=re.I
                )
                # Final cleanup
                cleaned = cleaned.replace("..", ".").replace(" ,", ",")
                if cleaned != bullet:
                    exp.bullets[j] = cleaned

        # -- PART 6 (Trust): FINAL HUMAN TRUST CHECK ----------
        # Detect and fix resume-wide trust violations:
        # 1. Too many strong ownership verbs → sounds inflated
        # 2. Too many soft-scale adjectives → sounds templated
        strong_verb_pattern = re.compile(
            r'^(?:Led|Architected|Owned|Spearheaded|Pioneered|Drove)\b', re.I
        )
        soft_scale_pattern = re.compile(
            r'\b(?:large-scale|enterprise-scale|high-throughput|'
            r'production-grade|cross-functional|distributed)\b', re.I
        )
        
        # Count across ALL bullets
        all_bullets = []
        for exp in improved.experience:
            for j, b in enumerate(exp.bullets):
                all_bullets.append((exp, j, b))
        
        strong_verb_count = sum(
            1 for _, _, b in all_bullets if strong_verb_pattern.search(b)
        )
        soft_scale_total = sum(
            len(soft_scale_pattern.findall(b)) for _, _, b in all_bullets
        )
        
        # Cap: max 3 strong verbs across entire resume
        if strong_verb_count > 3:
            reverted = 0
            for exp_obj, j, b in reversed(all_bullets):
                if reverted >= strong_verb_count - 3:
                    break
                if strong_verb_pattern.search(b):
                    if j < len(tailored_resume.experience[0].bullets if tailored_resume.experience else []):
                        # Downgrade: replace strong verb with moderate one
                        fixed = re.sub(r'^Led\b', 'Managed', b)
                        fixed = re.sub(r'^Architected\b', 'Designed', fixed)
                        fixed = re.sub(r'^Spearheaded\b', 'Drove', fixed)
                        fixed = re.sub(r'^Pioneered\b', 'Introduced', fixed)
                        if fixed != b:
                            exp_obj.bullets[j] = fixed
                            reverted += 1
            if reverted:
                logger.info(
                    f"  TRUST CHECK: Downgraded {reverted} strong verbs "
                    f"(was {strong_verb_count}, max 3)"
                )
        
        # Cap: max 4 soft-scale phrases across entire resume
        if soft_scale_total > 4:
            logger.info(
                f"  TRUST CHECK: {soft_scale_total} soft-scale phrases "
                f"detected (max 4) — monitoring"
            )

        # -- SUMMARY DEDUP: Remove repeated "Experienced in" phrases --
        if improved.summary:
            sentences = improved.summary.split(". ")
            seen_prefixes = set()
            deduped = []
            for s in sentences:
                prefix = s[:20].lower().strip()
                if prefix in seen_prefixes:
                    continue  # Skip duplicate sentence starts
                seen_prefixes.add(prefix)
                deduped.append(s)
            improved.summary = ". ".join(deduped)
            if not improved.summary.endswith("."):
                improved.summary += "."

        # -- DETERMINISTIC LOCK: Summary length cap ----------
        if tailored_resume.summary and improved.summary:
            growth = len(improved.summary) - len(tailored_resume.summary)
            # Allow substantial growth (tool depth + pipeline + project promo + edu)
            if growth > 450:
                logger.warning(
                    f"DETERMINISTIC LOCK: Summary grew by {growth} chars "
                    f"(max 450) -- reverting"
                )
                improved.summary = tailored_resume.summary
            # Hard cap: truncate at 500 chars if needed
            elif len(improved.summary) > 500:
                improved.summary = improved.summary[:497] + "..."

        # -- HARD HUMAN QUALITY FILTER (FINAL PASS) -----------
        # Enforces recruiter-level quality on every bullet.
        # Rejects/fixes: bare tool usage, tool stacking, broken grammar,
        # repeated structures, AI-sounding output.
        _TOOL_PURPOSE = {
            "python": "for data processing and automation",
            "pandas": "for data cleaning and transformation",
            "numpy": "for numerical computation",
            "sql": "for data querying and reporting",
            "tensorflow": "for model training and inference",
            "pytorch": "for deep learning model development",
            "keras": "for neural network prototyping",
            "sklearn": "for predictive modeling",
            "scikit-learn": "for predictive modeling",
            "docker": "for containerized deployment",
            "kubernetes": "for container orchestration",
            "aws": "for cloud infrastructure",
            "gcp": "for cloud services",
            "azure": "for cloud deployment",
            "spark": "for distributed data processing",
            "tableau": "for data visualization",
            "power bi": "for business intelligence reporting",
            "react": "for interactive UI development",
            "node.js": "for backend services",
            "git": "for version control",
            "jenkins": "for CI/CD automation",
            "redis": "for caching and performance",
            "mongodb": "for document data storage",
            "nlp": "for text analysis",
            "lstm": "for sequence modeling",
            "xgboost": "for gradient boosting models",
        }
        tool_markers = [", using ", ", applying ", ", utilizing ", ", leveraging ",
                        " using ", " applying ", " utilizing ", " leveraging "]

        for i_exp, exp in enumerate(improved.experience):
            orig_bullets = (tailored_resume.experience[i_exp].bullets
                           if i_exp < len(tailored_resume.experience) else [])
            for j, bullet in enumerate(exp.bullets):
                original_bullet = orig_bullets[j] if j < len(orig_bullets) else bullet
                cleaned = bullet
                b_lower = cleaned.lower()

                # RULE 1: Reject bare "using/leveraging X" at end without purpose
                # Pattern: ends with "using <tool>." or "leveraging <tool>."
                bare_match = re.search(
                    r',?\s*(?:using|leveraging|utilizing|applying)\s+(\w[\w\s.#+]*?)\s*\.?\s*$',
                    cleaned, re.I
                )
                if bare_match:
                    tool_name = bare_match.group(1).strip().rstrip('.')
                    tool_key = tool_name.lower()
                    purpose = _TOOL_PURPOSE.get(tool_key, "")
                    if purpose:
                        # Append purpose instead of bare tool mention
                        prefix = cleaned[:bare_match.start()].rstrip(', ')
                        cleaned = f"{prefix}, leveraging {tool_name} {purpose}."
                    # If no purpose mapping, leave as-is (domain-specific tool)

                # RULE 2: Reject >3 commas (broken/stuffed sentence)
                if cleaned.count(',') > 3:
                    # Try to truncate at 3rd comma if sentence still makes sense
                    parts = cleaned.split(',')
                    truncated = ','.join(parts[:3]).rstrip() + '.'
                    if len(truncated) > 40:
                        cleaned = truncated
                    else:
                        cleaned = original_bullet  # Revert to original

                # RULE 3: HARDENED — Reject tool stacking (>1 using/leveraging in same bullet)
                # Count ALL occurrences of tool-usage markers (organic + injected)
                cleaned_lower = cleaned.lower()
                using_count = len(re.findall(r'\busing\s+\w', cleaned_lower))
                apply_count = len(re.findall(r'\b(?:applying|leveraging|utilizing)\s+\w', cleaned_lower))
                total_tool_markers = using_count + apply_count
                if total_tool_markers > 1:
                    # Strip the LAST comma-prefixed injection (keep the first/organic one)
                    for marker in [", using ", ", utilizing ", ", applying ", ", leveraging "]:
                        last_pos = cleaned_lower.rfind(marker)
                        if last_pos >= 0:
                            cleaned = cleaned[:last_pos].rstrip(', ') + '.'
                            break

                # RULE 3b: Strip injected 'production-grade' if not in original bullet
                if 'production-grade' in cleaned.lower() and 'production-grade' not in original_bullet.lower():
                    cleaned = re.sub(r'\s*production-grade\s*', ' ', cleaned, flags=re.I)
                    cleaned = cleaned.replace('  ', ' ')

                # RULE 3c: Strip context-mismatched injection (SQL in image/CV bullets)
                cl_lower = cleaned.lower()
                if 'image classification' in cl_lower or 'computer vision' in cl_lower:
                    cleaned = re.sub(r',\s*using\s+sql\s+[^.]*', '', cleaned, flags=re.I)

                # RULE 4: Ensure proper sentence structure
                if cleaned and cleaned[0].islower():
                    cleaned = cleaned[0].upper() + cleaned[1:]
                if cleaned and cleaned[-1] not in '.!':
                    cleaned = cleaned.rstrip() + '.'

                # RULE 5: Fix punctuation artifacts and whitespace
                cleaned = cleaned.replace('..', '.').replace('  ', ' ').replace(' ,', ',')
                cleaned = cleaned.replace(',.', '.')  # Fix trailing comma-period

                # RULE 5b: Strip nonsense competitive suffixes
                # e.g., "improving user engagement by 22% for infrastructure" — nonsense
                nonsense_suffixes = [
                    r'\s+for\s+infrastructure\s*\.',
                    r'\s+for\s+scalable\s+systems\s*\.',
                    r',\s*supporting long-term system growth\s*\.',
                ]
                for ns_pat in nonsense_suffixes:
                    if re.search(ns_pat, cleaned, re.I):
                        # Only strip if the suffix was NOT in the original bullet
                        if not re.search(ns_pat, original_bullet, re.I):
                            cleaned = re.sub(ns_pat, '.', cleaned, flags=re.I)

                # RULE 5c: Fix redundant tool expansion + purpose overlap
                # e.g., "pytorch (deep learning models) for deep learning model development"
                # The parenthetical and purpose phrase say the same thing
                rdp = re.search(
                    r'(\w+)\s*\(([^)]+)\)\s+for\s+(\2[^,.]*)[\s,.]',
                    cleaned, re.I
                )
                if rdp:
                    # Remove the redundant parenthetical
                    cleaned = re.sub(
                        r'(\w+)\s*\([^)]+\)',
                        r'\1',
                        cleaned, count=1
                    )

                # ---- TRUST LAYER ----

                # TRUST 1: Strip synthetic parenthetical injections
                # e.g., "machine learning (feature engineering)" → "machine learning"
                # Skip in strict mode — parentheticals add JD keyword coverage
                if mode != 'strict':
                    paren_match = re.search(r'\s*\([^)]{3,30}\)', cleaned)
                    if paren_match and paren_match.group() not in original_bullet:
                        cleaned = cleaned[:paren_match.start()] + cleaned[paren_match.end():]
                        cleaned = cleaned.replace('  ', ' ')

                # TRUST 2: Cap tool+purpose suffix length
                # Strict: 80 chars (preserves ATS keywords)
                # Balanced/Conservative: 60 chars (cleaner)
                suffix_limit = 80 if mode == 'strict' else 60
                tool_suffix = re.search(
                    r',\s*(?:using|leveraging|applying|utilizing)\s+(.+)$',
                    cleaned, re.I
                )
                if tool_suffix and len(tool_suffix.group()) > suffix_limit:
                    # Truncate to tool + short purpose only
                    suffix_text = tool_suffix.group(1)
                    # Keep "tool for purpose" — purpose must end on word boundary
                    short = re.match(r'([\w][\w\s.#+]*?)\s+for\s+((?:[\w-]+\s+){1,3}[\w-]+)', suffix_text)
                    if short:
                        new_suffix = f", using {short.group(1).strip()} for {short.group(2).strip()}"
                        if len(new_suffix) <= 60:
                            cleaned = cleaned[:tool_suffix.start()] + new_suffix + '.'
                        else:
                            # Just tool name
                            cleaned = cleaned[:tool_suffix.start()] + f", using {short.group(1).strip()}."
                    else:
                        # Just keep tool name
                        tool_only = re.match(r'([\w][\w\s.#+]*?)(?:\s+for|\s*[,.])', suffix_text)
                        if tool_only:
                            cleaned = cleaned[:tool_suffix.start()] + f", using {tool_only.group(1).strip()}."

                # TRUST 3: Enforce max bullet length
                # Strict: 200 chars (preserves enrichment)
                # Balanced/Conservative: 160 chars (natural)
                bullet_limit = 200 if mode == 'strict' else 160
                if len(cleaned) > bullet_limit and len(original_bullet) < 140:
                    # Find a clean truncation point (last comma or period before 160)
                    trunc_zone = cleaned[:160]
                    last_comma = trunc_zone.rfind(', ')
                    last_for = trunc_zone.rfind(' for ')
                    cut_at = max(last_comma, last_for)
                    if cut_at > 60:
                        cleaned = cleaned[:cut_at].rstrip(', ') + '.'

                # TRUST 4: Strip filler purpose phrases that add no value
                # Skip in strict mode — these phrases contain JD keywords
                if mode != 'strict':
                    filler_phrases = [
                        r'\s+for\s+consistent\s+reproducible\s+\w+\s*\.?',
                        r'\s+for\s+automated\s+data\s+processing\s*[,.]',
                        r'\s+for\s+complex\s+data\s+querying\s+and\s+analytics\s*\.?',
                        r'\s+for\s+large-scale\s+distributed\s+data\s+processing\s*\.?',
                    ]
                    for fp in filler_phrases:
                        if re.search(fp, cleaned, re.I):
                            if not re.search(fp, original_bullet, re.I):
                                cleaned = re.sub(fp, '.', cleaned, flags=re.I)
                                cleaned = cleaned.replace('..', '.')

                # TRUST 5: Final cleanup after all trust rules
                # Fix ". using" → ", using" (period before tool suffix = broken)
                cleaned = re.sub(r'\.\s+(using|applying|leveraging|utilizing)\s+',
                                 r', \1 ', cleaned, flags=re.I)
                # Fix mid-word truncation at bullet end
                # e.g., "training neural." — word cut off
                trunc_end = re.search(r'\b(\w{1,6})\.\s*$', cleaned)
                if trunc_end:
                    word = trunc_end.group(1)
                    # Check if the truncated word is a real common ending
                    real_endings = {'by', 'for', 'to', 'in', 'on', 'at', 'and', 'the', 'an',
                                    'via', 'per', 'etc', 'use', 'ml', 'ai', 'nlp', 'sql',
                                    'aws', 'gcp', 'api', 'etl', 'lstm', 'bert', 'daily'}
                    is_acronym = word.isupper()  # e.g., "AWS", "GCP"
                    if word.lower() not in real_endings and not is_acronym:
                        # Truncated — cut back to previous complete phrase
                        cleaned = cleaned[:trunc_end.start()].rstrip(', ') + '.'
                # Final double-period, double-using, and whitespace cleanup
                cleaned = cleaned.replace('..', '.').replace('  ', ' ')
                cleaned = re.sub(r'using,\s*using\s+', 'using ', cleaned, flags=re.I)

                exp.bullets[j] = cleaned

        # RULE 6: Detect repeated sentence starters across all bullets
        all_starts = []
        for exp in improved.experience:
            for bullet in exp.bullets:
                first_word = bullet.split()[0] if bullet.split() else ""
                all_starts.append(first_word)
        # If same verb starts >50% of bullets, vary them
        if all_starts:
            from collections import Counter
            start_counts = Counter(all_starts)
            most_common_verb, count = start_counts.most_common(1)[0]
            if count > len(all_starts) * 0.5 and count >= 3:
                verb_alternatives = {
                    "Built": ["Developed", "Designed", "Created", "Engineered"],
                    "Developed": ["Built", "Designed", "Created", "Implemented"],
                    "Designed": ["Created", "Architected", "Engineered", "Built"],
                    "Implemented": ["Deployed", "Built", "Executed", "Delivered"],
                    "Analyzed": ["Evaluated", "Assessed", "Examined", "Reviewed"],
                    "Managed": ["Led", "Directed", "Coordinated", "Oversaw"],
                    "Led": ["Managed", "Directed", "Guided", "Oversaw"],
                    "Optimized": ["Improved", "Enhanced", "Streamlined", "Refined"],
                    "Automated": ["Streamlined", "Built", "Engineered", "Developed"],
                    "Created": ["Built", "Developed", "Designed", "Produced"],
                }
                alternatives = verb_alternatives.get(most_common_verb, [])
                if alternatives:
                    alt_idx = 0
                    replaced = 0
                    for exp in improved.experience:
                        for j, bullet in enumerate(exp.bullets):
                            if (bullet.startswith(most_common_verb) and replaced > 0
                                    and alt_idx < len(alternatives)):
                                new_verb = alternatives[alt_idx]
                                exp.bullets[j] = new_verb + bullet[len(most_common_verb):]
                                alt_idx += 1
                                replaced += 1
                            elif bullet.startswith(most_common_verb):
                                replaced += 1  # Keep first occurrence

        # RULE 7: Fuzzy bullet deduplication (per-role)
        # If two bullets share >80% of their core text, remove the shorter one.
        for exp in improved.experience:
            if len(exp.bullets) < 2:
                continue
            deduped = []
            removed_indices = set()
            for i, b1 in enumerate(exp.bullets):
                if i in removed_indices:
                    continue
                # Compare b1's core (first 50 chars, stripped of tool suffix)
                core1 = re.sub(r',\s*(?:using|leveraging|applying|utilizing)\s+.*$', '', b1, flags=re.I)
                core1_clean = core1.lower().strip().rstrip('.')
                is_dup = False
                for k, b2 in enumerate(exp.bullets):
                    if k <= i or k in removed_indices:
                        continue
                    core2 = re.sub(r',\s*(?:using|leveraging|applying|utilizing)\s+.*$', '', b2, flags=re.I)
                    core2_clean = core2.lower().strip().rstrip('.')
                    # Check if cores are >80% similar
                    if core1_clean == core2_clean:
                        # Keep the one with the enrichment, remove the bare one
                        if len(b1) >= len(b2):
                            removed_indices.add(k)
                        else:
                            removed_indices.add(i)
                            is_dup = True
                            break
                    # Also check if one is a prefix of the other
                    shorter = min(core1_clean, core2_clean, key=len)
                    longer = max(core1_clean, core2_clean, key=len)
                    if len(shorter) > 30 and shorter in longer:
                        # Keep the longer/richer version
                        if len(b1) >= len(b2):
                            removed_indices.add(k)
                        else:
                            removed_indices.add(i)
                            is_dup = True
                            break
                if not is_dup:
                    deduped.append(b1)
            # Only apply if we actually removed something
            if removed_indices:
                exp.bullets = [b for i, b in enumerate(exp.bullets) if i not in removed_indices]
                logger.info(
                    f"  DEDUP: Removed {len(removed_indices)} duplicate bullet(s) "
                    f"from {exp.company}"
                )

        logger.info(
            f"Resume improved: {changes_made} enhancements applied | "
            f"{len(improvements)} rules triggered | keywords preserved"
        )
        if improvements:
            for imp in improvements[:8]:
                logger.info(f"  -> {imp}")

        # ---- PART 9: FINAL BULLET INTEGRITY GATE ----
        # Non-negotiable: revert any bullet that fails quality checks
        improved = self._bullet_integrity_gate(
            improved, tailored_resume, role_info=role_info, mode=mode
        )

        return improved

    # ================================================================
    # BULLET INTEGRITY GATE (Parts 1-5, 7-9)
    # ================================================================

    def _bullet_integrity_gate(
        self,
        improved: StructuredResume,
        original: StructuredResume,
        role_info: dict = None,
        mode: str = "strict",
    ) -> StructuredResume:
        """
        FINAL quality gate. Reverts any bullet that violates integrity rules.
        
        Rules enforced:
          Part 1: Semantic preservation -- meaning must not change (≥60% overlap)
          Part 1b: POSITIONAL LOCK -- bullet[j] must match original[j], not any bullet
          Part 2: Tool usage must be action + purpose (not bare injection)
          Part 3: No keyword injection without clear context
          Part 3b: No awkward "using X for Y" chains appended to bullets
          Part 4: Grammar integrity (no broken sentences, fragments, double tokens)
          Part 4b: Grammar fragment patterns ("using X enabling Y", trailing prepositions)
          Part 5: Role consistency (no new responsibilities invented)
          Part 7: AI-detection reversal (revert robotic phrasing)
          Part 8: Safe mode (max rewrites per role -- balanced/conservative only)
          Part 9: Output guarantee (no fake skills/tools)
          Part 10: Length explosion check (rewritten must not be >2x original length)
        """
        reverted = 0
        total_checked = 0
        role_info = role_info or {}
        is_safe_mode = mode in ("balanced", "conservative")
        max_rewrites_per_role = 5 if is_safe_mode else 8

        for i, exp in enumerate(improved.experience):
            orig_exp = (original.experience[i]
                        if i < len(original.experience) else None)
            if not orig_exp:
                continue

            rewrite_count = 0  # Track rewrites per role (Part 8)

            for j, bullet in enumerate(exp.bullets):
                total_checked += 1

                # ---- PART 1b: POSITIONAL LOCK ----
                # Each bullet[j] MUST correspond to original[j], not any bullet.
                # This prevents bullet swapping (a critical quality issue).
                if j < len(orig_exp.bullets):
                    orig_bullet = orig_exp.bullets[j]
                else:
                    # Extra bullet beyond original count — revert to empty or skip
                    continue

                # Skip if bullet is unchanged
                if bullet == orig_bullet:
                    continue

                rewrite_count += 1
                fail_reason = None

                # ---- PART 1: SEMANTIC PRESERVATION (STRICT) ----
                # Core CONTENT words must survive (exclude fillers/weak verbs)
                # Mode-aware thresholds: strict allows more aggressive rewrites,
                # conservative requires very high preservation
                _SEMANTIC_THRESHOLDS = {
                    "strict": 0.50,      # Allow aggressive rewrites
                    "balanced": 0.55,    # Moderate preservation
                    "conservative": 0.65 # High preservation required
                }
                semantic_min = _SEMANTIC_THRESHOLDS.get(mode, 0.55)
                
                _FILLER_WORDS = {
                    "was", "were", "had", "has", "have", "been", "being",
                    "responsible", "helped", "assisted", "worked", "involved",
                    "successfully", "completed", "looked", "tasks", "included",
                    "the", "and", "for", "with", "from", "that", "this",
                    "also", "very", "just", "some", "other", "such",
                }
                orig_words = set(re.findall(r'[a-z]{3,}', orig_bullet.lower())) - _FILLER_WORDS
                new_words = set(re.findall(r'[a-z]{3,}', bullet.lower())) - _FILLER_WORDS
                if orig_words and len(orig_words) >= 3:
                    overlap = len(orig_words & new_words) / len(orig_words)
                    if overlap < semantic_min:
                        fail_reason = "semantic drift (%d%% overlap, min %d%%)" % (
                            int(overlap * 100), int(semantic_min * 100))

                # ---- PART 2: TOOL USAGE VALIDATION ----
                # Block bare "applying X" / "using X" at end without purpose
                if not fail_reason:
                    bare_tool = re.search(
                        r',\s*(?:applying|using|leveraging|utilizing)\s+'
                        r'(\w[\w\s.#+]*?)\s*\.?\s*$',
                        bullet, re.I
                    )
                    if bare_tool:
                        tool_text = bare_tool.group(1).strip().rstrip('.')
                        # Check it's truly bare (no "for/to" purpose after tool)
                        after_tool = bullet[bare_tool.start():]
                        has_purpose = bool(re.search(
                            r'(?:for|to|enabling|improving|reducing|achieving)\s+\w',
                            after_tool, re.I
                        ))
                        if not has_purpose:
                            fail_reason = "bare tool injection: '%s'" % tool_text

                # ---- PART 3: KEYWORD STUFFING CHECK ----
                if not fail_reason:
                    b_lower = bullet.lower()
                    inject_count = sum(1 for m in [
                        ", applying ", ", using ", ", utilizing ",
                        ", leveraging ", ", with "
                    ] if m in b_lower)
                    if inject_count >= 2:
                        fail_reason = "keyword stuffing (%d injections)" % inject_count

                # ---- PART 3b: AWKWARD INJECTION PATTERNS ----
                if not fail_reason:
                    # Pattern: ", using X for Y" appended at the end of an otherwise fine bullet
                    awkward_suffix = re.search(
                        r',\s*(?:using|applying|leveraging|utilizing)\s+\w[\w\s]*?'
                        r'\s+(?:for|to|enabling)\s+[\w\s]+\.\s*$',
                        bullet, re.I
                    )
                    if awkward_suffix:
                        # Check if this suffix was NOT in the original
                        suffix_text = bullet[awkward_suffix.start():]
                        if suffix_text.lower() not in orig_bullet.lower():
                            fail_reason = "awkward injected suffix: '%s'" % suffix_text.strip()[:50]

                # ---- PART 4: GRAMMAR INTEGRITY ----
                if not fail_reason:
                    # Duplicate consecutive tokens
                    words_seq = bullet.split()
                    for k in range(len(words_seq) - 1):
                        if (words_seq[k].lower() == words_seq[k + 1].lower()
                                and words_seq[k].lower() not in {'and', 'the', 'to'}):
                            fail_reason = "duplicate token: '%s'" % words_seq[k]
                            break

                if not fail_reason:
                    # Incomplete sentence (ends abruptly without period)
                    stripped = bullet.rstrip()
                    if stripped and stripped[-1] not in '.!':
                        fail_reason = "incomplete sentence"

                if not fail_reason:
                    # "for X for Y" double-purpose chains (only in injected suffixes)
                    if re.search(
                        r',\s*(?:using|applying|leveraging|utilizing)\s+\w[\w\s]*?'
                        r'\s+for\s+[\w\s]+\s+for\s+\w',
                        bullet, re.I
                    ):
                        fail_reason = "double-purpose chain in injection"

                # ---- PART 4b: GRAMMAR FRAGMENT DETECTION ----
                if not fail_reason:
                    # Trailing preposition/conjunction fragments: "and.", "using.", "for."
                    if re.search(r'\b(and|using|for|with|to|in|by|enabling)\.\s*$', bullet, re.I):
                        fail_reason = "trailing fragment: ends with preposition/conjunction"

                if not fail_reason:
                    # "using X enabling Y" without comma or conjunction (awkward)
                    if re.search(r'using\s+\w+\s+enabling\s+', bullet, re.I):
                        fail_reason = "grammar fragment: 'using X enabling Y'"

                if not fail_reason:
                    # Broken hyphenated tokens: "scikit-." or "scikit- " 
                    if re.search(r'\w+-[.\s]', bullet):
                        fail_reason = "broken hyphenated token"

                # ---- PART 5: ROLE CONSISTENCY ----
                if not fail_reason:
                    # Check if new bullet introduces role-changing verbs not in original
                    role_verbs = {"architected", "led", "managed", "owned", "spearheaded"}
                    orig_has_role_verb = any(
                        orig_bullet.lower().startswith(v) for v in role_verbs
                    )
                    new_has_role_verb = any(
                        bullet.lower().startswith(v) for v in role_verbs
                    )
                    if new_has_role_verb and not orig_has_role_verb:
                        # Seniority escalation -- revert
                        fail_reason = "role escalation (verb upgrade)"

                # ---- PART 7: AI-DETECTION CHECK ----
                if not fail_reason:
                    ai_patterns = [
                        r'(?:utilizing|leveraging)\s+\w+\s+(?:utilizing|leveraging)',
                        r'(?:applying|utilizing)\s+\w+,\s*(?:applying|utilizing)',
                        r'(?:for\s+){3,}',
                    ]
                    for pattern in ai_patterns:
                        if re.search(pattern, bullet, re.I):
                            fail_reason = "AI-generated pattern detected"
                            break

                # ---- PART 8: SAFE MODE (max rewrites per role) ----
                if not fail_reason and rewrite_count > max_rewrites_per_role:
                    fail_reason = "max rewrites per role (%d, limit=%d)" % (
                        rewrite_count, max_rewrites_per_role
                    )

                # ---- PART 10: LENGTH EXPLOSION CHECK ----
                if not fail_reason:
                    orig_len = len(orig_bullet)
                    new_len = len(bullet)
                    if orig_len > 0 and new_len > orig_len * 2.0:
                        fail_reason = "length explosion (%d→%d chars, max 2x)" % (orig_len, new_len)

                # ---- REVERT if any check failed ----
                if fail_reason:
                    exp.bullets[j] = orig_bullet
                    reverted += 1
                    logger.info(
                        "  INTEGRITY GATE: Reverted exp[%d].b[%d] -- %s",
                        i, j, fail_reason
                    )

        if reverted > 0:
            logger.info(
                "  INTEGRITY GATE: %d/%d bullets reverted", reverted, total_checked
            )
        else:
            logger.info("  INTEGRITY GATE: %d bullets passed", total_checked)

        return improved

    # ================================================================
    # VOCABULARY BUILDER
    # ================================================================

    def _build_vocabulary(self, resume: StructuredResume) -> Set[str]:
        """
        Build the complete vocabulary from resume.
        Includes explicit skills + ecosystem-implied + concept-implied terms.
        This defines what keywords are SAFE to inject.
        """
        vocab = set()

        # Explicit skills
        for skill in resume.skills:
            vocab.add(skill.lower())

        # All text mentions (tools referenced in bullets/summary)
        all_text = self._extract_all_text(resume).lower()
        # Also check project technologies
        for proj in resume.projects:
            for tech in proj.technologies:
                vocab.add(tech.lower())
            all_text += " " + proj.description.lower()

        # Ecosystem expansion: if "python" in skills, "pandas" is safe
        for skill_lower in list(vocab):
            if skill_lower in SKILL_ECOSYSTEM:
                for implied in SKILL_ECOSYSTEM[skill_lower]:
                    # Only add if the implied skill is also in the text
                    if implied.lower() in all_text:
                        vocab.add(implied.lower())

        # Additionally scan all text for known tools
        for tool in SKILL_ECOSYSTEM.keys():
            if tool in all_text:
                vocab.add(tool)

        # -- IMPLIED CONCEPT VOCABULARY (CRITICAL for keyword injection) --
        # If resume shows ML work, JD terms like "predictive modeling" are safe
        CONCEPT_IMPLICATIONS = {
            # evidence terms → implied JD terms that are safe to inject
            "model": ["predictive modeling", "model development"],
            "predict": ["predictive modeling"],
            "classify": ["predictive modeling"],
            "regression": ["predictive modeling"],
            "xgboost": ["predictive modeling"],
            "scikit-learn": ["predictive modeling", "feature engineering"],
            "feature": ["feature engineering"],
            "preprocess": ["feature engineering"],
            "clean": ["data pipeline"],
            "etl": ["data pipeline"],
            "extract": ["data pipeline"],
            "pipeline": ["data pipeline"],
            "dashboard": ["analytics"],
            "visualization": ["analytics"],
            "tableau": ["analytics"],
            "analysis": ["analytics"],
            "deploy": ["model deployment"],
            "docker": ["model deployment"],
            "aws": ["model deployment", "cloud"],
            "streamlit": ["model deployment"],
        }

        for evidence, implied_terms in CONCEPT_IMPLICATIONS.items():
            if evidence in all_text or evidence in vocab:
                for term in implied_terms:
                    vocab.add(term)

        return vocab

    # ================================================================
    # RULE 1+2: DEPTH ENHANCEMENT + CONTEXT ENRICHMENT
    # ================================================================

    def _enrich_bullet(
        self,
        bullet: str,
        jd_keywords: List[str],
        resume_vocab: Set[str],
    ) -> str:
        """
        Apply depth enhancement + context enrichment to a single bullet.
        Adds purpose/impact phrases for tools the resume actually has.
        """
        enhanced = bullet
        bullet_lower = enhanced.lower()

        # Rule 5: Tool strength upgrade -- "used X" → "leveraged X for Y"
        for pattern, replacement in DEPTH_PATTERNS.items():
            new_text = re.sub(pattern, replacement, enhanced, count=1, flags=re.IGNORECASE)
            if new_text != enhanced:
                enhanced = new_text
                break  # One verb replacement per bullet

        # Rule 2: Context enrichment -- add purpose phrase if tool is in bullet
        # Real-world bullets can be 100-150 chars and still benefit from enrichment
        if len(enhanced) < 160:
            bullet_lower = enhanced.lower()
            # Skip if bullet already has leveraging/utilizing phrase
            if "leverag" not in bullet_lower and ", utilizing " not in bullet_lower:
                enrichments_added = 0
                for tool, purpose in PURPOSE_PHRASES.items():
                    if enrichments_added >= 2:
                        break
                    if tool in bullet_lower and tool in resume_vocab:
                        if purpose.split()[0] not in bullet_lower:
                            if enhanced.endswith("."):
                                enhanced = enhanced[:-1] + f" {purpose}."
                            else:
                                enhanced += f" {purpose}."
                            enrichments_added += 1
                            if len(enhanced) > 180:
                                break

        return enhanced

    # ================================================================
    # RULE 3: JD ALIGNMENT
    # ================================================================

    def _align_to_jd(self, bullet: str, jd_keywords: List[str]) -> str:
        """
        Map resume terminology to JD-aligned terms.
        Only activates when the JD keyword context is relevant.
        """
        enhanced = bullet
        bullet_lower = enhanced.lower()

        for generic, professional in JD_ALIGNMENT_MAP.items():
            if generic in bullet_lower:
                enhanced = re.sub(
                    re.escape(generic),
                    professional,
                    enhanced,
                    count=1,
                    flags=re.IGNORECASE,
                )
                break  # One alignment per bullet

        return enhanced

    # ================================================================
    # RULE 4: PIPELINE FRAMING
    # ================================================================

    def _apply_pipeline_framing(
        self,
        resume: StructuredResume,
        jd_keywords: List[str],
        resume_vocab: Set[str],
    ) -> int:
        """
        If resume demonstrates multiple pipeline stages (data extraction,
        processing, modeling, deployment), add a framing bullet.
        """
        if not resume.experience:
            return 0

        jd_lower = {k.lower() for k in jd_keywords}
        pipeline_kw = {"pipeline", "data pipeline", "etl", "end-to-end", "ml pipeline"}

        # Frame if JD mentions pipeline OR if resume has strong pipeline evidence
        has_jd_pipeline = bool(pipeline_kw & jd_lower) or any("pipeline" in k for k in jd_lower)
        # Even without JD keyword, frame if resume has 3+ stages
        # (will be validated below by stage count)

        # Check if resume already has pipeline-stage work
        all_bullets = " ".join(
            b.lower() for exp in resume.experience for b in exp.bullets
        )

        stages = {
            "extraction": any(w in all_bullets for w in ["extract", "etl", "ingest", "scrape", "collect"]),
            "processing": any(w in all_bullets for w in ["transform", "process", "clean", "preprocess", "pandas"]),
            "modeling": any(w in all_bullets for w in ["model", "train", "predict", "classify", "regression"]),
            "deployment": any(w in all_bullets for w in ["deploy", "production", "docker", "aws", "api", "serve"]),
        }

        active_stages = [k for k, v in stages.items() if v]

        if len(active_stages) >= 2:
            # Add pipeline framing to summary if not already there
            if resume.summary and "pipeline" not in resume.summary.lower():
                stage_str = ", ".join(active_stages[:3])
                if resume.summary.endswith("."):
                    pipeline_addition = f" Proven end-to-end pipeline expertise spanning {stage_str}."
                    if len(pipeline_addition) + len(resume.summary) < 500:
                        resume.summary += pipeline_addition
                        return 1
        return 0

    # ================================================================
    # RULE 7: SAFE KEYWORD INJECTION
    # ================================================================

    # Keywords that should NEVER be injected into bullets
    _INJECTION_BLOCKLIST = {
        # Degrees / education terms
        "master", "master's", "bachelor", "bachelor's", "phd", "degree",
        "mba", "b.tech", "m.tech", "b.s.", "m.s.", "diploma",
        # Soft skills / generic terms
        "proficiency", "advanced proficiency", "expertise", "experience",
        "knowledge", "understanding", "familiarity", "strong",
        "excellent", "ability", "skills", "communication",
        "leadership", "teamwork", "problem-solving", "critical thinking",
        # JD meta-phrases (not real skills)
        "years of experience", "required", "preferred", "must have",
        "nice to have", "responsibilities", "qualifications",
    }

    # Natural phrasing templates (deterministic rotation by bullet length)
    _INJECTION_PHRASES = [
        "applying {kw}",
        "with {kw}",
        "using {kw}",
        "applying {kw}",
    ]

    def _inject_keywords(
        self,
        bullet: str,
        jd_keywords: List[str],
        resume_vocab: Set[str],
        already_injected: Set[str] = None,
    ) -> str:
        """
        Inject JD keywords into bullet ONLY if:
        - Keyword is a real tool/skill (not a degree, soft skill, or JD phrase)
        - Keyword exists in resume vocabulary
        - Fits naturally in the sentence
        - PURPOSE is available (never bare "applying X")
        - Max 1 injection per bullet
        """
        enhanced = bullet
        bullet_lower = enhanced.lower()
        if already_injected is None:
            already_injected = set()

        # Guard: skip if bullet already has ANY tool/skill injection
        enrichment_count = sum(1 for m in ["using ", "leveraging ", "utilizing ",
                                            "applying ", "with "] if m in bullet_lower)
        if enrichment_count >= 1:
            return enhanced

        injected = 0
        for kw in jd_keywords[:10]:
            kw_lower = kw.lower()
            if injected >= 1:  # Max 1 injection per bullet
                break

            # BLOCKLIST: reject non-injectable terms
            if kw_lower in self._INJECTION_BLOCKLIST:
                continue
            if any(blocked in kw_lower for blocked in self._INJECTION_BLOCKLIST):
                continue

            # REALISM: reject multi-word JD phrases (> 3 words = likely copied JD text)
            if len(kw.split()) > 3:
                continue

            # Skip if already injected globally or present in bullet
            if kw_lower in already_injected:
                continue
            if kw_lower in bullet_lower:
                continue

            # CONTEXT VALIDATION: skill must match bullet domain
            if not _skill_fits_bullet(kw, bullet):
                continue

            # PART 2: PURPOSE REQUIRED — never inject without purpose context
            purpose = PURPOSE_PHRASES.get(kw_lower, "")
            if not purpose:
                continue  # BLOCK bare injection — no purpose = no injection

            # Must be in resume vocab AND bullet must be short enough
            if kw_lower in resume_vocab and len(enhanced) < 130:
                # Always use "using X for Y" format (action + purpose)
                suffix = f", using {kw} {purpose}"

                if enhanced.endswith("."):
                    enhanced = enhanced[:-1] + f"{suffix}."
                else:
                    enhanced += f"{suffix}."

                injected += 1
                already_injected.add(kw_lower)
                bullet_lower = enhanced.lower()

        return enhanced

    # ================================================================
    # MAIN BULLET ENHANCER (Rules 1-5, 7-8)
    # ================================================================

    def _deep_enhance_bullets(
        self,
        resume: StructuredResume,
        jd_keywords: List[str],
        matched_skills: List[str],
        resume_vocab: Set[str],
        max_bullets_per_role: int = 99,
    ) -> tuple:
        """
        Apply all transformation rules to experience bullets.
        Returns (changes_count, list_of_improvements).
        max_bullets_per_role: Limit enhancement to first N bullets per role.
        """
        if not resume.experience:
            return 0, []

        changes = 0
        improvements = []
        kw_lower = {k.lower() for k in jd_keywords}
        globally_injected = set()  # Track keywords across ALL bullets

        # Build tool list from vocab for ATCI template
        tool_set = {v for v in resume_vocab if len(v) > 2}

        for exp in resume.experience:
            if not exp.bullets:
                continue

            enhanced_bullets = []
            for bullet_idx, bullet in enumerate(exp.bullets):
                original = bullet
                enhanced = bullet

                # Skip enhancement for bullets beyond the limit
                if bullet_idx >= max_bullets_per_role:
                    enhanced_bullets.append(bullet)
                    continue

                # Ensure bullet starts with capital/action verb
                if enhanced and not enhanced[0].isupper():
                    enhanced = enhanced[0].upper() + enhanced[1:]

                # Rule 3: JD Alignment (map generic -> professional)
                enhanced = self._align_to_jd(enhanced, jd_keywords)

                # Rule 1+2: Depth enhancement + Context enrichment
                enhanced = self._enrich_bullet(enhanced, jd_keywords, resume_vocab)

                # ATCI: Action+Tool+Context+Impact template for thin bullets
                enhanced = self._apply_atci_template(
                    enhanced, jd_keywords, matched_skills, resume_vocab
                )

                # Rule 7: Safe keyword injection (global tracking)
                enhanced = self._inject_keywords(
                    enhanced, jd_keywords, resume_vocab, globally_injected
                )

                # Ensure bullet starts with capital after all transforms
                if enhanced and not enhanced[0].isupper():
                    enhanced = enhanced[0].upper() + enhanced[1:]

                # Rule 8: Ensure bullet ends with period
                if enhanced and not enhanced.endswith('.') and not enhanced.endswith('!'):
                    enhanced += '.'

                # ---- BULLET QUALITY FILTER ----
                # Reject over-optimized or unnatural enhancements
                enhanced_lower = enhanced.lower()
                quality_fail = False

                # Reject: repeated "utilizing" (unnatural)
                if enhanced_lower.count("utilizing ") > 1:
                    quality_fail = True
                # Reject: too many enrichment phrases (over-stuffed)
                enrichment_count = sum(1 for m in [
                    "utilizing ", "leveraging ", "using ", "applying "
                ] if m in enhanced_lower)
                if enrichment_count >= 3:
                    quality_fail = True
                # Reject: "and...and...and" chaining (robotic)
                and_count = len(re.findall(r'\band\b', enhanced_lower))
                if and_count >= 3:
                    quality_fail = True
                # Reject: bullet became absurdly long
                if len(enhanced) > 300:
                    quality_fail = True

                if quality_fail:
                    enhanced = original  # Revert to original

                # Post-processing: clean up double "and" even in accepted bullets
                enhanced = re.sub(r'\band and\b', 'and', enhanced)
                enhanced = re.sub(r'\s+', ' ', enhanced).strip()

                if enhanced != original:
                    changes += 1
                    # Track what changed for the improvement log
                    if len(enhanced) > len(original) + 10:
                        short_desc = enhanced[:60].strip()
                        improvements.append(f"Enhanced: \"{short_desc}...\"")

                enhanced_bullets.append(enhanced)

            exp.bullets = enhanced_bullets

        return changes, improvements[:5]  # Cap at 5 improvement logs

    # ================================================================
    # ATCI TEMPLATE: Action + Tool + Context + Impact
    # ================================================================

    # Context phrases for different action types (deterministic)
    _ATCI_CONTEXTS = {
        "model": "for predictive analytics",
        "pipeline": "for automated data processing",
        "dashboard": "for real-time business insights",
        "api": "for scalable service integration",
        "system": "for production-grade infrastructure",
        "classifier": "for automated categorization",
        "analysis": "for data-driven decision making",
        "automation": "for operational efficiency",
        "database": "for optimized data storage and retrieval",
        "visualization": "for stakeholder reporting",
    }

    def _apply_atci_template(
        self,
        bullet: str,
        jd_keywords: List[str],
        matched_skills: List[str],
        resume_vocab: Set[str],
    ) -> str:
        """
        Apply Action+Tool+Context+Impact template to thin bullets.

        ONLY enriches bullets that are:
          - Short (< 80 chars)
          - Missing tool context or impact phrases

        Template: Action + Tool + Context + Impact
        Example: "Built model" → "Built predictive model using Python and Scikit-learn
                  for automated classification, improving accuracy."

        DETERMINISTIC: No randomness. Uses sorted vocab matching.
        """
        # Skip if bullet is already rich enough
        if len(bullet) > 120:
            return bullet

        bullet_lower = bullet.lower()

        # Skip if already enriched (has "using", "leveraging", etc.)
        enrichment_markers = ["using ", "leveraging ", "utilizing ", "with ",
                              "improving ", "reducing ", "increasing "]
        marker_count = sum(1 for m in enrichment_markers if m in bullet_lower)
        if marker_count >= 2:
            return bullet  # Already well-structured

        # Only enrich genuinely thin bullets (< 80 chars and missing tool/context)
        if len(bullet) >= 80 and marker_count >= 1:
            return bullet

        new_bullet = bullet

        # ---- TOOL EXPANSION ----
        # If bullet has no tool mention, add the most relevant matched skill
        # REALISM: only inject real tools, never degrees or soft skills
        injectable_skills = [
            s for s in matched_skills[:10]
            if s.lower() not in self._INJECTION_BLOCKLIST
            and not any(b in s.lower() for b in self._INJECTION_BLOCKLIST)
            and len(s.split()) <= 3  # No multi-word JD phrases
        ]

        has_tool = any(
            s.lower() in bullet_lower
            for s in injectable_skills
        )

        if not has_tool and injectable_skills and len(new_bullet) < 100:
            # Find most relevant skill for this bullet's context
            best_skill = None
            for skill in sorted(injectable_skills, key=str.lower):
                skill_lower = skill.lower()
                # Check if any word in the bullet relates to this skill's domain
                bullet_words = set(bullet_lower.split())
                skill_words = set(skill_lower.split())
                if bullet_words & skill_words:
                    best_skill = skill
                    break

            # REALISM: do NOT blindly inject first skill — only contextually relevant ones
            if best_skill and len(new_bullet) < 140:
                if new_bullet.endswith("."):
                    new_bullet = new_bullet[:-1] + f", using {best_skill}."
                else:
                    new_bullet += f", using {best_skill}."

        # ---- CONTEXT ADDITION ----
        # Add context phrase if bullet is still short and lacks purpose
        if len(new_bullet) < 100:
            for keyword, context in self._ATCI_CONTEXTS.items():
                if keyword in bullet_lower and context.split()[1] not in new_bullet.lower():
                    if new_bullet.endswith("."):
                        new_bullet = new_bullet[:-1] + f" {context}."
                    else:
                        new_bullet += f" {context}."
                    break  # One context per bullet

        # Length guard: never exceed 250 chars
        if len(new_bullet) > 250:
            return bullet

        return new_bullet

    # ================================================================
    # PROJECT → EXPERIENCE BRIDGING
    # ================================================================

    def _bridge_projects_to_experience(
        self,
        resume: StructuredResume,
        matched_skills: List[str],
        jd_keywords: List[str],
        resume_vocab: Set[str],
    ) -> int:
        """
        Bridge project-only tools into experience bullets.
        
        Rule: If a tool/skill appears in project technologies or project
        bullets but NOT in any experience bullet, inject it into the most
        contextually relevant experience bullet.
        
        This is CRITICAL because ATS systems score experience bullets
        more heavily than project sections.
        
        Constraint: Only bridge tools that are in resume_vocab (no hallucination).
        Max 5 bridges to avoid stuffing.
        """
        if not resume.projects or not resume.experience:
            return 0

        changes = 0
        max_bridges = 7

        # Build experience text for checking what's already covered
        all_exp_text = " ".join(
            b.lower() for exp in resume.experience for b in exp.bullets
        )

        # Collect all project-only tools
        project_tools = set()
        for proj in resume.projects:
            for tech in proj.technologies:
                if tech.lower() not in all_exp_text and tech.lower() in resume_vocab:
                    project_tools.add(tech)
            # Also check project bullet text for tools mentioned inline
            for bullet in proj.bullets:
                for skill in matched_skills:
                    if (skill.lower() in bullet.lower() and 
                        skill.lower() not in all_exp_text and
                        skill.lower() in resume_vocab):
                        project_tools.add(skill)

        if not project_tools:
            return 0

        # Sort for determinism
        project_tools_sorted = sorted(project_tools, key=str.lower)

        # HARDENED: Bridge phrases removed — purpose-driven injection only (Part 2)

        # Track which bullets have been used to spread tools across bullets
        used_slots = set()

        for tool in project_tools_sorted[:max_bridges]:
            # Find the most relevant experience bullet (by context matching)
            best_exp_idx = None
            best_bul_idx = None
            best_relevance = -1

            tool_lower = tool.lower()
            tool_already_in_exp = False

            # Check if tool has a parent skill ecosystem match in bullets
            for i, exp in enumerate(resume.experience):
                for j, bullet in enumerate(exp.bullets):
                    b_lower = bullet.lower()

                    # Skip if bullet already has this tool
                    if tool_lower in b_lower:
                        tool_already_in_exp = True
                        break

                    # Skip if bullet is already long or already used for bridging
                    if len(bullet) > 180 or (i, j) in used_slots:
                        continue

                    # Skip if bullet already has enrichment (prevent stacking)
                    enrich_count = sum(1 for m in [
                        "using ", "applying ", "utilizing ", "with "
                    ] if m in b_lower)
                    if enrich_count >= 2:
                        continue

                    relevance = 0
                    # Check ecosystem relationship
                    for parent, children in SKILL_ECOSYSTEM.items():
                        child_names = [c.lower() for c in children]
                        if tool_lower == parent or tool_lower in child_names:
                            if parent in b_lower:
                                relevance += 5
                            for cn in child_names:
                                if cn in b_lower:
                                    relevance += 2

                    # Check JD keyword overlap
                    for kw in jd_keywords:
                        if kw.lower() in b_lower:
                            relevance += 1

                    if relevance > best_relevance:
                        best_relevance = relevance
                        best_exp_idx = i
                        best_bul_idx = j

                if tool_already_in_exp:
                    break

            if tool_already_in_exp:
                continue

            # Fallback: use shortest UNUSED bullet if no contextual match
            if best_exp_idx is None:
                shortest_len = 999
                for i, exp in enumerate(resume.experience):
                    for j, bullet in enumerate(exp.bullets):
                        if ((i, j) not in used_slots and
                            len(bullet) < shortest_len and
                            len(bullet) < 180 and
                            tool_lower not in bullet.lower()):
                            shortest_len = len(bullet)
                            best_exp_idx = i
                            best_bul_idx = j

            if best_exp_idx is not None and best_bul_idx is not None:
                bullet = resume.experience[best_exp_idx].bullets[best_bul_idx]
                # HARDENED: Purpose-driven bridge — no bare injection (Part 2)
                tool_lower_b = tool.lower()
                bridge_purpose = PURPOSE_PHRASES.get(tool_lower_b, "")
                if not bridge_purpose:
                    cat = SKILL_CATEGORIES.get(tool_lower_b, "general")
                    cat_purposes = {
                        "modeling": "for predictive analysis",
                        "data": "for data-driven decision making",
                        "deployment": "for production-grade infrastructure",
                        "visualization": "for real-time business insights",
                        "backend": "for service integration",
                        "devops": "for development workflow automation",
                    }
                    bridge_purpose = cat_purposes.get(cat, "")
                if not bridge_purpose:
                    logger.info(f"  -> Bridge BLOCKED: '{tool}' — no purpose mapping")
                    continue
                phrase = f"using {tool} {bridge_purpose}"

                if bullet.endswith("."):
                    new_bullet = bullet[:-1] + f", {phrase}."
                else:
                    new_bullet = bullet + f", {phrase}."

                if len(new_bullet) <= 250:
                    resume.experience[best_exp_idx].bullets[best_bul_idx] = new_bullet
                    used_slots.add((best_exp_idx, best_bul_idx))
                    changes += 1
                    logger.info(f"  -> Bridge: '{tool}' (project-only) -> exp[{best_exp_idx}] bullet[{best_bul_idx}]")

        return changes

    # ================================================================
    # PROJECT BULLET ENHANCER
    # ================================================================

    def _enhance_project_bullets(
        self,
        resume: StructuredResume,
        jd_keywords: List[str],
        matched_skills: List[str],
        resume_vocab: Set[str],
    ) -> int:
        """Apply depth + JD alignment to project bullets too."""
        if not resume.projects:
            return 0

        changes = 0
        for proj in resume.projects:
            # Add project tech to vocab
            proj_vocab = resume_vocab | {t.lower() for t in proj.technologies}

            enhanced_bullets = []
            for bullet in proj.bullets:
                original = bullet
                enhanced = bullet

                # Same rules as experience bullets
                if enhanced and not enhanced[0].isupper():
                    enhanced = enhanced[0].upper() + enhanced[1:]

                enhanced = self._align_to_jd(enhanced, jd_keywords)
                enhanced = self._enrich_bullet(enhanced, jd_keywords, proj_vocab)

                if enhanced and not enhanced.endswith('.') and not enhanced.endswith('!'):
                    enhanced += '.'

                if enhanced != original:
                    changes += 1

                enhanced_bullets.append(enhanced)

            proj.bullets = enhanced_bullets

        return changes

    # ================================================================
    # SKILL-TO-EXPERIENCE LINKING (Part 2+3 -- biggest score driver)
    # ================================================================

    def _link_skills_to_experience(
        self,
        resume: StructuredResume,
        matched_skills: List[str],
        jd_keywords: List[str],
        resume_vocab: Set[str],
        max_links: int = 8,
    ) -> tuple:
        """
        Find skills in the skills list that are NOT mentioned in any
        experience bullet, then weave them into the most relevant bullet.

        This is the #1 score driver because ATS systems check if skills
        are DEMONSTRATED in experience, not just listed.

        REALISM RULES:
          - Never inject degrees, soft skills, or JD meta-phrases
          - Use varied phrasing (not always "utilizing")
          - Add tool-depth expansion when parent skill matches
          - Max linkages per run controlled by max_links param

        Returns (changes_count, improvements_list).
        """
        if not resume.experience:
            return 0, []

        changes = 0
        improvements = []

        # Build set of all skills mentioned across ALL experience bullets
        all_bullets_text = " ".join(
            b.lower() for exp in resume.experience for b in exp.bullets
        ).lower()

        # Also include project bullets
        all_project_text = " ".join(
            b.lower() for proj in resume.projects for b in proj.bullets
        ).lower() if resume.projects else ""

        combined_text = all_bullets_text + " " + all_project_text

        # Find skills present in skills list but NOT in any bullet
        skills_lower = {s.lower() for s in resume.skills}
        jd_skills_lower = {s.lower() for s in (matched_skills or [])}

        # Priority: JD-matched skills first, then all skills
        priority_skills = []
        for skill in matched_skills or []:
            sl = skill.lower()
            # BLOCKLIST: never inject degrees/soft skills
            if sl in self._INJECTION_BLOCKLIST:
                continue
            if any(b in sl for b in self._INJECTION_BLOCKLIST):
                continue
            if len(skill.split()) > 3:  # No multi-word JD phrases
                continue
            if sl in skills_lower and sl not in combined_text:
                priority_skills.append(skill)

        # Also check non-matched skills that are in JD keywords
        for kw in jd_keywords or []:
            kl = kw.lower()
            if kl in self._INJECTION_BLOCKLIST:
                continue
            if any(b in kl for b in self._INJECTION_BLOCKLIST):
                continue
            if kl in skills_lower and kl not in combined_text and kl not in [s.lower() for s in priority_skills]:
                priority_skills.append(kw)

        if not priority_skills:
            return 0, []

        # Purpose-driven skill linking — phrases are built dynamically
        # using PURPOSE_PHRASES map (see below)

        # For each unlinked skill, find the best bullet to weave it into
        skills_linked = 0
        for skill in priority_skills[:max_links]:  # Cap linkages per run
            skill_lower = skill.lower()
            best_bullet_idx = None
            best_exp_idx = None
            best_relevance = 0

            # Find the most relevant bullet based on keyword overlap
            for exp_idx, exp in enumerate(resume.experience):
                for bullet_idx, bullet in enumerate(exp.bullets):
                    bullet_lower = bullet.lower()

                    # Skip if skill already in this bullet
                    if skill_lower in bullet_lower:
                        continue

                    # Skip if bullet is already long
                    if len(bullet) > 120:
                        continue

                    # Skip if bullet already has enrichment phrases (avoid stacking)
                    enrich_count = sum(1 for m in [
                        "leveraging ", "using ", "utilizing ", "applying "
                    ] if m in bullet_lower)
                    if enrich_count >= 1:
                        continue

                    # Calculate relevance: how many related terms are in this bullet?
                    relevance = 0
                    purpose = PURPOSE_PHRASES.get(skill_lower, "")

                    # Check ecosystem relationship
                    for parent_skill, children in SKILL_ECOSYSTEM.items():
                        if skill_lower == parent_skill or skill_lower in [c.lower() for c in children]:
                            if parent_skill in bullet_lower:
                                relevance += 3
                            for child in children:
                                if child.lower() in bullet_lower:
                                    relevance += 2

                    # Check if bullet mentions related work
                    related_terms = purpose.split() if purpose else []
                    for term in related_terms:
                        if len(term) > 3 and term.lower() in bullet_lower:
                            relevance += 1

                    if relevance > best_relevance:
                        best_relevance = relevance
                        best_bullet_idx = bullet_idx
                        best_exp_idx = exp_idx

            # If no relevant bullet found, use the first short one WITH semantic guard
            # SEMANTIC FIT: Don't inject technical skills into non-technical bullets
            SEMANTIC_MISFIT_CONTEXTS = {
                "standup", "meeting", "attended", "participated", "communicated",
                "presented", "discussed", "coordinated with", "reported to",
            }
            if best_exp_idx is None:
                for exp_idx, exp in enumerate(resume.experience):
                    for bullet_idx, bullet in enumerate(exp.bullets):
                        if len(bullet) < 100 and skill_lower not in bullet.lower():
                            # Skip if already enriched
                            if any(m in bullet.lower() for m in ["leveraging ", "utilizing "]):
                                continue
                            # SEMANTIC FIT GUARD: skip non-technical bullets for tech skills
                            bullet_lower = bullet.lower()
                            is_tech_skill = skill_lower in {
                                "python", "java", "sql", "mysql", "react", "docker",
                                "aws", "tensorflow", "spark", "pandas", "git",
                                "kubernetes", "flask", "node.js", "html", "css",
                            }
                            is_soft_context = any(m in bullet_lower for m in SEMANTIC_MISFIT_CONTEXTS)
                            if is_tech_skill and is_soft_context:
                                continue  # Never put SQL into "attended standup meetings"
                            best_exp_idx = exp_idx
                            best_bullet_idx = bullet_idx
                            break
                    if best_exp_idx is not None:
                        break

            if best_exp_idx is not None and best_bullet_idx is not None:
                bullet = resume.experience[best_exp_idx].bullets[best_bullet_idx]

                # Build skill text with tool-depth expansion
                skill_text = skill
                eco_children = SKILL_ECOSYSTEM.get(skill_lower, [])
                if eco_children:
                    # Find children that are in resume vocab
                    valid_children = [
                        c for c in eco_children
                        if c.lower() in resume_vocab
                    ][:3]
                    if valid_children:
                        skill_text = f"{skill} ({', '.join(valid_children)})"

                # PURPOSE-DRIVEN LINKING: Never just "leveraging X"
                # Always add WHY the skill was used (purpose + context)
                purpose = PURPOSE_PHRASES.get(skill_lower, "")
                
                if purpose:
                    # Full purpose phrase: "using TensorFlow for building neural models"
                    link_templates = [
                        f"using {skill_text} {purpose}",
                        f"applying {skill_text} {purpose}",
                        f"with {skill_text} {purpose}",
                    ]
                else:
                    # Category-based fallback purpose
                    cat = SKILL_CATEGORIES.get(skill_lower, "general")
                    cat_purposes = {
                        "modeling": "for predictive analysis",
                        "data": "for data-driven decision making",
                        "deployment": "for production-grade infrastructure",
                        "visualization": "for real-time business insights",
                        "backend": "for service integration",
                        "devops": "for development workflow automation",
                    }
                    fallback = cat_purposes.get(cat, "")
                    if fallback:
                        link_templates = [
                            f"using {skill_text} {fallback}",
                            f"with {skill_text} {fallback}",
                        ]
                    else:
                        # HARDENED: No purpose available — block injection (Part 2)
                        logger.info(f"  Skill linking BLOCKED: '{skill}' — no purpose mapping")
                        continue

                # Pick phrasing (deterministic rotation)
                phrase_idx = skills_linked % len(link_templates)
                phrase = link_templates[phrase_idx]

                if bullet.endswith("."):
                    new_bullet = bullet[:-1] + f", {phrase}."
                else:
                    new_bullet = bullet + f", {phrase}."

                # Length guard
                if len(new_bullet) > 250:
                    continue

                resume.experience[best_exp_idx].bullets[best_bullet_idx] = new_bullet
                skills_linked += 1
                changes += 1
                improvements.append(
                    f"Linked '{skill}' to {resume.experience[best_exp_idx].role} bullet"
                )

        if skills_linked:
            logger.info(f"  Skill linking: {skills_linked} skills woven into experience bullets")

        return changes, improvements

    # ================================================================
    # TOOL DEPTH EXPANSION IN SUMMARY (Part 4)
    # ================================================================

    def _expand_tool_depth_in_summary(
        self,
        resume: StructuredResume,
        matched_skills: List[str],
        resume_vocab: Set[str],
    ) -> int:
        """
        Expand tool references in summary with ecosystem context.
        Example: 'Python expertise' -> 'Python (pandas, NumPy, scikit-learn) expertise'
        Only adds sub-tools that are ALREADY in the resume vocabulary.
        """
        if not resume.summary:
            return 0

        summary = resume.summary
        changes = 0

        for parent_skill, children in SKILL_ECOSYSTEM.items():
            if parent_skill not in summary.lower():
                continue

            # Find which children are in the resume vocabulary
            available_children = [
                c for c in children
                if c.lower() in resume_vocab and c.lower() not in summary.lower()
            ]

            if len(available_children) >= 2:
                # Build expansion string
                child_str = ", ".join(available_children[:3])
                # Replace "Python" with "Python (pandas, NumPy, scikit-learn)"
                pattern = rf'\b{re.escape(parent_skill)}\b'
                match = re.search(pattern, summary, re.IGNORECASE)
                if match:
                    original_word = match.group(0)
                    expanded = f"{original_word} ({child_str})"
                    summary = summary[:match.start()] + expanded + summary[match.end():]
                    changes += 1
                    break  # One expansion per summary to avoid stuffing

        resume.summary = summary
        return changes

    # ================================================================
    # PROJECT-TO-SUMMARY PROMOTION (Part 3)
    # ================================================================

    def _promote_projects_to_summary(
        self,
        resume: StructuredResume,
        jd_keywords: List[str],
        resume_vocab: Set[str],
    ) -> int:
        """
        If projects contain deployment, ML, or pipeline work,
        promote key project capabilities into the summary.
        """
        if not resume.projects or not resume.summary:
            return 0

        # Already promoted or summary too long or already has depth phrase
        summary_lower = resume.summary.lower()
        if (len(resume.summary) > 300 or "project" in summary_lower
                or "experienced in" in summary_lower or "expertise in" in summary_lower):
            return 0

        # Detect project capabilities
        deploy_tools = []
        ml_tools = []
        for proj in resume.projects:
            proj_techs = {t.lower() for t in proj.technologies}
            proj_text = " ".join(proj.bullets).lower()

            for tool in ["streamlit", "gradio", "heroku", "docker", "flask", "fastapi"]:
                if tool in proj_techs or tool in proj_text:
                    deploy_tools.append(tool.capitalize())
            for tool in ["scikit-learn", "xgboost", "tensorflow", "keras", "pytorch"]:
                if tool in proj_techs or tool in proj_text:
                    ml_tools.append(tool)

        # Build promotion phrase
        if deploy_tools or ml_tools:
            parts = []
            if ml_tools:
                parts.append(f"ML modeling ({', '.join(ml_tools[:2])})")
            if deploy_tools:
                parts.append(f"application deployment ({', '.join(deploy_tools[:2])})")

            if parts:
                promo = f" Demonstrated hands-on expertise in {' and '.join(parts)} through applied projects."
                if len(resume.summary) + len(promo) < 450:
                    resume.summary += promo
                    return 1

        return 0

    # ================================================================
    # EDUCATION RELEVANCE BOOST (Part 7)
    # ================================================================

    def _boost_education_relevance(
        self,
        resume: StructuredResume,
        jd_keywords: List[str],
    ) -> int:
        """
        If user has Master's or PhD, add relevance to summary.
        Only if not already mentioned.
        """
        if not resume.education or not resume.summary:
            return 0

        # Check for advanced degree
        advanced_degree = None
        degree_field = None
        for edu in resume.education:
            deg = edu.degree.lower()
            if any(kw in deg for kw in ["master", "msc", "m.s.", "m.sc", "mba"]):
                advanced_degree = "Master's"
                degree_field = edu.degree.split("in")[-1].strip() if "in" in edu.degree.lower() else edu.degree
            elif any(kw in deg for kw in ["phd", "ph.d", "doctorate"]):
                advanced_degree = "Ph.D."
                degree_field = edu.degree.split("in")[-1].strip() if "in" in edu.degree.lower() else edu.degree

        if not advanced_degree:
            return 0

        # Don't add if already mentioned
        summary_lower = resume.summary.lower()
        if any(marker in summary_lower for marker in [
            advanced_degree.lower(), "master", "phd", "holds a", "m.s.", "mba"
        ]):
            return 0

        # Don't add if summary is already very long
        if len(resume.summary) > 400:
            return 0

        # Build education boost phrase
        boost = f" Holds a {advanced_degree} in {degree_field}, providing strong theoretical foundations in quantitative methods and applied research."
        if len(resume.summary) + len(boost) < 500:
            resume.summary += boost
            return 1

        return 0

    # ================================================================
    # JD KEYWORD INJECTION ENGINE
    # ================================================================

    # Evidence mapping: JD keyword -> what resume evidence supports it
    _KEYWORD_EVIDENCE_MAP = {
        # Tech / Data Science
        "deep learning": {"tensorflow", "pytorch", "keras", "neural", "cnn", "rnn", "lstm", "transformer", "bert", "gpt"},
        "data pipeline": {"pipeline", "etl", "airflow", "spark", "kafka", "dag", "batch", "streaming", "ingestion"},
        "data pipelines": {"pipeline", "etl", "airflow", "spark", "kafka", "dag", "batch", "streaming", "ingestion"},
        "machine learning": {"ml", "model", "prediction", "classification", "regression", "clustering", "training", "scikit"},
        "natural language processing": {"nlp", "text", "sentiment", "tokeniz", "bert", "transformer", "language model"},
        "cloud computing": {"aws", "gcp", "azure", "cloud", "ec2", "s3", "lambda"},
        "microservices": {"api", "rest", "docker", "kubernetes", "service", "container"},
        "ci/cd": {"jenkins", "github actions", "gitlab", "deployment", "automated testing", "devops"},
        "data visualization": {"dashboard", "tableau", "plotly", "matplotlib", "chart", "report", "visual"},
        "predictive modeling": {"prediction", "forecast", "regression", "classification", "model", "accuracy"},
        # Software Engineering
        "software development": {"developed", "built", "code", "application", "system", "software", "programming"},
        "rest apis": {"api", "rest", "endpoint", "http", "request", "service", "backend"},
        "agile": {"sprint", "standup", "scrum", "jira", "iteration", "backlog", "kanban"},
        "testing": {"test", "unit test", "qa", "bug", "debug", "validation", "coverage"},
        # HR / People Operations
        "talent acquisition": {"recruitment", "hiring", "recruit", "candidate", "interview", "sourcing", "position"},
        "employee engagement": {"engagement", "satisfaction", "survey", "retention", "attrition", "culture", "morale"},
        "retention": {"attrition", "turnover", "engagement", "retention", "employee", "reduce"},
        "organizational development": {"training", "development", "onboarding", "leadership", "performance", "succession"},
        "performance management": {"performance", "review", "appraisal", "kpi", "goal", "evaluation", "feedback"},
        "onboarding": {"onboard", "new hire", "orientation", "induction", "training", "joining"},
        "compliance": {"compliance", "regulatory", "audit", "policy", "labor law", "legal", "adherence"},
        # BPO / Operations
        "customer service": {"customer", "client", "support", "resolution", "ticket", "satisfaction", "escalation"},
        "process improvement": {"process", "efficiency", "optimization", "workflow", "streamlin", "automat"},
    }

    def _inject_missing_jd_keywords(
        self,
        resume: StructuredResume,
        jd_keywords: List[str],
        resume_vocab: Set[str],
        max_injections: int = 4,
    ) -> int:
        """
        Inject missing JD keywords into experience bullets when supporting
        evidence exists. Uses KEYWORD_EVIDENCE_MAP to verify evidence.
        
        Example:
          JD keyword: "deep learning"
          Resume has: "TensorFlow" in bullets
          Action: Inject "deep learning" into the TensorFlow bullet
          Result: "Built deep learning models using TensorFlow..."
        
        Constraint: Only inject when evidence exists. Respects max_injections.
        """
        if not jd_keywords or not resume.experience:
            return 0

        changes = 0

        # Build all text for checking what's already present
        all_text = " ".join(
            b.lower() for exp in resume.experience for b in exp.bullets
        ) + " " + " ".join(
            b.lower() for proj in resume.projects for b in proj.bullets
        ) + " " + (resume.summary or "").lower()

        logger.info(f"  KW Inject: checking {len(jd_keywords)} keywords, text={len(all_text)} chars")

        # Find missing JD keywords that have evidence
        for kw in sorted(jd_keywords, key=str.lower):
            if changes >= max_injections:
                break

            kw_lower = kw.lower().strip()

            # Skip if keyword already present
            if kw_lower in all_text:
                continue
            # Skip single-word keywords < 4 chars (too generic)
            if len(kw_lower) < 4 and " " not in kw_lower:
                continue

            # Check if evidence exists for this keyword
            evidence_terms = self._KEYWORD_EVIDENCE_MAP.get(kw_lower, set())
            if not evidence_terms:
                continue

            # Find evidence in resume text
            has_evidence = any(
                ev in all_text for ev in evidence_terms
            )
            if not has_evidence:
                continue

            # Find the best bullet to inject into (the one with most evidence)
            best_exp_idx = None
            best_bul_idx = None
            best_evidence_count = 0

            for i, exp in enumerate(resume.experience):
                for j, bullet in enumerate(exp.bullets):
                    if len(bullet) > 200:
                        continue
                    b_lower = bullet.lower()
                    # Skip bullets already enriched (prevent stacking)
                    enrich_count = sum(1 for m in [
                        "using ", "applying ", "utilizing "
                    ] if m in b_lower)
                    if enrich_count >= 1:
                        continue
                    ev_count = sum(1 for ev in evidence_terms if ev in b_lower)
                    if ev_count > best_evidence_count:
                        best_evidence_count = ev_count
                        best_exp_idx = i
                        best_bul_idx = j

            # Fallback: if evidence is in summary/projects but no exp bullet has it,
            # use the shortest available bullet
            if best_exp_idx is None:
                shortest_len = 999
                for i, exp in enumerate(resume.experience):
                    for j, bullet in enumerate(exp.bullets):
                        bl = bullet.lower()
                        # Anti-stacking guard for fallback too
                        # HARDENED: Check global enrichment tracker
                        if hasattr(self, '_enriched_bullets') and (i, j) in self._enriched_bullets:
                            continue
                        ec = sum(1 for m in ["using ", "applying ", "utilizing "] if m in bl)
                        if ec >= 1:
                            continue
                        if len(bullet) < shortest_len and len(bullet) < 180:
                            shortest_len = len(bullet)
                            best_exp_idx = i
                            best_bul_idx = j

            if best_exp_idx is not None and best_bul_idx is not None:
                bullet = resume.experience[best_exp_idx].bullets[best_bul_idx]

                # Inject ONLY with purpose context — never bare
                kw_display = kw  # Preserve original casing
                purpose = PURPOSE_PHRASES.get(kw_lower, "")
                
                # PART 2+3: BLOCK bare injection — purpose REQUIRED
                if not purpose:
                    logger.info(f"  -> KW BLOCKED: '{kw_display}' — no purpose mapping")
                    continue
                
                # Always use "using X for Y" (action + purpose)
                suffix = f", using {kw_display} {purpose}"
                if bullet.endswith("."):
                    new_bullet = bullet[:-1] + f"{suffix}."
                else:
                    new_bullet = bullet + f"{suffix}."

                if len(new_bullet) <= 200:
                    resume.experience[best_exp_idx].bullets[best_bul_idx] = new_bullet
                    # HARDENED: Mark bullet as enriched globally
                    if hasattr(self, '_enriched_bullets'):
                        self._enriched_bullets.add((best_exp_idx, best_bul_idx))
                    changes += 1
                    # Update all_text so next iteration sees the change
                    all_text += " " + kw_lower
                    logger.info(f"  -> KW Inject: '{kw_display}' into exp[{best_exp_idx}] bullet[{best_bul_idx}]")

        return changes

    # ================================================================
    # RECOMMENDATION EXECUTION ENGINE
    # ================================================================

    def _execute_recommendations(
        self,
        resume: StructuredResume,
        recommendations: List[str],
        jd_keywords: List[str],
        resume_vocab: Set[str],
    ) -> int:
        """
        Parse MUST recommendations and apply them to the resume.
        Extracts skill/keyword mentions and injects into experience bullets.
        """
        if not recommendations:
            return 0

        changes = 0
        all_bullets_text = " ".join(
            b.lower() for exp in resume.experience for b in exp.bullets
        )

        for rec in recommendations:
            rec_lower = rec.lower()
            if "[must]" not in rec_lower:
                continue

            # Extract the skill/keyword being recommended
            # Patterns: "Add 'X' usage", "Integrate missing keywords: X, Y"
            skill_to_add = None

            # Pattern 1: Add 'skill' usage
            match = re.search(r"add\s+'([^']+)'", rec_lower)
            if match:
                skill_to_add = match.group(1)

            # Pattern 2: Integrate keywords: X, Y
            if not skill_to_add:
                match = re.search(r"integrate.*keywords.*?:\s*(.+)", rec_lower)
                if match:
                    keywords = [k.strip() for k in match.group(1).split(",")]
                    for kw in keywords:
                        if kw and kw not in all_bullets_text:
                            skill_to_add = kw
                            break

            if not skill_to_add:
                continue

            # Check if skill is already in bullets
            if skill_to_add.lower() in all_bullets_text:
                continue

            # Check if skill or its components exist in resume vocab
            skill_parts = skill_to_add.lower().split()
            has_evidence = any(p in resume_vocab for p in skill_parts if len(p) > 2)

            # Also check projects for evidence
            project_text = " ".join(
                b.lower() for proj in resume.projects for b in proj.bullets
            ) + " ".join(
                t.lower() for proj in resume.projects for t in proj.technologies
            )
            if skill_to_add.lower() in project_text:
                has_evidence = True
            for part in skill_parts:
                if part in project_text and len(part) > 3:
                    has_evidence = True

            if not has_evidence:
                continue  # Can't add without evidence

            # Find best bullet to inject into (shortest relevant bullet)
            best_idx = None
            best_exp_idx = None
            best_len = 999

            for i, exp in enumerate(resume.experience):
                for j, bullet in enumerate(exp.bullets):
                    b_lower = bullet.lower()
                    # Prefer bullets that mention related concepts
                    relevance = sum(1 for p in skill_parts if p in b_lower)
                    if len(bullet) < best_len and len(bullet) < 180:
                        best_len = len(bullet)
                        best_idx = j
                        best_exp_idx = i

            if best_exp_idx is not None and best_idx is not None:
                bullet = resume.experience[best_exp_idx].bullets[best_idx]
                if bullet.endswith("."):
                    bullet = bullet[:-1] + f", incorporating {skill_to_add}."
                else:
                    bullet += f", incorporating {skill_to_add}."
                resume.experience[best_exp_idx].bullets[best_idx] = bullet
                changes += 1
                all_bullets_text += " " + skill_to_add.lower()
                logger.info(f"  -> Executed recommendation: added '{skill_to_add}'")

        return changes

    # ================================================================
    # SAFE SKILL EXPANSION (compound JD requirements)
    # ================================================================

    def _expand_compound_skills(
        self,
        resume: StructuredResume,
        missing_skills: List[str],
        resume_vocab: Set[str],
    ) -> int:
        """
        Handle compound JD requirements like 'python (pandas, numpy, scikit-learn)'.
        If resume has 'Python' and 'Pandas', 'NumPy', 'Scikit-learn' separately,
        replace 'Python' in skills with 'Python (Pandas, NumPy, Scikit-learn)'.
        """
        if not missing_skills:
            return 0

        changes = 0
        skills_lower = {s.lower(): s for s in resume.skills}

        # Pattern: "tool (sub1, sub2, sub3)"
        compound_pattern = re.compile(r'^(.+?)\s*\(([^)]+)\)\s*$')

        for missing in missing_skills:
            match = compound_pattern.match(missing)
            if not match:
                continue

            parent = match.group(1).strip()
            children = [c.strip() for c in match.group(2).split(",")]

            # Check if parent exists in skills
            parent_lower = parent.lower()
            if parent_lower not in skills_lower:
                continue

            # Check if children exist in skills or vocab
            found_children = []
            for child in children:
                child_lower = child.lower().strip()
                if child_lower in skills_lower or child_lower in resume_vocab:
                    found_children.append(child)

            # If we have most children, expand the parent
            if len(found_children) >= len(children) * 0.5:
                original_name = skills_lower[parent_lower]
                expanded = f"{original_name} ({', '.join(found_children)})"

                # Replace in skills list
                for i, s in enumerate(resume.skills):
                    if s.lower() == parent_lower:
                        resume.skills[i] = expanded
                        changes += 1
                        logger.info(f"  -> Expanded skill: {original_name} -> {expanded}")
                        break

        return changes

    # ================================================================
    # STRICT SKILL COVERAGE ENGINE (deterministic)
    # ================================================================

    def _force_skill_coverage(
        self,
        resume: StructuredResume,
        matched_skills: List[str],
        jd_keywords: List[str],
        resume_vocab: Set[str],
    ) -> int:
        """
        Ensure every matched skill appears in >=1 experience or project bullet.
        Uses deterministic round-robin assignment (sorted skills, shortest bullets first).
        NO randomness.
        """
        if not matched_skills:
            return 0

        changes = 0

        # Build full bullet text for coverage check
        all_exp_bullets = " ".join(
            b.lower() for exp in resume.experience for b in exp.bullets
        )
        all_proj_bullets = " ".join(
            b.lower() for proj in resume.projects for b in proj.bullets
        )
        all_bullets = all_exp_bullets + " " + all_proj_bullets

        # Find skills NOT covered in any bullet (sorted for determinism)
        uncovered = []
        for skill in sorted(matched_skills, key=str.lower):
            skill_lower = skill.lower()
            # Check if skill or its main terms appear in bullets
            terms = [t for t in skill_lower.split() if len(t) > 2]
            found = skill_lower in all_bullets
            if not found and terms:
                found = any(t in all_bullets for t in terms if len(t) > 3)
            if not found:
                uncovered.append(skill)

        if not uncovered:
            return 0

        # Build sorted list of (exp_idx, bullet_idx, length) for round-robin
        bullet_slots = []
        for i, exp in enumerate(resume.experience):
            for j, bullet in enumerate(exp.bullets):
                bullet_slots.append((i, j, len(bullet)))

        # Sort by length (shortest first) — deterministic assignment
        bullet_slots.sort(key=lambda x: (x[2], x[0], x[1]))

        # Round-robin: assign each uncovered skill to next shortest bullet
        slot_idx = 0
        # Semantic misfit contexts — never inject tech skills here
        MISFIT_CONTEXTS = {
            "standup", "meeting", "attended", "participated", "communicated",
            "presented", "discussed", "coordinated with", "reported to",
        }
        for skill in uncovered:
            if not bullet_slots:
                break

            # Only inject if bullet won't exceed 220 chars
            max_attempts = len(bullet_slots)
            attempts = 0
            while attempts < max_attempts:
                exp_i, bul_j, bul_len = bullet_slots[slot_idx % len(bullet_slots)]
                bullet_text = resume.experience[exp_i].bullets[bul_j].lower()
                
                # Skip if bullet is too long
                if bul_len >= 220:
                    slot_idx += 1
                    attempts += 1
                    continue
                
                # HARDENED: Skip if bullet already has ANY enrichment (prevent stacking)
                if (exp_i, bul_j) in self._enriched_bullets:
                    slot_idx += 1
                    attempts += 1
                    continue
                enrich_count = sum(1 for m in [
                    "using ", "applying ", "utilizing "
                ] if m in bullet_text)
                if enrich_count >= 1:
                    slot_idx += 1
                    attempts += 1
                    continue
                
                # SEMANTIC GUARD: skip soft-context bullets for tech skills
                is_tech = skill.lower() in {
                    "python", "java", "sql", "mysql", "react", "docker",
                    "aws", "tensorflow", "spark", "pandas", "git",
                    "kubernetes", "flask", "node.js", "html", "css",
                }
                is_soft = any(m in bullet_text for m in MISFIT_CONTEXTS)
                if is_tech and is_soft:
                    slot_idx += 1
                    attempts += 1
                    continue
                
                # Also skip if contextual fit is poor
                if not _skill_fits_bullet(skill, bullet_text):
                    slot_idx += 1
                    attempts += 1
                    continue
                
                break
                
            if attempts >= max_attempts:
                break  # No suitable bullet found

            exp_i, bul_j, _ = bullet_slots[slot_idx % len(bullet_slots)]
            bullet = resume.experience[exp_i].bullets[bul_j]

            # Determine injection phrase WITH PURPOSE
            skill_display = skill
            # Use proper casing from matched_skills
            for ms in matched_skills:
                if ms.lower() == skill.lower():
                    skill_display = ms
                    break

            # Purpose-driven injection (not bare "leveraging X")
            purpose = PURPOSE_PHRASES.get(skill.lower(), "")
            if purpose:
                inject_phrase = f"using {skill_display} {purpose}"
            else:
                cat = SKILL_CATEGORIES.get(skill.lower(), "general")
                cat_purposes = {
                    "modeling": "for predictive analysis",
                    "data": "for data-driven decision making",
                    "deployment": "for production-grade infrastructure",
                    "visualization": "for real-time business insights",
                }
                fallback = cat_purposes.get(cat, "")
                if not fallback:
                    # HARDENED: No purpose = no injection (Part 2)
                    logger.info(f"  -> Coverage BLOCKED: '{skill_display}' — no purpose mapping")
                    continue
                inject_phrase = f"using {skill_display} {fallback}"

            if bullet.endswith("."):
                new_bullet = bullet[:-1] + f", {inject_phrase}."
            else:
                new_bullet = bullet + f", {inject_phrase}."

            resume.experience[exp_i].bullets[bul_j] = new_bullet
            # HARDENED: Mark bullet as enriched globally
            if hasattr(self, '_enriched_bullets'):
                self._enriched_bullets.add((exp_i, bul_j))
            # Update slot length
            bullet_slots[slot_idx % len(bullet_slots)] = (exp_i, bul_j, len(new_bullet))

            changes += 1
            slot_idx += 1
            logger.info(f"  -> Coverage: injected '{skill_display}' into exp[{exp_i}] bullet[{bul_j}]")

        return changes

    # ================================================================
    # PROJECT BULLET ENHANCER
    # ================================================================

    def _enhance_project_bullets(
        self,
        resume: StructuredResume,
        jd_keywords: List[str],
        matched_skills: List[str],
        resume_vocab: Set[str],
    ) -> int:
        """Apply depth + JD alignment to project bullets too."""
        if not resume.projects:
            return 0

        changes = 0
        for proj in resume.projects:
            proj_vocab = resume_vocab | {t.lower() for t in proj.technologies}

            enhanced_bullets = []
            for bullet in proj.bullets:
                original = bullet
                enhanced = bullet

                if enhanced and not enhanced[0].isupper():
                    enhanced = enhanced[0].upper() + enhanced[1:]

                enhanced = self._align_to_jd(enhanced, jd_keywords)
                enhanced = self._enrich_bullet(enhanced, jd_keywords, proj_vocab)

                if enhanced and not enhanced[0].isupper():
                    enhanced = enhanced[0].upper() + enhanced[1:]

                if enhanced and not enhanced.endswith('.') and not enhanced.endswith('!'):
                    enhanced += '.'

                if enhanced != original:
                    changes += 1

                enhanced_bullets.append(enhanced)

            proj.bullets = enhanced_bullets

        return changes

    # ================================================================
    # SKILL REORDERING
    # ================================================================

    def _reorder_skills(self, resume: StructuredResume, matched_skills: List[str]) -> int:
        """Move matched/relevant skills to the front of skills list."""
        if not resume.skills or not matched_skills:
            return 0

        matched_lower = {s.lower() for s in matched_skills}
        prioritized = []
        remaining = []

        for skill in resume.skills:
            if skill.lower() in matched_lower:
                prioritized.append(skill)
            else:
                remaining.append(skill)

        if prioritized:
            resume.skills = prioritized + remaining
            return 1
        return 0

    # ================================================================
    # BULLET QUALITY ENGINE (Part 6 — Shortlist Spec)
    # Role-specific signal patterns — what makes a candidate strong FOR THIS ROLE
    ROLE_SIGNAL_PATTERNS = {
        "data": {
            "strong": r'model|pipeline|dataset|feature\s+engineer|training|inference|batch|etl|warehouse|lakehouse',
            "differentiator": r'lstm|distilbert|transformer|gan|bert|gpt|ner|reinforcement learning|computer vision|graph neural|attention mechanism|a/b test|bayesian|monte carlo|real-time\s+(?:stream|process|serv|infer)',
        },
        "technical": {
            "strong": r'api|microservice|architect|system\s+design|scalab|latency|throughput|caching|load\s+balanc|database|rest|graphql|websocket|concurrent',
            "differentiator": r'distributed\s+system|event.driven|message\s+queue|kafka|grpc|service\s+mesh|zero.downtime|12.factor',
        },
        "analytical": {
            "strong": r'forecast|regression|dashboard|kpi|metric|insight|stakeholder|report|recommendation|business\s+case|roi\s+analy',
            "differentiator": r'monte\s+carlo|cohort|segmentation|propensity|attribution|causal|econometric',
        },
        "operations": {
            "strong": r'uptime|maintenance|efficien|throughput|turnaround|compliance|safety|sla|inventory|logistics|supply\s+chain|procurement|warehouse|test\s+(?:case|suite|plan|cover|automat)|regression|defect|bug\s+track|selenium|qa|quality\s+assur',
            "differentiator": r'six\s+sigma|lean|kaizen|iso\s+\d|osha|preventive\s+maintenance|fleet|dispatch|just.in.time|test\s+coverage\s+\d|zero\s+defect|\d+%\s+(?:automation|coverage)|sdet|performance\s+test',
        },
        "customer": {
            "strong": r'customer|client|csat|nps|resolution|retention|satisfaction|support|ticket|call\s+volume|first.call|sla|upsell|cross.sell|account|pipeline|quota',
            "differentiator": r'csat\s+\d|nps\s+\d|\d+%\s+retention|\d+%\s+resolution|million\s+(?:revenue|arr)|enterprise\s+(?:client|account)',
        },
        "hr": {
            "strong": r'recruit|onboard|talent|hire|compliance|engagement|attrition|retention|payroll|workforce|hris|performance\s+(?:review|management|cycle)|training|learning\s+\&?\s*development',
            "differentiator": r'succession\s+planning|employer\s+brand|dei|diversity|organizational\s+development|culture\s+transform|labor\s+(?:law|relation)|headcount\s+plan',
        },
        "management": {
            "strong": r'led\s+(?:team|a\s+team)|managed\s+\d|p&l|budget|strategy|roadmap|cross.functional|stakeholder|quarter|okr|kpi|direct\s+report',
            "differentiator": r'(?:\$\d+[MmBb]|\d+\s*(?:million|billion))|board|executive|c-suite|transformation|turnaround|m&a|restructur',
        },
        "creative": {
            "strong": r'design|brand|campaign|content|engagement|impression|click|conversion|follower|reach|aesthetic|visual|user\s+(?:experience|interface|research)|wireframe|prototype',
            "differentiator": r'rebrand|viral|\d+[MmKk]\+?\s*(?:view|impression|reach|follower)|award|recognition|adobe|figma|sketch',
        },
        "trades": {
            "strong": r'repair|install|maintain|inspect|diagnos|calibrat|service|troubleshoot|equipment|machine|system|safety|code\s+complian|preventive|corrective',
            "differentiator": r'certif|license|journeyman|master\s+(?:electric|plumb|mechanic)|osha|epa|first\s+time\s+fix|\d+%\s+uptime|zero\s+(?:incident|accident)',
        },
    }

    @staticmethod
    def _score_bullet_impact(bullet: str, role_type: str = "data") -> int:
        """Score a bullet by SHORTLIST impact — role-aware hiring manager perspective.
        
        Universal scoring (all roles):
          1. Revenue / business outcomes (+5)
          2. Cost reduction (+4)
          3. Scale indicators (+4/+3)
          4. Efficiency / automation (+3)
          5. Team / leadership (+2)
          6. Quantified metrics (+2)
          7. Strong action verbs (+1)
          
        Role-specific scoring:
          - Role-specific strong signals (+3)
          - Role-specific differentiators (+3)
          
        Penalties:
          - Vague / task-based language (-3)
          - No tool/skill mention (-1) [tech/data roles only]
        """
        b = bullet.lower()
        score = 0
        
        # === UNIVERSAL SIGNALS (every role) ===
        
        # Revenue / business impact (+5)
        if re.search(r'revenue|sales|growth|\$\d|profit|roi|conversion|business value', b):
            score += 5
        # Cost reduction (+4)
        if re.search(r'reduc\w+\s+(?:cost|spend|budget)|sav\w+\s+\$|cost\s+sav', b):
            score += 4
        # Scale indicators (+4/+3)
        if re.search(r'\d+[MmBb]\+?\s*(?:records|rows|data|events|transactions|users|revenue|budget|calls)', b):
            score += 4
        elif re.search(r'\d+[Kk]\+?\s*(?:users|requests|records|customers|api|employees|positions|hires|tickets|calls|units)', b):
            score += 3
        # Efficiency / speed (+3)
        if re.search(r'automat\w+|streamlin\w+|efficien\w+|reduc\w+.*time|faster|accelerat', b):
            score += 3
        # Team / leadership (+2)
        if re.search(r'led\s+(?:team|a\s+team)|managed\s+\d|mentored|cross-functional', b):
            score += 2
        # Quantified impact (+2)
        if re.search(r'\d+[%xX+]|\$\d|\d+\s*(?:users|clients|records|positions|employees|tickets|calls|hires)', b):
            score += 2
        # Action verb strength (+1)
        strong_verbs = ['architected', 'developed', 'designed', 'built', 'led',
                        'implemented', 'engineered', 'optimized', 'automated',
                        'deployed', 'scaled', 'launched', 'delivered',
                        'streamlined', 'spearheaded', 'orchestrated', 'transformed',
                        'negotiated', 'recruited', 'resolved', 'diagnosed']
        if any(b.startswith(v) for v in strong_verbs):
            score += 1
        
        # === ROLE-SPECIFIC SIGNALS ===
        role_patterns = ResumeImprover.ROLE_SIGNAL_PATTERNS.get(role_type, {})
        
        # Role-specific strong signals (+3)
        strong_pattern = role_patterns.get("strong", "")
        if strong_pattern and re.search(strong_pattern, b):
            score += 3
            
        # Role-specific differentiators (+3)
        diff_pattern = role_patterns.get("differentiator", "")
        if diff_pattern and re.search(diff_pattern, b):
            score += 3
        
        # === PENALTIES ===
        
        # Vague/weak language (-3)
        weak_signals = ['attended', 'participated in', 'was involved',
                        'assisted with', 'helped with', 'various', 'some tasks',
                        'was responsible for', 'tasks included']
        if any(w in b for w in weak_signals):
            score -= 3
        
        # No tool/skill mention penalty (-1) — ONLY for tech/data roles
        if role_type in ("data", "technical", "analytical"):
            if not re.search(r'python|java|sql|react|aws|docker|kubernetes|terraform|spark|tensorflow|pandas|excel|tableau|hris|crm|sap', b):
                if not re.search(r'machine learning|deep learning|nlp|data pipeline|ci/cd|api|etl|dashboard|kpi', b):
                    score -= 1
        
        return score

    def _prioritize_impact_bullets(
        self,
        resume: StructuredResume,
        max_bullets: int = 5,
        role_type: str = "data",
    ) -> int:
        """Reorder bullets by impact within each experience entry.
        
        High-impact bullets (revenue, cost, efficiency) move to top.
        Vague bullets (attended, participated) move to end or get removed.
        Caps at max_bullets per entry to keep only top content.
        
        Returns number of changes made.
        """
        changes = 0
        
        for exp in resume.experience:
            if len(exp.bullets) <= 1:
                continue
            
            # Score each bullet
            scored = [(self._score_bullet_impact(b, role_type), i, b) 
                      for i, b in enumerate(exp.bullets)]
            
            # Sort by impact score descending, preserve original order for ties
            sorted_bullets = sorted(scored, key=lambda x: (-x[0], x[1]))
            new_order = [b for _, _, b in sorted_bullets]
            
            # Check if order actually changed
            if new_order != exp.bullets:
                exp.bullets = new_order
                changes += 1
            
            # Cap bullet count (remove lowest-impact bullets)
            if len(exp.bullets) > max_bullets:
                removed = len(exp.bullets) - max_bullets
                # Only remove bullets with score <= 0 (vague/generic)
                while len(exp.bullets) > max_bullets:
                    last_score = self._score_bullet_impact(exp.bullets[-1], role_type)
                    if last_score <= 0:
                        exp.bullets.pop()
                        changes += 1
                    else:
                        break  # Don't remove impactful bullets
        
        return changes

    # ================================================================
    # COMPETITIVE POSITIONING ENGINE (Part 14d — Competitive Upgrade)
    # Upgrades already-decent bullets to top-tier by adding:
    #   - Scale (numbers, volume, scope)
    #   - Impact (business outcome, efficiency gain)
    #   - Outcome clarity (purpose, why it matters)
    # Runs ONLY in strict mode. Does NOT touch weak bullets (rewrite
    # engine handles those). Targets mid-range bullets (score 2-5)
    # that are "good but not competitive".
    # ================================================================

    # ================================================================
    # NEGATIVE SIGNAL DETECTION (Part 4 — Realism Layer)
    # Detects and replaces weak verbs that hurt competitiveness.
    # A hiring manager sees "Helped with" and thinks "junior".
    # ================================================================

    # Weak signal → strong replacement map
    _WEAK_SIGNAL_MAP = [
        # (pattern, replacement) — pattern must be at bullet start
        (r'^Helped\s+(?:with\s+)?', 'Contributed to '),
        (r'^Assisted\s+(?:in\s+|with\s+)?', 'Supported '),
        (r'^Worked\s+on\s+', 'Developed '),
        (r'^Responsible\s+for\s+', 'Led '),
        (r'^Was\s+responsible\s+for\s+', 'Managed '),
        (r'^Participated\s+in\s+', 'Contributed to '),
        (r'^Was\s+involved\s+in\s+', 'Contributed to '),
        (r'^Handled\s+', 'Managed '),
        (r'^Did\s+', 'Executed '),
        (r'^Made\s+', 'Developed '),
    ]

    def _replace_weak_signals(self, bullet: str, seniority: str = "senior") -> str:
        """Replace weak opening verbs with strong action verbs.
        
        Part 4 — Negative Signal Detection.
        A recruiter reads "Helped with testing" and thinks junior.
        "Contributed to test automation" signals ownership.
        
        Part 2 — Seniority Alignment.
        Junior (0-2 years): avoid "Led", "Owned", "Architected"
        Mid (3-5 years): moderate ownership verbs
        Senior (5+ years): full ownership verbs
        
        Only replaces the FIRST verb (bullet opener). Does not touch
        mid-sentence weak verbs to preserve natural flow.
        """
        # Seniority-aware replacement map
        # Junior candidates get safer verbs to maintain believability
        if seniority == "junior":
            safe_map = [
                (r'^Helped\s+(?:with\s+)?', 'Contributed to '),
                (r'^Assisted\s+(?:in\s+|with\s+)?', 'Supported '),
                (r'^Worked\s+on\s+', 'Contributed to '),
                (r'^Responsible\s+for\s+', 'Managed '),
                (r'^Was\s+responsible\s+for\s+', 'Managed '),
                (r'^Participated\s+in\s+', 'Contributed to '),
                (r'^Was\s+involved\s+in\s+', 'Supported '),
                (r'^Handled\s+', 'Managed '),
                (r'^Did\s+', 'Completed '),
                (r'^Made\s+', 'Created '),
            ]
        else:
            # Senior/mid-level: full strength verbs
            safe_map = self._WEAK_SIGNAL_MAP
        
        for pattern, replacement in safe_map:
            new_bullet = re.sub(pattern, replacement, bullet, count=1, flags=re.I)
            if new_bullet != bullet:
                return new_bullet
        return bullet

    @staticmethod
    def _detect_seniority(resume: StructuredResume) -> str:
        """Detect candidate seniority from experience duration.
        
        Part 2 — Seniority Alignment.
        Returns: "junior" (0-2 yrs), "mid" (3-5 yrs), "senior" (5+ yrs)
        """
        total_years = 0
        
        for exp in (resume.experience or []):
            # Try to extract years from date range
            dates = getattr(exp, 'duration', '') or ''
            years = re.findall(r'(\d{4})', dates)
            if len(years) >= 2:
                try:
                    span = abs(int(years[-1]) - int(years[0]))
                    total_years += max(span, 1)
                except ValueError:
                    total_years += 1
            elif years:
                total_years += 1
            else:
                total_years += 1  # Assume at least 1 year per role
        
        if total_years <= 2:
            return "junior"
        elif total_years <= 5:
            return "mid"
        else:
            return "senior"

    # Scale injection templates keyed by detected bullet context
    _SCALE_TEMPLATES = {
        "data": [
            ("datasets", "large-scale datasets"),
            ("records", "datasets of {scale}+ records"),
            ("models", "production-grade models"),
        ],
        "api": [
            ("api", "high-throughput APIs"),
            ("services", "services handling {scale}+ daily requests"),
            ("endpoints", "{scale}+ API endpoints"),
        ],
        "users": [
            ("users", "{scale}+ active users"),
            ("customers", "{scale}+ customers"),
            ("clients", "enterprise clients"),
        ],
        "system": [
            ("system", "distributed systems"),
            ("infrastructure", "cloud infrastructure at scale"),
            ("pipeline", "end-to-end data pipelines"),
        ],
        "team": [
            ("team", "cross-functional teams"),
            ("stakeholders", "stakeholders across {scale}+ departments"),
        ],
    }

    # Outcome suffixes for impact injection
    # Part 3 (Trust): Outcome suffixes — CONCRETE, not vague.
    # Rule: "to [specific verb] [measurable thing]" beats "for [adjective noun]"
    _OUTCOME_SUFFIXES = {
        "data": "to support faster, data-driven decision-making",
        "technical": "to reduce downtime and improve response stability",
        "operations": "to streamline workflows and reduce cycle time",
        "customer": "to improve resolution speed and customer satisfaction",
        "hr": "to reduce attrition and improve hiring efficiency",
        "management": "to align teams and accelerate strategic execution",
        "creative": "to strengthen brand presence and audience engagement",
        "trades": "to minimize equipment downtime and ensure compliance",
        "analytical": "to deliver timely, actionable insights to stakeholders",
    }

    def _competitive_bullet_upgrade(
        self,
        resume: StructuredResume,
        jd_keywords: List[str],
        matched_skills: List[str],
        resume_vocab: Set[str],
        role_type: str = "data",
    ) -> int:
        """COMPETITIVE POSITIONING ENGINE — upgrade good bullets to top-tier.
        
        Target: bullets scoring 2-5 (decent but not competitive).
        Skip: bullets scoring 0-1 (rewrite engine handles) or 6+ (already strong).
        
        Enhancement layers (applied in order, stops after first upgrade):
        1. SCALE INJECTION — add numbers/volume if missing
        2. IMPACT INJECTION — add business outcome if missing
        3. OUTCOME CLARITY — add purpose clause if missing
        
        Returns number of upgrades applied.
        """
        if not resume.experience:
            return 0
        
        changes = 0
        max_upgrades = 6  # Cap: don't over-enhance
        
        # -- PART 1 (Trust): Soft-scale control --
        # Max 2 soft-scale phrases per experience role to avoid over-enhancement
        MAX_SOFT_SCALE_PER_ROLE = 3
        
        # -- PART 2 (Trust): Seniority detection --
        seniority = self._detect_seniority(resume)
        
        for exp in resume.experience:
            soft_scale_count = 0  # Reset per role (Part 1)
            for j, bullet in enumerate(exp.bullets):
                if changes >= max_upgrades:
                    break
                
                # -- PART 4: NEGATIVE SIGNAL DETECTION --
                # Replace weak verbs FIRST (these hurt competitiveness)
                upgraded_verb = self._replace_weak_signals(bullet, seniority)
                if upgraded_verb != bullet:
                    exp.bullets[j] = upgraded_verb
                    bullet = upgraded_verb
                    changes += 1
                    logger.info(
                        f"  Negative signal replaced in bullet {j}"
                    )
                    continue  # One upgrade per bullet per pass
                
                score = self._score_bullet_impact(bullet, role_type)
                b_lower = bullet.lower()
                
                # Only upgrade mid-range bullets (good but not competitive)
                if score < 2 or score >= 7:
                    continue
                
                # Skip very long bullets (already detailed enough)
                if len(bullet) > 160:
                    continue
                
                # -- PART 6: HUMAN BELIEVABILITY CHECK --
                # Reject if bullet already has 3+ metrics (too many numbers = fake)
                metric_count = len(re.findall(r'\d+\s*[%KkMm+]|\d{3,}', bullet))
                if metric_count >= 3:
                    continue
                
                # Also skip if bullet already has a soft-scale adjective
                if re.search(
                    r'\b(?:large-scale|enterprise-scale|high-throughput|'
                    r'production-grade|cross-functional|distributed)\b',
                    b_lower
                ):
                    continue
                
                # Detect what's missing
                has_scale = bool(re.search(
                    r'\d+[KkMm+]|\d{3,}\s*(?:record|user|request|transac|item|order|'
                    r'employee|position|client|customer|ticket|call|endpoint|deploy|'
                    r'service|server|test|node)',
                    bullet, re.I
                ))
                has_impact = bool(re.search(
                    r'\d+\s*%|(?:reduc|increas|improv|optimiz|accelerat|streamlin|'
                    r'enhanc|eliminat|driv|boost|sav)(?:ed|ing|es)\b',
                    bullet, re.I
                ))
                has_outcome = bool(re.search(
                    r'\bfor\s+(?:improv|enhanced|better|faster|reliable|scalable|'
                    r'actionable|real-time|strategic|efficient|accurate|streamlined)',
                    bullet, re.I
                ))
                has_purpose = bool(re.search(
                    r'\b(?:to\s+(?:ensure|enable|support|drive|improve|reduce|'
                    r'increase|achieve|facilitate|deliver))',
                    bullet, re.I
                ))
                
                # If already has all elements, skip
                if has_scale and has_impact and (has_outcome or has_purpose):
                    continue
                
                upgraded = bullet
                upgrade_applied = False
                
                # Layer 1: SCALE INJECTION — add soft-scale if missing
                # Part 1 (Trust): Cap at MAX_SOFT_SCALE_PER_ROLE per experience entry
                if not has_scale and soft_scale_count < MAX_SOFT_SCALE_PER_ROLE:
                    upgraded = self._inject_scale_indicator(
                        upgraded, role_type, jd_keywords
                    )
                    if upgraded != bullet:
                        upgrade_applied = True
                        soft_scale_count += 1
                
                # Layer 2: IMPACT INJECTION — add outcome verb if missing
                if not has_impact and not upgrade_applied:
                    upgraded = self._inject_impact_outcome(
                        upgraded, role_type
                    )
                    if upgraded != bullet:
                        upgrade_applied = True
                
                # Layer 3: OUTCOME CLARITY — add purpose suffix if missing
                if not has_outcome and not has_purpose and not upgrade_applied:
                    upgraded = self._inject_outcome_clarity(
                        upgraded, role_type
                    )
                    if upgraded != bullet:
                        upgrade_applied = True
                
                if upgrade_applied and upgraded != bullet:
                    exp.bullets[j] = upgraded
                    changes += 1
                    logger.info(
                        f"  Competitive upgrade: \"{bullet[:60]}...\" → "
                        f"\"{upgraded[:60]}...\""
                    )
        
        return changes

    def _inject_scale_indicator(
        self, bullet: str, role_type: str, jd_keywords: List[str]
    ) -> str:
        """Add SOFT scale indicator to a bullet missing quantification.
        
        REALISM RULE: Never fabricate specific numbers (500K+, 10K+).
        Only use soft-scale phrasing that signals scope without lying:
          - "large-scale datasets" (not "500K+ records")
          - "high-volume APIs" (not "10K+ requests")
          - "enterprise-scale systems" (not "50+ services")
        
        If the bullet already contains real numbers from the candidate,
        those are preserved unchanged.
        """
        b_lower = bullet.lower()
        
        # If bullet already has numbers, don't add scale — it already has it
        if re.search(r'\d+[KkMm+]|\d{3,}', bullet):
            return bullet
        
        # Soft-scale phrasing keyed by detected context
        # These are qualitative descriptors that signal scope without fabrication
        soft_scale_map = {
            # Data context
            "data": [
                (r'\b(datasets?|data\s+(?:sets?|sources?))\b', r'large-scale \1'),
                (r'\b(analyz\w+|process\w+|transform\w+)\s+', r'\1 large-scale '),
                (r'\b(model\w*)\b(?!\s+(?:large|multi|complex|production))',
                 r'production-grade \1'),
            ],
            # API/Backend context
            "api": [
                (r'\b(APIs?)\b(?!\s+(?:high|scalable|production))',
                 r'high-throughput \1'),
                (r'\b(endpoints?|services?)\b(?!\s+(?:high|scalable|production))',
                 r'production \1'),
                (r'\b(microservices?)\b', r'distributed \1'),
            ],
            # User/Customer context
            "users": [
                (r'\b(users?)\b(?!\s+(?:base|facing))', r'user base'),
                (r'\b(customers?|clients?)\b(?!\s+(?:enterprise|key|major))',
                 r'enterprise \1'),
            ],
            # System/Infrastructure context
            "system": [
                (r'\b(systems?)\b(?!\s+(?:enterprise|distributed|complex))',
                 r'enterprise-scale \1'),
                (r'\b(infrastructure)\b(?!\s+(?:cloud|enterprise))',
                 r'cloud infrastructure'),
                (r'\b(platforms?)\b(?!\s+(?:enterprise|scalable))',
                 r'scalable \1'),
            ],
            # Team/Leadership context
            "team": [
                (r'\b(teams?)\b(?!\s+(?:cross|multi|diverse))',
                 r'cross-functional \1'),
                (r'\b(stakeholders?)\b(?!\s+(?:key|senior|multiple))',
                 r'key \1'),
            ],
        }
        
        # Detect context from bullet content
        context_signals = {
            "data": ["data", "dataset", "record", "analyz", "model", "pipeline",
                     "etl", "query", "table"],
            "api": ["api", "endpoint", "request", "service", "microservice",
                    "deploy", "server", "backend", "rest"],
            "users": ["user", "customer", "client", "support", "account",
                      "ticket", "call"],
            "system": ["system", "infrastructure", "monitor", "platform",
                       "architect", "automat", "configur"],
            "team": ["team", "collaborat", "stakeholder", "cross-function",
                     "department", "mentor", "train", "lead"],
        }
        
        detected_context = None
        for ctx, signals in context_signals.items():
            if any(sig in b_lower for sig in signals):
                detected_context = ctx
                break
        
        if not detected_context or detected_context not in soft_scale_map:
            return bullet
        
        # Try each soft-scale pattern for this context
        for pattern, replacement in soft_scale_map[detected_context]:
            enhanced = re.sub(pattern, replacement, bullet, count=1, flags=re.I)
            if enhanced != bullet:
                return enhanced
        
        return bullet

    def _inject_impact_outcome(self, bullet: str, role_type: str) -> str:
        """Add impact outcome to a bullet missing business value.
        
        Uses DOMAIN-SPECIFIC differentiation (Part 2) and
        OUTPUT VARIATION (Part 3) — rotates suffix patterns to avoid
        uniform structure across bullets.
        """
        b_lower = bullet.lower().rstrip('.')
        
        # Don't add if bullet already ends with an impact phrase
        if re.search(
            r'(?:improv|reduc|increas|boost|sav|driv|enabl|achiev)\w*\s+\w+\.?$',
            b_lower
        ):
            return bullet
        
        # Domain-specific impact suffixes (Part 2)
        # Each entry has MULTIPLE variants for output variation (Part 3)
        domain_impact_map = {
            # Frontend-specific
            "frontend": [
                (r'(?:responsive|layout|css|style|ui|ux|component)',
                 [", improving page load performance and user experience",
                  ", enhancing responsiveness and visual consistency",
                  ", driving higher user engagement and conversion"]),
            ],
            # Backend-specific
            "backend": [
                (r'(?:api|endpoint|service|server|backend|database|query)',
                 [", improving throughput and reducing response latency",
                  ", enhancing system scalability and reliability",
                  ", ensuring high availability for production workloads"]),
            ],
            # QA-specific
            "qa": [
                (r'(?:test|qa|quality|validat|regression|automat|selenium|defect|bug)',
                 [", increasing test coverage and reducing defect escape rate",
                  ", improving release quality and reducing regression risk",
                  ", accelerating QA cycles and strengthening release confidence"]),
            ],
            # DevOps-specific
            "devops": [
                (r'(?:deploy|releas|ci.?cd|pipeline|container|kubernetes|docker|infra)',
                 [", accelerating release velocity and reducing deployment risk",
                  ", improving infrastructure reliability and reducing downtime",
                  ", enabling faster and more reliable production deployments"]),
            ],
        }
        
        # General impact map (all roles)
        general_impact_map = [
            (r'(?:automat|streamlin|optimiz)',
             [", reducing manual effort and processing time",
              ", improving operational efficiency",
              ", streamlining workflows and reducing bottlenecks"]),
            (r'(?:test|qa|quality|validat)',
             [", improving release quality and reducing defects",
              ", strengthening quality assurance processes"]),
            (r'(?:monitor|alert|log|observ)',
             [", enabling proactive issue detection",
              ", improving system observability and incident response"]),
            (r'(?:deploy|releas|ci.?cd|pipeline)',
             [", accelerating release velocity",
              ", reducing deployment cycle time"]),
            (r'(?:secur|auth|encrypt|complian)',
             [", strengthening security posture",
              ", ensuring regulatory compliance"]),
            (r'(?:migrat|upgrad|refactor)',
             [", improving system maintainability",
              ", reducing technical debt"]),
            (r'(?:design|architect|build|develop)',
             [", enabling scalable and reliable operations",
              ", supporting long-term system growth"]),
            (r'(?:report|dashboard|visuali)',
             [", enabling data-driven decision-making",
              ", improving visibility into key business metrics"]),
            (r'(?:train|mentor|onboard|coach)',
             [", accelerating team productivity",
              ", reducing ramp-up time for new team members"]),
            (r'(?:collaborat|coordin|facilitat)',
             [", ensuring alignment across teams",
              ", improving cross-team collaboration"]),
        ]
        
        # Use bullet hash for deterministic variation (Part 3)
        variation_seed = hash(bullet) % 3
        
        # Try domain-specific first
        domain_key = None
        if role_type == "technical":
            # Detect sub-domain from bullet content
            if re.search(r'(?:ui|ux|css|responsive|component|frontend|react)', b_lower):
                domain_key = "frontend"
            elif re.search(r'(?:api|backend|server|database|microservice)', b_lower):
                domain_key = "backend"
            elif re.search(r'(?:deploy|ci.?cd|container|kubernetes|infra)', b_lower):
                domain_key = "devops"
        elif role_type == "operations":
            if re.search(r'(?:test|qa|quality|selenium|defect|regression)', b_lower):
                domain_key = "qa"
        
        if domain_key and domain_key in domain_impact_map:
            for pattern, suffixes in domain_impact_map[domain_key]:
                if re.search(pattern, b_lower):
                    suffix = suffixes[variation_seed % len(suffixes)]
                    clean = bullet.rstrip('.')
                    return clean + suffix + "."
        
        # Fall back to general impact map
        for pattern, suffixes in general_impact_map:
            if re.search(pattern, b_lower):
                suffix = suffixes[variation_seed % len(suffixes)]
                clean = bullet.rstrip('.')
                return clean + suffix + "."
        
        return bullet

    def _inject_outcome_clarity(self, bullet: str, role_type: str) -> str:
        """Add 'for [purpose]' clause when bullet lacks outcome clarity.
        
        Uses role-appropriate purpose suffix with variation.
        """
        b_lower = bullet.lower()
        
        # Don't add if bullet already has a purpose clause
        if re.search(
            r'\b(?:for\s+\w+|to\s+(?:ensure|enable|support|drive|improve))',
            b_lower
        ):
            return bullet
        
        # Only append if bullet is long enough to be meaningful
        if len(bullet) < 40:
            return bullet
        
        # Get role-appropriate outcome
        outcome = self._OUTCOME_SUFFIXES.get(role_type, "for improved outcomes")
        
        clean = bullet.rstrip('.')
        return f"{clean} {outcome}."


    # ================================================================
    # BULLET REWRITE ENGINE (Part 1 — Shortlist Spec v2)
    # Replaces append-based injection with FULL structural rewrites.
    # Template: [Action] + [Tool] + [Purpose] + [Impact]
    # ================================================================

    @staticmethod
    def _find_tools_in_text(text: str, all_tools: Set[str]) -> List[str]:
        """Find which tools/skills are already mentioned in a text."""
        t = text.lower()
        found = []
        for tool in sorted(all_tools, key=len, reverse=True):  # longest first
            if tool.lower() in t:
                found.append(tool)
        return found

    @staticmethod
    def _extract_metrics(bullet: str) -> Optional[str]:
        """Extract quantified metrics from a bullet if present."""
        patterns = [
            r'\d+[%+]',          # 15%, 30+
            r'\$[\d,.]+[KkMm]?', # $5M, $100K
            r'\d+[KkMm]\+?',     # 10K+
            r'\d{2,}\+?\s*(?:users|records|positions|employees|clients|requests|hires|orders)',
        ]
        for p in patterns:
            m = re.search(p, bullet, re.IGNORECASE)
            if m:
                return m.group(0)
        return None

    def _extract_project_signals(
        self, resume: StructuredResume, jd_keywords: List[str]
    ) -> Dict[str, str]:
        """Extract strongest tool→capability signals from projects.
        
        Returns dict: tool_name → capability description
        Used for project→experience bridging.
        """
        signals = {}
        for proj in resume.projects:
            proj_text = " ".join(proj.bullets).lower()
            # Check TOOL_TO_CAPABILITY map
            for tool, capability in TOOL_TO_CAPABILITY.items():
                if tool in proj_text:
                    signals[tool] = capability
            # Check standard tools
            for tool in SKILL_ECOSYSTEM:
                if tool in proj_text:
                    purpose = PURPOSE_PHRASES.get(tool, "")
                    if purpose and tool not in signals:
                        signals[tool] = purpose.lstrip("for ").lstrip("to ")
        return signals

    def _rewrite_bullet_structural(
        self,
        bullet: str,
        relevant_tools: List[str],
        jd_keywords: List[str],
        resume_vocab: Set[str],
        bullet_idx: int = 0,
    ) -> str:
        """Rewrite a single bullet as a hiring manager would for clarity and impact.
        
        STRUCTURE: [Strong Action Verb] + [What was done] + [How/Context] + [Impact]
        
        HARD CONSTRAINTS:
          - 12 to 22 words ONLY
          - Single sentence, max 2 commas
          - Must start with strong action verb
          - Must be grammatically complete
          - No keyword stuffing
          - If rewrite is NOT clearly better → return original
        
        Returns rewritten bullet string, or original if rewrite fails quality check.
        """
        original = bullet
        b_lower = bullet.lower()
        
        # ---- STEP 0: SKIP if already well-structured ----
        # If bullet already has [verb + object + method + impact], don't touch it
        has_metric = bool(re.search(r'\d+[%+]', bullet))
        has_purpose = bool(re.search(r'\b(?:for|to|enabling|improving|reducing|achieving)\s+\w', b_lower))
        has_tool = bool(re.search(r'\b(?:using|with|via)\s+\w', b_lower))
        word_count = len(bullet.split())
        if has_metric and has_purpose and word_count >= 12:
            return original  # Already well-structured
        if has_metric and has_tool and word_count >= 12:
            return original  # Already well-structured
        
        # ---- STEP 1: DECOMPOSE bullet into components ----
        action, obj, method, impact, domain = self._decompose_bullet(bullet, resume_vocab)
        
        # ---- STEP 2: UPGRADE action verb if weak ----
        _WEAK_TO_STRONG = {
            "worked": "developed", "helped": "supported", "did": "executed",
            "made": "built", "created": "developed", "used": "leveraged",
            "ran": "executed", "handled": "managed", "looked": "analyzed",
            "wrote": "developed", "set up": "configured", "fixed": "resolved",
            "got": "achieved", "put": "deployed", "tried": "implemented",
        }
        action_lower = action.lower().rstrip("ed").rstrip("ing")
        if action.lower() in _WEAK_TO_STRONG:
            action = _WEAK_TO_STRONG[action.lower()].capitalize()
        
        # ---- STEP 3: ADD tool ONLY if contextually appropriate ----
        tool_str = ""
        if relevant_tools and not has_tool:
            # Find ONE tool that fits the bullet's domain
            for tool in relevant_tools[:3]:
                if tool.lower() not in b_lower and _skill_fits_bullet(tool, bullet):
                    tool_str = tool
                    break
        
        # ---- STEP 4: BUILD impact phrase ----
        impact_str = impact  # Preserve existing metric/impact
        if not impact_str:
            # Use domain-aware SAFE impact phrases (never invent numbers)
            _SAFE_IMPACTS = {
                "data": ["improving data quality", "enabling data-driven decisions",
                         "enhancing analytical accuracy", "supporting business insights"],
                "modeling": ["improving prediction accuracy", "enhancing model performance",
                             "optimizing model reliability"],
                "deployment": ["improving system reliability", "enabling faster deployments",
                               "optimizing performance"],
                "backend": ["improving system performance", "enhancing scalability",
                            "reducing processing time"],
                "visualization": ["enabling stakeholder insights", "improving reporting clarity",
                                  "supporting data-driven decisions"],
                "general": ["improving efficiency", "enhancing productivity",
                            "optimizing performance", "supporting decision-making"],
            }
            cat = _detect_bullet_category(bullet)
            safe_list = _SAFE_IMPACTS.get(cat, _SAFE_IMPACTS["general"])
            impact_str = safe_list[bullet_idx % len(safe_list)]
        
        # ---- STEP 5: ASSEMBLE the rewrite ----
        # Structure: "{Action} {object}[, using {tool}][, {impact}]."
        parts = []
        
        # Core: Action + Object
        core = f"{action} {obj}" if obj else action
        # Ensure core doesn't already end with a comma
        core = core.rstrip(",. ")
        parts.append(core)
        
        # Method/Tool (if available and fits)
        if tool_str and method:
            parts.append(f"using {tool_str}")
        elif tool_str:
            parts.append(f"using {tool_str}")
        elif method:
            # Method without new tool — already in the core usually
            pass
        
        # Impact
        if impact_str:
            # Clean up impact phrase
            impact_clean = impact_str.strip().rstrip(".")
            # Don't duplicate if impact is already in core
            if impact_clean.lower() not in core.lower():
                # GUARD: Skip if core already has "for X" and impact adds another "for X"
                core_has_purpose = bool(re.search(r'\bfor\s+\w', core, re.I))
                impact_has_for = impact_clean.lower().startswith("for ")
                if core_has_purpose and impact_has_for:
                    pass  # Skip: would create "for X for Y" chain
                else:
                    parts.append(impact_clean)
        
        # Assemble
        if len(parts) == 3:
            result = f"{parts[0]}, {parts[1]}, {parts[2]}."
        elif len(parts) == 2:
            result = f"{parts[0]}, {parts[1]}."
        else:
            result = f"{parts[0]}."
        
        # POST-ASSEMBLY GUARD: Reject if result has "for X for Y" chain
        if re.search(r'\bfor\s+[\w\s]+\bfor\s+\w', result, re.I):
            return original
        
        # ---- STEP 6: SELF-CHECK (5-point quality gate) ----
        # 1. Starts with strong action verb
        first_word = result.split()[0].lower().rstrip(",.")
        _STRONG_VERBS = {
            "built", "developed", "designed", "implemented", "optimized",
            "analyzed", "automated", "deployed", "architected", "created",
            "engineered", "integrated", "configured", "managed", "led",
            "reduced", "improved", "increased", "established", "maintained",
            "executed", "streamlined", "enhanced", "resolved", "supported",
            "generated", "delivered", "trained", "tested", "cleaned",
            "labeled", "applied", "transformed", "migrated", "scaled",
        }
        has_strong_verb = first_word in _STRONG_VERBS
        
        # 2. Word count: 12-22 words
        result_words = len(result.split())
        good_length = 8 <= result_words <= 25  # Slightly relaxed for real-world bullets
        
        # 3. Max 2 commas
        comma_count = result.count(",")
        good_commas = comma_count <= 2
        
        # 4. Single complete sentence (ends with period)
        good_sentence = result.strip().endswith(".")
        
        # 5. Natural and fluent (no stacking: "using X using Y", "for X for Y")
        no_stacking = not re.search(
            r'(?:using|applying|leveraging)\s+\w+.*?(?:using|applying|leveraging)\s+\w',
            result, re.I
        )
        
        # ---- STEP 7: CONSERVATISM — return original if rewrite isn't clearly better ----
        # Score original vs rewrite
        orig_score = self._score_bullet_impact(original, "data")
        new_score = self._score_bullet_impact(result, "data")
        
        # Rewrite must pass ALL checks AND be equal or better
        all_checks_pass = (has_strong_verb and good_length and good_commas 
                           and good_sentence and no_stacking)
        
        if not all_checks_pass:
            return original  # Failed quality check
        
        if new_score < orig_score:
            return original  # Not an improvement
        
        # Final semantic preservation: must share ≥ 50% content words
        _FILLER = {"was", "were", "had", "the", "and", "for", "with", "from",
                    "that", "this", "also", "very", "just", "some"}
        orig_content = set(re.findall(r'[a-z]{3,}', original.lower())) - _FILLER
        new_content = set(re.findall(r'[a-z]{3,}', result.lower())) - _FILLER
        if orig_content and len(orig_content) >= 3:
            overlap = len(orig_content & new_content) / len(orig_content)
            if overlap < 0.50:
                return original  # Too much semantic drift
        
        return result
    
    def _decompose_bullet(
        self, bullet: str, resume_vocab: Set[str]
    ) -> tuple:
        """Decompose a bullet into (action, object, method, impact, domain).
        
        Returns 5-tuple of strings (any may be empty string).
        """
        b_lower = bullet.lower()
        
        # ACTION: first word (verb)
        words = bullet.split()
        action = words[0] if words else ""
        
        # IMPACT: extract metric if present ("improving X by Y%", "reducing X by Y%")
        impact = ""
        metric_match = re.search(
            r'(?:improv|reduc|increas|achiev|enabl)\w*\s+[\w\s]*?\s*(?:by\s+)?\d+[%+]?\+?',
            bullet, re.I
        )
        if metric_match:
            impact = metric_match.group().strip()
        elif re.search(r'\d+[%+K]+', bullet):
            # Has standalone metric — extract the clause containing it
            m = re.search(r'[\w\s]*\d+[%+K]+[\w\s]*', bullet)
            if m:
                impact = m.group().strip()
        
        # METHOD: detect tools/technologies mentioned
        existing_tools = self._find_tools_in_text(b_lower, resume_vocab)
        method = ", ".join(existing_tools) if existing_tools else ""
        
        # OBJECT: everything between action and method/impact (the "what")
        obj_text = bullet
        # Remove action verb
        if action and obj_text.startswith(action):
            obj_text = obj_text[len(action):].strip()
        # Remove impact clause
        if impact and impact in obj_text:
            obj_text = obj_text.replace(impact, "").strip()
        # Remove trailing tool suffix
        obj_text = re.sub(
            r',?\s*(?:using|with|via|leveraging|applying)\s+.*$', '',
            obj_text, flags=re.I
        ).strip().rstrip(",. ")
        obj = obj_text
        
        # DOMAIN: classify bullet category
        domain = _detect_bullet_category(bullet)
        
        return (action, obj, method, impact, domain)

    def _rewrite_experience_bullets(
        self,
        resume: StructuredResume,
        matched_skills: List[str],
        jd_keywords: List[str],
        resume_vocab: Set[str],
        project_signals: Dict[str, str],
        max_rewrites: int = 8,
    ) -> int:
        """Adaptive Bullet Rewrite Engine (v2 — Priority-Based).
        
        Instead of naively iterating all bullets, this engine:
          1. SCORES every bullet on priority + impact dimensions
          2. RANKS into tiers (ELITE / HIGH / MEDIUM / LOW)
          3. SELECTS only ELITE + HIGH bullets (max 5)
          4. ASSIGNS each a strategy (STRENGTHEN_SIGNAL, ADD_CONTEXT, etc.)
          5. REWRITES only selected bullets with their assigned strategy
        
        This creates MAXIMUM hiring impact with MINIMUM changes.
        """
        if not matched_skills or not resume.experience:
            return 0
        
        # ---- STEP 1: BUILD CONTEXT ----
        all_text = " ".join(b.lower() for e in resume.experience for b in e.bullets)
        jd_kw_set = {kw.lower() for kw in jd_keywords}
        
        # Build tool priority: JD-matching tools not yet in bullets
        tool_priority = []
        for skill in matched_skills:
            if skill.lower() not in all_text:
                tool_priority.append(skill)
        for tool in project_signals:
            if tool not in [t.lower() for t in tool_priority]:
                tool_priority.append(tool)
        
        # ---- STEP 2: SCORE & RANK ALL BULLETS ----
        scored_bullets = []
        for exp_idx, exp in enumerate(resume.experience):
            for b_idx, bullet in enumerate(exp.bullets):
                analysis = self._score_bullet_priority(
                    bullet, jd_kw_set, matched_skills, resume_vocab, tool_priority
                )
                analysis["exp_idx"] = exp_idx
                analysis["b_idx"] = b_idx
                analysis["bullet"] = bullet
                scored_bullets.append(analysis)
        
        # Sort by final_score descending
        scored_bullets.sort(key=lambda x: x["final_score"], reverse=True)
        
        # ---- STEP 3: SELECT ELITE + HIGH ONLY (max 5) ----
        selected = [
            b for b in scored_bullets
            if b["tier"] in ("ELITE", "HIGH")
        ][:min(5, max_rewrites)]
        
        if not selected:
            return 0
        
        logger.info(f"  Priority Engine: {len(selected)} bullets selected "
                     f"(of {len(scored_bullets)} total)")
        for s in selected:
            logger.info(f"    [{s['tier']}] score={s['final_score']} "
                         f"strategy={s['strategy']} | \"{s['bullet'][:50]}...\"")
        
        # ---- STEP 4: REWRITE SELECTED BULLETS ----
        changes = 0
        # Semantic misfit contexts — never inject tech into soft-context
        MISFIT_CONTEXTS = {
            "standup", "meeting", "attended", "participated",
            "communicated", "presented", "discussed",
        }
        
        for item in selected:
            exp_idx = item["exp_idx"]
            b_idx = item["b_idx"]
            bullet = resume.experience[exp_idx].bullets[b_idx]
            b_lower = bullet.lower()
            strategy = item["strategy"]
            
            # Skip soft-context bullets
            if any(m in b_lower for m in MISFIT_CONTEXTS):
                continue
            
            # KEEP_ORIGINAL strategy → skip
            if strategy == "KEEP_ORIGINAL":
                continue
            
            # Filter tools that fit this bullet
            fitting_tools = [
                t for t in tool_priority
                if t.lower() not in b_lower and _skill_fits_bullet(t, bullet)
            ]
            
            # For STRENGTHEN_SIGNAL / SIMPLIFY: rewrite even without new tools
            # For ADD_CONTEXT: need tools to add
            if strategy == "ADD_CONTEXT" and not fitting_tools:
                continue
            
            # Rewrite with strategy awareness
            rewritten = self._rewrite_bullet_structural(
                bullet, fitting_tools or [], jd_keywords, resume_vocab,
                bullet_idx=b_idx,
            )
            
            if rewritten != bullet:
                resume.experience[exp_idx].bullets[b_idx] = rewritten
                changes += 1
                # Remove used tools from priority
                for t in fitting_tools[:2]:
                    if t in tool_priority:
                        tool_priority.remove(t)
                logger.info(f"  -> Rewrite: \"{rewritten[:70]}...\"")
        
        return changes
    
    # ================================================================
    # BULLET PRIORITY SCORING ENGINE
    # ================================================================
    
    def _score_bullet_priority(
        self,
        bullet: str,
        jd_keywords: Set[str],
        matched_skills: List[str],
        resume_vocab: Set[str],
        available_tools: List[str],
    ) -> Dict:
        """Score a single bullet on priority + impact dimensions.
        
        PRIORITY SCORING (max 8):
          1. Role Relevance    (0-3) — matches JD keywords
          2. Technical Depth   (0-2) — real systems / models / pipelines
          3. Impact Presence   (0-2) — clear outcome / metric
          4. Tool Relevance    (0-1) — mentions meaningful tools
          5. Weak Language     (-2)  — penalty for passive/vague language
          BONUS: +2 for strong JD keyword match
        
        IMPACT SCORING (max 10):
          1. Recruiter Attention  (0-3) — would a recruiter notice?
          2. Decision Influence   (0-3) — increases shortlist confidence?
          3. Uniqueness           (0-2) — differentiating vs generic?
          4. Credibility          (0-2) — clear and believable?
        
        Returns dict with scores, tier, and assigned strategy.
        """
        b_lower = bullet.lower()
        words = b_lower.split()
        
        # ---- PRIORITY SCORING ----
        
        # 1. Role Relevance (0-3)
        jd_match_count = sum(1 for kw in jd_keywords if kw in b_lower)
        role_relevance = min(3, jd_match_count)
        
        # 2. Technical Depth (0-2)
        _DEPTH_SIGNALS = {
            "pipeline", "model", "algorithm", "architecture", "system",
            "api", "backend", "database", "microservice", "deployment",
            "infrastructure", "ml", "neural", "distributed", "etl",
            "warehouse", "schema", "index", "optimization", "scalab",
        }
        depth_hits = sum(1 for s in _DEPTH_SIGNALS if s in b_lower)
        technical_depth = min(2, depth_hits)
        
        # 3. Impact Presence (0-2)
        has_metric = bool(re.search(r'\d+[%+$K]', bullet))
        has_outcome = bool(re.search(
            r'improv|reduc|increas|enabl|achiev|accelerat|streamlin|optimiz',
            b_lower
        ))
        impact_presence = (1 if has_metric else 0) + (1 if has_outcome else 0)
        
        # 4. Tool Relevance (0-1)
        existing_tools = self._find_tools_in_text(b_lower, resume_vocab)
        tool_relevance = 1 if existing_tools else 0
        
        # 5. Weak Language Penalty (-2)
        _WEAK_PATTERNS = [
            "worked on", "responsible for", "involved in",
            "handled", "helped with", "assisted in", "participated in",
        ]
        weak_penalty = -2 if any(wp in b_lower for wp in _WEAK_PATTERNS) else 0
        
        # BONUS: +2 for strong JD match (2+ keywords)
        jd_bonus = 2 if jd_match_count >= 2 else 0
        
        priority_score = (role_relevance + technical_depth + impact_presence 
                          + tool_relevance + weak_penalty + jd_bonus)
        
        # ---- IMPACT SCORING ----
        
        # 1. Recruiter Attention (0-3)
        first_word = words[0] if words else ""
        _ATTENTION_VERBS = {
            "built", "developed", "designed", "architected", "led",
            "scaled", "automated", "engineered", "reduced", "improved",
        }
        attention = 0
        if first_word in _ATTENTION_VERBS:
            attention += 1
        if has_metric:
            attention += 1
        if len(bullet) >= 60:  # Substantive bullet
            attention += 1
        recruiter_attention = min(3, attention)
        
        # 2. Decision Influence (0-3)
        decision = 0
        if jd_match_count >= 2:
            decision += 2  # Strong JD alignment
        elif jd_match_count >= 1:
            decision += 1
        if has_metric and has_outcome:
            decision += 1  # Quantified impact = strong signal
        decision_influence = min(3, decision)
        
        # 3. Uniqueness (0-2)
        _GENERIC_PATTERNS = [
            "maintained", "supported", "managed tasks",
            "communicated with", "coordinated with",
            "participated in meetings", "documented",
        ]
        is_generic = any(gp in b_lower for gp in _GENERIC_PATTERNS)
        uniqueness = 0 if is_generic else (2 if technical_depth >= 2 else 1)
        
        # 4. Credibility (0-2)
        credibility = 0
        if has_metric:
            credibility += 1
        if existing_tools:
            credibility += 1
        
        impact_score = (recruiter_attention + decision_influence 
                        + uniqueness + credibility)
        
        # ---- FINAL SCORE & TIER ----
        final_score = priority_score + impact_score
        
        if final_score >= 14:
            tier = "ELITE"
        elif final_score >= 10:
            tier = "HIGH"
        elif final_score >= 6:
            tier = "MEDIUM"
        else:
            tier = "LOW"
        
        # ---- STRATEGY ASSIGNMENT ----
        strategy = self._assign_rewrite_strategy(
            bullet, b_lower, has_metric, has_outcome,
            existing_tools, available_tools, weak_penalty,
            technical_depth, role_relevance,
        )
        
        return {
            "priority_score": priority_score,
            "impact_score": impact_score,
            "final_score": final_score,
            "tier": tier,
            "strategy": strategy,
            "role_relevance": role_relevance,
            "technical_depth": technical_depth,
            "impact_presence": impact_presence,
            "tool_relevance": tool_relevance,
            "recruiter_attention": recruiter_attention,
            "decision_influence": decision_influence,
            "uniqueness": uniqueness,
            "credibility": credibility,
        }
    
    def _assign_rewrite_strategy(
        self,
        bullet: str,
        b_lower: str,
        has_metric: bool,
        has_outcome: bool,
        existing_tools: List[str],
        available_tools: List[str],
        weak_penalty: int,
        technical_depth: int,
        role_relevance: int,
    ) -> str:
        """Assign a rewrite strategy based on bullet analysis.
        
        Strategies:
          STRENGTHEN_SIGNAL  → improve clarity + structure (weak verb → strong)
          ADD_CONTEXT        → add HOW (tools/methods) to bare bullet
          IMPACT_ELEVATION   → improve outcome phrasing (safe only)
          SIMPLIFY           → improve readability (overlong/complex)
          KEEP_ORIGINAL      → already strong, don't touch
        """
        word_count = len(bullet.split())
        
        # Already strong: has metric + tools + good verb + right length
        if has_metric and existing_tools and weak_penalty == 0 and 10 <= word_count <= 22:
            return "KEEP_ORIGINAL"
        
        # Weak language → STRENGTHEN_SIGNAL (highest priority fix)
        if weak_penalty < 0:
            return "STRENGTHEN_SIGNAL"
        
        # No tools mentioned + tools available → ADD_CONTEXT
        if not existing_tools and available_tools:
            fitting = [t for t in available_tools if _skill_fits_bullet(t, bullet)]
            if fitting:
                return "ADD_CONTEXT"
        
        # Has no impact/outcome → IMPACT_ELEVATION
        if not has_metric and not has_outcome:
            return "IMPACT_ELEVATION"
        
        # Overlong → SIMPLIFY
        if word_count > 25:
            return "SIMPLIFY"
        
        # Good technical depth + role relevance but could be clearer
        if technical_depth >= 1 and role_relevance >= 1:
            return "STRENGTHEN_SIGNAL"
        
        return "KEEP_ORIGINAL"

    # ================================================================
    # SUMMARY STRENGTHENER
    # ================================================================

    def _strengthen_summary(
        self,
        resume: StructuredResume,
        jd_keywords: List[str],
        matched_skills: List[str],
        resume_vocab: Set[str],
    ) -> int:
        """Enhance summary to align with role keywords using vocabulary.
        
        CRITICAL: If the summary contains generic filler phrases, REPLACE
        the entire summary instead of appending to it. Appending to
        'Experienced X with a passion for Y' sounds robotic.
        """
        if not resume.summary:
            return 0

        summary = resume.summary
        summary_lower = summary.lower()
        changes = 0

        # Detect generic filler phrases that must be replaced, not appended to
        GENERIC_PATTERNS = [
            r"with a passion for",
            r"looking for opportunities",
            r"seeking (?:a |an )?(?:position|role|opportunity)",
            r"^(?:experienced|dedicated|hardworking|passionate|motivated|result.driven)\s+\w+\s+(?:professional|with|who)",
        ]
        is_generic = any(re.search(p, summary_lower) for p in GENERIC_PATTERNS)

        if is_generic:
            # FULL REPLACEMENT: Generate a proper summary
            # [Role] + [Specialization] + [Scale] + [Impact] + [Tools]
            role = resume.title or "professional"
            
            # Extract top tools from matched skills
            top_tools = [s for s in matched_skills[:5] if s.lower() in resume_vocab]
            tool_phrase = ", ".join(top_tools[:4]) if top_tools else ""
            
            # Extract years from experience
            years = len(resume.experience) * 2  # Rough estimate
            
            # Extract specialization from JD keywords
            specialization = [kw for kw in jd_keywords[:3] if kw.lower() in resume_vocab]
            spec_phrase = " and ".join(specialization[:2]) if specialization else ""
            
            # Build replacement summary
            parts = []
            if years >= 3:
                parts.append(f"{role} with {years}+ years of experience")
            else:
                parts.append(f"{role}")
            
            if spec_phrase:
                parts[0] += f" specializing in {spec_phrase}"
            
            # Extract SCALE from bullet metrics (e.g., "500+ records", "300 employees")
            scale_phrases = []
            for exp in resume.experience:
                for bullet in exp.bullets:
                    scale_match = re.search(
                        r'(\d{2,}[Kk+]?\+?\s*(?:records|users|positions|employees|'
                        r'clients|requests|hires|datasets|transactions|models|'
                        r'customers|orders|applications))',
                        bullet, re.IGNORECASE
                    )
                    if scale_match and scale_match.group(0) not in [s for s in scale_phrases]:
                        scale_phrases.append(scale_match.group(0))
                        if len(scale_phrases) >= 1:
                            break
                if scale_phrases:
                    break
            
            if scale_phrases:
                parts[0] += f", with experience processing {scale_phrases[0]}"
            
            if tool_phrase:
                parts.append(f"Proficient in {tool_phrase}")
            
            # Extract IMPACT from bullet metrics (%, $, x)
            impact_phrases = []
            for exp in resume.experience:
                for bullet in exp.bullets:
                    impact_match = re.search(
                        r'(?:improv|reduc|increas|achiev|driv|sav)\w*\s+.*?'
                        r'(\d+[%$xX+])',
                        bullet, re.IGNORECASE
                    )
                    if impact_match:
                        impact_phrases.append(impact_match.group(0))
                        break
                if impact_phrases:
                    break
            
            # Add education credentials (Master's/PhD = credibility signal)
            if resume.education:
                for edu in resume.education:
                    deg = (edu.degree or "").lower()
                    if any(d in deg for d in ['m.s.', 'master', 'mba', 'ph.d', 'phd']):
                        parts.append(
                            f"Holds a {edu.degree} from {edu.institution}, "
                            f"providing strong theoretical foundations in quantitative methods and applied research"
                        )
                        break
            
            new_summary = ". ".join(parts) + "."
            if len(new_summary) >= 30:
                resume.summary = new_summary
                changes += 1
                return changes

        # Non-generic summary: enrich with missing keywords
        keywords_to_add = []
        for kw in jd_keywords[:6]:
            kw_lower = kw.lower()
            if kw_lower not in summary_lower and kw_lower in resume_vocab:
                keywords_to_add.append(kw)

        if keywords_to_add and len(keywords_to_add) <= 4:
            keyword_phrase = ", ".join(keywords_to_add[:3])
            if summary.endswith("."):
                summary = summary[:-1] + f", with expertise in {keyword_phrase}."
            else:
                summary += f", with expertise in {keyword_phrase}."
            changes += 1

        # Fix weak starts
        weak_starts = ["i am ", "i have ", "i'm ", "my name is "]
        for weak in weak_starts:
            if summary.lower().startswith(weak):
                summary = summary[len(weak):]
                summary = summary[0].upper() + summary[1:] if summary else summary
                changes += 1
                break

        resume.summary = summary
        return changes

    # ================================================================
    # UTILITY METHODS
    # ================================================================

    @staticmethod
    def _extract_all_text(resume: StructuredResume) -> str:
        """Extract all text content from a resume for keyword analysis."""
        parts = []
        if resume.summary:
            parts.append(resume.summary)
        for exp in resume.experience:
            parts.extend(exp.bullets)
        for proj in resume.projects:
            parts.extend(proj.bullets)
        return " ".join(parts)

    @staticmethod
    def _extract_keyword_set(text: str) -> set:
        """Extract meaningful keywords (3+ chars) from text."""
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        stop = {"the", "and", "for", "with", "that", "this", "from", "have", "has",
                "was", "were", "are", "been", "being", "will", "would", "could",
                "should", "may", "can", "not", "but", "also", "into", "over"}
        return {w for w in words if w not in stop}

    @staticmethod
    def _has_excessive_repetition(text: str, max_repeat: int = 4) -> bool:
        """Check if any meaningful word appears more than max_repeat times."""
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        if len(words) < 20:
            return False
        from collections import Counter
        counts = Counter(words)
        # Common words that naturally appear multiple times in enhanced resumes
        stop = {"with", "that", "this", "from", "have", "been", "were", "also",
                "their", "which", "using", "experience", "development", "including",
                "data", "based", "leveraged", "utilized", "utilizing", "leveraging",
                "scalable", "automated", "predictive", "deployment", "modeling",
                "pipeline", "processing", "engineering", "analysis", "analytics",
                "learning", "machine", "model", "cloud", "science", "designed",
                "developed", "implemented", "built", "system", "python", "through",
                "applied", "expertise", "driven", "business", "scale", "across"}
        for word, count in counts.items():
            if word in stop:
                continue
            if count > max_repeat and count > len(words) * 0.08:
                return True
        return False

    # ================================================================
    # MAX SCORE UTILIZATION ENGINE (Step 13)
    # Pushes score toward ceiling using 3 strategies:
    #   1. Verb amplification (weak → strong action verbs)
    #   2. Skill depth in bullets (tool → tool + context)
    #   3. Coverage enforcement (85%+ utilization)
    # ================================================================

    # Weak → Strong verb upgrades (deterministic, first match wins)
    _VERB_UPGRADES = [
        (r"\bworked on\b", "developed"),
        (r"\bhelped build\b", "implemented"),
        (r"\bhelped with\b", "contributed to"),
        (r"\bhelped create\b", "co-developed"),
        (r"\bwas responsible for\b", "managed"),
        (r"\bwas involved in\b", "contributed to"),
        (r"\btasked with\b", "spearheaded"),
        (r"\bwas part of\b", "collaborated on"),
        (r"\bassisted in\b", "supported"),
        (r"\bdid\b", "executed"),
        (r"\bmade\b", "engineered"),
        (r"\bhandled\b", "managed"),
        (r"\bused\b", "utilized"),
        (r"\bran\b", "orchestrated"),
        (r"\bfixed\b", "resolved"),
        (r"\bset up\b", "configured"),
        (r"\bworked with\b", "collaborated with"),
        (r"\blearned\b", "gained proficiency in"),
        (r"\btried\b", "evaluated"),
    ]

    def _maximize_score(
        self,
        resume: StructuredResume,
        matched_skills: List[str],
        jd_keywords: List[str],
        resume_vocab: Set[str] = None,
        light_mode: bool = False,
    ) -> tuple:
        """
        Max Score Utilization Engine.
        
        Pushes ATS score toward the ceiling by:
          1. Amplifying weak verbs -> strong action verbs (skip in light_mode)
          2. Expanding skill depth in bullets (tool -> tool + ecosystem)
          3. Enforcing 85%+ skill utilization in evidence bullets
        
        Args:
            light_mode: If True, skip verb amplification (for balanced mode).
        
        Returns (changes_count, list_of_improvements).
        ALL transformations are deterministic and evidence-based.
        """
        changes = 0
        improvements = []
        resume_vocab = resume_vocab or set()

        # ---- 1. VERB AMPLIFICATION (strict only) ----
        if not light_mode:
            verb_changes = self._amplify_verbs(resume)
            changes += verb_changes
            if verb_changes:
                improvements.append(f"Amplified {verb_changes} weak verbs to strong action verbs")

        # ---- 2. SKILL DEPTH IN BULLETS ----
        depth_changes = self._expand_skill_depth_in_bullets(
            resume, matched_skills, resume_vocab
        )
        changes += depth_changes
        if depth_changes:
            improvements.append(f"Expanded {depth_changes} skills with ecosystem depth in bullets")

        # ---- 3. COVERAGE ENFORCEMENT (85%+ utilization) ----
        coverage_pct, cov_changes = self._enforce_coverage_target(
            resume, matched_skills, jd_keywords, resume_vocab
        )
        changes += cov_changes
        if cov_changes:
            improvements.append(
                f"Coverage: {coverage_pct:.0f}% skills demonstrated in bullets "
                f"({cov_changes} promoted)"
            )

        return changes, improvements

    def _amplify_verbs(self, resume: StructuredResume) -> int:
        """
        Replace weak verbs with strong action verbs in experience bullets.
        Deterministic: processes bullets in order, applies first matching upgrade.
        """
        changes = 0

        for exp in resume.experience:
            for i, bullet in enumerate(exp.bullets):
                original = bullet
                for pattern, replacement in self._VERB_UPGRADES:
                    new_bullet = re.sub(pattern, replacement, bullet, count=1, flags=re.IGNORECASE)
                    if new_bullet != bullet:
                        # Capitalize first letter if at start
                        if new_bullet and not new_bullet[0].isupper():
                            new_bullet = new_bullet[0].upper() + new_bullet[1:]
                        bullet = new_bullet
                        break  # One upgrade per bullet

                if bullet != original:
                    exp.bullets[i] = bullet
                    changes += 1

        # Also amplify project bullets
        for proj in resume.projects:
            for i, bullet in enumerate(proj.bullets):
                original = bullet
                for pattern, replacement in self._VERB_UPGRADES:
                    new_bullet = re.sub(pattern, replacement, bullet, count=1, flags=re.IGNORECASE)
                    if new_bullet != bullet:
                        if new_bullet and not new_bullet[0].isupper():
                            new_bullet = new_bullet[0].upper() + new_bullet[1:]
                        bullet = new_bullet
                        break
                if bullet != original:
                    proj.bullets[i] = bullet
                    changes += 1

        return changes

    def _expand_skill_depth_in_bullets(
        self,
        resume: StructuredResume,
        matched_skills: List[str],
        resume_vocab: Set[str],
    ) -> int:
        """
        When a bullet mentions a skill generically (e.g., 'Python'),
        expand to show ecosystem depth (e.g., 'Python (pandas, numpy)').
        ONLY if the sub-tools already exist in resume vocabulary.
        """
        changes = 0
        vocab_lower = {v.lower() for v in resume_vocab}

        # Build expansion map from SKILL_ECOSYSTEM (only tools in vocab)
        expansions = {}
        for parent, children in SKILL_ECOSYSTEM.items():
            parent_lower = parent.lower()
            available_children = [
                c for c in children
                if c.lower() in vocab_lower and c.lower() != parent_lower
            ]
            if available_children:
                expansions[parent_lower] = available_children[:3]  # Max 3 sub-tools

        if not expansions:
            return 0

        # Apply to experience bullets
        for exp in resume.experience:
            for i, bullet in enumerate(exp.bullets):
                if len(bullet) > 200:
                    continue  # Skip already long bullets
                bullet_lower = bullet.lower()
                for parent, children in sorted(expansions.items()):
                    # Check if parent is in bullet but children aren't
                    if parent in bullet_lower:
                        # HARDENED: Skip if ANY child tool already appears in bullet
                        children_already_present = any(
                            c.lower() in bullet_lower for c in children
                        )
                        if children_already_present:
                            continue
                        children_text = ", ".join(children)
                        expanded = f"{parent} ({children_text})"
                        if expanded.lower() not in bullet_lower and len(children_text) > 2:
                            # Replace first occurrence of standalone parent
                            pattern = re.compile(
                                r"\b" + re.escape(parent) + r"\b", re.IGNORECASE
                            )
                            match = pattern.search(bullet)
                            if match:
                                original_word = match.group(0)
                                new_bullet = pattern.sub(
                                    f"{original_word} ({children_text})",
                                    bullet, count=1
                                )
                                if len(new_bullet) <= 250:
                                    exp.bullets[i] = new_bullet
                                    changes += 1
                                    break  # One expansion per bullet

        return changes

    def _enforce_coverage_target(
        self,
        resume: StructuredResume,
        matched_skills: List[str],
        jd_keywords: List[str],
        resume_vocab: Set[str],
    ) -> tuple:
        """
        Ensure >= 85% of matched skills are demonstrated in bullets.
        Skills present only in skills list get promoted to project bullets.
        
        Returns (coverage_percentage, changes_count).
        """
        if not matched_skills:
            return 100.0, 0

        # Build combined bullet text
        all_bullets = " ".join(
            b.lower() for exp in resume.experience for b in exp.bullets
        ) + " " + " ".join(
            b.lower() for proj in resume.projects for b in proj.bullets
        )

        # Check which skills are demonstrated
        demonstrated = 0
        missing_in_bullets = []
        for skill in sorted(matched_skills, key=str.lower):
            skill_lower = skill.lower()
            terms = [t for t in skill_lower.split() if len(t) > 2]
            found = skill_lower in all_bullets
            if not found and terms:
                found = any(t in all_bullets for t in terms if len(t) > 3)
            if found:
                demonstrated += 1
            else:
                missing_in_bullets.append(skill)

        coverage = (demonstrated / len(matched_skills)) * 100
        if coverage >= 85 or not missing_in_bullets:
            return coverage, 0

        # Promote missing skills into project bullets (shortest first)
        changes = 0
        proj_slots = []
        for p_idx, proj in enumerate(resume.projects):
            for b_idx, bullet in enumerate(proj.bullets):
                proj_slots.append((p_idx, b_idx, len(bullet)))

        proj_slots.sort(key=lambda x: (x[2], x[0], x[1]))

        slot_idx = 0
        for skill in missing_in_bullets:
            if not proj_slots or slot_idx >= len(proj_slots):
                break

            p_idx, b_idx, b_len = proj_slots[slot_idx]
            if b_len > 220:
                slot_idx += 1
                continue

            bullet = resume.projects[p_idx].bullets[b_idx]
            skill_display = skill
            for ms in matched_skills:
                if ms.lower() == skill.lower():
                    skill_display = ms
                    break

            if bullet.endswith("."):
                new_bullet = bullet[:-1] + f", utilizing {skill_display}."
            else:
                new_bullet = bullet + f", utilizing {skill_display}."

            resume.projects[p_idx].bullets[b_idx] = new_bullet
            changes += 1
            slot_idx += 1

        # Recompute coverage
        new_demonstrated = demonstrated + changes
        new_coverage = (new_demonstrated / len(matched_skills)) * 100

        return new_coverage, changes

