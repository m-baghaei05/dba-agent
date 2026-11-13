"""Tests for configuration loading. No network or API key needed."""

from pathlib import Path

import pytest

from dba_agent.config import ConfigError, load_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.yaml"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    # Make tests independent of the developer's own environment.
    for var in ("DBA_PROFILE", "OPENROUTER_API_KEY", "GAPGPT_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def test_loads_committed_config():
    cfg = load_config(CONFIG, env_file=None)
    assert cfg.active_profile in cfg.profiles
    assert cfg.workflow.interview_min_followup_rounds >= 1


def test_profile_can_be_switched_by_env_var(monkeypatch):
    monkeypatch.setenv("DBA_PROFILE", "deepseek")
    cfg = load_config(CONFIG, env_file=None)
    assert cfg.active_profile == "deepseek"
    assert cfg.provider.model == "deepseek-v4-flash"


def test_unknown_profile_is_rejected(monkeypatch):
    monkeypatch.setenv("DBA_PROFILE", "does-not-exist")
    with pytest.raises(ConfigError, match="Unknown profile"):
        load_config(CONFIG, env_file=None)


def test_missing_api_key_gives_clear_error(monkeypatch):
    monkeypatch.setenv("DBA_PROFILE", "openrouter_free")
    cfg = load_config(CONFIG, env_file=None)
    with pytest.raises(ConfigError, match="OPENROUTER_API_KEY"):
        cfg.provider.api_key()


def test_api_key_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("DBA_PROFILE", "openrouter_free")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    cfg = load_config(CONFIG, env_file=None)
    assert cfg.provider.api_key() == "sk-test"


def test_local_profile_needs_no_key(monkeypatch):
    monkeypatch.setenv("DBA_PROFILE", "ollama")
    cfg = load_config(CONFIG, env_file=None)
    assert cfg.provider.api_key() == "not-needed"
