import io
from unittest.mock import MagicMock

from PIL import Image

from redbull_api.receipts import (
    ParseResult,
    _MAX_RAW_BYTES,
    _shrink_for_claude,
    parse_receipt,
)


class _FakeToolUseBlock:
    def __init__(self, input_dict):
        self.type = "tool_use"
        self.input = input_dict


class _FakeResponse:
    def __init__(self, items, confidence):
        self.content = [_FakeToolUseBlock({"items": items, "confidence": confidence})]


def _client_returning(*responses):
    """Build a fake Anthropic client whose .messages.create returns the given responses in order."""
    client = MagicMock()
    client.messages.create.side_effect = list(responses)
    return client


def test_high_confidence_returns_items():
    client = _client_returning(
        _FakeResponse([{"type": "sugarfree", "count": 2}], "high")
    )
    result = parse_receipt(client, image_bytes=b"\xff\xd8", media_type="image/jpeg")
    assert isinstance(result, ParseResult)
    assert result.items == [{"type": "sugarfree", "count": 2}]
    assert result.confidence == "high"
    assert result.model_used == "claude-haiku-4-5"
    assert client.messages.create.call_count == 1


def test_low_confidence_retries_with_sonnet():
    client = _client_returning(
        _FakeResponse([{"type": "default", "count": 1}], "low"),
        _FakeResponse([{"type": "default", "count": 1}], "high"),
    )
    result = parse_receipt(client, image_bytes=b"\xff\xd8", media_type="image/jpeg")
    assert result.model_used == "claude-sonnet-4-6"
    assert result.confidence == "high"
    assert client.messages.create.call_count == 2

    # Verify the second call used the larger model
    second_call_kwargs = client.messages.create.call_args_list[1].kwargs
    assert second_call_kwargs["model"] == "claude-sonnet-4-6"


def test_none_confidence_returns_empty_items_no_retry():
    client = _client_returning(_FakeResponse([], "none"))
    result = parse_receipt(client, image_bytes=b"\xff\xd8", media_type="image/jpeg")
    assert result.items == []
    assert result.confidence == "none"
    assert client.messages.create.call_count == 1


def test_shrink_passthrough_when_small():
    small = b"\xff\xd8" + b"\x00" * 1024
    out_bytes, out_media = _shrink_for_claude(small, "image/jpeg")
    assert out_bytes is small
    assert out_media == "image/jpeg"


def test_shrink_downscales_oversized_image():
    # 6000x4000 noise compresses poorly enough to exceed the limit as JPEG.
    img = Image.effect_noise((6000, 4000), 64).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95)
    huge = buf.getvalue()
    assert len(huge) > _MAX_RAW_BYTES

    out_bytes, out_media = _shrink_for_claude(huge, "image/jpeg")
    assert len(out_bytes) <= _MAX_RAW_BYTES
    assert out_media == "image/jpeg"
    # Result is still a valid JPEG
    Image.open(io.BytesIO(out_bytes)).verify()


def test_low_then_low_keeps_sonnet_result():
    client = _client_returning(
        _FakeResponse([{"type": "default", "count": 1}], "low"),
        _FakeResponse([{"type": "default", "count": 1}], "low"),
    )
    result = parse_receipt(client, image_bytes=b"\xff\xd8", media_type="image/jpeg")
    assert result.confidence == "low"
    assert result.model_used == "claude-sonnet-4-6"
