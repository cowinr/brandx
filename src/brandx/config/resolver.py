"""Cascade resolver — deep-merge four config layers and produce an immutable resolved config.

Resolution order (highest wins):
    1. Application defaults
    2. Home YAML config (from discovery)
    3. Document frontmatter (nested YAML)
    4. Invocation flags (dotted key overrides)

After merging, the resolver derives:
    - initials and monogram from the resolved name
    - the name from the OS account when unset at every layer
    - a graceful fallback when the OS exposes only a username (title-cased; initials derived)
    - email avatar falls back to the main avatar when absent

Returns an immutable (frozen) ResolvedConfig object threaded through the renderers.
No module-global brand state.

Usage:
    from brandx.config.resolver import resolve
    cfg = resolve(home_config={...}, frontmatter={...}, flags={})
    cfg.name, cfg.colours["primary"], cfg.fonts["font"]
"""

from __future__ import annotations

import pwd
import re
import sys
from pathlib import Path
from types import MappingProxyType
from typing import Any

from brandx.config.defaults import nested_defaults


# ---------------------------------------------------------------------------
# Deep merge
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """Return a new dict that is base deep-merged with override.

    Nested dicts are merged recursively; scalars in override win. A scalar in
    override does not replace a nested block in base: keeping the block prevents
    a document's top-level `date:` (parsed as a datetime.date) from clobbering
    the `date` config block. Neither argument is mutated.
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict):
            if isinstance(value, dict):
                result[key] = _deep_merge(result[key], value)
            # A scalar cannot replace a nested block; keep the base block.
        else:
            result[key] = value
    return result


def _apply_dotted_flags(config: dict, flags: dict[str, Any]) -> dict:
    """Apply dotted-key flag overrides into a nested config dict.

    e.g. {"colours.primary": "#123"} sets config["colours"]["primary"] = "#123".
    A flag whose path does not resolve to a pre-existing key is silently skipped;
    the CLI validates flag names earlier and this prevents pollution of the config.
    """
    result = dict(config)
    for dotted_key, value in flags.items():
        parts = dotted_key.split(".")
        node = result
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node = None
                break
            node = node[part]
        if node is None:
            continue
        if parts[-1] not in node:
            continue
        node[parts[-1]] = value
    return result


# ---------------------------------------------------------------------------
# OS name lookup
# ---------------------------------------------------------------------------

def _resolve_os_name() -> str:
    """Return a display name derived from the OS account.

    Priority:
        1. OS full name from GECOS / Directory Services (may be absent)
        2. Title-cased login username as fallback
    """
    import os

    if sys.platform != "win32":
        try:
            entry = pwd.getpwuid(os.getuid())
            gecos = (entry.pw_gecos or "").split(",")[0].strip()
            if gecos:
                return gecos
            username = entry.pw_name
        except Exception:
            username = os.environ.get("USER", os.environ.get("LOGNAME", "user"))
    else:
        username = os.environ.get("USERNAME", "user")

    # Graceful fallback: title-case the username (e.g. "jsmith" → "Jsmith")
    return _title_case_username(username)


def _title_case_username(username: str) -> str:
    """Convert a login username to a display-friendly form.

    Splits on dots, underscores, and hyphens then title-cases each part.
    e.g. "john.smith" → "John Smith", "jsmith" → "Jsmith"
    """
    parts = re.split(r"[._\-]", username)
    return " ".join(p.capitalize() for p in parts if p)


# ---------------------------------------------------------------------------
# Initials derivation
# ---------------------------------------------------------------------------

def _initials(name: str) -> str:
    """Return a two-letter (max) monogram from a display name.

    e.g. "Richard Cowin" → "RC", "Alice" → "A", "" → "?"
    Matches the prototype's _initials() logic.
    """
    parts = [p for p in name.split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


# ---------------------------------------------------------------------------
# ResolvedConfig
# ---------------------------------------------------------------------------

class ResolvedConfig:
    """Immutable resolved brand configuration.

    Attributes are the resolved values after all four cascade layers are merged
    and derivations are applied. Access nested values via the .colours, .fonts,
    .date, and .identity mapping attributes, or via helper properties.
    """

    __slots__ = (
        "_data",
        "name",
        "role",
        "initials",
        "mark",
        "avatar",
        "avatar_email",
        "colours",
        "fonts",
        "date_format",
    )

    def __init__(self, merged: dict) -> None:
        # Guard against a layer supplying a scalar where a block is expected.
        # For example, a document's top-level `date:` frontmatter (parsed by
        # pyyaml as a datetime.date) deep-merges over the `date` brand block;
        # the CLI strips document-meta keys, but the resolver stays robust too.
        def _block(key: str) -> dict:
            value = merged.get(key, {})
            return value if isinstance(value, dict) else {}

        identity = _block("identity")
        colours = _block("colours")
        fonts = _block("fonts")
        date_block = _block("date")

        name: str = (identity.get("name") or "").strip()
        if not name:
            name = _resolve_os_name()

        object.__setattr__(self, "_data", merged)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "role", (identity.get("role") or "").strip())
        object.__setattr__(self, "initials", _initials(name))
        object.__setattr__(self, "mark", (identity.get("mark") or "monogram").lower())

        raw_avatar = identity.get("avatar")
        object.__setattr__(self, "avatar", Path(raw_avatar) if raw_avatar else None)

        raw_avatar_email = identity.get("avatar_email")
        if raw_avatar_email:
            object.__setattr__(self, "avatar_email", Path(raw_avatar_email))
        else:
            # Fall back to the main avatar
            object.__setattr__(self, "avatar_email", object.__getattribute__(self, "avatar"))

        object.__setattr__(self, "colours", MappingProxyType(colours))
        object.__setattr__(self, "fonts", MappingProxyType(fonts))
        object.__setattr__(
            self,
            "date_format",
            (date_block.get("format") or "long-british"),
        )

    def __setattr__(self, _name, _value):
        raise AttributeError("ResolvedConfig is immutable.")

    def __repr__(self) -> str:
        return f"ResolvedConfig(name={self.name!r}, mark={self.mark!r})"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve(
    home_config: dict | None = None,
    frontmatter: dict | None = None,
    flags: dict[str, Any] | None = None,
    os_name_fn=None,
) -> ResolvedConfig:
    """Resolve the four cascade layers into an immutable ResolvedConfig.

    Args:
        home_config: Loaded home YAML config dict (from discovery.load_home_config).
        frontmatter: Nested YAML parsed from the document frontmatter.
        flags: Dotted-key overrides from invocation flags (e.g. {"colours.primary": "#123"}).
        os_name_fn: Optional callable returning the OS display name (for testing).

    Returns:
        An immutable ResolvedConfig.
    """
    merged = nested_defaults()
    if home_config:
        merged = _deep_merge(merged, home_config)
    if frontmatter:
        merged = _deep_merge(merged, frontmatter)
    if flags:
        merged = _apply_dotted_flags(merged, flags)

    if os_name_fn is not None:
        import brandx.config.resolver as _self_mod
        original = _self_mod._resolve_os_name
        _self_mod._resolve_os_name = os_name_fn
        try:
            cfg = ResolvedConfig(merged)
        finally:
            _self_mod._resolve_os_name = original
        return cfg

    return ResolvedConfig(merged)
