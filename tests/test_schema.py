"""Tests for application defaults and schema (U2).

Covers:
- Every schema key has a default value, a comment, and a purpose (R2, R5).
- The default set validates clean (no warnings, no errors).
- An unknown key is reported by the validator.
- nested_defaults() and flat_defaults() produce consistent output.
"""

import io
import sys
import pytest

from brandx.config.defaults import DEFAULTS, flat_defaults, nested_defaults
from brandx.config.schema import validate_config, known_paths


def _all_leaf_entries(node: dict, path: str = "") -> list[tuple[str, dict]]:
    """Walk DEFAULTS and collect all leaf (key, entry) pairs."""
    leaves = []
    for k, v in node.items():
        p = f"{path}.{k}" if path else k
        if isinstance(v, dict) and "value" in v and "comment" in v:
            leaves.append((p, v))
        elif isinstance(v, dict):
            leaves.extend(_all_leaf_entries(v, p))
    return leaves


class TestDefaults:
    def test_every_key_has_value_comment_purpose(self):
        leaves = _all_leaf_entries(DEFAULTS)
        assert len(leaves) > 0, "DEFAULTS must not be empty"
        for path, entry in leaves:
            assert "value" in entry, f"{path}: missing 'value'"
            assert "comment" in entry, f"{path}: missing 'comment'"
            assert isinstance(entry["comment"], str) and entry["comment"], (
                f"{path}: comment must be a non-empty string"
            )
            assert "purpose" in entry, f"{path}: missing 'purpose'"
            assert isinstance(entry["purpose"], str) and entry["purpose"], (
                f"{path}: purpose must be a non-empty string"
            )

    def test_colours_block_present(self):
        assert "colours" in DEFAULTS

    def test_identity_block_present(self):
        assert "identity" in DEFAULTS

    def test_fonts_block_present(self):
        assert "fonts" in DEFAULTS

    def test_date_block_present(self):
        assert "date" in DEFAULTS

    def test_flat_defaults_non_empty(self):
        flat = flat_defaults()
        assert len(flat) > 0

    def test_flat_defaults_keys_dot_separated(self):
        flat = flat_defaults()
        for key in flat:
            assert "." in key, f"Expected dot-separated key, got: {key!r}"

    def test_nested_defaults_structure(self):
        nd = nested_defaults()
        assert "colours" in nd
        assert isinstance(nd["colours"], dict)
        assert "blue" in nd["colours"]

    def test_nested_and_flat_agree_on_colours_blue(self):
        nd = nested_defaults()
        flat = flat_defaults()
        assert nd["colours"]["blue"] == flat["colours.blue"]

    def test_default_mark_is_monogram(self):
        nd = nested_defaults()
        assert nd["identity"]["mark"] == "monogram"

    def test_default_date_format_is_long_british(self):
        nd = nested_defaults()
        assert nd["date"]["format"] == "long-british"

    def test_all_known_paths_present_in_flat(self):
        flat = flat_defaults()
        paths = known_paths()
        for p in paths:
            assert p in flat, f"Path {p!r} in known_paths() not in flat_defaults()"


class TestSchemaValidation:
    def test_empty_config_validates_clean(self, capsys):
        validate_config({}, source_label="<test>")
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_valid_partial_config_no_warnings(self, capsys):
        validate_config({"colours": {"blue": "#123456"}}, source_label="<test>")
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_unknown_top_level_key_warns(self, capsys):
        validate_config({"nonsense_key": "value"}, source_label="<test>")
        captured = capsys.readouterr()
        assert "unknown" in captured.err.lower()
        assert "nonsense_key" in captured.err

    def test_unknown_nested_key_warns(self, capsys):
        validate_config({"colours": {"neon_pink": "#ff00ff"}}, source_label="<test>")
        captured = capsys.readouterr()
        assert "neon_pink" in captured.err

    def test_non_dict_at_block_raises(self):
        with pytest.raises(SystemExit):
            validate_config({"colours": "not-a-dict"}, source_label="<test>")

    def test_non_dict_root_raises(self):
        with pytest.raises(SystemExit):
            validate_config("not-a-dict", source_label="<test>")  # type: ignore[arg-type]

    def test_source_label_in_warning(self, capsys):
        validate_config({"bad_key": 1}, source_label="my-config.yaml")
        captured = capsys.readouterr()
        assert "my-config.yaml" in captured.err
