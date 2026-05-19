import sqlite3
from pathlib import Path

import pytest

from redbull_api.db import connect, init_db
from redbull_api.stock import (
    add_batch,
    delete_batch,
    get_stock,
    list_batches,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return connect(db_path)


def test_get_stock_empty(conn):
    s = get_stock(conn)
    assert s == {"total": 0, "by_type": {}, "updated_at": None}


def test_add_manual_batch_updates_stock(conn):
    bid = add_batch(conn, source="manual", items=[("default", 2)], note=None)
    assert bid > 0
    s = get_stock(conn)
    assert s["total"] == 2
    assert s["by_type"] == {"default": 2}


def test_add_batch_multiple_types(conn):
    add_batch(conn, source="manual", items=[("default", 3), ("sugarfree", 2)], note=None)
    s = get_stock(conn)
    assert s["total"] == 5
    assert s["by_type"] == {"default": 3, "sugarfree": 2}


def test_negative_delta_decrements(conn):
    add_batch(conn, source="manual", items=[("default", 3)], note=None)
    add_batch(conn, source="manual", items=[("default", -1)], note=None)
    s = get_stock(conn)
    assert s["by_type"] == {"default": 2}


def test_stock_cannot_go_negative(conn):
    with pytest.raises(sqlite3.IntegrityError):
        add_batch(conn, source="manual", items=[("default", -1)], note=None)


def test_delete_batch_reverses_stock(conn):
    bid = add_batch(conn, source="manual", items=[("default", 2), ("sugarfree", 1)], note=None)
    delete_batch(conn, bid)
    s = get_stock(conn)
    assert s["total"] == 0
    assert s["by_type"] == {}


def test_delete_nonexistent_batch_returns_false(conn):
    assert delete_batch(conn, 9999) is False


def test_list_batches_returns_newest_first(conn):
    b1 = add_batch(conn, source="manual", items=[("default", 1)], note="first")
    b2 = add_batch(conn, source="manual", items=[("sugarfree", 1)], note="second")
    batches = list_batches(conn, limit=10)
    assert [b["id"] for b in batches] == [b2, b1]
    assert batches[0]["items"] == [{"type": "sugarfree", "delta": 1}]
    assert batches[0]["note"] == "second"


def test_list_batches_includes_receipt_when_present(conn):
    conn.execute(
        "INSERT INTO receipts (filename, thumbnail, uploaded_at, model_used, raw_response, confidence) "
        "VALUES ('r.jpg', 't.jpg', '2026-01-01', 'claude-haiku-4-5', '{}', 'high')"
    )
    receipt_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    add_batch(conn, source="receipt", items=[("default", 2)], note=None, receipt_id=receipt_id)
    batches = list_batches(conn, limit=10)
    assert batches[0]["receipt"] is not None
    assert batches[0]["receipt"]["id"] == receipt_id


def test_empty_batch_creates_row_with_zero_items(conn):
    """For confidence=none receipts that still need to appear in the log."""
    conn.execute(
        "INSERT INTO receipts (filename, thumbnail, uploaded_at, model_used, raw_response, confidence) "
        "VALUES ('r.jpg', 't.jpg', '2026-01-01', 'claude-haiku-4-5', '{}', 'none')"
    )
    receipt_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    bid = add_batch(conn, source="receipt", items=[], note=None, receipt_id=receipt_id)
    batches = list_batches(conn, limit=10)
    assert batches[0]["id"] == bid
    assert batches[0]["items"] == []
