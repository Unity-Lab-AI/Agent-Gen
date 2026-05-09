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

# Git branch + dirty flag (line 1, after model). Computed in bash because
# `git` shell calls are quick (~5-20ms each) and avoid round-tripping through
# Python. GIT_PART stays empty in non-git directories so the segment self-
# omits cleanly. Color: green clean, yellow dirty — matching git CLI vibe.
GIT_PART=""
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
if [ -n "$GIT_BRANCH" ]; then
    if git status --porcelain 2>/dev/null | grep -q .; then
        GIT_PART=" \033[92m|\033[0m \033[33m${GIT_BRANCH}*\033[0m"
    else
        GIT_PART=" \033[92m|\033[0m \033[32m${GIT_BRANCH}\033[0m"
    fi
fi

eval $(echo "$input" | PYTHONIOENCODING=utf-8 PROJECT_NAME_RESOLVED="$PROJECT_NAME" $PYBIN -c "
import sys, json, os, hashlib, re, shutil, platform, subprocess, time
sys.stdout.reconfigure(encoding='utf-8')
try:
    d = json.load(sys.stdin)

    # 6-tier color gradient applied to every gauge (ctx, 5h, 7d, cpu, ram,
    # drive %used, vram, gpu util). Truecolor escapes — passthrough only,
    # works on every modern terminal that supports 24-bit color (Windows
    # Terminal, Git Bash mintty, Console Host since Win10 v1809, etc.).
    #   <=35%  green        (#22c55e — Tailwind green-500)
    #   36-45  green-yellow (#a3e635 — Tailwind lime-400)
    #   46-55  yellow       (#eab308 — Tailwind yellow-500)
    #   56-65  orange       (#f97316 — Tailwind orange-500)
    #   66-79  red-orange   (#ea580c — Tailwind orange-600 / red-orange)
    #   80+    red          (#dc2626 — Tailwind red-600)
    #   None / N/A          dim grey \033[90m
    def _grad_color(p):
        if p is None: return '\033[90m'
        if p <= 35: return '\033[38;2;34;197;94m'
        if p <= 45: return '\033[38;2;163;230;53m'
        if p <= 55: return '\033[38;2;234;179;8m'
        if p <= 65: return '\033[38;2;249;115;22m'
        if p < 80:  return '\033[38;2;234;88;12m'
        return '\033[38;2;220;38;38m'

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

    # Bar color from the shared 6-tier _grad_color gradient.
    bar_len = 15
    filled = int(pct / 100 * bar_len)
    bar = '#' * filled + '-' * (bar_len - filled)
    ctx_str = f'{_grad_color(pct)}[{bar}] {pct:.0f}%\033[0m'

    # Rate limit gauges (Pro/Max only — rate_limits block absent on free
    # plans, so each bar self-omits when its used_percentage is missing).
    # Same bar style + same green/yellow/red threshold as ctx for visual
    # consistency. 5h = current session usage (rolling 5-hour window),
    # 7d = weekly usage (rolling 7-day window). Cyan label matches the
    # uptime/thinking cyan-label convention.
    # NOTE: no backticks anywhere in this Python block — they trigger
    # bash command substitution inside the python3 -c "..." heredoc.
    def _pct_bar(p):
        try: p = float(p)
        except: p = 0
        if p < 0: p = 0
        if p > 100: p = 100
        bl = 15
        fl = int(p / 100 * bl)
        bar = '#' * fl + '-' * (bl - fl)
        return f'{_grad_color(p)}[{bar}] {p:.0f}%\033[0m'

    rate_limits = d.get('rate_limits', {})
    five_h_pct = rate_limits.get('five_hour', {}).get('used_percentage')
    seven_d_pct = rate_limits.get('seven_day', {}).get('used_percentage')
    rate5h_part = f' \033[92m|\033[0m \033[36m5h\033[0m {_pct_bar(five_h_pct)}' if five_h_pct is not None else ''
    rate7d_part = f' \033[92m|\033[0m \033[36m7d\033[0m {_pct_bar(seven_d_pct)}' if seven_d_pct is not None else ''

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

    # Line 3: cpu | ram | drive free space.
    # Linux uses /proc + shutil stdlib for sub-millisecond reads. Windows
    # CPU/RAM deferred to a follow-up commit (wmic + sidecar cache);
    # disk works cross-platform via shutil.disk_usage.
    cpu_pct = None
    if platform.system() == 'Linux':
        try:
            with open('/proc/loadavg') as f_la:
                load_1m = float(f_la.read().split()[0])
            ncpu = os.cpu_count() or 1
            cpu_pct = min(100.0, (load_1m / ncpu) * 100.0)
        except Exception:
            pass

    ram_used_gb = ram_total_gb = ram_pct = None
    if platform.system() == 'Linux':
        try:
            with open('/proc/meminfo') as f_mi:
                mi = f_mi.read()
            total_kb = int(re.search(r'MemTotal:\s+(\d+)', mi).group(1))
            avail_kb = int(re.search(r'MemAvailable:\s+(\d+)', mi).group(1))
            ram_total_gb = (total_kb * 1024) / (1024**3)
            ram_used_gb = ((total_kb - avail_kb) * 1024) / (1024**3)
            ram_pct = (ram_used_gb / ram_total_gb) * 100 if ram_total_gb > 0 else 0
        except Exception:
            pass

    disk_free_gb = disk_pct = None
    try:
        du = shutil.disk_usage('.')
        disk_free_gb = du.free / (1024**3)
        disk_pct = (du.used / du.total) * 100 if du.total > 0 else 0
    except Exception:
        pass

    def _sys_seg(label, value_str, pct):
        # value_str is dim-grey '—' on N/A; otherwise gradient-colored
        # via the shared _grad_color helper.
        if value_str is None:
            return f'\033[36m{label}\033[0m \033[90m—\033[0m'
        return f'\033[36m{label}\033[0m {_grad_color(pct)}{value_str}\033[0m'

    cpu_val = f'{cpu_pct:.0f}%' if cpu_pct is not None else None
    ram_val = f'{ram_used_gb:.1f}/{ram_total_gb:.1f}G' if ram_pct is not None else None
    disk_val = f'{disk_free_gb:.0f}G free' if disk_free_gb is not None else None

    sys_line = (
        f'{_sys_seg(\"cpu\", cpu_val, cpu_pct)}'
        f' \033[92m|\033[0m '
        f'{_sys_seg(\"ram\", ram_val, ram_pct)}'
        f' \033[92m|\033[0m '
        f'{_sys_seg(\"drive\", disk_val, disk_pct)}'
    )

    # Line 4: GPU(s) via nvidia-smi. Cached in ~/.claude/gpu-cache.json
    # with a 5-second TTL so the ~150ms nvidia-smi shell-out doesn't
    # block every render. On cache miss the script blocks once to refresh.
    # When nvidia-smi is missing OR returns no GPUs, line 4 renders as
    # red 'No GPU Detected' so the user knows the card wasn't found.
    home_dir = os.environ.get('USERPROFILE') or os.path.expanduser('~')
    gpu_cache_file = os.path.join(home_dir, '.claude', 'gpu-cache.json')
    gpu_data = {'gpus': []}
    cache_fresh = False
    try:
        if os.path.exists(gpu_cache_file):
            if (time.time() - os.path.getmtime(gpu_cache_file)) < 5.0:
                with open(gpu_cache_file) as f_gc:
                    gpu_data = json.load(f_gc)
                cache_fresh = True
    except Exception:
        pass

    if not cache_fresh:
        try:
            sm = subprocess.run(
                ['nvidia-smi',
                 '--query-gpu=name,memory.used,memory.total,utilization.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=2.0
            )
            gpus = []
            if sm.returncode == 0 and sm.stdout.strip():
                for line_g in sm.stdout.strip().split('\n'):
                    parts = [p.strip() for p in line_g.split(',')]
                    if len(parts) >= 4:
                        try:
                            gpus.append({
                                'name': parts[0],
                                'mem_used_mb': float(parts[1]),
                                'mem_total_mb': float(parts[2]),
                                'util_pct': float(parts[3]),
                            })
                        except ValueError:
                            pass
            gpu_data = {'gpus': gpus}
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            gpu_data = {'gpus': []}
        try:
            os.makedirs(os.path.dirname(gpu_cache_file), exist_ok=True)
            with open(gpu_cache_file, 'w') as f_gc:
                json.dump(gpu_data, f_gc)
        except Exception:
            pass

    def _short_gpu(name):
        # Match common NVIDIA naming: RTX/GTX/GT prefix + digits + optional Ti/SUPER.
        # Falls through to first 12 chars on no match.
        mm = re.search(r'(?:RTX|GTX|GT|Tesla|Quadro)\s*([A-Za-z0-9]+)\s*(SUPER|Ti)?', name, re.IGNORECASE)
        if mm:
            base = mm.group(1)
            sfx = (mm.group(2) or '').lower()
            return base + ('s' if sfx == 'super' else 'ti' if sfx == 'ti' else '')
        return name[:12]

    gpus_list = gpu_data.get('gpus', [])
    if not gpus_list:
        gpu_line = '\033[31mNo GPU Detected\033[0m'
    else:
        gpu_segs = []
        for g in gpus_list:
            short_n = _short_gpu(g.get('name', '?'))
            mu_mb = g.get('mem_used_mb', 0)
            mt_mb = g.get('mem_total_mb', 0)
            ut = g.get('util_pct', 0)
            vram_pct = (mu_mb / mt_mb * 100) if mt_mb > 0 else 0
            used_gb = mu_mb / 1024
            total_gb = mt_mb / 1024
            gpu_segs.append(
                f'\033[36m{short_n}\033[0m {_grad_color(vram_pct)}{used_gb:.1f}/{total_gb:.0f}gb\033[0m {_grad_color(ut)}{ut:.0f}%\033[0m'
            )
        gpu_line = ' \033[92m|\033[0m '.join(gpu_segs)

    print(f'CTX=\"{ctx_str}\" RATE5H=\"{rate5h_part}\" RATE7D=\"{rate7d_part}\" MODEL=\"{model_str}\" UPTIME=\"{uptime_part}\" THINK=\"{think_part}\" LABEL=\"{label}\" SYS3=\"{sys_line}\" GPU=\"{gpu_line}\"')
except:
    fallback_name = os.environ.get('PROJECT_NAME_RESOLVED') or '?'
    fallback_label = f'\033[35m[{fallback_name}]\033[0m'
    print(f'CTX=\"?\" RATE5H=\"\" RATE7D=\"\" MODEL=\"?\" UPTIME=\"\" THINK=\"\" LABEL=\"{fallback_label}\" SYS3=\"\" GPU=\"\"')
" 2>/dev/null)

# Render TWO lines so the segment list can keep growing (git branch,
# system stats, etc.) without busting terminal width:
#   Line 1: [Label] | up · think | Model     (identity + activity)
#   Line 2: [ctx-bar] | 5h | 7d              (gauges)
#
# LABEL carries the colored brackets — magenta when no rename is set
# (Unity-AI-Lab pink, closest 4-bit match to brand pink #ff4d9a), or a
# hash-derived bright color when /rename has been used. Pipe separators
# in bright green (92) frame each section visually.
#
# UPTIME has its leading pipe baked in so it self-omits cleanly on
# fresh sessions; when absent, line 1 falls back to a single pipe
# directly between label and model. Line 2's RATE5H / RATE7D segments
# also have leading pipes baked in so they self-omit independently.
PIPE="\033[92m|\033[0m"
if [ -n "$UPTIME" ]; then
    LINE1="$LABEL$UPTIME$THINK $PIPE $MODEL$GIT_PART"
else
    LINE1="$LABEL $PIPE $MODEL$GIT_PART"
fi
LINE2="$CTX$RATE5H$RATE7D"
LINE3="$SYS3"
LINE4="$GPU"
echo -e "$LINE1"
echo -e "$LINE2"
[ -n "$LINE3" ] && echo -e "$LINE3"
[ -n "$LINE4" ] && echo -e "$LINE4"
