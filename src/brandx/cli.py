"""brandx CLI entry point.

Running `brandx` with no subcommand (optionally `brandx <file.md>`) launches the
interactive session (see brandx.session). `init` and `render` stay explicit
subcommands; `render` is the unchanged, pipeable one-shot.

Subcommands:
    init       Write a starter brand config to the home location.
    render     Render a markdown file to a branded document or email.
    watermark  Read a hidden watermark back out of a file or stdin.

Usage:
    brandx                   Launch the interactive session (unfocused).
    brandx <file.md>         Launch the session focused on a file.
    brandx --help
    brandx init [--force]
    brandx render <file.md> [--email] [-o OUTPUT] [--open] [--preview]
                            [--clipboard] [--brand PATH] [--mark monogram|avatar]
                            [--letterhead | --no-letterhead]
                            [--watermark ID | --no-watermark] [--set KEY=VALUE ...]
    brandx watermark [FILE] [--all]

Watermark precedence for render (highest first):
    --no-watermark       Suppress a frontmatter watermark.
    --watermark ID       Use ID.
    frontmatter          `watermark: ID` in the document.

Destination precedence for render (pick exactly one):
    --clipboard          Copy rich text to the macOS clipboard.
    -o / --output FILE   Write HTML to FILE; combine with --open to also
                         open in the browser.
    --preview            Write to a temp file and open in the browser.
    (none)               Print HTML to stdout (pipeable).

Exit codes for watermark:
    0   A payload was recovered and printed to stdout.
    1   The input could not be read.
    2   No valid watermark was found.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="brandx",
        description="Render markdown to a branded document or Outlook-safe email.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 1.3.0")

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    _add_init_subcommand(subparsers)
    _add_render_subcommand(subparsers)
    _add_watermark_subcommand(subparsers)

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
        description=(
            "Render a markdown file to a branded document or Outlook-safe email. "
            "Pick one destination; precedence is --clipboard, then -o/--output, "
            "then --preview. With no destination flag, the HTML is written to "
            "stdout so it can be piped."
        ),
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
        help="Write to a temp file and open it in the browser.",
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
    letterhead_group = sub.add_mutually_exclusive_group()
    letterhead_group.add_argument(
        "--letterhead",
        dest="letterhead",
        action="store_true",
        default=None,
        help="Show the letterhead banner (mark, name, role, date). Off by default.",
    )
    letterhead_group.add_argument(
        "--no-letterhead",
        dest="letterhead",
        action="store_false",
        default=None,
        help="Hide the letterhead banner, overriding a config that turns it on.",
    )
    watermark_group = sub.add_mutually_exclusive_group()
    watermark_group.add_argument(
        "--watermark",
        metavar="ID",
        default=None,
        help=(
            "Hide ID in the output as zero-width characters, repeated at every "
            "paragraph. Read it back with `brandx watermark`."
        ),
    )
    watermark_group.add_argument(
        "--no-watermark",
        dest="no_watermark",
        action="store_true",
        help="Suppress a watermark set in the document frontmatter.",
    )
    sub.add_argument(
        "--set",
        metavar="KEY=VALUE",
        action="append",
        dest="set_flags",
        help="Override a config value using dotted key notation, e.g. --set colours.accent=#e63946. Repeatable.",
    )


def _add_watermark_subcommand(subparsers):
    sub = subparsers.add_parser(
        "watermark",
        help="Read a hidden watermark back out of a file or stdin.",
        description=(
            "Recover the id hidden by `brandx render --watermark ID`. Reads a "
            "file, or stdin when FILE is omitted or '-'. The input can be the "
            "rendered HTML, a saved reply, or pasted plain text: the watermark "
            "survives the conversion. Prints the payload to stdout and exits 0; "
            "exits 2 when nothing valid is found."
        ),
    )
    sub.add_argument(
        "input",
        metavar="FILE",
        nargs="?",
        default="-",
        help="File to read. Omit or pass '-' to read stdin.",
    )
    sub.add_argument(
        "--all",
        action="store_true",
        dest="show_all",
        help="Print every distinct payload found, one per line, not just the first.",
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
    letterhead: bool | None = None,
    set_flags: dict[str, str] | None = None,
    watermark: str | None = None,
    no_watermark: bool = False,
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
        letterhead: Optional letterhead banner override. None leaves the cascade
            to decide; True or False wins over the config.
        set_flags: Already-validated dotted-key overrides.
        watermark: Optional id to hide in the output as zero-width characters.
            Wins over the document's `watermark:` frontmatter key.
        no_watermark: Suppress a frontmatter watermark for this render.

    Returns:
        (html, ResolvedConfig, brand_source_label).

    Raises:
        RenderInputError: when the input file is missing, the brand config
            cannot be loaded, or the watermark payload cannot be encoded. All
            callers handle this rather than exiting here.
    """
    from brandx.config.discovery import load_home_config
    from brandx.config.resolver import resolve
    from brandx.render.document import render_document
    from brandx.render.email import render_email
    from brandx.render.pipeline import parse_document
    from brandx.watermark import WatermarkError

    # load_home_config calls sys.exit on a missing/malformed explicit brand file.
    # Translate that into RenderInputError so the session can survive it.
    try:
        home, source = load_home_config(explicit_path=brand_path)
    except SystemExit as exc:
        raise RenderInputError(str(exc)) from exc

    if not input_path.is_file():
        raise RenderInputError(f"Error: input file not found: {input_path}")

    doc = parse_document(input_path)

    flags: dict[str, Any] = dict(set_flags or {})
    if mark is not None:
        flags["identity.mark"] = mark
    if letterhead is not None:
        flags["identity.letterhead"] = letterhead

    # Resolve the cascade. Document metadata in the frontmatter (title, date, and
    # similar) is harmless: the resolver ignores unknown top-level keys and a
    # scalar cannot clobber a nested brand block (see _deep_merge).
    cfg = resolve(home_config=home, frontmatter=doc.frontmatter, flags=flags)

    # Watermark precedence: --no-watermark, then --watermark, then frontmatter.
    if no_watermark:
        effective_watermark = None
    elif watermark is not None:
        effective_watermark = watermark
    else:
        effective_watermark = doc.watermark

    # A malformed watermark is user error, not a crash: surface it the same way
    # a missing input file is surfaced, so the session survives it too.
    try:
        html = (
            render_email(doc, cfg, watermark=effective_watermark)
            if email
            else render_document(doc, cfg, watermark=effective_watermark)
        )
    except WatermarkError as exc:
        raise RenderInputError(f"Error: {exc}") from exc

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
            letterhead=args.letterhead,
            set_flags=set_flags,
            watermark=args.watermark,
            no_watermark=args.no_watermark,
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


def _cmd_watermark(args) -> int:
    from brandx.watermark import extract_all

    if args.input == "-":
        raw = sys.stdin.buffer.read()
    else:
        source = Path(args.input)
        if not source.is_file():
            print(f"Error: input file not found: {source}", file=sys.stderr)
            return 1
        raw = source.read_bytes()

    # errors="replace" rather than a hard decode: an exported reply can carry
    # any encoding, and a mangled byte only costs the one copy of the token it
    # sits in. The other copies are why the token is repeated.
    text = raw.decode("utf-8", errors="replace")

    payloads = extract_all(text)
    if not payloads:
        print("No watermark found.", file=sys.stderr)
        return 2

    for payload in (payloads if args.show_all else payloads[:1]):
        print(payload)
    return 0


_SUBCOMMANDS = {"init", "render", "watermark"}


def _is_session_invocation(argv: list[str]) -> bool:
    """True when argv should launch the interactive session rather than argparse.

    Bare `brandx` (no args) and `brandx <file>` start the session. A leading
    subcommand from _SUBCOMMANDS, or a leading flag (`-h`, `--help`,
    `--version`), routes to the one-shot parser instead.
    """
    if not argv:
        return True
    first = argv[0]
    return first not in _SUBCOMMANDS and not first.startswith("-")


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
    elif args.command == "watermark":
        sys.exit(_cmd_watermark(args))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
