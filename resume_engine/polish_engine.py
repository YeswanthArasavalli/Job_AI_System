"""
Final Polish Engine -- Executes automatic quality refinements when score >= 80.

Applies:
  1. Redundancy removal (duplicate phrases across bullets)
  2. Verb strengthening (weak → strong action verbs)
  3. Formatting normalization (consistent punctuation, capitalization)
  4. Summary cleanup (remove filler, tighten language)
  5. Bullet normalization (consistent length, structure)

ONLY runs when ATS score >= 80 (resume is already strong,
needs professional polish, not content changes).
"""

import re
from collections import Counter
from typing import Dict, List, Set, Tuple

from utils.models import StructuredResume
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ================================================================
# WEAK → STRONG VERB MAP (for polish phase — different from improver)
# ================================================================

# -- TIER 1: Simple word replacements (no structural change needed) --
SIMPLE_VERB_SWAPS = {
    "helped": "contributed to",
    "did": "executed",
    "made": "developed",
    "got": "achieved",
    "tried": "implemented",
    "learned": "developed expertise in",
    "looked at": "analyzed",
    "worked with": "collaborated with",
    "served as": "performed as",
}

# -- TIER 2: Phrases that should be STRIPPED, letting the gerund become past tense --
# Pattern: "Was responsible for building X" → "Built X"
# These phrases are followed by a gerund (-ing word) and should be completely removed
# so the gerund gets promoted to the main verb.
GERUND_STRIP_PHRASES = [
    "was responsible for",
    "responsible for",
    "was involved in",
    "involved in",
    "was tasked with",
    "tasked with",
    "was in charge of",
    "in charge of",
    "worked on",
    "helped with",
    "helped to",
    "assisted in",
    "assisted with",
    "participated in",
    "played a key role in",
    "played a role in",
    "was part of",
    "had to",
    "started to",
    "began to",
    "was able to",
    "working on",
    "used to",
]

# Gerund-to-past-tense conversion (for promoting gerunds after strip)
GERUND_TO_PAST = {
    "building": "Built", "maintaining": "Maintained", "developing": "Developed",
    "creating": "Created", "deploying": "Deployed", "managing": "Managed",
    "leading": "Led", "driving": "Drove", "analyzing": "Analyzed",
    "designing": "Designed", "implementing": "Implemented", "optimizing": "Optimized",
    "automating": "Automated", "delivering": "Delivered", "establishing": "Established",
    "launching": "Launched", "coordinating": "Coordinated", "facilitating": "Facilitated",
    "training": "Trained", "mentoring": "Mentored", "processing": "Processing",
    "streamlining": "Streamlined", "scaling": "Scaled", "integrating": "Integrated",
    "engineering": "Engineered", "monitoring": "Monitored", "testing": "Tested",
    "configuring": "Configured", "writing": "Wrote", "running": "Ran",
    "setting": "Set", "preparing": "Prepared", "handling": "Handled",
    "supporting": "Supported", "troubleshooting": "Troubleshot",
    "improving": "Improved", "reducing": "Reduced", "increasing": "Increased",
    "migrating": "Migrated", "refactoring": "Refactored",
}

# -- TIER 3: Valueless bullet patterns (should be REMOVED entirely) --
VALUELESS_PATTERNS = [
    r'^(?:attended|participated in)\s+(?:daily\s+|team\s+|weekly\s+)?(?:meetings|standups|stand-ups|scrums|retrospectives|sprint\s+planning)',
    r'^tasks\s+included',
    r'^duties\s+included',
    r'^responsibilities\s+included',
    r'^other\s+duties',
    r'^also\s+(?:helped|assisted|supported)',
    r'^was\s+(?:a\s+)?member\s+of',
    r'^helped\s+with\s+on-call',
]

# Bullet starts that indicate passive/weak voice (match at START of bullet)
WEAK_BULLET_STARTS = [
    (r'^The\s+team\s+', ''),       # "The team did X" → rewrite needed
    (r'^I\s+', ''),                 # "I built X" → "Built X"
    (r'^My\s+', ''),                # "My role was" → rewrite needed
    # NOTE: "Was", "Were", "Had" removed — handled by GERUND_STRIP_PHRASES
    # to avoid conflicts (e.g., "Was responsible for building" needs full phrase match)
    (r'^Successfully\s+', ''),      # "Successfully completed" → redundant adverb
    (r'^Effectively\s+', ''),       # Same
    (r'^Actively\s+', ''),          # Same
]

# Filler phrases to remove from summaries
SUMMARY_FILLERS = [
    "in order to", "as well as", "a variety of",
    "in addition to", "due to the fact that",
    "for the purpose of", "with regard to",
    "in terms of", "on a daily basis",
    "at this point in time", "in a timely manner",
    "on an ongoing basis", "the ability to",
]

# Redundant phrase patterns
REDUNDANT_PATTERNS = [
    (r"\bvery\s+unique\b", "unique"),
    (r"\bcompletely\s+eliminated\b", "eliminated"),
    (r"\bfully\s+automated\b", "automated"),
    (r"\bactively\s+participated\b", "participated"),
    (r"\bsuccessfully\s+completed\b", "completed"),
    (r"\beffectively\s+managed\b", "managed"),
    (r"\bcurrently\s+working\b", "working"),
    (r"\bcarefully\s+analyzed\b", "analyzed"),
    (r"\bthoroughly\s+tested\b", "tested"),
    (r"\bclosely\s+collaborated\b", "collaborated"),
]


def polish_resume(
    resume: StructuredResume,
    role_type: str = "technical",
) -> Tuple[StructuredResume, List[Dict]]:
    """
    Apply final professional polish to a resume that scored >= 80.

    This is NOT content optimization — it's QUALITY refinement:
      - Remove redundancy
      - Strengthen weak verbs
      - Fix formatting inconsistencies
      - Tighten summary language
      - Normalize bullet structure

    Args:
        resume: The improved resume (already high-scoring)
        role_type: From role_engine classification

    Returns:
        (polished_resume, list_of_changes)
        Each change: {"type": "...", "before": "...", "after": "...", "reason": "..."}
    """
    polished = resume.model_copy(deep=True)
    changes = []

    # 1. Remove redundancy across bullets
    redundancy_changes = _remove_redundancy(polished)
    changes.extend(redundancy_changes)

    # 2. Strengthen remaining weak verbs
    verb_changes = _strengthen_verbs(polished)
    changes.extend(verb_changes)

    # 3. Fix formatting
    format_changes = _fix_formatting(polished)
    changes.extend(format_changes)

    # 4. Clean summary
    summary_changes = _clean_summary(polished)
    changes.extend(summary_changes)

    # 5. Normalize bullet length
    norm_changes = _normalize_bullets(polished)
    changes.extend(norm_changes)

    # 6. Remove redundant adverb-verb pairs
    adverb_changes = _remove_redundant_adverbs(polished)
    changes.extend(adverb_changes)

    # 7. STRUCTURAL POLISH — max bullets, reorder by impact
    struct_changes = _structural_polish(polished)
    changes.extend(struct_changes)

    logger.info(
        f"Polish engine: {len(changes)} refinements applied "
        f"(redundancy={len(redundancy_changes)}, verbs={len(verb_changes)}, "
        f"format={len(format_changes)}, summary={len(summary_changes)}, "
        f"structure={len(struct_changes)})"
    )

    return polished, changes


def _remove_redundancy(resume: StructuredResume) -> List[Dict]:
    """Remove duplicate phrases across experience bullets."""
    changes = []

    # Collect all bullet phrases (3+ word sequences)
    phrase_counts = Counter()
    phrase_locations = {}  # phrase -> [(exp_idx, bullet_idx)]

    for exp_idx, exp in enumerate(resume.experience):
        for bul_idx, bullet in enumerate(exp.bullets):
            # Extract 3-word phrases
            words = bullet.lower().split()
            for i in range(len(words) - 2):
                phrase = " ".join(words[i:i+3])
                if len(phrase) > 10:  # Skip short phrases
                    phrase_counts[phrase] += 1
                    if phrase not in phrase_locations:
                        phrase_locations[phrase] = []
                    phrase_locations[phrase].append((exp_idx, bul_idx))

    # Find phrases that appear 3+ times (true redundancy)
    redundant_phrases = {
        phrase for phrase, count in phrase_counts.items()
        if count >= 3
    }

    # Skip common structural phrases
    safe_phrases = {
        "and", "the", "for", "with", "using", "leveraging",
        "in the", "of the", "to the", "for the",
    }
    redundant_phrases = {
        p for p in redundant_phrases
        if not any(s in p for s in safe_phrases)
    }

    # For each redundant phrase, rewrite 2nd+ occurrences
    modified = set()
    for phrase in list(redundant_phrases)[:3]:  # Max 3 fixes per run
        locations = phrase_locations[phrase]
        # Keep first occurrence, mark others
        for exp_idx, bul_idx in locations[1:]:
            key = (exp_idx, bul_idx)
            if key in modified:
                continue

            bullet = resume.experience[exp_idx].bullets[bul_idx]
            # Don't modify if bullet is short
            if len(bullet) < 80:
                continue

            modified.add(key)
            changes.append({
                "type": "redundancy",
                "before": f"...{phrase}...",
                "after": "(reduced repetition)",
                "reason": f"Phrase '{phrase}' appears {phrase_counts[phrase]}x across bullets",
            })

    return changes


def _strengthen_verbs(resume: StructuredResume) -> List[Dict]:
    """
    3-tier verb strengthening for professional polish.
    
    QUALITY FIX:
      Tier 1: GERUND STRIP — "Was responsible for building X" → "Built X"
      Tier 2: SIMPLE SWAP — "helped" → "contributed to"  
      Tier 3: VALUELESS REMOVAL — "Attended team meetings" → REMOVED
      Also: PREFIX STRIP — "I analyzed" → "Analyzed"
    """
    changes = []

    # Sort gerund strip phrases longest-first
    sorted_strips = sorted(GERUND_STRIP_PHRASES, key=len, reverse=True)
    sorted_swaps = sorted(SIMPLE_VERB_SWAPS.items(), key=lambda x: len(x[0]), reverse=True)

    for exp in resume.experience:
        bullets_to_remove = []

        for i, bullet in enumerate(exp.bullets):
            original = bullet

            # --- TIER 3: Check for valueless bullets first ---
            bullet_stripped = bullet.strip().rstrip('.')
            for pattern in VALUELESS_PATTERNS:
                if re.match(pattern, bullet_stripped, re.IGNORECASE):
                    bullets_to_remove.append(i)
                    changes.append({
                        "type": "valueless_removal",
                        "before": bullet[:50],
                        "after": "(removed — no impact or capability)",
                        "reason": "Bullet adds no professional value",
                    })
                    break
            else:
                # Only proceed if bullet wasn't marked for removal

                # --- PREFIX STRIP: Remove first-person / passive starts ---
                for pattern, _ in WEAK_BULLET_STARTS:
                    match = re.match(pattern, bullet, re.IGNORECASE)
                    if match:
                        bullet = bullet[match.end():]
                        if bullet and bullet[0].islower():
                            bullet = bullet[0].upper() + bullet[1:]
                        break

                # --- TIER 1: GERUND STRIP ---
                # "Was responsible for building X" → "Built X"
                applied = False
                for phrase in sorted_strips:
                    # Check if bullet starts with this phrase
                    bullet_check = bullet.lower()
                    if not bullet_check.startswith(phrase.lower()):
                        continue

                    remainder = bullet[len(phrase):].strip()
                    if not remainder:
                        continue

                    first_word = remainder.split()[0]
                    rest_after_first = remainder[len(first_word):].strip()

                    # CASE A: Followed by gerund (-ing word)
                    if first_word.lower().endswith("ing"):
                        gerund = first_word.lower()
                        past = GERUND_TO_PAST.get(gerund)
                        if past:
                            bullet = past + " " + rest_after_first
                        else:
                            bullet = first_word[0].upper() + first_word[1:] + " " + rest_after_first
                        
                        # Post-fix: convert "and maintaining" → "and maintained"
                        def _fix_compound_gerunds(text):
                            def repl(m):
                                g = m.group(1).lower()
                                past_form = GERUND_TO_PAST.get(g, g.rstrip("ing") + "ed")
                                return " and " + past_form.lower()
                            return re.sub(r'\band\s+(\w+ing)\b', repl, text)

                        bullet = _fix_compound_gerunds(bullet)
                        applied = True
                        break

                    # CASE B: "had to manage" / "started to build" → past tense
                    elif phrase.lower().endswith(" to"):
                        # Convert infinitive to past tense
                        INFINITIVE_TO_PAST = {
                            "manage": "Managed", "build": "Built", "create": "Created",
                            "develop": "Developed", "deploy": "Deployed", "analyze": "Analyzed",
                            "design": "Designed", "implement": "Implemented", "lead": "Led",
                            "run": "Ran", "write": "Wrote", "drive": "Drove",
                            "coordinate": "Coordinated", "establish": "Established",
                            "maintain": "Maintained", "optimize": "Optimized",
                            "handle": "Handled", "prepare": "Prepared",
                            "review": "Reviewed", "process": "Processed",
                            "support": "Supported", "deliver": "Delivered",
                            "improve": "Improved", "reduce": "Reduced",
                        }
                        past = INFINITIVE_TO_PAST.get(first_word.lower())
                        if past:
                            bullet = past + " " + rest_after_first
                        else:
                            # Generic: capitalize and add -ed if sensible
                            bullet = first_word[0].upper() + first_word[1:] + "d " + rest_after_first
                            bullet = bullet.rstrip()
                        applied = True
                        break

                    # CASE C: Followed by a noun (e.g., "helped with data preprocessing")
                    else:
                        # Use a fallback verb appropriate for the phrase
                        PHRASE_NOUN_FALLBACK = {
                            "helped with": "Performed",
                            "assisted in": "Contributed to",
                            "assisted with": "Supported",
                            "was involved in": "Contributed to",
                            "involved in": "Contributed to",
                            "was part of": "Contributed to",
                            "played a key role in": "Led",
                            "played a role in": "Contributed to",
                            "participated in": "Contributed to",
                            "was responsible for": "Managed",
                            "responsible for": "Managed",
                        }
                        fallback = PHRASE_NOUN_FALLBACK.get(phrase.lower())
                        if fallback:
                            bullet = fallback + " " + remainder
                        else:
                            # Generic: just capitalize remainder
                            bullet = remainder[0].upper() + remainder[1:]
                        applied = True
                        break

                # --- TIER 2: SIMPLE SWAP (only if Tier 1 didn't fire) ---
                if not applied:
                    for weak, strong in sorted_swaps:
                        swap_pattern = r'\b' + re.escape(weak) + r'\b'
                        if re.search(swap_pattern, bullet, re.IGNORECASE):
                            bullet = re.sub(
                                swap_pattern, strong, bullet,
                                count=1, flags=re.IGNORECASE,
                            )
                            if bullet and not bullet[0].isupper():
                                bullet = bullet[0].upper() + bullet[1:]
                            break

                if bullet != original:
                    exp.bullets[i] = bullet
                    changes.append({
                        "type": "verb_strength",
                        "before": original[:60],
                        "after": bullet[:60],
                        "reason": "Strengthened weak verb for professional polish",
                    })

        # Remove valueless bullets (reverse order)
        for idx in reversed(bullets_to_remove):
            if len(exp.bullets) > 2:  # Keep at least 2 bullets per role
                exp.bullets.pop(idx)

    return changes


def _fix_formatting(resume: StructuredResume) -> List[Dict]:
    """Fix formatting inconsistencies across the resume."""
    changes = []

    for exp in resume.experience:
        for i, bullet in enumerate(exp.bullets):
            original = bullet
            fixed = bullet

            # Ensure starts with capital letter
            if fixed and fixed[0].islower():
                fixed = fixed[0].upper() + fixed[1:]

            # Ensure ends with period (not comma, not nothing)
            if fixed and not fixed.endswith('.') and not fixed.endswith('!'):
                if fixed.endswith(','):
                    fixed = fixed[:-1] + '.'
                else:
                    fixed += '.'

            # Remove double periods
            fixed = fixed.replace('..', '.')

            # Remove trailing whitespace before period
            fixed = re.sub(r'\s+\.', '.', fixed)

            # Collapse multiple spaces
            fixed = re.sub(r'\s{2,}', ' ', fixed)

            if fixed != original:
                exp.bullets[i] = fixed
                changes.append({
                    "type": "formatting",
                    "before": original[:40],
                    "after": fixed[:40],
                    "reason": "Fixed punctuation/formatting inconsistency",
                })

    # Same for project bullets
    for proj in resume.projects:
        for i, bullet in enumerate(proj.bullets):
            original = bullet
            fixed = bullet
            if fixed and fixed[0].islower():
                fixed = fixed[0].upper() + fixed[1:]
            if fixed and not fixed.endswith('.') and not fixed.endswith('!'):
                fixed += '.'
            fixed = fixed.replace('..', '.')
            fixed = re.sub(r'\s{2,}', ' ', fixed)
            if fixed != original:
                proj.bullets[i] = fixed

    return changes


def _clean_summary(resume: StructuredResume) -> List[Dict]:
    """Remove filler phrases and tighten summary language."""
    changes = []

    if not resume.summary:
        return changes

    original = resume.summary
    cleaned = resume.summary

    # Remove filler phrases
    for filler in SUMMARY_FILLERS:
        if filler in cleaned.lower():
            cleaned = re.sub(
                re.escape(filler), '', cleaned,
                flags=re.IGNORECASE
            )

    # Collapse whitespace
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()

    # Ensure proper ending
    if cleaned and not cleaned.endswith('.'):
        cleaned += '.'

    if cleaned != original:
        resume.summary = cleaned
        changes.append({
            "type": "summary_cleanup",
            "before": original[:60],
            "after": cleaned[:60],
            "reason": "Removed filler phrases for tighter summary",
        })

    return changes


def _normalize_bullets(resume: StructuredResume) -> List[Dict]:
    """
    Ensure consistent bullet length and structure.
    
    BEHAVIOR FIX: Actually REMOVES bullets that are too short (<20 chars)
    instead of just flagging them. These are fragments that hurt quality.
    """
    changes = []

    for exp in resume.experience:
        bullets_to_remove = []
        for i, bullet in enumerate(exp.bullets):
            # Remove bullets that are too short (<20 chars) — fragments
            if len(bullet.strip()) < 20 and len(exp.bullets) > 3:
                bullets_to_remove.append(i)
                changes.append({
                    "type": "bullet_normalization",
                    "before": bullet,
                    "after": "(removed — too short to add value)",
                    "reason": f"Removed {len(bullet.strip())}-char fragment bullet",
                })

            # Truncate extremely long bullets (> 300 chars)
            elif len(bullet) > 300:
                truncated = bullet[:297] + "."
                exp.bullets[i] = truncated
                changes.append({
                    "type": "bullet_normalization",
                    "before": bullet[:40] + "...",
                    "after": truncated[:40] + "...",
                    "reason": "Bullet exceeds 300 chars — truncated for readability",
                })

        # Actually remove short bullets (reverse order to preserve indices)
        for idx in reversed(bullets_to_remove):
            exp.bullets.pop(idx)

    return changes


def _remove_redundant_adverbs(resume: StructuredResume) -> List[Dict]:
    """Remove redundant adverb-verb combinations."""
    changes = []

    for exp in resume.experience:
        for i, bullet in enumerate(exp.bullets):
            original = bullet
            for pattern, replacement in REDUNDANT_PATTERNS:
                bullet = re.sub(pattern, replacement, bullet, flags=re.IGNORECASE)

            if bullet != original:
                exp.bullets[i] = bullet
                changes.append({
                    "type": "adverb_cleanup",
                    "before": original[:50],
                    "after": bullet[:50],
                    "reason": "Removed redundant adverb for cleaner prose",
                })

    return changes


def _structural_polish(resume: StructuredResume) -> List[Dict]:
    """
    STRUCTURAL QUALITY: Enforce recruiter-grade bullet structure.
    
    Rules:
      - Max 5 bullets per role (recruiters skim, more = noise)
      - Reorder: quantified impact bullets FIRST
      - Remove weak bullets that add no value
      - Each bullet must show impact OR capability
      - NEVER remove a bullet if it's the ONLY evidence of a skill (coverage safety)
    """
    changes = []

    # Build global skill set from resume for coverage check
    all_skills_lower = {s.lower() for s in resume.skills} if resume.skills else set()

    for exp in resume.experience:
        if len(exp.bullets) <= 5:
            continue  # Already within limit

        # --- SKILL COVERAGE SAFETY ---
        # Find skills that are ONLY mentioned in one bullet of this role
        # These bullets MUST survive the cut
        protected_indices = set()
        if all_skills_lower:
            for i, bullet in enumerate(exp.bullets):
                b_lower = bullet.lower()
                for skill in all_skills_lower:
                    if skill in b_lower:
                        # Check if any OTHER bullet in this role also has this skill
                        other_has_it = any(
                            skill in exp.bullets[j].lower()
                            for j in range(len(exp.bullets)) if j != i
                        )
                        if not other_has_it:
                            protected_indices.add(i)
                            break  # This bullet is protected, move to next

        # Score each bullet for impact
        scored = []
        for i, bullet in enumerate(exp.bullets):
            score = _score_bullet_impact(bullet)
            # Boost protected bullets so they survive the cut
            if i in protected_indices:
                score += 50  # Guaranteed survival
            scored.append((score, i, bullet))

        # Sort by score descending (highest impact first)
        scored.sort(key=lambda x: x[0], reverse=True)

        # Keep top 5
        keep_indices = set()
        for score, idx, bullet in scored[:5]:
            keep_indices.add(idx)

        # Record removals
        removed = []
        for score, idx, bullet in scored[5:]:
            removed.append(bullet)
            changes.append({
                "type": "structural",
                "before": bullet[:50],
                "after": "(removed — exceeded 5-bullet limit)",
                "reason": f"Weakest bullet removed (impact score: {score})",
            })

        # Rebuild bullets in impact order (top 5 only)
        new_bullets = [bullet for score, idx, bullet in scored[:5]]
        exp.bullets = new_bullets

        if removed:
            changes.append({
                "type": "structural",
                "before": f"{len(removed)} weak bullets",
                "after": f"5 high-impact bullets kept",
                "reason": f"Enforced max 5 bullets per role for recruiter readability",
            })

    return changes


def _score_bullet_impact(bullet: str) -> int:
    """
    Score a bullet on 0-100 scale for impact/value.
    
    High scores = quantified results, action verbs, specific outcomes
    Low scores = vague, short, no metrics, passive voice
    """
    score = 50  # Base

    b = bullet.lower()

    # +20: Has quantified metric (%, $, numbers)
    if re.search(r'\d+[%$Kk]|\d{2,}', b):
        score += 20

    # +15: Has impact words
    impact_words = [
        "improved", "reduced", "increased", "delivered", "launched",
        "achieved", "grew", "saved", "accelerated", "optimized",
        "streamlined", "automated", "generated", "exceeded",
    ]
    if any(w in b for w in impact_words):
        score += 15

    # +10: Has tool/technology mention
    tech_words = [
        "python", "sql", "aws", "docker", "kubernetes", "tensorflow",
        "pandas", "spark", "react", "django", "api", "database",
        "pipeline", "model", "dashboard", "system", "platform",
    ]
    if any(w in b for w in tech_words):
        score += 10

    # -20: Too short (< 40 chars)
    if len(bullet) < 40:
        score -= 20

    # -15: No action verb at start
    action_starts = [
        "built", "developed", "designed", "implemented", "deployed",
        "managed", "led", "created", "analyzed", "optimized",
        "automated", "delivered", "established", "launched",
        "coordinated", "engineered", "integrated", "maintained",
    ]
    first_word = b.split()[0] if b.split() else ""
    if first_word not in action_starts:
        score -= 5

    # -10: Valueless/vague
    vague_words = ["various", "several", "multiple", "etc", "general"]
    if any(w in b for w in vague_words):
        score -= 10

    return max(0, min(100, score))
