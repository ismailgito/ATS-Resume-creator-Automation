"""ATS-Safe PDF Resume Document Builder using pure-Python fpdf2."""

from __future__ import annotations

from pathlib import Path
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from src.models.profile import CandidateProfile
from src.models.resume import TailoredResume


class ATSResumePDF(FPDF):
    """Clean ATS-compatible PDF generator."""

    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(15, 15, 15)

    def header(self):
        pass

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(140, 140, 140)
        self.cell(self.epw, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def sanitize_text(text: str) -> str:
    """Sanitize text to Latin-1 compatible characters for standard core PDF fonts."""
    if not text:
        return ""
    replacements = {
        "—": "-",
        "–": "-",
        "•": "*",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "\u2022": "*",
        "\xa0": " ",
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    return text.encode("latin-1", "replace").decode("latin-1")


def build_pdf_resume(candidate: CandidateProfile, tailored: TailoredResume, output_path: Path) -> Path:
    """Generate ATS-optimized PDF resume."""
    pdf = ATSResumePDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    epw = pdf.epw

    def add_p(text: str, h: float = 4.5, font_style: str = "", font_size: float = 9.5, align: str = "L"):
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", font_style, font_size)
        pdf.multi_cell(w=epw, h=h, text=sanitize_text(text), align=align)

    # 1. Candidate Header
    add_p(candidate.full_name, h=8, font_style="B", font_size=18, align="C")
    add_p(candidate.headline, h=5, font_style="I", font_size=10, align="C")

    contact_line = f"{candidate.contact.email}  |  {candidate.contact.phone}  |  {candidate.contact.location}"
    add_p(contact_line, h=4.5, font_style="", font_size=8.5, align="C")

    links_line = f"LinkedIn: {candidate.contact.linkedin}  |  Portfolio: {candidate.contact.portfolio}"
    add_p(links_line, h=4.5, font_style="", font_size=8.5, align="C")
    pdf.ln(3)

    def draw_section(title: str):
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(16, 44, 87)
        pdf.cell(epw, 6, sanitize_text(title.upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        y = pdf.get_y()
        pdf.set_draw_color(180, 190, 205)
        pdf.set_line_width(0.4)
        pdf.line(pdf.l_margin, y, pdf.l_margin + epw, y)
        pdf.set_text_color(30, 30, 30)
        pdf.ln(2)

    # 2. Professional Summary
    draw_section("Professional Summary")
    add_p(tailored.summary, h=4.5, font_size=9.5)
    pdf.ln(2)

    # 3. Core Competencies & Skills
    draw_section("Core Competencies & Skills")
    skills_str = " * ".join(tailored.skills)
    add_p(skills_str, h=4.5, font_size=9)
    tools_line = f"Platforms & Tools: {', '.join(candidate.tools)}"
    add_p(tools_line, h=4.5, font_size=9)
    pdf.ln(2)

    # 4. Professional Experience
    draw_section("Professional Experience")
    for role in tailored.experience:
        role_header = f"{role.title} - {role.company} ({role.location} | {role.period})"
        add_p(role_header, h=5, font_style="B", font_size=9.5)
        for bullet in role.bullets:
            add_p(f"-  {bullet}", h=4.2, font_size=9)
        pdf.ln(2)

    # 5. Key Achievements & Impact
    draw_section("Key Achievements & Track Record")
    for ach in candidate.achievements:
        add_p(f"-  {ach.metric}: {ach.statement} ({ach.time_period})", h=4.2, font_size=9)
    pdf.ln(2)

    # 6. Education & Certifications
    draw_section("Education & Certifications")
    for edu in candidate.education:
        add_p(f"-  {edu.degree}, {edu.institution} ({edu.start_year} - {edu.end_year})", h=4.2, font_size=9)

    for cert in candidate.certifications:
        add_p(f"-  {cert.name} - {cert.issuer} ({cert.date})", h=4.2, font_size=9)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path
