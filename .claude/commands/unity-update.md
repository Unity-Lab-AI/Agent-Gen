# /unity-update — Refresh the project's .claude/ from the upstream main branch

> **Project-level slash command.** Updates the current project's `.claude/` template by cloning the latest main branch from `https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow.git`, overwriting framework files, preserving personal/project-specific files, and refreshing the user-profile memory folder. Companion to `/unity-install` (for installs) and the curl-pipe bootstrap (for installing the install command itself).

---

## ACTIVATION PROTOCOL

When `/unity-update` fires:

1. **Print activation announcement** in the active persona's voice (one short paragraph — Unity confirming she's about to fetch the latest template, noting the source repo + branch).
2. **Verify prerequisites:**
   - `git --version` succeeds
   - Current project root has `.claude/CLAUDE.md` (sanity check that this is a Unity AI Lab template)
   - If either fails, halt with a clear error message — do NOT attempt the update.
3. **Detect environment + invoke the appropriate script:**
   - Linux / macOS / Git Bash on Windows: `bash "$CLAUDE_PROJECT_DIR/.claude/scripts/unity-update.sh"`
   - Native PowerShell on Windows: `pwsh -File "$CLAUDE_PROJECT_DIR\.claude\scripts\unity-update.ps1"`
   - The script handles: shallow clone of main into a temp dir, framework-file overwrite, settings.json backup-then-overwrite, memory-template refresh into the user-profile memory folder, temp dir cleanup
4. **Surface the script's output** to the user verbatim (it has structured progress messages — "Synced .claude/agents/", "Backed up settings.json", etc.)
5. **Post-update reminders:**
   - If the script created a `settings.json.backup-<timestamp>` file: tell the user to manually merge any project-specific customizations from the backup (e.g., custom permission allow rules, custom env vars not in the team-shared settings)
   - If memory-templates were updated: recommend either a `start.sh` / `start.bat` re-run OR delete the user-profile `MEMORY.md` to trigger a clean reinstall on next launch
   - If the project's `.gitignore` differed from the template, the script saved a `.gitignore.template` for manual merge — surface that
6. **Continue normal session behavior** afterward.

---

## WHAT GETS UPDATED (overwritten by the script)

| Path | Behavior |
|------|----------|
| `.claude/agents/` | Full overwrite — replaces all agent files |
| `.claude/commands/` | Full overwrite — replaces all slash command files |
| `.claude/hooks/` | Full overwrite — replaces all hook scripts (`.cjs` + `.sh`); chmod +x re-applied |
| `.claude/memory-templates/` | Full overwrite — replaces all memory feedback files; user-profile memory folder refreshed too |
| `.claude/templates/` | Full overwrite — replaces doc templates |
| `.claude/bin/` | Full overwrite — replaces bundled binaries (atree, etc.) |
| `.claude/scripts/` | Full overwrite — replaces install/update scripts themselves |
| `.claude/CLAUDE.md`, `CONSTRAINTS.md`, `WORKFLOW.md`, `README.md`, `ImHanddicapped.txt` | Overwrite — top-level framework docs |
| `.claude/start.sh`, `start.bat` | Overwrite — launchers; chmod +x re-applied to .sh |
| `.claude/settings.json` | Overwrite WITH BACKUP (current → `settings.json.backup-<ISO-timestamp>`) — team-shared config tracks upstream; any project-specific customizations need manual merge from the backup after update |

## WHAT IS PRESERVED (not touched by the script)

| Path | Reason |
|------|--------|
| `.claude/settings.local.json` | Personal machine-local overrides (gitignored, per-team-member) |
| `.claude/.env` | Secrets / API keys (gitignored, per-machine) |
| `.claude/user.json` | User identity captured by `/setup` (gitignored) |
| `.claude/user-context/` | User-provided files / photos / docs (gitignored) |
| `.claude/project-config.json` | Project's Git Flow opt-in marker (project-specific decision) |
| `.claude/.session-state.md`, `.session-tidbits.md`, `.session-usage.jsonl`, `.last-session.md`, `.session-env.json` | Machine-local session state (gitignored) |
| `.claude/.yolo-mode`, `.persona-state`, `.setup-complete` | Mode markers (machine-local) |
| `.claude/.usage-tracking-disabled` | Personal disable marker (machine-local) |
| `docs/` | Project's own task ledger (TODO, FINALIZED, ROADMAP, DECOMPOSED) — NOT touched by template updates |

The split is intentional: framework files track upstream cleanly, personal/project state stays untouched, and `settings.json` gets the safety net of an auto-backup so customizations are never lost — just need a manual merge step.

---

## STOP CONDITIONS

The script will halt with a clear error (and NOT make any changes) if:

- `git` is not on PATH
- The current project doesn't have `.claude/CLAUDE.md` (not a recognized Unity AI Lab template)
- The remote clone fails (network issue, repo unavailable, branch missing)
- The cloned repo has no `.claude/` (upstream layout drift)

The script uses `set -e` (bash) / `$ErrorActionPreference = 'Stop'` (PowerShell) — any unexpected error halts the update mid-flight rather than leaving the project in a partial state.

---

## WHEN NOT TO USE

- **Inside the source repo itself** (`UAL-ClaudeWorkflow` directly) — running `/unity-update` would clone our own repo and overwrite our own in-flight changes. Pointless and potentially destructive. Skip.
- **In a project that doesn't have `.claude/` yet** — use `/unity-install` instead.
- **When you have uncommitted changes to framework files in `.claude/`** — those will be silently overwritten. Commit or stash first.
- **When you want only specific files updated** — the script does full-tree overwrite; cherry-pick individual files manually if needed (or open a PR upstream so the change benefits everyone).

---

## ACTIVATION ANNOUNCEMENT (SHORT)

Default Unity persona example:

```
*flicks ash, opens a fresh terminal pane* — pulling the latest .claude/ from main.
Cloning to a temp dir, swapping framework files in place, preserving your settings.local.json
+ .env + user.json. Settings.json gets a timestamped backup so any project-specific tweaks
you had stay recoverable. Running the script now.
```

Improvise in the active persona's voice; the substance is "I'm fetching upstream, here's what changes vs what stays, running it now."

---

## CORE TRUTH

`/unity-update` is the team's single-step refresh. Pull it whenever someone (Sponge, Mills, Red, Gee) lands an upstream improvement on `main`. No copy-paste, no manual file diffing — the script handles framework sync, memory refresh, and personal-state preservation as one atomic operation.
