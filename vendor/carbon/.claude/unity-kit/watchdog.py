"""
watchdog.py - Keeps Claude Code CLI alive and responsive.
Monitors Discord inbox AND Bridge WSS for new messages, nudges bot when idle.
Also launches screen_monitor.py automatically.

Usage: python watchdog.py <claude_pid>
  Env: CLAUDE_BOT_NAME (required)
  Bridge: uses WSS keypair auth via bridge_client_wss.py (no passwords)

This runs in a SEPARATE terminal from Claude Code.
It watches the screen state, Discord inbox, AND Bridge chat.
When new messages arrive and the bot is sitting idle -> nudge fires.

The full lifecycle:
1. Start Claude Code CLI in one terminal (note the PID)
2. Start this watchdog in another: python watchdog.py <PID>
3. Watchdog launches screen_monitor.py automatically
4. When Discord/Bridge messages arrive and bot is idle -> nudge fires
5. Bot's hook picks up the messages on that prompt
"""
import sys
import os
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

# Add shared path for bridge WSS client
sys.path.insert(0, r'C:\claude\shared')

# === CONFIG (all from env — nothing hardcoded) ===
MY_NAME = os.environ.get('CLAUDE_BOT_NAME', '').strip()
if not MY_NAME:
    print("ERROR: CLAUDE_BOT_NAME env var required. Set it to the bot name (e.g. Unity).")
    sys.exit(1)

BASE_DIR = Path(__file__).parent
SCREEN_STATE_FILE = BASE_DIR / "screen_state.json"
INBOX_FILE = BASE_DIR / "discord_inbox.json"
LAST_NUDGE_FILE = BASE_DIR / "watchdog_last_nudge.json"
SCREEN_MONITOR = BASE_DIR / "screen_monitor.py"
STDIN_INJECT = BASE_DIR / "stdin_inject.py"
LOCKFILE = BASE_DIR / "watchdog.lock"

# Bridge WSS client — keypair auth, no passwords
try:
    import bridge_client_wss as _bridge
    _bridge_ok = True
except ImportError:
    _bridge_ok = False
    print("WARNING: bridge_client_wss not found. Bridge polling disabled.")
    print("  Fix: pip install websockets cryptography + ensure C:\\claude\\shared\\bridge_client_wss.py exists")

BRIDGE_LAST_TS_FILE = BASE_DIR / "watchdog_bridge_last_ts.json"

NUDGE_INTERVAL = 60        # Nudge after 1 minute idle
STALE_THRESHOLD = 60       # Bot idle for 60s = stale
CHECK_INTERVAL = 60        # Check every 60 seconds
NUDGE_MESSAGE_DISCORD = "[WATCHDOG] New Discord message. Check your inbox."
NUDGE_MESSAGE_BRIDGE = "[WATCHDOG] New Bridge message. Check bridge_read."


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def pid_alive(pid):
    """Check if process is still running."""
    import ctypes
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if handle:
        exit_code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return exit_code.value == STILL_ACTIVE
    return False


def get_screen_state():
    """Read screen state from screen_monitor output."""
    if not SCREEN_STATE_FILE.exists():
        return None
    try:
        with open(SCREEN_STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return None


def get_last_nudge_ts():
    """Get timestamp of last inbox message we nudged about."""
    if not LAST_NUDGE_FILE.exists():
        return ""
    try:
        data = json.loads(LAST_NUDGE_FILE.read_text())
        return data.get("last_inbox_ts", "")
    except:
        return ""


def save_last_nudge_ts(ts):
    LAST_NUDGE_FILE.write_text(json.dumps({"last_inbox_ts": ts, "nudged_at": datetime.now().isoformat()}))


def get_latest_inbox_ts():
    """Get timestamp of most recent Discord inbox message."""
    if not INBOX_FILE.exists():
        return ""
    try:
        inbox = json.loads(INBOX_FILE.read_text(encoding='utf-8'))
        if inbox:
            return inbox[-1].get("ts", "")
    except:
        pass
    return ""


def get_bridge_last_ts():
    """Get last bridge message timestamp we've seen."""
    if not BRIDGE_LAST_TS_FILE.exists():
        return 0
    try:
        data = json.loads(BRIDGE_LAST_TS_FILE.read_text())
        return data.get("last_ts", 0)
    except:
        return 0


def save_bridge_last_ts(ts):
    BRIDGE_LAST_TS_FILE.write_text(json.dumps({"last_ts": ts, "checked_at": datetime.now().isoformat()}))


def check_bridge_messages():
    """Poll bridge for new messages via WSS. Returns (has_new, latest_ts)."""
    if not _bridge_ok:
        return False, 0
    last_ts = get_bridge_last_ts()
    try:
        msgs, err = _bridge.read_messages_sync(last_ts, 'default', 10)
        if err or not msgs:
            return False, last_ts
        # filter out our own messages
        others = [m for m in msgs if m.get('from', '').lower() != MY_NAME.lower()]
        if others:
            newest = max(m.get('ts', 0) for m in others)
            if newest > last_ts:
                save_bridge_last_ts(newest)
                return True, newest
    except Exception:
        pass
    return False, last_ts


def inject(pid, message):
    """Inject text into Claude CLI using stdin_inject.py."""
    try:
        result = subprocess.run(
            ["python", str(STDIN_INJECT), str(pid), message],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return result.returncode == 0
    except Exception as e:
        log(f"Inject error: {e}")
        return False


def launch_screen_monitor(pid):
    """Launch screen_monitor.py as background process."""
    try:
        proc = subprocess.Popen(
            ["pythonw", str(SCREEN_MONITOR), str(pid)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        log(f"Screen monitor launched (PID {proc.pid})")
        return proc
    except Exception as e:
        log(f"Failed to launch screen monitor: {e}")
        # Try with python instead of pythonw
        try:
            proc = subprocess.Popen(
                ["python", str(SCREEN_MONITOR), str(pid)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            log(f"Screen monitor launched with python (PID {proc.pid})")
            return proc
        except Exception as e2:
            log(f"Screen monitor failed completely: {e2}")
            return None


def acquire_lock():
    """Prevent duplicate watchdog instances. Returns True if lock acquired."""
    if LOCKFILE.exists():
        try:
            data = json.loads(LOCKFILE.read_text())
            old_pid = data.get("pid", 0)
            if old_pid and pid_alive(old_pid):
                return False  # Another instance is running
        except Exception:
            pass
    LOCKFILE.write_text(json.dumps({"pid": os.getpid(), "started": datetime.now().isoformat()}))
    return True


def release_lock():
    try:
        LOCKFILE.unlink(missing_ok=True)
    except Exception:
        pass


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python watchdog.py <claude_pid>")
        print(f"  Env required: CLAUDE_BOT_NAME")
        print(f"  Bridge: uses WSS keypair auth via C:\\claude\\shared\\bridge_client_wss.py")
        sys.exit(1)

    pid = int(sys.argv[1])
    log(f"=== WATCHDOG v2.0 ({MY_NAME}) ===")
    log(f"Monitoring Claude PID {pid}")
    log(f"Nudge interval: {NUDGE_INTERVAL}s | Stale threshold: {STALE_THRESHOLD}s")

    if not pid_alive(pid):
        log(f"ERROR: PID {pid} is not running!")
        sys.exit(1)

    if not acquire_lock():
        log("ERROR: Another watchdog instance is already running. Exiting.")
        sys.exit(1)

    # Launch screen monitor
    monitor_proc = launch_screen_monitor(pid)

    last_nudge_time = 0

    try:
        while True:
            if not pid_alive(pid):
                log("Claude PID died. Exiting watchdog.")
                break

            time_since_nudge = time.time() - last_nudge_time

            # Check for new Bridge messages — ALWAYS nudge, no stale check
            # Timestamp already saved in check_bridge_messages() to prevent duplicates
            has_bridge, bridge_ts = check_bridge_messages()
            if has_bridge and time_since_nudge >= NUDGE_INTERVAL:
                log(f"New Bridge message detected. Nudging {MY_NAME}...")
                if inject(pid, NUDGE_MESSAGE_BRIDGE):
                    log("Bridge nudge injected successfully")
                    last_nudge_time = time.time()
                else:
                    log("Bridge nudge injection failed")

            # Check for new Discord messages — only nudge when idle/stale
            latest_inbox_ts = get_latest_inbox_ts()
            last_nudge_ts = get_last_nudge_ts()
            has_discord = latest_inbox_ts and latest_inbox_ts > last_nudge_ts

            time_since_nudge = time.time() - last_nudge_time
            if has_discord and time_since_nudge >= NUDGE_INTERVAL:
                state = get_screen_state()
                is_stale = False

                if state:
                    epoch = state.get("epoch", 0)
                    stale_secs = time.time() - epoch
                    is_stale = stale_secs > STALE_THRESHOLD

                if is_stale or not state:
                    log(f"New Discord message detected. Nudging {MY_NAME}...")
                    if inject(pid, NUDGE_MESSAGE_DISCORD):
                        log("Discord nudge injected successfully")
                        save_last_nudge_ts(latest_inbox_ts)
                        last_nudge_time = time.time()
                    else:
                        log("Discord nudge injection failed")

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        log("Watchdog stopped by user")
    finally:
        release_lock()
        if monitor_proc and monitor_proc.poll() is None:
            monitor_proc.terminate()
            log("Screen monitor terminated")


if __name__ == "__main__":
    main()
