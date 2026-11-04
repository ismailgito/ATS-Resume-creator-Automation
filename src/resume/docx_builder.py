"""German tabular Lebenslauf as DOCX.

The two-column look (dates left, content right) is built with a hanging indent and a tab
stop instead of a Word table, so ATS parsers read it as plain paragraphs in the right order.
"""

from __future__ import annotations

from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from src.models.profile import CandidateProfile
from src.models.resume import TailoredResume
from src.resume.layout import Entry, build_layout

FONT = "Calibri"
LEFT_COL = Cm(4.0)
BULLET_INDENT = Cm(0.4)
ACCENT = RGBColor(16, 44, 87)
MUTED = RGBColor(90, 90, 90)


def build_docx_resume(candidate: CandidateProfile, tailored: TailoredResume, output_path: Path) -> Path:
    """Generate the German tabular Lebenslauf as a Word document (.docx)."""
    layout = build_layout(candidate, tailored)
    doc = Document()

    for section in doc.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(1.8)
        section.bottom_margin = Cm(1.6)
        section.left_margin = Cm(2.0)
        section.right_margin = Cm(2.0)

    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(0)

    def add_run(paragraph, text, bold=False, italic=False, size=10.0, color=None):
        run = paragraph.add_run(text)
        run.font.name = FONT
        run.font.size = Pt(size)
        run.bold = bold
        run.italic = italic
        if color is not None:
            run.font.color.rgb = color
        return run

    def add_bottom_border(paragraph):
        borders = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        for key, value in (("val", "single"), ("sz", "6"), ("space", "1"), ("color", "B4BECD")):
            bottom.set(qn(f"w:{key}"), value)
        borders.append(bottom)
        paragraph._p.get_or_add_pPr().append(borders)

    def add_heading(title: str):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        add_run(p, title.upper(), bold=True, size=11, color=ACCENT)
        add_bottom_border(p)

    def hanging(paragraph, indent, hang=None, tab=None):
        fmt = paragraph.paragraph_format
        fmt.left_indent = indent
        if hang is not None:
            fmt.first_line_indent = -hang
            fmt.tab_stops.add_tab_stop(tab if tab is not None else indent)

    def add_entry(entry: Entry):
        # Full-width paragraph (Kurzprofil)
        if not entry.left:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            add_run(p, entry.text)
            return

        is_label_row = not entry.heading
        first = doc.add_paragraph()
        first.paragraph_format.space_before = Pt(0 if is_label_row else 5)
        first.paragraph_format.space_after = Pt(1)
        first.paragraph_format.keep_with_next = bool(entry.detail or entry.bullets or (entry.heading and entry.text))
        hanging(first, LEFT_COL, hang=LEFT_COL)
        add_run(first, entry.left, bold=is_label_row)
        add_run(first, "\t")
        if entry.heading:
            add_run(first, entry.heading, bold=True)
        else:
            add_run(first, entry.text)

        def indented(text: str, italic=False, color=None):
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.left_indent = LEFT_COL
            add_run(p, text, italic=italic, color=color)

        if entry.detail:
            indented(entry.detail, italic=True, color=MUTED)
        if entry.heading and entry.text:
            indented(entry.text)
        for bullet in entry.bullets:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(1.5)
            hanging(p, LEFT_COL + BULLET_INDENT, hang=BULLET_INDENT)
            add_run(p, "•\t" + bullet)

    # ── Header ──
    if layout.title:
        title_p = doc.add_paragraph()
        add_run(title_p, layout.title.upper(), bold=True, size=10, color=MUTED)

    if layout.photo:
        photo_p = doc.add_paragraph()
        photo_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        photo_p.add_run().add_picture(str(layout.photo), width=Cm(3.2))

    name_p = doc.add_paragraph()
    name_p.paragraph_format.space_after = Pt(1)
    add_run(name_p, layout.name, bold=True, size=20, color=RGBColor(26, 36, 43))
    if layout.headline:
        head_p = doc.add_paragraph()
        add_run(head_p, layout.headline, italic=True, size=10.5, color=MUTED)

    # ── Sections ──
    for section in layout.sections:
        add_heading(section.title)
        for entry in section.entries:
            add_entry(entry)

    # ── Ort, Datum, Name ──
    place_p = doc.add_paragraph()
    place_p.paragraph_format.space_before = Pt(18)
    place_p.paragraph_format.keep_with_next = True
    add_run(place_p, f"{layout.place}, {layout.date}")
    sign_p = doc.add_paragraph()
    sign_p.paragraph_format.space_before = Pt(14)
    add_run(sign_p, layout.name, bold=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return output_path
