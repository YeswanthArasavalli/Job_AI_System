"""
Resume formatter -- converts a StructuredResume into clean, readable plain text.

Used for:
  - Terminal output / logging
  - Quick preview before PDF generation
  - Debug inspection
"""

from utils.models import StructuredResume


def format_resume_text(resume: StructuredResume) -> str:
    """
    Convert a StructuredResume to a clean, ATS-friendly plain text format.

    Returns:
        Formatted string ready for display or text file export.
    """
    sections = []

    # --- Header ---
    header_lines = []
    c = resume.contact
    header_lines.append(c.name.upper())
    if resume.title:
        header_lines.append(resume.title)

    contact_parts = []
    if c.email:
        contact_parts.append(c.email)
    if c.phone:
        contact_parts.append(c.phone)
    if c.location:
        contact_parts.append(c.location)
    if contact_parts:
        header_lines.append(" | ".join(contact_parts))

    link_parts = []
    if c.linkedin:
        link_parts.append(c.linkedin)
    if c.portfolio:
        link_parts.append(c.portfolio)
    if link_parts:
        header_lines.append(" | ".join(link_parts))

    sections.append("\n".join(header_lines))

    # --- Summary ---
    if resume.summary:
        sections.append(_section("PROFESSIONAL SUMMARY", resume.summary))

    # --- Skills ---
    if resume.skills:
        skills_text = " • ".join(resume.skills)
        sections.append(_section("TECHNICAL SKILLS", skills_text))

    # --- Experience ---
    if resume.experience:
        exp_lines = []
        for exp in resume.experience:
            title_line = f"{exp.role}"
            company_line = f"{exp.company}"
            if exp.location:
                company_line += f" -- {exp.location}"
            company_line += f" | {exp.duration}"

            exp_lines.append(title_line)
            exp_lines.append(company_line)
            for bullet in exp.bullets:
                exp_lines.append(f"  • {bullet}")
            exp_lines.append("")

        sections.append(_section("PROFESSIONAL EXPERIENCE", "\n".join(exp_lines)))

    # --- Projects ---
    if resume.projects:
        proj_lines = []
        for proj in resume.projects:
            proj_lines.append(f"{proj.name}")
            if proj.description:
                proj_lines.append(f"  {proj.description}")
            if proj.technologies:
                proj_lines.append(f"  Technologies: {', '.join(proj.technologies)}")
            for bullet in proj.bullets:
                proj_lines.append(f"  • {bullet}")
            proj_lines.append("")

        sections.append(_section("PROJECTS", "\n".join(proj_lines)))

    # --- Education ---
    if resume.education:
        edu_lines = []
        for edu in resume.education:
            line = f"{edu.degree} -- {edu.institution}"
            if edu.year:
                line += f" ({edu.year})"
            if edu.gpa:
                line += f" | GPA: {edu.gpa}"
            edu_lines.append(line)
            if edu.details:
                edu_lines.append(f"  {edu.details}")

        sections.append(_section("EDUCATION", "\n".join(edu_lines)))

    # --- Certifications ---
    if resume.certifications:
        cert_lines = []
        for cert in resume.certifications:
            line = cert.name
            if cert.issuer:
                line += f" -- {cert.issuer}"
            if cert.year:
                line += f" ({cert.year})"
            cert_lines.append(f"  • {line}")

        sections.append(_section("CERTIFICATIONS", "\n".join(cert_lines)))

    return "\n\n".join(sections)


def _section(title: str, body: str) -> str:
    """Format a resume section with a title and horizontal rule."""
    separator = "-" * 50
    return f"{separator}\n{title}\n{separator}\n{body}"