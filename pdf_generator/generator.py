"""
Professional ATS-friendly PDF Resume Generator.

Design principles:
  - Clean, single-column layout (ATS parsers struggle with multi-column)
  - Standard fonts only (Helvetica/Arial -- universally parsed by ATS)
  - No images, no graphics, no tables (ATS can't read them)
  - Clear section headers with consistent formatting
  - Proper spacing and margins for readability
  - Unicode-safe text handling
"""

import os
import re
from typing import Optional

from fpdf import FPDF

from utils.logger import setup_logger
from utils.models import StructuredResume

logger = setup_logger(__name__)


class PDFResumeGenerator:
    """
    Generates a professional, ATS-optimized PDF from a StructuredResume.

    Usage:
        gen = PDFResumeGenerator()
        path = gen.generate(resume, output_path="output/resume.pdf")
    """

    # --- Color Palette (Professional Dark) ---
    COLOR_PRIMARY = (33, 37, 41)       # Dark charcoal -- headings, name
    COLOR_SECONDARY = (73, 80, 87)     # Medium gray -- subheadings
    COLOR_BODY = (52, 58, 64)          # Body text
    COLOR_ACCENT = (0, 86, 179)        # Blue -- links, subtle accents
    COLOR_LIGHT = (134, 142, 150)      # Light gray -- dates, metadata
    COLOR_RULE = (206, 212, 218)       # Lightest gray -- horizontal rules

    # --- Layout ---
    PAGE_WIDTH = 210  # A4 mm
    MARGIN_LEFT = 18
    MARGIN_RIGHT = 18
    MARGIN_TOP = 15
    CONTENT_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT

    def __init__(self, output_dir: str = "output/pdfs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate(
        self,
        resume: StructuredResume,
        output_path: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate a PDF resume.

        Args:
            resume: StructuredResume to render.
            output_path: Full path for the PDF. If None, auto-generates.
            filename: Just the filename (placed in output_dir). Ignored if output_path set.

        Returns:
            Absolute path to the generated PDF file.
        """
        if not output_path:
            if not filename:
                safe_name = re.sub(r'[^\w\s-]', '', resume.contact.name).strip()
                safe_name = re.sub(r'[\s]+', '_', safe_name)
                filename = f"{safe_name}_Resume.pdf"
            output_path = os.path.join(self.output_dir, filename)

        logger.info(f"Generating PDF: {output_path}")

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_margins(self.MARGIN_LEFT, self.MARGIN_TOP, self.MARGIN_RIGHT)
        pdf.add_page()

        # --- Render Sections (smart ordering) ---
        self._render_header(pdf, resume)
        self._render_summary(pdf, resume)
        self._render_skills(pdf, resume)

        # Smart section ordering: experience before projects (always)
        # but education position depends on experience length
        self._render_experience(pdf, resume)
        self._render_projects(pdf, resume)
        self._render_education(pdf, resume)
        self._render_certifications(pdf, resume)

        # --- Save ---
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        pdf.output(output_path)

        file_size = os.path.getsize(output_path)
        logger.info(f"PDF generated: {output_path} ({file_size:,} bytes)")

        return os.path.abspath(output_path)

    # ================================================================
    # Section Renderers
    # ================================================================

    def _render_header(self, pdf: FPDF, resume: StructuredResume):
        """Render the header block: name, title, contact info."""
        c = resume.contact

        # Name
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(*self.COLOR_PRIMARY)
        pdf.cell(self.CONTENT_WIDTH, 10, self._safe(c.name), align="C", new_x="LMARGIN", new_y="NEXT")

        # Title
        if resume.title:
            pdf.set_font("Helvetica", "", 12)
            pdf.set_text_color(*self.COLOR_SECONDARY)
            pdf.cell(self.CONTENT_WIDTH, 6, self._safe(resume.title), align="C", new_x="LMARGIN", new_y="NEXT")

        # Contact line
        contact_parts = []
        if c.email:
            contact_parts.append(c.email)
        if c.phone:
            contact_parts.append(c.phone)
        if c.location:
            contact_parts.append(c.location)
        if contact_parts:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*self.COLOR_LIGHT)
            pdf.cell(
                self.CONTENT_WIDTH, 5,
                self._safe(" | ".join(contact_parts)),
                align="C", new_x="LMARGIN", new_y="NEXT"
            )

        # Links line
        link_parts = []
        if c.linkedin:
            link_parts.append(c.linkedin)
        if c.portfolio:
            link_parts.append(c.portfolio)
        if link_parts:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*self.COLOR_ACCENT)
            pdf.cell(
                self.CONTENT_WIDTH, 5,
                self._safe(" | ".join(link_parts)),
                align="C", new_x="LMARGIN", new_y="NEXT"
            )

        pdf.ln(2)
        self._draw_rule(pdf)

    def _render_summary(self, pdf: FPDF, resume: StructuredResume):
        """Render the professional summary section."""
        if not resume.summary:
            return

        self._section_header(pdf, "PROFESSIONAL SUMMARY")

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*self.COLOR_BODY)
        pdf.multi_cell(self.CONTENT_WIDTH, 5, self._safe(resume.summary))
        pdf.ln(2)

    def _render_skills(self, pdf: FPDF, resume: StructuredResume):
        """Render skills as a clean, wrapped inline list with separators."""
        if not resume.skills:
            return

        self._section_header(pdf, "TECHNICAL SKILLS")

        # Group skills into rows of ~5 for readability
        skills = resume.skills
        row_size = 5
        rows = [skills[i:i + row_size] for i in range(0, len(skills), row_size)]

        for row in rows:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*self.COLOR_BODY)
            row_text = "  |  ".join(row)
            pdf.multi_cell(self.CONTENT_WIDTH, 5, self._safe(row_text))
            pdf.ln(0.5)

        pdf.ln(1)

    def _render_experience(self, pdf: FPDF, resume: StructuredResume):
        """Render the professional experience section."""
        if not resume.experience:
            return

        self._section_header(pdf, "PROFESSIONAL EXPERIENCE")

        for i, exp in enumerate(resume.experience):
            # Check if we need a new page (enough space for at least header + 2 bullets)
            if pdf.get_y() > 260:
                pdf.add_page()

            # Role title (bold)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*self.COLOR_PRIMARY)
            pdf.cell(self.CONTENT_WIDTH * 0.65, 6, self._safe(exp.role), new_x="RIGHT")

            # Duration (right-aligned, lighter)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*self.COLOR_LIGHT)
            pdf.cell(self.CONTENT_WIDTH * 0.35, 6, self._safe(exp.duration), align="R", new_x="LMARGIN", new_y="NEXT")

            # Company + location
            company_line = exp.company
            if exp.location:
                company_line += f" - {exp.location}"
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(*self.COLOR_SECONDARY)
            pdf.cell(self.CONTENT_WIDTH, 5, self._safe(company_line), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

            # Bullets
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*self.COLOR_BODY)
            for bullet in exp.bullets:
                self._render_bullet(pdf, bullet)

            if i < len(resume.experience) - 1:
                pdf.ln(4)  # More breathing room between entries

        pdf.ln(2)

    def _render_projects(self, pdf: FPDF, resume: StructuredResume):
        """Render the projects section."""
        if not resume.projects:
            return

        self._section_header(pdf, "PROJECTS")

        for i, proj in enumerate(resume.projects):
            if pdf.get_y() > 260:
                pdf.add_page()

            # Project name
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*self.COLOR_PRIMARY)
            pdf.cell(self.CONTENT_WIDTH, 6, self._safe(proj.name), new_x="LMARGIN", new_y="NEXT")

            # Description
            if proj.description:
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(*self.COLOR_SECONDARY)
                pdf.multi_cell(self.CONTENT_WIDTH, 4.5, self._safe(proj.description))

            # Technologies
            if proj.technologies:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*self.COLOR_ACCENT)
                tech_str = "Technologies: " + ", ".join(proj.technologies)
                pdf.cell(self.CONTENT_WIDTH, 5, self._safe(tech_str), new_x="LMARGIN", new_y="NEXT")

            # Bullets
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*self.COLOR_BODY)
            for bullet in proj.bullets:
                self._render_bullet(pdf, bullet)

            if i < len(resume.projects) - 1:
                pdf.ln(2)

        pdf.ln(2)

    def _render_education(self, pdf: FPDF, resume: StructuredResume):
        """Render the education section."""
        if not resume.education:
            return

        self._section_header(pdf, "EDUCATION")

        for edu in resume.education:
            if pdf.get_y() > 265:
                pdf.add_page()

            # Degree
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*self.COLOR_PRIMARY)
            pdf.cell(self.CONTENT_WIDTH * 0.7, 6, self._safe(edu.degree), new_x="RIGHT")

            # Year
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*self.COLOR_LIGHT)
            pdf.cell(self.CONTENT_WIDTH * 0.3, 6, self._safe(edu.year), align="R", new_x="LMARGIN", new_y="NEXT")

            # Institution
            institution_line = edu.institution
            if edu.gpa:
                institution_line += f" | GPA: {edu.gpa}"
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(*self.COLOR_SECONDARY)
            pdf.cell(self.CONTENT_WIDTH, 5, self._safe(institution_line), new_x="LMARGIN", new_y="NEXT")

            # Details
            if edu.details:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(*self.COLOR_BODY)
                pdf.multi_cell(self.CONTENT_WIDTH, 4.5, self._safe(edu.details))

            pdf.ln(2)

    def _render_certifications(self, pdf: FPDF, resume: StructuredResume):
        """Render the certifications section."""
        if not resume.certifications:
            return

        self._section_header(pdf, "CERTIFICATIONS")

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*self.COLOR_BODY)

        for cert in resume.certifications:
            line = cert.name
            if cert.issuer:
                line += f" - {cert.issuer}"
            if cert.year:
                line += f" ({cert.year})"
            self._render_bullet(pdf, line)

        pdf.ln(2)

    # ================================================================
    # Layout Helpers
    # ================================================================

    def _section_header(self, pdf: FPDF, title: str):
        """Render a section header with a horizontal rule."""
        # Check if enough space for header + some content
        if pdf.get_y() > 265:
            pdf.add_page()

        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*self.COLOR_PRIMARY)
        pdf.cell(self.CONTENT_WIDTH, 7, self._safe(title.upper()), new_x="LMARGIN", new_y="NEXT")

        self._draw_rule(pdf, thickness=0.3)
        pdf.ln(1.5)

    def _draw_rule(self, pdf: FPDF, thickness: float = 0.5):
        """Draw a horizontal rule across the content width."""
        y = pdf.get_y()
        pdf.set_draw_color(*self.COLOR_RULE)
        pdf.set_line_width(thickness)
        pdf.line(self.MARGIN_LEFT, y, self.PAGE_WIDTH - self.MARGIN_RIGHT, y)
        pdf.ln(2)

    def _render_bullet(self, pdf: FPDF, text: str, indent: float = 5):
        """Render a bullet point with proper indentation and wrapping."""
        x = pdf.get_x()
        pdf.set_x(x + indent)

        # Bullet character (Latin-1 safe)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(4, 5, "-")

        # Text (wrapped)
        available_width = self.CONTENT_WIDTH - indent - 4
        pdf.multi_cell(available_width, 5, self._safe(text))

    @staticmethod
    def _safe(text: str) -> str:
        """
        Make text safe for FPDF (which uses Latin-1 by default).
        Replace problematic Unicode characters with safe equivalents.
        """
        if not text:
            return ""

        replacements = {
            '\u2013': '-',    # en dash
            '\u2014': '-',    # em dash
            '\u2018': "'",    # left single quote
            '\u2019': "'",    # right single quote
            '\u201c': '"',    # left double quote
            '\u201d': '"',    # right double quote
            '\u2022': '-',    # bullet (in text context)
            '\u2026': '...',  # ellipsis
            '\u00a0': ' ',    # non-breaking space
            '\u2010': '-',    # hyphen
            '\u2011': '-',    # non-breaking hyphen
            '\u2012': '-',    # figure dash
            '\u00b7': '-',    # middle dot
        }

        for char, replacement in replacements.items():
            text = text.replace(char, replacement)

        # Final safety: encode to latin-1, replacing unknown chars
        try:
            text.encode('latin-1')
        except UnicodeEncodeError:
            text = text.encode('latin-1', errors='replace').decode('latin-1')

        return text
