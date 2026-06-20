"""Brand config schema — key set, validation, and warnings.

Knows which keys are valid (derived from DEFAULTS) and validates a loaded
config dict against that set. Unknown keys produce a stderr warning; a
malformed structure (non-dict at a branch point) raises SystemExit.

Usage:
    from brandx.config.schema import validate_config
    validate_config(loaded_dict, source_label="~/.config/brandx/brand.yaml")
"""

import sys
from typing import Any

from brandx.config.defaults import DEFAULTS


def _known_paths(node: dict, prefix: str = "") -> set[str]:
    """Return the full set of known dot-separated key paths from DEFAULTS."""
    paths: set[str] = set()
    for k, v in node.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict) and "value" in v and "comment" in v:
            paths.add(path)
        elif isinstance(v, dict):
            paths.update(_known_paths(v, path))
    return paths


_KNOWN_PATHS: frozenset[str] = frozenset(_known_paths(DEFAULTS))

# The top-level block keys (identity, colours, fonts, date)
_KNOWN_BLOCKS: frozenset[str] = frozenset(DEFAULTS.keys())


def _walk_config(node: Any, schema_node: dict, path: str, source: str) -> list[str]:
    """Recursively walk a loaded config and collect warnings for unknown keys.

    Returns a list of warning strings. Raises SystemExit on structural errors
    (e.g. a non-dict where a mapping is expected).
    """
    warnings: list[str] = []

    if not isinstance(node, dict):
        sys.exit(
            f"Error: expected a mapping at '{path}' in {source}, "
            f"got {type(node).__name__}."
        )

    for key, value in node.items():
        child_path = f"{path}.{key}" if path else key
        schema_child = schema_node.get(key)

        if schema_child is None:
            warnings.append(
                f"Warning: unknown brand key '{child_path}' in {source} — ignored."
            )
            continue

        if isinstance(schema_child, dict) and "value" not in schema_child:
            # This is a nested block (colours, fonts, etc.)
            warnings.extend(_walk_config(value, schema_child, child_path, source))

    return warnings


def validate_config(config: dict, source_label: str = "<config>") -> None:
    """Validate a loaded config dict against the schema.

    Emits stderr warnings for unknown keys. Raises SystemExit on structural
    errors (non-dict where a mapping is expected at a known branch point).

    Does not raise for missing keys — the cascade resolver fills gaps from
    defaults.
    """
    if not isinstance(config, dict):
        sys.exit(
            f"Error: brand config in {source_label} must be a YAML mapping, "
            f"got {type(config).__name__}."
        )

    warnings = _walk_config(config, DEFAULTS, "", source_label)
    for warning in warnings:
        print(warning, file=sys.stderr)


def known_paths() -> frozenset[str]:
    """Return the frozenset of all valid dot-separated config key paths."""
    return _KNOWN_PATHS


def known_blocks() -> frozenset[str]:
    """Return the frozenset of valid top-level block names."""
    return _KNOWN_BLOCKS
