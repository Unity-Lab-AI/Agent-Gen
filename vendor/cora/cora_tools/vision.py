#!/usr/bin/env python3
"""
C.O.R.A vision captures — the two grabs ambient awareness and the tools ask for.

    capture_screenshot()       -> Path | None   (whole desktop, data/screenshots)
    capture_camera_snapshot()  -> Path | None   (webcam, data/camera, timeout-bounded)

Both are thin: the screenshot comes from cora_tools.screenshots, the camera
frame from services.camera (probed device, hard timeout, never hangs). The
image goes to the configured vision model through ai.ollama.analyze_image.
"""

from pathlib import Path
from typing import Optional

PROJECT_DIR = Path(__file__).resolve().parent.parent


def capture_screenshot() -> Optional[Path]:
    """Full-desktop screenshot as a file path, or None."""
    try:
        from cora_tools.screenshots import desktop
        r = desktop()
        path = getattr(r, 'path', None)
        if path and Path(path).exists():
            return Path(path)
        return None
    except Exception as e:
        print(f"[vision] screenshot failed: {e}")
        return None


def capture_camera_snapshot(save_path: Optional[Path] = None) -> Optional[Path]:
    """One webcam frame as a file path, or None (bounded by camera.open_timeout)."""
    try:
        from services import camera
        return camera.capture_to_file(save_path)
    except Exception as e:
        print(f"[vision] camera snapshot failed: {e}")
        return None


def describe_screen(prompt: str = "Briefly describe what is on the screen.") -> Optional[str]:
    """Screenshot + vision model, text or None."""
    p = capture_screenshot()
    if not p:
        return None
    from ai.ollama import analyze_image
    return analyze_image(str(p), prompt) or None


def describe_camera(prompt: str = "Briefly describe what you see through the camera.") -> Optional[str]:
    """Webcam frame + vision model, text or None."""
    p = capture_camera_snapshot()
    if not p:
        return None
    from ai.ollama import analyze_image
    return analyze_image(str(p), prompt) or None
