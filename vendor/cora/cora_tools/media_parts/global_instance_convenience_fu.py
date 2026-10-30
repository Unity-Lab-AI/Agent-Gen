#!/usr/bin/env python3
"""cora_tools.media_parts: global_instance_convenience_fu (split from cora_tools/media.py on 2026-10-14)."""
from __future__ import annotations

import os
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from cora_tools.media_parts import _base  # noqa: F401
from cora_tools.media_parts._base import get_media  # noqa: F401




# CLI-friendly functions
def play(target: str = None) -> str:
    """Play media - URL, file, or search query."""
    result = get_media().play(target)
    if result['success']:
        msg = result.get('message', 'Playing')
        if result.get('title'):
            msg += f": {result['title']}"
        elif result.get('file'):
            msg += f": {result['file']}"
        return f"[+] {msg}"
    return f"[!] {result.get('error', 'Failed')}"


def pause() -> str:
    """Pause playback."""
    result = get_media().pause()
    return "[+] Paused" if result['success'] else f"[!] {result.get('error', 'Failed')}"


def resume() -> str:
    """Resume playback."""
    result = get_media().resume()
    return "[+] Resumed" if result['success'] else f"[!] {result.get('error', 'Failed')}"


def stop() -> str:
    """Stop playback."""
    result = get_media().stop()
    return "[+] Stopped" if result['success'] else f"[!] {result.get('error', 'Failed')}"


def next_track() -> str:
    """Next track."""
    result = get_media().next_track()
    return "[+] Next track" if result['success'] else f"[!] {result.get('error', 'Failed')}"


def prev_track() -> str:
    """Previous track."""
    result = get_media().prev_track()
    return "[+] Previous track" if result['success'] else f"[!] {result.get('error', 'Failed')}"


def volume(level: int = None) -> str:
    """Get or set volume."""
    media = get_media()
    if level is not None:
        result = media.set_volume(level)
        if result['success']:
            return f"[+] Volume set to {level}%"
        return f"[!] {result.get('error', 'Failed')}"
    else:
        vol = media.get_volume()
        return f"[+] Volume: {vol}%" if vol >= 0 else "[!] Couldn't get volume"


def mute() -> str:
    """Toggle mute."""
    result = get_media().mute()
    return "[+] Mute toggled" if result['success'] else f"[!] {result.get('error', 'Failed')}"


def now() -> str:
    """Get now playing."""
    return get_media().now_playing()
