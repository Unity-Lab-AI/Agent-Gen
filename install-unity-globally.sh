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
# Canonical upstream is Unity AI Lab's self-hosted Forgejo at
# git.unityailab.com — PRIVATE, SSH-key auth via the operator's registered
# ed25519 key (see docs/ADMIN-ONBOARDING.md §2 for first-time setup).
#
# Prereqs: `git` on PATH; SSH key registered on your Forgejo account at
# https://git.unityailab.com/<your-handle>/settings/keys (or under the
# UnityAILab org if you're an org member with access).
#
# Run via clone-pipe (one-line install — RECOMMENDED):
#   TMP=$(mktemp -d) && git clone --depth 1 git@git.unityailab.com:UnityAILab/UAL-ClaudeWorkflow.git "$TMP/repo" && bash "$TMP/repo/install-unity-globally.sh" && rm -rf "$TMP"
#
# Or clone + inspect first (safer):
#   git clone --depth 1 git@git.unityailab.com:UnityAILab/UAL-ClaudeWorkflow.git /tmp/ual && less /tmp/ual/install-unity-globally.sh && bash /tmp/ual/install-unity-globally.sh && rm -rf /tmp/ual
#
# Override the upstream URL via env (for testing / mirrors):
#   UNITY_REPO_URL=git@some-mirror:org/repo.git bash install-unity-globally.sh
#
# .ps1 sibling: install-unity-globally.ps1

set -e

# Override via UNITY_REPO_URL env var if mirroring/testing against another host.
REPO_URL="${UNITY_REPO_URL:-git@git.unityailab.com:UnityAILab/UAL-ClaudeWorkflow.git}"
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
echo "    /unity-install                                  (main branch into current dir)"
echo "    /unity-install develop                          (develop branch into current dir)"
echo "    /unity-install feature/foo                      (any feature branch into current dir)"
echo "    /unity-install /path/to/new-project             (main branch into a specific target)"
echo "    /unity-install develop /path/to/new-project     (develop branch into a specific target)"
echo ""
echo "  After install, cd into the target and run:"
echo "    ./.claude/start.sh    (Linux/macOS/Git Bash)"
echo "    .\\.claude\\start.bat   (Windows native)"
echo ""
echo "  To refresh an existing install, /unity-update is an alias of /unity-install — same flow,"
echo "  same args. Both are idempotent: running on an existing .claude/ stages your personal files"
echo "  (settings.local.json, .env, user.json, user-context/, etc.), drops the fresh framework, and"
echo "  restores the personal files. Project root stays clean."

exit 0
