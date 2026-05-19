import sqlite3
from pathlib import Path

from redbull_api.db import connect, init_db


def test_init_db_creates_tables(tmp_path: Path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with connect(db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )}
    assert tables == {"stock", "batches", "batch_items", "receipts"}


def test_init_db_is_idempotent(tmp_path: Path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    init_db(db_path)  # second call must not error


def test_foreign_keys_enabled(tmp_path: Path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with connect(db_path) as conn:
        (val,) = conn.execute("PRAGMA foreign_keys").fetchone()
    assert val == 1
