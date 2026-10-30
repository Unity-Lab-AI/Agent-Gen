#!/usr/bin/env python3
"""C.O.R.A tools: calendar + reminders. Registered on import (see ai/tools/__init__.py)."""

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

# =========================================================================== calendar + reminders
def _parse_when(when: str) -> Optional[datetime]:
    from cora_tools.reminders import parse_time_string
    for cand in (when, f"in {when}", f"at {when}"):
        try:
            dt = parse_time_string(cand)
            if dt:
                return dt
        except Exception:
            pass
    try:
        return datetime.fromisoformat(when)
    except Exception:
        return None


@_tool('add_event', 'Add a calendar event.', 'calendar',
       {'title': _p('Event title'), 'start': _p('When: ISO datetime or natural like "tomorrow 3pm"'),
        'duration_minutes': _p('Length in minutes', 'integer'), 'description': _p('Optional details'),
        'location': _p('Optional place')}, ['title', 'start'])
def t_add_event(title: str, start: str, duration_minutes: int = 60, description: str = '', location: str = ''):
    from cora_tools.calendar import add_event
    dt = _parse_when(start)
    if not dt:
        return _err(f"could not understand time: {start}")
    ev = add_event(title, dt.isoformat(), int(duration_minutes or 60), description or '', location or '')
    return _ok(f"Event '{title}' at {dt.strftime('%A %I:%M %p')}", event=ev)


@_tool('today_events', "Today's calendar events.", 'calendar')
def t_today_events():
    from cora_tools.calendar import get_today_events, get_events_summary
    ev = get_today_events()
    return _ok(get_events_summary(ev), events=ev)


@_tool('upcoming_events', 'Calendar events for the next N days.', 'calendar', {'days': _p('Days ahead', 'integer')})
def t_upcoming_events(days: int = 7):
    from cora_tools.calendar import get_upcoming
    ev = get_upcoming(int(days or 7))
    return _ok(f"{len(ev)} upcoming", events=ev)


@_tool('delete_event', 'Delete a calendar event by id.', 'calendar', {'event_id': _p('Event id')}, ['event_id'], confirm=True)
def t_delete_event(event_id: str):
    from cora_tools.calendar import delete_event
    return _ok('deleted') if delete_event(event_id) else _err('not found')


@_tool('set_reminder', 'Set a reminder that will be spoken and shown when due.', 'calendar',
       {'text': _p('What to remind'), 'when': _p('"in 20 minutes", "at 3pm", "tomorrow 9am", or ISO datetime'),
        'repeat': _p('none, daily, weekly, monthly', enum=['none', 'daily', 'weekly', 'monthly'])}, ['text', 'when'])
def t_set_reminder(text: str, when: str, repeat: str = 'none'):
    from cora_tools.reminders import ReminderManager
    dt = _parse_when(when)
    if not dt:
        return _err(f"could not understand time: {when}")
    rid = ReminderManager().add(text, dt, repeat=None if repeat in (None, '', 'none') else repeat)
    return _ok(f"Reminder {rid} set for {dt.strftime('%A %I:%M %p')}", id=rid, time=dt.isoformat())


@_tool('list_reminders', 'List reminders.', 'calendar')
def t_list_reminders():
    from cora_tools.reminders import ReminderManager
    rs = ReminderManager().list_all()
    return _ok(f"{len(rs)} reminder(s)", reminders=[{'id': r['id'], 'text': r['text'], 'time': r.get('time'),
                                                     'enabled': r.get('enabled', True)} for r in rs])


@_tool('delete_reminder', 'Delete a reminder by id.', 'calendar', {'reminder_id': _p('Reminder id like R002')}, ['reminder_id'], confirm=True)
def t_delete_reminder(reminder_id: str):
    from cora_tools.reminders import ReminderManager
    return _ok('deleted') if ReminderManager().remove(reminder_id.upper()) else _err('not found')
