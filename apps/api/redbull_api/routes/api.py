"""JSON endpoints under /api/v1/."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import anthropic
from flask import Blueprint, current_app, g, jsonify, request, send_from_directory

from ..codex_vision import CodexError
from ..images import save_image_and_thumbnail
from ..openai_vision import OpenAIVisionError
from ..prices import add_price, delete_price, list_prices, refresh_from_web
from ..stock import add_batch, delete_batch, get_stock, list_batches
from ..vision import recognize

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


def _load_scan_input():
    """Read + persist the uploaded image. Returns ((data, media_type, cfg, saved), None)
    on success, or (None, error_response) to return directly."""
    file = request.files.get("image")
    if not file:
        return None, (jsonify({"error": "missing_image"}), 400)

    data = file.read()
    if not data:
        return None, (jsonify({"error": "missing_image"}), 400)

    cfg = current_app.config["CONFIG"]
    media_type = file.mimetype or "image/jpeg"
    try:
        saved = save_image_and_thumbnail(data, content_type=media_type, data_dir=cfg.data_dir)
    except ValueError:
        return None, (jsonify({"error": "invalid_image"}), 400)

    return (data, media_type, cfg, saved), None


def _persist_scan(saved, result, source: str):
    """Record one scan (receipts row) + one batch with the detected source."""
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
    batch_id = add_batch(g.db, source=source, items=items, note=None, receipt_id=receipt_id)

    payload = {
        "batch_id": batch_id,
        "receipt_id": receipt_id,
        "source": source,
        "items": result.items,
        "confidence": result.confidence,
        "stock": get_stock(g.db),
    }
    if result.confidence == "none":
        payload["error"] = "no_redbulls_found"
        return jsonify(payload), 422
    return jsonify(payload)


def _scan_and_record(*, mode: str, source: str):
    """Save the image, run a single recognition mode, record a batch."""
    loaded, err = _load_scan_input()
    if err:
        return err
    data, media_type, cfg, saved = loaded

    try:
        result = recognize(cfg, image_bytes=data, media_type=media_type, mode=mode)
    except (CodexError, OpenAIVisionError, anthropic.APIError) as e:
        return jsonify({"error": "vision_error", "detail": str(e)[:300]}), 502

    return _persist_scan(saved, result, source)


@bp.post("/receipts")
def upload_receipt():
    return _scan_and_record(mode="receipt", source="receipt")


@bp.post("/scan")
def smart_scan():
    """One-shot smart scan: a single unified vision call classifies the image as
    a receipt or a photo of cans and extracts accordingly. Records one batch
    tagged with the detected source (defaults to 'photo' if unclassified)."""
    loaded, err = _load_scan_input()
    if err:
        return err
    data, media_type, cfg, saved = loaded

    try:
        result = recognize(cfg, image_bytes=data, media_type=media_type, mode="scan")
    except (CodexError, OpenAIVisionError, anthropic.APIError) as e:
        return jsonify({"error": "vision_error", "detail": str(e)[:300]}), 502

    source = result.kind if result.kind in ("receipt", "photo") else "photo"
    return _persist_scan(saved, result, source)


@bp.post("/photos")
def upload_photo():
    """Recognize Red Bull cans in an ordinary photo (e.g. cans on a desk)."""
    return _scan_and_record(mode="photo", source="photo")


@bp.get("/receipts/<int:receipt_id>/image")
def receipt_image(receipt_id: int):
    row = g.db.execute(
        "SELECT filename FROM receipts WHERE id = ?", (receipt_id,)
    ).fetchone()
    if not row:
        return jsonify({"error": "not_found"}), 404
    cfg = current_app.config["CONFIG"]
    return send_from_directory(cfg.data_dir / "receipts", row["filename"])


@bp.get("/prices")
def get_prices():
    return jsonify({"prices": list_prices(g.db)})


@bp.post("/prices")
def create_price():
    data = request.get_json(silent=True) or request.form or {}
    type_ = (data.get("type") or "").strip().lower()
    url = (data.get("url") or "").strip()
    label = (data.get("label") or "").strip()
    if not type_:
        return jsonify({"error": "invalid_type"}), 400
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"error": "invalid_url"}), 400
    row = add_price(g.db, type=type_, url=url, label=label or None)
    return jsonify({"price": row}), 201


@bp.delete("/prices/<type_>")
def remove_price(type_: str):
    ok = delete_price(g.db, type_)
    if not ok:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"prices": list_prices(g.db)})


@bp.post("/prices/refresh")
def refresh_prices():
    cfg = current_app.config["CONFIG"]
    if not cfg.anthropic_api_key:
        return jsonify({"error": "anthropic_key_missing"}), 503
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    try:
        fetched = refresh_from_web(client, g.db)
    except anthropic.APIError as e:
        return jsonify({"error": "anthropic_error", "detail": str(e)[:300]}), 502
    return jsonify({
        "fetched": len(fetched),
        "prices": list_prices(g.db),
    })


@bp.get("/receipts/<int:receipt_id>/thumb")
def receipt_thumb(receipt_id: int):
    row = g.db.execute(
        "SELECT thumbnail FROM receipts WHERE id = ?", (receipt_id,)
    ).fetchone()
    if not row or not row["thumbnail"]:
        return jsonify({"error": "not_found"}), 404
    cfg = current_app.config["CONFIG"]
    return send_from_directory(cfg.data_dir / "receipts" / "thumbs", row["thumbnail"])
