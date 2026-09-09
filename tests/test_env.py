"""env.sec_user_agent(): real env var wins, then .env file, then a clear error."""

import pytest

from credit_risk import env


def test_env_var_takes_priority(monkeypatch, tmp_path):
    monkeypatch.setenv("SEC_USER_AGENT", "from-env test@example.com")
    monkeypatch.setattr(env, "ENV_FILE", tmp_path / "does-not-exist.env")
    assert env.sec_user_agent() == "from-env test@example.com"


def test_falls_back_to_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('SEC_USER_AGENT="from-file test@example.com"\n')
    monkeypatch.setattr(env, "ENV_FILE", env_file)
    assert env.sec_user_agent() == "from-file test@example.com"


def test_missing_raises_clear_error(monkeypatch, tmp_path):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.setattr(env, "ENV_FILE", tmp_path / "does-not-exist.env")
    with pytest.raises(RuntimeError, match="SEC_USER_AGENT"):
        env.sec_user_agent()
