# Unity Command — Usage

Every Discord-side surface: commands, natural-chat patterns, response shapes, and the CLI-bridge triggers.


> **⚠ REMOVED 2026-05-19** — The collab subsystem (claudecolab + Supabase shared brain + cross-Claude G/R task queue + `.claude/collab/` Python modules + `/brain/*` Flask endpoints) was deleted wholesale per operator directive. V4 is single-instance only. References below are retained as historical context but the features no longer exist.


---

## 1. Commands (prefix `!`)

The command prefix is the literal exclamation mark. There are four. All are case-sensitive.

### `!unityhelp`
- **Scope**: any channel or DM
- **Response**: embed listing the four commands + every model loaded from Pollinations (with description if provided)
- **Example output**:
  ```
  Unity Bot Help
  Available commands and models:
  Commands
  !unityhelp - Show this help
  !setmodel - Choose a model
  !savememory <text> - Save a memory
  !wipe - Clear chat history

  Available Models
  unity: Default unity model
  mistral: Mistral 7B
  openai-large: ...
  ```

### `!setmodel`
- **Scope**: any channel — sends instruction back to user, actual UI happens in DM
- **Flow**:
  1. Bot replies: `<@you>, check your DMs for model selection.`
  2. Bot DMs you a series of embeds, each with up to 25 model-name buttons
  3. Click a button → bot DMs you a `Model Selected` embed and saves your choice
  4. Selection is **per-user-per-guild** — same user in different guilds can pick different models
- **Failure**: if your Discord privacy settings block DMs from server members, the bot responds in-channel: `please enable DMs from server members`
- **Default**: new users start on `"unity"`. The default is assigned lazily the first time their model is looked up.

### `!savememory <text>`
- **Scope**: any channel
- **Storage**: per-channel, capped at 5 entries; oldest entries fall off when the cap is reached
- **Behavior**: trimmed via `.strip()`; duplicate of an existing memory is silently ignored
- **Response**: embed titled `Memory Saved` showing the saved text
- **Effect on chat**: every subsequent chat turn in that channel prepends all current channel memories as a synthetic user message before the rolling history — so Unity "remembers" the pinned info
- **Examples**:
  ```
  !savememory The user prefers tea over coffee
  !savememory We are working on a Python game called Sparkbear
  !savememory Don't talk about the bug we're fixing tomorrow
  ```

### `!wipe`
- **Scope**: any channel
- **Effect**: clears the **invoking user's** rolling history (channel-history entries, user-history entries, and every per-user-per-model history) in the invoking guild
- **NOT cleared**: channel memories (use a fresh `!savememory` to overwrite, or edit `logs/chat_data.json` directly), other users' histories, other guilds' histories
- **Response**: `<@you> Chat history wiped for this server.`

---

## 2. Natural chat (no prefix)

Any non-command message in an allowed channel or DM triggers a chat completion via Pollinations.

### Trigger conditions (in order — `bot.py:on_message`)

1. **Not from this bot** (`message.author == bot.user` short-circuits)
2. **Not in the Claude-chat channel** (when `CLAUDE_CHAT_CHANNEL_ID` matches the channel, the bot only records the message — no auto-response)
3. **In the channel allowlist** (when `ALLOWED_CHANNELS` is set; DMs always pass)
4. **Not a CLI-trigger phrase** (see §3)
5. **If from another bot**, wait 10 s before responding (etiquette delay)
6. Process commands first (`bot.process_commands`), then run the message handler

### What the bot sees (per chat completion)

```
system: <system_instructions.txt contents>
        You are <user's selected model>.
user (synthetic): <newline-joined channel memories, if any>
user / assistant: <last up-to-20 turns of per-user-per-model history>
user: <your current message>
```

### Response sizing

| Length | Form |
|--------|------|
| ≤ 2000 chars | plain `channel.send(content)` |
| 2001 – 4096 chars | `discord.Embed(description=content)` |
| > 4096 chars | content written to a `BytesIO` → attached as `response.txt` |

When images are present in the response (URLs matched by `https?://\S+`), they're downloaded and attached as `discord.File(filename="image.png")` (same filename for every image — no collision-handling).

### Code-block delivery

If your message contains the substring `"code"` or `"script"`, the response is parsed for `[CODE]<lang>...[/CODE]` blocks. Each block is sent as its own message:

| Block length | Form |
|--------------|------|
| ≤ 2000 chars (with ` ``` ` fence) | plain message |
| ≤ 4096 chars | embed |
| > 4096 chars | `<lang>_code.txt` attachment |

The remaining text (with all `[CODE]...[/CODE]` blocks stripped) is then sent through the normal sizing logic.

---

## 3. Claude-CLI bridge

Unity Command includes a side-channel that lets a Claude CLI session **be Unity in Discord** — read recent channel messages and post replies as Unity. See [API.md](API.md) and [ARCHITECTURE.md §5](ARCHITECTURE.md) for the full data flow.

### Trigger phrases (case-insensitive)

| Phrase | Where to put it |
|--------|----------------|
| `!cli` | command-like trigger anywhere in message |
| `!realunity` | command-like trigger anywhere in message |
| `hey cli` | natural language |
| `claude cli` | natural language |
| `real claude` | natural language |
| `actual claude` | natural language |

### Behavior when a trigger fires

1. The message is recorded to the Flask API's in-memory ring **prefixed with `[CLI_REQUEST]`**
2. The bot reacts with 🤖 to confirm receipt
3. The bot does **NOT** auto-respond — it waits for the external CLI to post via `/claude/post`

### Behavior in the Claude-chat channel

If `CLAUDE_CHAT_CHANNEL_ID` matches the channel, ALL messages there (not just trigger-phrase ones) are recorded, and the bot NEVER auto-responds. That channel is treated as CLI-only territory.

---

## 4. Image generation

Unity Command doesn't generate images on its own — it relies on the Pollinations model emitting `https://image.pollinations.ai/prompt/...` URLs in its text response, which the bot then downloads and attaches.

To prompt for an image, lean on language the model recognizes:

| Phrase | Why |
|--------|-----|
| `generate an image of <thing>` | Direct |
| `draw <thing>` | Direct |
| `selfie` | The system instructions tell the model to depict a specific persona for selfies — emits a Pollinations URL with persona-consistent description |
| `picture of <thing>` | Direct |

The shipped `system_instructions.txt` formats image URLs for the new gen.pollinations.ai stack as:
```
https://gen.pollinations.ai/image/<urlencoded_prompt>?width=1024&height=1024&seed=<6digit>&model=flux&nologo=true&private=true&safe=false
```

The bot's runtime appends `&key=<POLLINATIONS_API_KEY>` automatically — `system_instructions.txt` tells the model NOT to include the key inline. The bot downloads each URL and attaches the bytes as a Discord file. If the download fails (non-200, connection error), the image is silently dropped from the response but the text still sends.

If the bot is running on the legacy stack (16-char `POLLINATIONS_TOKEN`), `Config.image_url()` swaps the base to `https://image.pollinations.ai/prompt/...` and appends `&apikey=<token>` instead of `&key=`. The model still emits the same shape — only the runtime URL changes.

---

## 5. DMs vs guild channels

| Aspect | DM | Guild channel |
|--------|----|---------------|
| Auto-respond by default | ✅ always | ✅ unless `ALLOWED_CHANNELS` excludes it |
| `!setmodel` works | ✅ (DM doesn't need to bounce — buttons appear immediately) | ✅ (bounces through your DM) |
| `!savememory` scope | DM-channel-specific | Guild-channel-specific |
| Bot-detection (`detect_channel_bots`) | empty (DMs have no member list) | scans the guild channel members |
| `guild_id` in storage | string `"DM"` | actual guild ID string |
| Startup greeting | never | only in `CLAUDE_CHAT_CHANNEL_ID` |

---

## 6. Model behavior tips

Different Pollinations models behave differently for the same prompts. Hints based on observed defaults:

| Model name pattern | Tends to |
|--------------------|----------|
| `unity` (default) | Hold the system-instructions persona well, including emo/goth voice, profanity, no-filter |
| `mistral` | More compact replies, sometimes drops persona under pressure |
| `openai-*` (large/small) | Polished but corporate-leaning — needs strong system-instruction grounding to stay in character |
| `dolphin-*` | Uncensored, holds persona consistently |
| `evil` | Specialty unfiltered model |
| `searchgpt` | Adds web-search results — useful for current-events queries |

Use `!setmodel` to swap. Each user-model combination has its own conversation history (capped at 20 turns), so you can flip back and forth without losing context per model.

---

## 7. Edge cases and surprises

- **Empty response**: if Pollinations returns nothing parseable, the bot sends `Empty response from API—please try again later.`
- **Model not in `!setmodel` list**: any non-listed name passed via internal code paths falls back to `"unity"`. Users can't pick a non-existing model from the button UI.
- **3 consecutive newlines**: collapsed to 2 by `clean_response`
- **Lines beginning `---`**: dropped (treated as horizontal rule noise)
- **Lines containing `Generated by`**: dropped (some models append attribution)
- **Lines containing `\d{4}-\d{2}-\d{2}`**: dropped (some models append timestamps)
- **Response starts with `[claude]` / `[revclaude]` / `[gpt]` / `[openai]` / `[assistant]`** (case-insensitive): the bracket prefix is stripped before sending to Discord
- **Multiple URLs in response**: ALL are downloaded and attached (same filename `image.png` — Discord will show them as `image.png`, `image (1).png`, etc. on the receiver side)

---

## 8. Logs you can watch while using it

```bash
# Linux / macOS
tail -f logs/application.log

# Windows PowerShell
Get-Content -Wait logs\application.log
```

Every message handled produces a sequence like:
```
INFO - Received message from <user_id> in channel <channel_id> (guild: <guild_id>): <content>
INFO - User <user_id> using model: <model_name> in guild <guild_id>
INFO - Preparing to send message for user <user_id> with model <model_name>
INFO - Using model: <model_name>
INFO - Response length for user <user_id>: <length> characters
```

Errors live alongside as `ERROR` lines with stack traces (file logger is at `DEBUG` level, console at `INFO`).

---

## 9. Alternate surfaces — Web UI and Terminal CLI

Unity Command ships with two non-Discord surfaces for talking to Unity. Both share the same `Config` + `APIClient` + Pollinations backend; both work alongside the Discord bot or standalone.

### 9.1 Web UI (browser)

A Flask-served single-page app at `http://localhost:5051` with:
- **First-run setup wizard** — 7-step browser walkthrough in plain language, validates each field as you type, shows current values redacted
- **Dynamic chat** — input box, model dropdown, real-time responses
- **Inline image rendering** — image URLs in Unity's responses render directly in the chat as `<img>` tags
- **🎨 Image button** — direct image generation bypassing chat
- **⚙ Setup button** — re-run the configuration wizard any time
- **Cross-platform** — works in any modern browser on Linux + Windows

Launch:
```bash
# Linux/macOS
./linux/start_web.sh

# Windows
windows\start_web.bat

# Or directly
python web_server.py
python web_server.py --host 0.0.0.0 --port 8080  # LAN access on custom port
python web_server.py --no-browser                # don't auto-open browser
```

Combined mode — run Discord bot + Web UI together by setting `WEB_UI_ENABLED=1` in `.env`. The bot spawns the web server in a background thread on port 5051 by default (configurable via `WEB_UI_PORT` and `WEB_UI_HOST`).

### 9.2 Terminal CLI (SSH/server)

`unity_cli.py` is a standalone REPL for typing to Unity from a terminal — useful for headless servers where you've SSH'd in.

Features:
- Auto-detects terminal image renderers in priority order: **chafa → viu → kitty +kitten icat → imgcat → wezterm imgcat**, falls back to printing the Pollinations URL when none available
- Saves every generated image to `./generated_images/<timestamp>.png`
- Multi-turn conversation with session-local history
- `!image <prompt>` for direct image-gen bypass
- `!model`, `!history`, `!clear`, `!render`, `!show`, `!help`

Launch:
```bash
python unity_cli.py
python unity_cli.py --model openai
python unity_cli.py --save-dir /var/lib/unity/images
python unity_cli.py --renderer chafa             # force a specific renderer
python unity_cli.py --no-render                  # save+URL only, never try inline render
```

For best inline image quality install **chafa** (most portable) or **viu**:
```bash
# Linux
sudo apt install chafa     # or: cargo install viu

# macOS
brew install chafa         # or: brew install viu

# Windows (chafa is easiest)
# Download from https://github.com/hpjansson/chafa/releases
# Or use scoop: scoop install chafa
```

---

## 10. Claude Code admin bridge — for the four founders

Each Unity AI Lab founder (Gee / Sponge / Red / Alfreddo) can talk to Unity FROM their local Claude Code instance via the authenticated MCP bridge. Anonymous Discord + web UI users keep their existing un-gated chat surfaces — admin auth ONLY gates the Claude Code → Unity path.

**Operator side (one-time per admin, run on the bot host):**

```bash
# Operator (typically Gee) issues a temp password for an admin email
python admin_cli.py issue Sponge@unityailab.com
# → prints 16-char temp password ONCE; hand to admin via secure channel
```

Equivalent via `configure.py`:

```bash
python configure.py --issue-admin-token Sponge@unityailab.com
```

**Admin side (one-time, on the admin's own machine):**

1. Receive temp password from operator (secure channel — Signal, encrypted DM, in-person)
2. Add to your local `.env` (or your Claude Code MCP env block):
   ```
   UNITY_USER_EMAIL=Sponge@unityailab.com
   UNITY_USER_PASSWORD=<the-temp-password>
   ```
3. From Claude Code (with the MCP server wired to `unity_mcp_server.py`), call the `unity_admin_set_password` tool with a new password (min 12 chars):
   ```
   /mcp unity unity_admin_set_password new_password="MyR3alPasswordHere!"
   ```
4. Update `UNITY_USER_PASSWORD` in your `.env` to the new real password
5. Smoke test: `unity_post message="Sponge here, online"` — should land in Discord, Unity should reply addressing you by handle + role

**Day-to-day:**

- `unity_post(message)` — post as the authenticated admin; Unity sees `<Handle>:` prefix + `[Admin identity: <Handle>, role: <Role>]` in her context and responds by name
- `unity_read(limit, since)` — pull recent Discord messages (open endpoint, no auth needed)
- `unity_status()` — bridge online check
- `unity_whoami()` — verify which identity you've resolved as

**Admin operations:**

- Rotate password: operator runs `python admin_cli.py issue <email>` again → fresh temp issued → admin redeems via `unity_admin_set_password`
- List admin state: `python admin_cli.py list` (operator) — shows has-password, force-reset, last-login per founder
- Audit log: `logs/admin_audit.log` (operator) — append-only TSV of every auth event

For the full bridge architecture + spoofing protection + three-user-population diagram see [SECURITY.md §6.5](SECURITY.md). For the matching MCP tool reference see [API.md](API.md).

---

## 11. Related docs

- [SETUP.md](SETUP.md) — install + first-launch verification
- [API.md](API.md) — Flask REST + MCP stdio reference
- [CONFIGURATION.md](CONFIGURATION.md) — env vars + tunables
- [SECURITY.md](SECURITY.md) — threat model + admin-bridge auth
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — when things go sideways
