"""Events-feed URL construction and validation.

The events feed URL carries the token in its path (``…/events/<username>/<token>/``),
so any URL this module emits or accepts must stay pinned to the official events host.
"""

from __future__ import annotations

from urllib.parse import quote

from .api import EVENTS_HOST


def events_feed_url(username: str, token: str, timeout: int | None = None) -> str:
    """Build the base long-poll feed URL for an account/token pair.

    ``timeout`` (0..90 s) is embedded as a query param; omit for the upstream
    default (10 s). The returned URL contains the events token — treat as secret.
    """
    url = f"{EVENTS_HOST}/events/{quote(username, safe='')}/{quote(token, safe='')}/"
    if timeout is not None:
        url = f"{url}?timeout={int(timeout)}"
    return url


def validate_events_url(url: str) -> str:
    """Ensure a caller-supplied ``next_url`` targets the official events host.

    Guards against a misdirected/forged URL smuggling the events token to a
    third-party host. Returns the URL unchanged when valid.
    """
    prefix = f"{EVENTS_HOST}/events/"
    if not url.startswith(prefix):
        raise ValueError(
            "next_url must be a chaturbate events feed URL on eventsapi.chaturbate.com "
            "obtained from a prior fetch_events call"
        )
    return url
