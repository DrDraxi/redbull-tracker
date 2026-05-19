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
