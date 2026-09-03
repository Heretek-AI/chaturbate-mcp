# chaturbate-mcp

Read-only MCP server for Chaturbate's room-stats, affiliate-earnings, and live events APIs,
plus a companion Claude Code skill. See `README.md` for setup and tool docs.

## Layout

- `src/chaturbate_mcp/` — Python package (mcp 2.x `MCPServer` + `httpx2`).
  - `server.py` — the 6 MCP tools (`config_status`, `fetch_room_stats`, `fetch_affiliate_stats`,
    `fetch_events`, `build_events_feed_url`, `get_events_schema`) and the `main()` entry point.
  - `config.py` — env + `.env` loading, `resolve_account()` credential resolution.
  - `api.py` — httpx2 GET helpers for the three endpoints; `ApiError` with redacted URLs.
  - `events_schema.py` — the 12 event methods and their object shapes.
  - `events_util.py` — events feed URL builder + host pinning for `next_url`.
- `tests/` — offline pytest suite (uses `httpx2.MockTransport`; no network, no tokens).
- `scripts/smoke_test.py` — live smoke test against the real API.
- `.claude/skills/chaturbate/SKILL.md` — companion skill.

## Hard rules (secrets)

- **Never read, print, or commit anything under `review/`** — it is a saved copy of the user's
  Chaturbate authtoken page and contains **live API tokens**. It is gitignored; keep it that way.
- **Never commit `mitm_mcp_traffic.db`** (captured traffic; gitignored).
- **Never commit `.env`** or echo `CHATURBATE_*` values. Only `.env.example` (placeholders) is committed.
- Events `next_url` values embed the events token — redact `/events/<user>/<token>/` when quoting.
- The smoke test reads tokens from `review/…html` strictly in memory and prints PASS/FAIL summaries
  only. Do not add logging that dumps credentials or raw feed URLs.

## Tool/API gotchas

- Stats snapshots refresh ~every 5 minutes upstream.
- Affiliate `start_date`/`end_date`/`breakdown` params are undocumented; rapid requests with them can
  trigger HTTP 403 throttling. Default tool behavior sends only `username`+`token`.
- `fetch_events` is stateless: thread the returned `next_url`. Default `timeout=0` (quick peek);
  long polls (up to 90 s) may exceed client tool-call deadlines.
