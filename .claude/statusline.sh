#!/bin/bash
# Unity AI Lab — Claude Code Status Line
#
# Renders a strip at the bottom of the Claude Code CLI showing:
#   [LABEL] | [######-------] 57% | O4.7 | up 1h23m · think 2m41s
#
# Label rules (auto-adapt to /rename):
#   - If `session_name` is present in the statusline JSON (set via Claude
#     Code's /rename slash command), display that as the label.
#   - Otherwise fall back to `basename(cwd)` so unnamed sessions keep the
#     classic project-folder identity.
#
# Label color rules (auto-vary per session):
#   - When a rename has been applied, the bracket color is picked by
#     hashing `session_id` against a 12-color ANSI palette. Stable for
#     the lifetime of one session, distinct across concurrent sessions.
#   - When no rename is set, color stays brand magenta (35) — the
#     original look. Anthropic's /color slash command does NOT persist
#     anywhere readable to the statusline (verified against live JSON +
#     ~/.claude.json + ~/.claude/sessions/*.json), so we can't sync to
#     it directly; the hash gives an auto-distinct alternative.
#
# How it works (per docs/STATUSLINE.md):
#   1. Claude Code spawns this script as a subprocess each time the
#      status line refreshes.
#   2. Pipes a JSON blob to stdin: { context_window: { used_percentage },
#      model: { display_name }, session_name, session_id, ... }
#   3. We parse, format, and print the result to stdout. Claude Code
#      renders it as the status line text. ANSI color escapes honored.
#
# Side effect (per spec section 3): writes the current context % to
# ~/.claude/context_pct.txt so hooks / watchdogs / external tooling can
# `cat` that file to know how full the context is without querying
# Claude Code directly. This is the bridge for auto-compaction warnings
# or memory-backlog routines.
#
# Wired in: .claude/settings.json → statusLine.command
# Project-agnostic: auto-detects fallback label from cwd basename, so
# the same script drops into any Unity AI Lab project without per-
# project configuration.

input=$(cat)

# Project name = basename of cwd. Claude Code's cwd is the project root
# (where .claude/ lives), so basename gives "Dream", "Website2.0", etc.
# Fallback through pwd -W (Git Bash on Windows reports W-style path).
PROJECT_NAME=$(basename "$(pwd -W 2>/dev/null || pwd)")

# Pick python launcher: prefer python3 (Linux/macOS), fall back to py -3 (Windows).
# `py` is the Windows Python launcher and doesn't exist on Linux/macOS, so the
# previous hardcoded `py -3` silently broke the statusline for any team member
# not on Windows. python3 is the POSIX-standard name; py -3 is the Windows path.
PYBIN=$(command -v python3 >/dev/null 2>&1 && echo python3 || echo "py -3")

eval $(echo "$input" | PYTHONIOENCODING=utf-8 PROJECT_NAME_RESOLVED="$PROJECT_NAME" $PYBIN -c "
import sys, json, os, hashlib
sys.stdout.reconfigure(encoding='utf-8')
try:
    d = json.load(sys.stdin)

    # Label = renamed session_name if present, else cwd basename.
    # session_id drives a stable per-session color hash when renamed.
    session_name = (d.get('session_name') or '').strip()
    session_id = (d.get('session_id') or '').strip()
    project_resolved = os.environ.get('PROJECT_NAME_RESOLVED') or '?'
    label_text = session_name if session_name else project_resolved

    # 12-color ANSI palette: 6 normal + 6 bright. Skips black/white to
    # avoid invisibility on either light or dark terminals. Magenta (35)
    # stays the un-renamed default to preserve the original brand look.
    PALETTE = ['91','92','93','94','95','96','31','32','33','34','35','36']
    if session_name and session_id:
        h = hashlib.md5(session_id.encode('utf-8')).digest()[0]
        name_color = PALETTE[h % len(PALETTE)]
    else:
        name_color = '35'
    label = f'\033[{name_color}m[{label_text}]\033[0m'

    cw = d.get('context_window', {})
    pct = cw.get('used_percentage', 0)

    # Model abbreviation + family-specific color.
    #   Opus    -> O#.#  in gold (truecolor #FFD700 — closest to gold,
    #                    no named ANSI equivalent; passthrough only)
    #   Sonnet  -> S#.#  in bright red (91)
    #   Haiku   -> H#.#  in bright blue (94)
    #   MiniMax -> M#.#  in bright magenta (95) — purple-ish
    # Detection checks both display_name AND id so providers that surface
    # only one or the other (e.g., minimax via ANTHROPIC_BASE_URL override
    # naming the model 'MiniMax-M2.7') still classify correctly.
    import re
    model_block = d.get('model', {})
    model_disp = model_block.get('display_name', '?')
    model_id = model_block.get('id', '')
    model_search = f'{model_disp} {model_id}'

    minimax_m = re.search(r'(?i)MiniMax-?M?(\d+(?:\.\d+)?)', model_search)
    if minimax_m:
        model = f'M{minimax_m.group(1)}'
        model_color = '95'
    elif 'Opus' in model_disp:
        ver = model_disp.split('Opus')[1].strip().split()[0]
        model = f'O{ver}'
        model_color = '38;2;255;215;0'
    elif 'Sonnet' in model_disp:
        ver = model_disp.split('Sonnet')[1].strip().split()[0]
        model = f'S{ver}'
        model_color = '91'
    elif 'Haiku' in model_disp:
        ver = model_disp.split('Haiku')[1].strip().split()[0]
        model = f'H{ver}'
        model_color = '94'
    else:
        model = model_disp
        model_color = '0'

    model_str = f'\033[{model_color}m{model}\033[0m'

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

    # Session uptime + cumulative thinking/API time from cost block.
    # cost.total_duration_ms = wall-clock since CLI session start (CC docs)
    # cost.total_api_duration_ms = cumulative time spent in API calls (Claude
    #   processing time = the closest signal to 'time Claude has been thinking')
    cost = d.get('cost', {})
    def _fmt_ms(ms):
        try: ms_int = int(ms)
        except: return ''
        if ms_int <= 0: return ''
        s = ms_int // 1000
        if s < 60: return f'{s}s'
        mm, ss = divmod(s, 60)
        if mm < 60: return f'{mm}m{ss:02d}s'
        hh, mm = divmod(mm, 60)
        if hh < 24: return f'{hh}h{mm:02d}m'
        dd, hh = divmod(hh, 24)
        return f'{dd}d{hh:02d}h'
    uptime_fmt = _fmt_ms(cost.get('total_duration_ms', 0))
    think_fmt = _fmt_ms(cost.get('total_api_duration_ms', 0))
    # Cyan label + bright-white value (97). Bright white over plain white
    # so the timer values pop on dark terminals — terminal-default fg
    # often renders as light gray, which got lost next to the cyan label.
    # Leading separator baked in so empty values don't leave dangling
    # ' | ·' fragments in the echo line.
    uptime_part = f' \033[92m|\033[0m \033[36mup\033[0m \033[97m{uptime_fmt}\033[0m' if uptime_fmt else ''
    think_part = f' \033[92m·\033[0m \033[36mthink\033[0m \033[97m{think_fmt}\033[0m' if think_fmt else ''

    print(f'CTX=\"{ctx_str}\" MODEL=\"{model_str}\" UPTIME=\"{uptime_part}\" THINK=\"{think_part}\" LABEL=\"{label}\"')
except:
    fallback_name = os.environ.get('PROJECT_NAME_RESOLVED') or '?'
    fallback_label = f'\033[35m[{fallback_name}]\033[0m'
    print(f'CTX=\"?\" MODEL=\"?\" UPTIME=\"\" THINK=\"\" LABEL=\"{fallback_label}\"')
" 2>/dev/null)

# Render the line. LABEL carries the colored brackets — magenta when no
# rename is set (Unity-AI-Lab pink, closest 4-bit match to brand pink
# #ff4d9a), or a hash-derived bright color when /rename has been used.
# CTX placed right after the label so Claude Code's weekly-limit banner
# (which sometimes overlaps the END of the status line) can't eat the
# critical % info. Pipe separators in bright green (92) frame each
# section visually; the third pipe (before 'up') is baked into
# uptime_part so it disappears cleanly when no cost timers exist.
PIPE="\033[92m|\033[0m"
echo -e "$LABEL $PIPE $CTX $PIPE $MODEL$UPTIME$THINK"
