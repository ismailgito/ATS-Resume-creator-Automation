"""German tabular Lebenslauf as PDF (pure-Python fpdf2, standard Helvetica font)."""

from __future__ import annotations

from pathlib import Path
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from src.models.profile import CandidateProfile
from src.models.resume import TailoredResume
from src.resume.layout import Entry, build_layout
from src.resume.sections import get_sub_labels

MARGIN_X = 18
LEFT_W = 36          # date / label column
GAP = 3
BULLET_W = 4
PHOTO_W = 30


class ATSResumePDF(FPDF):
    """Clean, text-based PDF (no images except an optional photo, no text boxes)."""

    def __init__(self, page_label: str = "Seite"):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(MARGIN_X, 16, MARGIN_X)
        self.page_label = page_label

    def header(self):
        pass

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(140, 140, 140)
        self.cell(self.epw, 10, f"{self.page_label} {self.page_no()}/{{nb}}", align="C")


def sanitize_text(text: str) -> str:
    """Make text safe for the Latin-1 core fonts (German umlauts and ß are fine as they are)."""
    if not text:
        return ""
    replacements = {
        "₹": "INR ",
        "—": "-",
        "–": "-",
        "•": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "\xa0": " ",
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    return text.encode("latin-1", "replace").decode("latin-1")


def build_pdf_resume(candidate: CandidateProfile, tailored: TailoredResume, output_path: Path) -> Path:
    """Generate the German tabular Lebenslauf as PDF."""
    layout = build_layout(candidate, tailored)
    pdf = ATSResumePDF(page_label=get_sub_labels()["page"])
    pdf.alias_nb_pages()
    pdf.add_page()

    right_x = MARGIN_X + LEFT_W + GAP
    right_w = pdf.w - MARGIN_X - right_x

    def write(x: float, w: float, text: str, h: float = 4.5, style: str = "", size: float = 9.5,
              color=(30, 30, 30), align: str = "L"):
        pdf.set_x(x)
        pdf.set_font("Helvetica", style, size)
        pdf.set_text_color(*color)
        pdf.multi_cell(w, h, sanitize_text(text), align=align, new_x=XPos.LEFT, new_y=YPos.NEXT)

    # ── Header ──
    top_y = pdf.get_y()
    header_w = pdf.epw
    photo_bottom = top_y
    if layout.photo:
        info = pdf.image(str(layout.photo), x=pdf.w - MARGIN_X - PHOTO_W, y=top_y, w=PHOTO_W)
        photo_bottom = top_y + PHOTO_W * info.height / info.width
        header_w = pdf.epw - PHOTO_W - 4

    if layout.title:
        write(MARGIN_X, header_w, layout.title.upper(), h=5, style="B", size=9, color=(110, 110, 110))
    write(MARGIN_X, header_w, layout.name, h=9, style="B", size=20, color=(26, 36, 43))
    if layout.headline:
        write(MARGIN_X, header_w, layout.headline, h=5, style="I", size=10, color=(70, 80, 95))
    pdf.set_y(max(pdf.get_y(), photo_bottom) + 2)

    def draw_heading(title: str):
        if pdf.get_y() > pdf.page_break_trigger - 24:
            pdf.add_page()
        pdf.ln(3)
        pdf.set_x(MARGIN_X)
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(16, 44, 87)
        pdf.cell(pdf.epw, 6, sanitize_text(title.upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        y = pdf.get_y()
        pdf.set_draw_color(180, 190, 205)
        pdf.set_line_width(0.3)
        pdf.line(MARGIN_X, y, MARGIN_X + pdf.epw, y)
        pdf.ln(2.5)

    def draw_entry(entry: Entry):
        if not entry.left:
            write(MARGIN_X, pdf.epw, entry.text)
            pdf.ln(1)
            return

        if pdf.get_y() > pdf.page_break_trigger - 18:
            pdf.add_page()
        start_y = pdf.get_y()
        start_page = pdf.page_no()
        is_label_row = not entry.heading

        # Left column: dates, or the row label
        pdf.set_xy(MARGIN_X, start_y)
        write(MARGIN_X, LEFT_W, entry.left, style="B" if is_label_row else "", size=9.5)
        left_end = pdf.get_y()

        # Right column
        pdf.set_xy(right_x, start_y)
        if entry.heading:
            write(right_x, right_w, entry.heading, style="B", size=10)
        else:
            write(right_x, right_w, entry.text)
        if entry.detail:
            write(right_x, right_w, entry.detail, style="I", size=9, color=(90, 90, 90))
        if entry.heading and entry.text:
            write(right_x, right_w, entry.text, size=9.5)
        for bullet in entry.bullets:
            bullet_y = pdf.get_y()
            pdf.set_xy(right_x, bullet_y)
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(BULLET_W, 4.4, "-", new_x=XPos.RIGHT, new_y=YPos.TOP)
            write(right_x + BULLET_W, right_w - BULLET_W, bullet, h=4.4, size=9.5)

        end_y = pdf.get_y()
        pdf.set_y(max(left_end, end_y) if pdf.page_no() == start_page else end_y)
        pdf.ln(2.2 if entry.heading else 0.8)

    for section in layout.sections:
        draw_heading(section.title)
        for entry in section.entries:
            draw_entry(entry)

    # ── Ort, Datum, Name ──
    if pdf.get_y() > pdf.page_break_trigger - 30:
        pdf.add_page()
    pdf.ln(10)
    write(MARGIN_X, pdf.epw, f"{layout.place}, {layout.date}")
    pdf.ln(8)
    write(MARGIN_X, pdf.epw, layout.name, style="B")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path
