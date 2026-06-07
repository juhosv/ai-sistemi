"""Convert README.md to SmartBlue-TasmotaManager-UserGuide.pdf using xhtml2pdf."""
import sys
from pathlib import Path
import markdown
from xhtml2pdf import pisa

SCRIPT_DIR = Path(__file__).parent
MD_FILE    = SCRIPT_DIR / "README.md"
PDF_FILE   = SCRIPT_DIR / "SmartBlue-TasmotaManager-UserGuide.pdf"

CSS = """
@page {
    size: A4;
    margin: 2cm 2cm 2.5cm 2cm;
}

body {
    font-family: Arial, Helvetica, sans-serif;
    font-size: 10pt;
    color: #222;
    line-height: 1.55;
}

h1 {
    font-size: 20pt;
    color: #003366;
    border-bottom: 2px solid #003366;
    padding-bottom: 6px;
    margin-top: 0;
}

h2 {
    font-size: 14pt;
    color: #004080;
    border-bottom: 1px solid #cce0ff;
    padding-bottom: 4px;
    margin-top: 24px;
    page-break-after: avoid;
}

h3 {
    font-size: 11pt;
    color: #005a9e;
    margin-top: 16px;
    page-break-after: avoid;
}

h4 {
    font-size: 10pt;
    color: #333;
    margin-top: 12px;
}

p { margin: 6px 0; }

code {
    font-family: "Courier New", Courier, monospace;
    font-size: 9pt;
    background: #f4f4f4;
    padding: 1px 4px;
    border-radius: 3px;
    color: #c7254e;
}

pre {
    background: #f4f4f4;
    border-left: 4px solid #003366;
    padding: 10px 14px;
    font-family: "Courier New", Courier, monospace;
    font-size: 8.5pt;
    white-space: pre-wrap;
    word-wrap: break-word;
    margin: 10px 0;
}

pre code {
    background: none;
    padding: 0;
    color: #222;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0;
    font-size: 9.5pt;
}

th {
    background: #003366;
    color: #fff;
    padding: 6px 8px;
    text-align: left;
}

td {
    padding: 5px 8px;
    border-bottom: 1px solid #dde;
}

tr:nth-child(even) td {
    background: #f0f4ff;
}

blockquote {
    border-left: 4px solid #ffa500;
    background: #fff8e8;
    margin: 10px 0;
    padding: 8px 14px;
    color: #555;
    font-size: 9.5pt;
}

ul, ol {
    margin: 6px 0 6px 20px;
    padding: 0;
}

li { margin: 3px 0; }

hr {
    border: none;
    border-top: 1px solid #cce0ff;
    margin: 18px 0;
}

a { color: #004080; }

/* Screenshot placeholder – skip missing images gracefully */
img { max-width: 100%; }
"""

def md_to_pdf(md_path: Path, pdf_path: Path) -> bool:
    md_text = md_path.read_text(encoding="utf-8")

    # Remove screenshot img tags (missing files would break xhtml2pdf)
    import re
    md_text = re.sub(r'!\[.*?\]\(screenshots/[^\)]+\)', '', md_text)
    md_text = re.sub(r'\*\(ha a kép hiányzik.*?\)\*', '', md_text)

    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "toc"],
    )

    html_full = f"""<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="utf-8"/>
<style>{CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""

    with open(pdf_path, "wb") as pdf_file:
        result = pisa.CreatePDF(html_full, dest=pdf_file, encoding="utf-8")

    return not result.err


if __name__ == "__main__":
    print(f"Konvertalas: {MD_FILE} -> {PDF_FILE}")
    ok = md_to_pdf(MD_FILE, PDF_FILE)
    if ok:
        size_kb = PDF_FILE.stat().st_size // 1024
        print(f"PDF elkeszult: {PDF_FILE.name}  ({size_kb} KB)")
    else:
        print("Hiba a PDF generalas soran.")
        sys.exit(1)
