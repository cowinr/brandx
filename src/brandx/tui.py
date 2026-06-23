"""Full-screen, in-place TUI for the interactive session (POSIX terminals).

A single status panel is drawn on the alternate screen buffer and redrawn in
place (no scrollback churn). Options are driven by single keypresses rather than
typed commands. State and resolution are reused from ``brandx.session`` — this is
the full-TUI realisation the line loop was structured to allow.

``is_supported`` gates use to real TTYs with ``termios`` available; otherwise the
caller falls back to the line-driven loop (which also covers Windows and piped
input). The key-handling logic (``TuiSession.dispatch``) is kept free of terminal
I/O so it can be tested directly.
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

from brandx.session import (
    DEST_CLIPBOARD,
    DEST_FILE,
    DEST_PREVIEW,
    SessionState,
    resolve_for_state,
)

_WIDTH = 50
_RULE = "─" * _WIDTH
_DEST_ORDER = [DEST_PREVIEW, DEST_CLIPBOARD, DEST_FILE]


def _discover_brand_configs() -> list[tuple[str, str | None]]:
    """Return ``[(label, path|None)]`` of brand configs to cycle through.

    'default' (None — the auto-resolved home config) plus every ``*.yaml`` in
    the config directory, so the user can flip brands without typing a path.
    """
    from brandx.config.discovery import default_config_path

    cfg_dir = default_config_path().parent
    items: list[tuple[str, str | None]] = [("default", None)]
    if cfg_dir.is_dir():
        for path in sorted(cfg_dir.glob("*.yaml")):
            items.append((path.name, str(path)))
    return items


def _opt_row(label: str, value: str, key: str) -> str:
    left = f"  {label.ljust(7)} {value}"
    return f"{left.ljust(_WIDTH - 3)}{key}"


class TuiSession:
    """Holds session state plus a transient status line, and maps keys to actions.

    ``dispatch`` performs no terminal I/O — text input is delegated to an injected
    ``ask`` callable — so the key logic is testable without a real terminal.
    """

    def __init__(self, state: SessionState | None = None) -> None:
        self.state = state or SessionState()
        self.status = "Ready. Single keys change options; r renders."
        self.brands = _discover_brand_configs()

    # -- rendering --------------------------------------------------------

    def render_screen(self) -> str:
        cfg, brand_label = resolve_for_state(self.state)
        title = self.state.focused_file.name if self.state.focused_file else "(no file)"

        effective_avatar = cfg.avatar_email if self.state.email else cfg.avatar
        mark = cfg.mark
        if cfg.mark == "avatar" and effective_avatar is None:
            mark = "avatar → monogram"

        brand_short = "defaults" if brand_label == "defaults" else Path(brand_label).name

        if self.state.destination == DEST_FILE and self.state.dest_path is not None:
            dest = f"file → {self.state.dest_path}"
        else:
            dest = self.state.destination

        overrides = ", ".join(f"{k}={v}" for k, v in self.state.overrides.items()) or "(none)"

        rows = [
            f"brandx · {title}",
            _RULE,
            _opt_row("output", f"‹ {'email' if self.state.email else 'document'} ›", "o"),
            _opt_row("mark", mark, "m"),
            _opt_row("brand", brand_short, "b"),
            _opt_row("dest", dest, "d"),
            _opt_row("set", overrides, "s"),
            _RULE,
            "  r render    f file    x reset    q quit",
            "",
            f"  {self.status}",
        ]
        return "\r\n".join(rows)

    # -- key dispatch -----------------------------------------------------

    def dispatch(self, key: str, ask) -> bool:
        """Handle one keypress. Returns True to stop the loop.

        ``ask(prompt)`` returns a line of user input (for focus/set/file path).
        """
        if key in ("q", "Q", "\x03", "\x04"):
            return True

        lower = key.lower()
        if lower == "o":
            self.state.email = not self.state.email
            self.status = f"output: {'email' if self.state.email else 'document'}"
        elif lower == "m":
            self.state.mark = "monogram" if self.state.mark == "avatar" else "avatar"
            self.status = f"mark: {self.state.mark}"
        elif lower == "b":
            self._cycle_brand()
        elif lower == "d":
            self._cycle_dest(ask)
        elif lower == "f":
            self._focus(ask)
        elif lower == "s":
            self._set(ask)
        elif lower == "x":
            self.state = SessionState(focused_file=self.state.focused_file)
            self.status = "reset to defaults"
        elif lower == "r":
            self._render()
        else:
            self.status = "keys: o m b d s  ·  r f x q"
        return False

    def _cycle_brand(self) -> None:
        paths = [path for _, path in self.brands]
        try:
            index = paths.index(self.state.brand_path)
        except ValueError:
            index = 0
        label, path = self.brands[(index + 1) % len(self.brands)]
        self.state.brand_path = path
        self.status = f"brand: {label}"

    def _cycle_dest(self, ask) -> None:
        nxt = _DEST_ORDER[(_DEST_ORDER.index(self.state.destination) + 1) % len(_DEST_ORDER)]
        self.state.destination = nxt
        if nxt == DEST_FILE and self.state.dest_path is None:
            answer = ask("output file path: ").strip()
            if answer:
                self.state.dest_path = Path(answer).expanduser()
            else:
                self.state.destination = DEST_PREVIEW
                self.status = "dest: preview (file cancelled)"
                return
        self.status = f"dest: {self.state.destination}"

    def _focus(self, ask) -> None:
        answer = ask("focus file: ").strip()
        if not answer:
            self.status = "focus cancelled"
            return
        path = Path(answer).expanduser()
        if path.is_file():
            self.state.focused_file = path
            self.status = f"focused {path.name}"
        else:
            self.status = f"not found: {answer}"

    def _set(self, ask) -> None:
        answer = ask("set key=value (blank clears all): ").strip()
        if not answer:
            self.state.overrides.clear()
            self.status = "overrides cleared"
            return
        if "=" not in answer:
            self.status = "need key=value"
            return
        key, _, value = answer.partition("=")
        self.state.overrides[key.strip()] = value.strip()
        self.status = f"set {key.strip()}"

    def _render(self) -> None:
        if self.state.focused_file is None:
            self.status = "no file focused — press f"
            return

        from brandx.cli import RenderInputError, build_html
        from brandx.clipboard import copy_html
        from brandx.output import preview, write_file

        try:
            html, _cfg, _source = build_html(
                self.state.focused_file,
                email=self.state.email,
                brand_path=self.state.brand_path,
                mark=self.state.mark,
                set_flags=self.state.overrides,
            )
        except RenderInputError as exc:
            self.status = str(exc)
            return

        # Suppress the destinations' own stderr chatter to keep the screen clean;
        # the status line carries the outcome instead.
        with contextlib.redirect_stderr(io.StringIO()):
            if self.state.destination == DEST_CLIPBOARD:
                ok = copy_html(html)
                self.status = "copied to clipboard" if ok else "clipboard is macOS-only"
            elif self.state.destination == DEST_FILE:
                write_file(html, self.state.dest_path)
                self.status = f"written {self.state.dest_path}"
            else:
                path = preview(html)
                self.status = f"preview {path}"


# ---------------------------------------------------------------------------
# Terminal driver
# ---------------------------------------------------------------------------

def is_supported() -> bool:
    """True when a full-screen TUI can run: a real TTY with termios available."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False
    try:
        import termios  # noqa: F401
    except ImportError:
        return False
    return True


def run_tui(state: SessionState) -> int:
    """Run the full-screen TUI loop. Restores the terminal on exit."""
    import termios
    import tty

    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    tui = TuiSession(state)

    def ask(prompt: str) -> str:
        # Drop to cooked mode (echo + line editing) for a one-line prompt.
        termios.tcsetattr(fd, termios.TCSADRAIN, original)
        sys.stdout.write("\033[?25h\r\n" + prompt)
        sys.stdout.flush()
        try:
            return sys.stdin.readline().rstrip("\n")
        finally:
            tty.setcbreak(fd)
            sys.stdout.write("\033[?25l")

    try:
        sys.stdout.write("\033[?1049h\033[?25l")  # alternate screen, hide cursor
        tty.setcbreak(fd)
        while True:
            sys.stdout.write("\033[2J\033[H")  # clear, home
            sys.stdout.write(tui.render_screen())
            sys.stdout.flush()
            key = sys.stdin.read(1)
            if not key or tui.dispatch(key, ask):
                break
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original)
        sys.stdout.write("\033[?25h\033[?1049l")  # show cursor, leave alternate screen
        sys.stdout.flush()
    return 0
