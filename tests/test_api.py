"""HTTP-layer tests against httpx2.MockTransport (no network, no real tokens)."""

import httpx2
import pytest

from chaturbate_mcp import api
from chaturbate_mcp.api import (
    ApiError,
    fetch_affiliate_stats,
    fetch_events_feed,
    fetch_room_stats,
    redact_url,
)
from chaturbate_mcp.events_util import events_feed_url

ROOM_SAMPLE = {
    "username": "testuser",
    "token_balance": 0,
    "tips_in_last_hour": None,
    "votes_up": 0,
    "votes_down": 0,
    "satisfaction_score": 100,
    "last_broadcast": -1,
    "time_online": -1,
    "num_followers": 0,
    "num_viewers": 0,
    "num_registered_viewers": 0,
    "num_tokened_viewers": 0,
    "num_ad_anon_viewers": 0,  # undocumented extra key must be tolerated
}

AFFILIATE_SAMPLE = {
    "stats": [{"program": "p", "columns": ["Date"], "rows": [], "totals": {}}] * 9,
    "range": {"start_date": "2026-09-01", "end_date": "2026-09-15"},
    "breakdown": "Date",
}

EVENTS_SAMPLE = {
    "events": [{"method": "tip", "id": "1-0", "object": {"broadcaster": "testuser"}}],
    "nextUrl": "https://eventsapi.chaturbate.com/events/testuser/T/?i=1-0&timeout=0",
}


def transport_responding(handler):
    return httpx2.MockTransport(handler)


async def test_room_stats_success_and_unknown_keys_tolerated():
    async def ok(request):
        return httpx2.Response(200, json=ROOM_SAMPLE)

    data = await fetch_room_stats("testuser", "TOK", transport_responding(ok))
    assert data["username"] == "testuser"
    assert "num_ad_anon_viewers" in data  # undocumented key passed through


async def test_room_stats_non200_redacts_query_token():
    async def forbidden(request):
        return httpx2.Response(403, text="rate limited")

    with pytest.raises(ApiError) as exc:
        await fetch_room_stats("testuser", "S3CR3T", transport_responding(forbidden))
    msg = str(exc.value)
    assert "HTTP 403" in msg
    assert "S3CR3T" not in msg  # token stripped from the URL echoed in the message


async def test_affiliate_default_sends_no_range_params():
    async def echo(request):
        return httpx2.Response(200, json={"seen": str(request.url)})

    data = await fetch_affiliate_stats("testuser", "TOK", None, transport_responding(echo))
    seen = data["seen"]
    assert "username=testuser" in seen and "token=TOK" in seen
    assert "start_date" not in seen and "end_date" not in seen and "breakdown" not in seen


async def test_affiliate_appends_only_supplied_extra_params():
    async def echo(request):
        return httpx2.Response(200, json={"seen": str(request.url)})

    data = await fetch_affiliate_stats(
        "testuser", "TOK", {"start_date": "2026-08-01", "end_date": "", "breakdown": None},  # type: ignore[misc]
        transport_responding(echo),
    )
    seen = data["seen"]
    assert "start_date=2026-08-01" in seen
    assert "end_date=" not in seen and "breakdown" not in seen  # empty/None filtered


async def test_events_feed_success_shape():
    async def ok(request):
        return httpx2.Response(200, json=EVENTS_SAMPLE)

    url = events_feed_url("testuser", "TOK", 0)
    data = await fetch_events_feed(url, transport_responding(ok))
    assert data["events"][0]["method"] == "tip"
    assert data["nextUrl"].startswith("https://eventsapi.chaturbate.com/events/")


async def test_events_feed_non200_redacts_path_token():
    async def nf(request):
        return httpx2.Response(404, text="gone")

    url = events_feed_url("testuser", "PATHTOKEN", 0)
    with pytest.raises(ApiError) as exc:
        await fetch_events_feed(url, transport_responding(nf))
    assert "PATHTOKEN" not in str(exc.value)


def test_redact_url_query_token():
    out = redact_url("https://chaturbate.com/statsapi/?username=testuser&token=QUERYTOK")
    assert "QUERYTOK" not in out
    assert "token=<redacted>" in out
    assert "testuser" in out  # username kept (not a secret)


def test_redact_url_events_path_token():
    out = redact_url("https://eventsapi.chaturbate.com/events/testuser/PATHTOK/?i=1-0&timeout=0")
    assert "PATHTOK" not in out
    assert "/events/testuser/<token>/" in out


async def test_non_json_body_raises():
    async def bad(request):
        return httpx2.Response(200, text="<html>not json</html>")

    with pytest.raises(ApiError, match="non-JSON"):
        await fetch_room_stats("testuser", "TOK", transport_responding(bad))


def test_module_constants():
    assert api.STATS_URL == "https://chaturbate.com/statsapi/"
    assert api.AFFILIATE_URL == "https://chaturbate.com/affiliates/apistats/"
    assert api.EVENTS_HOST == "https://eventsapi.chaturbate.com"
