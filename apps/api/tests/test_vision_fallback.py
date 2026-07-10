"""Tests for the provider-agnostic vision dispatcher's Anthropic fallback."""

from unittest.mock import patch

import pytest

from redbull_api.codex_vision import CodexError
from redbull_api.config import Config
from redbull_api.openai_vision import OpenAIVisionError
from redbull_api.receipts import ParseResult
from redbull_api.vision import recognize


def _cfg(monkeypatch, provider, *, anthropic_key="sk-ant-test"):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("VISION_PROVIDER", provider)
    monkeypatch.setenv("ANTHROPIC_API_KEY", anthropic_key)
    return Config.from_env()


def _anthropic_result():
    return ParseResult(
        items=[{"type": "default", "count": 2}],
        confidence="high",
        model_used="claude-haiku-4-5",
        raw_response={},
    )


@pytest.mark.parametrize(
    "provider, primary_target, primary_error",
    [
        ("openai", "redbull_api.vision.parse_via_openai", OpenAIVisionError("proxy down")),
        ("codex", "redbull_api.vision.parse_via_codex", CodexError("codex login required")),
    ],
)
def test_falls_back_to_anthropic_when_primary_fails(
    monkeypatch, provider, primary_target, primary_error
):
    cfg = _cfg(monkeypatch, provider)
    with patch(primary_target, side_effect=primary_error), patch(
        "redbull_api.vision.parse_photo", return_value=_anthropic_result()
    ) as anthropic_photo, patch("anthropic.Anthropic"):
        result = recognize(cfg, image_bytes=b"img", media_type="image/jpeg", mode="photo")

    assert result.model_used == "claude-haiku-4-5"
    assert anthropic_photo.called


def test_no_fallback_when_anthropic_key_missing(monkeypatch):
    cfg = _cfg(monkeypatch, "openai", anthropic_key="")
    with patch(
        "redbull_api.vision.parse_via_openai", side_effect=OpenAIVisionError("proxy down")
    ):
        with pytest.raises(OpenAIVisionError):
            recognize(cfg, image_bytes=b"img", media_type="image/jpeg", mode="photo")


def test_success_path_does_not_touch_anthropic(monkeypatch):
    cfg = _cfg(monkeypatch, "openai")
    ok = ParseResult(
        items=[{"type": "default", "count": 1}],
        confidence="high",
        model_used="openai:gpt-5.6-terra",
        raw_response={},
    )
    with patch("redbull_api.vision.parse_via_openai", return_value=ok) as primary, patch(
        "redbull_api.vision.parse_photo"
    ) as anthropic_photo:
        result = recognize(cfg, image_bytes=b"img", media_type="image/jpeg", mode="photo")

    assert result.model_used == "openai:gpt-5.6-terra"
    assert primary.called
    assert not anthropic_photo.called
