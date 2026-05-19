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
from ..prices import list_prices
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
    stock = get_stock(g.db)
    return render_template(
        "dashboard.html",
        stock=stock,
        prices=list_prices(g.db) if stock["total"] == 0 else None,
        batches=list_batches(g.db, limit=50),
        session_authed=True,
    )


@bp.get("/ui/stock")
def stock_fragment():
    if not _is_authed():
        return "", 401
    stock = get_stock(g.db)
    return render_template(
        "partials/stock.html",
        stock=stock,
        prices=list_prices(g.db) if stock["total"] == 0 else None,
    )


@bp.get("/ui/log")
def log_fragment():
    if not _is_authed():
        return "", 401
    return render_template(
        "partials/log.html", batches=list_batches(g.db, limit=50)
    )
