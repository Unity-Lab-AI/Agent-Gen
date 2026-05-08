#!/usr/bin/env bash
# install-unity-globally.sh
#
# One-shot bootstrap: clones the Unity AI Lab template repo into a temp dir,
# copies ONLY the /unity-install slash command file into the user's global
# Claude Code commands folder (~/.claude/commands/), then cleans up the temp.
#
# After running this, /unity-install is available in ANY Claude Code session
# the user starts on this machine.
#
# Run via curl-pipe (one-line install):
#   curl -fsSL https://raw.githubusercontent.com/Unity-Lab-AI/UAL-ClaudeWorkflow/main/install-unity-globally.sh | bash
#
# Or download + inspect first (safer):
#   curl -fsSL https://raw.githubusercontent.com/Unity-Lab-AI/UAL-ClaudeWorkflow/main/install-unity-globally.sh -o install-unity.sh
#   less install-unity.sh   # read it
#   bash install-unity.sh
#
# .ps1 sibling: install-unity-globally.ps1

set -e

REPO_URL="https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow.git"
BRANCH="main"
USER_GLOBAL_COMMANDS="$HOME/.claude/commands"

echo "[unity-bootstrap] Installing /unity-install into $USER_GLOBAL_COMMANDS/"
echo ""

# ─────────────────────────────────────────────────────────────────────
# Prerequisites
# ─────────────────────────────────────────────────────────────────────
if ! command -v git >/dev/null 2>&1; then
  echo "[unity-bootstrap] ERROR: git not found on PATH. Install git first, then re-run." >&2
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────
# Temp dir + cleanup trap
# ─────────────────────────────────────────────────────────────────────
TMPDIR=$(mktemp -d -t unity-bootstrap-XXXXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT

# ─────────────────────────────────────────────────────────────────────
# Clone (shallow, only main branch)
# ─────────────────────────────────────────────────────────────────────
echo "[unity-bootstrap] Cloning $REPO_URL ($BRANCH) to $TMPDIR..."
if ! git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$TMPDIR/repo" 2>&1; then
  echo "[unity-bootstrap] ERROR: git clone failed" >&2
  exit 1
fi

SRC_FILE="$TMPDIR/repo/.claude/commands/unity-install.md"
if [ ! -f "$SRC_FILE" ]; then
  echo "[unity-bootstrap] ERROR: cloned repo has no .claude/commands/unity-install.md — upstream layout may have changed" >&2
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────
# Install just the unity-install command file globally
# ─────────────────────────────────────────────────────────────────────
mkdir -p "$USER_GLOBAL_COMMANDS"
cp "$SRC_FILE" "$USER_GLOBAL_COMMANDS/unity-install.md"

echo "[unity-bootstrap] Installed: $USER_GLOBAL_COMMANDS/unity-install.md"
echo ""
echo "  Done. In ANY Claude Code session on this machine, you can now run:"
echo "    /unity-install                       (installs .claude/ into the current working directory)"
echo "    /unity-install /path/to/new-project  (installs into a specific target)"
echo ""
echo "  After install, cd into the target and run:"
echo "    ./.claude/start.sh    (Linux/macOS/Git Bash)"
echo "    .\\.claude\\start.bat   (Windows native)"
echo ""
echo "  To update an existing install: cd into a project with .claude/, then run /unity-update."

exit 0
