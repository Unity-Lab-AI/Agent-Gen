#!/usr/bin/env python3
"""C.O.R.A tools: system. Registered on import (see ai/tools/__init__.py)."""

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

# =========================================================================== system
@_tool('system_stats', 'CPU, RAM, disk, GPU usage.', 'system')
def t_system_stats():
    from cora_tools.system import get_system_info, get_gpu_info
    info = get_system_info() or {}
    try:
        info['gpu'] = get_gpu_info()
    except Exception:
        pass
    return _ok('stats', **info)


@_tool('running_processes', 'List running processes (optionally filtered).', 'system', {'filter': _p('Name fragment, optional')})
def t_running_processes(filter: str = None):
    from cora_tools.system import get_running_processes
    procs = get_running_processes() or []
    if filter:
        f = filter.lower()
        procs = [p for p in procs if f in str(p).lower()]
    return _ok(f"{len(procs)} process(es)", processes=procs[:60])


@_tool('kill_process', 'End a process by name.', 'system', {'name': _p('Process name')}, ['name'], confirm=True)
def t_kill_process(name: str):
    from cora_tools.system import kill_process
    return _ok(f"killed {name}") if kill_process(name) else _err('could not kill')


@_tool('set_system_volume', 'Set master volume 0-100.', 'system', {'level': _p('0-100', 'integer')}, ['level'])
def t_set_system_volume(level: int):
    from cora_tools.system import set_volume
    return _ok(f"volume {level}") if set_volume(int(level)) else _err('volume control unavailable')


@_tool('notify', 'Show a desktop notification.', 'system', {'title': _p('Title'), 'message': _p('Body')}, ['title', 'message'])
def t_notify(title: str, message: str):
    from cora_tools.system import notify
    notify(title, message)
    return _ok('notified')


@_tool('clipboard_copy', 'Put text on the clipboard.', 'system', {'text': _p('Text')}, ['text'])
def t_clipboard_copy(text: str):
    from cora_tools.system import clipboard_copy
    return _ok('copied') if clipboard_copy(text) else _err('clipboard unavailable')


@_tool('clipboard_paste', 'Read the clipboard.', 'system')
def t_clipboard_paste():
    from cora_tools.system import clipboard_paste
    return _ok('clipboard', text=str(clipboard_paste() or '')[:4000])


@_tool('calculate', 'Evaluate a math expression safely.', 'system', {'expression': _p('e.g. 12*(3+4)/7')}, ['expression'])
def t_calculate(expression: str):
    from cora_tools.system import calculate
    r = calculate(expression)
    return r if isinstance(r, dict) else _ok(str(r))


@_tool('run_shell', 'Run a shell command and return its output.', 'system',
       {'command': _p('Command line'), 'timeout': _p('Seconds', 'integer')}, ['command'], confirm=True)
def t_run_shell(command: str, timeout: int = 30):
    from cora_tools.system import run_shell
    r = run_shell(command, timeout=int(timeout or 30))
    if isinstance(r, dict):
        for k in ('stdout', 'output', 'stderr'):
            if isinstance(r.get(k), str):
                r[k] = r[k][-4000:]
    return r
