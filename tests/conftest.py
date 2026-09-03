"""Shared test fixtures.

Every test is isolated from the real repo ``.env`` and from any ambient
``CHATURBATE_*`` variables: tests opt in to credentials via ``monkeypatch.setenv``.
"""

import pytest

from chaturbate_mcp import config

_CRED_ENV = ("CHATURBATE_USERNAME", "CHATURBATE_STATS_TOKEN", "CHATURBATE_EVENTS_TOKEN")


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    # Never read the repo .env during tests; skip the one-time load.
    monkeypatch.setattr(config, "_loaded", True)
    for var in _CRED_ENV:
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture
def creds(monkeypatch):
    """Install fake credentials into the environment."""

    def _set(username: str = "testuser", stats: str = "STATS_TOK", events: str = "EV_TOK"):
        monkeypatch.setenv("CHATURBATE_USERNAME", username)
        monkeypatch.setenv("CHATURBATE_STATS_TOKEN", stats)
        monkeypatch.setenv("CHATURBATE_EVENTS_TOKEN", events)
        return {"username": username, "stats": stats, "events": events}

    return _set
