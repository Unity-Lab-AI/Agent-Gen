# FINALIZED — Permanent Task Archive

Permanent archive of every completed task. Per `.claude/CONSTRAINTS.md §NEVER DELETE TODO INFO` + `§FINALIZED BEFORE DELETE`, no entry is EVER deleted from this file. New entries APPEND only.

Per LAW #0, every entry includes the user's verbatim words from the original ask.

Each session entry includes:
- `## Session <YYYY-MM-DD>` — date heading
- Verbatim user quote
- Files touched
- Closure notes (what shipped, verification)

---

## Session 2026-05-09

### Statusline label adapts to /rename + auto-color per session

**Verbatim user quote:** "The color of the project name should auto-update if the color for the session has been set to match that, and if named using the rename should reflect there as well, can you make that change?"

**Verbatim user follow-up:** "I also just set the color and name so re-check potentially the global .claude and the project level .claude"

**Verbatim user palette decision:** "Random selection of a color then" (selected via AskUserQuestion after empirical confirmation that `/color` doesn't persist anywhere readable to the statusline script).

**Files touched:**
- `.claude/statusline.sh` — Python block parses `session_name` + `session_id` from stdin JSON; label = renamed value or cwd basename fallback; color = MD5(session_id) → 12-color ANSI palette when renamed, magenta `35` when not. `LABEL` exported via eval, replaces hardcoded `${B}[${PROJECT_NAME}]${R}`. `B`/`R` dead vars removed.
- `docs/STATUSLINE.md` — added §8.5 "Label & color — auto-adapt to /rename" documenting the new rules + why hash-based instead of /color (verified empirically that `/color` doesn't persist). Removed `session_name` row from §9 brainstorm table since it's now shipped; added inline ✓ implemented note pointing to §8.5.

**Closure notes:**
- Empirically verified Claude Code 2.1.138 does NOT expose `/color` value to the statusline JSON (captured live JSON via stdin tee, checked `~/.claude.json`, `~/.claude/sessions/<pid>.json`, project `.claude/`). Documented in code comments + §8.5.
- 4 test scenarios passed: (a) renamed `UnityWorkflow` + real session_id → bright green palette slot, (b) different session_id → blue (different hash), (c) no rename → cwd basename + magenta (original behavior preserved), (d) broken JSON → magenta fallback label + `?` for ctx/model.
- Branch: `feature/extra-status-bar-features` off `develop`. Atomic commit will bundle code + doc per `§DOCS BEFORE PUSH` LAW.

### Per-model color + MiniMax extension

**Verbatim user quote:** "Lets make it so different models will disaply different things, also extend support to minimax (look at global .claude minimax.json for refference on that specific model) Opus models, sonnet, and haiku can all use the same O#.#, S#.#, H#.# format, but, I want opus to be orange / gold (closest to gold, orange if no close to gold), I want haiku to be blue (closest), and I want sonnet to be red. For the minimax models we should do a purple and do M#.#"

**Files touched:**
- `.claude/statusline.sh` — model classifier rewritten: regex `(?i)MiniMax-?M?(\d+(?:\.\d+)?)` against `display_name + id`, then Opus/Sonnet/Haiku branches against `display_name`. Each family assigns both abbreviation (`O#.#`/`S#.#`/`H#.#`/`M#.#`) and color escape. New `model_str` wraps the abbreviation in the family color before being eval'd into `MODEL` for the bash echo.
- `docs/STATUSLINE.md` — new §8.6 "Model abbreviation + family color" with the full family/color/escape table, MiniMax detection rationale, and test recipes for all four families.

**Color choices:**
- Opus → truecolor gold `\033[38;2;255;215;0m` (CSS `#FFD700`). Named ANSI has no gold/orange equivalent; bright yellow (93) reads as lemon, not gold. Truecolor is doc-silent passthrough but works on any modern terminal.
- Sonnet → bright red `\033[91m` (named).
- Haiku → bright blue `\033[94m` (named).
- MiniMax → bright magenta `\033[95m` (named, purple-ish).
- Unknown family → `\033[0m` reset, full `display_name` preserved.

**Closure notes:**
- 6 test scenarios passed: Opus/Sonnet/Haiku each render with correct family color + abbrev; MiniMax detected via both `display_name` path and `id`-only path; unknown model falls through to terminal-default color with full name preserved.
- MiniMax model name format reference taken from `~/.claude/minimax.json` (`ANTHROPIC_MODEL=MiniMax-M2.7`, plus the four `ANTHROPIC_DEFAULT_*_MODEL` aliases all set to the same value).
- Bundled in same feature branch (`feature/extra-status-bar-features`); separate atomic commit since this is a distinct ask + closure cycle.

### Timer values render bright white

**Verbatim user quote:** "Now the up and think, those arent colored at all ('up' and 'think' are colored), so they render as normal terminal text, can we make the time on those render white?"

**Files touched:**
- `.claude/statusline.sh` — wrapped `{uptime_fmt}` and `{think_fmt}` in `\033[97m...\033[0m` (bright white) inside the existing `uptime_part` and `think_part` f-strings. Cyan labels (`up` / `think`) unchanged.
- `docs/STATUSLINE.md` §8 — updated copy describing label + value color split.

**Closure notes:**
- Bright white (97) chosen over plain white (37) because terminal-default white often renders as light gray on dark themes, which was the original problem. 97 forces the value to pop next to the cyan label.
- Verified output via test recipe → `[36mup[0m [97m9m14s[0m · [36mthink[0m [97m4m50s[0m`.

### Separators render bright green

**Verbatim user quote:** "The pipes in between the sections, can we render those as bright green?"

**Verbatim user follow-up:** "And the dot inbetween up and think, make that green too"

**Files touched:**
- `.claude/statusline.sh` — `PIPE="\033[92m|\033[0m"` defined in the bash render block; the two main pipes in the echo line now use `$PIPE`. The third pipe (inside `uptime_part`) and the `·` middle-dot (inside `think_part`) both wrapped in `\033[92m...\033[0m` so they pick up the same bright-green when present and stay auto-omitted when no cost block exists.
- `docs/STATUSLINE.md` §8 — extended copy: ALL separators (pipes + middle-dot) render bright green now; auto-omit behavior on fresh sessions explained.

**Closure notes:**
- Verified output: `[92m[UnityWorkflow][0m [92m|[0m [bar] [92m|[0m [model] [92m|[0m [36mup[0m [97m9m14s[0m [92m·[0m [36mthink[0m [97m4m50s[0m` — every separator green, segments untouched.
- Fresh-session render (no cost block) collapses cleanly to two pipes between LABEL/CTX/MODEL with no dangling separators.

### Rate-limit usage bars — 5h session + 7d weekly

**Verbatim user quote:** "Now can we add another section that will display like the context window bar, two actually, one for current session usage and another for weekly usage?"

**Files touched:**
- `.claude/statusline.sh` — Python block adds local `_pct_bar(p)` helper that returns the colored `[####---] N%` string for any 0–100 percentage. Uses the same 15-char width and same green/yellow/red threshold as the existing ctx bar. Two new f-string parts (`rate5h_part`, `rate7d_part`) wrap the helper output with cyan `5h`/`7d` labels and a leading bright-green pipe separator. Both parts self-omit when their respective `rate_limits.{five_hour,seven_day}.used_percentage` is missing. Print statement extended to emit `RATE5H="..."` and `RATE7D="..."` for bash to eval. Bash echo line places `$RATE5H$RATE7D` immediately after `$CTX` so the gauges group together visually before the model and timer sections.
- `docs/STATUSLINE.md` — new §8.7 "Rate-limit usage bars — 5h session + 7d weekly" with the full table, threshold rules, self-omit behavior, test recipes, and a "footgun fixed" note about backticks. §9 brainstorm rows for 5h/7d removed (now shipped) + new ✓ implemented note added pointing to §8.7.

**Footgun caught + documented:**
- Backticks inside Python comments embedded in the `python3 -c "..."` bash heredoc trigger BASH command substitution before Python ever parses the script. Original comment used `\`rate_limits\``, `\`up\``, `\`think\`` around code-like terms — bash tried to execute them as shell commands and threw `command not found` errors on every render. Fix: NO backticks anywhere in the Python heredoc. Documented in §8.7 + an inline NOTE comment in the script so future edits don't reintroduce.
- A second bug landed first attempt: f-string with `\"#\"` and `\"-\"` inside an expression — Python f-string expressions don't allow backslash-escaped quotes (PEP 701 lifted some restrictions in 3.12 but not all). Fix: precompute the bar string outside the f-string (matches the pattern the existing ctx block already uses).

**Closure notes:**
- 5 test scenarios passed: (a) both bars with mixed colors, (b) all three bars hitting different thresholds (red/green/yellow), (c) only 5h present (7d auto-omits cleanly), (d) no rate_limits block at all (both auto-omit, free-plan friendly), (e) broken JSON falls through to fallback label + `?` for ctx/model.
- All four prior commits' behavior preserved — label color rotation, model family colors, bright-white timer values, bright-green separators all still render correctly.
