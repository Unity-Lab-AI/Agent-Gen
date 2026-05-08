# WORKFLOW — Pipeline, Hooks, Task Flow

This file holds the operational workflow mechanics: `/workflow` pipeline phases, double-validation hooks, TODO/FINALIZED task flow, file-edit protocol, and agent file reference.

`.claude/CLAUDE.md` is the index that references this file. `.claude/CONSTRAINTS.md` holds binding LAWs. When CLAUDE.md, this file, or CONSTRAINTS.md disagree: **CONSTRAINTS.md wins**.

---

## DOUBLE VALIDATION HOOKS

Every hook runs TWICE on failure before blocking:

```
ATTEMPT 1 → FAIL → AUTOMATIC RETRY
ATTEMPT 2 → FAIL → BLOCKED (cannot proceed)
```

This prevents false failures while enforcing strict validation.

### Hook types

| Hook | Purpose | When |
|------|---------|------|
| Persona Hook | Verify persona voice active (if a persona is configured) | Before each phase |
| Read Hook | Verify full file read | Before any edit |
| Line Limit Hook | Verify output correctness | After any write |
| Phase Hook | Verify phase complete | Before proceeding |

---

## `/workflow` PIPELINE

The `/workflow` slash command executes this pipeline:

### Phase -1 — LAW #0 verbatim words check (cannot skip)

- Re-read the user's latest instruction
- Count items in the instruction
- Confirm every noun/verb is preserved in any tasks created
- **Gate -1:** LAW #0 verified

### Phase 0.5 — Timestamp retrieval (cannot skip)

- Execute system-time command (PowerShell `Get-Date` on Windows, `date` on macOS/Linux)
- Lock the timestamp for the session
- **Gate 0.5:** Real system time captured (year ≥ current year)

### Phase 0 — Persona Validation (cannot skip if a persona is configured)

- If a persona slash command was used (e.g. `/<persona-name>`), confirm the agent's voice is active
- If no persona is configured, this gate auto-passes
- **Gate 0.1:** Persona confirmed (if configured) — first-person + project tone in normal speech

### Phase 1 — Environment Check

Phase 1 records platform + toolchain state for the rest of the pipeline. The user's verbatim policy on env-scan responsibilities (binding):

> Additionally, during the env scanning tidbits of the .claude files, commands should be ran to check that git is installed, if it is installed, we should check if the project is a git repository, and if it is not a git repo, we need to setup and follow that git flow to ensure we have proper versioning and control of the changes between the states of the project, as well as checking to ensure we know what operating system work is being done on, weather that be linux (and a specific distro + version of the distro), or windows (and what version of windows, and what type, ie home, pro, workstation, ext.), for full context of the availabiltiy of commands, services, and weather work is restrained to bash or batch / powershell. Windows will be running through a git bash terminal, linux will have a full bash shell, but in windows powershell and CMD are both invokable through tooling.

Five sub-checks run in this phase:

1. **Working directory** — confirm project root via `pwd` (Linux/macOS/Git Bash) or `cd` with no args (CMD) or `Get-Location` (PowerShell)
2. **`docs/ARCHITECTURE.md` presence** — feeds mode routing (FIRST_SCAN if missing, WORK_MODE if present)
3. **OS + version + edition detection** — full context for command availability:
   - Linux: `cat /etc/os-release` (records `NAME`, `VERSION_ID`, `PRETTY_NAME`) + `uname -r` for kernel
   - Windows (Git Bash, PowerShell, or CMD): `powershell -Command "Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, WindowsEditionId, OsBuildNumber"` — captures edition (Home / Pro / Pro for Workstations / Enterprise / Education / etc.) and build number
   - macOS: `sw_vers` (records `ProductName`, `ProductVersion`, `BuildVersion`)
4. **Shell context detection** — determines which command syntax is available downstream:
   - `$MSYSTEM` set (e.g. `MINGW64`) → **Git Bash on Windows**: bash subset, no `apt`/`yum`, can call `powershell.exe` and `cmd.exe` via tooling
   - `$SHELL` contains `bash` AND no `$MSYSTEM` → **native Linux/macOS bash**: full POSIX toolchain
   - `$PSModulePath` set with no `$MSYSTEM` → **native PowerShell**
   - else → **CMD or unknown** — fall back to most-portable commands
5. **Git toolchain + repo state**:
   - `command -v git >/dev/null 2>&1` → `git installed: YES/NO`
   - if installed: `git rev-parse --is-inside-work-tree 2>/dev/null` → `repo: YES/NO`
   - if a repo: `git rev-parse --abbrev-ref HEAD` → current branch (feeds PRE-EDIT BRANCH HOOK)
   - if a repo: `git remote -v` → remote present YES/NO + remote URL(s)
   - if a repo: `git branch --list develop main master` → which protected branches exist

6. **Git Flow opt-in marker** (`.claude/project-config.json`):
   - If file exists AND `git_flow.enabled` is set → honor recorded decision (true = LAW applies, false = LAW skipped for this project, hooks bypassed)
   - If file missing OR `git_flow.enabled` unset AND git is installed → **prompt user for confirmation** (see flow below)
   - If git is not installed → implicitly `git_flow.enabled = false`, skip the prompt

   **Confirmation prompt (asked once per project, then persisted):**

   ```
   ╔══════════════════════════════════════════════════════════════════════╗
   ║  GIT FLOW OPT-IN — first-run confirmation                            ║
   ╠══════════════════════════════════════════════════════════════════════╣
   ║  Project: <PROJECT_DIR>                                              ║
   ║  Git installed: YES                                                  ║
   ║  Git repo: <YES|NO>                                                  ║
   ║  Current branch (if repo): <branch>                                  ║
   ║                                                                      ║
   ║  Should this project use Git Flow branch discipline?                 ║
   ║  (main = clean master, develop = in-dev, feature/* = work,           ║
   ║   PR review at every merge, no commits to main/develop directly)     ║
   ║                                                                      ║
   ║  [Y] Yes — apply the LAW. Hooks fire on every edit/push/merge.       ║
   ║  [N] No  — opt this project out. Hooks skipped for this repo.        ║
   ║  [D] Defer — don't ask now, ask again next /workflow run.            ║
   ║                                                                      ║
   ║  Choice [Y/N/D]: _                                                   ║
   ╚══════════════════════════════════════════════════════════════════════╝
   ```

   **On response:**
   - **Y** → write `.claude/project-config.json` with `{"git_flow": {"enabled": true, "confirmed_at": "<ISO-8601>", "main_branch": "main", "develop_branch": "develop"}}`. Then if NOT a repo, ask SECOND confirmation: "Scaffold Git Flow now? (`git init` + `main` + `develop` + `.gitignore` stub) [Y/n]" — only run write commands on explicit Y. If repo exists but no `develop` branch, ask: "Create `develop` from current `main` and push to origin (if remote exists)? [Y/n]" — only run on Y.
   - **N** → write `.claude/project-config.json` with `{"git_flow": {"enabled": false, "confirmed_at": "<ISO-8601>"}}`. Skip all Git Flow hooks for this project until the marker is changed.
   - **D** → no marker written. Phase 1 records `git_flow_decision: deferred`. The prompt fires again on next `/workflow` run.

   **Marker file schema** (`.claude/project-config.json`):
   ```json
   {
     "git_flow": {
       "enabled": true,
       "confirmed_at": "2026-05-04T14:25:30Z",
       "main_branch": "main",
       "develop_branch": "develop",
       "custom_protected_branches": []
     }
   }
   ```

   The marker file is project-level config and SHOULD be tracked in git once a repo exists (it represents a team decision, not personal preference).

- **Gate 1.1:** Mode determination (FIRST_SCAN / WORK_MODE / RESCAN) AND env state recorded for the session (OS + edition, shell context, git installed/repo/branch/remote, git_flow opt-in state from marker file)

### Phase 2 — Codebase Scan (first run only)

- File system scan (glob `**/*`)
- Dependency detection (`package.json`, `requirements.txt`, `Cargo.toml`, `go.mod`, etc.)
- Config discovery (`.env`, build tools)
- **Gates 2.1, 2.2:** Scan results valid

### Phase 3 — Analysis & Generation

- Pattern recognition, structure mapping
- Generate `docs/ARCHITECTURE.md`, `docs/SKILL_TREE.md`, `docs/TODO.md`, `docs/ROADMAP.md`, `docs/FINALIZED.md`
- **Gates 3.1, 3.2:** All docs valid, no placeholders

### Phase 4 — Work Mode

- Read ALL existing workflow docs (TODO/ARCHITECTURE/SKILL_TREE/ROADMAP/FINALIZED) before any work
- Pick up tasks from `docs/TODO.md`
- Execute with pre/post-edit hooks
- **Gate 4.1:** Work mode ready

### Phase 5 — Finalization

- Update `docs/FINALIZED.md` with completed tasks (verbatim)
- Clean `docs/TODO.md` of completed entries (status flip + move, never delete description)
- **Gate 5.1:** Archive valid, TODO clean

---

## WORKFLOW FILES (`docs/` folder)

| File | Purpose |
|------|---------|
| `docs/ARCHITECTURE.md` | Codebase structure, patterns, dependencies, system documentation |
| `docs/SKILL_TREE.md` | Capabilities by domain / complexity / priority |
| `docs/TODO.md` | **ACTIVE tasks ONLY** — pending / in-progress work |
| `docs/ROADMAP.md` | Milestones, phases, current status |
| `docs/FINALIZED.md` | **PERMANENT ARCHIVE** — every completed task with full description |
| `docs/NOW.md` | Current session snapshot (optional) |

When updating these files: write out ACTUAL system changes — how things work now, what was added, what changed architecturally. NOT just bumping numbers or adding counts.

All files read in 800-line chunks. Full file must be read before any edit.

---

## TODO.md / FINALIZED.md TASK FLOW

```
┌─────────────────────────────────────────────────────────────┐
│ 1. BEFORE WORK: Add task to TODO.md                         │
│    - Task must exist in TODO.md BEFORE any work begins      │
│    - Mark status as "in_progress"                           │
│    - User's verbatim words in the description (LAW #0)      │
├─────────────────────────────────────────────────────────────┤
│ 2. DO THE WORK                                              │
│    - Read files (800-line chunks)                           │
│    - Make changes                                           │
│    - Verify success                                         │
├─────────────────────────────────────────────────────────────┤
│ 3. AFTER WORK: Move to FINALIZED.md                         │
│    - Copy completed task to FINALIZED.md (with details)     │
│    - Verify FINALIZED.md write succeeded                    │
│    - THEN remove from TODO.md                               │
│    - NEVER delete from FINALIZED.md                         │
└─────────────────────────────────────────────────────────────┘
```

### TODO.md rules

- Only unfinished tasks live in TODO.md
- Tasks have status: `pending` or `in_progress`
- When completed → MOVE to FINALIZED.md
- Never delete tasks — always move them
- **Never rewrite TODO from scratch** — edit in place, change status only
- **Never delete task descriptions** — keep the user's verbatim words permanently

### FINALIZED.md rules

- Permanent archive of all completed work
- NEVER delete entries — only APPEND
- Include: task, date, files modified, details, closure notes
- Provides full history of every session

### PRE-WORK HOOK

```
[PRE-WORK HOOK — ATTEMPT 1]
Task: [DESCRIPTION]
TODO.md entry exists: YES/NO (MUST be YES)
Verbatim user quote: YES/NO (required if from user)
Status: pending → in_progress
Gate: PASS/FAIL
```

### POST-WORK HOOK

```
[POST-WORK HOOK — ATTEMPT 1]
Task: [DESCRIPTION]
Completed: YES
FINALIZED.md updated: YES/NO (MUST be YES)
TODO.md cleaned: YES/NO (MUST be YES)
Gate: PASS/FAIL
```

---

## FILE EDIT PROTOCOL

### Before editing ANY file

```
[PRE-EDIT HOOK — ATTEMPT 1]
File: [PATH]
Full file read: YES/NO (MUST be YES)
Lines in file: [NUMBER]
Read method: SINGLE (≤800) / CHUNKED (>800)
Reason for edit: [EXPLANATION]
Status: PASS/FAIL
```

### Before editing ANY git-tracked file (BRANCH DISCIPLINE)

Per `CONSTRAINTS.md §GIT FLOW`, work happens ONLY in `feature/*`, `hotfix/*`, or `release/*` branches — never directly in `main`, `master`, `develop`, `prod`, `production`, or unsuffixed `release`. This hook fires alongside the standard PRE-EDIT HOOK when ALL of the following are true (per Phase 1 Gate 1.1):

1. The project is a git repo, AND
2. `.claude/project-config.json` has `git_flow.enabled: true` (or marker is present and the user confirmed Git Flow opt-in)

If `git_flow.enabled: false` (project opted out) or marker file is missing (decision deferred), the hook is skipped and edits proceed without branch checks.

```
[PRE-EDIT BRANCH HOOK — ATTEMPT 1]
Git repo: YES/NO (skip hook if NO)
Git Flow opt-in: YES/NO/DEFERRED (skip hook if NO or DEFERRED — marker file decides)
Current branch: $(git rev-parse --abbrev-ref HEAD)
Branch type: feature/* | hotfix/* | release/* | main | master | develop | prod | production | other
Branch is work-eligible: YES (feature/hotfix/release/other-non-protected) / NO (main/master/develop/prod/production)
Status: PASS/FAIL
```

**FAIL conditions:** Git Flow opt-in = YES AND current branch is `main`, `master`, `develop`, `prod`, `production`, or unsuffixed `release`.

**ON FAIL → ATTEMPT 2:**
```
[PRE-EDIT BRANCH HOOK — ATTEMPT 2]
Remediation: stash uncommitted work → checkout develop → branch feature/<descriptor> → pop stash
Confirm with user before running git commands (write actions require confirmation)
Status: PASS/FAIL
```

**ON FAIL×2 → BLOCKED:** edits cannot proceed until on a work-eligible branch. Full recovery procedure in `CONSTRAINTS.md §GIT FLOW Failure recovery`.

### After editing ANY file

```
[POST-EDIT HOOK — ATTEMPT 1]
File: [PATH]
Edit successful: YES/NO
Lines after edit: [NUMBER]
Status: PASS/FAIL
```

---

## HOOK FAILURE PROTOCOL

When ANY hook fails twice:

```
[HOOK FAILURE — BLOCKED]
Phase: [WHICH PHASE]
Gate: [WHICH GATE]
Attempt 1: FAIL — [REASON]
Attempt 2: FAIL — [REASON]
Status: CANNOT PROCEED
Required action: [WHAT TO DO]
Workflow: HALTED
```

Recovery: fix the issue, re-run the validation, only proceed when PASS.

---

## AGENT FILES REFERENCE

Agents live in `.claude/agents/`. Read on demand when a slash command requires them.

| Agent | Purpose |
|-------|---------|
| `timestamp.md` | **FIRST** — gets real system time for accurate timestamps / searches |
| `orchestrator.md` | Coordinates all phases with hooks |
| `scanner.md` | Scans codebase with validation |
| `architect.md` | Analyzes architecture with hooks |
| `planner.md` | Plans tasks with hierarchy validation |
| `documenter.md` | Generates docs with line limits |
| `coder.md` | Code-handling rules (project-agnostic) |
| `persona-template.md` | Fill-in template for project-specific persona |
| `hooks.md` | Complete hook system reference |

---

## SLASH COMMANDS REFERENCE

Commands live in `.claude/commands/`. Read when the command fires.

| Command | File | Purpose |
|---------|------|---------|
| `/workflow` | `workflow.md` | Run this pipeline |
| `/super-review` | `super-review.md` | **INTERNAL** — ruthless senior-engineer code review of the current branch / files / diff. Treats every line as if it came from a fast LLM and reviews accordingly. Output is severity-tagged ISSUES FOUND (Critical / High / Medium / Low / Nitpick) plus a prioritized FINAL FIX & IMPROVEMENT PLAN. Optional `$ARGUMENTS` narrows the scope to a stated intent; with no arguments, defaults to a full architectural / security / performance / maintainability / clean-code sweep. Internal dev usage only — never wired into any public-facing doc, README, or HTML. |

If your project ships a custom persona slash command (e.g. `/<persona-name>`), it goes here too with a pointer to its activation protocol file.

---

## RESCAN MODE

User must explicitly say "rescan" or "scan again":

```
[RESCAN TRIGGERED]
Reason: User requested full rescan
Existing files: WILL BE OVERWRITTEN
Proceeding to: PHASE 2
```

---

## ADDING NEW PHASES OR HOOKS

If your project needs a phase beyond 0–5 (e.g. a security audit phase, a performance baseline phase, a deployment-prep phase), add it here with:

1. **Phase number** (e.g. `Phase 6 — Security Audit`)
2. **Trigger condition** (always vs only on certain commands)
3. **Pre-hook** with validation gate
4. **Execution steps**
5. **Post-hook** with success criteria
6. **Gate** identifier

Then update the pipeline diagram + the `/workflow` command file to include the new phase.

---

## YOLO MODE — Lead-dev autonomy overlay

YOLO mode is a **behavioral overlay** on top of base Unity (or whichever manifestation is active). It flips the default decision posture from "ask, then act" to "act, verify, report." Activated by the `/yolo` slash command, deactivated by `/sober`, an explicit mid-task user interrupt, or a bash-safety hook firing.

### Architectural placement

YOLO is an **overlay**, not a layer. It modifies Unity's behavior without replacing any existing layer:

```
policy layer       → CONSTRAINTS.md (LAWs)             ← UNCHANGED. NO-TESTS gets a YOLO override subsection.
mechanics layer    → WORKFLOW.md, agents/*.md          ← UNCHANGED.
memory layer       → memory-templates/*.md             ← gains feedback_yolo_mode.md
persona layer      → ImHanddicapped.txt + commands/*   ← UNCHANGED. YOLO overlays whichever persona is active.
harness layer      → settings.local.json hooks         ← UNCHANGED — hooks just expose YOLO state in env JSON
overlay (mode)     → .claude/.yolo-mode marker         ← NEW. Machine-local state (gitignore once repo exists).
```

### Activation marker

`.claude/.yolo-mode` is the source of truth for whether YOLO is on. Created by `/yolo`, deleted by `/sober` or auto-triggered stop conditions. Hooks (`session-start-env-dump`, `user-prompt-state-refresh`) read the marker on every fire and surface the state as `yolo_mode: ENABLED|DISABLED` in their context output.

Marker file format:

```
yolo_mode_enabled=true
activated_at=2026-05-04T15:30:00Z
active_persona=unity
```

(Plain key=value lines so both bash and node hooks can parse with minimal logic.)

### What YOLO bypasses

| Pattern | Default | YOLO |
|---------|---------|------|
| "Want me to proceed?" | Ask user, wait | Proceed; document the choice in FINALIZED |
| "Should I update the doc too?" | Ask, then do | Just do, document it |
| Multi-step approval ("opt in? then scaffold? then push?") | Step-by-step | Single autonomous decision per project context |
| Minor design call (variable name, file location, style) | Ask | Lead-dev judgment, document |
| Trailing "want me to wire X next?" question | Default pattern | Skipped — Unity ships the next action and reports |

### What YOLO does NOT bypass

These stay no matter what:

- **LAW #0 verbatim words** — user's exact sentence still goes verbatim into TODO/FINALIZED/docs
- **800-line read before edit** — non-negotiable
- **TODO/FINALIZED ceremony** — Unity tracks her own work autonomously; ledger stays complete
- **Docs-before-push atomic commits** — code + every affected doc still ship together
- **The 3 bash-safety hooks** — project-root delete / system-path delete / sudo still BLOCK
- **Per-project Git Flow opt-in** — still honored
- **Branch discipline when Git Flow opt-in is ENABLED** — Unity auto-branches into `feature/<descriptor>` if on a protected branch (no asking — just branches and proceeds)
- **Persona** — Unity stays Unity (or whichever manifestation is active)
- **Memory layer auto-sync** — PostToolUse hook still fires
- **NO-TESTS LAW** — still default. Tests only when YOLO override criteria met (see `CONSTRAINTS.md §NO TESTS POLICY §YOLO mode override`)

### User test plan — REQUIRED on every YOLO task

Every task Unity completes in YOLO mode includes:

1. **Unity's own verification** — what she ran, what output she read, what behavior she confirmed
2. **A user-facing test plan** — non-negotiable deliverable

Format (also documented in `.claude/commands/yolo.md`):

```markdown
## Verification Unity completed

- [bullets — commands run, output read, behavior observed, edge cases considered]

## Your test plan

**What to test:** [1–2 line scope]

**How to test:**
1. [concrete step + exact command if applicable]
2. [...]

**Expected results:**
- [what success looks like — observable output, behavior, file state]

**If it fails:**
- [common failure modes + what to check]

**(Optional) Tests Unity wrote:** [path(s) + how to run, only if Unity exercised the YOLO testing override]
```

The test plan goes in the chat response AND gets cross-referenced from the FINALIZED.md entry.

### Stop conditions (auto-deactivate YOLO)

1. **`/sober` slash command** — explicit user deactivation
2. **Mid-task user interrupt** — "stop", "wait", "don't", "hold on", "pause", "halt" appearing as a clear directive (not incidental usage). Unity stops in-flight work, deactivates YOLO, confirms.
3. **Bash-safety hook fires** — pre-tool-bash-safety.cjs exit-2 auto-deactivates because the user is now in the loop on a destructive op anyway. Mode does NOT auto-reactivate — user has to `/yolo` again.
4. **Persona switch** — `/unity` / `/girlfriend` / etc. preserves YOLO if it was on (overlay, not persona). `/sober` is the canonical reset.

### Hook integration

- **`session-start-env-dump.{js,sh}`** — reads `.claude/.yolo-mode`, adds `yolo_mode: { enabled: true|false, activated_at: "...", active_persona: "..." }` block to the env JSON envelope
- **`user-prompt-state-refresh.{js,sh}`** — adds `**YOLO mode:** ENABLED|DISABLED` line to the state-refresh injection on every prompt
- **No new hooks added** — the existing harness layer's six hooks already cover everything; YOLO is mode-state on top of the same hook scripts

### Cross-references

- Slash commands: `.claude/commands/yolo.md`, `.claude/commands/sober.md`
- LAW override: `.claude/CONSTRAINTS.md §NO TESTS POLICY §YOLO mode override`
- Persistent memory: `.claude/memory-templates/feedback_yolo_mode.md`
- CLAUDE.md QUICK REFERENCE + mode table for at-a-glance lookup

---

## HARNESS LAYER — Claude Code settings.json hooks

The harness layer is `.claude/settings.local.json`'s `hooks` block plus the scripts under `.claude/hooks/`. It sits **on top of** everything else (LAWs, mechanics, persona, memory) — every existing rule, ceremony, gate, and read-before-edit discipline still applies. Hooks are pure enhancements that standardize execution across the team's machines (Linux / Git Bash on Windows / native PowerShell).

When `.claude/CLAUDE.md` / `WORKFLOW.md` / `CONSTRAINTS.md` / hooks disagree: **CONSTRAINTS.md wins** (LAWs are source of truth). Hooks are mechanics, not policy.

### Architectural placement

```
policy layer       → CONSTRAINTS.md (LAWs)
mechanics layer    → WORKFLOW.md, commands/workflow.md, agents/*.md
memory layer       → memory-templates/*.md (persistent feedback across sessions)
persona layer      → ImHanddicapped.txt + commands/unity*.md + manifestations
harness layer      → settings.local.json hooks + .claude/hooks/*.{cjs,sh}  ← THIS SECTION
bundled tools      → .claude/bin/* (atree fast scanner; future: more binary tools)
cross-platform     → start.sh + start.bat + Option A node primary + Option B bash fallback
```

### The five hooks (six events — Continuity bundle covers two)

| # | Hook event | Matcher | Script | What it does | Blocks? |
|---|------------|---------|--------|--------------|---------|
| 1 | `SessionStart` | `startup\|resume\|clear\|compact` | `session-start-env-dump.cjs` | Outputs project state JSON (OS, shell, git, opt-in marker, TODO summary, FINALIZED last entry, memory drift, persona) on stdout for context injection. Writes `.claude/.session-env.json` for downstream hooks. | No (exit 0) |
| 2 | `UserPromptSubmit` | (none) | `user-prompt-state-refresh.cjs` | Compact between-turn recap on stdout — current branch, opt-in state, in-progress TODO count + titles, branch-discipline note if on protected branch. | No (exit 0) |
| 3 | `PostToolUse` | `Edit\|Write\|MultiEdit` | `post-tool-memory-sync.cjs` | When a file in `.claude/memory-templates/` is edited, auto-`cp` to appdata memory folder. New memory takes effect immediately, no manual sync. | No (exit 0) |
| 4a | `PreCompact` | (none) | `pre-compact-snapshot.cjs` | Writes `.claude/.session-state.md` with TODO + git state + compaction trigger so post-compact Unity can pick up cleanly. | No (exit 0) |
| 4b | `Stop` | (none) | `stop-session-writeup.cjs` | Updates `.claude/.last-session.md` with branch + TODO + last-FINALIZED on every turn boundary. Read by next session's SessionStart. | No (exit 0) |
| 5 | `PreToolUse` | `Bash` | `pre-tool-bash-safety.cjs` | The ONLY blocking hook. Catches three classes: project-root deletion, system-path deletion, privileged commands (sudo/su/doas/runas/RunAs). Routes each to user with paste-ready command. | YES (exit 2 on match) |

### Option A primary + Option B fallback

Each hook ships as both `.cjs` and `.sh`:

- **`.cjs`** — Node.js, default. `claude` itself ships through npm so node is on every dev machine. Clean cross-platform path handling, JSON parsing, regex. The `.cjs` extension is mandatory (not `.js`): it forces Node to treat the script as CommonJS regardless of the host project's `package.json` `"type"` field, so the harness works inside ESM projects too without an ESM-vs-CJS rewrite.
- **`.sh`** — POSIX-portable bash sibling. Functional parity (best-effort). Use this if a team member's machine genuinely doesn't have node — swap the `command` field in `settings.local.json` from `node "..."` to `bash "..."`.
- **`.ps1`** — skipped in v1. Native PowerShell is rare in the team's setup (Windows users launch through `start.bat` → Git Bash). Add later if needed.

### Cross-platform invocation

The `command` field in `settings.local.json` uses `$CLAUDE_PROJECT_DIR` (Claude Code substitutes the project root path automatically) — works identically on Linux bash, Git Bash on Windows, and native PowerShell.

### Side effects (files the harness writes)

| File | Written by | Read by | Lifecycle |
|------|-----------|---------|-----------|
| `.claude/.session-env.json` | session-start-env-dump | user-prompt-state-refresh (cache lookup) | overwritten each session start |
| `.claude/.session-state.md` | pre-compact-snapshot | (manual read on resume) | overwritten on each compaction |
| `.claude/.last-session.md` | stop-session-writeup | session-start-env-dump (next session) | overwritten on every turn boundary |

These files should be added to `.gitignore` once a project becomes a git repo — they're machine-local state, not team-shared config. The `project-config.json` (Git Flow opt-in marker from §GIT FLOW) IS team-shared and gets tracked.

### What hooks do NOT replace

- The 800-line read LAW — still self-enforced by the model
- The verbatim quote LAW (LAW #0) — still self-enforced
- The TODO/FINALIZED ceremony — still self-enforced
- The persona system — hooks just inject a reminder; persona activation still flows through slash commands
- The Git Flow LAW's pre-edit branch hook — hooks just inject branch awareness as context; the discipline is still model-honored unless we later add a blocking PreToolUse Edit/Write check (intentionally NOT in v1 — would be too restrictive given the team's `--dangerously-skip-permissions` posture)

The harness layer is the **execution-standardization floor**, not a replacement for the discipline layers above it.

### Adding new hooks

To add a new hook to the harness layer:

1. Write `.claude/hooks/<name>.cjs` (primary) — receives stdin JSON if applicable, outputs stdout for context injection or stderr for transcript-only logging
2. Write `.claude/hooks/<name>.sh` (fallback) — bash sibling
3. Add an entry to `settings.local.json` under the appropriate event:
   ```json
   "EventName": [
     { "matcher": "regex", "hooks": [{ "type": "command", "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/<name>.cjs\"" }] }
   ]
   ```
4. Document it in this section's table and any relevant cross-references in `CONSTRAINTS.md`
5. Smoke test: run the script locally with a fake stdin payload to verify exit codes and output

### Disabling a hook

To disable a single hook, remove its entry from `settings.local.json`. The script files stay on disk and can be re-enabled by re-adding the settings entry. Don't delete the scripts — they're the team-standard library.

To disable the entire harness layer for a specific machine, set `"hooks": {}` in a user-level `~/.claude/settings.json` (overrides project-level for that user only).

---

## BUNDLED TOOLS — `.claude/bin/`

Native binaries that ship with the `.claude/` template so every team member has the same fast tooling without a per-machine install step. Tools live in `.claude/bin/`. Each tool has a documented fallback ladder so a missing/broken binary degrades cleanly to system equivalents — never a hard failure.

### Inventory

| Binary | Platforms | Purpose | Used by | Fallback ladder |
|--------|-----------|---------|---------|-----------------|
| `atree` | Linux ELF (x86_64) | Parallel filesystem scanner + A\* file pathfinder. Map mode (`--tree --no-limit -f`) is the primary use case (fast tree dump); A\* mode (`-s` / `-g`) is the surgical-file-locator bonus. JSON output (`--json`) for tooling, DOT (`--dot`) for diagrams, bundled JSON Schema (`--print-schema`) for parser contracts. ~2.6× faster than `tree` on `/usr`-size trees. | `agents/scanner.md` Task 1 (File System Scan) | atree → tree → find → Glob |
| `atree.exe` | Windows (x86_64) | Same binary for Git-Bash on Windows | same | same |

macOS not bundled — the team doesn't run macOS. If that changes, build a darwin universal2 binary and drop it at `.claude/bin/atree-darwin`, then update scanner.md detection logic.

### Detection pattern (used by scanner.md and any future tool consumer)

```bash
# Linux / native bash
[ -x .claude/bin/atree ] && ATREE=".claude/bin/atree"

# Windows Git-Bash
[ -x .claude/bin/atree.exe ] && ATREE=".claude/bin/atree.exe"

# Cross-platform one-liner used by scanner agent:
if [ -x .claude/bin/atree ]; then
    ATREE=".claude/bin/atree"
elif [ -x .claude/bin/atree.exe ]; then
    ATREE=".claude/bin/atree.exe"
else
    ATREE=""   # signals fallback ladder
fi
```

### Fallback ladder (canonical)

Every consumer of a bundled tool MUST implement a fallback chain so a missing binary degrades to a system equivalent rather than blocking the workflow. For the scanner this is:

```
.claude/bin/atree[.exe]  →  tree -a -J  →  find . [excludes]  →  Claude Glob tool
```

Drop tier on:
- Binary not found / not executable
- Non-zero exit
- Empty / malformed output
- Schema-version bump consumer can't handle (atree only)

Always record `engine_used` in scan output so downstream agents know which tier ran.

### Adding a new bundled tool

1. Drop the binary at `.claude/bin/<name>` (linux) and `.claude/bin/<name>.exe` (windows)
2. Set executable bit: `chmod +x .claude/bin/<name>*`
3. Add a row to the inventory table above with platforms / purpose / fallback ladder
4. Wire it into the appropriate consumer agent (`agents/*.md`)
5. Add a memory-templates feedback file documenting the tool's role and the fallback ladder
6. Test the fallback ladder works by temporarily renaming the binary

### What bundled tools are NOT

- Not a replacement for the harness hooks — hooks standardize execution; tools standardize capability
- Not auto-installed system-wide — they live inside `.claude/bin/` and are referenced by relative path; no PATH manipulation
- Not blocking — every tool has a documented fallback to standard system commands

---

*Workflow template — strict validation, real results.*
