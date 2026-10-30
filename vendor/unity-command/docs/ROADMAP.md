# ROADMAP — Major Task List (High-Level Phases / Milestones)

**Tier 1 of 3 — the MAJOR task list.** Holds the high-level phases / milestones that span multiple sessions or multiple PRs. Each major item breaks down into MINOR tasks in `docs/TODO.md`, which break down further into DECOMPOSED tasks in `docs/DECOMPOSED.md`.

YOLO mode reads all three tiers on activation. The cascade rule: complete the current decomposed task → next decomposed task in the same minor → if minor is done, next minor in the same major → if major is done, surface a milestone-boundary check-in to the user → start next major unless user stops.

Status markers (same scheme as TODO.md):
- `[ ]` pending
- `[~]` in_progress
- `[x]` complete (move to FINALIZED.md immediately, never leave here)

LAW #0 reminder: every milestone description preserves the user's verbatim words.

---

## In progress

_(none — bootstrap state. First major milestone added when one is identified or when the user explicitly states one.)_

---

## Pending

### [ ] Major milestone — "Extra hooks" workflow extension (current branch: `feature/extra-hooks`)

**Verbatim user context (from current session):**

> we are on a specific branch for extra workflows, so the whole main -> develop -> feature/branch is currently in place

This milestone covers the `feature/extra-hooks` branch's full scope: pre/post-compact hooks with cache-prefix strategy + tidbits, YOLO mode rework with three-tier task lists + 60s wake-word pattern + skill hooks, and the HOOKS.html reference doc. Closes when all in-flight TODO entries from this session are FINALIZED and the branch is ready for PR to `develop`.

**Minor tasks under this milestone** live in `docs/TODO.md` and are referenced by their verbatim TODO subject lines.

### [x] Major milestone — Unity Command full documentation set (branch: `feature/migrate-commands-to-skills`) — closed 2026-05-19

**Verbatim user context (from session 2026-05-19):**

> i want you to make all the docs for this project V4

V4 = the Unity Command Discord bot (at that point still nested under `Unity Command-develop/`; flattened to project root 2026-05-20). Prior state at session 2026-05-19 start: zero `docs/` folder under V4, only `README.md` + `agents.md` + `system_instructions.txt`. This milestone covered writing the complete documentation set inside (then) `Unity Command-develop/docs/` to cover architecture, setup, usage, configuration, the Flask Claude REST API on :5050, the MCP stdio server stub, the Supabase shared-brain/task-queue collab subsystem (G/R author IDs) — collab subsystem subsequently deleted 2026-05-19 — security findings (hardcoded keys), deployment (systemd + auto-update), and troubleshooting.

**Closure 2026-05-19**: 12 docs shipped (3322 lines total, all under 800-line LAW: ARCHITECTURE.md 358, SKILL_TREE.md 251, CONFIGURATION.md 257, SETUP.md 262, USAGE.md 229, API.md 507, COLLAB.md 371, SECURITY.md 240, DEPLOYMENT.md 321, TROUBLESHOOTING.md 292, V4-internal TODO.md 108, V4-internal ROADMAP.md 126). Root `README.md` updated with Documentation section (table linking all 12 docs) + expanded Files section. 7 security findings surfaced in V4 SECURITY.md as pending remediation items in V4-internal TODO. Full audit trail in `docs/FINALIZED.md` Session 2026-05-19.

**Minor tasks under this milestone** lived in `docs/TODO.md` (outer task tracker — now flipped `[x]`). Internal V4 task tracking continues inside `docs/TODO.md`.

---

## TOMBSTONES

_(none)_

---

## V4 Bot stream — absorbed from `docs/ROADMAP.md` 2026-05-20

Per the de-nesting restructure 2026-05-20 (Gee's directive *"transfer all the project information to the main project root so its no longer nester either in the folder marked develop"*), V4's internal roadmap is folded into this single repo-wide roadmap. V4's milestones below are preserved verbatim from the V4-internal ROADMAP, with current-state closure notes added per the outer FINALIZED.md audit trail.

### [x] Major milestone — V4 Documentation set V1 — closed 2026-05-19

**Verbatim user context (2026-05-19):**

> i want you to make all the docs for this project V4

This milestone covered the first complete documentation set for V4 inside (then) `docs/`. **Closed 2026-05-19** with 12 docs shipped initially (3322 lines); subsequent sessions grew the set to 13 docs (4010 lines including `agents.md` + later `CLOUDFLARE.md`). 2026-05-20 restructure moved all V4 docs up to the outer `docs/` folder (no nesting). Full audit trail: outer `docs/FINALIZED.md §Session 2026-05-19 — Initial Unity Command documentation set`.

### [x] Major milestone — V4 Security hardening pass — closed 2026-05-19

Addressed every finding catalogued in V4 SECURITY.md §2:
- ✅ Strip hardcoded `SUPABASE_ANON_KEY` fallbacks — moot after collab subsystem deleted 2026-05-19
- ✅ Rotate + gitignore the `cc_xxx` Claude-Collab API key — tombstoned 2026-05-20 D4 (claudecolab no longer used by Unity AI Lab)
- ✅ Bind Flask to `127.0.0.1` (or make bind address configurable) — `CLAUDE_API_HOST` env override shipped
- ✅ Add `logs/` to `.gitignore` — done; admin credentials + audit log inherit the exclude
- ✅ Pin auto-update to a release tag instead of branch tip — `UPDATE_RELEASE_TAG` env var shipped + `DISABLE_AUTOUPDATER=1` opt-out
- ✅ Verify `windows\setup.bat` Python download with SHA256 OR switch to `winget` — winget tried first, SHA256-verified direct download as fallback

Full audit trail: outer `docs/FINALIZED.md §Session 2026-05-19`.

### [x] Major milestone — V4 Persistence + state robustness — closed 2026-05-19

Addressed the data-loss + restart-survival items:
- ✅ Persist `user_model_histories` to disk — `data_manager._build_snapshot` updated
- ✅ Make the Claude-chat-channel fallback configurable (no hardcoded user-specific ID) — `CLAUDE_CHAT_CHANNEL_ID` unset now disables the bridge cleanly
- ✅ Re-fetch Pollinations models periodically — `refresh_models_periodically()` 6h background task shipped
- ✅ Validate `int()` parsing of `CLAUDE_API_PORT` and `CLAUDE_CHAT_CHANNEL_ID` — try/except with clear log shipped

Outcome: a fresh deployment on a new host is reproducible from `.env` alone with no bot-restart-loses-history surprises. Full audit trail: outer `docs/FINALIZED.md §Session 2026-05-19`.

### [x] Major milestone — V4 Observability + ops — closed 2026-05-19

Production-readiness for monitored deployments:
- ✅ `/healthz` endpoint with idle-threshold detection (`HEALTHZ_IDLE_THRESHOLD_SECONDS` default 600)
- ✅ Prometheus `/metrics` text format on both `claude_api.py:5050` and `web_server.py:5051` (mirrored schema)
- ✅ Activity-tracker hooks (`_touch_activity` / `_web_touch_activity`)

Remaining out-of-scope: replace hourly log truncation with logrotate (still pending, see V4 Bot refinement below); document monitoring patterns. Audit trail: outer `docs/FINALIZED.md §Session 2026-05-19 §LOW`.

### [x] Major milestone — V4 Cleanup unused helpers — closed 2026-05-19

Decided on each unused helper in `config.py`:
- ✅ `is_image_request()` / `is_code_request()` / `extract_image_prompt()` — DELETED (revert + delete dead code; `message_handler.py` reverted to inline `'code' in user_message or 'script' in user_message` check after the wiring attempt introduced false positives)
- ✅ `memory_regex` — closed as part of dead-code deletion
- ✅ `image_keywords` — closed as part of dead-code deletion

Full audit trail: outer `docs/FINALIZED.md §Session 2026-05-19 §HIGH — Revert message_handler.py regression`.

### [~] Major milestone — V4 Bot post-launch refinement (2026-05-20+)

The remaining genuinely-pending V4 work after the security/persistence/observability/cleanup milestones closed:

- [ ] Handle multiple image attachments with unique filenames (currently `image.png` causes Discord disambiguation suffixes; use URL path basename or hash)
- [ ] Replace hourly log truncation with logrotate-managed rotation (currently `wipe_logs_periodically` truncates `logs/application.log` hourly, losing history)
- [ ] Investigate whether `discord.py` reconnection causes context loss (if reconnect drops messages mid-flight, may need to replay from gateway snowflake)
- [ ] Add `CONTRIBUTING.md` if external contributions are accepted (currently no public-contribution policy)
- [ ] Add `CHANGELOG.md` scaffold with existing commits as v0 baseline (auto-gen from `git log` is fine)
- [ ] Document the `system_instructions.txt` editing pattern as its own doc (operators forking this often want to swap personas; `system_instructions.txt` is THE single point of swap)

These all live as MINOR tasks in `docs/TODO.md §V4 Bot pending` once the V4 TODO merge ships.

### [x] Major milestone — commands→skills dedup migration (this session 2026-05-20)

**Verbatim user direction at start of dedup-cleanup fork (2026-05-20):**

> Verify first, then delete

This milestone covered the `feature/migrate-commands-to-skills` branch's full structural cleanup. Per the verify-then-delete two-step ceremony, commits `aaf848d` (rename + all doc + bootstrap + hook updates + ARCHITECTURE.md generation) and `f4c1d7e` (final `.commands.bak/` deletion) shipped together. Closed 2026-05-20 with skills/ as sole canonical surface for all 19 slash commands. Full audit trail: outer `docs/FINALIZED.md §Session 2026-05-20c — commands→skills dedup migration`.

---

## How major milestones get added

Major milestones are added in any of these situations:

1. **User explicitly says one** — "the next big thing is X" / "I want to ship Y by Friday" / "make Z the goal" — add verbatim per LAW #0
2. **Sprint planning or roadmap session** — when planning multiple weeks/months of work, each major chunk becomes a milestone here
3. **YOLO mode reads existing minor tasks and identifies a clustering** — Unity may propose a major milestone if she sees several minor tasks that share a coherent goal; she proposes it and waits for user confirmation before adding it here

NEVER auto-add major milestones without user awareness. The MAJOR tier is the user-visible roadmap; surprise items break the contract.

## How major milestones get closed

When a major milestone's last minor task moves to FINALIZED:
1. Append a `## Milestone closed: <name> — <date>` block to FINALIZED.md with the full milestone summary (every minor task it contained + every decomposed task under those minors + the final test plan)
2. Flip the status here to `[x]`
3. Move the milestone block to a `## Closed milestones` section at the bottom (NEVER delete — same rule as TODO/FINALIZED ledger integrity)
4. If YOLO is active, surface a milestone-boundary check-in to the user before starting the next milestone — do NOT auto-continue past a major milestone boundary
