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
