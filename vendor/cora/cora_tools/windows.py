#!/usr/bin/env python3
"""
C.O.R.A Window Management Tools
Control and manage application windows on the desktop.

Per ARCHITECTURE.md v1.0.0:
- minimize_window(app_name)
- maximize_window(app_name)
- arrange_windows(layout)
- focus_window(app_name)

Created by: Unity AI Lab
Date: 2025-12-23
"""

import subprocess
import time
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# Try to import Windows-specific modules
try:
    import win32gui
    import win32con
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import pygetwindow as gw
    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False


class WindowLayout(Enum):
    """Predefined window arrangement layouts."""
    CASCADE = "cascade"
    TILE_HORIZONTAL = "tile_horizontal"
    TILE_VERTICAL = "tile_vertical"
    GRID_2X2 = "grid_2x2"
    LEFT_RIGHT = "left_right"
    TOP_BOTTOM = "top_bottom"
    FOCUS_CENTER = "focus_center"


@dataclass
class WindowInfo:
    """Information about a window."""
    hwnd: int
    title: str
    x: int
    y: int
    width: int
    height: int
    is_visible: bool
    is_minimized: bool
    is_maximized: bool
    process_id: Optional[int] = None


class WindowManager:
    """
    Manages application windows on the desktop.

    Provides functions to minimize, maximize, arrange, and focus windows.
    Works on Windows using win32gui or pygetwindow as fallback.
    """

    def __init__(self):
        """Initialize window manager."""
        self._screen_width = 1920  # Default, will be updated
        self._screen_height = 1080
        self._update_screen_size()

    def _update_screen_size(self):
        """Update screen dimensions."""
        if HAS_WIN32:
            try:
                self._screen_width = win32gui.GetSystemMetrics(0)
                self._screen_height = win32gui.GetSystemMetrics(1)
            except Exception:
                pass
        elif HAS_PYGETWINDOW:
            try:
                # Use a visible window to estimate screen size
                windows = gw.getAllWindows()
                if windows:
                    # Get the largest window dimensions as estimate
                    max_w = max(w.width for w in windows if w.width > 0)
                    max_h = max(w.height for w in windows if w.height > 0)
                    self._screen_width = max(self._screen_width, max_w)
                    self._screen_height = max(self._screen_height, max_h)
            except Exception:
                pass

    def get_all_windows(self) -> List[WindowInfo]:
        """Get information about all visible windows.

        Returns:
            List of WindowInfo objects
        """
        windows = []

        if HAS_WIN32:
            def enum_callback(hwnd, results):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:  # Skip windows without titles
                        try:
                            rect = win32gui.GetWindowRect(hwnd)
                            placement = win32gui.GetWindowPlacement(hwnd)
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)

                            is_minimized = placement[1] == win32con.SW_SHOWMINIMIZED
                            is_maximized = placement[1] == win32con.SW_SHOWMAXIMIZED

                            info = WindowInfo(
                                hwnd=hwnd,
                                title=title,
                                x=rect[0],
                                y=rect[1],
                                width=rect[2] - rect[0],
                                height=rect[3] - rect[1],
                                is_visible=True,
                                is_minimized=is_minimized,
                                is_maximized=is_maximized,
                                process_id=pid
                            )
                            results.append(info)
                        except Exception:
                            pass
                return True

            win32gui.EnumWindows(enum_callback, windows)

        elif HAS_PYGETWINDOW:
            for w in gw.getAllWindows():
                if w.title and w.visible:
                    info = WindowInfo(
                        hwnd=getattr(w, '_hWnd', 0),
                        title=w.title,
                        x=w.left,
                        y=w.top,
                        width=w.width,
                        height=w.height,
                        is_visible=w.visible,
                        is_minimized=w.isMinimized,
                        is_maximized=w.isMaximized
                    )
                    windows.append(info)

        return windows

    def find_window(self, app_name: str) -> Optional[WindowInfo]:
        """Find a window by application name (partial match).

        Args:
            app_name: Application name or window title to search for

        Returns:
            WindowInfo if found, None otherwise
        """
        app_name_lower = app_name.lower()
        windows = self.get_all_windows()

        # Try exact match first
        for w in windows:
            if w.title.lower() == app_name_lower:
                return w

        # Try partial match
        for w in windows:
            if app_name_lower in w.title.lower():
                return w

        return None

    def find_windows(self, app_name: str) -> List[WindowInfo]:
        """Find all windows matching application name.

        Args:
            app_name: Application name or window title to search for

        Returns:
            List of matching WindowInfo objects
        """
        app_name_lower = app_name.lower()
        windows = self.get_all_windows()
        return [w for w in windows if app_name_lower in w.title.lower()]

    def minimize_window(self, app_name: str) -> bool:
        """Minimize a window by application name.

        Args:
            app_name: Application name or window title

        Returns:
            True if successful, False otherwise
        """
        window = self.find_window(app_name)
        if not window:
            return False

        if HAS_WIN32:
            try:
                win32gui.ShowWindow(window.hwnd, win32con.SW_MINIMIZE)
                return True
            except Exception:
                return False
        elif HAS_PYGETWINDOW:
            try:
                w = gw.getWindowsWithTitle(window.title)[0]
                w.minimize()
                return True
            except Exception:
                return False

        return False

    def maximize_window(self, app_name: str) -> bool:
        """Maximize a window by application name.

        Args:
            app_name: Application name or window title

        Returns:
            True if successful, False otherwise
        """
        window = self.find_window(app_name)
        if not window:
            return False

        if HAS_WIN32:
            try:
                win32gui.ShowWindow(window.hwnd, win32con.SW_MAXIMIZE)
                return True
            except Exception:
                return False
        elif HAS_PYGETWINDOW:
            try:
                w = gw.getWindowsWithTitle(window.title)[0]
                w.maximize()
                return True
            except Exception:
                return False

        return False

    def restore_window(self, app_name: str) -> bool:
        """Restore a window to normal size.

        Args:
            app_name: Application name or window title

        Returns:
            True if successful, False otherwise
        """
        window = self.find_window(app_name)
        if not window:
            return False

        if HAS_WIN32:
            try:
                win32gui.ShowWindow(window.hwnd, win32con.SW_RESTORE)
                return True
            except Exception:
                return False
        elif HAS_PYGETWINDOW:
            try:
                w = gw.getWindowsWithTitle(window.title)[0]
                w.restore()
                return True
            except Exception:
                return False

        return False

    def focus_window(self, app_name: str) -> bool:
        """Bring a window to the foreground and give it focus.

        Args:
            app_name: Application name or window title

        Returns:
            True if successful, False otherwise
        """
        window = self.find_window(app_name)
        if not window:
            return False

        if HAS_WIN32:
            try:
                # Restore if minimized
                if window.is_minimized:
                    win32gui.ShowWindow(window.hwnd, win32con.SW_RESTORE)

                # Bring to foreground
                win32gui.SetForegroundWindow(window.hwnd)
                return True
            except Exception:
                return False
        elif HAS_PYGETWINDOW:
            try:
                w = gw.getWindowsWithTitle(window.title)[0]
                if w.isMinimized:
                    w.restore()
                w.activate()
                return True
            except Exception:
                return False

        return False

    def move_window(self, app_name: str, x: int, y: int) -> bool:
        """Move a window to specific coordinates.

        Args:
            app_name: Application name or window title
            x: New X position
            y: New Y position

        Returns:
            True if successful, False otherwise
        """
        window = self.find_window(app_name)
        if not window:
            return False

        if HAS_WIN32:
            try:
                win32gui.SetWindowPos(
                    window.hwnd, 0, x, y,
                    window.width, window.height,
                    win32con.SWP_NOSIZE | win32con.SWP_NOZORDER
                )
                return True
            except Exception:
                return False
        elif HAS_PYGETWINDOW:
            try:
                w = gw.getWindowsWithTitle(window.title)[0]
                w.moveTo(x, y)
                return True
            except Exception:
                return False

        return False

    def resize_window(self, app_name: str, width: int, height: int) -> bool:
        """Resize a window.

        Args:
            app_name: Application name or window title
            width: New width
            height: New height

        Returns:
            True if successful, False otherwise
        """
        window = self.find_window(app_name)
        if not window:
            return False

        if HAS_WIN32:
            try:
                win32gui.SetWindowPos(
                    window.hwnd, 0,
                    window.x, window.y, width, height,
                    win32con.SWP_NOMOVE | win32con.SWP_NOZORDER
                )
                return True
            except Exception:
                return False
        elif HAS_PYGETWINDOW:
            try:
                w = gw.getWindowsWithTitle(window.title)[0]
                w.resizeTo(width, height)
                return True
            except Exception:
                return False

        return False

    def set_window_position(
        self,
        app_name: str,
        x: int,
        y: int,
        width: int,
        height: int
    ) -> bool:
        """Set window position and size.

        Args:
            app_name: Application name or window title
            x: X position
            y: Y position
            width: Width
            height: Height

        Returns:
            True if successful, False otherwise
        """
        window = self.find_window(app_name)
        if not window:
            return False

        if HAS_WIN32:
            try:
                # Restore first if minimized/maximized
                if window.is_minimized or window.is_maximized:
                    win32gui.ShowWindow(window.hwnd, win32con.SW_RESTORE)

                win32gui.SetWindowPos(
                    window.hwnd, 0, x, y, width, height,
                    win32con.SWP_NOZORDER
                )
                return True
            except Exception:
                return False
        elif HAS_PYGETWINDOW:
            try:
                w = gw.getWindowsWithTitle(window.title)[0]
                if w.isMinimized:
                    w.restore()
                w.moveTo(x, y)
                w.resizeTo(width, height)
                return True
            except Exception:
                return False

        return False

    def arrange_windows(
        self,
        layout: str = "tile_horizontal",
        app_names: Optional[List[str]] = None
    ) -> bool:
        """Arrange windows according to a layout.

        Args:
            layout: Layout name (cascade, tile_horizontal, tile_vertical,
                   grid_2x2, left_right, top_bottom, focus_center)
            app_names: Optional list of app names to arrange (None = all visible)

        Returns:
            True if successful, False otherwise
        """
        # Get windows to arrange
        if app_names:
            windows = []
            for name in app_names:
                w = self.find_window(name)
                if w:
                    windows.append(w)
        else:
            windows = [w for w in self.get_all_windows()
                      if w.width > 100 and w.height > 100]

        if not windows:
            return False

        self._update_screen_size()
        sw, sh = self._screen_width, self._screen_height

        # Apply layout
        if layout == "cascade" or layout == WindowLayout.CASCADE.value:
            return self._arrange_cascade(windows, sw, sh)
        elif layout == "tile_horizontal" or layout == WindowLayout.TILE_HORIZONTAL.value:
            return self._arrange_tile_horizontal(windows, sw, sh)
        elif layout == "tile_vertical" or layout == WindowLayout.TILE_VERTICAL.value:
            return self._arrange_tile_vertical(windows, sw, sh)
        elif layout == "grid_2x2" or layout == WindowLayout.GRID_2X2.value:
            return self._arrange_grid(windows, sw, sh, 2, 2)
        elif layout == "left_right" or layout == WindowLayout.LEFT_RIGHT.value:
            return self._arrange_left_right(windows, sw, sh)
        elif layout == "top_bottom" or layout == WindowLayout.TOP_BOTTOM.value:
            return self._arrange_top_bottom(windows, sw, sh)
        elif layout == "focus_center" or layout == WindowLayout.FOCUS_CENTER.value:
            return self._arrange_focus_center(windows, sw, sh)

        return False

    def _arrange_cascade(self, windows: List[WindowInfo], sw: int, sh: int) -> bool:
        """Cascade windows diagonally."""
        offset = 30
        width = int(sw * 0.6)
        height = int(sh * 0.6)

        for i, w in enumerate(windows):
            x = offset * i
            y = offset * i
            self.set_window_position(w.title, x, y, width, height)

        return True

    def _arrange_tile_horizontal(self, windows: List[WindowInfo], sw: int, sh: int) -> bool:
        """Tile windows horizontally (side by side)."""
        count = len(windows)
        if count == 0:
            return False

        width = sw // count
        for i, w in enumerate(windows):
            self.set_window_position(w.title, i * width, 0, width, sh)

        return True

    def _arrange_tile_vertical(self, windows: List[WindowInfo], sw: int, sh: int) -> bool:
        """Tile windows vertically (stacked)."""
        count = len(windows)
        if count == 0:
            return False

        height = sh // count
        for i, w in enumerate(windows):
            self.set_window_position(w.title, 0, i * height, sw, height)

        return True

    def _arrange_grid(self, windows: List[WindowInfo], sw: int, sh: int, cols: int, rows: int) -> bool:
        """Arrange windows in a grid."""
        cell_w = sw // cols
        cell_h = sh // rows

        for i, w in enumerate(windows[:cols * rows]):
            row = i // cols
            col = i % cols
            x = col * cell_w
            y = row * cell_h
            self.set_window_position(w.title, x, y, cell_w, cell_h)

        return True

    def _arrange_left_right(self, windows: List[WindowInfo], sw: int, sh: int) -> bool:
        """Arrange first window on left, rest on right."""
        if len(windows) == 0:
            return False

        # First window takes left half
        self.set_window_position(windows[0].title, 0, 0, sw // 2, sh)

        # Rest take right half, stacked
        if len(windows) > 1:
            right_count = len(windows) - 1
            height = sh // right_count
            for i, w in enumerate(windows[1:]):
                self.set_window_position(w.title, sw // 2, i * height, sw // 2, height)

        return True

    def _arrange_top_bottom(self, windows: List[WindowInfo], sw: int, sh: int) -> bool:
        """Arrange first window on top, rest on bottom."""
        if len(windows) == 0:
            return False

        # First window takes top half
        self.set_window_position(windows[0].title, 0, 0, sw, sh // 2)

        # Rest take bottom half, side by side
        if len(windows) > 1:
            bottom_count = len(windows) - 1
            width = sw // bottom_count
            for i, w in enumerate(windows[1:]):
                self.set_window_position(w.title, i * width, sh // 2, width, sh // 2)

        return True

    def _arrange_focus_center(self, windows: List[WindowInfo], sw: int, sh: int) -> bool:
        """Put first window in center, minimize others."""
        if len(windows) == 0:
            return False

        # Center window (80% of screen)
        width = int(sw * 0.8)
        height = int(sh * 0.8)
        x = (sw - width) // 2
        y = (sh - height) // 2
        self.set_window_position(windows[0].title, x, y, width, height)
        self.focus_window(windows[0].title)

        # Minimize others
        for w in windows[1:]:
            self.minimize_window(w.title)

        return True

    def close_window(self, app_name: str) -> bool:
        """Close a window.

        Args:
            app_name: Application name or window title

        Returns:
            True if successful, False otherwise
        """
        window = self.find_window(app_name)
        if not window:
            return False

        if HAS_WIN32:
            try:
                win32gui.PostMessage(window.hwnd, win32con.WM_CLOSE, 0, 0)
                return True
            except Exception:
                return False
        elif HAS_PYGETWINDOW:
            try:
                w = gw.getWindowsWithTitle(window.title)[0]
                w.close()
                return True
            except Exception:
                return False

        return False

    def minimize_all(self) -> int:
        """Minimize all windows.

        Returns:
            Number of windows minimized
        """
        count = 0
        for w in self.get_all_windows():
            if self.minimize_window(w.title):
                count += 1
        return count

    def list_windows(self) -> List[str]:
        """Get list of all window titles.

        Returns:
            List of window title strings
        """
        return [w.title for w in self.get_all_windows()]


# Global instance
_window_manager: Optional[WindowManager] = None


def get_window_manager() -> WindowManager:
    """Get or create the global WindowManager instance."""
    global _window_manager
    if _window_manager is None:
        _window_manager = WindowManager()
    return _window_manager


# Convenience functions (per ARCHITECTURE.md spec)
def minimize_window(app_name: str) -> bool:
    """Minimize a window by application name."""
    return get_window_manager().minimize_window(app_name)


def maximize_window(app_name: str) -> bool:
    """Maximize a window by application name."""
    return get_window_manager().maximize_window(app_name)


def arrange_windows(layout: str = "tile_horizontal", app_names: Optional[List[str]] = None) -> bool:
    """Arrange windows according to a layout."""
    return get_window_manager().arrange_windows(layout, app_names)


def focus_window(app_name: str) -> bool:
    """Bring a window to the foreground."""
    return get_window_manager().focus_window(app_name)


def list_windows() -> List[str]:
    """Get list of all window titles."""
    return get_window_manager().list_windows()


def close_window(app_name: str) -> bool:
    """Close a window."""
    return get_window_manager().close_window(app_name)


# Module test
if __name__ == '__main__':
    print("=== WINDOW MANAGEMENT TEST ===\n")

    print(f"win32gui available: {HAS_WIN32}")
    print(f"pygetwindow available: {HAS_PYGETWINDOW}")

    if not HAS_WIN32 and not HAS_PYGETWINDOW:
        print("\nNo window management libraries available.")
        print("Install with: pip install pywin32 pygetwindow")
    else:
        wm = get_window_manager()

        print(f"\nScreen size: {wm._screen_width}x{wm._screen_height}")

        print("\n--- All Windows ---")
        windows = wm.get_all_windows()
        for i, w in enumerate(windows[:10]):
            state = "min" if w.is_minimized else ("max" if w.is_maximized else "normal")
            print(f"{i+1}. [{state}] {w.title[:50]}")

        if len(windows) > 10:
            print(f"   ... and {len(windows) - 10} more")

        print(f"\nTotal windows: {len(windows)}")

    print("\n=== TEST COMPLETE ===")
