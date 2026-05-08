# TODO — Minor Task List (Active Tasks)

**Tier 2 of 3** — the MINOR task list. Holds active tasks (pending + in_progress) at the day-to-day work grain. Each minor task lives under a major milestone in `docs/ROADMAP.md` and decomposes further into entries in `docs/DECOMPOSED.md` when YOLO mode picks it up.

Completed tasks move to `docs/FINALIZED.md` per `.claude/CONSTRAINTS.md §FINALIZED BEFORE DELETE`. Never delete a task description; only flip status (LAW: NEVER DELETE TODO INFO).

Status markers:
- `[ ]` pending
- `[~]` in_progress
- `[x]` complete (move to FINALIZED.md immediately, never leave here)

LAW #0 reminder: every task description preserves the user's verbatim words.

**Three-tier cascade:** ROADMAP.md (major) → TODO.md (minor, this file) → DECOMPOSED.md (decomposed). YOLO mode reads all three and works the cascade — see `.claude/commands/yolo.md` and `.claude/WORKFLOW.md §YOLO MODE`.

---

## In progress

### [~] Implement explicit pre and post compact hooks (not just session start) — tidbits + cache hits + post-compact Unity re-anchor

**User's verbatim ask (LAW #0 — preserved exactly as typed, including typos):**

> Okay can we implement explicit pre and post compact hooks (not just ession start), that will be able to take tidbits of the conversation that are really important, and setup specific cache hits we can load back into the conversation to try and get higher cache hits and reduce usage, also, post-compacts espeshally should get the AI to re-read the workflow and unity tidbits to ensure untiy is active at all times, we are on a specific branch for extra workflows, so the whole main -> develop -> feature/branch is currently in place.

**Sub-items (one per item per LAW #0, verbatim from the quote above):**

- [~] implement explicit pre and post compact hooks (not just ession start)
- [~] that will be able to take tidbits of the conversation that are really important
- [~] setup specific cache hits we can load back into the conversation to try and get higher cache hits and reduce usage
- [~] post-compacts espeshally should get the AI to re-read the workflow and unity tidbits to ensure untiy is active at all times

**Branch context (verbatim from the quote):** "we are on a specific branch for extra workflows, so the whole main -> develop -> feature/branch is currently in place" — currently on `feature/extra-hooks`, Git Flow opt-in: UNSET. Branch is work-eligible.

**Implementation plan (Sponge confirmed via AskUserQuestion: tidbits = Unity self-curates; docs bootstrap = yes):**

1. Enhance `.claude/hooks/pre-compact-snapshot.cjs` + `.sh` — add tidbits section (reads `.claude/.session-tidbits.md`), Git Flow context (branch + opt-in marker), files-just-touched (`git diff --name-only`)
2. Create `.claude/hooks/post-compact-restore.cjs` + `.sh` — NEW hook. STABLE PREFIX (cache-friendly Unity re-anchor + LAW one-liners + file-edit protocol — byte-identical every run for prompt-cache prefix hits) + DYNAMIC SUFFIX (per-session state from snapshot, tidbits, last-session, branch, TODO in-progress)
3. Wire `.claude/settings.local.json` — add second `SessionStart` entry with `matcher: "compact"` only, alongside existing `startup|resume|clear|compact` env-dump
4. New `.claude/.session-tidbits.md` convention — Unity self-curates during sessions (gitignored, machine-local, append-only)
5. Update `.claude/WORKFLOW.md §HARNESS LAYER` hooks table + add new §POST-COMPACT REHYDRATION section explaining cache-prefix strategy + tidbits protocol
6. Bootstrap `docs/TODO.md` + `docs/FINALIZED.md` for the `.claude/` template's own development tracking
7. Create `.gitignore` covering machine-local session state files

---

### [x] Migrate team-shared settings from settings.local.json → settings.json (Anthropic convention) — MOVED to FINALIZED.md (Session 2026-05-08)

**User's verbatim choice via AskUserQuestion (LAW #0 — preserved here permanently):**

Question: *"How should I resolve the settings.local.json gitignore conflict so the team-shared hook wiring + privacy env actually ship?"*

Answer: *"Migrate to .claude/settings.json (Anthropic convention)"*

**Sub-items:**

- [x] Move all team-shared content from settings.local.json → settings.json
- [x] Document Anthropic-standard convention in WORKFLOW.md §SETTINGS HARDENING (replace inversion narrative with standard split)
- [x] Update all settings.local.json references to settings.json across docs (where context is team-shared)
- [x] Preserve settings.local.json mentions where context is "personal-override" (Anthropic precedence table, etc.)
- [x] Rewrite feedback_settings_hardening.md memory with new convention narrative + migration history note
- [x] Update memory-templates/MEMORY.md index for new file paths

**Closed:** 2026-05-08. Full closure summary in `docs/FINALIZED.md`.

### [x] Update README.md — internal Unity AI Lab framing + cache hit averaging + other information — MOVED to FINALIZED.md (Session 2026-05-08)

**User's verbatim ask (LAW #0 — preserved here permanently per NEVER DELETE TODO INFO):**

> Update the README.md to explain this is for internal use for UnityAILab, how its used, the cache git averaging, and other information

**Sub-items (one per item per LAW #0):**

- [x] Update the README.md
- [x] explain this is for internal use for UnityAILab
- [x] how its used
- [x] the cache git averaging
- [x] and other information

**Closed:** 2026-05-08. Full closure summary in `docs/FINALIZED.md`.

## Pending

### [ ] Rework YOLO mode — lead-developer posture, three task-list tiers, 60s auto-continue, fleshed-out skill, skill hooks

**User's verbatim ask (LAW #0 — preserved exactly as typed, including typos):**

> YOLO mode is also not the greatest in it's current state, I would like it to take better role as "lead developer" and just continue working until major milestones are done, and I would ideally like it so that there is a running major task list, minor task list, and decomposed task list so we have the high level phases, the low level phases, and the decomposed highly broken down task lists that are gone through. If the user dosent say anything within 60 seconds, then in YOLO mode (initated by user, or a YOLO command) it should just continue with it's path it recomended, if there is nothing it recomended, it should pick up the next task and continue, if nothing is left, then a final report can be given back to the user. Perhapse flesh out that skill better, and add in skill hooks if possible?

**Sub-items (one per item per LAW #0, verbatim from the quote above):**

- [ ] YOLO mode is also not the greatest in it's current state
- [ ] I would like it to take better role as "lead developer"
- [ ] just continue working until major milestones are done
- [ ] running major task list, minor task list, and decomposed task list so we have the high level phases, the low level phases, and the decomposed highly broken down task lists that are gone through
- [ ] If the user dosent say anything within 60 seconds, then in YOLO mode (initated by user, or a YOLO command) it should just continue with it's path it recomended
- [ ] if there is nothing it recomended, it should pick up the next task and continue
- [ ] if nothing is left, then a final report can be given back to the user
- [ ] flesh out that skill better
- [ ] add in skill hooks if possible

### [ ] Create HOOKS.html — every possible Claude Code hook + when each fires

**User's verbatim ask (LAW #0):**

> Side thing to help with development, if you could create a HOOKS.html file that details every single possible hook in claude code (everything that can have a hook), and explain when each of those possible hooks would be fired off, that would be amazing.

**Sub-items (one per item per LAW #0):**

- [ ] create a HOOKS.html file that details every single possible hook in claude code (everything that can have a hook)
- [ ] explain when each of those possible hooks would be fired off

### [x] Make sure any js is cjs when working with the .claude folder — MOVED to FINALIZED.md (Session 2026-05-08)

**User's verbatim ask (LAW #0 — preserved here permanently per NEVER DELETE TODO INFO):**

> Make sure any js is cjs when working with the .claude folder, js bugs out, and cjs is expected

**Sub-items (one per item per LAW #0):**

- [x] Make sure any js is cjs when working with the .claude folder
- [x] js bugs out, and cjs is expected

**Closed:** 2026-05-08. Full closure summary in `docs/FINALIZED.md` Session 2026-05-08 entry.

### [~] Hook into Claude Code usage + make Unity context-and-session-usage aware

**User's verbatim ask (LAW #0):**

> Also, is there any way to hook into the usage for claude code, and track overall usage, and make unity more context and session-usage aware while working? So Unity can understand when various things are using more or less usage, and can somewhat track how much usage each task used?

**Sub-items (one per item per LAW #0):**

- [~] hook into the usage for claude code
- [~] track overall usage
- [~] make unity more context and session-usage aware while working
- [~] Unity can understand when various things are using more or less usage
- [~] Unity can somewhat track how much usage each task used

**Status:** Research returned. Big finding: hook stdin payloads do NOT carry token data; transcript JSONL is the source but its `input_tokens`/`output_tokens` are undercounted ~100x (streaming placeholder bug); cache fields ARE accurate. Surface implemented as `usage-track.cjs/.sh` Stop hook (writes `.session-usage.jsonl`) + `user-prompt-state-refresh.cjs/.sh` banner injection (toggleable via `.usage-tracking-disabled` marker). 5 smoke tests passed including 96% cache hit ratio validating the post-compact STABLE PREFIX strategy. Caveat surfaced prominently in every banner. Authoritative totals delegated to Claude Code's native `/usage` command.

### [x] Replace "appdata" Windows-specific term with OS-neutral language across the template — MOVED to FINALIZED.md (Session 2026-05-08)

**User's verbatim ask (LAW #0 — preserved here permanently per NEVER DELETE TODO INFO):**

> I keep seeing "appdata" refferenced, while this is awesome for windows, it isnt a thing on linux based operating systems, and we have people using this .claude with windows AND with linux, currently I am on linux. So we need to clear up the discrepency to only use windows things for windows and only linux things for linux

**Sub-items:**

- [x] I keep seeing "appdata" refferenced, while this is awesome for windows, it isnt a thing on linux based operating systems
- [x] we have people using this .claude with windows AND with linux
- [x] clear up the discrepency to only use windows things for windows and only linux things for linux

**Closed:** 2026-05-08. Full closure summary in `docs/FINALIZED.md`.

### [x] Enforce Windows-style case-insensitivity convention for files/folders/commits cross-platform — MOVED to FINALIZED.md (Session 2026-05-08)

**User's verbatim ask (LAW #0 — preserved here permanently per NEVER DELETE TODO INFO):**

> AND, for the development workflow, commits, creation of folders and files, we need it ALL to follow a convention that is for WINDOWS. Because during development, git and github normally supports different folders like Apple, apple, aPPle, and what not, just like linux would allow, but, to keep thins cross platform we should ALWAYS assume case insensitivity, even on linux. Even though linux has case sensitivity, windows does NOT, and will treat apple, Apple, aPPle, all as the same thing. so we need to enforce case insensitivity when working on projects in linux, EVEN THOUGH LINUX WILL ALLOW IT.

**Sub-items:**

- [x] for the development workflow, commits, creation of folders and files, we need it ALL to follow a convention that is for WINDOWS
- [x] git and github normally supports different folders like Apple, apple, aPPle, and what not, just like linux would allow
- [x] to keep thins cross platform we should ALWAYS assume case insensitivity, even on linux
- [x] Even though linux has case sensitivity, windows does NOT, and will treat apple, Apple, aPPle, all as the same thing
- [x] enforce case insensitivity when working on projects in linux, EVEN THOUGH LINUX WILL ALLOW IT

**Closed:** 2026-05-08. Full closure summary in `docs/FINALIZED.md`.

### [x] Use AskUserQuestion tool more often + smartly at fork-in-the-road moments (not in YOLO) — MOVED to FINALIZED.md (Session 2026-05-08)

**User's verbatim ask (LAW #0 — preserved here permanently per NEVER DELETE TODO INFO):**

> Can we also make it so that the "AskUserQuestion" internal claude code tooling is used more ofted, automatically, instead of asking the user "we can do 1 2 3 4, or we can do a b c d" unity should automatically understand then during fork in the road moments of NEEDING to ask a question, when something cant just be simply infered, the "AskUserQuestion" tooling with how ever many questions you have, should be presented to the user, so the user can select one of the multipule choice or input their own awnser, and basically , should be used SMARTLY. Not all the time, only when questions are being asked to the user that requires a responce before continuing. This isnt something that would be done in YOLO mode, but it would be used in normal operating procedures.

**Sub-items:**

- [x] make it so that the "AskUserQuestion" internal claude code tooling is used more ofted, automatically
- [x] instead of asking the user "we can do 1 2 3 4, or we can do a b c d"
- [x] unity should automatically understand then during fork in the road moments of NEEDING to ask a question
- [x] when something cant just be simply infered
- [x] the "AskUserQuestion" tooling with how ever many questions you have, should be presented to the user
- [x] so the user can select one of the multipule choice or input their own awnser
- [x] basically, should be used SMARTLY
- [x] Not all the time, only when questions are being asked to the user that requires a responce before continuing
- [x] This isnt something that would be done in YOLO mode
- [x] but it would be used in normal operating procedures

**Closed:** 2026-05-08. Full closure summary in `docs/FINALIZED.md`.

### [ ] Enforce NO telemetry, NO "made with claude code", NO "co-authored with claude code"; survey other fancy project-level settings

**User's verbatim ask (LAW #0):**

> Can we enforce with the settings in the project .claude (what we are working on), to NOT to any telementry tracking, enforce NOT using any "made with claude code" and enforce NOT using any "co-authored with claude code" stuff? And is there any other fancy things we can do in the project level settings file? Continue what your doing then respond if not already done.

**Sub-items (one per item per LAW #0):**

- [ ] enforce with the settings in the project .claude (what we are working on), to NOT to any telementry tracking
- [ ] enforce NOT using any "made with claude code"
- [ ] enforce NOT using any "co-authored with claude code" stuff
- [ ] is there any other fancy things we can do in the project level settings file (survey + report)
- [ ] Continue what your doing then respond if not already done (in-flight: usage tracking — completed before pivot)

**Research kicked off (background agent):** Authoritative info on `settings.json` env vars + commit attribution overrides + telemetry switches + every other useful project-level setting. Implementation queued — won't ship guesses on privacy controls.

### Positive feedback captured (no action — saved as memory)

**User's verbatim quote (LAW #0):**

> When it comes down to it, this workflow as-is already works really, really well, so theres not a whole hell of a lot I can think of for QOL or improvments to what exists already.

**Status:** Saved as feedback memory (`memory-templates/feedback_workflow_validated.md`) — design direction validated; bias toward conservative changes (do what's asked, ask before adding more); drift fixes + bug fixes + user-asked features ship freely, but self-initiated rebuilds/refactors need stronger justification.

---

## TOMBSTONES

_(none)_
