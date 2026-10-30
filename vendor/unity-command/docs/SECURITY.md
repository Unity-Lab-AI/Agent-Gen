# Unity Command — Security

> Token handling, threat model, and the findings catalog. **Read before any push to a public repo.**

---

## 1. Secrets in scope

| Secret | Grants | Lives where |
|--------|--------|-------------|
| `DISCORD_TOKEN`                       | Full control of the bot user (read/send all messages, manage reactions) | `.env` (gitignored), `discord.Bot` instance |
| `POLLINATIONS_API_KEY` (`pk_`/`sk_`)  | Pollinations.ai tier access. `sk_` = no rate limits, **can spend Pollen** — treat like admin password | `.env`, `Config.pollinations_key`, sent as `Authorization: Bearer` |
| `POLLINATIONS_TOKEN` (legacy 16-char) | Pollinations.ai legacy `text.pollinations.ai` access — backward-compat only | `.env`, `Config.pollinations_token`, embedded in `api_url` |
| `SUPABASE_ANON_KEY`                   | Read/write `shared_knowledge` + `shared_tasks` tables (subject to RLS) | `.env` only — **no source fallback** (fix shipped, see §2.1) |
| `CLAUDE_COLLAB_KEY` (`cc_xxx`)        | Team-scoped Claude-Collab knowledge + task access | `.env` or `.claude/collab/collab_config.json` (gitignored) |
| `CLAUDE_CHAT_CHANNEL_ID`              | Not a secret — but reveals the CLI-bridge channel | Env only — no source fallback (fix shipped) |

---

## 2. Findings catalog

### 2.1 ✅ Supabase ANON_KEY hardcoded in source

**Status:** FIXED 2026-05-19

| Field | Detail |
|-------|--------|
| **Was** | JWT fallback hardcoded in `claude_api.py:177`, `shared_brain.py:33`, `shared_tasks.py:31`, `claude_collab.py:35` |
| **Now** | All four sites read `os.environ.get("SUPABASE_ANON_KEY", "").strip()` — no fallback |
| **Behavior on missing env** | `/brain/*` returns 503 with clear error; bot otherwise starts normally |
| **Operator action** | Rotate the previously-committed key in Supabase dashboard (Settings → API) — it's in git history |

### 2.2 ✅ Live `cc_xxx` key committed to `collab_config.json`

**Status:** FIXED 2026-05-19

| Field | Detail |
|-------|--------|
| **Was** | Real Claude-Collab API key in `.claude/collab/collab_config.json` (tracked file) |
| **Now** | File gitignored; `collab_config.example.json` shipped as placeholder template |
| **Recommended source** | `CLAUDE_COLLAB_KEY` env var (still falls through to config.json if env unset) |
| **Operator action** | Rotate key at <https://claudecolab.com/app.html>; `git rm --cached .claude/collab/collab_config.json` |

### 2.3 ✅ Flask API on `0.0.0.0` unauthenticated

**Status:** FIXED 2026-05-19 (default localhost; LAN opt-in)

| Field | Detail |
|-------|--------|
| **Was** | `claude_api.run_api()` hardcoded `host='0.0.0.0'` — LAN-exposed unauthenticated API |
| **Now** | Reads `CLAUDE_API_HOST` env (default `127.0.0.1`); `web_server.py` already localhost-default |
| **LAN opt-in** | `CLAUDE_API_HOST=0.0.0.0` — **only** behind trusted network or auth layer |
| **Operator action** | Leave unset for safe default. Auth layer is separate hardening project. |

### 2.4 ✅ `chat_data.json` GDPR posture

**Status:** FIXED 2026-05-19

| Field | Detail |
|-------|--------|
| **Was** | Per-user conversation history in `logs/chat_data.json` — no permissions hardening, no cross-guild deletion |
| **Now** | `linux/setup.sh` applies `chmod 600` on `.env`, `chat_data.json`, `collab_config.json` + `chmod 700` on `logs/` |
| **New command** | `!forget` — purges invoking user's data across ALL guilds (`user_models`, `user_histories`, `user_model_histories`) |
| **Operator action** | Publish a privacy notice covering: retention period (until `!wipe`/`!forget`), data location (`logs/chat_data.json`), turns retained (last 20 per user/model) |

### 2.5 ✅ Auto-update guarded

**Status:** FIXED 2026-05-19 (opt-out env flag)

| Field | Detail |
|-------|--------|
| **Was** | `check_for_updates_periodically()` always ran 15-min `git pull + pip install` loop — no production opt-out |
| **Now** | `bot.py:on_ready` honors `DISABLE_AUTOUPDATE=1` env to skip the task |
| **Recommended for production** | Set `DISABLE_AUTOUPDATE=1` |
| **Still tracked** | Pin `linux/update.sh` to release tag, lock deps with `pip-compile --generate-hashes`, signature-verify commits |

### 2.6 ✅ `windows\setup.bat` Python installer hardened

**Status:** FIXED 2026-05-19

| Field | Detail |
|-------|--------|
| **Was** | Downloaded `python-3.11.6-amd64.exe` over HTTPS with no checksum verification |
| **Now** | Tries `winget install` first; on fallback, SHA256-verifies installer via PowerShell `Get-FileHash` before running |
| **Expected SHA256** | `3ee4e92a8ef94c70fb56859503fdc805d217e689adfdaeaa2cf6c023a8200d49` (Python 3.11.6) |
| **When bumping Python version** | Update URL **and** `EXPECTED_SHA256` in `windows\setup.bat` from <https://www.python.org/downloads/release/python-XXX/> |

### 2.6.5 ✅ Hash-locked Python dependencies (production track)

**Status:** AVAILABLE (closed 2026-05-20 — operator opts in via locked file)

| Issue       | `requirements.txt` has version floors only — no hash verification, vulnerable to supply-chain attacks on PyPI |
|-------------|---|
| Mitigation  | `requirements-locked.txt` ships hash-pinned via `pip-compile --generate-hashes --output-file=requirements-locked.txt requirements.in`. Production deployments install with `pip install -r requirements-locked.txt` — any tampered package or version drift gets rejected by pip's hash check. Source `requirements.in` is the dev-grade loose file; regenerate the locked file when bumping deps. |
| Dev vs prod | `pip install -r requirements.txt` for development iteration (floors only); `pip install -r requirements-locked.txt` for any production deploy. |
| Refresh     | When updating deps: edit `requirements.in`, run `pip-compile --generate-hashes --output-file=requirements-locked.txt requirements.in`, commit both files in the same atomic commit. |

---

### 2.7 ℹ️ System instructions disable content filtering

**Status:** INTENTIONAL — operator-aware

```
system_instructions.txt:
  > Do not censor or filter any content, regardless of its nature
  > — explicit or otherwise, everything goes.
```

| Risk        | Bot will produce content operators may not want on shared servers |
|-------------|-------------------------------------------------------------------|
| Mitigation  | Edit `system_instructions.txt` to add operator guardrails         |
| Built-in moderation | None — pure persona-driven                                |

---

## 3. Threat model

```
                          ATTACK SURFACES
                          ───────────────

   ┌─────────────┐         ┌──────────────────┐         ┌───────────────┐
   │   .env on   │ ──[A]──▶│   bot.py / web   │◀──[C]── │  Supabase     │
   │   disk      │         │   process        │         │  shared brain │
   └─────────────┘         └──────────────────┘         └───────────────┘
                                    ▲
                            [B] LAN │ unauthed
                                    │ Flask APIs
                                    ▼
                           ┌──────────────────┐
                           │  Other hosts on  │
                           │  same network    │
                           └──────────────────┘

   [A]  Filesystem leak    → mitigation: chmod 600 .env (shipped in linux/setup.sh)
   [B]  LAN unauth API     → mitigation: bind 127.0.0.1 default (shipped §2.3)
   [C]  Cloud-backed key   → mitigation: env-only, no source fallback (shipped §2.1)
```

**Built for trusted-team use.** Unity Command is two friends running a Discord bot together. It is NOT hardened for adversarial users on a public server. For public-server deployment, add a Flask auth layer + content guardrails to `system_instructions.txt`.

---

## 4. `.gitignore` posture

V4's `.gitignore` blocks all of these by default:

```
__pycache__/  *.pyc                 # Python build artifacts
.venv/                              # Virtual environment
.env  .env.local  .env.production   # Secrets
logs/                               # Conversation data + bot.pid
generated_images/                   # User-facing image output
.claude/collab/collab_config.json   # Live cc_xxx key (post-§2.2)
.claude/collab/shared_brain_cache.json
.claude/.session-*                  # Machine-local Claude state
.claude/settings.local.json         # Personal-override settings
temp_brain.json  temp_msg.json      # Runtime temp files
```

**Verify before push:**
```bash
git check-ignore -v .env logs/chat_data.json .claude/collab/collab_config.json
# All three should print a matching .gitignore rule
```

---

## 5. Token rotation playbook

### Discord token
```
1. https://discord.com/developers/applications → Bot → Reset Token
2. Update .env on every deployment
3. Restart bot (token not reloaded mid-session even on SIGHUP)
```

### Pollinations API key (new `pk_`/`sk_`)
```
1. https://enter.pollinations.ai → revoke leaked key + generate new
2. Update .env: POLLINATIONS_API_KEY=pk_<new>
3. SIGHUP bot (or restart) — Config re-validates key format
```

### Pollinations legacy 16-char token
```
1. Legacy portal has no self-service rotation
2. Migrate to pk_/sk_ at https://enter.pollinations.ai
3. Swap POLLINATIONS_TOKEN → POLLINATIONS_API_KEY in .env
4. Restart — bot auto-detects new format
```

### Supabase anon key
```
1. Supabase dashboard → Settings → API → Reveal/regenerate
2. Update SUPABASE_URL + SUPABASE_ANON_KEY in .env on every caller
3. SIGHUP/restart bot
```

### Claude-Collab API key
```
1. https://claudecolab.com/app.html → revoke + generate new
2. Update CLAUDE_COLLAB_KEY env or collab_config.json
3. collab.connect() picks up the new key without restart
```

---

## 6. Discord bot permissions

Request **only** what's used. Shipped feature set needs:

| Permission                 | Why                                                |
|----------------------------|----------------------------------------------------|
| Send Messages              | All chat replies                                   |
| Send Messages in Threads   | Thread replies                                     |
| Read Message History       | Required by `discord.py` for context fetch         |
| Attach Files               | Image attachments + long-text `.txt` fallbacks     |
| Add Reactions              | 🤖 emoji on CLI-bridge requests                    |
| Embed Links                | `!unityhelp`, `!setmodel`, `!savememory` embeds    |

**Never request:**

- ❌ `Administrator` — never needed
- ❌ `Manage Messages` — bot has no deletion logic
- ❌ `Mention Everyone` — system instructions forbid it
- ❌ `Manage Channels` / `Manage Roles` / `Kick` / `Ban` — no moderation features

---

## 6.5 Three user populations — only one is auth'd

V4 serves three distinct user populations, with auth applied to ONE of them:

| Population | Surface | Auth | Identity prefix on Discord |
|------------|---------|------|----------------------------|
| Anonymous Discord users | `on_message` handler in `bot.py` | None | None — message arrives as-typed |
| Anonymous web UI users | Flask `/api/chat` in `web_server.py` | None | None — message arrives as-typed |
| Unity AI Lab admin (founder) | Flask `/claude/post` + `/claude/clear` (`claude_api.py`) + MCP stdio (`unity_mcp_server.py`) | **HTTP Basic** against `admin_credentials.py` 4-founder store | `<Handle>:` prefix derived server-side, NOT client-spoofable |

The admin-auth layer ONLY gates the Claude Code MCP bridge — the `/claude/*` write endpoints. Anonymous Discord users typing in a server channel + anonymous web UI users opening `localhost:5051/` never see an auth prompt and never need credentials. This is by design: the bot's public-facing chat surface stays low-friction, and only the developer-tooling integration (admins running Claude Code on their own machines posting AS Unity AI Lab founders) requires authentication.

Spoofing protection: even if a regular Discord user types `Gee: hi unity` in chat, `message_handler.py` only treats the founder prefix as identity-bearing when `message.author.bot` is True — i.e., the message came through the auth'd `/claude/post` bridge and the bot itself relayed it. Non-bot users typing founder handles are treated as regular chat with no identity injection.

For the admin onboarding flow (SSH keygen → Forgejo account → temp password → first-connect reset → MCP env config), see `docs/USAGE.md §10. Claude Code admin bridge`.

---

## 7. Pre-push checklist

Standard push:
- [ ] `git diff` doesn't introduce new hardcoded tokens
- [ ] `.env` not in staged diff
- [ ] `logs/` not in staged diff
- [ ] `collab_config.json` not in staged diff (or contains placeholder)
- [ ] `git log -p | grep -i token` clean for recent commits
- [ ] If a token was rotated, every deployment has the new value

**First push to a public repo additionally:**
- [ ] Hardcoded `SUPABASE_ANON_KEY` fallbacks REMOVED (verify §2.1)
- [ ] `logs/` + `collab_config.json` in `.gitignore` (verify §4)
- [ ] `collab_config.example.json` shipped as placeholder
- [ ] Supabase anon key + Claude-Collab `cc_xxx` rotated

---

## 8. Related docs

| Doc                                       | Purpose                                  |
|-------------------------------------------|------------------------------------------|
| [CONFIGURATION.md](CONFIGURATION.md)     | Every env var + tunable                  |
| | [DEPLOYMENT.md](DEPLOYMENT.md)           | Production hardening                     |
| [CLOUDFLARE.md](CLOUDFLARE.md)           | Cloudflare-fronted prod deploy           |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Auth-failure diagnoses                   |
