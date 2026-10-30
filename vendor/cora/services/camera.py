#!/usr/bin/env python3
"""
C.O.R.A camera access — the ONE place a webcam is opened.

Why this exists (2026-10-14): boot hung forever on a virtual webcam (a phone
camera app exposed as a Windows capture device). OpenCV's open() and read()
are blocking C calls with no timeout, so when a virtual device's source is
not streaming the whole process stalls. Every other machine that runs CORA
has different cameras, indices and drivers, so nothing here assumes a device:

  - every open/read runs on a worker thread with a hard timeout
    (config camera.open_timeout, default 4 s); a stalled device is given up
    on and remembered for the rest of the process, never retried in a loop
  - the device is found by probing: config camera.index ("auto" = 0, 1, 2)
    x the platform's backends (Windows: DirectShow, Media Foundation, any;
    Linux: V4L2, any; macOS: AVFoundation, any), or a pinned camera.backend
  - the first working (index, backend) pair is cached for the process so
    later captures do not probe again
  - camera.enabled=false skips the hardware entirely

Use:
    from services import camera
    frame = camera.capture_frame()            # ndarray or None
    path  = camera.capture_to_file(path)      # Path or None
    cap   = camera.open_capture()             # opened cv2.VideoCapture for live feeds, or None
    info  = camera.camera_status()            # dict for boot checks
"""

import json
import os
import platform
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_DIR / 'config' / 'config.json'
SNAPSHOT_DIR = PROJECT_DIR / 'data' / 'camera'

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:  # pragma: no cover
    cv2 = None
    CV2_AVAILABLE = False

_lock = threading.RLock()
_working: Optional[Tuple[int, int]] = None        # (index, backend) that produced a frame
_dead: set = set()                                # (index, backend) pairs that hung or failed
_last_error: str = ''
_probed_once = False


# --------------------------------------------------------------------------- config
def _cfg() -> Dict[str, Any]:
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f).get('camera') or {}
    except Exception:
        return {}


def enabled() -> bool:
    return bool(_cfg().get('enabled', True)) and CV2_AVAILABLE


def open_timeout() -> float:
    try:
        return max(0.5, float(_cfg().get('open_timeout', 4.0)))
    except (TypeError, ValueError):
        return 4.0


def _backend_names() -> Dict[str, int]:
    if not CV2_AVAILABLE:
        return {}
    names = {'any': cv2.CAP_ANY}
    for attr, key in (('CAP_DSHOW', 'dshow'), ('CAP_MSMF', 'msmf'), ('CAP_V4L2', 'v4l2'),
                      ('CAP_AVFOUNDATION', 'avfoundation'), ('CAP_GSTREAMER', 'gstreamer')):
        if hasattr(cv2, attr):
            names[key] = getattr(cv2, attr)
    return names


def _candidate_backends() -> List[int]:
    names = _backend_names()
    pinned = str(_cfg().get('backend', 'auto') or 'auto').lower()
    if pinned != 'auto' and pinned in names:
        return [names[pinned]]
    system = platform.system()
    if system == 'Windows':
        order = ['dshow', 'msmf', 'any']
    elif system == 'Darwin':
        order = ['avfoundation', 'any']
    else:
        order = ['v4l2', 'any']
    return [names[k] for k in order if k in names]


def _candidate_indices() -> List[int]:
    idx = _cfg().get('index', 'auto')
    if isinstance(idx, int) and idx >= 0:
        return [idx]
    if isinstance(idx, str) and idx.strip().isdigit():
        return [int(idx)]
    if isinstance(idx, list):
        return [int(i) for i in idx if str(i).isdigit()]
    return [0, 1, 2]


def backend_name(backend: int) -> str:
    for k, v in _backend_names().items():
        if v == backend and k != 'any':
            return k
    return 'any'


# --------------------------------------------------------------------------- guarded open
def _open_and_read(index: int, backend: int, timeout: float):
    """Open + read one frame on a worker thread. Returns (cap, frame) or (None, None).
    If the device stalls past `timeout`, the worker is abandoned (daemon) and
    the pair is marked dead for this process."""
    global _last_error
    box: Dict[str, Any] = {}

    def work():
        cap = None
        try:
            cap = cv2.VideoCapture(index, backend)
            if not cap.isOpened():
                box['err'] = 'not opened'
                cap.release()
                return
            ok, frame = cap.read()
            if not ok or frame is None:
                # some devices need a warm-up frame
                time.sleep(0.2)
                ok, frame = cap.read()
            if ok and frame is not None:
                box['cap'], box['frame'] = cap, frame
            else:
                box['err'] = 'opened but no frame'
                cap.release()
        except Exception as e:  # pragma: no cover
            box['err'] = str(e)
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
        finally:
            box['done'] = True

    t = threading.Thread(target=work, daemon=True, name=f'camera-open-{index}-{backend}')
    t.start()
    t.join(timeout)
    if not box.get('done'):
        _dead.add((index, backend))
        _last_error = f"camera {index} ({backend_name(backend)}) did not respond within {timeout:.0f}s"
        print(f"[camera] {_last_error}; giving up on it for this session")
        # if the stalled worker ever finishes, release what it opened
        def _cleanup():
            t.join()
            c = box.get('cap')
            if c is not None:
                try:
                    c.release()
                except Exception:
                    pass
        threading.Thread(target=_cleanup, daemon=True).start()
        return None, None
    if 'cap' in box:
        return box['cap'], box['frame']
    _last_error = f"camera {index} ({backend_name(backend)}): {box.get('err', 'failed')}"
    return None, None


def _probe(keep_open: bool = False):
    """Find a working (index, backend). Returns (cap_or_None, frame_or_None)."""
    global _working, _probed_once
    timeout = open_timeout()
    tried = 0
    for index in _candidate_indices():
        for backend in _candidate_backends():
            if (index, backend) in _dead:
                continue
            tried += 1
            cap, frame = _open_and_read(index, backend, timeout)
            if cap is not None:
                _working = (index, backend)
                _probed_once = True
                print(f"[camera] using index {index} via {backend_name(backend)}")
                if keep_open:
                    return cap, frame
                cap.release()
                return None, frame
    _probed_once = True
    if tried == 0 and not _last_error:
        globals()['_last_error'] = 'no camera candidates left'
    return None, None


# --------------------------------------------------------------------------- public API
def capture_frame(timeout: Optional[float] = None):
    """One frame as a numpy array, or None. Never blocks longer than the
    configured timeout per attempt; a stalled device is not retried."""
    if not enabled():
        return None
    with _lock:
        if _working is not None:
            for attempt in range(2):          # the device may still be releasing (live feed just closed)
                cap, frame = _open_and_read(_working[0], _working[1], timeout or open_timeout())
                if cap is not None:
                    cap.release()
                    return frame
                if (_working[0], _working[1]) in _dead:
                    break
                time.sleep(0.4)
            globals()['_working'] = None     # it broke; probe again next time
        _, frame = _probe(keep_open=False)
        return frame


def capture_to_file(path: Optional[Path] = None) -> Optional[Path]:
    """Capture a frame and write it as JPEG. Default: data/camera/snapshot_<ts>.jpg."""
    frame = capture_frame()
    if frame is None:
        return None
    if path is None:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = SNAPSHOT_DIR / f"snapshot_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), frame)
    return path


def open_capture():
    """An opened cv2.VideoCapture on the working device (for live feeds), or None.
    The caller owns it and must release() it."""
    if not enabled():
        return None
    with _lock:
        if _working is not None:
            for attempt in range(2):
                cap, _ = _open_and_read(_working[0], _working[1], open_timeout())
                if cap is not None:
                    return cap
                if (_working[0], _working[1]) in _dead:
                    break
                time.sleep(0.4)
            globals()['_working'] = None
        cap, _ = _probe(keep_open=True)
        return cap


def working_device() -> Optional[Tuple[int, str]]:
    """(index, backend name) once a capture succeeded this session."""
    return (_working[0], backend_name(_working[1])) if _working else None


def camera_status(probe: bool = True) -> Dict[str, Any]:
    """For boot checks. probe=True captures one frame (bounded by the timeout)."""
    info: Dict[str, Any] = {'available': False, 'enabled': enabled(), 'opencv': CV2_AVAILABLE,
                            'index': None, 'backend': None, 'resolution': None, 'error': ''}
    if not enabled():
        info['error'] = 'disabled' if CV2_AVAILABLE else 'opencv missing'
        return info
    frame = capture_frame() if probe else None
    if frame is not None:
        info.update(available=True, resolution=f"{frame.shape[1]}x{frame.shape[0]}")
    dev = working_device()
    if dev:
        info['index'], info['backend'] = dev
    info['error'] = '' if info['available'] else (_last_error or 'no camera found')
    return info


def last_error() -> str:
    return _last_error


if __name__ == '__main__':
    t0 = time.time()
    print(camera_status(), f"{time.time() - t0:.1f}s")
