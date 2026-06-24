"""Tests for config-reference doc generation (U11).

Covers (from plan):
- The generated reference lists every default key with its purpose (R12).
- A changed default appears in the regenerated reference without hand edits
  (install AE3).
"""

from brandx.config.defaults import DEFAULTS
from brandx.docsgen import generate_reference_markdown, write_reference


def _all_leaf_entries(node: dict, path: str = "") -> list[tuple[str, dict]]:
    leaves = []
    for k, v in node.items():
        p = f"{path}.{k}" if path else k
        if isinstance(v, dict) and "value" in v and "comment" in v:
            leaves.append((p, v))
        elif isinstance(v, dict):
            leaves.extend(_all_leaf_entries(v, p))
    return leaves


class TestGenerateReferenceMarkdown:
    def test_returns_non_empty_string(self):
        md = generate_reference_markdown()
        assert isinstance(md, str)
        assert len(md) > 200

    def test_contains_header(self):
        md = generate_reference_markdown()
        assert "brandx config reference" in md

    def test_contains_generated_note(self):
        md = generate_reference_markdown()
        assert "generated" in md.lower()

    def test_every_key_purpose_present(self):
        md = generate_reference_markdown()
        leaves = _all_leaf_entries(DEFAULTS)
        for path, entry in leaves:
            purpose_fragment = entry["purpose"][:30]
            assert purpose_fragment in md, (
                f"Purpose for {path!r} not found in reference doc"
            )

    def test_all_block_names_present(self):
        md = generate_reference_markdown()
        for block_key in DEFAULTS:
            assert block_key in md

    def test_defaults_values_present(self):
        md = generate_reference_markdown()
        assert "#1c2b39" in md

    def test_regeneration_reflects_runtime_defaults(self, monkeypatch):
        """install AE3: a changed default appears in the regenerated reference."""
        import brandx.config.defaults as defs
        original = defs.DEFAULTS["colours"]["primary"]["value"]
        try:
            defs.DEFAULTS["colours"]["primary"]["value"] = "#abcdef"
            import importlib
            import brandx.docsgen
            importlib.reload(brandx.docsgen)
            from brandx.docsgen import generate_reference_markdown as gen
            md = gen()
            assert "#abcdef" in md
        finally:
            defs.DEFAULTS["colours"]["primary"]["value"] = original


class TestWriteReference:
    def test_writes_file(self, tmp_path):
        out = tmp_path / "config-reference.md"
        write_reference(out)
        assert out.is_file()
        assert len(out.read_text()) > 200

    def test_creates_parent_dirs(self, tmp_path):
        out = tmp_path / "docs" / "config-reference.md"
        write_reference(out)
        assert out.is_file()

    def test_written_content_matches_generate(self, tmp_path):
        out = tmp_path / "config-reference.md"
        write_reference(out)
        md = generate_reference_markdown()
        assert out.read_text() == md
