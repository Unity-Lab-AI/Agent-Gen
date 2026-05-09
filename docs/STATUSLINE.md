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

Both labels render in cyan (`\033[36m`) so they're visually distinct from the green/yellow/red context bar without competing with the model abbreviation.

### Graceful fallback

If the `cost` block is absent, malformed, or both values are zero (fresh session, never made an API call), the leading separator is omitted entirely so the line collapses cleanly to `[Project] | [bar] X% | Model` with no dangling `| ·` fragments.

### Test recipe

```bash
echo '{"context_window":{"used_percentage":45},"model":{"display_name":"Claude Opus 4.7"},"cost":{"total_duration_ms":5012345,"total_api_duration_ms":161234}}' | bash .claude/statusline.sh
# → [Project] | [######---------] 45% | O4.7 | up 1h23m · think 2m41s
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
| **5-hour rate limit** | `rate_limits.five_hour.used_percentage` | `5h: 23%` (yellow >70%, red >90%) | Pro/Max users — pace warning |
| **7-day rate limit** | `rate_limits.seven_day.used_percentage` | `7d: 11%` | Long-arc usage tracking |
| **Session name** | `session_name` | `«recovery-branch»` if set | Context-switching between named sessions |
| **Model variant** | `model.id` | full ID on hover, shortened in line | Distinguish 1M-context from standard |

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
| **Git branch** | `git rev-parse --abbrev-ref HEAD` | `[main]` / `[feature/foo]` |
| **Dirty working tree** | `git status --porcelain` non-empty | `*` suffix on branch name |
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
