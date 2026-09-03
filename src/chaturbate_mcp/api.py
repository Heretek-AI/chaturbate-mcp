"""Thin async HTTP layer over the three Chaturbate endpoints.

Uses ``httpx2`` (already a dependency of ``mcp`` 2.x), mirroring the httpx API.
Error messages are redacted so a raised :class:`ApiError` never echoes a token.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx2

STATS_URL = "https://chaturbate.com/statsapi/"
AFFILIATE_URL = "https://chaturbate.com/affiliates/apistats/"
EVENTS_HOST = "https://eventsapi.chaturbate.com"

# The events long-poll can hold a request up to 90s upstream; the client read
# timeout must comfortably exceed the longest upstream wait.
EVENTS_READ_TIMEOUT = 120.0
DEFAULT_READ_TIMEOUT = 30.0


class ApiError(RuntimeError):
    """A non-200 / non-JSON / timed-out Chaturbate response, with secrets scrubbed."""

    def __init__(self, status: int | None, url: str, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"Chaturbate API HTTP {status}: {detail} (url: {redact_url(url)})" if status else detail)


def redact_url(url: str) -> str:
    """Strip credentials from a URL for safe inclusion in errors and logs.

    Handles two shapes: the events feed ``…/events/<username>/<token>/`` path form
    and the ``token=…`` query form used by the stats/affiliate endpoints.
    """
    parts = urlsplit(url)
    segs = parts.path.split("/")
    if len(segs) >= 4 and segs[1] == "events":
        # /events/<username>/<token>/...
        segs[3] = "<token>"
        path = "/".join(segs)
    else:
        path = parts.path
    query = re.sub(r"(token=)[^&]*", r"\1<redacted>", parts.query)
    return urlunsplit((parts.scheme, parts.netloc, path, query, ""))


async def _get_json(
    url: str,
    *,
    params: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_READ_TIMEOUT,
    transport: httpx2.BaseTransport | None = None,
) -> dict[str, Any]:
    try:
        kwargs = {"timeout": timeout, "follow_redirects": True}
        if transport is not None:
            kwargs["transport"] = transport
        async with httpx2.AsyncClient(**kwargs) as client:
            resp = await client.get(url, params=dict(params) if params else None)
    except httpx2.TimeoutException as exc:
        raise ApiError(None, url, f"timed out after {timeout:.0f}s") from exc
    if resp.status_code != 200:
        raise ApiError(resp.status_code, str(resp.url), (resp.text or "")[:300])
    try:
        return resp.json()
    except ValueError as exc:
        raise ApiError(resp.status_code, str(resp.url), "non-JSON response body") from exc


async def fetch_room_stats(
    username: str, token: str, transport: httpx2.BaseTransport | None = None
) -> dict[str, Any]:
    """One-shot room/account stats snapshot (upstream refreshes ~every 5 minutes)."""
    return await _get_json(
        STATS_URL, params={"username": username, "token": token}, transport=transport
    )


async def fetch_affiliate_stats(
    username: str,
    token: str,
    extra: Mapping[str, str] | None = None,
    transport: httpx2.BaseTransport | None = None,
) -> dict[str, Any]:
    """Affiliate earnings report. Only ``username``+``token`` are sent by default.

    ``extra`` (best-effort, undocumented upstream range/breakdown params) is
    appended verbatim when the caller supplies it.
    """
    params: dict[str, str] = {"username": username, "token": token}
    if extra:
        params.update({k: v for k, v in extra.items() if v})
    return await _get_json(AFFILIATE_URL, params=params, transport=transport)


async def fetch_events_feed(
    url: str, transport: httpx2.BaseTransport | None = None
) -> dict[str, Any]:
    """One long-poll GET against a feed URL (base or ``nextUrl``). URL not logged."""
    return await _get_json(url, timeout=EVENTS_READ_TIMEOUT, transport=transport)
