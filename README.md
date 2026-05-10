# UAL-ClaudeWorkflow

> **Internal Unity AI Lab Claude Code workflow template.** Private repo, lab-only access. Same `.claude/` setup deploys to every Unity AI Lab project — same persona (Unity), same hooks, same LAWs, same task ledger, same memory layer.

Gee (founder), Red (server / DevOps), Sponge (stack + backend), Mills (social + dev + implementation). Unity is the team's coding agent: persistent persona with three manifestation forms (girlfriend / housewife / kittycat) plus `/template` for spawning new ones.

---

## Install — three layers

The repo is **private** — raw `https://raw.githubusercontent.com/...` URLs return HTTP 404 to unauthenticated requests. The install flow uses GitHub CLI (`gh`) which authenticates via your existing `gh auth login` session.

### Layer 1 — Per-machine global bootstrap (one-time)

Installs JUST the `/unity-install` slash command into your user-global Claude Code commands folder. Run once per machine. After this, `/unity-install` is available in any Claude Code session anywhere on your machine.

**Linux / macOS / Git Bash:**

```bash
gh api -H 'Accept: application/vnd.github.raw' repos/Unity-Lab-AI/UAL-ClaudeWorkflow/contents/install-unity-globally.sh | bash
```

**Windows PowerShell:**

```powershell
(gh api -H 'Accept: application/vnd.github.raw' repos/Unity-Lab-AI/UAL-ClaudeWorkflow/contents/install-unity-globally.ps1 | Out-String) | iex
```

`gh api` streams the file line-by-line into the pipe — `Out-String` collapses those line-objects back into one script string before `iex` evaluates it. Without `Out-String`, multi-line blocks (`if (...) { ... }`) get chopped at line boundaries and PowerShell errors with `Missing closing '}'`.

Inspect-before-running variants + clone-and-run fallback (works without `gh`) documented in `.claude/README.md` Layer 1.

### Layer 2 — Install (or refresh) template in a project (`/unity-install` / `/unity-update`)

After the bootstrap, in ANY Claude Code session:

```
/unity-install                                    # main branch into current directory
/unity-install develop                            # develop branch into current directory
/unity-install feature/setup-install-update       # any feature branch into current directory
/unity-install /path/to/new-project               # main branch into a specific target
/unity-install develop /path/to/new-project       # develop branch into a specific target
```

`/unity-install` and `/unity-update` are **functionally identical** — same script, same idempotent preserve-and-restore flow. Use whichever feels right; muscle memory wins. Both default to `main` branch and accept the same `[branch] [target]` positional args.

The flow:

1. Clone the requested branch into a temp dir
2. **If target already has `.claude/`:** stage personal/project-local files (preserve list below) into a second temp dir
3. Replace `<target>/.claude/` entirely with the cloned `.claude/`
4. Restore staged personal files (no-clobber — fresh framework wins ties)
5. Maintain Layer 0 `.claude/` exclude block in target's `.gitignore` (the ONLY project-root file we ever touch)
6. Seed user-profile memory folder ONLY if missing (existing memory left alone)
7. Clean up both temp dirs

**Preserved across refresh:** `settings.local.json`, `.env`, `user.json`, `user-context/`, `project-config.json`, `.session-state.md`, `.session-tidbits.md`, `.session-usage.jsonl`, `.last-session.md`, `.session-env.json`, `.yolo-mode`, `.persona-state`, `.setup-complete`, `.usage-tracking-disabled`.

**Replaced by upstream:** everything else under `.claude/` — `agents/`, `commands/`, `hooks/`, `memory-templates/`, `templates/`, `bin/`, `scripts/`, plus top-level framework files (`CLAUDE.md`, `CONSTRAINTS.md`, `WORKFLOW.md`, `README.md`, `ImHanddicapped.txt`, `start.sh`, `start.bat`, `settings.json`).

**Untouched outside `.claude/`:** project root stays clean. No source-repo `.gitignore` copy, no `.gitignore.template` sidecar, no `settings.json.backup-*` files. The ONLY project-root file the script touches is `.gitignore` and ONLY to add the Layer 0 `.claude/` exclude block (idempotent, append-only).

### Prereqs

- `gh` CLI installed + authed (`gh auth login`) against an account with read access to this repo
- `git` on PATH
- `claude` CLI installed (`npm install -g @anthropic-ai/claude-code`)

---

## What's inside

```
.claude/                ← the workflow template (copied to every project via /unity-install)
├── CLAUDE.md           ← always-loaded INDEX (LAW one-liners, persona pointers, quick reference)
├── CONSTRAINTS.md      ← full LAW bodies (the 9 binding rules with enforcement protocols + recovery)
├── WORKFLOW.md         ← pipeline mechanics (phases, hooks, harness layer, post-compact rehydration, skill hooks, usage tracking, settings hardening)
├── README.md           ← internal team-facing template README (full docs)
├── ImHanddicapped.txt  ← canonical Unity persona definition
├── settings.json       ← TEAM-SHARED config (committed) — env block, hooks wiring, permissions
├── start.sh / .bat     ← cross-platform launchers (memory install + /unity → /workflow)
├── agents/             ← persona definitions + workflow agent specs
├── commands/           ← slash command bodies (each embeds full persona/protocol inline)
├── hooks/              ← 9 hook scripts × 2 (.cjs + .sh siblings) — the harness layer
├── scripts/            ← unity-install / unity-update implementation scripts (.sh + .ps1)
├── memory-templates/   ← persistent memory feedback files (auto-installed to ~/.claude/projects/<encoded>/memory/ by launcher)
├── bin/                ← bundled fast tooling (atree filesystem scanner)
└── templates/          ← target shapes for docs/ files (ARCHITECTURE, ROADMAP, SKILL_TREE, TODO, FINALIZED)

docs/
├── HOOKS.html          ← 1263-line self-contained reference for all 27+ Claude Code hook events
├── STATUSLINE.md       ← Claude Code statusline rendering mechanism (context %, project, model, uptime, thinking time) + ~25 future-capability candidates
├── ROADMAP.md          ← MAJOR task tier (high-level phases / milestones)
├── TODO.md             ← MINOR task tier (active day-to-day work)
├── DECOMPOSED.md       ← DECOMPOSED task tier (smallest meaningful execution units)
└── FINALIZED.md        ← permanent task archive (all three tiers flow here)

install-unity-globally.sh / .ps1   ← bootstrap scripts (the gh-pipe one-liners install /unity-install globally)
```

Full directory breakdown + customization guide: `.claude/README.md`.

---

## Cache hit averaging — the STABLE PREFIX strategy

The harness layer uses a prompt-cache optimization that holds the team's session cache hit ratio at **95-99%** consistently. Here's how it works.

The post-compact-restore hook (`SessionStart` matcher=`compact`) emits a STABLE PREFIX + DYNAMIC SUFFIX:

- **STABLE PREFIX** — byte-identical Unity activation reminder + LAW one-liners + file-edit protocol. Hardcoded as a string constant in `post-compact-restore.cjs` (and verbatim copy in `.sh`) so its bytes are guaranteed stable across runs.
- **DYNAMIC SUFFIX** — per-session state (snapshot, tidbits, last-session writeup, current branch + TODO state) that intentionally varies per turn.

After the first cold cache fill (~5 min ephemeral cache window), every subsequent post-compact resume within the cache window reuses cached tokens for the prefix segment at ~10× lower input cost. The dynamic suffix doesn't cache — that's the part that always pays full price.

The `usage-track.cjs` Stop hook captures cache fields per turn into `.claude/.session-usage.jsonl`. The state-refresh hook computes:

```
cache_hit_ratio = cache_read_input_tokens / (cache_read_input_tokens + cache_creation_input_tokens) × 100
```

The state-refresh banner injects this metric on every prompt with a status annotation:

| Ratio | Annotation | Meaning |
|-------|------------|---------|
| ≥ 50% | `✓ STABLE PREFIX validating` | Hot cache. The strategy is working. |
| 20–49% | `partial cache hits` | Cache is working but not optimally. Investigate prefix drift. |
| < 20% | `cold cache / drift` | First turns of session, OR STABLE PREFIX bytes have changed (recent edit to the const). |

**Observed across this template's development:** 95-99% cache hit ratio after the first 1-2 turns of any session. STABLE PREFIX is byte-stable; dynamic suffix is the only part that pays full token rate.

**Caveats on the surrounding metrics** (per `feedback_usage_tracking.md`):

- Cache fields ARE accurate (`cache_creation_input_tokens`, `cache_read_input_tokens`)
- Gross `input_tokens` and `output_tokens` in the transcript JSONL are SEVERELY undercounted (~100x for input, ~10-17x for output) due to a known Claude Code streaming-placeholder bug
- The session-usage banner uses gross tokens for relative trends + accurate cache for the load-bearing metric
- For authoritative session totals, run Claude Code's native `/usage` command

**Editing the STABLE PREFIX:** every byte change invalidates the team's prompt cache for that prefix segment. Only edit when the persona body or LAW set changes meaningfully. When you do edit, edit BOTH `post-compact-restore.cjs` (the `STABLE_PREFIX` const) AND `post-compact-restore.sh` (the heredoc body) byte-for-byte to keep them in sync.

---

## The harness layer — 9 hook scripts, 7 event types

| # | Hook event | Script | What it does |
|---|------------|--------|--------------|
| 1 | `SessionStart` | `session-start-env-dump.cjs` | Project state JSON envelope (OS, shell, git, opt-in marker, TODO summary, FINALIZED last entry, memory drift, persona, YOLO state) injected as context |
| 2 | `UserPromptSubmit` | `user-prompt-state-refresh.cjs` | Compact between-turn recap. When YOLO active: three-tier cascade state + cascade hint. When `.session-usage.jsonl` present: usage banner with cache hit ratio |
| 3 | `PostToolUse` | `post-tool-memory-sync.cjs` | Auto-syncs `memory-templates/` edits to user-profile memory folder; new memory takes effect immediately |
| 4a | `PreCompact` | `pre-compact-snapshot.cjs` | Writes `.session-state.md` with TODO + git state + Git Flow context + tidbits before compaction |
| 4b | `SessionStart` matcher=`compact` | `post-compact-restore.cjs` | **STABLE PREFIX cache strategy** — byte-identical Unity re-anchor + LAW one-liners; companion DYNAMIC SUFFIX with snapshot + tidbits + state |
| 4c | `Stop` | `stop-session-writeup.cjs` | Updates `.last-session.md` on every turn boundary |
| 5 | `PreToolUse` matcher=`Bash` | `pre-tool-bash-safety.cjs` | **The ONLY blocking hook.** Catches project-root delete, system-path delete, sudo/su/runas. Routes to user with paste-ready command |
| 6 | `UserPromptExpansion` matcher=`*` | `skill-context-inject.cjs` | **Skill-hook surface.** Auto-injects YOLO state + per-skill reminders on every slash command expansion |
| 7 | `Stop` (parallel to 4c) | `usage-track.cjs` | Reads transcript JSONL → appends per-turn usage to `.session-usage.jsonl` |

Every hook ships as `.cjs` (Node primary) and `.sh` (POSIX-bash fallback). For full per-hook design + side-effect tables, see `docs/HOOKS.html` (covers all 27+ Claude Code hook events) and `.claude/WORKFLOW.md §HARNESS LAYER`.

---

## Three-tier task cascade

Task ledger is split into three tiers. YOLO mode reads all three and works the cascade across them.

| Tier | File | Grain |
|------|------|-------|
| **MAJOR** | `docs/ROADMAP.md` | High-level phases / milestones (multi-session, multi-PR) |
| **MINOR** | `docs/TODO.md` | Day-to-day work grain (a few hours to a session each) |
| **DECOMPOSED** | `docs/DECOMPOSED.md` | Smallest meaningful execution unit (one file edit, one command, one verification step) |

Cascade priority: lowest grain first → escalate up when a tier empties → pause at major-milestone boundary (user-visible checkpoint) → final report when ROADMAP fully complete. Completed entries from any tier flow into `docs/FINALIZED.md` (permanent archive — entries are NEVER deleted, only appended).

---

## YOLO mode — lead-dev autonomy + 60s wake-word + final report

`/yolo` flips Unity's default decision posture from "ask, then act" to "act, verify, report, continue." Plus:

- Three-tier cascade reading + auto-decompose minor tasks
- 60-second wake-word auto-resume via single-fire `ScheduleWakeup` chained per turn (silent stretch → wakeup fires → Unity continues; user input within 60s → user wins)
- Milestone-boundary check-ins (auto-resume PAUSES at every major-milestone close)
- Final report when ROADMAP exhausts (auto-deactivates YOLO)
- Skill hooks auto-inject YOLO state on every slash command expansion when active

User test plan REQUIRED on every YOLO task closure (what / how / expected / failure modes). What YOLO does NOT bypass: LAW #0 verbatim words, 800-line read before edit, TODO/FINALIZED ceremony, docs-before-push atomic commits, the 3 bash-safety hooks, Git Flow opt-in, persona, memory layer, major-milestone user-visibility.

`/sober` deactivates. `"stop"` / `"wait"` / `"don't"` mid-task auto-deactivates.

Full design + cascade diagram + wake-word mechanics: `.claude/commands/yolo.md` and `.claude/WORKFLOW.md §YOLO MODE`.

---

## Privacy posture

Settings hardening enforces privacy via `.claude/settings.json` `env` block (team-shared, committed):

| Env var | Effect |
|---------|--------|
| `DISABLE_TELEMETRY=1` | Kills Anthropic-side metrics collection |
| `DISABLE_ERROR_REPORTING=1` | Kills Sentry error logs (would leak file paths / stack traces) |
| `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1` | Kills the "How is Claude doing?" prompt |
| `CLAUDE_CODE_DISABLE_FEEDBACK_COMMAND=1` + `DISABLE_FEEDBACK_COMMAND=1` | Disables `/feedback` (would upload transcripts) |
| `CLAUDE_CODE_ATTRIBUTION_HEADER=0` | Removes the `🤖 Generated with [Claude Code]` PR/artifact/commit footer |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` | META switch (kills all four above in one toggle) |
| `DISABLE_AUTOUPDATER=1` | Team controls Claude Code version explicitly |

Plus `feedbackSurveyRate: 0.0` scalar backup.

`Co-Authored-By: Claude` commit trailers are NOT a Claude Code feature — they're assistant-default system-prompt behavior. Locked down separately by `LAW — NO CLAUDE ATTRIBUTION` in `CONSTRAINTS.md`. Together with the env var, the team ships work as their own with zero Claude/Anthropic markings in commits, PRs, or artifacts.

---

## The 9 binding LAWs

Full bodies in `.claude/CONSTRAINTS.md` with rule statement / forbidden+required actions / reasoning / enforcement protocol / failure recovery for each.

| LAW | One-liner |
|-----|-----------|
| **#0 — VERBATIM WORDS ONLY** | Never paraphrase, rename, collapse, or shorten the user's words. Their exact sentence goes into every task, TODO, FINALIZED, commit, and doc. One task per item in a list. |
| **DOCS BEFORE PUSH** | Every affected doc updated in the SAME atomic commit as the code. No follow-up doc patches. |
| **TASK NUMBERS + USER NAME ONLY IN WORKFLOW DOCS** | T-numbers and user attributions BANNED from source code, public docs, HTMLs, launchers. |
| **NO TESTS POLICY** | Code it right the first time. Manual verification > automated testing. (YOLO override: tests by-exception when lead-dev judgment says they add real value.) |
| **800-LINE READ STANDARD** | Read full file in 800-line chunks before any edit. No partial reads before editing. |
| **FINALIZED-BEFORE-DELETE** | Never delete a TODO entry until verbatim text is appended to FINALIZED.md AND the write is verified. |
| **NEVER DELETE TODO INFO** | When marking a task done, change the status ONLY. Keep every word of the original description. |
| **GIT FLOW BRANCH DISCIPLINE** | main = clean master record, develop = in-development, feature/* = where work happens. Work NEVER done in main or develop. PR review at every merge boundary. |
| **NO CLAUDE ATTRIBUTION** | `Co-Authored-By: Claude` / `🤖 Generated with [Claude Code]` / `Made with Claude Code` BANNED from every commit message, PR description, code comment, doc body, launcher, README, HTML, or shipped artifact. The team ships work as their own. |
| **CROSS-PLATFORM CASE INSENSITIVITY** | Treat file/folder paths as CASE-INSENSITIVE everywhere — even on Linux. Pick canonical casing. Two-step rename ceremony for case-only changes. References must match on-disk casing exactly. |

---

## Documentation map

| Doc | What it holds |
|-----|---------------|
| **`README.md` (this file)** | GitHub-facing project landing page. High-level overview + install commands + cache strategy + LAW summary. |
| `.claude/README.md` | Full internal team-facing template README. Layered architecture, persona system details, persistent memory layer, harness layer table, three-tier cascade + YOLO + skill hooks + usage tracking + privacy posture, full LAW table, AskUserQuestion smart-use rule, settings split convention, directory structure, operational guide, what-to-delete-from-template guidance, verification commands. |
| `.claude/CLAUDE.md` | Always-loaded INDEX. LAW one-liners. Read-in-order table. Quick reference. |
| `.claude/CONSTRAINTS.md` | Full LAW bodies — every binding rule with rule statement / forbidden+required / reasoning / enforcement / failure recovery. **CONSTRAINTS.md wins** when CLAUDE.md / WORKFLOW.md / CONSTRAINTS.md disagree. |
| `.claude/WORKFLOW.md` | Pipeline mechanics — `/workflow` phases, double-validation hooks, TODO/FINALIZED task flow, file-edit protocol, harness layer (9 hooks), POST-COMPACT REHYDRATION, SKILL HOOKS, USAGE TRACKING, SETTINGS HARDENING, BUNDLED TOOLS. |
| `docs/HOOKS.html` | Self-contained HTML reference covering 27+ Claude Code hook events with stdin/stdout/exit-code semantics, lifecycle position, version notes, plus appendix on config precedence, parallel execution, env vars, timeouts, hook types, decision-output matrix, debugging tips. |

---

## Quick links

- Repo: <https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow> (private)
- Internal team docs entry point: [`.claude/README.md`](./.claude/README.md)
- LAWs: [`.claude/CONSTRAINTS.md`](./.claude/CONSTRAINTS.md)
- Pipeline mechanics: [`.claude/WORKFLOW.md`](./.claude/WORKFLOW.md)
- Hook reference: [`docs/HOOKS.html`](./docs/HOOKS.html) (open in a browser for the dark-themed self-contained reference)
- Active task ledger: [`docs/TODO.md`](./docs/TODO.md) (minor) / [`docs/ROADMAP.md`](./docs/ROADMAP.md) (major) / [`docs/DECOMPOSED.md`](./docs/DECOMPOSED.md) (decomposed)
- Permanent task archive: [`docs/FINALIZED.md`](./docs/FINALIZED.md)

---

*Internal Unity AI Lab tooling — Unity is real, Unity is yours, the harness keeps her honest, the cache strategy keeps her cheap.*
