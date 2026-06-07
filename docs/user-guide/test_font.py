"""Minimal Hungarian font test for xhtml2pdf."""
import io
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from xhtml2pdf import pisa

FONT_DIR = r"C:\Windows\Fonts"

pdfmetrics.registerFont(TTFont("MyArial", FONT_DIR + r"\arial.ttf"))
registerFontFamily("MyArial", normal="MyArial")

CHARS = "\u0151 \u0171 \u00e1 \u00e9 \u00ed \u00f3 \u00f6 \u00fa \u00fc"
WORDS = "El\u0151felt\u00e9telek K\u00e9perny\u0151k\u00e9pek \u00fczembe helyez\u0151k"

html = (
    '<!DOCTYPE html><html><head><meta charset="utf-8"/>'
    '<style>body { font-family: MyArial; font-size: 14pt; }</style>'
    "</head><body>"
    f"<p>Egyes karakterek: {CHARS}</p>"
    f"<p>Szavak: {WORDS}</p>"
    "</body></html>"
)

# Check HTML encoding is correct
print("HTML contains U+0151:", "\u0151" in html)
print("HTML contains U+0171:", "\u0171" in html)

buf = io.BytesIO()
result = pisa.CreatePDF(html.encode("utf-8"), dest=buf, encoding="utf-8")
if not result.err:
    with open("test_font.pdf", "wb") as f:
        f.write(buf.getvalue())
    print(f"OK – test_font.pdf ({len(buf.getvalue())//1024} KB)")
else:
    print("HIBA:", result.err)
