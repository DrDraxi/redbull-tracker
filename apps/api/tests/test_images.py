import io
from pathlib import Path

import pytest
from PIL import Image

from redbull_api.images import save_image_and_thumbnail


def _make_image_bytes(size=(800, 600), fmt="JPEG") -> bytes:
    img = Image.new("RGB", size, color=(200, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_save_jpeg_creates_files(tmp_path: Path):
    data = _make_image_bytes()
    result = save_image_and_thumbnail(data, content_type="image/jpeg", data_dir=tmp_path)
    full = tmp_path / "receipts" / result.filename
    thumb = tmp_path / "receipts" / "thumbs" / result.thumbnail
    assert full.exists()
    assert thumb.exists()


def test_thumbnail_is_smaller(tmp_path: Path):
    data = _make_image_bytes(size=(2000, 1500))
    result = save_image_and_thumbnail(data, content_type="image/jpeg", data_dir=tmp_path)
    thumb = tmp_path / "receipts" / "thumbs" / result.thumbnail
    with Image.open(thumb) as t:
        assert max(t.size) <= 200


def test_rejects_non_image(tmp_path: Path):
    with pytest.raises(ValueError, match="not an image"):
        save_image_and_thumbnail(b"not an image", content_type="image/jpeg", data_dir=tmp_path)


def test_filename_is_uuid_based(tmp_path: Path):
    data = _make_image_bytes()
    result = save_image_and_thumbnail(data, content_type="image/jpeg", data_dir=tmp_path)
    # filename should look like '<uuid>.jpg', not the original
    assert result.filename.endswith(".jpg")
    assert len(result.filename) > 10
