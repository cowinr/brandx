"""Tests for the document renderer (U7).

Covers (from plan):
- Output contains a <style> block and :root CSS variables from the config.
- The @media print block is present.
- A fenced code block is syntax-highlighted (inline-styled spans present).
- A local image becomes a data: URI; an http(s) image is left untouched; a missing
  local image warns and is left untouched.
- Default config renders the monogram (generic-engine AE2).
- mark: avatar with a resolvable avatar renders an embedded avatar <img> (AE4).
- Alerts: each bx:alert type maps to the right .alert-{type} class.
- bx:blockquote becomes a styled <blockquote>.
- Date formatting: long-british default; named formats; strftime passthrough.
- Section h2 gets class="section-title"; table gets class="data-table".
- Empty role omits the .letterhead-role element.
- No date in frontmatter defaults to today's date.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path


from brandx.config.resolver import resolve, ResolvedConfig
from brandx.render.document import (
    render_document,
    render_document_file,
    _resolve_doc_date,
    _format_date,
)
from brandx.render.pipeline import parse_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cfg(**overrides) -> ResolvedConfig:
    """Build a ResolvedConfig with optional identity overrides."""
    home = {}
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
    return render_document(doc, cfg)


# ---------------------------------------------------------------------------
# Style block and CSS variables
# ---------------------------------------------------------------------------

class TestStyleBlock:
    def test_style_block_present(self):
        html = _render("Hello.")
        assert "<style>" in html

    def test_root_css_variables_present(self):
        html = _render("Hello.")
        assert ":root {" in html

    def test_blue_colour_var(self):
        cfg = resolve(
            home_config={"colours": {"blue": "#112233"}},
            os_name_fn=lambda: "X",
        )
        html = _render("Hello.", cfg=cfg)
        assert "--blue: #112233" in html

    def test_accent_colour_var(self):
        cfg = resolve(
            home_config={"colours": {"accent": "#cafeba"}},
            os_name_fn=lambda: "X",
        )
        html = _render("Hello.", cfg=cfg)
        assert "--accent: #cafeba" in html

    def test_note_bg_mapped_to_note_bg_var(self):
        html = _render("Hello.")
        # note_bg_html → --note-bg
        assert "--note-bg:" in html

    def test_important_bg_mapped_to_important_bg_var(self):
        html = _render("Hello.")
        # important_bg_html → --important-bg
        assert "--important-bg:" in html

    def test_font_family_var_present(self):
        html = _render("Hello.")
        assert "--font:" in html

    def test_print_media_block_present(self):
        html = _render("Hello.")
        assert "@media print" in html

    def test_google_font_link_present(self):
        html = _render("Hello.")
        # Default config has a google_url
        assert 'fonts.googleapis.com' in html

    def test_no_google_font_link_when_url_empty(self):
        cfg = resolve(
            home_config={"fonts": {"google_url": ""}},
            os_name_fn=lambda: "X",
        )
        html = _render("Hello.", cfg=cfg)
        assert 'fonts.googleapis.com' not in html


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
        assert 'class="letterhead-role"' in html

    def test_empty_role_omits_letterhead_role_element(self):
        cfg = resolve(
            home_config={"identity": {"name": "Alice Smith", "role": ""}},
            os_name_fn=lambda: "X",
        )
        html = _render("Hello.", cfg=cfg)
        assert 'class="letterhead-role"' not in html

    def test_gradient_bar_present(self):
        html = _render("Hello.")
        assert 'class="letterhead-bar"' in html

    def test_monogram_rendered_by_default(self):
        """generic-engine AE2: default mark renders the monogram."""
        cfg = resolve(
            home_config={"identity": {"name": "Alice Smith"}},
            os_name_fn=lambda: "X",
        )
        html = _render("Hello.", cfg=cfg)
        assert 'class="letterhead-monogram"' in html
        assert "AS" in html

    def test_avatar_rendered_when_mark_is_avatar(self, tmp_path):
        """generic-engine AE4: mark=avatar with a readable file embeds the image."""
        img = tmp_path / "avatar.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
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
        assert 'data:image/png;base64,' in html
        # The monogram box should NOT appear.
        assert 'class="letterhead-monogram"' not in html

    def test_avatar_falls_back_to_monogram_when_file_missing(self, tmp_path, capsys):
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
        # Falls back to monogram.
        assert 'class="letterhead-monogram"' in html
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()


# ---------------------------------------------------------------------------
# Title block
# ---------------------------------------------------------------------------

class TestTitleBlock:
    def test_doc_title_rendered(self):
        html = _render("---\ntitle: My Report\n---\n\nContent.")
        assert 'class="doc-title"' in html
        assert "My Report" in html

    def test_doc_subtitle_rendered(self):
        html = _render("---\ntitle: T\nsubtitle: My Subtitle\n---\n\nContent.")
        assert 'class="doc-subtitle"' in html
        assert "My Subtitle" in html

    def test_no_title_omits_title_block(self):
        html = _render("Just a paragraph.")
        assert 'class="doc-title"' not in html


# ---------------------------------------------------------------------------
# Body transformations
# ---------------------------------------------------------------------------

class TestAlerts:
    def test_note_alert(self):
        md = "> [!NOTE]\n> This is a note.\n"
        html = _render(md)
        assert 'class="alert alert-note"' in html
        assert 'class="alert-title"' in html
        assert "Note" in html

    def test_tip_alert(self):
        md = "> [!TIP]\n> A tip.\n"
        html = _render(md)
        assert 'class="alert alert-tip"' in html
        assert "Tip" in html

    def test_important_alert(self):
        md = "> [!IMPORTANT]\n> Pay attention.\n"
        html = _render(md)
        assert 'class="alert alert-important"' in html
        assert "Important" in html

    def test_warning_alert(self):
        md = "> [!WARNING]\n> Be careful.\n"
        html = _render(md)
        assert 'class="alert alert-warning"' in html
        assert "Warning" in html

    def test_caution_alert(self):
        md = "> [!CAUTION]\n> Danger ahead.\n"
        html = _render(md)
        assert 'class="alert alert-caution"' in html
        assert "Caution" in html

    def test_plain_blockquote_becomes_blockquote_element(self):
        md = "> Just a plain quote.\n"
        html = _render(md)
        assert "<blockquote>" in html
        assert 'class="alert' not in html

    def test_stacked_alerts_both_rendered(self):
        md = "> [!NOTE] First.\n>\n> [!WARNING] Second.\n"
        html = _render(md)
        assert 'class="alert alert-note"' in html
        assert 'class="alert alert-warning"' in html


class TestHeadingsAndTables:
    def test_h2_gets_section_title_class(self):
        md = "## My Section\n\nContent."
        html = _render(md)
        assert 'class="section-title"' in html

    def test_table_gets_data_table_class(self):
        md = "| A | B |\n| - | - |\n| 1 | 2 |\n"
        html = _render(md)
        assert 'class="data-table"' in html


class TestCodeBlocks:
    def test_fenced_code_is_syntax_highlighted(self):
        """Inline-styled spans from codehilite should be present."""
        md = "```python\nprint('hello')\n```"
        html = _render(md)
        # codehilite with noclasses=True emits inline style attributes on spans.
        assert "<span" in html
        assert "style=" in html

    def test_codehilite_div_wrapper_removed(self):
        """The codehilite <div> wrapper should be unwrapped."""
        md = "```python\nx = 1\n```"
        html = _render(md)
        assert 'class="codehilite"' not in html

    def test_pre_element_present(self):
        md = "```bash\necho hello\n```"
        html = _render(md)
        assert "<pre>" in html or "<pre " in html


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
# Date formatting
# ---------------------------------------------------------------------------

class TestDateFormatting:
    def test_long_british_default(self):
        dt = date(2026, 4, 8)
        assert _format_date(dt, "long-british") == "8 April 2026"

    def test_long_british_no_leading_zero(self):
        dt = date(2026, 1, 1)
        result = _format_date(dt, "long-british")
        assert result == "1 January 2026"
        assert result[0] == "1"  # no leading zero

    def test_iso_format(self):
        dt = date(2026, 4, 8)
        assert _format_date(dt, "iso") == "2026-04-08"

    def test_eu_format(self):
        dt = date(2026, 4, 8)
        assert _format_date(dt, "eu") == "08.04.2026"

    def test_strftime_passthrough(self):
        dt = date(2026, 4, 8)
        result = _format_date(dt, "%Y/%m/%d")
        assert result == "2026/04/08"

    def test_resolve_doc_date_parses_iso(self):
        result = _resolve_doc_date("2026-04-08", "long-british")
        assert result == "8 April 2026"

    def test_resolve_doc_date_uses_today_when_none(self):
        today = date.today()
        result = _resolve_doc_date(None, "long-british")
        today_str = f"{today.day} {['January','February','March','April','May','June','July','August','September','October','November','December'][today.month - 1]} {today.year}"
        assert result == today_str

    def test_date_rendered_in_letterhead(self):
        cfg = resolve(
            home_config={"identity": {"name": "Alice"}},
            os_name_fn=lambda: "X",
        )
        doc = parse_text("---\ndate: 2026-04-08\n---\nContent.")
        html = render_document(doc, cfg)
        assert "8 April 2026" in html

    def test_date_in_footer(self):
        cfg = resolve(
            home_config={"identity": {"name": "Alice"}},
            os_name_fn=lambda: "X",
        )
        doc = parse_text("---\ndate: 2026-04-08\n---\nContent.")
        html = render_document(doc, cfg)
        footer_idx = html.find('class="report-footer"')
        assert footer_idx > 0
        footer_fragment = html[footer_idx:]
        assert "8 April 2026" in footer_fragment


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

class TestFooter:
    def test_footer_contains_name(self):
        cfg = resolve(
            home_config={"identity": {"name": "Jane Doe"}},
            os_name_fn=lambda: "X",
        )
        html = _render("Hello.", cfg=cfg)
        assert 'class="report-footer"' in html
        # Name appears in footer
        footer_idx = html.find('class="report-footer"')
        footer_fragment = html[footer_idx:]
        assert "Jane Doe" in footer_fragment


# ---------------------------------------------------------------------------
# render_document_file convenience function
# ---------------------------------------------------------------------------

class TestRenderDocumentFile:
    def test_render_from_file(self, tmp_path):
        md_file = tmp_path / "note.md"
        md_file.write_text("# My Note\n\nContent here.", encoding="utf-8")
        cfg = resolve(
            home_config={"identity": {"name": "Test User"}},
            os_name_fn=lambda: "X",
        )
        html = render_document_file(md_file, cfg)
        assert "My Note" in html
        assert "<style>" in html
