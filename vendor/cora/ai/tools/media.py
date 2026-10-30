#!/usr/bin/env python3
"""C.O.R.A tools: media. Registered on import (see ai/tools/__init__.py)."""

import json
import os
import re
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai.tools._base import PROJECT_DIR, Tool, _tool, _p, _ok, _err, get_tool, all_tools, tool_catalog_text

# =========================================================================== media
def _media(fn, *a):
    from cora_tools import media as M
    msg = getattr(M, fn)(*a)
    ok = not str(msg).startswith('[!]')
    return (_ok if ok else _err)(str(msg).replace('[+] ', '').replace('[!] ', ''))


@_tool('media_play', 'Play media: a file path, a YouTube URL, a search like "lofi beats", or empty to toggle play/pause.', 'media',
       {'target': _p('File, URL, or search; optional')})
def t_media_play(target: str = None):
    return _media('play', target or None)


@_tool('media_pause', 'Pause playback.', 'media')
def t_media_pause():
    return _media('pause')


@_tool('media_resume', 'Resume playback.', 'media')
def t_media_resume():
    return _media('resume')


@_tool('media_stop', 'Stop playback.', 'media')
def t_media_stop():
    return _media('stop')


@_tool('media_next', 'Next track.', 'media')
def t_media_next():
    return _media('next_track')


@_tool('media_previous', 'Previous track.', 'media')
def t_media_previous():
    return _media('prev_track')


@_tool('media_volume', 'Get or set media volume 0-100.', 'media', {'level': _p('0-100, omit to read', 'integer')})
def t_media_volume(level: int = None):
    return _media('volume', int(level)) if level is not None else _media('volume')


@_tool('media_mute', 'Toggle mute.', 'media')
def t_media_mute():
    return _media('mute')


@_tool('now_playing', "What's playing now.", 'media')
def t_now_playing():
    return _media('now')
