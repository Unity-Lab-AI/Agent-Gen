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

### Two-line static layout

**Verbatim user quote:** "Does it support multi-line for the status line? Cause we are getting really long on the status line currently."

**Verbatim user follow-up:** "well, we have the project name, the context, the 5h, the 7d, the model, the up and think, and theres still more I want to add that I think would be useful... I was thinking of putting it so the unity workflow + up and think, and the model are on the top line, the context, 5h, and 7d could be on the second line, and we just display that? -- or actually, lets think about this, cant we do a 'rolling' display where we display some info, then other info, then other info, in a loop, so we can have one thing show for 10 seconds, another thing for 10 seconds, and what not? We could limit 3 sections per thing right?"

**User layout decision (via AskUserQuestion):** Two-line static (their first idea). Future sections to plan for: Git branch + dirty flag, CPU / GPU / RAM utilization (GPU as its own with model + VRAM + utilization %, e.g., `4070s v0.3gb 5%`).

**User decision against rolling:** Discussed but ruled out — rolling display is technically possible (script reads time.time() and picks frame), but only "ticks" when CC actively refreshes. During idle the line freezes on whatever frame happened to render last; user loses glance-ability ("what's my 7d burn right now?"); changing/animated info is attention-stealing where status lines should be passive-awareness. Static multi-line wins on reliability + glance-ability.

**Files touched:**
- `.claude/statusline.sh` — bash render block at the bottom rewritten to compose two lines. Line 1 = `[Label] | UPTIME · THINK | Model`, Line 2 = `[ctx-bar] | 5h | 7d`. Conditional fallback `if [ -n "$UPTIME" ]` avoids a double-pipe on line 1 when timers self-omit, since UPTIME's leading separator is baked into its f-string for the prior single-line auto-omit semantics. Final `echo -e "$LINE1"` + `echo -e "$LINE2"` pipes both to Claude Code's stdout.
- `docs/STATUSLINE.md` — new §8.8 "Two-line static layout" with: layout diagram, rationale (line length, rendering risks, semantic grouping), layout rules (line 1 / line 2 composition + banner-safety placement of ctx at start of line 2), implementation note about the conditional fallback, test recipes covering full + fresh-session renders. §9 brainstorm "implemented" notes extended with §8.8 entry.

**Closure notes:**
- 4 test scenarios passed: (a) full render with timers + both rate bars → two clean lines; (b) fresh session no cost no rate_limits → line 1 collapses to `[Label] | Model`, line 2 to `[ctx]` only; (c) timers present, no rate_limits → line 1 with timers, line 2 with ctx only; (d) broken JSON → both lines render with `?` placeholders.
- Multi-line rendering risk acknowledged in §8.8 ("more prone to rendering issues than single-line plain text" per Claude Code docs) — no observed garbling in local tests but documented for future reference.
- Architecture explicitly leaves room for future sections (git branch + system stats per user's roadmap) to be appended to either line or to spawn a third line.

### Git branch + dirty flag (line 1)

**Verbatim user quote:** "And how are we going about the git, gpu, cpu, ram, ext? I would like two more lines I think for this, and the git stuff I think can be on the first line after model, but the cpu, ram, and current project's drive's free same should be on a new line, and the GPU stuff should have it's own line. nvidia-smi, and if no GPU detected we just put in red 'No GPU Detected', should work for linux + windows."

(Multi-step ask — this entry covers the git branch+dirty piece. CPU/RAM/disk → next entry. GPU/nvidia-smi → entry after that.)

**Files touched:**
- `.claude/statusline.sh` — bash block before the eval computes `GIT_BRANCH` via `git rev-parse --abbrev-ref HEAD` and dirty state via `git status --porcelain | grep -q .`. Composes `GIT_PART` with leading bright-green pipe + green-clean / yellow-dirty branch name. Both line-1 composition branches (`if [ -n "$UPTIME" ]` and the no-cost fallback) append `$GIT_PART` after `$MODEL`. Self-omits cleanly in non-git directories.
- `docs/STATUSLINE.md` — new §8.9 "Git branch + dirty flag" with the source table, color rationale (matching git CLI conventions), self-omit fallback explanation, test recipes for both git-repo and non-git scenarios. §9 brainstorm rows for git branch + dirty working tree removed (now shipped); ✓ implemented note added pointing to §8.9.

**Closure notes:**
- Bash-side computation chosen over Python because `git` calls are quick (~5–20ms) and avoid round-tripping through the Python heredoc — render time stays well under the sub-100ms budget.
- 2 test scenarios passed: (a) in this repo with uncommitted changes → `feature/extra-status-bar-features*` in yellow appended after model on line 1; (b) in `/tmp` (non-git) → segment self-omits, line 1 collapses to `[tmp] | Model` cleanly.
- Color choice (green clean / yellow dirty) intentionally matches git CLI conventions for instant recognition; same hues as ctx bar threshold colors but distinct semantic context (static state vs gauge threshold).

### Line 3 — CPU / RAM / drive free space

(Continuation of the multi-step "git, gpu, cpu, ram, ext" ask above.)

**User scope decisions (via AskUserQuestion):**
- Windows CPU/RAM: ship Linux now, Windows wmic-cache later.
- Drive segment label correction: "free space" not "free same" (user's typo correction).

**Files touched:**
- `.claude/statusline.sh` — Python imports extended to include `re, shutil, platform` (re moved to top imports from inline lazy-import). New stats block before the print statement: CPU via `/proc/loadavg ÷ os.cpu_count() × 100` (Linux only, clamped to 100%); RAM via `/proc/meminfo` parsing `MemTotal` + `MemAvailable` (Linux only); disk via `shutil.disk_usage('.')` (cross-platform stdlib). Helper `_sys_color(p)` returns the `<60% green / 60–80% yellow / >80% red` ANSI code, `_sys_seg(label, value_str, pct)` composes the cyan-labeled colored segment with `—` dim-grey N/A fallback. `sys_line` joins the three segments with bright-green pipes. Print statement extended with `SYS3="..."`. Bash echo block adds `LINE3="$SYS3"` and `[ -n "$LINE3" ] && echo -e "$LINE3"` so empty SYS3 cleanly degrades to two-line layout.
- `docs/STATUSLINE.md` — new §8.10 "Line 3 — system stats (CPU / RAM / drive)" with source-by-platform table, rationale (stdlib speed on Linux vs wmic latency on Windows = deferred to cache infra), color rules, self-omit fallback explanation, test recipes. §9 brainstorm updated with ✓ implemented note.

**Closure notes:**
- Drive threshold is `% used` (matching the other gauges' semantic — high = bad). `261G free` showing yellow means the drive is 60–80% full overall, regardless of how plentiful the absolute free figure looks.
- 3 test scenarios passed: (a) full Linux render — three lines clean, all sections colored correctly; (b) broken JSON → line 3 omits cleanly via SYS3="" guard; (c) non-git dir → git segment self-omits, line 3 still renders correctly using CWD's filesystem.
- Architecture explicitly leaves room for the Windows wmic-cache follow-up (will refresh `~/.claude/syscache.json` periodically in the background; statusline reads cache for sub-ms latency).

### Line 4 — GPU(s) via nvidia-smi (with 5s sidecar cache)

(Final piece of the multi-step "git, gpu, cpu, ram, ext" ask above.)

**User format decision (via AskUserQuestion):** `4070s 0.3/12gb 5%` — short model name + used/total VRAM in GB + utilization %.

**User no-GPU spec:** Red "No GPU Detected" exactly.

**Cross-platform spec:** Linux + Windows; `nvidia-smi` ships with the official NVIDIA driver on every platform that supports CUDA cards.

**Files touched:**
- `.claude/statusline.sh` — Python imports extended with `subprocess, time`. New GPU block before the print: reads `~/.claude/gpu-cache.json` if mtime <5s old (sub-ms hit path); otherwise shell-out to `nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits` with 2s timeout, parse CSV per-GPU into a dicts list, write fresh cache. `FileNotFoundError` / `TimeoutExpired` / non-zero returncode all collapse to empty `{"gpus": []}` so the next 5 seconds of renders don't re-attempt. `_short_gpu(name)` regex extracts model digits + suffix (`SUPER→s`, `Ti→ti`); fallback truncates to 12 chars. Each GPU rendered as `<short> <used>/<total>gb <util>%` with cyan name + threshold-colored VRAM and util. Multi-GPU pipe-separated. When `gpus_list` is empty (driver missing OR no cards): red `\033[31mNo GPU Detected\033[0m`. Print statement extended with `GPU="..."`. Bash echo block adds `LINE4="$GPU"` and `[ -n "$LINE4" ] && echo -e "$LINE4"` so empty GPU on broken-JSON degrades to three-line layout.
- `docs/STATUSLINE.md` — new §8.11 "Line 4 — GPU(s) via nvidia-smi (with sidecar cache)" with: source command, cache TTL strategy, short-name regex table, color rules, self-omit fallback, multi-GPU + no-GPU test recipes, cross-platform note. §9 brainstorm updated with ✓ implemented note.

**Closure notes:**
- 4 test scenarios passed: (a) full render with two physical GPUs (4070 SUPER + 2060) → both render with correct short-names, VRAM, util; (b) empty cache file `{"gpus": []}` → "No GPU Detected" red; (c) cache deleted → nvidia-smi shells out, cache repopulates, line renders; (d) broken JSON → line 4 self-omits cleanly.
- Render-time impact: cache hit = +1ms (file read + JSON parse). Cache miss every 5s = +150ms once, then sub-ms for the next ~30 renders. Net average overhead: ~5ms.
- Color thresholds: VRAM `<60% green / 60–80% yellow / >80% red` (matching ctx, rate bars, system stats); util same scale. The 4070 SUPER at 9.5GB / 12GB shows yellow VRAM (~79%); at 100% util shows red.
- The script DOES write `~/.claude/gpu-cache.json` even on the FileNotFoundError path (writing `{"gpus": []}`). This intentional — caches the "no GPU" result for 5 seconds so the script doesn't shell-out repeatedly on every render in a no-GPU environment.

### 6-tier color gradient applied to every gauge

**Verbatim user quote:** "All the numbers and percentages and bars should be green <= 35% should be a green-ish yellow between 36% and 45%, yellow at 45% - 55%, orange at 56% - 65% red-orange at 65%-79% and red at 80%+ drive free space, and vram should follow the same scheme of color changing"

**Files touched:**
- `.claude/statusline.sh` — new `_grad_color(p)` helper at the top of the try block returning truecolor escape codes for the 6-tier gradient (green-500 / lime-400 / yellow-500 / orange-500 / orange-600 / red-600 RGB stops). Every gauge call site updated:
  - ctx_str: previous inline 3-tier (`>80 red, >60 yellow, else green`) replaced with `_grad_color(pct)`.
  - `_pct_bar(p)` (5h + 7d bars): same replacement.
  - `_sys_seg(label, value, pct)`: previous `_sys_color(p)` removed entirely; cyan label + `_grad_color(pct)` value now.
  - GPU per-card render: `_sys_color(vram_pct)` and `_sys_color(ut)` both replaced with `_grad_color(...)`.
  - `_sys_color` function deleted (unused after refactor).
- `docs/STATUSLINE.md` — new §8.12 "Canonical 6-tier color gradient (used by every gauge)" with the full RGB / hex / Tailwind-equivalent table, applied-to gauge list, drive-axis note (color tracks `% used`, label shows `GB free`), helper code, test recipe. §8.7 line "Color thresholds identical to ctx — green `<60%`, yellow `60–80%`, red `>80%`" rewritten to point at §8.12 as canonical source.

**Closure notes:**
- 10 gradient stops verified via test loop (5%, 30%, 36%, 40%, 50%, 60%, 70%, 79%, 85%, 95%) — each percentage produces the expected RGB escape code.
- Truecolor passthrough — works on Windows Terminal, Git Bash mintty, Console Host since Win10 v1809, PowerShell 7+, and any modern Linux terminal. Doc-silent in CC docs but reliable in practice.
- Tailwind-equivalent palette chosen for visual harmony — these stops are commonly used in modern UI design and look clean at every brightness level.

### Branch state-aware coloring

**Verbatim user quote:** "lets ensure that the main/master branch displays as blue, develop displays as purple, features display as green, clean branches are their normal color, not clean branches are red with a * displayed, stagged and commited is orange with a +, pushed to remote goes back to normal color."

**Files touched:**
- `.claude/statusline.sh` — git block at top of bash extended with state detection: `git status --porcelain | grep -q .` for dirty, `git rev-list --count @{u}..HEAD` for ahead-of-remote (with `2>/dev/null` so non-tracking branches collapse to "ahead" when AHEAD is empty). Branch-type color picked via case statement: `main|master` → blue truecolor `\033[38;2;59;130;246m`, `develop` → purple `\033[38;2;168;85;247m`, anything else → green `\033[38;2;34;197;94m` (matches gradient ≤35%). State markers override type color: dirty → red `\033[38;2;220;38;38m` + `*` (matches gradient 80%+), ahead → orange `\033[38;2;249;115;22m` + `+` (matches gradient 56–65%), pushed → branch-type color, no marker.
- `docs/STATUSLINE.md` — §8.9 rewritten from the simple "green clean / yellow dirty" flag doc into the full state matrix: branch-type color table, state-marker priority, color rationale (state colors deliberately reuse RGB values from §8.12 gradient for unified palette), throwaway-repo test recipe covering all 6 state combinations. §9 brainstorm "implemented" note updated.

**Closure notes:**
- 6 test scenarios passed via mkdir/mktemp throwaway repo: (a) main + clean + pushed → BLUE, (b) main + dirty → RED `*`, (c) main + commit-not-pushed → ORANGE `+`, (d) main + push → back to BLUE, (e) develop + clean + pushed → PURPLE, (f) feature/foo + clean + pushed → GREEN.
- Test setup gotcha caught + documented: the bare remote repo MUST be created OUTSIDE the working tree, otherwise its files appear as untracked in `git status --porcelain` and trigger false-dirty state.
- State priority `dirty > ahead > pushed` is intentional: any `git add`-staged file (even with no working-tree change) shows in porcelain output and triggers red `*`. Once the commit lands, the tree becomes clean and either orange `+` (unpushed) or branch-type color (in sync) applies.
- `dirty.txt` test file naming is unrelated to the actual dirty-state semantics (just a test fixture name); the dirty color is triggered by the git porcelain output, not the filename.

### Unicode block-fill bars — 16 cells × 8 sub-levels

**Verbatim user quote:** "I think we only have 16 spaces in the bars if I am correct, which 16/100 is 6.25, so each bar is 6.25% of 100%, if we swap the bars to something like this: '', '▏', '▎', '▍', '▌', '▋', '▊', '▉', '█' we could make the bars look a bit better overall, and give us more ganular look at the usage, so instead of each bar being 6.25% we can have another ~0.78% granularity to the progress, and we can fill out the additional space so it looks blank between [ and ] with 0%, but also pad it out between those bars so we can make it spaced basically the same, just would look like [#########        ] ##% but instead of # it would be those other characters."

**Verbatim user follow-up (bug catch):** "I dont see it padding out to the 16 spaces per bar (18 characters including [])"

**Files touched:**
- `.claude/statusline.sh` —
  - Added `_make_bar(p, cells=16)` helper. `LEVELS = [' ', '▏', '▎', '▍', '▌', '▋', '▊', '▉']` (0/8 through 7/8). Computes `filled_sub = round(p / 100 * 128)`, splits into `full = filled_sub // 8` and `rem = filled_sub % 8`, returns `'█' * full + LEVELS[rem] + ' ' * (16 - full - 1)`. Special-cases 100% to avoid index-out-of-bounds.
  - `ctx_str` now calls `_make_bar(pct)` instead of inline `'#' * filled + '-' * (bar_len - filled)`.
  - `_pct_bar(p)` (5h + 7d bars) refactored to call `_make_bar(p)`; old 15-cell `#`/`-` logic removed.
  - **Critical bug fix**: `eval $(echo "$input" | python3 -c "...")` changed to `eval "$(echo "$input" | python3 -c "...")"`. Without the outer double quotes, bash word-splits the command substitution output, collapsing the new bars' multi-space padding (`[████            ]` → `[████ ]`). Latent footgun that didn't manifest with `#`/`-` bars (no consecutive spaces) but broke immediately with space-padded Unicode bars. Closing `)` now has trailing `"` to match the opening `"$(`.
- `docs/STATUSLINE.md` — new §8.13 "Canonical bar geometry — Unicode block-fill cells" with: visual ladder showing 0% / 25% / 50% / 79% / 100% renders, glyph table mapping fractions to U+2588 family code points, the `_make_bar` helper code, "Why 16 × 8" rationale (128 total sub-cells = 0.78% granularity, fits under model + git segments, matches standard Unicode block-fill range), and a section on the eval-quoting footgun for future reference.

**Closure notes:**
- 5 test sweeps verified each gradient stop from 0% → 100% renders the correct number of full blocks + correct partial glyph + correct trailing space count = 16 cells total.
- 0.78125% granularity confirmed mathematically: 16 cells × 8 sub-levels = 128 sub-cells, 100/128 = 0.78125%.
- Color gradient (§8.12) layered on top of the bar geometry — the helper returns plain text; `_grad_color(p)` wraps the bracket-and-bar string in the truecolor escape.
- Render width: 16-char bar interior + 2 brackets + space + percent + percent sign ≈ 22–23 chars per bar. Three bars on line 2 = ~70 chars. Well within terminal width on every modern setup.
