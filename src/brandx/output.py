"""Output destinations for rendered HTML.

Provides three surface-agnostic destinations:
    - write_file: write HTML to a named file, creating parent dirs as needed.
    - preview: write to a temp file and open it in the browser.
    - open_in_browser: open an existing file in the browser.

These functions take rendered HTML strings and know nothing about document vs
email surfaces; that distinction belongs to the caller.

Usage:
    from brandx.output import write_file, preview, open_in_browser
    from pathlib import Path

    write_file(html, Path("out/report.html"))
    tmp = preview(html)
    open_in_browser(Path("out/report.html"))
"""

from __future__ import annotations

import sys
import tempfile
import webbrowser
from pathlib import Path


def _open_in_browser(path: Path) -> None:
    """Open a file path in the system default browser.

    Isolated here so tests can monkeypatch it without touching the webbrowser
    module directly.
    """
    webbrowser.open(path.as_uri())


def write_file(html: str, path: Path) -> None:
    """Write HTML to path, creating parent directories if needed.

    Prints a confirmation to stderr.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    print(f"Written: {path}", file=sys.stderr)


def preview(html: str) -> Path:
    """Write HTML to a temp file and open it in the browser.

    The temp file is kept (delete=False) so the browser can read it after
    this function returns. Returns the temp file path.
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".html",
        encoding="utf-8",
        delete=False,
    ) as fh:
        fh.write(html)
        tmp_path = Path(fh.name)

    _open_in_browser(tmp_path)
    print(f"Preview: {tmp_path}", file=sys.stderr)
    return tmp_path


def open_in_browser(path: Path) -> None:
    """Open an existing file in the system default browser."""
    _open_in_browser(path)
