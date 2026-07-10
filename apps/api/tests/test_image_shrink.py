"""Tests for shrink_image, shared by all vision providers."""

import io

from PIL import Image

from redbull_api.receipts import shrink_image


def _jpeg(size, color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_small_image_passes_through_unchanged():
    data = _jpeg((400, 300))
    out, media = shrink_image(data, "image/png", max_bytes=5_000_000)
    assert out is data
    assert media == "image/png"  # untouched


def test_large_image_is_shrunk_under_limit_and_bounded():
    # Noise fills JPEG poorly → a genuinely large payload.
    import os

    big = Image.frombytes("RGB", (4000, 3000), os.urandom(4000 * 3000 * 3))
    buf = io.BytesIO()
    big.save(buf, format="JPEG", quality=95)
    data = buf.getvalue()
    assert len(data) > 500_000

    out, media = shrink_image(data, "image/jpeg", max_bytes=500_000, max_dim=1500)
    assert media == "image/jpeg"
    assert len(out) <= 500_000
    with Image.open(io.BytesIO(out)) as im:
        assert max(im.size) <= 1500
