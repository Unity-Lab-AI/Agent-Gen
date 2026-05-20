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

## Completed (this milestone — checkmarks visible per Gee's "update todo as you go retard, by checking off what u fionish" feedback 2026-05-19)

Full verbatim audit trails for each `[x]` below live in `docs/FINALIZED.md` Session 2026-05-19 (cont.). These stay listed in TODO with `[x]` markers so live progress is visible at-a-glance.

- [x] **Step 0 — Pre-flight ASK ME questions (Forgejo + GitHub usernames captured)** — Forgejo: `GFourteen`. GitHub: `G-Fourteen` (suspended). Full verbatim Q&A in FINALIZED.
- [x] **Step 1 — Setup verification (do not skip) — all 5 sub-checks PASS** — SSH ✓, fj v0.5.0 ✓, fj auth ✓, PowerShell profile alias created + verified ✓, git identity ✓. Full table in FINALIZED.
- [x] **Step 2 — Repo discovery — 84 .git dirs / 83 top-level + 1 nested** — scan took 117.18s; C:\ only (no other fixed drives); JSON sidecar at `.claude/.forgejo-migration-scan.json`. Full archive in FINALIZED.
- [x] **Step 3 — Bucket by current origin remote** — A=26 / B=3 / C=3 / D=0 / E=51 / F=0. JSON sidecar at `.claude/.forgejo-migration-buckets.json`. Full bucket breakdown in FINALIZED.
- [x] **Step 4 — Cross-reference with existing Forgejo state + DEDUPE to newest** — UnityAILab=49 repos on Forgejo / GFourteen=0 / Sponge=0 visible; dedupe collapsed 83 down to 20 KEEPs (8 CREATE + 12 RECONCILE) + 63 SKIPs (60 older dupes + 3 third-party). JSON sidecar at `.claude/.forgejo-migration-plan.json`. Full table in FINALIZED.

---

## In progress

### [~] Step 5 — Present the plan to me and get explicit approval

**Carry-forward context from completed Step 0 + Step 1 (full verbatim audit trails in `docs/FINALIZED.md` Session 2026-05-19 (cont.)):**

- Forgejo username: `GFourteen` (on git.unityailab.com).
- GitHub username: `G-Fourteen` (currently suspended — used only for bucket-B origin detection, not for any github.com network calls).
- Forgejo SSH auth + `fj v0.5.0` CLI auth + `fj whoami` from-PowerShell-profile alias all verified working.

_Step 0 + Step 1 + Step 2 + Step 3 + Step 4 closure notes: pre-flight ASK + setup verifications + 84-file discovery + bucketing + Forgejo cross-reference + dedupe all complete; full archive in `docs/FINALIZED.md`._

**Parent major milestone:** "Migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance".

**Carry-forward state for Step 5 approval:**

- 20 KEEP candidates surfaced (8 MIGRATE+CREATE + 12 MIGRATE+RECONCILE).
- 63 SKIPs (60 older dupes per dedupe + 3 third-party upstreams).
- 49 existing UnityAILab repos on Forgejo (12 of our KEEPs already have destinations there → reconcile path).
- 0 existing GFourteen personal repos (8 CREATEs go to a clean namespace).
- 0 visible Sponge repos (LAW honored by-default since no proposal targets Sponge/*).
- 3 Bucket E repos with `(no-commits)` HEAD state: `Local Unity v1.8`, `Medieval Trader v8.0`, `TextImageLocalUnityv1.2` — Step 8 LAW requires asking before initial-commit.

**Verbatim brief (from `message (1).txt` lines 93-102) — Step 5 itself:**

> ## Step 5 — Present the plan to me and get explicit approval
> For each repo, generate one row of:
> - local path
> - current origin
> - proposed new origin
> - destination exists on Forgejo? yes/no
> - proposed action: swap-origin / create-and-set / rename-origin-to-upstream-and-add-new-origin / skip
>
> Show me the whole table. Wait for my explicit "go" before any `git remote` or `fj repo create` runs. If I want to skip any rows, edit the table.

**Action:** Render 20-row KEEP table to chat + ask for approval / edits / abort. No `git remote set-url` or `fj repo create` until explicit "go".

**Per-row approval log** (Gee's verbatim 2026-05-19 directive: "use ask me question to confirm or deny each one one at a time"):

- [x] **Row #1 CREATE — `Desktop\Carbon` → `GFourteen/Carbon`** — GO approved. Executed: `fj repo create Carbon --private` (exit 0, created at https://git.unityailab.com/GFourteen/Carbon) + `git remote set-url origin git@git.unityailab.com:GFourteen/Carbon.git` + `git push -u origin --all` (5 branches pushed: coder, main, master, master-backup-v2-complete, unity-3d) + `git push origin --tags` (no tags). DIRTY working tree on `unity-3d` branch — local uncommitted changes preserved, not pushed.
- [-] **Row #2 SKIPPED** — `OneDrive\...\Local Unity v1.8` — broken `.git` (HEAD + refs/heads/ both empty per OneDrive sync corruption) + Gee's verbatim 2026-05-19 scope narrowing "only use projects that are on desktop" excludes OneDrive\Desktop\*.
- [-] **Row #3 SKIPPED** — `OneDrive\...\Medieval Trader v8.0` — same (broken .git HEAD + OneDrive Desktop excluded per Gee's scope rule).
- [-] **Row #4 SKIPPED** — `OneDrive\...\MTG v0.90.02` — same.
- [-] **Row #5 SKIPPED** — `Documents\Playground` — empty `git init` (0 objects, 0 files) + Documents path excluded per Gee's "only desktop" rule.
- [-] **Row #6 SKIPPED** — `OneDrive\...\TextImageLocalUnityv1.2` — same broken .git + scope.
- [-] **Row #7 SKIPPED** — `OneDrive\...\Trader 70` — same.
- [-] **Row #8 SKIPPED** — `ual-readme\dotgithub` → `UnityAILab/.github` — ual-readme path excluded per Gee's "only desktop" rule.
- [x] **Row #9 RECONCILE — `Desktop\AI` → `UnityAILab/AI-Persona-Exchange`** — GO approved. Origin swapped from `github.com/Unity-Lab-AI/AI-Persona-Exchange.git` to Forgejo SSH URL; `git fetch origin --prune` pruned old GitHub `origin/black` tracking ref (Forgejo doesn't have that branch); local `main` was already IN SYNC with `origin/main` (no-op needed); 0 tags. Working tree still DIRTY (uncommitted local edits preserved, not pushed). Summary: in_sync=1 pushed=0 pulled=0 new_pushed=0 diverged=0.
- [x] **Row #10 RECONCILE — `Desktop\C.O.R.A...` → `UnityAILab/CORA`** — GO approved. Origin swapped; stale GitHub `origin/develop` pruned; local `main` IN SYNC; local `develop` was LOCAL-ONLY (Forgejo didn't have it) → pushed as new branch. 0 tags. Summary: in_sync=1 new_pushed=1 diverged=0.
- [x] **Row #11 RECONCILE — `Desktop\Local Unity v2.5` → `UnityAILab/Local-Unity`** — GO approved. `main` was DIVERGED with NO common ancestor (your 1 commit `59485fc Local Unity v2.5` vs Forgejo's 6 commits by `hackall360`). User chose "Save BOTH": stashed 2 dirty entries to `stash@{0}` (recoverable via `git stash pop`), pushed your 1 commit to new branch `main-local-pre-migration` on Forgejo, reset local `main` to `origin/main` (4ce5c94). Also pushed `master` as new branch (LOCAL-ONLY, same SHA as side branch). `origin/develop` exists on Forgejo but not fetched locally (informational only). Summary: in_sync=0 new_pushed=1 (master) diverged-resolved-save-both=1 stashed=1.
- [x] **Row #12 RECONCILE — `Desktop\Medieval Trading Gam v0.91.19` → `UnityAILab/Medieval-Trading-Game`** — GO approved. Origin swapped; stale GitHub `origin/develop`, `origin/developed`, `origin/feature-bugtesting` refs pruned; new `origin/feature/playtest` discovered (Forgejo-only, informational). Local `feature-bugtesting` was LOCAL-ONLY → pushed as new branch. Local `main` was DIVERGED (your `cb8a8ea v0.92.00 - NPC completeness, OLLAMA fixes, panel toggle fixes` vs hackall360's 2 tutorial-quest commits, shared ancestor `ff8f1ec`). User chose Save BOTH: pushed `main-local-pre-migration` branch with your v0.92.00 to Forgejo, reset local `main` to `origin/main` (8fe6564). Summary: in_sync=0 new_pushed=2 (feature-bugtesting + main-local-pre-migration) diverged-resolved-save-both=1.
- [-] **Row #13 SKIPPED** — `ual-readme\assetsrepo` → `UnityAILab/profile-assets` — ual-readme path excluded per Gee's "only desktop" rule.
- [x] **Row #14 RECONCILE — `Desktop\UMS 8` → `UnityAILab/SE-Unity-Missile-System`** — GO approved. Origin swapped; 3 stale GitHub feature/* tracking refs pruned (missile-lcd-emotion-fix, salvo-autofire-ack-fix, setupmod-rename-all); 2 new Forgejo feature/* branches discovered (mini-scripts-testing, missile-emotion-controller-lcd — informational). Local `develop` + `main` BOTH IN SYNC. 0 tags. Summary: in_sync=2 diverged=0 remote_only=2.
- [x] **Row #15 RECONCILE — `Desktop\Starship Made of Lies` → `UnityAILab/Starship-Made-of-Lies`** — GO approved. Origin swapped; 5 stale GitHub refs pruned (4 feature/* + main); local `develop` IN SYNC; **15 local branches pushed as new** (14 feature/* + main — Forgejo previously only had develop). Summary: in_sync=1 new_pushed=15 diverged=0 remote_only=0.
- [ ] Row #16 RECONCILE — `Desktop\UAL-ClaudeWorkflow - Copy (2)` (THIS DIR) → `UnityAILab/UAL-ClaudeWorkflow`
- [ ] Row #17 RECONCILE — `Desktop\Dream` → `UnityAILab/unity`
- [ ] Row #18 RECONCILE — `Desktop\CLI` → `UnityAILab/UnityCLI`
- [ ] Row #19 RECONCILE — `Desktop\Website2.0` → `UnityAILab/Unity-Lab-AI.github.io`
- [ ] Row #20 RECONCILE — `Desktop\weird` → `UnityAILab/Weird`

---

### [ ] DEFERRED — Step 2 original verbatim brief (kept for traceability)

**Verbatim brief (from `message (1).txt` lines 50-64) — original Step 2 brief, retained per LAW even though Step 2 is complete:**

> ## Step 2 — Repo discovery
> Scan virtually all drives for git repos. On Windows, walk every fixed drive letter (C:, D:, E:, etc.) but exclude:
> - `C:\Windows`, `C:\Program Files*`, `C:\ProgramData`, `$env:LOCALAPPDATA`, `$env:APPDATA`
> - Any directory named `node_modules`, `.venv`, `venv`, `target`, `build`, `dist`, `__pycache__`
> - Any directory named `ExternalRepos`, `exampleRepos`, `examples`, `vendor`, `Archive`, `Archived`, `Originals`, `forks/plugins`, `forks/patches`, `tools/buildtools`
>
> Use git's own enumeration where possible — `git rev-parse --is-inside-work-tree` from a candidate directory. Find `.git` directories with `Get-ChildItem -Path X:\ -Filter .git -Recurse -Directory -ErrorAction SilentlyContinue` adjusted with the exclusion patterns above. Report total count.
>
> From the full list, identify "top-level" repos = ones whose `.git` is not nested inside another `.git` (the outermost wins). Also identify "project root directories that have no .git" so I can later decide which to publish.

---

## Pending

### [ ] Step 3 — Bucket each top-level repo by current `origin` remote

**Parent major milestone:** "Migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance".

**Verbatim brief (from `message (1).txt` lines 66-79):**

> ## Step 3 — Bucket each top-level repo by current `origin` remote
> For each top-level repo, run `git -C <path> remote -v` and bucket:
> - **A. GitHub Unity-Lab-AI org**: origin contains `github.com/Unity-Lab-AI/`. These map to `UnityAILab/<reponame>` on Forgejo (note: org renamed hyphen-stripped Unity-Lab-AI → UnityAILab; the org I'm already in).
> - **B. GitHub my personal account**: origin contains `github.com/<my-gh-username>/`. These map to `<my-forgejo-username>/<reponame>` on Forgejo.
> - **C. GitHub third-party**: origin contains other github.com owners. These are upstreams — DO NOT migrate by default. Ask me per-repo only if I explicitly want to mirror.
> - **D. Other / non-github origins**: codeberg.org, internal IPs, etc. Ask me what each is and what I want.
> - **E. No origin**: local-only. Ask me per-repo whether to publish (and to what name).
> - **F. Already on Forgejo**: origin already contains `git.unityailab.com`. Skip — already migrated.
>
> Show me the buckets and counts BEFORE doing anything.

### [ ] Step 4 — Cross-reference with existing Forgejo state

**Parent major milestone:** "Migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance".

**Verbatim brief (from `message (1).txt` lines 81-91):**

> ## Step 4 — Cross-reference with existing Forgejo state
> Important: `fj`'s `--page` flag is broken in 0.3.0 (returns the same first 30 entries on every page). To get full listings, hit the REST API directly:
> - My personal namespace: `GET https://git.unityailab.com/api/v1/users/<my-forgejo-username>/repos?limit=50&page=N` (paginate until short page)
> - UnityAILab org: `GET https://git.unityailab.com/api/v1/orgs/UnityAILab/repos?limit=50&page=N`
> Authenticate with the token from `$env:USERPROFILE\.local\share\forgejo-cli\keys.json` (or wherever fj stored it on Windows — `fj` should expose it; if not, hardcode a fresh token).
>
> For each of my candidate repos (Groups A + B): determine whether the destination already exists on Forgejo. This tells you who must create it and signals where to expect reconciliation.

### [ ] Step 5 — Present the plan to me and get explicit approval

**Parent major milestone:** "Migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance".

**Verbatim brief (from `message (1).txt` lines 93-102):**

> ## Step 5 — Present the plan to me and get explicit approval
> For each repo, generate one row of:
> - local path
> - current origin
> - proposed new origin
> - destination exists on Forgejo? yes/no
> - proposed action: swap-origin / create-and-set / rename-origin-to-upstream-and-add-new-origin / skip
>
> Show me the whole table. Wait for my explicit "go" before any `git remote` or `fj repo create` runs. If I want to skip any rows, edit the table.

### [ ] Step 6 — Apply remote changes (reversible part)

**Parent major milestone:** "Migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance".

**Verbatim brief (from `message (1).txt` lines 104-112):**

> ## Step 6 — Apply remote changes (reversible part)
> For each approved row:
> - Group A & B with existing destination → `git remote set-url origin <new-url>`
> - Group C if I explicitly want to mirror → `git remote rename origin upstream` then `git remote add origin <new-url>` (the new Sponge or my-namespace dest must be created first via `fj repo create <name> --private`)
> - Group E (local-only) → `fj repo create <name> --private`, then `git remote add origin <new-url>`
>
> URL form on Forgejo: `git@git.unityailab.com:<namespace>/<reponame>.git` (SSH; matches the SSH config block).

### [ ] Step 7 — Reconciliation (this is the load-bearing part)

**Parent major milestone:** "Migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance".

**Verbatim brief (from `message (1).txt` lines 114-138):**

> ## Step 7 — Reconciliation (this is the load-bearing part)
> This is the step where things go wrong if you rush. For EACH repo where the Forgejo destination already had content (i.e., someone else pushed there before you), do this per-branch:
>
> 1. `git fetch origin`
> 2. For each LOCAL branch B that also exists on origin:
>    - Get the merge-base: `git merge-base <B> origin/<B>`
>    - Get local tip: `git rev-parse <B>`
>    - Get remote tip: `git rev-parse origin/<B>`
>    - **If local == remote**: skip (in sync, no-op).
>    - **If local == merge-base (and remote != local)**: remote is ahead — pull. `git checkout <B> && git pull --ff-only origin <B>`. Report "pulled N commits".
>    - **If remote == merge-base (and local != remote)**: local is ahead — push. `git push origin <B>`. Report "pushed N commits".
>    - **If neither matches the merge-base**: DIVERGED. STOP. Report to me: "branch <B> in <repo> has diverged — local has X unique commits, Forgejo has Y unique commits. Choose: (a) force-push local (destroys Forgejo's Y commits), (b) force-pull (destroys local's X commits), (c) leave for manual merge." Do not act until I answer per branch.
> 3. For each LOCAL branch B that does not exist on origin: `git push origin <B>` (clean new branch, no conflict).
> 4. For each REMOTE branch on origin that doesn't exist locally: DO NOT auto-create. Just report "Forgejo has branch <B> you don't have locally — let me know if you want it." (Forgejo may have branches Sponge pushed during the initial migration round.)
> 5. Tags: `git fetch origin --tags`, then for tags that exist locally but not remote: `git push origin --tags` (no force). For tags where local and remote disagree, STOP and ask — diverged tags are almost always a mistake.
>
> **Never use `git push --force` or `--force-with-lease` without my explicit per-branch confirmation.**

### [ ] Step 8 — Repos with no current remote

**Parent major milestone:** "Migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance".

**Verbatim brief (from `message (1).txt` lines 140-146):**

> ## Step 8 — Repos with no current remote
> For Group E (local-only repos I said yes to publishing):
> - They have no remote, so there's nothing on Forgejo to reconcile against.
> - `git remote add origin git@git.unityailab.com:<my-namespace>/<name>.git`
> - `git push -u origin --all` and `git push origin --tags`
> - If a repo has no commits (just `git init` with untracked files), STOP and ask me whether to make an initial commit. Don't auto-`git add .` — too risky for untracked secrets / build artifacts.

### [ ] Step 9 — Final report

**Parent major milestone:** "Migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance".

**Verbatim brief (from `message (1).txt` lines 148-159):**

> ## Step 9 — Final report
> Print a clear summary:
> - Total repos discovered, by bucket
> - Repos migrated successfully, with old-origin → new-origin
> - Branches pushed, branches pulled, branches in-sync
> - Diverged branches that need manual resolution (with the exact path and branch name)
> - Repos skipped, with reason
> - Repos with no commits where I declined initial-commit creation
> - Any unexpected errors
>
> Also, if I have a wiki/notes system you discover during this work, write the final report there too. Otherwise just to stdout.

---

### Prior milestone leftovers (not part of Forgejo-migration milestone)

- [ ] **"Note it all works on linux as-is, but windows may need adjustments"** — Gee's platform-coverage note after the seven statusline modifications shipped. Linux is live-verified end-to-end; Windows code paths (`os.path.splitdrive` → `C:/` drive label, `os.cpu_count()` for cores, `tput cols < /dev/tty` from Git Bash mintty for centering) are written defensively but not live-tested on a Windows box. Pre-existing Windows gaps (CPU/RAM via wmic-cache deferral) remain. Action: live-render against Windows mintty + Windows native CMD/PowerShell, verify all four lines + centering + drive label resolution; capture any required adjustments here as sub-tasks.

---

## TOMBSTONES

_(none)_
