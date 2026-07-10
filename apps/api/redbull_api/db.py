"""SQLite connection helper + schema bootstrap."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Iterator


def connect(db_path: Path) -> sqlite3.Connection:
    """Return a connection with foreign keys + row factory configured."""
    conn = sqlite3.connect(db_path, isolation_level=None)  # autocommit
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: Path) -> None:
    """Create the schema if not present, then run migrations. Idempotent."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema = files("redbull_api").joinpath("schema.sql").read_text(encoding="utf-8")
    with connect(db_path) as conn:
        conn.executescript(schema)
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply idempotent, in-place migrations to an existing database."""
    _allow_photo_batch_source(conn)


def _allow_photo_batch_source(conn: sqlite3.Connection) -> None:
    """Widen the batches.source CHECK to include 'photo' on older databases.

    `CREATE TABLE IF NOT EXISTS` never alters an existing table, so a database
    created before 'photo' was added still carries the old CHECK constraint and
    would reject photo batches. SQLite can't ALTER a CHECK, so we rebuild the
    table following the documented 12-step procedure, preserving row ids (and
    therefore batch_items references).
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='batches'"
    ).fetchone()
    if not row or "'photo'" in row["sql"]:
        return  # fresh schema already includes 'photo', or table absent

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN")
    try:
        conn.execute(
            """
            CREATE TABLE batches_new (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                source       TEXT NOT NULL CHECK (source IN ('receipt', 'manual', 'photo')),
                created_at   TEXT NOT NULL,
                note         TEXT,
                receipt_id   INTEGER REFERENCES receipts(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO batches_new (id, source, created_at, note, receipt_id) "
            "SELECT id, source, created_at, note, receipt_id FROM batches"
        )
        conn.execute("DROP TABLE batches")
        conn.execute("ALTER TABLE batches_new RENAME TO batches")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_batches_created_at ON batches(created_at DESC)"
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Context manager wrapping a BEGIN/COMMIT/ROLLBACK on an autocommit connection.

    Since `connect()` returns a connection in autocommit mode (isolation_level=None),
    we manage the transaction explicitly here.
    """
    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
