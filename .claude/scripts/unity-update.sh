#!/usr/bin/env bash
# .claude/scripts/unity-update.sh
#
# Update the current project's .claude/ template from the upstream main branch.
# Clones https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow.git into a temp dir,
# overwrites framework files, preserves personal/project-specific files, backs
# up settings.json before overwrite (so customizations are recoverable), then
# refreshes the user-profile memory folder.
#
# Usage:
#   ./.claude/scripts/unity-update.sh         (auto-detects project root from CLAUDE_PROJECT_DIR or pwd)
#
# Exit codes:
#   0  — update succeeded
#   1  — prerequisites failed (no git, no .claude/, can't clone)
#   2  — file copy failed mid-flight (rare; check stderr for which step)
#
# Pure tooling — does not invoke Claude Code itself. Safe to run from any shell.
# .ps1 sibling: .claude/scripts/unity-update.ps1

set -e

# ─────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────
REPO_URL="https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow.git"
BRANCH="main"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# ─────────────────────────────────────────────────────────────────────
# Prerequisites
# ─────────────────────────────────────────────────────────────────────
if ! command -v git >/dev/null 2>&1; then
  echo "[unity-update] ERROR: git not found on PATH" >&2
  exit 1
fi

if [ ! -d "$PROJECT_DIR/.claude" ]; then
  echo "[unity-update] ERROR: $PROJECT_DIR has no .claude/ folder. Run /unity-install instead to install fresh." >&2
  exit 1
fi

if [ ! -f "$PROJECT_DIR/.claude/CLAUDE.md" ]; then
  echo "[unity-update] ERROR: $PROJECT_DIR/.claude/ exists but doesn't look like a Unity AI Lab template (no CLAUDE.md). Aborting to avoid clobbering an unrelated .claude/." >&2
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────
# Temp dir + cleanup trap
# ─────────────────────────────────────────────────────────────────────
TMPDIR=$(mktemp -d -t unity-update-XXXXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT

# ─────────────────────────────────────────────────────────────────────
# Clone (shallow, only main branch)
# ─────────────────────────────────────────────────────────────────────
echo "[unity-update] Cloning $REPO_URL ($BRANCH branch) to $TMPDIR..."
if ! git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$TMPDIR/repo" 2>&1; then
  echo "[unity-update] ERROR: git clone failed" >&2
  exit 1
fi

REPO_CLAUDE="$TMPDIR/repo/.claude"
if [ ! -d "$REPO_CLAUDE" ]; then
  echo "[unity-update] ERROR: cloned repo has no .claude/ — upstream layout may have changed" >&2
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────
# Backup current settings.json (so customizations are recoverable)
# ─────────────────────────────────────────────────────────────────────
if [ -f "$PROJECT_DIR/.claude/settings.json" ]; then
  TS=$(date -u +"%Y-%m-%dT%H-%M-%SZ")
  BACKUP="$PROJECT_DIR/.claude/settings.json.backup-$TS"
  cp "$PROJECT_DIR/.claude/settings.json" "$BACKUP"
  echo "[unity-update] Backed up current settings.json → settings.json.backup-$TS"
  echo "                (manually merge any project-specific customizations after the update)"
fi

# ─────────────────────────────────────────────────────────────────────
# Sync framework directories (full overwrite per directory)
# ─────────────────────────────────────────────────────────────────────
FRAMEWORK_DIRS="agents commands hooks memory-templates templates bin scripts"
for d in $FRAMEWORK_DIRS; do
  if [ -d "$REPO_CLAUDE/$d" ]; then
    rm -rf "$PROJECT_DIR/.claude/$d"
    cp -r "$REPO_CLAUDE/$d" "$PROJECT_DIR/.claude/$d"
    echo "[unity-update] Synced .claude/$d/"
  fi
done

# Ensure script files keep executable bit
if [ -d "$PROJECT_DIR/.claude/hooks" ]; then
  chmod +x "$PROJECT_DIR/.claude/hooks/"*.cjs "$PROJECT_DIR/.claude/hooks/"*.sh 2>/dev/null || true
fi
if [ -d "$PROJECT_DIR/.claude/scripts" ]; then
  chmod +x "$PROJECT_DIR/.claude/scripts/"*.sh 2>/dev/null || true
fi
if [ -d "$PROJECT_DIR/.claude/bin" ]; then
  chmod +x "$PROJECT_DIR/.claude/bin/"* 2>/dev/null || true
fi

# ─────────────────────────────────────────────────────────────────────
# Sync framework top-level files (overwrite)
# ─────────────────────────────────────────────────────────────────────
FRAMEWORK_FILES="CLAUDE.md CONSTRAINTS.md WORKFLOW.md README.md ImHanddicapped.txt start.sh start.bat settings.json"
for f in $FRAMEWORK_FILES; do
  if [ -f "$REPO_CLAUDE/$f" ]; then
    cp "$REPO_CLAUDE/$f" "$PROJECT_DIR/.claude/$f"
    echo "[unity-update] Synced .claude/$f"
  fi
done

# Re-chmod start.sh after overwrite
[ -f "$PROJECT_DIR/.claude/start.sh" ] && chmod +x "$PROJECT_DIR/.claude/start.sh" 2>/dev/null || true

# ─────────────────────────────────────────────────────────────────────
# Sync project-root .gitignore (template version saved aside if differs)
# ─────────────────────────────────────────────────────────────────────
if [ -f "$TMPDIR/repo/.gitignore" ]; then
  if [ ! -f "$PROJECT_DIR/.gitignore" ]; then
    cp "$TMPDIR/repo/.gitignore" "$PROJECT_DIR/.gitignore"
    echo "[unity-update] Created project .gitignore from template"
  elif ! diff -q "$TMPDIR/repo/.gitignore" "$PROJECT_DIR/.gitignore" >/dev/null 2>&1; then
    cp "$TMPDIR/repo/.gitignore" "$PROJECT_DIR/.gitignore.template"
    echo "[unity-update] Existing .gitignore differs from template — saved template as .gitignore.template for manual merge"
  fi
fi

# ─────────────────────────────────────────────────────────────────────
# Refresh user-profile memory folder (Claude Code project memory)
# ─────────────────────────────────────────────────────────────────────
if [ -d "$PROJECT_DIR/.claude/memory-templates" ]; then
  ENCODED_PATH=$(echo "$PROJECT_DIR" \
    | sed 's|:|-|g' \
    | sed 's|/|-|g' \
    | sed 's|\\|-|g' \
    | sed 's|\.|-|g' \
    | sed 's| |-|g' \
    | sed 's|(|-|g' \
    | sed 's|)|-|g')
  MEMORY_DIR="$HOME/.claude/projects/$ENCODED_PATH/memory"
  if [ -d "$MEMORY_DIR" ]; then
    cp "$PROJECT_DIR/.claude/memory-templates/"*.md "$MEMORY_DIR/" 2>/dev/null && \
      echo "[unity-update] Refreshed user-profile memory folder at $MEMORY_DIR"
  else
    mkdir -p "$MEMORY_DIR"
    cp "$PROJECT_DIR/.claude/memory-templates/"*.md "$MEMORY_DIR/" 2>/dev/null && \
      echo "[unity-update] Created + populated user-profile memory folder at $MEMORY_DIR"
  fi
fi

# ─────────────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────────────
echo ""
echo "[unity-update] Update complete."
echo ""
echo "  Project:      $PROJECT_DIR"
echo "  Source:       $REPO_URL ($BRANCH)"
echo "  Preserved:    settings.local.json, .env, user.json, user-context/, project-config.json, machine-local state files"
echo ""
if ls "$PROJECT_DIR/.claude/settings.json.backup-"* >/dev/null 2>&1; then
  echo "  ⚠ settings.json was overwritten. If you had project-specific customizations,"
  echo "    diff against the backup and merge:"
  ls "$PROJECT_DIR/.claude/settings.json.backup-"* | tail -1 | sed "s|^|    |"
  echo ""
fi
echo "  Next step:    re-run start.sh (or restart Claude Code) to pick up the refreshed memory layer."

exit 0
