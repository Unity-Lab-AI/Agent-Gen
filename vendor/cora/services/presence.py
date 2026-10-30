#!/usr/bin/env python3
"""
C.O.R.A Presence Detection Service
Webcam + AI vision to detect if the user is present.

- Quick check: is anyone at the desk?
- Full analysis: emotion, activity, posture, holding
- Vision model and Ollama URL come from ai.settings (no hardcoding)
- PresenceMonitor: a background thread that keeps a cached answer so callers
  on latency-sensitive paths (the TTS queue) never open the webcam or wait on
  the vision model themselves.
"""

import os
import sys
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# Snapshot location (kept small: only the latest snapshot is retained)
SNAPSHOT_DIR = PROJECT_DIR / 'data' / 'snapshots'
MAX_SNAPSHOTS = 5


@dataclass
class PresenceResult:
    """Result of presence detection."""
    present: bool
    confidence: float
    emotion: Optional[str] = None
    activity: Optional[str] = None
    posture: Optional[str] = None
    holding: Optional[str] = None
    raw_response: Optional[str] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None


_camera_lock = threading.Lock()


def _prune_snapshots():
    try:
        files = sorted(SNAPSHOT_DIR.glob('snapshot_*.jpg'), key=lambda p: p.stat().st_mtime)
        for p in files[:-MAX_SNAPSHOTS]:
            p.unlink(missing_ok=True)
    except Exception:
        pass


def capture_webcam(camera_index: int = 0, save_path: Optional[Path] = None) -> Optional[Path]:
    """Capture a frame from the webcam. Serialized so two callers never fight
    over the device."""
    if not CV2_AVAILABLE:
        print("[!] OpenCV not available - install with: pip install opencv-python")
        return None
    with _camera_lock:
        try:
            # services.camera: probed device, hard timeout per attempt, never hangs
            from services import camera as _camera
            if save_path is None:
                SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                save_path = SNAPSHOT_DIR / f'snapshot_{timestamp}.jpg'
            path = _camera.capture_to_file(save_path)
            if not path:
                print(f"[!] Webcam capture failed: {_camera.last_error() or 'no camera'}")
                return None
            _prune_snapshots()
            return path
        except Exception as e:
            print(f"[!] Webcam capture error: {e}")
            return None


def ask_vision(image_path: Path, prompt: str, model: Optional[str] = None) -> Optional[str]:
    """Send an image to the configured vision model. Returns text or None."""
    try:
        from ai.ollama import generate_with_image
        r = generate_with_image(prompt, str(image_path), model=model, max_tokens=120)
        if r.error:
            print(f"[!] Vision error: {r.error}")
            return None
        return r.content
    except Exception as e:
        print(f"[!] Vision error: {e}")
        return None


def check_human_present(camera_index: int = 0) -> PresenceResult:
    """Quick check if someone is at the desk (webcam + vision model)."""
    image_path = capture_webcam(camera_index)
    if not image_path:
        return PresenceResult(present=False, confidence=0.0, error="Failed to capture webcam")

    prompt = "Look at this webcam image. Is there a person visible at the desk?\nAnswer with just: YES or NO"
    response = ask_vision(image_path, prompt)
    if response is None:
        return PresenceResult(present=False, confidence=0.0, error="Vision model unavailable")

    present = 'yes' in response.lower().strip()
    return PresenceResult(present=present, confidence=0.9 if present else 0.8,
                          raw_response=response, timestamp=datetime.now().isoformat())


def full_human_check(camera_index: int = 0) -> PresenceResult:
    """Deep analysis of the human at the desk: emotion, activity, posture, holding."""
    image_path = capture_webcam(camera_index)
    if not image_path:
        return PresenceResult(present=False, confidence=0.0, error="Failed to capture webcam")

    prompt = """Analyze this webcam image of a person at their desk.
If no person is visible, say "NO PERSON".
If a person is visible, describe:
1. EMOTION: (focused, tired, happy, stressed, bored, etc.)
2. ACTIVITY: (typing, reading, watching screen, thinking, talking, etc.)
3. POSTURE: (leaning forward, sitting back, hunched, relaxed, etc.)
4. HOLDING: (coffee mug, phone, nothing, pen, etc.)

Format:
PERSON: YES/NO
EMOTION: <emotion>
ACTIVITY: <activity>
POSTURE: <posture>
HOLDING: <item>"""

    response = ask_vision(image_path, prompt)
    if response is None:
        return PresenceResult(present=False, confidence=0.0, error="Vision model unavailable")

    result = parse_human_analysis(response)
    result.raw_response = response
    result.timestamp = datetime.now().isoformat()
    return result


def parse_human_analysis(response: str) -> PresenceResult:
    """Parse the detailed human analysis response."""
    lines = response.strip().split('\n')
    result = PresenceResult(present=False, confidence=0.5)
    for line in lines:
        line = line.strip().upper()
        if 'PERSON:' in line:
            result.present = 'YES' in line
            result.confidence = 0.9 if result.present else 0.8
        elif 'EMOTION:' in line:
            result.emotion = line.split(':', 1)[-1].strip().lower()
        elif 'ACTIVITY:' in line:
            result.activity = line.split(':', 1)[-1].strip().lower()
        elif 'POSTURE:' in line:
            result.posture = line.split(':', 1)[-1].strip().lower()
        elif 'HOLDING:' in line:
            result.holding = line.split(':', 1)[-1].strip().lower()
    if not result.present and 'no person' not in response.lower():
        if any(word in response.lower() for word in ['person', 'human', 'someone', 'user']):
            result.present = True
            result.confidence = 0.6
    return result


def should_interrupt(camera_index: int = 0) -> bool:
    """Whether it is appropriate to interrupt the user right now."""
    result = full_human_check(camera_index)
    if not result.present:
        return False
    if result.emotion in ('focused', 'concentrating', 'deep thought'):
        return False
    if result.emotion in ('stressed', 'frustrated', 'angry'):
        return False
    if result.activity in ('talking', 'phone call', 'on call'):
        return False
    return True


def wait_for_presence(camera_index: int = 0, timeout: int = 300, check_interval: int = 10) -> bool:
    """Block until the user is present or the timeout expires."""
    elapsed = 0
    while elapsed < timeout:
        if check_human_present(camera_index).present:
            return True
        time.sleep(check_interval)
        elapsed += check_interval
    return False


# ---------------------------------------------------------------------------
# Background monitor: the cached answer the TTS queue and ambient awareness read
# ---------------------------------------------------------------------------

class PresenceMonitor:
    """Polls the webcam on its own thread and caches the last answer.

    present() never blocks: it returns the cached value (default True so speech
    is never suppressed before the first check completes).
    """

    def __init__(self, interval: float = 20.0, camera_index: int = 0):
        self.interval = interval
        self.camera_index = camera_index
        self._present = True
        self._last: Optional[PresenceResult] = None
        self._checked_at = 0.0
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.enabled = True

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='presence-monitor', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            if self.enabled and CV2_AVAILABLE:
                try:
                    r = check_human_present(self.camera_index)
                    with self._lock:
                        self._last = r
                        self._checked_at = time.time()
                        if not r.error:
                            self._present = r.present
                except Exception:
                    pass
            self._stop.wait(self.interval)

    def present(self) -> bool:
        with self._lock:
            return self._present

    def last_result(self) -> Optional[PresenceResult]:
        with self._lock:
            return self._last

    def age(self) -> float:
        with self._lock:
            return time.time() - self._checked_at if self._checked_at else float('inf')


_monitor: Optional[PresenceMonitor] = None


def get_monitor(start: bool = True) -> PresenceMonitor:
    """Process-wide presence monitor."""
    global _monitor
    if _monitor is None:
        _monitor = PresenceMonitor()
    if start:
        _monitor.start()
    return _monitor


def user_is_present() -> bool:
    """Non-blocking cached presence (True until the first check says otherwise)."""
    return get_monitor().present()


if __name__ == "__main__":
    print("=== PRESENCE DETECTION TEST ===")
    if not CV2_AVAILABLE:
        print("[!] OpenCV not installed. Install with: pip install opencv-python")
        sys.exit(1)
    print("\n--- Quick Presence Check ---")
    result = check_human_present()
    print(f"Present: {result.present}  Confidence: {result.confidence}  Error: {result.error}")
    if result.present:
        print("\n--- Full Analysis ---")
        full = full_human_check()
        print(f"Emotion: {full.emotion}  Activity: {full.activity}  Posture: {full.posture}  Holding: {full.holding}")
