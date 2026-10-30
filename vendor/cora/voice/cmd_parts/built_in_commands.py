#!/usr/bin/env python3
"""voice.cmd_parts: built_in_commands (split from voice/commands.py on 2026-10-14)."""
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
from voice.cmd_parts._base import CommandResult, Dict, PROJECT_DIR, Path, _commands, datetime, json, re, register_command, sys  # noqa: F401




# ============ BUILT-IN COMMANDS ============

@register_command("calendar", aliases=["events", "schedule", "today"])
def cmd_calendar(args: str, context: Dict) -> CommandResult:
    """Show today's calendar events."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.calendar import get_today_events, get_events_summary

        events = get_today_events()
        summary = get_events_summary(events)

        return CommandResult(
            success=True,
            message=summary,
            data={'events': events, 'count': len(events)},
            should_speak=True
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Couldn't get calendar: {e}",
            should_speak=True
        )


@register_command("weather", aliases=["forecast", "temperature"])
def cmd_weather(args: str, context: Dict) -> CommandResult:
    """Show current weather."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from services.weather import get_weather, get_weather_summary

        where = (args or '').strip() or None
        weather = get_weather(where)
        if not weather or not weather.get('success'):
            return CommandResult(
                success=False,
                message="Couldn't get weather data",
                should_speak=True
            )

        summary = get_weather_summary(where)
        return CommandResult(
            success=True,
            message=summary,
            data={'weather': weather},
            should_speak=True
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Weather error: {e}",
            should_speak=True
        )


@register_command("time", aliases=["clock", "what time"])
def cmd_time(args: str, context: Dict) -> CommandResult:
    """Tell the current time."""
    now = datetime.now()
    time_str = now.strftime("%I:%M %p")
    date_str = now.strftime("%A, %B %d")

    message = f"It's {time_str} on {date_str}."

    return CommandResult(
        success=True,
        message=message,
        data={'time': time_str, 'date': date_str},
        should_speak=True
    )


@register_command("tasks", aliases=["todos", "todo", "to do"])
def cmd_tasks(args: str, context: Dict) -> CommandResult:
    """Show pending tasks."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from ai.context import get_task_context, format_task_summary

        # Load tasks from file
        import json
        tasks_file = PROJECT_DIR / 'data' / 'tasks.json'

        if tasks_file.exists():
            with open(tasks_file) as f:
                data = json.load(f)
                tasks = data.get('tasks', [])
        else:
            tasks = []

        summary = format_task_summary(tasks)

        return CommandResult(
            success=True,
            message=summary,
            data={'tasks': tasks},
            should_speak=True
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Couldn't get tasks: {e}",
            should_speak=True
        )


@register_command("remind", aliases=["reminder", "remind me"])
def cmd_remind(args: str, context: Dict) -> CommandResult:
    """Set a reminder."""
    if not args:
        return CommandResult(
            success=False,
            message="What should I remind you about?",
            should_speak=True
        )

    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from ai.tools_registry import execute

        # "remind me to X in Y minutes" / "X at 6pm" / "X tomorrow at 9"
        text, when = args.strip(), ''
        m = re.search(r'\b(in|at|tomorrow|next|tonight|on)\b', args, flags=re.IGNORECASE)
        if m:
            text = args[:m.start()].strip() or args.strip()
            when = args[m.start():].strip()
        text = re.sub(r'^(me\s+)?(to\s+)?', '', text, flags=re.IGNORECASE).strip() or args.strip()
        result = execute('set_reminder', {'text': text, 'when': when or 'in 30 minutes'})

        if result.get('ok'):
            return CommandResult(
                success=True,
                message=result.get('message') or "Reminder set.",
                data={'reminder_id': result.get('id'), 'time': result.get('time')},
                should_speak=True
            )
        else:
            return CommandResult(
                success=False,
                message=result.get('error') or result.get('message') or "Couldn't create reminder",
                should_speak=True
            )

    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Reminder error: {e}",
            should_speak=True
        )


@register_command("screenshot", aliases=["capture", "screen"])
def cmd_screenshot(args: str, context: Dict) -> CommandResult:
    """Take a screenshot."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.screenshots import desktop

        result = desktop()

        if result.success:
            return CommandResult(
                success=True,
                message="Screenshot saved.",
                data={'path': str(result.path), 'size': f"{result.width}x{result.height}"},
                should_speak=True
            )
        else:
            return CommandResult(
                success=False,
                message=f"Screenshot failed: {result.error}",
                should_speak=True
            )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Screenshot error: {e}",
            should_speak=True
        )


@register_command("close", aliases=["exit", "quit", "goodbye", "bye"])
def cmd_close(args: str, context: Dict) -> CommandResult:
    """Close the application."""
    return CommandResult(
        success=True,
        message="Goodbye!",
        data={'action': 'close'},
        should_speak=True
    )


@register_command("help", aliases=["commands", "what can you do"])
def cmd_help(args: str, context: Dict) -> CommandResult:
    """List available commands."""
    # Get unique commands (skip aliases)
    unique_commands = set()
    for name, func in _commands.items():
        if func.__name__ not in [f.__name__ for f in unique_commands]:
            unique_commands.add(func)

    command_list = [f.__name__.replace('cmd_', '') for f in unique_commands]
    command_str = ", ".join(sorted(command_list))

    return CommandResult(
        success=True,
        message=f"Available commands: {command_str}",
        data={'commands': list(_commands.keys())},
        should_speak=True
    )


@register_command("see", aliases=["look", "vision", "check presence"])
def cmd_see(args: str, context: Dict) -> CommandResult:
    """Check if user is present and get visual analysis."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from services.presence import check_human_present, full_human_check

        # Quick check or full analysis?
        if args and any(word in args.lower() for word in ['full', 'detail', 'analyze', 'emotion']):
            result = full_human_check()
            if result.present:
                message = f"I can see you. You appear {result.emotion or 'neutral'}."
                if result.activity:
                    message += f" You're {result.activity}."
                if result.holding:
                    message += f" I see you're holding {result.holding}."
            else:
                message = "I don't see anyone at the desk right now."
        else:
            result = check_human_present()
            if result.present:
                message = "Yes, I can see you're there."
            else:
                message = "I don't see anyone at the desk."

        return CommandResult(
            success=True,
            message=message,
            data={
                'present': result.present,
                'confidence': result.confidence,
                'emotion': result.emotion,
                'activity': result.activity,
                'posture': result.posture,
                'holding': result.holding
            },
            should_speak=True
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Vision check failed: {e}",
            should_speak=True
        )


@register_command("camera", aliases=["show camera", "open camera", "show my camera", "webcam", "live camera", "camera feed", "show webcam"])
def cmd_camera(args: str, context: Dict) -> CommandResult:
    """Open live camera feed window."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from ui.camera_feed import open_live_camera, get_live_camera

        # Check if already open
        existing = get_live_camera()
        if existing and existing.is_active():
            return CommandResult(
                success=True,
                message="Camera feed is already open.",
                should_speak=True
            )

        # Open camera
        camera = open_live_camera()
        if camera:
            return CommandResult(
                success=True,
                message="Camera feed is now open. I can see through your webcam.",
                should_speak=True
            )
        else:
            return CommandResult(
                success=False,
                message="Couldn't open camera. Make sure it's connected.",
                should_speak=True
            )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Camera error: {e}",
            should_speak=True
        )


@register_command("close camera", aliases=["stop camera", "hide camera", "camera off", "close webcam"])
def cmd_close_camera(args: str, context: Dict) -> CommandResult:
    """Close live camera feed."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from ui.camera_feed import close_live_camera, get_live_camera

        if get_live_camera():
            close_live_camera()
            return CommandResult(
                success=True,
                message="Camera feed closed.",
                should_speak=True
            )
        else:
            return CommandResult(
                success=True,
                message="Camera wasn't open.",
                should_speak=True
            )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Error closing camera: {e}",
            should_speak=True
        )


@register_command("what do you see", aliases=["describe what you see", "what am i doing", "how many fingers", "what is this", "look at this", "analyze camera", "camera snapshot"])
def cmd_analyze_camera(args: str, context: Dict) -> CommandResult:
    """Analyze current camera frame with AI vision."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from ui.camera_feed import get_live_camera, capture_from_live_camera, open_live_camera
        from ai.ollama import generate_with_image

        # Open camera if not already open
        camera = get_live_camera()
        if not camera or not camera.is_active():
            camera = open_live_camera()
            if not camera:
                return CommandResult(
                    success=False,
                    message="Couldn't access camera.",
                    should_speak=True
                )
            # Wait for camera to initialize
            import time
            time.sleep(1)

        # Capture frame
        frame_path = capture_from_live_camera()
        if not frame_path:
            return CommandResult(
                success=False,
                message="Couldn't capture frame from camera.",
                should_speak=True
            )

        # Build prompt based on what user asked
        prompt = "What do you see in this image? Describe in detail."
        if args:
            args_lower = args.lower()
            if "finger" in args_lower:
                prompt = "How many fingers is the person holding up? Count carefully and tell me the number."
            elif "doing" in args_lower:
                prompt = "What is the person doing right now? Describe their activity."
            elif "holding" in args_lower or "this" in args_lower:
                prompt = "What is the person holding or showing? Describe what you see."
            elif "emotion" in args_lower or "feel" in args_lower:
                prompt = "How does the person appear to be feeling? Describe their emotional state."
            else:
                prompt = f"Looking at this camera image: {args}"

        # Analyze with vision AI
        result = generate_with_image(
            prompt=prompt,
            image_path=str(frame_path),
        )

        if result and result.content:
            # Clean up response
            import re
            description = result.content.strip()
            description = re.sub(r'\*\*([^*]+)\*\*', r'\1', description)
            description = re.sub(r'\*([^*]+)\*', r'\1', description)
            description = re.sub(r'\n+', ' ', description)
            description = re.sub(r'\s+', ' ', description).strip()

            return CommandResult(
                success=True,
                message=description,
                data={'image_path': str(frame_path)},
                should_speak=True
            )
        else:
            return CommandResult(
                success=False,
                message="I couldn't analyze the image.",
                should_speak=True
            )

    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Vision analysis failed: {e}",
            should_speak=True
        )


@register_command("viewfile", aliases=["openfile", "showfile", "open file", "show file", "view file"])
def cmd_viewfile(args: str, context: Dict) -> CommandResult:
    """Open a file in modal viewer."""
    if not args:
        return CommandResult(
            success=False,
            message="What file should I open?",
            should_speak=True
        )

    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.modal_tools import viewfile

        result = viewfile(args.strip())

        if result.get('success'):
            return CommandResult(
                success=True,
                message=f"Opened {Path(args).name}",
                data=result,
                should_speak=True
            )
        else:
            return CommandResult(
                success=False,
                message=result.get('error', 'Failed to open file'),
                should_speak=True
            )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Error opening file: {e}",
            should_speak=True
        )


@register_command("viewcode", aliases=["opencode", "showcode", "open code", "show code", "view code"])
def cmd_viewcode(args: str, context: Dict) -> CommandResult:
    """Open a code file with syntax highlighting."""
    if not args:
        return CommandResult(
            success=False,
            message="What code file should I open?",
            should_speak=True
        )

    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.modal_tools import viewcode

        result = viewcode(args.strip())

        if result.get('success'):
            return CommandResult(
                success=True,
                message=f"Opened {Path(args).name} in code viewer",
                data=result,
                should_speak=True
            )
        else:
            return CommandResult(
                success=False,
                message=result.get('error', 'Failed to open code file'),
                should_speak=True
            )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Error opening code: {e}",
            should_speak=True
        )


@register_command("viewimage", aliases=["openimage", "showimage", "open image", "show image", "display image"])
def cmd_viewimage(args: str, context: Dict) -> CommandResult:
    """Display an image in popup window."""
    if not args:
        return CommandResult(
            success=False,
            message="What image should I show?",
            should_speak=True
        )

    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.modal_tools import viewimage

        result = viewimage(args.strip())

        if result.get('success'):
            return CommandResult(
                success=True,
                message=f"Showing {Path(args).name}",
                data=result,
                should_speak=True
            )
        else:
            return CommandResult(
                success=False,
                message=result.get('error', 'Failed to show image'),
                should_speak=True
            )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Error showing image: {e}",
            should_speak=True
        )


@register_command("websearch", aliases=["search", "web search", "google", "look up"])
def cmd_websearch(args: str, context: Dict) -> CommandResult:
    """Search the web and show results in modal."""
    if not args:
        return CommandResult(
            success=False,
            message="What should I search for?",
            should_speak=True
        )

    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.modal_tools import websearch

        result = websearch(args.strip())

        if result.get('success'):
            count = result.get('count', 0)
            return CommandResult(
                success=True,
                message=f"Found {count} results for {args}",
                data=result,
                should_speak=True
            )
        else:
            return CommandResult(
                success=False,
                message=result.get('error', 'Search failed'),
                should_speak=True
            )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Search error: {e}",
            should_speak=True
        )


@register_command("fetchurl", aliases=["fetch", "get url", "open url", "browse"])
def cmd_fetchurl(args: str, context: Dict) -> CommandResult:
    """Fetch a webpage and display content."""
    if not args:
        return CommandResult(
            success=False,
            message="What URL should I fetch?",
            should_speak=True
        )

    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.modal_tools import fetchurl

        result = fetchurl(args.strip())

        if result.get('success'):
            return CommandResult(
                success=True,
                message=f"Fetched {args}",
                data=result,
                should_speak=True
            )
        else:
            return CommandResult(
                success=False,
                message=result.get('error', 'Failed to fetch URL'),
                should_speak=True
            )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Fetch error: {e}",
            should_speak=True
        )


@register_command("systemstats", aliases=["stats", "system stats", "hardware", "show stats"])
def cmd_systemstats(args: str, context: Dict) -> CommandResult:
    """Open live system stats monitor."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.modal_tools import systemstats

        result = systemstats()

        if result.get('success'):
            return CommandResult(
                success=True,
                message="Opening system stats monitor",
                data=result,
                should_speak=True
            )
        else:
            return CommandResult(
                success=False,
                message=result.get('error', 'Failed to open stats'),
                should_speak=True
            )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Stats error: {e}",
            should_speak=True
        )


@register_command("terminal", aliases=["run", "execute", "shell", "cmd"])
def cmd_terminal(args: str, context: Dict) -> CommandResult:
    """Run a command and show output in terminal modal."""
    if not args:
        return CommandResult(
            success=False,
            message="What command should I run?",
            should_speak=True
        )

    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.modal_tools import terminal

        result = terminal(args.strip())

        if result.get('success'):
            return CommandResult(
                success=True,
                message=f"Command executed",
                data=result,
                should_speak=True
            )
        else:
            return CommandResult(
                success=False,
                message=result.get('error', 'Command failed'),
                should_speak=True
            )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Terminal error: {e}",
            should_speak=True
        )


@register_command("memory", aliases=["remember", "recall"])
def cmd_memory(args: str, context: Dict) -> CommandResult:
    """Access working memory."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.memory import get_memory

        mem = get_memory()

        if not args:
            # Show all memory
            all_mem = mem.recall()
            if all_mem:
                items = [f"{k}: {v}" for k, v in list(all_mem.items())[:5]]
                message = "I remember: " + "; ".join(items)
            else:
                message = "My memory is empty."
            return CommandResult(success=True, message=message)

        # Check for "remember X is Y"
        if " is " in args:
            parts = args.split(" is ", 1)
            key = parts[0].strip()
            value = parts[1].strip()
            mem.remember(key, value)
            return CommandResult(
                success=True,
                message=f"OK, I'll remember that {key} is {value}."
            )

        # Recall specific key
        value = mem.recall(args.strip())
        if value:
            return CommandResult(
                success=True,
                message=f"{args.strip()} is {value}."
            )
        else:
            return CommandResult(
                success=False,
                message=f"I don't remember anything about {args.strip()}."
            )

    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Memory error: {e}"
        )
