"""brandx CLI entry point.

Subcommands:
    init      Write a starter brand config to the home location.
    render    Render a markdown file to a branded document or email.

Usage:
    brandx --help
    brandx init [--force]
    brandx render <file.md> [--email] [-o OUTPUT] [--open] [--preview] [--brand PATH]
"""

import argparse
import sys


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
        help="Open a temporary browser preview (implied when no --output given).",
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


def _cmd_init(_args) -> int:
    print("Error: 'init' not yet implemented.", file=sys.stderr)
    return 1


def _cmd_render(_args) -> int:
    print("Error: 'render' not yet implemented.", file=sys.stderr)
    return 1


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "init":
        sys.exit(_cmd_init(args))
    elif args.command == "render":
        sys.exit(_cmd_render(args))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
