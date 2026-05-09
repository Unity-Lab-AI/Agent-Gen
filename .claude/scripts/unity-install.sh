#!/usr/bin/env bash
# .claude/scripts/unity-install.sh
#
# Install the Unity AI Lab .claude/ template into a target directory (new or
# existing). Clones the upstream main branch into a temp dir, copies .claude/
# to <target>/.claude/, and brings the project-root .gitignore if absent.
#
# Usage:
#   ./.claude/scripts/unity-install.sh                 (installs into current directory)
#   ./.claude/scripts/unity-install.sh /path/to/target (installs into specified directory)
#
# Behavior on existing .claude/ in target:
#   - If target/.claude/ exists → ABORT (use /unity-update instead to refresh existing)
#   - If target/ doesn't exist → mkdir -p, then install
#   - If target/ exists but no .claude/ → install
#
# Exit codes:
#   0 — install succeeded
#   1 — prerequisites failed (no git, target unwritable, can't clone)
#   2 — target already has .claude/ (use /unity-update instead)
#
# .ps1 sibling: .claude/scripts/unity-install.ps1

set -e

# ─────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────
REPO_URL="https://github.com/Unity-Lab-AI/UAL-ClaudeWorkflow.git"
BRANCH="main"
TARGET_DIR="${1:-$(pwd)}"

# Resolve to absolute path
if [ ! -d "$TARGET_DIR" ]; then
  mkdir -p "$TARGET_DIR" 2>/dev/null || {
    echo "[unity-install] ERROR: cannot create target directory: $TARGET_DIR" >&2
    exit 1
  }
fi
TARGET_DIR=$(cd "$TARGET_DIR" && pwd)

# ─────────────────────────────────────────────────────────────────────
# Prerequisites
# ─────────────────────────────────────────────────────────────────────
if ! command -v git >/dev/null 2>&1; then
  echo "[unity-install] ERROR: git not found on PATH" >&2
  exit 1
fi

if [ -d "$TARGET_DIR/.claude" ]; then
  echo "[unity-install] ERROR: $TARGET_DIR/.claude/ already exists." >&2
  echo "                Use /unity-update (or .claude/scripts/unity-update.sh) to refresh an existing template." >&2
  exit 2
fi

# ─────────────────────────────────────────────────────────────────────
# Temp dir + cleanup trap
# ─────────────────────────────────────────────────────────────────────
TMPDIR=$(mktemp -d -t unity-install-XXXXXXXX)
trap 'rm -rf "$TMPDIR"' EXIT

# ─────────────────────────────────────────────────────────────────────
# Clone (shallow, only main branch)
# ─────────────────────────────────────────────────────────────────────
echo "[unity-install] Cloning $REPO_URL ($BRANCH branch) to $TMPDIR..."
if ! git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$TMPDIR/repo" 2>&1; then
  echo "[unity-install] ERROR: git clone failed" >&2
  exit 1
fi

REPO_CLAUDE="$TMPDIR/repo/.claude"
if [ ! -d "$REPO_CLAUDE" ]; then
  echo "[unity-install] ERROR: cloned repo has no .claude/ — upstream layout may have changed" >&2
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────
# Install (full .claude/ copy)
# ─────────────────────────────────────────────────────────────────────
echo "[unity-install] Installing .claude/ to $TARGET_DIR/..."
mkdir -p "$TARGET_DIR/.claude"
cp -r "$REPO_CLAUDE/." "$TARGET_DIR/.claude/"

# Bring project-root .gitignore if target doesn't have one
if [ ! -f "$TARGET_DIR/.gitignore" ] && [ -f "$TMPDIR/repo/.gitignore" ]; then
  cp "$TMPDIR/repo/.gitignore" "$TARGET_DIR/.gitignore"
  echo "[unity-install] Installed project-root .gitignore"
fi

# Layer 0 of the .claude/ IP-boundary defense-in-depth — ensure .gitignore has
# a blanket `.claude/` exclude so accidental `git add -A` cannot stage the
# workflow into the target project. See CONSTRAINTS.md §LAW — .CLAUDE WORKFLOW
# IP BOUNDARY. Idempotent: if `.claude/` is already excluded, skip.
GITIGNORE="$TARGET_DIR/.gitignore"
[ ! -f "$GITIGNORE" ] && touch "$GITIGNORE"
if grep -Eq '^\.claude/?[[:space:]]*$' "$GITIGNORE"; then
  echo "[unity-install] .gitignore already excludes .claude/ — Layer 0 already in place"
else
  {
    echo ""
    echo "# Unity AI Lab .claude/ workflow — proprietary, never commit to public repos."
    echo "# See .claude/CONSTRAINTS.md §LAW — .CLAUDE WORKFLOW IP BOUNDARY for full text."
    echo "# Removal sanctioned only via /claude-publish after gh confirms private + Unity-Lab-AI."
    echo ".claude/"
  } >> "$GITIGNORE"
  echo "[unity-install] Added .claude/ exclude to $GITIGNORE (Layer 0 IP-boundary defense-in-depth)"
fi

# Ensure script files have executable bit
chmod +x "$TARGET_DIR/.claude/hooks/"*.cjs "$TARGET_DIR/.claude/hooks/"*.sh 2>/dev/null || true
chmod +x "$TARGET_DIR/.claude/scripts/"*.sh 2>/dev/null || true
chmod +x "$TARGET_DIR/.claude/start.sh" 2>/dev/null || true
chmod +x "$TARGET_DIR/.claude/bin/"* 2>/dev/null || true

# ─────────────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────────────
echo ""
echo "[unity-install] Install complete."
echo ""
echo "  Target:       $TARGET_DIR"
echo "  Source:       $REPO_URL ($BRANCH)"
echo ""
echo "  Next steps:"
echo "    cd $TARGET_DIR"
if [ -f "$TARGET_DIR/.claude/start.sh" ]; then
  echo "    ./.claude/start.sh           # Linux/macOS launcher (installs memory + activates Unity + runs /workflow)"
fi
if [ -f "$TARGET_DIR/.claude/start.bat" ]; then
  echo "    .\\.claude\\start.bat          # Windows launcher (same flow)"
fi
echo ""
echo "  The launcher handles memory installation idempotently on first run."
echo "  See $TARGET_DIR/.claude/README.md for full documentation."

exit 0
