"""Generate comprehensive, beautifully styled PDF documentation and organize all docs into Documentation/ folder."""
import os, sys, subprocess, shutil
from pathlib import Path
import markdown

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "Documentation"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE_EXE):
    EDGE_EXE = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

# 1. Copy Markdown docs to Documentation folder
files_to_copy = [
    ROOT / "SYSTEM_DOCUMENTATION.md",
    ROOT / "API_DOCUMENTATION.md",
    ROOT / "API_CONTRACT.md",
]

for src in files_to_copy:
    if src.exists():
        dest = DOCS_DIR / src.name
        shutil.copy2(src, dest)
        print(f"Copied {src.name} -> {DOCS_DIR / src.name}")

# CSS Template for PDF Generation
PDF_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap');

@page {
    size: A4;
    margin: 18mm 16mm 18mm 16mm;
    @bottom-right {
        content: counter(page);
        font-family: 'Inter', sans-serif;
        font-size: 9pt;
        color: #64748b;
    }
}

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #1e293b;
    line-height: 1.65;
    font-size: 10pt;
    background: #ffffff;
    margin: 0;
    padding: 0;
}

/* Header & Cover Banner */
.cover-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #2563eb 100%);
    color: #ffffff;
    padding: 36px 30px;
    border-radius: 12px;
    margin-bottom: 28px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.15);
}

.cover-header h1 {
    font-size: 24pt;
    font-weight: 900;
    margin: 0 0 10px 0;
    color: #ffffff;
    border: none;
    padding: 0;
    letter-spacing: -0.5px;
}

.cover-header p {
    font-size: 11pt;
    color: #cbd5e1;
    margin: 0;
    line-height: 1.5;
}

.badge-row {
    margin-top: 14px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.badge {
    background: rgba(255, 255, 255, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.25);
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 8.5pt;
    font-weight: 600;
    color: #f8fafc;
    display: inline-block;
}

/* Typography */
h1 {
    font-size: 18pt;
    font-weight: 800;
    color: #0f172a;
    margin-top: 32px;
    margin-bottom: 14px;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 8px;
    page-break-after: avoid;
    letter-spacing: -0.3px;
}

h2 {
    font-size: 14pt;
    font-weight: 700;
    color: #1e3a8a;
    margin-top: 24px;
    margin-bottom: 10px;
    border-bottom: 1px solid #f1f5f9;
    padding-bottom: 6px;
    page-break-after: avoid;
}

h3 {
    font-size: 11.5pt;
    font-weight: 700;
    color: #334155;
    margin-top: 18px;
    margin-bottom: 8px;
    page-break-after: avoid;
}

h4 {
    font-size: 10.5pt;
    font-weight: 600;
    color: #475569;
    margin-top: 14px;
    margin-bottom: 6px;
}

p {
    margin: 0 0 10px 0;
}

ul, ol {
    margin: 0 0 12px 0;
    padding-left: 20px;
}

li {
    margin-bottom: 4px;
}

/* Tables */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0 20px 0;
    font-size: 9pt;
    page-break-inside: avoid;
    box-shadow: 0 2px 5px rgba(0,0,0,0.03);
    border-radius: 6px;
    overflow: hidden;
}

th {
    background: #0f172a;
    color: #ffffff;
    font-weight: 700;
    text-align: left;
    padding: 9px 12px;
    border: 1px solid #1e293b;
    font-size: 8.5pt;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

td {
    padding: 8px 12px;
    border: 1px solid #e2e8f0;
    color: #334155;
    background: #ffffff;
}

tr:nth-child(even) td {
    background: #f8fafc;
}

/* Code Blocks */
pre {
    background: #0f172a;
    color: #e2e8f0;
    padding: 14px 18px;
    border-radius: 8px;
    font-family: 'JetBrains Mono', Consolas, monospace;
    font-size: 8.5pt;
    line-height: 1.5;
    overflow-x: auto;
    margin: 14px 0;
    border: 1px solid #1e293b;
    page-break-inside: avoid;
}

code {
    font-family: 'JetBrains Mono', Consolas, monospace;
    font-size: 8.5pt;
    background: #f1f5f9;
    color: #0369a1;
    padding: 2px 5px;
    border-radius: 4px;
    border: 1px solid #e2e8f0;
}

pre code {
    background: transparent;
    color: #e2e8f0;
    padding: 0;
    border: none;
}

/* Blockquotes & Callouts */
blockquote {
    border-left: 4px solid #3b82f6;
    background: #eff6ff;
    margin: 14px 0;
    padding: 10px 16px;
    border-radius: 0 8px 8px 0;
    color: #1e40af;
    font-size: 9.5pt;
}

blockquote p {
    margin: 0;
}

hr {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 24px 0;
}

.footer-note {
    margin-top: 30px;
    padding-top: 12px;
    border-top: 1px solid #cbd5e1;
    font-size: 8pt;
    color: #64748b;
    text-align: center;
}
"""

def generate_pdf_from_markdown(md_path: Path, output_pdf: Path, title: str, subtitle: str, badges: list[str]):
    md_content = md_path.read_text(encoding="utf-8")
    
    # Strip existing top title if duplicate
    lines = md_content.splitlines()
    body_lines = []
    skip = False
    for line in lines:
        if line.startswith("# ") and not body_lines:
            continue
        body_lines.append(line)
    clean_md = "\n".join(body_lines)

    html_body = markdown.markdown(
        clean_md,
        extensions=["extra", "tables", "fenced_code", "codehilite", "toc"]
    )

    badge_html = "".join([f'<span class="badge">{b}</span>' for b in badges])

    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
{PDF_CSS}
</style>
</head>
<body>

<div class="cover-header">
    <h1>{title}</h1>
    <p>{subtitle}</p>
    <div class="badge-row">
        {badge_html}
    </div>
</div>

{html_body}

<div class="footer-note">
    DataLink Engine Architecture & Engineering Reference &bull; Verified in Visual Studio Code (VS Code) &bull; Confidential & Proprietary
</div>

</body>
</html>"""

    temp_html = DOCS_DIR / f"temp_{output_pdf.stem}.html"
    temp_html.write_text(full_html, encoding="utf-8")

    cmd = [
        EDGE_EXE,
        "--headless",
        "--disable-gpu",
        f"--print-to-pdf={output_pdf.resolve()}",
        f"file:///{temp_html.resolve().as_posix()}",
    ]
    
    res = subprocess.run(cmd, capture_output=True)
    temp_html.unlink(missing_ok=True)

    if output_pdf.exists():
        size_kb = output_pdf.stat().st_size / 1024
        print(f"✓ Generated PDF: {output_pdf.name} ({size_kb:.1f} KB)")
    else:
        print(f"✗ Failed to generate PDF: {output_pdf.name}")

# Generate 1: System Documentation PDF
sys_md = DOCS_DIR / "SYSTEM_DOCUMENTATION.md"
sys_pdf = DOCS_DIR / "DataLink_Engine_System_Documentation.pdf"
generate_pdf_from_markdown(
    sys_md, sys_pdf,
    title="DataLink Engine — System & Architecture Manual",
    subtitle="Enterprise Real Estate Data Ingestion, Normalization, Deduplication & Export Platform",
    badges=["Python 3.12", "FastAPI", "React 18", "Vite 5", "Supabase PostgreSQL", "VS Code Tooling", "Production v2.0"]
)

# Generate 2: API Documentation PDF
api_md = DOCS_DIR / "API_DOCUMENTATION.md"
api_pdf = DOCS_DIR / "DataLink_Engine_REST_API_Documentation.pdf"
generate_pdf_from_markdown(
    api_md, api_pdf,
    title="DataLink Engine — Complete REST API Specification",
    subtitle="Interactive Endpoints, Pydantic Schemas, Filtering & Streaming Export Reference",
    badges=["OpenAPI 3.0", "RESTful", "FastAPI", "Pydantic v2", "Excel & CSV Streaming", "Production Ready"]
)

# Generate 3: Combined Unified Manual PDF
combined_md_content = f"""
# Part I: System Architecture & Engineering

{sys_md.read_text(encoding='utf-8')}

---

# Part II: REST API Reference & Verification Guide

{api_md.read_text(encoding='utf-8')}
"""
combined_md = DOCS_DIR / "COMPLETE_MANUAL.md"
combined_md.write_text(combined_md_content, encoding="utf-8")
combined_pdf = DOCS_DIR / "DataLink_Engine_Complete_Manual.pdf"

generate_pdf_from_markdown(
    combined_md, combined_pdf,
    title="DataLink Engine — Complete Technical & API Master Manual",
    subtitle="Comprehensive System Architecture, Pipeline Specifications, Tools, and REST API Reference",
    badges=["Complete Edition", "VS Code Toolchain", "FastAPI + React 18", "Supabase PostgreSQL", "Production Ready"]
)

print("\n=== Documentation Packaging Complete ===")
for item in sorted(DOCS_DIR.iterdir()):
    print(f"  📁 Documentation/{item.name} ({item.stat().st_size / 1024:.1f} KB)")
