#!/usr/bin/env python3
"""cora_tools.media_parts: emby_media_server_optional (split from cora_tools/media.py on 2026-10-14)."""
from __future__ import annotations

import os
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from cora_tools.media_parts import _base  # noqa: F401
from cora_tools.media_parts._base import List, json  # noqa: F401




# ================================================================
# EMBY MEDIA SERVER (Optional)
# ================================================================

class EmbyControl:
    """Control Emby media server - play, pause, search, etc."""

    def __init__(self, config: dict = None):
        from cora_tools.media_parts.configuration import load_media_config
        if config is None:
            config = load_media_config()

        server = config.get('emby_server', '')
        port = config.get('emby_port', '8096')
        self.api_key = config.get('emby_api_key', '')

        self.base_url = f"http://{server}:{port}/emby" if server else ''
        self.headers = {'X-Emby-Token': self.api_key} if self.api_key else {}
        self.configured = bool(server and self.api_key)

    def _check_configured(self) -> dict:
        from cora_tools.media_parts.configuration import MEDIA_CONFIG_FILE
        """Check if Emby is configured."""
        if not self.configured:
            return {
                'success': False,
                'error': 'Emby not configured',
                'hint': f'Create {MEDIA_CONFIG_FILE} with emby_server, emby_port, emby_api_key'
            }
        return None

    def get_sessions(self) -> List[dict]:
        """Get active Emby sessions."""
        if not self.configured:
            return []
        try:
            import requests
            response = requests.get(
                f"{self.base_url}/../Sessions",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"[EMBY] Error getting sessions: {e}")
        return []

    def get_controllable_session(self) -> tuple:
        """Find a session that supports remote control."""
        sessions = self.get_sessions()
        for session in sessions:
            if session.get('SupportsRemoteControl', False):
                return session['Id'], session.get('DeviceName', 'Unknown')
        return None, None

    def search(self, query: str, media_type: str = None, limit: int = 10) -> List[dict]:
        """Search Emby library."""
        err = self._check_configured()
        if err:
            return []

        try:
            import requests
            # Get user ID first
            resp = requests.get(f"{self.base_url}/Users", headers=self.headers, timeout=10)
            if resp.status_code != 200:
                return []
            users = resp.json()
            user_id = users[0]['Id'] if users else None
            if not user_id:
                return []

            url = f"{self.base_url}/Users/{user_id}/Items"
            params = {
                'SearchTerm': query,
                'Recursive': 'true',
                'Limit': limit,
                'Fields': 'PrimaryImageAspectRatio,Overview',
                'api_key': self.api_key
            }
            if media_type:
                params['IncludeItemTypes'] = media_type

            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json().get('Items', [])
        except Exception as e:
            print(f"[EMBY] Search error: {e}")
        return []

    def play(self, item_id: str) -> dict:
        """Play an item by ID."""
        err = self._check_configured()
        if err:
            return err

        session_id, device = self.get_controllable_session()
        if not session_id:
            return {'success': False, 'error': 'No controllable Emby session found'}

        try:
            import requests
            url = f"{self.base_url}/../Sessions/{session_id}/Playing"
            data = {'ItemIds': item_id, 'PlayCommand': 'PlayNow'}
            response = requests.post(url, headers=self.headers, json=data, timeout=10)

            if response.status_code == 204:
                return {'success': True, 'message': f'Playing on {device}'}
            return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def control(self, command: str) -> dict:
        """Control playback: Pause, Unpause, Stop, NextTrack, PreviousTrack."""
        err = self._check_configured()
        if err:
            return err

        session_id, device = self.get_controllable_session()
        if not session_id:
            return {'success': False, 'error': 'No controllable session'}

        try:
            import requests
            url = f"{self.base_url}/../Sessions/{session_id}/Playing/{command}"
            response = requests.post(url, headers=self.headers, timeout=10)

            if response.status_code == 204:
                return {'success': True, 'message': f'{command} on {device}'}
            return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def now_playing(self) -> str:
        """Get what's currently playing."""
        if not self.configured:
            return "Emby not configured"

        sessions = self.get_sessions()
        for session in sessions:
            if session.get('NowPlayingItem'):
                item = session['NowPlayingItem']
                name = item.get('Name', 'Unknown')
                item_type = item.get('Type', '')
                artist = item.get('Artists', [''])[0] if item.get('Artists') else ''
                is_paused = session.get('PlayState', {}).get('IsPaused', False)
                status = "Paused" if is_paused else "Playing"

                if artist:
                    return f"{status}: {artist} - {name}"
                return f"{status}: {name} ({item_type})"
        return "Nothing playing"

    def pause(self) -> dict:
        return self.control('Pause')

    def resume(self) -> dict:
        return self.control('Unpause')

    def stop(self) -> dict:
        return self.control('Stop')

    def next_track(self) -> dict:
        return self.control('NextTrack')

    def prev_track(self) -> dict:
        return self.control('PreviousTrack')
