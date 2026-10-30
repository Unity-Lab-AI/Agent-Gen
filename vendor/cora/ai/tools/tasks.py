#!/usr/bin/env python3
"""C.O.R.A tools: tasks. Registered on import (see ai/tools/__init__.py)."""

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

# =========================================================================== tasks
@_tool('add_task', 'Create a task/todo item.', 'tasks',
       {'text': _p('Task description'), 'priority': _p('1 (highest) to 10', 'integer'),
        'due': _p('Due date YYYY-MM-DD or +Nd')}, ['text'])
def _normalize_due(due: Optional[str]) -> Optional[str]:
    """Accept YYYY-MM-DD, +Nd, or natural language ("tomorrow", "next friday") -> YYYY-MM-DD."""
    if not due:
        return None
    d = str(due).strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', d) or re.match(r'^\+\d+d$', d):
        return d
    dt = _parse_when(d)
    return dt.strftime('%Y-%m-%d') if dt else None


def t_add_task(text: str, priority: int = None, due: str = None):
    from cora_tools import tasks as T
    tid = T.add_task(text)
    if not tid:
        return _err('could not add task')
    if priority is not None:
        T.set_priority(tid, int(priority))
    due_norm = _normalize_due(due)
    if due and not due_norm:
        return _ok(f"Added task {tid}: {text} (could not understand due date '{due}')", id=tid)
    if due_norm:
        T.set_due(tid, due_norm)
    return _ok(f"Added task {tid}: {text}" + (f", due {due_norm}" if due_norm else ''), id=tid, due=due_norm)


@_tool('list_tasks', 'List tasks.', 'tasks',
       {'filter': _p('all, pending, done or overdue', enum=['all', 'pending', 'done', 'overdue'])})
def t_list_tasks(filter: str = 'pending'):
    from cora_tools import tasks as T
    items = T.list_tasks(filter or 'pending')
    brief = [{'id': t.get('id'), 'text': t.get('text'), 'status': t.get('status'),
              'priority': t.get('priority'), 'due': t.get('due')} for t in items[:25]]
    return _ok(f"{len(items)} task(s)", tasks=brief)


@_tool('complete_task', 'Mark a task done.', 'tasks', {'task_id': _p('Task id like T003')}, ['task_id'])
def t_complete_task(task_id: str):
    from cora_tools import tasks as T
    return _ok(f"{task_id} done") if T.complete_task(task_id.upper()) else _err(f"{task_id} not found")


@_tool('delete_task', 'Delete a task permanently.', 'tasks', {'task_id': _p('Task id')}, ['task_id'], confirm=True)
def t_delete_task(task_id: str):
    from cora_tools import tasks as T
    return _ok(f"{task_id} deleted") if T.delete_task(task_id.upper()) else _err(f"{task_id} not found")


@_tool('set_task_priority', 'Set a task priority (1 highest, 10 lowest).', 'tasks',
       {'task_id': _p('Task id'), 'level': _p('1-10', 'integer')}, ['task_id', 'level'])
def t_set_task_priority(task_id: str, level: int):
    from cora_tools import tasks as T
    return _ok('priority set') if T.set_priority(task_id.upper(), int(level)) else _err('task not found')


@_tool('set_task_due', 'Set a task due date.', 'tasks',
       {'task_id': _p('Task id'), 'date': _p('YYYY-MM-DD or +Nd')}, ['task_id', 'date'])
def t_set_task_due(task_id: str, date: str):
    from cora_tools import tasks as T
    d = _normalize_due(date)
    if not d:
        return _err(f"could not understand date '{date}'")
    return _ok(f'due date set to {d}') if T.set_due(task_id.upper(), d) else _err('task not found')


@_tool('add_task_note', 'Add a note to a task.', 'tasks',
       {'task_id': _p('Task id'), 'text': _p('Note text')}, ['task_id', 'text'])
def t_add_task_note(task_id: str, text: str):
    from cora_tools import tasks as T
    return _ok('note added') if T.add_note(task_id.upper(), text) else _err('task not found')


@_tool('search_tasks', 'Search tasks by text.', 'tasks', {'query': _p('Search text')}, ['query'])
def t_search_tasks(query: str):
    from cora_tools import tasks as T
    items = T.search_tasks(query)
    return _ok(f"{len(items)} match(es)", tasks=[{'id': t.get('id'), 'text': t.get('text')} for t in items[:20]])
