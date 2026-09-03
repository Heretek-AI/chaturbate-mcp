---
name: chaturbate
description: Drive the chaturbate MCP server (room stats, affiliate earnings, live events) to answer questions about a Chaturbate room's performance, earnings, or recent activity. Use when the user asks about a Chaturbate account's stats, tips, viewers, followers, broadcast history, affiliate payouts, or event streams, or when chaturbate tool names (fetch_room_stats, fetch_affiliate_stats, fetch_events, config_status, get_events_schema) come up.
---

# Chaturbate (chaturbate-mcp)

Use the `chaturbate` MCP server's tools to answer questions about the user's Chaturbate
account. All tools are read-only.

## Prerequisites

- The `chaturbate` MCP server is connected (`.mcp.json` at the repo root; approve under `/mcp` once).
- Credentials are set in `<repo>/.env` (see `.env.example`). Run `config_status` first to confirm
  which credential sets are ready — if `stats_configured`/`events_configured` are false, tools that
  need them will error with a credential message.

## Tool reference

| Tool | Purpose |
|---|---|
| `config_status` | Which credentials are configured (never prints values) |
| `fetch_room_stats` | Account/room snapshot (upstream ~5 min stale) |
| `fetch_affiliate_stats` | 9-program earnings report (raw JSON) |
| `fetch_events` | Poll the events feed; thread `next_url` to stream |
| `build_events_feed_url` | Construct a base feed URL (embeds the token!) |
| `get_events_schema` | The 12 event methods + object shapes, for interpreting events |

## Workflows

### 1. Room snapshot ("what's my room status / viewer count")
`config_status` → `fetch_room_stats`. Interpret:
- `last_broadcast: -1` = never broadcast; otherwise an ISO datetime.
- `time_online: -1` = offline now; otherwise minutes since going live.
- Numbers can be up to ~5 minutes old — don't present them as live.
- Unknown response keys are tolerated; pass them through to the user.

### 2. Affiliate earnings ("how much did I earn / how many signups")
`fetch_affiliate_stats` **without** date params unless the user explicitly asks for a custom
window. The default response covers the API's chosen range. Caveats to relay if relevant:
- Range/breakdown params are undocumented upstream and can trigger 403 throttling when sent
  rapidly — prefer the default, and if a 403 appears, retry without extra params.
- Earnings data is also refreshed on Chaturbate's ~5-minute cycle.

### 3. Live events ("what's happening in my room / new tips / follows")
The feed is cursor-based and stateless — thread the cursor yourself across calls:

```
1. fetch_events(timeout=0)                 # initial: recent events + next_url
2. fetch_events(next_url="<from step 1>")  # next batch, then repeat with the new next_url
```

- `events: []` with a valid `next_url` = nothing new in that window — poll again.
- Keep `timeout=0` for quick checks. A real wait is possible up to 90 s, but keep it ≤ 60 s so
  the MCP client's tool-call deadline isn't exceeded.
- Use `get_events_schema` to interpret each event's `method`/`object`. Key ones: `tip`
  (tokens, anon), `chatMessage`, `privateMessage`, `follow`/`unfollow`, `userEnter`/`userLeave`,
  `mediaPurchase`, `fanclubJoin`, `broadcastStart`/`broadcastStop`, `roomSubjectChange`.
- A quiet/empty feed is expected for an account that isn't currently broadcasting — not an error.

### 4. When tools error
Run `config_status` first. "Missing credentials" → point the user at `.env`. An HTTP error body
is redacted and safe to show.

## Secrets handling (hard rules)

- `fetch_events` output and `build_events_feed_url` return **URLs that embed the events token**.
  Never paste them verbatim into chat, files, or logs — redact the `/events/<username>/<token>/`
  segment when you must refer to them.
- Never read, print, or commit anything in `review/` (a saved authtoken page with live tokens) or
  `mitm_mcp_traffic.db`, and never print `CHATURBATE_*` values.

## Limits / gotchas

- Stats refresh ~every 5 min upstream.
- Affiliate date params are undocumented; 403 throttling risk under rapid odd-param requests.
- Events rate limit: 2000 requests/minute; long polls hold a connection open.
