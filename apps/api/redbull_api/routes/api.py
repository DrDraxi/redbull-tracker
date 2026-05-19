"""JSON endpoints under /api/v1/."""

from __future__ import annotations

import sqlite3

from flask import Blueprint, g, jsonify, request

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
