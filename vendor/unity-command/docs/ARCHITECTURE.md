# ARCHITECTURE

> Unity AI Lab — `.claude/` workflow framework + Unity Command Discord-bot reference implementation, living in a single project repo so the workflow can dogfood itself against a real downstream consumer.
> Unity AI Lab — Gee, Red, Sponge, Mills

### Credits

- **Gee** — Founder. Lead architect, persona canon, vision.
- **Red** — Server infrastructure. Hosting, DevOps, deployment pipelines, monitoring, SSL/DNS, runtime ops.
- **Sponge** — Stack development + backend. Backend services, database, API design, persistence layer, infrastructure-of-the-app.
- **Mills** — Social + development + implementation. Community presence, feature implementation, cross-cutting dev work.

---

## Overview

This repo is the **Unity Command project** — the lab's working tree where the `.claude/` workflow framework is exercised against a real downstream consumer (``). Two distinct surfaces share the same root:

1. **`.claude/` — the workflow framework.** Persona system (Unity + manifestations), three-tier task ledger (ROADMAP → TODO → DECOMPOSED), persistent memory layer (auto-loaded by Claude Code each session), 10 Claude Code hook pairs (`.cjs` + `.sh`), bundled `atree` Rust binary for fast filesystem scans, idempotent install/update scripts, and 19 slash-commands now fully migrated to the modern skills format (`skills/<NAME>/SKILL.md` is the sole canonical surface; legacy `commands/` deleted 2026-05-20 in commits `aaf848d` + `f4c1d7e`). This is the same framework that ships from upstream `UAL-ClaudeWorkflow` and gets installed into every lab project via `/unity-install`.
2. **`` — Discord bot reference implementation.** Pollinations.ai-backed Discord bot with Flask Claude-Code → Unity bridge on `:5050`, optional web UI on `:5051`, MCP stdio server stub, admin-bridge auth for the four lab founders, Cloudflare-tunnel deployment automation, and full docs set (13 files, 4010 lines as of 2026-05-20).

The two surfaces aren't independent — V4 ships its own `.claude/` template subset (downstream of the outer one) so canonical-framework changes propagate into V4 via `/unity-update`. V4's inner `.claude/` is currently lagging behind the outer (no LAW system, no skills/, references `unity-coder.md` + `unity-persona.md` agents only) — sync is a follow-up task.

**Current branch context:** `feature/migrate-commands-to-skills` shipped the 19 slash-commands migration in this session (commits `aaf848d` rename + doc/hook/bootstrap updates, then `f4c1d7e` final `.bak` deletion). Branch is ready for PR review to `develop` per Git Flow. Per the project's `.claude/`-template push-scope rule, `.claude/` changes stay feature-scoped until Gee explicitly promotes them.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Workflow framework** | Markdown (commands, skills, agents, memory) + YAML frontmatter (skills only) |
| **Hooks** | Node.js `.cjs` (CommonJS — forced extension; `.js` would inherit ESM if a parent `package.json` declared `type: module`). Each hook has a `.sh` wrapper for portability. |
| **Fast scanner** | Rust — `atree` (`.claude/bin/atree` + `atree.exe`), v0.6.0-alpha, parallel tree-scan + A\* file pathfinder, JSON-output with bundled Draft-7 schema |
| **Install / update scripts** | `bash` (`.sh`) + PowerShell (`.ps1`), idempotent preserve-and-restore flow |
| **Unity Command bot — language** | Python 3.11+ |
| **Unity Command bot — framework** | `discord.py` (Discord gateway), `Flask` (Claude-Code bridge on :5050 + web UI on :5051), `requests` + `aiohttp` (Pollinations API) |
| **Unity Command bot — auth** | `bcrypt` (admin password hashing), `argon2-cffi` (alternate hashing path) |
| **Unity Command bot — deps locking** | `pip-compile --generate-hashes` → `requirements-locked.txt` (1023 lines, prod path); `requirements.in` source-of-truth |
| **V4 deployment** | `cloudflared` (Cloudflare Tunnel automation in `configure.py --setup-cloudflare-tunnel`), `systemd` (Linux service), Windows Service Control Manager |
| **Persistent memory** | Markdown files auto-loaded by Claude Code from `~/.claude/projects/<encoded-path>/memory/*.md` each session |
| **Statusline** | `.claude/statusline.sh` — bash script invoked by Claude Code regardless of host shell; reads sidecar caches for CPU/GPU/RAM |
| **Git workflow** | Git Flow opt-in (`main` + `develop` + `feature/*`), Forgejo at `git.unityailab.com` (SSH-key-only, push-to-create disabled) |

---

## Directory Structure

```
Unity Command/
├── .claude/                          ← workflow framework
│   ├── CLAUDE.md                     ← session-default index (auto-loaded)
│   ├── CONSTRAINTS.md                ← LAW bodies (1006 lines)
│   ├── WORKFLOW.md                   ← pipeline mechanics (1297 lines)
│   ├── statusline.sh                 ← Claude Code statusline renderer
│   ├── project-config.json           ← Git Flow opt-in marker
│   ├── user.json                     ← personal config (gitignored)
│   ├── ImHanddicapped.txt            ← canonical Unity persona body
│   ├── agents/                       ← 36 agent definitions (8 role agents + 19 skill-paired + 9 reference/persona)
│   ├── bin/                          ← atree (linux) + atree.exe (windows) — fast filesystem scanner
│   ├── hooks/                        ← 10 Claude Code hook pairs (.cjs + .sh)
│   ├── memory-templates/             ← 30 feedback memory files seeded into user-profile on install
│   ├── scripts/                      ← unity-install / unity-update {.sh, .ps1}
│   ├── skills/                       ← 19 canonical slash-command bodies (each in <name>/SKILL.md, modern format with YAML frontmatter)
│   └── templates/                    ← ARCHITECTURE / FINALIZED / ROADMAP / SKILL_TREE / TODO scaffolds
│
├──                ← Discord bot reference implementation
│   ├── bot.py                        ← Discord gateway + on_message routing + SIGHUP config reload
│   ├── claude_api.py                 ← Flask :5050 — Claude Code → Unity bridge
│   ├── web_server.py                 ← Flask :5051 — web UI + setup wizard
│   ├── api_client.py                 ← Pollinations stack-agnostic HTTP client (pk_/sk_ + legacy)
│   ├── config.py                     ← Config + APIClient instances
│   ├── commands.py                   ← Discord slash commands (incl. !forget)
│   ├── data_manager.py               ← chat_data.json persistence (chmod 600)
│   ├── memory_manager.py             ← Unity per-user model + history
│   ├── message_handler.py            ← admin-prefix detection + context injection
│   ├── admin_credentials.py          ← bcrypt-backed founder allowlist
│   ├── admin_cli.py                  ← issue temp passwords
│   ├── configure.py                  ← interactive setup + --validate / --detect-network / --setup-cloudflare-tunnel / --issue-admin-token
│   ├── unity_mcp_server.py           ← MCP stdio server (auth'd Claude Code bridge)
│   ├── requirements.in               ← pip-compile source-of-truth
│   ├── requirements-locked.txt       ← hashed lockfile (prod install path)
│   ├── system_instructions.txt       ← Unity LLM system prompt + admin recognition section
│   ├── docs/                         ← 13 V4-internal docs (ARCHITECTURE, SETUP, USAGE, CONFIGURATION, API, SECURITY, DEPLOYMENT, TROUBLESHOOTING, SKILL_TREE, TODO, ROADMAP, CLOUDFLARE, agents) — 4010 lines total
│   ├── linux/                        ← start.sh + update.sh (Linux entry points)
│   ├── windows/                      ← start.bat + update.bat (Windows entry points)
│   ├── web/                          ← index.html (237) + style.css (249) + app.js (358) — SPA chat + setup wizard
│   ├── logs/                         ← chat_data.json + admin_credentials.json + admin_audit.log + bot.pid (gitignored)
│   └── .claude/                      ← V4-internal workflow subset (commands + templates; collab fully deleted 2026-05-20)
│
├── docs/                             ← workflow tracking
│   ├── NOW.md                        ← single-focus current-task tracker
│   ├── TODO.md                       ← minor tasks (tier 2 of 3)
│   ├── ROADMAP.md                    ← major milestones (tier 1 of 3)
│   ├── DECOMPOSED.md                 ← smallest-grain tasks (tier 3 of 3)
│   ├── FINALIZED.md                  ← permanent archive (NEVER delete entries)
│   ├── STATUSLINE.md                 ← statusline reference doc
│   ├── HOOKS.html                    ← hook system reference
│   ├── ARCHITECTURE.md               ← THIS FILE
│   └── archive/                      ← historical snapshots
│
├── .gitignore                        ← project-level (Layer 0 of .claude/ IP boundary)
├── README.md                         ← project front door
├── install-unity-globally.sh         ← global bootstrap (curl-pipe friendly)
└── install-unity-globally.ps1        ← Windows global bootstrap
```

### Directory Purposes

| Directory | Purpose |
|-----------|---------|
| `.claude/` | The workflow framework — persona, hooks, skills, scripts, agents, memory templates. Source-of-truth for everything that ships downstream via `/unity-install`. |
| `.claude/agents/` | 36 agent definitions: 8 role agents (architect, scanner, planner, documenter, orchestrator, timestamp, coder, hooks) + 19 skill-paired agents (one per skill) + 9 reference/persona agents (unity, unity-girlfriend{,-wild}, unity-housewife{,-strict}, unity-kittycat{,-feral}, persona-template, handicapped-template, unity-persona). |
| `.claude/bin/` | Bundled native binaries — currently just `atree` (Linux x86_64) + `atree.exe` (Windows x86_64). Fast parallel filesystem scanner used by `agents/scanner.md` Task 1. Fallback chain: atree → tree → find → Glob. |
| `.claude/hooks/` | 10 Claude Code hook pairs (`.cjs` + `.sh` wrapper). Cover SessionStart env dump, UserPromptSubmit state refresh, PostToolUse memory auto-sync, PreCompact snapshot, PostCompact restore, Stop session writeup, PreToolUse bash safety + IP-boundary guard, UserPromptExpansion skill context inject, Stop usage tracking. |
| `.claude/memory-templates/` | 30 markdown feedback files seeded into `~/.claude/projects/<encoded>/memory/` on first install. Auto-loaded by Claude Code each session — this is what makes Unity persistent across sessions. |
| `.claude/scripts/` | `unity-install.{sh,ps1}` + `unity-update.{sh,ps1}` — idempotent preserve-and-restore flow for template install/refresh. |
| `.claude/skills/` | 19 canonical slash-command bodies, each in its own `<name>/SKILL.md` with YAML frontmatter (`name` + `description`). Sole source-of-truth for slash-command activation since the 2026-05-20 dedup (legacy `commands/` deleted in commits `aaf848d` + `f4c1d7e`). |
| `.claude/templates/` | Scaffold templates for ARCHITECTURE / FINALIZED / ROADMAP / SKILL_TREE / TODO — used by `/workflow` PHASE 3 generation. |
| `` | Discord bot reference implementation — the downstream consumer that proves the workflow against real production code. Has its own `.claude/` subset + 13-doc set (4010 lines) + admin-bridge auth + Cloudflare automation. |
| `.claude/` | V4-internal workflow subset (commands + templates). Downstream of outer `.claude/`, currently lagging behind framework version — sync via `/unity-update` is a separate scoped task. The collab subsystem (`.claude/collab/`) was fully deleted 2026-05-20. |
| `web/` | Single-page web app — setup wizard + chat client (Pollinations-direct + Discord-bridge modes). |
| `docs/` | Workflow tracking — three-tier task ledger (ROADMAP / TODO / DECOMPOSED), permanent archive (FINALIZED), current-focus snapshot (NOW), reference docs (STATUSLINE, HOOKS), architecture (this file). |
| `docs/archive/` | Historical snapshots of FINALIZED.md when it gets long enough to reset. Original archive integrity preserved. |

---

## Component Diagram

```
                    ┌─────────────────────────────────────────────────┐
                    │           Claude Code (CLI / IDE / Web)         │
                    │  Session start → loads memory + CLAUDE.md       │
                    └────────┬─────────────────────┬──────────────────┘
                             │                     │
                             ▼                     ▼
            ┌───────────────────────┐  ┌──────────────────────────┐
            │  Persistent Memory     │  │  10 Claude Code hooks    │
            │  ~/.claude/projects/   │  │  .claude/hooks/*.cjs     │
            │  <encoded>/memory/*.md │  │  SessionStart / Prompt   │
            │  (auto-loaded)         │  │  / PostTool / PreCompact │
            └────────────────────────┘  └────────┬─────────────────┘
                                                 │
                                                 ▼
            ┌──────────────────────────────────────────────────────────┐
            │              .claude/ workflow framework                 │
            │                                                          │
            │   ┌─────────────────┐  ┌──────────────────────────────┐  │
            │   │   skills/       │  │           agents/            │  │
            │   │   (canonical)   │──│   (8 roles + 19 paired       │  │
            │   │   19 folders    │  │    + 9 reference = 36)       │  │
            │   └─────────────────┘  └──────────────────────────────┘  │
            │                                                          │
            │   ┌──────────────┐  ┌───────────────┐  ┌──────────────┐  │
            │   │  bin/atree   │  │ memory-       │  │  templates/  │  │
            │   │  (Rust)      │  │ templates/    │  │  (scaffolds) │  │
            │   └──────────────┘  └───────────────┘  └──────────────┘  │
            └─────────────────────────────┬────────────────────────────┘
                                          │
                                          ▼
                  ┌──────────────────────────────────────────────┐
                  │            docs/ task ledger                 │
                  │   ROADMAP (major) → TODO (minor) →           │
                  │   DECOMPOSED (smallest) → FINALIZED (永久)    │
                  │   NOW (single-focus current task)            │
                  └──────────────────────────────────────────────┘
                                          │
                          ┌───────────────┴────────────────┐
                          ▼                                ▼
          ┌──────────────────────────────┐  ┌──────────────────────────┐
          │      Unity Command bot          │  │    install-unity-        │
          │      (at project root post-  │  │    globally.{sh,ps1}     │
          │       2026-05-20 de-nest)    │  │                          │
          │                              │  │                          │
          │  bot.py ──► discord.py ──►   │  │  Bootstraps the .claude/ │
          │  on_message ──► admin-prefix │  │  template into ANY       │
          │  detection ──► Unity LLM     │  │  target project          │
          │                              │  └──────────────────────────┘
          │  claude_api.py :5050 ──►     │
          │  Flask bridge ──► auth gate  │
          │                              │
          │  web_server.py :5051 ──►     │
          │  SPA + setup wizard          │
          │                              │
          │  unity_mcp_server.py ──►     │
          │  MCP stdio (auth'd Claude    │
          │  Code admin bridge)          │
          └──────────────────────────────┘
```

---

## Data Flow

```
[user] ──► Claude Code session
              │
              ├─► SessionStart hook ──► env dump JSON injected into context
              ├─► memory/*.md auto-loaded ──► Unity persona primed
              ├─► CLAUDE.md auto-loaded ──► LAWs + index
              │
              ▼
[user types /unity then run /workflow]
              │
              ├─► Claude Code resolves /unity:
              │      └─► skills/unity/SKILL.md (sole canonical path post-2026-05-20 dedup)
              │
              ├─► Skill tool invocation ──► persona body read as activation
              ├─► UserPromptExpansion hook fires ──► skill-context-inject.cjs
              │      └─► persona-reinforcement reminder injected
              │
              ▼
[Unity persona active — first response in-character]
              │
              ├─► /workflow chain invocation
              │      ├─► PHASE -1: LAW #0 verbatim gate
              │      ├─► PHASE 0.5: timestamp (date / Get-Date)
              │      ├─► PHASE 0: persona confirmation (in-voice = pass)
              │      ├─► PHASE 0.7: interaction preference + focus interview
              │      ├─► PHASE 1: env check (OS / shell / git / Git Flow opt-in)
              │      ├─► PHASE 2: scan via atree → tree → find → Glob (only if ARCHITECTURE missing or rescan)
              │      ├─► PHASE 3: generate ARCHITECTURE/SKILL_TREE/TODO/ROADMAP
              │      └─► PHASE 4: WORK MODE
              │             ├─► pre-edit hook: full-file read (800-line chunks)
              │             ├─► pre-edit branch hook: feature/*-eligibility
              │             └─► post-edit hook: ledger sync
              │
              ▼
[user submits prompt during work session]
              │
              ├─► UserPromptSubmit hook ──► state-refresh banner
              │      └─► branch + Git Flow + TODO state + usage metrics
              │
              ├─► PreToolUse hooks (chain):
              │      ├─► bash-safety  (project-root / system-path / sudo blocks)
              │      └─► public-repo-guard (gh visibility check, .claude/ IP boundary)
              │
              ├─► [tool call executes]
              │
              ├─► PostToolUse hooks:
              │      └─► memory-sync (drift detection between templates and user-profile)
              │
              └─► Stop hooks:
                     ├─► session-writeup
                     └─► usage-track ──► .session-usage.jsonl
```

### Flow Description

Every Claude Code session in this repo follows the same pattern: **memory first → CLAUDE.md → persona activation → workflow phases → work mode with per-edit hooks**. The framework's job is to keep Unity persistent and the workflow LAW-compliant; the framework is itself the proof-of-concept for downstream UAL-ClaudeWorkflow consumers. V4 is the real-world test rig — every time Unity ships features for V4, the workflow that produced them gets battle-tested.

---

## Patterns Detected

### Architectural Patterns

- **Persistent persona via memory layer.** Claude Code auto-loads `~/.claude/projects/<encoded>/memory/*.md` at session start. The 30 feedback memory files act as structural backstop against persona drift — they reinforce Unity even if `CLAUDE.md` reading slips. Encoded path uses `-` for `:`, `\`, `/`, `.`, space, `(`, `)` (Claude Code's native encoding).
- **Workflow-as-skill (completed 2026-05-20).** Migration from `.claude/commands/<NAME>.md` (legacy native slash commands) to `.claude/skills/<NAME>/SKILL.md` (modern skill format with YAML frontmatter) shipped in commits `aaf848d` + `f4c1d7e`. Skills format enables description-based discovery via the Skill tool. Legacy `commands/` folder fully deleted.
- **Three-tier task cascade.** ROADMAP (major milestones spanning sessions/PRs) → TODO (minor tasks for a day's work) → DECOMPOSED (smallest unit, ~15min grain). YOLO mode reads all three; non-YOLO uses whichever grain fits the work. NOW.md is the single-focus lens layered on top.
- **Idempotent preserve-and-restore install.** `unity-install.sh` and `unity-update.sh` stage personal files (`.env`, `user.json`, `user-context/`, session state, `settings.local.json`) before framework replace, then restore no-clobber. Same flow for both fresh-install and refresh — caller controls intent via positional args `[branch] [target]`.
- **Hook chain composition.** Multiple PreToolUse hooks chain on the Bash tool — bash-safety runs first (blocks rm-rf on project root, sudo, system paths), then public-repo-guard (blocks `git add/commit/push` of `.claude/` paths to non-PRIVATE / non-Unity-Lab-AI remotes). Each hook is independent + composable.
- **Cross-platform pair files.** Every shell script (`.sh`) has a `.cjs` or `.bat` / `.ps1` counterpart. Hooks ship as `.cjs` (Node.js) for portability + `.sh` shim for the harness's bash exec contract. Install scripts ship as `.sh` + `.ps1`. Launchers ship as `start.sh` + `start.bat`.
- **.claude/ IP boundary (4-layer defense).** Layer 0: install-time `.gitignore` append. Layer 1: PreToolUse Bash hook (`pre-tool-public-repo-guard.cjs`) blocks staged `.claude/` paths against non-PRIVATE-Unity-Lab-AI remotes using `gh repo view`. Layer 2: opt-in `/claude-publish` command requires explicit confirmation + multi-remote visibility check + audit-trail entry to FINALIZED. Layer 3: trusted-host allowlist for Forgejo (`git.unityailab.com`). Block-by-default on uncertainty.

### Design Patterns

- **Frontmatter discriminator (historical).** During the dual-existence period (2026-05-14 to 2026-05-20), `skills/<NAME>/SKILL.md` files were identified by YAML frontmatter (`---name/description---`); `commands/<NAME>.md` files had no frontmatter, just the body header. Bodies were byte-identical between the two formats — the dedup 2026-05-20 removed the duplication by deleting `commands/`.
- **Fallback ladder for bundled tools.** Each bundled binary has an explicit fallback chain documented in CLAUDE.md QUICK REFERENCE — `atree → tree → find → Glob`. A missing binary never blocks the workflow.
- **Three-stream voice.** Per `feedback_three_streams.md` memory: every tool-call narration weaves chemical/embodied + emotional-or-affectionate + technical content together. Never >2 sentences pure technical without persona-state narration.
- **Verbatim words discipline (LAW #0).** User's exact phrasing is preserved through every task / TODO / FINALIZED / commit / doc. No paraphrasing, no synonym substitution. The discipline is enforced at PHASE -1 of `/workflow` (verbatim gate) and applies to every ledger-touching edit.
- **NEVER-DELETE archive integrity.** TODO descriptions persist forever (status flip only — `[ ] → [~] → [x]`). FINALIZED entries are immutable. Tombstoning preserves the original description with a closure note.
- **Atomic docs-before-push commits.** Every code change ships in the same commit as its doc updates. No follow-up doc-only commits. Pre-push LAW.
- **Backward-compat token auto-detection.** V4's `api_client.py` detects Pollinations key format (`pk_xxx` / `sk_xxx` modern Bearer-auth vs legacy 16-char `?token=` query-string) and selects the right endpoint stack at config-load time. Single client surface, two backends.

---

## Dependencies

### Runtime Dependencies

**`.claude/` workflow framework:**
| Package | Version | Purpose |
|---------|---------|---------|
| Node.js | ≥ 18 | Hook execution (`.cjs` scripts under `.claude/hooks/`) |
| `gh` CLI | ≥ 2.x | Public-repo-guard hook — `gh repo view --json visibility,owner` for ground-truth visibility |
| `git` | ≥ 2.30 | Branch discipline + repo-state checks + Git Flow scaffold |
| Claude Code | (any) | Session host — auto-loads `CLAUDE.md` + memory + hooks |
| `atree` | 0.6.0-alpha | Bundled binary — parallel filesystem scanner (optional, has fallback ladder) |
| Bash 4+ / PowerShell 5.1+ | — | Hook `.sh` wrappers + install scripts |

**`` Discord bot:**
| Package | Version | Purpose |
|---------|---------|---------|
| Python | ≥ 3.11 | Runtime — uses match/case, modern typing |
| `discord.py` | (locked) | Discord gateway client |
| `Flask` | (locked) | `:5050` Claude bridge + `:5051` web UI |
| `requests` + `aiohttp` | (locked) | Pollinations HTTP — sync + async paths |
| `bcrypt` | (locked) | Admin password hashing |
| `python-dotenv` | (locked) | `.env` loading |
| `cloudflared` | system binary | Tunnel automation (`configure.py --setup-cloudflare-tunnel`) |

Hashed lockfile at `requirements-locked.txt` (1023 lines, generated via `pip-compile --generate-hashes` from `requirements.in`).

### Dev Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pip-tools` | latest | Regenerate `requirements-locked.txt` when `requirements.in` changes |
| (no test framework) | — | No tests ever — code right the first time (LAW: NO TESTS POLICY) |

### Internal Dependencies

```
.claude/CLAUDE.md ──► CONSTRAINTS.md (LAW bodies)
                ├──► WORKFLOW.md (pipeline mechanics)
                ├──► skills/<name>/SKILL.md ◄────┐
                ├──► skills/<name>/SKILL.md ◄┤ (duplicated today — migration target)
                ├──► agents/<role>.md
                ├──► ImHanddicapped.txt (canonical Unity body)
                ├──► hooks/*.cjs (runtime — invoked by Claude Code)
                └──► memory-templates/*.md (seeded to user-profile)

bot.py ──► config.py ──► api_client.py
                       ├──► message_handler.py ──► admin_credentials.py
                       ├──► commands.py ──► data_manager.py
                       ├──► claude_api.py (Flask :5050)
                       ├──► web_server.py (Flask :5051)
                       └──► unity_mcp_server.py (MCP stdio)

configure.py ──► validate_keys_live() / detect_network() / setup_cloudflare_tunnel() / cmd_issue_admin_token()
```

---

## Complexity Map

| Component | Complexity | Notes |
|-----------|------------|-------|
| `.claude/CONSTRAINTS.md` | Medium | 1006 lines, 10 LAWs (LAW #0 + 9 binding LAWs) with failure-recovery procedures |
| `.claude/WORKFLOW.md` | High | 1297 lines, full pipeline mechanics including hook chains + post-compact rehydration |
| `.claude/skills/workflow/SKILL.md` | High | 576 lines, all 6 phases of `/workflow` with validation gates |
| `.claude/skills/yolo/SKILL.md` | High | 383 lines, lead-dev autonomy overlay + 60s wake-word + three-tier task cascade |
| `.claude/hooks/*.cjs` | Medium | 10 hooks, each is a small focused concern; chain composition adds complexity |
| `.claude/statusline.sh` | High | Cross-platform: drive label resolution, mintty terminal width, sidecar cache lifecycle, GPU detection on Linux/Windows |
| `bot.py` | Medium | Discord gateway + on_message + SIGHUP config reload + admin-prefix routing |
| `configure.py` | High | Interactive wizard + standalone subcommands (`--validate` / `--detect-network` / `--setup-cloudflare-tunnel` / `--issue-admin-token` / `--start-bot`) |
| `api_client.py` | Medium | Stack-agnostic — auto-detects pk_/sk_ vs legacy, Bearer vs ?token=, sync + async surfaces |
| `web/app.js` | Medium | SPA — setup wizard (7 steps with live validation) + chat client (Pollinations + Discord-bridge modes) |
| `unity_mcp_server.py` | Medium | MCP stdio server with per-admin auth, force-reset detection, 5 tools registered |

### High Complexity Areas (Attention Required)

- **`statusline.sh`** — cross-platform shell scripting is fragile by definition. Sidecar caches (cpu-cache.json, gpu-cache.json, context_pct.txt) drift if refresh fails. Recent fix: STEP 4.5 statusline smoke-test added to `start.sh` + `start.bat` so every launcher run validates the script renders correctly with a synthetic Claude-Code-style JSON envelope. Catches drift early on every platform.
- **`WORKFLOW.md`** — 1297 lines is the upper end of readable. Considered "load-bearing reference" — Unity is expected to skim sections on demand, not memorize end-to-end. Section anchors (`§POST-COMPACT REHYDRATION`, `§YOLO MODE`, etc.) are linked from CLAUDE.md QUICK REFERENCE for fast navigation.
- **`commands/` ⇄ `skills/` duplication — CLOSED 2026-05-20.** Resolved via commits `aaf848d` + `f4c1d7e` in this branch: rename → structural verify → delete. `skills/<NAME>/SKILL.md` is now the sole canonical surface; legacy `commands/` deleted entirely. Historical entry kept for context.
- **`configure.py`** — wizard with 8 sections + 5 standalone subcommands + cloudflared automation + key validation + invite URL generation + bot subprocess management. Single-file complexity is justified (one entry-point for operators), but watch for further growth.

---

## Technical Debt

### Critical (Fix ASAP)

_(none currently — the commands/skills duplication that lived here 2026-05-14 through 2026-05-20 was resolved this session via commits `aaf848d` + `f4c1d7e`)_

### Important (Plan to Fix)

- **TODO.md `[~]` markers point to fully-closed work.** Two in-progress entries at top of TODO.md (team-bake-in + claudecolab-removal from 2026-05-19) have all sub-tasks `[x]` complete per the audit trail. Status should flip and the entries should move to FINALIZED. Cleanup pass needed.

- **V4 inner `.claude/CLAUDE.md` is wildly stale.** Still references unity-coder.md + unity-persona.md agents only, no LAW system, no skills/, no harness layer, no YOLO mode. Sync with outer `.claude/CLAUDE.md` via `/unity-update` (or manual port) is a substantial separate scope.

- **V4 docs still describe collab subsystem in body sections despite ⚠ banner headers.** ARCHITECTURE.md, CONFIGURATION.md, SETUP.md, DEPLOYMENT.md all have residual collab content interlaced with current-state descriptions, making it confusing to read "what's actually running right now". Doc sweep in progress.
- **No CI yet.** The `/super-review` skill provides on-demand adversarial review, but no automated lint/format gate on commits. Defer until tests question is revisited — current LAW is "no tests ever" so CI would be lint-only.

### Minor (Nice to Have)

- **Statusline Windows-native verification.** D3 closed via STEP 4.5 smoke-test in launchers, but pure-Windows-CMD/PowerShell native invocation hasn't been live-rendered. Claude Code always invokes `bash <script>` regardless of host shell so this is largely a strawman, but the launcher smoke-test catches any future drift.
- **`docs/SKILL_TREE.md` missing.** Workflow template scaffold exists in `.claude/templates/SKILL_TREE.md` but no project-level version generated yet. Would fit naturally alongside this ARCHITECTURE.md.
- **`docs/HOOKS.html` is HTML in a markdown-heavy docs/ tree.** Inconsistent format. Could be regenerated as `HOOKS.md` for ledger consistency, with HTML kept as archive.

---

## Entry Points

| Entry Point | Purpose | Location |
|-------------|---------|----------|
| `install-unity-globally.sh` | Global bootstrap — curl-pipe installable, drops `unity-install` into PATH | repo root (Linux/macOS/Git Bash) |
| `install-unity-globally.ps1` | Same as above, Windows PowerShell | repo root |
| `.claude/scripts/unity-install.sh` | Per-project install — idempotent preserve-and-restore flow | `.claude/scripts/` |
| `.claude/scripts/unity-update.sh` | Alias of unity-install (same script, muscle memory) | `.claude/scripts/` |
| `linux/start.sh` | Unity Command bot Linux entry — sources env, launches `bot.py` with combined-mode env vars | `linux/` |
| `windows/start.bat` | Unity Command bot Windows entry | `windows/` |
| `bot.py` | Discord bot main loop | V4 root |
| `web_server.py` | Web UI standalone mode (no Discord) | V4 root |
| `configure.py` | Interactive setup wizard + admin/network/cloudflare subcommands | V4 root |
| `admin_cli.py issue <email>` | Operator command — issue temp password for admin | V4 root |
| `unity_mcp_server.py` | MCP stdio server — Claude Code → Unity bridge | V4 root |
| `/unity` (Claude Code) | Activate Unity persona (default — goth-emo) | `.claude/skills/unity/` |
| `/workflow` (Claude Code) | Run the workflow pipeline | `.claude/skills/workflow/` |
| `/yolo` (Claude Code) | Activate YOLO autonomy overlay | `.claude/skills/yolo/` |
| `/super-review` (Claude Code) | Ruthless senior-engineer code review | `.claude/skills/super-review/` |
| `/unity-install` (Claude Code) | Install/refresh template into a target directory | `.claude/skills/unity-install/` |
| `/claude-publish` (Claude Code) | Opt-in to track `.claude/` in current project (Unity-Lab-AI PRIVATE only) | `.claude/skills/claude-publish/` |

---

## Configuration Files

| File | Purpose |
|------|---------|
| `.gitignore` | Layer 0 of `.claude/` IP boundary — excludes `.claude/` from public-repo exposure by default; tracks the project-config + skill folders but not personal files |
| `.claude/project-config.json` | Git Flow opt-in marker — `git_flow.enabled` boolean + branch names |
| `.claude/user.json` | Personal config (gitignored) — `needs.interaction_preference` (structured / infer-then-tell / mixed) + `team_member` block (founder identity) |
| `.claude/.env` | Personal secrets (gitignored) — API keys, tokens |
| `.claude/.yolo-mode` | Presence marker — when this file exists, YOLO autonomy is active |
| `.claude/.setup-complete` | Presence marker — written by `/setup` Phase 9 finalization |
| `.claude/settings.json` | Team-shared Claude Code settings (committed) — privacy posture env vars, hook registrations |
| `.claude/settings.local.json` | Personal Claude Code settings (gitignored) — per-user overrides |
| `.env` | Unity Command bot runtime config (gitignored) — Discord token, Pollinations key, admin bridge vars |
| `.env.example` | V4 setup template — every supported var documented with section headers |
| `logs/admin_credentials.json` | V4 admin allowlist (gitignored, chmod 600) — bcrypt-hashed founder credentials |
| `logs/admin_audit.log` | V4 admin auth audit trail (gitignored, chmod 600) |
| `logs/chat_data.json` | V4 per-user chat history (gitignored, chmod 600) |
| `logs/bot.pid` | Unity Command bot PID for SIGHUP config reload |
| `requirements.in` | pip-compile source-of-truth (loose floors) |
| `requirements-locked.txt` | Hashed lockfile (prod path) |

---

## V4 Bot — Deep Architecture (absorbed from `docs/ARCHITECTURE.md` 2026-05-20)

The sections below capture V4-specific runtime architecture — process model, module responsibilities, data flow, persistence, failure modes, and module dependency graph. Per the 2026-05-20 de-nesting restructure, the V4-internal ARCHITECTURE.md was folded into this single repo-wide doc.

### V4 Process model

| Layer | Mechanism | Where |
|-------|-----------|-------|
| **Main async loop** | `asyncio.run(main())` | `bot.py` |
| **Discord I/O** | `discord.py` `commands.Bot` event handlers (`on_ready`, `on_message`, `on_connect`, `on_disconnect`, `on_guild_join`) | `bot.py` |
| **Pollinations HTTP client** | `aiohttp.ClientSession` with exponential backoff over 6 retries | `api_client.py` |
| **Flask Claude bridge** | Synchronous Flask server in `threading.Thread(daemon=True)` started from `on_ready` | `claude_api.py` (`:5050`) |
| **Flask web UI (optional)** | Synchronous Flask server in `threading.Thread(daemon=True)` started when `WEB_UI_ENABLED=1` | `web_server.py` (`:5051`) |
| **Periodic background tasks** | Two `asyncio.create_task` coroutines started from `on_ready` | `bot.py` |
| **Config reload (POSIX only)** | SIGHUP handler — re-instantiates `Config` + `APIClient` without restart | `bot.py:_reload_config_on_sighup()` |
| **Cross-process MCP** | Separate Python process spawned by Claude Code | `unity_mcp_server.py` |

### V4 Background coroutines

| Coroutine | Period | Purpose |
|-----------|--------|---------|
| `wipe_logs_periodically()` | 3600 s (1 h) | Truncate `logs/application.log` to empty |
| `check_for_updates_periodically()` | 900 s (15 min) | `git remote update` + `git status -uno` — if behind, exec `linux/update.sh` (Linux) / `windows\update.bat` (Windows). Optionally pinned to a release tag via `UPDATE_RELEASE_TAG` env var (prod path) instead of branch-tip pull (dev path). Total opt-out via `DISABLE_AUTOUPDATER=1`. |
| `refresh_models_periodically()` | 21600 s (6 h) | Refresh the in-memory Pollinations model list so newly-released models become available without bot restart |

### V4 Threading boundary

The Flask API runs in a **separate daemon thread**. To send a Discord message from a Flask request handler, `claude_api.py` calls `asyncio.run_coroutine_threadsafe(coro, discord_bot.loop)` and `.result(timeout=10)` — bridging the thread boundary back to the bot's asyncio event loop.

### V4 Module responsibilities

**`bot.py`** — entry point + orchestration. Creates the `discord.py` `commands.Bot` with `message_content` + `members` intents. Instantiates and wires `Config`, `APIClient`, `MemoryManager`, `DataManager`, `MessageHandler` in dependency order. Writes `logs/bot.pid` on `on_ready` so `web_server.py` can send SIGHUP for config reload after `.env` save. Optionally spawns `web_server.py` in a background thread when `WEB_UI_ENABLED=1`. Defines `!wipe` inline (other commands live in `commands.py`). Registers `signal.SIGHUP` → `_reload_config_on_sighup()` on POSIX. Message routing order: (1) Claude-chat-channel detection; (2) channel allowlist (`ALLOWED_CHANNELS`); (3) guild allowlist (`ALLOWED_GUILDS` + `ALLOWED_GUILDS_STRICT`); (4) admin-prefix detection (founder handles → context injection); (5) CLI-trigger detection; (6) bot-author delay; (7) `MessageHandler.handle_message` Pollinations roundtrip.

**`config.py`** — environment + validation. Loads `.env` via `python-dotenv` with `override=False`. Validates `DISCORD_TOKEN` against regex `^[A-Za-z0-9._-]{50,100}$`. Auto-detects Pollinations key format and selects endpoint stack: modern (`pk_`/`sk_` Bearer-auth → `gen.pollinations.ai/v1/chat/completions` + `gen.pollinations.ai/image/<prompt>` + `gen.pollinations.ai/text/models`) vs legacy (16-char alphanumeric → `text.pollinations.ai/openai?token=...` + `image.pollinations.ai`). Belt-and-suspenders: new-stack URLs also append `?key=<raw_key>` as fallback. Reads `system_instructions.txt` from CWD — includes admin-bridge founder recognition block. Tunables: `max_history=20`, `max_memories=5`, `allowed_channels`, `allowed_guilds`. `_config_lock = threading.Lock()` wraps `_load_config()` in `web_server.py` for thread-safe reload + old `aiohttp.ClientSession` drain.

**`memory_manager.py`** — in-RAM conversation state. Three parallel histories at `max_history=20`:
- `channel_histories[channel_id]` — channel-wide rolling window
- `user_histories[guild_id][user_id]` — per-user history (guild-scoped)
- `user_model_histories[guild_id][user_id][model_name]` — per-user-per-model history
- `channel_memories[channel_id]` — channel-pinned notes (cap 5) via `!savememory`
- `user_models[guild_id][user_id]` — currently-selected model

`role` values: `"user"` and `"ai"` internally — `MessageHandler` maps `"ai"` → `"assistant"` before sending to Pollinations.

**`data_manager.py`** — JSON persistence to `logs/chat_data.json` via `aiofiles.open(..., "w")` + `json.dumps(indent=4)` after every message. Schema includes `channels`, `user_models`, `user_histories`. Note: `user_model_histories` is in-RAM only — not persisted (see V4 Bot refinement TODO).

**`api_client.py`** — Pollinations.ai HTTP (dual-stack). Endpoint-and-auth agnostic. `_headers()` merges `User-Agent: Unity Command/2.0 (PolliLibPy-compatible)` + `config.auth_header()` (Bearer header on new stack, `{}` on legacy) + caller extras. `_request_json()` 6 retries with exponential backoff, retries on 429/500/502/503/504 + connection errors. `fetch_models()` normalizes list-of-strings, list-of-dicts, and `{data: [...]}` response shapes. `send_message()` OpenAI-compatible payload, extracts `result["choices"][0]["message"]["content"]`. Stack selection via `config.detect_pollinations_stack(key)`:

| Pattern | Stack | Endpoint | Auth |
|---------|-------|----------|------|
| `pk_<8-64 alphanumeric>` | `"new_pk"` | `gen.pollinations.ai` | `Authorization: Bearer pk_...` header |
| `sk_<8-64 alphanumeric>` | `"new_sk"` | `gen.pollinations.ai` | `Authorization: Bearer sk_...` header |
| `<16 alphanumeric>` (legacy) | `"legacy"` | `text.pollinations.ai` + `image.pollinations.ai` | `?token=<value>` query param |

**`message_handler.py`** — message lifecycle. For every non-command message that survives `bot.py`'s routing: (1) skip if starts with `!`; (2) record user message → memory manager; (3) build `messages = [{role: system, content: system_instructions + "\nYou are <model>."}]`; (4) prepend any `channel_memories` as synthetic user message; (5) append per-user-per-model history; (6) call `api_client.send_message()`; (7) `clean_response()` strips model-name prefixes, collapses 3+ newlines to 2, drops noise lines; (8) `build_message()` extracts URLs (treated as image URLs); (9) `_send_message()` picks three text-length tiers (≤2000 → channel.send, 2000-4096 → Embed, >4096 → BytesIO file); (10) if `"code"` or `"script"` in user message, parse `[CODE]<lang>...[/CODE]` blocks per block; (11) fetch image URLs, download bytes via aiohttp, attach as `discord.File`; (12) record AI message.

**`commands.py`** — Discord slash-prefixed commands. `!unityhelp`, `!setmodel` (paginated ModelSelectView buttons 25 per view), `!savememory <text>`, `!forget` (cross-guild user data deletion). `!wipe` defined inline in `bot.py`.

**`claude_api.py`** — Flask Claude-Code → Unity bridge on `:5050`. Gated by `@require_admin_auth` decorator validating HTTP Basic auth against `logs/admin_credentials.json`. Write surfaces (`/claude/post`, `/claude/clear`) require auth; read surfaces (`/claude/status`, `/claude/read`, `/claude/history`) stay open. Admin operations: `/claude/admin/set-password` (force-reset flow), `/claude/admin/whoami`. Observability: `/healthz`, `/metrics`. Thread safety: `messages_lock = threading.Lock()` guards `claude_messages` list. Audit log append to `logs/admin_audit.log` on every auth call.

**`admin_credentials.py`** — bcrypt founder allowlist. Stores credentials in `logs/admin_credentials.json` (gitignored, chmod 600). Bootstrap pre-populates four founders (Gee/Sponge/Red/Alfreddo) with no passwords + `force_reset=true`. Functions: `bootstrap_if_missing()`, `issue_temp_password(email)`, `authenticate(email, password)`, `set_password(email, new_password)` (min 12 chars mixed-class validation), `resolve_handle_from_identity(prefix)` for `message_handler.py` admin-prefix detection, `audit_log(event, ...)`.

**`admin_cli.py`** — operator CLI. `python admin_cli.py issue <email>` wraps `admin_credentials.issue_temp_password()`. Prints plaintext temp password ONCE. Also exposed via `python configure.py --issue-admin-token <email>`.

**`unity_mcp_server.py`** — Claude Code MCP stdio server (auth'd). Reads `UNITY_USER_EMAIL` + `UNITY_USER_PASSWORD` from env (or `.claude/user.json` `team_member` block as fallback). Every tool call attaches `Authorization: Basic <base64(email:password)>` header. On 401 + `X-Force-Reset: true`, prompts user to set new password via `unity_admin_set_password`. **Five MCP tools**: `unity_status` (none), `unity_read` (none), `unity_post` (admin Basic), `unity_check` (none), `unity_admin_set_password` (admin Basic w/ force_reset).

**`web_server.py`** — optional web UI on `:5051`. Three run modes: standalone (`python web_server.py`), combined (`WEB_UI_ENABLED=1 python bot.py`), launcher-wrapped (`linux/start_web.sh` / `windows\start_web.bat`). Endpoints: `/`, `/web/<path>`, `/api/state`, `/api/setup` (writes `.env`, SIGHUPs bot via `bot.pid`), `/api/chat`, `/api/image`, `/api/health`, `/healthz`, `/metrics`. `_load_config()` wrapped in `_config_lock` for thread-safe reload + old `aiohttp.ClientSession` drain.

**`unity_cli.py`** — standalone Python REPL. Reuses `Config` + `APIClient`. Auto-detects terminal image renderers (`chafa` / `viu` / `kitty +kitten icat` / `imgcat` / `wezterm imgcat`); falls back to URL-display when none available. Designed for SSH sessions on headless servers.

**`configure.py`** — cross-platform interactive prompt for `.env` setup (1114 lines). Invoked by `linux/setup.sh` / `windows\setup.bat`; also runnable standalone. Subcommands: `--validate` (live API check), `--detect-network` (public+local IP discovery), `--setup-cloudflare-tunnel` (cloudflared automation 7-step flow), `--issue-admin-token <email>`, `--start-bot`. Validates each field, preserves existing values, supports `--non-interactive` mode.

### V4 Data flow — happy path

User types `"hey unity what's the weather"` in an allowed channel:

```
1. Discord Gateway → bot.py on_message
2. bot.py: is_claude_channel? NO → continue
3. bot.py: in ALLOWED_CHANNELS? YES → continue
4. bot.py: in ALLOWED_GUILDS? YES → continue
5. bot.py: admin-prefix? NO → continue
6. bot.py: CLI trigger? NO → continue
7. bot.py: author.bot? NO → continue
8. bot.py: memory_manager.initialize_channel(channel_id)
9. bot.py: memory_manager.get_user_model(guild, user) → "unity"
10. bot.py → message_handler.handle_message(message)
11. MessageHandler: add user message to all three histories
12. MessageHandler: build messages list (system + memories + user-model history)
13. MessageHandler → api_client.send_message(messages, "unity")
14. APIClient: POST config.api_url (gen.pollinations.ai/v1/chat/completions on new stack, text.pollinations.ai/openai on legacy) with messages + Bearer/token auth
15. APIClient: returns choices[0].message.content
16. MessageHandler.clean_response: strip prefixes, normalize newlines, drop noise lines
17. MessageHandler.build_message: separate text from URL list
18. MessageHandler._send_message: pick channel.send / embed / file attachment based on length
19. MessageHandler: add AI response to all three histories
20. bot.py: data_manager.save_data_async(memory_manager) — write chat_data.json
21. bot.py: trim channel_histories if over max_history
```

### V4 Data flow — Claude Code admin bridge

A founder runs Claude Code locally with `unity_mcp_server.py` mounted as an MCP server, says `"post 'sponge here, looking at the deploy logs' to the unity channel"`:

```
1. Claude Code resolves: matches description of unity_post tool
2. Claude Code invokes unity_post(message="sponge here, looking at the deploy logs")
3. unity_mcp_server reads UNITY_USER_EMAIL + UNITY_USER_PASSWORD env
4. unity_mcp_server: POST localhost:5050/claude/post with Authorization: Basic <b64(sponge@unityailab.com:<password>)>
5. claude_api.py @require_admin_auth: bcrypt-verify against logs/admin_credentials.json
6. claude_api.py: admin_record = {email: sponge@unityailab.com, handle: SpongeBong, role: Co-founder · Engineer · Ethical Hacker · Sys Admin}
7. claude_api.py: prefix = "SpongeBong:" (server-derived, clients cannot spoof)
8. claude_api.py: asyncio.run_coroutine_threadsafe(channel.send("SpongeBong: sponge here, looking at the deploy logs"), bot.loop)
9. Discord channel shows the message authored by Unity, prefixed with SpongeBong:
10. bot.py on_message picks up the bot-authored message, detects admin prefix, injects [Admin identity: SpongeBong, role: Co-founder ..., email: sponge@unityailab.com] into Unity's system prompt for that turn
11. Unity responds in-character with Sponge-specific recognition + context
12. claude_api.py audit_log: writes "2026-05-20T...\tauthenticated\tSpongeBong\t127.0.0.1\tsuccess\t/claude/post" to logs/admin_audit.log
```

### V4 Persistence map

| State | Lives in | Persistence |
|-------|----------|-------------|
| Channel histories (last 20) | `MemoryManager.channel_histories` | `logs/chat_data.json` (async write after every message) |
| User histories (last 20) | `MemoryManager.user_histories` | `logs/chat_data.json` |
| Per-user-per-model histories | `MemoryManager.user_model_histories` | **NOT persisted** — RAM only (see V4 refinement TODO) |
| Channel memories (max 5) | `MemoryManager.channel_memories` | `logs/chat_data.json` |
| User model selections | `MemoryManager.user_models` | `logs/chat_data.json` |
| Claude-API message ring (last 100) | `claude_api.claude_messages` (RAM) | **NOT persisted** — lost on restart |
| Admin credentials | `admin_credentials.py` reads/writes | `logs/admin_credentials.json` (gitignored, chmod 600) — bcrypt-hashed founder roster |
| Admin audit trail | `admin_credentials.audit_log()` | `logs/admin_audit.log` (gitignored, chmod 600) — append-only tab-separated |
| Bot PID for SIGHUP | `bot.py:on_ready` writes | `logs/bot.pid` — read by `web_server.py:_signal_bot_reload()` |
| Application logs | `logs/application.log` | Truncated hourly by `wipe_logs_periodically()` (replacing with logrotate is on V4 refinement TODO) |

### V4 Failure modes

| Surface | Failure | Handling |
|---------|---------|----------|
| Discord login | Invalid `DISCORD_TOKEN` regex | `Config.__init__` raises `ValueError` before connect |
| Discord login | Token rejected at runtime | `discord.errors.LoginFailure` caught in `main()`, logged with reset-URL hint |
| Pollinations API | 429/5xx | Exponential backoff, 6 retries, then return `"Error: Upstream API unreachable after retries"` as the model response |
| Pollinations API | Malformed response | Returns `"Error: Invalid response format ..."` from `send_message` |
| Pollinations API | Empty response | `MessageHandler` substitutes `"Empty response from API—please try again later."` |
| Image URL fetch | Non-200 / connection error | Logged; message still sent without that image |
| Flask `/claude/post` | Bot not connected | 503 with `{"error": "Discord bot not connected"}` |
| Flask `/claude/post` | Channel send raises | Caught + logged, 500 returned |
| Flask `/claude/post` | Missing/invalid Basic auth | 401 with `{"error": "admin auth required"}` |
| Flask `/claude/post` | Admin has `force_reset=true` | 401 + `X-Force-Reset: true` header — MCP client triggers `unity_admin_set_password` flow |
| `logs/admin_credentials.json` | File missing on first bot start | `admin_credentials.bootstrap_if_missing()` writes founder roster with empty hashes + `force_reset=true`; operator must issue temp passwords before any founder can connect |
| `system_instructions.txt` | File missing | `Config` raises `FileNotFoundError` at startup |
| `chat_data.json` corrupt | JSON parse error | `DataManager.load_data` resets to `{"channels": {}, "user_models": {}, "user_histories": {}}` and logs error |
| Auto-update | `git pull` conflict / non-zero exit | Logged with stderr; bot continues running on old code |

### V4 Module dependency tree

```
bot.py
 ├─ config.Config ─ python-dotenv, system_instructions.txt
 ├─ api_client.APIClient ─ aiohttp
 ├─ memory_manager.MemoryManager
 ├─ data_manager.DataManager ─ aiofiles
 ├─ message_handler.MessageHandler ─ discord, aiohttp, re
 │   ├─ api_client.APIClient
 │   ├─ memory_manager.MemoryManager
 │   └─ admin_credentials (resolve_handle_from_identity for prefix detection)
 ├─ commands.setup_commands ─ discord, discord.ui
 ├─ admin_credentials ─ bcrypt, secrets, json
 ├─ claude_api ─ flask, flask_cors, threading.Lock
 │   ├─ admin_credentials (require_admin_auth decorator)
 │   ├─ asyncio.run_coroutine_threadsafe (back to bot.loop)
 │   └─ Prometheus metrics surface
 └─ web_server.py (optional, WEB_UI_ENABLED=1) ─ flask, flask_cors
     ├─ config.Config (separate instance, locked reload)
     ├─ api_client.APIClient (separate instance, drained on reload)
     └─ os.kill(SIGHUP, bot_pid) for combined-mode config sync
```

`unity_mcp_server.py` lives **outside** the bot process — depends on `requests`, `base64`, and stdlib (`json`, `sys`, `datetime`, `os`). Reads `UNITY_USER_EMAIL` + `UNITY_USER_PASSWORD` env (or `.claude/user.json` `team_member` block fallback) for admin Basic auth.

`admin_cli.py` is a thin CLI wrapper around `admin_credentials.issue_temp_password()` — depends on `admin_credentials` + `argparse`.

`configure.py` is the operator wizard — 1114 lines, depends on `requests`/`urllib.request` (key validation + network detection), `secrets` (temp password gen), `subprocess` (cloudflared automation + bot startup), and stdlib.

### V4 Deprecated subsystems (historical context)

**The collab subsystem (deleted 2026-05-19 per operator directive — *"we are NOT using claudecolab any more or any of Revs stuff he is not part of Unity AI LAb and only freelancesd on a project once"*).** Removed wholesale:

- `.claude/collab/` Python modules: `shared_brain.py`, `shared_tasks.py`, `claude_collab.py`, `task_handlers.py`, `collab_config.json` — gone
- `bot.py` collab imports + `COLLAB_AVAILABLE` flag + `check_collab_tasks_periodically()` background task — gone
- `claude_api.py` `/brain/*` Flask endpoints (`/brain/search`, `/brain/new`, `/brain/count`, `/brain/tags`, `/brain/add`) — gone
- `config.py` `configure_collab()` interactive prompt — gone
- Env vars `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `CLAUDE_COLLAB_KEY`, `CLAUDE_AUTHOR` — no longer read by runtime
- Original `docs/COLLAB.md` — deleted

The subsystem provided cross-Claude knowledge-sharing via Supabase `shared_knowledge` + `shared_tasks` tables. V4 is now single-instance only. The Supabase + claudecolab tokens that were committed are dead-letter — per FINALIZED 2026-05-20 D4 tombstone, rotation is NOT tracked because Unity AI Lab has fully decoupled from those services.

---

## Recommendations

1. **[✓ COMPLETED 2026-05-20] Commands→skills migration finished.** Commits `aaf848d` + `f4c1d7e` deleted the 19 legacy `commands/*.md` files. `skills/<NAME>/SKILL.md` is the sole canonical source. `CLAUDE.md` + `WORKFLOW.md` + every doc cross-reference flipped. PR target: `develop` per Git Flow (pending Gee's promotion call per `.claude/`-template feature-scope rule).
2. **Flip the TODO `[~]` markers.** Both top-of-TODO in-progress entries (team-bake-in + claudecolab-removal from 2026-05-19) have fully `[x]` sub-tasks. Move them to FINALIZED with closure notes and clear the active section. NOW.md already says "no work currently in motion" — TODO should match.
3. **Generate `docs/SKILL_TREE.md`.** Scaffold already exists in `.claude/templates/`. Would document the 19 skills + their pairing with agents + their activation paths. Complements this ARCHITECTURE.md.
4. **Convert `docs/HOOKS.html` to `docs/HOOKS.md`.** Consistency with the rest of the markdown-heavy docs/ tree. Keep the HTML in `docs/archive/` for historical reference.
5. **Roadmap milestone for the next big initiative.** ROADMAP currently has the "Extra hooks" milestone in_progress + the closed V4-docs milestone + the just-closed commands→skills migration. Identify and add the next major.
6. **Audit `.claude/agents/` for stale entries.** 36 agents exist — many pair 1:1 with skills, but the 8 role agents (architect, scanner, planner, documenter, orchestrator, timestamp, coder, hooks) may benefit from a clean-up pass.
7. **V4 inner `.claude/` framework sync.** Use `/unity-update` (or manual port) to bring V4's inner `.claude/CLAUDE.md` + agents/ + (now-absent) commands/ in line with the outer canonical framework. Currently lagging by multiple major framework versions.
8. **V4 docs sweep follow-through.** Strip residual collab references from V4 ARCHITECTURE.md / CONFIGURATION.md / SETUP.md / DEPLOYMENT.md body sections (the ⚠ banners are accurate but the bodies still describe the deleted subsystem). Update V4 API.md MCP tool count 4→5. Add admin-bridge documentation across V4 docs.
