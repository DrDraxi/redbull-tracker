# API Monorepo + Receipt-Driven Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Flask API + web UI to RedBull Tracker for per-type stock tracking and receipt-based auto-counting via Claude, plus an API-client mode for the widget. Deployed to Railway.

**Architecture:** Monorepo with `apps/widget/` (existing .NET app, moved) and `apps/api/` (new Flask + SQLite + HTMX). Widget polls `/api/v1/stock` every 5s when `REDBULL_API_URL` is set, otherwise runs offline. Receipt parsing uses the Anthropic SDK (Haiku-4.5 primary, Sonnet-4.6 fallback) with forced tool-use for strict structured output.

**Tech Stack:**
- Existing widget: .NET 8, Win32 GDI via TaskbarWidget submodule
- API: Python 3.12, Flask, SQLite, `uv` for dep management, gunicorn for serving
- Web UI: Jinja templates + HTMX (no build step)
- AI: Anthropic Python SDK (`anthropic` package), adaptive thinking, prompt caching
- Deploy: Railway with Nixpacks (no Docker)

---

## File Structure

### New files

```
apps/api/
├── pyproject.toml                       # uv-managed Python deps
├── redbull_api/
│   ├── __init__.py
│   ├── app.py                           # Flask app factory
│   ├── config.py                        # env-var loading
│   ├── db.py                            # SQLite connection + schema apply
│   ├── schema.sql                       # DB DDL
│   ├── auth.py                          # bearer + cookie middleware
│   ├── stock.py                         # stock + batch business logic
│   ├── receipts.py                      # Anthropic vision call
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── api.py                       # /api/v1/* JSON endpoints
│   │   └── ui.py                        # web UI routes (/, /login, /logout)
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   └── partials/
│   │       ├── stock.html               # HTMX swap target for stock display
│   │       ├── log.html                 # HTMX swap target for activity log
│   │       └── batch_row.html           # single log row partial
│   └── static/
│       ├── style.css
│       └── htmx.min.js                  # vendored HTMX (~14KB)
└── tests/
    ├── conftest.py
    ├── fixtures/receipts/tesco.jpg      # canned receipt for live test
    ├── test_auth.py
    ├── test_stock.py
    ├── test_batches.py
    ├── test_receipts.py
    └── manual/test_receipt_live.py      # opt-in, hits real Anthropic API

apps/widget/Services/
├── ApiRedBullService.cs                 # polls API
└── RedBullServiceFactory.cs             # picks Offline vs Api

apps/widget/Assets/
└── redbull-generic.png                  # fallback icon for unknown types

apps/widget/Tests/                       # new test project
├── RedBullTracker.Tests.csproj
├── ApiRedBullServiceTests.cs
└── RedBullServiceFactoryTests.cs

.github/workflows/
├── ci-widget.yml                        # was ci.yml, scoped to widget
└── ci-api.yml                           # new

railway.toml                             # repo root
```

### Moved files (Phase 0)

```
src/RedBullTracker/  →  apps/widget/
```

### Modified files

- `RedBullTracker.sln` — point at new path
- `apps/widget/RedBullTracker.csproj` — embed `redbull-generic.png` resource
- `apps/widget/Services/IRedBullService.cs` — add `ByType` and `IsReadOnly`
- `apps/widget/Services/OfflineRedBullService.cs` — implement `ByType`
- `apps/widget/Widget/RedBullWidget.cs` — multi-icon render, click gating
- `apps/widget/Program.cs` — use factory
- `CLAUDE.md` — describe monorepo + new commands
- `README.md` — update build instructions
- `.github/workflows/release.yml` — update widget path

---

## Phase 0 — Monorepo restructure

Goal: move the widget into `apps/widget/`, update build + CI to find it there, leave behavior unchanged.

### Task 0.1: Move widget source

**Files:**
- Move: `src/RedBullTracker/` → `apps/widget/`

- [ ] **Step 1: Verify clean working tree**

Run: `git status`
Expected: `working tree clean` (no uncommitted changes before restructure)

- [ ] **Step 2: Create new directory and move with git**

```bash
mkdir -p apps
git mv src/RedBullTracker apps/widget
rmdir src   # should be empty after the move
```

- [ ] **Step 3: Verify the move**

Run: `git status`
Expected: all files shown as `renamed: src/RedBullTracker/... -> apps/widget/...`

### Task 0.2: Update solution file

**Files:**
- Modify: `RedBullTracker.sln`

- [ ] **Step 1: Inspect current solution file paths**

Run: `Select-String -Path RedBullTracker.sln -Pattern "src\\RedBullTracker"`
Expected: at least one line referencing `src\RedBullTracker\RedBullTracker.csproj`

- [ ] **Step 2: Update paths in solution**

Replace every occurrence of `src\RedBullTracker` with `apps\widget` in `RedBullTracker.sln`. There is exactly one project reference; just swap the path segment.

Run: `Select-String -Path RedBullTracker.sln -Pattern "src\\RedBullTracker"`
Expected: no matches

- [ ] **Step 3: Verify solution still builds**

Run: `dotnet build -p:Platform=x64`
Expected: `Build succeeded.` with one project built (RedBullTracker).

### Task 0.3: Update GitHub Actions workflows

**Files:**
- Rename: `.github/workflows/ci.yml` → `.github/workflows/ci-widget.yml`
- Modify: `.github/workflows/release.yml`

- [ ] **Step 1: Inspect existing workflow paths**

Run: `Select-String -Path .github/workflows/*.yml -Pattern "src/RedBullTracker"`
Expected: paths referencing `src/RedBullTracker/RedBullTracker.csproj` in both `ci.yml` and `release.yml`

- [ ] **Step 2: Rename CI workflow**

```bash
git mv .github/workflows/ci.yml .github/workflows/ci-widget.yml
```

- [ ] **Step 3: Update paths in both workflows**

In `.github/workflows/ci-widget.yml` and `.github/workflows/release.yml`, replace every occurrence of `src/RedBullTracker` with `apps/widget`.

Add a `paths:` filter to `ci-widget.yml` so it only runs on widget changes:

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'apps/widget/**'
      - 'lib/taskbar-widget/**'
      - 'RedBullTracker.sln'
      - '.github/workflows/ci-widget.yml'
  pull_request:
    paths:
      - 'apps/widget/**'
      - 'lib/taskbar-widget/**'
      - 'RedBullTracker.sln'
      - '.github/workflows/ci-widget.yml'
```

(Keep the existing `jobs:` section as-is apart from the path substitution.)

- [ ] **Step 4: Verify no stale references remain**

Run: `Select-String -Path .github/workflows/*.yml -Pattern "src/RedBullTracker"`
Expected: no matches

### Task 0.4: Update CLAUDE.md and README

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Update CLAUDE.md project structure section**

Find the "Solution Structure" section in `CLAUDE.md` and replace:

```
- **RedBullTracker** (`src/RedBullTracker/`) - Win32 GDI app with taskbar widget
```

with:

```
- **RedBullTracker** (`apps/widget/`) - Win32 GDI app with taskbar widget
- **API** (`apps/api/`) - Flask + SQLite backend (planned; see docs/superpowers/specs/2026-05-18-api-monorepo-receipt-tracking-design.md)
```

Update the directory tree below it to show `apps/widget/` instead of `src/RedBullTracker/`.

Update every build command in CLAUDE.md that references `src/RedBullTracker/` to use `apps/widget/`:
- `dotnet run --project src/RedBullTracker/RedBullTracker.csproj` → `dotnet run --project apps/widget/RedBullTracker.csproj`
- `dotnet publish src/RedBullTracker/RedBullTracker.csproj` → `dotnet publish apps/widget/RedBullTracker.csproj`

- [ ] **Step 2: Update README.md**

Find any `src/RedBullTracker` references and update to `apps/widget`. Add a brief note above the Building section:

```markdown
This is a monorepo. The widget lives in `apps/widget/`; the API will live in `apps/api/` (in progress).
```

- [ ] **Step 3: Verify**

Run: `Select-String -Path CLAUDE.md,README.md -Pattern "src/RedBullTracker"`
Expected: no matches

### Task 0.5: Commit Phase 0

- [ ] **Step 1: Run full build to verify**

Run: `dotnet build -p:Platform=x64`
Expected: `Build succeeded.`

- [ ] **Step 2: Quick runtime smoke check**

Run: `dotnet run --project apps/widget/RedBullTracker.csproj -p:Platform=x64`
Expected: widget appears in taskbar with current count, left/right click work. Stop with Ctrl+C.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: move widget to apps/widget for monorepo layout

Phase 0 of the API + monorepo work. No behavior change.
- src/RedBullTracker/ -> apps/widget/
- Updated solution, CI workflows, CLAUDE.md, README
- ci.yml renamed to ci-widget.yml with path filter"
```

---

## Phase 1 — API skeleton

Goal: a working Flask API with SQLite, auth, manual adjust + log + delete, and a basic web UI. No receipt parsing yet.

### Task 1.1: Bootstrap the Python project

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/redbull_api/__init__.py` (empty)

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "redbull-api"
version = "0.1.0"
description = "Red Bull stock tracking API"
requires-python = ">=3.12"
dependencies = [
    "flask>=3.0",
    "gunicorn>=21.2",
    "itsdangerous>=2.1",
    "flask-limiter>=3.5",
    "pillow>=10.0",
    "anthropic>=0.40",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-flask>=1.3",
    "ruff>=0.5",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty package marker**

Create `apps/api/redbull_api/__init__.py` with no content.

- [ ] **Step 3: Resolve and lock dependencies**

```bash
cd apps/api
uv sync
```

Expected: creates `apps/api/.venv/` and `apps/api/uv.lock`.

- [ ] **Step 4: Smoke import**

```bash
cd apps/api
uv run python -c "import flask, anthropic, itsdangerous; print('OK')"
```

Expected output: `OK`

### Task 1.2: Config module

**Files:**
- Create: `apps/api/redbull_api/config.py`

- [ ] **Step 1: Write the test for required env vars**

Create `apps/api/tests/conftest.py`:

```python
import os
import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Strip Redbull API env vars so each test starts clean."""
    for k in list(os.environ):
        if k.startswith(("API_TOKEN", "COOKIE_SECRET", "ANTHROPIC_API_KEY", "DATA_DIR")):
            monkeypatch.delenv(k, raising=False)
```

Create `apps/api/tests/test_config.py`:

```python
import pytest

from redbull_api.config import Config


def test_config_loads_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    cfg = Config.from_env()
    assert cfg.api_token == "tok"
    assert cfg.cookie_secret == "sec"
    assert cfg.anthropic_api_key == "sk-test"
    assert cfg.data_dir == tmp_path


def test_config_missing_api_token_raises(monkeypatch):
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk")
    with pytest.raises(RuntimeError, match="API_TOKEN"):
        Config.from_env()


def test_config_missing_cookie_secret_raises(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk")
    with pytest.raises(RuntimeError, match="COOKIE_SECRET"):
        Config.from_env()


def test_config_default_data_dir(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk")
    cfg = Config.from_env()
    assert str(cfg.data_dir) == "/data"
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
cd apps/api
uv run pytest tests/test_config.py -v
```

Expected: `ImportError` (no `Config` class yet).

- [ ] **Step 3: Implement Config**

Create `apps/api/redbull_api/config.py`:

```python
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
```

- [ ] **Step 4: Tests pass**

```bash
cd apps/api
uv run pytest tests/test_config.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/redbull_api/__init__.py apps/api/redbull_api/config.py apps/api/tests/conftest.py apps/api/tests/test_config.py
git commit -m "feat(api): bootstrap python project + config loader"
```

### Task 1.3: Database schema

**Files:**
- Create: `apps/api/redbull_api/schema.sql`
- Create: `apps/api/redbull_api/db.py`

- [ ] **Step 1: Write schema.sql**

```sql
-- Per-type stock; denormalized counter maintained transactionally.
CREATE TABLE IF NOT EXISTS stock (
    type        TEXT PRIMARY KEY,
    count       INTEGER NOT NULL CHECK (count >= 0),
    updated_at  TEXT NOT NULL
);

-- Each batch is one action: a receipt scan or a manual +/- adjustment.
CREATE TABLE IF NOT EXISTS batches (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT NOT NULL CHECK (source IN ('receipt', 'manual')),
    created_at   TEXT NOT NULL,
    note         TEXT,
    receipt_id   INTEGER REFERENCES receipts(id) ON DELETE SET NULL
);

-- Line items inside a batch; positive delta = add, negative = remove.
CREATE TABLE IF NOT EXISTS batch_items (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id  INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    type      TEXT NOT NULL,
    delta     INTEGER NOT NULL
);

-- Receipts: image file metadata + Claude's raw response.
CREATE TABLE IF NOT EXISTS receipts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT NOT NULL,
    thumbnail       TEXT,
    uploaded_at     TEXT NOT NULL,
    model_used      TEXT NOT NULL,
    raw_response    TEXT NOT NULL,
    confidence      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_batches_created_at ON batches(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_batch_items_batch  ON batch_items(batch_id);
```

- [ ] **Step 2: Write the test for db.py**

Create `apps/api/tests/test_db.py`:

```python
import sqlite3
from pathlib import Path

from redbull_api.db import connect, init_db


def test_init_db_creates_tables(tmp_path: Path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with connect(db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
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
```

- [ ] **Step 3: Run, confirm fail**

```bash
cd apps/api
uv run pytest tests/test_db.py -v
```

Expected: `ImportError` for `redbull_api.db`.

- [ ] **Step 4: Implement db.py**

Create `apps/api/redbull_api/db.py`:

```python
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
    """Create the schema if not present. Idempotent."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema = files("redbull_api").joinpath("schema.sql").read_text()
    with connect(db_path) as conn:
        conn.executescript(schema)


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Explicit transaction wrapper (since autocommit is on)."""
    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
```

- [ ] **Step 5: Tests pass**

```bash
cd apps/api
uv run pytest tests/test_db.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/api/redbull_api/schema.sql apps/api/redbull_api/db.py apps/api/tests/test_db.py
git commit -m "feat(api): sqlite schema + db connection helper"
```

### Task 1.4: Stock module (business logic)

**Files:**
- Create: `apps/api/redbull_api/stock.py`
- Create: `apps/api/tests/test_stock.py`

- [ ] **Step 1: Write the tests**

Create `apps/api/tests/test_stock.py`:

```python
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
    # Insert receipt row manually
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
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd apps/api
uv run pytest tests/test_stock.py -v
```

Expected: ImportError for `redbull_api.stock`.

- [ ] **Step 3: Implement stock.py**

Create `apps/api/redbull_api/stock.py`:

```python
"""Stock + batch business logic. Stays at the SQL level — no Flask deps."""

from __future__ import annotations

import json
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
            # Upsert stock; CHECK constraint enforces count >= 0
            conn.execute(
                """
                INSERT INTO stock (type, count, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(type) DO UPDATE SET
                    count = count + excluded.count,
                    updated_at = excluded.updated_at
                """,
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
```

- [ ] **Step 4: Tests pass**

```bash
cd apps/api
uv run pytest tests/test_stock.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/redbull_api/stock.py apps/api/tests/test_stock.py
git commit -m "feat(api): stock + batch business logic"
```

### Task 1.5: Auth module

**Files:**
- Create: `apps/api/redbull_api/auth.py`
- Create: `apps/api/tests/test_auth.py`

- [ ] **Step 1: Write the tests**

Create `apps/api/tests/test_auth.py`:

```python
import hmac

import pytest
from itsdangerous import URLSafeTimedSerializer

from redbull_api.auth import (
    check_bearer,
    check_cookie,
    make_cookie_value,
)


def test_check_bearer_accepts_correct_token():
    assert check_bearer("Bearer secret123", expected="secret123") is True


def test_check_bearer_rejects_missing_header():
    assert check_bearer(None, expected="secret123") is False


def test_check_bearer_rejects_wrong_token():
    assert check_bearer("Bearer wrong", expected="secret123") is False


def test_check_bearer_rejects_wrong_scheme():
    assert check_bearer("Basic secret123", expected="secret123") is False


def test_make_and_check_cookie_roundtrip():
    secret = "cookie-secret"
    value = make_cookie_value(secret)
    assert check_cookie(value, secret=secret, max_age_seconds=3600) is True


def test_check_cookie_rejects_tampered_value():
    secret = "cookie-secret"
    value = make_cookie_value(secret) + "x"
    assert check_cookie(value, secret=secret, max_age_seconds=3600) is False


def test_check_cookie_rejects_missing_cookie():
    assert check_cookie(None, secret="x", max_age_seconds=3600) is False


def test_check_cookie_rejects_expired():
    secret = "s"
    s = URLSafeTimedSerializer(secret)
    # Sign with a known timestamp in the past
    import time

    old = s.dumps("authed")
    time.sleep(0.05)  # ensure we move past the issue time
    assert check_cookie(old, secret=secret, max_age_seconds=0) is False
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd apps/api
uv run pytest tests/test_auth.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement auth.py**

Create `apps/api/redbull_api/auth.py`:

```python
"""Bearer-token + signed-cookie auth helpers."""

from __future__ import annotations

import hmac

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE_NAME = "redbull_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
_COOKIE_PAYLOAD = "authed"


def check_bearer(authorization_header: str | None, *, expected: str) -> bool:
    """Constant-time bearer token check."""
    if not authorization_header:
        return False
    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        return False
    return hmac.compare_digest(parts[1], expected)


def make_cookie_value(secret: str) -> str:
    """Generate a signed cookie payload."""
    return URLSafeTimedSerializer(secret).dumps(_COOKIE_PAYLOAD)


def check_cookie(value: str | None, *, secret: str, max_age_seconds: int) -> bool:
    """Validate a signed cookie. False on missing, tampered, or expired."""
    if not value:
        return False
    try:
        payload = URLSafeTimedSerializer(secret).loads(value, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return False
    return payload == _COOKIE_PAYLOAD
```

- [ ] **Step 4: Tests pass**

```bash
cd apps/api
uv run pytest tests/test_auth.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/redbull_api/auth.py apps/api/tests/test_auth.py
git commit -m "feat(api): bearer + signed-cookie auth helpers"
```

### Task 1.6: Flask app factory + auth middleware

**Files:**
- Create: `apps/api/redbull_api/app.py`

- [ ] **Step 1: Write the test**

Create `apps/api/tests/test_app_auth.py`:

```python
from pathlib import Path

import pytest

from redbull_api.app import create_app
from redbull_api.auth import make_cookie_value


@pytest.fixture
def app(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_health_endpoint_no_auth(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json["ok"] is True


def test_stock_endpoint_requires_auth(client):
    resp = client.get("/api/v1/stock")
    assert resp.status_code == 401


def test_stock_endpoint_accepts_bearer(client):
    resp = client.get("/api/v1/stock", headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 200


def test_stock_endpoint_rejects_wrong_bearer(client):
    resp = client.get("/api/v1/stock", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_stock_endpoint_accepts_cookie(client):
    cookie = make_cookie_value("sec")
    client.set_cookie("redbull_session", cookie)
    resp = client.get("/api/v1/stock")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd apps/api
uv run pytest tests/test_app_auth.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement app.py**

Create `apps/api/redbull_api/app.py`:

```python
"""Flask application factory."""

from __future__ import annotations

import sqlite3

from flask import Flask, g, jsonify, request

from .auth import COOKIE_MAX_AGE, COOKIE_NAME, check_bearer, check_cookie
from .config import Config
from .db import connect, init_db


def create_app(config: Config | None = None) -> Flask:
    config = config or Config.from_env()

    app = Flask(__name__)
    app.config["CONFIG"] = config

    db_path = config.data_dir / "redbull.db"
    init_db(db_path)
    app.config["DB_PATH"] = db_path

    @app.before_request
    def _open_db():
        g.db = connect(app.config["DB_PATH"])

    @app.teardown_request
    def _close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.before_request
    def _check_auth():
        # Public endpoints
        if request.path == "/api/v1/health":
            return None
        # Skip auth for UI auth flow + static (Phase 1.10 wires UI)
        if request.endpoint in {"ui.login_form", "ui.login_submit", "static"}:
            return None
        if not request.path.startswith("/api/v1/"):
            return None  # UI handled separately in Phase 1.10

        cfg: Config = app.config["CONFIG"]
        if check_bearer(request.headers.get("Authorization"), expected=cfg.api_token):
            return None
        cookie = request.cookies.get(COOKIE_NAME)
        if check_cookie(cookie, secret=cfg.cookie_secret, max_age_seconds=COOKIE_MAX_AGE):
            return None
        return jsonify({"error": "unauthorized"}), 401

    @app.get("/api/v1/health")
    def health():
        try:
            g.db.execute("SELECT 1").fetchone()
            return jsonify({"ok": True, "db": "ok"})
        except sqlite3.Error:
            return jsonify({"ok": False, "db": "error"}), 503

    @app.get("/api/v1/stock")
    def stock():
        from .stock import get_stock
        return jsonify(get_stock(g.db))

    return app
```

- [ ] **Step 4: Tests pass**

```bash
cd apps/api
uv run pytest tests/test_app_auth.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/redbull_api/app.py apps/api/tests/test_app_auth.py
git commit -m "feat(api): app factory + auth middleware + /health + /stock"
```

### Task 1.7: Adjust + batches + delete endpoints

**Files:**
- Create: `apps/api/redbull_api/routes/__init__.py` (empty)
- Create: `apps/api/redbull_api/routes/api.py`
- Modify: `apps/api/redbull_api/app.py` to register the blueprint

- [ ] **Step 1: Write the tests**

Create `apps/api/tests/test_api_endpoints.py`:

```python
from pathlib import Path

import pytest

from redbull_api.app import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


HEADERS = {"Authorization": "Bearer tok"}


def test_adjust_creates_batch(client):
    r = client.post("/api/v1/adjust", json={"type": "default", "delta": 2}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json["batch_id"] > 0
    assert r.json["stock"]["by_type"] == {"default": 2}


def test_adjust_with_note(client):
    r = client.post(
        "/api/v1/adjust",
        json={"type": "default", "delta": 1, "note": "found one"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    log = client.get("/api/v1/batches", headers=HEADERS).json
    assert log["batches"][0]["note"] == "found one"


def test_adjust_rejects_missing_fields(client):
    r = client.post("/api/v1/adjust", json={"type": "default"}, headers=HEADERS)
    assert r.status_code == 400


def test_adjust_rejects_zero_delta(client):
    r = client.post(
        "/api/v1/adjust", json={"type": "default", "delta": 0}, headers=HEADERS
    )
    assert r.status_code == 400


def test_adjust_rejects_underflow(client):
    r = client.post(
        "/api/v1/adjust", json={"type": "default", "delta": -1}, headers=HEADERS
    )
    assert r.status_code == 400


def test_batches_list(client):
    client.post("/api/v1/adjust", json={"type": "default", "delta": 1}, headers=HEADERS)
    client.post("/api/v1/adjust", json={"type": "sugarfree", "delta": 2}, headers=HEADERS)
    r = client.get("/api/v1/batches", headers=HEADERS)
    assert r.status_code == 200
    assert len(r.json["batches"]) == 2
    assert r.json["batches"][0]["source"] == "manual"


def test_batches_limit_param(client):
    for _ in range(5):
        client.post(
            "/api/v1/adjust", json={"type": "default", "delta": 1}, headers=HEADERS
        )
    r = client.get("/api/v1/batches?limit=3", headers=HEADERS)
    assert len(r.json["batches"]) == 3


def test_delete_batch_reverses_stock(client):
    bid = client.post(
        "/api/v1/adjust", json={"type": "default", "delta": 3}, headers=HEADERS
    ).json["batch_id"]
    r = client.delete(f"/api/v1/batches/{bid}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json["stock"]["by_type"] == {}


def test_delete_nonexistent_batch_404(client):
    r = client.delete("/api/v1/batches/9999", headers=HEADERS)
    assert r.status_code == 404
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd apps/api
uv run pytest tests/test_api_endpoints.py -v
```

Expected: 9 fails — 404 on POST /adjust etc.

- [ ] **Step 3: Create routes/__init__.py and routes/api.py**

`apps/api/redbull_api/routes/__init__.py` is an empty file.

Create `apps/api/redbull_api/routes/api.py`:

```python
"""JSON endpoints under /api/v1/."""

from __future__ import annotations

import sqlite3

from flask import Blueprint, g, jsonify, request

from ..stock import add_batch, delete_batch, get_stock, list_batches

bp = Blueprint("api", __name__, url_prefix="/api/v1")


@bp.post("/adjust")
def adjust():
    data = request.get_json(silent=True) or {}
    type_ = data.get("type")
    delta = data.get("delta")
    note = data.get("note")
    if not isinstance(type_, str) or not type_:
        return jsonify({"error": "invalid_type"}), 400
    if not isinstance(delta, int) or delta == 0:
        return jsonify({"error": "invalid_delta"}), 400

    try:
        batch_id = add_batch(
            g.db, source="manual", items=[(type_, delta)], note=note
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": "stock_underflow"}), 400

    return jsonify({"batch_id": batch_id, "stock": get_stock(g.db)})


@bp.get("/batches")
def batches():
    try:
        limit = int(request.args.get("limit", "50"))
    except ValueError:
        limit = 50
    limit = max(1, min(limit, 500))
    return jsonify({"batches": list_batches(g.db, limit=limit)})


@bp.delete("/batches/<int:batch_id>")
def delete(batch_id: int):
    ok = delete_batch(g.db, batch_id)
    if not ok:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"stock": get_stock(g.db)})
```

- [ ] **Step 4: Register the blueprint and remove inline routes**

In `apps/api/redbull_api/app.py`, replace the existing `@app.get("/api/v1/stock")` route with blueprint registration. After `init_db(db_path)`, replace the file's `health()` and `stock()` route handlers with this — keep `health()` as-is (it's path-checked before auth), and move `stock()` into the blueprint:

Final `apps/api/redbull_api/app.py`:

```python
"""Flask application factory."""

from __future__ import annotations

import sqlite3

from flask import Flask, g, jsonify, request

from .auth import COOKIE_MAX_AGE, COOKIE_NAME, check_bearer, check_cookie
from .config import Config
from .db import connect, init_db
from .routes.api import bp as api_bp
from .stock import get_stock


def create_app(config: Config | None = None) -> Flask:
    config = config or Config.from_env()

    app = Flask(__name__)
    app.config["CONFIG"] = config

    db_path = config.data_dir / "redbull.db"
    init_db(db_path)
    app.config["DB_PATH"] = db_path

    @app.before_request
    def _open_db():
        g.db = connect(app.config["DB_PATH"])

    @app.teardown_request
    def _close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.before_request
    def _check_auth():
        if request.path == "/api/v1/health":
            return None
        if request.endpoint in {"ui.login_form", "ui.login_submit", "static"}:
            return None
        if not request.path.startswith("/api/v1/"):
            return None

        cfg: Config = app.config["CONFIG"]
        if check_bearer(request.headers.get("Authorization"), expected=cfg.api_token):
            return None
        cookie = request.cookies.get(COOKIE_NAME)
        if check_cookie(cookie, secret=cfg.cookie_secret, max_age_seconds=COOKIE_MAX_AGE):
            return None
        return jsonify({"error": "unauthorized"}), 401

    @app.get("/api/v1/health")
    def health():
        try:
            g.db.execute("SELECT 1").fetchone()
            return jsonify({"ok": True, "db": "ok"})
        except sqlite3.Error:
            return jsonify({"ok": False, "db": "error"}), 503

    @app.get("/api/v1/stock")
    def stock():
        return jsonify(get_stock(g.db))

    app.register_blueprint(api_bp)
    return app
```

- [ ] **Step 5: Tests pass**

```bash
cd apps/api
uv run pytest tests/ -v
```

Expected: all tests pass (test_app_auth + test_api_endpoints + test_config + test_db + test_stock + test_auth).

- [ ] **Step 6: Commit**

```bash
git add apps/api/redbull_api/routes/ apps/api/redbull_api/app.py apps/api/tests/test_api_endpoints.py
git commit -m "feat(api): adjust + batches + delete endpoints"
```

### Task 1.8: Vendor HTMX

**Files:**
- Create: `apps/api/redbull_api/static/htmx.min.js`

- [ ] **Step 1: Download HTMX 2.x**

```bash
mkdir -p apps/api/redbull_api/static
curl -L -o apps/api/redbull_api/static/htmx.min.js https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js
```

- [ ] **Step 2: Verify size**

```bash
ls -la apps/api/redbull_api/static/htmx.min.js
```

Expected: ~14-16KB file.

- [ ] **Step 3: Commit**

```bash
git add apps/api/redbull_api/static/htmx.min.js
git commit -m "chore(api): vendor htmx 2.0.4"
```

### Task 1.9: Templates (base + login + dashboard + partials)

**Files:**
- Create: `apps/api/redbull_api/templates/base.html`
- Create: `apps/api/redbull_api/templates/login.html`
- Create: `apps/api/redbull_api/templates/dashboard.html`
- Create: `apps/api/redbull_api/templates/partials/stock.html`
- Create: `apps/api/redbull_api/templates/partials/log.html`
- Create: `apps/api/redbull_api/templates/partials/batch_row.html`
- Create: `apps/api/redbull_api/static/style.css`

- [ ] **Step 1: Write base.html**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Red Bull Tracker{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
  <script src="{{ url_for('static', filename='htmx.min.js') }}"></script>
</head>
<body>
  <header>
    <h1>Red Bull Tracker</h1>
    {% if session_authed %}<form method="post" action="{{ url_for('ui.logout') }}"><button>Logout</button></form>{% endif %}
  </header>
  <main>
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 2: Write login.html**

```html
{% extends "base.html" %}
{% block title %}Login — Red Bull Tracker{% endblock %}
{% block content %}
  <form method="post" action="{{ url_for('ui.login_submit') }}" class="login">
    <label>Token <input type="password" name="token" autofocus required></label>
    <button type="submit">Sign in</button>
    {% if error %}<p class="error">{{ error }}</p>{% endif %}
  </form>
{% endblock %}
```

- [ ] **Step 3: Write dashboard.html**

```html
{% extends "base.html" %}
{% block content %}
  <section id="stock" hx-get="/ui/stock" hx-trigger="every 5s" hx-swap="outerHTML">
    {% include "partials/stock.html" %}
  </section>

  <section class="actions">
    <h2>Manual adjust</h2>
    <form hx-post="/api/v1/adjust" hx-ext="json-enc" hx-target="#stock" hx-swap="none">
      <input name="type" placeholder="type (e.g. default)" required>
      <input name="delta" type="number" required>
      <input name="note" placeholder="note (optional)">
      <button>Apply</button>
    </form>

    <h2>Upload receipt</h2>
    <form hx-post="/api/v1/receipts" hx-encoding="multipart/form-data" hx-target="#log" hx-swap="outerHTML">
      <input type="file" name="image" accept="image/*" required>
      <button>Parse with Claude</button>
    </form>
  </section>

  <section id="log" hx-get="/ui/log" hx-trigger="every 10s" hx-swap="outerHTML">
    {% include "partials/log.html" %}
  </section>
{% endblock %}
```

(The form for `/api/v1/adjust` uses `hx-ext="json-enc"` which we'll wire next. Receipt upload comes in Phase 2; the form is here now and will function after Phase 2.)

- [ ] **Step 4: Write partials/stock.html**

```html
<section id="stock" hx-get="/ui/stock" hx-trigger="every 5s" hx-swap="outerHTML">
  <h2>Stock: {{ stock.total }}</h2>
  {% if stock.by_type %}
    <ul class="by-type">
      {% for type, count in stock.by_type.items() %}
        <li><strong>{{ type }}</strong>: {{ count }}</li>
      {% endfor %}
    </ul>
  {% else %}
    <p>No Red Bulls in stock.</p>
  {% endif %}
</section>
```

- [ ] **Step 5: Write partials/log.html**

```html
<section id="log" hx-get="/ui/log" hx-trigger="every 10s" hx-swap="outerHTML">
  <h2>Recent activity</h2>
  {% if batches %}
    <ul class="log">
      {% for batch in batches %}
        {% include "partials/batch_row.html" %}
      {% endfor %}
    </ul>
  {% else %}
    <p>No activity yet.</p>
  {% endif %}
</section>
```

- [ ] **Step 6: Write partials/batch_row.html**

```html
<li class="batch batch--{{ batch.source }}" id="batch-{{ batch.id }}">
  <div class="batch-meta">
    <span class="time">{{ batch.created_at }}</span>
    <span class="source">{{ batch.source }}</span>
    {% if batch.receipt %}<a href="/api/v1/receipts/{{ batch.receipt.id }}/thumb">thumb</a>{% endif %}
  </div>
  <div class="batch-items">
    {% if batch.items %}
      {% for it in batch.items %}
        <span class="item">{{ it.delta }} {{ it.type }}</span>
      {% endfor %}
    {% else %}
      <em>(no items)</em>
    {% endif %}
  </div>
  {% if batch.note %}<div class="batch-note">{{ batch.note }}</div>{% endif %}
  <button hx-delete="/api/v1/batches/{{ batch.id }}" hx-target="#log" hx-swap="outerHTML"
          hx-confirm="Delete this entry?">×</button>
</li>
```

- [ ] **Step 7: Write static/style.css**

```css
* { box-sizing: border-box; }
body { font: 14px/1.4 system-ui, sans-serif; margin: 0; padding: 1rem; max-width: 800px; margin-inline: auto; }
header { display: flex; align-items: center; justify-content: space-between; }
h1 { font-size: 1.4rem; margin: 0; }
h2 { font-size: 1.1rem; margin-top: 1.5rem; }
section { margin-block: 1.5rem; padding: 1rem; border: 1px solid #ddd; border-radius: 6px; }
ul.by-type, ul.log { list-style: none; padding: 0; margin: 0; }
ul.by-type li { display: inline-block; margin-right: 1rem; padding: 0.25rem 0.5rem; background: #f5f5f5; border-radius: 4px; }
li.batch { padding: 0.5rem; border-bottom: 1px solid #eee; display: grid; grid-template-columns: 1fr auto; gap: 0.25rem 1rem; }
li.batch--receipt { background: #fafffd; }
.batch-meta { color: #666; font-size: 0.85rem; }
.batch-items .item { margin-right: 0.5rem; }
.batch-note { font-style: italic; color: #555; grid-column: 1; }
li.batch button { background: transparent; border: none; cursor: pointer; color: #c33; font-size: 1.2rem; align-self: start; }
form { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }
input, button { padding: 0.4rem 0.6rem; font: inherit; }
button { cursor: pointer; }
.login { flex-direction: column; align-items: stretch; max-width: 300px; }
.error { color: #c33; }
```

- [ ] **Step 8: Commit**

```bash
git add apps/api/redbull_api/templates/ apps/api/redbull_api/static/style.css
git commit -m "feat(api): web ui templates + stylesheet"
```

### Task 1.10: UI routes (login, dashboard, HTMX fragments)

**Files:**
- Create: `apps/api/redbull_api/routes/ui.py`
- Modify: `apps/api/redbull_api/app.py` to register UI blueprint and update auth to gate UI routes

- [ ] **Step 1: Write the tests**

Create `apps/api/tests/test_ui.py`:

```python
from pathlib import Path

import pytest

from redbull_api.app import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_root_redirects_to_login_when_unauthed(client):
    r = client.get("/")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_login_form_renders(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert b"token" in r.data.lower()


def test_login_submit_sets_cookie(client):
    r = client.post("/login", data={"token": "tok"})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/")
    set_cookie = r.headers.get("Set-Cookie", "")
    assert "redbull_session=" in set_cookie


def test_login_submit_rejects_wrong_token(client):
    r = client.post("/login", data={"token": "wrong"})
    assert r.status_code == 401


def test_dashboard_renders_when_authed(client):
    client.post("/login", data={"token": "tok"})
    r = client.get("/")
    assert r.status_code == 200
    assert b"Stock" in r.data


def test_ui_stock_fragment(client):
    client.post("/login", data={"token": "tok"})
    r = client.get("/ui/stock")
    assert r.status_code == 200
    # HTML fragment, not full page
    assert b"<html" not in r.data
    assert b"Stock" in r.data


def test_ui_log_fragment(client):
    client.post("/login", data={"token": "tok"})
    r = client.get("/ui/log")
    assert r.status_code == 200
    assert b"<html" not in r.data
    assert b"Recent activity" in r.data


def test_logout_clears_cookie(client):
    client.post("/login", data={"token": "tok"})
    r = client.post("/logout")
    assert r.status_code == 302
    # Cookie cleared
    set_cookie = r.headers.get("Set-Cookie", "")
    assert "redbull_session=" in set_cookie  # set to empty/expired
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd apps/api
uv run pytest tests/test_ui.py -v
```

Expected: 8 fails (404 / endpoint missing).

- [ ] **Step 3: Implement routes/ui.py**

Create `apps/api/redbull_api/routes/ui.py`:

```python
"""Web UI routes — login + dashboard + HTMX fragments."""

from __future__ import annotations

import hmac

from flask import (
    Blueprint,
    current_app,
    g,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from ..auth import (
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    check_cookie,
    make_cookie_value,
)
from ..config import Config
from ..stock import get_stock, list_batches

bp = Blueprint("ui", __name__)


def _is_authed() -> bool:
    cfg: Config = current_app.config["CONFIG"]
    cookie = request.cookies.get(COOKIE_NAME)
    return check_cookie(cookie, secret=cfg.cookie_secret, max_age_seconds=COOKIE_MAX_AGE)


@bp.get("/login")
def login_form():
    return render_template("login.html", error=None, session_authed=False)


@bp.post("/login")
def login_submit():
    cfg: Config = current_app.config["CONFIG"]
    submitted = request.form.get("token", "")
    if not hmac.compare_digest(submitted, cfg.api_token):
        return render_template(
            "login.html", error="Invalid token.", session_authed=False
        ), 401

    resp = make_response(redirect(url_for("ui.dashboard")))
    resp.set_cookie(
        COOKIE_NAME,
        make_cookie_value(cfg.cookie_secret),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=not current_app.config.get("TESTING", False),
        samesite="Lax",
    )
    return resp


@bp.post("/logout")
def logout():
    resp = make_response(redirect(url_for("ui.login_form")))
    resp.set_cookie(COOKIE_NAME, "", expires=0)
    return resp


@bp.get("/")
def dashboard():
    if not _is_authed():
        return redirect(url_for("ui.login_form"))
    return render_template(
        "dashboard.html",
        stock=get_stock(g.db),
        batches=list_batches(g.db, limit=50),
        session_authed=True,
    )


@bp.get("/ui/stock")
def stock_fragment():
    if not _is_authed():
        return "", 401
    return render_template("partials/stock.html", stock=get_stock(g.db))


@bp.get("/ui/log")
def log_fragment():
    if not _is_authed():
        return "", 401
    return render_template(
        "partials/log.html", batches=list_batches(g.db, limit=50)
    )
```

- [ ] **Step 4: Register the UI blueprint**

In `apps/api/redbull_api/app.py`, add to the imports:

```python
from .routes.ui import bp as ui_bp
```

And after `app.register_blueprint(api_bp)`:

```python
    app.register_blueprint(ui_bp)
```

- [ ] **Step 5: Tests pass**

```bash
cd apps/api
uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Manual smoke test**

```bash
cd apps/api
API_TOKEN=devtoken COOKIE_SECRET=devsecret ANTHROPIC_API_KEY=sk DATA_DIR=./.data \
  uv run flask --app redbull_api.app:create_app run --debug
```

Visit `http://127.0.0.1:5000/`. Expected: redirected to `/login`. Enter `devtoken`. Expected: dashboard with empty stock. Add `default` with delta `3`. Expected: stock updates within 5s; log shows the manual batch with a × button.

Stop the server (Ctrl+C).

- [ ] **Step 7: Commit**

```bash
git add apps/api/redbull_api/routes/ui.py apps/api/redbull_api/app.py apps/api/tests/test_ui.py
git commit -m "feat(api): web ui — login, dashboard, htmx fragments"
```

### Task 1.11: CI workflow for the API

**Files:**
- Create: `.github/workflows/ci-api.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: CI (API)

on:
  push:
    branches: [main]
    paths:
      - 'apps/api/**'
      - '.github/workflows/ci-api.yml'
  pull_request:
    paths:
      - 'apps/api/**'
      - '.github/workflows/ci-api.yml'

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/api
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"
      - name: Set up Python
        run: uv python install 3.12
      - name: Install deps
        run: uv sync --frozen
      - name: Lint
        run: uv run ruff check .
      - name: Test
        run: uv run pytest tests/ -v --ignore=tests/manual
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci-api.yml
git commit -m "ci: add api workflow"
```

---

## Phase 2 — Receipt parsing

Goal: `POST /api/v1/receipts` accepts an image, calls Claude, persists batch + receipt, returns updated stock.

### Task 2.1: Image storage helpers

**Files:**
- Create: `apps/api/redbull_api/images.py`
- Create: `apps/api/tests/test_images.py`

- [ ] **Step 1: Write the tests**

Create `apps/api/tests/test_images.py`:

```python
import io
from pathlib import Path

import pytest
from PIL import Image

from redbull_api.images import save_image_and_thumbnail


def _make_image_bytes(size=(800, 600), fmt="JPEG") -> bytes:
    img = Image.new("RGB", size, color=(200, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_save_jpeg_creates_files(tmp_path: Path):
    data = _make_image_bytes()
    result = save_image_and_thumbnail(data, content_type="image/jpeg", data_dir=tmp_path)
    full = tmp_path / "receipts" / result.filename
    thumb = tmp_path / "receipts" / "thumbs" / result.thumbnail
    assert full.exists()
    assert thumb.exists()


def test_thumbnail_is_smaller(tmp_path: Path):
    data = _make_image_bytes(size=(2000, 1500))
    result = save_image_and_thumbnail(data, content_type="image/jpeg", data_dir=tmp_path)
    thumb = tmp_path / "receipts" / "thumbs" / result.thumbnail
    with Image.open(thumb) as t:
        assert max(t.size) <= 200


def test_rejects_non_image(tmp_path: Path):
    with pytest.raises(ValueError, match="not an image"):
        save_image_and_thumbnail(b"not an image", content_type="image/jpeg", data_dir=tmp_path)


def test_filename_is_uuid_based(tmp_path: Path):
    data = _make_image_bytes()
    result = save_image_and_thumbnail(data, content_type="image/jpeg", data_dir=tmp_path)
    # filename should look like '<uuid>.jpg', not the original
    assert result.filename.endswith(".jpg")
    assert len(result.filename) > 10
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd apps/api
uv run pytest tests/test_images.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement images.py**

Create `apps/api/redbull_api/images.py`:

```python
"""Image persistence: full image + 200px thumbnail."""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

THUMB_MAX = 200
SUPPORTED_FORMATS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


@dataclass(frozen=True)
class SavedImage:
    filename: str   # relative to data_dir/receipts/
    thumbnail: str  # relative to data_dir/receipts/thumbs/


def save_image_and_thumbnail(
    data: bytes, *, content_type: str, data_dir: Path
) -> SavedImage:
    ext = SUPPORTED_FORMATS.get(content_type, "jpg")
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError("not an image") from e

    receipts_dir = data_dir / "receipts"
    thumbs_dir = receipts_dir / "thumbs"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    uid = uuid.uuid4().hex
    full_name = f"{uid}.{ext}"
    thumb_name = f"{uid}.jpg"  # thumbnails always JPEG

    full_path = receipts_dir / full_name
    full_path.write_bytes(data)

    with Image.open(full_path) as img:
        # Convert to RGB so we can save as JPEG even for PNG/WebP inputs
        thumb = img.convert("RGB")
        thumb.thumbnail((THUMB_MAX, THUMB_MAX))
        thumb.save(thumbs_dir / thumb_name, "JPEG", quality=85)

    return SavedImage(filename=full_name, thumbnail=thumb_name)
```

- [ ] **Step 4: Tests pass**

```bash
cd apps/api
uv run pytest tests/test_images.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/redbull_api/images.py apps/api/tests/test_images.py
git commit -m "feat(api): image + thumbnail persistence"
```

### Task 2.2: Receipt parsing module

**Files:**
- Create: `apps/api/redbull_api/receipts.py`
- Create: `apps/api/tests/test_receipts.py`

- [ ] **Step 1: Write the tests**

Create `apps/api/tests/test_receipts.py`:

```python
import json
from unittest.mock import MagicMock

import pytest

from redbull_api.receipts import (
    ParseResult,
    parse_receipt,
)


class _FakeToolUseBlock:
    def __init__(self, input_dict):
        self.type = "tool_use"
        self.input = input_dict


class _FakeResponse:
    def __init__(self, items, confidence):
        self.content = [_FakeToolUseBlock({"items": items, "confidence": confidence})]


def _client_returning(*responses):
    """Build a fake Anthropic client whose .messages.create returns the given responses in order."""
    client = MagicMock()
    client.messages.create.side_effect = list(responses)
    return client


def test_high_confidence_returns_items():
    client = _client_returning(
        _FakeResponse([{"type": "sugarfree", "count": 2}], "high")
    )
    result = parse_receipt(client, image_bytes=b"\xff\xd8", media_type="image/jpeg")
    assert isinstance(result, ParseResult)
    assert result.items == [{"type": "sugarfree", "count": 2}]
    assert result.confidence == "high"
    assert result.model_used == "claude-haiku-4-5"
    assert client.messages.create.call_count == 1


def test_low_confidence_retries_with_sonnet():
    client = _client_returning(
        _FakeResponse([{"type": "default", "count": 1}], "low"),
        _FakeResponse([{"type": "default", "count": 1}], "high"),
    )
    result = parse_receipt(client, image_bytes=b"\xff\xd8", media_type="image/jpeg")
    assert result.model_used == "claude-sonnet-4-6"
    assert result.confidence == "high"
    assert client.messages.create.call_count == 2

    # Verify the second call used the larger model
    second_call_kwargs = client.messages.create.call_args_list[1].kwargs
    assert second_call_kwargs["model"] == "claude-sonnet-4-6"


def test_none_confidence_returns_empty_items_no_retry():
    client = _client_returning(_FakeResponse([], "none"))
    result = parse_receipt(client, image_bytes=b"\xff\xd8", media_type="image/jpeg")
    assert result.items == []
    assert result.confidence == "none"
    assert client.messages.create.call_count == 1


def test_low_then_low_keeps_sonnet_result():
    client = _client_returning(
        _FakeResponse([{"type": "default", "count": 1}], "low"),
        _FakeResponse([{"type": "default", "count": 1}], "low"),
    )
    result = parse_receipt(client, image_bytes=b"\xff\xd8", media_type="image/jpeg")
    assert result.confidence == "low"
    assert result.model_used == "claude-sonnet-4-6"
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd apps/api
uv run pytest tests/test_receipts.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement receipts.py**

Create `apps/api/redbull_api/receipts.py`:

```python
"""Receipt parsing via Anthropic vision."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import anthropic

MODEL_PRIMARY = "claude-haiku-4-5"
MODEL_FALLBACK = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a receipt parser specialized in identifying Red Bull energy drink purchases.

Given an image of a receipt, identify every line item that is a Red Bull product
and call the record_redbulls tool with the results.

Type identification:
- "default" — regular Red Bull (red can). Receipt lines: "RED BULL", "RED BULL ENERGY"
- "sugarfree" — sugar-free / zero variants. Receipt lines: "RED BULL SUG.FRE", "SUGARFREE", "ZERO"
- "tropical", "watermelon", "peach", "coconut", "summer" — Edition / Summer Edition flavors
- For any other flavor variant, use a short lowercase English keyword

Multi-pack handling: a line like "2 *  43.90  RED BULL" means count=2, not count=1.

Confidence:
- "high" — receipt is clearly legible and you are confident in types and counts
- "low" — text is partially obscured / OCR-ambiguous but you made a best guess
- "none" — no Red Bull on this receipt, or image unreadable
"""

RECORD_TOOL = {
    "name": "record_redbulls",
    "description": "Record Red Bull cans purchased on this receipt.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": (
                                "Red Bull variant: 'default' for regular, "
                                "'sugarfree' for sugar-free/zero, or another "
                                "lowercase keyword if clearly identifiable. "
                                "Default to 'default' if ambiguous."
                            ),
                        },
                        "count": {"type": "integer", "minimum": 1},
                    },
                    "required": ["type", "count"],
                },
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "low", "none"],
            },
        },
        "required": ["items", "confidence"],
    },
}


@dataclass(frozen=True)
class ParseResult:
    items: list[dict[str, Any]]
    confidence: str
    model_used: str
    raw_response: dict[str, Any]


def _call_claude(
    client: anthropic.Anthropic,
    *,
    model: str,
    image_b64: str,
    media_type: str,
) -> dict[str, Any]:
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[RECORD_TOOL],
        tool_choice={"type": "tool", "name": "record_redbulls"},
        thinking={"type": "adaptive"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": "Parse this receipt."},
                ],
            }
        ],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    return {"items": [], "confidence": "none"}


def parse_receipt(
    client: anthropic.Anthropic,
    *,
    image_bytes: bytes,
    media_type: str,
) -> ParseResult:
    image_b64 = base64.standard_b64encode(image_bytes).decode("ascii")

    # Primary call
    raw = _call_claude(client, model=MODEL_PRIMARY, image_b64=image_b64, media_type=media_type)
    items = raw.get("items", []) or []
    confidence = raw.get("confidence", "none")

    if confidence == "low":
        # Retry with Sonnet
        raw = _call_claude(client, model=MODEL_FALLBACK, image_b64=image_b64, media_type=media_type)
        items = raw.get("items", []) or []
        confidence = raw.get("confidence", "none")
        return ParseResult(
            items=items, confidence=confidence, model_used=MODEL_FALLBACK, raw_response=raw
        )

    return ParseResult(
        items=items, confidence=confidence, model_used=MODEL_PRIMARY, raw_response=raw
    )
```

- [ ] **Step 4: Tests pass**

```bash
cd apps/api
uv run pytest tests/test_receipts.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/redbull_api/receipts.py apps/api/tests/test_receipts.py
git commit -m "feat(api): receipt parsing via Anthropic vision"
```

### Task 2.3: POST /receipts endpoint

**Files:**
- Modify: `apps/api/redbull_api/routes/api.py`

- [ ] **Step 1: Write the integration test**

Create `apps/api/tests/test_api_receipts.py`:

```python
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from redbull_api.app import create_app


def _make_jpeg(size=(800, 600)) -> bytes:
    img = Image.new("RGB", size, color=(180, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


HEADERS = {"Authorization": "Bearer tok"}


def _fake_parse(items, confidence, model="claude-haiku-4-5"):
    from redbull_api.receipts import ParseResult

    return ParseResult(
        items=items, confidence=confidence, model_used=model,
        raw_response={"items": items, "confidence": confidence},
    )


def test_upload_high_confidence_creates_batch(client):
    with patch("redbull_api.routes.api.parse_receipt") as mock_parse:
        mock_parse.return_value = _fake_parse(
            [{"type": "sugarfree", "count": 2}], "high"
        )
        r = client.post(
            "/api/v1/receipts",
            data={"image": (io.BytesIO(_make_jpeg()), "receipt.jpg")},
            content_type="multipart/form-data",
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert r.json["confidence"] == "high"
    assert r.json["stock"]["by_type"] == {"sugarfree": 2}
    assert r.json["batch_id"] > 0
    assert r.json["receipt_id"] > 0


def test_upload_none_confidence_still_creates_batch_returns_422(client):
    with patch("redbull_api.routes.api.parse_receipt") as mock_parse:
        mock_parse.return_value = _fake_parse([], "none")
        r = client.post(
            "/api/v1/receipts",
            data={"image": (io.BytesIO(_make_jpeg()), "receipt.jpg")},
            content_type="multipart/form-data",
            headers=HEADERS,
        )
    assert r.status_code == 422
    assert r.json["error"] == "no_redbulls_found"
    assert r.json["confidence"] == "none"
    assert r.json["batch_id"] > 0
    # Verify the empty batch shows in the log
    log = client.get("/api/v1/batches", headers=HEADERS).json
    assert any(b["id"] == r.json["batch_id"] for b in log["batches"])


def test_upload_rejects_non_image(client):
    r = client.post(
        "/api/v1/receipts",
        data={"image": (io.BytesIO(b"not an image"), "x.jpg")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )
    assert r.status_code == 400


def test_upload_rejects_missing_file(client):
    r = client.post("/api/v1/receipts", data={}, headers=HEADERS)
    assert r.status_code == 400
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd apps/api
uv run pytest tests/test_api_receipts.py -v
```

Expected: 404 / missing route.

- [ ] **Step 3: Extend routes/api.py**

Add to `apps/api/redbull_api/routes/api.py`:

```python
import json
import os

import anthropic

from ..images import save_image_and_thumbnail
from ..receipts import parse_receipt
```

(Add these imports near the top with the existing ones.)

Then add the route after `delete()`:

```python
@bp.post("/receipts")
def upload_receipt():
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "missing_image"}), 400

    data = file.read()
    if not data:
        return jsonify({"error": "missing_image"}), 400

    cfg = current_app.config["CONFIG"]
    try:
        saved = save_image_and_thumbnail(
            data, content_type=file.mimetype or "image/jpeg", data_dir=cfg.data_dir
        )
    except ValueError:
        return jsonify({"error": "invalid_image"}), 400

    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    result = parse_receipt(
        client, image_bytes=data, media_type=file.mimetype or "image/jpeg"
    )

    # Insert receipt row
    cur = g.db.execute(
        "INSERT INTO receipts (filename, thumbnail, uploaded_at, model_used, raw_response, confidence) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            saved.filename,
            saved.thumbnail,
            __import__("datetime").datetime.utcnow().isoformat() + "Z",
            result.model_used,
            json.dumps(result.raw_response),
            result.confidence,
        ),
    )
    receipt_id = cur.lastrowid

    # Create the batch — even with zero items when confidence == "none"
    items = [(it["type"], it["count"]) for it in result.items]
    batch_id = add_batch(
        g.db, source="receipt", items=items, note=None, receipt_id=receipt_id
    )

    payload = {
        "batch_id": batch_id,
        "receipt_id": receipt_id,
        "items": result.items,
        "confidence": result.confidence,
        "stock": get_stock(g.db),
    }
    if result.confidence == "none":
        payload["error"] = "no_redbulls_found"
        return jsonify(payload), 422
    return jsonify(payload)
```

And add `from flask import current_app` to the imports at the top of the file.

- [ ] **Step 4: Tests pass**

```bash
cd apps/api
uv run pytest tests/test_api_receipts.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/redbull_api/routes/api.py apps/api/tests/test_api_receipts.py
git commit -m "feat(api): POST /receipts endpoint with claude parsing"
```

### Task 2.4: Serve receipt images

**Files:**
- Modify: `apps/api/redbull_api/routes/api.py`

- [ ] **Step 1: Write the tests**

Add to `apps/api/tests/test_api_receipts.py`:

```python
def test_serve_thumbnail(client):
    with patch("redbull_api.routes.api.parse_receipt") as mock_parse:
        mock_parse.return_value = _fake_parse([{"type": "default", "count": 1}], "high")
        upload = client.post(
            "/api/v1/receipts",
            data={"image": (io.BytesIO(_make_jpeg()), "r.jpg")},
            content_type="multipart/form-data",
            headers=HEADERS,
        )
    rid = upload.json["receipt_id"]
    r = client.get(f"/api/v1/receipts/{rid}/thumb", headers=HEADERS)
    assert r.status_code == 200
    assert r.mimetype == "image/jpeg"


def test_serve_full_image(client):
    with patch("redbull_api.routes.api.parse_receipt") as mock_parse:
        mock_parse.return_value = _fake_parse([{"type": "default", "count": 1}], "high")
        upload = client.post(
            "/api/v1/receipts",
            data={"image": (io.BytesIO(_make_jpeg()), "r.jpg")},
            content_type="multipart/form-data",
            headers=HEADERS,
        )
    rid = upload.json["receipt_id"]
    r = client.get(f"/api/v1/receipts/{rid}/image", headers=HEADERS)
    assert r.status_code == 200
    assert r.mimetype.startswith("image/")


def test_serve_thumbnail_404(client):
    r = client.get("/api/v1/receipts/9999/thumb", headers=HEADERS)
    assert r.status_code == 404
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd apps/api
uv run pytest tests/test_api_receipts.py::test_serve_thumbnail -v
```

Expected: 404.

- [ ] **Step 3: Implement the image-serving routes**

Add to `apps/api/redbull_api/routes/api.py`:

```python
from flask import send_from_directory


@bp.get("/receipts/<int:receipt_id>/image")
def receipt_image(receipt_id: int):
    row = g.db.execute(
        "SELECT filename FROM receipts WHERE id = ?", (receipt_id,)
    ).fetchone()
    if not row:
        return jsonify({"error": "not_found"}), 404
    cfg = current_app.config["CONFIG"]
    return send_from_directory(cfg.data_dir / "receipts", row["filename"])


@bp.get("/receipts/<int:receipt_id>/thumb")
def receipt_thumb(receipt_id: int):
    row = g.db.execute(
        "SELECT thumbnail FROM receipts WHERE id = ?", (receipt_id,)
    ).fetchone()
    if not row or not row["thumbnail"]:
        return jsonify({"error": "not_found"}), 404
    cfg = current_app.config["CONFIG"]
    return send_from_directory(cfg.data_dir / "receipts" / "thumbs", row["thumbnail"])
```

- [ ] **Step 4: Tests pass**

```bash
cd apps/api
uv run pytest tests/test_api_receipts.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Update batch_row.html to use thumbnail URL**

The template was already wired in Phase 1.9 (`<a href="/api/v1/receipts/{{ batch.receipt.id }}/thumb">`). No template change needed; commit just the route changes.

- [ ] **Step 6: Commit**

```bash
git add apps/api/redbull_api/routes/api.py apps/api/tests/test_api_receipts.py
git commit -m "feat(api): serve receipt image + thumbnail"
```

### Task 2.5: Manual live-test script

**Files:**
- Create: `apps/api/tests/manual/__init__.py` (empty)
- Create: `apps/api/tests/manual/test_receipt_live.py`
- Create: `apps/api/tests/fixtures/receipts/.gitkeep` (placeholder; you place a real receipt here yourself)

- [ ] **Step 1: Write the manual test script**

Create `apps/api/tests/manual/test_receipt_live.py`:

```python
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
```

- [ ] **Step 2: Create the fixture placeholder**

```bash
mkdir -p apps/api/tests/fixtures/receipts
touch apps/api/tests/fixtures/receipts/.gitkeep
```

Add to `apps/api/.gitignore` (create if absent):

```
tests/fixtures/receipts/*
!tests/fixtures/receipts/.gitkeep
.venv/
.data/
__pycache__/
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/manual/ apps/api/tests/fixtures/ apps/api/.gitignore
git commit -m "test(api): add opt-in live receipt parsing test"
```

---

## Phase 3 — Widget API mode

Goal: when `REDBULL_API_URL` is set, the widget polls the API instead of using its local count, renders per-type cans, and disables clicks.

### Task 3.1: Extend IRedBullService

**Files:**
- Modify: `apps/widget/Services/IRedBullService.cs`
- Modify: `apps/widget/Services/OfflineRedBullService.cs`

- [ ] **Step 1: Update the interface**

Replace `apps/widget/Services/IRedBullService.cs` with:

```csharp
namespace RedBullTracker.Services;

public interface IRedBullService
{
    int Count { get; }
    IReadOnlyDictionary<string, int> ByType { get; }
    bool IsReadOnly { get; }
    event EventHandler? CountChanged;
    Task AddCanAsync();
    Task RemoveCanAsync();
}
```

- [ ] **Step 2: Update OfflineRedBullService**

In `apps/widget/Services/OfflineRedBullService.cs`, find the existing class and update it to expose `ByType` based on the configured `canType` (passed via constructor):

```csharp
namespace RedBullTracker.Services;

public class OfflineRedBullService : IRedBullService
{
    private readonly SettingsService _settings;
    private readonly string _canType;
    private int _count;

    public int Count => _count;
    public bool IsReadOnly => false;
    public IReadOnlyDictionary<string, int> ByType
    {
        get
        {
            if (_count == 0)
                return new Dictionary<string, int>();
            return new Dictionary<string, int> { [_canType] = _count };
        }
    }

    public event EventHandler? CountChanged;

    public OfflineRedBullService(SettingsService settings)
    {
        _settings = settings;
        _canType = settings.Config.CanType ?? "default";
        _count = _settings.LoadCount();
    }

    public Task AddCanAsync()
    {
        _count++;
        _settings.SaveCount(_count);
        CountChanged?.Invoke(this, EventArgs.Empty);
        return Task.CompletedTask;
    }

    public Task RemoveCanAsync()
    {
        if (_count > 0)
        {
            _count--;
            _settings.SaveCount(_count);
            CountChanged?.Invoke(this, EventArgs.Empty);
        }
        return Task.CompletedTask;
    }
}
```

- [ ] **Step 3: Verify build**

Run: `dotnet build -p:Platform=x64`
Expected: `Build succeeded.` (will fail at widget render code referencing single-type — fix in Task 3.5).

If the build fails because `RedBullWidget` references the single-image fields, that's expected — leave it. Task 3.5 fixes it.

- [ ] **Step 4: Don't commit yet** — wait until widget rendering is updated to match.

### Task 3.2: Create test project

**Files:**
- Create: `apps/widget/Tests/RedBullTracker.Tests.csproj`
- Create: `apps/widget/Tests/Usings.cs`
- Modify: `RedBullTracker.sln` to include the test project

- [ ] **Step 1: Write the .csproj**

Create `apps/widget/Tests/RedBullTracker.Tests.csproj`:

```xml
<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <TargetFramework>net8.0-windows</TargetFramework>
    <Nullable>enable</Nullable>
    <IsPackable>false</IsPackable>
    <Platforms>x64</Platforms>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.10.0" />
    <PackageReference Include="xunit" Version="2.9.0" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.8.2" />
    <PackageReference Include="Moq" Version="4.20.70" />
  </ItemGroup>

  <ItemGroup>
    <ProjectReference Include="..\RedBullTracker.csproj" />
  </ItemGroup>

</Project>
```

- [ ] **Step 2: Write Usings.cs**

Create `apps/widget/Tests/Usings.cs`:

```csharp
global using Xunit;
```

- [ ] **Step 3: Add test project to solution**

```bash
dotnet sln RedBullTracker.sln add apps/widget/Tests/RedBullTracker.Tests.csproj
```

- [ ] **Step 4: Verify**

```bash
dotnet build apps/widget/Tests/RedBullTracker.Tests.csproj -p:Platform=x64
```

Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add apps/widget/Tests/ RedBullTracker.sln
git commit -m "test(widget): scaffold xunit test project"
```

### Task 3.3: ApiRedBullService

**Files:**
- Create: `apps/widget/Services/ApiRedBullService.cs`
- Create: `apps/widget/Models/StockResponse.cs`
- Create: `apps/widget/Tests/ApiRedBullServiceTests.cs`

- [ ] **Step 1: Write the response model**

Create `apps/widget/Models/StockResponse.cs`:

```csharp
using System.Text.Json.Serialization;

namespace RedBullTracker.Models;

public class StockResponse
{
    [JsonPropertyName("total")]
    public int Total { get; set; }

    [JsonPropertyName("by_type")]
    public Dictionary<string, int> ByType { get; set; } = new();

    [JsonPropertyName("updated_at")]
    public string? UpdatedAt { get; set; }
}
```

Also extend `apps/widget/AppJsonContext.cs` to include `StockResponse`. Find the existing `[JsonSerializable]` attributes and add:

```csharp
[JsonSerializable(typeof(StockResponse))]
```

- [ ] **Step 2: Write the tests**

Create `apps/widget/Tests/ApiRedBullServiceTests.cs`:

```csharp
using System.Net;
using System.Text;
using RedBullTracker.Services;

namespace RedBullTracker.Tests;

public class ApiRedBullServiceTests
{
    private class StubHandler : HttpMessageHandler
    {
        private readonly Queue<HttpResponseMessage> _responses;
        public int CallCount { get; private set; }

        public StubHandler(params HttpResponseMessage[] responses)
        {
            _responses = new Queue<HttpResponseMessage>(responses);
        }

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            CallCount++;
            return Task.FromResult(_responses.Dequeue());
        }
    }

    private static HttpResponseMessage Json(string body, HttpStatusCode status = HttpStatusCode.OK)
        => new(status) { Content = new StringContent(body, Encoding.UTF8, "application/json") };

    [Fact]
    public async Task RefreshAsync_PopulatesByType()
    {
        var handler = new StubHandler(Json("""{"total":3,"by_type":{"default":2,"sugarfree":1},"updated_at":null}"""));
        var http = new HttpClient(handler) { BaseAddress = new Uri("http://x") };
        var svc = new ApiRedBullService(http, "tok");

        await svc.RefreshAsync();

        Assert.Equal(3, svc.Count);
        Assert.Equal(2, svc.ByType["default"]);
        Assert.Equal(1, svc.ByType["sugarfree"]);
        Assert.True(svc.IsReadOnly);
        Assert.False(svc.IsStale);
    }

    [Fact]
    public async Task RefreshAsync_OnError_MarksStale()
    {
        var handler = new StubHandler(new HttpResponseMessage(HttpStatusCode.InternalServerError));
        var http = new HttpClient(handler) { BaseAddress = new Uri("http://x") };
        var svc = new ApiRedBullService(http, "tok");

        await svc.RefreshAsync();

        Assert.True(svc.IsStale);
        Assert.Equal(0, svc.Count);  // no cached state yet
    }

    [Fact]
    public async Task RefreshAsync_AfterErrorThenSuccess_ClearsStale()
    {
        var handler = new StubHandler(
            new HttpResponseMessage(HttpStatusCode.InternalServerError),
            Json("""{"total":1,"by_type":{"default":1},"updated_at":null}""")
        );
        var http = new HttpClient(handler) { BaseAddress = new Uri("http://x") };
        var svc = new ApiRedBullService(http, "tok");

        await svc.RefreshAsync();
        Assert.True(svc.IsStale);

        await svc.RefreshAsync();
        Assert.False(svc.IsStale);
        Assert.Equal(1, svc.Count);
    }

    [Fact]
    public async Task RefreshAsync_NoChange_DoesNotFireEvent()
    {
        var handler = new StubHandler(
            Json("""{"total":2,"by_type":{"default":2},"updated_at":null}"""),
            Json("""{"total":2,"by_type":{"default":2},"updated_at":null}""")
        );
        var http = new HttpClient(handler) { BaseAddress = new Uri("http://x") };
        var svc = new ApiRedBullService(http, "tok");

        int events = 0;
        svc.CountChanged += (_, _) => events++;

        await svc.RefreshAsync();  // first refresh fires (state went from empty to populated)
        await svc.RefreshAsync();  // second refresh shouldn't fire (identical state)

        Assert.Equal(1, events);
    }

    [Fact]
    public async Task AddCanAsync_Throws_BecauseReadOnly()
    {
        var http = new HttpClient(new StubHandler()) { BaseAddress = new Uri("http://x") };
        var svc = new ApiRedBullService(http, "tok");
        await Assert.ThrowsAsync<InvalidOperationException>(() => svc.AddCanAsync());
    }

    [Fact]
    public async Task RefreshAsync_SendsBearerHeader()
    {
        AuthenticationHeaderValue? captured = null;
        var handler = new CapturingHandler(req => captured = req.Headers.Authorization,
            Json("""{"total":0,"by_type":{},"updated_at":null}"""));
        var http = new HttpClient(handler) { BaseAddress = new Uri("http://x") };
        var svc = new ApiRedBullService(http, "my-token");

        await svc.RefreshAsync();

        Assert.NotNull(captured);
        Assert.Equal("Bearer", captured!.Scheme);
        Assert.Equal("my-token", captured.Parameter);
    }

    private class CapturingHandler : HttpMessageHandler
    {
        private readonly Action<HttpRequestMessage> _capture;
        private readonly HttpResponseMessage _response;

        public CapturingHandler(Action<HttpRequestMessage> capture, HttpResponseMessage response)
        {
            _capture = capture;
            _response = response;
        }

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            _capture(request);
            return Task.FromResult(_response);
        }
    }
}
```

Add `using System.Net.Http.Headers;` to the top of the test file.

- [ ] **Step 3: Run tests, confirm fail**

```bash
dotnet test apps/widget/Tests/RedBullTracker.Tests.csproj -p:Platform=x64
```

Expected: build error — `ApiRedBullService` doesn't exist.

- [ ] **Step 4: Implement ApiRedBullService**

Create `apps/widget/Services/ApiRedBullService.cs`:

```csharp
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using RedBullTracker.Models;

namespace RedBullTracker.Services;

public class ApiRedBullService : IRedBullService, IDisposable
{
    private static readonly TimeSpan PollInterval = TimeSpan.FromSeconds(5);
    private static readonly TimeSpan HttpTimeout = TimeSpan.FromSeconds(3);

    private readonly HttpClient _http;
    private readonly string _token;
    private System.Threading.Timer? _timer;
    private Dictionary<string, int> _byType = new();
    private int _count;
    private bool _isStale;
    private bool _disposed;

    public int Count => _count;
    public IReadOnlyDictionary<string, int> ByType => _byType;
    public bool IsReadOnly => true;
    public bool IsStale => _isStale;
    public event EventHandler? CountChanged;

    public ApiRedBullService(HttpClient http, string token)
    {
        _http = http;
        _token = token;
        _http.Timeout = HttpTimeout;
    }

    public void StartPolling()
    {
        _timer = new System.Threading.Timer(
            async _ => await RefreshAsync(),
            null,
            TimeSpan.Zero,
            PollInterval);
    }

    public async Task RefreshAsync()
    {
        try
        {
            using var req = new HttpRequestMessage(HttpMethod.Get, "/api/v1/stock");
            req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _token);
            using var resp = await _http.SendAsync(req).ConfigureAwait(false);

            if (!resp.IsSuccessStatusCode)
            {
                MarkStale();
                return;
            }

            var stream = await resp.Content.ReadAsStreamAsync().ConfigureAwait(false);
            var stock = await JsonSerializer.DeserializeAsync(stream, AppJsonContext.Default.StockResponse).ConfigureAwait(false);
            if (stock is null)
            {
                MarkStale();
                return;
            }

            var newByType = stock.ByType ?? new Dictionary<string, int>();
            var newTotal = stock.Total;
            var changed = newTotal != _count || !DictEquals(newByType, _byType) || _isStale;

            _byType = newByType;
            _count = newTotal;
            _isStale = false;

            if (changed)
                CountChanged?.Invoke(this, EventArgs.Empty);
        }
        catch
        {
            MarkStale();
        }
    }

    private void MarkStale()
    {
        if (!_isStale)
        {
            _isStale = true;
            CountChanged?.Invoke(this, EventArgs.Empty);
        }
    }

    private static bool DictEquals(IDictionary<string, int> a, IDictionary<string, int> b)
    {
        if (a.Count != b.Count) return false;
        foreach (var kv in a)
            if (!b.TryGetValue(kv.Key, out var v) || v != kv.Value) return false;
        return true;
    }

    public Task AddCanAsync() => throw new InvalidOperationException("Widget is in read-only API mode");
    public Task RemoveCanAsync() => throw new InvalidOperationException("Widget is in read-only API mode");

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _timer?.Dispose();
        _http.Dispose();
    }
}
```

- [ ] **Step 5: Tests pass**

```bash
dotnet test apps/widget/Tests/RedBullTracker.Tests.csproj -p:Platform=x64
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/widget/Services/ApiRedBullService.cs apps/widget/Models/StockResponse.cs apps/widget/Services/IRedBullService.cs apps/widget/Services/OfflineRedBullService.cs apps/widget/AppJsonContext.cs apps/widget/Tests/ApiRedBullServiceTests.cs
git commit -m "feat(widget): ApiRedBullService with polling + stale tracking"
```

### Task 3.4: RedBullServiceFactory

**Files:**
- Create: `apps/widget/Services/RedBullServiceFactory.cs`
- Create: `apps/widget/Tests/RedBullServiceFactoryTests.cs`

- [ ] **Step 1: Write the tests**

Create `apps/widget/Tests/RedBullServiceFactoryTests.cs`:

```csharp
using RedBullTracker.Services;

namespace RedBullTracker.Tests;

public class RedBullServiceFactoryTests
{
    [Fact]
    public void Create_NoApiUrl_ReturnsOffline()
    {
        Environment.SetEnvironmentVariable("REDBULL_API_URL", null);
        Environment.SetEnvironmentVariable("REDBULL_API_TOKEN", null);

        var settings = new SettingsService();
        using var svc = RedBullServiceFactory.Create(settings);

        Assert.IsType<OfflineRedBullService>(svc);
        Assert.False(svc.IsReadOnly);
    }

    [Fact]
    public void Create_WithApiUrlButNoToken_Throws()
    {
        Environment.SetEnvironmentVariable("REDBULL_API_URL", "http://localhost:5000");
        Environment.SetEnvironmentVariable("REDBULL_API_TOKEN", null);

        var settings = new SettingsService();
        Assert.Throws<InvalidOperationException>(() => RedBullServiceFactory.Create(settings));

        Environment.SetEnvironmentVariable("REDBULL_API_URL", null);
    }

    [Fact]
    public void Create_WithApiUrlAndToken_ReturnsApi()
    {
        Environment.SetEnvironmentVariable("REDBULL_API_URL", "http://localhost:5000");
        Environment.SetEnvironmentVariable("REDBULL_API_TOKEN", "tok");

        var settings = new SettingsService();
        using var svc = RedBullServiceFactory.Create(settings);

        Assert.IsType<ApiRedBullService>(svc);
        Assert.True(svc.IsReadOnly);

        Environment.SetEnvironmentVariable("REDBULL_API_URL", null);
        Environment.SetEnvironmentVariable("REDBULL_API_TOKEN", null);
    }
}
```

- [ ] **Step 2: Run, confirm fail**

```bash
dotnet test apps/widget/Tests/RedBullTracker.Tests.csproj -p:Platform=x64
```

Expected: build error.

- [ ] **Step 3: Implement the factory**

Create `apps/widget/Services/RedBullServiceFactory.cs`:

```csharp
namespace RedBullTracker.Services;

public static class RedBullServiceFactory
{
    public static IRedBullService Create(SettingsService settings)
    {
        var apiUrl = Environment.GetEnvironmentVariable("REDBULL_API_URL");
        var apiToken = Environment.GetEnvironmentVariable("REDBULL_API_TOKEN");

        if (string.IsNullOrEmpty(apiUrl))
            return new OfflineRedBullService(settings);

        if (string.IsNullOrEmpty(apiToken))
            throw new InvalidOperationException(
                "REDBULL_API_URL is set but REDBULL_API_TOKEN is missing");

        var handler = new SocketsHttpHandler
        {
            PooledConnectionLifetime = TimeSpan.FromMinutes(10)
        };
        var http = new HttpClient(handler) { BaseAddress = new Uri(apiUrl) };
        var svc = new ApiRedBullService(http, apiToken);
        svc.StartPolling();
        return svc;
    }
}
```

- [ ] **Step 4: Tests pass**

```bash
dotnet test apps/widget/Tests/RedBullTracker.Tests.csproj -p:Platform=x64
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/widget/Services/RedBullServiceFactory.cs apps/widget/Tests/RedBullServiceFactoryTests.cs
git commit -m "feat(widget): RedBullServiceFactory env-var-driven mode selection"
```

### Task 3.5: Update widget rendering for multi-type + click gating

**Files:**
- Modify: `apps/widget/Widget/RedBullWidget.cs`
- Modify: `apps/widget/Program.cs`
- Add asset: `apps/widget/Assets/redbull-generic.png`
- Modify: `apps/widget/RedBullTracker.csproj` (embed generic asset)

- [ ] **Step 1: Add the generic icon asset**

You need to produce `apps/widget/Assets/redbull-generic.png` — a stylized generic Red Bull can with a `?` overlay or similar fallback look. Use the same 12x24 dimensions and visual style as `redbull-default.png`. Drop the file into `apps/widget/Assets/redbull-generic.png`.

If you don't have an image editor handy, copy `apps/widget/Assets/redbull-default.png` to `redbull-generic.png` as a temporary stand-in:

```bash
copy apps\widget\Assets\redbull-default.png apps\widget\Assets\redbull-generic.png
```

- [ ] **Step 2: Embed the asset in the csproj**

In `apps/widget/RedBullTracker.csproj`, find the `<ItemGroup>` containing existing `<EmbeddedResource Include="Assets\redbull-default.png" />` lines and add:

```xml
    <EmbeddedResource Include="Assets\redbull-generic.png" />
```

- [ ] **Step 3: Rewrite RedBullWidget.cs**

Replace `apps/widget/Widget/RedBullWidget.cs` with:

```csharp
using RedBullTracker.Services;
using TaskbarWidget;
using TaskbarWidget.Rendering;

namespace RedBullTracker.Widget;

public class RedBullWidget : IDisposable
{
    private const int CanWidthDip = 12;
    private const int CanHeightDip = 24;
    private const int CanSpacing = 2;

    private readonly IRedBullService _service;
    private TaskbarWidget.Widget? _widget;
    private readonly Dictionary<string, WidgetImage> _icons = new();
    private WidgetImage? _genericIcon;
    private WidgetImage? _emptyIcon;
    private bool _disposed;

    public RedBullWidget(IRedBullService service)
    {
        _service = service;
        _service.CountChanged += OnCountChanged;
    }

    public void Initialize()
    {
        LoadImages();

        _widget = new TaskbarWidget.Widget("RedBull", render: ctx =>
        {
            ctx.Panel(p =>
            {
                var byType = _service.ByType;
                int total = _service.Count;
                bool stale = (_service as ApiRedBullService)?.IsStale ?? false;

                p.Horizontal(CanSpacing, h =>
                {
                    if (total == 0)
                    {
                        h.DrawImage(_emptyIcon!, widthDip: CanWidthDip, heightDip: CanHeightDip);
                    }
                    else
                    {
                        // Stable ordering across renders
                        foreach (var (type, count) in byType.OrderBy(kv => kv.Key))
                        {
                            var icon = GetIcon(type);
                            for (int i = 0; i < count; i++)
                                h.DrawImage(icon, widthDip: CanWidthDip, heightDip: CanHeightDip);
                        }
                    }
                });

                if (!_service.IsReadOnly)
                {
                    p.OnClick(() => _ = _service.RemoveCanAsync());
                    p.OnRightClick(() => _ = _service.AddCanAsync());
                }

                p.Tooltip(BuildTooltip(byType, total, stale));
            });
        });

        _widget.Show();
    }

    private string BuildTooltip(IReadOnlyDictionary<string, int> byType, int total, bool stale)
    {
        if (_service.IsReadOnly)
        {
            if (total == 0) return "Red Bulls: 0\nSynced from API" + (stale ? " (stale)" : "");
            var breakdown = string.Join(", ", byType.OrderBy(kv => kv.Key).Select(kv => $"{kv.Value} {kv.Key}"));
            return $"Red Bulls: {breakdown} ({total} total)\nSynced from API" + (stale ? " (stale)" : "");
        }
        return $"Red Bulls: {total}\nLeft-click: Remove | Right-click: Add";
    }

    private WidgetImage GetIcon(string type)
    {
        if (_icons.TryGetValue(type, out var icon))
            return icon;
        return _genericIcon!;
    }

    private void LoadImages()
    {
        var asm = typeof(RedBullWidget).Assembly;
        _icons["default"] = WidgetImage.FromResource(asm, "RedBullTracker.Assets.redbull-default.png");
        _icons["sugarfree"] = WidgetImage.FromResource(asm, "RedBullTracker.Assets.redbull-sugarfree.png");
        _genericIcon = WidgetImage.FromResource(asm, "RedBullTracker.Assets.redbull-generic.png");
        _emptyIcon = WidgetImage.FromResource(asm, "RedBullTracker.Assets.redbull-empty.png");
    }

    private void OnCountChanged(object? sender, EventArgs e)
    {
        _widget?.Invalidate();
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _service.CountChanged -= OnCountChanged;
        _widget?.Dispose();
        (_service as IDisposable)?.Dispose();
    }
}
```

Note: the existing constructor took `string canType`. The new constructor doesn't — the service now owns type information. This is intentional.

- [ ] **Step 4: Update Program.cs**

Replace `apps/widget/Program.cs` with:

```csharp
using RedBullTracker.Services;
using RedBullTracker.Widget;

namespace RedBullTracker;

public static class Program
{
    [STAThread]
    public static void Main(string[] args)
    {
        var settings = new SettingsService();
        var service = RedBullServiceFactory.Create(settings);

        StartupService.SyncWithConfig(settings.Config.StartWithWindows);

        var widget = new RedBullWidget(service);
        widget.Initialize();

        TaskbarWidget.Widget.RunMessageLoop();
    }
}
```

- [ ] **Step 5: Build and verify**

```bash
dotnet build -p:Platform=x64
```

Expected: `Build succeeded.`

- [ ] **Step 6: Run tests**

```bash
dotnet test apps/widget/Tests/RedBullTracker.Tests.csproj -p:Platform=x64
```

Expected: all tests pass.

- [ ] **Step 7: Smoke test — offline mode**

```bash
dotnet run --project apps/widget/RedBullTracker.csproj -p:Platform=x64
```

Expected: widget runs identically to before (offline mode). Left/right click work.

Stop with Ctrl+C.

- [ ] **Step 8: Smoke test — API mode**

In one terminal, run the API:

```bash
cd apps/api
API_TOKEN=devtoken COOKIE_SECRET=devsecret ANTHROPIC_API_KEY=sk DATA_DIR=./.data \
  uv run flask --app redbull_api.app:create_app run
```

In another:

```powershell
$env:REDBULL_API_URL="http://127.0.0.1:5000"
$env:REDBULL_API_TOKEN="devtoken"
dotnet run --project apps/widget/RedBullTracker.csproj -p:Platform=x64
```

Use the web UI at `http://127.0.0.1:5000/` to add a manual batch (`default`, delta `3`). Within 5s, the widget should show 3 cans. Clicks should do nothing. Tooltip should say "Synced from API".

Stop both.

- [ ] **Step 9: Commit**

```bash
git add apps/widget/Widget/RedBullWidget.cs apps/widget/Program.cs apps/widget/RedBullTracker.csproj apps/widget/Assets/redbull-generic.png
git commit -m "feat(widget): multi-type rendering + api-mode click gating"
```

---

## Phase 4 — Railway deploy

Goal: deploy the API to Railway via `railway.toml`.

### Task 4.1: Write railway.toml

**Files:**
- Create: `railway.toml`

- [ ] **Step 1: Write the config**

Create `railway.toml` at the repo root:

```toml
[build]
builder = "NIXPACKS"
buildCommand = "cd apps/api && uv sync --frozen"

[deploy]
startCommand = "cd apps/api && uv run gunicorn --bind 0.0.0.0:$PORT --workers 2 --access-logfile - 'redbull_api.app:create_app()'"
healthcheckPath = "/api/v1/health"
healthcheckTimeout = 10
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5

[[deploy.volumes]]
mountPath = "/data"
```

- [ ] **Step 2: Add a nixpacks.toml for Python version pinning**

Create `apps/api/nixpacks.toml`:

```toml
[phases.setup]
nixPkgs = ["python312", "gcc"]

[phases.install]
cmds = ["pip install uv", "uv sync --frozen"]
```

- [ ] **Step 3: Commit**

```bash
git add railway.toml apps/api/nixpacks.toml
git commit -m "build: add railway + nixpacks config"
```

### Task 4.2: Write deploy docs

**Files:**
- Create: `docs/deploy-railway.md`

- [ ] **Step 1: Write the doc**

Create `docs/deploy-railway.md`:

```markdown
# Deploying the API to Railway

## One-time setup

1. Install the CLI and log in:
   ```bash
   npm i -g @railway/cli
   railway login
   ```

2. Create a new project linked to this repo:
   ```bash
   railway init
   railway link
   ```

3. Add a volume mounted at `/data`:
   - In the Railway dashboard → Service → Volumes → "Add Volume" → mount path `/data`.
   - (CLI equivalent: `railway volume add --mount-path /data`)

4. Set environment variables. Generate strong secrets:
   ```bash
   railway variables set \
     API_TOKEN=$(openssl rand -hex 32) \
     COOKIE_SECRET=$(openssl rand -hex 32) \
     ANTHROPIC_API_KEY=sk-ant-...
   ```

5. Deploy:
   ```bash
   railway up
   ```

6. (Optional) Add a custom domain:
   - Dashboard → Service → Settings → Networking → "Custom Domain"
   - Railway provides HTTPS via Let's Encrypt automatically.

## Verifying the deploy

```bash
RAILWAY_URL=$(railway domain)   # or copy from dashboard
curl "$RAILWAY_URL/api/v1/health"
# → {"ok": true, "db": "ok"}
```

Set the widget env vars locally:

```powershell
$env:REDBULL_API_URL = "https://your-railway-app.up.railway.app"
$env:REDBULL_API_TOKEN = "<the API_TOKEN you set above>"
```

Then launch the widget.

## Updating env vars later

```bash
railway variables set API_TOKEN=<new-token>
```

The service restarts automatically.

## Backups

Railway volumes aren't backed up automatically. For periodic SQLite backups:

```bash
railway volume export <volume-id> -o ./backup-$(date +%F).tar.gz
```

For automated backups, consider adding a `litestream` sidecar later (out of scope for the initial launch).
```

- [ ] **Step 2: Commit**

```bash
git add docs/deploy-railway.md
git commit -m "docs: railway deployment guide"
```

### Task 4.3: First deploy + smoke test

**Files:** none — this is an operational task.

- [ ] **Step 1: Deploy from CLI**

```bash
railway login          # if not already logged in
railway link           # link this repo to your Railway project
railway up
```

Expected: Railway builds via Nixpacks, deploys the API. CLI streams logs.

- [ ] **Step 2: Set the env vars**

```bash
railway variables set API_TOKEN=$(openssl rand -hex 32)
railway variables set COOKIE_SECRET=$(openssl rand -hex 32)
railway variables set ANTHROPIC_API_KEY=sk-ant-<your-real-key>
```

The service will redeploy.

- [ ] **Step 3: Verify health**

```bash
curl https://<your-app>.up.railway.app/api/v1/health
```

Expected: `{"ok": true, "db": "ok"}`.

- [ ] **Step 4: Smoke test via browser**

Visit `https://<your-app>.up.railway.app/` → login with the `API_TOKEN` value → add a manual batch → verify it appears in the log.

Upload a real receipt → verify Claude parses it and the log shows it with a thumbnail.

- [ ] **Step 5: Smoke test the widget against production**

```powershell
$env:REDBULL_API_URL = "https://<your-app>.up.railway.app"
$env:REDBULL_API_TOKEN = "<the token from step 2>"
dotnet run --project apps/widget/RedBullTracker.csproj -p:Platform=x64
```

Expected: widget shows current stock from production, polls every 5s, no clicks active.

- [ ] **Step 6: Tag a release**

```bash
git tag v2.1.0  # adjust to your versioning
git push origin v2.1.0
```

(The existing release workflow builds the widget exe on tag push.)

---

## Self-review notes

The plan covers every requirement in the design spec:

- ✅ Monorepo restructure (Phase 0)
- ✅ Per-type stock tracking with denormalized `stock` table (Phase 1, Task 1.3, 1.4)
- ✅ Bearer + cookie auth (Phase 1, Task 1.5, 1.6)
- ✅ `/health`, `/stock`, `/adjust`, `/batches`, `DELETE /batches/{id}` (Phase 1, Task 1.6, 1.7)
- ✅ Web UI with HTMX (Phase 1, Task 1.8, 1.9, 1.10)
- ✅ Receipt parsing with Haiku primary + Sonnet fallback (Phase 2, Task 2.2)
- ✅ `POST /receipts` with image storage + thumbnail (Phase 2, Task 2.1, 2.3)
- ✅ `confidence: none` creates batch with zero items (Phase 2, Task 2.3, test_upload_none_confidence_still_creates_batch_returns_422)
- ✅ Image serving routes (Phase 2, Task 2.4)
- ✅ `ApiRedBullService` polling with stale-flag (Phase 3, Task 3.3)
- ✅ `RedBullServiceFactory` env-var-driven (Phase 3, Task 3.4)
- ✅ Multi-icon rendering + click gating (Phase 3, Task 3.5)
- ✅ Generic fallback icon (Phase 3, Task 3.5)
- ✅ Railway deploy via Nixpacks, no Docker (Phase 4)
- ✅ CLI deploy path (Phase 4, Task 4.2)

Type consistency: `IRedBullService.ByType` is `IReadOnlyDictionary<string, int>` everywhere it appears. `ParseResult` fields match between `receipts.py` and the test file. `Config` fields match between `config.py` and `app.py`.
