"""Shared test fixtures.

Isolates brandx config discovery from the developer's real home config. Without
this, any test that runs `brandx init --force` (including the subprocess CLI test)
would write to the real `~/.config/brandx/brand.yaml` and clobber it. Pointing
XDG_CONFIG_HOME (and APPDATA on Windows) at a per-test temp directory keeps every
test self-contained; subprocesses inherit os.environ, so the redirect covers
subprocess-based tests too.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_brandx_config(monkeypatch, tmp_path):
    config_home = tmp_path / "xdg-config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("APPDATA", str(config_home))  # Windows config root
    monkeypatch.delenv("BRANDX_CONFIG", raising=False)
    yield
