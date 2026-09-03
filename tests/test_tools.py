"""Tool-level tests through the built MCPServer (network stubbed at the api layer)."""

import json

import pytest

from chaturbate_mcp.server import build_server

# Event feed URLs accepted by validate_events_url (host must match eventsapi.chaturbate.com).
GOOD_NEXT_URL = "https://eventsapi.chaturbate.com/events/testuser/EVTOK/?i=1-0&timeout=0"
BAD_NEXT_URL = "https://evil.example/events/testuser/EVTOK/"


async def invoke(server, name, args):
    """Call a tool and return parsed JSON text, or {'__error__': msg} on a tool error."""
    try:
        result = await server.call_tool(name, args)
    except Exception as exc:  # noqa: BLE001 - tool errors surface as exceptions via direct call_tool
        return {"__error__": str(exc)}
    text = result.content[0].text if result.content else ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


@pytest.fixture
def server():
    return build_server()


async def test_config_status_no_creds(server):
    out = await invoke(server, "config_status", {})
    assert out["username"] is None
    assert out["stats_configured"] is False
    assert out["events_configured"] is False
    assert out["env_source"].endswith(".env")


async def test_config_status_never_prints_tokens(server, creds):
    creds(username="testuser", stats="SECRET_STATS_TOKEN_ABC", events="SECRET_EVENTS_TOKEN_ABC")
    result = await server.call_tool("config_status", {})
    text = result.content[0].text
    out = json.loads(text)
    assert out["stats_configured"] is True and out["events_configured"] is True
    assert out["username"] == "testuser"
    assert "SECRET_STATS_TOKEN_ABC" not in text
    assert "SECRET_EVENTS_TOKEN_ABC" not in text


async def test_room_stats_happy_path(server, creds, monkeypatch):
    expected = {"username": "testuser", "num_followers": 3, "num_viewers": 10}
    captured = {}

    async def stub(username, token, transport=None):
        captured.update(username=username, token=token)
        return expected

    monkeypatch.setattr("chaturbate_mcp.server.api_room_stats", stub)
    creds(stats="REAL_STATS_TOK")
    out = await invoke(server, "fetch_room_stats", {})
    assert out == expected
    assert captured == {"username": "testuser", "token": "REAL_STATS_TOK"}


async def test_room_stats_missing_creds_is_clear_error(server):
    out = await invoke(server, "fetch_room_stats", {})
    assert "__error__" in out
    assert "Missing credentials" in out["__error__"]


async def test_affiliate_default_sends_no_extra(server, creds, monkeypatch):
    captured = {}

    async def stub(username, token, extra=None, transport=None):
        captured["extra"] = extra
        return {"ok": True}

    monkeypatch.setattr("chaturbate_mcp.server.api_affiliate_stats", stub)
    creds(stats="REAL_STATS_TOK")
    out = await invoke(server, "fetch_affiliate_stats", {})
    assert out == {"ok": True}
    assert captured["extra"] == {}


async def test_affiliate_forwards_only_supplied_params(server, creds, monkeypatch):
    captured = {}

    async def stub(username, token, extra=None, transport=None):
        captured["extra"] = extra
        return {"ok": True}

    monkeypatch.setattr("chaturbate_mcp.server.api_affiliate_stats", stub)
    creds(stats="REAL_STATS_TOK")
    await invoke(server, "fetch_affiliate_stats", {"start_date": "2026-08-01"})
    assert captured["extra"] == {"start_date": "2026-08-01"}


async def test_fetch_events_threads_next_url(server, monkeypatch):
    captured = {}
    sample = {"events": [], "nextUrl": GOOD_NEXT_URL}

    async def stub(url, transport=None):
        captured["url"] = url
        return sample

    monkeypatch.setattr("chaturbate_mcp.server.api_events_feed", stub)
    out = await invoke(server, "fetch_events", {"next_url": GOOD_NEXT_URL})
    assert out == {"events": [], "next_url": GOOD_NEXT_URL}
    assert captured["url"] == GOOD_NEXT_URL


async def test_fetch_events_rejects_foreign_host(server):
    out = await invoke(server, "fetch_events", {"next_url": BAD_NEXT_URL})
    assert "eventsapi.chaturbate.com" in out["__error__"]


async def test_fetch_events_timeout_range(server):
    out = await invoke(server, "fetch_events", {"timeout": 999})
    assert "0 and 90" in out["__error__"]


async def test_fetch_events_requires_events_creds(server):
    out = await invoke(server, "fetch_events", {})
    assert "Missing credentials" in out["__error__"]
    assert "CHATURBATE_EVENTS_TOKEN" in out["__error__"]


async def test_fetch_events_payload_without_keys_is_error(server, creds, monkeypatch):
    async def stub(url, transport=None):
        return {"nope": True}

    monkeypatch.setattr("chaturbate_mcp.server.api_events_feed", stub)
    creds(events="EV")
    out = await invoke(server, "fetch_events", {"next_url": GOOD_NEXT_URL})
    assert "'events' or 'nextUrl'" in out["__error__"]


async def test_build_events_feed_url(server, creds):
    creds(username="testuser", events="EVTOK_123")
    out = await invoke(server, "build_events_feed_url", {"timeout": 0})
    assert out == "https://eventsapi.chaturbate.com/events/testuser/EVTOK_123/?timeout=0"


async def test_get_events_schema_returns_12_rows(server):
    out = await invoke(server, "get_events_schema", {})
    assert isinstance(out, str)
    assert out.count("| `") == 12
