"""Receipt parsing via Anthropic vision."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import anthropic

MODEL_PRIMARY = "claude-haiku-4-5"
MODEL_FALLBACK = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a receipt parser specialized in identifying Red Bull energy drink purchases.

Given an image of a receipt, identify every line item that is a Red Bull product
and call the record_redbulls tool with the results.

Type identification:
- "default" — regular Red Bull (red can). Receipt lines: "RED BULL", "RED BULL ENERGY"
- "sugarfree" — sugar-free / zero variants. Receipt lines: "RED BULL SUG.FRE", "SUGARFREE", "ZERO"
- "tropical", "watermelon", "peach", "coconut", "summer" — Edition / Summer Edition flavors
- For any other flavor variant, use a short lowercase English keyword

Multi-pack handling: a line like "2 *  43.90  RED BULL" means count=2, not count=1.

Confidence:
- "high" — receipt is clearly legible and you are confident in types and counts
- "low" — text is partially obscured / OCR-ambiguous but you made a best guess
- "none" — no Red Bull on this receipt, or image unreadable
"""

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
) -> dict[str, Any]:
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
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
                    {"type": "text", "text": "Parse this receipt."},
                ],
            }
        ],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    return {"items": [], "confidence": "none"}


def parse_receipt(
    client: anthropic.Anthropic,
    *,
    image_bytes: bytes,
    media_type: str,
) -> ParseResult:
    image_b64 = base64.standard_b64encode(image_bytes).decode("ascii")

    # Primary call
    raw = _call_claude(client, model=MODEL_PRIMARY, image_b64=image_b64, media_type=media_type)
    items = raw.get("items", []) or []
    confidence = raw.get("confidence", "none")

    if confidence == "low":
        # Retry with Sonnet
        raw = _call_claude(client, model=MODEL_FALLBACK, image_b64=image_b64, media_type=media_type)
        items = raw.get("items", []) or []
        confidence = raw.get("confidence", "none")
        return ParseResult(
            items=items, confidence=confidence, model_used=MODEL_FALLBACK, raw_response=raw
        )

    return ParseResult(
        items=items, confidence=confidence, model_used=MODEL_PRIMARY, raw_response=raw
    )
