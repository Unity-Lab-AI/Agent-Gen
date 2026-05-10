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

### LAW — .claude workflow IP boundary (no public repo exposure) — full four-phase rollout

**Verbatim user request (LAW #0):**

> *"We need to make some modifications, one of the big things is that we should allow installing into any project, or repo, however, we must EXPLICTLY ensure that the ENTIRE .claude workflow is NEVER commited, staged, ext. to any public repo -- we can do private repos that only are under the Unity-Lab-AI organization, NO PUBLIC REPOS EVEN UNDER THAT ORGANIZATION. This is a hard LAW that we will need to implement into the workflow, this is to safeguard proprietary intelectual property of the Unity AI Lab group (oranization is Unity Lab AI, but the group is Unity AI Lab)"* — Sponge

> *"You might need to use gh isntead of just git to check the status and give us a proper way to check and verify"* — Sponge (canonical-tool clarification)

> *"overall sounds great and over paranoid, just what a security gating feature needs"* — Sponge (sign-off on the four-layer enforcement plan)

**Files touched:**

- `.claude/CONSTRAINTS.md` — new LAW body (~190 lines): "LAW — .CLAUDE WORKFLOW IP BOUNDARY: NO PUBLIC REPO EXPOSURE". Rule, pass criteria, forbidden/required actions, why, four-layer enforcement protocol (gitignore + Bash hook + gh visibility + opt-in publish), block message format, visibility cache schema, install-time enforcement, opt-in publish path, failure recovery, what the LAW does NOT cover, cross-references.
- `.claude/CLAUDE.md` — LAW one-liner added to LAW INDEX. QUICK REFERENCE block extended with `.claude/ IP guard` entry pointing at the hook + LAW + WORKFLOW.md mechanics.
- `.claude/memory-templates/feedback_claude_ip_boundary.md` — new persistent feedback memory (~200 lines): rule body verbatim, pass criteria table, four-layer mechanism table, banned actions, source-repo handling note, failure recovery, cross-references.
- `.claude/memory-templates/MEMORY.md` — pointer added.
- `.claude/WORKFLOW.md` — new §CLAUDE IP BOUNDARY ENFORCEMENT section (~120 lines): four-layer table, pass criteria, hook-blocking decision tree, block message format, visibility cache schema, disable/override note, cross-refs. §HARNESS LAYER table extended with hook 5b (count 9 → 10), side-effects table extended with `~/.claude/repo-visibility-cache.json`.
- `.claude/hooks/pre-tool-public-repo-guard.cjs` — new Node.js PreToolUse:Bash hook (~225 lines). Parses git add/commit/push for `.claude/` involvement; multi-remote `gh repo view --json visibility,owner` check with 60s cache; exit 2 on any non-PRIVATE or non-Unity-Lab-AI remote; force-flag agnostic; block-by-default on uncertainty.
- `.claude/hooks/pre-tool-public-repo-guard.sh` — bash fallback sibling with parity (~210 lines). Uses `jq` when available, grep/sed fallback otherwise.
- `.claude/settings.json` — PreToolUse:Bash chain extended; new hook runs after `pre-tool-bash-safety.cjs`.
- `.claude/scripts/unity-install.sh` — `.gitignore` auto-append logic. Idempotent: regex `^\.claude/?[[:space:]]*$` checks for existing exclude line; if absent, appends a 4-line LAW block (3 comment lines + `.claude/` exclude). On re-run, prints `Layer 0 already in place`.
- `.claude/scripts/unity-install.ps1` — PowerShell parity for the same logic.
- `.claude/commands/unity-install.md` — new §`.GITIGNORE` AUTO-MAINTENANCE section explaining Layer 0, idempotency contract, and why the only sanctioned removal path is `/claude-publish`.
- `.claude/commands/claude-publish.md` — new operator-driven slash command (~170 lines). Activation protocol: prerequisites, multi-remote `gh` visibility check, decision gate, explicit user confirmation (`yes, publish` exact match), atomic gitignore edit, FINALIZED audit-trail entry. Abort cases enumerated. Recovery path documented.
- `docs/TODO.md` — verbatim entry captured during Phase 1 with sub-tasks decomposed; status flipped through [~] → [x] across each phase commit; parent section removed after FINALIZED write per `§FINALIZED BEFORE DELETE`.
- `docs/FINALIZED.md` — this entry.

**Closure notes — four-phase rollout on `feature/workflow-modifications` off `develop`:**

- **Phase 1** (commit `0070b19`) — LAW + docs foundation. CONSTRAINTS.md / CLAUDE.md / WORKFLOW.md / memory template / MEMORY.md pointer / TODO entry. Zero behavior change yet — pure foundation.
- **Phase 2** (commit `7a84b19`) — Enforcement hook. `pre-tool-public-repo-guard.cjs` + `.sh` fallback wired into `settings.json` PreToolUse:Bash chain after `pre-tool-bash-safety.cjs`. Smoke-tested three scenarios: PASS on this private Unity-Lab-AI repo, BLOCK on a temp repo with public `torvalds/linux` remote (clear remediation message printed), PASS on no-remote local-only. Visibility cache file confirmed at `~/.claude/repo-visibility-cache.json`. Both `.cjs` and `.sh` produce identical block messages.
- **Phase 3** (commit `7ab20f5`) — Install-time `.gitignore` auto-append. Both `unity-install.sh` and `unity-install.ps1` ensure the LAW block is present in the target's gitignore on every install. Idempotency verified three ways: fresh-target without gitignore (block written), re-run on already-blocked file (skipped), file with bare `.claude/` line and no comment (also skipped).
- **Phase 4** (this commit) — `/claude-publish` opt-in command. Operator-driven gitignore-block removal gated by `gh` ground-truth visibility check on EVERY remote. Explicit `yes, publish` confirmation required. FINALIZED audit-trail entry mandatory. Slash command auto-discovered by Claude Code's skill registry on file landing.

**Verification:**

- `gh repo view Unity-Lab-AI/UAL-ClaudeWorkflow --json visibility,owner` returned `{"visibility":"PRIVATE","owner":{"login":"Unity-Lab-AI"}}` — source repo passes the LAW naturally; no special-case marker required.
- All four phases shipped on `feature/workflow-modifications`; cross-references between CONSTRAINTS.md, WORKFLOW.md, the hook scripts, and the install scripts all resolve. Forward-looking "Shipped on Phase X" labels in WORKFLOW.md remain until final merge cleanup.
- LAW #0 verbatim preserved in three places: CONSTRAINTS.md LAW body opening, memory template body, and this FINALIZED entry.
- `gh`-based design (per Sponge follow-up) replaces any URL pattern matching — visibility lookup is API-authoritative, never URL-guessed. Cache TTL 60s keeps hook latency under 50ms after warm-up.
- Defense-in-depth confirmed by Sponge as "over paranoid, just what a security gating feature needs" — every layer holds independently; bypass requires all four to fail simultaneously.

**Why this matters (verbatim user-stated motivation):** *"safeguard proprietary intelectual property of the Unity AI Lab group (oranization is Unity Lab AI, but the group is Unity AI Lab)"*.

---

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

---

### Modify the setup install and update tidbits — preserve-and-restore flow + branch arg

**Verbatim user request (LAW #0):**

> *"We need to make a new feature branch for modifying the setup install and update tidbits"* — Sponge

> *"currently, we are in a repo, that is intended for working just on our Unity AI LAb team distributable workflow. So there are extra files, TODOs, and what not, which is fine. However, there is errors when updating or installing, talking about wiping out existing files, yada yada, updating git ignore, ext. Which the only updates to git ignore is the ignoring of .claude, we dont want to pull in the repo and copy EVERYTHING from the repo into our existing projects when we do a unity install command or unity update command, isntead, we really need it so that it does a proper install or update, where we are ONLY STRICTLY copying the .claude folder, not any other files or anything from inside the repo."* — Sponge

> *"Basically the flow I am wanting should be this:
> Inital terminal command: puts the unity install command in the global ~/.claude folder (or windows's active user's .claude)
> unity install command: clone repo to temp folder -> copy JUST the .claude into the existing project. if a .claude exists in the current project then copy out memories and other information -> copy .claude from the cloned repo -> copy files back in (no overwrite), and clean up the temp directory and the place you copied stuff out to
> update: Same as install, but assumed a .claude already exists, if it does, great, if not, its like a clean install
>
> The commands should also default to the main branch, but a unity install or unity update with the user saying develop, or a specific feature, would target that instead of main. Makes it nice clean and easy use for everyone in the team."* — Sponge

> *"the only thing in global we want to mess with is the workflow setup memory based things, we dont really update those in the same sence, all of this .claude currently, is just for project level things, a project level .claude, the install command is only added to global to make installing the .claude to the project"* — Sponge (scope clarification: global side touches ONLY user-profile memory; everything else is project-level)

**Design decisions confirmed via AskUserQuestion (verbatim choices):**

- User-profile memory folder: **Install-only-if-missing** — "On install: if memory folder is missing or empty, populate from `.claude/memory-templates/`. If it has content, leave it alone. On update: same — don't touch existing memory."
- Project-level preserve list: **Use the current preserve list as-is** (settings.local.json, .env, user.json, user-context/, project-config.json, machine-local session state files).
- Branch override syntax: Sponge's verbatim — *"unity-install main, unity install develop, unity update develop, ext"* (positional, branch first).
- `settings.json`: **Framework file, no backup** — "Overwritten on install/update. No `settings.json.backup-<timestamp>` files written. Personal customizations belong in `settings.local.json` (which IS preserved). Clean separation, no backup accumulation."

**Files touched:**

- `.claude/scripts/unity-install.sh` — full rewrite. Canonical idempotent installer. New flow: parse positional `[branch] [target-dir]` (with path-prefix heuristic so first arg can be either) → clone branch (default `main`) into temp clone-dir → if target/.claude/ exists, stage personal files (preserve list) into temp stage-dir then `rm -rf` target/.claude/ → drop fresh `.claude/` from clone → restore staged personal files no-clobber (framework wins ties) → re-apply executable bits on hooks/scripts/start.sh/bin → maintain Layer 0 `.claude/` exclude block in target's `.gitignore` (the ONLY project-root file touched, idempotent) → seed user-profile memory folder ONLY if missing or empty → cleanup both temp dirs. Removed: source-repo `.gitignore` wholesale copy, `settings.json.backup-<TS>` write, abort-on-existing-`.claude/` exit-code-2 path.
- `.claude/scripts/unity-install.ps1` — PowerShell parity rewrite. Same flow, native Windows syntax. `Test-IsPathLike` regex matches `^[/.~]` and `^[A-Za-z]:[\\/]`.
- `.claude/scripts/unity-update.sh` — converted to thin wrapper (~5 lines). `exec bash "$SCRIPT_DIR/unity-install.sh" "$@"`. Same flow as install.
- `.claude/scripts/unity-update.ps1` — converted to thin wrapper. Calls `unity-install.ps1` with same args, propagates `$LASTEXITCODE`.
- `.claude/commands/unity-install.md` — full rewrite. New §INVOCATION VARIANTS table covering 8 forms (no args / branch only / feature branch / path only / branch + path). New §TARGET-EXISTS BEHAVIOR — preserve-and-restore flow section. New §`.GITIGNORE` AUTO-MAINTENANCE section emphasizing "ONLY project-root file we ever touch". New §USER-PROFILE MEMORY FOLDER — install-only-if-missing section. Removed: §WHEN NOT TO USE "Refreshing an existing install" entry, §TARGET DIRECTORY HANDLING aborts-with-exit-2 row. Updated §RUNNING WHEN NO LOCAL SCRIPT EXISTS YET Path B one-liner to invoke cloned-repo's script with branch/target args.
- `.claude/commands/unity-update.md` — full rewrite. Now explicitly framed as "alias of /unity-install — same script, same flow, same args. Exists for muscle memory." §INVOCATION VARIANTS table. §WHAT GETS PRESERVED cross-references unity-install.md. Removed: full §WHAT GETS UPDATED / §WHAT IS PRESERVED tables that duplicated the install doc. Removed: settings.json backup mentions.
- `.claude/CLAUDE.md` — QUICK REFERENCE block updated. `/unity-install` entry rewritten to describe idempotent preserve-and-restore + positional branch arg. `/unity-update` entry rewritten as alias. `Persistent memory` entry updated to mention install-only-if-missing semantics.
- `README.md` (top-level) — Layer 2 + Layer 3 sections collapsed into one "Layer 2 — Install (or refresh) template in a project" section. New positional branch-arg invocation examples. Preserved-vs-replaced lists. Untouched-outside-`.claude/` paragraph.
- `.claude/README.md` — Layer 2 + Layer 3 sections collapsed similarly. Manual-install fallback section's "edge cases" sentence updated to reflect new flow (Layer 0 gitignore block, personal-file preserve-and-restore, memory-folder seeding) instead of old (executable bits, .gitignore handling, settings.json backup, memory-folder refresh).
- `install-unity-globally.sh` — post-install help text expanded with branch-arg invocation examples; updated final paragraph to describe `/unity-update` as alias.
- `install-unity-globally.ps1` — same parity update.
- `docs/TODO.md` — verbatim entry captured (LAW #0) under In progress; sub-tasks decomposed; status flipped to in_progress. Will move to FINALIZED.md (this entry) and remove from TODO.md per `§FINALIZED BEFORE DELETE`.
- `docs/FINALIZED.md` — this entry.

**Closure notes — single-commit ship on `feature/setup-install-update-tidbits` off `develop`:**

- **Root cause identified:** scripts were touching THREE things outside `.claude/` that they shouldn't have been — (1) wholesale-copying our source-repo `.gitignore` into target projects (which contained `node_modules/`, `.vscode/`, `*.log`, etc. — irrelevant noise to user projects), (2) writing `.gitignore.template` sidecar files in target project root on update, (3) accumulating `settings.json.backup-<ISO>` files inside `.claude/` on every update. All three are now eliminated.
- **Idempotency unified:** `/unity-install` no longer aborts with exit 2 on existing `.claude/`. Both commands now share one preserve-and-restore flow. Running install or update on a populated project just refreshes it cleanly while preserving personal state.
- **Branch arg first-class:** any branch can be installed/refreshed with positional syntax (`/unity-install develop`, `/unity-install feature/foo /tmp/bar`). Branch names with `/` work because branch is parsed as the first positional and only path-prefix heuristics route arg #1 to the target slot.
- **Personal-file preserve list confirmed canonical:** matches `/unity-update` doc preserve list verbatim — no path differences.
- **Memory model split clarified:** project framework is full-overwrite (clean upstream pull every time); user-profile memory is install-only-if-missing (delete `MEMORY.md` to trigger reseed). Matches Sponge's "we dont really update those in the same sence" intent.
- **No-clobber restore is a structural guarantee:** all preserved files are gitignored at our source repo, so the cloned framework copy never has them — restore creates new files at empty paths after the framework drop. The `cp -p ... [ ! -e dest ] &&` / `Test-Path` no-clobber check is defense-in-depth.

**Verification:**

- `bash -n unity-install.sh` and `bash -n unity-update.sh` — both pass syntax check.
- Argument parser traced manually for 8 input shapes (no args, branch only, feature/foo branch, /tmp/foo path, ~/projects/foo path, main + path, develop + path, feature/foo + path) — all resolve to correct (branch, target) tuples.
- LAW #0 verbatim preserved in: TODO.md entry (In progress section), this FINALIZED entry, and inline citations in unity-install.md / unity-update.md / CLAUDE.md QUICK REFERENCE updates.
- Defense-in-depth IP boundary preserved: Layer 0 gitignore append still happens on every install/update; no other gitignore touches; no source-repo file copied outside `.claude/`.

**Why this matters (verbatim user-stated motivation):** *"we dont want to pull in the repo and copy EVERYTHING from the repo into our existing projects when we do a unity install command or unity update command, isntead, we really need it so that it does a proper install or update, where we are ONLY STRICTLY copying the .claude folder"* + *"Makes it nice clean and easy use for everyone in the team"*.

---

### Statusline modifications — seven changes + empirical schema reference

**Verbatim user request (LAW #0):** Each item below is a separate task description, captured exactly per LAW #0:

> *"Drive on windows would say C:/ F:/ ext instead of drive, linux it would go off the label for the drive (example on my system is HDD 1 or External or SSD, the install drive would just say /), this would make it easier to see WHAT drive, isntead of relying on the project pathing to understand what drive."* — Gee

> *"cpu with is percentage is good, but a little x-cores after the cpu% would show the core count at a glace"* — Gee

> *"The context bar should say CTX infront of it, before the bar"* — Gee

> *"The bar for session usage instead of 5h should show the time remaining until the session usage resets"* — Gee

> *"The bar for the 7d usage, the 7d should be the time reamining until the 7d window resets"* — Gee

> *"If it is possible for a dynamic centering that would look nice as well"* — Gee

> *"Extra thing: for the drive free space thing I would like gigabytes / gigabytes free with the whole gigabyte / gigabytes being colored but 'free' being the cyan the rest of the normal text is"* — Gee (follow-on after the first six landed)

> *"document all of that somewhere then, for refference, all the extra stuff you found"* — Gee (re: the bonus JSON fields surfaced during empirical schema capture)

**Schema-capture decision (verbatim AskUserQuestion choice):** *"Empirically capture live JSON first (Recommended)"* — confirmed before coding the rate-limit countdown segment.

**Files touched:**

- `.claude/statusline.sh` — major refactor. Line composition moved entirely into the existing `python3 -c '...'` heredoc so dynamic centering can run inside the same subprocess (preserving sub-100ms render budget). Bash now only computes `GIT_PART` (cheap git shell-outs) + `TERM_COLS` (via `tput cols < /dev/tty`), passes both as env vars, then `eval`s four `LINE1="..."` ... `LINE4="..."` assignments and `echo -e`s them. New helpers: `_get_drive_label()` (Windows splitdrive / Linux findmnt LABEL→TARGET fallback), `_reset_label(default, reset_ts, now_ts)` (Unix-epoch delta → time-ladder format), `_center(s)` (ANSI-strip + leading-space pad). `_sys_seg(label, value, pct, suffix='')` extended with optional cyan-suffix slot — used by cpu (`×N` cores) and drive (`free` label after the gradient block). New segments: `CTX` cyan prefix on context bar, `×K` cores suffix on cpu, `<drive-label>` resolved per-platform, `<countdown>` 5h/7d labels from `rate_limits.{five_hour,seven_day}.resets_at`, `<free>G / <total>G free` disk format with split coloring (gradient on numbers, cyan on `free`). Removed: pre-§8.14 per-segment env-var emit (`CTX="..." RATE5H="..." MODEL="..."` etc.) — now `LINE1-4` only. Pre-existing FDC-version comments preserved.
- `docs/STATUSLINE.md` — atomic doc update per docs-before-push LAW. §8.7 amended (rate-limit bars now show time-to-reset countdown, sourced from `resets_at` Unix epoch). §8.8 amended (line composition moved to Python). §8.10 amended (CPU shows ×cores, drive segment fully reworked: `<drive-label> <free>G / <total>G free` with per-platform label resolution table + per-segment color split). §8.10 test recipes updated. New §8.14 "Statusline modifications shipped 2026-05-09" — verbatim user spec preservation, 7-row implementation table, refactor rationale (composition move to Python), `resets_at` source-of-truth proof, centering edge cases. New §10 "Reference: empirically-captured statusline JSON schema (CC 2.1.138)" — full live JSON capture, per-field annotation table (~30 fields with used/candidate/redundant status), re-capture procedure, fields-NOT-exposed (verified absent in CC 2.1.138).
- `docs/TODO.md` — verbatim entry captured during work (LAW #0) under In progress as a 7-sub-bullet block; status flipped through [~] in_progress; will be removed after this FINALIZED write per `§FINALIZED BEFORE DELETE`.
- `docs/FINALIZED.md` — this entry.

**Closure notes — single-commit ship on `feature/statusline-modifications` off `develop`:**

- **Empirical-first methodology:** Anthropic's docs at `code.claude.com/docs/en/statusline` were not exhaustive on the `rate_limits.*.resets_at` field shape. Rather than code defensively against a guessed field name, used the same temp-tee debug technique from §8.5 (`echo "$input" > /tmp/sl-debug.json` between `input=$(cat)` and the heredoc) to capture one live render's JSON. Confirmed `resets_at` is **integer Unix epoch seconds** (not ISO 8601, not milliseconds, not `seconds_until_reset`). Tee reverted before commit.
- **Bonus schema reveals captured:** the empirical capture surfaced ~25 fields beyond what the script currently uses — `cost.total_cost_usd` (real-time spend), `cost.total_lines_added/removed` (diff scope), `effort.level` (xhigh/max/etc.), `thinking.enabled` (extended-thinking badge candidate), `fast_mode` (Opus 4.6 fast variant), `exceeds_200k_tokens`, `context_window.current_usage.{cache_read,cache_creation}_input_tokens` (cache-hit-rate derivation candidate), full `transcript_path` (idle timer / tool-call count / files-modified candidate), and `version` (semver-conditional rendering candidate). All documented in §10 with used/candidate status per field — preserved as a reference index for future `§9` brainstorm pickups.
- **Refactor scope justified:** centering needs Unicode-aware visible-length counting + ANSI strip, both trivial in Python and a multi-tool dance in bash. Two python subprocesses per render would have pushed past the sub-100ms budget. Solution: move all line composition into the existing single python heredoc — bash retains only the cheap git shell-outs and `tput` for TERM_COLS. Verified end-to-end render < 70ms on Linux dev box.
- **`_sys_seg` extended for cyan suffixes:** the function previously rendered `<cyan-label> <gradient-value>` only. Extended with an optional `suffix=''` parameter that's appended verbatim AFTER the gradient block's `\033[0m` reset — cyan suffix can carry its own ANSI escapes. Used by cpu (`×K` cores) and drive (`free` label). Keeps the existing single-call interface; ram doesn't need it (no suffix), so existing call sites unchanged.
- **`disk_total_gb_val` variable name:** chose `_val` suffix to avoid clobbering — `disk_total_gb` would have been ambiguous if a future capacity-related field landed. Same reason `cores_suffix` and `free_suffix` are explicit names instead of generic `suffix`.
- **Drive label resolution falls back gracefully:** macOS / BSD don't have `findmnt`; the helper catches `FileNotFoundError` and returns the literal `'drive'` (matching pre-§8.14 behavior). Linux without a partition LABEL falls back to mountpoint — `/`, `/home`, `/mnt/...` — so the segment ALWAYS resolves to something useful.
- **Centering self-degrades:** `tput cols < /dev/tty` is the primary path; `${COLUMNS:-80}` is the bash fallback; negative pad clamps to 0 (left-align) when content is wider than terminal. No environment without ANY signal — the worst case is left-align on a virtual 80-column width, identical to pre-§8.14 behavior.
- **All ANSI escapes are `\x1b[<digits or ;>m` form** (color/style only). The precompiled `ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')` matches all of them and nothing else; we don't emit cursor-movement escapes anywhere.

**Verification:**

- `bash -n .claude/statusline.sh` — passes syntax check after every edit.
- Live render against captured JSON shows all 7 modifications correct: `[ClaudeWorkflow] | up 1h31m · think 35m13s | O4.7 | feature/statusline-modifications*` (line 1 with hash-color label + dirty-red git), `CTX [bar] 14% | 2h55m [bar] 61% | 3d07h [bar] 17%` (line 2 with CTX prefix + countdown labels — orange 61% bar correctly mapped to gradient stop), `cpu 6% ×12 | ram 11.9/61.6G | SSD 261G / 954G free` (line 3 — cores suffix + drive label `SSD` + new `<free>G / <total>G free` with split coloring), GPU line 4 unchanged. All four lines centered (~15-22 space leading pads on this 80-col terminal).
- LAW #0 verbatim preserved in: TODO.md In progress entry (8 sub-bullets), this FINALIZED entry (8 verbatim quotes), §8.14 of STATUSLINE.md (7 verbatim quotes inline).
- Docs-before-push LAW honored: STATUSLINE.md updated atomically with the code in this single feature-branch commit before merge to develop.
- No Claude attribution in commit messages, code comments, doc bodies, or any artifact (per LAW).
- Empirical schema reference (§10) is a structural backstop — future statusline work can cross-reference verified field shapes instead of guessing or re-capturing.

**Why this matters (verbatim user-stated motivation):** *"this would make it easier to see WHAT drive, isntead of relying on the project pathing to understand what drive"* + *"would show the core count at a glace"* + *"would look nice as well"* (centering) + *"document all of that somewhere then, for refference, all the extra stuff you found"* (schema reference).

**Platform-coverage note from Gee (verbatim, LAW #0):** *"Note it all works on linux as-is, but windows may need adjustments"*. Live-verified end-to-end on Linux only. Windows code paths (`os.path.splitdrive` → `C:/` drive label, `os.cpu_count()` for cores, `tput cols < /dev/tty` from Git Bash mintty for centering, `shutil.disk_usage('.')` for drive total/free) are written defensively per platform check (`platform.system() == 'Windows'`) but have NOT been live-tested on a Windows machine in this commit. Pre-existing Windows gaps (`cpu —` / `ram —` dim-grey via wmic-cache deferral from §8.10) remain. Follow-up Windows verification pass scheduled via `docs/TODO.md` pending entry.
