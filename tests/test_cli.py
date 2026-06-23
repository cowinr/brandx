"""Tests for the brandx CLI entry point.

Covers (U1 originals kept intact):
    - --help lists both subcommands.
    - Entry point imports without error.
    - --version.
    - No subcommand exits zero.
    - init --force writes a config.

Covers (U9 — render command):
    - render without destination prints HTML to stdout.
    - render -o FILE writes the expected surface to a file.
    - render --email writes email HTML (no <style>, has role="presentation").
    - render --preview calls the browser-open seam with a temp .html file.
    - render --clipboard on macOS calls the osascript seam and exits 0.
    - render --clipboard on non-macOS prints unsupported message and exits 0.
    - render --brand PATH selects an alternate config (colour appears in output).
    - render --set KEY=VALUE flows into resolved config.
    - render --set malformed (no =) prints error and exits non-zero.
    - Missing input file prints error and exits non-zero.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import brandx.output as _output_mod
import brandx.clipboard as _clipboard_mod
from brandx.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_MD = textwrap.dedent("""\
    ---
    title: Test Doc
    ---

    # Test Doc

    Hello world.
""")


# ---------------------------------------------------------------------------
# U1 originals (subprocess-based; kept unchanged)
# ---------------------------------------------------------------------------

def test_help_lists_subcommands():
    result = subprocess.run(
        [sys.executable, "-m", "brandx.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "init" in result.stdout
    assert "render" in result.stdout


def test_import_without_error():
    import brandx.cli as cli  # noqa: F401
    assert hasattr(cli, "main")


def test_version():
    result = subprocess.run(
        [sys.executable, "-m", "brandx.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_no_subcommand_launches_session_and_exits_zero():
    """Bare `brandx` starts the interactive session; closed stdin (EOF) exits 0."""
    result = subprocess.run(
        [sys.executable, "-m", "brandx.cli"],
        capture_output=True,
        text=True,
        input="",
    )
    assert result.returncode == 0
    assert "interactive session" in result.stdout


def test_init_force_writes_config():
    result = subprocess.run(
        [sys.executable, "-m", "brandx.cli", "init", "--force"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Written:" in result.stderr


# ---------------------------------------------------------------------------
# U9 render tests (main(argv=...) style)
# ---------------------------------------------------------------------------

def test_render_missing_input_file_exits_nonzero(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["render", str(tmp_path / "nonexistent.md")])
    assert exc.value.code != 0
    captured = capsys.readouterr()
    assert "Error" in captured.err


def test_render_stdout_no_destination(tmp_path, capsys):
    """No destination flag → HTML goes to stdout."""
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        main(["render", str(md)])
    assert exc.value.code == 0

    captured = capsys.readouterr()
    assert "<html" in captured.out or "<!DOCTYPE" in captured.out or "<body" in captured.out


def test_render_to_file_document(tmp_path, capsys):
    """render -o FILE writes document HTML with a <style> block."""
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    out = tmp_path / "out.html"

    with pytest.raises(SystemExit) as exc:
        main(["render", str(md), "-o", str(out)])
    assert exc.value.code == 0

    content = out.read_text(encoding="utf-8")
    assert "<style" in content
    # Document surface has no role="presentation" on the outermost wrapper
    # (that's the email surface)


def test_render_to_file_email(tmp_path, capsys):
    """render --email -o FILE writes email HTML (no <style>; has role=presentation)."""
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    out = tmp_path / "email.html"

    with pytest.raises(SystemExit) as exc:
        main(["render", str(md), "--email", "-o", str(out)])
    assert exc.value.code == 0

    content = out.read_text(encoding="utf-8")
    assert 'role="presentation"' in content
    assert "<style" not in content


def test_render_document_and_email_differ(tmp_path):
    """Document and email renders of the same file should differ structurally."""
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    doc_out = tmp_path / "doc.html"
    email_out = tmp_path / "email.html"

    with pytest.raises(SystemExit):
        main(["render", str(md), "-o", str(doc_out)])
    with pytest.raises(SystemExit):
        main(["render", str(md), "--email", "-o", str(email_out)])

    doc_content = doc_out.read_text(encoding="utf-8")
    email_content = email_out.read_text(encoding="utf-8")

    assert "<style" in doc_content
    assert "<style" not in email_content
    assert 'role="presentation"' in email_content


def test_render_preview_opens_temp_file(tmp_path, monkeypatch, capsys):
    """--preview calls _open_in_browser with a .html temp path containing the HTML."""
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")

    opened = []
    monkeypatch.setattr(_output_mod, "_open_in_browser", lambda p: opened.append(p))

    with pytest.raises(SystemExit) as exc:
        main(["render", str(md), "--preview"])
    assert exc.value.code == 0

    assert len(opened) == 1
    tmp_file = opened[0]
    assert isinstance(tmp_file, Path)
    assert tmp_file.suffix == ".html"
    assert tmp_file.exists()
    content = tmp_file.read_text(encoding="utf-8")
    assert "<html" in content or "<body" in content


def test_render_clipboard_macos(tmp_path, monkeypatch, capsys):
    """--clipboard on macOS calls osascript and exits 0."""
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")

    monkeypatch.setattr(_clipboard_mod, "_is_macos", lambda: True)
    monkeypatch.setattr(_clipboard_mod, "_osascript_available", lambda: True)

    script_calls = []

    def fake_osascript(script: str) -> bool:
        script_calls.append(script)
        return True

    monkeypatch.setattr(_clipboard_mod, "_run_osascript", fake_osascript)

    with pytest.raises(SystemExit) as exc:
        main(["render", str(md), "--clipboard"])
    assert exc.value.code == 0

    assert len(script_calls) == 1
    # The AppleScript command should carry the HTML class hint
    assert "HTML" in script_calls[0]


def test_render_clipboard_non_macos_prints_message_exits_zero(tmp_path, monkeypatch, capsys):
    """--clipboard on a non-macOS platform prints guidance and exits 0 (non-fatal)."""
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")

    monkeypatch.setattr(_clipboard_mod, "_is_macos", lambda: False)

    with pytest.raises(SystemExit) as exc:
        main(["render", str(md), "--clipboard"])
    assert exc.value.code == 0

    captured = capsys.readouterr()
    assert "macOS" in captured.err or "clipboard" in captured.err.lower()


def test_render_set_flows_into_output(tmp_path, capsys):
    """--set colours.accent=... appears in the rendered document output."""
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        main(["render", str(md), "--set", "colours.accent=#abcdef"])
    assert exc.value.code == 0

    captured = capsys.readouterr()
    assert "#abcdef" in captured.out


def test_render_set_malformed_exits_nonzero(tmp_path, capsys):
    """--set without = prints an error and exits non-zero."""
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        main(["render", str(md), "--set", "colours.accent"])
    assert exc.value.code != 0

    captured = capsys.readouterr()
    assert "Error" in captured.err


def test_render_brand_selects_alternate_config(tmp_path, capsys):
    """--brand PATH uses the alternate config; a distinctive colour appears in output."""
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")

    brand_yaml = tmp_path / "brand.yaml"
    brand_yaml.write_text(
        "colours:\n  accent: '#deadbe'\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        main(["render", str(md), "--brand", str(brand_yaml)])
    assert exc.value.code == 0

    captured = capsys.readouterr()
    assert "#deadbe" in captured.out or "deadbe" in captured.out.lower()


def test_render_with_date_frontmatter(tmp_path, capsys):
    """Regression: a `date:` in frontmatter (parsed as datetime.date) must not
    crash the render; the date appears in the document and resolution succeeds."""
    md = tmp_path / "dated.md"
    md.write_text(
        "---\ntitle: Dated Doc\ndate: 2026-06-20\n---\n\n# Dated Doc\n\nBody.\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as exc:
        main(["render", str(md)])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "20 June 2026" in captured.out


def test_render_output_and_open(tmp_path, monkeypatch, capsys):
    """-o FILE --open writes the file and opens it in the browser."""
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    out = tmp_path / "result.html"

    opened = []
    monkeypatch.setattr(_output_mod, "_open_in_browser", lambda p: opened.append(p))

    with pytest.raises(SystemExit) as exc:
        main(["render", str(md), "-o", str(out), "--open"])
    assert exc.value.code == 0

    assert out.is_file()
    assert opened == [out]


# ---------------------------------------------------------------------------
# U5 entry dispatch (bare brandx / brandx <file> → session)
# ---------------------------------------------------------------------------

def _no_session(monkeypatch):
    """Make run_session blow up so we can assert it was NOT taken."""
    def _boom(*_a, **_k):
        raise AssertionError("session launched unexpectedly")

    monkeypatch.setattr("brandx.session.run_session", _boom)


def test_bare_invocation_launches_session(monkeypatch):
    calls = []
    monkeypatch.setattr("brandx.session.run_session", lambda focused=None: calls.append(focused) or 0)
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 0
    assert calls == [None]


def test_file_argument_focuses_session(monkeypatch):
    calls = []
    monkeypatch.setattr("brandx.session.run_session", lambda focused=None: calls.append(focused) or 0)
    with pytest.raises(SystemExit) as exc:
        main(["note.md"])
    assert exc.value.code == 0
    assert calls == ["note.md"]


def test_render_subcommand_does_not_launch_session(tmp_path, monkeypatch, capsys):
    md = tmp_path / "doc.md"
    md.write_text(SAMPLE_MD, encoding="utf-8")
    _no_session(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        main(["render", str(md)])
    assert exc.value.code == 0


def test_version_flag_does_not_launch_session(monkeypatch):
    _no_session(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
