#!/usr/bin/env python3
"""cora_tools.media_parts: unified_media_controller (split from cora_tools/media.py on 2026-10-14)."""
from __future__ import annotations

import os
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from cora_tools.media_parts import _base  # noqa: F401
from cora_tools.media_parts._base import Path  # noqa: F401




# ================================================================
# UNIFIED MEDIA CONTROLLER
# ================================================================

class MediaController:
    """
    Unified media controller - automatically routes to best backend.

    Priority:
    1. YouTube URLs -> YouTubePlayer
    2. Local files -> LocalMediaPlayer
    3. Emby queries (if configured) -> EmbyControl
    4. System media keys -> SystemMediaControl
    """

    def __init__(self, config: dict = None):
        from cora_tools.media_parts.emby_media_server_optional import EmbyControl
        from cora_tools.media_parts.local_file_playback import LocalMediaPlayer
        from cora_tools.media_parts.system_media_keys_control_any import SystemMediaControl
        from cora_tools.media_parts.youtube_playback import YouTubePlayer
        from cora_tools.media_parts.configuration import load_media_config
        if config is None:
            config = load_media_config()

        self.config = config
        self.system = SystemMediaControl()
        self.local = LocalMediaPlayer(config.get('local_player', 'default'))
        self.youtube = YouTubePlayer(config.get('youtube_method', 'browser'))
        self.emby = EmbyControl(config)

    def play(self, target: str = None) -> dict:
        from cora_tools.media_parts.configuration import MEDIA_EXTENSIONS
        from cora_tools.media_parts.global_instance_convenience_fu import play
        """
        Smart play - figures out what to do based on input.

        - No target: Toggle play/pause on current app
        - YouTube URL: Open in browser/player
        - File path: Play local file
        - Search query: Search YouTube (or Emby if configured)
        """
        if not target:
            return self.system.play_pause()

        target = target.strip()

        # Check if it's a YouTube URL
        if self.youtube.is_youtube_url(target):
            return self.youtube.play(target)

        # Check if it's a local file
        if Path(target).exists():
            return self.local.play(target)

        # Check if it looks like a file path but doesn't exist
        if '\\' in target or '/' in target or target.endswith(tuple(MEDIA_EXTENSIONS)):
            return {'success': False, 'error': f'File not found: {target}'}

        # It's a search query - try Emby first if configured, then YouTube
        if self.emby.configured:
            results = self.emby.search(target)
            if results:
                item = results[0]
                result = self.emby.play(item['Id'])
                if result['success']:
                    result['source'] = 'emby'
                    result['title'] = item.get('Name', 'Unknown')
                    return result

        # Search YouTube
        return self.youtube.search_and_play(target)

    def pause(self) -> dict:
        from cora_tools.media_parts.global_instance_convenience_fu import pause
        """Pause playback."""
        # Try Emby first if configured
        if self.emby.configured:
            result = self.emby.pause()
            if result['success']:
                return result
        # Fall back to system media keys
        return self.system.pause()

    def resume(self) -> dict:
        """Resume playback."""
        return self.system.play_pause()

    def stop(self) -> dict:
        from cora_tools.media_parts.global_instance_convenience_fu import stop
        """Stop playback."""
        if self.emby.configured:
            result = self.emby.stop()
            if result['success']:
                return result
        return self.system.stop()

    def next_track(self) -> dict:
        from cora_tools.media_parts.global_instance_convenience_fu import next_track
        """Next track."""
        if self.emby.configured:
            result = self.emby.next_track()
            if result['success']:
                return result
        return self.system.next_track()

    def prev_track(self) -> dict:
        from cora_tools.media_parts.global_instance_convenience_fu import prev_track
        """Previous track."""
        if self.emby.configured:
            result = self.emby.prev_track()
            if result['success']:
                return result
        return self.system.prev_track()

    def volume_up(self) -> dict:
        """Volume up."""
        return self.system.volume_up()

    def volume_down(self) -> dict:
        """Volume down."""
        return self.system.volume_down()

    def mute(self) -> dict:
        from cora_tools.media_parts.global_instance_convenience_fu import mute
        """Toggle mute."""
        return self.system.mute()

    def set_volume(self, level: int) -> dict:
        """Set volume to specific level (0-100)."""
        return self.system.set_volume(level)

    def get_volume(self) -> int:
        """Get current volume."""
        return self.system.get_volume()

    def now_playing(self) -> str:
        """Get what's playing (Emby only for now)."""
        if self.emby.configured:
            return self.emby.now_playing()
        return "Use Spotify/VLC/etc - check your player for now playing info"
