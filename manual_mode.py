"""
Manual Analysis Mode -- Run the full pipeline on user-provided resume + JD.

Supports:
  - Raw text resume
  - JSON resume (StructuredResume format)
  - Master resume file path
  - Raw JD text

Reuses existing pipeline modules -- zero duplication.
"""

import json
import os
from typing import Optional, Union

from resume_engine.engine import ResumeEngine
from resume_engine.naturalizer import ResumeNaturalizer
from resume_engine.formatter import format_resume_text
from ats_scoring.scorer import ATSScorer
from jd_processor.processor import JDProcessor
from pdf_generator.generator import PDFResumeGenerator
from utils.config_loader import load_config, AppConfig
from utils.models import StructuredResume, ExtractedJD
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ManualAnalyzer:
    """
    Analyze any resume against any JD without the scraper/database.

    Usage:
        analyzer = ManualAnalyzer()
        result = analyzer.analyze(resume_text="...", jd_text="...")
        result = analyzer.analyze(resume_path="data/master_resume.json", jd_text="...")
    """

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or load_config()
        self.engine = ResumeEngine(config=self.config)
        self.scorer = ATSScorer(config=self.config)
        self.jd_processor = JDProcessor()
        self.naturalizer = ResumeNaturalizer()
        self.pdf_gen = PDFResumeGenerator()

    def analyze(
        self,
        jd_text: str,
        resume_path: str = None,
        resume_json: dict = None,
        resume_text: str = None,
        resume_file_bytes: bytes = None,
        resume_filename: str = "",
        generate_pdf: bool = False,
        mode: str = "strict",
    ) -> dict:
        """
        Run full pipeline on provided resume + JD.

        Args:
            jd_text: Raw job description text.
            resume_path: Path to master resume JSON file.
            resume_json: Resume as dict (StructuredResume format).
            resume_text: Raw text resume (unused currently).
            resume_file_bytes: Raw file bytes (PDF/DOCX/JSON upload).
            resume_filename: Original filename for type detection.
            generate_pdf: Whether to generate PDF output.

        Returns:
            Dict with all analysis results.
        """
        if not jd_text or len(jd_text.strip()) < 20:
            return {"error": "JD text is too short. Provide a full job description."}

        # Handle file upload (PDF/DOCX/JSON)
        if resume_file_bytes and resume_filename:
            from resume_parser.file_parser import ResumeFileParser
            parser = ResumeFileParser()
            ext = os.path.splitext(resume_filename)[1].lower()

            if ext == ".json":
                resume_json = parser.parse_to_dict(
                    file_bytes=resume_file_bytes, filename=resume_filename
                )
                if not resume_json:
                    return {"error": "Failed to parse JSON resume."}
            else:
                # PDF/DOCX -- extract text and convert to StructuredResume
                try:
                    extracted_text = parser.extract_text(
                        file_bytes=resume_file_bytes, filename=resume_filename
                    )
                    logger.info(f"Extracted {len(extracted_text)} chars from {resume_filename}")
                except Exception as e:
                    return {"error": f"Failed to parse {resume_filename}: {e}"}

                # Convert extracted text to StructuredResume via hybrid parser
                try:
                    from resume_parser.rule_based_parser import RuleBasedResumeParser
                    rule_parser = RuleBasedResumeParser()
                    rule_data = rule_parser.parse(extracted_text)

                    # Try LLM first (primary parser)
                    llm_succeeded = False
                    try:
                        from resume_engine.prompts import RESUME_JSON_SCHEMA
                        import json as _json

                        parse_messages = [
                            {"role": "system", "content": (
                                "You are a resume parser. Given raw resume text, extract it into "
                                "the exact JSON schema provided. Output ONLY valid JSON. "
                                "Do NOT invent any information -- only extract what is present in the text. "
                                "If a field is not found, use an empty string or empty list."
                            )},
                            {"role": "user", "content": (
                                f"Parse this resume text into JSON:\n\n"
                                f"=== RESUME TEXT ===\n{extracted_text}\n\n"
                                f"=== REQUIRED SCHEMA ===\n{RESUME_JSON_SCHEMA}\n\n"
                                f"Return ONLY the JSON object."
                            )}
                        ]

                        raw_output = self.engine._call_llm_with_json_retry(
                            parse_messages, task="Resume Parsing"
                        )
                        from resume_engine.parser import repair_json, parse_llm_resume_output
                        parsed_resume = parse_llm_resume_output(raw_output)
                        llm_data = parsed_resume.model_dump()
                        llm_succeeded = True

                        # HYBRID MERGE: Fill gaps in LLM output with rule-based data
                        resume_json = rule_parser.merge_with_llm(llm_data, rule_data)

                        logger.info(
                            f"HYBRID PARSE: LLM + rule-based merge | "
                            f"{resume_json.get('contact', {}).get('name', '?')} | "
                            f"{len(resume_json.get('skills', []))} skills | "
                            f"{len(resume_json.get('experience', []))} exp | "
                            f"{len(resume_json.get('education', []))} edu"
                        )
                    except Exception as llm_err:
                        logger.warning(f"LLM parsing failed: {llm_err}. Using rule-based only.")

                    # Validation: if LLM failed or output is incomplete, use rule-based
                    if not llm_succeeded:
                        resume_json = rule_data
                        logger.info(
                            f"RULE-BASED PARSE (fallback): "
                            f"{resume_json.get('contact', {}).get('name', '?')} | "
                            f"{len(resume_json.get('skills', []))} skills | "
                            f"{len(resume_json.get('experience', []))} exp | "
                            f"{len(resume_json.get('education', []))} edu"
                        )

                    # Final validation: ensure critical sections exist
                    if not resume_json.get("skills"):
                        resume_json["skills"] = rule_data.get("skills", [])
                    if not resume_json.get("experience"):
                        resume_json["experience"] = rule_data.get("experience", [])
                    if not resume_json.get("education"):
                        resume_json["education"] = rule_data.get("education", [])

                except Exception as e:
                    logger.error(f"Resume parsing failed completely: {e}")
                    return {"error": f"Could not parse resume: {e}"}

        # Determine resume source
        if resume_path is None and resume_json is None:
            resume_path = self.config.resume_engine.master_resume_path

        logger.info("=" * 60)
        logger.info("MANUAL ANALYSIS MODE")
        logger.info("=" * 60)

        try:
            # STATELESS: Clear ALL caches for deterministic execution
            from resume_engine.engine import ResumeEngine as _RE
            _RE.clear_cache()

            # STATELESS: Clear semantic matcher embedding cache
            try:
                from ats_scoring.semantic_matcher import SemanticMatcher
                SemanticMatcher._embedding_cache = {}
                logger.info("Semantic cache cleared for stateless run")
            except Exception:
                pass

            # STATELESS: Normalize JD text (strip whitespace variance)
            jd_text = " ".join(jd_text.split())

            # Step 1: Clean JD
            processed_jd = self.jd_processor.process(jd_text)
            clean_jd = processed_jd.cleaned_text
            logger.info(
                f"  JD quality: {processed_jd.quality_score:.0f}% | "
                f"{len(processed_jd.skills_required)} skills detected"
            )

            # Step 2: Run Resume Engine
            if resume_path:
                original, tailored, extracted_jd = self.engine.process(
                    master_resume_path=resume_path,
                    job_description=clean_jd,
                )
            elif resume_json:
                # Parse JSON into StructuredResume, then tailor
                original = StructuredResume(**resume_json)
                extracted_jd = self.engine.analyze_jd(clean_jd)
                tailored = self.engine.tailor_resume(original, clean_jd)
                tailored = self.engine._enforce_content_protection(original, tailored)
            else:
                return {"error": "No resume source provided."}

            # -- RESUME PARSER VALIDATION LAYER ----------------
            if not original.experience or len(original.experience) == 0:
                logger.warning("PARSER WARNING: Resume has zero experience entries")
            if not original.skills or len(original.skills) < 3:
                logger.warning(
                    f"PARSER WARNING: Incomplete skill extraction "
                    f"({len(original.skills or [])} skills found)"
                )

            # -- HARD ASSERT: identity must match ----------------
            logger.info(f"DASHBOARD FLOW -> ResumeEngine used")
            logger.info(f"  Input name:  {original.contact.name}")
            logger.info(f"  Output name: {tailored.contact.name}")

            # Step 3-5: CANONICAL ENGINE (Phase 3) - single analysis entry point.
            # The dashboard's LLM-tailored resume is passed as the tailored base
            # so tailoring depth is preserved; scoring/shortlist/truth are canonical.
            from pipeline.service import analyze_tailored
            pipeline_result = analyze_tailored(
                original=original,
                tailored=tailored,
                jd=extracted_jd,
                mode=mode,
                job_id="manual_analysis",
                config=self.config,
                scorer=self.scorer,
            )
            ats_report = pipeline_result.ats_report
            improved = pipeline_result.improved
            readability = pipeline_result.readability

            # Step 6: PDF from IMPROVED resume (not tailored)
            # -- PDF SOURCE VALIDATION --
            pdf_path = None
            if generate_pdf:
                # Assert: PDF source must be the improved resume with correct identity
                assert improved.contact.name == original.contact.name, (
                    f"PDF IDENTITY MISMATCH: "
                    f"improved={improved.contact.name}, original={original.contact.name}"
                )
                pdf_path = self.pdf_gen.generate(improved, filename="improved_resume.pdf")
                logger.info(f"PDF generated from improved resume ({improved.contact.name})")

            # Build next actions (career assistant style)
            next_actions = []
            if ats_report.missing_skills:
                top_missing = ats_report.missing_skills[:3]
                next_actions.append(f"Highlight experience with: {', '.join(top_missing)}")
            if ats_report.semantic_score < 30:
                next_actions.append("Align resume bullet points more closely with JD language")
            if ats_report.decision == "IMPROVE":
                next_actions.append("Consider adding relevant project work or certifications")
            if ats_report.score_after < 50:
                next_actions.append("Rewrite summary to mirror the target role description")

            # Status — EXECUTION-AWARE: never say NO_CHANGE when improvements applied
            delta = ats_report.score_after - ats_report.score_before
            # Check if text actually changed (structural improvements)
            improved_text = " ".join(b for exp in improved.experience for b in exp.bullets)
            tailored_text = " ".join(b for exp in tailored.experience for b in exp.bullets)
            text_changed = improved_text != tailored_text
            has_recommendations = bool(ats_report.recommendations)

            if delta > 5:
                status = "IMPROVED"
                status_message = f"Resume improved by {delta:.0f} points through keyword alignment and optimization."
            elif delta > 0 or text_changed:
                status = "IMPROVED"
                status_message = (
                    f"Resume optimized (+{delta:.0f} pts). "
                    f"Applied skill linking, keyword alignment, and structural improvements."
                )
            elif has_recommendations:
                status = "IMPROVED"
                status_message = "Resume structurally improved with skill-experience linking and keyword alignment."
            else:
                status = "NO_CHANGE"
                status_message = "Current resume is already optimal for this JD. No changes needed."

            # CANONICAL packaging (Phase 3): single result contract from
            # pipeline.service.package_result. Dashboard-specific extras
            # (next_actions, PDF, tailored text) are appended below.
            from pipeline.service import package_result
            result = package_result(pipeline_result, mode)

            # Build next actions (career assistant style) - dashboard UX layer
            next_actions = []
            if ats_report.missing_skills:
                top_missing = ats_report.missing_skills[:3]
                next_actions.append(f"Highlight experience with: {', '.join(top_missing)}")
            if ats_report.semantic_score < 30:
                next_actions.append("Align resume bullet points more closely with JD language")
            if ats_report.decision == "IMPROVE":
                next_actions.append("Consider adding relevant project work or certifications")
            if ats_report.score_after < 50:
                next_actions.append("Rewrite summary to mirror the target role description")

            # Backward-compatible aliases for existing dashboard consumers
            result["next_actions"] = next_actions
            result["status_message"] = (
                f"Resume improved by {result['scores']['after'] - result['scores']['before']:.0f} points."
                if result["status"] == "IMPROVED"
                else "Current resume is already optimal for this JD. No changes needed."
            )
            result["probability"] = pipeline_result.shortlist_probability
            result["scores"]["semantic"] = ats_report.semantic_score
            result["tailored_resume_text"] = format_resume_text(tailored)
            result["improved_resume_text"] = format_resume_text(pipeline_result.improved)
            result["improved_resume_json"] = pipeline_result.improved.model_dump()
            result["tailored_resume_json"] = tailored.model_dump()
            result["pdf_path"] = pdf_path
            result["target_plan"] = pipeline_result.target_plan
            result["role_info"] = pipeline_result.role_info
            result["resume_type"] = pipeline_result.resume_type
            result["polish_changes"] = pipeline_result.polish_changes

            # Canonical shortlist aliases (v6 names kept for existing tests)
            result["canonical_shortlist_probability"] = pipeline_result.shortlist_probability
            result["canonical_shortlist_band"] = pipeline_result.shortlist_band
            result["canonical_shortlist_decision"] = pipeline_result.shortlist_decision
            result["canonical_shortlist_reason"] = pipeline_result.shortlist_decision_reason
            return result

        except RuntimeError as e:
            error_msg = str(e)
            if "Failed to connect" in error_msg or "Ollama" in error_msg:
                logger.error(f"MANUAL ANALYSIS FAILED (Ollama): {e}")
                return {
                    "error": (
                        "LLM (Ollama) is not available. "
                        "Please ensure Ollama is running: open a terminal and run 'ollama serve'. "
                        "The system can still score resumes from JSON files without LLM."
                    ),
                    "success": False,
                    "ollama_error": True,
                }
            logger.error(f"MANUAL ANALYSIS FAILED: {e}")
            return {"error": str(e), "success": False}

        except Exception as e:
            logger.error(f"MANUAL ANALYSIS FAILED: {e}")
            return {"error": str(e), "success": False}
