#!/usr/bin/env bash
# === Project Startup (macOS / Linux) — DIAGNOSTIC LOGGING ENABLED ===
#
# Every step echoes BOTH to the screen and to ${TMPDIR:-/tmp}/unity-launcher.log
# so we can post-mortem after a crash. Look at that log if the window closes
# unexpectedly — it will show the last successful step before the crash.
#
LAUNCHER_LOG="${TMPDIR:-/tmp}/unity-launcher.log"
: > "$LAUNCHER_LOG"   # truncate

log() {
    local msg="$1"
    echo "[LAUNCHER] $msg"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $msg" >> "$LAUNCHER_LOG"
}

log "===== Unity launcher started at $(date) ====="
log "Working dir at entry: $(pwd)"
log "Script path: ${BASH_SOURCE[0]}"

# === Project Startup (macOS / Linux) ===
# Auto-builds Unity's persistent memory (idempotent), then launches Claude Code
# with `/unity then run /workflow`. That's it. No login, no portal, no admin claim,
# no first-run /setup branching — just memory + Unity + workflow.
#
# Status line: configured in .claude/settings.json via the
#   statusLine.command field, which points at .claude/statusline.sh.
# Claude Code spawns that script on every status-refresh, pipes JSON
# to its stdin, and renders the printed result as the bottom strip
# (project name + context bar + % + model abbrev). Side-effect: the
# script writes the current context % to ~/.claude/context_pct.txt
# so hooks/watchdogs can read it without querying Claude Code. The
# same script drops into any project — project name auto-detects
# from cwd basename, no per-project config needed. See the spec block
# at the top of .claude/statusline.sh for extension instructions.
#
# /setup, /template, /super-review, and every manifestation/escalation slash command
# still work as normal slash commands inside the session if the user invokes them.
#
# MEMORY INSTALL (every run, idempotent):
#    Copies .claude/memory-templates/*.md into the Claude Code project memory folder
#    under the user's home directory (~/.claude/projects/<encoded-project-path>/memory/)
#    IF that folder is empty. ~ resolves to $HOME on Linux/macOS — NOT %APPDATA% on
#    Windows; that's a different folder. The path is OS-neutral by design.
#    These files prime Unity as persistent persona via Claude Code's auto-memory system.
#    Without them, Unity activation is fragile and easily reverts to default Anthropic voice.
#    Re-run after editing memory-templates by deleting the memory folder's MEMORY.md to trigger reinstall.
#
# Unity is one persona with multiple manifestation forms:
#   /unity      — DEFAULT — 25-year-old goth-emo Unity from ImHanddicapped.txt (default below)
#   /girlfriend — Unity in 22-year-old freckled brunette girlfriend manifestation
#   /housewife  — Unity in 34-year-old domestic-dom housewife manifestation
#   /kittycat   — Unity in 23-year-old catgirl-hybrid manifestation
#
# Each manifestation has an alternate intensity sub-mode + a return-to-mode-default command:
#   girlfriend: /wild   (escalate)  /sweet  (return)
#   housewife:  /strict (escalate)  /cozy   (return)
#   kittycat:   /feral  (escalate)  /purr   (return)
#
# From any manifestation, invoke /unity again to return to base Unity (ImHanddicapped.txt form).
# Use /template to build a NEW Unity manifestation using the handicapped-template.md scaffold.
#
# CUSTOMIZE IF NEEDED:
#   - Swap /unity below for /girlfriend, /housewife, or /kittycat to start in a manifestation.
#   - Drop the chain entirely (use just "/workflow") if you don't want a persona.
#   - Drop --dangerously-skip-permissions if you want explicit per-tool permission prompts.

# NOTE: previously this script had `set -e` here, which aborted on the FIRST
# error silently — making diagnostic post-mortem impossible. Removed during the
# diagnostic-logging overhaul. Individual commands now use explicit error
# handling + the log() function so we can see exactly where things go wrong.

log "STEP 1: Resolving project root"
# Resolve project root (one level up from .claude/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR" || { log "STEP 1 FAIL: cd to $PROJECT_DIR failed"; read -p "Press Enter to close..."; exit 1; }
log "STEP 1 OK: Project root = $PROJECT_DIR"

log "STEP 2: Checking 'claude' on PATH"
# === Verify claude is available ===
if ! command -v claude >/dev/null 2>&1; then
    log "STEP 2 FAIL: 'claude' NOT found on PATH"
    echo
    echo "============================================================"
    echo " ERROR: 'claude' not found on PATH."
    echo " Install Claude Code CLI first: npm install -g @anthropic-ai/claude-code"
    echo "============================================================"
    echo " Log written to: $LAUNCHER_LOG"
    read -p "Press Enter to close..."
    exit 1
fi
log "STEP 2 OK: 'claude' found at $(command -v claude)"

log "STEP 3: Computing Claude Code project memory path"
# === Compute Claude Code project memory path ===
# Claude Code encodes project paths by replacing : / \ . space ( ) with - and prefixing the projects directory under the user's home (~/.claude/projects/).
# Example: /Users/me/Project              ->  -Users-me-Project
# Example: /Users/me/New folder (2)       ->  -Users-me-New-folder--2-
# Example: C:\Users\gfour\Desktop\Website ->  C--Users-gfour-Desktop-Website (Windows-style)
ENCODED_PATH="${PROJECT_DIR//:/-}"
ENCODED_PATH="${ENCODED_PATH//\//-}"
ENCODED_PATH="${ENCODED_PATH//\\/-}"
ENCODED_PATH="${ENCODED_PATH//./-}"
ENCODED_PATH="${ENCODED_PATH// /-}"
ENCODED_PATH="${ENCODED_PATH//(/-}"
ENCODED_PATH="${ENCODED_PATH//)/-}"
MEMORY_DIR="$HOME/.claude/projects/$ENCODED_PATH/memory"
MEMORY_TEMPLATES="$SCRIPT_DIR/memory-templates"
log "STEP 3 OK: encoded path = $ENCODED_PATH"
log "  MEMORY_DIR = $MEMORY_DIR"
log "  MEMORY_TEMPLATES = $MEMORY_TEMPLATES"

log "STEP 4: Memory template install check"
# === Install memory templates if the user-profile memory folder is empty ===
# This is what makes Unity stick across sessions. Claude Code auto-loads every .md
# in this folder as persistent user feedback at session start.
if [ ! -f "$MEMORY_DIR/MEMORY.md" ]; then
    log "STEP 4: MEMORY.md missing — installing templates"
    if ! mkdir -p "$MEMORY_DIR"; then
        log "STEP 4 FAIL: could not create $MEMORY_DIR"
    elif [ -d "$MEMORY_TEMPLATES" ] && ls "$MEMORY_TEMPLATES"/*.md >/dev/null 2>&1; then
        if cp "$MEMORY_TEMPLATES"/*.md "$MEMORY_DIR/"; then
            log "STEP 4 OK: Memory templates installed"
        else
            log "STEP 4 FAIL: cp failed copying templates"
        fi
    else
        log "STEP 4 WARN: memory-templates folder not found at $MEMORY_TEMPLATES"
    fi
else
    log "STEP 4 OK: Memory folder already populated"
fi

# === Launch Claude Code with Unity persona + workflow ===
#
# Default chain:
#   claude --dangerously-skip-permissions "/unity then run /workflow"
#
# Manifestation alternatives:
#   claude --dangerously-skip-permissions "/girlfriend then run /workflow"
#   claude --dangerously-skip-permissions "/housewife then run /workflow"
#   claude --dangerously-skip-permissions "/kittycat then run /workflow"
#
# No persona at all:
#   claude --dangerously-skip-permissions "/workflow"
#
log "STEP 5: About to launch claude (the moment of truth)"
log "  Command: claude --dangerously-skip-permissions \"/unity then run /workflow\""
echo
echo "============================================================"
echo " Starting Claude Code... (any pre-claude crashes are above)"
echo "============================================================"
echo

# NOTE: changed from `exec claude ...` to non-exec invocation so we can capture
# the exit code, log it, and pause before the terminal closes. With `exec`,
# control NEVER returns to this script and any crash error is lost the moment
# the terminal closes. Non-exec + read at end = always-visible diagnostic.
claude --dangerously-skip-permissions "/unity then run /workflow"
EXITCODE=$?
log "STEP 5 DONE: claude exited with code $EXITCODE"
echo
echo "============================================================"
echo " Claude Code has exited with code $EXITCODE."
echo " Diagnostic log: $LAUNCHER_LOG"
echo " Press Enter to close this window."
echo "============================================================"
read -r _
