"""Tests for the shared structural pass (U6).

Covers (from plan):
- Stacked alerts in one blockquote split into two bx:alert markers.
- Plain blockquote with no marker stays a plain blockquote marker.
- Missing title: first H1 used and removed from the body.
- File with no frontmatter parses cleanly.
- Nested frontmatter keys parse into a nested mapping.
"""

from brandx.render.pipeline import parse_text, _parse_frontmatter, _extract_title


class TestParseFrontmatter:
    def test_no_frontmatter(self):
        meta, body = _parse_frontmatter("# Hello\n\nWorld.")
        assert meta == {}
        assert "# Hello" in body

    def test_simple_frontmatter(self):
        text = "---\ntitle: My Doc\n---\n\nBody here."
        meta, body = _parse_frontmatter(text)
        assert meta["title"] == "My Doc"
        assert "Body here." in body

    def test_nested_frontmatter(self):
        text = "---\ncolours:\n  accent: '#red'\n---\n\nBody."
        meta, body = _parse_frontmatter(text)
        assert isinstance(meta["colours"], dict)
        assert meta["colours"]["accent"] == "#red"

    def test_malformed_yaml_returns_empty(self):
        text = "---\n: broken [ yaml\n---\nBody."
        meta, body = _parse_frontmatter(text)
        assert meta == {}

    def test_empty_frontmatter_block(self):
        text = "---\n---\nBody."
        meta, body = _parse_frontmatter(text)
        assert meta == {}


class TestExtractTitle:
    def test_frontmatter_title_wins(self):
        meta = {"title": "FM Title"}
        body = "# Heading\n\nContent."
        title, out_body, from_heading = _extract_title(meta, body)
        assert title == "FM Title"
        assert from_heading is False
        assert "# Heading" in out_body

    def test_first_h1_used_when_no_frontmatter_title(self):
        meta = {}
        body = "# First Heading\n\nContent."
        title, out_body, from_heading = _extract_title(meta, body)
        assert title == "First Heading"
        assert from_heading is True

    def test_empty_title_when_no_source(self):
        meta = {}
        body = "No heading here."
        title, out_body, from_heading = _extract_title(meta, body)
        assert title == ""
        assert from_heading is False


class TestParseText:
    def test_simple_paragraph(self):
        doc = parse_text("Hello world.")
        assert "<p>" in doc.body_html
        assert doc.title == ""
        assert doc.frontmatter == {}

    def test_title_from_heading_strips_h1(self):
        doc = parse_text("# My Title\n\nSome content.")
        assert doc.title == "My Title"
        assert doc.title_from_heading is True
        assert "<h1" not in doc.body_html

    def test_frontmatter_title_does_not_strip_h1(self):
        text = "---\ntitle: FM Title\n---\n\n# Still Here\n\nContent."
        doc = parse_text(text)
        assert doc.title == "FM Title"
        assert doc.title_from_heading is False
        assert "<h1" in doc.body_html

    def test_no_frontmatter_parses_cleanly(self):
        doc = parse_text("Just plain text here.")
        assert doc.frontmatter == {}
        assert doc.date_raw is None
        assert doc.subtitle == ""
        assert doc.mark is None

    def test_nested_frontmatter_preserved(self):
        text = "---\ncolours:\n  accent: '#ff0000'\n---\nContent."
        doc = parse_text(text)
        assert isinstance(doc.frontmatter["colours"], dict)
        assert doc.frontmatter["colours"]["accent"] == "#ff0000"

    def test_stacked_alerts_produce_two_bx_markers(self):
        text = "> [!NOTE] First note.\n>\n> [!WARNING] A warning.\n\nContent."
        doc = parse_text(text)
        assert '<!-- bx:alert type="note" -->' in doc.body_html
        assert '<!-- bx:alert type="warning" -->' in doc.body_html

    def test_plain_blockquote_becomes_bx_blockquote(self):
        text = "> Just a design principle.\n\nContent."
        doc = parse_text(text)
        assert "<!-- bx:blockquote -->" in doc.body_html
        assert "bx:alert" not in doc.body_html

    def test_tables_render(self):
        text = "| A | B |\n| - | - |\n| 1 | 2 |"
        doc = parse_text(text)
        assert "<table>" in doc.body_html

    def test_fenced_code_renders(self):
        text = "```python\nprint('hello')\n```"
        doc = parse_text(text)
        assert "<pre>" in doc.body_html or "<code>" in doc.body_html

    def test_date_raw_from_frontmatter(self):
        text = "---\ndate: 2026-06-20\n---\nBody."
        doc = parse_text(text)
        assert doc.date_raw == "2026-06-20"

    def test_subtitle_from_frontmatter(self):
        text = "---\nsubtitle: My Subtitle\n---\nBody."
        doc = parse_text(text)
        assert doc.subtitle == "My Subtitle"

    def test_mark_from_frontmatter(self):
        text = "---\nmark: avatar\n---\nBody."
        doc = parse_text(text)
        assert doc.mark == "avatar"

    def test_reset_between_documents(self):
        text = "```python\nx = 1\n```"
        doc1 = parse_text(text)
        doc2 = parse_text(text)
        assert doc1.body_html == doc2.body_html
