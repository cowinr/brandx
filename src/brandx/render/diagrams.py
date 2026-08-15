"""Mermaid diagram extraction, rendering, and substitution.

Turns fenced ```mermaid blocks in a markdown source into rendered diagram
images. Extraction runs on the raw markdown text, before python-markdown
converts it: codehilite (noclasses=True) strips the language name from a
fenced block, so a mermaid fence is indistinguishable from a plain fence
once it reaches HTML. Rendering shells out once per document to the
mermaid-cli (`mmdc`) binary, batching every diagram into a single Chrome
launch. Results are cached on disk, keyed on the diagram source and its
render settings, so a re-render with nothing changed launches no subprocess.
Any failure (mmdc missing, mmdc failing, an unreadable output file) degrades
to leaving the affected diagrams unrendered; nothing in this module raises.

Usage:
    from brandx.render.diagrams import extract_diagrams, render_diagrams, substitute

    body, sources = extract_diagrams(raw_markdown)
    html = md.convert(body)
    rendered = render_diagrams(sources, cfg, "svg")
    html = substitute(html, rendered, sources, "svg", build_image, build_fallback)
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from brandx.config.resolver import ResolvedConfig


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

# A fence opens at the very start of a line (so an indented code block never
# matches), with 3+ backtick or tilde characters, an info string of exactly
# "mermaid", and closes with the identical fence string. Requiring the
# closing fence to match the opening one exactly, rather than merely be no
# shorter, is a deliberate simplification rather than a full CommonMark
# parser: it also means a fence nested inside a longer one (four backticks
# wrapping a diagram source that itself contains a triple-backtick line) is
# handled correctly, since the inner triple-backtick line cannot close it.
_MERMAID_FENCE_RE = re.compile(
    r"^(?P<fence>`{3,}|~{3,})[ \t]*mermaid[ \t]*\n"
    r"(?P<body>.*?)"
    r"^(?P=fence)[ \t]*(?:\n|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)


def extract_diagrams(markdown_text: str) -> tuple[str, list[str]]:
    """Pull every mermaid fence out of raw markdown, in document order.

    Each fence is replaced by a blank-line-delimited HTML comment marker,
    ``<!-- bx:mermaid id="N" -->``, which survives python-markdown's
    conversion unwrapped at block level. A fence indented as part of an
    indented code block, or one with no matching closing fence, is left
    untouched (see the regex comment above for the exact limitation).

    Args:
        markdown_text: Raw markdown, before md.convert(). Frontmatter may
            or may not already be stripped; this function does not care.

    Returns:
        (rewritten_text, sources): the markdown with every mermaid fence
        replaced by its marker, and the diagram sources in document order,
        matching the marker ids.
    """
    sources: list[str] = []
    parts: list[str] = []
    last_end = 0

    for match in _MERMAID_FENCE_RE.finditer(markdown_text):
        parts.append(markdown_text[last_end : match.start()])
        body = match.group("body")
        if body.endswith("\n"):
            body = body[:-1]
        idx = len(sources)
        sources.append(body)
        parts.append(f'\n\n<!-- bx:mermaid id="{idx}" -->\n\n')
        last_end = match.end()

    parts.append(markdown_text[last_end:])
    return "".join(parts), sources


# ---------------------------------------------------------------------------
# Theme mapping
# ---------------------------------------------------------------------------

def _theme_variables(colours, fonts) -> dict:
    """Map the brandx palette onto mermaid's themeVariables for theme 'brand'."""
    return {
        "primaryColor": colours.get("surface", "#f4f7f8"),
        "primaryBorderColor": colours.get("primary", "#1c2b39"),
        "primaryTextColor": colours.get("text", "#1f2933"),
        "secondaryColor": colours.get("info_bg", "#e6f4f2"),
        "secondaryBorderColor": colours.get("secondary", "#0d8a7d"),
        "secondaryTextColor": colours.get("text", "#1f2933"),
        "tertiaryColor": colours.get("emphasis_bg", "#fdf3e3"),
        "tertiaryBorderColor": colours.get("emphasis", "#b07514"),
        "tertiaryTextColor": colours.get("text", "#1f2933"),
        "lineColor": colours.get("accent", "#0d8a7d"),
        "textColor": colours.get("text", "#1f2933"),
        "mainBkg": colours.get("surface", "#f4f7f8"),
        "nodeBorder": colours.get("primary", "#1c2b39"),
        "clusterBkg": colours.get("surface", "#f4f7f8"),
        "clusterBorder": colours.get("border", "#e2e8ec"),
        "titleColor": colours.get("primary", "#1c2b39"),
        # The default palette carries no 'background' key; a brand config
        # that adds one overrides the edge-label background deliberately.
        "edgeLabelBackground": colours.get("background", "#ffffff"),
        "noteBkgColor": colours.get("warning_bg", "#fdf3e3"),
        "noteTextColor": colours.get("warning_text", "#b07514"),
        "noteBorderColor": colours.get("emphasis", "#b07514"),
        "fontFamily": fonts.get("font", "'Inter', -apple-system, 'Segoe UI', Arial, sans-serif"),
    }


def _mermaid_config(theme: str, colours, fonts) -> dict | None:
    """Build the mermaid -c config for theme 'brand'; None for a named built-in theme."""
    if theme != "brand":
        return None
    return {
        "theme": "base",
        "themeVariables": _theme_variables(colours, fonts),
        "flowchart": {"useMaxWidth": True},
    }


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _cache_dir() -> Path:
    """Return the on-disk diagram cache directory, honouring XDG_CACHE_HOME."""
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "brandx" / "diagrams"


def _cache_key(source: str, theme_json: str, fmt: str, scale) -> str:
    """Return the cache key for one diagram: sha256(source + theme_json + fmt + scale)."""
    material = source + theme_json + fmt + str(scale)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Browser discovery
# ---------------------------------------------------------------------------

_MACOS_CHROME_PATHS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
)

_CHROME_EXECUTABLE_NAMES = (
    "google-chrome-stable",
    "google-chrome",
    "chromium",
    "chromium-browser",
)


def _find_chrome() -> str | None:
    """Locate a Chrome-family browser for mmdc's Puppeteer. First hit wins.

    Order: BRANDX_CHROME, PUPPETEER_EXECUTABLE_PATH, known macOS app
    paths, then a handful of Linux executable names on PATH. None found
    means mmdc runs without an explicit browser and falls back to its own
    bundled Puppeteer cache.
    """
    for env_var in ("BRANDX_CHROME", "PUPPETEER_EXECUTABLE_PATH"):
        value = os.environ.get(env_var)
        if value:
            return value
    for candidate in _MACOS_CHROME_PATHS:
        if Path(candidate).exists():
            return candidate
    for name in _CHROME_EXECUTABLE_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


# ---------------------------------------------------------------------------
# mmdc invocation
# ---------------------------------------------------------------------------

_MMDC_ABSENT_MSG = (
    "brandx: mermaid diagrams skipped — mmdc not found. "
    "Install with: npm install -g @mermaid-js/mermaid-cli"
)
_MMDC_FAILED_MSG = (
    "brandx: mermaid diagrams skipped — mmdc failed. If the error mentions Chrome, "
    "set BRANDX_CHROME to a Chrome or Chromium binary, or run: "
    "npx puppeteer browsers install chrome-headless-shell"
)

_SUBPROCESS_TIMEOUT_SECONDS = 60


def _call_mmdc(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run the mmdc subprocess. The sole call site, so tests can monkeypatch it."""
    return subprocess.run(cmd, capture_output=True, timeout=_SUBPROCESS_TIMEOUT_SECONDS)


def _render_batch(
    sources: list[str],
    mermaid_config: dict | None,
    theme: str,
    background: str,
    scale,
    fmt: str,
) -> list[bytes | None] | None:
    """Render a batch of mermaid sources in one mmdc subprocess call.

    One temp markdown file holds every source as its own ```mermaid fence,
    so mmdc launches Chrome once and writes one numbered output file per
    diagram. Returns one entry per source (raw output bytes, or None for a
    diagram whose output file was missing), or None outright if mmdc is not
    on PATH, the subprocess fails, or it times out. Prints at most one
    warning to stderr regardless of how many diagrams in the batch fail.
    """
    mmdc_path = shutil.which("mmdc")
    if mmdc_path is None:
        print(_MMDC_ABSENT_MSG, file=sys.stderr)
        return None

    with tempfile.TemporaryDirectory(prefix="brandx-mermaid-") as tmp:
        tmp_dir = Path(tmp)
        in_md = tmp_dir / "in.md"
        out_md = tmp_dir / "out.md"
        in_md.write_text(
            "\n\n".join(f"```mermaid\n{source}\n```" for source in sources) + "\n",
            encoding="utf-8",
        )

        cmd = [
            mmdc_path, "-i", str(in_md), "-o", str(out_md),
            "-e", fmt, "-b", background, "-q",
        ]

        if mermaid_config is not None:
            cfg_path = tmp_dir / "cfg.json"
            cfg_path.write_text(json.dumps(mermaid_config), encoding="utf-8")
            cmd += ["-c", str(cfg_path)]
        else:
            cmd += ["-t", theme]

        if fmt == "png":
            cmd += ["-s", str(scale)]

        chrome = _find_chrome()
        if chrome is not None:
            pptr_path = tmp_dir / "pptr.json"
            pptr_path.write_text(
                json.dumps({"executablePath": chrome, "args": ["--no-sandbox"]}),
                encoding="utf-8",
            )
            cmd += ["-p", str(pptr_path)]

        try:
            proc = _call_mmdc(cmd)
        except (subprocess.TimeoutExpired, OSError):
            print(_MMDC_FAILED_MSG, file=sys.stderr)
            return None

        if proc.returncode != 0:
            print(_MMDC_FAILED_MSG, file=sys.stderr)
            return None

        outputs: list[bytes | None] = []
        any_missing = False
        for i in range(1, len(sources) + 1):
            out_path = tmp_dir / f"out-{i}.{fmt}"
            if out_path.exists():
                outputs.append(out_path.read_bytes())
            else:
                outputs.append(None)
                any_missing = True

        if any_missing:
            print(_MMDC_FAILED_MSG, file=sys.stderr)

        return outputs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_diagrams(sources: list[str], cfg: ResolvedConfig, fmt: str) -> list[str | None]:
    """Render mermaid diagram sources to SVG text or base64-encoded PNG.

    Every diagram already cached under identical settings skips the
    subprocess entirely; a cache miss triggers exactly one batched mmdc
    call for the whole document, one Chrome launch regardless of how many
    diagrams miss. Any failure degrades to None for the affected diagrams;
    this function never raises.

    Args:
        sources: Mermaid diagram sources, in document order (as returned
            by extract_diagrams).
        cfg: Resolved brand configuration.
        fmt: 'svg' or 'png'. SVG entries are the rendered file's raw text;
            PNG entries are the rendered file's bytes, base64-encoded.

    Returns:
        One entry per source: rendered text/base64, or None when that
        diagram could not be rendered (including when diagrams are
        disabled in config, in which case every entry is None).
    """
    if not sources:
        return []

    diagrams_cfg = dict(cfg.diagrams)
    if not diagrams_cfg.get("enabled", True):
        return [None] * len(sources)

    theme = diagrams_cfg.get("theme", "brand")
    background = diagrams_cfg.get("background", "white")
    scale = diagrams_cfg.get("scale", 2)

    mermaid_config = _mermaid_config(theme, cfg.colours, cfg.fonts)
    theme_json = (
        json.dumps(mermaid_config, sort_keys=True) if mermaid_config is not None else theme
    )

    ext = "svg" if fmt == "svg" else "png"
    cache_dir = _cache_dir()

    results: list[str | None] = [None] * len(sources)
    cache_paths: list[Path] = []
    misses: list[int] = []

    for i, source in enumerate(sources):
        key = _cache_key(source, theme_json, fmt, scale)
        path = cache_dir / f"{key}.{ext}"
        cache_paths.append(path)
        if path.exists():
            data = path.read_bytes()
            results[i] = (
                data.decode("utf-8") if fmt == "svg" else base64.b64encode(data).decode("ascii")
            )
        else:
            misses.append(i)

    if not misses:
        return results

    rendered = _render_batch(
        [sources[i] for i in misses], mermaid_config, theme, background, scale, ext,
    )
    if rendered is None:
        return results

    cache_dir.mkdir(parents=True, exist_ok=True)
    for miss_pos, data in zip(misses, rendered):
        if data is None:
            continue
        cache_paths[miss_pos].write_bytes(data)
        results[miss_pos] = (
            data.decode("utf-8") if fmt == "svg" else base64.b64encode(data).decode("ascii")
        )

    return results


_MARKER_RE = re.compile(r'<!-- bx:mermaid id="(\d+)" -->')


def substitute(
    html: str,
    rendered: list[str | None],
    sources: list[str],
    fmt: str,
    build_image: Callable[[str, int], str],
    build_fallback: Callable[[str], str],
) -> str:
    """Replace every bx:mermaid marker with rendered image or fallback markup.

    Each renderer supplies its own builders because the surrounding markup
    differs by surface (an inline SVG <img> in a <div>, versus a sized PNG
    <img> in an Outlook presentation table): build_image(rendered_entry,
    index) handles a successfully rendered diagram; build_fallback(source)
    handles one that could not be rendered, escaping the mermaid source
    into a plain code block so the reader still sees the diagram text.

    Args:
        html: Structural HTML containing bx:mermaid markers.
        rendered: render_diagrams() output, one entry per source.
        sources: The mermaid sources extracted alongside the markers.
        fmt: 'svg' or 'png'. Unused here; kept for symmetry with
            render_diagrams, since callers already specialise their
            builders by format.
        build_image: Called for a diagram that rendered successfully.
        build_fallback: Called for a diagram that could not be rendered.

    Returns:
        HTML with every bx:mermaid marker replaced.
    """

    def _replace(m: re.Match) -> str:
        idx = int(m.group(1))
        entry = rendered[idx] if idx < len(rendered) else None
        if entry is not None:
            return build_image(entry, idx)
        source = sources[idx] if idx < len(sources) else ""
        return build_fallback(source)

    return _MARKER_RE.sub(_replace, html)
