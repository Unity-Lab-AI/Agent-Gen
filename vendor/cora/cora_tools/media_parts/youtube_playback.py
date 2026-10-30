#!/usr/bin/env python3
"""cora_tools.media_parts: youtube_playback (split from cora_tools/media.py on 2026-10-14)."""
from __future__ import annotations

import os
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from cora_tools.media_parts import _base  # noqa: F401
from cora_tools.media_parts._base import Optional, Path, re, subprocess, webbrowser  # noqa: F401




# ================================================================
# YOUTUBE PLAYBACK
# ================================================================

class YouTubePlayer:
    """Play YouTube videos/audio."""

    # YouTube URL patterns
    YT_PATTERNS = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]

    def __init__(self, method: str = 'browser'):
        """
        Args:
            method: 'browser', 'mpv', 'vlc', 'download'
        """
        self.method = method
        self.current_process = None

    def is_youtube_url(self, url: str) -> bool:
        """Check if URL is a YouTube link."""
        for pattern in self.YT_PATTERNS:
            if re.match(pattern, url):
                return True
        return False

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        for pattern in self.YT_PATTERNS:
            match = re.match(pattern, url)
            if match:
                return match.group(1)
        return None

    def play(self, url: str, audio_only: bool = False) -> dict:
        """Play a YouTube video."""
        if not self.is_youtube_url(url):
            return {'success': False, 'error': 'Not a valid YouTube URL'}

        video_id = self.extract_video_id(url)
        clean_url = f'https://www.youtube.com/watch?v={video_id}'

        if self.method == 'browser':
            return self._play_in_browser(clean_url)
        elif self.method == 'mpv':
            return self._play_with_mpv(clean_url, audio_only)
        elif self.method == 'vlc':
            return self._play_with_vlc(clean_url)
        else:
            # Default to browser
            return self._play_in_browser(clean_url)

    def _play_in_browser(self, url: str) -> dict:
        """Open YouTube in default browser."""
        try:
            webbrowser.open(url)
            return {
                'success': True,
                'message': 'Opened in browser',
                'url': url,
                'method': 'browser'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _play_with_mpv(self, url: str, audio_only: bool = False) -> dict:
        """Play with mpv (requires mpv + yt-dlp installed)."""
        try:
            cmd = ['mpv']
            if audio_only:
                cmd.extend(['--no-video'])
            cmd.append(url)

            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            return {
                'success': True,
                'message': 'Playing with mpv',
                'url': url,
                'audio_only': audio_only
            }
        except FileNotFoundError:
            return {'success': False, 'error': 'mpv not found. Install mpv and yt-dlp'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _play_with_vlc(self, url: str) -> dict:
        """Play with VLC (requires VLC installed)."""
        vlc_paths = [
            r'C:\Program Files\VideoLAN\VLC\vlc.exe',
            r'C:\Program Files (x86)\VideoLAN\VLC\vlc.exe',
        ]

        vlc_path = None
        for path in vlc_paths:
            if Path(path).exists():
                vlc_path = path
                break

        if not vlc_path:
            return {'success': False, 'error': 'VLC not found'}

        try:
            self.current_process = subprocess.Popen(
                [vlc_path, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return {
                'success': True,
                'message': 'Playing with VLC',
                'url': url
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def search_and_play(self, query: str, audio_only: bool = False) -> dict:
        from cora_tools.media_parts.global_instance_convenience_fu import play
        """Search YouTube and play first result (requires yt-dlp)."""
        try:
            # Use yt-dlp to search
            result = subprocess.run(
                ['yt-dlp', '--get-id', f'ytsearch1:{query}'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0 and result.stdout.strip():
                video_id = result.stdout.strip()
                url = f'https://www.youtube.com/watch?v={video_id}'
                return self.play(url, audio_only)
            else:
                return {'success': False, 'error': f'No results for: {query}'}

        except FileNotFoundError:
            # Fallback: open YouTube search in browser
            search_url = f'https://www.youtube.com/results?search_query={query.replace(" ", "+")}'
            webbrowser.open(search_url)
            return {
                'success': True,
                'message': 'Opened YouTube search in browser (install yt-dlp for direct play)',
                'query': query
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
