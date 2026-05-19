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


HEADERS = {"Authorization": "Bearer tok"}


def test_adjust_creates_batch(client):
    r = client.post("/api/v1/adjust", json={"type": "default", "delta": 2}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json["batch_id"] > 0
    assert r.json["stock"]["by_type"] == {"default": 2}


def test_adjust_with_note(client):
    r = client.post(
        "/api/v1/adjust",
        json={"type": "default", "delta": 1, "note": "found one"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    log = client.get("/api/v1/batches", headers=HEADERS).json
    assert log["batches"][0]["note"] == "found one"


def test_adjust_rejects_missing_fields(client):
    r = client.post("/api/v1/adjust", json={"type": "default"}, headers=HEADERS)
    assert r.status_code == 400


def test_adjust_rejects_zero_delta(client):
    r = client.post(
        "/api/v1/adjust", json={"type": "default", "delta": 0}, headers=HEADERS
    )
    assert r.status_code == 400


def test_adjust_rejects_underflow(client):
    r = client.post(
        "/api/v1/adjust", json={"type": "default", "delta": -1}, headers=HEADERS
    )
    assert r.status_code == 400


def test_batches_list(client):
    client.post("/api/v1/adjust", json={"type": "default", "delta": 1}, headers=HEADERS)
    client.post("/api/v1/adjust", json={"type": "sugarfree", "delta": 2}, headers=HEADERS)
    r = client.get("/api/v1/batches", headers=HEADERS)
    assert r.status_code == 200
    assert len(r.json["batches"]) == 2
    assert r.json["batches"][0]["source"] == "manual"


def test_batches_limit_param(client):
    for _ in range(5):
        client.post(
            "/api/v1/adjust", json={"type": "default", "delta": 1}, headers=HEADERS
        )
    r = client.get("/api/v1/batches?limit=3", headers=HEADERS)
    assert len(r.json["batches"]) == 3


def test_delete_batch_reverses_stock(client):
    bid = client.post(
        "/api/v1/adjust", json={"type": "default", "delta": 3}, headers=HEADERS
    ).json["batch_id"]
    r = client.delete(f"/api/v1/batches/{bid}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json["stock"]["by_type"] == {}


def test_delete_nonexistent_batch_404(client):
    r = client.delete("/api/v1/batches/9999", headers=HEADERS)
    assert r.status_code == 404


def test_adjust_accepts_form_encoded(client):
    r = client.post(
        "/api/v1/adjust",
        data={"type": "default", "delta": "2", "note": "from form"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    assert r.json["stock"]["by_type"] == {"default": 2}
