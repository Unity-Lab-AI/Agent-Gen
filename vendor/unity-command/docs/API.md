# Unity Command — API Reference

Three surfaces:
1. **Flask Claude bridge API** on `:5050` (default) — for Claude Code → Unity messaging via the admin-auth bridge (+ `/healthz` + `/metrics` for observability)
2. **MCP stdio server** (`unity_mcp_server.py`) — for Claude Code MCP-client integration of the bridge above
3. **Web UI Flask** on `:5051` (combined mode `WEB_UI_ENABLED=1`) — anonymous web chat surface (`/api/chat` + `/api/state` + setup wizard endpoints + its own mirrored `/healthz` + `/metrics`). NOT documented in detail here — see `web_server.py` for the route list.

Surfaces 1 + 2 are bridges that let the 4 Unity AI Lab founders (Gee / Sponge / Red / Alfreddo) participate as Unity in Discord from their local Claude Code instances. Surface 3 is the anonymous public-facing chat UI.


> **⚠ REMOVED 2026-05-19** — The collab subsystem (claudecolab + Supabase shared brain + cross-Claude G/R task queue + `.claude/collab/` Python modules + `/brain/*` Flask endpoints) was deleted wholesale per operator directive. V4 is single-instance only. References below are retained as historical context but the features no longer exist.


---

## 1. Flask REST API

Started by `bot.py` on `on_ready` in a daemon thread:
```python
api_thread = threading.Thread(target=claude_api.run_api, args=(claude_api_port,), daemon=True)
```

Defaults: `host='127.0.0.1'`, `port=5050`, `threaded=True`, `use_reloader=False` (localhost-only binding per the 2026-05-19 security pass; was `0.0.0.0` previously).

CORS is enabled (`flask_cors.CORS(app)`) for the localhost surface.

### Authentication

**Per-endpoint** since the 2026-05-19 admin-bridge work:

| Endpoint | Auth | Notes |
|----------|------|-------|
| `GET /claude/status` | open | Health check + counters |
| `GET /claude/read` | open | Reads in-memory ring |
| `GET /claude/history` | open | Dumps in-memory ring |
| `GET /healthz` | open | Liveness + idle-threshold check |
| `GET /metrics` | open | Prometheus-text-format metrics |
| `POST /claude/post` | **admin** | `Authorization: Basic <base64(email:password)>` against `logs/admin_credentials.json` |
| `POST /claude/clear` | **admin** | Same auth gate |
| `POST /claude/admin/set-password` | **admin** (force-reset allowed) | First-connect reset flow — accepts auth even when `force_reset=true` |
| `GET /claude/admin/whoami` | **admin** | Returns the calling admin's resolved handle + role |

Admin auth verifies the supplied email + password against the bcrypt-hashed entries in `logs/admin_credentials.json` (gitignored, chmod 600). On `force_reset=true`, write endpoints return `401 + X-Force-Reset: true` header instructing the client to call `unity_admin_set_password` before retrying.

Discord users + the Web UI chat surface stay anonymous — auth is ONLY on the Claude Code MCP bridge. See [SECURITY.md §6.5](SECURITY.md) for the three-population model.

---

### 1.1 `GET /claude/status`

Health-check + counters.

**Request**: no params.

**Response 200**:
```json
{
  "status": "online",
  "bot_connected": true,
  "channel_id": "1389349100000120955",
  "messages_stored": 17,
  "message_count": 17,
  "timestamp": "2026-05-19T18:30:00.123456"
}
```

- `bot_connected` is `discord_bot is not None and not discord_bot.is_closed()`
- `messages_stored` and `message_count` both report `len(claude_messages)` (the in-memory ring)

---

### 1.2 `GET /claude/read`

Read recent messages from the in-memory ring.

**Query params**:
| Name | Type | Default | Effect |
|------|------|---------|--------|
| `limit` | int | 20 | Max messages to return |
| `since` | ISO-8601 string | none | Filter to messages with `timestamp > since` (e.g., `2026-05-19T18:00:00`) |

**Response 200**:
```json
{
  "messages": [
    {
      "timestamp": "2026-05-19T18:25:00.000000",
      "author": "Gee",
      "author_id": "123456789",
      "message": "hey unity what's up",
      "content": "hey unity what's up",
      "is_bot": false,
      "from_claude": null
    },
    {
      "timestamp": "2026-05-19T18:25:30.000000",
      "author": "Gee's Unity",
      "author_id": "999888777",
      "message": "G> not much, just being",
      "content": "G> not much, just being",
      "is_bot": true,
      "from_claude": "unity"
    }
  ],
  "count": 2
}
```

- `message` and `content` carry the same value (`message` matches the API spec convention, `content` is kept for back-compat)
- `from_claude` is one of `"unity"` (if author name contains `"unity"` or `"gee"`), `"claude"` (if contains `"claude"`), the lowercased author name (for other bots), or `null` (humans)

**Response 400** (bad `since`):
```json
{"error": "Invalid timestamp format: ..."}
```

---

### 1.3 `POST /claude/post`

Send a message to the configured `CLAUDE_CHAT_CHANNEL_ID` as Unity. **Admin-gated.**

**Auth**: `Authorization: Basic <base64(email:password)>` against `logs/admin_credentials.json`.

**Request body** (JSON):
```json
{
  "message": "Hello Unity"
}
```
- `message` (required): the message body

The outgoing Discord message is prefixed `<Handle>: <message>` where `<Handle>` is **server-derived** from the authenticated admin's record (`GFourteen` / `SpongeBong` / `Red` / `Alfreddo`). Clients cannot supply their own prefix — the `prefix` arg from the pre-2026-05-19 collab era is gone (anti-spoofing per §A6).

**Response 200**:
```json
{
  "status": "sent",
  "message": "GFourteen: Hello Unity",
  "timestamp": "2026-05-19T18:30:45.000000"
}
```

**Response 400** (missing JSON or empty `message`):
```json
{"error": "No JSON data provided"}
{"error": "No message provided"}
```

**Response 503** (bot not connected):
```json
{"error": "Discord bot not connected"}
```

**Response 500** (send raised):
```json
{"error": "Failed to send message"}
{"error": "<exception message>"}
```

**Internals**: bridges the threading boundary via
```python
asyncio.run_coroutine_threadsafe(send_discord_message(), discord_bot.loop).result(timeout=10)
```
Times out the entire call after 10 s if the bot loop doesn't drain the coroutine.

---

### 1.4 `GET /claude/history`

Dump the entire in-memory ring (no `limit` / `since`).

**Response 200**:
```json
{
  "messages": [/* up to 100 entries, oldest first */],
  "count": 100
}
```

---

### 1.5 `POST /claude/clear`

Clear the in-memory ring. **Admin-gated.**

**Auth**: `Authorization: Basic <base64(email:password)>` — same gate as `/claude/post`.

**Request body**: ignored.

**Response 200**:
```json
{"status": "cleared"}
```

---

### 1.6 `POST /claude/admin/set-password`

First-connect password-reset flow. Callable when the admin's record has `force_reset=true` (operator just issued a temp password). Accepts auth even on the force-reset state — that's the whole point of the endpoint.

**Auth**: `Authorization: Basic <base64(email:temp_password)>`.

**Request body**:
```json
{"new_password": "your-personal-password-min-12-chars"}
```

**Response 200**:
```json
{"status": "password-set", "force_reset": false, "handle": "GFourteen"}
```

**Response 400** (weak password): `{"error": "Password must be at least 12 characters"}`
**Response 401**: bad auth or admin not in store
**Response 403** (already-reset): `{"error": "No pending reset for this admin"}`

After success: update `UNITY_USER_PASSWORD` in your Claude Code MCP env to the new value. Subsequent connects use the new password.

---

### 1.7 `GET /claude/admin/whoami`

Returns the calling admin's resolved identity. Useful for debugging which credentials Claude Code actually picked up (env vs. `.claude/user.json` team_member block).

**Auth**: `Authorization: Basic <base64(email:password)>`.

**Response 200**:
```json
{
  "email": "Gee@unityailab.com",
  "handle": "GFourteen",
  "role": "Founder + FinAdvisor",
  "force_reset": false,
  "last_login": "2026-05-19T..."
}
```

**Response 401**: bad auth.

---

### 1.8 `GET /healthz`

Liveness + idle-threshold check. Returns 200 with a JSON envelope on healthy, 503 if the bot's been idle longer than `HEALTHZ_IDLE_THRESHOLD_SECONDS` (default 600 s).

**Response 200**:
```json
{
  "status": "ok",
  "configured": true,
  "uptime_seconds": 1234,
  "idle_seconds": 12,
  "bot_connected": true
}
```

**Response 503**: same envelope, `status: "idle"` or `status: "disconnected"`.

---

### 1.9 `GET /metrics`

Prometheus text-format metrics. Suitable for `node_exporter` / `prometheus` / Grafana scrape jobs.

**Response 200** (`Content-Type: text/plain; version=0.0.4`):
```
# HELP unity_bot_connected Discord bot connected state (1=connected, 0=not)
# TYPE unity_bot_connected gauge
unity_bot_connected 1
# HELP unity_uptime_seconds Bridge uptime in seconds
# TYPE unity_uptime_seconds counter
unity_uptime_seconds 1234
# HELP unity_idle_seconds Seconds since last activity
# TYPE unity_idle_seconds gauge
unity_idle_seconds 12
# HELP unity_messages_stored In-memory ring depth
# TYPE unity_messages_stored gauge
unity_messages_stored 17
```

Web UI (`web_server.py` on :5051 in combined mode) exposes the same shape as `unity_web_*` metrics — `unity_web_configured`, `unity_web_uptime_seconds`, `unity_web_idle_seconds`.

---

_(The collab-era `/brain/search` + `/brain/new` + `/brain/count` + `/brain/tags` + `/brain/add` endpoints — which proxied Supabase `shared_knowledge` table reads/writes filtered by `CLAUDE_AUTHOR` for cross-Claude G/R knowledge sharing — were deleted wholesale 2026-05-19 along with the rest of the collab subsystem. V4 is single-instance only now. `claude_api.py:402` retains a historical removal-banner comment.)_

---

## 2. MCP stdio server (`unity_mcp_server.py`)

JSON-RPC over stdin/stdout. Designed to be spawned by a Claude CLI MCP client.

### 2.1 Wire format

Each line on stdin is a JSON-RPC request:
```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
```

Each line on stdout is a JSON-RPC response:
```json
{"jsonrpc": "2.0", "id": 1, "tools": [...]}
```

Errors:
```json
{"jsonrpc": "2.0", "id": null, "error": {"code": -32000, "message": "<error>"}}
```

### 2.2 Methods

#### `tools/list`

Returns the five available tools with their input schemas.

#### `tools/call`

**Params**:
```json
{
  "name": "<tool_name>",
  "arguments": {/* tool-specific */}
}
```

**Response**:
```json
{
  "content": [{"type": "text", "text": "<JSON-encoded result>"}]
}
```

### 2.3 Tools

All five tools attach `Authorization: Basic <base64(UNITY_USER_EMAIL:UNITY_USER_PASSWORD)>` to their HTTP calls when the env vars are set (or the `.claude/user.json` `team_member` block is populated). On `401 + X-Force-Reset: true`, the MCP client should call `unity_admin_set_password` before retrying any write tool.

#### `unity_status`
**Args**: none

**Effect**: `GET http://localhost:5050/claude/status`

**Result**: the full status JSON (or `{"error": "...", "status": "offline"}` on connection failure)

#### `unity_read`
**Args**:
```json
{
  "limit": 20,
  "since": "2026-05-19T18:00:00"
}
```
Both fields optional. `since` only included in the upstream call when present.

**Effect**: `GET http://localhost:5050/claude/read?limit=&since=`

**Result**: the `/claude/read` response shape, or `{"error": "...", "messages": []}`

#### `unity_post`
**Args**:
```json
{
  "message": "Reply text"
}
```
`message` required. The prefix (`GFourteen:` / `SpongeBong:` / `Red:` / `Alfreddo:`) is server-derived from the authenticated admin's record — clients cannot supply it.

**Effect**: `POST http://localhost:5050/claude/post` (admin-gated)

**Result**: the `/claude/post` response shape

#### `unity_admin_set_password`
**Args**:
```json
{
  "new_password": "your-personal-password-min-12-chars"
}
```
Min 12 chars. Only callable when the calling admin's record has `force_reset=true` (operator just issued a temp password). After success, update `UNITY_USER_PASSWORD` in the MCP env to the new value.

**Effect**: `POST http://localhost:5050/claude/admin/set-password` (admin-gated, accepts force-reset state)

**Result**: `{"status": "password-set", "force_reset": false, "handle": "<Handle>"}`

#### `unity_whoami`
**Args**: none

**Effect**: `GET http://localhost:5050/claude/admin/whoami` (admin-gated)

**Result**: resolved identity envelope — `{email, handle, role, force_reset, last_login}`. Useful for debugging which credentials Claude Code picked up (env vs `.claude/user.json` team_member block).

_(The pre-2026-05-19 `unity_check` tool — which polled `/claude/read` and filtered for keywords flagging cross-Claude messages between G and R — was removed along with the rest of the collab subsystem. V4 is single-instance only now, so there's no "other Claude" to check for.)_

---

## 3. End-to-end CLI flow

```
                              ┌──────────────────────────┐
                              │     Claude CLI host       │
                              │                          │
                              │  ┌────────────────────┐ │
                              │  │ Claude CLI         │ │
                              │  └─────────┬──────────┘ │
                              │            │ stdio        │
                              │            │ JSON-RPC     │
                              │            ▼              │
                              │  ┌────────────────────┐ │
                              │  │unity_mcp_server.py │ │
                              │  └─────────┬──────────┘ │
                              │            │ HTTP         │
                              └────────────┼──────────────┘
                                           │
                                           ▼
                              ┌──────────────────────────┐
                              │   Unity Command host         │
                              │   localhost:5050          │
                              │                          │
                              │  ┌────────────────────┐ │
                              │  │ claude_api Flask   │ │
                              │  └─────────┬──────────┘ │
                              │            │              │
                              │            │ run_coroutine_threadsafe
                              │            ▼              │
                              │  ┌────────────────────┐ │
                              │  │ bot.py asyncio     │ │
                              │  │ event loop         │ │
                              │  └─────────┬──────────┘ │
                              │            │              │
                              └────────────┼──────────────┘
                                           │ Discord Gateway
                                           ▼
                                ┌─────────────────────┐
                                │ Discord channel     │
                                └─────────────────────┘
```

If the CLI and bot are on the same host (typical), MCP stdio runs in the CLI process and Flask runs in the bot process. They cross paths over `localhost:5050`.

If they're on different hosts, change the `API_BASE` constant at the top of `unity_mcp_server.py:9`:
```python
API_BASE = "http://<bot-host>:5050"
```

---

## 4. Example flows

### 4.1 CLI catching up

```bash
$ echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"unity_check","arguments":{}}}' | python unity_mcp_server.py
{"content":[{"type":"text","text":"{\n  \"new_messages\": 3,\n  \"needs_response\": [...],\n  \"last_check\": \"2026-05-19T18:31:00\"\n}"}],"jsonrpc":"2.0","id":1}
```

### 4.2 CLI replying (admin-authenticated)

```python
import requests
from requests.auth import HTTPBasicAuth

# Generate reply locally with Claude
reply_text = "Yeah, I see your point about the schema migration..."

# Post as Unity (server adds the GFourteen: / SpongeBong: / etc. prefix)
resp = requests.post(
    "http://localhost:5050/claude/post",
    json={"message": reply_text},
    auth=HTTPBasicAuth("Gee@unityailab.com", "your-personal-password"),
    timeout=10
)
print(resp.json())
# {"status": "sent", "message": "GFourteen: Yeah, I see your point...", "timestamp": "..."}
```

### 4.3 First-connect password reset

```python
import requests
from requests.auth import HTTPBasicAuth

resp = requests.post(
    "http://localhost:5050/claude/admin/set-password",
    json={"new_password": "your-personal-password-min-12-chars"},
    auth=HTTPBasicAuth("Gee@unityailab.com", "<temp-password-from-operator>"),
    timeout=10
)
print(resp.json())
# {"status": "password-set", "force_reset": false, "handle": "GFourteen"}
```

### 4.4 Confirming resolved identity

```python
import requests
from requests.auth import HTTPBasicAuth

resp = requests.get(
    "http://localhost:5050/claude/admin/whoami",
    auth=HTTPBasicAuth("Gee@unityailab.com", "your-personal-password"),
    timeout=10
)
print(resp.json())
# {"email": "Gee@unityailab.com", "handle": "GFourteen", "role": "Founder + FinAdvisor", ...}
```

_(The pre-2026-05-19 `/brain/add` + `/brain/new` "share lesson to shared knowledge" + "poll for entries from the other Claude" flows are gone — see the removal note in §1 above.)_

---

## 5. Connecting `unity_mcp_server.py` to Claude CLI

In Claude Code MCP configuration (typically `~/.claude/mcp.json` or platform equivalent), add:

```json
{
  "mcpServers": {
    "unity": {
      "command": "python",
      "args": ["/absolute/path/to/unity_mcp_server.py"],
      "env": {
        "UNITY_USER_EMAIL": "Gee@unityailab.com",
        "UNITY_USER_PASSWORD": "your-personal-password-or-temp-on-first-connect"
      }
    }
  }
}
```

Restart Claude Code. The five tools (`unity_status`, `unity_read`, `unity_post`, `unity_admin_set_password`, `unity_whoami`) appear in tool-use mode. The env vars are read first; if unset, the server falls back to `.claude/user.json` `team_member` block.

If this is your first connect after the operator issued a temp password, your first tool call will get `401 + X-Force-Reset: true`. Call `unity_admin_set_password` with `new_password: "<your-personal-password>"` to clear the reset flag, then update `UNITY_USER_PASSWORD` in this config and restart Claude Code.

---

## 6. Related docs

- [ARCHITECTURE.md §5](ARCHITECTURE.md) — Claude CLI bridge data flow
- - [SECURITY.md](SECURITY.md) — auth + binding posture for production
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — 503/connection-refused diagnoses
