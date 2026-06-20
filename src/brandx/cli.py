"""brandx CLI entry point.

Subcommands:
    init      Write a starter brand config to the home location.
    render    Render a markdown file to a branded document or email.

Usage:
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
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

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


def _cmd_render(args) -> int:
    from brandx.clipboard import copy_html
    from brandx.config.discovery import load_home_config
    from brandx.config.resolver import resolve
    from brandx.output import open_in_browser, preview, write_file
    from brandx.render.document import render_document
    from brandx.render.email import render_email
    from brandx.render.pipeline import parse_document

    # 1. Load home config.
    home, _source = load_home_config(explicit_path=args.brand)

    # 2. Parse the document.
    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    doc = parse_document(input_path)

    # 3. Build flags dict from CLI overrides.
    flags: dict[str, str] = {}

    for item in (args.set_flags or []):
        if "=" not in item:
            print(
                f"Error: --set requires KEY=VALUE form, got: {item!r}",
                file=sys.stderr,
            )
            return 1
        key, _, value = item.partition("=")
        flags[key] = value

    if args.mark is not None:
        flags["identity.mark"] = args.mark

    # 4. Resolve the cascade.
    cfg = resolve(home_config=home, frontmatter=doc.frontmatter, flags=flags)

    # 5. Render.
    html = render_email(doc, cfg) if args.email else render_document(doc, cfg)

    # 6. Dispatch to the chosen destination.
    #    Precedence: --clipboard > -o/--output > --preview > stdout.
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


def main(argv: list[str] | None = None) -> None:
    """Entry point. Accepts an optional argv list for testing; defaults to sys.argv."""
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
