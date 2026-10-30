#!/usr/bin/env python3
"""cora_tools.media_parts: local_file_playback (split from cora_tools/media.py on 2026-10-14)."""
from __future__ import annotations

import os
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from cora_tools.media_parts import _base  # noqa: F401
from cora_tools.media_parts._base import Path, os, subprocess  # noqa: F401




# ================================================================
# LOCAL FILE PLAYBACK
# ================================================================

class LocalMediaPlayer:
    """Play local media files (MP3, MP4, etc)."""

    def __init__(self, preferred_player: str = 'default'):
        """
        Args:
            preferred_player: 'default', 'mpv', 'vlc'
        """
        self.preferred_player = preferred_player
        self.current_process = None

    def _find_player(self) -> tuple:
        """Find available media player. Returns (player_path, player_name)."""
        # Check for mpv
        mpv_paths = [
            r'C:\Program Files\mpv\mpv.exe',
            r'C:\Program Files (x86)\mpv\mpv.exe',
            'mpv'  # In PATH
        ]
        for path in mpv_paths:
            if Path(path).exists() or self._is_in_path('mpv'):
                return (path if Path(path).exists() else 'mpv', 'mpv')

        # Check for VLC
        vlc_paths = [
            r'C:\Program Files\VideoLAN\VLC\vlc.exe',
            r'C:\Program Files (x86)\VideoLAN\VLC\vlc.exe',
            'vlc'
        ]
        for path in vlc_paths:
            if Path(path).exists() or self._is_in_path('vlc'):
                return (path if Path(path).exists() else 'vlc', 'vlc')

        # Fallback to system default
        return ('default', 'default')

    def _is_in_path(self, cmd: str) -> bool:
        """Check if command is in system PATH."""
        try:
            subprocess.run([cmd, '--version'], capture_output=True, timeout=5)
            return True
        except:
            return False

    def play(self, file_path: str) -> dict:
        from cora_tools.media_parts.configuration import AUDIO_EXTENSIONS, MEDIA_EXTENSIONS
        """Play a local media file."""
        path = Path(file_path)

        if not path.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}

        ext = path.suffix.lower()
        if ext not in MEDIA_EXTENSIONS:
            return {'success': False, 'error': f'Unsupported file type: {ext}'}

        try:
            if self.preferred_player == 'default':
                # Use system default player
                os.startfile(str(path))
                return {
                    'success': True,
                    'message': f'Opened with default player',
                    'file': path.name,
                    'type': 'audio' if ext in AUDIO_EXTENSIONS else 'video'
                }
            else:
                player_path, player_name = self._find_player()

                if player_name == 'default':
                    os.startfile(str(path))
                else:
                    self.current_process = subprocess.Popen(
                        [player_path, str(path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )

                return {
                    'success': True,
                    'message': f'Playing with {player_name}',
                    'file': path.name,
                    'player': player_name
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def stop(self) -> dict:
        """Stop current playback (if we started it)."""
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process = None
                return {'success': True, 'message': 'Stopped playback'}
            except:
                pass
        return {'success': False, 'error': 'No active playback to stop'}
