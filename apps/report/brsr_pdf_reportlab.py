# apps/report/brsr_pdf_reportlab.py
"""
Builds the BRSR report as a PDF matching the exact Lucas TVS BRSR PDF format.

--------------------------------------------------------------------------
FIX: _flatten_rows now renders a proper table for EVERY table question
--------------------------------------------------------------------------
The previous version's _flatten_rows had two bugs:

1. `_is_complex_table()` in brsr_report_data.py gated grid rendering to
   only tables whose columns mentioned "FY"/"Financial Year". Every other
   table field (business activities, holding/subsidiary companies,
   locations, employee gender breakdowns, ...) fell through to a
   cell-by-cell flatten path that produced individual "label — row —
   column" list rows instead of an actual table -- not what the UI shows.
   brsr_report_data.py now always builds a full header+rows grid for any
   non-matrix table field, so that gate is gone entirely.

2. Here, when a row `has_table`, the old code grabbed only the FIRST
   table sub-question and `break`, silently dropping any other
   sub-questions on that same row. The second "catch anything unhandled"
   loop then never actually caught them either, because its conditions
   (`not has_table`, `not has_matrix`) were already false by construction.

_flatten_rows below walks every sub_question in original order and
renders each one for what it actually is (matrix grid / table grid /
plain Q&A row) -- nothing gets dropped, and every table-shaped answer
renders as a real table, matching the question workspace UI.
--------------------------------------------------------------------------
STYLING NOTES (matched against the reference PDF screenshots)
--------------------------------------------------------------------------
- Navy blue (#1B2A56) header/label cells with white bold text.
- Gold (#F4B000) grid borders throughout.
- Question rows are three columns (Number | Question | Answer), with the
  Number cell right-aligned black-on-white and the Question cell navy/white
  bold, matching the merged "1. Corporate Identity Number..." look.
- Links/emails render in a reddish-orange (#C0504D).
- P1-P9 tables (policy coverage, Q11/Q12 assessment grids, etc.) render as
  an actual grid -- navy header row with P1..P9, navy row-label column,
  white value cells.
- Every other table-shaped answer (business activities, locations,
  holding/subsidiary companies, gender breakdowns, complaints-by-year,
  etc.) also renders as an actual grid: header row(s) + one row per entry.
- The cover page is fully custom-drawn (navy background, gold banner with
  company name/CIN, white title panel) via `_draw_cover_page`, and every
  later page gets a running "BRSR {financial_year}" header + page-number
  footer via `_draw_later_page` -- both wired in through SimpleDocTemplate's
  onFirstPage/onLaterPages hooks in generate_brsr_pdf().
"""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Lucas TVS color palette -- navy + gold, matched against the source PDF
# ---------------------------------------------------------------------------
NAVY = colors.HexColor("#1B2A56")
NAVY_TEXT = colors.white
GOLD_BORDER = colors.HexColor("#F4B000")
LINK_ORANGE = colors.HexColor("#C0504D")
BODY_TEXT = colors.HexColor("#1A1A1A")
MUTED_TEXT = colors.HexColor("#6B7280")
SECTION_LABEL_ORANGE = colors.HexColor("#F4A300")
PAGE_WHITE = colors.white

LUCAS_GREEN = NAVY
LUCAS_BLUE = NAVY
LUCAS_TABLE_BORDER = GOLD_BORDER
LUCAS_DARK = BODY_TEXT
LUCAS_MUTED = MUTED_TEXT
LUCAS_WHITE = PAGE_WHITE
LUCAS_BLACK = colors.black


def _display_financial_year(financial_year):
    if not financial_year:
        return "FY 2024-25"
    value = str(financial_year).strip()
    if value.upper().startswith("FY "):
        value = value[3:].strip()
    parts = value.split("-")
    if len(parts) == 2 and len(parts[0]) == 4 and len(parts[1]) == 4:
        value = f"{parts[0]}-{parts[1][-2:]}"
    return f"FY {value}"


def _short_company_name(company_name):
    value = (company_name or "Lucas TVS").strip()
    for suffix in (" Private Limited", " Limited", " Pvt. Ltd.", " Pvt Ltd", " Ltd.", " Ltd"):
        if value.lower().endswith(suffix.lower()):
            return value[: -len(suffix)].strip()
    return value


def _draw_later_page(canvas, doc, financial_year):
    width, height = A4
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#4B5563"))
    canvas.setLineWidth(0.5)
    canvas.rect(24, 24, width - 48, height - 48, stroke=1, fill=0)
    canvas.setFont("Helvetica-Bold", 12)
    canvas.setFillColor(colors.black)
    canvas.drawRightString(width - 38, height - 38, f"BRSR {_display_financial_year(financial_year)}")
    canvas.setFont("Helvetica", 10)
    canvas.drawRightString(width - 54, 50, str(canvas.getPageNumber()))
    canvas.restoreState()


def _draw_cover_page(canvas, doc, company_name, financial_year, company_cin):
    width, height = A4
    panel_x, panel_w = 265, 240
    panel_top = height - 24
    yellow_h = 268
    white_h = 320
    white_y = panel_top - yellow_h - white_h

    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(24, 24, width - 48, height - 48, stroke=0, fill=1)
    canvas.setFillColor(GOLD_BORDER)
    canvas.rect(panel_x, panel_top - yellow_h, panel_w, yellow_h, stroke=0, fill=1)
    canvas.setFillColor(PAGE_WHITE)
    canvas.rect(panel_x, white_y, panel_w, white_h, stroke=0, fill=1)
    canvas.setStrokeColor(colors.HexColor("#9CA3AF"))
    canvas.setLineWidth(1)
    canvas.rect(panel_x, white_y, panel_w, yellow_h + white_h, stroke=1, fill=0)
    canvas.setFillColor(GOLD_BORDER)
    canvas.rect(panel_x, white_y + 62, panel_w, 10, stroke=0, fill=1)

    canvas.setFillColor(colors.black)
    canvas.setFont("Times-Bold", 15)
    canvas.drawCentredString(panel_x + panel_w / 2, panel_top - 170, _short_company_name(company_name))
    canvas.setFont("Times-Bold", 14)
    cin_text = f"CIN: {company_cin}" if company_cin else "CIN:"
    canvas.drawCentredString(panel_x + panel_w / 2, panel_top - 208, cin_text)

    canvas.setFillColor(NAVY)
    canvas.setFont("Times-Roman", 31)
    y = white_y + white_h - 62
    for line in ("Business", "Responsibility", "&", "Sustainability", "Report", _display_financial_year(financial_year)):
        canvas.drawCentredString(panel_x + panel_w / 2, y, line)
        y -= 35
    canvas.restoreState()


def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="BRSR_CoverTitle", fontSize=26, leading=32, alignment=TA_CENTER,
        textColor=NAVY, spaceAfter=6, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_CoverSub", fontSize=14, alignment=TA_CENTER, textColor=MUTED_TEXT,
        spaceAfter=4, fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_CoverCompany", fontSize=18, alignment=TA_CENTER, textColor=NAVY,
        spaceAfter=6, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_CoverFooter", fontSize=10, alignment=TA_CENTER, textColor=MUTED_TEXT,
        spaceBefore=20, fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_SectionHeading", fontSize=14, leading=18, textColor=NAVY,
        spaceBefore=14, spaceAfter=8, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_SubHeading", fontSize=10.5, leading=13, textColor=SECTION_LABEL_ORANGE,
        spaceBefore=10, spaceAfter=4, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_PrincipleHeading", fontSize=11, leading=14, textColor=colors.white,
        backColor=NAVY, spaceBefore=8, spaceAfter=4, leftIndent=4,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_IndicatorLabel", fontSize=9, leading=12, textColor=MUTED_TEXT,
        spaceBefore=6, spaceAfter=3, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_LabelText", fontSize=9, leading=11.5, textColor=NAVY_TEXT,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_NumberText", fontSize=9, leading=11.5, textColor=colors.black,
        fontName="Helvetica-Bold", alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        name="BRSR_AnswerText", fontSize=8, leading=10.5, textColor=BODY_TEXT,
        fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_AnswerBlank", fontSize=8, leading=10.5, textColor=MUTED_TEXT,
        fontName="Helvetica-Oblique",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_AnswerLink", fontSize=8, leading=10.5, textColor=LINK_ORANGE,
        fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_MatrixHeader", fontSize=7.5, leading=9.5, textColor=NAVY_TEXT,
        fontName="Helvetica-Bold", alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="BRSR_MatrixRowLabel", fontSize=7.5, leading=9.5, textColor=NAVY_TEXT,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_MatrixValue", fontSize=8, leading=10, textColor=BODY_TEXT,
        fontName="Helvetica", alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="BRSR_MatrixHeaderSmall", fontSize=6, leading=8, textColor=NAVY_TEXT,
        fontName="Helvetica-Bold", alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="BRSR_MatrixValueSmall", fontSize=6, leading=8, textColor=BODY_TEXT,
        fontName="Helvetica", alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="BRSR_MatrixRowLabelSmall", fontSize=6, leading=8, textColor=NAVY_TEXT,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_BodyText", fontSize=10.5, leading=14, alignment=TA_JUSTIFY,
        spaceAfter=9, fontName="Times-Roman",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_Signature", fontSize=10.5, leading=15, alignment=TA_RIGHT,
        spaceAfter=6, fontName="Times-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_SubjectLine", fontSize=11, leading=14, alignment=TA_LEFT,
        spaceBefore=10, spaceAfter=10, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_TOCHeading", fontSize=20, leading=24, alignment=TA_LEFT,
        textColor=colors.black, spaceAfter=26, fontName="Times-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_TOCSectionLabel", fontSize=10, leading=15, alignment=TA_LEFT,
        textColor=SECTION_LABEL_ORANGE, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_TOCPrincipleNumber", fontSize=10, leading=13, alignment=TA_LEFT,
        textColor=colors.white, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="BRSR_TOCPrincipleText", fontSize=10.5, leading=12.5, alignment=TA_LEFT,
        textColor=colors.black, fontName="Times-Roman",
    ))
    return styles


def _create_cover_page(story, styles, company_name, financial_year):
    story.append(PageBreak())


def _create_subject_page(story, styles, company_name, financial_year):
    story.append(Spacer(1, 36))
    story.append(Paragraph("<b><font size='28'>pwc</font></b>", styles["BRSR_BodyText"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Subject: Expression of gratitude", styles["BRSR_SubjectLine"]))
    story.append(Spacer(1, 8))

    body_text = f"""
    We, PricewaterhouseCoopers Private Limited (PwC India), are pleased to submit our
    deliverable for the "Preparation of Business Responsibility & Sustainability Report
    (BRSR) as per SEBI Guidelines for {_display_financial_year(financial_year)}" for
    {company_name}.
    """
    story.append(Paragraph(body_text.strip(), styles["BRSR_BodyText"]))
    story.append(Spacer(1, 6))

    body_text2 = f"""
    Leveraging our experience and expertise, and in collaboration with the {company_name}
    team, we have developed a comprehensive Business Responsibility & Sustainability
    Report for the {_display_financial_year(financial_year)}. We believe that our deliverable meets the expectations
    and requirements of this project.
    """
    story.append(Paragraph(body_text2.strip(), styles["BRSR_BodyText"]))
    story.append(Spacer(1, 6))

    body_text3 = """
    We express our gratitude for this opportunity and eagerly look forward to continuing
    our partnership with you, supporting any future initiatives. We will be happy to
    provide any clarifications or additional information necessary.
    """
    story.append(Paragraph(body_text3.strip(), styles["BRSR_BodyText"]))
    story.append(Spacer(1, 32))

    story.append(Paragraph("Yours sincerely,", styles["BRSR_Signature"]))
    story.append(Spacer(1, 20))
    story.append(Paragraph("Sandeep Mohanty", styles["BRSR_Signature"]))
    story.append(Paragraph("Partner, PwC India", styles["BRSR_Signature"]))
    story.append(PageBreak())


def _create_toc_page(story, styles):
    story.append(Spacer(1, 58))
    story.append(Paragraph("BRSR Overview", styles["BRSR_TOCHeading"]))
    story.append(Spacer(1, 6))

    for label in (
        "Section A: General Disclosures",
        "Section B: Management and Process Disclosures",
        "Section C: Principle-wise Performance Disclosure",
    ):
        story.append(Paragraph(label, styles["BRSR_TOCSectionLabel"]))
    story.append(Spacer(1, 14))

    principles = [
        ("Principle 1", "Businesses should conduct and govern themselves with integrity and in a manner that is ethical, transparent, and accountable"),
        ("Principle 2", "Businesses should provide goods and services in a manner that is sustainable and safe"),
        ("Principle 3", "Businesses should respect and promote the well-being of ALL employees, including those in their value chains"),
        ("Principle 4", "Businesses should respect the interests of and be responsive to ALL their stakeholders"),
        ("Principle 5", "Businesses should respect and promote human rights"),
        ("Principle 6", "Businesses should respect and make efforts to protect and restore the environment"),
        ("Principle 7", "Businesses, when engaging in influencing public and regulatory policy, should do so in a manner that is responsible and transparent"),
        ("Principle 8", "Businesses should promote inclusive growth and equitable development"),
        ("Principle 9", "Businesses should engage with and provide value to their consumers in a responsible manner"),
    ]

    data = [
        [Paragraph(num, styles["BRSR_TOCPrincipleNumber"]), Paragraph(text, styles["BRSR_TOCPrincipleText"])]
        for num, text in principles
    ]

    table = Table(data, colWidths=[110, 390])
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (0, -1), 0.6, colors.HexColor("#D1D5DB")),
        ("BACKGROUND", (0, 0), (0, -1), NAVY),
        ("BACKGROUND", (1, 0), (1, -1), PAGE_WHITE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    story.append(PageBreak())


# ---------------------------------------------------------------------------
# Answer formatting
# ---------------------------------------------------------------------------

def _looks_like_link(value):
    v = (value or "").strip().lower()
    return v.startswith("http") or v.startswith("www.") or "@" in v


def _answer_paragraph(value, styles):
    if not value:
        return Paragraph("-", styles["BRSR_AnswerBlank"])
    if _looks_like_link(str(value)):
        return Paragraph(str(value), styles["BRSR_AnswerLink"])
    return Paragraph(str(value), styles["BRSR_AnswerText"])


def _is_roman_heading(value):
    value = (value or "").strip().upper().rstrip(".")
    return bool(value) and all(ch in "IVXLCDM" for ch in value)


# ---------------------------------------------------------------------------
# Flatten rows -> render items, in original order, dropping nothing
# ---------------------------------------------------------------------------

def _flatten_rows(rows):
    """
    Walks each top-level row and ALL of its sub_questions (not just the
    first one), yielding one of:
      ("heading", roman_numeral, text, None, None)
      ("matrix", label, columns, matrix_rows, None)
      ("table", label, table_rows, table_headers, None)
      ("row", number, text, question_type, answer_value)
    in original document order. Roman-numeral headings (Section A's "I.",
    "II.", ...) get their sub_questions numbered 1, 2, 3... continuously,
    matching the source PDF; ordinary multi-field questions keep the
    parent's number on the first field only.
    """
    items = []
    serial = 1

    for row in rows:
        number = row.get("question_number") or ""
        row_text = row.get("question_text", "")
        sub_questions = row.get("sub_questions", []) or []
        is_heading = _is_roman_heading(number) and bool(sub_questions)

        if not sub_questions:
            items.append(("row", number, row_text, row.get("question_type"), row.get("answer_value", "")))
            continue

        if is_heading:
            items.append(("heading", number, row_text, None, None))

        for i, sub in enumerate(sub_questions):
            sub_type = sub.get("question_type")

            if sub_type == "matrix":
                items.append((
                    "matrix",
                    sub.get("question_text") or row_text,
                    sub.get("matrix_columns", []),
                    sub.get("matrix_rows", []),
                    None,
                ))
            elif sub_type == "table":
                items.append((
                    "table",
                    sub.get("question_text") or row_text,
                    sub.get("table_rows", []),
                    sub.get("table_headers", []),
                    None,
                ))
            else:
                if is_heading:
                    sub_number = str(serial)
                    serial += 1
                else:
                    sub_number = number if i == 0 else ""
                items.append(("row", sub_number, sub.get("question_text", ""), sub_type, sub.get("answer_value", "")))

    return items


def _create_matrix_grid(field_label, columns, matrix_rows, styles):
    """One P1-P9 grid: navy header row (P1..P9), navy row-label column,
    white value cells -- matches Q11/Q12 in the reference PDF."""
    story_items = []
    if field_label:
        story_items.append(Paragraph(field_label, styles["BRSR_SubHeading"]))

    header = [Paragraph("", styles["BRSR_MatrixHeader"])] + [
        Paragraph(col, styles["BRSR_MatrixHeader"]) for col in columns
    ]
    data = [header]

    for mrow in matrix_rows:
        row_label = Paragraph(mrow.get("label", ""), styles["BRSR_MatrixRowLabel"])
        values = mrow.get("values", {})
        cells = []
        for col in columns:
            val = values.get(col, "")
            if val is True or val == "True":
                val = "Yes"
            elif val is False or val == "False":
                val = ""
            elif val is None:
                val = "-"
            cells.append(Paragraph(str(val) if val not in ("", "-") else "-", styles["BRSR_MatrixValue"]))
        data.append([row_label] + cells)

    label_col_width = 170
    value_col_width = (480 - label_col_width) / max(len(columns), 1)
    col_widths = [label_col_width] + [value_col_width] * len(columns)

    table = Table(data, colWidths=col_widths, repeatRows=1)
    style_commands = [
        ("GRID", (0, 0), (-1, -1), 0.6, GOLD_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("BACKGROUND", (0, 1), (0, -1), NAVY),
        ("BACKGROUND", (1, 1), (-1, -1), PAGE_WHITE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("TEXTCOLOR", (0, 1), (0, -1), colors.white),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
    ]
    table.setStyle(TableStyle(style_commands))
    story_items.append(table)
    story_items.append(Spacer(1, 8))
    return story_items


def _create_table_grid(question_text, table_headers, table_rows, styles):
    """
    Renders ANY table-shaped answer as a real grid: navy header row(s) at
    top, navy row-label column down the left, white data cells -- e.g.
    business activities, locations, holding/subsidiary companies, employee
    gender breakdowns, complaints-by-year, etc. This is what EVERY
    "table"-type sub_question routes through now, not just ones with
    "FY"-style columns.
    """
    story_items = []
    if question_text:
        story_items.append(Paragraph(question_text, styles["BRSR_SubHeading"]))
        story_items.append(Spacer(1, 4))

    if not table_headers or not table_rows:
        story_items.append(Paragraph("-", styles["BRSR_AnswerBlank"]))
        return story_items

    num_cols = len(table_headers[0])
    is_wide = num_cols > 6

    header_style = styles["BRSR_MatrixHeaderSmall"] if is_wide else styles["BRSR_MatrixHeader"]
    value_style = styles["BRSR_MatrixValueSmall"] if is_wide else styles["BRSR_MatrixValue"]
    row_label_style = styles["BRSR_MatrixRowLabelSmall"] if is_wide else styles["BRSR_MatrixRowLabel"]

    data = []
    for header_row in table_headers:
        data.append([Paragraph(h or "", header_style) for h in header_row])

    for row in table_rows:
        row_cells = []
        for i, cell in enumerate(row):
            if i == 0:
                row_cells.append(Paragraph(str(cell) if cell else "", row_label_style))
            else:
                row_cells.append(Paragraph(str(cell) if cell not in (None, "") else "-", value_style))
        data.append(row_cells)

    available_width = 480
    if is_wide:
        label_width = 90
        data_width = max(28, (available_width - label_width) / max(num_cols - 1, 1))
    else:
        label_width = 150
        data_width = max(40, (available_width - label_width) / max(num_cols - 1, 1))
    col_widths = [label_width] + [data_width] * (num_cols - 1)

    total_width = sum(col_widths)
    if total_width > available_width:
        scale = available_width / total_width
        col_widths = [w * scale for w in col_widths]

    table = Table(data, colWidths=col_widths, repeatRows=len(table_headers))
    style_commands = [
        ("GRID", (0, 0), (-1, -1), 0.4 if is_wide else 0.6, GOLD_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3 if is_wide else 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 if is_wide else 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 if is_wide else 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 if is_wide else 5),
    ]
    num_header_rows = len(table_headers)
    for row_idx in range(num_header_rows):
        style_commands += [
            ("BACKGROUND", (0, row_idx), (-1, row_idx), NAVY),
            ("TEXTCOLOR", (0, row_idx), (-1, row_idx), colors.white),
            ("FONTNAME", (0, row_idx), (-1, row_idx), "Helvetica-Bold"),
            ("ALIGN", (0, row_idx), (-1, row_idx), "CENTER"),
        ]
    for row_idx in range(num_header_rows, len(data)):
        style_commands += [
            ("BACKGROUND", (0, row_idx), (0, row_idx), NAVY),
            ("TEXTCOLOR", (0, row_idx), (0, row_idx), colors.white),
            ("FONTNAME", (0, row_idx), (0, row_idx), "Helvetica-Bold"),
            ("BACKGROUND", (1, row_idx), (-1, row_idx), PAGE_WHITE),
        ]

    table.setStyle(TableStyle(style_commands))
    story_items.append(table)
    story_items.append(Spacer(1, 8))
    return story_items


def _create_question_table(rows, styles):
    """
    Renders a block of rows: plain questions batch into one 3-column
    (Number | Question | Answer) navy/white table; matrix and table
    sub_questions each get their own grid, interleaved in original order
    via _flatten_rows so nothing from the source data gets skipped.
    """
    if not rows:
        return [Spacer(1, 4)]

    items = _flatten_rows(rows)
    story_items = []
    pending_data = []

    def flush_table():
        if not pending_data:
            return
        table = Table(pending_data, colWidths=[30, 236, 214])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.6, GOLD_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (0, 0), (0, -1), PAGE_WHITE),
            ("BACKGROUND", (1, 0), (1, -1), NAVY),
            ("BACKGROUND", (2, 0), (2, -1), PAGE_WHITE),
            ("TEXTCOLOR", (1, 0), (1, -1), colors.white),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ]))
        story_items.append(table)
        story_items.append(Spacer(1, 6))
        pending_data.clear()

    for item in items:
        kind = item[0]
        if kind == "matrix":
            flush_table()
            _, field_label, columns, matrix_rows, _ = item
            story_items.extend(_create_matrix_grid(field_label, columns, matrix_rows, styles))
        elif kind == "table":
            flush_table()
            _, question_text, table_rows, table_headers, _ = item
            story_items.extend(_create_table_grid(question_text, table_headers, table_rows, styles))
        elif kind == "heading":
            flush_table()
            _, number, text, _, _ = item
            story_items.append(Paragraph(f"{number}.&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{text}", styles["BRSR_SubHeading"]))
        else:
            _, number, text, q_type, answer = item
            if q_type == "checkbox" and isinstance(answer, str) and answer:
                if answer.lower() in ("true", "yes", "1", "on"):
                    answer = "Yes"
                elif answer.lower() in ("false", "no", "0", "off"):
                    answer = "No"
            number_para = Paragraph(f"{number}." if number else "", styles["BRSR_NumberText"])
            label_para = Paragraph(text, styles["BRSR_LabelText"])
            answer_para = _answer_paragraph(answer, styles)
            pending_data.append([number_para, label_para, answer_para])

    flush_table()
    return story_items


def generate_brsr_pdf(financial_year=None, assignment_id=None, company_name="Lucas TVS Ltd", company_cin=""):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="BRSR Report",
    )

    styles = _build_styles()
    story = []

    _create_cover_page(story, styles, company_name, financial_year)
    _create_subject_page(story, styles, company_name, financial_year)
    _create_toc_page(story, styles)

    try:
        from .brsr_report_data import get_brsr_report_data
        report_sections = get_brsr_report_data(financial_year, assignment_id)
    except ImportError:
        report_sections = []

    for block in report_sections:
        section = block.get("section", {})
        section_name = getattr(section, "name", "Unknown Section") if hasattr(section, "name") else "Unknown Section"

        story.append(Paragraph(section_name.upper(), styles["BRSR_SectionHeading"]))

        if not block.get("is_principle_section", False):
            for sub in block.get("sub_sections", []):
                sub_title = sub.get("title", "General")
                if sub_title != "General" and sub_title:
                    story.append(Paragraph(sub_title, styles["BRSR_SubHeading"]))
                if sub.get("rows"):
                    story.extend(_create_question_table(sub["rows"], styles))
        else:
            for p_block in block.get("principle_blocks", []):
                principle = p_block.get("principle")
                if principle:
                    if hasattr(principle, "principle_number"):
                        principle_num = principle.principle_number
                        principle_title = getattr(principle, "title", "")
                    else:
                        principle_num = principle.get("principle_number", "")
                        principle_title = principle.get("title", "")
                    story.append(Paragraph(
                        f"Principle {principle_num}: {principle_title}",
                        styles["BRSR_PrincipleHeading"],
                    ))
                if p_block.get("rows"):
                    essential = [r for r in p_block["rows"] if (r.get("sub_section") or "").lower().startswith("essential")]
                    leadership = [r for r in p_block["rows"] if (r.get("sub_section") or "").lower().startswith("leadership")]
                    other = [r for r in p_block["rows"] if r not in essential and r not in leadership]

                    if essential:
                        story.append(Paragraph("Essential Indicators", styles["BRSR_IndicatorLabel"]))
                        story.extend(_create_question_table(essential, styles))
                    if leadership:
                        story.append(Paragraph("Leadership Indicators", styles["BRSR_IndicatorLabel"]))
                        story.extend(_create_question_table(leadership, styles))
                    if other:
                        story.extend(_create_question_table(other, styles))

        story.append(Spacer(1, 6))

    doc.build(
        story,
        onFirstPage=lambda canvas, doc: _draw_cover_page(
            canvas, doc, company_name, financial_year, company_cin
        ),
        onLaterPages=lambda canvas, doc: _draw_later_page(canvas, doc, financial_year),
    )
    buffer.seek(0)
    return buffer


__all__ = ["generate_brsr_pdf"]