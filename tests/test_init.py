"""Tests for brandx init command (U10).

Covers (from plan):
- With no config, init writes a fully-commented full-palette file whose keys
  and comments match the defaults source (R11, R12).
- Run again, it refuses to overwrite (install AE2).
- The target directory is created when absent.
"""

import pytest

from brandx.config.defaults import DEFAULTS
from brandx.initcmd import generate_init_yaml, run_init


def _all_leaf_entries(node: dict, path: str = "") -> list[tuple[str, dict]]:
    leaves = []
    for k, v in node.items():
        p = f"{path}.{k}" if path else k
        if isinstance(v, dict) and "value" in v and "comment" in v:
            leaves.append((p, v))
        elif isinstance(v, dict):
            leaves.extend(_all_leaf_entries(v, p))
    return leaves


class TestGenerateInitYaml:
    def test_yaml_is_non_empty_string(self):
        yaml = generate_init_yaml()
        assert isinstance(yaml, str)
        assert len(yaml) > 100

    def test_yaml_contains_generated_header(self):
        yaml = generate_init_yaml()
        assert "brandx brand configuration" in yaml

    def test_all_leaf_keys_present(self):
        yaml = generate_init_yaml()
        leaves = _all_leaf_entries(DEFAULTS)
        for _, entry in leaves:
            comment = entry["comment"].split(".")[0]
            assert comment[:20] in yaml, f"Comment {comment!r} not found in generated YAML"

    def test_all_block_keys_present(self):
        yaml = generate_init_yaml()
        for block_key in DEFAULTS:
            assert f"{block_key}:" in yaml

    def test_comments_present(self):
        yaml = generate_init_yaml()
        assert "#" in yaml

    def test_valid_yaml_parseable(self):
        import yaml as pyyaml
        yaml_str = generate_init_yaml()
        parsed = pyyaml.safe_load(yaml_str)
        assert isinstance(parsed, dict)

    def test_colours_block_in_output(self):
        yaml = generate_init_yaml()
        assert "colours:" in yaml
        assert "primary:" in yaml


class TestRunInit:
    def test_writes_file_at_target_path(self, tmp_path):
        target = tmp_path / "brand.yaml"
        result = run_init(target_path=target)
        assert result == target
        assert target.is_file()
        assert len(target.read_text()) > 0

    def test_creates_parent_directory(self, tmp_path):
        target = tmp_path / "nested" / "config" / "brand.yaml"
        run_init(target_path=target)
        assert target.is_file()

    def test_refuses_to_overwrite_without_force(self, tmp_path):
        target = tmp_path / "brand.yaml"
        target.write_text("existing content", encoding="utf-8")
        with pytest.raises(SystemExit, match="already exists"):
            run_init(target_path=target)
        # Existing content preserved
        assert target.read_text() == "existing content"

    def test_overwrites_with_force(self, tmp_path):
        target = tmp_path / "brand.yaml"
        target.write_text("old content", encoding="utf-8")
        run_init(force=True, target_path=target)
        content = target.read_text()
        assert "brandx brand configuration" in content

    def test_written_file_is_valid_yaml(self, tmp_path):
        import yaml as pyyaml
        target = tmp_path / "brand.yaml"
        run_init(target_path=target)
        parsed = pyyaml.safe_load(target.read_text())
        assert isinstance(parsed, dict)

    def test_written_file_contains_colours_primary(self, tmp_path):
        import yaml as pyyaml
        target = tmp_path / "brand.yaml"
        run_init(target_path=target)
        parsed = pyyaml.safe_load(target.read_text())
        assert "colours" in parsed
        assert "primary" in parsed["colours"]
