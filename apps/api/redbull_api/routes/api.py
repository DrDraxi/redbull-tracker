"""JSON endpoints under /api/v1/."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import anthropic
from flask import Blueprint, current_app, g, jsonify, request, send_from_directory

from ..images import save_image_and_thumbnail
from ..receipts import parse_receipt
from ..stock import add_batch, delete_batch, get_stock, list_batches

bp = Blueprint("api", __name__, url_prefix="/api/v1")


@bp.post("/adjust")
def adjust():
    data = request.get_json(silent=True) or request.form or {}
    type_ = data.get("type")
    raw_delta = data.get("delta")
    # delta arrives as int via JSON or str via form-encoded — normalize
    try:
        delta = int(raw_delta) if raw_delta is not None and raw_delta != "" else None
    except (TypeError, ValueError):
        delta = None
    note = data.get("note") or None
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
            datetime.now(timezone.utc).isoformat(),
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
