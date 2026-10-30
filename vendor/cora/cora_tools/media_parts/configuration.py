#!/usr/bin/env python3
"""cora_tools.media_parts: configuration (split from cora_tools/media.py on 2026-10-14)."""
from __future__ import annotations

import os
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from cora_tools.media_parts import _base  # noqa: F401
from cora_tools.media_parts._base import Path, json  # noqa: F401


CONFIG_DIR = Path(__file__).parent.parent.parent / 'config'
MEDIA_CONFIG_FILE = CONFIG_DIR / 'media_config.json'

# Supported media extensions
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.wma'}
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm'}
MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


def load_media_config() -> dict:
    """Load media configuration."""
    default_config = {
        'default_backend': 'system',  # system, local, emby
        'youtube_method': 'browser',  # browser, mpv, vlc
        'local_player': 'default',    # default, mpv, vlc
        'emby_server': '',
        'emby_port': '8096',
        'emby_api_key': ''
    }

    if MEDIA_CONFIG_FILE.exists():
        try:
            with open(MEDIA_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                default_config.update(config)
        except Exception:
            pass

    return default_config
