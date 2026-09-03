"""LIVE smoke test for the Chaturbate MCP HTTP layer.

Hits the real Chaturbate endpoints once each. Credentials come from the
``CHATURBATE_*`` environment (including the project ``.env``) or, failing that,
are regex-extracted IN MEMORY from ``review/Stats Token Authorization - Chaturbate.html``.
Tokens are never written anywhere and never printed; output is PASS/FAIL + non-secret
summaries only.

Usage:  uv run python scripts/smoke_test.py
"""

from __future__ import annotations

import asyncio
import os
import re

import httpx2

from chaturbate_mcp import api
from chaturbate_mcp.config import load_env, project_root
from chaturbate_mcp.events_util import events_feed_url

REVIEW_HTML = project_root() / "review" / "Stats Token Authorization - Chaturbate.html"

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str) -> None:
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def short_username(u: str) -> str:
    return f"{u[:2]}…{u[-1]}" if len(u) > 3 else u


def creds_from_review() -> dict[str, str] | None:
    """Extract username/stats/events tokens from the saved authtoken page, in memory."""
    if not REVIEW_HTML.exists():
        return None
    text = REVIEW_HTML.read_text(encoding="utf-8", errors="replace")
    m_stats = re.search(r"statsapi/\?username=([^&\"' ]+)&(?:amp;)?token=([A-Za-z0-9]+)", text)
    m_events = re.search(r"eventsapi\.chaturbate\.com/events/([^/\"' ]+)/([A-Za-z0-9]+)/", text)
    if not (m_stats and m_events):
        return None
    return {
        "username": m_stats.group(1),
        "stats_token": m_stats.group(2),
        "events_token": m_events.group(2),
    }


def get_creds() -> dict[str, str]:
    load_env()

    env = {
        "username": os.getenv("CHATURBATE_USERNAME"),
        "stats_token": os.getenv("CHATURBATE_STATS_TOKEN"),
        "events_token": os.getenv("CHATURBATE_EVENTS_TOKEN"),
    }
    if all(env.values()):
        return env  # type: ignore[return-value]
    from_review = creds_from_review()
    if from_review:
        return from_review
    raise SystemExit(
        "No credentials found. Set CHATURBATE_USERNAME/CHATURBATE_STATS_TOKEN/"
        "CHATURBATE_EVENTS_TOKEN (or the project .env), or ensure "
        f"{REVIEW_HTML.relative_to(project_root())} exists with token URLs."
    )


async def guarded(name: str, coro):
    """Run one check with a single spaced retry (Chaturbate can 403-throttle)."""
    for attempt in (1, 2):
        try:
            return await coro()
        except api.ApiError as exc:
            if attempt == 1 and exc.status == 403:
                await asyncio.sleep(6)  # back off once before reporting throttling
                continue
            raise
    raise AssertionError("unreachable")


async def check_room_stats(u: str, tok: str) -> None:
    body = await guarded("room-stats", lambda: api.fetch_room_stats(u, tok))
    required = {"username", "token_balance", "num_followers", "num_viewers", "time_online", "last_broadcast"}
    missing = required - set(body)
    if missing:
        record("room-stats", False, f"missing keys: {sorted(missing)}")
        return
    record(
        "room-stats",
        True,
        f"user={short_username(body['username'])} followers={body['num_followers']} "
        f"viewers={body['num_viewers']} time_online={body['time_online']} last_broadcast={body['last_broadcast']}",
    )


async def check_affiliate(u: str, tok: str) -> None:
    body = await guarded("affiliate-stats", lambda: api.fetch_affiliate_stats(u, tok))
    stats = body.get("stats")
    if not isinstance(stats, list) or len(stats) != 9:
        record("affiliate-stats", False, f"expected 9 programs, got {len(stats) if isinstance(stats, list) else type(stats).__name__}")
        return
    if not all({"program", "columns", "rows", "totals"} <= set(p) for p in stats):
        record("affiliate-stats", False, "program rows missing program/columns/rows/totals")
        return
    rng = body.get("range", {})
    record(
        "affiliate-stats",
        True,
        f"9 programs | range {rng.get('start_date')}..{rng.get('end_date')} | breakdown={body.get('breakdown')}",
    )


async def check_events(u: str, tok: str) -> None:
    base = events_feed_url(u, tok, timeout=0)
    first = await guarded("events-initial", lambda: api.fetch_events_feed(base))
    if not isinstance(first.get("events"), list) or not isinstance(first.get("nextUrl"), str):
        record("events-initial", False, "payload missing 'events' list or 'nextUrl'")
        return
    methods = sorted({e.get("method") for e in first["events"] if isinstance(e, dict)})
    record(
        "events-initial",
        True,
        f"events={len(first['events'])} methods={methods if methods else '(none)'}",
    )
    # Follow nextUrl exactly once to confirm the cursor handshake, then STOP.
    nxt = first["nextUrl"]
    if not nxt.startswith("https://eventsapi.chaturbate.com/events/"):
        record("events-follow", False, "nextUrl is not on eventsapi.chaturbate.com")
        return
    second = await guarded("events-follow", lambda: api.fetch_events_feed(nxt))
    ok = isinstance(second.get("events"), list) and isinstance(second.get("nextUrl"), str)
    record("events-follow", ok, f"follow-up events={len(second.get('events', [])) if ok else 'n/a'}")


async def main() -> int:
    creds = get_creds()
    u = creds["username"]
    print(f"account: {short_username(u)} | creds source: env/.env or review HTML (in memory)")
    try:
        await check_room_stats(u, creds["stats_token"])
        await asyncio.sleep(2)
        await check_affiliate(u, creds["stats_token"])
        await asyncio.sleep(2)
        await check_events(u, creds["events_token"])
    except api.ApiError as exc:
        record("network", False, str(exc))
    except httpx2.HTTPError as exc:
        record("network", False, f"HTTP transport error: {exc}")
    print()
    failures = [name for name, ok, _ in RESULTS if not ok]
    if failures:
        print(f"SMOKE TEST FAILED ({len(failures)}): {failures}")
        return 1
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
