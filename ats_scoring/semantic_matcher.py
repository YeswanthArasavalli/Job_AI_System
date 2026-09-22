"""
Semantic Matcher -- TF-IDF cosine similarity for JD vs Resume matching.

No heavy ML dependencies. Pure Python + basic math.

Uses:
  - Term Frequency (TF): how often a term appears in a document
  - Inverse Document Frequency (IDF): how rare a term is across documents
  - Cosine Similarity: angle between two TF-IDF vectors

This gives us a semantic overlap score between JD responsibilities
and resume bullets WITHOUT needing an LLM.
"""

import math
import re
from collections import Counter
from typing import Dict, List, Set, Tuple

from utils.logger import setup_logger

logger = setup_logger(__name__)

# Stop words for TF-IDF (expanded for resume/JD context)
_STOP_WORDS: Set[str] = {
    "a", "an", "the", "and", "or", "of", "in", "to", "for", "with", "on", "at",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "should", "could", "may", "might",
    "can", "must", "shall", "not", "no", "but", "if", "so", "as", "by",
    "from", "up", "out", "about", "into", "through", "during", "before", "after",
    "above", "below", "between", "under", "over", "such", "than", "too", "very",
    "just", "also", "both", "each", "more", "most", "other", "some", "any",
    "all", "many", "much", "own", "same", "few", "those", "these", "this", "that",
    "their", "our", "your", "its", "they", "them", "we", "you", "i", "me",
    "my", "he", "she", "it", "his", "her", "who", "which", "what", "when",
    "where", "how", "why", "there", "here", "then", "now",
    "strong", "excellent", "good", "ability", "experience", "knowledge",
    "skills", "skill", "etc", "including", "using", "across", "various",
}


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase words, removing stop words and short tokens."""
    words = re.findall(r'[a-z0-9+#/.]+', text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


def compute_tf(tokens: List[str]) -> Dict[str, float]:
    """Compute term frequency (normalized by document length)."""
    counts = Counter(tokens)
    total = len(tokens) if tokens else 1
    return {term: count / total for term, count in counts.items()}


def compute_idf(documents: List[List[str]]) -> Dict[str, float]:
    """Compute inverse document frequency across a corpus."""
    n_docs = len(documents)
    if n_docs == 0:
        return {}

    # Count how many documents contain each term
    doc_freq: Dict[str, int] = {}
    for doc in documents:
        unique_terms = set(doc)
        for term in unique_terms:
            doc_freq[term] = doc_freq.get(term, 0) + 1

    # IDF = log(N / df) with smoothing
    idf = {}
    for term, df in doc_freq.items():
        idf[term] = math.log((n_docs + 1) / (df + 1)) + 1  # Smoothed IDF

    return idf


def compute_tfidf(tf: Dict[str, float], idf: Dict[str, float]) -> Dict[str, float]:
    """Compute TF-IDF vector."""
    return {term: tf_val * idf.get(term, 1.0) for term, tf_val in tf.items()}


def cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Compute cosine similarity between two sparse vectors."""
    # Find common terms
    common_terms = set(vec_a.keys()) & set(vec_b.keys())

    if not common_terms:
        return 0.0

    # Dot product
    dot_product = sum(vec_a[t] * vec_b[t] for t in common_terms)

    # Magnitudes
    mag_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot_product / (mag_a * mag_b)


class SemanticMatcher:
    """
    TF-IDF based semantic matcher for comparing JD content against resume content.

    Usage:
        matcher = SemanticMatcher()

        # Compare JD responsibilities vs resume bullets
        score = matcher.match_responsibilities(jd_responsibilities, resume_bullets)

        # Get detailed per-responsibility scores
        details = matcher.match_detailed(jd_responsibilities, resume_bullets)
    """

    # Phrase normalization: action phrases -> canonical concepts
    _PHRASE_MAP = {
        # Data
        "built dashboards": "data visualization",
        "created dashboards": "data visualization",
        "designed dashboards": "data visualization",
        "data visualization": "data visualization",
        "tableau": "data visualization",
        "power bi": "data visualization",
        "looker": "data visualization",
        "created etl": "data engineering",
        "built etl": "data engineering",
        "etl pipeline": "data engineering",
        "data pipeline": "data engineering",
        "data workflow": "data engineering",
        "data ingestion": "data engineering",
        "analyzed datasets": "data analysis",
        "data analysis": "data analysis",
        "statistical analysis": "data analysis",
        "data insights": "data analysis",
        "business insights": "data analysis",
        "analytics": "data analysis",
        "derive insights": "data analysis",
        "a/b testing": "experimentation",
        "ran experiments": "experimentation",
        "hypothesis testing": "experimentation",
        # Backend
        "built api": "api development",
        "designed api": "api development",
        "rest api": "api development",
        "graphql": "api development",
        "microservices": "distributed systems",
        "distributed system": "distributed systems",
        "database optimization": "database management",
        "query optimization": "database management",
        "sql tuning": "database management",
        "sql queries": "database management",
        "database design": "database management",
        # Frontend
        "responsive design": "frontend development",
        "built ui": "frontend development",
        "component library": "frontend development",
        "design system": "frontend development",
        # DevOps
        "ci/cd pipeline": "devops automation",
        "automated deployment": "devops automation",
        "containerized": "containerization",
        "docker": "containerization",
        "kubernetes": "container orchestration",
        # Cloud (synonym cluster)
        "aws": "cloud computing",
        "azure": "cloud computing",
        "gcp": "cloud computing",
        "google cloud": "cloud computing",
        "cloud infrastructure": "cloud computing",
        "cloud deployment": "cloud computing",
        # ML (synonym cluster)
        "trained model": "machine learning",
        "built model": "machine learning",
        "predictive model": "machine learning",
        "ml model": "machine learning",
        "machine learning model": "machine learning",
        "classification": "machine learning",
        "regression model": "machine learning",
        "deep learning": "neural networks",
        "neural network": "neural networks",
        # Pipeline/Workflow synonyms
        "pipeline": "data engineering",
        "workflow": "data engineering",
        "automation": "process automation",
        "automated": "process automation",
        "streamlined": "process automation",
        # General
        "led team": "technical leadership",
        "managed team": "technical leadership",
        "mentored": "technical leadership",
        "supervised": "technical leadership",
        "code review": "engineering practices",
        "unit test": "testing",
        "integration test": "testing",
        "automated test": "testing",
        "test coverage": "testing",
        "reduced latency": "performance optimization",
        "improved performance": "performance optimization",
        "optimized": "performance optimization",
        "optimization": "performance optimization",
        "scaled": "scalability",
        "high availability": "scalability",
        "load balancing": "scalability",
        # Deployment synonyms
        "deployed": "deployment",
        "production release": "deployment",
        "released to production": "deployment",
        "went live": "deployment",
        "streamlit": "deployment",
        "gradio": "deployment",
        "model serving": "deployment",
        "model deployment": "deployment",
        "hugging face": "deployment",
        # NLP concept cluster
        "nlp": "natural language processing",
        "natural language processing": "natural language processing",
        "text classification": "natural language processing",
        "text analysis": "natural language processing",
        "sentiment analysis": "natural language processing",
        "distilbert": "natural language processing",
        "bert": "natural language processing",
        "transformers": "natural language processing",
        "tokenization": "natural language processing",
        # Computer Vision concept cluster
        "computer vision": "computer vision",
        "image classification": "computer vision",
        "object detection": "computer vision",
        "cnn": "computer vision",
        "efficientnet": "computer vision",
        "resnet": "computer vision",
        "opencv": "computer vision",
        # ETL / Data pipeline synonyms (bidirectional)
        "etl": "data engineering",
        "data pipeline": "data engineering",
        "data processing": "data engineering",
        "data transformation": "data engineering",
    }

    def _normalize_phrases(self, text: str) -> set:
        """Extract normalized concept phrases from text."""
        text_lower = text.lower()
        concepts = set()
        for phrase, concept in self._PHRASE_MAP.items():
            if phrase in text_lower:
                concepts.add(concept)
        return concepts

    def _phrase_match_score(
        self,
        jd_responsibilities: List[str],
        resume_bullets: List[str],
    ) -> float:
        """Score based on normalized phrase overlap (0-100)."""
        jd_concepts = set()
        for resp in jd_responsibilities:
            jd_concepts |= self._normalize_phrases(resp)

        resume_concepts = set()
        for bullet in resume_bullets:
            resume_concepts |= self._normalize_phrases(bullet)

        if not jd_concepts:
            return 50.0  # No detectable phrases, neutral

        overlap = jd_concepts & resume_concepts
        return round((len(overlap) / len(jd_concepts)) * 100, 1)

    def match_responsibilities(
        self,
        jd_responsibilities: List[str],
        resume_bullets: List[str],
    ) -> float:
        """
        Score how well resume bullets cover JD responsibilities.
        Blends TF-IDF (70%) + phrase normalization (30%).

        Returns:
            Float 0-100 representing semantic overlap.
        """
        if not jd_responsibilities or not resume_bullets:
            return 0.0

        # === TF-IDF score ===
        all_docs = []
        jd_tokens_list = []
        resume_tokens_list = []

        for resp in jd_responsibilities:
            tokens = tokenize(resp)
            jd_tokens_list.append(tokens)
            all_docs.append(tokens)

        for bullet in resume_bullets:
            tokens = tokenize(bullet)
            resume_tokens_list.append(tokens)
            all_docs.append(tokens)

        idf = compute_idf(all_docs)

        match_scores = []
        for jd_tokens in jd_tokens_list:
            if not jd_tokens:
                continue
            jd_tf = compute_tf(jd_tokens)
            jd_tfidf = compute_tfidf(jd_tf, idf)

            best_similarity = 0.0
            for resume_tokens in resume_tokens_list:
                if not resume_tokens:
                    continue
                res_tf = compute_tf(resume_tokens)
                res_tfidf = compute_tfidf(res_tf, idf)
                sim = cosine_similarity(jd_tfidf, res_tfidf)
                best_similarity = max(best_similarity, sim)

            match_scores.append(best_similarity)

        if not match_scores:
            return 0.0

        tfidf_score = min((sum(match_scores) / len(match_scores)) * 100, 100)

        # === Phrase match score ===
        phrase_score = self._phrase_match_score(jd_responsibilities, resume_bullets)

        # === Embedding similarity (optional) ===
        embedding_score = self._embedding_similarity(jd_responsibilities, resume_bullets)

        # === Blend ===
        if embedding_score is not None:
            # 3-way blend with embeddings
            final = 0.5 * tfidf_score + 0.2 * phrase_score + 0.3 * embedding_score
        else:
            # Fallback: 2-way blend
            final = 0.7 * tfidf_score + 0.3 * phrase_score
        return round(final, 1)

    _embedding_model = None
    _embedding_cache = {}

    def _embedding_similarity(
        self, jd_responsibilities: List[str], resume_bullets: List[str]
    ):
        """
        Compute embedding cosine similarity if sentence-transformers is available.
        Returns 0-100 or None if not installed.
        """
        try:
            if SemanticMatcher._embedding_model is None:
                from sentence_transformers import SentenceTransformer
                SemanticMatcher._embedding_model = SentenceTransformer(
                    "all-MiniLM-L6-v2", device="cpu"
                )
                logger.info("Loaded embedding model: all-MiniLM-L6-v2")
        except ImportError:
            return None  # Graceful fallback

        model = SemanticMatcher._embedding_model

        # Encode (with caching)
        def encode_cached(text: str):
            if text not in SemanticMatcher._embedding_cache:
                SemanticMatcher._embedding_cache[text] = model.encode(text, normalize_embeddings=True)
            return SemanticMatcher._embedding_cache[text]

        # Best-match: for each JD resp, find most similar resume bullet
        import numpy as np
        scores = []
        for resp in jd_responsibilities:
            if not resp.strip():
                continue
            jd_emb = encode_cached(resp)
            best = 0.0
            for bullet in resume_bullets:
                if not bullet.strip():
                    continue
                res_emb = encode_cached(bullet)
                sim = float(np.dot(jd_emb, res_emb))
                best = max(best, sim)
            scores.append(best)

        if not scores:
            return 50.0

        avg = sum(scores) / len(scores)
        return round(min(avg * 100, 100), 1)

    def match_detailed(
        self,
        jd_responsibilities: List[str],
        resume_bullets: List[str],
    ) -> List[dict]:
        """
        Detailed per-responsibility matching.

        Returns:
            List of dicts with responsibility, best_match, and score.
        """
        if not jd_responsibilities or not resume_bullets:
            return []

        all_docs = []
        jd_tokens_list = []
        resume_tokens_list = []

        for resp in jd_responsibilities:
            tokens = tokenize(resp)
            jd_tokens_list.append(tokens)
            all_docs.append(tokens)

        for bullet in resume_bullets:
            tokens = tokenize(bullet)
            resume_tokens_list.append(tokens)
            all_docs.append(tokens)

        idf = compute_idf(all_docs)
        results = []

        for i, jd_tokens in enumerate(jd_tokens_list):
            if not jd_tokens:
                continue

            jd_tf = compute_tf(jd_tokens)
            jd_tfidf = compute_tfidf(jd_tf, idf)

            best_sim = 0.0
            best_bullet = ""
            for j, resume_tokens in enumerate(resume_tokens_list):
                if not resume_tokens:
                    continue
                res_tf = compute_tf(resume_tokens)
                res_tfidf = compute_tfidf(res_tf, idf)
                sim = cosine_similarity(jd_tfidf, res_tfidf)
                if sim > best_sim:
                    best_sim = sim
                    best_bullet = resume_bullets[j]

            results.append({
                "responsibility": jd_responsibilities[i],
                "best_match": best_bullet,
                "score": round(best_sim * 100, 1),
                "covered": best_sim > 0.15,  # Threshold for "covered"
            })

        return results

    def overall_similarity(self, text_a: str, text_b: str) -> float:
        """
        Compute overall TF-IDF cosine similarity between two texts.
        Returns 0-100.
        """
        tokens_a = tokenize(text_a)
        tokens_b = tokenize(text_b)

        if not tokens_a or not tokens_b:
            return 0.0

        idf = compute_idf([tokens_a, tokens_b])

        tfidf_a = compute_tfidf(compute_tf(tokens_a), idf)
        tfidf_b = compute_tfidf(compute_tf(tokens_b), idf)

        sim = cosine_similarity(tfidf_a, tfidf_b)
        return round(sim * 100, 1)
