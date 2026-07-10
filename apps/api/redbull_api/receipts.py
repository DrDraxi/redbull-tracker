"""Receipt parsing via Anthropic vision."""

from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass
from typing import Any

import anthropic
from PIL import Image

# Anthropic caps each image at 5 MB of base64 (~3.75 MB raw). Stay under
# with headroom so a marginal photo doesn't trip the limit.
_MAX_RAW_BYTES = 3_500_000

MODEL_PRIMARY = "claude-haiku-4-5"
MODEL_FALLBACK = "claude-sonnet-4-6"

# Shared Red Bull variant taxonomy — used by both the receipt and photo prompts.
TYPE_TAXONOMY = """Type identification:
- "default" — regular Red Bull (red/silver/blue can, red bull logo)
- "sugarfree" — sugar-free / zero variants
- "tropical", "watermelon", "peach", "coconut", "summer" — Edition / Summer Edition flavors
- For any other flavor variant, use a short lowercase English keyword"""

SYSTEM_PROMPT = f"""You are a receipt parser specialized in identifying Red Bull energy drink purchases.

Given an image of a receipt, identify every line item that is a Red Bull product
and call the record_redbulls tool with the results.

{TYPE_TAXONOMY}

Receipt line hints:
- "RED BULL", "RED BULL ENERGY" → default
- "RED BULL SUG.FRE", "SUGARFREE", "ZERO" → sugarfree

Multi-pack handling: a line like "2 *  43.90  RED BULL" means count=2, not count=1.

Confidence:
- "high" — receipt is clearly legible and you are confident in types and counts
- "low" — text is partially obscured / OCR-ambiguous but you made a best guess
- "none" — no Red Bull on this receipt, or image unreadable
"""

PHOTO_SYSTEM_PROMPT = f"""You are a vision assistant that counts Red Bull energy drink cans in ordinary photographs.

Given a photo (for example cans sitting on a desk, a table, or in a fridge), count
every Red Bull can you can clearly see and call the record_redbulls tool with the
per-type totals. Only count cans you are confident are Red Bull; ignore other drinks.

{TYPE_TAXONOMY}

Counting rules:
- Group identical cans: 3 regular cans → one item with type "default", count 3.
- Count each visible can once. Do not guess at cans fully hidden behind others.

Confidence:
- "high" — cans are clearly visible and you are confident in types and counts
- "low" — some cans are blurry / partially hidden but you made a best guess
- "none" — no Red Bull cans visible, or image unreadable
"""

def json_mode_prompt(prompt: str) -> str:
    """Adapt a tool-oriented system prompt for a JSON-output provider.

    ``SYSTEM_PROMPT`` / ``PHOTO_SYSTEM_PROMPT`` tell the model to "call the
    record_redbulls tool" — correct for the Anthropic tool-use path, but noise
    for the ``codex``/``openai`` providers, which instead ask for a raw JSON
    object. Strip the tool instruction so those providers get one coherent
    directive. A no-op if the phrase isn't present.
    """
    return re.sub(
        r"\s*and call the record_redbulls tool with[^.]*",
        " and report them",
        prompt,
    )


RECORD_TOOL = {
    "name": "record_redbulls",
    "description": "Record Red Bull cans purchased on this receipt.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": (
                                "Red Bull variant: 'default' for regular, "
                                "'sugarfree' for sugar-free/zero, or another "
                                "lowercase keyword if clearly identifiable. "
                                "Default to 'default' if ambiguous."
                            ),
                        },
                        "count": {"type": "integer", "minimum": 1},
                    },
                    "required": ["type", "count"],
                },
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "low", "none"],
            },
        },
        "required": ["items", "confidence"],
    },
}


@dataclass(frozen=True)
class ParseResult:
    items: list[dict[str, Any]]
    confidence: str
    model_used: str
    raw_response: dict[str, Any]


def _call_claude(
    client: anthropic.Anthropic,
    *,
    model: str,
    image_b64: str,
    media_type: str,
    system_prompt: str = SYSTEM_PROMPT,
    user_text: str = "Parse this receipt.",
) -> dict[str, Any]:
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[RECORD_TOOL],
        # Forced tool use rules out adaptive thinking — Anthropic API rejects
        # the combination. The strict tool schema already guarantees structured
        # output, so thinking isn't needed here.
        tool_choice={"type": "tool", "name": "record_redbulls"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": user_text},
                ],
            }
        ],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    return {"items": [], "confidence": "none"}


def shrink_image(
    image_bytes: bytes,
    media_type: str,
    *,
    max_bytes: int = _MAX_RAW_BYTES,
    max_dim: int = 2000,
) -> tuple[bytes, str]:
    """Downscale/recompress an image if it exceeds ``max_bytes``.

    Real phone photos are 4–5 MB, which is wasteful for can/receipt recognition
    and can exceed vision-API/proxy payload limits. Bounding both dimension and
    byte size keeps every provider (Anthropic, and the JSON providers that send
    the image inline as a data URI) within limits. No-op for small images.
    """
    if len(image_bytes) <= max_bytes:
        return image_bytes, media_type

    with Image.open(io.BytesIO(image_bytes)) as img:
        rgb = img.convert("RGB")
        rgb.thumbnail((max_dim, max_dim))
        for quality in (85, 75, 65, 55):
            buf = io.BytesIO()
            rgb.save(buf, "JPEG", quality=quality, optimize=True)
            if buf.tell() <= max_bytes:
                return buf.getvalue(), "image/jpeg"
        return buf.getvalue(), "image/jpeg"


def _shrink_for_claude(image_bytes: bytes, media_type: str) -> tuple[bytes, str]:
    return shrink_image(image_bytes, media_type)


def _parse(
    client: anthropic.Anthropic,
    *,
    image_bytes: bytes,
    media_type: str,
    system_prompt: str,
    user_text: str,
) -> ParseResult:
    image_bytes, media_type = _shrink_for_claude(image_bytes, media_type)
    image_b64 = base64.standard_b64encode(image_bytes).decode("ascii")

    # Primary call
    raw = _call_claude(
        client,
        model=MODEL_PRIMARY,
        image_b64=image_b64,
        media_type=media_type,
        system_prompt=system_prompt,
        user_text=user_text,
    )
    items = raw.get("items", []) or []
    confidence = raw.get("confidence", "none")

    if confidence == "low":
        # Retry with Sonnet
        raw = _call_claude(
            client,
            model=MODEL_FALLBACK,
            image_b64=image_b64,
            media_type=media_type,
            system_prompt=system_prompt,
            user_text=user_text,
        )
        items = raw.get("items", []) or []
        confidence = raw.get("confidence", "none")
        return ParseResult(
            items=items, confidence=confidence, model_used=MODEL_FALLBACK, raw_response=raw
        )

    return ParseResult(
        items=items, confidence=confidence, model_used=MODEL_PRIMARY, raw_response=raw
    )


def parse_receipt(
    client: anthropic.Anthropic,
    *,
    image_bytes: bytes,
    media_type: str,
) -> ParseResult:
    return _parse(
        client,
        image_bytes=image_bytes,
        media_type=media_type,
        system_prompt=SYSTEM_PROMPT,
        user_text="Parse this receipt.",
    )


def parse_photo(
    client: anthropic.Anthropic,
    *,
    image_bytes: bytes,
    media_type: str,
) -> ParseResult:
    """Count Red Bull cans in an ordinary photo (not a receipt)."""
    return _parse(
        client,
        image_bytes=image_bytes,
        media_type=media_type,
        system_prompt=PHOTO_SYSTEM_PROMPT,
        user_text="Count the Red Bull cans in this photo.",
    )
