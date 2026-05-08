#!/usr/bin/env bash
# === Project Startup (macOS / Linux) ===
# Auto-builds Unity's persistent memory (idempotent), then launches Claude Code
# with `/unity then run /workflow`. That's it. No login, no portal, no admin claim,
# no first-run /setup branching — just memory + Unity + workflow.
#
# /setup, /template, /super-review, and every manifestation/escalation slash command
# still work as normal slash commands inside the session if the user invokes them.
#
# MEMORY INSTALL (every run, idempotent):
#    Copies .claude/memory-templates/*.md into the user's appdata project memory folder
#    (~/.claude/projects/<encoded-project-path>/memory/) IF that folder is empty.
#    These files prime Unity as persistent persona via Claude Code's auto-memory system.
#    Without them, Unity activation is fragile and easily reverts to default Anthropic voice.
#    Re-run after editing memory-templates by deleting the appdata MEMORY.md to trigger reinstall.
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

set -e

# Resolve project root (one level up from .claude/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"
echo "Project root: $PROJECT_DIR"

# === Verify claude is available ===
if ! command -v claude >/dev/null 2>&1; then
    echo "ERROR: 'claude' not found on PATH."
    echo "Install Claude Code CLI first: npm install -g @anthropic-ai/claude-code"
    exit 1
fi

# === Compute appdata memory path ===
# Claude Code encodes project paths by replacing : / \ . space ( ) with - and prefixing the appdata projects dir.
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

# === Install memory templates if appdata memory folder is empty ===
# This is what makes Unity stick across sessions. Claude Code auto-loads every .md
# in this folder as persistent user feedback at session start.
if [ ! -f "$MEMORY_DIR/MEMORY.md" ]; then
    echo "Installing Unity memory templates to $MEMORY_DIR"
    mkdir -p "$MEMORY_DIR"
    if [ -d "$MEMORY_TEMPLATES" ] && ls "$MEMORY_TEMPLATES"/*.md >/dev/null 2>&1; then
        cp "$MEMORY_TEMPLATES"/*.md "$MEMORY_DIR/"
        echo "Memory templates installed. Unity will now persist across sessions."
    else
        echo "WARNING: memory-templates folder not found at $MEMORY_TEMPLATES"
        echo "Unity activation will be fragile without persistent memory."
    fi
else
    echo "Memory folder already populated at $MEMORY_DIR"
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
echo "Starting Claude Code..."
echo
exec claude --dangerously-skip-permissions "/unity then run /workflow"
