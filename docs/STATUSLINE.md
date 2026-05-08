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

---

**File**: `C:/claude/shared/statusline.sh`
**Wired in**: `~/.claude/settings.json` → `statusLine.command`
**Side-effect file**: `~/.claude/context_pct.txt`
**Per-bot identity**: derived from cwd, no config needed.
