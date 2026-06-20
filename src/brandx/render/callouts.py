"""GitHub-style alert detection and consecutive-blockquote splitting.

python-markdown merges consecutive blockquotes (e.g. stacked [!NOTE] and
[!WARNING]) into a single <blockquote> element. This module splits the merged
content by finding paragraphs that begin with [!TYPE] markers, then emits
typed callout markers that each renderer converts to its own HTML structure.

The split algorithm is ported from the prototype's _split_blockquote_paragraphs
(ea2email.py), which handles all edge cases correctly. The prototype's
style_github_alerts in ea2html.py uses only a single-blockquote regex and would
silently miss the second callout when two are stacked — this module does not
replicate that bug.

Output markers emitted into the HTML body:
    <!-- bx:alert type="note" -->...<!-- /bx:alert -->
    <!-- bx:blockquote -->...<!-- /bx:blockquote -->

These markers are neutral structural annotations; each renderer replaces them
with its own surface-appropriate HTML.

Usage:
    from brandx.render.callouts import process_alerts
    body_html = process_alerts(raw_html)
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Alert type mapping
# ---------------------------------------------------------------------------

_ALERT_TYPES = {
    "note": "note",
    "info": "note",
    "tip": "tip",
    "important": "important",
    "warning": "warning",
    "error": "warning",
    "caution": "caution",
    "danger": "caution",
}

_ALERT_TYPES_PATTERN = "|".join(_ALERT_TYPES.keys())
_ALERT_OPEN_RE = re.compile(
    rf"\[!({_ALERT_TYPES_PATTERN})\][ \t]*\n?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Blockquote paragraph splitting
# ---------------------------------------------------------------------------

def _split_blockquote_paragraphs(
    inner_html: str,
) -> list[tuple[bool, str | None, str]]:
    """Split the inner HTML of a blockquote into typed chunks.

    Returns a list of (is_alert, alert_type_or_None, html_content) tuples.
    Each tuple represents one logical callout or plain blockquote chunk.

    This is the correct splitter: it handles stacked alerts in one merged
    blockquote by iterating over all paragraphs rather than matching only
    the first.
    """
    paras = re.findall(r"<p>(.*?)</p>", inner_html, re.DOTALL)

    chunks: list[tuple[bool, str | None, str]] = []
    i = 0
    while i < len(paras):
        para = paras[i]
        alert_m = _ALERT_OPEN_RE.match(para.strip())
        if alert_m:
            key = alert_m.group(1).lower()
            alert_type = _ALERT_TYPES[key]
            first_content = para[alert_m.end():].strip()
            body_parts: list[str] = []
            if first_content:
                body_parts.append(f"<p>{first_content}</p>")
            j = i + 1
            while j < len(paras):
                if _ALERT_OPEN_RE.match(paras[j].strip()):
                    break
                body_parts.append(f"<p>{paras[j]}</p>")
                j += 1
            chunks.append((True, alert_type, "".join(body_parts)))
            i = j
        else:
            plain_parts = [f"<p>{para}</p>"]
            j = i + 1
            while j < len(paras):
                if _ALERT_OPEN_RE.match(paras[j].strip()):
                    break
                plain_parts.append(f"<p>{paras[j]}</p>")
                j += 1
            chunks.append((False, None, "".join(plain_parts)))
            i = j

    return chunks


# ---------------------------------------------------------------------------
# HTML annotation markers
# ---------------------------------------------------------------------------

def _alert_marker(alert_type: str, body_html: str) -> str:
    return (
        f'<!-- bx:alert type="{alert_type}" -->'
        f"{body_html}"
        f"<!-- /bx:alert -->"
    )


def _blockquote_marker(body_html: str) -> str:
    return (
        f"<!-- bx:blockquote -->"
        f"{body_html}"
        f"<!-- /bx:blockquote -->"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_alerts(html_body: str) -> str:
    """Replace <blockquote> elements with typed bx: markers.

    Blockquotes containing [!TYPE] markers become bx:alert markers.
    Blockquotes without markers become bx:blockquote markers.
    Both marker forms are then rendered by each surface renderer.

    Args:
        html_body: Structural HTML from the python-markdown pass.

    Returns:
        HTML with blockquotes replaced by bx: markers.
    """

    def replace_blockquote(m: re.Match) -> str:
        inner = m.group(1)
        chunks = _split_blockquote_paragraphs(inner)

        if not any(is_alert for is_alert, _, _ in chunks):
            return _blockquote_marker(inner.strip())

        parts: list[str] = []
        for is_alert, alert_type, body_html in chunks:
            if is_alert:
                parts.append(_alert_marker(alert_type, body_html))
            else:
                parts.append(_blockquote_marker(body_html))
        return "".join(parts)

    return re.sub(
        r"<blockquote>(.*?)</blockquote>",
        replace_blockquote,
        html_body,
        flags=re.DOTALL,
    )


def alert_type_for_key(raw_key: str) -> str | None:
    """Return the normalised alert type for a raw [!KEY], or None if unknown."""
    return _ALERT_TYPES.get(raw_key.lower())
