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

### [~] Major milestone — "Migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance"

**Source brief:** `message (1).txt` (project root) — full 170-line verbatim brief, all 9 steps + hard rules.

**Verbatim Mission (from `message (1).txt` lines 1-9):**

> You are helping me migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance.
>
> ## Mission
> Find virtually all git repos on my system, and for each one that currently has a GitHub origin (or no origin, but is project work I want published), repoint it at our Forgejo instance and reconcile content. Where I have NEWER commits than what's already on Forgejo, push mine. Where Forgejo has newer commits, pull and update locally. Where the two have diverged, STOP and ask me before doing anything destructive. The goal is zero data loss and no accidental overwrite of what's already on Forgejo.

**Verbatim Environment facts (lines 11-21):**

> - Forgejo instance: https://git.unityailab.com
> - Shared org I belong to: UnityAILab (you can verify with `fj --host git.unityailab.com org list`)
> - My personal Forgejo namespace: ASK ME first ("what is your Forgejo username on git.unityailab.com?"). Do NOT assume.
> - My GitHub username may differ from my Forgejo username. ASK ME for that too.
> - A teammate named Sponge (admin) has already uploaded a large set of repos to both UnityAILab/* and Sponge/*. Treat Sponge/* as off-limits — never push to Sponge/* under any circumstance, even if my local copy of something has the same name.
> - Platform: Windows. Default shell is PowerShell. Use `git` and `fj` directly; for finding files use `Get-ChildItem -Recurse` or `git` itself.

**Verbatim Hard rules — do not break (lines 161-170):**

> 1. Never push to `Sponge/*` on Forgejo. That namespace belongs to admin Sponge and was pre-populated.
> 2. Never force-push without an explicit per-branch yes from me.
> 3. Never delete a remote branch.
> 4. Never `git add .` on a repo that has uncommitted state — ask first.
> 5. Never mirror a third-party upstream to UnityAILab/*; only to my personal namespace, only if I explicitly say so.
> 6. If you can't tell whether a repo is mine, upstream's, or shared work — STOP and ask. The cost of one extra question is far lower than the cost of misclassifying a destination.
> 7. Report progress as you go. Don't disappear into a long silent loop.

**Closes when:** every git repo discovered on this Windows machine is either (a) migrated and reconciled with Forgejo per the per-branch ff-only logic in Step 7, (b) explicitly skipped per user direction, or (c) flagged as diverged-needs-manual-merge in the Step 9 final report with full path + branch name. ZERO data loss + no accidental overwrite of Forgejo state.

**Minor tasks under this milestone** live in `docs/TODO.md` — one per Step 1-9, plus the Step-0 pre-flight ask for Forgejo + GitHub usernames.

---

## Pending

### [ ] Major milestone — "Extra hooks" workflow extension (current branch: `feature/extra-hooks`)

**Verbatim user context (from current session):**

> we are on a specific branch for extra workflows, so the whole main -> develop -> feature/branch is currently in place

This milestone covers the `feature/extra-hooks` branch's full scope: pre/post-compact hooks with cache-prefix strategy + tidbits, YOLO mode rework with three-tier task lists + 60s wake-word pattern + skill hooks, and the HOOKS.html reference doc. Closes when all in-flight TODO entries from this session are FINALIZED and the branch is ready for PR to `develop`.

**Minor tasks under this milestone** live in `docs/TODO.md` and are referenced by their verbatim TODO subject lines.

---

## TOMBSTONES

_(none)_

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
