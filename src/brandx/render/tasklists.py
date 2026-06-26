"""GitHub-style task-list rendering.

python-markdown has no native task-list support, so ``- [ ]`` / ``- [x]`` list
items render with a literal ``[ ]`` / ``[x]`` prefix in the output. This module
post-processes the structural HTML, rewriting those items as checkbox list
items that render correctly on both surfaces (branded HTML document and
Outlook-safe email).

A Unicode ballot-box glyph (☐ / ☑) is used rather than an
``<input type="checkbox">``: the glyph renders identically in browsers and in
Outlook's Word engine, which does not render form controls. This keeps a single
code path for both renderers.

Output: each rewritten ``<li>`` gains the ``task-list-item`` class and its
marker becomes a ``task-checkbox`` span carrying the glyph. The document
renderer styles these via CSS; the email renderer suppresses the bullet inline.

Usage:
    from brandx.render.tasklists import process_tasklists
    body_html = process_tasklists(raw_html)
"""

from __future__ import annotations

import re

_UNCHECKED = "☐"  # ☐ BALLOT BOX
_CHECKED = "☑"  # ☑ BALLOT BOX WITH CHECK

# Matches a task-list marker at the very start of an <li>'s content. For simple
# items python-markdown emits `<li>[ ] text</li>`; for items with block content
# it emits `<li>\n<p>[ ] text</p>...`. Both start the visible text with the
# marker, optionally wrapped in an opening <p>.
_TASK_RE = re.compile(
    r"(<li[^>]*>\s*)(<p[^>]*>\s*)?\[([ xX])\]\s+",
)


def _add_class(li_open_tag: str, cls: str) -> str:
    """Add a class to an <li> opening tag, merging with any existing class."""
    if 'class="' in li_open_tag:
        return re.sub(
            r'class="([^"]*)"', rf'class="\1 {cls}"', li_open_tag, count=1
        )
    return li_open_tag.replace("<li", f'<li class="{cls}"', 1)


def process_tasklists(html_body: str) -> str:
    """Convert GitHub task-list items into checkbox list items.

    Args:
        html_body: Structural HTML from the python-markdown pass.

    Returns:
        HTML with ``[ ]`` / ``[x]`` list items rewritten as checkbox items.
    """

    def repl(m: re.Match) -> str:
        li_open, p_open, state = m.group(1), m.group(2) or "", m.group(3)
        checked = state in ("x", "X")
        glyph = _CHECKED if checked else _UNCHECKED
        label = "checked" if checked else "unchecked"
        li_open = _add_class(li_open, "task-list-item")
        span = (
            f'<span class="task-checkbox" role="img" '
            f'aria-label="{label}">{glyph}</span> '
        )
        return f"{li_open}{p_open}{span}"

    return _TASK_RE.sub(repl, html_body)
