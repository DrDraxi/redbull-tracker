"""Provider-agnostic vision entry point.

Dispatches receipt/photo recognition to the configured backend:
  - "codex"     → OpenAI Codex CLI (uses the user's Codex/ChatGPT subscription)
  - "openai"    → OpenAI-compatible /v1/chat/completions (e.g. a private Codex
                  subscription proxy); see ``openai_vision.py``
  - "anthropic" → Anthropic vision API (metered, needs ANTHROPIC_API_KEY)

Fallback: when the configured provider is *not* ``anthropic`` and it fails, and
an ``ANTHROPIC_API_KEY`` is configured, recognition retries once via Anthropic
so a hiccup in the subscription proxy/CLI doesn't hard-fail can detection.
"""

from __future__ import annotations

import logging

from .codex_vision import CodexError, parse_via_codex
from .config import Config
from .openai_vision import OpenAIVisionError, parse_via_openai
from .receipts import ParseResult, parse_photo, parse_receipt, parse_scan

log = logging.getLogger(__name__)

# "scan" is the unified single-pass mode: the model self-classifies the image as
# a receipt or a can photo and extracts accordingly (result.kind says which).
VALID_MODES = {"receipt", "photo", "scan"}

# Failures from the subscription-backed providers that are safe to retry on a
# different backend (network/CLI/parse errors), as opposed to programmer errors.
_FALLBACKABLE = (CodexError, OpenAIVisionError)


def recognize(
    cfg: Config,
    *,
    image_bytes: bytes,
    media_type: str,
    mode: str,
) -> ParseResult:
    """Recognize Red Bull items in an image using the configured provider.

    ``mode`` is ``"receipt"`` (parse a receipt) or ``"photo"`` (count cans in a
    photo). Uses ``cfg.vision_provider`` as the primary backend; on a provider
    failure it falls back to Anthropic when one is configured (unless Anthropic
    was already the primary). Raises the underlying provider error if no usable
    fallback succeeds.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"unknown vision mode: {mode!r}")

    provider = (cfg.vision_provider or "codex").lower()

    try:
        return _dispatch(provider, cfg, image_bytes=image_bytes, media_type=media_type, mode=mode)
    except _FALLBACKABLE as e:
        if provider != "anthropic" and cfg.anthropic_api_key:
            log.warning(
                "vision provider %r failed (%s); falling back to anthropic", provider, e
            )
            return _dispatch(
                "anthropic", cfg, image_bytes=image_bytes, media_type=media_type, mode=mode
            )
        raise


def _dispatch(
    provider: str,
    cfg: Config,
    *,
    image_bytes: bytes,
    media_type: str,
    mode: str,
) -> ParseResult:
    """Run a single provider with no fallback."""
    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
        if mode == "receipt":
            return parse_receipt(client, image_bytes=image_bytes, media_type=media_type)
        if mode == "scan":
            return parse_scan(client, image_bytes=image_bytes, media_type=media_type)
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
