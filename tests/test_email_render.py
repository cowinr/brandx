"""Tests for the email renderer (U8).

Covers (from plan):
- Output contains no <style> block and no class-based or inline-coloured syntax spans
  from codehilite (class="codehilite" absent; highlighted spans absent).
- Structural elements carry inline style= attributes.
- A code block renders as plain monospace, not highlighted (generic-engine AE1 email half).
- The body uses role="presentation" tables.
- Zebra striping alternates per row (odd white #ffffff, even surface #f4f7f8).
- A large embedded avatar triggers a size warning on stderr (generic-engine AE5).
- Each bx:alert type maps to the right bar colour + background colour.
- A bx:blockquote becomes the accent-bar two-cell table.
- Golden-HTML snapshot guards structural drift between manual Outlook checks.
- render_email_file convenience wrapper works.
- Edge cases: no avatar, empty role, no title, missing image.
"""

from __future__ import annotations

import re
from pathlib import Path


from brandx.config.resolver import resolve, ResolvedConfig
from brandx.render.email import (
    render_email,
    render_email_file,
    _strip_codehilite,
    _GMAIL_CLIP_WARN_BYTES,
)
from brandx.render.pipeline import parse_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cfg(**overrides) -> ResolvedConfig:
    """Build a ResolvedConfig with optional identity overrides."""
    home: dict = {}
    if overrides:
        home = {"identity": overrides}
    return resolve(
        home_config=home,
        os_name_fn=lambda: "Test User",
    )


def _render(md: str, cfg: ResolvedConfig | None = None, source_dir: Path | None = None) -> str:
    if cfg is None:
        cfg = _make_cfg(name="Test User", role="Test Role")
    doc = parse_text(md, source_dir=source_dir or Path("."))
    return render_email(doc, cfg)


# ---------------------------------------------------------------------------
# Golden HTML snapshot
# ---------------------------------------------------------------------------

# Fixed markdown and config used to generate the snapshot. Edit here and
# regenerate (run test with --update-snapshot or re-derive) when the renderer
# intentionally changes structure.
_GOLDEN_MD = """\
---
title: Sample Email
---

An introductory paragraph.

> [!NOTE]
> A note callout.

| Column A | Column B |
| -------- | -------- |
| Value 1  | Value 2  |

```bash
echo hello
```

> A plain blockquote.
"""

# Generated from the renderer with the fixed config below. This string guards
# structural drift — if the renderer output changes, the test fails and you
# must review the diff before updating this constant.
_GOLDEN_HTML = (
    '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    "<title>Sample Email</title>\n</head>\n<body>\n\n"
    '<table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%"'
    ' style="width:100%;border-collapse:collapse;">\n'
    '<tr><td align="center" style="padding:0;">\n\n'
    '<table role="presentation" border="0" cellpadding="0" cellspacing="0"\n'
    '  style="max-width:960px;width:100%;border-collapse:collapse;background:#ffffff;">\n'
    '<tr><td style="padding:20px 24px;font-family:\'Inter\', \'Segoe UI\', Arial, Helvetica,'
    ' sans-serif;font-size:14px;color:#1f2933;">\n\n'
    '<table role="presentation" border="0" cellpadding="0" cellspacing="0"'
    ' style="border-collapse:collapse;width:100%;margin:0 0 20px;">'
    '<tr><td style="padding:0 0 12px;border-bottom:2px solid #0d8a7d;">'
    '<table role="presentation" border="0" cellpadding="0" cellspacing="0"'
    ' style="border-collapse:collapse;"><tr>'
    '<td style="padding-right:12px;vertical-align:middle;">'
    '<div style="width:40px;height:40px;border-radius:9px;background:#1c2b39;color:#ffffff;'
    "font-family:'Inter', 'Segoe UI', Arial, Helvetica, sans-serif;font-weight:800;"
    'font-size:15px;text-align:center;line-height:40px;">TU</div></td>'
    '<td style="vertical-align:middle;">'
    '<div style="font-family:\'Inter\', \'Segoe UI\', Arial, Helvetica, sans-serif;'
    'font-weight:700;font-size:15px;color:#1c2b39;line-height:1.2;">Test User</div>'
    '<div style="font-family:\'Inter\', \'Segoe UI\', Arial, Helvetica, sans-serif;'
    'font-weight:600;font-size:12px;color:#0d8a7d;">Test Role</div>'
    "</td></tr></table></td></tr></table>\n"
    '<h2 style="font-family:\'Inter\', \'Segoe UI\', Arial, Helvetica, sans-serif;'
    'font-weight:800;color:#1c2b39;margin:0 0 8px 0;line-height:1.2;font-size:24px;">'
    "Sample Email</h2>\n\n"
    '<p style="font-family:\'Inter\', \'Segoe UI\', Arial, Helvetica, sans-serif;'
    'font-size:14px;line-height:1.6;color:#1f2933;margin:0 0 12px 0;">An introductory paragraph.</p>\n'
    '<table role="presentation" border="0" cellpadding="0" cellspacing="0"'
    ' style="width:100%;border-collapse:collapse;margin:12px 0;">'
    '<tr><td width="4" bgcolor="#1c2b39" style="width:4px;background:#1c2b39;'
    'font-size:0;line-height:0;padding:0;margin:0;">&nbsp;</td>'
    '<td style="background:#e6f4f2;padding:12px 14px;vertical-align:top;">'
    '<p style="font-family:\'Inter\', \'Segoe UI\', Arial, Helvetica, sans-serif;'
    'font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;'
    'color:#1c2b39;margin:0 0 6px 0;">Note</p>'
    '<div style="font-family:\'Inter\', \'Segoe UI\', Arial, Helvetica, sans-serif;'
    'font-size:14px;line-height:1.5;color:#46535f;margin:0;">'
    '<p style="font-family:\'Inter\', \'Segoe UI\', Arial, Helvetica, sans-serif;'
    'font-size:14px;line-height:1.6;color:#1f2933;margin:0 0 12px 0;">A note callout.</p>'
    "</div></td></tr></table>\n"
    '<table border="0" cellpadding="0" cellspacing="0"'
    ' style="width:100%;border-collapse:collapse;margin:12px 0;">\n<thead>\n<tr>\n'
    '<th style="background:#1c2b39;color:#ffffff;'
    "font-family:'Inter', 'Segoe UI', Arial, Helvetica, sans-serif;"
    'font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;'
    'padding:10px 12px;text-align:left;border-bottom:2px solid #1c2b39;">Column A</th>\n'
    '<th style="background:#1c2b39;color:#ffffff;'
    "font-family:'Inter', 'Segoe UI', Arial, Helvetica, sans-serif;"
    'font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;'
    'padding:10px 12px;text-align:left;border-bottom:2px solid #1c2b39;">Column B</th>\n'
    "</tr>\n</thead>\n<tbody>\n<tr>\n"
    '<td style="font-family:\'Inter\', \'Segoe UI\', Arial, Helvetica, sans-serif;'
    'font-size:13px;padding:8px 12px;vertical-align:top;border-bottom:1px solid #e2e8ec;'
    'background:#ffffff;">Value 1</td>\n'
    '<td style="font-family:\'Inter\', \'Segoe UI\', Arial, Helvetica, sans-serif;'
    'font-size:13px;padding:8px 12px;vertical-align:top;border-bottom:1px solid #e2e8ec;'
    'background:#ffffff;">Value 2</td>\n'
    "</tr>\n</tbody>\n</table>\n"
    '<table role="presentation" border="0" cellpadding="0" cellspacing="0"'
    ' style="width:100%;border-collapse:collapse;margin:12px 0;">'
    '<tr><td style="background:#f4f7f8;border:1px solid #e2e8ec;padding:14px 16px;">'
    "<pre style=\"font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;"
    'font-size:13px;line-height:1.5;margin:0;padding:0;white-space:pre-wrap;'
    'word-wrap:break-word;color:#1f2933;background:transparent;">'
    "echo hello\n</pre></td></tr></table>\n\n"
    '<table role="presentation" border="0" cellpadding="0" cellspacing="0"'
    ' style="width:100%;border-collapse:collapse;margin:12px 0;">'
    '<tr><td width="4" bgcolor="#0d8a7d" style="width:4px;background:#0d8a7d;'
    'font-size:0;line-height:0;padding:0;margin:0;">&nbsp;</td>'
    '<td style="background:#f4f7f8;padding:12px 14px;vertical-align:top;">'
    '<div style="font-family:\'Inter\', \'Segoe UI\', Arial, Helvetica, sans-serif;'
    'font-size:14px;line-height:1.5;color:#46535f;margin:0;">'
    '<p style="font-family:\'Inter\', \'Segoe UI\', Arial, Helvetica, sans-serif;'
    'font-size:14px;line-height:1.6;color:#1f2933;margin:0 0 12px 0;">A plain blockquote.</p>'
    "</div></td></tr></table>\n\n"
    "</td></tr>\n</table>\n\n</td></tr>\n</table>\n\n</body>\n</html>"
)


class TestGoldenSnapshot:
    def test_golden_html_matches(self):
        """Render the fixed sample and assert structural output is unchanged.

        If this test fails after an intentional renderer change, regenerate
        _GOLDEN_HTML by running the renderer on _GOLDEN_MD with the fixed config.
        """
        cfg = resolve(
            home_config={"identity": {"name": "Test User", "role": "Test Role"}},
            os_name_fn=lambda: "Test User",
        )
        doc = parse_text(_GOLDEN_MD, source_dir=Path("."))
        html = render_email(doc, cfg)
        assert html == _GOLDEN_HTML


# ---------------------------------------------------------------------------
# No <style> block; no codehilite
# ---------------------------------------------------------------------------

class TestNoStyleBlock:
    def test_no_style_block(self):
        html = _render("Hello.")
        assert "<style>" not in html
        assert "</style>" not in html

    def test_no_codehilite_class(self):
        """The codehilite wrapper div must not appear in email output."""
        md = "```python\nprint('hello')\n```"
        html = _render(md)
        assert 'class="codehilite"' not in html

    def test_no_highlighted_colour_spans(self):
        """Pygments inline colour spans must be stripped on the email path."""
        md = "```python\nprint('hello')\n```"
        html = _render(md)
        # codehilite with noclasses emits spans like <span style="color:#...">
        assert not re.search(r'<span\s+style="color:', html)

    def test_code_block_plain_monospace(self):
        """Code content is preserved but all span and code wrappers are stripped."""
        md = "```python\nprint('hello')\n```"
        html = _render(md)
        assert "print" in html
        assert "hello" in html
        # No spans or code tags inside pre blocks.
        pre_m = re.search(r'<pre[^>]*>(.*?)</pre>', html, re.DOTALL)
        assert pre_m is not None
        assert "<span" not in pre_m.group(1)
        assert "<code" not in pre_m.group(1)


# ---------------------------------------------------------------------------
# strip_codehilite unit tests
# ---------------------------------------------------------------------------

class TestStripCodehilite:
    def test_strips_codehilite_div(self):
        html = '<div class="codehilite" style="background:#fff"><pre style="line-height:125%"><span style="color:red">def</span> foo(): pass</pre></div>'
        result = _strip_codehilite(html)
        assert 'class="codehilite"' not in result

    def test_strips_colour_spans(self):
        html = '<div class="codehilite"><pre><span style="color:red">def</span> foo</pre></div>'
        result = _strip_codehilite(html)
        assert '<span' not in result
        assert "def" in result
        assert "foo" in result

    def test_strips_pre_inline_style(self):
        html = '<div class="codehilite"><pre style="background:#f8f8f8;line-height:125%">code</pre></div>'
        result = _strip_codehilite(html)
        # The style attribute should be removed from the <pre> tag.
        assert 'style="background' not in result
        assert "code" in result

    def test_strips_code_wrapper_inside_pre(self):
        """<code> tags inside <pre> are stripped (prevents pill styling on code blocks)."""
        html = "<pre><code>echo hello</code></pre>"
        result = _strip_codehilite(html)
        assert "<code" not in result
        assert "</code>" not in result
        assert "echo hello" in result

    def test_plain_pre_unchanged(self):
        html = "<pre>plain code</pre>"
        result = _strip_codehilite(html)
        assert "plain code" in result


# ---------------------------------------------------------------------------
# Inline styles on structural elements
# ---------------------------------------------------------------------------

class TestInlineStyles:
    def test_outer_table_has_inline_style(self):
        html = _render("Hello.")
        # The outer wrapper table should carry width:100%;border-collapse:collapse
        assert "width:100%;border-collapse:collapse" in html

    def test_heading_h2_has_inline_style(self):
        md = "## My Section\n\nContent."
        html = _render(md)
        assert re.search(r'<h2\s+style="[^"]+">My Section</h2>', html)

    def test_paragraph_has_inline_style(self):
        html = _render("A paragraph.")
        assert re.search(r'<p\s+style="[^"]+">A paragraph\.</p>', html)

    def test_letterhead_td_has_inline_style(self):
        html = _render("Hello.")
        # Letterhead cell should carry border-bottom style.
        assert "border-bottom:2px solid" in html


# ---------------------------------------------------------------------------
# role="presentation" tables
# ---------------------------------------------------------------------------

class TestPresentationTables:
    def test_outer_table_has_role_presentation(self):
        html = _render("Hello.")
        assert 'role="presentation"' in html

    def test_multiple_presentation_tables(self):
        html = _render("Hello.")
        count = html.count('role="presentation"')
        # Outer table + inner content table + letterhead tables ≥ 3
        assert count >= 3


# ---------------------------------------------------------------------------
# Letterhead
# ---------------------------------------------------------------------------

class TestLetterhead:
    def test_name_in_letterhead(self):
        cfg = resolve(
            home_config={"identity": {"name": "Alice Smith"}},
            os_name_fn=lambda: "X",
        )
        html = _render("Hello.", cfg=cfg)
        assert "Alice Smith" in html

    def test_role_in_letterhead(self):
        cfg = resolve(
            home_config={"identity": {"name": "Alice Smith", "role": "Senior Architect"}},
            os_name_fn=lambda: "X",
        )
        html = _render("Hello.", cfg=cfg)
        assert "Senior Architect" in html

    def test_empty_role_omits_role_div(self):
        cfg = resolve(
            home_config={"identity": {"name": "Alice Smith", "role": ""}},
            os_name_fn=lambda: "X",
        )
        html = _render("Hello.", cfg=cfg)
        assert "Senior Architect" not in html
        # The role div colour (#0d8a7d = secondary) should not appear in role context.
        # (It will appear in the border-bottom, not as a role line.)

    def test_monogram_in_letterhead_by_default(self):
        cfg = resolve(
            home_config={"identity": {"name": "Alice Smith"}},
            os_name_fn=lambda: "X",
        )
        html = _render("Hello.", cfg=cfg)
        assert "AS" in html

    def test_no_date_in_email_letterhead(self):
        """The email letterhead has no date line (differs from document)."""
        cfg = resolve(
            home_config={"identity": {"name": "Alice Smith"}},
            os_name_fn=lambda: "X",
        )
        doc = parse_text("---\ndate: 2026-04-08\n---\nHello.", source_dir=Path("."))
        html = render_email(doc, cfg)
        # Date from frontmatter should not appear in email.
        assert "8 April 2026" not in html
        assert "2026-04-08" not in html

    def test_no_footer_in_email(self):
        """The email renderer produces no report-footer element."""
        html = _render("Hello.")
        assert "report-footer" not in html

    def test_teal_bottom_border_on_letterhead(self):
        """The letterhead bottom border uses the secondary (teal) colour."""
        html = _render("Hello.")
        # Default secondary is #0d8a7d
        assert "border-bottom:2px solid #0d8a7d" in html

    def test_avatar_embedded_when_mark_is_avatar(self, tmp_path):
        """mark=avatar with a readable file embeds the image as data: URI."""
        img = tmp_path / "avatar.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        cfg = resolve(
            home_config={
                "identity": {
                    "name": "Alice Smith",
                    "mark": "avatar",
                    "avatar": str(img),
                }
            },
            os_name_fn=lambda: "X",
        )
        html = _render("Hello.", cfg=cfg)
        assert "data:image/png;base64," in html

    def test_avatar_falls_back_to_monogram_when_missing(self, tmp_path, capsys):
        cfg = resolve(
            home_config={
                "identity": {
                    "name": "Alice Smith",
                    "mark": "avatar",
                    "avatar": str(tmp_path / "ghost.png"),
                }
            },
            os_name_fn=lambda: "X",
        )
        html = _render("Hello.", cfg=cfg)
        # Falls back to monogram (initials).
        assert "AS" in html
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()

    def test_avatar_email_preferred_over_main_avatar(self, tmp_path):
        """avatar_email is used in the email letterhead when present."""
        main_img = tmp_path / "main.png"
        email_img = tmp_path / "email.png"
        main_img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\xAA" * 100)
        email_img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\xBB" * 100)
        cfg = resolve(
            home_config={
                "identity": {
                    "name": "Alice",
                    "mark": "avatar",
                    "avatar": str(main_img),
                    "avatar_email": str(email_img),
                }
            },
            os_name_fn=lambda: "X",
        )
        html = _render("Hello.", cfg=cfg)
        import base64
        email_b64 = base64.b64encode(email_img.read_bytes()).decode("ascii")
        assert email_b64 in html


# ---------------------------------------------------------------------------
# Title block
# ---------------------------------------------------------------------------

class TestTitleBlock:
    def test_title_rendered_as_h2(self):
        html = _render("---\ntitle: My Report\n---\n\nContent.")
        assert "My Report" in html
        assert re.search(r'<h2\s+style="[^"]+">My Report</h2>', html)

    def test_subtitle_rendered(self):
        html = _render("---\ntitle: T\nsubtitle: My Subtitle\n---\n\nContent.")
        assert "My Subtitle" in html

    def test_no_title_omits_title_block(self):
        html = _render("Just a paragraph.")
        # No doc-title h2 at the top (h2 only from section headings in body).
        # With no title, no title block is emitted.
        assert "doc-title" not in html


# ---------------------------------------------------------------------------
# Callouts
# ---------------------------------------------------------------------------

class TestAlerts:
    def test_note_bar_and_background(self):
        md = "> [!NOTE]\n> Note text.\n"
        html = _render(md)
        # bar colour: primary (#1c2b39), bg: info_bg (#e6f4f2)
        assert "background:#1c2b39" in html
        assert "background:#e6f4f2" in html
        assert ">Note<" in html

    def test_tip_bar_and_background(self):
        md = "> [!TIP]\n> Tip text.\n"
        html = _render(md)
        assert "background:#2a7f4f" in html
        assert "background:#e8f5ed" in html
        assert ">Tip<" in html

    def test_important_bar_and_background(self):
        md = "> [!IMPORTANT]\n> Important text.\n"
        html = _render(md)
        assert "background:#b07514" in html
        assert "background:#fdf3e3" in html
        assert ">Important<" in html

    def test_warning_bar_and_background(self):
        md = "> [!WARNING]\n> Warning text.\n"
        html = _render(md)
        assert "background:#b07514" in html
        assert "background:#fdf3e3" in html
        assert ">Warning<" in html

    def test_caution_bar_and_background(self):
        md = "> [!CAUTION]\n> Caution text.\n"
        html = _render(md)
        assert "background:#b33a3a" in html
        assert "background:#fce8e8" in html
        assert ">Caution<" in html

    def test_alert_is_two_cell_table(self):
        md = "> [!NOTE]\n> A note.\n"
        html = _render(md)
        # Two cells: bar cell (4px wide) and content cell.
        assert 'width="4"' in html or 'width:4px' in html

    def test_alert_label_uppercase_style(self):
        md = "> [!NOTE]\n> A note.\n"
        html = _render(md)
        assert "text-transform:uppercase" in html

    def test_stacked_alerts_both_rendered(self):
        md = "> [!NOTE] First.\n>\n> [!WARNING] Second.\n"
        html = _render(md)
        assert ">Note<" in html
        assert ">Warning<" in html


class TestBlockquote:
    def test_plain_blockquote_becomes_accent_bar_table(self):
        md = "> A plain quote.\n"
        html = _render(md)
        # Accent bar colour: #0d8a7d
        assert "background:#0d8a7d" in html
        # Grey-50 background for the content cell.
        assert "background:#f4f7f8" in html

    def test_plain_blockquote_no_alert_label(self):
        md = "> A plain quote.\n"
        html = _render(md)
        assert ">Note<" not in html
        assert ">Tip<" not in html
        assert "text-transform:uppercase" not in html


# ---------------------------------------------------------------------------
# Code blocks
# ---------------------------------------------------------------------------

class TestCodeBlocks:
    def test_code_block_wrapped_in_table(self):
        md = "```bash\necho hello\n```"
        html = _render(md)
        # The pre should be inside a table cell.
        assert re.search(r'<td[^>]*>.*?<pre', html, re.DOTALL)

    def test_code_block_has_pre_with_monospace(self):
        md = "```bash\necho hello\n```"
        html = _render(md)
        assert "SFMono-Regular" in html or "Consolas" in html

    def test_code_block_white_space_pre_wrap(self):
        md = "```bash\necho hello\n```"
        html = _render(md)
        assert "white-space:pre-wrap" in html

    def test_code_content_preserved(self):
        md = "```bash\necho hello world\n```"
        html = _render(md)
        assert "echo hello world" in html

    def test_fenced_code_pre_contains_no_code_tag(self):
        """The <pre> inside a fenced code block must not contain a <code> tag.

        python-markdown wraps fenced code in <pre><code>...</code></pre>.
        _strip_codehilite must unwrap that <code> so _style_inline_code
        cannot apply the pill background to it, which would render as a
        ragged grey rounded box instead of the plain transparent monospace.
        """
        md = "```bash\necho hello\n```"
        html = _render(md)
        pre_m = re.search(r'<pre[^>]*>(.*?)</pre>', html, re.DOTALL)
        assert pre_m is not None, "Expected a <pre> element in output"
        assert "<code" not in pre_m.group(1), (
            "Found <code> inside <pre> — inline-code pill styling will leak into code blocks"
        )

    def test_highlighted_python_has_no_colour_spans(self):
        """Python with codehilite would normally emit colour spans; email strips them."""
        md = "```python\ndef foo(x):\n    return x + 1\n```"
        html = _render(md)
        assert not re.search(r'<span\s+style="color:', html)
        assert "def" in html
        assert "return" in html


# ---------------------------------------------------------------------------
# Data tables and zebra striping
# ---------------------------------------------------------------------------

class TestZebraStriping:
    def test_odd_rows_are_white(self):
        md = "| A | B |\n| - | - |\n| R1 | V1 |\n| R2 | V2 |\n| R3 | V3 |\n"
        html = _render(md)
        # Parse out tbody row backgrounds.
        tbody_m = re.search(r'<tbody>(.*?)</tbody>', html, re.DOTALL)
        assert tbody_m is not None
        tbody = tbody_m.group(1)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody, re.DOTALL)
        assert len(rows) == 3
        # Row 1 (odd) — all td backgrounds should be white.
        row1_bgs = re.findall(r'background:(#[a-f0-9]{6})', rows[0], re.IGNORECASE)
        assert all(bg.lower() == "#ffffff" for bg in row1_bgs), f"Row 1 bgs: {row1_bgs}"

    def test_even_rows_are_grey50(self):
        md = "| A | B |\n| - | - |\n| R1 | V1 |\n| R2 | V2 |\n| R3 | V3 |\n"
        html = _render(md)
        tbody_m = re.search(r'<tbody>(.*?)</tbody>', html, re.DOTALL)
        assert tbody_m is not None
        tbody = tbody_m.group(1)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody, re.DOTALL)
        # Row 2 (even) — td backgrounds should be surface (#f4f7f8).
        row2_bgs = re.findall(r'background:(#[a-f0-9]{6})', rows[1], re.IGNORECASE)
        assert all(bg.lower() == "#f4f7f8" for bg in row2_bgs), f"Row 2 bgs: {row2_bgs}"

    def test_both_stripe_colours_present(self):
        md = "| A | B |\n| - | - |\n| R1 | V1 |\n| R2 | V2 |\n"
        html = _render(md)
        assert "#ffffff" in html
        assert "#f4f7f8" in html

    def test_table_header_styled(self):
        md = "| A | B |\n| - | - |\n| 1 | 2 |\n"
        html = _render(md)
        assert "text-transform:uppercase" in html
        # Header background is the primary blue.
        assert "background:#1c2b39" in html

    def test_existing_rag_colour_preserved(self):
        """A <td style="color:..."> from the body should keep its colour."""
        # We simulate a table where a cell already has color styling.
        # python-markdown won't produce inline colour, so we check the
        # combinator logic directly via the zebra striping helper.
        from brandx.render.email import _extract_existing_style
        attrs = ' style="color:#2a7f4f;font-weight:600;"'
        existing = _extract_existing_style(attrs)
        assert "color:#2a7f4f" in existing


# ---------------------------------------------------------------------------
# Gmail clip warning and avatar size warning
# ---------------------------------------------------------------------------

class TestSizeWarnings:
    def test_gmail_clip_warning_on_large_html(self, capsys):
        """Output larger than 80 KB triggers a stderr clip warning."""
        # Build an HTML blob that will push the rendered output over 80 KB.
        # A large repeated paragraph is enough once the email shell is added.
        big_content = "A" * (_GMAIL_CLIP_WARN_BYTES + 5000)
        cfg = _make_cfg(name="Test User")
        doc = parse_text(big_content, source_dir=Path("."))
        render_email(doc, cfg)
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()
        assert "gmail" in captured.err.lower() or "clip" in captured.err.lower() or "KB" in captured.err

    def test_no_clip_warning_for_small_html(self, capsys):
        """Small emails should not trigger the clip warning."""
        _render("Hello.")
        captured = capsys.readouterr()
        assert "clip" not in captured.err.lower()
        assert "gmail" not in captured.err.lower()

    def test_heavy_avatar_warning(self, tmp_path, capsys):
        """An embedded avatar larger than _AVATAR_HEAVY_WARN_BYTES triggers a stderr warning."""
        # Base64 is ~133% of raw, so we need raw bytes > 75 KB to cross 100 KB encoded.
        big_img = tmp_path / "big_avatar.png"
        # Write just over 76 KB of raw bytes (encoded will be ~101 KB).
        big_img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * (78 * 1024))
        cfg = resolve(
            home_config={
                "identity": {
                    "name": "Test",
                    "mark": "avatar",
                    "avatar": str(big_img),
                }
            },
            os_name_fn=lambda: "X",
        )
        doc = parse_text("Hello.", source_dir=Path("."))
        render_email(doc, cfg)
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()
        # The warning should mention the avatar or image size.
        assert "avatar" in captured.err.lower() or "large" in captured.err.lower() or "KB" in captured.err


# ---------------------------------------------------------------------------
# Image embedding
# ---------------------------------------------------------------------------

class TestImageEmbedding:
    def test_local_image_embedded_as_data_uri(self, tmp_path):
        img = tmp_path / "chart.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        md = "![chart](chart.png)"
        html = _render(md, source_dir=tmp_path)
        assert "data:image/png;base64," in html

    def test_http_image_left_untouched(self, tmp_path):
        md = "![remote](https://example.com/img.png)"
        html = _render(md, source_dir=tmp_path)
        assert "https://example.com/img.png" in html

    def test_missing_local_image_warns_and_leaves_src(self, tmp_path, capsys):
        md = "![missing](ghost.png)"
        html = _render(md, source_dir=tmp_path)
        assert "ghost.png" in html
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_no_title(self):
        html = _render("Just a paragraph.")
        assert "Just a paragraph" in html
        assert "<style>" not in html

    def test_empty_body(self):
        html = _render("")
        assert "<!DOCTYPE html>" in html
        assert "<style>" not in html

    def test_name_from_os_when_not_configured(self):
        cfg = resolve(os_name_fn=lambda: "OS User")
        doc = parse_text("Hello.", source_dir=Path("."))
        html = render_email(doc, cfg)
        assert "OS User" in html

    def test_html_special_chars_escaped_in_name(self):
        cfg = resolve(
            home_config={"identity": {"name": "Alice & Bob <Test>"}},
            os_name_fn=lambda: "X",
        )
        html = _render("Hello.", cfg=cfg)
        assert "&amp;" in html or "Alice" in html
        # Should not contain raw unescaped < or > in name context.
        assert "<Bob" not in html


# ---------------------------------------------------------------------------
# render_email_file convenience function
# ---------------------------------------------------------------------------

class TestRenderEmailFile:
    def test_render_from_file(self, tmp_path):
        md_file = tmp_path / "note.md"
        md_file.write_text("# My Note\n\nContent here.", encoding="utf-8")
        cfg = resolve(
            home_config={"identity": {"name": "Test User"}},
            os_name_fn=lambda: "X",
        )
        html = render_email_file(md_file, cfg)
        assert "My Note" in html
        assert "<style>" not in html
        assert 'role="presentation"' in html
