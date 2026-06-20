"""Config discovery and loading.

Resolves the home brand YAML config using three sources in priority order:

    1. --brand PATH (explicit override; callers pass this as `explicit_path`)
    2. BRANDX_CONFIG environment variable
    3. XDG home location: $XDG_CONFIG_HOME/brandx/brand.yaml (default: ~/.config/brandx/)
       Windows: %APPDATA%\\brandx\\brand.yaml

A missing file at any source returns an empty dict (not an error).
A malformed YAML raises SystemExit with a clear error.
Unknown keys are warned to stderr via validate_config().

Usage:
    from brandx.config.discovery import load_home_config
    config, source = load_home_config(explicit_path="/path/to/brand.yaml")
"""

import os
import sys
from pathlib import Path

import yaml

from brandx.config.schema import validate_config


def _xdg_config_home() -> Path:
    """Return the platform-appropriate config home directory."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "brandx" / "brand.yaml"


def _default_config_path() -> Path:
    return _xdg_config_home()


def _load_yaml(path: Path) -> dict:
    """Parse a YAML file. Returns empty dict for a missing file; raises SystemExit on malformed YAML."""
    if not path.is_file():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        sys.exit(f"Error: malformed YAML in {path}: {exc}")
    if raw is None:
        return {}
    return raw


def load_home_config(explicit_path: str | None = None) -> tuple[dict, str]:
    """Load and return the home brand config and its source label.

    Resolution order (highest wins):
        1. explicit_path (from --brand flag)
        2. BRANDX_CONFIG environment variable
        3. XDG home location

    Returns:
        (config_dict, source_label) where config_dict is {} when no file exists.

    Raises:
        SystemExit: if a located file is malformed YAML.
    """
    if explicit_path is not None:
        path = Path(explicit_path)
        source = str(path)
        raw = _load_yaml(path)
        if not path.is_file():
            sys.exit(f"Error: brand config not found at {path}.")
    elif "BRANDX_CONFIG" in os.environ:
        path = Path(os.environ["BRANDX_CONFIG"])
        source = f"$BRANDX_CONFIG ({path})"
        raw = _load_yaml(path)
    else:
        path = _default_config_path()
        source = str(path)
        raw = _load_yaml(path)

    if raw:
        validate_config(raw, source_label=source)

    return raw, source


def default_config_path() -> Path:
    """Return the default config path (XDG home location)."""
    return _default_config_path()
