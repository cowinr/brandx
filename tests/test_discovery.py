"""Tests for config discovery and loading (U3).

Covers (from plan):
- --brand wins over BRANDX_CONFIG which wins over the default path.
- Missing file yields an empty layer and no error.
- Malformed YAML raises a clear error.
- An unknown key warns but still loads.
- Source label reflects the discovery source.

identity-config AE6, R4, R5.
"""

import os
import textwrap
import pytest

from brandx.config.discovery import load_home_config, default_config_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp_path, content: str, name: str = "brand.yaml"):
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# Source precedence
# ---------------------------------------------------------------------------

class TestPrecedence:
    def test_explicit_path_wins_over_env(self, tmp_path, monkeypatch):
        explicit = _write(tmp_path, """\
            identity:
              name: Explicit Brand
        """, "explicit.yaml")
        env_file = _write(tmp_path, """\
            identity:
              name: Env Brand
        """, "env.yaml")
        monkeypatch.setenv("BRANDX_CONFIG", env_file)
        config, source = load_home_config(explicit_path=explicit)
        assert config["identity"]["name"] == "Explicit Brand"
        assert "explicit.yaml" in source

    def test_env_wins_over_default(self, tmp_path, monkeypatch):
        env_file = _write(tmp_path, """\
            identity:
              name: Env Brand
        """)
        monkeypatch.setenv("BRANDX_CONFIG", env_file)
        monkeypatch.delenv("BRANDX_CONFIG", raising=False)
        monkeypatch.setenv("BRANDX_CONFIG", env_file)
        # Patch default path to something non-existent
        monkeypatch.setattr(
            "brandx.config.discovery._default_config_path",
            lambda: tmp_path / "nonexistent.yaml",
        )
        config, source = load_home_config()
        assert config["identity"]["name"] == "Env Brand"
        assert "BRANDX_CONFIG" in source

    def test_default_path_used_when_no_override(self, tmp_path, monkeypatch):
        default_file = tmp_path / "brand.yaml"
        default_file.write_text("identity:\n  role: Default Role\n", encoding="utf-8")
        monkeypatch.delenv("BRANDX_CONFIG", raising=False)
        monkeypatch.setattr(
            "brandx.config.discovery._default_config_path",
            lambda: default_file,
        )
        config, source = load_home_config()
        assert config["identity"]["role"] == "Default Role"


# ---------------------------------------------------------------------------
# Missing file behaviour
# ---------------------------------------------------------------------------

class TestMissingFile:
    def test_missing_default_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.delenv("BRANDX_CONFIG", raising=False)
        monkeypatch.setattr(
            "brandx.config.discovery._default_config_path",
            lambda: tmp_path / "nonexistent.yaml",
        )
        config, _ = load_home_config()
        assert config == {}

    def test_missing_env_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BRANDX_CONFIG", str(tmp_path / "missing.yaml"))
        config, _ = load_home_config()
        assert config == {}

    def test_missing_explicit_path_raises(self, tmp_path):
        with pytest.raises(SystemExit, match="not found"):
            load_home_config(explicit_path=str(tmp_path / "missing.yaml"))


# ---------------------------------------------------------------------------
# Malformed YAML
# ---------------------------------------------------------------------------

class TestMalformedYaml:
    def test_malformed_yaml_raises_systemexit(self, tmp_path, monkeypatch):
        bad_file = tmp_path / "brand.yaml"
        bad_file.write_text("identity: [\nbad yaml: :", encoding="utf-8")
        monkeypatch.setattr(
            "brandx.config.discovery._default_config_path",
            lambda: bad_file,
        )
        with pytest.raises(SystemExit, match="malformed YAML"):
            load_home_config()

    def test_malformed_explicit_path_raises(self, tmp_path):
        bad_file = tmp_path / "brand.yaml"
        bad_file.write_text(": broken: [unclosed", encoding="utf-8")
        with pytest.raises(SystemExit, match="malformed YAML"):
            load_home_config(explicit_path=str(bad_file))


# ---------------------------------------------------------------------------
# Unknown keys
# ---------------------------------------------------------------------------

class TestUnknownKeys:
    def test_unknown_key_warns_but_loads(self, tmp_path, monkeypatch, capsys):
        cfg_file = tmp_path / "brand.yaml"
        cfg_file.write_text(
            "identity:\n  name: Known\ncolours:\n  neon_pink: '#ff00ff'\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "brandx.config.discovery._default_config_path",
            lambda: cfg_file,
        )
        config, _ = load_home_config()
        captured = capsys.readouterr()
        assert "neon_pink" in captured.err
        assert config["identity"]["name"] == "Known"


# ---------------------------------------------------------------------------
# Empty / null YAML file
# ---------------------------------------------------------------------------

class TestEmptyYaml:
    def test_empty_yaml_returns_empty_dict(self, tmp_path, monkeypatch):
        empty_file = tmp_path / "brand.yaml"
        empty_file.write_text("", encoding="utf-8")
        monkeypatch.setattr(
            "brandx.config.discovery._default_config_path",
            lambda: empty_file,
        )
        config, _ = load_home_config()
        assert config == {}


# ---------------------------------------------------------------------------
# default_config_path
# ---------------------------------------------------------------------------

class TestDefaultConfigPath:
    def test_returns_path_object(self):
        path = default_config_path()
        assert hasattr(path, "suffix")

    def test_xdg_config_home_respected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        # Re-import so the env var is picked up
        import importlib
        import brandx.config.discovery as disc
        importlib.reload(disc)
        path = disc.default_config_path()
        assert str(tmp_path) in str(path)
