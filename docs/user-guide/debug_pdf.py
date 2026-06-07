"""Debug: check encoding chain and font usage."""
import io, re, base64
from pathlib import Path
import markdown
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from xhtml2pdf import pisa

SCRIPT_DIR = Path(__file__).parent
FONT_DIR = r"C:\Windows\Fonts"

# 1. Check font file contains ő (U+0151) glyph
font = TTFont("TestArial", FONT_DIR + r"\arial.ttf")
cmap = font.face.charToGlyph
has_o_double = 0x0151 in cmap
has_u_double = 0x0171 in cmap
print(f"Arial TTF has U+0151 (ő): {has_o_double}")
print(f"Arial TTF has U+0171 (ű): {has_u_double}")

# 2. Register font
pdfmetrics.registerFont(TTFont("MyArial", FONT_DIR + r"\arial.ttf"))
registerFontFamily("MyArial", normal="MyArial")

# 3. Read a small portion of README and check characters survive markdown parsing
sample_md = "## Előfeltételek\nKépernyőképek üzembe helyezők.\n\n- ő ű á é í ó ö ú ü"
html_body = markdown.markdown(sample_md)
print(f"\nHTML body: {html_body}")
print(f"ő in HTML: {chr(0x0151) in html_body}")

# 4. Generate small test PDF
html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>body {{ font-family: MyArial; font-size: 14pt; }}</style>
</head><body>{html_body}</body></html>"""

buf = io.BytesIO()
result = pisa.CreatePDF(html.encode("utf-8"), dest=buf, encoding="utf-8")
with open("debug_test.pdf", "wb") as f:
    f.write(buf.getvalue())
print(f"\nPDF generated, errors: {result.err}, size: {len(buf.getvalue())} bytes")
