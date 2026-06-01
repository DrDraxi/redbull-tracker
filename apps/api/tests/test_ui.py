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
    assert b"stock" in r.data.lower()


def test_ui_stock_fragment(client):
    client.post("/login", data={"token": "tok"})
    r = client.get("/ui/stock")
    assert r.status_code == 200
    # HTML fragment, not full page
    assert b"<html" not in r.data
    assert b"stock" in r.data.lower()


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
    set_cookie = r.headers.get("Set-Cookie", "")
    assert "redbull_session=" in set_cookie


def test_manifest_served_without_auth(client):
    r = client.get("/static/manifest.webmanifest")
    assert r.status_code == 200
    assert b"Red Bull Tracker" in r.data
    assert b"standalone" in r.data


def test_service_worker_served_at_root_with_scope_header(client):
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["Content-Type"]
    # Must be allowed to control the whole "/" scope.
    assert r.headers.get("Service-Worker-Allowed") == "/"


def test_login_page_links_pwa_metadata(client):
    r = client.get("/login")
    assert b"manifest.webmanifest" in r.data
    assert b"apple-touch-icon" in r.data
    assert b"serviceWorker" in r.data
