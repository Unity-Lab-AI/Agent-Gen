#!/usr/bin/env python3
"""voice.cmd_parts: media_control_commands (split from voice/commands.py on 2026-10-14)."""
from __future__ import annotations

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass
from voice.cmd_parts import _base  # noqa: F401
from voice.cmd_parts._base import CommandResult, Dict, PROJECT_DIR, register_command, sys  # noqa: F401




# ============ MEDIA CONTROL COMMANDS ============

@register_command("play", aliases=["play music", "play video", "play song"])
def cmd_play(args: str, context: Dict) -> CommandResult:
    """Play media - file, YouTube URL, or search query."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.media import play, get_media

        if not args:
            # Toggle play/pause
            result = get_media().play()
            return CommandResult(
                success=result['success'],
                message="Toggled play/pause" if result['success'] else "Media control failed",
                should_speak=True
            )

        # Play specific target
        msg = play(args.strip())
        success = msg.startswith("[+]")
        return CommandResult(
            success=success,
            message=msg.replace("[+] ", "").replace("[!] ", ""),
            should_speak=True
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Media error: {e}",
            should_speak=True
        )


@register_command("pause", aliases=["pause music", "pause video"])
def cmd_pause(args: str, context: Dict) -> CommandResult:
    """Pause current media playback."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.media import pause

        msg = pause()
        success = msg.startswith("[+]")
        return CommandResult(
            success=success,
            message="Paused" if success else "Failed to pause",
            should_speak=True
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Pause error: {e}",
            should_speak=True
        )


@register_command("resume", aliases=["unpause", "continue playing"])
def cmd_resume(args: str, context: Dict) -> CommandResult:
    """Resume media playback."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.media import resume

        msg = resume()
        success = msg.startswith("[+]")
        return CommandResult(
            success=success,
            message="Resumed" if success else "Failed to resume",
            should_speak=True
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Resume error: {e}",
            should_speak=True
        )


@register_command("stop", aliases=["stop music", "stop video", "stop playing"])
def cmd_stop(args: str, context: Dict) -> CommandResult:
    """Stop media playback."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.media import stop

        msg = stop()
        success = msg.startswith("[+]")
        return CommandResult(
            success=success,
            message="Stopped" if success else "Failed to stop",
            should_speak=True
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Stop error: {e}",
            should_speak=True
        )


@register_command("next", aliases=["next track", "next song", "skip"])
def cmd_next(args: str, context: Dict) -> CommandResult:
    """Skip to next track."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.media import next_track

        msg = next_track()
        success = msg.startswith("[+]")
        return CommandResult(
            success=success,
            message="Next track" if success else "Failed to skip",
            should_speak=True
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Next error: {e}",
            should_speak=True
        )


@register_command("previous", aliases=["prev", "previous track", "previous song", "go back"])
def cmd_prev(args: str, context: Dict) -> CommandResult:
    """Go to previous track."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.media import prev_track

        msg = prev_track()
        success = msg.startswith("[+]")
        return CommandResult(
            success=success,
            message="Previous track" if success else "Failed",
            should_speak=True
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Previous error: {e}",
            should_speak=True
        )


@register_command("volume", aliases=["set volume", "volume level"])
def cmd_volume(args: str, context: Dict) -> CommandResult:
    """Get or set volume (0-100)."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.media import volume

        if args:
            # Try to parse volume level
            try:
                level = int(args.strip().replace("%", ""))
                level = max(0, min(100, level))  # Clamp to 0-100
                msg = volume(level)
            except ValueError:
                return CommandResult(
                    success=False,
                    message=f"Invalid volume level: {args}",
                    should_speak=True
                )
        else:
            msg = volume()

        success = msg.startswith("[+]")
        return CommandResult(
            success=success,
            message=msg.replace("[+] ", "").replace("[!] ", ""),
            should_speak=True
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Volume error: {e}",
            should_speak=True
        )


@register_command("mute", aliases=["unmute", "toggle mute"])
def cmd_mute(args: str, context: Dict) -> CommandResult:
    """Toggle mute."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.media import mute

        msg = mute()
        success = msg.startswith("[+]")
        return CommandResult(
            success=success,
            message="Mute toggled" if success else "Failed to toggle mute",
            should_speak=True
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Mute error: {e}",
            should_speak=True
        )


@register_command("now playing", aliases=["what's playing", "whats playing", "current song"])
def cmd_now_playing(args: str, context: Dict) -> CommandResult:
    """Get what's currently playing."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.media import now

        msg = now()
        return CommandResult(
            success=True,
            message=msg,
            should_speak=True
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Now playing error: {e}",
            should_speak=True
        )
