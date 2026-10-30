#!/usr/bin/env python3
"""
C.O.R.A Global Hotkeys
System-wide keyboard shortcuts

Per ARCHITECTURE.md v1.0.0:
- Global hotkeys for quick actions
- Push-to-talk (Ctrl+Space)
- Quick query (Alt+C)
- Screenshot (Win+Shift+S style)
"""

import os
import sys
import threading
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass

# Optional imports
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

try:
    from pynput import keyboard as pynput_kb
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


@dataclass
class HotkeyConfig:
    """Configuration for a hotkey."""
    key: str
    callback: Callable
    description: str = ""
    enabled: bool = True


class HotkeyManager:
    """Manages global hotkeys for CORA."""

    def __init__(self):
        """Initialize hotkey manager."""
        self._hotkeys: Dict[str, HotkeyConfig] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._listener = None

        # Determine which library to use
        self._use_keyboard = KEYBOARD_AVAILABLE
        self._use_pynput = PYNPUT_AVAILABLE and not KEYBOARD_AVAILABLE

    def register(
        self,
        key: str,
        callback: Callable,
        description: str = ""
    ) -> bool:
        """Register a global hotkey.

        Args:
            key: Key combination (e.g., "ctrl+shift+c", "alt+c")
            callback: Function to call when hotkey pressed
            description: Human-readable description

        Returns:
            True if registered successfully
        """
        config = HotkeyConfig(
            key=key.lower(),
            callback=callback,
            description=description
        )

        self._hotkeys[key.lower()] = config

        # If already running, add hotkey immediately
        if self._running and self._use_keyboard:
            try:
                keyboard.add_hotkey(key, callback)
                return True
            except Exception as e:
                print(f"[!] Hotkey register error: {e}")
                return False

        return True

    def unregister(self, key: str) -> bool:
        """Unregister a hotkey.

        Args:
            key: Key combination to remove

        Returns:
            True if removed
        """
        key_lower = key.lower()
        if key_lower in self._hotkeys:
            del self._hotkeys[key_lower]

            if self._running and self._use_keyboard:
                try:
                    keyboard.remove_hotkey(key)
                except Exception:
                    pass

            return True
        return False

    def start(self) -> bool:
        """Start listening for hotkeys.

        Returns:
            True if started successfully
        """
        if self._running:
            return True

        if self._use_keyboard:
            return self._start_keyboard()
        elif self._use_pynput:
            return self._start_pynput()
        else:
            print("[!] No hotkey library available")
            print("[!] Install: pip install keyboard  or  pip install pynput")
            return False

    def _start_keyboard(self) -> bool:
        """Start using keyboard library."""
        try:
            # Register all hotkeys
            for key, config in self._hotkeys.items():
                if config.enabled:
                    keyboard.add_hotkey(key, config.callback)

            self._running = True
            print(f"[HOTKEYS] Started with {len(self._hotkeys)} hotkeys")
            return True

        except Exception as e:
            print(f"[!] Keyboard start error: {e}")
            return False

    def _start_pynput(self) -> bool:
        """Start using pynput library."""
        try:
            # Create key combination handler
            current_keys = set()

            def on_press(key):
                try:
                    current_keys.add(key)
                    self._check_pynput_hotkeys(current_keys)
                except Exception:
                    pass

            def on_release(key):
                try:
                    current_keys.discard(key)
                except Exception:
                    pass

            self._listener = pynput_kb.Listener(
                on_press=on_press,
                on_release=on_release
            )
            self._listener.start()
            self._running = True
            print(f"[HOTKEYS] Started (pynput) with {len(self._hotkeys)} hotkeys")
            return True

        except Exception as e:
            print(f"[!] Pynput start error: {e}")
            return False

    def _check_pynput_hotkeys(self, current_keys: set):
        """Check if current keys match any registered hotkey."""
        # Simple implementation - checks for key names
        key_names = set()
        for k in current_keys:
            if hasattr(k, 'char') and k.char:
                key_names.add(k.char.lower())
            elif hasattr(k, 'name'):
                key_names.add(k.name.lower())

        for hotkey, config in self._hotkeys.items():
            if not config.enabled:
                continue

            # Parse hotkey parts
            parts = set(p.strip().lower() for p in hotkey.split('+'))

            # Map common names
            mapped_parts = set()
            for p in parts:
                if p == 'ctrl':
                    mapped_parts.add('ctrl_l')
                    mapped_parts.add('ctrl_r')
                elif p == 'alt':
                    mapped_parts.add('alt_l')
                    mapped_parts.add('alt_r')
                elif p == 'shift':
                    mapped_parts.add('shift')
                else:
                    mapped_parts.add(p)

            # Check if all required keys are pressed
            if parts.issubset(key_names) or mapped_parts.issubset(key_names):
                try:
                    config.callback()
                except Exception as e:
                    print(f"[!] Hotkey callback error: {e}")

    def stop(self):
        """Stop listening for hotkeys."""
        if not self._running:
            return

        if self._use_keyboard:
            try:
                keyboard.unhook_all_hotkeys()
            except Exception:
                pass

        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass

        self._running = False
        print("[HOTKEYS] Stopped")

    def is_running(self) -> bool:
        """Check if hotkey manager is running."""
        return self._running

    def list_hotkeys(self) -> Dict[str, str]:
        """Get list of registered hotkeys.

        Returns:
            Dict of {key: description}
        """
        return {k: v.description for k, v in self._hotkeys.items()}


# Global manager instance
_manager: Optional[HotkeyManager] = None


def get_manager() -> HotkeyManager:
    """Get or create global hotkey manager.

    Returns:
        HotkeyManager instance
    """
    global _manager
    if _manager is None:
        _manager = HotkeyManager()
    return _manager


# Convenience functions

def register_hotkey(key: str, callback: Callable, description: str = "") -> bool:
    """Register a global hotkey.

    Args:
        key: Key combination (e.g., "ctrl+alt+c")
        callback: Function to call
        description: Human-readable description

    Returns:
        True if registered
    """
    return get_manager().register(key, callback, description)


def start_hotkeys() -> bool:
    """Start listening for hotkeys.

    Returns:
        True if started
    """
    return get_manager().start()


def stop_hotkeys():
    """Stop listening for hotkeys."""
    get_manager().stop()


# Default CORA hotkeys
def setup_cora_hotkeys(
    on_push_to_talk: Optional[Callable] = None,
    on_quick_query: Optional[Callable] = None,
    on_screenshot: Optional[Callable] = None,
    on_toggle: Optional[Callable] = None
) -> HotkeyManager:
    """Set up default CORA hotkeys.

    Args:
        on_push_to_talk: Called when push-to-talk pressed (Ctrl+Space)
        on_quick_query: Called for quick query (Alt+C)
        on_screenshot: Called for screenshot (Ctrl+Shift+S)
        on_toggle: Called to toggle CORA (Ctrl+Alt+C)

    Returns:
        Configured HotkeyManager
    """
    manager = get_manager()

    if on_push_to_talk:
        manager.register("ctrl+space", on_push_to_talk, "Push-to-talk")

    if on_quick_query:
        manager.register("alt+c", on_quick_query, "Quick query")

    if on_screenshot:
        manager.register("ctrl+shift+s", on_screenshot, "Screenshot")

    if on_toggle:
        manager.register("ctrl+alt+c", on_toggle, "Toggle CORA")

    return manager


if __name__ == "__main__":
    print("=== HOTKEY MANAGER TEST ===")

    if not KEYBOARD_AVAILABLE and not PYNPUT_AVAILABLE:
        print("[!] No hotkey library installed")
        print("[!] Install: pip install keyboard")
        print("       or:  pip install pynput")
        sys.exit(1)

    # Test callbacks
    def on_test():
        print("[TEST] Hotkey triggered!")

    def on_quit():
        print("[QUIT] Stopping...")
        stop_hotkeys()
        sys.exit(0)

    # Register hotkeys
    register_hotkey("ctrl+shift+t", on_test, "Test hotkey")
    register_hotkey("ctrl+q", on_quit, "Quit")

    print("\nRegistered hotkeys:")
    for key, desc in get_manager().list_hotkeys().items():
        print(f"  {key}: {desc}")

    print("\nPress Ctrl+Shift+T to test, Ctrl+Q to quit")

    if start_hotkeys():
        try:
            # Keep running
            import time
            while get_manager().is_running():
                time.sleep(0.1)
        except KeyboardInterrupt:
            stop_hotkeys()
    else:
        print("Failed to start hotkeys")
