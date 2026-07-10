"""Unit tests for the Codex CLI vision provider (subprocess mocked)."""

import json

import pytest

from redbull_api.codex_vision import (
    CodexError,
    _extract_json,
    _last_json_object,
    _sanitize_items,
    parse_via_codex,
)


def _runner_returning(text, capture=None):
    def run(argv, *, cwd, timeout):
        if capture is not None:
            capture["argv"] = argv
            capture["cwd"] = cwd
        # Emulate --output-last-message by writing the file the CLI would write.
        out_idx = argv.index("--output-last-message")
        out_path = argv[out_idx + 1]
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return ""  # stdout unused when the file is present

    return run


def test_parse_photo_happy_path():
    capture = {}
    runner = _runner_returning(
        json.dumps({"items": [{"type": "Default", "count": 3}], "confidence": "high"}),
        capture,
    )
    result = parse_via_codex(
        image_bytes=b"\xff\xd8xx",
        media_type="image/jpeg",
        mode="photo",
        runner=runner,
    )
    assert result.items == [{"type": "default", "count": 3}]
    assert result.confidence == "high"
    assert result.model_used == "codex:default"
    # Prompt is passed positionally *before* the flags (exec parser requirement).
    argv = capture["argv"]
    assert argv[:2] == ["codex", "exec"]
    assert argv.index("--image") > 2
    prompt = argv[2]
    assert "photo" in prompt.lower()


def test_prompt_uses_receipt_wording_in_receipt_mode():
    capture = {}
    runner = _runner_returning(
        json.dumps({"items": [], "confidence": "none"}), capture
    )
    parse_via_codex(
        image_bytes=b"x", media_type="image/png", mode="receipt", runner=runner
    )
    assert "receipt" in capture["argv"][2].lower()
    # png image gets a .png temp file
    img_arg = capture["argv"][capture["argv"].index("--image") + 1]
    assert img_arg.endswith(".png")


def test_model_flag_added_when_configured():
    capture = {}
    runner = _runner_returning(
        json.dumps({"items": [{"type": "default", "count": 1}], "confidence": "high"}),
        capture,
    )
    parse_via_codex(
        image_bytes=b"x",
        media_type="image/jpeg",
        mode="photo",
        model="gpt-5-codex",
        runner=runner,
    )
    argv = capture["argv"]
    assert "--model" in argv
    assert argv[argv.index("--model") + 1] == "gpt-5-codex"


def test_no_items_forces_none_confidence():
    runner = _runner_returning(
        json.dumps({"items": [], "confidence": "high"})  # contradictory on purpose
    )
    result = parse_via_codex(
        image_bytes=b"x", media_type="image/jpeg", mode="photo", runner=runner
    )
    assert result.items == []
    assert result.confidence == "none"


def test_tolerates_prose_around_json():
    runner = _runner_returning(
        'Sure! Here is what I found:\n'
        '{"items": [{"type": "sugarfree", "count": 2}], "confidence": "low"}\n'
        'Let me know if you need more.'
    )
    result = parse_via_codex(
        image_bytes=b"x", media_type="image/jpeg", mode="photo", runner=runner
    )
    assert result.items == [{"type": "sugarfree", "count": 2}]
    assert result.confidence == "low"


def test_empty_output_raises():
    runner = _runner_returning("")
    with pytest.raises(CodexError):
        parse_via_codex(
            image_bytes=b"x", media_type="image/jpeg", mode="photo", runner=runner
        )


def test_last_json_object_picks_last_valid():
    text = '{"a": 1} noise {"items": [], "confidence": "none"}'
    assert _last_json_object(text) == {"items": [], "confidence": "none"}


def test_extract_json_from_code_fence():
    text = "```json\n{\"items\": [], \"confidence\": \"none\"}\n```"
    assert _extract_json(text) == {"items": [], "confidence": "none"}


def test_sanitize_items_filters_garbage():
    raw = [
        {"type": "default", "count": 2},
        {"type": "", "count": 3},          # empty type dropped
        {"type": "zero", "count": 0},      # count < 1 dropped
        {"type": "peach", "count": "bad"}, # non-int dropped
        "not a dict",                        # dropped
        {"type": "  Tropical ", "count": 1},  # normalized
    ]
    assert _sanitize_items(raw) == [
        {"type": "default", "count": 2},
        {"type": "tropical", "count": 1},
    ]
