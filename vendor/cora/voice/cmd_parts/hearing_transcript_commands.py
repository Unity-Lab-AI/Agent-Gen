#!/usr/bin/env python3
"""voice.cmd_parts: hearing_transcript_commands (split from voice/commands.py on 2026-10-14)."""
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
from voice.cmd_parts._base import CommandResult, Dict, List, _commands, get_wake_words, is_command_enabled, register_command  # noqa: F401




# ============ HEARING/TRANSCRIPT COMMANDS ============

@register_command("what did you hear", aliases=["what did i say", "what did i just say", "what was that", "repeat that", "what did you just hear"])
def handle_what_did_you_hear(args: str = "", context: Dict = None) -> CommandResult:
    """Tell user what was heard before the wake word."""
    try:
        from voice.stt import WakeWordDetector

        last_heard = WakeWordDetector.get_last_heard()

        if last_heard:
            return CommandResult(
                success=True,
                message=f"Before you said my name, I heard: {last_heard}",
                should_speak=True
            )
        else:
            return CommandResult(
                success=True,
                message="I didn't catch anything before you called me. Maybe it was too quiet or I wasn't picking it up clearly.",
                should_speak=True
            )
    except Exception as e:
        return CommandResult(success=False, message=f"Couldn't check transcript: {e}", should_speak=True)


@register_command("be more chatty", aliases=["talk more", "be more involved", "be active", "friend mode"])
def handle_be_more_chatty(args: str = "", context: Dict = None) -> CommandResult:
    """Increase CORA's ambient interjection frequency."""
    try:
        from voice.ambient_awareness import get_ambient_awareness

        ambient = get_ambient_awareness()
        new_threshold = min(1.0, ambient.friend_threshold + 0.2)
        ambient.set_friend_threshold(new_threshold)

        if new_threshold >= 0.8:
            msg = "Alright, I'll be more chatty. I'll chime in more often like a close friend would."
        elif new_threshold >= 0.5:
            msg = "Got it, I'll be more involved in what's going on. I'll speak up when I notice things."
        else:
            msg = "I'll try to be a bit more active. Let me know if you want me even more involved."

        return CommandResult(success=True, message=msg, should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Couldn't adjust: {e}", should_speak=True)


@register_command("be quiet", aliases=["be less chatty", "talk less", "quiet mode", "shut up", "give me space", "leave me alone"])
def handle_be_quiet(args: str = "", context: Dict = None) -> CommandResult:
    """Decrease CORA's ambient interjection frequency."""
    try:
        from voice.ambient_awareness import get_ambient_awareness

        ambient = get_ambient_awareness()
        new_threshold = max(0.0, ambient.friend_threshold - 0.3)
        ambient.set_friend_threshold(new_threshold)

        if new_threshold <= 0.1:
            msg = "Okay, I'll stay quiet unless you call me. Just say my name if you need me."
        elif new_threshold <= 0.3:
            msg = "Alright, I'll tone it down. I'll only speak up if something seems important."
        else:
            msg = "Got it, I'll give you more space. I'm still here if you need me though."

        return CommandResult(success=True, message=msg, should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Couldn't adjust: {e}", should_speak=True)


@register_command("how aware are you", aliases=["awareness level", "friend threshold", "how chatty are you"])
def handle_awareness_level(args: str = "", context: Dict = None) -> CommandResult:
    """Check CORA's current ambient awareness level."""
    try:
        from voice.ambient_awareness import get_ambient_awareness

        ambient = get_ambient_awareness()
        status = ambient.get_status()
        threshold = status['friend_threshold']
        interjections = status['interjection_count']

        if threshold >= 0.8:
            level = "very chatty, like a close friend"
        elif threshold >= 0.5:
            level = "moderately involved, chiming in occasionally"
        elif threshold >= 0.3:
            level = "pretty quiet, only speaking up for important stuff"
        else:
            level = "very quiet, mostly waiting for you to call me"

        msg = f"My friend threshold is at {threshold:.0%}. I'm {level}. I've interjected {interjections} times this session."

        return CommandResult(success=True, message=msg, should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Couldn't check: {e}", should_speak=True)


def list_commands() -> List[str]:
    """Get list of all registered commands.

    Returns:
        List of command names
    """
    return list(_commands.keys())


def parse_voice_input(text: str) -> tuple:
    """Parse voice input into command and args.

    Args:
        text: Raw voice input

    Returns:
        (command_name, args) tuple
    """
    text = text.lower().strip()

    # Remove wake word if present (use configured wake words)
    wake_words = get_wake_words()
    for wake in wake_words:
        if text.startswith(wake):
            text = text[len(wake):].strip()
            break

    # Try to match a command (only enabled ones)
    for cmd_name in sorted(_commands.keys(), key=len, reverse=True):
        if text.startswith(cmd_name) and is_command_enabled(cmd_name):
            args = text[len(cmd_name):].strip()
            return (cmd_name, args)

    # No command found - return as query
    return (None, text)
