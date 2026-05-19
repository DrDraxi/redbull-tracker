"""Tesco price cache. Best-effort refresh via Claude's web_fetch server tool."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import anthropic

MODEL = "claude-haiku-4-5"

RECORD_PRICES_TOOL = {
    "name": "record_prices",
    "description": "Record the prices you found on each Tesco product page.",
    "input_schema": {
        "type": "object",
        "properties": {
            "prices": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Matches the type slug you were asked about, e.g. 'default' or 'sugarfree'.",
                        },
                        "price_normal_kc": {
                            "type": "number",
                            "description": "Regular price in Czech koruna (Kč). Decimal allowed.",
                        },
                        "price_clubcard_kc": {
                            "type": ["number", "null"],
                            "description": "Clubcard discounted price in Kč, or null if no Clubcard discount visible.",
                        },
                        "notes": {
                            "type": "string",
                            "description": "Optional one-line note, e.g. 'Clubcard offer until 2026-05-25'.",
                        },
                    },
                    "required": ["type", "price_normal_kc"],
                },
            }
        },
        "required": ["prices"],
    },
}


@dataclass(frozen=True)
class FetchedPrice:
    type: str
    price_normal_kc: float
    price_clubcard_kc: float | None
    notes: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_cents(kc: float | None) -> int | None:
    if kc is None:
        return None
    return int(round(float(kc) * 100))


def list_prices(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT type, label, url, price_normal_cents, price_clubcard_cents, currency, updated_at "
        "FROM prices ORDER BY type"
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({
            "type": r["type"],
            "label": r["label"],
            "url": r["url"],
            "price_normal": r["price_normal_cents"] / 100 if r["price_normal_cents"] is not None else None,
            "price_clubcard": r["price_clubcard_cents"] / 100 if r["price_clubcard_cents"] is not None else None,
            "currency": r["currency"],
            "updated_at": r["updated_at"],
        })
    return out


def save_prices(conn: sqlite3.Connection, fetched: list[FetchedPrice]) -> None:
    now = _now()
    for p in fetched:
        conn.execute(
            "UPDATE prices SET price_normal_cents = ?, price_clubcard_cents = ?, updated_at = ? "
            "WHERE type = ?",
            (_to_cents(p.price_normal_kc), _to_cents(p.price_clubcard_kc), now, p.type),
        )


def refresh_from_tesco(
    client: anthropic.Anthropic, conn: sqlite3.Connection
) -> list[FetchedPrice]:
    """Ask Claude to fetch each Tesco URL and report prices. Stores results."""
    targets = conn.execute("SELECT type, label, url FROM prices ORDER BY type").fetchall()
    if not targets:
        return []

    target_lines = "\n".join(
        f"- type={r['type']!r}: {r['url']}  ({r['label']})" for r in targets
    )
    instruction = (
        "Fetch each Tesco product page below using the web_fetch tool, "
        "find the current price in Czech koruna (Kč) and the Clubcard price "
        "if any. Then call the record_prices tool ONCE with all results.\n\n"
        f"{target_lines}\n\n"
        "If a Clubcard price isn't shown, pass null for price_clubcard_kc. "
        "Keep the 'type' value exactly as given above."
    )

    resp = client.beta.messages.create(
        betas=["web-fetch-2025-09-10"],
        model=MODEL,
        max_tokens=2048,
        tools=[
            {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 5},
            RECORD_PRICES_TOOL,
        ],
        messages=[{"role": "user", "content": instruction}],
    )

    # Extract the record_prices tool call from the assistant's final turn
    fetched: list[FetchedPrice] = []
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "record_prices":
            for item in block.input.get("prices", []) or []:
                fetched.append(FetchedPrice(
                    type=item["type"],
                    price_normal_kc=float(item["price_normal_kc"]),
                    price_clubcard_kc=(
                        float(item["price_clubcard_kc"])
                        if item.get("price_clubcard_kc") is not None else None
                    ),
                    notes=item.get("notes"),
                ))
            break

    if fetched:
        save_prices(conn, fetched)
    return fetched
