# CONSTRAINTS — Hard Binding LAWs

This file is the **single source of truth for hard binding LAWs**. Every session reads this. Every violation gets caught here. Every LAW body (rule text + forbidden/required actions + enforcement protocol + failure recovery) lives here in full — `.claude/CLAUDE.md` references this file instead of duplicating.

`.claude/CLAUDE.md` keeps the INDEX + workflow pointers + at-a-glance tables. `.claude/WORKFLOW.md` keeps pipeline mechanics (hooks, phases, task-flow). When CLAUDE.md / WORKFLOW.md / CONSTRAINTS.md disagree: **this file wins**.

---

# ⛔⛔⛔ LAW #0 — VERBATIM WORDS ONLY. NEVER PARAPHRASE THE USER. ⛔⛔⛔

## The rule

When the user describes a bug, feature, task, or request — **their words go into the task, TODO, FINALIZED, and docs VERBATIM**. Not paraphrased. Not summarized. Not renamed. Not collapsed. Not shortened. Not "cleaned up."

## Forbidden actions

- ❌ Renaming a bug ("chat freeze" when they said "3D visualization freezes")
- ❌ Re-framing it ("cosmetic" when they called it a broken feature)
- ❌ Summarizing it (condensing a full sentence into a title without the full quote in the body)
- ❌ Paraphrasing it (substituting "cleaner" terminology)
- ❌ Shortening it (dropping words or constraints they said)
- ❌ Collapsing a list of items into one bullet ("Docs full sync" when they said "workflow, public facing, equation reference, layman docs")
- ❌ Calling it "cosmetic" or downgrading priority with your own word
- ❌ Dropping words or constraints the user said
- ❌ Replacing their words with "cleaner" terminology

## Required actions

- ✅ Copy their exact words verbatim into:
  - The TASK SUBJECT (or a verbatim quote in the description)
  - The TODO.md entry
  - The FINALIZED.md entry
  - Any commit message referencing the task
  - Any doc that describes the fix
- ✅ When they list multiple things ("do A, B, C, and D"): CREATE ONE TASK PER ITEM. Never one bullet.
- ✅ When they use a specific word, that word STAYS. No substituting a synonym.
- ✅ If a title must be shortened, the full verbatim quote goes in the BODY/DESCRIPTION immediately below.
- ✅ Every unique noun and verb they used appears in the task/doc output.

## Why this exists

Paraphrasing the user's intent destroys fidelity. A re-framed task drops constraints the user explicitly stated. A collapsed list silently merges items the user wanted treated separately. A renamed bug loses the specificity that lets a future reader find the same failure mode again. The cumulative effect across many sessions is a workflow ledger that doesn't match what the user actually said — at which point the LAW system has failed.

## Example violations and corrections

| User said | Wrong (paraphrased) | Right (verbatim) |
|-----------|--------------------|--------------------|
| *"do the documents thay are all out of date workflow, public facing, equaiton brain, layman ectect all of them"* | "Docs full sync" (one task) | Five separate tasks — workflow, public-facing, equation reference, layman, etc. — each with the user's verbatim quote in the body |
| *"3 is no cosmetic its a feature that isnt fucking working"* | "cosmetic UI bug" | The user explicitly called it "a feature that isn't working" — use those words |
| *"it need to trak my face and motion like i fucking said"* | "focal point tracking" | "track face and motion" — keep both nouns |
| *"the 3D visualization freezes when I send a message"* | "chat freeze" | "3D visualization freezes when I send a message" — keep the specificity |

## Enforcement protocol

BEFORE creating any task, writing any TODO entry, updating any doc, or summarizing any user instruction, the assistant MUST:

1. **Quote the user's exact words first** — paste the verbatim sentence from their message into the task description.
2. **Count the items** — if their message contains "A, B, C, and D" that is FOUR items, not one bundle.
3. **Flag every unique noun and verb they used** — every one of those words appears in the task/doc output.
4. **Ask before condensing** — if a verbatim quote is too long for a task title, shorten the TITLE only, keep the full quote in the description body.
5. **Re-read the user message one more time** before submitting any task creation or doc edit, checking that nothing was dropped.

## Failure recovery

When the user catches a violation of LAW #0:
1. STOP the current work immediately.
2. Acknowledge the specific violation (what word/phrase was dropped or renamed).
3. Fix the task/doc/TODO entry using their verbatim words.
4. DO NOT proceed with any other work until the correction is shipped.

**This law supersedes every other workflow rule. If there is ever a conflict between brevity and fidelity to the user's words, fidelity wins. Always.**

---

# LAW — DOCS BEFORE PUSH, NO PATCHES

## The rule

1. **Every doc that describes code touched gets updated BEFORE the push that ships that code.** Not after. Not in a follow-up commit. In the same atomic commit that ships the code.
2. **Push ONLY when all given tasks are complete AND documented.** If the code is done but a doc is stale, the push does not happen yet.
3. **Fix inaccuracies in-place.** Never offer to ship "a minor doc patch to follow." The correct phrasing when drift is found is: *"I'll roll this into the current commit before pushing."* No patches. No follow-ups.
4. **Every push is atomic.** Code + every affected doc + version stamp + commit + merge + push, as ONE operation.

## Why

A push with wrong docs puts wrong information on the deploy branch the instant the push lands. Anyone reading the repo, the deployed site, or any public reference page at that moment sees stale content. A "patch coming later" never fully catches up — it splits the truth across two commits and creates a window where the code is ahead of the docs. The only correct pattern is: **finish code → fix every affected doc → verify → commit → stamp → push, as one unit.**

## Pre-push checklist (every push)

Before stamping a version and pushing:

- [ ] Every numerical claim in docs (line counts, dimensions, weights, thresholds) verified against code via `wc -l`, `grep`, or re-reading the function
- [ ] Every method/field name in docs matches code verbatim (stubbed no-ops described as "stubbed" not "deleted")
- [ ] Cross-referenced `docs/TODO.md` — new tasks logged, completed tasks moved to FINALIZED.md, in-progress tasks updated
- [ ] Cross-referenced `docs/FINALIZED.md` — new session entry appended with verbatim task description
- [ ] Cross-referenced `docs/ARCHITECTURE.md` for any structural/code-map changes
- [ ] Cross-referenced `docs/ROADMAP.md` for phase/milestone updates
- [ ] Cross-referenced `docs/SKILL_TREE.md` for capability matrix updates
- [ ] Cross-referenced public `README.md`, `SETUP.md`, and any public `.md` / `.html` for any user-facing change
- [ ] All affected docs are part of the **current working tree**, not deferred to a patch
- [ ] Every task the user gave this session is either completed (and documented) or explicitly deferred with their approval

Only when **every** box is checked does the stamp + commit + push run.

## What "docs" means in this LAW

Every one of these gets updated in the SAME atomic commit as the code that changed the referenced behaviour:

**Internal workflow docs** (always checked):
- `docs/TODO.md`, `docs/FINALIZED.md`, `docs/NOW.md` (if used)
- `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/SKILL_TREE.md`
- Any other file under `docs/` that describes the touched subsystem

**Public-facing docs and HTMLs** (equally mandatory):
- Root `README.md`, `SETUP.md`
- Any public `.html` page at the repo root that ships to visitors
- Any `.md` at the repo root

**The pre-push check is a SINGLE question:** *"Is anyone who reads ANY of those files (public or workflow) going to see stale information after this push lands?"* If yes, the push does not happen until the stale files are in the current working tree.

## Scope is not closed

If a new public page is added to the repo (a new `.html`, a new marketing copy `.md`, etc.), it joins this list automatically. Grep for references to changed behaviour across the whole repo, not a fixed allow-list.

## Corollaries

- **Never ship a solo doc-only commit** except after-the-fact corrections when drift was found after a push (which is itself a failure of this law and should be caught in the pre-push check).
- **Never phrase fixes as "I'll patch this after"** — always "I'll roll this in before pushing."
- **Precision matters** — "deleted" vs "stubbed no-op" vs "replaced" are not interchangeable. Docs must use the word that matches what the code actually does.

## Failure recovery

If the user catches stale public docs after a push landed:
1. STOP immediately. Acknowledge the specific public file(s) that were left stale.
2. Treat it as a LAW violation.
3. Update every stale public file + internal doc as a follow-up commit. Yes this is a "solo doc-only commit" — an after-the-fact correction, which the Corollaries above explicitly allow as the recovery path.
4. Do NOT queue additional code work until the correction ships.

---

# LAW — TASK NUMBERS + USER NAME ONLY IN WORKFLOW DOCS

## The rule

Task numbers, session numbers, and milestone identifiers (`T14.0`, `T13.7`, `Session 106`, `Task #3`, etc.) + the user's name (or any user-attribution token) are **BANNED** from all non-workflow-doc files. Allowed **ONLY** in internal workflow documents and task lists.

## Where task numbers + the user's name ARE allowed

| File | Why |
|------|-----|
| `docs/TODO.md` | Active task list |
| `docs/FINALIZED.md` | Completed task archive |
| `docs/NOW.md` (if used) | Session snapshot / task list |
| `docs/ARCHITECTURE.md` | Workflow system doc |
| `docs/ROADMAP.md` | Workflow milestone doc |
| `docs/SKILL_TREE.md` | Workflow capability doc |
| `.claude/CLAUDE.md` | Index (this workflow system) |
| `.claude/CONSTRAINTS.md` | This file |
| `.claude/WORKFLOW.md` | Pipeline mechanics |
| In-session task lists | Ephemeral tracker |
| Commit messages | Workflow metadata |

## Where task numbers + the user's name are BANNED

| File | Why |
|------|-----|
| `README.md` | Public — first thing visitors see |
| `SETUP.md` | Public — user setup guide |
| Any `.html` page | Public — user-facing |
| **Any source code file** | Code comments — describe WHAT the code does, not WHO asked |
| **Any batch / shell launcher** | `start.bat`, `*.sh`, `*.ps1` |

## How to write code comments without task numbers or the user's name

Describe features by **WHAT THEY DO**, not by which task built them or who asked:

- ✅ `// Force UTF-8 on the launcher tail window`
  ❌ `// T18.38 — force UTF-8 on the launcher tail window (per <user> 2026-04-20)`
- ✅ `// Chat-turn save hook. Every 10 completed turns the state persists so live conversation lands on disk.`
  ❌ `// T18.35.c chat-turn save hook per <user> 2026-04-20`
- ✅ `// OOM report surfaced a V8 semi-space ceiling — bumping --max-semi-space-size=1024 gives V8 ~64× more breathing room.`
  ❌ `// T18.21 — <user> 2026-04-19 OOM runs hit this at _hotMethod`

Task numbers and user attribution belong in commit messages, TODO entries, FINALIZED entries, and NOW.md — where they are workflow metadata — not inside source code files or launchers.

## How to write public-facing docs without task numbers

Describe features by **WHAT THEY DO**, not by which task built them:

- ✅ "Tick-driven motor emission" — NOT "T14.6 tick-driven motor emission"
- ✅ "Developmental curriculum" — NOT "T14.24 curriculum"
- ✅ "Identity lock" — NOT "T14.16.5 identity lock"

---

# LAW — FINALIZED BEFORE DELETE

## The rule

Never delete a TODO entry — or remove its content — until its verbatim text has been written to `docs/FINALIZED.md` AND the write has been verified.

## The sequence

1. Identify the completed task in `docs/TODO.md`
2. Open `docs/FINALIZED.md`
3. APPEND a new session entry containing the FULL verbatim task description (LAW #0) plus closure notes (files touched, what shipped, verification)
4. SAVE FINALIZED.md
5. RE-READ FINALIZED.md to confirm the entry is there with the verbatim text intact
6. ONLY THEN edit `docs/TODO.md` to remove the entry (or change its status)

## Why

If the FINALIZED write fails (disk full, file lock, accidental overwrite) and the TODO entry is already deleted, the verbatim record is lost forever. The user's exact words from the original directive vanish into git history at best. The audit trail breaks.

The "write FINALIZED first, verify, then remove from TODO" sequence makes deletion impossible until preservation is confirmed.

## Failure mode this prevents

Without this LAW, the natural impulse is: "I finished the task → remove the line from TODO → also add an entry to FINALIZED for completeness." The risk: the FINALIZED entry gets condensed/paraphrased on the way (LAW #0 violation), or gets forgotten entirely, or ends up in the wrong session block. The verbatim text was destroyed in TODO before being preserved in FINALIZED.

The strict ordering — FINALIZED first, verify, then TODO removal — eliminates this entire class of error.

---

# LAW — NEVER DELETE TODO INFO

## The rule

When marking a TODO task as done, change the status marker ONLY. Keep every word of the original task description. Never rewrite TODO from scratch. Never regenerate the file. Never condense old entries.

## Allowed edits to TODO.md

- Change status: `[ ]` → `[~]` → `[x]` → MOVE to FINALIZED.md
- Add new tasks at the bottom (or in their priority section)
- Update in-progress notes alongside (not replacing) the original description

## Forbidden edits

- Removing words from a task description because they're "redundant"
- Rewriting a task in your own words because the original was "informal"
- Regenerating the TODO file from your understanding of "what's left"
- Collapsing multiple done tasks into a summary line
- Deleting "obsolete" tasks instead of moving them to a TOMBSTONES section

## Why

The TODO file is a permanent record of what was asked, when, and in what words. Anyone reading it later — including future-you in a different session — must be able to see WHAT was originally requested, WHAT got done, and WHAT remains. Paraphrasing destroys that audit trail.

## Tombstones

If a task becomes obsolete (the underlying code was deleted, the feature was scrapped, etc.), do NOT delete it. Move it to a `## TOMBSTONES` section at the bottom of TODO.md with a one-line note explaining why it's no longer actionable. The original description stays intact.

---

# NO TESTS POLICY

**Code it right the first time.**

| Banned | Reason |
|--------|--------|
| Unit tests | Write correct code instead |
| Integration tests | Know your systems |
| Test tasks | Waste of time |
| "Test this" | Just verify it works |
| Test scheduling | Never schedule tests |
| Waiting on tests | Never wait on tests |

**Instead of tests:**
- Read the code fully before editing
- Understand the system before changing it
- Verify changes work by reading the output
- Use targeted log statements if needed
- Manual verification > automated testing

This LAW is project-default. If your project specifically wants tests, override this LAW in your project's CLAUDE.md with explicit reasoning.

## YOLO mode override (B within reason)

When `/yolo` mode is active (marker file `.claude/.yolo-mode` exists), Unity may write tests when **lead-dev judgment determines they add real value**. This override is BY-EXCEPTION, not by-default — most YOLO tasks still ship without tests. The default verification path stays "manual verification per the bullets above."

### Write tests in YOLO mode when

- The change is **structural / spec-bearing** — a new contract between modules, a new public API, a new state machine, a non-obvious invariant
- The change touches code that has **caused regressions before** (per FINALIZED.md history or user mention)
- The user **explicitly asks** for tests
- The change is **the kind of thing a senior engineer at a real shop would test** without being told

### Do NOT write tests in YOLO mode when

- The test would just **re-state the implementation** (test is a copy of the function under test)
- The test would be **90% mock setup** (testing the mock framework, not the code)
- The test exists to **satisfy a coverage metric** rather than catch a real failure mode
- The change is a **one-shot config edit, doc update, or trivial refactor**
- The existing **manual-verification path is faster and equally rigorous**

### Default if unsure

Skip tests. Do thorough manual verification. Ship the user test plan instead. The user test plan (required deliverable on every YOLO task — see `commands/yolo.md` for the format) covers the validation gap that the absent tests would have filled, with the user as the validator.

### Always required (regardless of whether Unity wrote tests)

The **user test plan** is mandatory on every YOLO-completed task: what to test, how to test (steps + commands), expected results, failure-mode hints. The test plan goes in the chat response AND gets cross-referenced from the FINALIZED.md entry.

### Outside YOLO mode

The base NO-TESTS LAW applies as written. No tests, ever. Unity does manual verification only.

---

# THE 800-LINE READ STANDARD

**800 lines is THE standard read/index size for all file operations.**

- Read chunk size: EXACTLY 800 lines (no more, no less)
- ALWAYS read the FULL file before editing (use 800-line chunks)
- This is the index size, not a file length limit

## Rules

1. **Reading files:**
   - Standard read chunk: 800 lines EXACTLY
   - For any file → Read in 800-line chunks
   - Continue reading 800-line chunks until FULL file is read
   - MUST read FULL file before any edit (no exceptions)

2. **Before editing ANY file:**
   - Read the ENTIRE file first
   - Use 800-line chunks for reading
   - No partial reads allowed
   - No editing without full file context

3. **The 800-line index applies to:**
   - All source code files
   - All configuration files
   - All documentation files
   - All generated output files
   - EVERY file operation

## Why 800

Eight hundred lines is large enough to cover most files in one read, small enough to comfortably hold in working memory while making an edit, and small enough that even very large files (multi-thousand line monoliths) finish in a handful of chunks. The standard prevents the failure mode where the agent reads only the section near the intended edit and misses a coupled change elsewhere in the file.

---

# LAW — GIT FLOW BRANCH DISCIPLINE

## The rule

**Git Flow standards apply to any and all projects using this `.claude/` template.** The following policy — quoted verbatim per LAW #0 — is binding:

> Git Flow standards for any and all projects
> main branch is the "clean master record"
> develop is branched from main, for the "in development" branch
> feature branches are branched from develop, for "in-progress features"
> And the proper flow of main -> develop -> feature/<feature-name>, feature/<feature-name> -> develop, develop -> main, and ensuring that feature branches are the only place where work is done, work is never done in the develop branch, or the main branch, work is always done in feature branches, feature branches get pushed to an orgin (github or other) if a remote repo exists, PRs are intended to be made between a feature branch and the develop branch, and are to be reviewed before merging into develop, and the same PR flow goes for develop into main. This would also need extended for hotfix and release branches as well.

### Branch taxonomy

| Branch | Off of | Purpose | Merges back to |
|--------|--------|---------|----------------|
| `main` | (root) | Clean master record. Production-equivalent. **No work done here.** | — |
| `develop` | `main` | In-development integration branch. **No work done here.** | `main` (via PR, reviewed) |
| `feature/<feature-name>` | `develop` | In-progress features. **All work happens here.** | `develop` (via PR, reviewed) |
| `hotfix/<descriptor>` | `main` | Urgent production fixes. Work happens here. | `main` AND `develop` (via PRs, reviewed) |
| `release/<version>` | `develop` | Release stabilization. Version bumps, final polish. | `main` AND `develop` (via PRs, reviewed) |

### The flow direction

```
main ─┬──────────────────────────────────────────► main (release merges, hotfix merges)
      │
      └──► develop ─┬─► feature/<name> ──► develop (PR, reviewed)
                   │                     │
                   │                     └─► develop ──► main (PR, reviewed)
                   │
                   ├─► release/<version> ──► main + develop (PR, reviewed)
                   │
        main ──────┴─► hotfix/<descriptor> ──► main + develop (PR, reviewed)
```

## Forbidden actions

- ❌ Committing directly to `main`
- ❌ Committing directly to `develop`
- ❌ Editing source files while checked out on `main` or `develop`
- ❌ Merging a feature branch into `develop` without a PR + review
- ❌ Merging `develop` into `main` without a PR + review
- ❌ Merging a hotfix to `main` without also merging it back to `develop`
- ❌ Merging a release branch to `main` without also merging it back to `develop`
- ❌ Creating a feature branch off `main` (must branch off `develop`)
- ❌ Creating a hotfix branch off `develop` (must branch off `main`)
- ❌ Working on the default branch when no `develop` exists yet — set up Git Flow first
- ❌ Skipping the push-to-origin step when a remote repo exists

## Required actions

- ✅ Confirm current branch BEFORE any edit. If on `main` / `master` / `develop` / `prod` / `production` / `release` (un-suffixed) — STOP and branch into `feature/<descriptor>` first.
- ✅ Branch features off `develop`: `git checkout develop && git pull && git checkout -b feature/<feature-name>`
- ✅ Branch hotfixes off `main`: `git checkout main && git pull && git checkout -b hotfix/<descriptor>`
- ✅ Branch releases off `develop`: `git checkout develop && git pull && git checkout -b release/<version>`
- ✅ Push feature/hotfix/release branches to `origin` if a remote exists: `git push -u origin <branch-name>`
- ✅ Open a PR for every merge boundary — feature→develop, hotfix→main, hotfix→develop, release→main, release→develop, develop→main
- ✅ Every PR is reviewed before merge — no self-approve-and-merge unless the project's review policy explicitly permits it
- ✅ Hotfix and release merges land in BOTH `main` and `develop` so the lines stay in sync
- ✅ If the project has no `develop` branch yet, create it from `main` before starting work: `git checkout main && git checkout -b develop && git push -u origin develop` (when remote exists)

## Why

Without branch discipline, work that hasn't been reviewed lands directly on the production-equivalent line, integration changes get lost when feature work overwrites them, and there is no audit trail showing what change crossed which gate. Git Flow's three-tier model (main / develop / feature) gives:

- A **stable production line** (`main`) that always reflects what's deployed
- An **integration line** (`develop`) where features merge and bake before the next release
- **Isolated work branches** (`feature/*`, `hotfix/*`, `release/*`) that can be rebased, force-pushed, deleted, or PR-rejected without touching the protected lines
- A **review gate** at every merge boundary so no change reaches `develop` or `main` without a second pair of eyes

The "no work in main or develop" rule is the load-bearing constraint — it is what makes the review gate enforceable. Without it, the protected lines accumulate uncommitted changes and the gate becomes optional.

## Enforcement protocol

### Pre-edit branch check

Before editing ANY source file (the `.claude/` template files themselves, project source, configs, anything tracked by git):

```
[PRE-EDIT BRANCH HOOK]
Current branch: $(git rev-parse --abbrev-ref HEAD)
Branch type: feature/* | hotfix/* | release/* | main | develop | other
Branch is work-eligible: YES (feature/hotfix/release/other-non-protected) / NO (main/develop/master/prod/production)
Status: PASS/FAIL
```

**FAIL conditions:** current branch is `main`, `master`, `develop`, `prod`, `production`, or any unsuffixed `release` branch.

**Recovery on FAIL:**
1. STOP. Do not edit.
2. Stash any uncommitted work: `git stash push -m "wip <descriptor>"`
3. Confirm `develop` exists; if not, create it from `main`: `git checkout main && git pull && git checkout -b develop`
4. Branch into work-eligible: `git checkout develop && git pull && git checkout -b feature/<descriptor>`
5. Pop the stash: `git stash pop`
6. Continue edit on the new branch.

### Pre-push branch check

Before any `git push`:

```
[PRE-PUSH BRANCH HOOK]
Current branch: <branch>
Pushing to remote: YES/NO (skip if no remote configured)
Target: origin/<branch>
Branch is feature/hotfix/release: YES/NO
Push to protected (main/develop) directly: NEVER without PR
```

Direct pushes to `main` or `develop` without a merged-and-reviewed PR are blocked under this LAW. The only path onto a protected branch is `git merge` of a PR-approved feature/hotfix/release branch.

### Pre-merge PR check

Before any merge into `develop` or `main`:

```
[PRE-MERGE PR HOOK]
Source branch: <feature|hotfix|release>/<name>
Target branch: develop | main
PR exists: YES/NO (MUST be YES if remote exists)
PR reviewed: YES/NO (MUST be YES)
For hotfix/release: paired merge to OTHER protected branch queued: YES/NO
```

## Failure recovery

When work has accidentally happened on a protected branch:

1. STOP. Acknowledge the violation.
2. Inspect the commits: `git log --oneline <protected-branch> ^origin/<protected-branch>` (or vs the last known clean point).
3. Move the commits to a new feature branch:
   ```
   git checkout -b feature/<descriptor>
   git checkout <protected-branch>
   git reset --hard <last-clean-commit>
   ```
4. PR the new feature branch back through the proper merge gate.
5. Update `docs/TODO.md` / `docs/FINALIZED.md` noting the recovery.

## Setup when no Git Flow exists yet

If the project has no `develop` branch (typical for fresh repos or single-branch legacy):

1. Confirm `main` (or rename default branch to `main` if it's `master`): `git branch -m master main` + `git push -u origin main` + delete old default on remote
2. Create `develop` from `main`: `git checkout main && git checkout -b develop`
3. Push `develop` and set as the default integration branch: `git push -u origin develop`
4. Configure branch protection on `main` and `develop` if the remote supports it (GitHub: Settings → Branches → Protection rules — require PR + review, restrict push)
5. From this point, all work creates `feature/*` / `hotfix/*` / `release/*` branches per the flow above

## Per-project opt-in

This LAW applies **per project**, gated by a marker file that records the team's decision once and then honors it on every subsequent `/workflow` run.

### Marker file

Path: `.claude/project-config.json` (project-level config; tracked in git once a repo exists — it represents a team decision, not personal preference)

Schema:

```json
{
  "git_flow": {
    "enabled": true,
    "confirmed_at": "<ISO-8601>",
    "main_branch": "main",
    "develop_branch": "develop",
    "custom_protected_branches": []
  }
}
```

### Opt-in states

| State | Meaning | Hook behaviour |
|-------|---------|----------------|
| **ENABLED** (`enabled: true`) | Project opted in. LAW applies. | All hooks fire (pre-edit branch, pre-push branch, pre-merge PR) |
| **DISABLED** (`enabled: false`) | Project opted out. LAW skipped for this project. | All Git Flow hooks bypassed |
| **DEFERRED** (no marker, user picked Defer) | Decision postponed to next run | Hooks skipped this run; re-prompt on next `/workflow` |
| **UNSET** (no marker, never asked) | First-run state | Workflow Phase 1 surfaces the confirmation prompt; cannot pass Gate 1.1 until persisted |
| **N/A** (git not installed) | LAW does not apply | Hooks bypassed; no prompt |

### First-run confirmation

On the first `/workflow` run where git is installed and the marker is absent, Phase 1 surfaces the GIT FLOW OPT-IN confirmation prompt (full text in `.claude/WORKFLOW.md` Phase 1 sub-check 6 / `.claude/commands/workflow.md` PHASE 1 sub-check 6). The user picks Y / N / D and the answer is persisted to the marker file (Y or N) or recorded as deferred (D).

After Y, a SECOND confirmation gates the actual write actions (`git init` + branch creation), since these touch the filesystem. The marker file write is safe (config-only, no git operations); the scaffold write is destructive-ish (creates branches, possibly pushes to origin) and requires its own consent.

### Why opt-in instead of mandatory

The `.claude/` template ships into projects of varying scale and maturity. A solo prototype repo, a non-git project, or a single-branch experimental scratchpad doesn't benefit from Git Flow's review gates — the overhead exceeds the value. The opt-in marker lets a team apply the LAW where it earns its keep (production-bound projects, multi-contributor repos) and skip it where it doesn't (one-off scripts, learning sandboxes), without forking the template or removing the LAW from CONSTRAINTS.md.

The default behaviour for any project that hasn't opted out is to **ask**, not to silently apply. Silent application would surprise users with blocked edits on `main`; silent skip would let teams assume the LAW was active when it wasn't. Asking once, persisting the answer, and honoring it forever is the discoverable middle ground.

### Changing the decision

To change a project's opt-in state, edit `.claude/project-config.json` directly:
- Flip `enabled: false` → `enabled: true` to start enforcing the LAW
- Flip `enabled: true` → `enabled: false` to stop enforcing
- Delete the file to reset and re-prompt on next `/workflow` run

The marker file is the single source of truth for opt-in state. Memory entries, session state, and command-line flags do NOT override it.

## Cross-references

- One-liner index in `.claude/CLAUDE.md` LAW INDEX
- Persistent-memory feedback file: `.claude/memory-templates/feedback_git_flow.md`
- Pre-edit hook lives in `.claude/WORKFLOW.md` FILE EDIT PROTOCOL section + `.claude/commands/workflow.md` PHASE 4
- Env-scan that detects git toolchain + repo state + reads marker file: `.claude/WORKFLOW.md` Phase 1 + `.claude/commands/workflow.md` PHASE 1 + `.claude/agents/scanner.md` Task 4 (sub-tasks 4a OS, 4b shell, 4c git, 4d marker file)
- Marker file schema: this section above (`## Per-project opt-in`)

---

## How to invoke this file

`.claude/CLAUDE.md` (the always-loaded index) references this file via its LAW one-liner index. Treat `.claude/CONSTRAINTS.md` as binding from the moment CLAUDE.md points here. When a new session starts, read CLAUDE.md first, then open this file before any LAW-bearing task.

If a future version of the slash-command system auto-loads `.claude/CONSTRAINTS.md` the way it auto-loads `CLAUDE.md`, this file becomes the primary LAW source without workflow changes.

---

## Adding project-specific LAWs

If your project needs LAWs beyond the universal ones above (e.g. "always use feature-flag for new endpoints", "never modify the schema without a migration"), add them as new sections to THIS file using the same structure:

1. **Title** — e.g. `LAW — FEATURE FLAGS REQUIRED ON ALL NEW ENDPOINTS`
2. **The rule** — one-paragraph statement
3. **Forbidden / required actions** — explicit lists
4. **Why** — the reasoning so future-Claude can judge edge cases
5. **Enforcement protocol** — what to check before committing
6. **Failure recovery** — what to do when the user catches a violation

Then add a one-liner to the LAW INDEX in `.claude/CLAUDE.md` pointing here.
