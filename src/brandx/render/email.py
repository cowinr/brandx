"""Email renderer — emit Outlook-safe email HTML from a ParsedDocument + ResolvedConfig.

Responsibilities:
    - Emit 100% inline styles with a table-based layout and no <style> block.
    - Compose the letterhead (monogram or embedded avatar, name, role) with a
      teal bottom-border row. No date line and no footer (differs from document).
    - Transform the structural body HTML from the pipeline:
        - bx:alert markers → two-cell bar+content tables (Outlook-safe callouts).
        - bx:blockquote markers → two-cell accent-bar+grey tables.
        - <h2>, <h3>, <h4> → inline-styled headings.
        - <table> → inline-styled data table with Python-computed zebra striping.
        - <p>, <ul>, <ol>, <li>, <a>, <code> → inline styles on every element.
    - Strip syntax-highlighting spans from code blocks (email path = plain monospace).
    - Wrap code blocks in a single-cell table.
    - Embed local body images as base64 via assets.py.
    - Warn to stderr when total email size nears the Gmail clip threshold (80 KB).
    - Warn to stderr when the embedded avatar image is heavy (> 100 KB encoded).

Reuses:
    - brandx.render.assets.file_to_data_uri, embed_images
    - brandx.render.document._resolve_doc_date (date helpers, imported by name)

The renderer reads only the resolved config and hardcodes no person-specific value
(R8 / KTD4). No module-global brand state; cfg is threaded through (KTD3).

Date helpers from document.py are re-exported here so callers can access them
without importing from document.py.

Usage:
    from brandx.render.email import render_email
    from brandx.render.pipeline import parse_document
    from brandx.config.resolver import resolve

    cfg = resolve(home_config={...})
    doc = parse_document(Path("report.md"))
    html = render_email(doc, cfg)
"""

from __future__ import annotations

import html as _html_lib
import re
import sys
from pathlib import Path

from brandx.config.resolver import ResolvedConfig
from brandx.render.assets import embed_images, file_to_data_uri
from brandx.render.document import _resolve_doc_date  # reuse, not reimplementing
from brandx.render.pipeline import ParsedDocument, parse_document


# ---------------------------------------------------------------------------
# Gmail clip threshold constants
# ---------------------------------------------------------------------------

# Warn when total email HTML exceeds this UTF-8 byte size.
_GMAIL_CLIP_WARN_BYTES = 80 * 1024  # 80 KB

# Warn when a single embedded (base64) avatar string exceeds this threshold.
# Base64 is ~133% of raw bytes, so 100 KB encoded ≈ 75 KB raw image file.
_AVATAR_HEAVY_WARN_BYTES = 100 * 1024  # 100 KB


# ---------------------------------------------------------------------------
# Alert colour mapping
# ---------------------------------------------------------------------------

# Each alert type maps to (bar_colour, background_colour, label_colour).
# note/important use email-specific palette keys; rag types use the shared values.
# These are resolved at render time from cfg.colours.
def _alert_colours(alert_type: str, colours: dict) -> tuple[str, str, str]:
    """Return (bar_colour, bg_colour, label_colour) for an alert type."""
    if alert_type == "note":
        return colours.get("blue", "#1c2b39"), colours.get("note_bg_email", "#e6f4f2"), colours.get("blue", "#1c2b39")
    if alert_type == "tip":
        return colours.get("rag_green_text", "#2a7f4f"), colours.get("rag_green_bg", "#e8f5ed"), colours.get("rag_green_text", "#2a7f4f")
    if alert_type == "important":
        return colours.get("important", "#b07514"), colours.get("important_bg_email", "#fdf3e3"), colours.get("important", "#b07514")
    if alert_type == "warning":
        return colours.get("rag_amber_text", "#b07514"), colours.get("rag_amber_bg", "#fdf3e3"), colours.get("rag_amber_text", "#b07514")
    if alert_type == "caution":
        return colours.get("rag_red_text", "#b33a3a"), colours.get("rag_red_bg", "#fce8e8"), colours.get("rag_red_text", "#b33a3a")
    # Unknown type: default to note styling
    return colours.get("blue", "#1c2b39"), colours.get("note_bg_email", "#e6f4f2"), colours.get("blue", "#1c2b39")


_ALERT_LABELS = {
    "note": "Note",
    "tip": "Tip",
    "important": "Important",
    "warning": "Warning",
    "caution": "Caution",
}


# ---------------------------------------------------------------------------
# Syntax-highlighting strip
# ---------------------------------------------------------------------------

def _strip_codehilite(html: str) -> str:
    """Strip pygments highlighting from code blocks, leaving plain text.

    The shared pipeline emits:
        <div class="codehilite" ...><pre ...>...<span style="...">text</span>...</pre></div>

    Plain fenced code (no language) produces:
        <pre><code>text</code></pre>

    This function:
        1. Removes the outer codehilite <div> wrapper.
        2. Inside every <pre>...</pre> block:
           a. Strips <span ...> wrappers, keeping their text content.
           b. Strips <code ...> / </code> wrapper tags, keeping their text content.
              (The <code> sits inside <pre> for fenced blocks; stripping it here
               prevents _style_inline_code from applying the pill style inside a
               code block. Genuine inline <code> outside <pre> is unaffected.)
           c. Strips the inline style attribute from the <pre> tag itself.

    The result is a plain <pre> containing only text nodes.
    """
    # Step 1: unwrap the codehilite div, keeping only the inner <pre>...</pre>.
    html = re.sub(
        r'<div class="codehilite"[^>]*>(.*?)</div>',
        lambda m: m.group(1).strip(),
        html,
        flags=re.DOTALL,
    )

    # Step 2: clean up the interior of every <pre>...</pre> block.
    def _strip_tags_in_pre(m: re.Match) -> str:
        pre_open = m.group(1)  # the <pre ...> tag
        content = m.group(2)
        # Remove span and code open/close tags; keep their text content.
        plain = re.sub(r'<span[^>]*>', '', content)
        plain = plain.replace('</span>', '')
        plain = re.sub(r'<code[^>]*>', '', plain)
        plain = plain.replace('</code>', '')
        # Strip inline style from the <pre> tag itself (codehilite adds one).
        pre_open = re.sub(r'\s*style="[^"]*"', '', pre_open)
        return pre_open + plain + "</pre>"

    html = re.sub(
        r'(<pre[^>]*>)(.*?)(</pre>)',
        _strip_tags_in_pre,
        html,
        flags=re.DOTALL,
    )

    return html


# ---------------------------------------------------------------------------
# Body transformations
# ---------------------------------------------------------------------------

def _font_style(family: str) -> str:
    """Return the font-family CSS fragment for inline styles."""
    return f"font-family:{family};"


def _build_alert_table(alert_type: str, body_html: str, cfg: ResolvedConfig) -> str:
    """Render a bx:alert as a two-cell Outlook-safe table."""
    colours = dict(cfg.colours)
    bar_colour, bg_colour, label_colour = _alert_colours(alert_type, colours)
    label = _ALERT_LABELS.get(alert_type, alert_type.capitalize())
    family = cfg.fonts.get("family_email", "'Inter','Segoe UI',Arial,Helvetica,sans-serif")
    grey_700 = colours.get("grey_700", "#46535f")

    return (
        f'<table role="presentation" border="0" cellpadding="0" cellspacing="0"'
        f' style="width:100%;border-collapse:collapse;margin:12px 0;">'
        f'<tr>'
        f'<td width="4" bgcolor="{bar_colour}"'
        f' style="width:4px;background:{bar_colour};font-size:0;line-height:0;padding:0;margin:0;">&nbsp;</td>'
        f'<td style="background:{bg_colour};padding:12px 14px;vertical-align:top;">'
        f'<p style="{_font_style(family)}font-size:11px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.8px;color:{label_colour};margin:0 0 6px 0;">{label}</p>'
        f'<div style="{_font_style(family)}font-size:14px;line-height:1.5;color:{grey_700};margin:0;">'
        f'{body_html}'
        f'</div>'
        f'</td>'
        f'</tr>'
        f'</table>'
    )


def _build_blockquote_table(inner_html: str, cfg: ResolvedConfig) -> str:
    """Render a bx:blockquote as a two-cell accent-bar table."""
    colours = dict(cfg.colours)
    accent = colours.get("accent", "#0d8a7d")
    grey_50 = colours.get("grey_50", "#f4f7f8")
    grey_700 = colours.get("grey_700", "#46535f")
    family = cfg.fonts.get("family_email", "'Inter','Segoe UI',Arial,Helvetica,sans-serif")

    return (
        f'<table role="presentation" border="0" cellpadding="0" cellspacing="0"'
        f' style="width:100%;border-collapse:collapse;margin:12px 0;">'
        f'<tr>'
        f'<td width="4" bgcolor="{accent}"'
        f' style="width:4px;background:{accent};font-size:0;line-height:0;padding:0;margin:0;">&nbsp;</td>'
        f'<td style="background:{grey_50};padding:12px 14px;vertical-align:top;">'
        f'<div style="{_font_style(family)}font-size:14px;line-height:1.5;color:{grey_700};margin:0;">'
        f'{inner_html.strip()}'
        f'</div>'
        f'</td>'
        f'</tr>'
        f'</table>'
    )


def _build_code_table(pre_html: str, cfg: ResolvedConfig) -> str:
    """Wrap a plain <pre> in a single-cell Outlook-safe table."""
    colours = dict(cfg.colours)
    grey_50 = colours.get("grey_50", "#f4f7f8")
    grey_200 = colours.get("grey_200", "#e2e8ec")
    grey_900 = colours.get("grey_900", "#1f2933")
    mono = "'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"

    # Replace the <pre ...> open tag with our inline-styled version.
    pre_styled = re.sub(
        r'<pre[^>]*>',
        (
            f'<pre style="font-family:{mono};font-size:13px;line-height:1.5;'
            f'margin:0;padding:0;white-space:pre-wrap;word-wrap:break-word;'
            f'color:{grey_900};background:transparent;">'
        ),
        pre_html,
        count=1,
    )

    return (
        f'<table role="presentation" border="0" cellpadding="0" cellspacing="0"'
        f' style="width:100%;border-collapse:collapse;margin:12px 0;">'
        f'<tr>'
        f'<td style="background:{grey_50};border:1px solid {grey_200};padding:14px 16px;">'
        f'{pre_styled}'
        f'</td>'
        f'</tr>'
        f'</table>'
    )


def _replace_bx_alerts(html: str, cfg: ResolvedConfig) -> str:
    """Replace bx:alert markers with two-cell Outlook-safe tables."""

    def replace_alert(m: re.Match) -> str:
        alert_type = m.group(1)
        body_html = m.group(2)
        return _build_alert_table(alert_type, body_html, cfg)

    return re.sub(
        r'<!-- bx:alert type="([^"]+)" -->(.*?)<!-- /bx:alert -->',
        replace_alert,
        html,
        flags=re.DOTALL,
    )


def _replace_bx_blockquotes(html: str, cfg: ResolvedConfig) -> str:
    """Replace bx:blockquote markers with accent-bar tables."""

    def replace_blockquote(m: re.Match) -> str:
        inner = m.group(1).strip()
        return _build_blockquote_table(inner, cfg)

    return re.sub(
        r"<!-- bx:blockquote -->(.*?)<!-- /bx:blockquote -->",
        replace_blockquote,
        html,
        flags=re.DOTALL,
    )


def _wrap_code_blocks(html: str, cfg: ResolvedConfig) -> str:
    """Wrap every plain <pre>...</pre> in a single-cell table."""

    def wrap_pre(m: re.Match) -> str:
        pre_html = m.group(0)
        return _build_code_table(pre_html, cfg)

    return re.sub(
        r'<pre[^>]*>.*?</pre>',
        wrap_pre,
        html,
        flags=re.DOTALL,
    )


def _style_headings(html: str, cfg: ResolvedConfig) -> str:
    """Apply inline styles to h2, h3, h4 elements."""
    colours = dict(cfg.colours)
    blue = colours.get("blue", "#1c2b39")
    family = cfg.fonts.get("family_email", "'Inter','Segoe UI',Arial,Helvetica,sans-serif")

    h2_style = (
        f"font-family:{family};font-weight:700;"
        f"color:{blue};margin:0 0 12px 0;line-height:1.3;font-size:20px;"
    )
    h3_style = (
        f"font-family:{family};font-weight:700;"
        f"color:{blue};margin:20px 0 10px;line-height:1.3;font-size:17px;"
    )
    h4_style = (
        f"font-family:{family};font-weight:600;"
        f"color:{blue};margin:16px 0 8px;line-height:1.3;font-size:14px;"
        f"text-transform:uppercase;letter-spacing:0.5px;"
    )

    html = re.sub(
        r'<h2[^>]*>',
        f'<h2 style="{h2_style}">',
        html,
    )
    html = re.sub(
        r'<h3[^>]*>',
        f'<h3 style="{h3_style}">',
        html,
    )
    html = re.sub(
        r'<h4[^>]*>',
        f'<h4 style="{h4_style}">',
        html,
    )
    return html


def _style_paragraphs(html: str, cfg: ResolvedConfig) -> str:
    """Apply inline styles to <p> elements that don't already carry a style attribute.

    Alert bodies emit <p> tags with explicit styles; we skip those to avoid
    writing a second style= attribute onto the same element.
    """
    colours = dict(cfg.colours)
    grey_900 = colours.get("grey_900", "#1f2933")
    family = cfg.fonts.get("family_email", "'Inter','Segoe UI',Arial,Helvetica,sans-serif")

    p_style = (
        f"font-family:{family};font-size:14px;"
        f"line-height:1.6;color:{grey_900};margin:0 0 12px 0;"
    )

    def _maybe_style(m: re.Match) -> str:
        attrs = m.group(1)
        # Skip elements that already have a style attribute.
        if re.search(r'\bstyle=', attrs):
            return m.group(0)
        return f'<p{attrs} style="{p_style}">'

    return re.sub(r'<p([^>]*)>', _maybe_style, html)


def _style_lists(html: str, cfg: ResolvedConfig) -> str:
    """Apply inline styles to ul, ol, li elements."""
    colours = dict(cfg.colours)
    grey_900 = colours.get("grey_900", "#1f2933")
    family = cfg.fonts.get("family_email", "'Inter','Segoe UI',Arial,Helvetica,sans-serif")

    list_style = f"font-family:{family};font-size:14px;color:{grey_900};margin:0 0 12px 16px;padding:0;"
    li_style = f"font-family:{family};font-size:14px;color:{grey_900};margin:0 0 4px 0;line-height:1.6;"

    html = re.sub(r'<ul([^>]*)>', lambda m: f'<ul{m.group(1)} style="{list_style}">', html)
    html = re.sub(r'<ol([^>]*)>', lambda m: f'<ol{m.group(1)} style="{list_style}">', html)
    html = re.sub(r'<li([^>]*)>', lambda m: f'<li{m.group(1)} style="{li_style}">', html)
    return html


def _style_links(html: str, cfg: ResolvedConfig) -> str:
    """Apply inline styles to <a> elements."""
    colours = dict(cfg.colours)
    blue = colours.get("blue", "#1c2b39")
    return re.sub(
        r'<a([^>]*)>',
        lambda m: f'<a{m.group(1)} style="color:{blue};text-decoration:underline;">',
        html,
    )


def _style_inline_code(html: str, cfg: ResolvedConfig) -> str:
    """Apply inline styles to <code> elements (inline code only, not inside <pre>)."""
    colours = dict(cfg.colours)
    grey_200 = colours.get("grey_200", "#e2e8ec")
    mono = "'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"

    code_style = (
        f"font-family:{mono};font-size:13px;"
        f"background:{grey_200};padding:1px 4px;border-radius:2px;"
    )
    # Only style <code> not preceded immediately by <pre> (i.e. inline code).
    # We do a simple global replacement; <pre> blocks have already been wrapped
    # in the code table so their <code> (if any) will pick up these styles too —
    # but that is acceptable since pre has its own background set on the cell.
    return re.sub(
        r'<code([^>]*)>',
        lambda m: f'<code{m.group(1)} style="{code_style}">',
        html,
    )


def _apply_zebra_striping(html: str, cfg: ResolvedConfig) -> str:
    """Walk data table <tbody> rows and set alternating background on every <td>.

    Only targets tables that do NOT have role="presentation" (those are the
    structural wrapper tables from the letterhead and callouts). Data tables
    come from the user's markdown and will not have role="presentation".

    Odd rows (1, 3, 5…) → white (#ffffff).
    Even rows (2, 4, 6…) → grey-50.

    Email clients ignore CSS :nth-child, so we compute the stripe in Python
    and write it directly onto each <td> as an inline background style.

    Preserves any existing inline style (e.g. color: for RAG cells) by
    appending background rather than clobbering the entire style attribute.
    """
    colours = dict(cfg.colours)
    white = "#ffffff"
    grey_50 = colours.get("grey_50", "#f4f7f8")
    grey_200 = colours.get("grey_200", "#e2e8ec")
    blue = colours.get("blue", "#1c2b39")
    family = cfg.fonts.get("family_email", "'Inter','Segoe UI',Arial,Helvetica,sans-serif")

    def _style_table(table_m: re.Match) -> str:
        table_html = table_m.group(0)
        open_tag = table_m.group(1)  # attributes inside <table ...>

        # Only process non-presentation tables (data tables from user markdown).
        if 'role="presentation"' in open_tag:
            return table_html

        # Rewrite the <table> open tag.
        table_html = re.sub(
            r'<table[^>]*>',
            (
                f'<table border="0" cellpadding="0" cellspacing="0"'
                f' style="width:100%;border-collapse:collapse;margin:12px 0;">'
            ),
            table_html,
            count=1,
        )

        # Style <th> cells (use \b to avoid matching <thead>).
        th_style = (
            f"background:{blue};color:#ffffff;font-family:{family};"
            f"font-size:12px;font-weight:700;text-transform:uppercase;"
            f"letter-spacing:0.5px;padding:10px 12px;text-align:left;"
            f"border-bottom:2px solid {blue};"
        )
        table_html = re.sub(
            r'<th\b([^>]*)>',
            f'<th style="{th_style}">',
            table_html,
        )

        # Zebra-stripe <tbody> rows.
        def _stripe_tbody(tbody_m: re.Match) -> str:
            tbody_content = tbody_m.group(0)
            row_index = 0

            def _stripe_row(row_m: re.Match) -> str:
                nonlocal row_index
                row_index += 1
                bg = white if row_index % 2 == 1 else grey_50
                row_html = row_m.group(0)

                def _style_td(td_m: re.Match) -> str:
                    existing_style = _extract_existing_style(td_m.group(1))
                    base_td_style = (
                        f"font-family:{family};font-size:13px;"
                        f"padding:8px 12px;vertical-align:top;"
                        f"border-bottom:1px solid {grey_200};"
                        f"background:{bg};"
                    )
                    # Append any existing style properties (e.g. color for RAG cells).
                    combined = base_td_style
                    if existing_style:
                        combined = combined + existing_style
                    return f'<td style="{combined}">'

                return re.sub(r'<td([^>]*)>', _style_td, row_html)

            return re.sub(r'<tr[^>]*>.*?</tr>', _stripe_row, tbody_content, flags=re.DOTALL)

        table_html = re.sub(r'<tbody>.*?</tbody>', _stripe_tbody, table_html, flags=re.DOTALL)
        return table_html

    # Capture the opening tag attributes so we can check for role="presentation".
    return re.sub(r'<table([^>]*)>.*?</table>', _style_table, html, flags=re.DOTALL)


def _extract_existing_style(attrs: str) -> str:
    """Extract the value of a style="..." attribute from an element's attributes string."""
    m = re.search(r'style="([^"]*)"', attrs)
    if m:
        val = m.group(1).strip()
        # Ensure it ends with a semicolon for clean concatenation.
        if val and not val.endswith(";"):
            val += ";"
        return val
    return ""


def _transform_body(body_html: str, cfg: ResolvedConfig, source_dir: Path) -> str:
    """Apply all email-surface body transformations."""
    # Strip codehilite highlighting before anything else.
    body_html = _strip_codehilite(body_html)
    # Replace bx: markers.
    body_html = _replace_bx_alerts(body_html, cfg)
    body_html = _replace_bx_blockquotes(body_html, cfg)
    # Wrap code blocks before heading/paragraph styling touches the pre content.
    body_html = _wrap_code_blocks(body_html, cfg)
    # Style text elements.
    body_html = _style_headings(body_html, cfg)
    body_html = _style_paragraphs(body_html, cfg)
    body_html = _style_lists(body_html, cfg)
    body_html = _style_links(body_html, cfg)
    body_html = _style_inline_code(body_html, cfg)
    # Zebra-stripe tables (must run after heading/para styling, before embed).
    body_html = _apply_zebra_striping(body_html, cfg)
    # Embed local images as base64.
    body_html = embed_images(body_html, source_dir)
    return body_html


# ---------------------------------------------------------------------------
# Letterhead
# ---------------------------------------------------------------------------

def _build_email_mark(cfg: ResolvedConfig) -> str:
    """Render the email letterhead mark: monogram div or embedded avatar img."""
    colours = dict(cfg.colours)
    blue = colours.get("blue", "#1c2b39")
    family = cfg.fonts.get("family_email", "'Inter','Segoe UI',Arial,Helvetica,sans-serif")

    if cfg.mark == "avatar" and cfg.avatar_email is not None:
        data_uri = file_to_data_uri(cfg.avatar_email)
        if data_uri is not None:
            # Warn if the avatar is heavy.
            encoded_bytes = len(data_uri.encode("ascii"))
            if encoded_bytes > _AVATAR_HEAVY_WARN_BYTES:
                print(
                    f"brandx warning: embedded avatar is large "
                    f"({encoded_bytes // 1024} KB encoded); "
                    f"consider a smaller image to stay under Gmail's 102 KB clip limit.",
                    file=sys.stderr,
                )
            return (
                f'<img src="{data_uri}" alt="{_html_lib.escape(cfg.name)}"'
                f' style="width:40px;height:40px;border-radius:9px;object-fit:cover;display:block;">'
            )
        print(
            f"brandx warning: email avatar could not be embedded, falling back to monogram: {cfg.avatar_email}",
            file=sys.stderr,
        )

    # Monogram box (default).
    return (
        f'<div style="width:40px;height:40px;border-radius:9px;background:{blue};color:#ffffff;'
        f'font-family:{family};font-weight:800;'
        f'font-size:15px;text-align:center;line-height:40px;">'
        f'{_html_lib.escape(cfg.initials)}'
        f'</div>'
    )


def _build_email_letterhead(cfg: ResolvedConfig) -> str:
    """Render the email letterhead block.

    Differs from the document letterhead: no date, no footer, teal bottom border.
    """
    colours = dict(cfg.colours)
    blue = colours.get("blue", "#1c2b39")
    blue_light = colours.get("blue_light", "#0d8a7d")
    family = cfg.fonts.get("family_email", "'Inter','Segoe UI',Arial,Helvetica,sans-serif")

    mark = _build_email_mark(cfg)

    role_cell = ""
    if cfg.role:
        role_cell = (
            f'<div style="font-family:{family};font-weight:600;'
            f'font-size:12px;color:{blue_light};">'
            f'{_html_lib.escape(cfg.role)}'
            f'</div>'
        )

    return (
        f'<table role="presentation" border="0" cellpadding="0" cellspacing="0"'
        f' style="border-collapse:collapse;width:100%;margin:0 0 20px;">'
        f'<tr><td style="padding:0 0 12px;border-bottom:2px solid {blue_light};">'
        f'<table role="presentation" border="0" cellpadding="0" cellspacing="0"'
        f' style="border-collapse:collapse;">'
        f'<tr>'
        f'<td style="padding-right:12px;vertical-align:middle;">'
        f'{mark}'
        f'</td>'
        f'<td style="vertical-align:middle;">'
        f'<div style="font-family:{family};font-weight:700;'
        f'font-size:15px;color:{blue};line-height:1.2;">'
        f'{_html_lib.escape(cfg.name)}'
        f'</div>'
        f'{role_cell}'
        f'</td>'
        f'</tr>'
        f'</table>'
        f'</td></tr>'
        f'</table>'
    )


# ---------------------------------------------------------------------------
# Title rendering
# ---------------------------------------------------------------------------

def _build_title_block(doc: ParsedDocument, cfg: ResolvedConfig) -> str:
    """Render the document title and subtitle as inline-styled headings."""
    if not doc.title and not doc.subtitle:
        return ""

    colours = dict(cfg.colours)
    blue = colours.get("blue", "#1c2b39")
    blue_light = colours.get("blue_light", "#0d8a7d")
    family = cfg.fonts.get("family_email", "'Inter','Segoe UI',Arial,Helvetica,sans-serif")

    parts: list[str] = []
    if doc.title:
        parts.append(
            f'<h2 style="font-family:{family};font-weight:800;'
            f'color:{blue};margin:0 0 8px 0;line-height:1.2;font-size:24px;">'
            f'{_html_lib.escape(doc.title)}'
            f'</h2>'
        )
    if doc.subtitle:
        parts.append(
            f'<p style="font-family:{family};font-size:14px;'
            f'color:{blue_light};margin:0 0 20px 0;font-weight:500;">'
            f'{_html_lib.escape(doc.subtitle)}'
            f'</p>'
        )
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Size warning
# ---------------------------------------------------------------------------

def _check_size(html: str) -> None:
    """Warn to stderr if the email HTML approaches the Gmail clip threshold."""
    byte_size = len(html.encode("utf-8"))
    if byte_size >= _GMAIL_CLIP_WARN_BYTES:
        print(
            f"brandx warning: email HTML is {byte_size // 1024} KB "
            f"(threshold {_GMAIL_CLIP_WARN_BYTES // 1024} KB); "
            f"Gmail may clip this message. Consider reducing embedded image sizes.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_email(doc: ParsedDocument, cfg: ResolvedConfig) -> str:
    """Render Outlook-safe email HTML from a ParsedDocument and ResolvedConfig.

    Args:
        doc: ParsedDocument from the shared structural pass.
        cfg: Immutable resolved brand configuration.

    Returns:
        A complete email HTML string (100% inline styles, table-based layout,
        no <style> block).
    """
    colours = dict(cfg.colours)
    grey_900 = colours.get("grey_900", "#1f2933")
    family = cfg.fonts.get("family_email", "'Inter','Segoe UI',Arial,Helvetica,sans-serif")

    letterhead = _build_email_letterhead(cfg)
    title_block = _build_title_block(doc, cfg)
    body = _transform_body(doc.body_html, cfg, doc.source_dir)

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_html_lib.escape(doc.title or cfg.name or "Email")}</title>
</head>
<body>

<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="width:100%;border-collapse:collapse;">
<tr><td align="center" style="padding:0;">

<table role="presentation" border="0" cellpadding="0" cellspacing="0"
  style="max-width:960px;width:100%;border-collapse:collapse;background:#ffffff;">
<tr><td style="padding:20px 24px;font-family:{family};font-size:14px;color:{grey_900};">

{letterhead}
{title_block}
{body}

</td></tr>
</table>

</td></tr>
</table>

</body>
</html>"""

    _check_size(html)
    return html


def render_email_file(source: Path, cfg: ResolvedConfig) -> str:
    """Convenience wrapper: parse a markdown file then render the email.

    Args:
        source: Path to the markdown file.
        cfg: Immutable resolved brand configuration.

    Returns:
        A complete email HTML string.
    """
    doc = parse_document(source)
    return render_email(doc, cfg)
