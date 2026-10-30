#!/usr/bin/env bash
# Install the .claude/tools toolkit into a project, or globally for every project.
#
#   ./install.sh                  # into ./.claude/tools
#   ./install.sh ~/code/app       # into that project's .claude/tools
#   ./install.sh --global         # into ~/.claude/tools (all projects)
#   ./install.sh --no-deps        # copy files only
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="."
GLOBAL=0
NODEPS=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --global) GLOBAL=1 ;;
    --no-deps) NODEPS=1 ;;
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) TARGET="$arg" ;;
  esac
done

if [ "$GLOBAL" = 1 ]; then DEST="$HOME/.claude/tools"; else DEST="$(cd "$TARGET" && pwd)/.claude/tools"; fi

if [ "$SRC" = "$DEST" ]; then
  echo "Already installed here: $DEST"
else
  mkdir -p "$DEST"
  for f in doctor.py screen.py browser.py web.py README.md requirements.txt LICENSE install.ps1 install.sh; do
    [ -f "$SRC/$f" ] || continue
    if [ -e "$DEST/$f" ] && [ "$FORCE" = 0 ]; then echo "  skip (exists) $f"; continue; fi
    cp "$SRC/$f" "$DEST/$f"; echo "  copied $f"
  done
  chmod +x "$DEST/install.sh" 2>/dev/null || true
  echo; echo "Installed to $DEST"
fi

PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo; echo "Python not found - install Python 3.8+ then run: python3 $DEST/doctor.py --install"; exit 1
fi

if [ "$NODEPS" = 1 ]; then
  echo; echo "Skipping dependencies. Check them later with:  $PY $DEST/doctor.py"
else
  echo; echo "--- checking dependencies ---"
  "$PY" "$DEST/doctor.py" --install || true
fi

cat <<EOF

Done. Try:
  $PY "$DEST/doctor.py"
  $PY "$DEST/web.py" get https://example.com
  $PY "$DEST/browser.py" open https://example.com

Note: screen.py (desktop control) is Windows-only; browser.py and web.py are cross-platform.
Paste the "Tell Claude about it" block from README.md into your CLAUDE.md.
EOF
