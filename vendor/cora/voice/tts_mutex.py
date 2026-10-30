#!/usr/bin/env python3
"""
C.O.R.A TTS Mutex System
Lock-based speech coordination to prevent overlapping TTS

Per ARCHITECTURE.md v1.0.0:
- Prevents multiple bots/instances from talking over each other
- Lock file in CLAUDE_MUTEX_DIR env var, or temp dir, or local data dir
- Acquires lock before speaking, releases after audio complete
"""

import os
import sys
import time
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable
from contextlib import contextmanager
import portalocker  # For cross-process file locking


# Lock file location (shared across all Claude instances)
# Use CLAUDE_MUTEX_DIR env var, fallback to temp dir or local data dir
_MUTEX_DIR = os.environ.get('CLAUDE_MUTEX_DIR')
if _MUTEX_DIR:
    _MUTEX_PATH = Path(_MUTEX_DIR)
elif os.name == 'nt':
    # Windows: use user's temp dir
    _MUTEX_PATH = Path(os.environ.get('TEMP', os.environ.get('TMP', ''))) / 'claude'
else:
    # Unix: use /tmp or XDG_RUNTIME_DIR
    _MUTEX_PATH = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / 'claude'

TTS_LOCK_FILE = _MUTEX_PATH / 'tts_mutex.lock'
TTS_STATE_FILE = _MUTEX_PATH / 'tts_state.json'

# Fallback to local data directory
LOCAL_LOCK_FILE = Path(__file__).parent.parent / 'data' / 'tts_mutex.lock'
LOCAL_STATE_FILE = Path(__file__).parent.parent / 'data' / 'tts_state.json'

# Lock timeout (seconds)
LOCK_TIMEOUT = 30


class TTSMutex:
    """Mutex for coordinating TTS across multiple processes/instances."""

    def __init__(self, caller: str = "CORA"):
        """Initialize TTS mutex.

        Args:
            caller: Identifier for this instance (for logging)
        """
        self.caller = caller
        self._lock_file: Optional[object] = None
        self._local_lock = threading.Lock()

        # Determine which lock file to use
        if TTS_LOCK_FILE.parent.exists():
            self.lock_path = TTS_LOCK_FILE
            self.state_path = TTS_STATE_FILE
        else:
            self.lock_path = LOCAL_LOCK_FILE
            self.state_path = LOCAL_STATE_FILE

        # Ensure lock file exists
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.lock_path.exists():
            self.lock_path.touch()

    def acquire(self, timeout: float = LOCK_TIMEOUT) -> bool:
        """Acquire the TTS lock.

        Args:
            timeout: Maximum time to wait for lock

        Returns:
            True if lock acquired, False if timeout
        """
        try:
            self._lock_file = open(self.lock_path, 'w')
            # portalocker >= 3 has no timeout on lock(): poll a non-blocking
            # exclusive lock until we get it or the timeout runs out.
            deadline = time.time() + max(0.0, float(timeout))
            while True:
                try:
                    portalocker.lock(self._lock_file, portalocker.LOCK_EX | portalocker.LOCK_NB)
                    break
                except (portalocker.LockException, BlockingIOError, PermissionError, OSError):
                    if time.time() >= deadline:
                        raise portalocker.LockException("timeout")
                    time.sleep(0.05)

            # Update state file
            self._update_state('acquired')
            global _held
            _held = self
            return True

        except portalocker.LockException:
            self._log(f"Failed to acquire lock (timeout {timeout}s)")
            if self._lock_file:
                self._lock_file.close()
                self._lock_file = None
            return False

        except Exception as e:
            self._log(f"Lock error: {e}")
            if self._lock_file:
                try:
                    self._lock_file.close()
                except Exception:
                    pass
                self._lock_file = None
            return False

    def heartbeat(self):
        """Refresh acquired_at while a long reply is being spoken, so other
        processes never mistake a live lock for a stale one (is_locked() treats
        anything older than LOCK_TIMEOUT as abandoned)."""
        if self._lock_file:
            self._update_state('acquired')

    def release(self):
        """Release the TTS lock."""
        global _held
        if _held is self:
            _held = None
        try:
            if self._lock_file:
                self._update_state('released')
                portalocker.unlock(self._lock_file)
                self._lock_file.close()
                self._lock_file = None
                return True
        except Exception as e:
            self._log(f"Release error: {e}")
        return False

    def is_locked(self) -> bool:
        """Check if TTS is currently locked by another process.

        Returns:
            True if locked by someone else
        """
        try:
            state = self._read_state()
            if state and state.get('status') == 'acquired':
                # Check if lock is stale (older than timeout)
                acquired_at = state.get('acquired_at', '')
                if acquired_at:
                    acquired_time = datetime.fromisoformat(acquired_at)
                    age = (datetime.now() - acquired_time).total_seconds()
                    if age < LOCK_TIMEOUT:
                        return True
            return False
        except Exception:
            return False

    def who_has_lock(self) -> Optional[str]:
        """Get the name of the instance holding the lock.

        Returns:
            Caller name or None
        """
        try:
            state = self._read_state()
            if state and state.get('status') == 'acquired':
                return state.get('caller')
        except Exception:
            pass
        return None

    @contextmanager
    def locked(self, timeout: float = LOCK_TIMEOUT):
        """Context manager for acquiring/releasing lock.

        Usage:
            with mutex.locked():
                speak("Hello!")

        Args:
            timeout: Maximum time to wait
        """
        acquired = self.acquire(timeout)
        try:
            if acquired:
                yield True
            else:
                yield False
        finally:
            if acquired:
                self.release()

    def _update_state(self, status: str):
        """Update state file with current status."""
        try:
            state = {
                'status': status,
                'caller': self.caller,
                'acquired_at': datetime.now().isoformat() if status == 'acquired' else None,
                'released_at': datetime.now().isoformat() if status == 'released' else None
            }
            with open(self.state_path, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def _read_state(self) -> Optional[dict]:
        """Read current state from file."""
        try:
            if self.state_path.exists():
                with open(self.state_path) as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _log(self, message: str):
        """Log mutex events."""
        print(f"[TTS-MUTEX][{self.caller}] {message}")


# Global mutex instance
_mutex: Optional[TTSMutex] = None
_held: Optional[TTSMutex] = None      # the mutex this process currently holds (for heartbeat())


def heartbeat():
    """Called by the voice engine between sentences of one reply."""
    if _held is not None:
        try:
            _held.heartbeat()
        except Exception:
            pass


def get_mutex(caller: str = "CORA") -> TTSMutex:
    """Get or create the global TTS mutex.

    Args:
        caller: Identifier for this instance

    Returns:
        TTSMutex instance
    """
    global _mutex
    if _mutex is None:
        _mutex = TTSMutex(caller=caller)
    return _mutex


def speak_with_mutex(
    message: str,
    speak_func: Callable[[str], None],
    caller: str = "CORA",
    timeout: float = LOCK_TIMEOUT
) -> bool:
    """Speak with mutex lock - prevents overlapping speech.

    Args:
        message: Text to speak
        speak_func: The actual TTS function to call
        caller: Identifier for logging
        timeout: Max time to wait for lock

    Returns:
        True if spoke successfully
    """
    mutex = get_mutex(caller)

    with mutex.locked(timeout) as acquired:
        if acquired:
            try:
                speak_func(message)
                return True
            except Exception as e:
                print(f"[TTS-MUTEX] Speak error: {e}")
                return False
        else:
            holder = mutex.who_has_lock()
            print(f"[TTS-MUTEX] Skipped - {holder or 'someone'} is speaking")
            return False


def wait_for_speech(timeout: float = 30) -> bool:
    """Wait until no one is speaking.

    Args:
        timeout: Maximum time to wait

    Returns:
        True if clear to speak, False if timeout
    """
    mutex = get_mutex()
    start = time.time()

    while time.time() - start < timeout:
        if not mutex.is_locked():
            return True
        time.sleep(0.1)

    return False


# Fallback implementation without portalocker
class SimpleTTSMutex:
    """Simple file-based mutex (fallback if portalocker unavailable)."""

    def __init__(self, caller: str = "CORA"):
        self.caller = caller
        self.lock_path = LOCAL_LOCK_FILE
        self.state_path = LOCAL_STATE_FILE
        self._lock = threading.Lock()

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

    def acquire(self, timeout: float = LOCK_TIMEOUT) -> bool:
        """Acquire lock (simple file-based)."""
        start = time.time()

        while time.time() - start < timeout:
            with self._lock:
                if not self.lock_path.exists():
                    # Create lock file
                    with open(self.lock_path, 'w') as f:
                        json.dump({
                            'caller': self.caller,
                            'acquired': datetime.now().isoformat()
                        }, f)
                    return True

                # Check if lock is stale
                try:
                    with open(self.lock_path) as f:
                        data = json.load(f)
                        acquired = datetime.fromisoformat(data.get('acquired', ''))
                        if (datetime.now() - acquired).total_seconds() > LOCK_TIMEOUT:
                            # Stale lock, take over
                            self.lock_path.unlink()
                            continue
                except Exception:
                    # Corrupted lock file, remove it
                    self.lock_path.unlink()
                    continue

            time.sleep(0.1)

        return False

    def release(self):
        """Release lock."""
        try:
            if self.lock_path.exists():
                self.lock_path.unlink()
                return True
        except Exception:
            pass
        return False

    @contextmanager
    def locked(self, timeout: float = LOCK_TIMEOUT):
        """Context manager for lock."""
        acquired = self.acquire(timeout)
        try:
            yield acquired
        finally:
            if acquired:
                self.release()


# Try to use portalocker, fall back to simple implementation
try:
    import portalocker
    MutexClass = TTSMutex
except ImportError:
    print("[TTS-MUTEX] portalocker not available, using simple file-based mutex")
    MutexClass = SimpleTTSMutex


if __name__ == "__main__":
    # Test mutex
    print("=== TTS MUTEX TEST ===")

    mutex = get_mutex("TEST")

    print(f"Lock path: {mutex.lock_path}")
    print(f"Is locked: {mutex.is_locked()}")
    print(f"Who has lock: {mutex.who_has_lock()}")

    print("\nAcquiring lock...")
    with mutex.locked() as acquired:
        if acquired:
            print("Lock acquired!")
            print(f"Who has lock: {mutex.who_has_lock()}")
            time.sleep(2)
            print("Releasing...")
        else:
            print("Failed to acquire lock")

    print(f"Is locked: {mutex.is_locked()}")
