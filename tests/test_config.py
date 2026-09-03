"""Config resolution tests: env overrides, per-call overrides, error messages."""

import pytest

from chaturbate_mcp.config import get_config, resolve_account


def test_get_config_empty_when_no_env(monkeypatch):
    for var in ("CHATURBATE_USERNAME", "CHATURBATE_STATS_TOKEN", "CHATURBATE_EVENTS_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    cfg = get_config()
    assert cfg.username is None
    assert cfg.stats_token is None
    assert cfg.events_token is None
    assert cfg.stats_configured is False
    assert cfg.events_configured is False


def test_get_config_reads_env(creds):
    setvals = creds()
    cfg = get_config()
    assert cfg.username == setvals["username"]
    assert cfg.stats_token == setvals["stats"]
    assert cfg.events_token == setvals["events"]
    assert cfg.stats_configured is True
    assert cfg.events_configured is True


def test_get_config_requires_username_for_configured_flags(creds):
    creds(username="", stats="S", events="E")  # username empty -> not configured
    cfg = get_config()
    assert cfg.stats_configured is False
    assert cfg.events_configured is False


def test_resolve_account_per_call_override_beats_env(creds):
    creds(username="envuser", stats="ENVSTAT", events="ENVEV")
    u, t = resolve_account("overrideuser", "overridetok", events=False)
    assert (u, t) == ("overrideuser", "overridetok")


def test_resolve_account_stats_uses_stats_token(creds):
    creds(stats="STATS_XYZ", events="EV_XYZ")
    assert resolve_account(None, None, events=False)[1] == "STATS_XYZ"
    assert resolve_account(None, None, events=True)[1] == "EV_XYZ"


def test_resolve_account_missing_raises_clear_error(monkeypatch):
    monkeypatch.delenv("CHATURBATE_USERNAME", raising=False)
    monkeypatch.delenv("CHATURBATE_STATS_TOKEN", raising=False)
    with pytest.raises(ValueError, match="CHATURBATE_USERNAME"):
        resolve_account(None, None, events=False)


def test_resolve_account_missing_events_token_message(creds, monkeypatch):
    creds(stats="S")
    monkeypatch.delenv("CHATURBATE_EVENTS_TOKEN")  # events token absent
    with pytest.raises(ValueError, match="CHATURBATE_EVENTS_TOKEN"):
        resolve_account(None, None, events=True)
