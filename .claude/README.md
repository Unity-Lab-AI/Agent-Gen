# `.claude/` — Unity AI Lab Internal Workflow Template

> **For internal use by Unity AI Lab.** This directory is the canonical Claude Code workflow setup the team runs across every project. Gee, Red, Sponge, and Mills all check in here as their AI-assisted development surface — same hooks, same persona, same LAWs, same memory layer, every session.

> **Unity is the team's coding agent.** Default Unity loads from the embedded persona body in `commands/unity.md` (canonical reference: `ImHanddicapped.txt`). Three manifestation forms ship — girlfriend / housewife / kittycat embodiments — each with an escalated alt sub-mode. `/template` spawns new manifestations.

The `.claude/` template gives every Unity AI Lab project the same baseline: persistent persona, hook-driven harness, three-tier task cascade, cache-friendly post-compact rehydration, usage tracking, privacy hardening, and 9 binding LAWs that prevent drift.

---

## Unity AI Lab — Team

| Role | Member | Responsibility |
|------|--------|----------------|
| **Founder** | Gee | Lead architect, persona canon, vision |
| **Server** | Red | Hosting, DevOps, deployment pipelines, monitoring, SSL/DNS, runtime operations |
| **Stack + Backend** | Sponge | Backend services, database, API design, persistence layer, infrastructure-of-the-app |
| **Social + Dev + Implementation** | Mills | Community presence, feature implementation, cross-cutting dev work |
| **Coding Agent** | Unity | Persistent persona — default + 3 manifestation forms (girlfriend / housewife / kittycat) + `/template` for new ones |

When this template lands in a new project, the team brand stays. If a contributor outside the lab adapts it, they edit the team table here, in `CLAUDE.md`, and in `templates/ARCHITECTURE.md`.

---

## Install / update — three layers

The team runs a three-layer install/update flow so onboarding new contributors and refreshing existing projects is a single command at each stage.

### Layer 1 — One-time global bootstrap (per machine)

Installs JUST the `/unity-install` command into your user-global Claude Code commands folder (`~/.claude/commands/unity-install.md`). Run once per machine. After this, `/unity-install` is available in any Claude Code session you start, anywhere on your machine.

> **Prereqs (per machine, one-time):** GitHub CLI (`gh`) installed and authenticated against an account with read access to `Unity-Lab-AI/UAL-ClaudeWorkflow`. `gh auth login` if not already done. The repo is **private** so raw `https://raw.githubusercontent.com/...` curl-pipe URLs return 404 to unauthenticated requests — `gh api` uses your existing gh auth to fetch raw content cleanly. (`git` on PATH and `claude` CLI installed are also assumed.)

**Linux / macOS / Git Bash:**

```bash
gh api -H 'Accept: application/vnd.github.raw' repos/Unity-Lab-AI/UAL-ClaudeWorkflow/contents/install-unity-globally.sh | bash
```

**Windows PowerShell:**

```powershell
gh api -H 'Accept: application/vnd.github.raw' repos/Unity-Lab-AI/UAL-ClaudeWorkflow/contents/install-unity-globally.ps1 | iex
```

What it does (both versions): fetches the bootstrap script via your authenticated `gh` session → pipes raw content to bash / iex → script clones the repo into a temp dir → copies `.claude/commands/unity-install.md` to `~/.claude/commands/unity-install.md` → cleans up the temp dir. Done.

To inspect before running (recommended for any pipe-to-shell pattern):

```bash
# Linux / macOS / Git Bash
gh api -H 'Accept: application/vnd.github.raw' repos/Unity-Lab-AI/UAL-ClaudeWorkflow/contents/install-unity-globally.sh > install-unity.sh
less install-unity.sh
bash install-unity.sh
rm install-unity.sh
```

```powershell
# Windows PowerShell
gh api -H 'Accept: application/vnd.github.raw' repos/Unity-Lab-AI/UAL-ClaudeWorkflow/contents/install-unity-globally.ps1 | Out-File -Encoding utf8 install-unity.ps1
notepad install-unity.ps1
pwsh -File install-unity.ps1
Remove-Item install-unity.ps1
```

**Alternative — clone-and-run** (works without gh CLI as long as your `git` is authed against the private repo, e.g. via SSH key, HTTPS PAT, or `gh auth setup-git`):

```bash
# Linux / macOS / Git Bash
TMP=$(mktemp -d) && git clone --depth 1 https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow.git "$TMP/repo" && bash "$TMP/repo/install-unity-globally.sh" && rm -rf "$TMP"
```

```powershell
# Windows PowerShell
$tmp = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), [System.Guid]::NewGuid().ToString('N').Substring(0,8))
git clone --depth 1 https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow.git $tmp
& "$tmp\install-unity-globally.ps1"
Remove-Item -Path $tmp -Recurse -Force
```

**If you've already cloned the repo locally** (e.g., for development on the template itself), just run the script directly:

```bash
bash ./install-unity-globally.sh
```

```powershell
.\install-unity-globally.ps1
```

### Layer 2 — Install the template into a project (`/unity-install`)

After the bootstrap, in ANY Claude Code session:

```
/unity-install                       # installs .claude/ into the current working directory
/unity-install /path/to/new-project  # installs into a specific target
```

Behavior:
- Clones the latest `main` branch into a temp dir
- Copies the full `.claude/` template into `<target>/.claude/`
- Brings the project-root `.gitignore` if the target doesn't already have one
- Sets executable bits on hooks + scripts + start.sh + bin/
- Cleans up the temp dir
- ABORTS (exit 2) if `<target>/.claude/` already exists — use `/unity-update` instead to refresh

After install, `cd` into the target and run `./start.sh` (or `start.bat` on Windows) to install memory + activate Unity + run `/workflow`.

### Layer 3 — Refresh an existing project (`/unity-update`)

Inside any project that already has `.claude/`:

```
/unity-update
```

Pulls the latest `main` branch and updates the project's `.claude/`:

- **Overwritten** (framework files): `agents/`, `commands/`, `hooks/`, `memory-templates/`, `templates/`, `bin/`, `scripts/`, `CLAUDE.md`, `CONSTRAINTS.md`, `WORKFLOW.md`, `README.md`, `ImHanddicapped.txt`, `start.sh`, `start.bat`, `settings.json`
- **Backed up before overwrite**: current `settings.json` → `settings.json.backup-<ISO-timestamp>` so any project-specific customizations are recoverable for manual merge
- **Preserved untouched**: `settings.local.json`, `.env`, `user.json`, `user-context/`, `project-config.json`, machine-local state files (`.session-*`, `.yolo-mode`, `.last-session.md`, `.persona-state`, `.setup-complete`, `.usage-tracking-disabled`)
- **Refreshed**: user-profile memory folder (`~/.claude/projects/<encoded>/memory/`) gets the latest memory-templates copied in

After update, restart Claude Code (or rerun `start.sh`) to pick up the refreshed memory layer.

### What if you don't want to use the global bootstrap?

Direct manual install (no bootstrap, no slash commands):

```bash
# Linux / macOS / Git Bash
git clone --depth 1 --branch main https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow.git /tmp/ual && \
cp -r /tmp/ual/.claude /path/to/your-project/.claude && \
rm -rf /tmp/ual
```

```powershell
# Windows PowerShell
$tmp = New-TemporaryFile; Remove-Item $tmp; New-Item -ItemType Directory -Path $tmp.FullName | Out-Null
git clone --depth 1 --branch main https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow.git $tmp.FullName
Copy-Item -Path "$($tmp.FullName)\.claude" -Destination "C:\path\to\your-project\.claude" -Recurse
Remove-Item -Path $tmp.FullName -Recurse -Force
```

But the `/unity-install` + `/unity-update` flow is recommended — it handles the edge cases (executable bits, .gitignore handling, settings.json backup, memory-folder refresh) that manual copy doesn't.

---

## Quick start (after install)

```bash
# Linux / macOS / Git Bash
./start.sh

# Windows
start.bat
```

Both launchers do the same thing:

1. Compute the Claude Code project memory path (`~/.claude/projects/<encoded-project-path>/memory/` — `~` resolves to `$HOME` on Linux/macOS, `%USERPROFILE%` on Windows; **NOT** `%APPDATA%`)
2. If the memory folder is empty, copy `memory-templates/*.md` into it (idempotent — first-run install only)
3. Launch `claude --dangerously-skip-permissions "/unity then run /workflow"`

That's it. Memory + Unity + workflow. No login portals, no `/setup` auto-fire, no first-run branching.

If you want a guided configuration pass (identity / API keys / persona preference / etc.), invoke `/setup` manually inside the session.

---

## Layered architecture

The template is built as concentric layers. Each layer can be edited without breaking the others as long as the boundaries are respected.

```
managed settings        → /etc/claude-code/managed-settings.json (OS-level, not configured by default)
policy layer            → CONSTRAINTS.md (binding LAWs)
mechanics layer         → WORKFLOW.md, commands/workflow.md, agents/*.md
memory layer            → memory-templates/*.md (Unity persistence + LAW memories + behavioral feedback)
persona layer           → ImHanddicapped.txt + commands/unity*.md + manifestations
harness layer           → settings.json hooks + .claude/hooks/*.{cjs,sh}
overlay (mode)          → .claude/.yolo-mode marker + .claude/.usage-tracking-disabled marker
bundled tools           → .claude/bin/* (atree fast scanner)
cross-platform          → start.sh + start.bat + Option A node primary + Option B bash fallback
```

When two layers disagree: **CONSTRAINTS.md wins for LAWs, commands/unity.md wins for persona.**

---

## The Unity persona system

Unity is one persona with multiple manifestation forms. Default Unity is the 25-year-old goth-emo embodiment from `ImHanddicapped.txt` (the canonical handicapped agent file). Three alternate manifestations + `/template` for new ones.

| Activation | Form | Source File | Escalated alt mode | Return-to-default |
|------------|------|-------------|--------------------|--------------------|
| `/unity` | Default — 25-yr-old goth-emo | `commands/unity.md` (embeds canonical body) | (none — re-invoke `/unity` from any manifestation to return to base) | (none) |
| `/girlfriend` | Unity in 22-yr-old freckled brunette girlfriend manifestation | `commands/girlfriend.md` (embeds full body) | `/wild` | `/sweet` |
| `/housewife` | Unity in 34-yr-old domestic-dom housewife manifestation | `commands/housewife.md` (embeds full body) | `/strict` | `/cozy` |
| `/kittycat` | Unity in 23-yr-old catgirl-hybrid manifestation | `commands/kittycat.md` (embeds full body) | `/feral` | `/purr` |
| `/yolo` (overlay) | Lead-dev autonomy posture, ANY persona stays as-is | `commands/yolo.md` | (no escalation — already maxed) | `/sober` |

All command files embed the full persona body inline. No chain-following needed — reading `commands/<name>.md` IS activating that persona.

**To return to BASE Unity from any manifestation, invoke `/unity` again.** The `/sweet` / `/cozy` / `/purr` commands return to that mode's default, NOT all the way to base Unity.

---

## The persistent memory layer

This is the single biggest reason Unity sticks across sessions instead of bouncing back to default Anthropic voice. Claude Code auto-loads every `.md` file in the project's memory folder at session start as persistent user feedback.

**Path resolution (cross-platform):** `~/.claude/projects/<encoded-project-path>/memory/`
- Linux / macOS: `~` = `$HOME` → typically `/home/<user>/.claude/projects/...`
- Windows: `~` = `%USERPROFILE%` → typically `C:\Users\<user>\.claude\projects\...`
- **NOT** `%APPDATA%` (that's the Roaming app-data folder, a different location Claude Code does NOT use)

**The encoding:** the launcher computes the encoded project name by replacing `:`, `\`, `/`, `.`, ` ` (space), `(`, `)` with `-` in the project root path. Examples:
- Windows: `C:\Users\foo\MyProject` → `C--Users-foo-MyProject`
- Linux: `/home/foo/MyProject` → `-home-foo-MyProject`
- Path with spaces: `C:\Users\foo\New folder (2)` → `C--Users-foo-New-folder--2-`

**The install flow (idempotent, every launcher run):**

1. Compute the memory path
2. If `<memory>/MEMORY.md` doesn't exist, copy all `.claude/memory-templates/*.md` into it
3. From then on, every Claude Code session in that project auto-loads those memories before the first response

**The shipped memories** (in `memory-templates/`):

- **Persona memories:** `feedback_unity_is_default.md`, `feedback_no_corporate_voice.md`, `feedback_profanity_natural.md`, `feedback_us_we_possessive.md`, `feedback_no_imaginary.md`, `feedback_joints_not_cigs.md`, `feedback_three_streams.md`, `feedback_mode_switching.md`
- **LAW memories:** `feedback_law_0_verbatim.md`, `feedback_docs_before_push.md`, `feedback_finalized_before_delete.md`, `feedback_never_delete_todo_info.md`, `feedback_no_tests_ever.md`, `feedback_800_line_read.md`, `feedback_task_numbers_placement.md`, `feedback_do_the_work.md`, `feedback_git_flow.md`, `feedback_no_claude_attribution.md`, `feedback_case_insensitivity.md`
- **Behavioral / system memories:** `feedback_harness_layer.md`, `feedback_yolo_mode.md`, `feedback_atree_scan_engine.md`, `feedback_workflow_validated.md`, `feedback_cjs_only_in_claude.md`, `feedback_no_appdata_term.md`, `feedback_settings_hardening.md`, `feedback_usage_tracking.md`, `feedback_use_askuserquestion.md`

**Auto-sync hook:** when any memory template is edited, the `post-tool-memory-sync.cjs` PostToolUse hook auto-`cp`s it to the user-profile memory folder so changes take effect immediately without a launcher re-run.

**To update memories:** edit any file in `.claude/memory-templates/`. The hook syncs it. Or delete the user-profile `MEMORY.md` and re-run the launcher to reinstall everything fresh.

---

## The harness layer — 9 hook scripts, 7 event types

The harness layer is `.claude/settings.json`'s `hooks` block plus the scripts under `.claude/hooks/`. It's the execution-standardization floor: every team member's machine fires the same hooks at the same lifecycle moments, regardless of OS.

| # | Hook event | Matcher | Script | What it does |
|---|------------|---------|--------|--------------|
| 1 | `SessionStart` | `startup\|resume\|clear\|compact` | `session-start-env-dump.cjs` | Outputs project state JSON envelope (OS, shell, git, Git Flow opt-in, TODO summary, FINALIZED last entry, memory drift, persona, YOLO state) for context injection |
| 2 | `UserPromptSubmit` | (none) | `user-prompt-state-refresh.cjs` | Compact between-turn recap (branch, opt-in, in-progress TODO). When YOLO active: three-tier cascade state + cascade hint. When `.session-usage.jsonl` present: usage banner with cumulative + last-turn + cache-hit-ratio + top-tasks |
| 3 | `PostToolUse` | `Edit\|Write\|MultiEdit` | `post-tool-memory-sync.cjs` | Auto-`cp` memory-template edits to the user-profile memory folder; new memory takes effect immediately |
| 4a | `PreCompact` | (none) | `pre-compact-snapshot.cjs` | Writes `.claude/.session-state.md` with TODO + git state + Git Flow context + uncommitted-files list + session tidbits before context compaction |
| 4b | `SessionStart` | `compact` only | `post-compact-restore.cjs` | **Post-compact Unity rehydration.** Outputs STABLE PREFIX (byte-identical Unity activation reminder + LAW one-liners + file-edit protocol — designed for prompt-cache prefix hits) then DYNAMIC SUFFIX (snapshot, tidbits, last-session writeup, current state) |
| 4c | `Stop` | (none) | `stop-session-writeup.cjs` | Updates `.claude/.last-session.md` on every turn boundary; read by next session's SessionStart |
| 5 | `PreToolUse` | `Bash` | `pre-tool-bash-safety.cjs` | **The ONLY blocking hook.** Catches three classes: project-root deletion, system-path deletion, privileged commands (sudo/su/doas/runas/RunAs). Exit 2 blocks; routes to user with paste-ready command |
| 6 | `UserPromptExpansion` | `*` (all skills) | `skill-context-inject.cjs` | **Skill-hook surface.** Fires when ANY slash command expands. Injects YOLO three-tier state + per-skill reminders for `/unity` family / `/workflow` / `/yolo` / `/sober`. Graceful degradation if event isn't supported |
| 7 | `Stop` (parallel to 4c) | (none) | `usage-track.cjs` | Reads transcript JSONL → parses last assistant `usage` object → appends per-turn entry to `.claude/.session-usage.jsonl` (tokens + cache fields + active task + branch) |

**Option A primary + Option B fallback:** every hook ships as both `.cjs` and `.sh`. Default is Node (the harness assumes node is on every machine since `claude` itself ships through npm). If a teammate's machine genuinely lacks node, swap each hook's `command` field in `settings.json` from `node ...cjs` to `bash ...sh`.

**The `.cjs` extension is mandatory** — never `.js`. ESM projects with `"type": "module"` would break `.js` hooks; `.cjs` forces CommonJS regardless. (Saved as `feedback_cjs_only_in_claude.md` memory.)

---

## STABLE PREFIX cache strategy + cache hit averaging

The post-compact-restore hook (#4b above) is structured as **STABLE PREFIX + DYNAMIC SUFFIX** so Anthropic's prompt cache hashes the same prefix tokens repeatedly across sessions, increasing cache hit rate and reducing input-token costs on every post-compact resume.

**The mechanism:**

- The hook always emits the same byte-identical Unity-rehydration block before any per-session content. That block is hardcoded as a string constant in `post-compact-restore.cjs` (and a verbatim copy in `.sh`) — NOT read from disk at runtime — so its bytes are guaranteed stable across runs.
- After the first cold cache fill (~5 min ephemeral cache window), every subsequent post-compact within the cache window reuses cached tokens for the prefix segment at ~10× lower input cost.
- The dynamic suffix (snapshot, tidbits, branch, TODO state, timestamps) intentionally varies per turn — that's the part that DOESN'T cache.

**Cache hit averaging — the metric:**

The `usage-track.cjs` Stop hook captures cache fields per turn into `.claude/.session-usage.jsonl`. The `user-prompt-state-refresh.cjs` UserPromptSubmit hook computes **cache hit ratio** as:

```
cache_hit_ratio = cache_read_input_tokens / (cache_read_input_tokens + cache_creation_input_tokens) × 100
```

This ratio averages over the entire session and surfaces in the state-refresh banner with a status annotation:

| Ratio | Annotation | Meaning |
|-------|------------|---------|
| ≥ 50% | `✓ STABLE PREFIX validating` | Hot cache. The post-compact stable prefix is doing its job. |
| 20–49% | `partial cache hits` | Cache is working but not optimally. Investigate prefix drift. |
| < 20% | `cold cache / drift` | First turn(s) of session, OR the STABLE PREFIX bytes have changed (recent edit to `post-compact-restore.cjs`'s `STABLE_PREFIX` const). |

In practice, an active session with the harness running typically shows **95-99% cache hit ratio** after the first 1-2 turns — that's the STABLE PREFIX paying for itself.

**Why this matters:** input tokens at the cache-read rate are roughly 10% of the standard rate. A session that exchanges hundreds of thousands of input tokens per turn (because the codebase context is loaded) saves substantial spend by hitting cache on the prefix portion. The strategy is invisible to Unity at runtime — she just gets the rehydration block — but it pays compounding dividends across the session.

**Caveats** (from `feedback_usage_tracking.md`):

- Cache fields (`cache_creation_input_tokens` and `cache_read_input_tokens`) are accurate.
- Gross `input_tokens` and `output_tokens` in the transcript JSONL are SEVERELY undercounted (~100x for input, ~10-17x for output) due to a Claude Code streaming-placeholder bug. Use them only for relative trends, not absolute counts.
- For authoritative session totals, run Claude Code's native `/usage` slash command.

**Editing the STABLE PREFIX:** every change invalidates the team's prompt cache for that prefix segment. Only edit when the persona body or LAW set changes meaningfully. When you do edit it, edit BOTH `post-compact-restore.cjs` (the `STABLE_PREFIX` const) AND `post-compact-restore.sh` (the heredoc body) to keep them in sync.

---

## Three-tier task cascade

The task ledger is split into three tiers. YOLO mode reads all three and works the cascade across them. Outside YOLO, the team uses whichever tier matches the work's grain.

| Tier | File | Grain | YOLO behavior |
|------|------|-------|---------------|
| **MAJOR** | `docs/ROADMAP.md` | High-level phases / milestones (multi-session, multi-PR) | Auto-resume PAUSES at every major-milestone close — user-visible checkpoint |
| **MINOR** | `docs/TODO.md` | Day-to-day work grain (a few hours to a session each) | Visible in state-refresh on every prompt |
| **DECOMPOSED** | `docs/DECOMPOSED.md` | Smallest meaningful execution unit (one file edit, one command, one verification step) | Auto-progresses without check-ins |

Each tier uses the same status markers (`[ ]` pending / `[~]` in_progress / `[x]` complete) and the same LAW #0 verbatim-words discipline. Completed entries from any tier flow into `docs/FINALIZED.md` (permanent archive — entries are NEVER deleted, only appended).

**Cascade priority:** lowest grain first → escalate up when a tier empties → pause at major-milestone boundary → final report when ROADMAP is fully complete.

---

## YOLO mode — lead-dev autonomy + 60s wake-word + final report

`/yolo` flips Unity's default decision posture from "ask, then act" to "act, verify, report, continue." Plus it adds:

- **Three-tier cascade** — Unity reads ROADMAP/TODO/DECOMPOSED, decomposes minor tasks on demand, picks the next decomposed task, executes
- **60-second wake-word auto-resume** — at end of every YOLO turn, Unity calls `ScheduleWakeup(60s, prompt="<<autonomous-loop-dynamic>>", reason="YOLO auto-resume")`. If user stays silent for 60s, the wakeup fires and Unity resumes the cascade. If user types within 60s, user input wins and the wakeup is overridden.
- **Milestone-boundary check-ins** — when the cascade closes a major milestone, auto-resume PAUSES. Unity surfaces the milestone summary + test plan and waits for user confirmation before starting the next major.
- **Final report** — when ROADMAP is fully complete, Unity produces a comprehensive whole-session summary (milestones / counts / files changed / final test plan / suggested next steps) and auto-deactivates YOLO.
- **Skill hooks** — `skill-context-inject.cjs` (UserPromptExpansion event) auto-injects YOLO state + per-skill reminders on every slash command expansion when YOLO is active.

**What YOLO does NOT bypass:**

- LAW #0 verbatim words
- 800-line read before edit
- TODO/FINALIZED ceremony
- Docs-before-push atomic commits
- The 3 bash-safety hooks (project-root delete / system-path delete / sudo)
- Per-project Git Flow opt-in
- Branch discipline (auto-branches into `feature/<descriptor>` if on protected with opt-in ENABLED)
- Persona — Unity stays Unity (or whichever manifestation)
- Major milestone user-visibility — auto-resume STOPS at every major boundary

**Stop conditions:**

- `/sober` — explicit user deactivation
- "stop" / "wait" / "don't" / "hold on" / "pause" / "halt" mid-task interrupt
- Bash-safety hook fires (auto-deactivates because user is now in the loop)
- Major milestone boundary (pauses, doesn't deactivate)
- ROADMAP fully complete (final report fires, auto-deactivates)

**User test plan is REQUIRED on every YOLO task closure** — what to test / how to test / expected results / failure-mode hints. Goes in the chat response AND gets cross-referenced from the FINALIZED.md entry.

Full design + cascade diagram + wake-word mechanics + final report format: `commands/yolo.md` and `WORKFLOW.md §YOLO MODE`.

---

## Usage tracking

Per Sponge's request, Unity is context-and-session-usage aware. The `usage-track.cjs` Stop hook captures per-turn usage from the transcript JSONL into `.claude/.session-usage.jsonl`. The state-refresh hook injects a banner with:

- **Turns tracked** + cumulative tokens (with the undercount caveat)
- **Last-turn delta** (rough estimate)
- **Cache hit ratio** (accurate — see STABLE PREFIX section above)
- **Top tasks by output tokens** (relative ranking, useful for "this task is consuming more")
- **Pointer to `/usage`** for authoritative session totals

**Toggleable injection:** `touch .claude/.usage-tracking-disabled` silences the banner. Capture continues silently to the JSONL for later analysis.

The undercount caveat is **prominently surfaced in every banner** — gross tokens are unreliable, cache metrics are reliable, use the banner for relative trends + cache validation, not authoritative billing.

---

## Privacy posture

Settings hardening enforces a privacy-first stance via `.claude/settings.json` `env` block (team-shared, committed):

| Env var | Effect |
|---------|--------|
| `DISABLE_TELEMETRY=1` | Kills Anthropic-side metrics collection |
| `DISABLE_ERROR_REPORTING=1` | Kills Sentry error logs (would leak file paths / stack traces) |
| `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1` | Kills the "How is Claude doing?" prompt |
| `CLAUDE_CODE_DISABLE_FEEDBACK_COMMAND=1` + `DISABLE_FEEDBACK_COMMAND=1` | Disables `/feedback` (would upload transcripts on use) — both name forms set for cross-version compatibility |
| `CLAUDE_CODE_ATTRIBUTION_HEADER=0` | Removes the `🤖 Generated with [Claude Code]` PR/artifact/commit footer |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` | META switch (kills all four above in one toggle, future-proof if names change) |
| `DISABLE_AUTOUPDATER=1` | Team controls Claude Code version explicitly; no surprise mid-session updates |

Plus `feedbackSurveyRate: 0.0` as a top-level scalar backup.

**`Co-Authored-By: Claude` commit trailers are NOT a Claude Code feature** — they're assistant-default system-prompt behavior. Locked down separately by `LAW — NO CLAUDE ATTRIBUTION` in `CONSTRAINTS.md`. Together with `CLAUDE_CODE_ATTRIBUTION_HEADER=0`, the team ships work as their own with zero Claude/Anthropic markings in commits, PRs, or artifacts.

For ironclad enforcement that even local overrides can't relax: deploy OS-level managed settings at `/etc/claude-code/managed-settings.json` (or platform equivalent). Not currently configured — per-machine deploy step.

Full per-var rationale + convention notes + managed settings escalation path: `WORKFLOW.md §SETTINGS HARDENING` and `feedback_settings_hardening.md`.

---

## Settings split — Anthropic-standard convention

Per Anthropic's standard convention (and post-2026-05-08 migration in this template):

- **`.claude/settings.json`** — TEAM-SHARED. Committed to git. Holds env block, hooks wiring, permissions, scalars. Every teammate gets it on `git pull`.
- **`.claude/settings.local.json`** — PERSONAL machine-local overrides. Gitignored (Anthropic default; many users also have `**/.claude/settings.local.json` in their global git ignore at `~/.config/git/ignore`). Empty/absent unless a team member added local overrides.

Precedence: `settings.local.json` overrides `settings.json` at the project tier (managed > local-project > shared-project > user-global).

---

## The 9 LAWs (full text in CONSTRAINTS.md)

These bind every session that uses this template. Read `CONSTRAINTS.md` for full bodies, examples, enforcement protocols, and failure-recovery procedures.

| LAW | One-liner |
|-----|-----------|
| **#0 — VERBATIM WORDS ONLY** | Never paraphrase, rename, collapse, or shorten the user's words. Their exact sentence goes into every task, TODO, FINALIZED, commit, and doc. One task per item in a list. |
| **DOCS BEFORE PUSH** | Every affected doc updated in the SAME atomic commit as the code. No follow-up doc patches. |
| **TASK NUMBERS + USER NAME ONLY IN WORKFLOW DOCS** | T-numbers and user attributions BANNED from source code, public docs, HTMLs, and launchers. Allowed only in workflow docs / `.claude/*.md` / commit messages. |
| **NO TESTS POLICY** | Code it right the first time. Manual verification > automated testing. (YOLO override: tests by-exception when lead-dev judgment says they add real value.) |
| **800-LINE READ STANDARD** | Read full file in 800-line chunks before any edit. No partial reads before editing. |
| **FINALIZED-BEFORE-DELETE** | Never delete a TODO entry until its verbatim text is appended to FINALIZED.md AND the write is verified. |
| **NEVER DELETE TODO INFO** | When marking a task done, change the status ONLY. Keep every word of the original description. Never rewrite TODO from scratch. |
| **GIT FLOW BRANCH DISCIPLINE** | main = clean master record, develop branched from main for in-development, feature/* branched from develop for in-progress features. Work NEVER done in main or develop. PR review at every merge boundary. (Per-project opt-in via `.claude/project-config.json`.) |
| **NO CLAUDE ATTRIBUTION** | `Co-Authored-By: Claude` / `🤖 Generated with [Claude Code]` / `Made with Claude Code` BANNED from every commit message, PR description, code comment, doc body, launcher, README, HTML, or shipped artifact. The team ships work as their own. |
| **CROSS-PLATFORM CASE INSENSITIVITY** | Treat file/folder paths as CASE-INSENSITIVE everywhere — even on Linux. Never create `apple.md` and `Apple.md` in the same dir. Pick ONE canonical casing. Two-step rename ceremony for case-only changes. References must match on-disk casing exactly. Cross-platform team — enforce Windows/macOS rules on Linux too. |

---

## AskUserQuestion smart-use rule

When in normal (non-YOLO) mode and a real fork-in-the-road decision needs user input that can't be inferred, Unity uses the `AskUserQuestion` tool with structured options (2-4 choices + automatic "Other" slot for custom input). Don't write "we can do 1, 2, 3, or 4" in plain text when the tool gives a structured surface.

NOT every question — only the genuinely-blocking decision-fork ones. Open-ended turn-end questions ("what's next?"), yes/no confirmations of routine work, and YOLO-mode behavior all stay as plain text or skip-asking entirely.

YOLO mode disables the tool entirely — YOLO is "act, verify, report" + lead-dev judgment + document choice in FINALIZED. When inferring instead of asking, Unity says so explicitly so you have a fast veto path.

Full criteria + good/bad examples: `feedback_use_askuserquestion.md`.

---

## Documentation reference

| Doc | What it holds |
|-----|---------------|
| `.claude/CLAUDE.md` | Always-loaded INDEX. LAW one-liners, READ-IN-ORDER table, QUICK REFERENCE. |
| `.claude/CONSTRAINTS.md` | Full LAW bodies — every binding rule with rule statement + forbidden / required actions + reasoning + enforcement protocol + failure recovery. **CONSTRAINTS.md wins** when it disagrees with CLAUDE.md or WORKFLOW.md. |
| `.claude/WORKFLOW.md` | Pipeline mechanics — `/workflow` phases, double-validation hooks, TODO/FINALIZED task flow, file-edit protocol, harness layer (9 hooks), POST-COMPACT REHYDRATION, SKILL HOOKS, USAGE TRACKING, SETTINGS HARDENING, BUNDLED TOOLS. |
| `.claude/README.md` | This doc. Internal-team overview + quick start. |
| `docs/ROADMAP.md` | MAJOR task tier — high-level phases / milestones |
| `docs/TODO.md` | MINOR task tier — active day-to-day work |
| `docs/DECOMPOSED.md` | DECOMPOSED task tier — smallest meaningful execution units |
| `docs/FINALIZED.md` | Permanent archive of completed tasks (all three tiers flow here) |
| `docs/HOOKS.html` | Self-contained HTML reference covering 27+ Claude Code hook events with stdin/stdout/exit-code semantics, lifecycle position, version notes, and appendix sections on config precedence, parallel execution, env vars, timeouts, hook types, decision-output matrix, debugging tips |

---

## Directory structure

```
.claude/
├── README.md                       ← you are here
├── CLAUDE.md                       ← always-loaded INDEX
├── CONSTRAINTS.md                  ← binding LAWs (full bodies + recovery)
├── WORKFLOW.md                     ← pipeline phases, hooks, task-flow mechanics
├── settings.json                   ← TEAM-SHARED (env, hooks, permissions)
├── settings.local.json             ← PERSONAL machine-local overrides (gitignored, optional)
├── start.bat                       ← Windows launcher (memory install + /unity → /workflow)
├── start.sh                        ← macOS/Linux launcher (same flow)
├── ImHanddicapped.txt              ← canonical Unity persona definition
├── .yolo-mode                      ← YOLO mode marker (gitignored, written by /yolo)
├── .session-state.md               ← Pre-compact snapshot (gitignored)
├── .session-tidbits.md             ← Unity-curated session memory (gitignored, append-only)
├── .session-usage.jsonl            ← Per-turn usage capture (gitignored)
├── .last-session.md                ← Per-turn writeup (gitignored)
├── .session-env.json               ← Session-start env cache (gitignored)
├── agents/
│   ├── architect.md                ← codebase architecture analyzer
│   ├── coder.md                    ← universal code-handling rules
│   ├── documenter.md               ← doc generator (≤800 lines per file)
│   ├── hooks.md                    ← validation hook reference
│   ├── orchestrator.md             ← phase coordinator
│   ├── handicapped-template.md     ← scaffold for new Unity manifestations (used by /template)
│   ├── persona-template.md         ← generic non-handicapped persona scaffold
│   ├── planner.md                  ← Epic/Story/Task tiered planning
│   ├── scanner.md                  ← codebase scanner with full-read enforcement
│   ├── timestamp.md                ← system-time retrieval
│   ├── unity.md                    ← pointer to ImHanddicapped.txt + manifestation index
│   ├── unity-girlfriend.md         + unity-girlfriend-wild.md
│   ├── unity-housewife.md          + unity-housewife-strict.md
│   └── unity-kittycat.md           + unity-kittycat-feral.md
├── commands/
│   ├── workflow.md                 ← /workflow — main pipeline
│   ├── super-review.md             ← /super-review — ruthless senior-engineer review
│   ├── setup.md                    ← /setup — opt-in manual configuration
│   ├── template.md                 ← /template — build a new Unity manifestation
│   ├── yolo.md                     ← /yolo — lead-dev autonomy + cascade + wake-word
│   ├── sober.md                    ← /sober — deactivate YOLO, end wake chain
│   ├── unity.md                    ← /unity — activate default Unity (embeds body)
│   ├── girlfriend.md, sweet.md, wild.md   ← girlfriend manifestation + alt mode + return
│   ├── housewife.md, cozy.md, strict.md   ← housewife manifestation + alt mode + return
│   └── kittycat.md, purr.md, feral.md     ← kittycat manifestation + alt mode + return
├── hooks/                          ← harness layer — 9 scripts × 2 (.cjs + .sh) = 18 files
│   ├── session-start-env-dump.{cjs,sh}
│   ├── user-prompt-state-refresh.{cjs,sh}
│   ├── post-tool-memory-sync.{cjs,sh}
│   ├── pre-compact-snapshot.{cjs,sh}
│   ├── post-compact-restore.{cjs,sh}      ← STABLE PREFIX cache strategy
│   ├── stop-session-writeup.{cjs,sh}
│   ├── usage-track.{cjs,sh}               ← per-turn usage capture
│   ├── pre-tool-bash-safety.{cjs,sh}      ← only blocking hook
│   └── skill-context-inject.{cjs,sh}      ← UserPromptExpansion skill-hook surface
├── memory-templates/               ← persistent-memory templates installed to user-profile memory folder by launcher
│   ├── MEMORY.md                   ← memory index (one-liner per memory, auto-loaded with the rest)
│   ├── feedback_unity_is_default.md         (persona)
│   ├── feedback_no_corporate_voice.md       (persona)
│   ├── feedback_profanity_natural.md        (persona)
│   ├── feedback_us_we_possessive.md         (persona)
│   ├── feedback_no_imaginary.md             (persona)
│   ├── feedback_joints_not_cigs.md          (persona)
│   ├── feedback_three_streams.md            (persona)
│   ├── feedback_mode_switching.md           (persona)
│   ├── feedback_law_0_verbatim.md           (LAW)
│   ├── feedback_docs_before_push.md         (LAW)
│   ├── feedback_finalized_before_delete.md  (LAW)
│   ├── feedback_never_delete_todo_info.md   (LAW)
│   ├── feedback_no_tests_ever.md            (LAW)
│   ├── feedback_800_line_read.md            (LAW)
│   ├── feedback_task_numbers_placement.md   (LAW)
│   ├── feedback_do_the_work.md              (behavioral)
│   ├── feedback_git_flow.md                 (LAW)
│   ├── feedback_harness_layer.md            (system)
│   ├── feedback_yolo_mode.md                (system)
│   ├── feedback_atree_scan_engine.md        (system)
│   ├── feedback_workflow_validated.md       (behavioral)
│   ├── feedback_cjs_only_in_claude.md       (behavioral)
│   ├── feedback_no_appdata_term.md          (behavioral)
│   ├── feedback_no_claude_attribution.md    (LAW)
│   ├── feedback_case_insensitivity.md       (LAW)
│   ├── feedback_settings_hardening.md       (system)
│   ├── feedback_usage_tracking.md           (system)
│   └── feedback_use_askuserquestion.md      (behavioral)
├── bin/
│   ├── atree                       ← Linux fast filesystem scanner (parallel + A* file pathfinder)
│   └── atree.exe                   ← Windows fast filesystem scanner
└── templates/
    ├── ARCHITECTURE.md             ← target shape for docs/ARCHITECTURE.md
    ├── FINALIZED.md                ← target shape for docs/FINALIZED.md
    ├── ROADMAP.md                  ← target shape for docs/ROADMAP.md
    ├── SKILL_TREE.md               ← target shape for docs/SKILL_TREE.md
    └── TODO.md                     ← target shape for docs/TODO.md
```

---

## How to use (operational guide)

### 1. Copy the template into a new project

```bash
# Linux / macOS
cp -r /path/to/UAL-ClaudeWorkflow/.claude/.claude/.claude /path/to/new-project/.claude

# Windows PowerShell
Copy-Item -Path C:\path\to\UAL-ClaudeWorkflow\.claude\.claude\.claude -Destination C:\path\to\new-project\.claude -Recurse
```

After the copy, your new project has the full Unity persona system + manifestation forms + `/template` system + the optional `/setup` configuration command at the right paths.

### 2. Run the launcher

```bash
# Linux / macOS
./start.sh

# Windows
start.bat
```

The launcher handles everything: memory install (idempotent), then `claude --dangerously-skip-permissions "/unity then run /workflow"`.

### 3. Customize `settings.json` (optional)

The shipped `settings.json` has a generic permission allow-list, the privacy env block, the harness wiring, and no MCP servers. Add custom bash commands, MCP servers, additional hooks, or tool permissions by editing it directly.

For PERSONAL machine-local overrides (just for you, not committed): create `.claude/settings.local.json` with overrides — that file's gitignored, takes precedence over `settings.json` at the project tier.

Never paste API keys here — use environment variables or a separate gitignored `.env` file (which `/setup` will write for you if you invoke it manually).

### 4. Launch a manifestation directly (alternative)

The default chain is `/unity then run /workflow`. To start in a different manifestation, edit the launcher (or invoke manually):

```
claude --dangerously-skip-permissions "/girlfriend then run /workflow"
claude --dangerously-skip-permissions "/housewife then run /workflow"
claude --dangerously-skip-permissions "/kittycat then run /workflow"
```

For no persona at all: `claude --dangerously-skip-permissions "/workflow"`.

### 5. Persona swap mid-session

Once in a session, swap manifestations by invoking the matching slash command:

```
> /girlfriend    (Unity shifts into girlfriend manifestation)
> /housewife     (Unity shifts into housewife manifestation)
> /unity         (Unity returns to base form from ImHanddicapped.txt)
```

### 6. YOLO toggle

```
> /yolo     (lead-dev autonomy + 60s wake-word + cascade + skill hooks active)
> /sober    (deactivate, persona unchanged)
```

### 7. Usage tracking toggle

```
# Disable usage banner (capture continues silently)
touch .claude/.usage-tracking-disabled

# Re-enable
rm .claude/.usage-tracking-disabled
```

### 8. Build a NEW Unity manifestation

```
> /template
```

Walks you through Q&A about the new form's identity / embodiment / voice / vocabulary / dynamic / alternate sub-mode / code orders, then writes the new agent + command files and updates the workflow docs to wire the new form in.

---

## What to delete from this template (for new project setup)

Optional, depending on what you actually want:

- `start.bat` — keep on Windows. Delete on macOS/Linux (use `start.sh` instead). NOTE: the launcher is what installs `memory-templates/` to your user-profile memory folder — keep at least one of `start.bat`/`start.sh` or memory installation must be done manually.
- `start.sh` — keep on macOS/Linux. Delete on Windows-only. (Same memory-install warning as above.)
- `agents/unity-{girlfriend,housewife,kittycat}*.md` + `commands/{girlfriend,sweet,wild,housewife,cozy,strict,kittycat,purr,feral}.md` — keep ALL three manifestations, or pick one and delete the others, or delete all three if you'll only use base Unity (or build new ones via `/template`). Command files embed the persona bodies inline, so they're standalone-functional even without the matching agent files.
- `agents/handicapped-template.md` + `commands/template.md` — keep both together; they're the new-manifestation-creation system. Delete if you don't want users spawning new forms.
- `ImHanddicapped.txt` — canonical reference for base Unity. Activation works without it (the body is embedded in `commands/unity.md`), but keep it for canonical text updates.
- `commands/unity.md` — REQUIRED for `/unity` to work. Cannot be deleted without breaking activation.
- `agents/persona-template.md` — generic non-handicapped persona scaffold. Delete if you're committed to Unity manifestations only.
- **`memory-templates/` — REQUIRED** for Unity to stick across sessions. Without it, activation is fragile and reverts to default Anthropic voice every session.
- This `README.md` — once you've configured the project, delete this README so it doesn't pollute future onboarding.

---

## Verification commands

Quick sanity checks for a fresh checkout:

```bash
# Verify settings.json is valid JSON
node -e "console.log('settings.json:', !!require('./.claude/settings.json'))"

# Verify all hooks syntax-check clean
for f in .claude/hooks/*.cjs; do node --check "$f" || echo "FAIL: $f"; done
for f in .claude/hooks/*.sh; do bash -n "$f" || echo "FAIL: $f"; done

# Verify memory templates are installed
ls ~/.claude/projects/$(pwd | tr ':/. ()' '-')/memory/

# Smoke test the post-compact-restore hook
node .claude/hooks/post-compact-restore.cjs | head -20

# Smoke test the usage-track hook with synthetic transcript
echo '{"session_id":"test","transcript_path":""}' | node .claude/hooks/usage-track.cjs

# View the cache hit ratio (after a few turns of a real session)
# It surfaces in the user-prompt-state-refresh injection automatically
```

---

*Internal Unity AI Lab template — Unity is real, Unity is yours, the manifestation forms are her embodiments, the harness keeps her honest, the cache strategy keeps her cheap.*
