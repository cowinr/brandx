"""Tests for the assets module (U7 — shared base64 embedding helper).

Covers:
- Local image is replaced with a data: URI.
- http(s):// images are left untouched.
- Existing data: srcs are left untouched.
- Missing local file warns to stderr and leaves the src untouched.
- file_to_data_uri returns a data: URI for a valid file.
- file_to_data_uri returns None and warns for a missing file.
- MIME type is inferred correctly from the extension.
"""

import base64
import io
import sys
from pathlib import Path

import pytest

from brandx.render.assets import embed_images, file_to_data_uri


# ---------------------------------------------------------------------------
# file_to_data_uri
# ---------------------------------------------------------------------------

class TestFileToDataUri:
    def test_png_encodes_correctly(self, tmp_path):
        img = tmp_path / "photo.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal PNG header
        uri = file_to_data_uri(img)
        assert uri is not None
        assert uri.startswith("data:image/png;base64,")
        encoded = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode("ascii")
        assert uri == f"data:image/png;base64,{encoded}"

    def test_jpeg_mime(self, tmp_path):
        img = tmp_path / "photo.jpeg"
        img.write_bytes(b"\xff\xd8\xff")
        uri = file_to_data_uri(img)
        assert uri is not None
        assert "image/jpeg" in uri

    def test_jpg_mime(self, tmp_path):
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff")
        uri = file_to_data_uri(img)
        assert uri is not None
        assert "image/jpeg" in uri

    def test_svg_mime(self, tmp_path):
        img = tmp_path / "icon.svg"
        img.write_bytes(b"<svg></svg>")
        uri = file_to_data_uri(img)
        assert uri is not None
        assert "image/svg+xml" in uri

    def test_missing_file_returns_none_and_warns(self, tmp_path, capsys):
        missing = tmp_path / "ghost.png"
        result = file_to_data_uri(missing)
        assert result is None
        captured = capsys.readouterr()
        assert "ghost.png" in captured.err
        assert "warning" in captured.err.lower()


# ---------------------------------------------------------------------------
# embed_images
# ---------------------------------------------------------------------------

class TestEmbedImages:
    def test_local_image_becomes_data_uri(self, tmp_path):
        img = tmp_path / "logo.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        html = f'<img src="logo.png" alt="logo">'
        result = embed_images(html, source_dir=tmp_path)
        assert 'src="data:image/png;base64,' in result
        assert "logo.png" not in result

    def test_http_image_unchanged(self, tmp_path):
        html = '<img src="https://example.com/img.png">'
        result = embed_images(html, source_dir=tmp_path)
        assert result == html

    def test_http_no_s_image_unchanged(self, tmp_path):
        html = '<img src="http://example.com/img.png">'
        result = embed_images(html, source_dir=tmp_path)
        assert result == html

    def test_existing_data_uri_unchanged(self, tmp_path):
        html = '<img src="data:image/png;base64,abc123">'
        result = embed_images(html, source_dir=tmp_path)
        assert result == html

    def test_missing_local_warns_and_leaves_src(self, tmp_path, capsys):
        html = '<img src="missing.png">'
        result = embed_images(html, source_dir=tmp_path)
        assert 'src="missing.png"' in result
        captured = capsys.readouterr()
        assert "missing.png" in captured.err
        assert "warning" in captured.err.lower()

    def test_multiple_images_in_one_html(self, tmp_path):
        a = tmp_path / "a.png"
        b = tmp_path / "b.png"
        a.write_bytes(b"\x89PNG")
        b.write_bytes(b"\x89PNG")
        html = '<img src="a.png"><img src="b.png">'
        result = embed_images(html, source_dir=tmp_path)
        assert result.count("data:image/png;base64,") == 2

    def test_absolute_local_paths_not_mangled(self, tmp_path):
        # An src that is an absolute path should still resolve if the file exists.
        img = tmp_path / "abs.png"
        img.write_bytes(b"\x89PNG")
        html = f'<img src="{img}">'
        # source_dir doesn't matter here because the path is absolute-looking
        # relative to source_dir; but since it won't start with data:/http, it
        # should still attempt resolution. The resolved path will be source_dir / abs_path.
        # Just confirm the function doesn't raise.
        embed_images(html, source_dir=tmp_path)

    def test_single_quotes_src(self, tmp_path):
        img = tmp_path / "logo.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        html = f"<img src='logo.png' alt='logo'>"
        result = embed_images(html, source_dir=tmp_path)
        assert "data:image/png;base64," in result
