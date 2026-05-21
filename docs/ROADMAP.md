# ROADMAP — Major Task List (High-Level Phases / Milestones)

**Tier 1 of 3 — the MAJOR task list.** Holds the high-level phases / milestones that span multiple sessions or multiple PRs. Each major item breaks down into MINOR tasks in `docs/TODO.md`, which break down further into DECOMPOSED tasks in `docs/DECOMPOSED.md`.

YOLO mode reads all three tiers on activation. The cascade rule: complete the current decomposed task → next decomposed task in the same minor → if minor is done, next minor in the same major → if major is done, surface a milestone-boundary check-in to the user → start next major unless user stops.

Status markers (same scheme as TODO.md):
- `[ ]` pending
- `[~]` in_progress
- `[x]` complete (move to FINALIZED.md immediately, never leave here)

LAW #0 reminder: every milestone description preserves the user's verbatim words.

**Three-tier cascade:** ROADMAP.md (major, this file) → TODO.md (minor) → DECOMPOSED.md (decomposed). YOLO mode reads all three and works the cascade — see `.claude/commands/yolo.md` and `.claude/WORKFLOW.md §YOLO MODE`.

> **Template-repo clean state.** UAL-ClaudeWorkflow ships as a `.claude/` template seed for downstream private Unity AI Lab projects. This live `ROADMAP.md` is intentionally empty — active milestone entries shouldn't pollute downstream installs. Downstream projects populate their own ROADMAP after the `/unity-install` (or `/unity-update`) flow seeds the `.claude/` workflow.

---

## In progress

_(none — template-repo clean state)_

---

## Pending

_(none — template-repo clean state; downstream projects populate their own ROADMAP when they begin work after `/unity-install` or `/unity-update` seeds the `.claude/` workflow into the project root)_

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
