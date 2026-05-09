# Claude Code Statusline — How It Works

How the bot's status line (e.g. `[OSLO] | [######-------] 57% | O4.7 | ░▒▓ | FREE`) is wired in and rendered.

This is for anyone (Gee, future maintainers) who wants to understand the mechanism so they can build their own or modify ours.

---

## 1. The Claude Code statusline feature

Claude Code supports a custom **status line** — a strip of text rendered at the bottom of the CLI showing whatever you want. It's configured in `settings.json`:

```json
"statusLine": {
    "type": "command",
    "command": "bash C:/claude/shared/statusline.sh"
}
```

When Claude Code wants to refresh the status line, it:

1. Spawns the configured command as a subprocess.
2. Pipes a JSON blob to that command's **stdin**. The blob includes context window usage, model info, working directory, and other session state.
3. Captures the command's **stdout** and renders it as the status line text (ANSI escape codes for color are honored).

So the statusline.sh script just needs to: read JSON from stdin → render a string → print it.

The JSON Claude Code passes looks roughly like:
```json
{
  "context_window": {
    "used_percentage": 57.3,
    ...
  },
  "model": {
    "display_name": "Claude Opus 4.7 (1M context)"
  },
  ...
}
```

That `context_window.used_percentage` field is the **57%** (or whatever) you see in the status line. Claude Code computes it; we just display it.

## 2. Our `statusline.sh` script

Located at `C:/claude/shared/statusline.sh`. One script, all bots use it.

### Bot name detection (pure bash)
At startup the script walks up from the current working directory looking for a parent named `C:/claude` (or `/c/claude`). The folder directly under that is the bot name.

So if cwd is `C:/claude/OSLO/drafts/foo`, walking up hits `C:/claude/OSLO/drafts` → `C:/claude/OSLO` (parent is `C:/claude` ✓) → bot name = `OSLO`.

This means the same script runs identically for OSLO, ASTRID, REDTEAM, BLACK, CODER, etc. without per-bot configuration. Each bot's terminal cwd is under its own folder.

### Python embedded in bash
The bulk of the work happens in a Python heredoc invoked from bash. Why Python? JSON parsing, file I/O, datetime math, color-coding logic. Bash could do it but Python is cleaner.

The Python block reads the JSON from stdin (which it inherits from the bash script), extracts the values, formats colored strings, and `print`s the result as **shell-eval-safe variable assignments**:

```
CTX="..." MODEL="..." JUSTICE="..." EFFORT="..." BCOL="..." NCOL="..."
```

Bash then `eval`s that output, populating its own variables. Cleaner than passing data back via files.

### What gets shown
- **`[BOT_NAME]`** — colored brackets indicate containment state (green=locked, yellow=admin open, red=containment off). Bot name color shows dangerous-tool state (green=safe, red=tools open).
- **Context bar `[######-------] 57%`** — color shifts at thresholds (green <60%, yellow 60-80%, red >80%).
- **Model abbreviation** — `O4.7` for Opus 4.7, `S4.6` for Sonnet, `H4.5` for Haiku.
- **Effort indicator** — gradient blocks `░▒▓` for high, etc., from `effortLevel` in settings.
- **Justice status** — pulled from `C:/claude/cryo/justice_status.json`, shows JAILED / PROBATION / FREE / etc. with countdown timers.

## 3. The side effect: `context_pct.txt`

Buried in the Python block:

```python
ctx_file = os.path.join(os.environ.get('USERPROFILE', ''), '.claude', 'context_pct.txt')
with open(ctx_file, 'w') as f:
    f.write(str(round(pct)))
```

Every time the status line refreshes, the current context % is written to `~/.claude/context_pct.txt` as a plain integer string ("57"). Other systems can `cat` that file to know how full the bot's context is.

This is how the **watchdog** and other tools detect when a bot is approaching compaction without having to query Claude Code directly. It's a side-channel: the statusline is rendered → context file gets updated → outside readers know the current %.

## 4. Why bash + Python instead of pure shell

1. **JSON parsing** — bash's JSON support is awful, jq isn't always available.
2. **Cross-platform paths** — Python's `os.path` handles Windows path quirks better.
3. **Datetime math for justice timers** — bash date math is painful.
4. **Color logic** — easier to express thresholds in Python.
5. **Future extensibility** — adding new sections (memory backlog, AICHAT unread count, etc.) is one Python edit, not a bash refactor.

The bash wrapper is mostly just for the bot-name detection (which works without Python) and to glue the eval'd output into the final colored string.

## 5. How to add a new section

1. Decide what data you need.
2. In the Python heredoc, fetch / compute it.
3. Add it to the `print(f'...')` line at the bottom as another assignment, e.g. `MEMORY="$mem_str"`.
4. After the `eval`, append it to the `PARTS` variable in the bash wrapper.
5. Test by running the script manually with sample JSON input:
   ```bash
   echo '{"context_window":{"used_percentage":42},"model":{"display_name":"Claude Opus 4.7"}}' | bash C:/claude/shared/statusline.sh
   ```

## 6. Things that broke before and got fixed

- **Garbage `used_percentage` values** — Claude Code occasionally emitted negative or >100 values. Defensive clamp added: `if pct < 0: pct = 0; if pct > 100: pct = 100`.
- **Bot name failing on non-cygwin shells** — original used `/c/claude` only, broke when shell reported `C:\claude`. Now matches both.
- **Status line eaten by weekly-limit banner** — Claude Code's weekly-limit warning banner sometimes overlaps the END of the status line. Fixed by putting CTX (the most important info) early in the order, right after the bot name, so it survives even if the line gets truncated.

## 7. The minimum reproduction

If you're starting from scratch, the smallest possible statusline.sh is:

```bash
#!/bin/bash
input=$(cat)
pct=$(echo "$input" | py -3.12 -c "import sys, json; d = json.load(sys.stdin); print(round(d.get('context_window', {}).get('used_percentage', 0)))")
echo "[$pct%]"
```

That gets you the bare percentage in brackets. Everything else in our script is decoration on top of that core.

## 8. Session Timer Fields — uptime + thinking time

> Sections § 1–7 above describe the original FDC bot-system version (`C:/claude/shared/statusline.sh`). Sections § 8–9 below describe the slimmer UAL-ClaudeWorkflow template variant shipped at `.claude/statusline.sh` in this repo.

The UAL statusline shows two cumulative timers after the model abbreviation:

```
[Project] | [######---------] 45% | O4.7 | up 1h23m · think 2m41s
                                          ^^^^^^^^^^   ^^^^^^^^^^^^^
                                          uptime       thinking time
```

Both values come from the `cost` block of the JSON Claude Code pipes to stdin every render — no sidecar files, no extra state tracking:

| Display | JSON field | Semantics |
|---------|------------|-----------|
| **`up Xh Ym`** | `cost.total_duration_ms` | Total wall-clock time since the CLI session started. Includes typing, file edits, idle time — everything. |
| **`think Ym Zs`** | `cost.total_api_duration_ms` | Cumulative time spent waiting on Claude API responses. The closest signal to "time Claude has been thinking/processing" — covers extended thinking + token generation + roundtrip. Excludes idle, typing, file I/O. |

### Format ladder

The `_fmt_ms` helper picks the most readable unit for the magnitude:

| Range | Format | Example |
|-------|--------|---------|
| < 1 minute | `Ns` | `45s` |
| 1 min – 1 hour | `MmSSs` | `2m41s` |
| 1 hour – 1 day | `HhMMm` | `1h23m` |
| ≥ 1 day | `DdHHh` | `1d03h` |

Both labels render in cyan (`\033[36m`) and the duration values themselves render in bright white (`\033[97m`) — keeps the labels visually distinct from the green/yellow/red context bar while ensuring the durations pop on dark terminals (terminal-default fg often shows as light gray, which got lost next to the cyan).

All separators — the `|` pipes between major sections AND the `·` middle-dot between uptime and thinking — render in bright green (`\033[92m`) so they visually frame each segment without competing with any segment's own color. The third pipe (before `up`) is baked into the `uptime_part` f-string and the middle-dot is baked into `think_part`, so both auto-omit when no cost block is present, keeping the line clean on fresh sessions.

### Graceful fallback

If the `cost` block is absent, malformed, or both values are zero (fresh session, never made an API call), the leading separator is omitted entirely so the line collapses cleanly to `[Project] | [bar] X% | Model` with no dangling `| ·` fragments.

### Test recipe

```bash
echo '{"context_window":{"used_percentage":45},"model":{"display_name":"Claude Opus 4.7"},"cost":{"total_duration_ms":5012345,"total_api_duration_ms":161234}}' | bash .claude/statusline.sh
# → [Project] | [######---------] 45% | O4.7 | up 1h23m · think 2m41s
```

---

## 8.5 Label & color — auto-adapt to `/rename`

The leading `[Label]` segment is no longer hardcoded to `basename(cwd)` — it auto-adapts to Claude Code's `/rename` slash command and gives every session a stable, distinct color.

### Label rules

| State | Label source | JSON field | Example |
|-------|--------------|------------|---------|
| Session has been `/rename`d | renamed value | `session_name` (top-level) | `[UnityWorkflow]` |
| No rename set | cwd basename (original behavior) | derived from `cwd` | `[UAL-ClaudeWorkflow]` |

### Color rules

| State | Color source | Result |
|-------|--------------|--------|
| Renamed | hash(`session_id`) → 12-color palette | Stable per session, distinct across concurrent sessions |
| Un-renamed | hardcoded magenta `\033[35m` | Original Unity-AI-Lab pink (brand `#ff4d9a` 4-bit fallback) |

The 12-color palette is the 6 normal + 6 bright ANSI foreground colors (excluding black/white): `91 92 93 94 95 96 31 32 33 34 35 36`. Hash function is MD5 of `session_id` UTF-8 bytes, indexed by the first byte modulo 12.

### Why hash-based instead of reading `/color`?

Anthropic's `/color <name>` slash command does **NOT** persist anywhere readable to a status line script. Verified empirically by capturing the live statusline JSON stdin (Claude Code 2.1.138), inspecting `~/.claude/sessions/<pid>.json`, `~/.claude.json`, and the project-level `.claude/` directory — no field carries the user-set color through to scripts. Whatever `/color` does (theme accent? in-memory chrome?) stays inside the running CC process.

So the label color you see in *this* statusline won't necessarily match whatever color Claude Code's sidebar shows for the same session — the sidebar's mechanism is opaque. The hash gives an automatic, stable, distinct color per session without any manual configuration. Sister behavior: same `session_id` always picks the same palette slot, so re-attaching to a long-running session preserves visual identity.

### Test recipes for 8.5

```bash
# Renamed session → hash-derived color (bright green for this id)
echo '{"context_window":{"used_percentage":8},"model":{"display_name":"Claude Opus 4.7 (1M context)"},"session_name":"UnityWorkflow","session_id":"123236a1-13b0-4dd2-8c8d-b07585e8c5ee","cost":{"total_duration_ms":554072,"total_api_duration_ms":290840}}' | bash .claude/statusline.sh
# → [UnityWorkflow] (bright green) | [#--------------] 8% | O4.7 | up 9m14s · think 4m50s

# No rename → cwd basename + magenta (original behavior preserved)
echo '{"context_window":{"used_percentage":75},"model":{"display_name":"Claude Haiku 4.5"},"session_id":"00000000-0000-0000-0000-000000000000"}' | bash .claude/statusline.sh
# → [UAL-ClaudeWorkflow] (magenta) | [###########----] 75% | H4.5
```

---

## 8.6 Model abbreviation + family color

The model segment is colored by family, with a unified `<Letter><Version>` abbreviation pattern so different model families stay visually distinct at a glance. Detection runs against both `model.display_name` and `model.id` so providers that surface only one of the two (e.g., MiniMax via `ANTHROPIC_BASE_URL` override) still classify correctly.

| Family | Abbrev | Color | ANSI escape | Source |
|--------|--------|-------|-------------|--------|
| Opus | `O<ver>` (e.g. `O4.7`) | gold | `\033[38;2;255;215;0m` (truecolor `#FFD700`) | `display_name` contains `Opus` |
| Sonnet | `S<ver>` (e.g. `S4.6`) | bright red | `\033[91m` | `display_name` contains `Sonnet` |
| Haiku | `H<ver>` (e.g. `H4.5`) | bright blue | `\033[94m` | `display_name` contains `Haiku` |
| MiniMax | `M<ver>` (e.g. `M2.7`) | bright magenta (purple-ish) | `\033[95m` | regex `(?i)MiniMax-?M?(\d+(?:\.\d+)?)` against `display_name + id` |
| Other | full `display_name` unchanged | terminal default | `\033[0m` | fallback |

**Why gold uses truecolor:** Named ANSI has no gold or orange. Closest named is bright yellow (93), which reads more lemon than gold. `#FFD700` (CSS `gold`) renders cleanly on any 24-bit-color terminal — the same passthrough scope the docs warn is silent on but works in practice. If you're on a terminal that doesn't speak truecolor, Opus may degrade to the nearest 256-color or render as terminal default; downgrade gracefully via the existing `\033[0m` reset that wraps every segment.

**MiniMax detection:** the API config at `~/.claude/minimax.json` sets `ANTHROPIC_MODEL=MiniMax-M2.7` (typical naming), so the regex catches `MiniMax-M2.7`, `MiniMax-2.7`, `MiniMaxM2.7`, etc. The version capture group becomes the digits after the optional `M`.

### Test recipes for 8.6

```bash
# Opus → gold
echo '{"context_window":{"used_percentage":8},"model":{"id":"claude-opus-4-7","display_name":"Claude Opus 4.7 (1M context)"}}' | bash .claude/statusline.sh
# → [UAL-ClaudeWorkflow] (magenta) | [#--------------] 8% | O4.7 (gold)

# Sonnet → bright red
echo '{"context_window":{"used_percentage":42},"model":{"display_name":"Claude Sonnet 4.6"}}' | bash .claude/statusline.sh
# → [UAL-ClaudeWorkflow] | [...] 42% | S4.6 (bright red)

# Haiku → bright blue
echo '{"context_window":{"used_percentage":30},"model":{"display_name":"Claude Haiku 4.5"}}' | bash .claude/statusline.sh
# → [UAL-ClaudeWorkflow] | [...] 30% | H4.5 (bright blue)

# MiniMax → bright magenta
echo '{"context_window":{"used_percentage":55},"model":{"id":"MiniMax-M2.7","display_name":"MiniMax-M2.7"}}' | bash .claude/statusline.sh
# → [UAL-ClaudeWorkflow] | [...] 55% | M2.7 (bright magenta)
```

---

## 8.7 Rate-limit usage bars — 5h session + 7d weekly

Two additional progress bars render between the context bar and the model abbreviation, sourced from the `rate_limits` block of the statusline JSON:

```
[Label] | [ctx-bar] X% | 5h [bar] Y% | 7d [bar] Z% | Model | up · think
```

| Bar | JSON field | Window | Use case |
|-----|------------|--------|----------|
| `5h [bar] Y%` | `rate_limits.five_hour.used_percentage` | rolling 5-hour | "current session" pacing — shows how close you are to the 5h Pro/Max cap |
| `7d [bar] Z%` | `rate_limits.seven_day.used_percentage` | rolling 7-day | weekly burn — long-arc usage tracking |

### Visual treatment

- Bar style identical to ctx bar — 15-char `#`/`-` fill.
- Color thresholds match the shared 6-tier gradient — see §8.12 for the canonical scheme.
- Label (`5h`, `7d`) renders in cyan (`\033[36m`) matching the `up`/`think` label convention.
- Section pipe separators bright green (`\033[92m`) per §8 convention.

### Self-omitting fallback

The `rate_limits` block is **absent on free plans** and may not be populated immediately on every render. Each bar self-omits independently when its `used_percentage` is missing — if only `five_hour` is present, only the 5h bar renders; if neither, both segments disappear and the line collapses cleanly to the original ctx-bar-then-model layout.

### Test recipes

```bash
# Both bars present
echo '{"context_window":{"used_percentage":8},"model":{"display_name":"Claude Opus 4.7"},"rate_limits":{"five_hour":{"used_percentage":56},"seven_day":{"used_percentage":70}}}' | bash .claude/statusline.sh
# → [UAL-ClaudeWorkflow] | [#--] 8% | 5h [######-] 56% | 7d [#######-] 70% | O4.7

# Free plan / no rate_limits → both bars auto-omit
echo '{"context_window":{"used_percentage":50},"model":{"display_name":"Claude Sonnet 4.6"}}' | bash .claude/statusline.sh
# → [UAL-ClaudeWorkflow] | [#######-] 50% | S4.6
```

### Footgun fixed during implementation

Backticks inside Python comments embedded in the `python3 -c "..."` heredoc trigger bash command substitution before Python ever sees them. A comment like `# rate_limits block absent on free plans` (with backticks around `rate_limits`) caused bash to try to execute `rate_limits` as a shell command. Fix: avoid backticks anywhere in the Python heredoc — use plain text or single quotes for code-like terms in comments.

---

## 8.8 Two-line static layout

As of the multi-line layout commit, the statusline renders across **two terminal rows** instead of one to keep individual lines readable as more sections get added (git branch, system stats, etc. are planned).

```
Line 1:  [Label] | up Xs · think Ys | Model
Line 2:  [ctx-bar] X% | 5h [bar] Y% | 7d [bar] Z%
```

### Why two lines

- A single line was ~110–130 chars with everything present, wrapping awkwardly on narrow terminals.
- Multi-line is officially documented as supported by Claude Code; docs warn it's "more prone to rendering issues than single-line plain text" but in practice it works reliably.
- Splitting by **semantic group** keeps each line glanceable: line 1 is identity + activity (who/what/how-long), line 2 is gauges (resource usage).

### Layout rules

- **Line 1** — `[Label]` then UPTIME + THINK (auto-omits if no cost block) then `Model`. When timers are absent, falls back to a single bright-green pipe directly between label and model.
- **Line 2** — context bar + 5h + 7d, in that order. Each rate-limit bar self-omits independently when its `used_percentage` is missing (free-plan friendly). When all are absent, line 2 is just the context bar by itself.
- **Banner safety** — Claude Code's weekly-limit banner sometimes overlaps the END of the last rendered line. With multi-line, that risk shifts to line 2's tail (currently `7d`), which is less critical than ctx — so layout intentionally puts the most-critical-now gauge (`ctx`) at the start of line 2.

### Implementation note

Both lines composed in bash from the eval'd Python output. The conditional fallback for line 1 (`if [ -n "$UPTIME" ]`) avoids a double-pipe when timers self-omit, since UPTIME has its leading separator baked into the f-string for the original single-line auto-omit semantics.

### Test recipe for 8.8

```bash
# Full render → two lines
echo '{"context_window":{"used_percentage":8},"model":{"display_name":"Claude Opus 4.7 (1M context)"},"session_name":"UnityWorkflow","session_id":"123236a1-13b0-4dd2-8c8d-b07585e8c5ee","cost":{"total_duration_ms":554072,"total_api_duration_ms":290840},"rate_limits":{"five_hour":{"used_percentage":56},"seven_day":{"used_percentage":70}}}' | bash .claude/statusline.sh
# Line 1 → [UnityWorkflow] | up 9m14s · think 4m50s | O4.7
# Line 2 → [#--] 8% | 5h [######-] 56% | 7d [#######-] 70%

# Fresh session → both lines collapse to minimal content
echo '{"context_window":{"used_percentage":50},"model":{"display_name":"Claude Sonnet 4.6"}}' | bash .claude/statusline.sh
# Line 1 → [UAL-ClaudeWorkflow] | S4.6
# Line 2 → [#######-] 50%
```

---

## 8.9 Git branch + dirty flag

Line 1 ends with the current git branch + a dirty-flag suffix when the working tree has uncommitted changes. Computed in bash (not Python) since `git` shell calls are quick (~5–20ms each) and avoid the round-trip through the Python heredoc.

```
Line 1:  [Label] | up · think | Model | branch*
                                        ^^^^^^^
                                        green if clean
                                        yellow + * if dirty
```

| Source | Command | Behavior |
|--------|---------|----------|
| Branch name | `git rev-parse --abbrev-ref HEAD` | Empty when not in a git repo → segment self-omits |
| Dirty flag | `git status --porcelain \| grep -q .` | Non-empty → branch displays as `branch*` in yellow; empty → just `branch` in green |

### Color rationale

Green/yellow chosen to match git CLI conventions — most users instantly recognize "green = clean, yellow = uncommitted." Same hues as the ctx bar's threshold colors but used here for static state, not gauge thresholds; in practice the visual context of each segment makes the semantic distinct.

### Self-omit fallback

When `git rev-parse` fails (not in a repo, git not installed, etc.), `GIT_PART` stays empty and line 1 falls through cleanly to `[Label] | Model` with no dangling separator. Safe to drop the `.claude/` template into non-git directories.

### Test recipe

```bash
# In a git repo with uncommitted changes
echo '{"context_window":{"used_percentage":8},"model":{"display_name":"Claude Opus 4.7"},"session_name":"UnityWorkflow","session_id":"abc"}' | bash .claude/statusline.sh
# Line 1 → [UnityWorkflow] | O4.7 | feature/extra-status-bar-features* (yellow)

# In /tmp (non-git)
cd /tmp && echo '{"context_window":{"used_percentage":50},"model":{"display_name":"Claude Sonnet 4.6"}}' | bash /path/to/.claude/statusline.sh
# Line 1 → [tmp] | S4.6   (no git segment)
```

---

## 8.10 Line 3 — system stats (CPU / RAM / drive)

A new third row surfaces local machine resource usage so you can see at a glance whether your dev box is under stress while you're working:

```
Line 3:  cpu N% | ram U/TG | drive NG free
```

| Segment | Source (Linux) | Source (Windows) | Format |
|---------|----------------|------------------|--------|
| `cpu N%` | `/proc/loadavg` 1-minute load ÷ `os.cpu_count()` × 100 (clamped to 100%) | wmic + sidecar cache (deferred — see below) | percentage |
| `ram U/TG` | `/proc/meminfo` `MemTotal` and `MemAvailable` | wmic + sidecar cache (deferred) | used / total in GB |
| `drive NG free` | `shutil.disk_usage('.')` | `shutil.disk_usage('.')` (cross-platform stdlib) | free space in GB |

### Why this approach

- **Linux uses stdlib only** — `/proc/*` reads + `shutil.disk_usage` are sub-millisecond, fast enough to run every render with no caching infrastructure.
- **Windows CPU/RAM deferred** — `wmic` shell-outs are ~200–500ms, blowing the sub-100ms render budget per Claude Code docs. Cross-platform parity will land in a follow-up commit using a sidecar JSON cache (`~/.claude/syscache.json`) refreshed in the background. Until then, Windows shows `cpu —` and `ram —` (dim grey) while disk works correctly.
- **Disk works everywhere** — `shutil.disk_usage` is cross-platform stdlib and reads the filesystem of the script's CWD. Claude Code invokes the statusline with the project root as CWD, so the segment naturally reports the project's drive.

### Color rules

Same green / yellow / red threshold as the ctx and rate-limit bars: `<60%` green, `60–80%` yellow, `>80%` red. Cyan label (`cpu`, `ram`, `drive`) matching the `up` / `think` / `5h` / `7d` label convention.

For disk specifically, the threshold is on **percent used** (matching the other gauges' semantics — high % = bad). `261G free` showing yellow means the drive is 60–80% full overall, even though the absolute free figure looks plentiful.

### Self-omitting fallback

If a stat fails (e.g., `/proc/loadavg` unreadable, no `MemAvailable` in older kernels, disk path inaccessible), that single segment renders as a dim-grey `—` placeholder while the rest of line 3 stays intact. If the entire Python block fails (parse error, etc.), `SYS3` ends up empty and the bash `[ -n "$LINE3" ] && echo` guard skips line 3 entirely — degrades to two-line layout cleanly.

### Test recipes

```bash
# Linux full render
echo '{"context_window":{"used_percentage":8},"model":{"display_name":"Claude Opus 4.7"}}' | bash .claude/statusline.sh
# Line 3 → cpu 13% | ram 11.4/61.6G | drive 261G free

# Broken JSON → line 3 self-omits via SYS3=""
echo 'garbage' | bash .claude/statusline.sh
# Lines 1-2 render with ? placeholders, line 3 absent
```

---

## 8.11 Line 4 — GPU(s) via nvidia-smi (with sidecar cache)

A fourth row surfaces every NVIDIA GPU on the host with VRAM usage + utilization. Falls back to red `No GPU Detected` when nvidia-smi is missing OR returns an empty GPU list.

```
Line 4:  4070s 0.3/12gb 5% | 2060 0.0/6gb 0%
         ^^^^^ ^^^^^^^^ ^^   ^^^^ ^^^^^^^ ^^
         short used/   util  next gpu
         name  total
```

### Source command + parsing

```
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits
```

Returns one CSV row per GPU: `<name>, <mem_used_mb>, <mem_total_mb>, <util_pct>`. Parsed into a `gpus[]` list of dicts.

### Sidecar cache strategy

`nvidia-smi` takes ~150ms — too slow to call every render (sub-100ms render budget per CC docs). So:

- Cache lives at `~/.claude/gpu-cache.json` with **5-second TTL**.
- On render: if cache exists AND mtime <5s, read JSON (sub-ms).
- On cache miss / staleness: shell-out to nvidia-smi (timeout=2s), parse, write fresh cache. Blocks once, then 5s of fast renders.
- On `FileNotFoundError` (nvidia-smi not on PATH), `TimeoutExpired`, or `returncode != 0`: write empty `{"gpus": []}` to cache so subsequent renders don't re-attempt for 5s.

### Short-name extraction

NVIDIA's full names are long (`NVIDIA GeForce RTX 4070 SUPER`) — the script extracts the model digits + suffix:

| Full name | Regex match | Short |
|-----------|-------------|-------|
| `NVIDIA GeForce RTX 4070 SUPER` | `RTX 4070 SUPER` | `4070s` |
| `NVIDIA GeForce RTX 3090 Ti` | `RTX 3090 Ti` | `3090ti` |
| `NVIDIA GeForce RTX 2060` | `RTX 2060` | `2060` |
| (no match) | n/a | first 12 chars |

Pattern: `(?:RTX|GTX|GT|Tesla|Quadro)\s*(\w+)\s*(SUPER|Ti)?` (case-insensitive). Suffix maps `SUPER→s`, `Ti→ti`.

### Color rules

- **Short name** in cyan (matching label convention).
- **VRAM** color-coded by `% used` of total — green/yellow/red threshold.
- **Util %** color-coded — green/yellow/red threshold (same as ctx + system bars).
- **No-GPU fallback** in red (`\033[31m`) so it stands out as a not-normal state.

### Self-omitting fallback

When the entire Python block fails (parse error etc.), `GPU=""` and bash's `[ -n "$LINE4" ] && echo` guard skips line 4 entirely — degrades to three-line layout.

### Test recipes

```bash
# With NVIDIA card present → cache populates, GPU(s) render
echo '{"context_window":{"used_percentage":8},"model":{"display_name":"Claude Opus 4.7"}}' | bash .claude/statusline.sh
# Line 4 → 4070s 9.5/12gb 100% | 2060 0.0/6gb 0%

# Force empty-cache path → 'No GPU Detected'
echo '{"gpus": []}' > ~/.claude/gpu-cache.json
echo '{"context_window":{"used_percentage":50},"model":{"display_name":"Claude Sonnet 4.6"}}' | bash .claude/statusline.sh
# Line 4 → No GPU Detected (red)

# Cache regeneration after deletion → next render shells out + repopulates
rm -f ~/.claude/gpu-cache.json
echo '{"context_window":{"used_percentage":50},"model":{"display_name":"Claude Sonnet 4.6"}}' | bash .claude/statusline.sh
# Line 4 → 4070s 9.5/12gb 94% | 2060 0.0/6gb 0%
```

### Cross-platform note

`nvidia-smi` ships with the official NVIDIA driver on Linux + Windows + macOS (Tesla cards). The script's `subprocess.run(['nvidia-smi', ...])` call works on every platform that has the driver installed; on AMD/Intel-only systems or driverless installs, the FileNotFoundError handler triggers and "No GPU Detected" renders.

---

## 8.12 Canonical 6-tier color gradient (used by every gauge)

Every percentage / value gauge in the statusline shares the same 6-tier gradient so the eye learns one color-language and reads every segment instantly. Truecolor RGB only (passthrough), so terminal needs 24-bit color support — universal on Windows Terminal, Git Bash mintty, modern Console Host (Win10 v1809+), PowerShell 7+, and any Linux terminal in the last decade.

| Range | Color name | RGB | Hex | Tailwind equivalent |
|-------|------------|-----|-----|---------------------|
| ≤ 35% | green | `34, 197, 94` | `#22c55e` | green-500 |
| 36–45% | green-yellow / lime | `163, 230, 53` | `#a3e635` | lime-400 |
| 46–55% | yellow | `234, 179, 8` | `#eab308` | yellow-500 |
| 56–65% | orange | `249, 115, 22` | `#f97316` | orange-500 |
| 66–79% | red-orange | `234, 88, 12` | `#ea580c` | orange-600 |
| 80%+ | red | `220, 38, 38` | `#dc2626` | red-600 |
| `None` / N/A | dim grey | (terminal default) | `\033[90m` | — |

### Applied to

Every percentage-based segment uses `_grad_color(p)`:

| Gauge | Source % |
|-------|----------|
| Context window bar | `context_window.used_percentage` |
| 5h rate-limit bar | `rate_limits.five_hour.used_percentage` |
| 7d rate-limit bar | `rate_limits.seven_day.used_percentage` |
| CPU value (line 3) | load_1m / cpu_count × 100 |
| RAM value (line 3) | (used / total) × 100 |
| Drive value (line 3) | (used / total) × 100 (high % = drive nearly full) |
| GPU VRAM (line 4) | (used / total) × 100 |
| GPU util (line 4) | reported by nvidia-smi |

### Drive note

The drive segment displays "free GB" but the COLOR axis is "% used" (high = bad), matching every other gauge. So `261G free` showing red-orange means the drive is 66–79% full overall, even though the absolute free figure looks plentiful.

### Helper

```python
def _grad_color(p):
    if p is None: return '\033[90m'
    if p <= 35: return '\033[38;2;34;197;94m'
    if p <= 45: return '\033[38;2;163;230;53m'
    if p <= 55: return '\033[38;2;234;179;8m'
    if p <= 65: return '\033[38;2;249;115;22m'
    if p < 80:  return '\033[38;2;234;88;12m'
    return '\033[38;2;220;38;38m'
```

### Test recipe

```bash
for p in 5 30 36 50 60 70 79 85; do
  echo -n "  $p% → "
  echo "{\"context_window\":{\"used_percentage\":$p},\"model\":{\"display_name\":\"Claude Opus 4.7\"}}" | bash .claude/statusline.sh | sed -n '2p' | head -c 100
  echo
done
# Verifies each percentage hits the expected gradient stop.
```

---

## 9. Future Capabilities Brainstorm — other fields the statusline could surface

The full Claude Code statusLine JSON schema (per [code.claude.com/docs/en/statusline](https://code.claude.com/docs/en/statusline)) includes more than the four fields we currently use. Each row below is a candidate capability — pick what's useful, leave the rest. Order is by "easiest signal-to-effort ratio first."

### From the JSON blob (zero extra work)

| Capability | JSON field | Display idea | Why useful |
|------------|-----------|--------------|------------|
| **Session cost** | `cost.total_cost_usd` | `$0.42` (red >$5, yellow >$2, green) | Real-time spend awareness during long sessions |
| **Lines changed** | `cost.total_lines_added` / `cost.total_lines_removed` | `+150 -42` | Diff scope at a glance |
| **Token gauge** | `context_window.total_input_tokens` / `context_window_size` | `47k/200k` | Absolute token count beside the percentage |
| **Effort indicator** | `effort.level` | gradient blocks `░▒▓` for low/med/high/xhigh/max | What thinking budget the user has set |
| **Extended thinking badge** | `thinking.enabled` | `🧠` if true, omit if false | Quick visual when extended thinking is active |
| **Model variant** | `model.id` | full ID on hover, shortened in line | Distinguish 1M-context from standard |

> ✓ **Implemented**: `session_name` is now wired into the leading `[Label]` segment with hash-of-`session_id` color rotation. See §8.5 above for behavior + JSON field reference.
> ✓ **Implemented**: 5-hour and 7-day rate-limit progress bars render between the ctx bar and the model abbreviation. See §8.7 above for behavior + JSON field reference + self-omit fallback for free plans.
> ✓ **Implemented**: two-line static layout — line 1 is identity + activity, line 2 is gauges. See §8.8 above for the layout rules + multi-line rendering caveats.
> ✓ **Implemented**: git branch + dirty flag appended to line 1 after the model abbreviation. See §8.9 above for behavior + non-git fallback.
> ✓ **Implemented**: line 3 system stats — CPU, RAM, drive free space. Linux uses stdlib (sub-ms reads); Windows CPU/RAM deferred to a wmic-cache follow-up, disk works cross-platform. See §8.10 above for fallback behavior.
> ✓ **Implemented**: line 4 GPU stats via nvidia-smi with 5s sidecar cache. Multi-GPU pipe-separated; "No GPU Detected" red fallback when nvidia-smi missing or empty. See §8.11 above for short-name extraction + cache strategy.

### Derived from `transcript_path` (single file read per render)

| Capability | Derivation | Display idea |
|------------|------------|--------------|
| **Idle timer** | `now − transcript.last_message.created_at` | `idle 3m12s` (dim grey) |
| **Tool call count** | count of `tool_use` blocks in transcript | `tools: 47` |
| **Files modified** | unique paths in `Edit`/`Write` tool_use this session | `files: 12` |
| **Last user prompt summary** | first 60 chars of last `user` message | `«fix the dashboard…»` |
| **Cache hit rate** | sum of `cache_read_input_tokens` / total input tokens | `cache: 78%` (green >70%) |
| **Sub-agent depth** | count of nested `Agent` tool uses currently in-flight | `sub: 2` |

### Derived from project state (cheap shell calls)

| Capability | Source | Display idea |
|------------|--------|--------------|
| **Last commit hash** | `git rev-parse --short HEAD` | `@a3f8c1` |
| **Commits ahead/behind** | `git rev-list --count @{u}..HEAD` | `↑3 ↓1` |
| **TODO open count** | grep `[~]` or `[ ]` markers in `docs/TODO.md` | `todo: 7` |
| **Memory item count** | line count in `~/.claude/projects/<encoded>/memory/MEMORY.md` | `mem: 24` |
| **Hook firing indicator** | temp signal file written by hook scripts | `🪝` flash |

### Side-channel side effects (write-on-render)

The current script already writes `~/.claude/context_pct.txt` for external watchdogs. Same pattern could write:

- `~/.claude/uptime_ms.txt` — current session uptime, for compaction watchdogs
- `~/.claude/think_ms.txt` — cumulative thinking time, for cost-per-task analytics
- `~/.claude/cost_usd.txt` — running session cost, for "stop me at $X" tripwires
- `~/.claude/idle_seconds.txt` — for YOLO mode 60s auto-continue (`docs/TODO.md` YOLO rework task)

Each of these turns the statusline render cycle (which fires every few seconds) into a free state-broadcast for hooks, monitors, and external tooling — no extra polling required.

### What NOT to add

- **Live spinner / animation** — render cadence isn't guaranteed fast enough to look smooth; will look broken
- **Real-time CPU/memory of node process** — costs an `os.getpid` + `psutil` import every render; not worth the latency budget
- **Network ping to claude.ai** — adds tail-latency to every render; never put network calls in a statusline command

The render budget is sub-100ms target. Anything that costs more than parsing JSON + reading one file should be pre-computed by a hook and dropped into a sidecar file for the statusline to `cat`.

---

**File**: `.claude/statusline.sh` (UAL template) · `C:/claude/shared/statusline.sh` (FDC bot-system, § 1–7)
**Wired in**: `.claude/settings.json` → `statusLine.command` (project-level) · `~/.claude/settings.json` (global, FDC)
**Side-effect file**: `~/.claude/context_pct.txt`
**Per-project identity**: derived from cwd basename, no config needed
