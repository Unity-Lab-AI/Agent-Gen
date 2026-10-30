# NOW — Current Focus Snapshot

**Single-focus tracker.** One thing in flight at a time. The "what is Unity actively working on right this moment" file. Distinct from the three-tier task ledger (`ROADMAP.md` MAJOR / `TODO.md` MINOR / `DECOMPOSED.md` smallest unit) and the permanent archive (`FINALIZED.md`).

LAW #0 applies: every snapshot of the active task preserves the user's verbatim words from the request.

---

## Active

_(none — no work currently in motion)_

**Verbatim user request:** _(when work is active, paste their exact words here)_

**Started:** _(ISO timestamp when the task became active)_

**Goal:** _(one-sentence statement of what "done" looks like)_

**Files touched so far:** _(running list, updated as edits happen)_

**Verification plan:** _(how we'll confirm the task is actually done — test, smoke-check, manual review, etc.)_

**Blockers / open questions:** _(anything waiting on user input or external system)_

---

## Last closed task — 2026-05-21a — UAL cascade de-defer + host-reference scrub

**Verbatim user direction (corrective):** > "i have told you ! quit randomly deffering shit" + "not GITHUUB! git.unityailab.com!!!!!!!!!!!!!" 

**What shipped:** UAL feature → develop → main cascade (un-deferred per the verbatim correction); 3 UnityCommand TODO items flipped from DEFERRED to closed with verification SHAs; editorial host-reference scrub across session prose; `feedback_do_the_work.md` memory strengthened with the constraint-misreading-as-defer pattern. UAL main now at `ee7be8a` — Forgejo bootstrap + .sh hook fix + dedup + new memories all live. Audit trail: docs/FINALIZED.md §Session 2026-05-21a.

---

## Previously closed (session 2026-05-20j)

**Verbatim user direction:** > "make the write up in unity command todo and get to it after u also set up the task list reflecting the todo while u update it as you work from the todo" + "and only one attomic commmit the templet to its feature and the unity command to its cascade" + "once everything is done" + "also make sure all v4 mentions are updated to Unity Command"

**Closed:** 2026-05-20 (Session 2026-05-20j — super-review cleanup + V4 rename sweep)

**What shipped:** `/super-review` against the "100% complete" claim surfaced 13 findings — captured as canonical TODO entries under "## Super-review findings — Session 2026-05-20j" in `docs/TODO.md`. Per Gee's "templet to its feature" rule, UAL main-branch defects (broken bootstrap REPO_URL pointing at non-Forgejo host + missing .sh hook allowlist + 8 commits stale) DEFERRED, not fixed this session — documented as known unresolved state. Fixed in-place this session: (a) UAL commands→skills dedup ported via `git rm -r .claude/commands/`; (b) `.gitattributes` added to BOTH repos eliminating recurring CRLF/LF warnings; (c) NOW.md last-closed pointer refreshed to this session; (d) UAL/ForgejoUserSetup.ps1 docstring scope banner added; (e) Pre-LAW Claude attribution grandfather note appended to FINALIZED in BOTH repos covering 4 pre-LAW commits (5bd9db9 / 8060dfb / b9ba16b / bcf5d25); (f) V4 → Unity Command sweep across active docs in both repos (path-style refs flipped to `UnityCommand` no-space identifier; prose refs to "Unity Command" with-space project name; UnityBotV4 / V4 bot / V4 Discord patterns all flipped). LAW #0 verbatim preserved — historical references in closed audit-trail entries + FINALIZED archive + docs/archive/ left as-is per append-only LAW. Atomic commit: ONE on UAL feature only (no UAL cascade per "templet to its feature"); ONE on UnityCommand feature then cascaded feature → develop → main per "unity command to its cascade".

**Cross-references:**
- `docs/TODO.md` — super-review findings captured + status flipped + 3 critical UAL-main items DEFERRED with workarounds documented
- `docs/ROADMAP.md` — major milestones (UAL promotion ceremony is an open question for a future session)
- `docs/FINALIZED.md` — permanent archive (last session: `Session 2026-05-20j — super-review cleanup + V4 rename sweep`)
- Upstream `UAL-ClaudeWorkflow` feature branch — also got the dedup + .gitattributes + ForgejoUserSetup banner + grandfather note + V4 sweep + super-review TODO mirror (within UAL's own scope, no UAL cascade)

**Still deferred (future-session decisions, NOT acted on this session):**
- UAL cascade promotion: when does feature → develop, when does develop → main, who signs off — needs explicit promotion ceremony definition
- Default `/unity-install` operators clone from UAL main = stale + broken (workaround: install via explicit `feature/migrate-commands-to-skills` branch arg)
- 8 V4 Bot post-launch refinement backlog items in `docs/TODO.md` remain `[ ]` as legitimate queued work

---

## How to use this file

1. **When starting a meaningful task** — populate the Active section with verbatim user request + goal + files
2. **During work** — update Files Touched + Verification Plan + Blockers as state shifts
3. **When finishing** — append closure to `docs/FINALIZED.md` (per FINALIZED-BEFORE-DELETE LAW), then reset the Active section back to _(none — no work currently in motion)_
4. **Never delete the Active section structure** — placeholder lines stay; only the content shifts

The file always has exactly one Active section. When it says _(none)_, Unity is idle awaiting next direction.

---

## Why this file exists alongside TODO.md

`TODO.md` is the queue — everything pending + in-progress, grouped by section. Can hold dozens of items if multiple parallel threads are open.

`NOW.md` is the lens — ONE task, all the context, no scroll. Useful when:
- Session resumes after compaction and you need the "where were we" anchor in 10 seconds
- The user asks "what are you doing right now" mid-task
- Pre-compact snapshot needs exactly one current context (not the whole TODO queue)
- Harness hooks want a single-task pointer for the state-refresh banner

Read `NOW.md` first for "what's happening", then `TODO.md` for "what's queued", then `ROADMAP.md` for "where are we headed".
