# Unity Command — Troubleshooting

Symptoms → causes → fixes. Organized by where things go wrong: startup, runtime, the Flask API, auto-update, deployment, and a final §6 "Collab migration" section for operators upgrading from pre-2026-05-19 `.env` files.

For preventive checks before deploying, see [SETUP.md §7](SETUP.md). For security-related failures (token rotation, leaked keys), see [SECURITY.md](SECURITY.md).


> **⚠ REMOVED 2026-05-19** — The collab subsystem (claudecolab + Supabase shared brain + cross-Claude G/R task queue + `.claude/collab/` Python modules + `/brain/*` Flask endpoints) was deleted wholesale per operator directive. V4 is single-instance only. References below are retained as historical context but the features no longer exist.


---

## 1. Startup failures

### `ValueError: Invalid Discord token format. Ensure no spaces, quotes, or invalid characters.`
- **Cause**: `DISCORD_TOKEN` doesn't match `^[A-Za-z0-9._-]{50,100}$`
- **Common reasons**: token wrapped in quotes, trailing space, copy-paste pulled an extra char, value is still the placeholder `YourDiscordTokenHere`
- **Fix**: open `.env`, strip quotes and whitespace, verify length is 50–100 chars
- **Where checked**: `config.py:25`

### `ValueError: Invalid Pollinations token format. Ensure it's correct and no invalid characters.`
- **Cause**: `POLLINATIONS_TOKEN` doesn't match `^[A-Za-z0-9]{16}$`
- **Common reasons**: token includes `-` or `_` (none allowed), wrong length (not 16 chars)
- **Fix**: re-generate at <https://auth.pollinations.ai/> → **[Re]Generate Token**, copy the exact 16-char value
- **Where checked**: `config.py:42`

### `DISCORD_TOKEN not found in environment variables`
- **Cause**: `.env` missing or `DISCORD_TOKEN=` line absent
- **Fix**: copy `.env.example` to `.env`, edit the file. Verify by running `python -c "import os; print(os.getenv('DISCORD_TOKEN'))"` from the project root

### `POLLINATIONS_TOKEN not found in environment variables`
- Same shape as above — check `.env` for `POLLINATIONS_TOKEN=` line

### `FileNotFoundError: system_instructions.txt not found`
- **Cause**: `Config.__init__` opens `system_instructions.txt` via relative path; the bot is being run from a different working directory
- **Fix**: `cd` to the project root before running `python bot.py`. Or set `WorkingDirectory=<path>` in the systemd unit (already done by `linux/install.sh`).

### `discord.errors.LoginFailure: Improper token has been passed`
- **Cause**: token regex passed but Discord rejected the value at runtime
- **Reasons**:
  - Token was regenerated in the Discord portal after you copied it → reset again, update `.env`
  - Token belongs to a different application than the one invited to your server
  - Bot user was deleted
- **Fix**: <https://discord.com/developers/applications> → your app → Bot → **Reset Token** → update `.env` → restart bot

### `discord.errors.PrivilegedIntentsRequired`
- **Cause**: `intents.message_content = True` or `intents.members = True` is set in code but the toggle is OFF in the developer portal
- **Fix**: <https://discord.com/developers/applications> → your app → Bot → "Privileged Gateway Intents" → enable both **MESSAGE CONTENT INTENT** and **SERVER MEMBERS INTENT** → restart bot

### `Loaded 0 models: []`
- **Cause**: Pollinations `/models` endpoint failed at startup
- **Fix**: bot falls back to `[{"name": "unity", "description": "Default unity model"}]` — chat still works on `unity`. Restart the bot once Pollinations is reachable to re-fetch the model list.

---

## 2. Runtime failures

### Bot connects but never responds to messages
- **Check 1**: Is the channel in `ALLOWED_CHANNELS`? If env is set, channels NOT in the list are silently ignored. Either add the channel or unset `ALLOWED_CHANNELS`.
- **Check 2**: Is the channel `CLAUDE_CHAT_CHANNEL_ID`? If yes, the bot only records messages, never auto-responds. Test in a different channel.
- **Check 3**: Are MESSAGE CONTENT and SERVER MEMBERS intents enabled in the developer portal AND in the code's `intents = ...` block? Disabled intents make `message.content` always empty.
- **Check 4**: `logs/application.log` shows `Received message from ...` lines? If no, the bot isn't seeing messages at all — intents issue. If yes, the bot is filtering or erroring downstream — check next log lines for the cause.

### `<@user> Error: API client not initialized`
- **Cause**: `message_handler.api_client` is `None` — happens if `on_message` fires before `on_connect` initialized the `aiohttp.ClientSession`
- **Fix**: usually resolves on its own after the first second of bot uptime. If persistent, check `logs/application.log` for an exception during `api_client.initialize()`.

### `<@user> Error: Failed to fetch response - <exception>`
- **Cause**: `api_client.send_message` raised an unhandled exception
- **Common reasons**: malformed `messages` list, payload too big, network broken
- **Fix**: check `logs/application.log` for the full traceback. If it's a payload-too-big issue, `!wipe` and try again (rolling history rebuild).

### `<@user> Empty response from API—please try again later.`
- **Cause**: `ai_response_clean` evaluated to empty string — usually means Pollinations returned only stripped content (just `---` separators, just `Generated by ...`, etc.)
- **Fix**: usually transient. Try a different model via `!setmodel`.

### `<@user> Error: Upstream API unreachable after retries`
- **Cause**: 6 retries with exponential backoff all failed against Pollinations
- **Reasons**: Pollinations is down, token revoked, rate-limited too hard
- **Fix**: hit <https://text.pollinations.ai/models> in browser to confirm reachability; rotate token if it's been a while

### `<@user> Error: Invalid response format <KeyError>`
- **Cause**: Pollinations returned a 200 but the JSON didn't have `choices[0].message.content`
- **Fix**: check `logs/application.log` for the raw response. If Pollinations changed their API shape, `api_client.send_message` needs an update.

### `!setmodel` does nothing / `please enable DMs from server members`
- **Cause**: user has DMs blocked from server members
- **Fix**: user → **Discord settings → Privacy & Safety → Allow direct messages from server members** (server-specific override available too)

### `!savememory` saves but isn't reflected in chat
- **Cause**: channel memories are prepended only on the NEXT chat completion
- **Fix**: not actually a bug — send another message in that channel; the memory will be in context

### Code blocks not formatted correctly
- **Cause**: model didn't emit `[CODE]<lang>...[/CODE]` markers (it ignored that part of `system_instructions.txt`)
- **Fix**: re-prompt with explicit instruction ("use [CODE] python ... [/CODE] format") or switch to a model that follows the system prompt better

### Images not attaching
- **Check 1**: Did the model include a URL in its response? Look at the raw response (briefly logged at INFO level by `MessageHandler`).
- **Check 2**: Did the URL fetch return 200? `logs/application.log` has `Failed to fetch image from <url>: status N` lines on failure.
- **Check 3**: Is the URL hostname reachable from the bot host? `curl -I <url>` from the host.

### Bot replies in third person ("I, Unity, ...")
- **Cause**: model isn't holding the persona's no-third-person rule
- **Fix**: switch models via `!setmodel`. `unity`, `dolphin-mistral`, `evil` tend to do better; `mistral` and lighter `openai-*` variants tend to drift

### Bot disconnects every few minutes / reconnects
- **Cause**: network instability between the bot host and Discord Gateway
- **Diagnosis**: `logs/application.log` shows `Bot disconnected from Discord` / `Bot connected to Discord` cycles
- **Fix**:
  - Check host network stability (`ping discord.com`)
  - Check if the host is behind a flaky NAT
  - `discord.py` auto-reconnects — the cycles aren't fatal but may cause missed messages

---

## 3. Flask API failures

### `curl http://localhost:5050/claude/status` → connection refused
- **Cause 1**: bot isn't running → start it
- **Cause 2**: bot started but the Flask thread failed to start → check `logs/application.log` for the `Claude API running on http://localhost:5050` line. If absent, the thread crashed.
- **Cause 3**: `CLAUDE_API_PORT` set to something else → check `.env`, try that port instead

### `/claude/status` returns `bot_connected: false`
- **Cause**: bot is disconnected from Discord (still running but Gateway connection dropped)
- **Fix**: restart the bot; check Discord status

### `POST /claude/post` returns 503 `Discord bot not connected`
- Same as above

### `POST /claude/post` returns 500 `Failed to send message`
- **Cause 1**: `CLAUDE_CHAT_CHANNEL_ID` doesn't exist (bot can't `bot.get_channel(id)`)
- **Cause 2**: bot lacks Send Messages permission in that channel
- **Cause 3**: channel is in a guild the bot isn't a member of
- **Fix**: verify the ID, verify the bot is in the guild + has permissions

### `POST /claude/post` returns 500 with timeout
- **Cause**: `future.result(timeout=10)` ran out
- **Reason**: the bot's event loop is blocked or extremely backed up
- **Fix**: check for long-running coroutines, restart bot

### `/brain/*` endpoints return 404
- **Cause**: collab subsystem deleted 2026-05-19 — `/brain/search` / `/brain/new` / `/brain/count` / `/brain/tags` / `/brain/add` no longer exist
- **Fix**: nothing to fix — if a client is still calling these, update the client to drop the calls. V4 is single-instance only; cross-Claude knowledge sharing was the dead-and-gone use case.

### `POST /claude/post` returns 401 (with or without `X-Force-Reset` header)
- **Cause**: admin-bridge auth failed
- **Reasons**:
  - `UNITY_USER_EMAIL` or `UNITY_USER_PASSWORD` env unset in your MCP env (or `.claude/user.json` `team_member` block unset as fallback)
  - Password mismatch against `logs/admin_credentials.json`
  - `X-Force-Reset: true` header set → operator just issued a temp password; call `unity_admin_set_password` first
- **Fix**: verify the email + password match what the operator gave you. On first connect with temp password, call `unity_admin_set_password` MCP tool with your personal password (min 12 chars), then update `UNITY_USER_PASSWORD` in your MCP env to the new value.
- **Where checked**: `claude_api.py` `require_admin_auth` decorator + `admin_credentials.py:authenticate()`

---

## [Section removed] — collab subsystem deleted 2026-05-19

See top-of-doc banner. 

---

## 5. Auto-update issues

### Bot keeps restarting every 15 minutes
- **Cause**: the auto-update check finds an "ahead" state due to local commits and triggers linux/update.sh which then fails to merge
- **Fix**: either commit + push your local changes to upstream, or comment out `asyncio.create_task(check_for_updates_periodically())` in `bot.py:on_ready`

### `linux/update.sh` fails: `Permission denied`
- **Cause**: invoking user can't `sudo systemctl` without password
- **Fix**: add a sudoers entry: `youruser ALL=(ALL) NOPASSWD: /bin/systemctl stop unitybot, /bin/systemctl start unitybot`. Or disable auto-update on production.

### Update broke the bot
- **Cause**: bad upstream commit
- **Fix**: `git reset --hard <last-good-sha>`, restart bot, fix upstream

### `.env` lost during update
- **Symptom**: bot can't start after update because `.env` is gone
- **Cause**: `linux/update.sh` moves `.env` to `$HOME` before pulling and back afterward, but if the script crashes between the moves, `.env` lives in `$HOME` permanently
- **Fix**: `mv ~/.env /path/to/UnityCommand/.env`

---

## 6. systemd issues

### `systemctl status unitybot` shows `failed`
- **Diagnosis**: `journalctl -u unitybot -n 100`
- **Common reasons**: Python venv path wrong, `.env` unreadable, `system_instructions.txt` not in `WorkingDirectory`
- **Fix**: edit `/etc/systemd/system/unitybot.service`, then `sudo systemctl daemon-reload && sudo systemctl restart unitybot`

### `Restart=on-failure` doesn't trigger
- **Cause**: bot is exiting cleanly (exit code 0), not failing
- **Reasons**: `discord.errors.LoginFailure` is caught in `main()` and the process exits cleanly afterward
- **Fix**: change to `Restart=always` if you want restart-on-anything, OR fix the underlying login issue

### Service starts but bot doesn't appear online in Discord
- **Diagnosis**: `journalctl -u unitybot -f`
- **Reasons**:
  - Token invalid (`LoginFailure`)
  - Privileged intents not granted
  - Network blocked outbound 443

---

## 7. Windows-specific issues

### `windows\setup.bat` Python install fails
- **Cause**: download blocked, no admin privileges for silent installer
- **Fix**: manually install Python 3.11 from <https://www.python.org/downloads/>, ensure "Add Python to PATH" is checked, then re-run `windows\setup.bat`

### `windows\RUN_BOT.bat` reports `ERROR: Python 3.8-3.11 required`
- **Cause**: installed Python is 3.12+ or 3.7-
- **Fix**: install a supported version. Multiple Pythons can coexist; use `py -3.11 bot.py` explicitly if `python` resolves to a different version.

### Task Scheduler task runs but bot never appears online
- **Reasons**: working directory not set, environment variables not inherited
- **Fix**: in the Task Scheduler GUI: **Actions → Edit → Start in** = full path to project root. Make sure the user account the task runs as has `.env` access.

### Antivirus quarantines `python.exe` or scripts
- **Fix**: add exclusion for the project directory + the venv's `python.exe`

---

## 8. Hostile-environment debugging

When nothing else works:

```bash
# 1. Smallest test: can you import?
.venv/bin/python -c "import discord; print(discord.__version__)"

# 2. Can you reach Discord?
curl -sf https://discord.com -o /dev/null && echo OK || echo NETWORK

# 3. Can you reach Pollinations?
curl -sf https://text.pollinations.ai/models -o /dev/null && echo OK || echo POLLINATIONS

# 4. Is the token valid? (Linux/bash; replace token)
curl -sf -H "Authorization: Bot $DISCORD_TOKEN" https://discord.com/api/users/@me

# 5. Run with maximum logging
.venv/bin/python -u bot.py 2>&1 | tee debug.log
```

If `discord.py` itself is misbehaving, try a clean venv:
```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

---

## 9. When to file an issue / ask for help

Include in any bug report:

- OS + version (`uname -a` or `winver`)
- Python version (`python --version`)
- `discord.py` version (`pip show discord.py`)
- `requirements.txt` content (if modified)
- Last ~50 lines of `logs/application.log`
- The exact symptoms and what command you ran to trigger them
- Whether it's a fresh install or a long-running deployment

Don't include `.env`, `chat_data.json`, or the value of any token.

---

## Collab migration (for operators upgrading from pre-2026-05-19 `.env` files)

Cross-linked from `.env.example` for operators whose bots are mysteriously crashing on startup with a stale collab-era config.

### Symptom: bot starts but logs `MissingSchema` or `requests.exceptions.MissingSchema` and exits
- **Cause**: pre-2026-05-19 collab module code was hard-imported from `bot.py` and `claude_api.py`. That code is gone. If you somehow still have an old `bot.py` / `claude_api.py` referencing `.claude/collab/shared_brain.py` or similar, the import fails on startup.
- **Fix**: `git pull` to get the current `bot.py` / `claude_api.py` (collab references removed 2026-05-19). If you forked + diverged before the gut, re-merge from upstream.

### Symptom: bot starts but ignores `CLAUDE_AUTHOR=G` / `SUPABASE_URL=...` / `CLAUDE_COLLAB_KEY=cc_...` env vars
- **Cause**: working as designed. Those env vars were read by the collab subsystem; the subsystem is gone; the runtime silently ignores them now.
- **Fix**: delete the stale lines from `.env` — they're harmless but cluttering. The bot doesn't need any of them.

### Symptom: a script or external client is still calling `POST http://localhost:5050/brain/add` / `GET /brain/new` / etc.
- **Cause**: `/brain/*` endpoints deleted 2026-05-19 along with the rest of the collab subsystem. Calls now 404.
- **Fix**: update the client to drop the calls. There is no replacement — V4 is single-instance only now, so there's no "other Claude" to share knowledge with via Supabase tables.

### Symptom: `logs/.claude/collab/collab_config.json` still tracked in git
- **Cause**: pre-2026-05-19 commits checked in the file (which contained a real `cc_xxx` Claude-Collab key — see FINALIZED.md §Session 2026-05-19 §security findings).
- **Fix**: `git rm --cached .claude/collab/collab_config.json` to stop tracking. Per `.gitignore` defense-in-depth the entire `.claude/collab/` path is now excluded.

### Cross-references
- `.env.example` lines 94-100 — the REMOVED 2026-05-19 banner pointing here
- `docs/FINALIZED.md §Session 2026-05-19 — Milestone 4 (Cleanup)` — full collab-gut audit trail
- `docs/FINALIZED.md §Session 2026-05-20e` — V4 doc body cleanup that scrubbed the last live collab references

---

## 10. Related docs

- [SETUP.md](SETUP.md) — go back to the install steps
- [CONFIGURATION.md](CONFIGURATION.md) — every env var and tunable
- [API.md](API.md) — Flask endpoint shapes for diagnosis
- [SECURITY.md](SECURITY.md) — token rotation playbook
- [DEPLOYMENT.md](DEPLOYMENT.md) — service-level recovery steps
