#!/usr/bin/env python3
"""Shared base of the voice.cmd_parts package (split from voice/commands.py on 2026-10-14): imports, module
state, the helpers and every function that rebinds a module global."""
from __future__ import annotations
#!/usr/bin/env python3
"""
C.O.R.A Voice Commands
Command handlers for voice-triggered actions

Per ARCHITECTURE.md v1.0.0:
- cmd_calendar - show today's events
- cmd_weather - show weather
- cmd_close - close app
- cmd_tasks - show pending tasks
- cmd_remind - set reminder
"""

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass
PROJECT_DIR = Path(__file__).parent.parent.parent
CONFIG_FILE = PROJECT_DIR / 'config' / 'voice_commands.json'

# Voice command configuration (loaded from JSON)
_voice_config: Dict = {}


def load_voice_config() -> Dict:
    """Load voice command configuration from JSON file.

    Returns:
        Dict with voice command settings
    """
    global _voice_config

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                _voice_config = json.load(f)
        except Exception as e:
            print(f"[!] Error loading voice config: {e}")
            _voice_config = {'enabled': True, 'commands': {}}
    else:
        _voice_config = {'enabled': True, 'commands': {}}

    return _voice_config


def save_voice_config() -> bool:
    """Save current voice command configuration.

    Returns:
        True if saved successfully
    """
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(_voice_config, f, indent=2)
        return True
    except Exception as e:
        print(f"[!] Error saving voice config: {e}")
        return False


def get_voice_config() -> Dict:
    """Get current voice config, loading if necessary."""
    if not _voice_config:
        load_voice_config()
    return _voice_config


def is_command_enabled(name: str) -> bool:
    """Check if a command is enabled in config.

    Args:
        name: Command name

    Returns:
        True if enabled (or not configured = enabled by default)
    """
    config = get_voice_config()
    cmd_config = config.get('commands', {}).get(name, {})
    return cmd_config.get('enabled', True)


def get_wake_words() -> List[str]:
    """Get configured wake words.

    Returns:
        List of wake words
    """
    config = get_voice_config()
    return config.get('wake_words', ['cora', 'hey cora'])


def get_confidence_threshold() -> float:
    """Get voice recognition confidence threshold.

    Returns:
        Confidence threshold (0.0-1.0)
    """
    config = get_voice_config()
    return config.get('confidence_threshold', 0.7)


@dataclass
class CommandResult:
    """Result of command execution."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    should_speak: bool = True


# Command registry
_commands: Dict[str, Callable] = {}


def register_command(name: str, aliases: List[str] = None):
    """Decorator to register a voice command.

    Args:
        name: Primary command name
        aliases: Alternative names for the command
    """
    def decorator(func: Callable):
        _commands[name.lower()] = func
        if aliases:
            for alias in aliases:
                _commands[alias.lower()] = func
        return func
    return decorator


def get_command(name: str) -> Optional[Callable]:
    """Get command handler by name.

    Args:
        name: Command name

    Returns:
        Command handler or None
    """
    return _commands.get(name.lower())


def execute_command(name: str, args: str = "", context: Dict = None) -> CommandResult:
    """Execute a voice command.

    Args:
        name: Command name
        args: Command arguments
        context: Execution context

    Returns:
        CommandResult with response
    """
    # Check if voice commands are enabled globally
    config = get_voice_config()
    if not config.get('enabled', True):
        return CommandResult(
            success=False,
            message="Voice commands are disabled",
            should_speak=False
        )

    # Check if specific command is enabled
    if not is_command_enabled(name):
        return CommandResult(
            success=False,
            message=f"Command '{name}' is disabled",
            should_speak=True
        )

    handler = get_command(name)
    if not handler:
        return CommandResult(
            success=False,
            message=f"Unknown command: {name}",
            should_speak=True
        )

    try:
        return handler(args, context or {})
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Command error: {e}",
            should_speak=True
        )
