# Unity Command — Configuration Reference

Every environment variable, every file, every tunable. Validates against `config.py`, `bot.py`, `claude_api.py`, and `.claude/collab/*` as of the current commit.


> **⚠ REMOVED 2026-05-19** — The collab subsystem (claudecolab + Supabase shared brain + cross-Claude G/R task queue + `.claude/collab/` Python modules + `/brain/*` Flask endpoints) was deleted wholesale per operator directive. V4 is single-instance only. References below are retained as historical context but the features no longer exist.


---

## 1. Required environment variables

These two are validated at startup and the bot refuses to start without them.

### `DISCORD_TOKEN`
- **Source**: Discord Developer Portal → your application → Bot → Token → **Reset Token**
- **Format**: `^[A-Za-z0-9._-]{50,100}$` — base64-ish, 50–100 chars, no spaces or quotes
- **Validation**: `config.py:25` regex check; raises `ValueError("Invalid Discord token format...")` on failure
- **Where it's used**: `bot.start(config.discord_token)` in `bot.py:350`

### `POLLINATIONS_API_KEY` (new — preferred)
- **Source**: <https://enter.pollinations.ai> → sign in → generate a key
- **Format**:
  - `pk_<8-64 alphanumeric>` — **publishable** key (client-side safe, IP rate-limited: 3 req burst, 1/15s refill)
  - `sk_<8-64 alphanumeric>` — **secret** key (server-side only, no rate limits, can spend Pollen)
- **Validation**: `config.py` `POLLINATIONS_PK_RE` / `POLLINATIONS_SK_RE` regexes; `Config.__init__` raises `ValueError` on invalid format
- **Auth model**: sent as `Authorization: Bearer <key>` header on every request to `gen.pollinations.ai`
- **Where it's used**: `config.api_url = "https://gen.pollinations.ai/v1/chat/completions"`, `config.models_url = "https://gen.pollinations.ai/text/models"`, `config.image_url(...)` builds image URLs with `?key=<key>` query param

### `POLLINATIONS_TOKEN` (legacy — backward-compat fallback)
- **Source**: old `text.pollinations.ai` portal (now superseded; new users should get a `pk_`/`sk_` key)
- **Format**: `^[A-Za-z0-9]{16}$` — exactly 16 alphanumeric chars
- **Behavior**: if `POLLINATIONS_API_KEY` is unset but `POLLINATIONS_TOKEN` is set, the bot detects the legacy format and routes to the old endpoints (`text.pollinations.ai/openai?token=...` + `text.pollinations.ai/models` + `image.pollinations.ai/prompt/...`). A deprecation warning is logged at startup.
- **Recommendation**: rotate to a `pk_` or `sk_` key when convenient — the legacy stack may be retired by Pollinations without notice

---

## 2. Optional environment variables

### `CLAUDE_CHAT_CHANNEL_ID`
- **Default**: unset — the Claude CLI bridge stays disabled when this is empty (hardcoded `1389349100000120955` fallback removed 2026-05-19 per outer FINALIZED Persistence pass)
- **Type**: Discord channel ID (string, parsed via `int()`)
- **Purpose**: The single channel the Claude-CLI bridge uses
- **Effects when set**:
  - Bot does NOT auto-respond to messages in this channel (CLI-only)
  - All messages in this channel are recorded to the in-memory ring (`claude_api.claude_messages`)
  - Startup greeting fires here
- **Effects when unset**: `is_claude_channel` is always False, the bridge code path is bypassed entirely, no startup greeting, the Flask API still runs (so admin-bridge auth + `/healthz` + `/metrics` still work) but `/claude/post` will fail because there's no channel to post into

### `CLAUDE_API_PORT`
- **Default**: `5050` (string, parsed via `int()`)
- **Where**: `bot.py:116`
- **Effect**: port Flask binds to in `claude_api.run_api(port=5050)` — `app.run(host='0.0.0.0', port=port, threaded=True)`

### `ALLOWED_CHANNELS`
- **Format**: comma-separated channel IDs (no spaces enforced; `.strip()` runs anyway)
- **Where**: `config.py:68`
- **Behavior**:
  - **Empty / unset**: bot responds in every guild channel + every DM
  - **Set**: bot responds ONLY in guild channels whose ID is in the list; DMs always pass; the Claude-chat-channel skip logic runs **before** this check so the CLI channel is unaffected
- **Example**: `ALLOWED_CHANNELS=1234567890,9876543210`

### Admin bridge auth — `UNITY_USER_EMAIL` + `UNITY_USER_PASSWORD`
- **Read by**: `unity_mcp_server.py` (env-first; falls back to `.claude/user.json` `team_member` block when env is unset)
- **Effect**: every authenticated MCP/Flask call sends `Authorization: Basic <base64(email:password)>` so the bridge can resolve the admin's handle (`GFourteen` / `SpongeBong` / `Red` / `Alfreddo`) and inject it into the Discord message prefix
- **Format**: `UNITY_USER_EMAIL=<founder>@unityailab.com`, `UNITY_USER_PASSWORD=<temp-or-personal-password>`
- **First-connect flow**: operator issues a temp password via `python admin_cli.py issue <email>` (or `python configure.py --issue-admin-token <email>`); admin sets it in env, calls `unity_admin_set_password` MCP tool on first connect to swap it for a personal password, then updates `UNITY_USER_PASSWORD` in their MCP env
- **Where it's used**: `unity_mcp_server.py` `_auth_header()` + `claude_api.py` `require_admin_auth` decorator on `/claude/post` + `/claude/clear` + `/claude/admin/*`
- **Scope**: ONLY gates the Claude Code → Unity MCP bridge. Discord users + web UI chat users stay anonymous (no auth on `/api/chat` or Discord `on_message`). See [SECURITY.md §6.5](SECURITY.md) for the three-population model.
- **Override paths**: `ADMIN_CREDENTIALS_PATH` (default `logs/admin_credentials.json`) + `ADMIN_AUDIT_LOG` (default `logs/admin_audit.log`)

### Removed env vars (2026-05-19 collab gut)

The following env vars were read by V4's old collab subsystem and are NO LONGER honored by the runtime. Setting them in `.env` is harmless (they're ignored), but they appear in old configs:

- `SUPABASE_URL` — Supabase REST base (shared_knowledge + shared_tasks tables)
- `SUPABASE_ANON_KEY` — Supabase anon JWT
- `CLAUDE_AUTHOR` — `G` / `R` tag for the shared-brain author column
- `CLAUDE_COLLAB_KEY` — `cc_xxx` key from `claudecolab.com`

V4 is single-instance only now. The `.env.example` retains a REMOVED 2026-05-19 banner pointing operators at `docs/TROUBLESHOOTING.md` if a stale `.env` is mysteriously crashing the bot (it shouldn't — these are silently ignored).

---

## 3. Configuration files

### `.env` (gitignored)
- **Location**: project root
- **Created by**: `python configure.py` (cross-platform interactive prompt — recommended), or `linux/setup.sh` / `windows\setup.bat` (delegate to `configure.py` at the end), or manual edit
- **Format**: `KEY=value` lines, no quotes, no surrounding spaces, one per line. `configure.py` writes a sectioned file with `# ─── header ───` comments per group.
- **Example (new stack)**:
  ```env
  DISCORD_TOKEN=YourActualDiscordTokenHere
  POLLINATIONS_API_KEY=pk_YourPublishableKeyHere
  CLAUDE_CHAT_CHANNEL_ID=1234567890
  CLAUDE_API_PORT=5050
  # ALLOWED_CHANNELS=1234567890,9876543210
  # WEB_UI_ENABLED=1
  # WEB_UI_HOST=127.0.0.1
  # WEB_UI_PORT=5051
  ```
- **Example (legacy fallback)**:
  ```env
  DISCORD_TOKEN=YourActualDiscordTokenHere
  POLLINATIONS_TOKEN=A1B2C3D4E5F6G7H8
  ```
- **Precedence**: `load_dotenv(env_path, override=False)` — **system env vars win** over `.env` values when both are set
- **Discovery**: `os.path.join(os.path.dirname(__file__), '.env')` — must sit next to `config.py`
- **Re-configure later**: `python configure.py` is safe to re-run. It reads existing values, prompts with each as the default `[in brackets]`, and writes back only what changed. Use `python configure.py --print` to dump current values with secrets redacted.

### `system_instructions.txt`
- **Location**: project root (read via relative path `"system_instructions.txt"` in `config.py:59`)
- **Required**: yes — `Config.__init__` raises `FileNotFoundError` if missing
- **Content**: free-form system prompt — sent as the `system` role on every chat completion plus `\nYou are <model_name>.` appended
- **Default ships with**: full Unity persona definition (name, no-third-person rule, no-content-filtering, code-block format, image URL format with `seed`, Discord `<@USER_ID>` mentioning, bot-awareness)
- **Length**: no enforced cap, but it counts against Pollinations' input budget on every turn — keep it under ~2k chars for headroom

### `logs/admin_credentials.json`
- **Location**: `logs/admin_credentials.json` (gitignored, chmod 600 on POSIX)
- **Loaded by**: `admin_credentials.py` (bootstrap from `FOUNDERS` constant on first bot start if file missing; bcrypt-backed credential store thereafter)
- **Schema** (one entry per founder — Gee / Sponge / Red / Alfreddo):
  ```json
  {
    "Gee@unityailab.com": {
      "email": "Gee@unityailab.com",
      "handle": "GFourteen",
      "role": "Founder + FinAdvisor",
      "password_hash": "$2b$12$...",
      "force_reset": false,
      "created_at": "2026-05-19T...",
      "last_login": "2026-05-19T..."
    }
  }
  ```
- **Override path**: `ADMIN_CREDENTIALS_PATH` env var
- **Audit trail**: every authenticate / issue / set_password event appends to `logs/admin_audit.log` (gitignored, chmod 600). Override path via `ADMIN_AUDIT_LOG` env var.

### `logs/chat_data.json`
- **Location**: created at startup if missing (`DataManager.__init__`)
- **Format**: JSON with three top-level keys:
  ```json
  {
    "channels": {"<channel_id>": {"memories": [...], "history": [...]}},
    "user_models": {"<guild_id>": {"<user_id>": "<model_name>"}},
    "user_histories": {"<guild_id>": {"<user_id>": [...]}}
  }
  ```
- **Written**: after every message via `data_manager.save_data_async(memory_manager)` — async file I/O via `aiofiles`
- **Read**: once at startup by `setup_bot()` → `data_manager.load_data(memory_manager)`
- **Corruption recovery**: a bad JSON parse resets the in-RAM state to `{"channels": {}, "user_models": {}, "user_histories": {}}` and logs the error; **the file is NOT overwritten until the next message** so manual restore from backup is possible

### `logs/application.log`
- **Level**: `DEBUG` to file (`logging.basicConfig` in `bot.py:30`), `INFO` to console
- **Format**: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- **Rotation**: truncated to empty every 1 h by `wipe_logs_periodically()` — see [SKILL_TREE.md §8.2](SKILL_TREE.md)

---

## 4. Tunables in `config.py`

These are class attributes on `Config` set in `__init__`. Edit `config.py` directly; the bot reads them once at startup.

| Attribute | Default | Effect |
|-----------|---------|--------|
| `default_model` | `"unity"` | Fallback model name when a user has none set |
| `max_history` | `20` | Max conversation turns kept per ledger (channel / user / user-model) |
| `max_memories` | `5` | Max pinned channel notes via `!savememory` |
| `api_url` | new stack: `https://gen.pollinations.ai/v1/chat/completions` <br> legacy stack: `https://text.pollinations.ai/openai?token=<token>` | Pollinations chat endpoint — selected automatically by `detect_pollinations_stack()` based on key format |
| `models_url` | new stack: `https://gen.pollinations.ai/text/models` <br> legacy stack: `https://text.pollinations.ai/models` | Pollinations model-list endpoint |
| `image_base` | new stack: `https://gen.pollinations.ai/image` <br> legacy stack: `https://image.pollinations.ai/prompt` | Image-generation base URL (used by `Config.image_url(...)`) |
| `pollinations_stack` | `"new_pk"`, `"new_sk"`, or `"legacy"` | Stack classification — drives endpoint + auth selection |
| `code_block_regex` | `` r"```(\w*)\n([\s\S]*?)\n```" `` | Pattern for fenced code blocks in AI output |

_(Stale tunables — `code_keywords`, `image_keywords`, `is_code_request()`, `is_image_request()`, `extract_image_prompt()`, `memory_regex`, `url_regex` — were deleted from `config.py` per outer FINALIZED 2026-05-19 HIGH cleanup pass after they introduced false positives wiring conversational words into code-mode. Inline `'code' in user_message or 'script' in user_message` check in `message_handler.py` is the current behavior. `memory_regex` is the last dead-code attribute still pending decision — see TODO.md "V4 Bot pending — Code quality" section.)_

---

## 5. Tunables in `api_client.py`

| Attribute | Default | Effect |
|-----------|---------|--------|
| `retry_attempts` | `6` | Max retries on 429/5xx or network error |
| `retry_delay` | `2` (seconds) | Base delay — exponential is `retry_delay * 2^attempt + uniform(0, 0.1)` |

Per-request payload defaults in `send_message()`:

| Field | Value |
|-------|-------|
| `temperature` | `0.7` |
| `max_tokens` | `1024` |
| `stream` | `False` |
| Request timeout | `aiohttp.ClientTimeout(total=30)` |
| Models-fetch timeout | `15` |

---

## 6. Tunables in `bot.py`

| Location | Default | Effect |
|----------|---------|--------|
| `wipe_logs_periodically()` | `await asyncio.sleep(3600)` | Log rotation period (1 h) |
| `check_for_updates_periodically()` | `await asyncio.sleep(900)` | Auto-update check period (15 min) |
| `refresh_models_periodically()` | `await asyncio.sleep(21600)` | Pollinations model-list refresh period (6 h) |
| Bot-author delay | `await asyncio.sleep(10)` | Delay before responding to another bot |

---

## 7. Discord bot setup checklist

Before the bot will connect successfully:

1. **Create application + bot** at <https://discord.com/developers/applications>
2. **Enable privileged intents** in the Bot tab:
   - ✅ **MESSAGE CONTENT INTENT** (required — `intents.message_content = True`)
   - ✅ **SERVER MEMBERS INTENT** (required — `intents.members = True` for bot-detection)
   - PRESENCE INTENT: not required
3. **Reset Token** and copy it into `DISCORD_TOKEN`
4. **Generate OAuth2 URL** under OAuth2 → URL Generator:
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`, `Send Messages in Threads`, `Read Message History`, `Attach Files`, `Add Reactions`, `Embed Links`, `Use External Emojis` (optional)
5. **Invite to your server** with that URL
6. **Allow DMs from server members** — required for `!setmodel` (which DMs the chunked button UI)

---

## 8. Pollinations setup checklist (new gen.pollinations.ai stack)

1. Visit <https://enter.pollinations.ai>
2. Sign in (auto-assigns Seed tier on first login)
3. Generate an API key — choose:
   - **Publishable (`pk_xxx`)** if you're running the bot on shared infrastructure or want client-side-safe limits (3 req burst, 1 req / 15s refill)
   - **Secret (`sk_xxx`)** if you control the server end-to-end and want no rate limits (can spend Pollen)
4. Save it as `POLLINATIONS_API_KEY`
5. The key is sent as `Authorization: Bearer <key>` on every chat-completion request to `https://gen.pollinations.ai/v1/chat/completions`, and as `?key=<key>` on image-generation GETs to `https://gen.pollinations.ai/image/<prompt>`

If you have a legacy 16-char token from the old `text.pollinations.ai` portal, set `POLLINATIONS_TOKEN` instead and the bot will detect the format + use the legacy endpoints. A deprecation warning is logged at startup.

Image generation requires the key now (Pollinations enforces auth on the new stack). `Config.image_url(prompt, ...)` builds the complete URL with `?key=<key>` appended automatically — `system_instructions.txt` tells the model to emit the URL without the key, and the bot's runtime layers the key on.

---

## [Section removed] — collab subsystem deleted 2026-05-19

See top-of-doc banner. 

---

## 10. Configuration validation summary

| Surface | Validated? | Failure |
|---------|------------|---------|
| `DISCORD_TOKEN` format | ✅ regex | `ValueError` at startup |
| `POLLINATIONS_API_KEY` format (pk_/sk_) | ✅ regex via `detect_pollinations_stack` | `ValueError` at startup |
| `POLLINATIONS_TOKEN` legacy format (16-char) | ✅ regex via `detect_pollinations_stack` | `ValueError` at startup |
| `system_instructions.txt` presence | ✅ open() | `FileNotFoundError` at startup |
| `CLAUDE_CHAT_CHANNEL_ID` parseable | ⚠️ implicit (`int()`) | Channel-lookup fails at runtime, logged warning |
| `CLAUDE_API_PORT` parseable | ⚠️ implicit (`int()`) | Flask bind fails, exception in thread |
| `ALLOWED_CHANNELS` IDs valid | ❌ stored as strings, never parsed | Bad ID silently never matches |
| `.env` syntax | ❌ delegated to `python-dotenv` | Bad lines silently skipped |
| `chat_data.json` schema | ⚠️ JSON parse only | Corrupt file → reset to empty (logged) |
| Admin email/password (`UNITY_USER_EMAIL` + `UNITY_USER_PASSWORD`) | ✅ bcrypt-verified at every MCP/Flask write call via `require_admin_auth` decorator | 401 + `X-Force-Reset: true` header if `force_reset=true`; 401 otherwise on mismatch |

---

## 11. Related docs

- [SETUP.md](SETUP.md) — install + first-run walkthrough
- [SECURITY.md](SECURITY.md) — token handling + hardcoded-key findings
- [API.md](API.md) — Flask endpoint reference
- - [DEPLOYMENT.md](DEPLOYMENT.md) — systemd, auto-update, multi-host
