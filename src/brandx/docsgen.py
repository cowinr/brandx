"""Config-reference doc generation — renders every brand key with its purpose.

Generates a markdown config-reference document from the application defaults
single source (DEFAULTS in brandx.config.defaults). The generated file cannot
drift from the code: a new key cannot ship without its purpose text, and the
reference is regenerated from that same source.

Usage (programmatic):
    from brandx.docsgen import generate_reference_markdown
    md = generate_reference_markdown()

CLI (via brandx docsgen — if the subcommand is added in future):
    brandx docsgen > docs/config-reference.md
"""

from brandx.config.defaults import DEFAULTS


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

def _format_value(value) -> str:
    """Format a default value for display in the reference table."""
    if value is None:
        return "*(empty)*"
    return f"`{value}`"


def _render_block(node: dict, heading_prefix: str, depth: int) -> list[str]:
    """Recursively render a DEFAULTS block into markdown lines."""
    lines: list[str] = []
    heading_char = "#" * (depth + 2)

    for key, entry in node.items():
        if isinstance(entry, dict) and "value" in entry and "comment" in entry:
            value_str = _format_value(entry["value"])
            purpose = entry["purpose"]
            comment = entry["comment"]
            lines.append(f"**`{heading_prefix}{key}`**")
            lines.append("")
            lines.append(f"Default: {value_str}")
            lines.append("")
            lines.append(f"{purpose}")
            lines.append("")
            if comment:
                lines.append(f"*Config comment: {comment}*")
                lines.append("")
            lines.append("---")
            lines.append("")
        elif isinstance(entry, dict):
            block_heading = f"{heading_prefix}{key}"
            lines.append(f"{heading_char} `{block_heading}`")
            lines.append("")
            lines.extend(_render_block(entry, f"{heading_prefix}{key}.", depth + 1))

    return lines


def generate_reference_markdown() -> str:
    """Generate the full config-reference markdown document.

    Returns a markdown string listing every brand key, its default, its purpose,
    and its config comment. Generated from the DEFAULTS single source.
    """
    lines = [
        "# brandx config reference",
        "",
        "This document is generated from the application defaults source (`brandx.config.defaults`).",
        "Do not edit manually — regenerate with `brandx docsgen` after changing defaults.",
        "",
        "Keys are shown in their YAML dotted-path form.",
        "Nested blocks (e.g. `colours`) contain multiple keys; override any key individually.",
        "",
    ]

    lines.extend(_render_block(DEFAULTS, "", depth=0))

    return "\n".join(lines)


def write_reference(output_path) -> None:
    """Write the generated reference markdown to output_path."""
    from pathlib import Path
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    content = generate_reference_markdown()
    p.write_text(content, encoding="utf-8")
