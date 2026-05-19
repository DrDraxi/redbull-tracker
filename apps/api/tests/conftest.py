import os
import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Strip Redbull API env vars so each test starts clean."""
    for k in list(os.environ):
        if k.startswith(("API_TOKEN", "COOKIE_SECRET", "ANTHROPIC_API_KEY", "DATA_DIR")):
            monkeypatch.delenv(k, raising=False)
