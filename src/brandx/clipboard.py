"""macOS-first clipboard backend for rich-text HTML copy.

Copies rendered HTML to the macOS clipboard as rich text using osascript
and the AppleScript «class HTML» technique. On non-macOS platforms, or
when osascript is unavailable, prints guidance to stderr and returns False.

Only macOS is supported. Windows and Linux clipboard backends are deferred
(see KTD6 in the plan).

Usage:
    from brandx.clipboard import copy_html

    success = copy_html(html)
    if not success:
        # user has already been warned on stderr
        pass
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _is_macos() -> bool:
    """Return True when running on macOS."""
    return sys.platform == "darwin"


def _osascript_available() -> bool:
    """Return True when osascript is on PATH."""
    return shutil.which("osascript") is not None


def _run_osascript(script: str) -> bool:
    """Run an AppleScript string via osascript. Returns True on success."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
    )
    return result.returncode == 0


def copy_html(html: str) -> bool:
    """Copy HTML to the clipboard as rich text.

    On macOS with osascript available: writes the HTML to a temp file,
    encodes it as hex, and issues an AppleScript «class HTML» set-clipboard
    command. The temp file is deleted after use.

    On a non-macOS platform, or when osascript is unavailable: prints
    guidance to stderr and returns False (non-fatal; exit 0 is expected).

    Returns:
        True on successful copy; False when unsupported or on failure.
    """
    if not _is_macos() or not _osascript_available():
        print(
            "Clipboard copy is only supported on macOS; "
            "use -o FILE to write the output instead.",
            file=sys.stderr,
        )
        return False

    # Write to a temp file so the hex conversion stays in Python.
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".html",
        encoding="utf-8",
        delete=False,
    ) as fh:
        fh.write(html)
        tmp_path = Path(fh.name)

    try:
        hex_bytes = tmp_path.read_bytes().hex().upper()
        script = f'set the clipboard to «data HTML{hex_bytes}»'
        success = _run_osascript(script)
    finally:
        tmp_path.unlink(missing_ok=True)

    if success:
        print("Copied to clipboard.", file=sys.stderr)
    else:
        print("Error: clipboard copy failed.", file=sys.stderr)

    return success
