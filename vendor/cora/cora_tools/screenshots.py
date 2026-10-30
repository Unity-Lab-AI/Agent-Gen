#!/usr/bin/env python3
"""
C.O.R.A Screenshot Tools
Desktop and window capture for visual context

Per ARCHITECTURE.md v1.0.0:
- Capture full desktop
- Capture specific window by title
- Return image path or base64
- Configurable save location (default: Desktop)
"""

import os
import sys
import json
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, Union, List
from dataclasses import dataclass

# Optional imports
try:
    from PIL import ImageGrab, Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pygetwindow as gw
    GW_AVAILABLE = True
except ImportError:
    GW_AVAILABLE = False

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False


# Project paths
PROJECT_DIR = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_DIR / 'config'
SETTINGS_FILE = CONFIG_DIR / 'settings.json'

# Default screenshot directory - user's Desktop for easy access
DEFAULT_SCREENSHOT_DIR = Path.home() / 'Desktop' / 'CORA_Screenshots'


def get_screenshot_dir() -> Path:
    """Get the configured screenshot directory.

    Reads from config/settings.json if available.
    Falls back to Desktop/CORA_Screenshots.

    Returns:
        Path to screenshot directory
    """
    # Try to read from settings
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                config = json.load(f)
            screenshot_path = config.get('screenshots', {}).get('directory')
            if screenshot_path:
                return Path(screenshot_path)
        except Exception:
            pass

    return DEFAULT_SCREENSHOT_DIR


# Initialize screenshot directory
SCREENSHOT_DIR = get_screenshot_dir()


@dataclass
class ScreenshotResult:
    """Result of screenshot operation."""
    success: bool
    path: Optional[Path] = None
    base64: Optional[str] = None
    width: int = 0
    height: int = 0
    error: Optional[str] = None


def desktop(
    filename: Optional[str] = None,
    save_dir: Optional[Path] = None,
    return_base64: bool = False
) -> ScreenshotResult:
    """Capture full desktop screenshot.

    Args:
        filename: Optional filename (auto-generated if None)
        save_dir: Directory to save screenshot
        return_base64: If True, include base64 encoding

    Returns:
        ScreenshotResult with path and optional base64
    """
    if not PIL_AVAILABLE:
        return ScreenshotResult(
            success=False,
            error="Pillow not available. Install with: pip install Pillow"
        )

    try:
        # Capture desktop
        screenshot = ImageGrab.grab()

        # Generate filename
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'desktop_{timestamp}.png'

        # Ensure save directory exists
        save_path = (save_dir or SCREENSHOT_DIR) / filename
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # Save image
        screenshot.save(str(save_path))

        result = ScreenshotResult(
            success=True,
            path=save_path,
            width=screenshot.width,
            height=screenshot.height
        )

        # Optionally encode to base64
        if return_base64:
            result.base64 = image_to_base64(save_path)

        # Note: Don't auto-show modal here - let caller decide whether to display
        # This prevents double popups when boot_sequence also shows the image

        return result

    except Exception as e:
        return ScreenshotResult(success=False, error=str(e))


def window(
    title: Optional[str] = None,
    filename: Optional[str] = None,
    save_dir: Optional[Path] = None,
    return_base64: bool = False
) -> ScreenshotResult:
    """Capture specific window by title.

    Args:
        title: Window title (partial match). If None, captures active window
        filename: Optional filename
        save_dir: Directory to save screenshot
        return_base64: If True, include base64 encoding

    Returns:
        ScreenshotResult with path and optional base64
    """
    if not PIL_AVAILABLE:
        return ScreenshotResult(
            success=False,
            error="Pillow not available"
        )

    if not GW_AVAILABLE:
        return ScreenshotResult(
            success=False,
            error="pygetwindow not available. Install with: pip install pygetwindow"
        )

    try:
        # Find window
        if title:
            windows = gw.getWindowsWithTitle(title)
            if not windows:
                return ScreenshotResult(
                    success=False,
                    error=f"No window found with title: {title}"
                )
            win = windows[0]
        else:
            win = gw.getActiveWindow()
            if not win:
                return ScreenshotResult(
                    success=False,
                    error="No active window found"
                )

        # Get window bounds
        left, top, width, height = win.left, win.top, win.width, win.height

        # Capture region
        screenshot = ImageGrab.grab(bbox=(left, top, left + width, top + height))

        # Generate filename
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_title = (title or 'active')[:20].replace(' ', '_')
            filename = f'window_{safe_title}_{timestamp}.png'

        # Save
        save_path = (save_dir or SCREENSHOT_DIR) / filename
        save_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot.save(str(save_path))

        result = ScreenshotResult(
            success=True,
            path=save_path,
            width=screenshot.width,
            height=screenshot.height
        )

        if return_base64:
            result.base64 = image_to_base64(save_path)

        return result

    except Exception as e:
        return ScreenshotResult(success=False, error=str(e))


def region(
    x: int, y: int, width: int, height: int,
    filename: Optional[str] = None,
    save_dir: Optional[Path] = None
) -> ScreenshotResult:
    """Capture specific screen region.

    Args:
        x, y: Top-left corner coordinates
        width, height: Region size
        filename: Optional filename
        save_dir: Directory to save

    Returns:
        ScreenshotResult
    """
    if not PIL_AVAILABLE:
        return ScreenshotResult(success=False, error="Pillow not available")

    try:
        screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))

        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'region_{timestamp}.png'

        save_path = (save_dir or SCREENSHOT_DIR) / filename
        save_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot.save(str(save_path))

        return ScreenshotResult(
            success=True,
            path=save_path,
            width=screenshot.width,
            height=screenshot.height
        )

    except Exception as e:
        return ScreenshotResult(success=False, error=str(e))


def list_windows() -> List[str]:
    """Get list of all window titles.

    Returns:
        List of window titles
    """
    if not GW_AVAILABLE:
        return []

    try:
        return [w.title for w in gw.getAllWindows() if w.title]
    except Exception:
        return []


def image_to_base64(image_path: Path) -> Optional[str]:
    """Convert image file to base64 string.

    Args:
        image_path: Path to image

    Returns:
        Base64 encoded string or None
    """
    try:
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception:
        return None


def get_screen_size() -> tuple:
    """Get screen dimensions.

    Returns:
        (width, height) tuple
    """
    if PYAUTOGUI_AVAILABLE:
        return pyautogui.size()
    elif PIL_AVAILABLE:
        img = ImageGrab.grab()
        return (img.width, img.height)
    return (0, 0)


def quick_screenshot() -> Optional[Path]:
    """Take a quick desktop screenshot with auto-naming.

    Returns:
        Path to screenshot or None
    """
    result = desktop()
    return result.path if result.success else None


def set_screenshot_dir(new_dir: Union[str, Path]) -> bool:
    """Set the screenshot save directory in settings.

    Args:
        new_dir: New directory path

    Returns:
        True if successfully saved to settings
    """
    global SCREENSHOT_DIR

    new_path = Path(new_dir)

    # Ensure directory exists or can be created
    try:
        new_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False

    # Update settings file
    try:
        config = {}
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE) as f:
                config = json.load(f)

        if 'screenshots' not in config:
            config['screenshots'] = {}
        config['screenshots']['directory'] = str(new_path)

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(config, f, indent=2)

        SCREENSHOT_DIR = new_path
        return True
    except Exception:
        return False


def get_current_screenshot_dir() -> Path:
    """Get the current screenshot directory.

    Returns:
        Current screenshot directory path
    """
    return SCREENSHOT_DIR


if __name__ == "__main__":
    print("=== SCREENSHOT TEST ===")

    print("\n--- Screenshot Directory ---")
    print(f"Default: {DEFAULT_SCREENSHOT_DIR}")
    print(f"Current: {get_current_screenshot_dir()}")

    print("\n--- Screen Size ---")
    w, h = get_screen_size()
    print(f"Screen: {w}x{h}")

    print("\n--- Available Windows ---")
    windows = list_windows()
    for i, w in enumerate(windows[:10], 1):
        print(f"  {i}. {w[:50]}")

    print("\n--- Desktop Screenshot ---")
    result = desktop()
    if result.success:
        print(f"Saved to: {result.path}")
        print(f"Size: {result.width}x{result.height}")
    else:
        print(f"Error: {result.error}")
