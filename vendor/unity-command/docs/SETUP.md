# Unity Command — Setup

Step-by-step install for both platforms. Covers token acquisition, dependency install, validation, and first launch. Auto and manual paths.

For deployment as a long-running service (systemd, auto-update, Windows scheduled task), see [DEPLOYMENT.md](DEPLOYMENT.md) after you complete first-launch verification here.


> **⚠ REMOVED 2026-05-19** — The collab subsystem (claudecolab + Supabase shared brain + cross-Claude G/R task queue + `.claude/collab/` Python modules + `/brain/*` Flask endpoints) was deleted wholesale per operator directive. V4 is single-instance only. References below are retained as historical context but the features no longer exist.


---

## 1. Prerequisites

| Need | Why | Verify |
|------|-----|--------|
| **Python 3.8 – 3.11** | `discord.py` 2.x compatibility; pinned at the upper end because some upstream wheels lag 3.12+ | `python --version` |
| **`pip`** | Package install | `python -m pip --version` |
| **Internet access** | Discord Gateway + Pollinations.ai (+ Forgejo `git.unityailab.com` for the 4 founders' admin-bridge SSH) | `curl -I https://discord.com` |
| **Discord developer application + bot** | Token | <https://discord.com/developers/applications> |
| **Pollinations.ai account + token** | Chat backend | <https://auth.pollinations.ai/> |
| **(Optional) Forgejo account at `git.unityailab.com`** | Required ONLY for the 4 Unity AI Lab founders connecting their Claude Code → Unity bridge (Gee / Sponge / Red / Alfreddo). Anonymous Discord + web users don't need this. | <https://git.unityailab.com> |

Privileged Discord intents you MUST enable on the bot:

1. **MESSAGE CONTENT INTENT** — without this, the bot can't read `message.content`
2. **SERVER MEMBERS INTENT** — without this, `detect_channel_bots()` returns empty

---

## 2. Get your tokens

### Discord token

1. Visit <https://discord.com/developers/applications>
2. **New Application** (top right) → name it (e.g., `UnityBot`)
3. Left nav → **Bot**
4. **Reset Token** → copy the resulting string (you only see it once)
5. Same page → enable **MESSAGE CONTENT INTENT** + **SERVER MEMBERS INTENT** under "Privileged Gateway Intents"
6. Left nav → **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`, `Read Message History`, `Attach Files`, `Add Reactions`, `Embed Links`
7. Open the generated URL → invite the bot to your server

### Pollinations.ai API key (new gen.pollinations.ai stack)

1. <https://enter.pollinations.ai>
2. Sign in (Seed tier is free and sufficient)
3. Generate a key — choose `pk_xxx` (publishable, client-side safe, rate-limited) or `sk_xxx` (secret, server-only, no limits)

If you have a legacy 16-char token from the old portal, the bot still supports it via `POLLINATIONS_TOKEN` — see [CONFIGURATION.md §8](CONFIGURATION.md). Migrate to a `pk_`/`sk_` key when convenient.

### (Optional) Discord channel ID for the Claude-CLI bridge

In Discord client: **Settings → Advanced → Developer Mode ON**, then right-click any channel → **Copy Channel ID**.

---

## 3. Get the code

```bash
git clone <repo-url> Unity Command
cd Unity Command
```

Or download the zip from your fork and extract into a folder.

---

## 4. Automated setup

### Linux (Ubuntu / Debian / Fedora / Alpine / Arch)

```bash
chmod +x linux/setup.sh
./linux/setup.sh
```

What it does:
1. Detects distro and installs system packages (`python3`, `python3-pip`, `python3-venv`, build tools) via `apt-get`, `yum`, `apk`, or `pacman`
2. Creates `.venv/` and activates it
3. Upgrades `pip` + `wheel`
4. `pip install -r requirements.txt`
5. **Delegates to `python configure.py`** for the interactive key prompts (Discord token + Pollinations API key + every optional key) — see [§4.5 below](#45-the-configurepy-interactive-prompt)

Non-interactive mode (skip prompts when env vars supply the required keys):
```bash
DISCORD_TOKEN=xxx POLLINATIONS_API_KEY=pk_xxx bash linux/setup.sh
```

Legacy fallback (if you only have the old 16-char token):
```bash
DISCORD_TOKEN=xxx POLLINATIONS_TOKEN=A1B2C3D4E5F6G7H8 bash linux/setup.sh
```

When it finishes you'll see `✅ Setup complete.` and a hint to `source .venv/bin/activate && python3 bot.py`.

### Windows

```cmd
windows\setup.bat
```

What it does:
1. Detects Python via `where python`. If missing, downloads `python-3.11.6-amd64.exe` from python.org and silent-installs it.
2. Verifies Python ≥ 3.8 (`PY_VER` parsed from `python -V`)
3. Creates `.venv/` and activates it
4. `pip install -r requirements.txt`
5. **Delegates to `python configure.py`** for the interactive key prompts — see [§4.5 below](#45-the-configurepy-interactive-prompt)

Non-interactive mode (skip prompts when env vars supply the required keys):
```cmd
set DISCORD_TOKEN=xxx
set POLLINATIONS_API_KEY=pk_xxx
windows\setup.bat
```

### 4.5 The `configure.py` interactive prompt

`configure.py` is the cross-platform Python script that handles all key entry. Both `linux/setup.sh` and `windows\setup.bat` delegate to it at the end of their flow; you can also run it standalone any time.

```bash
python configure.py                       # interactive — recommended for first-time setup
python configure.py --print               # dump current .env values (secrets redacted)
python configure.py --validate            # live-check keys against Discord + Pollinations APIs
python configure.py --detect-network      # detect + print public/local IP for Cloudflare setup
python configure.py --start-bot           # after setup, launch bot.py and tail logs for 15s
python configure.py --setup-cloudflare-tunnel  # automated Cloudflare Tunnel deployment
python configure.py --non-interactive     # CI-friendly — fail if required env missing
```

The default interactive flow now runs in 7 steps (after key entry): writes `.env` → **validates keys live against Discord `/users/@me` + Pollinations `/text/models`** → generates a Discord OAuth2 invite URL from the bot's user ID → **detects public + local IPv4** → optionally **starts bot.py in a subprocess** and tails for 15s confirming "connected to Discord!" appears in logs. No more "did setup actually produce a running bot?" mystery.

What it prompts for, in order:

1. **Required** — `DISCORD_TOKEN`, `POLLINATIONS_API_KEY` (or legacy `POLLINATIONS_TOKEN`)
2. **Claude CLI bridge (optional)** — `CLAUDE_CHAT_CHANNEL_ID`, `CLAUDE_API_PORT`
3. **Channel allowlist (optional)** — `ALLOWED_CHANNELS` (comma-separated guild channel IDs)
4. **Web UI (optional)** — `WEB_UI_ENABLED`, `WEB_UI_HOST`, `WEB_UI_PORT` (defaults `127.0.0.1:5051`)
5. **Admin Claude Code → Unity bridge (optional, founders only)** — `UNITY_USER_EMAIL`, `UNITY_USER_PASSWORD` (set per-admin in their Claude Code MCP env, NOT in the bot's `.env`). Operator issues the temp password separately via `python admin_cli.py issue <email>` (or `python configure.py --issue-admin-token <email>`); admin redeems it via the `unity_admin_set_password` MCP tool on first connect. See [USAGE.md §10](USAGE.md) + [SECURITY.md §6.5](SECURITY.md).

Each prompt:
- Shows the current value in `[brackets]` (redacted for secrets)
- Accepts Enter to keep the current value
- Validates format and re-prompts on rejection
- Honors environment variables for non-interactive override

The output `.env` is sectioned with comment headers so you can find values quickly. Unknown keys (e.g., custom env vars you added) are preserved in a "Custom" section at the bottom.

---

## 5. Manual setup (if you skip the scripts)

### POSIX

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip wheel
pip install -r requirements.txt
cp .env.example .env
# Edit .env in your editor of choice
```

### Windows (cmd / PowerShell)

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -U pip wheel
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Populate `.env` with at minimum:
```env
DISCORD_TOKEN=your_actual_discord_token_here
POLLINATIONS_API_KEY=pk_your_publishable_or_sk_secret_key_here
```

Or if you have a legacy 16-char token from the old portal:
```env
DISCORD_TOKEN=your_actual_discord_token_here
POLLINATIONS_TOKEN=YourLegacy16CharToken
```

If you want the Claude-CLI bridge:
```env
CLAUDE_CHAT_CHANNEL_ID=1234567890
CLAUDE_API_PORT=5050
```

If you want to restrict the bot to specific channels:
```env
ALLOWED_CHANNELS=1234567890,9876543210
```

If you want the web UI running alongside the Discord bot (combined mode):
```env
WEB_UI_ENABLED=1
WEB_UI_HOST=127.0.0.1
WEB_UI_PORT=5051
```

_(The collab subsystem env vars — `CLAUDE_AUTHOR`, `CLAUDE_COLLAB_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` — were removed 2026-05-19 along with the `.claude/collab/` modules + `/brain/*` Flask endpoints. V4 is single-instance only now. Old `.env` files that still carry these vars are harmless — the runtime ignores them.)_

---

## 6. First launch

### Quick run (Linux / macOS)

```bash
source .venv/bin/activate
python bot.py
```

### Quick run (Windows)

Double-click `windows\RUN_BOT.bat` or:
```cmd
.venv\Scripts\activate.bat
python bot.py
```

`windows\RUN_BOT.bat` checks Python version, does a quick `pip install -r requirements.txt --quiet`, then runs `python bot.py`.

### What you should see

1. Console log: `Loaded N models: ['unity', 'mistral', ...]`
2. Console log: `<BotName> has connected to Discord!`
3. Console log: `Claude API running on http://localhost:5050`
4. If `CLAUDE_CHAT_CHANNEL_ID` is reachable, the bot posts a startup greeting in that channel
5. File appears: `logs/application.log` + `logs/chat_data.json` (the latter empty)

### What you should NOT see

- `ValueError: Invalid Discord token format` → check the token has no whitespace and isn't `YourDiscordTokenHere` or similar placeholder
- `ValueError: Invalid Pollinations token format` → token must be exactly 16 alphanumeric chars
- `FileNotFoundError: system_instructions.txt not found` → run the bot from the project root, not from a subdirectory
- `discord.errors.LoginFailure: Improper token has been passed` → token was reset in Discord portal; regenerate it
- `discord.errors.PrivilegedIntentsRequired` → flip the privileged intent toggles in the Discord portal

---

## 7. Verifying it works

### Smoke test the chat path

In any channel where the bot is present (and in `ALLOWED_CHANNELS` if set), send:
```
hey unity, how's it going
```

Expected: a reply tagged to you (`<@your_id> ...`), `200` in `logs/application.log` for the Pollinations call, a new entry in `logs/chat_data.json`.

### Smoke test commands

```
!unityhelp
```
Expected: an embed listing commands and available models.

```
!setmodel
```
Expected: bot sends `check your DMs for model selection` in-channel, then DMs you a paginated set of model-buttons.

### Smoke test the Claude API

```bash
curl http://localhost:5050/claude/status
```
Expected:
```json
{
  "status": "online",
  "bot_connected": true,
  "channel_id": "<your CLAUDE_CHAT_CHANNEL_ID value>",
  "messages_stored": 0,
  "message_count": 0,
  "timestamp": "2026-..."
}
```

### Smoke test the MCP server (optional)

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python unity_mcp_server.py
```
Expected: a JSON-RPC response listing `unity_status`, `unity_read`, `unity_post`, `unity_admin_set_password`, `unity_whoami` (five tools). The collab-era `unity_check` tool was removed 2026-05-19 along with the rest of the cross-Claude polling subsystem.

---

## 8. Common first-launch gotchas

| Symptom | Cause | Fix |
|---------|-------|-----|
| Bot connects but never replies | `ALLOWED_CHANNELS` set and your test channel isn't in it | Either add the channel ID or remove `ALLOWED_CHANNELS` from `.env` |
| Bot connects but says "Error: API client not initialized" | `api_client.initialize()` race with first message | Restart — the bot creates the `aiohttp.ClientSession` on `on_connect` |
| `!setmodel` fails silently | Discord DMs are blocked | In Discord: **User Settings → Privacy & Safety → Allow direct messages from server members** |
| Claude API returns 503 | `discord_bot.is_closed()` returned `True` | Bot disconnected; check `logs/application.log` for the disconnect reason |
| Pollinations returns "API unreachable after retries" | Outage / token revoked / rate-limited | Hit <https://text.pollinations.ai/models> in your browser; if that fails too, wait or regenerate token |
| Bot replies in third person ("I, Unity, ...") | Model isn't following the persona prompt | Try a different model via `!setmodel` (`mistral`, `openai-large`, etc.); some respect persona instructions better than others |
| Auto-update kills the bot mid-conversation | `linux/update.sh` / `windows\update.bat` stops the service or `python.exe` | Expected during updates; systemd restarts it. If running ad-hoc, accept the interruption or remove the auto-update background task |

---

## 9. Alternate surfaces — Web UI + Terminal CLI

Unity Command ships with two non-Discord surfaces alongside the Discord bot. Both reuse the same `Config` + `.env` you just set up.

### Web UI (recommended for fresh setup)

The Web UI's setup wizard is the most layman-friendly way to configure Unity Command. Multi-step walkthrough in plain English, validates each field as you type, gives detailed instructions for getting each key.

```bash
# Linux/macOS
./linux/start_web.sh

# Windows
windows\start_web.bat
```

Opens `http://localhost:5051` in your default browser. If `.env` isn't configured yet, the page boots into setup-wizard mode automatically. Once saved, the page transitions to the chat UI. Re-enter setup any time via the **⚙ Setup** button.

### Terminal CLI (for headless servers)

```bash
python unity_cli.py
```

A SSH-friendly REPL with auto-detected inline image rendering (chafa / viu / kitty's icat). Falls back to printing the Pollinations URL prominently if no renderer is available. See [USAGE.md §9](USAGE.md) for the full command reference.

### Combined mode — Discord bot + Web UI

Set `WEB_UI_ENABLED=1` in `.env`. Running `python bot.py` then spawns the Web UI in a background thread on port 5051 (configurable via `WEB_UI_HOST` + `WEB_UI_PORT`). Useful when you want to monitor + interact with the bot via the browser while it's running its Discord workload.

---

## 10.5 Production deployment behind Cloudflare

The canonical production target is **<https://www.unity.unityailab.com>** — served from a Linux origin via Cloudflare Tunnel. Full walkthrough lives in [CLOUDFLARE.md](CLOUDFLARE.md). Quick summary:

1. Install `cloudflared` on the origin host
2. `cloudflared tunnel login` + `cloudflared tunnel create unity-bot-prod`
3. `cloudflared tunnel route dns unity-bot-prod www.unity.unityailab.com`
4. Drop `/etc/cloudflared/config.yml` pointing the tunnel at `http://localhost:5051`
5. `cloudflared service install` + `systemctl enable --now cloudflared`
6. Confirm with `curl -I https://www.unity.unityailab.com/api/health`

The bot stays bound to `127.0.0.1:5051` (default) — no firewall holes, no public IP needed, Cloudflare handles TLS + DDoS protection. See [CLOUDFLARE.md §1](CLOUDFLARE.md) for every step in detail.

## 11. Where to go next

- [USAGE.md](USAGE.md) — every command + natural-chat pattern
- [CONFIGURATION.md](CONFIGURATION.md) — every tunable
- [DEPLOYMENT.md](DEPLOYMENT.md) — run as a systemd service / Windows Scheduled Task
- [SECURITY.md](SECURITY.md) — token hygiene + the hardcoded-key findings to remediate before going public
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — wider failure-mode catalog
