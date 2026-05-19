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
    set_cookie = r.headers.get("Set-Cookie", "")
    assert "redbull_session=" in set_cookie
