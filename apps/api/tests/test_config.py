import pytest

from redbull_api.config import Config


def test_config_loads_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    cfg = Config.from_env()
    assert cfg.api_token == "tok"
    assert cfg.cookie_secret == "sec"
    assert cfg.anthropic_api_key == "sk-test"
    assert cfg.data_dir == tmp_path


def test_config_missing_api_token_raises(monkeypatch):
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk")
    with pytest.raises(RuntimeError, match="API_TOKEN"):
        Config.from_env()


def test_config_missing_cookie_secret_raises(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk")
    with pytest.raises(RuntimeError, match="COOKIE_SECRET"):
        Config.from_env()


def test_config_default_data_dir(monkeypatch):
    from pathlib import Path

    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk")
    cfg = Config.from_env()
    # Path equality is platform-portable; on Windows str() would give '\data'.
    assert cfg.data_dir == Path("/data")
