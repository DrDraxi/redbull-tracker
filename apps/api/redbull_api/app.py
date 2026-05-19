"""Flask application factory."""

from __future__ import annotations

import sqlite3

from flask import Flask, g, jsonify, request

from .auth import COOKIE_MAX_AGE, COOKIE_NAME, check_bearer, check_cookie
from .config import Config
from .db import connect, init_db
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
        # Public endpoints
        if request.path == "/api/v1/health":
            return None
        # UI auth flow + static (Phase 1.10 wires UI) — skip for now
        if request.endpoint in {"ui.login_form", "ui.login_submit", "static"}:
            return None
        if not request.path.startswith("/api/v1/"):
            return None  # UI handled separately later

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

    return app
