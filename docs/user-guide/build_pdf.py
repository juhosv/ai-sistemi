"""
Convert README.md to SmartBlue-TasmotaManager-UserGuide.pdf.

Uses ReportLab Platypus with TTF fonts for full Unicode (ő, ű, etc.) support.
"""
import sys
import re
import base64
from io import BytesIO
from pathlib import Path

import markdown
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Preformatted,
    Table, TableStyle, PageBreak, KeepTogether,
    HRFlowable, Image,
)
from reportlab.platypus.tableofcontents import TableOfContents

SCRIPT_DIR = Path(__file__).parent
MD_FILE    = SCRIPT_DIR / "README.md"
PDF_FILE   = SCRIPT_DIR / "SmartBlue-TasmotaManager-UserGuide.pdf"
FONT_DIR   = r"C:\Windows\Fonts"

# ---------------------------------------------------------------------------
# Font registration
# ---------------------------------------------------------------------------

pdfmetrics.registerFont(TTFont("Arial",        FONT_DIR + r"\arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold",   FONT_DIR + r"\arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", FONT_DIR + r"\ariali.ttf"))
pdfmetrics.registerFont(TTFont("Courier-TTF",  FONT_DIR + r"\cour.ttf"))
registerFontFamily(
    "Arial",
    normal="Arial",
    bold="Arial-Bold",
    italic="Arial-Italic",
    boldItalic="Arial-Bold",
)

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

BLUE_DARK  = colors.HexColor("#003366")
BLUE_MID   = colors.HexColor("#004080")
BLUE_LIGHT = colors.HexColor("#cce0ff")
ORANGE     = colors.HexColor("#ffa500")
BG_CODE    = colors.HexColor("#f4f4f4")
RED_CODE   = colors.HexColor("#c7254e")

def make_styles():
    styles = getSampleStyleSheet()

    def s(name, **kw):
        styles.add(ParagraphStyle(
            name,
            fontName=kw.pop("fontName", "Arial"),
            fontSize=kw.pop("fontSize", 10),
            leading=kw.pop("leading", 15),
            textColor=kw.pop("textColor", colors.HexColor("#222222")),
            **kw,
        ))

    s("Body",       spaceAfter=4)
    s("H1",         fontSize=20, fontName="Arial-Bold", textColor=BLUE_DARK,
                    spaceBefore=6, spaceAfter=8, leading=26)
    s("H2",         fontSize=14, fontName="Arial-Bold", textColor=BLUE_MID,
                    spaceBefore=18, spaceAfter=6, leading=20)
    s("H3",         fontSize=11, fontName="Arial-Bold",
                    textColor=colors.HexColor("#005a9e"), spaceBefore=12, spaceAfter=4)
    s("H4",         fontName="Arial-Bold", spaceBefore=8, spaceAfter=4)
    s("ListItem",   leftIndent=14, spaceAfter=2)
    s("BlockQuote", leftIndent=14, rightIndent=8,
                    backColor=colors.HexColor("#fff8e8"),
                    textColor=colors.HexColor("#555555"), spaceAfter=6, spaceBefore=4)
    s("CodeInline", fontName="Courier-TTF", fontSize=9, textColor=RED_CODE)
    return styles


# ---------------------------------------------------------------------------
# Simple Markdown → Platypus flowables converter
# ---------------------------------------------------------------------------

def _inline(text: str, styles) -> str:
    """Convert inline markdown (bold, italic, code) to ReportLab XML tags."""
    # Escape existing XML special chars first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Code spans
    text = re.sub(r"`([^`]+)`",
                  lambda m: f'<font name="Courier-TTF" color="#c7254e">{m.group(1)}</font>', text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__",     r"<b>\1</b>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*",     r"<i>\1</i>", text)
    text = re.sub(r"_(.+?)_",       r"<i>\1</i>", text)
    # Links → just show text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    return text


def md_to_flowables(md_text: str, styles) -> list:
    """Convert markdown text to a list of ReportLab flowables."""
    flowables = []
    lines = md_text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_text = "\n".join(code_lines)
            flowables.append(Spacer(1, 4))
            flowables.append(
                Preformatted(code_text, ParagraphStyle(
                    "CodeBlock",
                    fontName="Courier-TTF", fontSize=8,
                    backColor=BG_CODE, leftIndent=10, rightIndent=10,
                    spaceBefore=4, spaceAfter=4, leading=12,
                ))
            )
            i += 1
            continue

        # Headings
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            text  = _inline(m.group(2), styles)
            style_name = f"H{level}" if level <= 4 else "H4"
            para = Paragraph(text, styles[style_name])
            if level == 1:
                flowables.append(HRFlowable(width="100%", thickness=2,
                                            color=BLUE_DARK, spaceAfter=6))
                flowables.append(para)
                flowables.append(HRFlowable(width="100%", thickness=1,
                                            color=BLUE_DARK, spaceBefore=4, spaceAfter=8))
            elif level == 2:
                flowables.append(para)
                flowables.append(HRFlowable(width="100%", thickness=0.5,
                                            color=BLUE_LIGHT, spaceAfter=4))
            else:
                flowables.append(para)
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^-{3,}$|^\*{3,}$|^_{3,}$", line.strip()):
            flowables.append(HRFlowable(width="100%", thickness=0.5,
                                        color=BLUE_LIGHT, spaceBefore=8, spaceAfter=8))
            i += 1
            continue

        # Unordered list item
        m = re.match(r"^[ \t]*[-*+]\s+(.*)", line)
        if m:
            text = _inline(m.group(1), styles)
            flowables.append(Paragraph(f"\u2022 {text}", styles["ListItem"]))
            i += 1
            continue

        # Ordered list item
        m = re.match(r"^[ \t]*\d+\.\s+(.*)", line)
        if m:
            text = _inline(m.group(1), styles)
            flowables.append(Paragraph(f"\u2022 {text}", styles["ListItem"]))
            i += 1
            continue

        # Blockquote
        m = re.match(r"^>\s?(.*)", line)
        if m:
            text = _inline(m.group(1), styles)
            flowables.append(Paragraph(text, styles["BlockQuote"]))
            i += 1
            continue

        # Table (detect by | chars)
        if "|" in line and i + 1 < len(lines) and re.match(r"^[\|\-: ]+$", lines[i + 1]):
            # Collect all table rows
            table_lines = [line]
            i += 1
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            # Parse header (row 0), skip separator (row 1), data rows (2+)
            def parse_row(r):
                return [_inline(c.strip(), styles)
                        for c in r.strip().strip("|").split("|")]
            rows = [parse_row(r) for r in table_lines if not re.match(r"^[\|\-: ]+$", r)]
            if rows:
                col_count = max(len(r) for r in rows)
                # Normalise row lengths
                rows = [r + [""] * (col_count - len(r)) for r in rows]
                col_w = (A4[0] - 4 * cm) / col_count
                tbl = Table([[Paragraph(c, styles["Body"]) for c in row] for row in rows],
                            colWidths=[col_w] * col_count, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ("BACKGROUND",  (0, 0), (-1, 0), BLUE_DARK),
                    ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
                    ("FONTNAME",    (0, 0), (-1, 0), "Arial-Bold"),
                    ("FONTSIZE",    (0, 0), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                     [colors.white, colors.HexColor("#f0f4ff")]),
                    ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#ddddee")),
                    ("VALIGN",      (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING",  (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                flowables.append(Spacer(1, 4))
                flowables.append(tbl)
                flowables.append(Spacer(1, 6))
            continue

        # Embedded image (base64 data URI)
        m = re.match(r'<img src="data:image/png;base64,([^"]+)" alt="([^"]*)"[^/]*/>', line)
        if m:
            img_data = base64.b64decode(m.group(1))
            img_buf  = BytesIO(img_data)
            img = Image(img_buf, width=14 * cm, height=8 * cm, kind="proportional")
            flowables.append(Spacer(1, 4))
            flowables.append(img)
            flowables.append(Spacer(1, 6))
            i += 1
            continue

        # Plain paragraph / empty line
        stripped = line.strip()
        if stripped:
            text = _inline(stripped, styles)
            flowables.append(Paragraph(text, styles["Body"]))
        else:
            flowables.append(Spacer(1, 4))
        i += 1

    return flowables


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

def _header_footer(canvas, doc):
    canvas.saveState()
    # Footer
    canvas.setFont("Arial", 8)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawCentredString(
        A4[0] / 2, 1.0 * cm,
        f"SmartBlue – Tasmota Manager  |  {doc.page}. oldal"
    )
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def md_to_pdf(md_path: Path, pdf_path: Path) -> bool:
    md_text = md_path.read_text(encoding="utf-8")

    # Embed screenshots as inline <img> tags
    def embed_image(m):
        alt  = m.group(1)
        path = SCRIPT_DIR / m.group(2)
        if path.exists():
            data = base64.b64encode(path.read_bytes()).decode()
            return f'<img src="data:image/png;base64,{data}" alt="{alt}" />'
        return f'*[Kép hiányzik: {alt}]*'

    md_text = re.sub(r'!\[([^\]]*)\]\((screenshots/[^\)]+)\)', embed_image, md_text)
    md_text = re.sub(r'\*\(ha a kép hiányzik.*?\)\*', '', md_text)

    styles = make_styles()
    story  = md_to_flowables(md_text, styles)

    doc = BaseDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm,  bottomMargin=2.5 * cm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=frame,
                                       onPage=_header_footer)])

    try:
        doc.build(story)
        return True
    except Exception as exc:
        print(f"ReportLab hiba: {exc}")
        import traceback; traceback.print_exc()
        return False


if __name__ == "__main__":
    print(f"Konvertalas: {MD_FILE} -> {PDF_FILE}")
    ok = md_to_pdf(MD_FILE, PDF_FILE)
    if ok:
        size_kb = PDF_FILE.stat().st_size // 1024
        print(f"PDF elkeszult: {PDF_FILE.name}  ({size_kb} KB)")
    else:
        print("Hiba a PDF generalas soran.")
        sys.exit(1)
