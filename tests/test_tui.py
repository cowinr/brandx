"""Tests for the in-place TUI (U7).

The terminal driver (raw mode, alternate screen) is verified manually; these
tests cover the testable surface: single-key dispatch, brand cycling, the
screen-render string, and the TTY-gated fallback.
"""

from __future__ import annotations

from brandx.config.resolver import resolve
from brandx.session import SessionState
from brandx.tui import TuiSession, is_supported

SAMPLE_MD = "---\ntitle: Doc\n---\n\n# Doc\n\nBody.\n"


def _ask_none(_prompt):
    return ""


def _ask(value):
    return lambda _prompt: value


def test_dispatch_o_toggles_output():
    tui = TuiSession(SessionState())
    assert tui.dispatch("o", _ask_none) is False
    assert tui.state.email is True
    tui.dispatch("o", _ask_none)
    assert tui.state.email is False


def test_dispatch_m_cycles_mark():
    tui = TuiSession(SessionState())
    tui.dispatch("m", _ask_none)
    assert tui.state.mark == "avatar"
    tui.dispatch("m", _ask_none)
    assert tui.state.mark == "monogram"


def test_dispatch_b_cycles_discovered_brands():
    tui = TuiSession(SessionState())
    tui.brands = [("default", None), ("hansard.yaml", "/x/hansard.yaml")]
    tui.dispatch("b", _ask_none)
    assert tui.state.brand_path == "/x/hansard.yaml"
    tui.dispatch("b", _ask_none)
    assert tui.state.brand_path is None


def test_dispatch_d_cycles_dest_and_prompts_for_file():
    tui = TuiSession(SessionState())
    tui.dispatch("d", _ask_none)
    assert tui.state.destination == "clipboard"
    tui.dispatch("d", _ask("/tmp/out.html"))  # lands on file → prompts for path
    assert tui.state.destination == "file"
    assert str(tui.state.dest_path) == "/tmp/out.html"


def test_dispatch_d_to_file_cancelled_reverts_to_preview():
    tui = TuiSession(SessionState(destination="clipboard"))
    tui.dispatch("d", _ask_none)  # → file, but blank path cancels
    assert tui.state.destination == "preview"
    assert tui.state.dest_path is None


def test_dispatch_f_focuses_file(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    tui = TuiSession(SessionState())
    tui.dispatch("f", _ask(str(md)))
    assert tui.state.focused_file == md


def test_dispatch_s_sets_and_clears_overrides():
    tui = TuiSession(SessionState())
    tui.dispatch("s", _ask("colours.accent=#e63946"))
    assert tui.state.overrides == {"colours.accent": "#e63946"}
    tui.dispatch("s", _ask_none)  # blank clears all
    assert tui.state.overrides == {}


def test_dispatch_x_resets_keeping_file(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    tui = TuiSession(SessionState(focused_file=md, email=True, mark="avatar"))
    tui.dispatch("x", _ask_none)
    assert tui.state.focused_file == md
    assert tui.state.email is False
    assert tui.state.mark is None


def test_dispatch_q_stops():
    tui = TuiSession(SessionState())
    assert tui.dispatch("q", _ask_none) is True
    assert tui.dispatch("\x03", _ask_none) is True  # Ctrl-C


def test_render_without_focus_sets_status():
    tui = TuiSession(SessionState())
    tui.dispatch("r", _ask_none)
    assert "no file focused" in tui.status


def test_render_to_file_writes(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    out = tmp_path / "out.html"
    tui = TuiSession(SessionState(focused_file=md, destination="file", dest_path=out))
    tui.dispatch("r", _ask_none)
    assert out.is_file()
    assert "written" in tui.status


def test_render_screen_shows_options_and_keys(tmp_path, monkeypatch):
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    fake_cfg = resolve(home_config={"identity": {"mark": "monogram"}}, os_name_fn=lambda: "Test User")
    monkeypatch.setattr("brandx.tui.resolve_for_state", lambda state: (fake_cfg, "defaults"))

    screen = TuiSession(SessionState(focused_file=md)).render_screen()
    assert "doc.md" in screen
    assert "document" in screen
    assert "r render" in screen
    assert "q quit" in screen
    for key in ("o", "m", "b", "d", "s"):
        assert key in screen


def test_is_supported_false_without_tty():
    # Under pytest stdin/stdout are captured, not TTYs.
    assert is_supported() is False
