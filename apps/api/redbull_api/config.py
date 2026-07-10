"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    api_token: str
    cookie_secret: str
    anthropic_api_key: str
    data_dir: Path
    # Vision backend for receipt/photo recognition.
    #   "codex"     — shell out to the OpenAI Codex CLI, which authenticates
    #                 with the user's Codex/ChatGPT subscription (no metered
    #                 API key). This is the default.
    #   "openai"    — call an OpenAI-compatible /v1/chat/completions endpoint.
    #                 Point OPENAI_BASE_URL at a local subscription proxy (e.g.
    #                 EvanZhouDev/openai-oauth) to use the subscription, or leave
    #                 it unset to use the real (metered) OpenAI API.
    #   "anthropic" — call the Anthropic vision API with ANTHROPIC_API_KEY.
    vision_provider: str = "codex"
    codex_bin: str = "codex"
    codex_model: str = ""  # empty → let the Codex CLI pick its default model
    openai_api_key: str = ""
    openai_base_url: str = ""  # empty → real OpenAI API; set for a local proxy
    openai_model: str = "gpt-4o-mini"

    @classmethod
    def from_env(cls) -> "Config":
        api_token = os.environ.get("API_TOKEN")
        if not api_token:
            raise RuntimeError("API_TOKEN env var is required")

        cookie_secret = os.environ.get("COOKIE_SECRET")
        if not cookie_secret:
            raise RuntimeError("COOKIE_SECRET env var is required")

        anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        # Not required at config load — only when the Anthropic provider parses.

        data_dir = Path(os.environ.get("DATA_DIR", "/data"))

        vision_provider = os.environ.get("VISION_PROVIDER", "codex").strip().lower() or "codex"
        codex_bin = os.environ.get("CODEX_BIN", "codex").strip() or "codex"
        codex_model = os.environ.get("CODEX_MODEL", "").strip()
        openai_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        openai_base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
        openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

        return cls(
            api_token=api_token,
            cookie_secret=cookie_secret,
            anthropic_api_key=anthropic_api_key,
            data_dir=data_dir,
            vision_provider=vision_provider,
            codex_bin=codex_bin,
            codex_model=codex_model,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            openai_model=openai_model,
        )
