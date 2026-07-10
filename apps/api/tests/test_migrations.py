"""Migration tests: widening batches.source to allow 'photo'."""

import sqlite3
import threading
from pathlib import Path

from redbull_api.db import _allow_photo_batch_source, connect, init_db

# The pre-'photo' batches table, as older databases have it on disk.
_OLD_SCHEMA = """
CREATE TABLE receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL, thumbnail TEXT, uploaded_at TEXT NOT NULL,
    model_used TEXT NOT NULL, raw_response TEXT NOT NULL, confidence TEXT NOT NULL
);
CREATE TABLE batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL CHECK (source IN ('receipt', 'manual')),
    created_at TEXT NOT NULL, note TEXT,
    receipt_id INTEGER REFERENCES receipts(id) ON DELETE SET NULL
);
CREATE TABLE batch_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    type TEXT NOT NULL, delta INTEGER NOT NULL
);
"""


def _make_old_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(_OLD_SCHEMA)
    # A pre-existing manual batch + item to prove data + FK references survive.
    conn.execute(
        "INSERT INTO batches (id, source, created_at, note) VALUES (7, 'manual', 't', NULL)"
    )
    conn.execute(
        "INSERT INTO batch_items (batch_id, type, delta) VALUES (7, 'default', 5)"
    )
    conn.commit()
    conn.close()


def test_old_db_rejects_photo_before_migration(tmp_path: Path):
    db = tmp_path / "old.db"
    _make_old_db(db)
    conn = sqlite3.connect(db)
    try:
        with_error = False
        try:
            conn.execute(
                "INSERT INTO batches (source, created_at) VALUES ('photo', 't')"
            )
        except sqlite3.IntegrityError:
            with_error = True
        assert with_error, "old schema should reject 'photo'"
    finally:
        conn.close()


def test_migration_allows_photo_and_preserves_data(tmp_path: Path):
    db = tmp_path / "old.db"
    _make_old_db(db)

    conn = connect(db)
    try:
        _allow_photo_batch_source(conn)

        # Existing rows + FK references preserved (id 7 kept).
        row = conn.execute("SELECT source FROM batches WHERE id = 7").fetchone()
        assert row["source"] == "manual"
        item = conn.execute(
            "SELECT delta FROM batch_items WHERE batch_id = 7"
        ).fetchone()
        assert item["delta"] == 5

        # 'photo' now accepted.
        conn.execute("INSERT INTO batches (source, created_at) VALUES ('photo', 't')")

        # 'manual'/'receipt' still accepted; junk still rejected.
        conn.execute("INSERT INTO batches (source, created_at) VALUES ('receipt', 't')")
        rejected = False
        try:
            conn.execute("INSERT INTO batches (source, created_at) VALUES ('junk', 't')")
        except sqlite3.IntegrityError:
            rejected = True
        assert rejected
    finally:
        conn.close()


def test_concurrent_migration_is_safe(tmp_path: Path):
    """Several workers booting at once must not corrupt or lose data.

    Each thread opens its own connection (as a gunicorn worker would) and runs
    the migration simultaneously. Exactly one should rebuild; the rest block on
    the write lock and then skip. No exceptions, and the pre-existing row must
    survive.
    """
    db = tmp_path / "old.db"
    _make_old_db(db)

    errors: list[Exception] = []
    barrier = threading.Barrier(5)

    def worker():
        conn = connect(db)
        try:
            barrier.wait()  # maximise overlap
            _allow_photo_batch_source(conn)
        except Exception as e:  # noqa: BLE001 - record for assertion
            errors.append(e)
        finally:
            conn.close()

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"migration raced: {errors}"

    conn = connect(db)
    try:
        # Data preserved exactly once (no duplication, no loss).
        rows = conn.execute("SELECT source FROM batches WHERE id = 7").fetchall()
        assert len(rows) == 1 and rows[0]["source"] == "manual"
        assert conn.execute("SELECT delta FROM batch_items WHERE batch_id = 7").fetchone()["delta"] == 5
        # Constraint widened...
        conn.execute("INSERT INTO batches (source, created_at) VALUES ('photo', 't')")
        # ...and no half-finished rebuild left the temp table behind.
        leftover = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = 'batches_new'"
        ).fetchone()
        assert leftover is None
    finally:
        conn.close()


def test_migration_is_noop_on_fresh_db(tmp_path: Path):
    db = tmp_path / "fresh.db"
    init_db(db)  # already includes 'photo'
    conn = connect(db)
    try:
        sql_before = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='batches'"
        ).fetchone()["sql"]
        _allow_photo_batch_source(conn)  # should detect 'photo' and skip
        sql_after = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='batches'"
        ).fetchone()["sql"]
        assert sql_before == sql_after
    finally:
        conn.close()
