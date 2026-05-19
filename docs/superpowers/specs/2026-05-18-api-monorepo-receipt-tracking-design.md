# Design: API monorepo + receipt-driven Red Bull tracking

**Date:** 2026-05-18
**Status:** Draft, pending user review

## Summary

Restructure the repo into a monorepo containing both the existing Windows taskbar widget and a new Flask API. The API stores per-type Red Bull stock in SQLite, exposes a small web UI for manual adjustment, and accepts receipt photos which are parsed by Claude (Haiku-first, Sonnet fallback) to auto-increment the right type. The widget gains an "API mode": when `REDBULL_API_URL` is set, it disables clicks and renders cans purely from the API. Deployment target is Railway (no Docker).

## Goals

- Track Red Bull stock by **type** (default, sugarfree, and any open-ended type Claude detects on a receipt), not just a single total.
- Eliminate manual click-tracking when a receipt is available — drop in a photo, get the right count.
- Keep the existing offline widget behavior available as a fallback (env-var-gated mode switch).
- Single-user, internet-exposed, shared-token auth.

## Non-goals

- Multi-user accounts, roles, OAuth.
- Can-size tracking (250ml / 355ml / 473ml — ignored).
- Caffeine / calorie aggregation.
- Real-time push to the widget (5s polling is sufficient).
- Mobile app.
- Backwards compatibility with old config layout — we restructure cleanly.

---

## 1. Repo layout (monorepo)

```
redbull-tracker/
├── apps/
│   ├── widget/                # moved from src/RedBullTracker/
│   │   ├── RedBullTracker.csproj
│   │   ├── Assets/
│   │   ├── Models/
│   │   ├── Services/
│   │   └── Widget/
│   └── api/                   # new
│       ├── pyproject.toml
│       ├── redbull_api/
│       │   ├── __init__.py
│       │   ├── app.py         # Flask app factory
│       │   ├── auth.py        # token + cookie middleware
│       │   ├── db.py          # SQLite schema + helpers
│       │   ├── models.py      # dataclasses for Batch/Stock
│       │   ├── receipts.py    # Claude vision call
│       │   ├── routes/
│       │   │   ├── api.py     # JSON endpoints
│       │   │   └── ui.py      # HTML routes (HTMX)
│       │   ├── templates/
│       │   └── static/
│       └── tests/
├── lib/
│   └── taskbar-widget/        # submodule, unchanged
├── docs/
├── .github/workflows/
│   ├── ci-widget.yml          # builds the .NET widget
│   ├── ci-api.yml             # lints + tests the Flask api
│   └── release.yml            # widget release on tags (unchanged)
├── railway.toml               # Railway deploy config (Nixpacks)
├── CHANGELOG.md
├── CLAUDE.md                  # updated to describe monorepo
└── RedBullTracker.sln         # path updated to apps/widget/
```

The `api` development branch (per user request) is used during initial implementation; merged to `main` when complete. All ongoing work lives on `main` thereafter.

---

## 2. Data model (SQLite)

DB lives at `${DATA_DIR}/redbull.db`, where `DATA_DIR` defaults to `/data` (the Railway volume mount).

```sql
-- Stock per type. Row exists only if count ever non-zero.
CREATE TABLE stock (
    type        TEXT PRIMARY KEY,           -- 'default', 'sugarfree', 'tropical', ...
    count       INTEGER NOT NULL CHECK (count >= 0),
    updated_at  TEXT NOT NULL               -- ISO 8601
);

-- Each batch is one action: a receipt scan or a manual +/- adjustment.
CREATE TABLE batches (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT NOT NULL CHECK (source IN ('receipt', 'manual')),
    created_at   TEXT NOT NULL,
    note         TEXT,                      -- optional, e.g. "Tesco Praha 21.04"
    receipt_id   INTEGER REFERENCES receipts(id) ON DELETE SET NULL
);

-- Line items inside a batch: which types and how many (signed; negative = removal).
CREATE TABLE batch_items (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id  INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    type      TEXT NOT NULL,
    delta     INTEGER NOT NULL               -- +2 means added 2; -1 means removed 1
);

-- Receipts: image file + Claude's raw response, for audit/debug.
CREATE TABLE receipts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT NOT NULL,            -- relative to /data/receipts/
    thumbnail       TEXT,                     -- relative to /data/receipts/thumbs/
    uploaded_at     TEXT NOT NULL,
    model_used      TEXT NOT NULL,            -- 'claude-haiku-4-5', 'claude-sonnet-4-6'
    raw_response    TEXT NOT NULL,            -- JSON of Claude's tool-use input
    confidence      TEXT NOT NULL             -- 'high' | 'low' | 'none'
);

CREATE INDEX idx_batches_created_at ON batches(created_at DESC);
CREATE INDEX idx_batch_items_batch  ON batch_items(batch_id);
```

### Key choices

- **`stock` is denormalized.** Source of truth is `SUM(batch_items.delta) GROUP BY type`, but `stock` is maintained transactionally on every batch insert/delete. Keeps the widget poll endpoint a single row read. A reconcile-on-startup job recomputes from `batch_items` and corrects drift.
- **Deleting a batch** cascades to `batch_items` and triggers a stock recompute for affected types. Receipt image file and `receipts` row are retained after batch delete (kept for re-processing). No automatic retention cleanup initially — revisit if `/data` storage becomes a concern.
- **Open-ended types.** No `types` table. Any string Claude returns gets a `stock` row when first seen. Widget renders unknown types with a fallback icon.

---

## 3. API surface

All JSON, under `/api/v1/`. Auth via `Authorization: Bearer <API_TOKEN>` header (widget) or signed session cookie (web UI). Both validate against the same `API_TOKEN`.

```
GET    /api/v1/stock
       → { "total": 7, "by_type": { "default": 4, "sugarfree": 3 }, "updated_at": "..." }

POST   /api/v1/adjust                          # manual +/- one type
       body: { "type": "sugarfree", "delta": -1, "note": "optional" }
       → 200 { "batch_id": 42, "stock": { ... } }

POST   /api/v1/receipts                        # multipart: image=<file>
       → 200 { "batch_id": 43, "receipt_id": 17, "items": [...], "confidence": "high"|"low", "stock": { ... } }
       → 422 { "error": "no_redbulls_found", "batch_id": 44, "receipt_id": 18, "confidence": "none" }
       # 422 still creates a batch (with zero items) so the failed receipt appears in the log

GET    /api/v1/batches?limit=50                # activity log
       → { "batches": [ { "id":43, "source":"receipt", "created_at":"...",
                          "items":[{"type":"sugarfree","delta":2}],
                          "receipt": { "id":17, "thumbnail_url":"/receipts/17/thumb" } }, ... ] }

DELETE /api/v1/batches/{id}                    # undo a batch
       → 200 { "stock": { ... } }

GET    /api/v1/receipts/{id}/image             # serves full image (auth required)
GET    /api/v1/receipts/{id}/thumb             # serves thumbnail

GET    /api/v1/health                          # liveness, no auth
       → { "ok": true, "db": "ok" }
```

### Web UI (separate, HTML/HTMX)

```
GET    /                  → dashboard: stock + activity log + upload form + manual adjust
GET    /login             → token entry form
POST   /login             → sets signed cookie, redirects to /
POST   /logout            → clears cookie
```

HTMX endpoints reuse the same `/api/v1/*` paths via content negotiation (`Accept: text/html` returns an HTML fragment), so we don't double-implement business logic.

### Widget polling

`GET /api/v1/stock` every **5 seconds**. Single-row read, no need for SSE/long-poll at this volume.

---

## 4. Receipt parsing flow

```
[upload]  POST /api/v1/receipts (multipart)
    │
    ▼
[save]    image → /data/receipts/<uuid>.<ext>
          200px thumbnail → /data/receipts/thumbs/<uuid>.jpg
    │
    ▼
[claude]  call_haiku(image_bytes) → tool-use response
          model: claude-haiku-4-5
          system: cached prompt (extract Red Bull purchases)
          tool:   record_redbulls({ items, confidence })
    │
    ├── confidence == "high"  → proceed with items
    ├── confidence == "low"   → retry with claude-sonnet-4-6
    └── confidence == "none"  → proceed with empty items (still creates batch)
    │
    ▼
[persist] BEGIN TRANSACTION
            INSERT receipts
            INSERT batches (source='receipt', receipt_id=...)
            INSERT batch_items  -- zero rows if confidence == "none"
            UPSERT stock per type  -- no-op if no items
          COMMIT
    │
    ▼
[return]  confidence == "none" → 422 { error, batch_id, receipt_id, confidence }
          else                 → 200 { batch_id, receipt_id, items, confidence, stock }
```

### Tool schema

```python
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
                            "description": "Red Bull variant: 'default' for regular, "
                                           "'sugarfree' for sugar-free/zero, or another "
                                           "lowercase keyword (e.g. 'tropical', 'watermelon', "
                                           "'peach') if clearly identifiable. Default to 'default' "
                                           "if the type is ambiguous."
                        },
                        "count": {"type": "integer", "minimum": 1}
                    },
                    "required": ["type", "count"]
                }
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "low", "none"],
                "description": "high: receipt clearly shows Red Bull lines with counts. "
                               "low: text is unclear but you made a best guess. "
                               "none: no Red Bull purchases visible."
            }
        },
        "required": ["items", "confidence"]
    }
}
```

### System prompt (cached)

```
You are a receipt parser specialized in identifying Red Bull energy drink purchases.

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
```

### Call shape

```python
resp = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=1024,
    system=[{"type": "text", "text": SYSTEM_PROMPT,
             "cache_control": {"type": "ephemeral"}}],
    tools=[RECORD_TOOL],
    tool_choice={"type": "tool", "name": "record_redbulls"},
    thinking={"type": "adaptive"},
    messages=[{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64",
                                     "media_type": "image/jpeg",
                                     "data": img_b64}},
        {"type": "text", "text": "Parse this receipt."}
    ]}]
)
items = next(b.input for b in resp.content if b.type == "tool_use")
```

Forced tool use eliminates JSON-parse fallback paths. Adaptive thinking lets Haiku reason about ambiguous receipts without budget tuning. Sonnet retry uses identical request shape with `model="claude-sonnet-4-6"`. The raw `resp.content[0].input` is stored in `receipts.raw_response` for debugging.

---

## 5. Widget changes (API client mode)

Widget runs in **one of two mutually exclusive modes**, selected at startup by the `REDBULL_API_URL` env var:

```
REDBULL_API_URL unset  →  OFFLINE MODE  (today's behavior)
                          • left-click removes a can
                          • right-click adds a can
                          • count persists to %LOCALAPPDATA%\count.txt
                          • single canType from config.json

REDBULL_API_URL set    →  API MODE
                          • no clicks (read-only)
                          • polls GET /api/v1/stock every 5s
                          • renders mixed-type cans (default + sugarfree + ...)
                          • tooltip shows per-type breakdown
                          • on poll failure: show last-known cans dimmed
```

### New env vars

| Var                 | Required in API mode | Notes                                       |
| ------------------- | -------------------- | ------------------------------------------- |
| `REDBULL_API_URL`   | yes                  | e.g. `https://redbull.mydomain.com`         |
| `REDBULL_API_TOKEN` | yes                  | sent as `Authorization: Bearer <token>`     |

### Service / DI changes

```
apps/widget/Services/
├── IRedBullService.cs               # extended interface (below)
├── OfflineRedBullService.cs         # unchanged behavior
├── ApiRedBullService.cs             # new — polls API
└── RedBullServiceFactory.cs         # new — picks impl from env
```

```csharp
public interface IRedBullService {
    int Count { get; }                              // total
    IReadOnlyDictionary<string, int> ByType { get; } // new: per-type breakdown
    bool IsReadOnly { get; }                        // new: true in API mode
    event EventHandler? CountChanged;
    Task AddCanAsync();                             // throws if IsReadOnly
    Task RemoveCanAsync();                          // throws if IsReadOnly
}
```

`OfflineRedBullService.ByType` returns a single-entry dict keyed by the configured `canType`.

### Render changes

```csharp
foreach (var (type, n) in service.ByType.OrderBy(kv => kv.Key))
    for (int i = 0; i < n; i++)
        h.DrawImage(GetIcon(type), ...);   // GetIcon falls back to default

if (!service.IsReadOnly) {
    p.OnClick(() => _ = service.RemoveCanAsync());
    p.OnRightClick(() => _ = service.AddCanAsync());
}
```

Tooltip:
- API mode: `"Red Bulls: 4 default, 2 sugarfree (6 total)\nSynced from API"`
- Offline mode: `"Red Bulls: 6\nLeft-click: Remove | Right-click: Add"`

### Polling

`ApiRedBullService` uses a single `System.Threading.Timer` firing every 5s. HTTP GET with 3s timeout, 1 retry on transient failure. On success, diff against cached state and fire `CountChanged` only if changed (no event spam). On failure, keep cached state and flip an `IsStale` flag the widget uses to dim icons.

`HttpClient` configured with `SocketsHttpHandler` for connection reuse — no per-poll handshake overhead.

### Icon fallback for unknown types

`Assets/redbull-generic.png` (stylized question-mark can) is added. `GetIcon(type)`:
- `"default"` → `redbull-default.png`
- `"sugarfree"` → `redbull-sugarfree.png`
- anything else → `redbull-generic.png`

Future named types ship dedicated icons by extending the lookup map.

---

## 6. Auth

### Server-side env vars (required, no defaults)

```
API_TOKEN          shared bearer token (suggest: openssl rand -hex 32)
COOKIE_SECRET      cookie signing key   (suggest: openssl rand -hex 32)
ANTHROPIC_API_KEY  Anthropic API key
```

Server refuses to start if `API_TOKEN` or `COOKIE_SECRET` are missing — loud failure, no insecure default.

### Bearer token (widget + raw API)

Every `/api/v1/*` request (except `/api/v1/health`) must carry `Authorization: Bearer <token>`. A Flask `before_request` handler compares against `API_TOKEN` using `hmac.compare_digest` (constant-time). Failure → 401, no body content.

### Cookie session (web UI)

```
GET  /login   → form with single password field
POST /login   → if form value == API_TOKEN, set signed cookie, redirect to /
                else show error
POST /logout  → clear cookie, redirect to /login
```

Cookie:
- Name: `redbull_session`
- Value: `itsdangerous.URLSafeTimedSerializer(COOKIE_SECRET).dumps("authed")`
- `HttpOnly`, `Secure`, `SameSite=Lax`
- Max-Age: 30 days, refreshed on each request

API requests from a browser fall through to the cookie check when `Authorization` header is absent. Either path is sufficient.

### Rate limiting

`flask-limiter` with in-memory backing applies 5/minute to `POST /login` only. Sufficient to stop dumb scanners; not needed elsewhere for a single-user app.

### Explicit non-features

- No user accounts, no password hashing — one secret, set by env var.
- No token rotation endpoint — change env var, restart container.
- No CSRF tokens (bearer auth for state-changing API; cookie auth only for same-origin web UI).
- No 2FA, no OAuth.

---

## 7. Deployment (Railway, no Docker)

### `railway.toml`

```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uv run gunicorn --bind 0.0.0.0:$PORT --workers 2 --access-logfile - redbull_api.app:create_app()"
healthcheckPath = "/api/v1/health"
healthcheckTimeout = 10
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5

[[deploy.volumes]]
mountPath = "/data"
```

Nixpacks reads `apps/api/pyproject.toml`, installs deps, runs the start command.

### Railway setup (dashboard, one-time)

1. Connect the GitHub repo → Railway auto-detects `railway.toml`.
2. Add a **Volume** mounted at `/data` (persists across deploys).
3. Set env vars on the service: `API_TOKEN`, `COOKIE_SECRET`, `ANTHROPIC_API_KEY`.
4. Railway provides `$PORT`. Optional custom domain via Railway's UI (HTTPS via Let's Encrypt, free).

### Railway CLI alternative

Same setup is doable via `railway` CLI without using the dashboard:

```bash
railway login
railway link            # link local repo to project
railway variables set API_TOKEN=... COOKIE_SECRET=... ANTHROPIC_API_KEY=...
railway volume add --mount-path /data
railway up              # deploy from local repo
```

### Local development

```bash
cd apps/api
uv sync
API_TOKEN=devtoken COOKIE_SECRET=devsecret ANTHROPIC_API_KEY=sk-... DATA_DIR=./.data \
  uv run gunicorn --bind 0.0.0.0:5000 --workers 1 --reload \
  redbull_api.app:create_app()
```

No Docker, no compose. If self-hosting outside Railway becomes a need later, adding a Dockerfile is a one-evening exercise.

### Operational notes

- **Backups:** Railway volumes aren't auto-backed-up. Manual `railway volume export` is enough for now; `litestream` sidecar to S3/B2 is a "later" item if data matters more.
- **Cold starts:** Widget polling every 5s keeps the container warm; first request after long idle is ~1s.
- **Cost:** Free tier covers single-user traffic comfortably.

---

## 8. Testing

### API (Python)

- `pytest`; SQLite `:memory:` or tmp file seeded per test.
- **Persistence layer:** mock the Anthropic client, feed canned tool-use responses (high/low/none confidence), assert correct rows in `batches` / `batch_items` / `stock`.
- **HTTP layer:** Flask test client against in-memory DB. Auth tests (missing → 401, bad → 401, good → 200). Adjust + delete + log roundtrips.
- **No live Claude in tests.** One opt-in `tests/manual/test_receipt_live.py` for prompt sanity-checking.

### Widget (.NET)

- `ApiRedBullService` unit test with stub `HttpMessageHandler` → polling, stale-flag transitions, retry-on-5xx, no event spam on unchanged state.
- `RedBullServiceFactory` unit test → env-var-driven impl selection.
- Widget rendering: manual smoke test only (visual eyeball).

### End-to-end

- Local API + widget with `REDBULL_API_URL` set, upload real receipt, watch widget update within 5s.
- Receipt fixtures: `tests/fixtures/receipts/` (gitignored if sensitive), including the Tesco receipt from the original conversation.

---

## 9. Build sequence

| Phase | What ships | Done when |
|---|---|---|
| **0. Monorepo restructure** | Move `src/RedBullTracker/` → `apps/widget/`. Update `.sln`, CI workflows, CLAUDE.md, README. | Widget builds + runs offline exactly as today. |
| **1. API skeleton** | Flask app, SQLite schema, auth middleware, `/health` + `/stock` + `/adjust` + `/batches` + `DELETE /batches/{id}`. Web UI: login + dashboard with manual +/- and log. No receipts yet. | `curl` works; web UI lets you manually add/remove and see the log. |
| **2. Receipt parsing** | `POST /receipts`, Anthropic SDK integration, image+thumbnail storage, web UI upload widget. | Drop a receipt image, see correct batch in log with thumbnail. |
| **3. Widget API mode** | `ApiRedBullService`, `RedBullServiceFactory`, env-var-based mode selection, multi-icon rendering, stale-flag dimming. | Widget with `REDBULL_API_URL` set shows cans from API. |
| **4. Railway deploy** | `railway.toml`, env vars set, volume mounted, optional custom domain. | `https://<your-railway-url>/api/v1/health` returns OK. |
| **5. Polish** | Better error messages on receipt parse failures, log pagination, optional litestream backup. | When you feel like it. |

Each phase ends in a working state — stopping after any of them leaves something usable. Phase 0 is the only one that touches existing code without adding features.

---

## Open questions / deferred items

- **Receipt retention policy** — currently keep image files forever after batch delete. Revisit if `/data` storage becomes a concern.
- **Activity log pagination** — Phase 1 ships with `?limit=50` only. Pagination cursor added in Phase 5 if needed.
- **Backups** — litestream is the standard SQLite → object storage pattern. Defer until there's data worth protecting.
- **Per-type icon set** — only `default`, `sugarfree`, and `generic` ship initially. Add named icons (`tropical`, `watermelon`, etc.) as needed.
