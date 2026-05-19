"""Price cache for any grocery URL. Refresh via Claude's web_fetch server tool.

User adds product rows (any store, any URL); refresh scrapes each one and saves
the current normal + loyalty-card price into the prices table.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import anthropic

MODEL = "claude-haiku-4-5"

RECORD_PRICES_TOOL = {
    "name": "record_prices",
    "description": (
        "Record the prices you scraped from each grocery product page. "
        "Call this ONCE at the end with one entry per product you were given."
    ),
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
                            "description": "Echo the type slug you were asked about, verbatim.",
                        },
                        "label": {
                            "type": "string",
                            "description": (
                                "Short product label as seen on the page, e.g. "
                                "'Red Bull Energy Drink 250ml'. Used only if the "
                                "existing label is empty/placeholder."
                            ),
                        },
                        "price_normal_kc": {
                            "type": "number",
                            "description": "Regular price in Czech koruna (Kč). Decimal allowed.",
                        },
                        "price_clubcard_kc": {
                            "type": ["number", "null"],
                            "description": (
                                "Loyalty-card discounted price in Kč (Clubcard, MultiClubcard, "
                                "Albert Naše, Kaufland Card, Lidl Plus, Můj Globus, etc.) — "
                                "null if no loyalty discount is visible."
                            ),
                        },
                        "notes": {
                            "type": "string",
                            "description": "Optional short note, e.g. 'Offer until 2026-05-25'.",
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
    label: str | None = None
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


def add_price(
    conn: sqlite3.Connection, *, type: str, url: str, label: str | None = None
) -> dict[str, Any]:
    """Create a new tracked product. Returns the inserted row as a dict."""
    if not type or not url:
        raise ValueError("type and url are required")
    conn.execute(
        "INSERT INTO prices (type, label, url) VALUES (?, ?, ?) "
        "ON CONFLICT(type) DO UPDATE SET url = excluded.url, "
        "label = CASE WHEN excluded.label != '' THEN excluded.label ELSE prices.label END",
        (type, label or "", url),
    )
    row = conn.execute(
        "SELECT type, label, url, price_normal_cents, price_clubcard_cents, currency, updated_at "
        "FROM prices WHERE type = ?",
        (type,),
    ).fetchone()
    return {
        "type": row["type"], "label": row["label"], "url": row["url"],
        "price_normal": row["price_normal_cents"] / 100 if row["price_normal_cents"] is not None else None,
        "price_clubcard": row["price_clubcard_cents"] / 100 if row["price_clubcard_cents"] is not None else None,
        "currency": row["currency"], "updated_at": row["updated_at"],
    }


def delete_price(conn: sqlite3.Connection, type: str) -> bool:
    cur = conn.execute("DELETE FROM prices WHERE type = ?", (type,))
    return cur.rowcount > 0


def save_prices(conn: sqlite3.Connection, fetched: list[FetchedPrice]) -> None:
    now = _now()
    for p in fetched:
        # Update label only when it's empty so users don't lose customized labels
        if p.label:
            conn.execute(
                "UPDATE prices SET price_normal_cents = ?, price_clubcard_cents = ?, "
                "updated_at = ?, label = CASE WHEN label = '' THEN ? ELSE label END "
                "WHERE type = ?",
                (_to_cents(p.price_normal_kc), _to_cents(p.price_clubcard_kc), now, p.label, p.type),
            )
        else:
            conn.execute(
                "UPDATE prices SET price_normal_cents = ?, price_clubcard_cents = ?, "
                "updated_at = ? WHERE type = ?",
                (_to_cents(p.price_normal_kc), _to_cents(p.price_clubcard_kc), now, p.type),
            )


def refresh_from_web(
    client: anthropic.Anthropic, conn: sqlite3.Connection
) -> list[FetchedPrice]:
    """Ask Claude to fetch each product URL and report prices. Stores results."""
    targets = conn.execute("SELECT type, label, url FROM prices ORDER BY type").fetchall()
    if not targets:
        return []

    target_lines = "\n".join(
        f"- type={r['type']!r}: {r['url']}"
        + (f"  (current label: {r['label']!r})" if r['label'] else "")
        for r in targets
    )
    instruction = (
        "Use the web_fetch tool to load each grocery product page below, find "
        "the current price in Czech koruna (Kč), and find any loyalty-card / "
        "membership-card discounted price if shown on the page (Clubcard, "
        "MultiClubcard, Albert Naše, Kaufland Card, Lidl Plus, Můj Globus, etc.). "
        "Then call the record_prices tool ONCE with all results.\n\n"
        f"{target_lines}\n\n"
        "Echo the 'type' value exactly as given. If the existing label is empty, "
        "also include a short clean label (e.g. 'Red Bull Sugarfree 250ml'). "
        "If no loyalty discount is visible, pass null for price_clubcard_kc."
    )

    resp = client.beta.messages.create(
        betas=["web-fetch-2025-09-10"],
        model=MODEL,
        max_tokens=2048,
        tools=[
            {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 10},
            RECORD_PRICES_TOOL,
        ],
        messages=[{"role": "user", "content": instruction}],
    )

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
                    label=item.get("label") or None,
                    notes=item.get("notes"),
                ))
            break

    if fetched:
        save_prices(conn, fetched)
    return fetched


# Back-compat alias for older code paths
refresh_from_tesco = refresh_from_web
