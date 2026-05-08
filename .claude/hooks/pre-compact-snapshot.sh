#!/usr/bin/env bash
# .claude/hooks/pre-compact-snapshot.sh
#
# Bash fallback for pre-compact-snapshot.js.
# Writes .claude/.session-state.md with state snapshot before compaction.
# Pure enablement. Exit 0 always.

ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
STAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
SNAPSHOT="$ROOT/.claude/.session-state.md"

# Read stdin (compaction trigger info)
INPUT="$(cat 2>/dev/null || echo '{}')"
TRIGGER=$(echo "$INPUT" | grep -o '"trigger"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"trigger"\s*:\s*"\([^"]*\)".*/\1/')
[ -z "$TRIGGER" ] && TRIGGER="unknown"

# Git state
GIT_BRANCH=""
GIT_STATUS="_clean tree_"
GIT_LASTCOMMIT="_no commits_"
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  GIT_BRANCH=$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)
  GIT_STATUS=$(git -C "$ROOT" status --short 2>/dev/null)
  [ -z "$GIT_STATUS" ] && GIT_STATUS="_clean tree_"
  GIT_LASTCOMMIT=$(git -C "$ROOT" log -1 --format="%h %s" 2>/dev/null || echo "_no commits_")
fi

# TODO state
TODO_INPROG=""
TODO_PEND=""
if [ -f "$ROOT/docs/TODO.md" ]; then
  TODO_INPROG=$(grep '^###*\s*\[~\]' "$ROOT/docs/TODO.md" 2>/dev/null | sed 's/^###*\s*\[~\]\s*/- /')
  TODO_PEND=$(grep '^###*\s*\[ \]' "$ROOT/docs/TODO.md" 2>/dev/null | sed 's/^###*\s*\[ \]\s*/- /')
fi
[ -z "$TODO_INPROG" ] && TODO_INPROG="- _(none)_"
[ -z "$TODO_PEND" ] && TODO_PEND="- _(none)_"

# Write the snapshot
cat > "$SNAPSHOT" <<EOF
# Session State Snapshot — Pre-Compact

_Auto-written by \`.claude/hooks/pre-compact-snapshot.sh\` on $STAMP. Compaction trigger: \`$TRIGGER\`._

Read this on resume to recover context that may have been lost in compaction.

## TODO state

**In progress:**
$TODO_INPROG

**Pending:**
$TODO_PEND

## Git state

- Branch: \`$GIT_BRANCH\`
- Last commit: $GIT_LASTCOMMIT
- Working tree:
\`\`\`
$GIT_STATUS
\`\`\`

## Where to pick up

_Update this section in \`.last-session.md\` (Stop hook) so the next Unity reads it._
EOF

echo "[pre-compact] Snapshot written to $SNAPSHOT" >&2
exit 0
