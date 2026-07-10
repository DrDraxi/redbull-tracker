"""Tests for the smart /api/v1/scan endpoint (receipt-first, photo fallback)."""

import io
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from redbull_api.app import create_app
from redbull_api.receipts import ParseResult


def _make_jpeg(size=(800, 600)) -> bytes:
    img = Image.new("RGB", size, color=(20, 20, 160))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VISION_PROVIDER", "openai")
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


HEADERS = {"Authorization": "Bearer tok"}


def _result(items, confidence, model="openai:gpt-5.6-terra"):
    return ParseResult(
        items=items,
        confidence=confidence,
        model_used=model,
        raw_response={"items": items, "confidence": confidence},
    )


def _post(client):
    return client.post(
        "/api/v1/scan",
        data={"image": (io.BytesIO(_make_jpeg()), "scan.jpg")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )


def test_receipt_wins_when_it_finds_items(client):
    def fake(cfg, *, image_bytes, media_type, mode):
        assert mode == "receipt"  # should never reach photo mode
        return _result([{"type": "sugarfree", "count": 4}], "high")

    with patch("redbull_api.routes.api.recognize", side_effect=fake) as mock:
        r = _post(client)
    assert r.status_code == 200
    assert r.json["source"] == "receipt"
    assert r.json["stock"]["by_type"] == {"sugarfree": 4}
    assert mock.call_count == 1  # no photo fallback needed


def test_falls_back_to_photo_when_receipt_empty(client):
    def fake(cfg, *, image_bytes, media_type, mode):
        if mode == "receipt":
            return _result([], "none")
        return _result([{"type": "summer", "count": 1}, {"type": "sugarfree", "count": 3}], "high")

    with patch("redbull_api.routes.api.recognize", side_effect=fake) as mock:
        r = _post(client)
    assert r.status_code == 200
    assert r.json["source"] == "photo"
    assert r.json["stock"]["by_type"] == {"summer": 1, "sugarfree": 3}
    assert mock.call_count == 2

    log = client.get("/api/v1/batches", headers=HEADERS).json
    entry = next(b for b in log["batches"] if b["id"] == r.json["batch_id"])
    assert entry["source"] == "photo"


def test_422_when_neither_mode_finds_anything(client):
    with patch("redbull_api.routes.api.recognize", side_effect=lambda *a, **k: _result([], "none")):
        r = _post(client)
    assert r.status_code == 422
    assert r.json["error"] == "no_redbulls_found"
