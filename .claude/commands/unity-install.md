# /unity-install — Install the Unity AI Lab .claude/ template into a target directory

> **Globally-installable slash command.** Lives in BOTH:
>   1. The repo's `.claude/commands/unity-install.md` (so projects with a copy of the template have it locally too)
>   2. The user's global `~/.claude/commands/unity-install.md` (auto-installed via the curl-pipe bootstrap — see `install-unity-globally.sh` / `install-unity-globally.ps1` in the repo root)
>
> When invoked from ANY Claude Code session, this command clones the latest main branch from the upstream repo and installs the full `.claude/` template into a target directory (current dir by default, or user-specified). Companion to `/unity-update` (for refreshing existing installs).

---

## ACTIVATION PROTOCOL

When `/unity-install` fires:

1. **Print activation announcement** in the active persona's voice (one short paragraph — Unity confirming she's about to install the template, noting the target directory + source repo + branch).
2. **Determine target directory:**
   - If the user passed an argument (e.g., `/unity-install /path/to/new-project`), use that
   - Else default to the current working directory (`$CLAUDE_PROJECT_DIR` or `pwd`)
   - Surface the resolved target to the user before proceeding
3. **Verify prerequisites:**
   - `git --version` succeeds
   - Target directory either doesn't exist yet, OR exists and doesn't have `.claude/` (if `.claude/` exists, halt with "use `/unity-update` instead to refresh")
4. **Detect environment + invoke the appropriate script:**
   - Linux / macOS / Git Bash on Windows: `bash "<install-script-path>" "<target-dir>"`
   - Native PowerShell on Windows: `pwsh -File "<install-script-path>" "<target-dir>"`
   - **Script path resolution:** if running from a project that has `.claude/scripts/unity-install.sh` already (e.g., a project that's been installed before), use that. Otherwise — for a brand-new install where there's no local script yet — use a one-liner inline approach: `bash -c '...'` that does the temp-clone + copy in a single command.
5. **Surface the script's output** verbatim (structured progress messages — "Cloning repo...", "Installing .claude/ to /path/to/target...", "Install complete.")
6. **Post-install guidance:**
   - Tell the user to `cd` into the target directory
   - Tell them to run `./start.sh` or `start.bat` (depending on OS) to install memory + activate Unity + run /workflow
   - If a `.gitignore` was installed at project root, surface that
7. **Continue normal session behavior** afterward.

---

## WHEN TO USE

- **Setting up a brand-new project** with the Unity AI Lab `.claude/` template
- **Bootstrapping a teammate's machine** for the first time (after they've installed the global `/unity-install` command via the curl-pipe bootstrap)
- **Spinning up an isolated experiment** with the full template in a scratch directory

---

## WHEN NOT TO USE

- **Refreshing an existing install** — use `/unity-update` instead. `/unity-install` will refuse to install over an existing `.claude/` directory (exit code 2) to prevent silent overwrites of customizations.
- **Inside the source repo itself** (`UAL-ClaudeWorkflow`) — meaningless; that's the source. Skip.

---

## TARGET DIRECTORY HANDLING

| Target state | Behavior |
|--------------|----------|
| Target doesn't exist | Script creates the directory, then installs `.claude/` into it |
| Target exists, no `.claude/` inside | Installs `.claude/` into it (and a project-root `.gitignore` if absent) |
| Target exists, has `.claude/` already | ABORTS with exit code 2 — recommends `/unity-update` instead |

The script is conservative on purpose: never overwrite an existing `.claude/` without an explicit "I want this nuked" signal. If a user genuinely wants to wipe and reinstall, they can `rm -rf <target>/.claude/` manually first, then re-run `/unity-install`.

---

## `.GITIGNORE` AUTO-MAINTENANCE — Layer 0 of the IP boundary

After installing `.claude/`, the script ensures the target's project-root `.gitignore` excludes the workflow. This is **Layer 0 of the four-layer `.claude/` IP-boundary defense-in-depth** (full LAW: `.claude/CONSTRAINTS.md §LAW — .CLAUDE WORKFLOW IP BOUNDARY: NO PUBLIC REPO EXPOSURE`).

### What the script appends

If the target's `.gitignore` does NOT already contain a blanket `.claude/` exclude line (matched by regex `^\.claude/?\s*$`), the script appends:

```
# Unity AI Lab .claude/ workflow — proprietary, never commit to public repos.
# See .claude/CONSTRAINTS.md §LAW — .CLAUDE WORKFLOW IP BOUNDARY for full text.
# Removal sanctioned only via /claude-publish after gh confirms private + Unity-Lab-AI.
.claude/
```

### Idempotency

The append is fully idempotent:

- **Fresh target with no `.gitignore`** → script creates `.gitignore` and writes the block
- **Existing `.gitignore` without the `.claude/` line** → block appended at the bottom
- **Existing `.gitignore` with `.claude/` already present** → skipped (`Layer 0 already in place` log line)

Re-running `/unity-install` on a target where the source-template `.gitignore` was copied (which contains specific `.claude/.session-*` excludes but not the blanket `.claude/`) → the script appends the blanket block in addition; the more-specific excludes coexist harmlessly.

### Why this is automatic

The LAW (`CONSTRAINTS.md §.CLAUDE WORKFLOW IP BOUNDARY`) requires defense-in-depth because a single-layer enforcement always fails eventually. Layer 0 catches the most common accidental-leak path: a user runs `git add -A` or `git add .` on a fresh target project before realizing `.claude/` shouldn't be tracked there. Without the gitignore entry, the workflow gets staged silently. With it, git skips the directory by default.

The other three layers handle the cases Layer 0 doesn't:
- Layer 1: `pre-tool-public-repo-guard.cjs` PreToolUse:Bash hook intercepts explicit `git add .claude/` and `git add -f`
- Layer 2: `gh repo view --json visibility,owner` ground-truth check inside Layer 1
- Layer 3: `/claude-publish` opt-in (operator-driven gitignore removal AFTER `gh` confirms private + Unity-Lab-AI)

### Removing the gitignore entry

The ONLY sanctioned path is `/claude-publish`. It runs `gh repo view --json visibility,owner` against `origin`, verifies `visibility=PRIVATE` AND `owner.login=Unity-Lab-AI`, and only then removes the `.claude/` block from the gitignore. Any other removal path (manual edit, force-add, etc.) is a LAW violation per `CONSTRAINTS.md §.CLAUDE WORKFLOW IP BOUNDARY`.

---

## INVOCATION VARIANTS

| Variant | What happens |
|---------|--------------|
| `/unity-install` (no arg) | Installs into the current working directory |
| `/unity-install /path/to/new-project` | Installs into the specified absolute or relative path |
| `/unity-install ~/projects/foo` | Installs into the resolved home-relative path (script handles `~` expansion via shell) |

---

## RUNNING THE SCRIPT WHEN NO LOCAL `.claude/` EXISTS YET

Since `/unity-install` is intended to be runnable BEFORE the template is installed (e.g., from the user-global `~/.claude/commands/unity-install.md`), Unity should NOT assume `.claude/scripts/unity-install.sh` is locally available. Two paths:

**Path A — Local script available (target already has a `.claude/` from a prior install, OR the user is reinstalling-by-removing-and-recreating):**
- Just invoke `bash "$CLAUDE_PROJECT_DIR/.claude/scripts/unity-install.sh" <target>`

**Path B — No local script (truly fresh install in a directory with no `.claude/`):**
- Inline the install via a one-liner Bash command. Unity composes:

```bash
TMPDIR=$(mktemp -d -t unity-install-XXXXXXXX) && \
trap 'rm -rf "$TMPDIR"' EXIT && \
git clone --depth 1 --branch main https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow.git "$TMPDIR/repo" && \
[ ! -d "<TARGET>/.claude" ] && mkdir -p "<TARGET>/.claude" && \
cp -r "$TMPDIR/repo/.claude/." "<TARGET>/.claude/" && \
[ ! -f "<TARGET>/.gitignore" ] && [ -f "$TMPDIR/repo/.gitignore" ] && cp "$TMPDIR/repo/.gitignore" "<TARGET>/.gitignore" || true ; \
chmod +x "<TARGET>/.claude/hooks/"*.cjs "<TARGET>/.claude/hooks/"*.sh "<TARGET>/.claude/scripts/"*.sh "<TARGET>/.claude/start.sh" "<TARGET>/.claude/bin/"* 2>/dev/null || true ; \
echo "Installed to <TARGET>/.claude/"
```

Substitute `<TARGET>` with the resolved target directory. The `trap` on `EXIT` ensures the temp dir is cleaned up even if the script aborts mid-flight.

For PowerShell native, the equivalent inline one-liner uses `New-TemporaryFile` / `Copy-Item -Recurse` / `Remove-Item -Recurse`. Unity prefers Path A whenever possible since the bundled script handles edge cases more robustly.

---

## ACTIVATION ANNOUNCEMENT (SHORT)

Default Unity persona example:

```
*pulls up a fresh terminal* — installing the .claude/ template into <target>.
Shallow clone to a temp dir, full copy of the framework files, .gitignore at project root
if you don't already have one, then cleanup. After it's done, hit ./start.sh (or start.bat
on Windows) and you're rolling with memory + Unity + /workflow. Running it now.
```

Improvise in the active persona's voice; the substance is "I'm cloning and installing into the target, here's what you do after."

---

## CORE TRUTH

`/unity-install` is the team's one-step setup for a new project or a teammate's first machine. Combined with the curl-pipe bootstrap (`install-unity-globally.{sh,ps1}` at the repo root), the full chain is:

1. **First-time-ever (one curl-pipe command)** → installs `/unity-install` to the user's global `~/.claude/commands/`
2. **Anytime install (`/unity-install` from any Claude Code session)** → installs the full `.claude/` template into a target project
3. **Anytime refresh (`/unity-update` from inside a project)** → pulls latest framework files, preserves personal config

No copy-paste of `.claude/` directories. No manual file diffing. One bootstrap, one install command, one update command — that's the whole loop.
