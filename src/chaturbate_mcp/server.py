"""MCP server exposing Chaturbate's room-stats, affiliate, and events APIs as tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import __version__
from .api import ApiError
from .api import fetch_affiliate_stats as api_affiliate_stats
from .api import fetch_events_feed as api_events_feed
from .api import fetch_room_stats as api_room_stats
from .config import get_config, project_root, resolve_account
from .events_schema import events_schema_markdown
from .events_util import events_feed_url, validate_events_url


def build_server() -> MCPServer:
    server = MCPServer(
        name="chaturbate",
        version=__version__,
        description=(
            "Read-only access to Chaturbate room stats, affiliate earnings, and the live "
            "events feed for a Chaturbate account."
        ),
    )

    def creds(username: str | None, token: str | None, *, events: bool = False) -> tuple[str, str]:
        """Resolve credentials, surfacing a clear tool error when any half is missing."""
        try:
            return resolve_account(username, token, events=events)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    async def _api(awaitable: Any) -> Any:
        """Run an API call, converting transport failures into tool errors."""
        try:
            return await awaitable
        except ApiError as exc:
            raise ToolError(str(exc)) from exc

    @server.tool()
    async def config_status() -> dict[str, Any]:
        """Report which Chaturbate credentials are configured. Never prints secrets.

        Use this first to confirm the server is ready before calling the other tools.
        Returns booleans (not token values), the configured username, and where the
        environment was loaded from.
        """
        cfg = get_config()
        return {
            "username": cfg.username,
            "stats_configured": cfg.stats_configured,  # same token also authorizes affiliate API
            "events_configured": cfg.events_configured,
            "env_source": str(project_root() / ".env"),
        }

    @server.tool()
    async def fetch_room_stats(username: str | None = None, token: str | None = None) -> dict[str, Any]:
        """Fetch the current Chaturbate room/account stats snapshot.

        Args:
            username: Chaturbate username. Defaults to CHATURBATE_USERNAME.
            token: Stats-API token. Defaults to CHATURBATE_STATS_TOKEN.

        Returns the raw JSON object (unknown keys are passed through). Chaturbate
        refreshes this snapshot about every 5 minutes, so numbers can lag reality by
        up to 5 minutes. ``last_broadcast`` is an ISO datetime or -1 if never;
        ``time_online`` is minutes, or -1 when offline.
        """
        u, t = creds(username, token)
        return await _api(api_room_stats(u, t))

    @server.tool()
    async def fetch_affiliate_stats(
        username: str | None = None,
        token: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        breakdown: str | None = None,
    ) -> dict[str, Any]:
        """Fetch the Chaturbate affiliate-earnings report (all 9 programs).

        Args:
            username: Chaturbate username. Defaults to CHATURBATE_USERNAME.
            token: Stats token (same token authorizes this endpoint). Defaults to env.
            start_date: Best-effort YYYY-MM-DD filter — undocumented upstream; omit normally.
            end_date: Best-effort YYYY-MM-DD filter — undocumented upstream; omit normally.
            breakdown: Best-effort breakdown type — undocumented upstream; omit normally.

        Returns the raw payload: ``{"stats": [9 program tables], "range", "breakdown"}``.
        Only username+token are sent by default. Upstream treats range params as
        undocumented and unreliable — rapid requests carrying them can trigger 403
        throttling. If you get a 403, retry without start_date/end_date/breakdown.
        """
        u, t = creds(username, token)
        extra = {
            k: v
            for k, v in (
                ("start_date", start_date),
                ("end_date", end_date),
                ("breakdown", breakdown),
            )
            if v is not None
        }
        return await _api(api_affiliate_stats(u, t, extra))

    @server.tool()
    async def fetch_events(
        timeout: int = 0,
        next_url: str | None = None,
        username: str | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        """Poll the live Chaturbate events feed (one request, no client state kept).

        Args:
            timeout: Seconds the server holds the request for new events, 0..90.
              Default 0 returns immediately (recommended — a long poll can exceed the
              MCP client's tool-call deadline). Empty ``events`` + a valid
              ``next_url`` means "nothing new in the window".
            next_url: Feed URL from a previous call; pass it back to advance the
              cursor. It embeds the events token — treat output as secret.
              When given, username/token/timeout are ignored.
            username: Chaturbate username. Defaults to CHATURBATE_USERNAME.
            token: Events-scope token. Defaults to CHATURBATE_EVENTS_TOKEN.

        Returns ``{"events": [...], "next_url": str}``. Streaming recipe: call once
        (no next_url) to get recent events + a cursor, then keep passing that
        ``next_url`` back to receive the next batch. Each event is
        ``{"method", "id", "object"}`` — see get_events_schema for shapes.
        """
        if not 0 <= timeout <= 90:
            raise ToolError("timeout must be between 0 and 90 seconds")
        if next_url:
            try:
                url = validate_events_url(next_url)
            except ValueError as exc:
                raise ToolError(str(exc)) from exc
        else:
            u, t = creds(username, token, events=True)
            url = events_feed_url(u, t, timeout)
        data = await _api(api_events_feed(url))
        if "events" not in data or "nextUrl" not in data:
            raise ToolError("Unexpected events-feed payload: missing 'events' or 'nextUrl'")
        return {"events": data["events"], "next_url": data["nextUrl"]}

    @server.tool()
    async def build_events_feed_url(
        timeout: int | None = None,
        username: str | None = None,
        token: str | None = None,
    ) -> str:
        """Build the events-feed base URL for the configured account.

        Args:
            timeout: Long-poll seconds 0..90 to embed; omit for the upstream default (10 s).
            username: Chaturbate username. Defaults to CHATURBATE_USERNAME.
            token: Events-scope token. Defaults to CHATURBATE_EVENTS_TOKEN.

        Returns a URL you can pass to fetch_events(next_url=...). WARNING: the URL
        contains the events token — treat it as sensitive and do not echo it
        verbatim in chat or files.
        """
        if timeout is not None and not 0 <= timeout <= 90:
            raise ToolError("timeout must be between 0 and 90 seconds")
        u, t = creds(username, token, events=True)
        return events_feed_url(u, t, timeout)

    @server.tool()
    async def get_events_schema() -> str:
        """Reference: the 12 events-feed methods and their object shapes.

        Call this to interpret raw events returned by fetch_events. Returns a
        markdown table mapping each method to the fields on ``event["object"]``.
        """
        return events_schema_markdown()

    return server


def main() -> None:
    """Entry point: run the stdio MCP server (blocking)."""
    build_server().run()


if __name__ == "__main__":
    main()
