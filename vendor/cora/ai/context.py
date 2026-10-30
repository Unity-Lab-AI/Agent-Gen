#!/usr/bin/env python3
"""
C.O.R.A Context Builder
Constructs context for AI prompts including time, tasks, and conversation history

Per ARCHITECTURE.md v1.0.0:
- Build system context with personality
- Include relevant task context
- Time-of-day awareness
- Conversation history management
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass, field


# Project root for data files
PROJECT_DIR = Path(__file__).parent.parent


@dataclass
class ConversationTurn:
    """Single conversation turn."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: Optional[datetime] = None


@dataclass
class ContextBuilder:
    """Builds and manages context for AI prompts."""

    personality: Dict[str, Any] = field(default_factory=dict)
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    history: List[ConversationTurn] = field(default_factory=list)
    max_history: int = 10
    include_time: bool = True
    include_tasks: bool = True

    def add_turn(self, role: str, content: str):
        """Add a conversation turn to history.

        Args:
            role: 'user' or 'assistant'
            content: Message content
        """
        self.history.append(ConversationTurn(
            role=role,
            content=content,
            timestamp=datetime.now()
        ))

        # Trim history if too long
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def clear_history(self):
        """Clear conversation history."""
        self.history = []

    def get_messages(self) -> List[Dict[str, str]]:
        """Get history as Ollama-compatible messages.

        Returns:
            List of {'role': '...', 'content': '...'} dicts
        """
        return [
            {'role': turn.role, 'content': turn.content}
            for turn in self.history
        ]

    def build_system_prompt(self) -> str:
        """Build the system prompt with all context.

        Returns:
            Complete system prompt string
        """
        parts = []

        # CORA's identity only - let system_prompt.txt define personality
        if self.personality:
            name = self.personality.get('name', 'CORA')
            parts.append(f"You are {name}. 25 year old goth emo bitch. Human.")

        # Time context - natural format
        if self.include_time:
            time_ctx = get_time_context()
            parts.append(f"\nIt's {time_ctx['time']} on {time_ctx['day']}, {time_ctx['date_long']}.")

        # Task context - natural integration into conversation
        if self.include_tasks and self.tasks:
            task_ctx = get_task_context(self.tasks)
            if task_ctx['pending'] > 0:
                parts.append(f"\nThe user has {task_ctx['pending']} pending task{'s' if task_ctx['pending'] > 1 else ''}.")
                # Include specific task details for natural references
                if task_ctx['pending_tasks']:
                    task_names = [t.get('title', t.get('task', 'untitled'))[:40] for t in task_ctx['pending_tasks'][:3]]
                    parts.append(f"Top tasks: {', '.join(task_names)}.")
            if task_ctx['due_today']:
                parts.append(f"Due today: {len(task_ctx['due_today'])} task{'s' if len(task_ctx['due_today']) > 1 else ''}.")
            if task_ctx['overdue']:
                parts.append(f"IMPORTANT: {len(task_ctx['overdue'])} task{'s' if len(task_ctx['overdue']) > 1 else ''} overdue!")
            if task_ctx['next_due']:
                next_task = task_ctx['next_due']
                next_name = next_task.get('title', next_task.get('task', ''))[:30]
                parts.append(f"Next due: '{next_name}' on {next_task.get('due', 'soon')}.")

        # Response guidelines
        parts.append("\nKeep responses concise and natural.")
        parts.append("If asked about tasks or reminders, reference the user's actual data.")

        return "\n".join(parts)

    def load_personality(self, filepath: Optional[Path] = None) -> Dict[str, Any]:
        """Load personality from JSON file.

        Args:
            filepath: Path to personality.json

        Returns:
            Personality dict
        """
        if filepath is None:
            filepath = PROJECT_DIR / 'data' / 'personality.json'

        try:
            if filepath.exists():
                with open(filepath) as f:
                    self.personality = json.load(f)
        except Exception:
            self.personality = {
                'name': 'CORA',
                'tone': 'friendly and helpful',
                'traits': ['efficient', 'witty', 'supportive']
            }

        return self.personality

    def load_tasks(self, filepath: Optional[Path] = None) -> List[Dict[str, Any]]:
        """Load tasks from JSON file.

        Args:
            filepath: Path to tasks.json

        Returns:
            List of tasks
        """
        if filepath is None:
            filepath = PROJECT_DIR / 'data' / 'tasks.json'

        try:
            if filepath.exists():
                with open(filepath) as f:
                    data = json.load(f)
                    self.tasks = data.get('tasks', [])
        except Exception:
            self.tasks = []

        return self.tasks


def build_system_context(
    personality: Optional[Dict[str, Any]] = None,
    tasks: Optional[List[Dict[str, Any]]] = None,
    include_time: bool = True,
    include_tasks: bool = True
) -> str:
    """Build a system context string (convenience function).

    Args:
        personality: Personality dict
        tasks: List of tasks
        include_time: Include time context
        include_tasks: Include task context

    Returns:
        System prompt string
    """
    builder = ContextBuilder(
        personality=personality or {},
        tasks=tasks or [],
        include_time=include_time,
        include_tasks=include_tasks
    )
    return builder.build_system_prompt()


def get_time_context() -> Dict[str, Any]:
    """Get current time context.

    Returns:
        Dict with time, date, day, period, hour
    """
    now = datetime.now()
    hour = now.hour

    # Determine time of day period
    if 5 <= hour < 12:
        period = 'morning'
    elif 12 <= hour < 17:
        period = 'afternoon'
    elif 17 <= hour < 21:
        period = 'evening'
    else:
        period = 'night'

    return {
        'time': now.strftime('%I:%M %p'),
        'time_24': now.strftime('%H:%M'),
        'date': now.strftime('%Y-%m-%d'),
        'date_long': now.strftime('%B %d, %Y'),
        'day': now.strftime('%A'),
        'period': period,
        'hour': hour,
        'minute': now.minute,
        'datetime': now
    }


def get_task_context(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Get task-related context.

    Args:
        tasks: List of task dicts

    Returns:
        Dict with pending count, overdue tasks, next due, etc.
    """
    if not tasks:
        return {
            'total': 0,
            'pending': 0,
            'completed': 0,
            'overdue': [],
            'due_today': [],
            'next_due': None
        }

    today = datetime.now().strftime('%Y-%m-%d')
    pending = []
    completed = []
    overdue = []
    due_today = []

    for task in tasks:
        status = task.get('status', 'pending')
        due = task.get('due', '')

        if status == 'done':
            completed.append(task)
        else:
            pending.append(task)

            if due:
                if due < today:
                    overdue.append(task)
                elif due == today:
                    due_today.append(task)

    # Find next due task
    next_due = None
    for task in sorted(pending, key=lambda t: t.get('due', 'z')):
        if task.get('due'):
            next_due = task
            break

    return {
        'total': len(tasks),
        'pending': len(pending),
        'completed': len(completed),
        'overdue': overdue,
        'due_today': due_today,
        'next_due': next_due,
        'pending_tasks': pending[:5]  # First 5 pending
    }


def get_greeting_context() -> str:
    """Get appropriate greeting based on time of day.

    Returns:
        Greeting string
    """
    time_ctx = get_time_context()
    period = time_ctx['period']

    greetings = {
        'morning': "Good morning!",
        'afternoon': "Good afternoon!",
        'evening': "Good evening!",
        'night': "Hey there, night owl!"
    }

    return greetings.get(period, "Hello!")


def get_calendar_context() -> Dict[str, Any]:
    """Get calendar context from cora_tools/calendar.py.

    Returns:
        Dict with today_events, upcoming_events, next_event
    """
    try:
        # Import calendar module
        import sys
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.calendar import get_today_events, get_upcoming, get_events_summary

        today_events = get_today_events()
        upcoming = get_upcoming(days=7)

        return {
            'today_events': today_events,
            'today_count': len(today_events),
            'upcoming_events': upcoming,
            'upcoming_count': len(upcoming),
            'summary': get_events_summary(today_events)
        }
    except Exception as e:
        return {
            'today_events': [],
            'today_count': 0,
            'upcoming_events': [],
            'upcoming_count': 0,
            'summary': '',
            'error': str(e)
        }


def get_location_context() -> Dict[str, Any]:
    """Get location and weather context.

    Returns:
        Dict with location and weather info
    """
    try:
        import sys
        sys.path.insert(0, str(PROJECT_DIR))
        from services.location import get_location
        from services.weather import get_weather

        location = get_location()
        weather = None

        if location:
            city = location.get('city', '')
            weather = get_weather(city) if city else get_weather()

        return {
            'location': location,
            'weather': weather,
            'city': location.get('city') if location else None,
            'country': location.get('country') if location else None
        }
    except Exception as e:
        return {
            'location': None,
            'weather': None,
            'error': str(e)
        }


def get_full_context() -> Dict[str, Any]:
    """Get complete context for AI prompts.

    Returns:
        Dict with time, tasks, calendar, location, weather
    """
    return {
        'time': get_time_context(),
        'greeting': get_greeting_context(),
        'calendar': get_calendar_context(),
        'location': get_location_context()
    }


def format_task_summary(tasks: List[Dict[str, Any]]) -> str:
    """Format a spoken summary of tasks for TTS.

    Args:
        tasks: List of tasks

    Returns:
        Natural language summary
    """
    ctx = get_task_context(tasks)

    if ctx['pending'] == 0:
        return "Your task list is all clear."

    parts = []

    if ctx['pending'] > 0:
        parts.append(f"You have {ctx['pending']} pending task{'s' if ctx['pending'] > 1 else ''}.")

    if ctx['overdue']:
        parts.append(f"Heads up - {len(ctx['overdue'])} {'are' if len(ctx['overdue']) > 1 else 'is'} overdue.")

    if ctx['due_today']:
        parts.append(f"{len(ctx['due_today'])} {'are' if len(ctx['due_today']) > 1 else 'is'} due today.")

    return " ".join(parts)


if __name__ == "__main__":
    # Test context building
    print("=== CONTEXT TEST ===")

    print("\n--- Time Context ---")
    time_ctx = get_time_context()
    for k, v in time_ctx.items():
        if k != 'datetime':
            print(f"  {k}: {v}")

    print("\n--- Greeting ---")
    print(f"  {get_greeting_context()}")

    print("\n--- System Prompt ---")
    builder = ContextBuilder()
    builder.personality = {
        'name': 'CORA',
        'tone': 'friendly',
        'traits': ['helpful', 'witty']
    }
    print(builder.build_system_prompt())
