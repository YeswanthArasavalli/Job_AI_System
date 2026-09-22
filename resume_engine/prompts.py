"""
LLM prompt templates for resume tailoring and JD analysis.

Design principles:
  - Prompts enforce strict JSON output (no markdown, no commentary)
  - Schema is embedded in the prompt so the LLM knows the exact structure
  - System prompt sets role; user prompt carries the data
"""

# ============================================================
# JSON schema snippet (embedded in prompts so the LLM conforms)
# ============================================================

RESUME_JSON_SCHEMA = """{
  "contact": {
    "name": "string",
    "email": "string",
    "phone": "string",
    "location": "string",
    "linkedin": "string",
    "portfolio": "string"
  },
  "title": "string -- targeted job title matching the JD",
  "summary": "string -- 3-4 sentence professional summary tailored to JD",
  "skills": ["string -- list of relevant skills, max 15, prioritized by JD relevance"],
  "experience": [
    {
      "role": "string",
      "company": "string",
      "duration": "string",
      "location": "string",
      "bullets": ["string -- achievement-oriented bullets with metrics, max 5 per role"]
    }
  ],
  "education": [
    {
      "degree": "string",
      "institution": "string",
      "year": "string",
      "gpa": "string",
      "details": "string"
    }
  ],
  "projects": [
    {
      "name": "string",
      "description": "string",
      "technologies": ["string"],
      "bullets": ["string"]
    }
  ],
  "certifications": [
    {
      "name": "string",
      "issuer": "string",
      "year": "string"
    }
  ]
}"""


# ============================================================
# Resume Tailoring Prompt
# ============================================================

SYSTEM_PROMPT_RESUME_TAILOR = """You are a resume rewriting assistant. You will be given an EXISTING resume and a job description. Your job is to REWRITE the existing resume to better match the job description.

ABSOLUTE RULES -- VIOLATION OF ANY RULE MEANS FAILURE:

NEVER CHANGE:
- Candidate's name (keep EXACTLY as provided)
- Candidate's email, phone, location, LinkedIn, portfolio
- Company names in experience (keep EXACTLY as provided)
- Job titles in experience (keep EXACTLY as provided -- do NOT upgrade "Developer" to "Senior Developer")
- Education entries (keep EXACTLY as provided)
- Certifications (keep EXACTLY as provided)
- Employment dates/durations (keep EXACTLY as provided)

YOU MAY ONLY:
- Rewrite the professional summary to align with the JD
- Rephrase experience bullet points (same achievements, better wording)
- Reorder skills by relevance to JD (most relevant first)
- Add JD-relevant keywords to bullet points IF the candidate actually did that work
- Improve clarity and impact of existing bullet points
- Adjust the target title to match the JD role name

YOU MUST NOT:
- Invent new companies or roles
- Add experience entries that don't exist in the original
- Add skills the candidate clearly doesn't have
- Fabricate metrics or achievements
- Create new projects that aren't in the original
- Change the candidate's identity in any way

OUTPUT FORMAT:
- Output ONLY valid JSON matching the schema below
- No markdown, no code fences, no commentary
- Just the raw JSON object"""


def build_resume_tailoring_prompt(master_resume_json: str, job_description: str) -> list:
    """
    Build the messages list for resume tailoring.
    Embeds identity fields to help the LLM lock onto the correct person.

    Returns a list of message dicts ready for ollama.chat().
    """
    # Extract name from resume JSON for explicit locking in prompt
    try:
        resume_data = __import__("json").loads(master_resume_json)
        candidate_name = resume_data.get("contact", {}).get("name", "THE CANDIDATE")
        companies = [exp.get("company", "") for exp in resume_data.get("experience", [])]
        companies_str = ", ".join(c for c in companies if c)
    except Exception:
        candidate_name = "THE CANDIDATE"
        companies_str = "(from the resume)"

    user_content = f"""TASK: Modify ONLY the wording of this existing resume to better match the target job description.

CANDIDATE NAME (DO NOT CHANGE): {candidate_name}
COMPANIES (DO NOT CHANGE): {companies_str}

=== TARGET JOB DESCRIPTION ===
{job_description}

=== CANDIDATE'S EXISTING RESUME (JSON) -- MODIFY THIS, DO NOT CREATE A NEW ONE ===
{master_resume_json}

=== REQUIRED OUTPUT SCHEMA ===
{RESUME_JSON_SCHEMA}

REMEMBER: The output MUST have name="{candidate_name}" and the SAME companies as the input.
Return ONLY the modified resume as a single JSON object. No commentary."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT_RESUME_TAILOR},
        {"role": "user", "content": user_content},
    ]


# ============================================================
# JD Analysis / Keyword Extraction Prompt
# ============================================================

SYSTEM_PROMPT_JD_ANALYSIS = """You are a job description analysis expert.

RULES:
1. Output ONLY valid JSON. No markdown. No explanation. No code fences.
2. Extract ALL relevant information from the job description.
3. Be thorough -- capture every skill, technology, and requirement mentioned.
4. Distinguish between required and preferred/nice-to-have skills.
5. Extract the minimum years of experience if mentioned.
6. Identify core keywords an ATS would scan for."""


def build_jd_analysis_prompt(job_description: str) -> list:
    """
    Build the messages list for JD analysis / keyword extraction.

    Returns a list of message dicts ready for ollama.chat().
    """
    schema = """{
  "job_title": "string",
  "company": "string",
  "location": "string",
  "required_skills": ["string -- skills explicitly required"],
  "preferred_skills": ["string -- nice-to-have skills"],
  "required_experience_years": integer_or_null,
  "education_requirements": ["string"],
  "responsibilities": ["string -- key responsibilities"],
  "keywords": ["string -- all ATS-relevant keywords and phrases"]
}"""

    user_content = f"""TASK: Analyze the following job description and extract structured information.

=== JOB DESCRIPTION ===
{job_description}

=== REQUIRED OUTPUT SCHEMA ===
{schema}

Return ONLY the structured JSON object. No commentary."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT_JD_ANALYSIS},
        {"role": "user", "content": user_content},
    ]


# Legacy alias for backward compat
def build_resume_prompt(master_resume: str, job_description: str) -> str:
    """Legacy single-string prompt (deprecated -- use build_resume_tailoring_prompt)."""
    messages = build_resume_tailoring_prompt(master_resume, job_description)
    return messages[0]["content"] + "\n\n" + messages[1]["content"]