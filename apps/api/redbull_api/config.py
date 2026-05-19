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

    @classmethod
    def from_env(cls) -> "Config":
        api_token = os.environ.get("API_TOKEN")
        if not api_token:
            raise RuntimeError("API_TOKEN env var is required")

        cookie_secret = os.environ.get("COOKIE_SECRET")
        if not cookie_secret:
            raise RuntimeError("COOKIE_SECRET env var is required")

        anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        # Not required at config load — only at receipt-parse time.

        data_dir = Path(os.environ.get("DATA_DIR", "/data"))

        return cls(
            api_token=api_token,
            cookie_secret=cookie_secret,
            anthropic_api_key=anthropic_api_key,
            data_dir=data_dir,
        )
