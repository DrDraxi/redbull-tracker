"""Provider-agnostic vision entry point.

Dispatches receipt/photo recognition to the configured backend:
  - "codex"     → OpenAI Codex CLI (uses the user's Codex/ChatGPT subscription)
  - "anthropic" → Anthropic vision API (metered, needs ANTHROPIC_API_KEY)
"""

from __future__ import annotations

from .codex_vision import parse_via_codex
from .config import Config
from .openai_vision import parse_via_openai
from .receipts import ParseResult, parse_photo, parse_receipt

VALID_MODES = {"receipt", "photo"}


def recognize(
    cfg: Config,
    *,
    image_bytes: bytes,
    media_type: str,
    mode: str,
) -> ParseResult:
    """Recognize Red Bull items in an image using the configured provider.

    ``mode`` is ``"receipt"`` (parse a receipt) or ``"photo"`` (count cans in a
    photo). Raises ``codex_vision.CodexError`` if the Codex provider fails and
    ``anthropic.APIError`` if the Anthropic provider fails.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"unknown vision mode: {mode!r}")

    provider = (cfg.vision_provider or "codex").lower()

    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
        if mode == "receipt":
            return parse_receipt(client, image_bytes=image_bytes, media_type=media_type)
        return parse_photo(client, image_bytes=image_bytes, media_type=media_type)

    if provider == "openai":
        return parse_via_openai(
            image_bytes=image_bytes,
            media_type=media_type,
            mode=mode,
            api_key=cfg.openai_api_key,
            base_url=cfg.openai_base_url,
            model=cfg.openai_model,
        )

    # Default: Codex subscription via the CLI.
    return parse_via_codex(
        image_bytes=image_bytes,
        media_type=media_type,
        mode=mode,
        codex_bin=cfg.codex_bin,
        model=cfg.codex_model,
    )
