"""Tests for mermaid diagram extraction, rendering, and substitution.

Covers (from spec):
- extract_diagrams finds one, several, and zero fences; sources in document order;
  a ```python fence untouched; a ~~~mermaid fence handled.
- Placeholder count matches source count; marker text is exactly
  <!-- bx:mermaid id="0" -->.
- ParsedDocument.diagrams is populated by parse_text.
- The theme mapping produces valid JSON containing the config's own colour values.
- Degradation: with rendering forced to fail, the document/email still render and
  the mermaid source survives as a code block.
- Cache: a second render_diagrams call with identical input launches no subprocess.

No test here shells out to real mmdc; the subprocess entry point is always
monkeypatched, so the suite passes on a machine with no Node.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import brandx.render.diagrams as diagrams
from brandx.config.resolver import resolve
from brandx.render.diagrams import (
    _mermaid_config,
    extract_diagrams,
    render_diagrams,
    substitute,
)
from brandx.render.document import _fix_svg_root, render_document
from brandx.render.email import render_email
from brandx.render.pipeline import parse_text


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolate_diagram_cache(monkeypatch, tmp_path):
    """Point the on-disk diagram cache at a per-test temp directory.

    Without this, render_diagrams would read/write the developer's real
    ~/.cache/brandx/diagrams, and a sha256 cache key from an earlier test
    run would make a "cache miss" test pass for the wrong reason.
    """
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))


def _fake_call_mmdc(calls: list, ext: str, content: bytes):
    """Build a fake for diagrams._call_mmdc that writes numbered output files.

    Mirrors what a real mmdc invocation leaves behind (out-1.<ext>, out-2.<ext>,
    ...) without shelling out, so render_diagrams' file-reading logic is
    exercised for real.
    """

    def fake(cmd: list[str]) -> subprocess.CompletedProcess:
        calls.append(cmd)
        out_dir = Path(cmd[cmd.index("-o") + 1]).parent
        in_md = Path(cmd[cmd.index("-i") + 1]).read_text(encoding="utf-8")
        count = in_md.count("```mermaid")
        for i in range(1, count + 1):
            (out_dir / f"out-{i}.{ext}").write_bytes(content)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    return fake


# ---------------------------------------------------------------------------
# extract_diagrams
# ---------------------------------------------------------------------------

class TestExtractDiagrams:
    def test_zero_fences_leaves_text_unchanged(self):
        text = "# Title\n\nJust a paragraph.\n"
        body, sources = extract_diagrams(text)
        assert body == text
        assert sources == []

    def test_one_fence_extracted(self):
        text = "Before.\n\n```mermaid\ngraph TD\n  A --> B\n```\n\nAfter.\n"
        body, sources = extract_diagrams(text)
        assert sources == ["graph TD\n  A --> B"]
        assert '<!-- bx:mermaid id="0" -->' in body
        assert "graph TD" not in body

    def test_several_fences_in_document_order(self):
        text = (
            "```mermaid\ngraph TD\n  A --> B\n```\n\n"
            "Some text.\n\n"
            "```mermaid\ngraph LR\n  X --> Y\n```\n"
        )
        body, sources = extract_diagrams(text)
        assert sources == ["graph TD\n  A --> B", "graph LR\n  X --> Y"]
        assert '<!-- bx:mermaid id="0" -->' in body
        assert '<!-- bx:mermaid id="1" -->' in body
        # Order in the rewritten body matches extraction order.
        assert body.index('id="0"') < body.index('id="1"')

    def test_python_fence_left_untouched(self):
        text = "```python\nprint('hello')\n```\n"
        body, sources = extract_diagrams(text)
        assert body == text
        assert sources == []

    def test_tilde_mermaid_fence_handled(self):
        text = "~~~mermaid\ngraph TD\n  A --> B\n~~~\n"
        body, sources = extract_diagrams(text)
        assert sources == ["graph TD\n  A --> B"]
        assert '<!-- bx:mermaid id="0" -->' in body

    def test_placeholder_count_matches_source_count(self):
        text = (
            "```mermaid\ngraph TD\n  A --> B\n```\n"
            "```mermaid\ngraph TD\n  C --> D\n```\n"
            "```mermaid\ngraph TD\n  E --> F\n```\n"
        )
        body, sources = extract_diagrams(text)
        assert len(sources) == 3
        assert body.count("<!-- bx:mermaid id=") == 3

    def test_marker_text_is_exact(self):
        text = "```mermaid\ngraph TD\n  A --> B\n```\n"
        body, _sources = extract_diagrams(text)
        assert '<!-- bx:mermaid id="0" -->' in body


# ---------------------------------------------------------------------------
# ParsedDocument.diagrams
# ---------------------------------------------------------------------------

class TestParsedDocumentDiagrams:
    def test_diagrams_populated_by_parse_text(self):
        text = "# Title\n\n```mermaid\ngraph TD\n  A --> B\n```\n"
        doc = parse_text(text)
        assert doc.diagrams == ["graph TD\n  A --> B"]
        assert '<!-- bx:mermaid id="0" -->' in doc.body_html

    def test_no_diagrams_yields_empty_list(self):
        doc = parse_text("Just a paragraph.")
        assert doc.diagrams == []


# ---------------------------------------------------------------------------
# Theme mapping
# ---------------------------------------------------------------------------

class TestThemeMapping:
    def test_brand_theme_produces_valid_json_with_configs_own_colours(self):
        cfg = resolve(
            home_config={"colours": {"primary": "#123456", "accent": "#abcdef"}},
            os_name_fn=lambda: "X",
        )
        mermaid_cfg = _mermaid_config("brand", cfg.colours, cfg.fonts)
        # json.dumps must not raise: the config is valid JSON.
        theme_json = json.dumps(mermaid_cfg)
        parsed = json.loads(theme_json)

        variables = parsed["themeVariables"]
        assert variables["primaryBorderColor"] == cfg.colours["primary"]
        assert variables["lineColor"] == cfg.colours["accent"]
        assert variables["fontFamily"] == cfg.fonts["font"]

    def test_named_theme_skips_the_mapping(self):
        cfg = resolve(os_name_fn=lambda: "X")
        assert _mermaid_config("dark", cfg.colours, cfg.fonts) is None
        assert _mermaid_config("forest", cfg.colours, cfg.fonts) is None


# ---------------------------------------------------------------------------
# render_diagrams
# ---------------------------------------------------------------------------

class TestRenderDiagrams:
    def test_empty_sources_returns_empty_list(self):
        cfg = resolve(os_name_fn=lambda: "X")
        assert render_diagrams([], cfg, "svg") == []

    def test_disabled_skips_rendering_entirely(self, monkeypatch):
        def boom(cmd):
            raise AssertionError("mmdc must not be invoked when diagrams are disabled")

        monkeypatch.setattr(diagrams, "_call_mmdc", boom)
        cfg = resolve(home_config={"diagrams": {"enabled": False}}, os_name_fn=lambda: "X")
        result = render_diagrams(["graph TD\n  A --> B"], cfg, "svg")
        assert result == [None]

    def test_successful_render_returns_svg_text(self, monkeypatch):
        calls: list = []
        monkeypatch.setattr(
            diagrams.shutil, "which", lambda name: "/usr/bin/mmdc" if name == "mmdc" else None
        )
        monkeypatch.setattr(diagrams, "_call_mmdc", _fake_call_mmdc(calls, "svg", b"<svg>fake</svg>"))

        cfg = resolve(os_name_fn=lambda: "X")
        result = render_diagrams(["graph TD\n  A --> B"], cfg, "svg")
        assert result == ["<svg>fake</svg>"]
        assert len(calls) == 1


# ---------------------------------------------------------------------------
# Degradation
# ---------------------------------------------------------------------------

class TestDegradation:
    def test_mmdc_absent_document_still_renders_with_fallback(self, monkeypatch, capsys):
        monkeypatch.setattr(diagrams.shutil, "which", lambda _name: None)
        cfg = resolve(os_name_fn=lambda: "Test User")
        doc = parse_text("# Title\n\n```mermaid\ngraph TD\n  A --> B\n```\n")

        html = render_document(doc, cfg)

        assert "<pre><code>" in html
        assert "graph TD" in html
        err = capsys.readouterr().err
        assert "mmdc not found" in err

    def test_mmdc_absent_email_still_renders_with_fallback(self, monkeypatch, capsys):
        monkeypatch.setattr(diagrams.shutil, "which", lambda _name: None)
        cfg = resolve(os_name_fn=lambda: "Test User")
        doc = parse_text("# Title\n\n```mermaid\ngraph TD\n  A --> B\n```\n")

        html = render_email(doc, cfg)

        assert "<pre" in html
        assert "graph TD" in html
        err = capsys.readouterr().err
        assert "mmdc not found" in err

    def test_mmdc_failure_warns_and_degrades(self, monkeypatch, capsys):
        monkeypatch.setattr(
            diagrams.shutil, "which", lambda name: "/usr/bin/mmdc" if name == "mmdc" else None
        )
        monkeypatch.setattr(
            diagrams, "_call_mmdc", lambda cmd: subprocess.CompletedProcess(cmd, 1, b"", b"boom")
        )
        cfg = resolve(os_name_fn=lambda: "X")

        result = render_diagrams(["graph TD\n  A --> B"], cfg, "svg")

        assert result == [None]
        assert "mmdc failed" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

class TestCache:
    def test_second_call_with_identical_input_launches_no_subprocess(self, monkeypatch):
        calls: list = []
        monkeypatch.setattr(
            diagrams.shutil, "which", lambda name: "/usr/bin/mmdc" if name == "mmdc" else None
        )
        monkeypatch.setattr(diagrams, "_call_mmdc", _fake_call_mmdc(calls, "svg", b"<svg>fake</svg>"))

        cfg = resolve(os_name_fn=lambda: "X")
        sources = ["graph TD\n  A --> B"]

        first = render_diagrams(sources, cfg, "svg")
        assert first == ["<svg>fake</svg>"]
        assert len(calls) == 1

        second = render_diagrams(sources, cfg, "svg")
        assert second == first
        assert len(calls) == 1  # no additional subprocess call on the cache hit


# ---------------------------------------------------------------------------
# substitute
# ---------------------------------------------------------------------------

class TestSubstitute:
    def test_success_and_fallback_routed_to_the_right_builder(self):
        html = '<!-- bx:mermaid id="0" --><!-- bx:mermaid id="1" -->'
        rendered = ["<svg>ok</svg>", None]
        sources = ["graph TD\n  A --> B", "graph TD\n  C --> D"]

        result = substitute(
            html, rendered, sources, "svg",
            build_image=lambda entry, idx: f"IMG[{idx}]:{entry}",
            build_fallback=lambda source: f"FALLBACK:{source}",
        )

        assert result == "IMG[0]:<svg>ok</svg>FALLBACK:graph TD\n  C --> D"


# ---------------------------------------------------------------------------

class TestFixSvgRoot:
    """The size on mmdc's SVG root is unreliable; the viewBox is the truth."""

    def test_percentage_width_replaced_from_viewbox(self):
        svg = '<svg id="my-svg" width="100%" viewBox="0 0 866.046875 236"><g/></svg>'
        assert ' width="866"' in _fix_svg_root(svg)
        assert ' height="236"' in _fix_svg_root(svg)

    def test_degenerate_size_with_offset_viewbox_is_corrected(self):
        """Regression: a flowchart came back 10x10 with a non-zero viewBox origin.

        The first two viewBox values are the origin, not the size, and they are
        not always "0 0". Reading them as the size collapsed the diagram to a
        10px square in the rendered document.
        """
        svg = (
            '<svg id="my-svg" width="10" height="10" class="flowchart" '
            'viewBox="131.8828125 0 1378.0390625 422"><g/></svg>'
        )
        fixed = _fix_svg_root(svg)
        assert ' width="1378"' in fixed
        assert ' height="422"' in fixed
        assert ' width="10"' not in fixed
        assert ' height="10"' not in fixed

    def test_negative_viewbox_origin_handled(self):
        svg = '<svg width="100%" viewBox="-20 -8.5 500 300"><g/></svg>'
        fixed = _fix_svg_root(svg)
        assert ' width="500"' in fixed
        assert ' height="300"' in fixed

    def test_missing_height_is_added(self):
        svg = '<svg width="100%" viewBox="0 0 400 200"><g/></svg>'
        assert ' height="200"' in _fix_svg_root(svg)

    def test_no_viewbox_left_alone(self):
        svg = '<svg width="100%"><g/></svg>'
        assert _fix_svg_root(svg) == svg

    def test_zero_sized_viewbox_left_alone(self):
        svg = '<svg width="100%" viewBox="0 0 0 0"><g/></svg>'
        assert _fix_svg_root(svg) == svg

    def test_only_the_root_element_is_rewritten(self):
        svg = (
            '<svg width="100%" viewBox="0 0 400 200">'
            '<rect width="99" height="99"/></svg>'
        )
        fixed = _fix_svg_root(svg)
        assert '<rect width="99" height="99"/>' in fixed
        assert fixed.count(' width="400"') == 1
