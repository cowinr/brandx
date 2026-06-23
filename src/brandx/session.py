"""Interactive brandx session: state model, status panel, and command loop.

The session lets a user focus a markdown file, set and re-set render options, and
re-render in place while an always-visible status panel shows the current resolved
settings. It is line-driven (stdlib ``cmd``) with no TUI dependency.

The option model (``SessionState``) and the panel renderer (``render_panel``) are
kept independent of the ``cmd.Cmd`` loop so a future full-screen TUI can replace the
loop without touching the option logic.

Usage:
    from brandx.session import run_session
    run_session("note.md")        # launch focused on a file
    run_session()                  # launch unfocused
"""

from __future__ import annotations

import cmd
from dataclasses import dataclass, field
from pathlib import Path

DEST_PREVIEW = "preview"
DEST_CLIPBOARD = "clipboard"
DEST_FILE = "file"

_PANEL_WIDTH = 54
_RULE = "─" * _PANEL_WIDTH

_COMMANDS_FOOTER = (
    "  focus  output  brand  mark  dest  set  unset\n"
    "  render  reset  status  help  quit"
)


# ---------------------------------------------------------------------------
# Session state (option model — independent of the command loop)
# ---------------------------------------------------------------------------

@dataclass
class SessionState:
    """The mutable option state of an interactive session.

    Holds only option state — no I/O, no ``cmd`` coupling — so the render loop
    can be swapped for a TUI without touching this model.
    """

    focused_file: Path | None = None
    email: bool = False
    brand_path: str | None = None
    mark: str | None = None
    overrides: dict[str, str] = field(default_factory=dict)
    destination: str = DEST_PREVIEW
    dest_path: Path | None = None

    def flags(self) -> dict[str, str]:
        """Build the dotted-flag dict the resolver consumes.

        Mirrors the one-shot path: the ``set`` overrides plus ``identity.mark``
        when a mark override is active.
        """
        result = dict(self.overrides)
        if self.mark is not None:
            result["identity.mark"] = self.mark
        return result


# ---------------------------------------------------------------------------
# Status panel (pure rendering)
# ---------------------------------------------------------------------------

def _row(label: str, value: str, extra: str = "") -> str:
    line = f"  {label.ljust(8)} {value.ljust(22)}"
    if extra:
        line = f"{line} {extra}"
    return line.rstrip()


def resolve_for_state(state: SessionState):
    """Run the cascade for a session state. Returns (ResolvedConfig, brand_label).

    Shared by the line loop and the TUI. Resolves with the focused file's
    frontmatter (or none when unfocused) so the panel matches the next render.
    """
    from brandx.config.discovery import load_home_config
    from brandx.config.resolver import resolve
    from brandx.render.pipeline import parse_document

    home, source = load_home_config(explicit_path=state.brand_path)
    frontmatter: dict = {}
    if state.focused_file is not None and state.focused_file.is_file():
        frontmatter = parse_document(state.focused_file).frontmatter
    cfg = resolve(home_config=home, frontmatter=frontmatter, flags=state.flags())
    brand_label = source if home else "defaults"
    return cfg, brand_label


def render_panel(state: SessionState, cfg, brand_label: str) -> str:
    """Render the status panel string from session state and resolved config.

    ``cfg`` must be resolved with the focused file's frontmatter (or no
    frontmatter when unfocused) so the panel matches what the next render
    produces. ``brand_label`` is the display label for the active brand source.
    """
    if state.focused_file is None:
        file_value = "(none — use: focus <file.md>)"
    else:
        file_value = state.focused_file.name

    if state.destination == DEST_FILE:
        dest_value = DEST_FILE
        dest_extra = str(state.dest_path) if state.dest_path is not None else ""
    else:
        dest_value = state.destination
        dest_extra = ""

    # The resolved name is shown alongside the mark only when a file is focused
    # (an unfocused session has no document frontmatter to resolve against).
    mark_extra = cfg.name if state.focused_file is not None else ""
    mark_value = cfg.mark

    # The renderer falls back to a monogram when 'avatar' is selected but no
    # avatar image is configured. Reflect what actually renders (R4) rather than
    # the inert selection. Email uses avatar_email (which falls back to avatar).
    effective_avatar = cfg.avatar_email if state.email else cfg.avatar
    if cfg.mark == "avatar" and effective_avatar is None:
        mark_value = "avatar → monogram (no avatar image set)"
        mark_extra = ""

    if state.overrides:
        set_value = ", ".join(f"{k} = {v}" for k, v in state.overrides.items())
    else:
        set_value = "(none)"

    rows = [
        "brandx · interactive session",
        _RULE,
        _row("file", file_value),
        _row("output", "email" if state.email else "document"),
        _row("brand", brand_label),
        _row("mark", mark_value, mark_extra),
        _row("dest", dest_value, dest_extra),
        _row("set", set_value),
        _RULE,
        _COMMANDS_FOOTER,
    ]
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Command loop
# ---------------------------------------------------------------------------

class SessionCmd(cmd.Cmd):
    """Line-driven interactive session. Reprints the status panel after each command."""

    prompt = "brandx> "

    def __init__(self, state: SessionState | None = None) -> None:
        super().__init__()
        self.state = state or SessionState()

    # -- panel ------------------------------------------------------------

    def _resolve(self):
        """Re-run the cascade for the current state. Returns (cfg, brand_label)."""
        return resolve_for_state(self.state)

    def _print_panel(self) -> None:
        cfg, brand_label = self._resolve()
        print(render_panel(self.state, cfg, brand_label))

    def preloop(self) -> None:
        self._print_panel()

    def postcmd(self, stop, line):
        if not stop:
            self._print_panel()
        return stop

    def emptyline(self):
        # Default cmd behaviour repeats the last command; we want a no-op
        # (the panel still reprints via postcmd).
        return False

    def default(self, line):
        print(f"Unknown command: {line.split()[0] if line.split() else line!r}. Type 'help'.")

    # -- option commands --------------------------------------------------

    def do_focus(self, arg):
        "focus <file.md> — focus a markdown file (replaces the current one)."
        arg = arg.strip()
        if not arg:
            print("Usage: focus <file.md>")
            return
        path = Path(arg)
        if not path.is_file():
            print(f"File not found: {arg}  (focus unchanged)")
            return
        self.state.focused_file = path

    def do_output(self, arg):
        "output <document|email> — choose the output form."
        choice = arg.strip().lower()
        if choice == "document":
            self.state.email = False
        elif choice == "email":
            self.state.email = True
        else:
            print("Usage: output <document|email>")

    def do_brand(self, arg):
        "brand <path>|default — use an alternate brand config, or return to default."
        arg = arg.strip()
        if not arg:
            print("Usage: brand <path>|default")
            return
        if arg == "default":
            self.state.brand_path = None
            return
        if not Path(arg).is_file():
            print(f"Brand config not found: {arg}  (brand unchanged)")
            return
        self.state.brand_path = arg

    def do_mark(self, arg):
        "mark <monogram|avatar> — choose the identity mark style."
        choice = arg.strip().lower()
        if choice in ("monogram", "avatar"):
            self.state.mark = choice
        else:
            print("Usage: mark <monogram|avatar>")

    def do_dest(self, arg):
        "dest <preview|clipboard|file <path>> — set the render destination."
        parts = arg.split()
        if not parts:
            print("Usage: dest <preview|clipboard|file <path>>")
            return
        kind = parts[0].lower()
        if kind in (DEST_PREVIEW, DEST_CLIPBOARD):
            self.state.destination = kind
            self.state.dest_path = None
        elif kind == DEST_FILE:
            if len(parts) < 2:
                print("dest file needs a path. Use: dest file <path>")
                return
            self.state.destination = DEST_FILE
            self.state.dest_path = Path(parts[1])
        else:
            print("Usage: dest <preview|clipboard|file <path>>")

    def do_set(self, arg):
        "set <key=value> — add a config override (e.g. set colours.accent=#e63946)."
        arg = arg.strip()
        if "=" not in arg:
            print("Usage: set <key=value>  (e.g. set colours.accent=#e63946)")
            return
        key, _, value = arg.partition("=")
        self.state.overrides[key.strip()] = value.strip()

    def do_unset(self, arg):
        "unset <key> — remove one config override."
        key = arg.strip()
        if key in self.state.overrides:
            del self.state.overrides[key]
        else:
            print(f"No override set for {key!r}.")

    def do_reset(self, arg):
        "reset [output|brand|mark|dest|set]|all — reset one option, or all, to defaults."
        target = arg.strip().lower()
        if target in ("", "all"):
            self.state = SessionState(focused_file=self.state.focused_file)
        elif target == "output":
            self.state.email = False
        elif target == "brand":
            self.state.brand_path = None
        elif target == "mark":
            self.state.mark = None
        elif target == "dest":
            self.state.destination = DEST_PREVIEW
            self.state.dest_path = None
        elif target == "set":
            self.state.overrides.clear()
        else:
            print("Usage: reset [output|brand|mark|dest|set]|all")

    # -- render -----------------------------------------------------------

    def do_render(self, arg):
        "render — render the focused file to the current destination."
        from brandx.cli import RenderInputError, build_html
        from brandx.clipboard import copy_html
        from brandx.output import preview, write_file

        if self.state.focused_file is None:
            print("No file focused. Use: focus <file.md>")
            return

        try:
            html, _cfg, _source = build_html(
                self.state.focused_file,
                email=self.state.email,
                brand_path=self.state.brand_path,
                mark=self.state.mark,
                set_flags=self.state.overrides,
            )
        except RenderInputError as exc:
            print(str(exc))
            return

        if self.state.destination == DEST_CLIPBOARD:
            if not copy_html(html):
                print(
                    "Clipboard is macOS-only. Set a different destination "
                    "(dest preview | file <path>)."
                )
        elif self.state.destination == DEST_FILE:
            if self.state.dest_path is None:
                print("No file path set. Use: dest file <path>")
                return
            write_file(html, self.state.dest_path)
        else:
            preview(html)

    # -- session control --------------------------------------------------

    def do_status(self, arg):
        "status — reprint the panel."
        # The panel is reprinted by postcmd; nothing to do here.
        return False

    def do_quit(self, arg):
        "quit — exit the session."
        print()
        return True

    def do_EOF(self, arg):
        "Ctrl-D — exit the session."
        return self.do_quit(arg)


def run_session(focused_file: Path | str | None = None) -> int:
    """Launch an interactive session, optionally focused on a file.

    Uses the full-screen TUI on a real terminal; falls back to the line-driven
    loop when stdin/stdout is not a TTY (piped input, tests) or the terminal
    primitives are unavailable. Returns a process exit code.
    """
    state = SessionState()
    if focused_file is not None:
        path = Path(focused_file)
        if path.is_file():
            state.focused_file = path
        else:
            print(f"File not found: {focused_file}")

    from brandx.tui import is_supported, run_tui

    if is_supported():
        return run_tui(state)
    SessionCmd(state).cmdloop()
    return 0
