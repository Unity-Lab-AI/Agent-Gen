#!/bin/bash
# Unity AI Lab — Claude Code Status Line
#
# Renders a strip at the bottom of the Claude Code CLI showing:
#   [PROJECT_NAME] | [######-------] 57% | O4.7
#
# How it works (per docs/STATUSLINE.md):
#   1. Claude Code spawns this script as a subprocess each time the
#      status line refreshes.
#   2. Pipes a JSON blob to stdin: { context_window: { used_percentage },
#      model: { display_name }, ... }
#   3. We parse, format, and print the result to stdout. Claude Code
#      renders it as the status line text. ANSI color escapes honored.
#
# Side effect (per spec section 3): writes the current context % to
# ~/.claude/context_pct.txt so hooks / watchdogs / external tooling can
# `cat` that file to know how full the context is without querying
# Claude Code directly. This is the bridge for auto-compaction warnings
# or memory-backlog routines.
#
# Wired in: .claude/settings.local.json → statusLine.command
# Project-agnostic: auto-detects project name from cwd basename, so the
# same script drops into any Unity AI Lab project without per-project
# configuration.

input=$(cat)

# Project name = basename of cwd. Claude Code's cwd is the project root
# (where .claude/ lives), so basename gives "Dream", "Website2.0", etc.
# Fallback through pwd -W (Git Bash on Windows reports W-style path).
PROJECT_NAME=$(basename "$(pwd -W 2>/dev/null || pwd)")

eval $(echo "$input" | PYTHONIOENCODING=utf-8 PROJECT_NAME_RESOLVED="$PROJECT_NAME" py -3.12 -c "
import sys, json, os
sys.stdout.reconfigure(encoding='utf-8')
try:
    d = json.load(sys.stdin)
    cw = d.get('context_window', {})
    pct = cw.get('used_percentage', 0)
    model = d.get('model', {}).get('display_name', '?')

    # Shorten model name (Claude Opus 4.7 -> O4.7)
    if 'Opus' in model:
        ver = model.split('Opus')[1].strip().split()[0]
        model = f'O{ver}'
    elif 'Sonnet' in model:
        ver = model.split('Sonnet')[1].strip().split()[0]
        model = f'S{ver}'
    elif 'Haiku' in model:
        ver = model.split('Haiku')[1].strip().split()[0]
        model = f'H{ver}'

    # Defensive clamp — Claude Code has emitted negative or >100 values.
    try:
        pct = float(pct)
    except:
        pct = 0
    if pct < 0: pct = 0
    if pct > 100: pct = 100

    # Side-effect: write context % to ~/.claude/context_pct.txt as a
    # plain integer string. Hooks read this without round-tripping
    # through Claude Code. mkdir -p so it works on first run.
    home = os.environ.get('USERPROFILE') or os.path.expanduser('~')
    ctx_file = os.path.join(home, '.claude', 'context_pct.txt')
    try:
        os.makedirs(os.path.dirname(ctx_file), exist_ok=True)
        with open(ctx_file, 'w') as f:
            f.write(str(round(pct)))
    except:
        pass

    # Color the bar by threshold:
    #   <60%  green  (lots of headroom)
    #   60-80 yellow (warning zone)
    #   >80%  red    (compaction imminent)
    if pct > 80: color = '31'
    elif pct > 60: color = '33'
    else: color = '32'

    bar_len = 15
    filled = int(pct / 100 * bar_len)
    bar = '#' * filled + '-' * (bar_len - filled)
    ctx_str = f'\033[{color}m[{bar}] {pct:.0f}%\033[0m'

    print(f'CTX=\"{ctx_str}\" MODEL=\"{model}\"')
except:
    print('CTX=\"?\" MODEL=\"?\"')
" 2>/dev/null)

# Render the line. Project name in Unity-AI-Lab pink (ANSI 35 = magenta,
# closest 4-bit-palette match to the brand pink #ff4d9a). CTX placed
# right after the project name so Claude Code's weekly-limit banner
# (which sometimes overlaps the END of the status line) can't eat the
# critical % info.
B="\033[35m"
R="\033[0m"
echo -e "${B}[${PROJECT_NAME}]${R} | $CTX | $MODEL"
