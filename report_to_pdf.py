"""
report_to_pdf.py — Markdown to styled PDF converter for financial reports.

Uses `markdown` for MD->HTML and `xhtml2pdf` for HTML->PDF.
Tables are post-processed to inject explicit <colgroup> widths so
xhtml2pdf doesn't collapse columns together.

Usage:
    from report_to_pdf import md_to_pdf

    pdf_path = md_to_pdf("reports/QuanTum_v7_20260222.md")

    pdf_path = md_to_pdf(md_text="# Hello\nWorld", output_path="out.pdf")
"""

import os
import re
from datetime import datetime
from pathlib import Path

import markdown
from xhtml2pdf import pisa

# ── Professional financial report stylesheet ──────────────────────────────────

CSS = """
@page {
    size: A4;
    margin: 1.8cm 1.5cm;

    @frame header {
        -pdf-frame-content: page-header;
        top: 0.4cm;
        margin-left: 1.5cm;
        margin-right: 1.5cm;
        height: 1.2cm;
    }

    @frame footer {
        -pdf-frame-content: page-footer;
        bottom: 0.3cm;
        margin-left: 1.5cm;
        margin-right: 1.5cm;
        height: 1cm;
    }
}

body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 10px;
    line-height: 1.5;
    color: #1a1a2e;
}

#page-header {
    border-bottom: 2px solid #0f3460;
    padding-bottom: 4px;
    font-size: 7px;
    color: #0f3460;
}
#page-footer {
    border-top: 1px solid #cccccc;
    padding-top: 4px;
    font-size: 7px;
    color: #888888;
    text-align: center;
}

h1 {
    font-size: 18px;
    color: #0f3460;
    border-bottom: 3px solid #e94560;
    padding-bottom: 6px;
    margin-top: 8px;
    margin-bottom: 12px;
}
h2 {
    font-size: 14px;
    color: #0f3460;
    border-bottom: 1.5px solid #0f3460;
    padding-bottom: 3px;
    margin-top: 16px;
    margin-bottom: 8px;
}
h3 {
    font-size: 11px;
    color: #16213e;
    margin-top: 12px;
    margin-bottom: 5px;
}
h4 {
    font-size: 10px;
    color: #e94560;
    margin-top: 8px;
    margin-bottom: 4px;
}

p  { margin: 3px 0 6px 0; }
ul, ol { margin: 3px 0 6px 16px; }
li { margin-bottom: 2px; }

strong { color: #16213e; }
em     { color: #555555; }
code   { font-family: Courier, monospace; font-size: 9px;
         background-color: #f0f0f0; padding: 1px 3px; }

/* ── Tables — fixed layout, explicit borders ──── */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0 12px 0;
    table-layout: fixed;
    -pdf-keep-in-frame-mode: shrink;
}
thead tr {
    background-color: #0f3460;
    color: #ffffff;
}
th {
    padding: 5px 6px;
    text-align: left;
    font-weight: bold;
    font-size: 8px;
    border: 1px solid #0f3460;
    white-space: nowrap;
    overflow: hidden;
}
td {
    padding: 4px 6px;
    font-size: 9px;
    border: 1px solid #cccccc;
    white-space: nowrap;
    overflow: hidden;
}
tbody tr:nth-child(even) { background-color: #f4f6fb; }
tbody tr:nth-child(odd)  { background-color: #ffffff; }

hr {
    border: none;
    border-top: 1.5px solid #e94560;
    margin: 14px 0;
}
blockquote {
    border-left: 3px solid #e94560;
    margin: 6px 0;
    padding: 5px 10px;
    background-color: #fef5f7;
    color: #333333;
    font-size: 9px;
}
"""


def _strip_emojis(text: str) -> str:
    """Remove emoji characters that xhtml2pdf can't render."""
    emoji_pattern = re.compile(
        "[\U0001f300-\U0001f9ff"
        "\U00002702-\U000027b0"
        "\U0000fe00-\U0000fe0f"
        "\U0000200d"
        "\U000020e3"
        "\U00002600-\U000026ff"
        "\U00002300-\U000023ff"
        "\U0000200b-\U0000200f"
        "\U0000205a-\U0000205f"
        "\U0000feff]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


"""
Table width profiles keyed by a frozenset of lowercase header texts.
Each profile maps column index -> percentage width.
"""
_TABLE_PROFILES: dict[frozenset, list[int]] = {
    # Portfolio Allocation: Ticker | Sector | Score | Weight
    frozenset({"ticker", "sector", "score", "weight"}):
        [25, 30, 20, 25],
    # Top 10 Rankings: # | Ticker | Sector | Score | Conv | Flow | EarnRev
    frozenset({"#", "ticker", "sector", "score", "conv", "flow", "earnrev"}):
        [5, 18, 16, 12, 14, 12, 13],
    # Factor Breakdown: Ticker | Val | Qual | Mom | Tech | Vol | SectGr | Flow | Earn
    frozenset({"ticker", "val", "qual", "mom", "tech", "vol", "sectgr", "flow", "earn"}):
        [16, 9, 10, 10, 10, 9, 12, 12, 12],
    # Entry Timing: Ticker | Entry Score | Status | Pullback | Volume | VolComp | RSI
    frozenset({"ticker", "entry score", "status", "pullback", "volume", "volcomp", "rsi"}):
        [14, 13, 25, 12, 12, 12, 12],
    # Stock Profile: Metric | Value | Metric | Value
    frozenset({"metric", "value"}):
        [22, 28, 22, 28],
    # Decay Active: Ticker | Days | P&L | Strength | Factor | Half-Life
    frozenset({"ticker", "days", "p&l", "strength", "factor", "half-life"}):
        [16, 10, 12, 14, 22, 14],
    # Decay Exit: Ticker | Days | P&L | Signal | Reason
    frozenset({"ticker", "days", "p&l", "signal", "reason"}):
        [16, 12, 12, 14, 36],
    # Exit Statistics / Performance: Metric | Value
    frozenset({"metric", "value"}):
        [22, 28, 22, 28],
    # Methodology: Factor | Description | Week | Year | 5-Year
    frozenset({"factor", "description", "week", "year", "5-year"}):
        [14, 42, 12, 12, 12],
}


def _get_header_texts(table_html: str) -> list[str]:
    """Extract header cell text content from the first row."""
    first_row = re.search(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL)
    if not first_row:
        return []
    cells = re.findall(r"<th[^>]*>(.*?)</th>", first_row.group(1), re.DOTALL)
    return [re.sub(r"<[^>]+>", "", c).strip() for c in cells]


def _find_profile(headers: list[str]) -> list[int] | None:
    """Match headers to a known table profile."""
    header_set = frozenset(h.lower() for h in headers)
    # Direct match
    if header_set in _TABLE_PROFILES:
        return _TABLE_PROFILES[header_set]
    # Subset match (e.g., 4-col Metric|Value matches the 2-col key)
    for key, widths in _TABLE_PROFILES.items():
        if key <= header_set and len(widths) == len(headers):
            return widths
    return None


def _inject_colgroups(html: str) -> str:
    """
    Post-process HTML to inject explicit column widths into every <table>.
    Uses known table profiles for smart widths; falls back to equal widths.
    Sets widths via inline style on <th>/<td> for maximum xhtml2pdf compat.
    """
    def _apply_widths_to_row(row_html: str, widths: list[int], tag: str) -> str:
        cells = list(re.finditer(rf"<{tag}([^>]*)>(.*?)</{tag}>", row_html, re.DOTALL))
        if len(cells) != len(widths):
            return row_html
        result = row_html
        for cell_match, w in zip(reversed(cells), reversed(widths)):
            attrs = cell_match.group(1)
            content = cell_match.group(2)
            new_cell = f'<{tag} style="width:{w}%"{attrs}>{content}</{tag}>'
            result = result[:cell_match.start()] + new_cell + result[cell_match.end():]
        return result

    def _replace_table(match):
        table_html = match.group(0)
        headers = _get_header_texts(table_html)
        if not headers:
            return table_html

        col_count = len(headers)
        profile = _find_profile(headers)
        if profile and len(profile) == col_count:
            widths = profile
        else:
            widths = [round(100.0 / col_count)] * col_count

        # Apply widths to all rows
        def _fix_row(m):
            row = m.group(0)
            if "<th" in row:
                return _apply_widths_to_row(row, widths, "th")
            return _apply_widths_to_row(row, widths, "td")

        table_html = re.sub(r"<tr[^>]*>.*?</tr>", _fix_row, table_html, flags=re.DOTALL)
        return table_html

    return re.sub(r"<table[^>]*>.*?</table>", _replace_table, html, flags=re.DOTALL)


def _build_html(body_html: str, title: str, generated_at: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <style>{CSS}</style>
</head>
<body>
    <div id="page-header">{title}</div>
    <div id="page-footer">Generated {generated_at} &bull; For personal use only &bull; Not financial advice</div>

    {body_html}
</body>
</html>"""


def md_to_pdf(
    md_path: str | None = None,
    md_text: str | None = None,
    output_path: str | None = None,
) -> str:
    """Convert a Markdown file (or raw text) to a styled PDF.

    Returns the output PDF path.
    """
    if md_path:
        with open(md_path, encoding="utf-8") as f:
            raw = f.read()
    elif md_text:
        raw = md_text
    else:
        raise ValueError("Provide either md_path or md_text")

    raw = _strip_emojis(raw)

    body_html = markdown.markdown(
        raw,
        extensions=["tables", "fenced_code", "nl2br", "sane_lists"],
    )

    # Inject explicit column widths so xhtml2pdf won't merge columns
    body_html = _inject_colgroups(body_html)

    title_match = re.search(r"^#\s+(.+)", raw, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Financial Report"
    title = _strip_emojis(title)

    generated_at = datetime.now().strftime("%d %b %Y, %I:%M %p")
    full_html = _build_html(body_html, title, generated_at)

    if output_path is None:
        if md_path:
            output_path = str(Path(md_path).with_suffix(".pdf"))
        else:
            output_path = f"report_{datetime.now():%Y%m%d_%H%M%S}.pdf"

    with open(output_path, "wb") as out:
        status = pisa.CreatePDF(full_html, dest=out, encoding="utf-8")

    if status.err:
        raise RuntimeError(f"PDF generation failed with {status.err} errors")

    return output_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: py report_to_pdf.py <input.md> [output.pdf]")
        sys.exit(1)

    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    result = md_to_pdf(md_path=src, output_path=dst)
    print(f"PDF saved: {result}")
