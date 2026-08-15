"""Tests for the cascade resolver (U4).

Covers (from plan):
- Frontmatter key overrides home config (identity-config AE1).
- Nested colour key (accent) set in frontmatter overrides only that entry (KTD11).
- No name + mocked OS full name yields that name and its initials (identity-config AE3).
- Username-only OS account yields graceful fallback, not raw username (identity-config AE4).
- Absent email avatar falls back to main avatar (identity-config AE5).
- Flag overrides frontmatter (R1).
- Complete merge: defaults always provide a full config (R2).
"""

import pytest

from brandx.config.defaults import nested_defaults
from brandx.config.resolver import (
    _deep_merge,
    _initials,
    _title_case_username,
    resolve,
)

# ---------------------------------------------------------------------------
# Deep merge
# ---------------------------------------------------------------------------

class TestDeepMerge:
    def test_scalar_override(self):
        result = _deep_merge({"a": 1}, {"a": 2})
        assert result["a"] == 2

    def test_new_key_added(self):
        result = _deep_merge({"a": 1}, {"b": 2})
        assert result["a"] == 1
        assert result["b"] == 2

    def test_nested_partial_override(self):
        base = {"colours": {"primary": "#000", "accent": "#aaa"}}
        override = {"colours": {"accent": "#bbb"}}
        result = _deep_merge(base, override)
        assert result["colours"]["primary"] == "#000"
        assert result["colours"]["accent"] == "#bbb"

    def test_base_not_mutated(self):
        base = {"colours": {"primary": "#000"}}
        _deep_merge(base, {"colours": {"primary": "#fff"}})
        assert base["colours"]["primary"] == "#000"


# ---------------------------------------------------------------------------
# Initials derivation
# ---------------------------------------------------------------------------

class TestInitials:
    def test_two_name_parts(self):
        assert _initials("Richard Cowin") == "RC"

    def test_single_name(self):
        assert _initials("Alice") == "A"

    def test_three_parts_returns_two(self):
        assert _initials("John Paul Smith") == "JP"

    def test_empty_string_returns_placeholder(self):
        assert _initials("") == "?"

    def test_whitespace_only(self):
        assert _initials("   ") == "?"


# ---------------------------------------------------------------------------
# Username title-casing
# ---------------------------------------------------------------------------

class TestTitleCaseUsername:
    def test_simple_username(self):
        assert _title_case_username("jsmith") == "Jsmith"

    def test_dot_separated(self):
        assert _title_case_username("john.smith") == "John Smith"

    def test_underscore_separated(self):
        assert _title_case_username("john_smith") == "John Smith"

    def test_hyphen_separated(self):
        assert _title_case_username("john-smith") == "John Smith"


# ---------------------------------------------------------------------------
# Cascade resolution
# ---------------------------------------------------------------------------

class TestResolve:
    def test_defaults_produce_complete_config(self):
        """R2: resolution with no layers beyond defaults yields a complete config."""
        cfg = resolve()
        assert cfg.colours["primary"]
        assert cfg.fonts["font"]
        assert cfg.date_format

    def test_home_config_overrides_default(self):
        cfg = resolve(home_config={"identity": {"role": "Senior Architect"}})
        assert cfg.role == "Senior Architect"

    def test_frontmatter_overrides_home_config(self):
        """identity-config AE1: frontmatter beats home config."""
        home = {"identity": {"name": "Home Name"}}
        fm = {"identity": {"name": "FM Name"}}
        cfg = resolve(home_config=home, frontmatter=fm)
        assert cfg.name == "FM Name"

    def test_nested_colour_partial_override(self):
        """KTD11 / identity-config AE1: partial palette override leaves rest intact."""
        defaults = nested_defaults()
        original_primary = defaults["colours"]["primary"]
        fm = {"colours": {"accent": "#cafeba"}}
        cfg = resolve(frontmatter=fm)
        assert cfg.colours["accent"] == "#cafeba"
        assert cfg.colours["primary"] == original_primary

    def test_flag_overrides_frontmatter(self):
        """R1: flag (top cascade layer) beats frontmatter."""
        fm = {"identity": {"role": "FM Role"}}
        flags = {"identity.role": "Flag Role"}
        cfg = resolve(frontmatter=fm, flags=flags)
        assert cfg.role == "Flag Role"

    def test_os_full_name_used_when_no_name(self):
        """identity-config AE3: OS full name used when name absent at every layer."""
        cfg = resolve(os_name_fn=lambda: "OS Full Name")
        assert cfg.name == "OS Full Name"
        assert cfg.initials == "OF"

    def test_username_fallback_title_cased(self):
        """identity-config AE4: username-only OS exposes title-cased display name."""
        cfg = resolve(os_name_fn=lambda: "Jsmith")
        assert cfg.name == "Jsmith"
        assert cfg.initials == "J"

    def test_name_from_config_used_over_os(self):
        cfg = resolve(
            home_config={"identity": {"name": "Config Name"}},
            os_name_fn=lambda: "OS Name",
        )
        assert cfg.name == "Config Name"

    def test_absent_email_avatar_falls_back_to_avatar(self):
        """identity-config AE5: absent email avatar resolves to main avatar."""
        cfg = resolve(home_config={"identity": {"avatar": "/tmp/avatar.png"}})
        assert cfg.avatar is not None
        assert cfg.avatar_email == cfg.avatar

    def test_explicit_email_avatar_not_overridden(self):
        home = {
            "identity": {
                "avatar": "/tmp/main.png",
                "avatar_email": "/tmp/email.png",
            }
        }
        cfg = resolve(home_config=home)
        assert str(cfg.avatar) == "/tmp/main.png"
        assert str(cfg.avatar_email) == "/tmp/email.png"

    def test_immutable_colours(self):
        cfg = resolve()
        with pytest.raises((AttributeError, TypeError)):
            cfg.colours["primary"] = "hacked"  # type: ignore[index]

    def test_immutable_config_itself(self):
        cfg = resolve()
        with pytest.raises(AttributeError):
            cfg.name = "hacked"  # type: ignore[misc]

    def test_monogram_default(self):
        cfg = resolve(home_config={"identity": {"name": "Jane Doe"}})
        assert cfg.mark == "monogram"
        assert cfg.initials == "JD"

    def test_dotted_flag_nested_colours(self):
        cfg = resolve(flags={"colours.primary": "#abcdef"})
        assert cfg.colours["primary"] == "#abcdef"

    def test_flag_unknown_path_skipped(self):
        cfg = resolve(flags={"colours.nonexistent_key": "value"})
        assert "nonexistent_key" not in cfg.colours

    def test_scalar_date_frontmatter_does_not_crash(self):
        """A top-level `date` (e.g. datetime.date from pyyaml) must not clobber
        the date block and crash resolution; it falls back to the default format."""
        import datetime

        cfg = resolve(frontmatter={"date": datetime.date(2026, 6, 20)})
        assert cfg.date_format == "long-british"

    def test_scalar_block_layers_are_ignored(self):
        """A scalar supplied where a block is expected is ignored, not fatal."""
        cfg = resolve(frontmatter={"colours": "not-a-block", "identity": 42})
        # Defaults still apply; resolution completes.
        assert cfg.colours["primary"] == "#1c2b39"
        assert cfg.name  # a name was still derived


# ---------------------------------------------------------------------------
# Letterhead toggle
# ---------------------------------------------------------------------------

class TestLetterheadToggle:
    """The letterhead banner is opt-in: off unless a layer turns it on."""

    def test_off_by_default(self):
        assert resolve().letterhead is False

    def test_home_config_turns_it_on(self):
        cfg = resolve(home_config={"identity": {"letterhead": True}})
        assert cfg.letterhead is True

    def test_frontmatter_overrides_home_config(self):
        cfg = resolve(
            home_config={"identity": {"letterhead": True}},
            frontmatter={"identity": {"letterhead": False}},
        )
        assert cfg.letterhead is False

    def test_flag_overrides_frontmatter(self):
        cfg = resolve(
            frontmatter={"identity": {"letterhead": False}},
            flags={"identity.letterhead": True},
        )
        assert cfg.letterhead is True

    @pytest.mark.parametrize(
        "token,expected",
        [
            ("true", True), ("True", True), ("yes", True), ("on", True), ("1", True),
            ("false", False), ("False", False), ("no", False), ("off", False), ("0", False),
            (" TRUE ", True), (" off ", False),
        ],
    )
    def test_set_flag_strings_are_coerced(self, token, expected):
        """--set yields strings, so "false" must not read as truthy."""
        cfg = resolve(flags={"identity.letterhead": token})
        assert cfg.letterhead is expected

    def test_unparseable_string_falls_back_to_default(self):
        cfg = resolve(flags={"identity.letterhead": "maybe"})
        assert cfg.letterhead is False

    def test_scalar_identity_block_does_not_crash(self):
        """A scalar where the identity block belongs leaves the toggle at its default."""
        cfg = resolve(frontmatter={"identity": 42})
        assert cfg.letterhead is False


# ---------------------------------------------------------------------------
# Diagrams block coercion
# ---------------------------------------------------------------------------

class TestDiagramsCoercion:
    """`--set` yields strings; the diagrams block is typed, so it must be coerced.

    Before this, `--set diagrams.enabled=false` read as truthy and did nothing,
    and a string scale or max_width raised TypeError inside the email renderer.
    """

    def test_defaults_keep_their_types(self):
        diagrams = resolve().diagrams
        assert diagrams["enabled"] is True
        assert diagrams["scale"] == 2
        assert diagrams["max_width"] == 912

    @pytest.mark.parametrize(
        "token,expected",
        [("false", False), ("no", False), ("off", False), ("0", False),
         ("true", True), ("yes", True), ("on", True), ("1", True)],
    )
    def test_enabled_string_is_coerced(self, token, expected):
        assert resolve(flags={"diagrams.enabled": token}).diagrams["enabled"] is expected

    def test_enabled_unparseable_falls_back_to_on(self):
        assert resolve(flags={"diagrams.enabled": "junk"}).diagrams["enabled"] is True

    @pytest.mark.parametrize("token,expected", [("1", 1), ("3", 3), ("1.5", 1.5)])
    def test_scale_string_is_coerced(self, token, expected):
        assert resolve(flags={"diagrams.scale": token}).diagrams["scale"] == expected

    def test_scale_survives_arithmetic(self):
        """The email renderer divides by scale; a string would raise TypeError."""
        assert 1000 / resolve(flags={"diagrams.scale": "1"}).diagrams["scale"] == 1000

    def test_max_width_survives_comparison(self):
        """The email renderer compares against max_width; a string would raise."""
        assert 1000 > resolve(flags={"diagrams.max_width": "600"}).diagrams["max_width"]

    @pytest.mark.parametrize("token", ["x", "", "  "])
    def test_unparseable_numbers_fall_back_to_the_default(self, token):
        cfg = resolve(flags={"diagrams.scale": token, "diagrams.max_width": token})
        assert cfg.diagrams["scale"] == 2
        assert cfg.diagrams["max_width"] == 912

    def test_yaml_booleans_and_numbers_pass_through(self):
        cfg = resolve(home_config={"diagrams": {"enabled": False, "scale": 3}})
        assert cfg.diagrams["enabled"] is False
        assert cfg.diagrams["scale"] == 3
