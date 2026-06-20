"""Asset embedding helpers — base64 image embedding for both document and email surfaces.

Responsibilities:
    - Embed a single image file as a base64 data: URI string (for avatars in the letterhead).
    - Walk HTML and replace local <img src="..."> with base64 data: URIs.
    - Leave http(s):// and existing data: srcs untouched.
    - Warn to stderr (project convention: stderr-only for status) when a local file is missing.
    - Infer MIME type from file extension.

This module is surface-agnostic and is used by both the document renderer (U7)
and the email renderer (U8).

Usage:
    from brandx.render.assets import embed_images, file_to_data_uri
    html = embed_images(html, source_dir=Path("."))
    data_uri = file_to_data_uri(Path("avatar.png"))
"""

from __future__ import annotations

import base64
import mimetypes
import re
import sys
from pathlib import Path


# Fallback MIME types for common image extensions not covered by mimetypes on all platforms.
_MIME_FALLBACK: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


def _mime_for_path(path: Path) -> str:
    """Return the MIME type for an image path, defaulting to image/png."""
    suffix = path.suffix.lower()
    mime, _ = mimetypes.guess_type(str(path))
    return mime or _MIME_FALLBACK.get(suffix, "image/png")


def file_to_data_uri(path: Path) -> str | None:
    """Encode a local image file to a base64 data: URI string.

    Returns None and warns to stderr if the file does not exist or cannot
    be read. Returns None for http(s):// or existing data: paths
    (callers should check first).

    Args:
        path: Resolved path to the image file.

    Returns:
        A data:image/... URI string, or None on failure.
    """
    try:
        data = path.read_bytes()
    except (OSError, FileNotFoundError):
        print(
            f"brandx warning: asset not found or unreadable: {path}",
            file=sys.stderr,
        )
        return None
    mime = _mime_for_path(path)
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def embed_images(html: str, source_dir: Path) -> str:
    """Replace local <img src="..."> references with base64 data: URIs.

    Skips:
        - srcs that begin with http:// or https://
        - srcs that already begin with data:

    Warns to stderr and leaves the img src untouched when the referenced
    local file is missing.

    Args:
        html: HTML string that may contain <img> elements.
        source_dir: Directory to resolve relative image paths against.

    Returns:
        HTML with local img srcs replaced by data: URIs.
    """

    def replace_src(m: re.Match) -> str:
        src = m.group(1)
        # Leave remote and already-embedded srcs unchanged.
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        image_path = (source_dir / src).resolve()
        if not image_path.exists():
            print(
                f"brandx warning: image not found: {src} (resolved to {image_path})",
                file=sys.stderr,
            )
            return m.group(0)
        data_uri = file_to_data_uri(image_path)
        if data_uri is None:
            return m.group(0)
        # Replace the original src value in the matched attribute.
        return m.group(0).replace(src, data_uri, 1)

    # Match src="..." or src='...' inside img tags.
    return re.sub(
        r'<img\b[^>]*\bsrc=["\']([^"\']+)["\'][^>]*>',
        replace_src,
        html,
        flags=re.IGNORECASE,
    )
