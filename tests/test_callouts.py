"""Tests for callout detection and blockquote splitting (U6).

Covers (from plan):
- Stacked [!NOTE] and [!WARNING] in one blockquote split into two callouts.
- A blockquote with no marker stays a plain blockquote.
- alert_type_for_key normalisation.
"""

from brandx.render.callouts import process_alerts, alert_type_for_key, _split_blockquote_paragraphs


class TestSplitBlockquoteParagraphs:
    def test_single_alert(self):
        inner = "<p>[!NOTE] This is a note.</p>"
        chunks = _split_blockquote_paragraphs(inner)
        assert len(chunks) == 1
        is_alert, atype, body = chunks[0]
        assert is_alert is True
        assert atype == "note"
        assert "This is a note." in body

    def test_stacked_alerts(self):
        inner = "<p>[!NOTE] First note.</p>\n<p>[!WARNING] A warning.</p>"
        chunks = _split_blockquote_paragraphs(inner)
        assert len(chunks) == 2
        assert chunks[0][0] is True
        assert chunks[0][1] == "note"
        assert chunks[1][0] is True
        assert chunks[1][1] == "warning"

    def test_plain_blockquote_no_alert(self):
        inner = "<p>Just some text.</p>"
        chunks = _split_blockquote_paragraphs(inner)
        assert len(chunks) == 1
        is_alert, _, _ = chunks[0]
        assert is_alert is False

    def test_mixed_alert_then_plain(self):
        inner = "<p>[!NOTE] A note.</p>\n<p>Plain continuation.</p>"
        chunks = _split_blockquote_paragraphs(inner)
        assert len(chunks) == 1
        is_alert, atype, body = chunks[0]
        assert is_alert is True
        assert "Plain continuation." in body

    def test_info_maps_to_note(self):
        inner = "<p>[!INFO] An info.</p>"
        chunks = _split_blockquote_paragraphs(inner)
        assert chunks[0][1] == "note"

    def test_caution_maps_to_caution(self):
        inner = "<p>[!CAUTION] Careful.</p>"
        chunks = _split_blockquote_paragraphs(inner)
        assert chunks[0][1] == "caution"

    def test_danger_maps_to_caution(self):
        inner = "<p>[!DANGER] Danger!</p>"
        chunks = _split_blockquote_paragraphs(inner)
        assert chunks[0][1] == "caution"

    def test_case_insensitive(self):
        inner = "<p>[!WARNING] Watch out.</p>"
        chunks = _split_blockquote_paragraphs(inner)
        assert chunks[0][1] == "warning"


class TestProcessAlerts:
    def test_single_alert_produces_marker(self):
        html = "<blockquote><p>[!NOTE] A note.</p></blockquote>"
        result = process_alerts(html)
        assert '<!-- bx:alert type="note" -->' in result
        assert "<blockquote>" not in result

    def test_stacked_alerts_produce_two_markers(self):
        html = (
            "<blockquote>"
            "<p>[!NOTE] First.</p>\n"
            "<p>[!WARNING] Second.</p>"
            "</blockquote>"
        )
        result = process_alerts(html)
        assert result.count("bx:alert") == 4  # 2 open + 2 close markers
        assert '<!-- bx:alert type="note" -->' in result
        assert '<!-- bx:alert type="warning" -->' in result

    def test_plain_blockquote_produces_blockquote_marker(self):
        html = "<blockquote><p>Just a quote.</p></blockquote>"
        result = process_alerts(html)
        assert "<!-- bx:blockquote -->" in result
        assert "<!-- /bx:blockquote -->" in result
        assert "bx:alert" not in result

    def test_blockquote_with_no_marker_stays_blockquote(self):
        html = "<blockquote><p>Design principle.</p></blockquote>"
        result = process_alerts(html)
        assert "bx:alert" not in result
        assert "bx:blockquote" in result

    def test_non_blockquote_html_untouched(self):
        html = "<p>Hello <strong>world</strong></p>"
        result = process_alerts(html)
        assert result == html

    def test_multiple_separate_blockquotes(self):
        html = (
            "<blockquote><p>[!NOTE] Note one.</p></blockquote>"
            "<blockquote><p>Plain quote.</p></blockquote>"
        )
        result = process_alerts(html)
        assert '<!-- bx:alert type="note" -->' in result
        assert "<!-- bx:blockquote -->" in result


class TestAlertTypeForKey:
    def test_known_types(self):
        assert alert_type_for_key("note") == "note"
        assert alert_type_for_key("info") == "note"
        assert alert_type_for_key("tip") == "tip"
        assert alert_type_for_key("important") == "important"
        assert alert_type_for_key("warning") == "warning"
        assert alert_type_for_key("error") == "warning"
        assert alert_type_for_key("caution") == "caution"
        assert alert_type_for_key("danger") == "caution"

    def test_unknown_type_returns_none(self):
        assert alert_type_for_key("nonsense") is None

    def test_case_insensitive(self):
        assert alert_type_for_key("NOTE") == "note"
        assert alert_type_for_key("Warning") == "warning"
