"""brandx CLI entry point.

Running `brandx` with no subcommand (optionally `brandx <file.md>`) launches the
interactive session (see brandx.session). `init` and `render` stay explicit
subcommands; `render` is the unchanged, pipeable one-shot.

Subcommands:
    init      Write a starter brand config to the home location.
    render    Render a markdown file to a branded document or email.

Usage:
    brandx                   Launch the interactive session (unfocused).
    brandx <file.md>         Launch the session focused on a file.
    brandx --help
    brandx init [--force]
    brandx render <file.md> [--email] [-o OUTPUT] [--open] [--preview]
                            [--clipboard] [--brand PATH] [--mark monogram|avatar]
                            [--set KEY=VALUE ...]

Destination precedence for render (pick exactly one):
    --clipboard          Copy rich text to the macOS clipboard.
    -o / --output FILE   Write HTML to FILE; combine with --open to also
                         open in the browser.
    --preview            Write to a temp file and open in the browser.
    (none)               Print HTML to stdout (pipeable).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="brandx",
        description="Render markdown to a branded document or Outlook-safe email.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.3.0")

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    _add_init_subcommand(subparsers)
    _add_render_subcommand(subparsers)

    return parser


def _add_init_subcommand(subparsers):
    sub = subparsers.add_parser(
        "init",
        help="Write a fully-commented starter brand config to the home location.",
    )
    sub.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing config (default: refuse).",
    )


def _add_render_subcommand(subparsers):
    sub = subparsers.add_parser(
        "render",
        help="Render a markdown file to a branded document or Outlook-safe email.",
    )
    sub.add_argument("input", metavar="FILE", help="Markdown file to render.")
    sub.add_argument(
        "--email",
        action="store_true",
        help="Render Outlook-safe email HTML instead of a document.",
    )
    sub.add_argument("-o", "--output", metavar="FILE", help="Write output to FILE.")
    sub.add_argument(
        "--open", action="store_true", help="Open output in the default browser."
    )
    sub.add_argument(
        "--preview",
        action="store_true",
        help="Open a temporary browser preview (prints HTML to stdout when no destination is given).",
    )
    sub.add_argument(
        "--clipboard",
        action="store_true",
        help="Copy output to the clipboard (macOS only).",
    )
    sub.add_argument(
        "--brand",
        metavar="PATH",
        help="Path to an alternate brand YAML config.",
    )
    sub.add_argument(
        "--mark",
        choices=["monogram", "avatar"],
        default=None,
        help="Identity mark style (overrides config).",
    )
    sub.add_argument(
        "--set",
        metavar="KEY=VALUE",
        action="append",
        dest="set_flags",
        help="Override a config value using dotted key notation, e.g. --set colours.accent=#e63946. Repeatable.",
    )


def _cmd_init(args) -> int:
    from brandx.initcmd import run_init
    run_init(force=args.force)
    return 0


class RenderInputError(Exception):
    """Raised by build_html when the input file or brand config cannot be loaded.

    Carries a user-facing message; callers decide how to surface it (the one-shot
    render command exits non-zero, the interactive session prints and continues).
    """


def build_html(
    input_path: Path,
    *,
    email: bool = False,
    brand_path: str | None = None,
    mark: str | None = None,
    set_flags: dict[str, str] | None = None,
):
    """Load config, parse the document, resolve the cascade, and render.

    Shared core of the one-shot `render` command and the interactive session.
    Raw `--set` KEY=VALUE string validation is the caller's job; this helper
    receives an already-built ``set_flags`` dict.

    Args:
        input_path: Path to the markdown file to render.
        email: Render the Outlook-safe email surface instead of a document.
        brand_path: Optional explicit brand config path.
        mark: Optional identity mark override ('monogram' or 'avatar').
        set_flags: Already-validated dotted-key overrides.

    Returns:
        (html, ResolvedConfig, brand_source_label).

    Raises:
        RenderInputError: when the input file is missing or the brand config
            cannot be loaded. Both callers handle this rather than exiting here.
    """
    from brandx.config.discovery import load_home_config
    from brandx.config.resolver import resolve
    from brandx.render.document import render_document
    from brandx.render.email import render_email
    from brandx.render.pipeline import parse_document

    # load_home_config calls sys.exit on a missing/malformed explicit brand file.
    # Translate that into RenderInputError so the session can survive it.
    try:
        home, source = load_home_config(explicit_path=brand_path)
    except SystemExit as exc:
        raise RenderInputError(str(exc)) from exc

    if not input_path.is_file():
        raise RenderInputError(f"Error: input file not found: {input_path}")

    doc = parse_document(input_path)

    flags: dict[str, str] = dict(set_flags or {})
    if mark is not None:
        flags["identity.mark"] = mark

    # Resolve the cascade. Document metadata in the frontmatter (title, date, and
    # similar) is harmless: the resolver ignores unknown top-level keys and a
    # scalar cannot clobber a nested brand block (see _deep_merge).
    cfg = resolve(home_config=home, frontmatter=doc.frontmatter, flags=flags)

    html = render_email(doc, cfg) if email else render_document(doc, cfg)
    return html, cfg, source


def _cmd_render(args) -> int:
    from brandx.clipboard import copy_html
    from brandx.output import open_in_browser, preview, write_file

    # Validate --set KEY=VALUE strings here; build_html receives a clean dict.
    set_flags: dict[str, str] = {}
    for item in (args.set_flags or []):
        if "=" not in item:
            print(
                f"Error: --set requires KEY=VALUE form, got: {item!r}",
                file=sys.stderr,
            )
            return 1
        key, _, value = item.partition("=")
        set_flags[key] = value

    try:
        html, _cfg, _source = build_html(
            Path(args.input),
            email=args.email,
            brand_path=args.brand,
            mark=args.mark,
            set_flags=set_flags,
        )
    except RenderInputError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # Dispatch to the chosen destination.
    # Precedence: --clipboard > -o/--output > --preview > stdout.
    if args.clipboard:
        copy_html(html)
        return 0  # non-fatal regardless; message already printed to stderr

    if args.output:
        out_path = Path(args.output)
        write_file(html, out_path)
        if args.open:
            open_in_browser(out_path)
        return 0

    if args.preview:
        preview(html)
        return 0

    # No destination flag — write to stdout (pipeable).
    sys.stdout.write(html)
    return 0


_SUBCOMMANDS = {"init", "render"}


def _is_session_invocation(argv: list[str]) -> bool:
    """True when argv should launch the interactive session rather than argparse.

    Bare `brandx` (no args) and `brandx <file>` start the session. A leading
    `init`/`render` subcommand, or a leading flag (`-h`, `--help`, `--version`),
    routes to the one-shot parser instead.
    """
    if not argv:
        return True
    first = argv[0]
    if first in _SUBCOMMANDS or first.startswith("-"):
        return False
    return True


def main(argv: list[str] | None = None) -> None:
    """Entry point. Accepts an optional argv list for testing; defaults to sys.argv."""
    argv = list(sys.argv[1:] if argv is None else argv)

    # Bare `brandx` or `brandx <file>` drops into the interactive session.
    if _is_session_invocation(argv):
        from brandx.session import run_session
        focused = argv[0] if argv else None
        sys.exit(run_session(focused))

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        sys.exit(_cmd_init(args))
    elif args.command == "render":
        sys.exit(_cmd_render(args))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
