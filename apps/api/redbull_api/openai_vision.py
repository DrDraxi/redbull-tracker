"""Vision recognition via an OpenAI-compatible chat/completions endpoint.

This provider is deliberately generic about *where* it points, via
``OPENAI_BASE_URL``:

  - Real OpenAI API (default base URL): metered, needs a real ``OPENAI_API_KEY``.
  - A local subscription proxy such as EvanZhouDev/openai-oauth, which exposes
    ``/v1/chat/completions`` backed by your Codex/ChatGPT ``auth.json``. Point
    ``OPENAI_BASE_URL`` at e.g. ``http://127.0.0.1:10531/v1`` and use any
    placeholder key. NOTE: that proxy's author states it is for *personal,
    local* use only — do not run it as part of a hosted deployment.

Compared to the ``codex exec`` provider this gives native image input and a
JSON-mode response in a single HTTP call, at the cost of an extra moving part
(the proxy) when used with a subscription.
"""

from __future__ import annotations

import base64
from typing import Any, Callable

from .codex_vision import _extract_json, _sanitize_items
from .receipts import PHOTO_SYSTEM_PROMPT, SYSTEM_PROMPT, ParseResult, json_mode_prompt, shrink_image

_JSON_CONTRACT = (
    'Return ONLY a JSON object of the form '
    '{"items": [{"type": "<lowercase keyword>", "count": <integer >= 1>}], '
    '"confidence": "high" | "low" | "none"}. '
    'No prose, no code fences.'
)


class OpenAIVisionError(RuntimeError):
    """Raised when the OpenAI-compatible endpoint fails or returns bad output."""


def _system_prompt(mode: str) -> str:
    base = PHOTO_SYSTEM_PROMPT if mode == "photo" else SYSTEM_PROMPT
    return json_mode_prompt(base)


def parse_via_openai(
    *,
    image_bytes: bytes,
    media_type: str,
    mode: str,
    api_key: str,
    base_url: str = "",
    model: str = "gpt-4o-mini",
    caller: Callable[..., Any] | None = None,
) -> ParseResult:
    """Recognize Red Bull items using an OpenAI-compatible vision endpoint.

    ``caller`` is injectable for tests; when omitted the real ``openai`` SDK is
    used (imported lazily so the dependency is only needed for this provider).
    """
    image_bytes, media_type = shrink_image(image_bytes, media_type)
    data_uri = f"data:{media_type};base64," + base64.standard_b64encode(image_bytes).decode("ascii")
    task = (
        "Count the Red Bull cans visible in this photo."
        if mode == "photo"
        else "Parse this receipt for Red Bull purchases."
    )
    messages = [
        {"role": "system", "content": _system_prompt(mode) + "\n\n" + _JSON_CONTRACT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": task},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        },
    ]

    call = caller or _default_caller
    try:
        text = call(api_key=api_key, base_url=base_url, model=model, messages=messages)
    except Exception as e:  # network / SDK / auth errors → uniform failure
        raise OpenAIVisionError(str(e)[:300]) from e

    data = _extract_json(text)
    items = _sanitize_items(data.get("items"))
    confidence = data.get("confidence")
    if confidence not in {"high", "low", "none"}:
        confidence = "high" if items else "none"
    if not items:
        confidence = "none"

    return ParseResult(
        items=items,
        confidence=confidence,
        model_used=f"openai:{model}",
        raw_response=data,
    )


def _default_caller(*, api_key: str, base_url: str, model: str, messages: list) -> str:
    from openai import OpenAI  # lazy: only this provider needs the SDK

    client = OpenAI(api_key=api_key or "unused", base_url=base_url or None)
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        max_tokens=1024,
    )
    return resp.choices[0].message.content or ""
