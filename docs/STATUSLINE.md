# Claude Code Statusline — How It Works

How the bot's status line (e.g. `[OSLO] | [######-------] 57% | O4.7 | ░▒▓ | FREE`) is wired in and rendered.

This is for anyone who wants to understand the mechanism so they can build their own or modify ours.

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

Two additional progress bars render on line 2 (alongside the ctx bar), sourced from the `rate_limits` block of the statusline JSON. **The label slot shows the time remaining until the window resets**, not the bare window length — so at a glance you see exactly when the cap rolls over without having to do mental subtraction. The bar itself still tracks `used_percentage` with the canonical gradient.

```
Line 2:  CTX [bar] X% | 4h12m [bar] Y% | 5d03h [bar] Z%
                       ^^^^^             ^^^^^
                       countdown to      countdown to
                       5h reset          7d reset
```

| Bar | JSON percentage field | JSON reset field (Unix epoch seconds) | Window | Label format |
|-----|------------------------|----------------------------------------|--------|--------------|
| `<countdown> [bar] Y%` | `rate_limits.five_hour.used_percentage` | `rate_limits.five_hour.resets_at` | rolling 5-hour | `XmYs` / `XhYYm` / `XdYYh` |
| `<countdown> [bar] Z%` | `rate_limits.seven_day.used_percentage` | `rate_limits.seven_day.resets_at` | rolling 7-day | same ladder |

`resets_at` is an **integer Unix epoch in seconds** (verified empirically against CC 2.1.138 — see §10 for the full schema capture). The script computes `delta = resets_at - time.time()` and formats the positive delta with the same time-format ladder as `up` / `think`. If `resets_at` is missing or already in the past, the label falls back to the literal `5h` / `7d` so the segment still renders something sensible.

### Visual treatment

- Bar style: 16-cell × 8-sub-level Unicode block-fill — see §8.13 for geometry.
- Color thresholds match the shared 6-tier gradient — see §8.12 for the canonical scheme.
- Countdown label renders in cyan (`\033[36m`) matching the `up`/`think`/`CTX`/`cpu`/`ram` label convention.
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

**As of §8.14 (centering refactor):** all four lines are composed inside the single embedded `python3 -c '...'` heredoc rather than in bash. Bash still computes `GIT_PART` (cheap git shell-outs) and the `TERM_COLS` value via `tput cols < /dev/tty`, then passes both as env vars into Python. Python composes line 1's conditional UPTIME fallback inline (`if uptime_part: ... else: ...`), centers each line independently using the shared `ANSI_RE` strip + leading-space pad, and emits four `LINEN="..."` assignments for bash to `eval` and `echo`. One python subprocess per render preserves the sub-100ms latency budget.

(Historical note: prior to §8.14, both lines were composed in bash via per-segment env vars `CTX="..." RATE5H="..." MODEL="..."` etc. The refactor was triggered by dynamic centering needing Unicode-aware visible-length counting, which is trivial in Python and a multi-tool dance in bash.)

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

## 8.9 Git branch + state-aware coloring

Line 1 ends with the current git branch, colored both by **branch type** and **working-tree state**. Computed in bash (not Python) since `git` shell calls are quick (~5–20ms each) and avoid the round-trip through the Python heredoc.

```
Line 1:  [Label] | up · think | Model | branch
                                        ^^^^^^
                                        color + suffix encode state
```

### Branch-type colors (applied when state is "pushed")

| Branch | Color | RGB | Hex | Tailwind |
|--------|-------|-----|-----|----------|
| `main` / `master` | blue | `59, 130, 246` | `#3b82f6` | blue-500 |
| `develop` | purple | `168, 85, 247` | `#a855f7` | purple-500 |
| anything else (`feature/*`, `hotfix/*`, `release/*`, `bugfix/*`, etc.) | green | `34, 197, 94` | `#22c55e` | matches gradient ≤35% |

### State markers (override branch-type color when applicable)

| State | Suffix | Color | Detection |
|-------|--------|-------|-----------|
| **pushed** (clean tree, in sync with remote) | (none) | branch-type color | `git status --porcelain` empty AND `git rev-list --count @{u}..HEAD` returns 0 |
| **ahead** (clean tree, local commits not on remote, OR no upstream) | `+` | orange `#f97316` (matches gradient 56–65%) | clean tree AND (`@{u}..HEAD` count > 0 OR no upstream tracker) |
| **dirty** (uncommitted changes — staged or unstaged) | `*` | red `#dc2626` (matches gradient 80%+) | `git status --porcelain` non-empty |

### State priority

`dirty` > `ahead` > `pushed`. Any uncommitted change (even a `git add`-staged file with no working-tree modification) triggers red `*`. Once you commit, the tree becomes clean and either orange `+` (commits not yet pushed) or branch-type color (in sync with remote) applies.

### Color rationale

The state colors deliberately reuse the **same RGB values** from the canonical 6-tier gradient (§8.12) — orange for `+` matches the 56–65% gradient stop, red for `*` matches the 80%+ stop. This keeps the whole statusline on a unified palette: green = healthy, orange = action needed (push or commit), red = problem (uncommitted work).

Branch-type colors (blue / purple) are only used when state is "pushed" and add a visual cue for which long-lived branch you're on without consuming horizontal space for an icon.

### Self-omit fallback

When `git rev-parse` fails (not in a repo, git not installed, etc.), `GIT_PART` stays empty and line 1 falls through cleanly to `[Label] | Model` with no dangling separator. Safe to drop the `.claude/` template into non-git directories.

### Test recipe

```bash
# Throwaway repo to verify each state combination:
TMPREPO=$(mktemp -d) && TMPREMOTE=$(mktemp -d)
git -C "$TMPREMOTE" init -q --bare
cd "$TMPREPO" && git init -q -b main
git remote add origin "$TMPREMOTE"
echo hi > x && git add x && git -c user.email=t@t -c user.name=t commit -qm i && git push -qu origin main
# main, clean, pushed → BLUE
echo '{"context_window":{"used_percentage":50},"model":{"display_name":"S"}}' | bash /path/to/.claude/statusline.sh

echo dirty >> x  # modify
# main, dirty → RED *
echo '{"context_window":{"used_percentage":50},"model":{"display_name":"S"}}' | bash /path/to/.claude/statusline.sh

git -c user.email=t@t -c user.name=t commit -qam ahead
# main, ahead (committed but not pushed) → ORANGE +
echo '{"context_window":{"used_percentage":50},"model":{"display_name":"S"}}' | bash /path/to/.claude/statusline.sh
```

---

## 8.10 Line 3 — system stats (CPU / RAM / drive)

A new third row surfaces local machine resource usage so you can see at a glance whether your dev box is under stress while you're working:

```
Line 3:  cpu N% ×K | ram U/TG | <drive-label> FG / TG free
```

| Segment | Source (Linux) | Source (Windows) | Format |
|---------|----------------|------------------|--------|
| `cpu N% ×K` | `/proc/loadavg` 1-min load ÷ `os.cpu_count()` × 100 (clamped to 100%); cores from `os.cpu_count()` | `ctypes.windll.kernel32.GetSystemTimes` → `(idle, kernel, user)` FILETIMEs; sidecar cache `~/.claude/cpu-cache.json` holds the previous render's tuple so the next render computes a delta (kernel includes idle, so total = kernel + user, busy = total - idle); cores from `os.cpu_count()` | percentage + `×<core-count>` cyan suffix |
| `ram U/TG` | `/proc/meminfo` `MemTotal` and `MemAvailable` | `ctypes.windll.kernel32.GlobalMemoryStatusEx` → `MEMORYSTATUSEX.{ullTotalPhys, ullAvailPhys}` (the same "Available" figure Task Manager shows: free + standby cache) | used / total in GB |
| `<drive-label> FG / TG free` | `shutil.disk_usage('.')` → `du.free` and `du.total`; label from `findmnt LABEL/TARGET` | `shutil.disk_usage('.')` → `du.free` and `du.total`; label from `os.path.splitdrive(os.getcwd())` → `C:/` / `F:/` | drive identifier (cyan) + `<free>G / <total>G` (gradient) + `free` (cyan suffix) |

### CPU cores suffix (§8.14)

The `×K` segment uses Unicode `×` (U+00D7 multiplication sign — visually distinct from lowercase `x`) followed by the integer core count from `os.cpu_count()`. Cyan-colored to match the cyan label palette. Self-omits when `os.cpu_count()` returns `None` (rare — virtualized environments without `/proc/cpuinfo`).

### Drive label resolution (§8.14)

The cyan label slot — previously the literal string `drive` — now displays the actual drive identifier so you can see WHICH drive without parsing the project path:

| Platform | Source | Examples |
|----------|--------|----------|
| Windows | `os.path.splitdrive(os.getcwd())[0]` + trailing `/` | `C:/`, `F:/`, `D:/` |
| Linux (labeled partition) | `findmnt -no LABEL --target $cwd` | `External`, `HDD1`, `SSD`, `Backup` |
| Linux (unlabeled partition) | `findmnt -no TARGET --target $cwd` (mountpoint fallback) | `/`, `/home`, `/mnt/data` |
| macOS / BSD / no findmnt | exception path | `drive` (literal — same as pre-§8.14) |

The two `findmnt` calls add ~5–15ms per render on Linux — well within the sub-100ms budget. No sidecar cache; the partition label rarely changes mid-session, but the cost is small enough that caching adds complexity without a meaningful speedup.

### Why this approach

- **Linux uses stdlib only** — `/proc/*` reads + `shutil.disk_usage` are sub-millisecond, fast enough to run every render with no caching infrastructure.
- **Windows uses ctypes → kernel32** — `GlobalMemoryStatusEx` (RAM) returns instantly; `GetSystemTimes` (CPU) returns instantly but a single sample is meaningless, so a tiny sidecar cache (`~/.claude/cpu-cache.json`, ~70 bytes) holds the previous render's `(idle, kernel, user)` FILETIMEs and the next render computes a delta. No `wmic`, no PowerShell, no subprocess shell-out — both reads stay sub-millisecond, matching the Linux stdlib path's render-budget profile. **First render after launch shows `cpu —`** because no prior sample exists yet; the cache seeds on that render and every render after is accurate. The CPU sidecar is independent of the GPU sidecar (`~/.claude/gpu-cache.json`, §8.11) — different TTL semantics (CPU = always-overwrite-with-latest; GPU = 5s freshness).
- **Disk works everywhere** — `shutil.disk_usage` is cross-platform stdlib and reads the filesystem of the script's CWD. Claude Code invokes the statusline with the project root as CWD, so the segment naturally reports the project's drive.

### Color rules

Same green / yellow / red threshold as the ctx and rate-limit bars: `<60%` green, `60–80%` yellow, `>80%` red. Cyan label (`cpu`, `ram`, plus the resolved drive identifier from §8.14 — `C:/`, `SSD`, `External`, `/`, etc.) matching the `up` / `think` / `CTX` / `5h-countdown` / `7d-countdown` label convention.

For disk specifically, the threshold is on **percent used** (matching the other gauges' semantics — high % = bad). `261G / 954G free` showing orange means the drive is 66–79% full overall (i.e. 73% used in this case — `(954-261)/954`), even though the absolute free figure looks plentiful. The literal word `free` is split out as a cyan suffix (it's a label, not a value), so only the gigabyte numbers carry the gradient color.

### Self-omitting fallback

If a stat fails (e.g., `/proc/loadavg` unreadable, no `MemAvailable` in older kernels, disk path inaccessible), that single segment renders as a dim-grey `—` placeholder while the rest of line 3 stays intact. If the entire Python block fails (parse error, etc.), `SYS3` ends up empty and the bash `[ -n "$LINE3" ] && echo` guard skips line 3 entirely — degrades to two-line layout cleanly.

### Test recipes

```bash
# Linux full render — drive label = partition label or mountpoint
echo '{"context_window":{"used_percentage":8},"model":{"display_name":"Claude Opus 4.7"}}' | bash .claude/statusline.sh
# Line 3 → cpu 13% ×16 | ram 11.4/61.6G | SSD 261G / 954G free
#                  ^^^                     ^^^ ^^^^^^^^^^^^ ^^^^
#                  cores from              |   gradient     cyan
#                  os.cpu_count()          |   (% used)     suffix
#                                          partition LABEL from findmnt
#                                          (or '/' / mountpoint when LABEL empty)

# Windows render — drive label = drive letter, CPU/RAM via ctypes -> kernel32
# Line 3 → cpu 62% ×16 | ram 21.0/127.9G | C:/ 107G / 931G free
# (First render after Claude Code launches shows `cpu —` while the sidecar cache
#  seeds; every render after that computes the (kernel + user - idle) delta and
#  shows accurate CPU%. RAM is always accurate from render 1 — no delta needed.)

# Broken JSON → line 3 self-omits via empty LINE3
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

## 8.13 Canonical bar geometry — Unicode block-fill cells

Every progress bar (ctx, 5h, 7d) renders as a **16-cell × 8-sub-level** Unicode block bar — total resolution 128 sub-cells, **~0.78% per sub-step** vs. the previous 6.67% per cell with `#`/`-`.

```
0%    [                ] 0%      empty (16 spaces)
25%   [████            ] 25%     4 full + 12 empty
50%   [████████        ] 50%     8 full + 8 empty
79%   [████████████▋   ] 79%     12 full + ▋ + 3 empty
100%  [████████████████] 100%    16 full
```

### Glyph ladder (8 sub-levels per cell)

| Fraction | Char | Code |
|----------|------|------|
| 0/8 | ` ` (space) | `U+0020` |
| 1/8 | `▏` | `U+258F` |
| 2/8 | `▎` | `U+258E` |
| 3/8 | `▍` | `U+258D` |
| 4/8 | `▌` | `U+258C` |
| 5/8 | `▋` | `U+258B` |
| 6/8 | `▊` | `U+258A` |
| 7/8 | `▉` | `U+2589` |
| 8/8 | `█` | `U+2588` |

### Helper

```python
def _make_bar(p, cells=16):
    LEVELS = [' ', '▏', '▎', '▍', '▌', '▋', '▊', '▉']
    sub_total = cells * 8
    filled_sub = max(0, min(sub_total, int(round(p / 100 * sub_total))))
    full = filled_sub // 8
    rem = filled_sub % 8
    if full >= cells:
        return '█' * cells
    return '█' * full + LEVELS[rem] + ' ' * (cells - full - 1)
```

### Why 16 × 8

- 16 cells × 8 sub-levels = 128 total sub-cells, **100/128 = 0.78125% granularity**.
- 16 cells fits comfortably under the model + git segments on line 1 alongside two more 16-cell bars on line 2.
- 8 sub-levels matches the standard Unicode block-fill range (`U+2588` through `U+258F`) — every modern terminal renders them correctly.

### Bash eval-quoting footgun (caught + fixed)

When implementing the multi-space padding (`[████            ]`), the bars rendered as `[████ ]` — 11 trailing spaces collapsed into 1. Root cause: the script's `eval $(echo "$input" | python3 -c "...")` had **unquoted** command substitution. Bash word-splits `$(...)` output, replacing whitespace runs with single field separators before `eval` sees it. Fix: change to `eval "$(...)"` — the outer double quotes treat the substitution result as a single string, preserving whitespace inside the quoted variable assignments. This was a latent bug that didn't manifest with the old `#`/`-` bars (no consecutive spaces) but broke immediately with the new space-padded layout.

---

## 8.14 Cross-platform polish — drive labels, core suffix, prefixes, reset countdowns, centering

Seven features that round out the statusline render: cross-platform drive label resolution, CPU core-count suffix on the cpu segment, `CTX` prefix on the context bar, time-to-reset countdowns on the 5h/7d rate-limit labels, dynamic centering across all four lines, and split-coloring on the drive free-space segment.

### Visual breakdown

```
Without these features                                With them
[Label] | up · think | Model | branch                 [Label] | up · think | Model | branch
[ctx] N% | 5h [..] N% | 7d [..] N%                    CTX [ctx] N% | 4h12m [..] N% | 5d03h [..] N%
cpu N% | ram U/T G | drive NG free                        cpu N% ×16 | ram U/T G | SSD FG / TG free
gpu1 U/T 0% | gpu2 U/T 0%                                       gpu1 U/T 0% | gpu2 U/T 0%
^                                                     ^^^^^^^^^^^^^^^^^
left-aligned                                          dynamically centered (each line independently)
```

### Feature reference

| # | Feature | Implementation |
|---|---------|----------------|
| 1 | Drive label per-platform | `os.path.splitdrive` on Windows; `findmnt -no LABEL` then `findmnt -no TARGET` fallback on POSIX. `_get_drive_label()` helper feeds the cyan label slot of the drive segment in `_sys_seg(...)`. |
| 2 | `×cores` after cpu% | `os.cpu_count()` provides the core count; `cores_suffix` cyan-colored `×K` appended via `_sys_seg(...)`'s `suffix` parameter. Self-omits when `cpu_count()` returns None. |
| 3 | `CTX` prefix on context bar | `ctx_str` f-string prepends cyan `CTX` matching the rate-limit / sys-stat / uptime cyan-label palette. |
| 4 | 5h label → time-to-reset | `_reset_label('5h', resets_at, now_ts)` formats `resets_at - time.time()` with the same time ladder as `_fmt_ms`. Falls back to literal `5h` when reset is missing or in the past. |
| 5 | 7d label → time-to-reset | Same `_reset_label('7d', ...)` helper. |
| 6 | Dynamic centering (best-effort) | `tput cols < /dev/tty` from bash → `TERM_COLS` env → python `_center()` strips ANSI via the precompiled `ANSI_RE`, prepends `(cols - visible) // 2` spaces. Each line centers independently. Fallback ladder: `tput` → `$COLUMNS` → 80; negative pad clamps to 0 (left-align). |
| 7 | Drive `<free>G / <total>G free` with split coloring | `disk_total_gb_val` computed alongside `disk_free_gb` from `shutil.disk_usage('.').total`. `disk_val` rebuilt as `f'{free}G / {total}G'` (gradient via `_sys_seg`). `free_suffix = ' \033[36mfree\033[0m'` passed as `_sys_seg`'s suffix slot so the cyan word lands AFTER the gradient block's `\033[0m` reset. Self-omits when disk metrics unavailable. Example render: `SSD 261G / 954G free` — `SSD` cyan, `261G / 954G` orange (73% used → §8.12 orange-600 stop), `free` cyan. |

### Implementation note — composition in Python

To keep dynamic centering inside the existing single python subprocess (avoiding a second python startup that would push the render past the sub-100ms budget), all four lines compose in Python rather than bash:

- Bash still computes `GIT_PART` (cheap git shell-outs) and `TERM_COLS`.
- Both pass into Python as env vars (`GIT_PART_RAW`, `TERM_COLS`).
- Python composes line 1's conditional UPTIME fallback (`if uptime_part: ... else: ...`), centers each line via `_center()` (uses the precompiled `ANSI_RE`), and emits `LINE1="..." LINE2="..." LINE3="..." LINE4="..."`.
- Bash `eval`s the four assignments and `echo -e`s each (with `[ -n "$LINEN" ]` guards on lines 2-4 for the exception fallback path).

### Source-of-truth for `resets_at`

Empirically verified shape (capture via temp-tee debug — `echo "$input" > /tmp/sl-debug.json` between `input=$(cat)` and the heredoc):

```json
"rate_limits": {
  "five_hour": { "used_percentage": 61, "resets_at": 1778384400 },
  "seven_day": { "used_percentage": 17, "resets_at": 1778659200 }
}
```

`resets_at` is an **integer Unix epoch seconds** value, not ISO 8601. The countdown is just `int(resets_at - time.time())` formatted via the existing time-ladder. Full schema dump in §10.

### Centering edge cases

- **Terminal narrower than line content** → negative pad clamps to 0; line renders left-aligned and overflows the right edge.
- **No `/dev/tty`** (sandboxed env, container without TTY) → `tput cols` fails; `${COLUMNS:-80}` fallback; centering lands on a virtual 80-column width which still produces a reasonable visual on most terminals.
- **Windows + Git Bash mintty** → `tput cols < /dev/tty` works; mintty exposes a TIOCGWINSZ-compatible ioctl.
- **Multi-byte unicode** (block-fill glyphs, `×`, `—`) → counted by Python `len()` which counts code points (not bytes). The block-fill chars are 1 column wide so `len()` matches visual width. For wider unicode (CJK, emoji) we'd need `wcwidth` — not currently a dependency, would require a follow-up if such characters ever entered a label.
- **ANSI escape stripping** → uses precompiled `ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')` matching the `[<digits or ;>]m` form (color/style escapes only). Cursor-movement escapes aren't stripped but we don't emit any.

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
> ✓ **Implemented**: git branch with state-aware coloring (main blue / develop purple / feature green; pushed = branch color, ahead = orange `+`, dirty = red `*`). See §8.9 above for the full state matrix.
> ✓ **Implemented**: line 3 system stats — CPU, RAM, drive free space. Linux uses stdlib (sub-ms reads); Windows uses `ctypes → kernel32` (`GlobalMemoryStatusEx` for RAM, `GetSystemTimes` + sidecar cache `~/.claude/cpu-cache.json` for CPU delta — both sub-ms, no `wmic` shell-out); disk works cross-platform via `shutil.disk_usage`. See §8.10 above for fallback behavior.
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

## 10. Reference: empirically-captured statusline JSON schema (CC 2.1.138)

Captured 2026-05-09 via temp-tee in `.claude/statusline.sh` (`echo "$input" > /tmp/sl-debug.json` between `input=$(cat)` and the heredoc) running against Claude Code 2.1.138 in this project. Use this as the **source of truth** when planning new segments — Anthropic's docs at [code.claude.com/docs/en/statusline](https://code.claude.com/docs/en/statusline) are not always exhaustive or current.

### Full live capture

```json
{
    "session_id": "3113828a-6e60-4817-a3ce-232df428ba0c",
    "transcript_path": "/home/sponge/.claude2/projects/-mnt-0C38361B292A2255-Development-UnityAILab-UAL-ClaudeWorkflow/3113828a-6e60-4817-a3ce-232df428ba0c.jsonl",
    "cwd": "/mnt/0C38361B292A2255/Development/UnityAILab/UAL-ClaudeWorkflow",
    "effort": { "level": "xhigh" },
    "session_name": "ClaudeWorkflow",
    "model": {
        "id": "claude-opus-4-7[1m]",
        "display_name": "Opus 4.7 (1M context)"
    },
    "workspace": {
        "current_dir": "/mnt/0C38361B292A2255/Development/UnityAILab/UAL-ClaudeWorkflow",
        "project_dir": "/mnt/0C38361B292A2255/Development/UnityAILab/UAL-ClaudeWorkflow",
        "added_dirs": []
    },
    "version": "2.1.138",
    "output_style": { "name": "default" },
    "cost": {
        "total_cost_usd": 9.378615499999997,
        "total_duration_ms": 5488065,
        "total_api_duration_ms": 1661996,
        "total_lines_added": 692,
        "total_lines_removed": 594
    },
    "context_window": {
        "total_input_tokens": 108070,
        "total_output_tokens": 8,
        "context_window_size": 1000000,
        "current_usage": {
            "input_tokens": 6,
            "output_tokens": 8,
            "cache_creation_input_tokens": 397,
            "cache_read_input_tokens": 107667
        },
        "used_percentage": 11,
        "remaining_percentage": 89
    },
    "exceeds_200k_tokens": false,
    "fast_mode": false,
    "thinking": { "enabled": true },
    "rate_limits": {
        "five_hour":  { "used_percentage": 61, "resets_at": 1778384400 },
        "seven_day":  { "used_percentage": 17, "resets_at": 1778659200 }
    }
}
```

### Per-field annotation

| Field | Type | Status | Notes |
|-------|------|--------|-------|
| `session_id` | string (UUID) | ✓ used | Drives the §8.5 hash-color palette when `session_name` is set. Stable for the session lifetime. |
| `transcript_path` | string (abs path) | candidate | §9 brainstorm (idle timer, tool-call count, files modified, last-prompt blurb, cache-hit rate, sub-agent depth) all derive from this — single file read per render. |
| `cwd` | string (abs path) | implicit | Same as `os.getcwd()` inside the script; we use the latter for cross-platform parity (e.g. `pwd -W` Git Bash quirk). |
| `effort.level` | string enum | candidate | `low` / `medium` / `high` / `xhigh` / `max` — could surface as a small gradient indicator (`░▒▓`) on line 1. |
| `session_name` | string (optional) | ✓ used | §8.5 — set via Claude Code's `/rename` slash command. Empty/absent on un-renamed sessions. |
| `model.id` | string | ✓ used (regex) | §8.6 — `MiniMax-?M?<digits>` regex matches against `display_name + id` for provider-override classification. |
| `model.display_name` | string | ✓ used | §8.6 — primary classifier for Opus/Sonnet/Haiku branches. Note: 1M-context Opus shows `Opus 4.7 (1M context)`, not `Claude Opus 4.7`, so the `'Opus' in model_disp` substring check is what triggers correctly. |
| `workspace.current_dir` | string (abs path) | unused | Same as `cwd` in this capture; might diverge if Claude Code adds workspace switching. |
| `workspace.project_dir` | string (abs path) | unused | Same as `current_dir` in this capture. |
| `workspace.added_dirs` | array | unused | Empty in this capture; would populate when user adds extra context dirs via Claude Code config. |
| `version` | string (semver) | candidate | Useful for version-conditional rendering (e.g. only enable a feature if CC ≥ 2.1.138). |
| `output_style.name` | string | candidate | `default` / others — could surface as a small badge if/when alt styles ship. |
| `cost.total_cost_usd` | float | **candidate (high value)** | §9 brainstorm — real-time spend awareness. Trivial to add. Color thresholds: `<$2` green, `$2-5` yellow, `>$5` red. |
| `cost.total_duration_ms` | int | ✓ used | §8 — feeds the `up` (uptime) timer via `_fmt_ms`. |
| `cost.total_api_duration_ms` | int | ✓ used | §8 — feeds the `think` timer. The closest signal to "time Claude has been thinking." |
| `cost.total_lines_added` | int | candidate | §9 brainstorm — `+L -R` diff scope at a glance. Visible on line 1 alongside model. |
| `cost.total_lines_removed` | int | candidate | (paired with `total_lines_added`) |
| `context_window.total_input_tokens` | int | candidate | §9 brainstorm — `47k/200k` token gauge alongside the percentage. |
| `context_window.total_output_tokens` | int | candidate | (output is usually tiny relative to input — small badge if anything) |
| `context_window.context_window_size` | int | candidate | Denominator for the token gauge. `1000000` for 1M-context Opus, `200000` for standard. |
| `context_window.current_usage.input_tokens` | int | candidate | Per-turn input tokens (vs `total_input_tokens` cumulative). Could surface as a "this turn cost" indicator. |
| `context_window.current_usage.output_tokens` | int | candidate | Per-turn output. |
| `context_window.current_usage.cache_creation_input_tokens` | int | candidate | Per-turn fresh cache writes. |
| `context_window.current_usage.cache_read_input_tokens` | int | candidate | Per-turn cache hits. **§9 brainstorm cache-hit-rate** can be derived from `cache_read / (cache_read + cache_creation + input)`. |
| `context_window.used_percentage` | int | ✓ used | §8 — primary ctx bar percentage. |
| `context_window.remaining_percentage` | int | redundant | `100 - used_percentage`; not used. |
| `exceeds_200k_tokens` | bool | candidate | True when context > 200k (1M-context Opus only). Could surface as a small badge. |
| `fast_mode` | bool | candidate | True when `/fast` is active (Opus 4.6 fast variant). Could surface as a small `⚡` badge. |
| `thinking.enabled` | bool | candidate | §9 brainstorm — `🧠` badge when true. |
| `rate_limits.five_hour.used_percentage` | int | ✓ used | §8.7 — bar value. |
| `rate_limits.five_hour.resets_at` | int (Unix epoch) | ✓ used | §8.14 — countdown label. **Verified seconds, not milliseconds, not ISO 8601.** |
| `rate_limits.seven_day.used_percentage` | int | ✓ used | §8.7 — bar value. |
| `rate_limits.seven_day.resets_at` | int (Unix epoch) | ✓ used | §8.14 — countdown label. |

### How to re-capture if the schema changes

Anthropic may add/remove/rename fields in future CC releases. To re-capture:

1. Edit `.claude/statusline.sh`, add `echo "$input" > /tmp/sl-debug.json 2>/dev/null` immediately after `input=$(cat)`.
2. Trigger a render — any user prompt or tool call will refresh the statusline.
3. Inspect: `cat /tmp/sl-debug.json | python3 -m json.tool`.
4. **Revert the tee** before committing — never ship the debug write.

This is the same procedure used to verify §8.5 (`/color` doesn't persist anywhere readable) and §8.14 (`resets_at` shape). Update this section's capture if the schema diverges materially from what's documented above.

### Fields NOT exposed (verified absent in CC 2.1.138)

- **`/color` selection** — verified empirically in §8.5; no field carries the user-set color through to the statusline. Whatever `/color` does, stays inside the running CC process.
- **Terminal width / size** — no `terminal.{width,height}` field; the script gets terminal dimensions via `tput cols < /dev/tty` from bash and falls back to `$COLUMNS` env or 80.
- **Active subagent / Task tool state** — no field exposes whether a subagent is currently running. Would need to derive from `transcript_path` parsing.
- **Hook firing signals** — no field. §9 brainstorm "hook firing indicator" needs a sidecar file written by hook scripts.

---

**File**: `.claude/statusline.sh` (UAL template) · `C:/claude/shared/statusline.sh` (FDC bot-system, § 1–7)
**Wired in**: `.claude/settings.json` → `statusLine.command` (project-level) · `~/.claude/settings.json` (global, FDC)
**Side-effect files**: `~/.claude/context_pct.txt` (every render — context %) · `~/.claude/gpu-cache.json` (5s TTL, §8.11) · `~/.claude/cpu-cache.json` (Windows only, every render — `(idle, kernel, user)` FILETIMEs for next-render CPU delta, §8.10)
**Per-project identity**: derived from cwd basename, no config needed
