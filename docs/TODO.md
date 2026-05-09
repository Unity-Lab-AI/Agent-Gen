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

### LAW — .claude workflow IP boundary (no public repo exposure)

**Verbatim user request (LAW #0):**

> *"We need to make some modifications, one of the big things is that we should allow installing into any project, or repo, however, we must EXPLICTLY ensure that the ENTIRE .claude workflow is NEVER commited, staged, ext. to any public repo -- we can do private repos that only are under the Unity-Lab-AI organization, NO PUBLIC REPOS EVEN UNDER THAT ORGANIZATION. This is a hard LAW that we will need to implement into the workflow, this is to safeguard proprietary intelectual property of the Unity AI Lab group (oranization is Unity Lab AI, but the group is Unity AI Lab)"* — Sponge, 2026-05-09

> *"You might need to use gh isntead of just git to check the status and give us a proper way to check and verify"* — Sponge, 2026-05-09

> *"overall sounds great and over paranoid, just what a security gating feature needs"* — Sponge, 2026-05-09 (sign-off on the four-layer enforcement plan)

**Sub-tasks (decomposed from the verbatim request):**

- `[x]` **Phase 1 — LAW + docs foundation.** Add new LAW body to `.claude/CONSTRAINTS.md` ("LAW — .CLAUDE WORKFLOW IP BOUNDARY: NO PUBLIC REPO EXPOSURE"). Add one-liner to `.claude/CLAUDE.md` LAW INDEX. Create `memory-templates/feedback_claude_ip_boundary.md`. Add pointer to `memory-templates/MEMORY.md`. Zero behavior change yet — foundation only. _Shipped in commit `0070b19` — also added `WORKFLOW.md §CLAUDE IP BOUNDARY ENFORCEMENT` so the cross-reference from CONSTRAINTS.md resolves cleanly._
- `[x]` **Phase 2 — Enforcement hook.** Create `.claude/hooks/pre-tool-public-repo-guard.cjs` (+ `.sh` fallback). PreToolUse:Bash matcher. Intercepts `git add` / `git commit` / `git push` for `.claude/` paths. Uses `gh repo view --json visibility,owner` for ground-truth. Multi-remote scan — any non-private-Unity-Lab-AI remote blocks. 60s session-cache. Register in `.claude/settings.json`. Update `.claude/agents/hooks.md`. _Smoke-tested: PASS on private Unity-Lab-AI remote (this repo), BLOCK on PUBLIC remote (torvalds/linux verification), PASS on no-remote (local-only). Cache file written correctly at `~/.claude/repo-visibility-cache.json`. Both `.cjs` and `.sh` fallback verified. WORKFLOW.md §HARNESS LAYER table updated to include hook 5b, side-effects table extended for the visibility cache. CLAUDE.md QUICK REFERENCE entry added._
- `[~]` **Phase 3 — Install-time gitignore add.** Update `.claude/scripts/unity-install.sh` + `.ps1` to auto-append `.claude/` to target's `.gitignore` (idempotent, with comment explaining the LAW). Update `.claude/commands/unity-install.md` to document the new behavior.
- `[ ]` **Phase 4 — Opt-in publish command.** Create `.claude/commands/claude-publish.md` — operator-driven opt-in to remove `.claude/` from gitignore IF and ONLY IF gh confirms `visibility=PRIVATE` AND `owner.login=Unity-Lab-AI`. Add quick-ref to `.claude/CLAUDE.md`. Cross-ref in `.claude/WORKFLOW.md`.

**Why (proprietary IP safeguard per Sponge):** The `.claude/` workflow is the proprietary intellectual property of the Unity AI Lab group (organization = Unity Lab AI on GitHub as `Unity-Lab-AI`; group = Unity AI Lab — Gee / Red / Sponge / Mills). Defense-in-depth (gitignore default + Bash hook + gh visibility check + opt-in publish command) ensures the workflow cannot leak even via accidental `git add -A` on a public repo, a public fork remote, or a forgotten gitignore entry.

---

## Pending

---

## TOMBSTONES

_(none)_
