"""Stock + batch business logic. Stays at the SQL level — no Flask deps."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

from .db import transaction


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_stock(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT type, count, updated_at FROM stock WHERE count > 0 ORDER BY type"
    ).fetchall()
    by_type = {r["type"]: r["count"] for r in rows}
    total = sum(by_type.values())
    updated_at = max((r["updated_at"] for r in rows), default=None)
    return {"total": total, "by_type": by_type, "updated_at": updated_at}


def add_batch(
    conn: sqlite3.Connection,
    *,
    source: str,
    items: Iterable[tuple[str, int]],
    note: str | None,
    receipt_id: int | None = None,
) -> int:
    """Insert a batch + its items + UPSERT stock atomically. Returns batch id."""
    items_list = list(items)
    now = _now()
    with transaction(conn):
        cur = conn.execute(
            "INSERT INTO batches (source, created_at, note, receipt_id) "
            "VALUES (?, ?, ?, ?)",
            (source, now, note, receipt_id),
        )
        batch_id = cur.lastrowid
        for type_, delta in items_list:
            if delta == 0:
                continue
            conn.execute(
                "INSERT INTO batch_items (batch_id, type, delta) VALUES (?, ?, ?)",
                (batch_id, type_, delta),
            )
            # Update existing row if present; otherwise insert. We can't use a
            # plain UPSERT here because SQLite evaluates the CHECK constraint
            # on the INSERT VALUES clause before applying ON CONFLICT, which
            # would reject any negative delta even when an existing row could
            # absorb it. CHECK still fires correctly on the UPDATE path (so
            # stock can't go negative) and on a fresh INSERT with delta < 0.
            cur = conn.execute(
                "UPDATE stock SET count = count + ?, updated_at = ? WHERE type = ?",
                (delta, now, type_),
            )
            if cur.rowcount == 0:
                conn.execute(
                    "INSERT INTO stock (type, count, updated_at) VALUES (?, ?, ?)",
                    (type_, delta, now),
                )
    return batch_id


def delete_batch(conn: sqlite3.Connection, batch_id: int) -> bool:
    """Reverse a batch's effect on stock and delete it. Returns False if not found."""
    items = conn.execute(
        "SELECT type, delta FROM batch_items WHERE batch_id = ?",
        (batch_id,),
    ).fetchall()
    if not items and not conn.execute(
        "SELECT 1 FROM batches WHERE id = ?", (batch_id,)
    ).fetchone():
        return False

    now = _now()
    with transaction(conn):
        for r in items:
            conn.execute(
                "UPDATE stock SET count = count - ?, updated_at = ? WHERE type = ?",
                (r["delta"], now, r["type"]),
            )
        # ON DELETE CASCADE on batch_items handles the items
        conn.execute("DELETE FROM batches WHERE id = ?", (batch_id,))
    return True


def list_batches(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT b.id, b.source, b.created_at, b.note, b.receipt_id,
               r.filename AS receipt_filename, r.thumbnail AS receipt_thumbnail,
               r.confidence AS receipt_confidence
        FROM batches b
        LEFT JOIN receipts r ON r.id = b.receipt_id
        ORDER BY b.created_at DESC, b.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    result = []
    for r in rows:
        items = conn.execute(
            "SELECT type, delta FROM batch_items WHERE batch_id = ? ORDER BY id",
            (r["id"],),
        ).fetchall()
        entry = {
            "id": r["id"],
            "source": r["source"],
            "created_at": r["created_at"],
            "note": r["note"],
            "items": [{"type": i["type"], "delta": i["delta"]} for i in items],
            "receipt": None,
        }
        if r["receipt_id"] is not None:
            entry["receipt"] = {
                "id": r["receipt_id"],
                "filename": r["receipt_filename"],
                "thumbnail": r["receipt_thumbnail"],
                "confidence": r["receipt_confidence"],
            }
        result.append(entry)
    return result
