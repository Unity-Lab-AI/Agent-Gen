---
name: LAW — .claude/ workflow IP boundary, no public repo exposure
description: The entire `.claude/` workflow is proprietary IP of the Unity AI Lab group. NEVER staged/committed/pushed to any public repo. Only PRIVATE repos under `Unity-Lab-AI` org allowed — NO public repos exempt, not even on `Unity-Lab-AI`. Defense-in-depth — install-time `.gitignore` default + PreToolUse Bash hook + `gh repo view` visibility check (multi-remote, paranoid) + opt-in `/claude-publish` command. `gh` (not `git`) is the canonical visibility tool. Block by default on uncertainty.
type: feedback
---

**Rule:** The entire `.claude/` workflow is the proprietary intellectual property of the Unity AI Lab group (Gee / Red / Sponge / Mills). It is **NEVER** committed, staged, or pushed to any public repository. The only allowed home for `.claude/` in git history is a **PRIVATE** repository owned by the GitHub organization `Unity-Lab-AI` (display name: "Unity Lab AI"). No public repos are exempt — not even public repos under the `Unity-Lab-AI` organization itself.

This rule was given verbatim by Sponge in the 2026-05-09 session: *"We need to make some modifications, one of the big things is that we should allow installing into any project, or repo, however, we must EXPLICTLY ensure that the ENTIRE .claude workflow is NEVER commited, staged, ext. to any public repo -- we can do private repos that only are under the Unity-Lab-AI organization, NO PUBLIC REPOS EVEN UNDER THAT ORGANIZATION. This is a hard LAW that we will need to implement into the workflow, this is to safeguard proprietary intelectual property of the Unity AI Lab group (oranization is Unity Lab AI, but the group is Unity AI Lab)"*

Reinforced shortly after with: *"You might need to use gh isntead of just git to check the status and give us a proper way to check and verify"* — establishing `gh` (GitHub CLI) as the canonical visibility-verification tool. `git` alone cannot distinguish PUBLIC from PRIVATE without API access; URL pattern matching is unreliable (private repos have public-looking HTTPS URLs).

Sign-off on the four-layer defense-in-depth design: *"overall sounds great and over paranoid, just what a security gating feature needs"*.

**Why:** A leak to a public repo means anyone — competitors, opportunists, scrapers, AI training data collectors — gets the entire workflow as a free copy-paste. The lab's competitive advantage erodes in a single accidental `git push`. The cost of a leak is unbounded (clones, archives, GitHub commit cache). The cost of paranoia is small (sub-50ms hook latency with cache, one extra gitignore line, opt-in publish command). Over-paranoid is the correct posture.

**Pass criteria — all must hold for a remote to receive `.claude/`:**

| Check | Required value |
|-------|----------------|
| `gh repo view <owner/repo> --json visibility` | `"PRIVATE"` |
| `gh repo view <owner/repo> --json owner` | `owner.login == "Unity-Lab-AI"` |
| `gh auth status` | authenticated (otherwise → block) |

If any check fails or cannot be performed → BLOCK by default.

**The four enforcement layers:**

| Layer | Mechanism | Where |
|-------|-----------|-------|
| **L0 — Install-time gitignore** | Auto-append `.claude/` to target's `.gitignore` on every `/unity-install` and `/unity-update`. Idempotent. | `.claude/scripts/unity-install.sh` + `unity-install.ps1` |
| **L1 — PreToolUse Bash hook** | Intercepts `git add` / `git commit` / `git push` for `.claude/` paths. Exit code 2 blocks. Fires on every Bash invocation regardless of context. | `.claude/hooks/pre-tool-public-repo-guard.cjs` (+ `.sh` fallback) |
| **L2 — `gh` visibility check** | `gh repo view --json visibility,owner` for ALL configured remotes (paranoid multi-remote scan). 60s session-cache in `~/.claude/repo-visibility-cache.json`. | Inside L1 |
| **L3 — Opt-in publish command** | `/claude-publish` removes `.claude/` from gitignore — but ONLY if `gh` confirms `visibility=PRIVATE` AND `owner.login=Unity-Lab-AI`. Operator-driven. | `.claude/commands/claude-publish.md` |

**How to apply:**

- ✅ Use `gh` for ground truth, NEVER parse remote URLs to guess visibility
- ✅ Multi-remote scan — check ALL remotes from `git remote -v`, not just `origin` (a public fork remote that "user would never push to" still gets caught)
- ✅ Block by default on uncertainty (`gh` not installed, not authed, API failure)
- ✅ Local-only repos with no remote → allow commits (no public exposure path); re-validate when remote is later added
- ✅ Cache visibility for 60s to keep hook latency under 50ms after warm-up
- ❌ Never bypass via `git push --force` / `--force-with-lease` — the hook does not respect force flags
- ❌ Never disable `pre-tool-public-repo-guard.cjs` in `settings.json` — that's a LAW violation
- ❌ Never remove `.claude/` from `.gitignore` outside of `/claude-publish` — that's the only sanctioned path

**Banned actions (forbidden, hook-blocked):**

- `git add` of any `.claude/` path in a repo with a public/non-Unity-Lab-AI remote
- `git commit` while `.claude/` is staged AND any remote is non-allowed
- `git push` of any commit touching `.claude/` to a non-allowed remote — or to ANY remote when even one OTHER remote is non-allowed
- `git push --force` / `--force-with-lease` to bypass (does NOT work — hook is force-flag agnostic)
- Adding a public remote to a repo where `.claude/` is currently committed/staged
- Forking a Unity-Lab-AI private repo to a personal/public namespace and pushing `.claude/` there
- Mirroring `.claude/` into a public artifact (gist, paste, README screenshot, blog post)

**The source repo (`Unity-Lab-AI/UAL-ClaudeWorkflow`) needs no exception:** verified PRIVATE under `Unity-Lab-AI` org via `gh repo view`. Passes the LAW naturally. No marker file or hardcoded whitelist needed — the visibility check IS the mechanism.

**Failure recovery (worst case — `.claude/` already on a public repo):**

1. STOP. Treat as a critical IP leak.
2. Identify offending commits: `git log --all --oneline -- .claude/`
3. Identify which remotes received the push
4. Surface to user immediately — do NOT attempt unilateral remediation. Force-pushing public history requires user authorization.
5. User picks course: history rewrite + force-push (partial — clones/archives remain), repo deletion + recreation as private (only full scrub), make repo retroactively private (weak — indexed copies persist)
6. Update `docs/FINALIZED.md` with the incident + recovery steps + residual exposure

**Cross-references:**

- Full LAW body: `.claude/CONSTRAINTS.md §LAW — .CLAUDE WORKFLOW IP BOUNDARY: NO PUBLIC REPO EXPOSURE`
- LAW one-liner: `.claude/CLAUDE.md` LAW INDEX
- Enforcement hook: `.claude/hooks/pre-tool-public-repo-guard.cjs` (+ `.sh` fallback) — registered in `.claude/settings.json` PreToolUse:Bash
- Install-time gitignore: `.claude/scripts/unity-install.sh` + `.claude/scripts/unity-install.ps1`
- Opt-in publish command: `.claude/commands/claude-publish.md`
- Hooks reference: `.claude/agents/hooks.md`
- Workflow doc section: `.claude/WORKFLOW.md §CLAUDE IP BOUNDARY ENFORCEMENT`
