#!/usr/bin/env python3
"""
C.O.R.A Live Camera Feed
Real-time camera window using cv2.imshow (works with any webcam including virtual ones).

Features:
- Live video feed from webcam using OpenCV native window
- Take snapshots on command
- Works with physical webcams, Iriun, OBS Virtual Cam, etc.
- Press Q or ESC to close, S to take snapshot
- CORA can capture frames anytime for AI vision analysis

Created by: Unity AI Lab
"""

import cv2
import threading
import time
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

# Project paths
PROJECT_DIR = Path(__file__).parent.parent
SNAPSHOTS_DIR = PROJECT_DIR / 'data' / 'camera'


class LiveCameraFeed:
    """Live camera feed using cv2.imshow (works with any webcam)."""

    def __init__(
        self,
        camera_index: int = 0,
        width: int = 640,
        height: int = 480,
        on_snapshot: Optional[Callable] = None,
        window_name: str = "CORA - Live Camera"
    ):
        """
        Initialize live camera feed.

        Args:
            camera_index: Camera device index (0 = default)
            width: Window width
            height: Window height
            on_snapshot: Callback when snapshot is taken
            window_name: Window title
        """
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.on_snapshot = on_snapshot
        self.window_name = window_name

        self.cap = None
        self.is_running = False
        self.current_frame = None
        self._thread = None

        # Ensure snapshot directory exists
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    def start(self) -> bool:
        """Start the camera feed in a separate thread."""
        if self.is_running:
            return True

        # services.camera finds the device (config camera.index/backend, else
        # probes) with a hard timeout per attempt, so a stalled virtual webcam
        # (phone camera app, OBS virtual cam with no source) cannot hang us.
        from services import camera as _camera
        self.cap = _camera.open_capture()
        if self.cap is None:
            print(f"[Camera] No camera found ({_camera.last_error() or 'no device'})")
            return False
        dev = _camera.working_device()
        if dev:
            self.camera_index = dev[0]
        print(f"[Camera] Opened camera at index {self.camera_index}")
        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        return True

    def _run_loop(self):
        """Camera loop on its own thread. This thread OWNS the device: it is the
        one that releases it and destroys the window. Releasing from another
        thread while read() is blocked inside DirectShow/MSMF deadlocks (boot
        froze at phase 3.1 that way on a phone-camera virtual webcam)."""
        try:
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.window_name, self.width, self.height)
            print("[Camera] Live feed started. Press Q to close, S to snapshot.")
            while self.is_running and self.cap is not None and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    self.current_frame = frame.copy()
                    cv2.imshow(self.window_name, frame)     # clean frame, no overlay
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:           # Q or ESC
                    break
                elif key == ord('s'):                      # S for snapshot
                    self.take_snapshot()
        except Exception as e:
            print(f"[Camera] feed error: {e}")
        finally:
            cap, self.cap = self.cap, None
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
            try:
                cv2.destroyWindow(self.window_name)
            except Exception:
                pass
            self.is_running = False
            print("[Camera] Feed stopped")

    def take_snapshot(self) -> Optional[Path]:
        """Take a snapshot of the current frame."""
        if self.current_frame is None:
            return None

        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'snapshot_{timestamp}.jpg'
            path = SNAPSHOTS_DIR / filename

            cv2.imwrite(str(path), self.current_frame)
            print(f"[Camera] Snapshot saved: {path}")

            if self.on_snapshot:
                self.on_snapshot(path)

            return path
        except Exception as e:
            print(f"[Camera] Snapshot error: {e}")
            return None

    def get_current_frame_path(self) -> Optional[Path]:
        """Save current frame and return path (for AI analysis)."""
        if self.current_frame is None:
            return None

        try:
            path = SNAPSHOTS_DIR / 'current_frame.jpg'
            cv2.imwrite(str(path), self.current_frame)
            return path
        except:
            return None

    def stop(self, timeout: float = 4.0) -> bool:
        """Ask the feed thread to finish and wait up to `timeout` seconds. The
        thread releases the device itself; if the device never returns from
        its blocked read we abandon the thread (daemon) instead of hanging."""
        self.is_running = False
        t = self._thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout)
            if t.is_alive():
                print(f"[Camera] device did not release within {timeout:.0f}s; abandoning it")
                self._thread = None
                return False
        self._thread = None
        return True

    def is_active(self) -> bool:
        """Check if camera feed is active."""
        return self.is_running


# Global camera instance
_live_camera: Optional[LiveCameraFeed] = None


def open_live_camera(
    parent=None,  # Ignored, kept for compatibility
    on_snapshot: Optional[Callable] = None
) -> Optional[LiveCameraFeed]:
    """
    Open live camera feed window.

    Args:
        parent: Ignored (kept for API compatibility)
        on_snapshot: Callback when snapshot taken

    Returns:
        LiveCameraFeed instance or None
    """
    global _live_camera

    # Close existing if open
    if _live_camera and _live_camera.is_active():
        _live_camera.stop()
        time.sleep(0.5)  # Give camera time to release

    _live_camera = LiveCameraFeed(on_snapshot=on_snapshot)
    if _live_camera.start():
        return _live_camera
    return None


def get_live_camera() -> Optional[LiveCameraFeed]:
    """Get current live camera instance."""
    global _live_camera
    if _live_camera and _live_camera.is_active():
        return _live_camera
    return None


def close_live_camera():
    """Close live camera feed."""
    global _live_camera
    if _live_camera:
        _live_camera.stop()
        _live_camera = None


def capture_from_live_camera() -> Optional[Path]:
    """Capture frame from live camera for AI analysis."""
    global _live_camera
    if _live_camera and _live_camera.is_active():
        return _live_camera.get_current_frame_path()
    return None


# Quick capture without keeping camera open
def quick_capture() -> Optional[Path]:
    """
    Take a quick snapshot without keeping camera open.
    Better for sharing camera with other apps.
    """
    from services import camera as _camera
    path = _camera.capture_to_file(SNAPSHOTS_DIR / 'quick_capture.jpg')
    if path:
        print(f"[Camera] Quick capture saved: {path}")
        return path
    print(f"[Camera] Quick capture failed - {_camera.last_error() or 'no camera available'}")
    return None


# Test
if __name__ == "__main__":
    print("=== Live Camera Feed Test ===")
    print("Press Q to close, S to take snapshot")

    def on_snap(path):
        print(f"Snapshot callback: {path}")

    camera = open_live_camera(on_snapshot=on_snap)
    if camera:
        # Wait for camera thread to finish
        while camera.is_active():
            time.sleep(0.1)
    else:
        print("Failed to start camera")
