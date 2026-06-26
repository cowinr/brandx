"""Document renderer — emit a complete branded HTML document from a ParsedDocument + ResolvedConfig.

Responsibilities:
    - Build a <style> block with :root CSS variables sourced from the resolved config.
    - Compose the letterhead (gradient bar, identity mark, name, role, date).
    - Render the document title block (doc-title, doc-subtitle).
    - Transform the structural body HTML from the pipeline:
        - bx:alert markers → .alert .alert-{type} blocks with labelled .alert-title.
        - bx:blockquote markers → styled <blockquote>.
        - <h2> → class="section-title".
        - <table> → class="data-table".
    - Embed local images as base64 data: URIs (via assets.py).
    - Load the web font via a <link> in <head> when font_url is non-empty (KTD7).
    - Include an @media print stylesheet.
    - Render the footer (name + date).
    - Embed the identity mark: monogram box (default) or base64 avatar img.

The renderer reads only the resolved config and hardcodes no person-specific value (R8/KTD4).
No module-global brand state; the config is threaded in (KTD3).

Date rendering supports four named formats plus strftime-pattern passthrough:
    'long-british' → "8 April 2026" (no leading zero)
    'iso'          → "2026-04-08"
    'us'           → "April 8, 2026"
    'eu'           → "08.04.2026"

Usage:
    from brandx.render.document import render_document
    from brandx.render.pipeline import parse_document
    from brandx.config.resolver import resolve

    cfg = resolve(home_config={...})
    doc = parse_document(Path("report.md"))
    html = render_document(doc, cfg)
"""

from __future__ import annotations

import html as _html_lib
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from brandx.config.resolver import ResolvedConfig
from brandx.render.assets import embed_images, file_to_data_uri
from brandx.render.pipeline import ParsedDocument, parse_document


# ---------------------------------------------------------------------------
# Date formatting
# ---------------------------------------------------------------------------

_NAMED_FORMATS = {
    "long-british": None,  # handled separately (no leading zero)
    "iso": "%Y-%m-%d",
    "us": "%B %-d, %Y",
    "eu": "%d.%m.%Y",
}

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _format_date(dt: date, fmt: str) -> str:
    """Render a date in the configured format.

    Named formats: 'long-british', 'iso', 'us', 'eu'.
    Anything else is treated as a strftime pattern and passed through.
    """
    if fmt == "long-british":
        # No leading zero on the day.
        return f"{dt.day} {_MONTHS[dt.month - 1]} {dt.year}"
    if fmt in _NAMED_FORMATS and _NAMED_FORMATS[fmt]:
        # On Windows %-d is not supported; use strftime safely.
        try:
            return dt.strftime(_NAMED_FORMATS[fmt])
        except ValueError:
            # Fallback: manual formatting for 'us' on Windows.
            if fmt == "us":
                return f"{_MONTHS[dt.month - 1]} {dt.day}, {dt.year}"
            raise
    # Treat as a strftime pattern.
    return dt.strftime(fmt)


def _resolve_doc_date(date_raw: str | None, date_format: str) -> str:
    """Parse date_raw (from frontmatter) or fall back to today; format per config."""
    dt: date | None = None
    if date_raw:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%B %d, %Y", "%d %B %Y"):
            try:
                dt = datetime.strptime(date_raw, fmt).date()
                break
            except ValueError:
                continue
        if dt is None:
            # Could not parse; warn and use today.
            print(
                f"brandx warning: could not parse date '{date_raw}', using today.",
                file=sys.stderr,
            )
    if dt is None:
        dt = date.today()
    return _format_date(dt, date_format)


# ---------------------------------------------------------------------------
# CSS variable mapping
# ---------------------------------------------------------------------------

def _colour_var_name(key: str) -> str:
    """Map a snake_case palette key to its CSS variable name.

    Underscores become hyphens, prefixed with --. e.g. text_muted → --text-muted.
    """
    return "--" + key.replace("_", "-")


def _build_root_vars(colours: Any, fonts: Any) -> str:
    """Emit a CSS :root { ... } block from the resolved palette and fonts."""
    lines: list[str] = ["  :root {"]
    lines.append(f"    --font: {fonts['font']};")
    lines.append("    --mono: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;")
    for key, value in colours.items():
        var_name = _colour_var_name(key)
        lines.append(f"    {var_name}: {value};")
    lines.append("    --white: #ffffff;")
    lines.append("  }")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Body transformations
# ---------------------------------------------------------------------------

_ALERT_LABELS = {
    "note": "Note",
    "tip": "Tip",
    "important": "Important",
    "warning": "Warning",
    "caution": "Caution",
}


def _replace_bx_alerts(html: str) -> str:
    """Replace bx:alert markers with .alert .alert-{type} HTML."""

    def replace_alert(m: re.Match) -> str:
        alert_type = m.group(1)
        body_html = m.group(2)
        label = _ALERT_LABELS.get(alert_type, alert_type.capitalize())
        return (
            f'<div class="alert alert-{alert_type}">'
            f'<div class="alert-title">{label}</div>'
            f'<div class="alert-body">{body_html}</div>'
            f"</div>"
        )

    return re.sub(
        r'<!-- bx:alert type="([^"]+)" -->(.*?)<!-- /bx:alert -->',
        replace_alert,
        html,
        flags=re.DOTALL,
    )


def _replace_bx_blockquotes(html: str) -> str:
    """Replace bx:blockquote markers with styled <blockquote>."""

    def replace_blockquote(m: re.Match) -> str:
        inner = m.group(1).strip()
        return f"<blockquote>{inner}</blockquote>"

    return re.sub(
        r"<!-- bx:blockquote -->(.*?)<!-- /bx:blockquote -->",
        replace_blockquote,
        html,
        flags=re.DOTALL,
    )


def _add_section_title_class(html: str) -> str:
    """Add class="section-title" to all <h2> elements."""
    return re.sub(
        r"<h2([^>]*)>",
        lambda m: f'<h2{m.group(1)} class="section-title">',
        html,
    )


def _add_data_table_class(html: str) -> str:
    """Add class="data-table" to all <table> elements."""
    return re.sub(
        r"<table([^>]*)>",
        lambda m: f'<table{m.group(1)} class="data-table">',
        html,
    )


def _unwrap_codehilite(html: str) -> str:
    """Unwrap the codehilite div wrapper, keeping the highlighted <pre> intact.

    codehilite (noclasses=True) wraps its output in:
        <div class="codehilite" style="..."><pre style="...">...<span ...>...</span>...</pre></div>

    The div may carry an inline style attribute. We remove the outer div so our
    CSS can style the <pre> directly, while preserving all pygments inline spans.
    """
    return re.sub(
        r'<div class="codehilite"[^>]*>(.*?)</div>',
        lambda m: m.group(1).strip(),
        html,
        flags=re.DOTALL,
    )


def _transform_body(body_html: str, source_dir: Path) -> str:
    """Apply all document-surface body transformations."""
    body_html = _replace_bx_alerts(body_html)
    body_html = _replace_bx_blockquotes(body_html)
    body_html = _add_section_title_class(body_html)
    body_html = _add_data_table_class(body_html)
    body_html = _unwrap_codehilite(body_html)
    body_html = embed_images(body_html, source_dir)
    return body_html


# ---------------------------------------------------------------------------
# Letterhead
# ---------------------------------------------------------------------------

def _build_mark(cfg: ResolvedConfig) -> str:
    """Render the identity mark: monogram box or embedded avatar img."""
    if cfg.mark == "avatar" and cfg.avatar is not None:
        avatar_path = cfg.avatar
        data_uri = file_to_data_uri(avatar_path)
        if data_uri is not None:
            return (
                f'<img src="{data_uri}" alt="{_html_lib.escape(cfg.name)}" '
                f'style="width:48px;height:48px;border-radius:10px;object-fit:cover;">'
            )
        # Fall back to monogram when avatar cannot be loaded.
        print(
            f"brandx warning: avatar could not be embedded, falling back to monogram: {avatar_path}",
            file=sys.stderr,
        )
    return (
        f'<div class="letterhead-monogram">'
        f'{_html_lib.escape(cfg.initials)}'
        f"</div>"
    )


def _build_letterhead(cfg: ResolvedConfig, date_str: str) -> str:
    """Render the full letterhead block."""
    mark = _build_mark(cfg)
    role_line = ""
    if cfg.role:
        role_line = (
            f'<div class="letterhead-role">{_html_lib.escape(cfg.role)}</div>'
        )
    return f"""\
  <div class="letterhead">
    <div class="letterhead-bar"></div>
    <div class="letterhead-row">
      <div class="letterhead-id">
        {mark}
        <div>
          <div class="letterhead-name">{_html_lib.escape(cfg.name)}</div>
          {role_line}
        </div>
      </div>
      <div class="letterhead-date">{_html_lib.escape(date_str)}</div>
    </div>
  </div>"""


# ---------------------------------------------------------------------------
# CSS stylesheet
# ---------------------------------------------------------------------------

_PRINT_STYLES = """\
  @media print {
    body { background: #ffffff; font-size: 10pt; }
    .page-shell { padding: 0; max-width: none; }
    .letterhead,
    .page { box-shadow: none; border-radius: 0; }
    .letterhead-bar {
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .alert,
    .data-table thead th {
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .alert { page-break-inside: avoid; }
    .data-table { page-break-inside: avoid; }
    pre { page-break-inside: avoid; overflow-x: visible; white-space: pre-wrap; }
    a { border-bottom: none; }
  }"""


def _build_stylesheet(colours: Any, fonts: Any) -> str:
    """Return the complete <style> block for the document surface."""
    root_vars = _build_root_vars(colours, fonts)
    return f"""\
<style>
{root_vars}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    font-family: var(--font);
    color: var(--text);
    background: var(--surface);
    font-size: 10pt;
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
  }}

  /* ── Page shell ── */
  .page-shell {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 28px 24px 64px;
  }}

  /* ── Letterhead ── */
  .letterhead {{
    background: var(--white);
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(28, 43, 57, 0.09);
    margin-bottom: 20px;
  }}
  .letterhead-bar {{
    height: 6px;
    background: linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%);
  }}
  .letterhead-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 18px 24px;
  }}
  .letterhead-id {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}
  .letterhead-monogram {{
    width: 48px; height: 48px;
    border-radius: 10px;
    background: var(--primary);
    color: var(--white);
    font-weight: 800;
    font-size: 17px;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }}
  .letterhead-name {{
    font-size: 16px;
    font-weight: 700;
    color: var(--primary);
    line-height: 1.2;
  }}
  .letterhead-role {{
    font-size: 12px;
    font-weight: 600;
    color: var(--secondary);
    margin-top: 2px;
  }}
  .letterhead-date {{
    font-size: 12px;
    color: var(--text-subtle);
    white-space: nowrap;
    flex-shrink: 0;
  }}

  /* ── Page content ── */
  .page {{
    background: var(--white);
    border-radius: 10px;
    box-shadow: 0 1px 4px rgba(28, 43, 57, 0.09);
    padding: 32px 40px 40px;
  }}

  /* ── Document title ── */
  .doc-title {{
    font-size: 28pt;
    font-weight: 800;
    color: var(--primary);
    line-height: 1.15;
    margin-bottom: 6px;
  }}
  .doc-subtitle {{
    font-size: 13pt;
    font-weight: 500;
    color: var(--secondary);
    margin-bottom: 28px;
  }}

  /* ── Section headings ── */
  .section-title {{
    font-size: 18pt;
    font-weight: 700;
    color: var(--primary);
    margin: 2rem 0 0;
    line-height: 1.25;
  }}
  .section-title::after {{
    content: '';
    display: block;
    width: 40px; height: 2px;
    background: var(--accent);
    margin-top: 7px;
    margin-bottom: 14px;
  }}

  h3 {{
    font-size: 12pt;
    font-weight: 700;
    color: var(--primary);
    margin: 1.5rem 0 0.5rem;
  }}
  h4 {{
    font-size: 9.5pt;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 1.2rem 0 0.3rem;
  }}

  /* ── Body text ── */
  p {{ margin-bottom: 0.8em; line-height: 1.6; }}
  ul, ol {{ margin: 0.5em 0 1em 1.5em; line-height: 1.6; }}
  li {{ margin-bottom: 0.3em; }}
  li.task-list-item {{ list-style: none; margin-left: -1.2em; }}
  .task-checkbox {{ font-size: 1.1em; line-height: 1; margin-right: 0.4em; }}
  a {{ color: var(--primary); text-decoration: none; border-bottom: 1px solid var(--secondary); }}

  /* ── Alerts ── */
  .alert {{
    border-left: 3px solid;
    padding: 10px 14px;
    margin: 1rem 0;
    border-radius: 0 4px 4px 0;
    font-size: 9pt;
    line-height: 1.5;
  }}
  .alert-title {{
    font-size: 8pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 5px;
  }}
  .alert-body p {{ margin-bottom: 0.4em; color: var(--text-muted); }}
  .alert-body p:last-child {{ margin-bottom: 0; }}

  .alert-note {{ background: var(--info-bg); border-color: var(--primary); }}
  .alert-note .alert-title {{ color: var(--primary); }}
  .alert-tip {{ background: var(--success-bg); border-color: var(--success-text); }}
  .alert-tip .alert-title {{ color: var(--success-text); }}
  .alert-important {{ background: var(--emphasis-bg); border-color: var(--emphasis); }}
  .alert-important .alert-title {{ color: var(--emphasis); }}
  .alert-warning {{ background: var(--warning-bg); border-color: var(--warning-text); }}
  .alert-warning .alert-title {{ color: var(--warning-text); }}
  .alert-caution {{ background: var(--danger-bg); border-color: var(--danger-text); }}
  .alert-caution .alert-title {{ color: var(--danger-text); }}

  /* ── Blockquote ── */
  blockquote {{
    background: var(--surface);
    border-left: 3px solid var(--accent);
    padding: 10px 14px;
    margin: 1rem 0;
    border-radius: 0 4px 4px 0;
    font-size: 9pt;
    color: var(--text-muted);
  }}

  /* ── Tables ── */
  .data-table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin: 1rem 0 1.5rem;
    font-size: 9pt;
  }}
  .data-table thead th {{
    background: var(--primary);
    color: var(--white);
    font-weight: 700;
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 10px 12px;
    text-align: left;
  }}
  .data-table thead th:first-child {{ border-radius: 3px 0 0 0; }}
  .data-table thead th:last-child {{ border-radius: 0 3px 0 0; }}
  .data-table tbody tr:nth-child(even) {{ background: var(--surface); }}
  .data-table tbody tr:hover {{ background: var(--row-hover); }}
  .data-table tbody td {{
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }}

  /* ── Code ── */
  pre {{
    position: relative;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 14px 16px;
    margin: 1rem 0 1.5rem;
    overflow-x: auto;
    font-family: var(--mono);
    font-size: 9pt;
    line-height: 1.5;
  }}
  code {{
    font-family: var(--mono);
    font-size: 9pt;
  }}
  p code, li code, td code {{
    background: var(--border);
    padding: 1px 4px;
    border-radius: 2px;
    font-size: 8.5pt;
  }}

  /* ── Footer ── */
  .report-footer {{
    margin-top: 2.5rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 8pt;
    color: var(--text-subtle);
  }}

{_PRINT_STYLES}
</style>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_document(doc: ParsedDocument, cfg: ResolvedConfig) -> str:
    """Render a complete branded HTML document string.

    Args:
        doc: ParsedDocument from the shared structural pass.
        cfg: Immutable resolved brand configuration.

    Returns:
        A complete HTML document as a string.
    """
    date_str = _resolve_doc_date(doc.date_raw, cfg.date_format)

    stylesheet = _build_stylesheet(cfg.colours, cfg.fonts)

    # Font link (KTD7): load via Google Fonts when a URL is configured.
    font_link = ""
    font_url = cfg.fonts.get("font_url", "")
    if font_url:
        font_link = f'\n<link href="{font_url}" rel="stylesheet">'

    # Title block.
    title_block = ""
    if doc.title:
        title_block += (
            f'    <div class="doc-title">{_html_lib.escape(doc.title)}</div>\n'
        )
    if doc.subtitle:
        title_block += (
            f'    <div class="doc-subtitle">{_html_lib.escape(doc.subtitle)}</div>\n'
        )

    # Body transformations.
    body = _transform_body(doc.body_html, doc.source_dir)

    letterhead = _build_letterhead(cfg, date_str)

    page_title = doc.title or cfg.name or "Document"

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_html_lib.escape(page_title)}</title>{font_link}
{stylesheet}
</head>
<body>

<div class="page-shell">

{letterhead}

  <!-- Page content -->
  <div class="page">

{title_block}
{body}

    <div class="report-footer">
      <span>{_html_lib.escape(cfg.name)}</span>
      <span>{_html_lib.escape(date_str)}</span>
    </div>

  </div><!-- .page -->
</div><!-- .page-shell -->

</body>
</html>"""


def render_document_file(source: Path, cfg: ResolvedConfig) -> str:
    """Convenience wrapper: parse a markdown file then render the document.

    Args:
        source: Path to the markdown file.
        cfg: Immutable resolved brand configuration.

    Returns:
        A complete HTML document as a string.
    """
    doc = parse_document(source)
    return render_document(doc, cfg)
