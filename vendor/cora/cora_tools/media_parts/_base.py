#!/usr/bin/env python3
"""Shared base of the cora_tools.media_parts package (split from cora_tools/media.py on 2026-10-14): imports, module
state, the helpers and every function that rebinds a module global."""
from __future__ import annotations
r"""
# ================================================================
#   ____   ___   ____      _
#  / ___| / _ \ |  _ \    / \
# | |    | | | || |_) |  / _ \
# | |___ | |_| ||  _ <  / ___ \
#  \____| \___/ |_| \_\/_/   \_\
#
# C.O.R.A Media Control Module
# ================================================================
# Version: 1.0.0
# Unity AI Lab
# Website: https://www.unityailab.com
# GitHub: https://github.com/Unity-Lab-AI
# Contact: unityailabcontact@gmail.com
# Creators: Hackall360, Sponge, GFourteen, Alfreddo
# ================================================================
#
# Media control with multiple backends:
# 1. System Media Keys - Control ANY playing app (Spotify, VLC, etc)
# 2. Local File Playback - Play MP3/MP4 files directly
# 3. YouTube Playback - Play YouTube URLs
# 4. Emby (optional) - Control Emby media server if configured
#
# ================================================================
"""

import os
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict, Any
import json


def get_media() -> MediaController:
    from cora_tools.media_parts.unified_media_controller import MediaController
    """Get or create global media controller."""
    global _media
    if _media is None:
        _media = MediaController()
    return _media


# ================================================================
# GLOBAL INSTANCE & CONVENIENCE FUNCTIONS
# ================================================================

_media: MediaController = None
