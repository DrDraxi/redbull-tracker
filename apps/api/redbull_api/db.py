"""SQLite connection helper + schema bootstrap."""

from __future__ import annotations

import sqlite3
from importlib.resources import files
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    """Return a connection with foreign keys + row factory configured."""
    conn = sqlite3.connect(db_path, isolation_level=None)  # autocommit
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: Path) -> None:
    """Create the schema if not present. Idempotent."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema = files("redbull_api").joinpath("schema.sql").read_text()
    with connect(db_path) as conn:
        conn.executescript(schema)
