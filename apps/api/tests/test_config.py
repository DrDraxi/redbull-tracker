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


def test_config_vision_provider_defaults_to_codex(monkeypatch, tmp_path):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cfg = Config.from_env()
    assert cfg.vision_provider == "codex"
    assert cfg.codex_bin == "codex"
    assert cfg.codex_model == ""
    assert cfg.openai_base_url == ""


def test_config_vision_provider_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VISION_PROVIDER", "OpenAI")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:10531/v1")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5-codex")
    cfg = Config.from_env()
    assert cfg.vision_provider == "openai"  # normalized to lowercase
    assert cfg.openai_base_url == "http://127.0.0.1:10531/v1"
    assert cfg.openai_model == "gpt-5-codex"


def test_config_default_data_dir(monkeypatch):
    from pathlib import Path

    monkeypatch.setenv("API_TOKEN", "tok")
    monkeypatch.setenv("COOKIE_SECRET", "sec")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk")
    cfg = Config.from_env()
    # Path equality is platform-portable; on Windows str() would give '\data'.
    assert cfg.data_dir == Path("/data")
