"""Tests for the zero-width watermark module.

Covers:
    - Checksum: deterministic, four lowercase hex digits, zero-padded.
    - Encode: zero-width characters only, and the framed length.
    - Round trip, including a payload that itself contains the separator.
    - Payload validation: empty, over-long, and non-ASCII are refused.
    - Decode rejects: misaligned bits, wrong checksum, non-hex checksum,
      missing separator, empty payload.
    - Redundancy: a reply trimmed to one paragraph still decodes.
    - Resilience: markup inserted mid-run, numeric character references, and
      an HTML-to-plain-text conversion all still decode.
    - Injection: paragraph target, list-item fallback, append fallback, and the
      guard refusing a bad payload before anything is injected.
"""

from __future__ import annotations

import html as _html_lib

import pytest

from brandx.watermark import (
    MAX_PAYLOAD_CHARS,
    ZW_DELIM,
    ZW_ONE,
    ZW_ZERO,
    WatermarkError,
    compute_checksum,
    encode,
    extract,
    extract_all,
    inject,
    strip,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ZW_CHARS = frozenset({ZW_ZERO, ZW_ONE, ZW_DELIM})


def _bits_of(token: str) -> str:
    """Return the bit string of a framed token, delimiters removed."""
    return "".join("1" if char == ZW_ONE else "0" for char in token.strip(ZW_DELIM))


def _token_from_bits(bits: str) -> str:
    """Frame a raw bit string as a token, bypassing encode()."""
    body = "".join(ZW_ONE if bit == "1" else ZW_ZERO for bit in bits)
    return f"{ZW_DELIM}{body}{ZW_DELIM}"


def _token_for_packet(packet: str) -> str:
    """Frame an arbitrary packet string, bypassing encode()'s checksum."""
    return _token_from_bits("".join(format(ord(char), "08b") for char in packet))


# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------

class TestChecksum:
    def test_is_deterministic(self):
        assert compute_checksum("T421") == compute_checksum("T421")

    def test_is_four_lowercase_hex_digits(self):
        for payload in ["T421", "a", "TRACK-ID:94827", "x" * MAX_PAYLOAD_CHARS]:
            digest = compute_checksum(payload)
            assert len(digest) == 4
            assert all(char in "0123456789abcdef" for char in digest)

    def test_small_digest_is_zero_padded(self):
        # chr(1) hashes to 1, which must render as "0001" and not "1".
        assert compute_checksum("\x01") == "0001"

    def test_differs_for_different_payloads(self):
        assert compute_checksum("T421") != compute_checksum("T422")


# ---------------------------------------------------------------------------
# Encode
# ---------------------------------------------------------------------------

class TestEncode:
    def test_token_is_invisible(self):
        assert set(encode("T421")) <= _ZW_CHARS

    def test_token_is_framed_by_the_delimiter(self):
        token = encode("T421")
        assert token.startswith(ZW_DELIM)
        assert token.endswith(ZW_DELIM)

    def test_length_is_eight_bits_per_packet_character_plus_two_delimiters(self):
        # packet = "T421" + ":" + 4 checksum digits = 9 characters.
        assert len(encode("T421")) == 9 * 8 + 2

    def test_is_stable_across_calls(self):
        assert encode("T421") == encode("T421")


# ---------------------------------------------------------------------------
# Round trip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    @pytest.mark.parametrize(
        "payload",
        [
            "T421",
            "a",
            "TASK-2026-08-16",
            "x" * MAX_PAYLOAD_CHARS,
            "spaces are allowed",
            "!\"#$%&'()*+,-./0123456789",
            ":;<=>?@[\\]^_`{|}~",
        ],
    )
    def test_payload_survives(self, payload):
        assert extract(encode(payload)) == payload

    def test_payload_containing_the_separator_survives(self):
        # The specification's own example. Its decoder splits on the FIRST
        # separator and demands exactly two parts, so this packet (three parts)
        # was rejected as a checksum failure. Splitting on the last separator
        # is what makes it round-trip.
        payload = "TRACK-ID:94827"
        packet = f"{payload}:{compute_checksum(payload)}"
        assert len(packet.split(":")) == 3, "the regression needs a multi-colon packet"
        assert extract(encode(payload)) == payload

    def test_payload_ending_in_the_separator_survives(self):
        assert extract(encode("T421:")) == "T421:"

    def test_every_printable_ascii_character_survives(self):
        payload = "".join(chr(code) for code in range(0x20, 0x7F))
        for start in range(0, len(payload), MAX_PAYLOAD_CHARS):
            chunk = payload[start:start + MAX_PAYLOAD_CHARS]
            assert extract(encode(chunk)) == chunk


# ---------------------------------------------------------------------------
# Payload validation
# ---------------------------------------------------------------------------

class TestPayloadValidation:
    def test_empty_payload_is_refused(self):
        with pytest.raises(WatermarkError, match="must not be empty"):
            encode("")

    def test_over_long_payload_is_refused(self):
        with pytest.raises(WatermarkError, match="the limit is"):
            encode("x" * (MAX_PAYLOAD_CHARS + 1))

    def test_payload_at_the_limit_is_accepted(self):
        assert extract(encode("x" * MAX_PAYLOAD_CHARS)) == "x" * MAX_PAYLOAD_CHARS

    @pytest.mark.parametrize("payload", ["café", "T421 🐱", "T421\n", "T421\t", "T\x00"])
    def test_non_printable_ascii_is_refused(self, payload):
        with pytest.raises(WatermarkError, match="printable ASCII"):
            encode(payload)

    def test_refusal_names_the_offending_character(self):
        with pytest.raises(WatermarkError, match="é"):
            encode("café")


# ---------------------------------------------------------------------------
# Decode rejections
# ---------------------------------------------------------------------------

class TestDecodeRejects:
    def test_misaligned_bit_run_is_dropped(self):
        token = encode("T421")
        misaligned = _token_from_bits(_bits_of(token)[:-3])
        assert extract(misaligned) is None

    def test_corrupted_payload_fails_the_checksum(self):
        bits = list(_bits_of(encode("T421")))
        bits[0] = "1" if bits[0] == "0" else "0"
        assert extract(_token_from_bits("".join(bits))) is None

    def test_non_hex_checksum_is_rejected(self):
        assert extract(_token_for_packet("T421:zzzz")) is None

    def test_short_checksum_is_rejected(self):
        assert extract(_token_for_packet("T421:fec")) is None

    def test_packet_without_a_separator_is_rejected(self):
        assert extract(_token_for_packet("T421")) is None

    def test_packet_with_an_empty_payload_is_rejected(self):
        assert extract(_token_for_packet(f":{compute_checksum('')}")) is None

    def test_text_with_no_token_returns_none(self):
        assert extract("<p>Nothing hidden here.</p>") is None
        assert extract_all("") == []

    def test_a_bad_token_does_not_stop_a_later_good_one(self):
        bad = _token_for_packet("T421:zzzz")
        good = encode("T999")
        assert extract(f"<p>a{bad}</p><p>b{good}</p>") == "T999"


# ---------------------------------------------------------------------------
# extract_all
# ---------------------------------------------------------------------------

class TestExtractAll:
    def test_repeats_are_collapsed(self):
        html = inject("<p>One.</p><p>Two.</p><p>Three.</p>", "T421")
        assert extract_all(html) == ["T421"]

    def test_distinct_payloads_are_returned_in_first_seen_order(self):
        thread = f"<p>reply{encode('T999')}</p><p>quoted{encode('T421')}</p>"
        assert extract_all(thread) == ["T999", "T421"]

    def test_extract_returns_the_first_of_several(self):
        thread = f"<p>reply{encode('T999')}</p><p>quoted{encode('T421')}</p>"
        assert extract(thread) == "T999"


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------

class TestInject:
    def test_token_lands_before_every_closing_paragraph(self):
        html = "<p>One.</p>\n<p>Two.</p>\n<p>Three.</p>"
        out = inject(html, "T421")
        assert out.count(f"{ZW_DELIM}</p>") == 3

    def test_visible_text_is_unchanged(self):
        html = "<p>One.</p>\n<p>Two.</p>"
        assert strip(inject(html, "T421")) == html

    def test_list_items_are_used_when_there_are_no_paragraphs(self):
        html = "<ul><li>One</li><li>Two</li></ul>"
        out = inject(html, "T421")
        assert out.count(f"{ZW_DELIM}</li>") == 2
        assert extract(out) == "T421"

    def test_paragraphs_win_so_a_loose_list_is_not_watermarked_twice(self):
        html = "<ul><li><p>One</p></li><li><p>Two</p></li></ul>"
        out = inject(html, "T421")
        assert out.count(f"{ZW_DELIM}</p>") == 2
        assert f"{ZW_DELIM}</li>" not in out

    def test_a_body_with_neither_gets_one_appended_token(self):
        html = "<table><tr><td>One</td></tr></table>"
        out = inject(html, "T421")
        assert out.startswith(html)
        assert extract(out) == "T421"

    def test_a_bad_payload_is_refused_before_anything_is_injected(self):
        html = "<p>One.</p>"
        with pytest.raises(WatermarkError):
            inject(html, "")


# ---------------------------------------------------------------------------
# Survival
# ---------------------------------------------------------------------------

class TestSurvival:
    def test_a_reply_trimmed_to_one_paragraph_still_decodes(self):
        out = inject("<p>One.</p>\n<p>Two.</p>\n<p>Three.</p>", "T421")
        trimmed = out.splitlines()[1]
        assert extract(trimmed) == "T421"

    def test_a_run_split_by_inserted_markup_still_decodes(self):
        token = encode("T421")
        midpoint = len(token) // 2
        mangled = f"<p>Hi{token[:midpoint]}<span style=\"color:red\">{token[midpoint:]}</span></p>"
        assert extract(mangled) == "T421"

    def test_numeric_character_references_still_decode(self):
        token = encode("T421")
        escaped = "".join(f"&#{ord(char)};" for char in token)
        assert extract(f"<p>Hi{escaped}</p>") == "T421"

    def test_conversion_to_plain_text_still_decodes(self):
        out = inject("<p>One.</p>\n<p>Two.</p>", "T421")
        # Crude HTML-to-text: drop the tags, keep the text nodes.
        plain = _html_lib.unescape(out.replace("<p>", "").replace("</p>", ""))
        assert extract(plain) == "T421"

    def test_two_tokens_merged_into_one_run_do_not_yield_a_false_payload(self):
        # Drop the delimiters where two adjacent tokens meet, so their bits
        # merge into a single run. The result must fail validation rather than
        # decode to something plausible.
        first, second = encode("T421"), encode("T999")
        merged = first[:-1] + second[1:]
        assert merged.count(ZW_DELIM) == 2, "the merge must leave one framed run"
        assert extract(merged) is None

    def test_a_lost_trailing_delimiter_costs_only_that_copy(self):
        # A run whose closing delimiter is stripped is unreadable, but the
        # redundancy means the next paragraph still carries a whole token.
        out = inject("<p>One.</p><p>Two.</p>", "T421")
        damaged = out.replace(ZW_DELIM, "", 2)
        assert extract(damaged) == "T421"


# ---------------------------------------------------------------------------
# strip
# ---------------------------------------------------------------------------

class TestStrip:
    def test_removes_every_watermark_character(self):
        stripped = strip(inject("<p>One.</p><p>Two.</p>", "T421"))
        assert not (set(stripped) & _ZW_CHARS)

    def test_leaves_unwatermarked_text_alone(self):
        assert strip("<p>One.</p>") == "<p>One.</p>"
