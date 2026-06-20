"""Shared structural pass — the common pipeline both renderers consume.

Responsibilities:
    - Parse YAML frontmatter from a markdown file (real YAML via pyyaml, nested keys).
    - Extract the document title (frontmatter wins; otherwise the first H1, which is
      then stripped from the body so it is not rendered twice).
    - Run python-markdown with the KTD1 extension set to produce structural HTML.
    - Reset the markdown instance between documents to avoid cross-document state.
    - Call callouts.split_alerts() so each renderer receives pre-processed alert HTML.

The pipeline produces a ParsedDocument that each renderer consumes directly.
It does not apply any surface-specific styling — that is each renderer's job.

Usage:
    from brandx.render.pipeline import parse_document
    doc = parse_document(Path("report.md"))
    doc.title, doc.body_html, doc.frontmatter
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from brandx.render.callouts import process_alerts


# ---------------------------------------------------------------------------
# Markdown instance (module-level, reset between documents)
# ---------------------------------------------------------------------------

def _make_md():
    """Build the shared python-markdown instance with the KTD1 extension set."""
    import markdown
    return markdown.Markdown(
        extensions=[
            "tables",
            "fenced_code",
            "attr_list",
            "smarty",
            "codehilite",
        ],
        extension_configs={
            "codehilite": {
                "noclasses": True,
                "guess_lang": False,
            },
        },
    )


# ---------------------------------------------------------------------------
# Frontmatter parsing (real YAML)
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Strip YAML frontmatter from markdown text; return (meta, body).

    Frontmatter is delimited by ``---`` fences. Keys are parsed as nested
    YAML (not flat splitter as in the prototype). Missing frontmatter returns
    ({}, original_text).
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}, text
    try:
        raw = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}, text
    meta = raw if isinstance(raw, dict) else {}
    body = text[m.end():]
    return meta, body


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------

def _extract_title(
    meta: dict[str, Any], body: str
) -> tuple[str, str, bool]:
    """Return (title, body, title_from_heading).

    Priority: frontmatter 'title' key > first H1 in the body.
    When the title comes from a heading, title_from_heading is True and
    the caller must strip that heading from the rendered HTML.
    """
    title = (meta.get("title") or "").strip()
    if title:
        return title, body, False

    h1 = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    if h1:
        return h1.group(1).strip(), body, True

    return "", body, False


# ---------------------------------------------------------------------------
# ParsedDocument
# ---------------------------------------------------------------------------

@dataclass
class ParsedDocument:
    """The result of running a markdown file through the shared structural pass.

    Attributes:
        title: Resolved document title (may be empty string).
        subtitle: Optional subtitle from frontmatter.
        date_raw: Raw 'date' value from frontmatter (string, or None).
        mark: Identity mark selection from frontmatter ('monogram'/'avatar'/None).
        frontmatter: Full parsed frontmatter dict.
        body_html: Structural HTML produced by the markdown pipeline,
                   with alerts already processed by callouts.process_alerts().
        title_from_heading: True when the title was extracted from the first H1.
        source_dir: Directory of the source file (for relative asset resolution).
    """

    title: str
    subtitle: str
    date_raw: str | None
    mark: str | None
    frontmatter: dict[str, Any]
    body_html: str
    title_from_heading: bool
    source_dir: Path = field(default_factory=Path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_document(source: Path) -> ParsedDocument:
    """Parse a markdown file through the shared structural pass.

    Args:
        source: Path to the markdown file.

    Returns:
        A ParsedDocument ready for consumption by either renderer.
    """
    text = source.read_text(encoding="utf-8")
    return parse_text(text, source_dir=source.parent)


def parse_text(text: str, source_dir: Path | None = None) -> ParsedDocument:
    """Parse markdown text through the shared structural pass.

    Args:
        text: Raw markdown content (may include frontmatter).
        source_dir: Directory to resolve relative asset paths against.

    Returns:
        A ParsedDocument.
    """
    if source_dir is None:
        source_dir = Path(".")

    meta, body = _parse_frontmatter(text)
    title, body, title_from_heading = _extract_title(meta, body)

    md = _make_md()
    body_html = md.convert(body)
    md.reset()

    if title_from_heading:
        body_html = re.sub(r"<h1[^>]*>.*?</h1>\s*", "", body_html, count=1)

    body_html = process_alerts(body_html)

    return ParsedDocument(
        title=title,
        subtitle=(meta.get("subtitle") or "").strip(),
        date_raw=str(meta["date"]) if "date" in meta else None,
        mark=meta.get("mark"),
        frontmatter=meta,
        body_html=body_html,
        title_from_heading=title_from_heading,
        source_dir=source_dir,
    )
