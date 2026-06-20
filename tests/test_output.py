"""Tests for brandx.output — file/preview/browser destinations.

Covers:
    - write_file writes UTF-8 content and creates parent dirs.
    - write_file prints a confirmation to stderr.
    - preview writes HTML to a temp .html file and calls _open_in_browser.
    - open_in_browser delegates to _open_in_browser.
"""

from pathlib import Path


from brandx import output as _output_mod
from brandx.output import open_in_browser, preview, write_file


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------

def test_write_file_creates_file(tmp_path):
    dest = tmp_path / "sub" / "out.html"
    write_file("<p>hello</p>", dest)
    assert dest.is_file()
    assert dest.read_text(encoding="utf-8") == "<p>hello</p>"


def test_write_file_creates_parent_dirs(tmp_path):
    dest = tmp_path / "a" / "b" / "c" / "out.html"
    write_file("<p>x</p>", dest)
    assert dest.is_file()


def test_write_file_prints_confirmation(tmp_path, capsys):
    dest = tmp_path / "out.html"
    write_file("<p>y</p>", dest)
    captured = capsys.readouterr()
    assert "Written:" in captured.err
    assert str(dest) in captured.err


# ---------------------------------------------------------------------------
# preview
# ---------------------------------------------------------------------------

def test_preview_writes_html_to_temp_file(monkeypatch, tmp_path):
    opened_paths = []

    def fake_open(path):
        opened_paths.append(path)

    monkeypatch.setattr(_output_mod, "_open_in_browser", fake_open)

    html = "<p>preview</p>"
    result = preview(html)

    assert result.is_file(), "temp file should exist after preview()"
    assert result.suffix == ".html"
    assert result.read_text(encoding="utf-8") == html
    assert len(opened_paths) == 1
    assert opened_paths[0] == result


def test_preview_returns_path(monkeypatch):
    monkeypatch.setattr(_output_mod, "_open_in_browser", lambda p: None)
    result = preview("<p>z</p>")
    assert isinstance(result, Path)
    assert result.exists()


def test_preview_prints_to_stderr(monkeypatch, capsys):
    monkeypatch.setattr(_output_mod, "_open_in_browser", lambda p: None)
    preview("<p>msg</p>")
    captured = capsys.readouterr()
    assert "Preview:" in captured.err


# ---------------------------------------------------------------------------
# open_in_browser
# ---------------------------------------------------------------------------

def test_open_in_browser_calls_seam(monkeypatch, tmp_path):
    called_with = []

    def fake_open(path):
        called_with.append(path)

    monkeypatch.setattr(_output_mod, "_open_in_browser", fake_open)

    dest = tmp_path / "test.html"
    dest.write_text("<p>hi</p>", encoding="utf-8")
    open_in_browser(dest)

    assert called_with == [dest]
