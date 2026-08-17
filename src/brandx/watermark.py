"""Zero-width watermark — hide a short id in rendered output and read it back.

Responsibilities:
    - Encode a payload string as a run of invisible Unicode code points, framed by
      a delimiter and protected by a 16-bit checksum.
    - Inject the same token at every paragraph in a rendered body, so a reply that
      quotes only part of the message still carries at least one whole copy.
    - Recover and validate the payload from a reply, in HTML or in plain text.

Wire format:
    packet = PAYLOAD + ":" + CHECKSUM      (CHECKSUM is 4 lowercase hex digits)
    token  = ZW_DELIM + one zero-width character per packet bit + ZW_DELIM

Every packet character becomes 8 bits and every bit becomes one zero-width
character, so a payload costs 24 UTF-8 bytes per character at each injection
site. MAX_PAYLOAD_CHARS caps that, and email output has its own size warning.

The packet splits on the LAST separator, not the first. A payload may itself
contain a colon (an id such as "TRACK-ID:94827" is the obvious case) and a
first-separator split cannot round-trip one. The checksum is fixed width, so
the last separator is the unambiguous one.

Extraction runs twice when the first pass finds nothing: once over the text as
given, then once over an unescaped, tag-stripped copy. That second reading
recovers a token whose run a mail client has split with markup, or has written
back as numeric character references.

Usage:
    from brandx.watermark import inject, extract, extract_all

    html = inject(html, "T421")
    extract(reply_text)       # -> "T421", or None when nothing validates
"""

from __future__ import annotations

import html as _html_lib
import re

# ---------------------------------------------------------------------------
# Alphabet
# ---------------------------------------------------------------------------

# Written as escapes on purpose: the literal characters are invisible, so a
# source file holding them cannot be read, grepped, or diffed reliably.
ZW_ZERO = "\u200b"   # ZERO WIDTH SPACE       — bit 0
ZW_ONE = "\u200c"    # ZERO WIDTH NON-JOINER  — bit 1
ZW_DELIM = "\u200d"  # ZERO WIDTH JOINER      — frame boundary

SEPARATOR = ":"
CHECKSUM_DIGITS = 4
MAX_PAYLOAD_CHARS = 64

# Closing tags to inject before, most preferred first. Only the first kind
# present in the document is used, so a loose list item is not watermarked
# twice (its <p> already carries the token).
_INJECTION_TARGETS = ("</p>", "</li>")

_TOKEN_RE = re.compile(f"{ZW_DELIM}([{ZW_ZERO}{ZW_ONE}]+){ZW_DELIM}")
_CHECKSUM_RE = re.compile(rf"^[0-9a-f]{{{CHECKSUM_DIGITS}}}$")
_TAG_RE = re.compile(r"<[^>]+>")


class WatermarkError(ValueError):
    """Raised when a payload cannot be encoded. Carries a user-facing message."""


# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------

def compute_checksum(text: str) -> str:
    """Return the 16-bit rolling hash of text as four lowercase hex digits."""
    digest = 0
    for char in text:
        digest = (digest * 31 + ord(char)) % 65536
    return f"{digest:0{CHECKSUM_DIGITS}x}"


# ---------------------------------------------------------------------------
# Encode
# ---------------------------------------------------------------------------

def _validate_payload(payload: str) -> None:
    """Reject a payload the wire format cannot carry. Raises WatermarkError."""
    if not payload:
        raise WatermarkError("watermark payload must not be empty")

    if len(payload) > MAX_PAYLOAD_CHARS:
        raise WatermarkError(
            f"watermark payload is {len(payload)} characters; "
            f"the limit is {MAX_PAYLOAD_CHARS}. Every character costs 24 bytes "
            f"at every injection site."
        )

    # Each character is carried as 8 bits, so anything outside printable ASCII
    # would be truncated on the wire rather than round-tripped.
    rejected = sorted({char for char in payload if not 0x20 <= ord(char) <= 0x7E})
    if rejected:
        shown = ", ".join(repr(char) for char in rejected)
        raise WatermarkError(
            f"watermark payload must be printable ASCII; rejected: {shown}"
        )


def encode(payload: str) -> str:
    """Return the framed zero-width token carrying payload.

    Args:
        payload: The id to hide. Printable ASCII, 1 to MAX_PAYLOAD_CHARS long.

    Returns:
        A string of zero-width characters only.

    Raises:
        WatermarkError: when the payload is empty, over-long, or not ASCII.
    """
    _validate_payload(payload)

    packet = f"{payload}{SEPARATOR}{compute_checksum(payload)}"
    bits = "".join(format(ord(char), "08b") for char in packet)
    body = "".join(ZW_ONE if bit == "1" else ZW_ZERO for bit in bits)
    return f"{ZW_DELIM}{body}{ZW_DELIM}"


# ---------------------------------------------------------------------------
# Inject
# ---------------------------------------------------------------------------

def inject(html: str, payload: str) -> str:
    """Return html with the watermark token repeated through its text blocks.

    The token goes immediately before every closing paragraph tag, so trimming a
    quoted reply down to one paragraph still leaves a whole copy. A body with no
    paragraphs falls back to list items, and one with neither gets a single
    token appended.

    Args:
        html: Rendered HTML from either renderer.
        payload: The id to hide.

    Returns:
        The HTML with the token injected.

    Raises:
        WatermarkError: when the payload cannot be encoded.
    """
    token = encode(payload)

    for closing_tag in _INJECTION_TARGETS:
        if closing_tag in html:
            return html.replace(closing_tag, token + closing_tag)

    return html + token


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def _decode_token(run: str) -> str | None:
    """Return the validated payload of one delimited run, or None."""
    bits = "".join("1" if char == ZW_ONE else "0" for char in run)

    # A run whose length is not a whole number of bytes is truncated or merged.
    if len(bits) % 8:
        return None

    decoded = "".join(
        chr(int(bits[index:index + 8], 2)) for index in range(0, len(bits), 8)
    )

    # Split on the LAST separator: the payload may contain one, the checksum
    # may not (it is four hex digits).
    payload, separator, checksum = decoded.rpartition(SEPARATOR)
    if separator != SEPARATOR or not payload:
        return None
    if not _CHECKSUM_RE.match(checksum):
        return None
    if compute_checksum(payload) != checksum:
        return None

    return payload


def _readings(text: str):
    """Yield the text as given, then a relaxed copy, for extraction to try."""
    yield text

    # A client may have split a run with markup, or written the characters back
    # as numeric references. Unescape first, then drop tags, so a run broken by
    # a <span> rejoins.
    relaxed = _TAG_RE.sub("", _html_lib.unescape(text))
    if relaxed != text:
        yield relaxed


def extract_all(text: str) -> list[str]:
    """Return every distinct valid payload in text, in the order first seen.

    Args:
        text: HTML or plain text, typically a reply that quotes the original.

    Returns:
        A list of payloads. Empty when nothing validates.
    """
    for reading in _readings(text):
        found = [
            payload
            for payload in (_decode_token(m.group(1)) for m in _TOKEN_RE.finditer(reading))
            if payload is not None
        ]
        if found:
            # dict preserves insertion order and drops the repeats redundancy created.
            return list(dict.fromkeys(found))
    return []


def extract(text: str) -> str | None:
    """Return the first valid payload in text, or None when nothing validates."""
    found = extract_all(text)
    return found[0] if found else None


def strip(text: str) -> str:
    """Return text with every watermark character removed.

    Useful for asserting that a watermark changed nothing visible, and for
    handing a clean copy to a diff.
    """
    return re.sub(f"[{ZW_ZERO}{ZW_ONE}{ZW_DELIM}]", "", text)
