"""
Resume parser -- loads, validates, and normalizes the master resume.

Supports:
  - JSON format (preferred, canonical)
  - Plain text format (converted to structured JSON via best-effort parsing)

Includes a production-grade JSON repair layer for handling messy LLM output.
"""

import json
import os
import re
from typing import Optional

from utils.logger import setup_logger
from utils.models import (
    ContactInfo,
    StructuredResume,
    ExperienceEntry,
    EducationEntry,
    ProjectEntry,
    CertificationEntry,
)

logger = setup_logger(__name__)


# ================================================================
# Resume Loading
# ================================================================

def load_resume(path: str) -> StructuredResume:
    """
    Load a master resume from disk.

    Args:
        path: Path to the resume file (.json or .txt)

    Returns:
        StructuredResume -- validated Pydantic model.

    Raises:
        FileNotFoundError: if the file doesn't exist.
        ValueError: if the file can't be parsed.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Resume file not found: {path}")

    ext = os.path.splitext(path)[1].lower()

    if ext == ".json":
        return _load_json_resume(path)
    elif ext == ".txt":
        return _load_text_resume(path)
    else:
        raise ValueError(f"Unsupported resume format: {ext}  (use .json or .txt)")


def _load_json_resume(path: str) -> StructuredResume:
    """Load and validate a JSON resume."""
    logger.info(f"Loading JSON resume from: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    try:
        resume = StructuredResume(**data)
        logger.info(
            f"Resume loaded -- {resume.contact.name} | "
            f"{len(resume.skills)} skills | "
            f"{len(resume.experience)} experience entries"
        )
        return resume
    except Exception as e:
        logger.error(f"Resume validation failed: {e}")
        raise ValueError(f"Invalid resume JSON structure: {e}") from e


def _load_text_resume(path: str) -> StructuredResume:
    """
    Best-effort parse of a plain text resume.
    Creates a minimal StructuredResume with the text stored in summary.
    For production use, prefer JSON format.
    """
    logger.warning(
        f"Loading plain text resume from: {path}. "
        "JSON format is recommended for better results."
    )

    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        raise ValueError("Resume file is empty")

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    name = lines[0] if lines else "Unknown"

    return StructuredResume(
        contact=ContactInfo(name=name),
        summary=text,
    )


def resume_to_json_string(resume: StructuredResume) -> str:
    """Serialize a StructuredResume to a formatted JSON string for LLM input."""
    return resume.model_dump_json(indent=2)


# ================================================================
# JSON Repair Layer (handles messy LLM output)
# ================================================================

def repair_json(raw: str) -> str:
    """
    Multi-strategy JSON repair pipeline.

    Strategies (tried in order):
      1. Direct parse (no fix needed)
      2. Strip markdown code fences
      3. Extract JSON object with regex
      4. Fix trailing commas
      5. Fix unquoted keys
      6. Balance braces (truncated output)

    Returns:
        Cleaned JSON string, or raises ValueError if all strategies fail.
    """
    # Strategy 1: Direct parse
    try:
        json.loads(raw.strip())
        return raw.strip()
    except json.JSONDecodeError:
        pass

    # Strategy 2: Strip markdown fences
    cleaned = _strip_code_fences(raw)
    try:
        json.loads(cleaned)
        logger.debug("JSON repair: fixed by stripping code fences")
        return cleaned
    except json.JSONDecodeError:
        pass

    # Strategy 3: Extract JSON object with regex
    extracted = _extract_json_object(cleaned)
    if extracted:
        try:
            json.loads(extracted)
            logger.debug("JSON repair: fixed by regex extraction")
            return extracted
        except json.JSONDecodeError:
            cleaned = extracted  # Use extracted for further fixing

    # Strategy 4: Fix trailing commas
    fixed_commas = _fix_trailing_commas(cleaned)
    try:
        json.loads(fixed_commas)
        logger.debug("JSON repair: fixed trailing commas")
        return fixed_commas
    except json.JSONDecodeError:
        pass

    # Strategy 5: Balance braces (truncated output)
    balanced = _balance_braces(fixed_commas)
    try:
        json.loads(balanced)
        logger.debug("JSON repair: fixed by balancing braces")
        return balanced
    except json.JSONDecodeError:
        pass

    # All strategies failed
    raise ValueError(
        f"JSON repair failed after all strategies. "
        f"Raw output starts with: {raw[:200]}..."
    )


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```)."""
    cleaned = text.strip()

    # Handle ```json or ``` at the start
    if cleaned.startswith("```"):
        try:
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
        except ValueError:
            cleaned = cleaned[3:]

    # Handle ``` at the end
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    return cleaned.strip()


def _extract_json_object(text: str) -> Optional[str]:
    """Extract the first complete JSON object {...} from text."""
    # Find the first opening brace
    start = text.find("{")
    if start == -1:
        return None

    # Find the matching closing brace
    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    # If we ran out of text, return what we have (will be fixed by brace balancer)
    return text[start:] if depth > 0 else None


def _fix_trailing_commas(text: str) -> str:
    """Remove trailing commas before ] or }."""
    # Remove comma before closing bracket/brace (with optional whitespace)
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def _balance_braces(text: str) -> str:
    """Close unclosed braces/brackets in truncated JSON."""
    stack = []
    in_string = False
    escape_next = False

    for char in text:
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue

        if char in "{[":
            stack.append("}" if char == "{" else "]")
        elif char in "}]":
            if stack and stack[-1] == char:
                stack.pop()

    # Close any remaining open braces/brackets (remove trailing comma first)
    result = text.rstrip().rstrip(",")
    for closer in reversed(stack):
        result += closer

    return result


# ================================================================
# LLM Output Parsing
# ================================================================

def parse_llm_resume_output(raw_output: str) -> StructuredResume:
    """
    Parse raw LLM output text into a validated StructuredResume.

    Uses the multi-strategy JSON repair pipeline to handle:
      - Markdown code fences
      - Trailing commas
      - Truncated output
      - Extra text before/after JSON
    """
    try:
        cleaned = repair_json(raw_output)
        data = json.loads(cleaned)
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f"Failed to parse LLM output as JSON: {e}")
        logger.debug(f"Raw output:\n{raw_output[:500]}")
        raise ValueError(f"LLM output is not valid JSON: {e}") from e

    try:
        resume = StructuredResume(**data)
        logger.info(
            f"Parsed LLM resume -- {resume.contact.name} | "
            f"{len(resume.skills)} skills | "
            f"{len(resume.experience)} experience entries"
        )
        return resume
    except Exception as e:
        logger.error(f"LLM output doesn't match resume schema: {e}")
        raise ValueError(f"LLM output doesn't match StructuredResume schema: {e}") from e