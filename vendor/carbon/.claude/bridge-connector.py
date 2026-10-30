#!/usr/bin/env python3
"""
Bridge Connector — polls VPS bridge chat, injects new messages into the active bot.
Uses stdin_inject_smart.py (or stdin_inject.py) + active.json PID.

Runs as background process from start.bat.

Env vars required:
  CLAUDE_BOT_NAME   - Bot identity (no hardcoded defaults)
  BRIDGE_PASSWORD   - VPS bridge auth token
Env vars optional:
  BRIDGE_URL        - VPS bridge URL (default: http://178.18.247.126:8766)
  INJECT_SCRIPT     - Path to stdin inject script (default: auto-detect from BASE_DIR)
  ACTIVE_FILE       - Path to active.json (default: derived from bot name)
  PYTHON_EXE        - Python executable (default: sys.executable)
  POLL_INTERVAL     - Seconds between polls (default: 10)
"""
import json
import os
import sys
import time
import logging
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).parent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [BRIDGE-CONN] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(BASE_DIR / 'bridge-connector.log')),
    ]
)
log = logging.getLogger('bridge-connector')

# Config — all from env, no hardcoded secrets or bot names
MY_NAME = os.environ.get('CLAUDE_BOT_NAME', '').strip()
if not MY_NAME:
    log.error("CLAUDE_BOT_NAME env var required. Exiting.")
    sys.exit(1)

BRIDGE_PASSWORD = os.environ.get('BRIDGE_PASSWORD', '')
if not BRIDGE_PASSWORD:
    log.error("BRIDGE_PASSWORD env var required. Exiting.")
    sys.exit(1)

BRIDGE_URL = os.environ.get('BRIDGE_URL', '')
if not BRIDGE_URL:
    log.error("BRIDGE_URL env var required. Exiting.")
    sys.exit(1)
POLL_INTERVAL = int(os.environ.get('POLL_INTERVAL', '10'))
PYTHON_EXE = os.environ.get('PYTHON_EXE', sys.executable)

# Auto-detect inject script: check local dir first, then fallback
_local_inject = BASE_DIR / "stdin_inject_smart.py"
_local_inject_basic = BASE_DIR / "stdin_inject.py"
INJECT_SCRIPT = os.environ.get('INJECT_SCRIPT',
    str(_local_inject) if _local_inject.exists()
    else str(_local_inject_basic) if _local_inject_basic.exists()
    else '')
if not INJECT_SCRIPT or not Path(INJECT_SCRIPT).exists():
    log.error(f"No inject script found. Set INJECT_SCRIPT env var. Checked: {_local_inject}, {_local_inject_basic}")
    sys.exit(1)

# Derive active.json path from bot name (or override with env)
ACTIVE_FILE = os.environ.get('ACTIVE_FILE',
    os.path.join(os.path.expanduser('~'), '.claude', 'services', MY_NAME, 'watchdog', 'active.json'))

# Track last seen timestamp
_last_ts = 0


def get_bot_pid():
    """Get bot PID from watchdog active.json"""
    try:
        with open(ACTIVE_FILE, 'r') as f:
            data = json.load(f)
        pid = data.get('pid')
        if pid:
            return int(pid)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        pass
    return None


def poll_bridge(since):
    """Poll bridge for messages since timestamp. Returns (messages, error)."""
    url = f"{BRIDGE_URL}/api/messages?since={since}&limit=20&channel=default"
    headers = {
        'Authorization': f'Bearer {BRIDGE_PASSWORD}',
        'Content-Type': 'application/json',
    }
    req = urllib.request.Request(url, headers=headers, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get('messages', []), None
    except urllib.error.HTTPError as e:
        return [], f'HTTP {e.code}'
    except Exception as e:
        return [], str(e)


def inject_to_bot(text, pid):
    """Inject text to bot via stdin_inject_smart.py"""
    try:
        result = subprocess.run(
            [PYTHON_EXE, INJECT_SCRIPT, str(pid), text],
            capture_output=True, text=True, timeout=30
        )
        output = (result.stdout or '').strip()
        if result.returncode == 0 and 'SUCCESS' in output:
            return True
        else:
            log.warning(f"Inject failed (rc={result.returncode}): {output}")
            return False
    except Exception as e:
        log.error(f"Inject error: {e}")
        return False


def main():
    global _last_ts

    if not BRIDGE_PASSWORD:
        log.error("BRIDGE_PASSWORD env var not set. Exiting.")
        sys.exit(1)

    log.info(f"Bridge connector starting for {MY_NAME}")
    log.info(f"Polling {BRIDGE_URL} every {POLL_INTERVAL}s")
    log.info(f"Active file: {ACTIVE_FILE}")

    # Initial poll to set baseline — don't inject old messages
    msgs, err = poll_bridge(0)
    if msgs:
        _last_ts = max(m.get('ts', 0) for m in msgs)
        log.info(f"Baseline set: {len(msgs)} existing messages, last_ts={_last_ts}")
    elif err:
        log.warning(f"Initial poll failed: {err}")

    # Main loop
    consecutive_errors = 0
    while True:
        time.sleep(POLL_INTERVAL)

        pid = get_bot_pid()
        if not pid:
            # Bot not active yet, keep polling silently
            continue

        msgs, err = poll_bridge(_last_ts)

        if err:
            consecutive_errors += 1
            if consecutive_errors <= 3 or consecutive_errors % 30 == 0:
                log.warning(f"Poll error ({consecutive_errors}): {err}")
            continue

        consecutive_errors = 0

        if not msgs:
            continue

        # Update timestamp
        _last_ts = max(m.get('ts', 0) for m in msgs)

        # Filter out our own messages
        incoming = [m for m in msgs if m.get('from', '').upper() != MY_NAME.upper()]

        if not incoming:
            continue

        # Build injection text
        lines = []
        for m in incoming:
            sender = m.get('from', '?')
            text = m.get('text', '')
            lines.append(f"{sender}: {text}")

        inject_text_str = "[BRIDGE] " + " | ".join(lines)

        # Truncate if too long (console input buffer limit)
        if len(inject_text_str) > 2000:
            inject_text_str = inject_text_str[:1997] + "..."

        log.info(f"Injecting {len(incoming)} bridge message(s) to {MY_NAME} (PID {pid})")
        success = inject_to_bot(inject_text_str, pid)
        if success:
            log.info("Injected OK")
        else:
            log.warning("Injection failed — bot may be busy")


if __name__ == '__main__':
    main()
