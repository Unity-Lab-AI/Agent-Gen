#!/usr/bin/env python3
"""cora_tools.media_parts: system_media_keys_control_any (split from cora_tools/media.py on 2026-10-14)."""
from __future__ import annotations

import os
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from cora_tools.media_parts import _base  # noqa: F401




# ================================================================
# SYSTEM MEDIA KEYS - Control ANY playing app
# ================================================================

class SystemMediaControl:
    """
    Control system media playback using keyboard media keys.
    Works with Spotify, VLC, YouTube in browser, Windows Media Player, etc.
    """

    def __init__(self):
        self.available = False
        self._init_backend()

    def _init_backend(self):
        """Initialize the best available backend for media keys."""
        # Try pycaw for Windows audio control
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            self.available = True
            self._backend = 'pycaw'
            return
        except ImportError:
            pass

        # Fallback: use keyboard simulation
        try:
            import keyboard
            self.available = True
            self._backend = 'keyboard'
            return
        except ImportError:
            pass

        # Fallback: use pyautogui
        try:
            import pyautogui
            self.available = True
            self._backend = 'pyautogui'
            return
        except ImportError:
            pass

        # Final fallback: use ctypes directly for Windows
        try:
            import ctypes
            self.available = True
            self._backend = 'ctypes'
        except:
            self._backend = None

    def _send_media_key(self, key_code: int) -> bool:
        """Send a media key press using Windows API."""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32

            # Virtual key codes for media keys
            VK_MEDIA_PLAY_PAUSE = 0xB3
            VK_MEDIA_NEXT_TRACK = 0xB0
            VK_MEDIA_PREV_TRACK = 0xB1
            VK_MEDIA_STOP = 0xB2
            VK_VOLUME_MUTE = 0xAD
            VK_VOLUME_DOWN = 0xAE
            VK_VOLUME_UP = 0xAF

            KEYEVENTF_EXTENDEDKEY = 0x0001
            KEYEVENTF_KEYUP = 0x0002

            # Key down
            user32.keybd_event(key_code, 0, KEYEVENTF_EXTENDEDKEY, 0)
            # Key up
            user32.keybd_event(key_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)

            return True
        except Exception as e:
            print(f"[MEDIA] Key send error: {e}")
            return False

    def play_pause(self) -> dict:
        """Toggle play/pause."""
        VK_MEDIA_PLAY_PAUSE = 0xB3
        success = self._send_media_key(VK_MEDIA_PLAY_PAUSE)
        return {'success': success, 'action': 'play_pause'}

    def play(self) -> dict:
        """Play (same as play_pause for most apps)."""
        return self.play_pause()

    def pause(self) -> dict:
        """Pause (same as play_pause for most apps)."""
        return self.play_pause()

    def stop(self) -> dict:
        """Stop playback."""
        VK_MEDIA_STOP = 0xB2
        success = self._send_media_key(VK_MEDIA_STOP)
        return {'success': success, 'action': 'stop'}

    def next_track(self) -> dict:
        """Skip to next track."""
        VK_MEDIA_NEXT_TRACK = 0xB0
        success = self._send_media_key(VK_MEDIA_NEXT_TRACK)
        return {'success': success, 'action': 'next'}

    def prev_track(self) -> dict:
        """Go to previous track."""
        VK_MEDIA_PREV_TRACK = 0xB1
        success = self._send_media_key(VK_MEDIA_PREV_TRACK)
        return {'success': success, 'action': 'previous'}

    def volume_up(self, steps: int = 2) -> dict:
        """Increase volume."""
        VK_VOLUME_UP = 0xAF
        for _ in range(steps):
            self._send_media_key(VK_VOLUME_UP)
        return {'success': True, 'action': 'volume_up', 'steps': steps}

    def volume_down(self, steps: int = 2) -> dict:
        """Decrease volume."""
        VK_VOLUME_DOWN = 0xAE
        for _ in range(steps):
            self._send_media_key(VK_VOLUME_DOWN)
        return {'success': True, 'action': 'volume_down', 'steps': steps}

    def mute(self) -> dict:
        """Toggle mute."""
        VK_VOLUME_MUTE = 0xAD
        success = self._send_media_key(VK_VOLUME_MUTE)
        return {'success': success, 'action': 'mute'}

    def set_volume(self, level: int) -> dict:
        from cora_tools.media_parts.global_instance_convenience_fu import volume
        """Set volume to specific level (0-100)."""
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))

            # Convert 0-100 to 0.0-1.0
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            return {'success': True, 'action': 'set_volume', 'level': level}
        except ImportError:
            return {'success': False, 'error': 'pycaw not installed. Run: pip install pycaw'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_volume(self) -> int:
        from cora_tools.media_parts.global_instance_convenience_fu import volume
        """Get current volume level (0-100)."""
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))

            return int(volume.GetMasterVolumeLevelScalar() * 100)
        except:
            return -1
