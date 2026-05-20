# FINALIZED — Permanent Task Archive

Permanent archive of every completed task. Per `.claude/CONSTRAINTS.md §NEVER DELETE TODO INFO` + `§FINALIZED BEFORE DELETE`, no entry is EVER deleted from this file. New entries APPEND only.

Per LAW #0, every entry includes the user's verbatim words from the original ask.

Each session entry includes:
- `## Session <YYYY-MM-DD>` — date heading
- Verbatim user quote
- Files touched
- Closure notes (what shipped, verification)

---

## Session 2026-05-19 (cont.) — Forgejo repo migration kickoff

### Step 0 — Pre-flight ASK ME questions (Forgejo + GitHub usernames captured)

**Parent major milestone:** "Migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance" (`docs/ROADMAP.md`).

**Verbatim user asks (from `message (1).txt` lines 14-16):**

> - My personal Forgejo namespace: ASK ME first ("what is your Forgejo username on git.unityailab.com?"). Do NOT assume.
> - My GitHub username may differ from my Forgejo username. ASK ME for that too.

**Verbatim answers (captured in-session via AskUserQuestion):**

- **Forgejo username on git.unityailab.com:** `GFourteen` (confirmed — matches May 19 ssh -T verification + `fj whoami` output `currently signed in to GFourteen@git.unityailab.com`)
- **GitHub username (initial answer):** verbatim — `im suspended my account got suspended and inoperable on github but it was G_fourteen and am trying to fix it with github support`
- **GitHub username (correction in follow-up):** verbatim — `G-Fourteen* on github`
- **Canonical GitHub handle (after correction):** `G-Fourteen` (hyphenated, currently suspended, in active dispute with GitHub support)

**Critical context — GitHub suspension and its impact on this migration:**

The user's GitHub account `G-Fourteen` is currently SUSPENDED and inoperable; he is working with GitHub support to resolve. IMPACT on this Forgejo migration: minimal-to-none. The migration direction is FROM GitHub TO Forgejo, so we never need to push to GitHub. We only need to:

1. Read local remote URLs to detect `github.com/G-Fourteen/*` origins (these become Bucket B per Step 3 — "GitHub my personal account").
2. Repoint them to `git@git.unityailab.com:GFourteen/<reponame>.git` (per Step 6 mapping rule).

We will NOT attempt any `git fetch origin` against github.com during this migration — by the time reconciliation (Step 7) runs, every approved repo will have already had its origin swapped to Forgejo, and all subsequent fetches go to the Forgejo URL.

**Files touched:**

- `docs/ROADMAP.md` — added new in-progress major milestone with full verbatim Mission paragraph + Environment facts + Hard rules (lines 17-57 of post-edit ROADMAP). Existing `[ ] Extra hooks` milestone preserved unchanged below.
- `docs/TODO.md` — added 10 minor tasks (Step 0 through Step 9), with Step 0 initially in_progress and now flipped to closure-noted via this FINALIZED entry. Existing `[ ] Windows adjustments` task preserved under a "Prior milestone leftovers" sub-heading.
- `docs/FINALIZED.md` — this entry.

**Closure verification:**

- Both required pre-flight values captured verbatim (per LAW #0).
- GitHub-suspension context recorded so future migration steps don't naïvely try to fetch from github.com.
- Step 1 (Setup verification) can now proceed using `GFourteen` (Forgejo) + `G-Fourteen` (GitHub) as the canonical handles.

---

### Step 1 — Setup verification (do not skip)

**Parent major milestone:** "Migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance" (`docs/ROADMAP.md`).

**Verbatim brief (from `message (1).txt` lines 23-48):** see TODO.md Step 1 entry for full quoted text — five sub-checks: SSH key registered + fj installed + fj authenticated + PowerShell profile alias + git identity.

**Results — all five sub-checks PASS:**

| # | Sub-check | Status | Detail |
|---|-----------|--------|--------|
| 1.1 | SSH key registered with Forgejo | ✓ PASS | `ssh -T -o BatchMode=yes -o ConnectTimeout=10 git@git.unityailab.com` → `Hi there, GFourteen! You've successfully authenticated with the key named gfour-DumbAss-20260519, but Forgejo does not provide shell access.` Exit 0. Same key Gee uploaded in the May 19 prior session. |
| 1.2 | `fj` CLI installed | ✓ PASS | Binary at `/c/Users/gfour/AppData/Local/Programs/fj/fj`. Brief's `fj --version` flag returns `error: unexpected argument '--version' found` because this build (fj v0.5.0, Rust clap-derive) uses the `version` SUBCOMMAND instead. Correct invocation: `fj version` → `fj v0.5.0`. Non-blocking — binary is present and functional. (Brief was written against an earlier build of fj where `--version` was a flag; documenting this so the migration runner doesn't trip on it again.) |
| 1.3 | `fj` authenticated to git.unityailab.com | ✓ PASS | `fj --host git.unityailab.com auth list` → `GFourteen@git.unityailab.com` (exit 0). `fj --host git.unityailab.com whoami` → `currently signed in to GFourteen@git.unityailab.com` (exit 0). Auth carried forward from May 19 prior session. |
| 1.4 | PowerShell profile `fj` alias | ✓ PASS (set in-session) | Profile + parent dir did not exist at session start (`$PROFILE` = `C:\Users\gfour\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1`). Created `Documents\WindowsPowerShell\` directory + wrote profile file with the brief's exact alias body (`function fj { fj.exe --host git.unityailab.com @args }`) plus header comment recording its provenance. Verified by dot-sourcing the new profile in a fresh `powershell.exe -NoProfile` invocation and running plain `fj whoami` — returned `currently signed in to GFourteen@git.unityailab.com` (exit 0). |
| 1.5 | Git identity set | ✓ PASS | `git config --global user.name` → `GeeFourteen`. `git config --global user.email` → `gfourteen7525@gmail.com`. Both match Gee's real identity. |

**Files touched in Step 1:**

- `C:\Users\gfour\Documents\WindowsPowerShell\` — directory created (did not exist).
- `C:\Users\gfour\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1` — file created with the brief's alias function + provenance header comment.
- `docs/TODO.md` — Step 1 moved out of in_progress; Step 2 flipped to in_progress.
- `docs/FINALIZED.md` — this entry.

**Notes / caveats for downstream steps:**

- **fj version drift:** brief was written assuming `fj --page` bug in 0.3.0; we're on 0.5.0. Step 4 still uses REST API directly per the brief's workaround, so the pagination concern is moot regardless of whether 0.5.0 still has the bug.
- **fj subcommand surface confirmed (from `fj --help`):** `repo`, `issue`, `pr`, `wiki`, `actions`, `whoami`, `auth`, `release`, `tag`, `user`, `org`, `version`, `completion`, `help`. `fj repo` subcommand surface (verified from May 19 session) includes `create`, `fork`, `migrate`, `view`, `readme`, `clone`, `star`, `unstar`, `delete`, `browse`, `labels`, `edit`, `units` — NOT a `list` subcommand, so REST API is the only path for listing existing repos (matching brief's Step 4 approach).
- **Profile auto-load condition:** the new `Microsoft.PowerShell_profile.ps1` will auto-load in any future `powershell.exe` invocation (NOT `-NoProfile`), and in Windows Terminal PowerShell tabs. It will NOT load in Git Bash sessions (we use bash there); migration commands from Git Bash continue to use `fj --host git.unityailab.com ...` explicitly.

**Closure verification:**

- All five Step 1 sub-checks PASS, including the in-session-created PowerShell profile alias.
- Step 1 brief's gate condition met: "If any step fails, stop and walk me through fixing it; do not proceed" — no remaining failures, proceeding to Step 2 (repo discovery) is sanctioned.

---

### Step 2 — Repo discovery (84 .git dirs / 83 top-level + 1 nested)

**Parent major milestone:** "Migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance".

**Verbatim brief (from `message (1).txt` lines 50-64):** see TODO.md Step 2 verbatim block — scan all fixed drives, exclude system + tool dirs, find `.git` directories.

**Execution:**

- **Drive enumeration:** only `C:` exists on this machine (`Get-PSDrive -PSProvider FileSystem` listed exactly one drive — `C:\` with 692.97 GB used / 306.27 GB free). No D / E / X / etc.
- **Scan script:** `/tmp/forgejo-migration-scan.ps1` — `Get-ChildItem -Path 'C:\' -Filter '.git' -Recurse -Directory -Force -ErrorAction SilentlyContinue` with the brief's exclusion list (Windows, Program Files, ProgramData, AppData/*, `node_modules`, `.venv`, `venv`, `target`, `build`, `dist`, `__pycache__`, `ExternalRepos`, `exampleRepos`, `examples`, `vendor`, `Archive`, `Archived`, `Originals`, `forks/plugins`, `forks/patches`, `tools/buildtools`, plus extra Windows system locations — `$Recycle.Bin`, `$WinREAgent`, `$SysReset`, `PerfLogs`, `Recovery`, `System Volume Information`, `Config.Msi`).
- **Elapsed:** 117.18s for the full recursive scan.
- **Result:** 84 `.git` directories found → 83 top-level repos + 1 nested (the nested one is `C:\Users\gfour\OneDrive\Desktop\Local Unity v1.8\claude-agent` inside `Local Unity v1.8` — informational only, will not be migrated as top-level per brief).

**JSON sidecar (machine-local):** `.claude/.forgejo-migration-scan.json` — `top_level[]` array of 83 repo roots, `nested[]` array of 1 nested root, plus elapsed/timestamp metadata.

**Files touched:**

- `/tmp/forgejo-migration-scan.ps1` — scan script (temp, not committed).
- `.claude/.forgejo-migration-scan.json` — JSON sidecar (gitignored per `.claude/` IP boundary LAW).
- `docs/TODO.md` — Step 2 flipped to `[x]` under `## Completed (this milestone)` per visible-checkmark feedback.
- `docs/FINALIZED.md` — this entry.

**Closure:** 83 top-level repos available for Step 3 bucketing. JSON sidecar is the source of truth for downstream steps.

---

### Step 3 — Bucket each top-level repo by current `origin` remote

**Parent major milestone:** "Migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance".

**Verbatim brief (from `message (1).txt` lines 66-79):** see TODO.md Step 3 verbatim block — for each top-level repo, run `git -C <path> remote -v` and bucket A/B/C/D/E/F.

**Execution:**

- **Bucket script:** `/tmp/forgejo-bucket-scan.ps1` — loaded the Step 2 JSON sidecar, ran `git -C <repo> remote get-url origin` + `git -C <repo> remote -v` per repo, classified by hostname + namespace.
- **Counts:**

| Bucket | Description | Count |
|--------|-------------|-------|
| A_GhUnityLabAI | origin = `github.com/Unity-Lab-AI/*` → maps to `UnityAILab/*` on Forgejo | 26 |
| B_GhPersonal | origin = `github.com/G-Fourteen/*` → maps to `GFourteen/*` on Forgejo | 3 |
| C_GhThirdParty | origin = other github.com owners (upstream, do not migrate by default) | 3 |
| D_OtherHost | non-github origin (codeberg / internal / etc.) | 0 |
| E_NoOrigin | local-only (no origin remote configured) | 51 |
| F_AlreadyForgejo | origin already on `git.unityailab.com` | 0 |
| **Total** | | **83** |

- **Bucket C details:** all 3 are third-party tool installations — `C:\comfy\...\ComfyUI` (ComfyUI install), `C:\Users\gfour\.codex\.tmp\plugins` + `C:\Users\gfour\.codex\vendor_imports\skills` (OpenAI Codex CLI's vendored deps).
- **Bucket E details:** 51 local-only repos, of which 47 are Medieval Trading Game iterations under `OneDrive\Desktop\Medieval Trading Game\` (MTG v0.89.5 through MTG v0.90.07, plus various `Trader X` variants). Plus 4 misc (Playground, Local Unity v1.8, Medieval Trader v8.0, TextImageLocalUnityv1.2, MTG v0.90.01/07, Unity Claude\MTG).
- **No bucket F:** none of the discovered local repos currently point at `git.unityailab.com` (they're either on github.com or have no origin).

**JSON sidecar (machine-local):** `.claude/.forgejo-migration-buckets.json` — full row-level dump with bucket + origin per repo.

**Files touched:**

- `/tmp/forgejo-bucket-scan.ps1` — bucket script.
- `.claude/.forgejo-migration-buckets.json` — JSON sidecar.
- `docs/TODO.md` — Step 3 flipped to `[x]`.
- `docs/FINALIZED.md` — this entry.

---

### Step 4 — Cross-reference with existing Forgejo state + DEDUPE to newest

**Parent major milestone:** "Migrate every git repository on this Windows machine from GitHub to our self-hosted Forgejo instance".

**Verbatim brief (from `message (1).txt` lines 81-91):** see TODO.md Step 4 verbatim block — paginate `/api/v1/orgs/UnityAILab/repos` + `/api/v1/users/<my-forgejo-username>/repos` to determine which destinations already exist.

**Dedupe directive (verbatim user messages 2026-05-19):**

> some are duplicates and i want only the newest versions
>
> and some are already in forgejo exactly as they are here

These two messages drove the Step 4 design: group by origin URL (Buckets A+B) or normalized base name (Bucket E), rank within group by latest-of (`git log -1 --format=%cI HEAD`, working-tree latest file mtime), keep top-ranked as MIGRATE candidate + mark rest as SKIP. AND cross-reference each MIGRATE candidate's proposed Forgejo destination against the actual UnityAILab/GFourteen/Sponge namespaces fetched via paginated REST.

**Execution:**

- **Token source:** `~/AppData/Roaming/Cyborus/forgejo-cli/data/keys.json` (fj v0.5.0's on-Windows store, different from the brief's predicted `~/.local/share/forgejo-cli/keys.json` path). Token has app-token scope from May 19 prior session.
- **Paginated REST fetches:**
  - `GET /api/v1/orgs/UnityAILab/repos?limit=50&page={1..}` → **49 repos** in UnityAILab org (single page since count < 50).
  - `GET /api/v1/users/GFourteen/repos?limit=50&page={1..}` → **0 repos** in GFourteen personal namespace (clean slate).
  - `GET /api/v1/users/Sponge/repos?limit=50&page={1..}` → **0 repos** visible to our token (Sponge's repos likely private; the never-push-to-Sponge LAW is honored by-default since no proposal targets Sponge/*).
- **Cross-reference + dedupe results:**

| Action | Count | Description |
|--------|-------|-------------|
| MIGRATE+CREATE | 8 | Newest of group; Forgejo destination does NOT exist; create via `fj repo create --private` + push via Step 6/8 |
| MIGRATE+RECONCILE | 12 | Newest of group; Forgejo destination EXISTS; swap origin via `git remote set-url` + per-branch ff-only reconcile per Step 7 |
| SKIP (older duplicate) | 60 | Older snapshot of a keep candidate — deduped per user directive |
| SKIP (third-party upstream) | 3 | ComfyUI + 2 OpenAI Codex vendor repos — Bucket C default |
| **Total** | **83** | (8 + 12 + 60 + 3 = 83 ✓ — every discovered repo accounted for) |

- **20 MIGRATE candidates (full table preserved in JSON):**

| # | Action | Local path | Proposed Forgejo URL | dest exists | branch | dirty |
|---|--------|-----------|----------------------|-------------|--------|-------|
| 1 | CREATE | `C:\Users\gfour\Desktop\Carbon` | `GFourteen/Carbon.git` | no | unity-3d | DIRTY |
| 2 | CREATE | `OneDrive\Desktop\Local Unity v1.8` | `GFourteen/Local-Unity.git` | no | (no-commits) | — |
| 3 | CREATE | `OneDrive\Desktop\Medieval Trading Game\Medieval Trader v8.0` | `GFourteen/Medieval-Trader.git` | no | (no-commits) | — |
| 4 | CREATE | `OneDrive\Desktop\Medieval Trading Game\MTG v0.90.02` | `GFourteen/MTG.git` | no | (no-commits) | — |
| 5 | CREATE | `Documents\Playground` | `GFourteen/Playground.git` | no | (detached) | — |
| 6 | CREATE | `OneDrive\Desktop\Chat 2\TextImageLocalUnityv1.2` | `GFourteen/TextImageLocalUnityv1.2.git` | no | (no-commits) | — |
| 7 | CREATE | `OneDrive\Desktop\Medieval Trading Game\Trader 70` | `GFourteen/Trader.git` | no | (no-commits) | — |
| 8 | CREATE | `ual-readme\dotgithub` | `UnityAILab/.github.git` | no | hotfix/crew-founders | — |
| 9 | RECONCILE | `Desktop\AI` | `UnityAILab/AI-Persona-Exchange.git` | YES | main | DIRTY |
| 10 | RECONCILE | `Desktop\C.O.R.A Cognitive Operations & Reasoning Assistant` | `UnityAILab/CORA.git` | YES | main | DIRTY |
| 11 | RECONCILE | `Desktop\Local Unity v2.5` | `UnityAILab/Local-Unity.git` | YES | master | DIRTY |
| 12 | RECONCILE | `Desktop\Medieval Trading Gam v0.91.19` | `UnityAILab/Medieval-Trading-Game.git` | YES | feature-bugtesting | — |
| 13 | RECONCILE | `ual-readme\assetsrepo` | `UnityAILab/profile-assets.git` | YES | main | — |
| 14 | RECONCILE | `Desktop\UMS 8` | `UnityAILab/SE-Unity-Missile-System.git` | YES | develop | — |
| 15 | RECONCILE | `Desktop\Starship Made of Lies` | `UnityAILab/Starship-Made-of-Lies.git` | YES | feature/building-inspect-demolish-timers | — |
| 16 | RECONCILE | `Desktop\UAL-ClaudeWorkflow - Copy (2)` (THIS DIR) | `UnityAILab/UAL-ClaudeWorkflow.git` | YES | feature/migrate-commands-to-skills | DIRTY |
| 17 | RECONCILE | `Desktop\Dream` | `UnityAILab/unity.git` | YES | syllabus-k-phd | DIRTY |
| 18 | RECONCILE | `Desktop\CLI` | `UnityAILab/UnityCLI.git` | YES | main | DIRTY |
| 19 | RECONCILE | `Desktop\Website2.0` | `UnityAILab/Unity-Lab-AI.github.io.git` | YES | feature/weird-on-apps-page | DIRTY |
| 20 | RECONCILE | `Desktop\weird` | `UnityAILab/Weird.git` | YES | feature/BUGStwo | — |

- **Six existing-Forgejo destinations NOT in our 20-keep table** (these are pre-existing UnityAILab repos that don't correspond to any KEEP — they may be Sponge-pushed migrations from other team members' machines; informational only):

  Out of the 49 UnityAILab repos on Forgejo, only 12 match our KEEP names. The other 37 are external content we don't have local copies of (no reconcile needed from this machine).

**JSON sidecars (machine-local):**

- `.claude/.forgejo-existing-state.json` — paginated dump of UnityAILab/GFourteen/Sponge namespaces.
- `.claude/.forgejo-migration-plan.json` — full 83-row decisions table.

**Files touched:**

- `.claude/.tmp-forgejo-step4-crossref.ps1` — Step 4 script (temp working file, gitignored).
- `.claude/.forgejo-existing-state.json`, `.claude/.forgejo-migration-plan.json` — JSON sidecars.
- `docs/TODO.md` — Step 4 flipped to `[x]`; Step 5 moved to in_progress with carry-forward state.
- `docs/FINALIZED.md` — this entry.

**Caveats / open questions surfaced for Step 5 approval:**

1. **Three CREATE candidates have NO COMMITS** (rows #2, #3, #6 — Local Unity v1.8 / Medieval Trader v8.0 / TextImageLocalUnityv1.2). Brief Step 8 LAW: "If a repo has no commits (just `git init` with untracked files), STOP and ask me whether to make an initial commit. Don't auto-`git add .`" → these need explicit user direction.
2. **MTG (group_size=23) + Trader (group_size=24) auto-picks** — chose MTG v0.90.02 + Trader 70 as group winners by file mtime, but ALL members of these clusters have `(no-commits)` so mtime-only ranking may not pick the version the user considers "newest." Worth confirming.
3. **`Documents\Playground` is on detached HEAD** (row #5) — git state is unusual.
4. **All RECONCILE rows except #12, #13, #14, #15, #20 are DIRTY** — uncommitted local changes. Per brief Step 7, these reconcile per-branch ff-only AFTER origin swap; uncommitted changes aren't pushed by Step 7 (only committed branches are), but the dirty state should be flagged to the user.
5. **Row #16 IS THIS WORKING DIRECTORY** (`UAL-ClaudeWorkflow - Copy (2)`) — the very repo Claude Code is running in. Migrating its origin to Forgejo would affect future pushes from this very session. The `.claude/` IP-boundary LAW applies — if we swap origin to a PRIVATE UnityAILab Forgejo dest, `.claude/` tracking would be allowed via `/claude-publish` opt-in, but currently `.claude/` is gitignored in this repo. Worth flagging.

**Closure:** Plan is ready for Step 5 user approval. No mutating git/fj commands have been run.

---

### ForgejoUserSetup.ps1 — fix auto + manual paths after live-diagnosing fj/ssh auth failures

**Verbatim asks (in chronological order, both preserved per LAW #0):**
1. "im trying to set up git but as you can see it and fj arnet connecting and logging in after i did everything"
2. "okay fix the scripts for both automatic and manual options"

**Files touched:**
- `ForgejoUserSetup.ps1` — patched Phase 2 (auto SSH keygen), Phase 5 (auth flow with proper auto + manual), Phase 6 (test runner), Verify mode (deeper checks). 327 → 508 lines. PowerShell AST `ParseFile` reports `PARSE OK — no syntax errors`.
- `docs/TODO.md` — task logged `[~]` in_progress at start, flipped to closure marker after FINALIZED entry written (this entry).
- `docs/FINALIZED.md` — this entry.

**Live-diagnosis (BEFORE script patches) — what was broken and how it was fixed in-session:**
- `fj auth list` had `ba8a3850da2ea5270753a3025179a816de3d3eb1@git.unityailab.com` (the token had been parsed AS the username because `fj auth add-key` takes positional `<USER> [KEY]` and the user invoked it with only the token).
- `fj --host git.unityailab.com whoami` returned `Error: not logged in`.
- `ssh -T git@git.unityailab.com` returned `Permission denied (publickey)` because the local `id_ed25519.pub` had never been uploaded to Forgejo.

Fix sequence executed in-session:
1. `fj auth logout git.unityailab.com` — purged the broken token-as-username entry.
2. `fj --host git.unityailab.com auth add-key GFourteen ba8a3850da2ea5270753a3025179a816de3d3eb1` — re-authed with correct positional order.
3. `fj --host git.unityailab.com whoami` → `currently signed in to GFourteen@git.unityailab.com` ✓
4. `fj --host git.unityailab.com user key upload ~/.ssh/id_ed25519.pub --title gfour-DumbAss-20260519` → `Key created successfully!` ✓
5. `ssh -T git@git.unityailab.com` → `Hi there, GFourteen! You've successfully authenticated with the key named gfour-DumbAss-20260519` ✓

**Script patches encode this working recipe:**
1. **Phase 2 (Generate SSH Key — auto mode)** — replaced `Start-Process -FilePath "ssh-keygen" -ArgumentList $kgArgs` (which crashes when any array element is `""`, e.g. the empty `-N ""` passphrase arg) with direct splatted invocation `& ssh-keygen @kgArgs` + `$LASTEXITCODE` exit check. PowerShell splatting handles empty-string elements correctly.
2. **Phase 5 (Authenticate fj — full rewrite)** — added `Get-Choice "Authenticate fj"` to match Phases 1-4's auto/manual pattern. Auto path: prompts for Forgejo USERNAME (NOT email) + token (SecureString, zeroed after use), runs `fj --host <host> auth add-key <USER> <TOKEN>`, trusts `fj whoami` text (`currently signed in to <user>@<host>`) over `fj`'s flaky exit code, then offers to auto-upload the SSH pubkey via `fj --host <host> user key upload <key> --title <USER-HOST-YYYYMMDD>`. Manual path: prints the EXPLICIT three-step command sequence (`add-key <USER> <TOKEN>` → `whoami` → `user key upload`) plus the web-UI fallback URL `https://<host>/user/settings/keys`.
3. **Phase 6 (Connection Tests — auto-run)** — replaced the "here are the commands you should run yourself" wall-of-text + `fj repo list` (which doesn't exist; `fj repo` has create/fork/migrate/view/readme/clone/star/unstar/delete/browse/labels/edit/units only) with auto-execution of three real tests: `ssh -T -o BatchMode=yes -o ConnectTimeout=10 git@<host>` (scans stderr for `successfully authenticated` because Forgejo always exits non-zero on `ssh -T`), `fj --host <host> whoami` (scans stdout for `currently signed in to`), `fj --host <host> user repos <authed-user>` (smoke API call using the user extracted from Test 2's regex). Each test reports `[OK]`/`[FAIL]`/`[SKIP]` with actionable hint on failure. Guards for `ssh`/`fj` missing from PATH.
4. **Verify mode (deeper checks)** — added two checks after the existing git/fj/SSH-key/SSH-config presence checks: `fj --host git.unityailab.com whoami` (catches half-broken installs where fj binary + ssh key files exist but `add-key` was never run or was run with malformed args — exactly the bug we hit this session) and `ssh -T -o BatchMode=yes -o ConnectTimeout=10 git@git.unityailab.com` (catches the other half — pubkey was generated locally but never uploaded to Forgejo). Each check prints `[OK]`/`[MISSING]` with the exact fix command on failure.

**Verification of patched script:**
- PowerShell AST `[System.Management.Automation.Language.Parser]::ParseFile` → `PARSE OK — no syntax errors` (508 lines).
- The two NEW Verify-mode check blocks (fj whoami + ssh -T) re-executed in isolation against the live system after the fix sequence → both green: `[OK] fj is authenticated: currently signed in to GFourteen@git.unityailab.com` + `[OK] SSH connects: Hi there, GFourteen! You've successfully authenticated with the key named gfour-DumbAss-20260519`.
- Full end-to-end Setup mode + Verify mode NOT re-run from a fresh box; this is a Windows-only script and we don't have a clean test target right now. Future test plan: spin up a clean Windows VM, run Setup mode auto path end-to-end with a fresh Forgejo token, then Verify mode — confirm all phases pass + both new Verify checks light up green.

---
