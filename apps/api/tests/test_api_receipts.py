import io
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from redbull_api.app import create_app


def _make_jpeg(size=(800, 600)) -> bytes:
    img = Image.new("RGB", size, color=(180, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


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


def _fake_parse(items, confidence, model="claude-haiku-4-5"):
    from redbull_api.receipts import ParseResult

    return ParseResult(
        items=items, confidence=confidence, model_used=model,
        raw_response={"items": items, "confidence": confidence},
    )


def test_upload_high_confidence_creates_batch(client):
    with patch("redbull_api.routes.api.parse_receipt") as mock_parse:
        mock_parse.return_value = _fake_parse(
            [{"type": "sugarfree", "count": 2}], "high"
        )
        r = client.post(
            "/api/v1/receipts",
            data={"image": (io.BytesIO(_make_jpeg()), "receipt.jpg")},
            content_type="multipart/form-data",
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert r.json["confidence"] == "high"
    assert r.json["stock"]["by_type"] == {"sugarfree": 2}
    assert r.json["batch_id"] > 0
    assert r.json["receipt_id"] > 0


def test_upload_none_confidence_still_creates_batch_returns_422(client):
    with patch("redbull_api.routes.api.parse_receipt") as mock_parse:
        mock_parse.return_value = _fake_parse([], "none")
        r = client.post(
            "/api/v1/receipts",
            data={"image": (io.BytesIO(_make_jpeg()), "receipt.jpg")},
            content_type="multipart/form-data",
            headers=HEADERS,
        )
    assert r.status_code == 422
    assert r.json["error"] == "no_redbulls_found"
    assert r.json["confidence"] == "none"
    assert r.json["batch_id"] > 0
    # Verify the empty batch shows in the log
    log = client.get("/api/v1/batches", headers=HEADERS).json
    assert any(b["id"] == r.json["batch_id"] for b in log["batches"])


def test_upload_rejects_non_image(client):
    r = client.post(
        "/api/v1/receipts",
        data={"image": (io.BytesIO(b"not an image"), "x.jpg")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )
    assert r.status_code == 400


def test_upload_rejects_missing_file(client):
    r = client.post("/api/v1/receipts", data={}, headers=HEADERS)
    assert r.status_code == 400


def test_serve_thumbnail(client):
    with patch("redbull_api.routes.api.parse_receipt") as mock_parse:
        mock_parse.return_value = _fake_parse([{"type": "default", "count": 1}], "high")
        upload = client.post(
            "/api/v1/receipts",
            data={"image": (io.BytesIO(_make_jpeg()), "r.jpg")},
            content_type="multipart/form-data",
            headers=HEADERS,
        )
    rid = upload.json["receipt_id"]
    r = client.get(f"/api/v1/receipts/{rid}/thumb", headers=HEADERS)
    assert r.status_code == 200
    assert r.mimetype == "image/jpeg"


def test_serve_full_image(client):
    with patch("redbull_api.routes.api.parse_receipt") as mock_parse:
        mock_parse.return_value = _fake_parse([{"type": "default", "count": 1}], "high")
        upload = client.post(
            "/api/v1/receipts",
            data={"image": (io.BytesIO(_make_jpeg()), "r.jpg")},
            content_type="multipart/form-data",
            headers=HEADERS,
        )
    rid = upload.json["receipt_id"]
    r = client.get(f"/api/v1/receipts/{rid}/image", headers=HEADERS)
    assert r.status_code == 200
    assert r.mimetype.startswith("image/")


def test_serve_thumbnail_404(client):
    r = client.get("/api/v1/receipts/9999/thumb", headers=HEADERS)
    assert r.status_code == 404
