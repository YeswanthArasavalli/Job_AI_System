"""
Job AI System -- Phase 1 + Phase 2 + Phase 3 Entry Point

Full pipeline:
  1. Load master resume
  2. Analyze job description (LLM)
  3. Score ORIGINAL resume (ATS)
  4. Tailor resume to JD (LLM)
  5. Score TAILORED resume (ATS)
  6. Generate professional PDF
  7. Save all outputs

Usage:
    python main.py
"""

import json
import os
import re
import sys

from resume_engine.engine import ResumeEngine
from resume_engine.formatter import format_resume_text
from resume_engine.parser import resume_to_json_string
from ats_scoring.scorer import ATSScorer
from ats_scoring.report_formatter import format_ats_report
from pdf_generator.generator import PDFResumeGenerator
from utils.config_loader import load_config
from utils.logger import setup_logger

logger = setup_logger("main")


# ============================================================
# Sample JD for testing
# ============================================================

SAMPLE_JD = """
Senior Data Analyst -- FinEdge Analytics (Bangalore, India)

About the Role:
We are seeking a Senior Data Analyst to join our growing analytics team. You will
work closely with stakeholders to derive actionable insights from complex datasets
and drive data-informed decision-making across the organization.

Requirements:
- 3+ years of experience in data analysis or a similar role
- Strong proficiency in SQL and Python (Pandas, NumPy)
- Experience with data visualization tools (Power BI, Tableau, or similar)
- Knowledge of statistical analysis and A/B testing
- Experience with ETL processes and data pipeline tools
- Familiarity with cloud platforms (AWS, GCP, or Azure)
- Strong communication skills and ability to present findings to non-technical audiences
- Bachelor's degree in Computer Science, Statistics, Mathematics, or related field

Nice to Have:
- Experience with machine learning / predictive modeling
- Knowledge of Apache Spark or Airflow
- Experience with dbt or similar data transformation tools
- MBA or Master's degree in a quantitative field

Responsibilities:
- Analyze large datasets to identify trends, patterns, and business opportunities
- Build and maintain dashboards and reports for executive leadership
- Design and execute A/B tests to measure product impact
- Collaborate with engineering teams to improve data infrastructure
- Develop and maintain ETL pipelines for data ingestion and transformation
- Present findings and recommendations to stakeholders across departments
""".strip()


def main():
    """Run the full Phase 1 + 2 + 3 pipeline."""

    print("\n" + "=" * 60)
    print("🧠  JOB AI SYSTEM -- Full Pipeline")
    print("    Phase 1: Resume Engine")
    print("    Phase 2: ATS Scoring")
    print("    Phase 3: PDF Generator")
    print("=" * 60 + "\n")

    # Load config
    config = load_config()
    logger.info("Configuration loaded")

    # Determine master resume path
    resume_path = config.resume_engine.master_resume_path
    if not os.path.exists(resume_path):
        logger.error(f"Master resume not found at: {resume_path}")
        print(f"\n[ERROR] Master resume not found at: {resume_path}")
        print("   Please create your master resume at that path (JSON format).")
        sys.exit(1)

    # Load JD
    jd_file = "data/job_description.txt"
    if os.path.exists(jd_file):
        with open(jd_file, "r", encoding="utf-8") as f:
            job_description = f.read().strip()
        logger.info(f"Job description loaded from: {jd_file}")
    else:
        job_description = SAMPLE_JD
        logger.info("Using sample job description")

    # -- Phase 1: Resume Engine -----------------------------

    engine = ResumeEngine(config=config)

    try:
        original, tailored, extracted_jd = engine.process(
            master_resume_path=resume_path,
            job_description=job_description,
        )
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        print(f"\n[ERROR] Resume Engine failed: {e}")
        print("\n[INFO] Troubleshooting:")
        print("   1. Is Ollama running? -> ollama serve")
        print(f"   2. Is the model pulled? -> ollama pull {config.llm.model}")
        print("   3. Check logs/system.log for details.\n")
        sys.exit(1)

    # Display JD analysis
    print("\n" + "=" * 60)
    print("  JOB DESCRIPTION ANALYSIS")
    print("=" * 60)
    print(f"\n  Job Title:  {extracted_jd.job_title}")
    print(f"  Company:    {extracted_jd.company}")
    print(f"  Location:   {extracted_jd.location}")
    print(f"\n  Required Skills ({len(extracted_jd.required_skills)}):")
    for skill in extracted_jd.required_skills:
        print(f"    * {skill}")
    print(f"\n  Preferred Skills ({len(extracted_jd.preferred_skills)}):")
    for skill in extracted_jd.preferred_skills:
        print(f"    ◦ {skill}")
    print(f"\n  Keywords ({len(extracted_jd.keywords)}):")
    print(f"    {', '.join(extracted_jd.keywords)}")
    if extracted_jd.required_experience_years:
        print(f"\n  Experience Required: {extracted_jd.required_experience_years}+ years")

    # Display tailored resume
    print("\n\n" + "=" * 60)
    print("  TAILORED RESUME")
    print("=" * 60 + "\n")
    print(format_resume_text(tailored))

    # -- Phase 2+3: Unified Pipeline (Naturalize -> Score -> Improve -> Guardrail) --

    from pipeline.core import run_full_pipeline
    scorer = ATSScorer(config=config)

    pipeline_result = run_full_pipeline(
        original=original,
        tailored=tailored,
        extracted_jd=extracted_jd,
        scorer=scorer,
        job_id="sample_001",
    )
    ats_report = pipeline_result.ats_report
    improved = pipeline_result.improved

    print("\n" + format_ats_report(ats_report))

    if improved is tailored:
        print("\n  [INFO] Improvement reverted or skipped")
    else:
        print(f"\n  [OK] Resume improved (score validated)")

    # -- Phase 4: PDF Generation ----------------------------

    print("\n" + "=" * 60)
    print("  PDF GENERATION")
    print("=" * 60)

    pdf_gen = PDFResumeGenerator()

    # Build filename: resume_{company}_{role}.pdf
    company_safe = re.sub(r'[^\w\s-]', '', extracted_jd.company or "unknown").strip()
    company_safe = re.sub(r'\s+', '_', company_safe)
    role_safe = re.sub(r'[^\w\s-]', '', extracted_jd.job_title or "unknown").strip()
    role_safe = re.sub(r'\s+', '_', role_safe)
    pdf_filename = f"resume_{company_safe}_{role_safe}.pdf"

    try:
        pdf_path = pdf_gen.generate(improved, filename=pdf_filename)
        print(f"\n  [OK] PDF generated: {pdf_path}")
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        print(f"\n  [FAIL] PDF generation failed: {e}")
        pdf_path = ""

    # -- Save all outputs -----------------------------------

    output_dir = config.resume_engine.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # Save tailored resume JSON
    json_path = os.path.join(output_dir, "tailored_resume.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(resume_to_json_string(tailored))

    # Save tailored resume text
    txt_path = os.path.join(output_dir, "tailored_resume.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(format_resume_text(tailored))

    # Save extracted JD
    jd_path = os.path.join(output_dir, "extracted_jd.json")
    with open(jd_path, "w", encoding="utf-8") as f:
        f.write(extracted_jd.model_dump_json(indent=2))

    # Save ATS report JSON
    ats_path = os.path.join(output_dir, "ats_report.json")
    with open(ats_path, "w", encoding="utf-8") as f:
        f.write(ats_report.model_dump_json(indent=2))

    # Save ATS report text
    ats_txt_path = os.path.join(output_dir, "ats_report.txt")
    with open(ats_txt_path, "w", encoding="utf-8") as f:
        f.write(format_ats_report(ats_report))

    logger.info(f"All outputs saved to: {output_dir}/")

    print(f"\n[OK] All output saved to:")
    print(f"   {output_dir}/")
    print(f"      - tailored_resume.json")
    print(f"      - tailored_resume.txt")
    print(f"      - extracted_jd.json")
    print(f"      - ats_report.json")
    print(f"      - ats_report.txt")
    if pdf_path:
        print(f"   output/pdfs/")
        print(f"      - {pdf_filename}")

    print("\n" + "=" * 60)
    print("[OK] Phase 1 + 2 + 3 Complete!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()