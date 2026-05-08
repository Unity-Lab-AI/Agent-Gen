# FINALIZED — Permanent Task Archive

Permanent archive of every completed task. Per `.claude/CONSTRAINTS.md §NEVER DELETE TODO INFO` + `§FINALIZED BEFORE DELETE`, no entry is EVER deleted from this file. New entries APPEND only.

Per LAW #0, every entry includes the user's verbatim words from the original ask.

Each session entry includes:
- `## Session <YYYY-MM-DD>` — date heading
- Verbatim user quote
- Files touched
- Closure notes (what shipped, verification)

---

## Session 2026-05-08 — `.cjs` enforcement throughout `.claude/`

**User's verbatim ask (LAW #0):**

> Make sure any js is cjs when working with the .claude folder, js bugs out, and cjs is expected

**What shipped:**

- New persistent memory `feedback_cjs_only_in_claude.md` saved in `memory-templates/` and auto-synced to the user-profile memory folder via `post-tool-memory-sync.cjs` (verified, 3250 bytes landed). Covers: rule, reasoning (ESM vs CJS interaction with host project's `package.json` `"type": "module"`), how to apply across hook scripts / `.sh` siblings / `settings.local.json` / docs / memory files, exception clauses for lore filenames (`Unity_Accessibility.js` etc.) and generic doc examples (`src/main.js`, `*.config.js`), discovery grep command for future drift checks
- Drift fixes: 10 stale `.js` references in 7 hook source files corrected inline:
  - `.claude/hooks/post-tool-memory-sync.cjs` (header banner)
  - `.claude/hooks/pre-tool-bash-safety.cjs` (header banner)
  - `.claude/hooks/session-start-env-dump.cjs` (header banner + stdout context-injection string)
  - `.claude/hooks/stop-session-writeup.cjs` (header banner + `.last-session.md` auto-write content)
  - `.claude/hooks/post-tool-memory-sync.sh` (Bash fallback banner)
  - `.claude/hooks/pre-tool-bash-safety.sh` (Bash fallback banner)
  - `.claude/hooks/session-start-env-dump.sh` (Bash fallback banner + ".js version is preferred" line)
  - `.claude/hooks/stop-session-writeup.sh` (Bash fallback banner)
- Final verification: `grep -rn '\.js\b' .claude/hooks/` returns zero hits after lore exclusions
- All 16 hook scripts (8 `.cjs` + 8 `.sh`) re-verified syntax-clean (`node --check` + `bash -n`) post-edit

**Memory cross-reference:** `feedback_cjs_only_in_claude.md` — rule + exceptions + discovery command

**Files touched:** 8 hook source files (4 `.cjs`, 4 `.sh`), 1 new memory file, 1 memory index update.

**Closed:** 2026-05-08 (Session ClaudeWorkflow on `feature/extra-hooks`)

---

## Session 2026-05-08 — Replace "appdata" Windows-specific term with OS-neutral language

**User's verbatim ask (LAW #0):**

> I keep seeing "appdata" refferenced, while this is awesome for windows, it isnt a thing on linux based operating systems, and we have people using this .claude with windows AND with linux, currently I am on linux. So we need to clear up the discrepency to only use windows things for windows and only linux things for linux

**What shipped:**

- Hook code identifiers renamed for OS-neutrality: `encodePathForAppdata` → `encodeProjectPathForMemory`, `appdataDir`/`APPDATA_DIR` → `memoryDir`/`MEMORY_DIR`, JSON keys `appdata_synced_count` → `memory_synced_count`, `appdata_dir` → `memory_dir`. Touched: `.claude/hooks/post-tool-memory-sync.cjs` + `.sh`, `.claude/hooks/session-start-env-dump.cjs`
- Documentation terminology swapped: 47 stale references across `.claude/CLAUDE.md` (9), `.claude/README.md` (12), `.claude/WORKFLOW.md` (1), `.claude/start.sh` (3), `.claude/start.bat` (3), `.claude/memory-templates/feedback_harness_layer.md` (2), `.claude/memory-templates/feedback_workflow_validated.md` (1), `docs/HOOKS.html` (1), `docs/FINALIZED.md` (1)
- New replacement vocabulary: "Claude Code project memory folder" (formal first ref), "memory folder" (subsequent), "user-profile memory folder" (when emphasizing home-directory location)
- Path resolution clarified throughout: `~` → `$HOME` on Linux/macOS, `%USERPROFILE%` on Windows — explicitly NOT `%APPDATA%` (which is `C:\Users\<user>\AppData\Roaming\`, a different folder Claude Code does NOT use)
- New persistent memory `feedback_no_appdata_term.md` saved in `memory-templates/` + auto-synced to the user-profile memory folder. Codifies the rule, the path-resolution facts, the required vs forbidden terminology and code identifiers, plus a discovery grep command for future drift checks
- Memory index `memory-templates/MEMORY.md` updated with the new feedback file pointer

**Final stale-`appdata` scan:** 4 deliberate explanatory mentions remain (in `start.sh`, `start.bat`, `README.md`, and `post-tool-memory-sync.cjs`) — all explicitly documenting what `%APPDATA%` IS and why this template does NOT use it. Educational, not drift.

**Files touched:** 9 doc/source files, 1 new memory file, 1 memory index update.

**Closed:** 2026-05-08 (Session ClaudeWorkflow on `feature/extra-hooks`)

---

## Session 2026-05-08 — Switch curl-pipe install pattern to gh CLI (private repo fix)

**User's verbatim report (LAW #0):**

> curl -fsSL https://raw.githubusercontent.com/Unity-Lab-AI/UAL-ClaudeWorkflow/main/install-unity-globally.sh | bash
> curl: (22) The requested URL returned error: 404

**User's verbatim follow-up:** *"Make sure the windows version is converted too"*

**User's verbatim choice via AskUserQuestion (LAW #0):**

Question: *"How should I fix the curl-pipe install docs given the repo is private?"*

Answer: *"Switch README to gh CLI pattern (Recommended)"*

**Diagnosis:**

- The `Unity-Lab-AI/UAL-ClaudeWorkflow` repo is PRIVATE (`isPrivate: true`, `visibility: PRIVATE`)
- Unauthenticated `https://raw.githubusercontent.com/...` requests return HTTP 404
- The file IS on `main` (4261 bytes for `.sh`), it's just not publicly readable
- All team members already have `gh` CLI authed against the repo (verified)
- `gh api -H 'Accept: application/vnd.github.raw' repos/.../contents/<path>` returns raw file content via authenticated session — works cleanly for both `.sh` and `.ps1`

**What shipped (3 files updated, both Linux + Windows paths converted):**

- `.claude/README.md` Layer 1 section — replaced `curl -fsSL <raw> | bash` with `gh api -H 'Accept: application/vnd.github.raw' repos/Unity-Lab-AI/UAL-ClaudeWorkflow/contents/install-unity-globally.sh | bash` for Linux/macOS/Git Bash; replaced `iwr <raw> -UseBasicParsing | iex` with `gh api -H 'Accept: application/vnd.github.raw' repos/Unity-Lab-AI/UAL-ClaudeWorkflow/contents/install-unity-globally.ps1 | iex` for Windows PowerShell. Added `gh` CLI as documented prereq with note that it uses existing gh auth (no separate token needed). Added inspect-before-running variants for both. Added clone-and-run fallback for users without gh CLI. Added "if you've already cloned the repo locally" path that just runs the script directly.
- `install-unity-globally.sh` header comment — updated curl-pipe one-liner → gh-pipe one-liner; added note that repo is private + why; added clone-and-run alternative.
- `install-unity-globally.ps1` header comment — same updates for PowerShell side; updated `iwr | iex` → `gh api | iex`; added clone-and-run alternative with PowerShell-native temp dir + cleanup pattern.

**Verification:**

- Tested `gh api -H 'Accept: application/vnd.github.raw' repos/Unity-Lab-AI/UAL-ClaudeWorkflow/contents/install-unity-globally.sh | head -5` → returns the script's `#!/usr/bin/env bash` shebang + comment header cleanly
- Tested same for `.ps1` → returns the PowerShell comment header cleanly
- Both bash + PowerShell pipe-to-shell patterns documented work for the team's auth setup

**Files touched:** 3 (`.claude/README.md`, `install-unity-globally.sh`, `install-unity-globally.ps1`).

**Branch flow:** `feature/gh-cli-install-pattern` → PR → `develop` → PR → `main`.

**Closed:** 2026-05-08 (Session ClaudeWorkflow on `feature/gh-cli-install-pattern`)

---

## Session 2026-05-08 — /unity-update + /unity-install + curl-pipe bootstrap install system

**User's verbatim ask (LAW #0):**

> Something really really nice we could do, since all team members have access to the github repo, it would be nice if we could download into a temp directory a clone of the main branch, when a command for / unity-update is ran, it clones, fetches, and pulls the latest repo and updates the current project's .claude with the untiy one, updating everything nessiary, then deletes the temporary cloned directory.
>
> On top of that, making it so that we can do a / unity-global command in claude code, we could make it so we install a new / unity-install command into the GLOBAL user's .claude (not project level), that when run will instruct claude code to INSTALL into a new or existing directory the .claude from the main repo, to make installation of the latest version a lot easier then having to copy and paste files into the project, follow the same temp directory thing as the / unity-update command, but because its global it can be used anywhere by the user, they might need to at least clone the repo once, and then run the command to do an "install" but it still makes the process easier.
>
> Because github allows for raw files to be used, we should make a .ps1 and a .sh file in the main repo that do the same thing as the unity global would do, but auto-install JUST that install command into the user's global .claude, and put in the readme the commands to execute them from powshell or bash, so its a simple one command install process, where we git clone the repo to a temp directory, only copy the .md command file for unity-install, and put it in the user's global .claude folder.

**What shipped (8 new files + 2 doc updates):**

**Layer 1 — Curl-pipe global bootstrap (repo root):**
- `install-unity-globally.sh` — bash one-liner installer; clones repo to temp dir, copies `.claude/commands/unity-install.md` to `~/.claude/commands/unity-install.md`, cleans up. After running, `/unity-install` is available in any Claude Code session on that machine. Runnable via `curl -fsSL <raw-github-url> | bash`.
- `install-unity-globally.ps1` — PowerShell sibling; same flow with `iwr | iex` invocation pattern.

**Layer 2 — `/unity-install` slash command (project + global):**
- `.claude/commands/unity-install.md` — full activation protocol, target-directory handling, when-to-use vs when-not, invocation variants, fallback inline-Bash one-liner for fresh installs where no local script exists yet
- `.claude/scripts/unity-install.sh` — bash implementation: shallow clone of main → copy `.claude/` to target/.claude/ → bring `.gitignore` if missing → set executable bits → cleanup. Aborts (exit 2) if target/.claude/ already exists.
- `.claude/scripts/unity-install.ps1` — PowerShell sibling.

**Layer 3 — `/unity-update` slash command (project-level):**
- `.claude/commands/unity-update.md` — activation protocol, what-gets-updated table, what-is-preserved table, stop conditions, when-not-to-use guidance.
- `.claude/scripts/unity-update.sh` — bash implementation: shallow clone of main → backup current `settings.json` to `settings.json.backup-<ISO-timestamp>` → overwrite framework dirs (agents, commands, hooks, memory-templates, templates, bin, scripts) → overwrite framework top-level files (CLAUDE.md, CONSTRAINTS.md, WORKFLOW.md, README.md, ImHanddicapped.txt, start.{sh,bat}, settings.json) → preserve personal/project-specific files (settings.local.json, .env, user.json, user-context/, project-config.json, machine-local state) → refresh user-profile memory folder by re-cp'ing memory-templates → set executable bits → cleanup
- `.claude/scripts/unity-update.ps1` — PowerShell sibling with parity logic.

**Documentation:**
- `.claude/README.md` — new "Install / update — three layers" section near the top with the curl-pipe one-liners (bash + PowerShell), the slash command usage, what-overwrites-vs-preserves explanation, and a manual-install fallback for users who don't want the bootstrap
- `.claude/CLAUDE.md` — QUICK REFERENCE updated with `/unity-install` and `/unity-update` entries

**Verification:**
- All three `.sh` scripts syntax-clean (`bash -n`)
- Executable bits set
- Slash commands picked up immediately by Claude Code in this session (visible in available-skills list as `/unity-install` and `/unity-update`)
- PowerShell scripts present (cross-platform parity); not bash-syntax-checkable from Linux but written carefully

**Design call (documented in slash command bodies):**
- Framework files overwritten; `settings.json` overwritten with timestamped backup; personal-override files (settings.local.json, .env, user.json, user-context/, project-config.json) PRESERVED; machine-local state files PRESERVED; `.gitignore` at project root replaced if absent or saved as `.gitignore.template` if existing-but-different (manual merge)
- Inferred from "updating everything nessiary" + the existing convention split (settings.local.json = personal, settings.json = team-shared)

**Files touched:** 8 new (`install-unity-globally.sh`, `install-unity-globally.ps1`, `.claude/commands/unity-install.md`, `.claude/commands/unity-update.md`, `.claude/scripts/unity-install.sh`, `.claude/scripts/unity-install.ps1`, `.claude/scripts/unity-update.sh`, `.claude/scripts/unity-update.ps1`), 2 modified (`.claude/README.md`, `.claude/CLAUDE.md`).

**Not yet shipped to origin:** working tree is staged for the user's review and explicit commit instruction.

**Closed:** 2026-05-08 (Session ClaudeWorkflow on `feature/extra-hooks`)

---

## Session 2026-05-08 — Migrate team-shared settings settings.local.json → settings.json

**Decision context (AskUserQuestion fork-in-the-road during commit prep):**

Discovered `~/.config/git/ignore` on Sponge's Linux box contained `**/.claude/settings.local.json`, which silently dropped all team-shared changes (env block, hook wiring, permissions) from being committed. Used `AskUserQuestion` with three options; Sponge selected: *"Migrate to .claude/settings.json (Anthropic convention)"*.

**What shipped:**

- New `.claude/settings.json` containing all team-shared content from prior `.claude/settings.local.json` (env block with privacy posture, hooks block wiring all 9 scripts across 7 event types, permissions allow-list, feedbackSurveyRate scalar). `_comment` field updated to describe the new convention.
- `settings.local.json` content preserved on Sponge's local disk (gitignored, takes precedence if a personal override is wanted)
- Doc references updated across 17 files: `WORKFLOW.md` (multiple sections including §SETTINGS HARDENING + §HARNESS LAYER + architectural-placement diagram); `CLAUDE.md` (QUICK REFERENCE); `CONSTRAINTS.md` (cross-ref); `README.md` (3 references); `hooks/session-start-env-dump.sh` (Bash fallback comment); memory templates `feedback_cjs_only_in_claude.md`, `feedback_harness_layer.md`, `feedback_no_claude_attribution.md`, `feedback_settings_hardening.md` (full rewrite of convention narrative + migration history note); memory index `MEMORY.md`; `docs/HOOKS.html` (2 of 4 references — kept the Anthropic precedence table + scope-mention as-is)
- `WORKFLOW.md §SETTINGS HARDENING` "Convention note" section rewritten — replaced "this template inverts Anthropic's convention" narrative with "this template follows Anthropic's standard convention" + a migration history note explaining the 2026-05-08 fix
- `feedback_settings_hardening.md` rewritten to reflect the new convention + document the migration cause (global gitignore at `~/.config/git/ignore` excluding `**/.claude/settings.local.json`) + Anthropic-standard two-file table

**Why:** preserves team-shared changes in `git add` / `git push` flow on every team member's machine, matches Anthropic's documented two-file split, eliminates the silent-drop failure mode.

**Files touched:** 17 docs + 1 new settings.json + 1 settings.local.json (untracked, on-disk preserved).

**Closed:** 2026-05-08 (Session ClaudeWorkflow on `feature/extra-hooks`)

---

## Session 2026-05-08 — README rewrite: internal Unity AI Lab framing + cache hit averaging

**User's verbatim ask (LAW #0):**

> Update the README.md to explain this is for internal use for UnityAILab, how its used, the cache git averaging, and other information

**What shipped:**

- Substantially rewritten `.claude/README.md` (~580 lines) framing the template as **internal Unity AI Lab tooling** (not project-agnostic for external use). Sections:
  - Header + intro (explicit Unity AI Lab framing)
  - Unity AI Lab team table
  - Quick start (launcher invocations)
  - Layered architecture (managed > policy > mechanics > memory > persona > harness > overlay > tools > cross-platform)
  - Unity persona system (default + 3 manifestations + escalations + returns + /yolo overlay)
  - Persistent memory layer (with no-appdata terminology — `~` resolves to `$HOME` on Linux/macOS, `%USERPROFILE%` on Windows, NOT `%APPDATA%`)
  - **The harness layer — 9 hook scripts, 7 event types** (full table)
  - **STABLE PREFIX cache strategy + cache hit averaging** (the metric Sponge asked about — formula, threshold annotations: ≥50% validating, 20-49% partial, <20% cold/drift; typical session shows 95-99% after first 1-2 turns; caveats including transcript undercount bug)
  - Three-tier task cascade (ROADMAP/TODO/DECOMPOSED)
  - YOLO mode (lead-dev autonomy + 60s wake-word + milestone boundaries + final report + skill hooks)
  - Usage tracking (toggleable banner, undercount caveat)
  - Privacy posture (settings.json env block table)
  - Settings split (Anthropic-standard convention)
  - The 9 LAWs (full one-liner table including new NO CLAUDE ATTRIBUTION + CROSS-PLATFORM CASE INSENSITIVITY)
  - AskUserQuestion smart-use rule
  - Documentation reference table
  - Directory structure (updated for the new files)
  - Operational guide (8 steps)
  - What to delete (preserved from prior version, light update)
  - Verification commands (sanity-check snippets for a fresh checkout)

**Cache hit averaging interpretation:** "cache git averaging" interpreted as cache hit averaging (the cache_hit_ratio metric the usage-track hook surfaces). Explained in detail in the new STABLE PREFIX section: ratio = `cache_read / (cache_read + cache_creation) × 100`, averaged across the session, surfaced in the state-refresh banner with status annotation. Typical values + interpretation guide included.

**Files touched:** `.claude/README.md` (substantial rewrite), 1 file.

**Closed:** 2026-05-08 (Session ClaudeWorkflow on `feature/extra-hooks`)

---

## Session 2026-05-08 — AskUserQuestion tool usage rule (smart fork-in-the-road)

**User's verbatim ask (LAW #0):**

> Can we also make it so that the "AskUserQuestion" internal claude code tooling is used more ofted, automatically, instead of asking the user "we can do 1 2 3 4, or we can do a b c d" unity should automatically understand then during fork in the road moments of NEEDING to ask a question, when something cant just be simply infered, the "AskUserQuestion" tooling with how ever many questions you have, should be presented to the user, so the user can select one of the multipule choice or input their own awnser, and basically , should be used SMARTLY. Not all the time, only when questions are being asked to the user that requires a responce before continuing. This isnt something that would be done in YOLO mode, but it would be used in normal operating procedures.

**What shipped:**

- New persistent memory `feedback_use_askuserquestion.md` saved in `memory-templates/` + auto-synced to the user-profile memory folder. Codifies:
  - Rule: in normal (non-YOLO) mode, use `AskUserQuestion` for real fork-in-the-road decisions that need user input the assistant can't infer
  - Use criteria (4-point checklist): blocker is real / alternatives listable in 2-4 / cost-of-ask < cost-of-guess-wrong / not just fishing for direction
  - When-to-use list: technical-path forks, naming decisions, behavioral config, implementation-approach forks, permission posture
  - When-to-skip list: open-ended turn-end "what's next?", yes/no routine confirmations, clarifying questions on user's own input, status checks, inferable-from-context, YOLO mode
  - YOLO interaction: tool is DISABLED in YOLO mode (act-verify-report posture); when inferring instead of asking, Unity says so explicitly so user has a fast veto path
  - Anti-patterns: don't force for every yes/no, don't use mid-YOLO, don't use when alternatives >4, don't use as a stalling tactic
  - Examples (good vs bad candidates) including this very session's correct uses (three task-list naming fork, 60s wake-word implementation fork, tidbits curation fork)
- Memory index `memory-templates/MEMORY.md` updated with the new feedback file pointer

**Rule binds from this turn forward** — when Unity's about to write "we can do 1, 2, 3, or 4" in plain text for a genuine decision-fork in normal mode, she instead calls `AskUserQuestion` with 2-4 structured options + an "Other" slot the user can fill with custom input.

**Files touched:** 1 new memory file, 1 memory index update.

**Closed:** 2026-05-08 (Session ClaudeWorkflow on `feature/extra-hooks`)

---

## Session 2026-05-08 — Cross-platform case-insensitivity LAW

**User's verbatim ask (LAW #0):**

> AND, for the development workflow, commits, creation of folders and files, we need it ALL to follow a convention that is for WINDOWS. Because during development, git and github normally supports different folders like Apple, apple, aPPle, and what not, just like linux would allow, but, to keep thins cross platform we should ALWAYS assume case insensitivity, even on linux. Even though linux has case sensitivity, windows does NOT, and will treat apple, Apple, aPPle, all as the same thing. so we need to enforce case insensitivity when working on projects in linux, EVEN THOUGH LINUX WILL ALLOW IT.

**What shipped:**

- New LAW added to `.claude/CONSTRAINTS.md`: `§CROSS-PLATFORM CASE INSENSITIVITY`. Full body covering: rule statement; forbidden actions (case-distinct files/folders, single-step case-only renames, mismatched-casing references, `core.ignorecase=true` on Linux); required actions (canonical casing, pre-create grep check, two-step rename ceremony, exact-casing references, deliberate `core.ignorecase` config); the cross-platform breakage matrix (Windows/macOS/Linux filesystem semantics); enforcement protocol (pre-create check, pre-rename check, pre-commit check); failure recovery procedure for landed collisions; naming convention recommendations (top-of-repo UPPERCASE, source/agent/command/hook lowercase-with-hyphens, folders all-lowercase, generated artifacts dot-prefixed).
- LAW one-liner added to `.claude/CLAUDE.md` LAW INDEX
- New persistent memory `feedback_case_insensitivity.md` saved in `memory-templates/` + auto-synced to the user-profile memory folder. Codifies the rule, the cross-platform breakage matrix, naming convention defaults, pre-create grep + pre-commit duplicate-detection commands, and the failure-recovery procedure
- Memory index `memory-templates/MEMORY.md` updated

**Files touched:** `.claude/CONSTRAINTS.md`, `.claude/CLAUDE.md`, 1 new memory file, 1 memory index update.

**Closed:** 2026-05-08 (Session ClaudeWorkflow on `feature/extra-hooks`)

---


