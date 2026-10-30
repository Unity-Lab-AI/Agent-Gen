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

# Split into the voice.cmd_parts package on 2026-10-14; this module keeps every name it always had.
from voice.cmd_parts import _base  # noqa: F401
from voice.cmd_parts._base import Any, CONFIG_FILE, Callable, CommandResult, Dict, List, Optional, PROJECT_DIR, Path, _commands, _voice_config, dataclass, datetime, execute_command, get_command, get_confidence_threshold, get_voice_config, get_wake_words, is_command_enabled, json, load_voice_config, os, re, register_command, save_voice_config, sys, timedelta  # noqa: F401
from voice.cmd_parts.built_in_commands import cmd_analyze_camera, cmd_calendar, cmd_camera, cmd_close, cmd_close_camera, cmd_fetchurl, cmd_help, cmd_memory, cmd_remind, cmd_screenshot, cmd_see, cmd_systemstats, cmd_tasks, cmd_terminal, cmd_time, cmd_viewcode, cmd_viewfile, cmd_viewimage, cmd_weather, cmd_websearch  # noqa: F401
from voice.cmd_parts.media_control_commands import cmd_mute, cmd_next, cmd_now_playing, cmd_pause, cmd_play, cmd_prev, cmd_resume, cmd_stop, cmd_volume  # noqa: F401
from voice.cmd_parts.git_github_commands import cmd_git_add, cmd_git_branch, cmd_git_checkout, cmd_git_clone, cmd_git_commit, cmd_git_log, cmd_git_merge, cmd_git_pull, cmd_git_push, cmd_git_status, cmd_github_create, cmd_github_login, cmd_github_repos  # noqa: F401
from voice.cmd_parts.email_commands import handle_add_contact, handle_check_email, handle_list_contacts, handle_send_email  # noqa: F401
from voice.cmd_parts.hearing_transcript_commands import handle_awareness_level, handle_be_more_chatty, handle_be_quiet, handle_what_did_you_hear, list_commands, parse_voice_input  # noqa: F401




if __name__ == "__main__":
    print("=== VOICE COMMANDS TEST ===")

    print("\nRegistered commands:")
    for name in sorted(set(f.__name__ for f in _commands.values())):
        print(f"  - {name.replace('cmd_', '')}")

    print("\n--- Testing commands ---")

    # Test time
    result = execute_command("time")
    print(f"\ntime: {result.message}")

    # Test calendar
    result = execute_command("calendar")
    print(f"calendar: {result.message}")

    # Test help
    result = execute_command("help")
    print(f"help: {result.message}")

    # Test parse
    print("\n--- Parsing test ---")
    test_inputs = [
        "what time is it",
        "cora show my calendar",
        "remind me to check email in 30 minutes",
        "take a screenshot"
    ]

    for inp in test_inputs:
        cmd, args = parse_voice_input(inp)
        print(f"'{inp}' -> cmd={cmd}, args='{args}'")
