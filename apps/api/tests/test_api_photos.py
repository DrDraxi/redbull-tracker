"""Tests for the plain-photo recognition endpoint (vision layer mocked)."""

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
    monkeypatch.setenv("VISION_PROVIDER", "codex")
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


HEADERS = {"Authorization": "Bearer tok"}


def _fake(items, confidence, model="codex:default"):
    return ParseResult(
        items=items,
        confidence=confidence,
        model_used=model,
        raw_response={"items": items, "confidence": confidence},
    )


def test_photo_adds_cans_to_stock_with_photo_source(client):
    with patch("redbull_api.routes.api.recognize") as mock:
        mock.return_value = _fake([{"type": "default", "count": 3}], "high")
        r = client.post(
            "/api/v1/photos",
            data={"image": (io.BytesIO(_make_jpeg()), "desk.jpg")},
            content_type="multipart/form-data",
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert r.json["stock"]["by_type"] == {"default": 3}
    # recognize was asked for photo mode
    assert mock.call_args.kwargs["mode"] == "photo"

    # The batch is logged with source "photo"
    log = client.get("/api/v1/batches", headers=HEADERS).json
    entry = next(b for b in log["batches"] if b["id"] == r.json["batch_id"])
    assert entry["source"] == "photo"


def test_photo_no_redbulls_returns_422(client):
    with patch("redbull_api.routes.api.recognize") as mock:
        mock.return_value = _fake([], "none")
        r = client.post(
            "/api/v1/photos",
            data={"image": (io.BytesIO(_make_jpeg()), "desk.jpg")},
            content_type="multipart/form-data",
            headers=HEADERS,
        )
    assert r.status_code == 422
    assert r.json["error"] == "no_redbulls_found"


def test_photo_vision_error_returns_502(client):
    from redbull_api.codex_vision import CodexError

    with patch("redbull_api.routes.api.recognize", side_effect=CodexError("codex login required")):
        r = client.post(
            "/api/v1/photos",
            data={"image": (io.BytesIO(_make_jpeg()), "desk.jpg")},
            content_type="multipart/form-data",
            headers=HEADERS,
        )
    assert r.status_code == 502
    assert r.json["error"] == "vision_error"


def test_photo_rejects_missing_file(client):
    r = client.post("/api/v1/photos", data={}, headers=HEADERS)
    assert r.status_code == 400
