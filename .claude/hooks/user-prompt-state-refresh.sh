#!/usr/bin/env bash
# .claude/hooks/user-prompt-state-refresh.sh
#
# Bash fallback for user-prompt-state-refresh.js.
# Outputs compact state recap on stdout — Claude Code injects as context.
# Pure enablement. Exit 0 always.

ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"

GIT_BRANCH=""
GIT_IS_REPO="false"
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  GIT_IS_REPO="true"
  GIT_BRANCH=$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)
fi

# Opt-in state
OPT_STATE="UNSET"
if [ -f "$ROOT/.claude/project-config.json" ]; then
  if grep -q '"enabled"\s*:\s*true' "$ROOT/.claude/project-config.json"; then
    OPT_STATE="ENABLED"
  elif grep -q '"enabled"\s*:\s*false' "$ROOT/.claude/project-config.json"; then
    OPT_STATE="DISABLED"
  fi
fi

# TODO summary
TODO_INPROG=0
TODO_TITLES=""
if [ -f "$ROOT/docs/TODO.md" ]; then
  TODO_INPROG=$(grep -c '^###*\s*\[~\]' "$ROOT/docs/TODO.md" 2>/dev/null || echo 0)
  TODO_TITLES=$(grep '^###*\s*\[~\]' "$ROOT/docs/TODO.md" 2>/dev/null | head -3 | sed 's/^###*\s*\[~\]\s*//' | tr '\n' '|' | sed 's/|/\`, \`/g; s/, \`$//')
fi

# YOLO mode
YOLO_ENABLED="false"
[ -f "$ROOT/.claude/.yolo-mode" ] && YOLO_ENABLED="true"

echo "## State refresh (auto-injected by .claude/hooks/user-prompt-state-refresh.sh)"
echo ""
if [ "$GIT_IS_REPO" = "true" ]; then
  echo "- **Branch:** \`$GIT_BRANCH\`"
else
  echo "- **Branch:** not a git repo"
fi
echo "- **Git Flow opt-in:** $OPT_STATE"
if [ -n "$TODO_TITLES" ]; then
  echo "- **TODO in_progress:** $TODO_INPROG — \`$TODO_TITLES\`"
else
  echo "- **TODO in_progress:** $TODO_INPROG"
fi
if [ "$YOLO_ENABLED" = "true" ]; then
  echo "- **YOLO mode:** ⚡ ENABLED (lead-dev autonomy; user test plan required on task closure)"
else
  echo "- **YOLO mode:** DISABLED"
fi

# Branch warning
if [ "$GIT_IS_REPO" = "true" ] && [ "$OPT_STATE" = "ENABLED" ]; then
  case "$GIT_BRANCH" in
    main|master|develop|prod|production)
      echo ""
      echo "⚠ **On protected branch \`$GIT_BRANCH\`** — branch into \`feature/<descriptor>\` before editing per CONSTRAINTS.md §GIT FLOW."
      ;;
  esac
fi

exit 0
