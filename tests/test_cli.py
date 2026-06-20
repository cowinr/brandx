"""Tests for the brandx CLI entry point (U1).

Covers: --help lists both subcommands; entry point imports without error; the
package version is accessible.
"""

import subprocess
import sys


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
    import brandx.cli as cli  # noqa: F401 (import side-effects only)
    assert hasattr(cli, "main")


def test_version():
    result = subprocess.run(
        [sys.executable, "-m", "brandx.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_no_subcommand_exits_zero():
    result = subprocess.run(
        [sys.executable, "-m", "brandx.cli"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_init_not_yet_implemented():
    result = subprocess.run(
        [sys.executable, "-m", "brandx.cli", "init"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "not yet implemented" in result.stderr


def test_render_not_yet_implemented():
    result = subprocess.run(
        [sys.executable, "-m", "brandx.cli", "render", "dummy.md"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "not yet implemented" in result.stderr
