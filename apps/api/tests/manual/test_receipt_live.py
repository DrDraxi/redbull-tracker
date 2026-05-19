"""Opt-in live test that hits the real Anthropic API.

Run: `cd apps/api && uv run pytest tests/manual/ -v`

Requires:
- ANTHROPIC_API_KEY env var
- A receipt image at tests/fixtures/receipts/sample.jpg
"""

from __future__ import annotations

import os
from pathlib import Path

import anthropic
import pytest

from redbull_api.receipts import parse_receipt

FIXTURE = Path(__file__).parent.parent / "fixtures" / "receipts" / "sample.jpg"


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
@pytest.mark.skipif(
    not FIXTURE.exists(),
    reason=f"No fixture at {FIXTURE}",
)
def test_live_parse_sample_receipt():
    client = anthropic.Anthropic()
    result = parse_receipt(
        client, image_bytes=FIXTURE.read_bytes(), media_type="image/jpeg"
    )
    print(f"\nModel: {result.model_used}")
    print(f"Confidence: {result.confidence}")
    print(f"Items: {result.items}")
    assert result.confidence in {"high", "low", "none"}
