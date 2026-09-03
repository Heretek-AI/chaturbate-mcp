# chaturbate-mcp

Read-only [MCP](https://modelcontextprotocol.io) server exposing three Chaturbate APIs as
tools, for use from Claude Code or any MCP client (e.g. lobehub):

| API | Endpoint | Tool | Data |
|---|---|---|---|
| Room/user stats | `chaturbate.com/statsapi/` | `fetch_room_stats` | viewers, token balance, satisfaction score, broadcast status… (refreshes ~every 5 min) |
| Affiliate earnings | `chaturbate.com/affiliates/apistats/` | `fetch_affiliate_stats` | per-program earnings tables (9 programs), totals, payout |
| Events feed | `eventsapi.chaturbate.com/events/…` | `fetch_events`, `build_events_feed_url`, `get_events_schema` | live long-poll stream: chat, tips, follows, media purchases, private messages… |

Built with the official Python MCP SDK (`mcp` ≥ 2.1, the release that renamed `FastMCP` →
`MCPServer`) and `httpx2`.

## Requirements

- Python ≥ 3.10 (developed on 3.14)
- [uv](https://docs.astral.sh/uv/)

## Install

```sh
uv sync --dev
```

## Configure

Copy `.env.example` to `.env` and fill in your Chaturbate account values:

```sh
cp .env.example .env   # then edit
```

Credentials are read from the environment, with `.env` as a local convenience:

- `CHATURBATE_USERNAME` — your Chaturbate account
- `CHATURBATE_STATS_TOKEN` — Stats-API scope token. The **same token** authorizes both the
  room-stats and the affiliate-earnings endpoints.
- `CHATURBATE_EVENTS_TOKEN` — Events-API scope token for the live feed. A *private* scope
  exposes tips + private messages; a *public* scope omits them.

Create/manage tokens at `https://chaturbate.com/statsapi/authtoken/`.

`.env` is gitignored. **Never commit a real token.**

## Run

Start the stdio server manually:

```sh
uv run chaturbate-mcp
```

For Claude Code, a project-scoped entry is committed in `.mcp.json` (launches via `uv`, no
secrets in the config — the server reads them from `.env`). Approve the `chaturbate` server
once under `/mcp`.

## Tools

| Tool | Purpose |
|---|---|
| `config_status` | Which credential sets are configured (booleans, never values) |
| `fetch_room_stats` | One-shot stats snapshot (optionally override `username`/`token`) |
| `fetch_affiliate_stats` | 9-program earnings report. Sends **only** username+token unless you supply `start_date`/`end_date`/`breakdown` (undocumented upstream — see note) |
| `fetch_events` | Stateless long-poll of the events feed; thread `next_url` to stream |
| `build_events_feed_url` | Return the base feed URL for explicit cursor control |
| `get_events_schema` | Reference table of the 12 event methods and their object shapes |

### Streaming events

The events feed is cursor-based and stateless:

1. `fetch_events(timeout=0)` → returns `{events, next_url}` (recent events + a cursor).
2. Pass that `next_url` back to `fetch_events(next_url=…)` to receive the next batch.
3. `events: []` + a valid `next_url` means *nothing new in the window* — poll again.

`timeout` (0–90 s) is how long the server waits for new events before returning. Default to
`0` for a quick peek; a long poll can exceed an MCP client's tool-call deadline.

The companion skill `.claude/skills/chaturbate/` documents these workflows for Claude Code.

## Tests

Offline unit tests (no network, no tokens):

```sh
uv run pytest -q
```

Live smoke test against the real API — it reads the account/tokens from
`review/Stats Token Authorization - Chaturbate.html` **in memory** (or `CHATURBATE_*` env) and
never prints or persists them:

```sh
uv run python scripts/smoke_test.py
```

## Security notes

- `review/` (a saved copy of your authtoken page — contains live tokens) and
  `mitm_mcp_traffic.db` are **gitignored** and must never be committed. See `CLAUDE.md`.
- Real tokens live only in `.env` (gitignored) or the environment.
- Events `next_url` values embed the events token. Treat tool output as sensitive: do not
  echo feed URLs verbatim into chat, logs, or files.
- API error messages are redacted before they reach the client.

## Caveats

- **Stats are ~5 minutes stale** upstream; don't treat a single snapshot as live.
- **Affiliate date-range params are undocumented** and unreliable — Chaturbate can answer
  rapid requests carrying them with HTTP 403 (throttling). The tool sends none by default.
- The affiliate/room-stats data refreshes once every ~5 minutes regardless of request rate.
- The events feed rate limit is 2000 requests/minute.
