"""Tests for the interactive session (U2 state/panel, U4 command loop).

Covers:
    - SessionState.flags() mirrors the one-shot flag build.
    - render_panel reflects defaults, overrides (AE1), and destinations.
    - do_* commands mutate state; bad args leave state unchanged and continue.
    - reset returns options to defaults (AE3); a bad brand path never crashes
      the re-resolve.
    - render re-parses the focused file each time (AE2), surfaces the
      clipboard-unsupported message, and prompts when no file is focused.
    - run_session focuses a file or reports a missing one.
"""

from __future__ import annotations

import brandx.clipboard as _clipboard_mod
import brandx.output as _output_mod
from brandx.config.resolver import resolve
from brandx.session import SessionCmd, SessionState, render_panel, run_session

SAMPLE_MD = "---\ntitle: Doc\n---\n\n# Doc\n\nBody.\n"


def _cfg(**kwargs):
    """Resolve a config with a deterministic OS name for panel assertions."""
    kwargs.setdefault("os_name_fn", lambda: "Test User")
    return resolve(**kwargs)


# ---------------------------------------------------------------------------
# U2 — SessionState and render_panel
# ---------------------------------------------------------------------------

def test_flags_mirror_one_shot_build():
    state = SessionState(mark="avatar", overrides={"colours.blue": "#111111"})
    assert state.flags() == {"colours.blue": "#111111", "identity.mark": "avatar"}


def test_flags_empty_without_mark_or_overrides():
    assert SessionState().flags() == {}


def test_panel_unfocused_shows_defaults():
    panel = render_panel(SessionState(), _cfg(), "defaults")
    assert "(none" in panel          # no file focused
    assert "document" in panel       # default output
    assert "monogram" in panel       # default mark
    assert "defaults" in panel       # brand label
    assert "(none)" in panel         # no overrides


def test_panel_reflects_override(tmp_path):
    """AE1: a session with colours.accent overridden shows the new value."""
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    state = SessionState(focused_file=md, overrides={"colours.accent": "#e63946"})
    cfg = _cfg(flags=state.flags())
    panel = render_panel(state, cfg, "defaults")
    assert "#e63946" in panel
    assert cfg.colours["accent"] == "#e63946"


def test_panel_file_destination_shows_path(tmp_path):
    state = SessionState(destination="file", dest_path=tmp_path / "out.html")
    panel = render_panel(state, _cfg(), "defaults")
    assert "out.html" in panel


# ---------------------------------------------------------------------------
# U4 — command loop
# ---------------------------------------------------------------------------

def _focused(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    return md, SessionCmd(SessionState(focused_file=md))


def test_output_and_dest_mutate_state(tmp_path):
    _, c = _focused(tmp_path)
    c.onecmd("output email")
    c.onecmd("dest clipboard")
    assert c.state.email is True
    assert c.state.destination == "clipboard"


def test_set_and_unset_overrides(tmp_path):
    _, c = _focused(tmp_path)
    c.onecmd("set colours.accent=#e63946")
    c.onecmd("set colours.blue=#111111")
    assert c.state.overrides == {"colours.accent": "#e63946", "colours.blue": "#111111"}
    c.onecmd("unset colours.accent")
    assert c.state.overrides == {"colours.blue": "#111111"}


def test_reset_all_keeps_file(tmp_path):
    """AE3: reset returns options to defaults while keeping the focused file."""
    md, c = _focused(tmp_path)
    c.onecmd("output email")
    c.onecmd("mark avatar")
    c.onecmd("set colours.accent=#e63946")
    c.onecmd("reset all")
    assert c.state.focused_file == md
    assert c.state.email is False
    assert c.state.mark is None
    assert c.state.overrides == {}


def test_focus_missing_file_leaves_state(tmp_path, capsys):
    md, c = _focused(tmp_path)
    c.onecmd("focus does-not-exist.md")
    assert c.state.focused_file == md
    assert "not found" in capsys.readouterr().out.lower()


def test_bad_brand_path_continues_and_resolve_survives(tmp_path, capsys):
    """A bad brand path is rejected and the re-resolve does not raise SystemExit."""
    _, c = _focused(tmp_path)
    c.onecmd("brand /no/such/brand.yaml")
    assert c.state.brand_path is None
    assert "not found" in capsys.readouterr().out.lower()
    # The panel re-resolve must not crash on the rejected path.
    cfg, label = c._resolve()
    assert cfg is not None


def test_dest_file_without_path_is_rejected(tmp_path, capsys):
    _, c = _focused(tmp_path)
    c.onecmd("dest file")
    assert "path" in capsys.readouterr().out.lower()
    assert c.state.destination == "preview"


def test_render_without_focus_prompts(capsys):
    c = SessionCmd(SessionState())
    c.onecmd("render")
    assert "No file focused" in capsys.readouterr().out


def test_render_email_to_clipboard(tmp_path, monkeypatch):
    """Happy path: email output to clipboard sends the email surface."""
    _, c = _focused(tmp_path)
    captured = {}

    def fake_copy(html):
        captured["html"] = html
        return True

    monkeypatch.setattr(_clipboard_mod, "copy_html", fake_copy)
    c.onecmd("output email")
    c.onecmd("dest clipboard")
    c.onecmd("render")
    assert 'role="presentation"' in captured["html"]  # email surface
    assert "<style" not in captured["html"]


def test_render_picks_up_external_edit(tmp_path):
    """AE2: re-rendering after an external edit reflects the new content."""
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    out = tmp_path / "out.html"
    c = SessionCmd(SessionState(focused_file=md))
    c.onecmd(f"dest file {out}")
    c.onecmd("render")
    assert "Doc" in out.read_text(encoding="utf-8")

    md.write_text("---\ntitle: Doc\n---\n\n# Doc\n\nEdited body marker.\n", encoding="utf-8")
    c.onecmd("render")
    assert "Edited body marker" in out.read_text(encoding="utf-8")


def test_render_clipboard_non_macos_surfaces_message(tmp_path, monkeypatch, capsys):
    _, c = _focused(tmp_path)
    monkeypatch.setattr(_clipboard_mod, "_is_macos", lambda: False)
    c.onecmd("dest clipboard")
    c.onecmd("render")
    assert "macOS-only" in capsys.readouterr().out


def test_quit_and_eof_stop_the_loop(tmp_path):
    _, c = _focused(tmp_path)
    assert c.onecmd("quit") is True
    assert c.onecmd("EOF") is True


def test_full_transcript_reprints_panel(tmp_path, monkeypatch, capsys):
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    opened = []
    monkeypatch.setattr(_output_mod, "_open_in_browser", lambda p: opened.append(p))

    c = SessionCmd(SessionState(focused_file=md))
    c.cmdqueue = ["set colours.accent=#e63946", "render", "quit"]
    c.cmdloop()

    out = capsys.readouterr().out
    assert "brandx · interactive session" in out  # panel printed
    assert "#e63946" in out                        # override shown in panel
    assert len(opened) == 1                        # preview opened once


# ---------------------------------------------------------------------------
# run_session
# ---------------------------------------------------------------------------

def test_run_session_focuses_existing_file(tmp_path, monkeypatch):
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    seen = []
    monkeypatch.setattr(SessionCmd, "cmdloop", lambda self: seen.append(self.state))
    assert run_session(md) == 0
    assert seen[0].focused_file == md


def test_run_session_reports_missing_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(SessionCmd, "cmdloop", lambda self: None)
    assert run_session(tmp_path / "missing.md") == 0
    assert "File not found" in capsys.readouterr().out
