"""
Synonym and alias mapping for ATS keyword matching.

This provides a basic but effective mapping for:
  - Technology aliases (e.g., "js" -> "javascript")
  - Skill synonyms (e.g., "machine learning" ↔ "ml")
  - Abbreviation expansion (e.g., "ci/cd" -> "continuous integration")

Design: Bidirectional -- if A maps to B, then B also maps to A.
"""

from typing import Dict, FrozenSet, List, Set


# ============================================================
# Raw synonym groups -- each list is a group of equivalent terms
# ============================================================

_SYNONYM_GROUPS: List[List[str]] = [
    # --- Programming Languages ---
    ["javascript", "js", "ecmascript"],
    ["typescript", "ts"],
    ["python", "py"],
    ["c#", "csharp", "c sharp"],
    ["c++", "cpp"],
    ["golang", "go"],

    # --- Frameworks & Libraries ---
    ["react", "reactjs", "react.js"],
    ["angular", "angularjs", "angular.js"],
    ["vue", "vuejs", "vue.js"],
    ["node.js", "nodejs", "node"],
    ["express", "expressjs", "express.js"],
    ["next.js", "nextjs"],
    ["django", "django framework"],
    ["flask", "flask framework"],
    ["fastapi", "fast api"],
    ["spring", "spring boot", "springboot"],

    # --- Data Science / ML ---
    ["machine learning", "ml"],
    ["deep learning", "dl"],
    ["natural language processing", "nlp"],
    ["computer vision", "cv"],
    ["artificial intelligence", "ai"],
    ["large language model", "llm", "large language models"],
    ["scikit-learn", "sklearn", "scikit learn"],
    ["tensorflow", "tf"],
    ["pytorch", "torch"],

    # --- Databases ---
    ["postgresql", "postgres", "psql"],
    ["mongodb", "mongo"],
    ["mysql", "my sql"],
    ["microsoft sql server", "mssql", "sql server"],
    ["dynamodb", "dynamo db"],
    ["elasticsearch", "elastic search", "es"],

    # --- Cloud & DevOps ---
    ["amazon web services", "aws"],
    ["google cloud platform", "gcp", "google cloud"],
    ["microsoft azure", "azure"],
    ["continuous integration", "continuous deployment", "ci/cd", "cicd", "ci cd"],
    ["kubernetes", "k8s"],
    ["infrastructure as code", "iac"],
    ["github actions", "gh actions"],

    # --- Data Tools ---
    ["apache spark", "spark", "pyspark"],
    ["apache airflow", "airflow"],
    ["apache kafka", "kafka"],
    ["power bi", "powerbi", "power-bi"],
    ["extract transform load", "etl"],
    ["data build tool", "dbt"],

    # --- Soft Skills ---
    ["communication skills", "communication", "verbal communication", "written communication"],
    ["problem solving", "problem-solving", "analytical thinking"],
    ["team player", "teamwork", "collaboration", "collaborative"],
    ["leadership", "team leadership", "people management"],
    ["project management", "program management"],
    ["agile", "agile methodology", "agile methodologies"],
    ["scrum", "scrum methodology"],

    # --- Concepts ---
    ["rest api", "restful api", "rest apis", "restful apis", "rest"],
    ["microservices", "micro services", "microservice architecture"],
    ["api", "apis", "application programming interface"],
    ["object oriented programming", "oop", "object-oriented"],
    ["test driven development", "tdd"],
    ["behavior driven development", "bdd"],
    ["a/b testing", "ab testing", "a-b testing", "split testing"],
    ["data visualization", "data viz"],
    ["statistical analysis", "statistics", "statistical methods"],
    ["data analysis", "data analytics"],
    ["version control", "git", "source control"],
]


# ============================================================
# Build lookup tables
# ============================================================

def _build_synonym_map() -> Dict[str, FrozenSet[str]]:
    """
    Build a mapping from each term to the set of all its synonyms.
    E.g., {"js": frozenset({"javascript", "js", "ecmascript"}), ...}
    """
    mapping: Dict[str, FrozenSet[str]] = {}
    for group in _SYNONYM_GROUPS:
        group_set = frozenset(term.lower() for term in group)
        for term in group_set:
            if term in mapping:
                # Merge existing group with new group
                merged = mapping[term] | group_set
                for t in merged:
                    mapping[t] = merged
            else:
                mapping[term] = group_set
    return mapping


SYNONYM_MAP: Dict[str, FrozenSet[str]] = _build_synonym_map()


def get_synonyms(term: str) -> FrozenSet[str]:
    """Get all synonyms for a term (including the term itself)."""
    return SYNONYM_MAP.get(term.lower().strip(), frozenset({term.lower().strip()}))


def are_synonyms(term_a: str, term_b: str) -> bool:
    """Check if two terms are synonyms of each other."""
    a = term_a.lower().strip()
    b = term_b.lower().strip()
    if a == b:
        return True
    return b in SYNONYM_MAP.get(a, frozenset())


def expand_keywords(keywords: List[str]) -> Set[str]:
    """
    Expand a list of keywords with all their synonyms.
    Returns the union of all terms + synonyms, lowercased.
    """
    expanded = set()
    for kw in keywords:
        kw_lower = kw.lower().strip()
        expanded.add(kw_lower)
        expanded.update(get_synonyms(kw_lower))
    return expanded
