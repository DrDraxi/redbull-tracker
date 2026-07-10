"""Tests for the unified single-pass /api/v1/scan endpoint."""

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


def _result(items, confidence, kind, model="openai:gpt-5.6-terra"):
    return ParseResult(
        items=items,
        confidence=confidence,
        model_used=model,
        raw_response={"items": items, "confidence": confidence, "kind": kind},
        kind=kind,
    )


def _post(client):
    return client.post(
        "/api/v1/scan",
        data={"image": (io.BytesIO(_make_jpeg()), "scan.jpg")},
        content_type="multipart/form-data",
        headers=HEADERS,
    )


def test_single_call_photo_kind(client):
    result = _result([{"type": "summer", "count": 1}, {"type": "sugarfree", "count": 3}], "high", "photo")
    with patch("redbull_api.routes.api.recognize", return_value=result) as mock:
        r = _post(client)
    assert r.status_code == 200
    assert r.json["source"] == "photo"
    assert r.json["stock"]["by_type"] == {"summer": 1, "sugarfree": 3}
    # Exactly one unified vision call, in scan mode.
    assert mock.call_count == 1
    assert mock.call_args.kwargs["mode"] == "scan"

    log = client.get("/api/v1/batches", headers=HEADERS).json
    entry = next(b for b in log["batches"] if b["id"] == r.json["batch_id"])
    assert entry["source"] == "photo"


def test_single_call_receipt_kind(client):
    result = _result([{"type": "default", "count": 2}], "high", "receipt")
    with patch("redbull_api.routes.api.recognize", return_value=result) as mock:
        r = _post(client)
    assert r.status_code == 200
    assert r.json["source"] == "receipt"
    assert mock.call_count == 1


def test_kind_missing_defaults_to_photo(client):
    result = _result([{"type": "default", "count": 1}], "high", None)
    with patch("redbull_api.routes.api.recognize", return_value=result):
        r = _post(client)
    assert r.status_code == 200
    assert r.json["source"] == "photo"


def test_422_when_nothing_found(client):
    with patch("redbull_api.routes.api.recognize", return_value=_result([], "none", None)):
        r = _post(client)
    assert r.status_code == 422
    assert r.json["error"] == "no_redbulls_found"
