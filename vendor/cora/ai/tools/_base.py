#!/usr/bin/env python3
"""
C.O.R.A tool registry core: the Tool dataclass, the registry, the decorator and
helpers every category module uses, tool selection and execution.

The tools themselves live in ai/tools/<category>.py and register on import;
ai/tools/__init__.py imports every category, and ai/tools_registry.py is the
facade the rest of CORA imports from (same names as before the split).
"""

import json
import os
import re
import subprocess
import sys
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., Any]
    params: Dict[str, Dict[str, Any]] = field(default_factory=dict)   # name -> {type, description, enum?}
    required: List[str] = field(default_factory=list)
    confirm: bool = False
    category: str = 'general'
    speak_result: bool = False     # result is already user-facing prose

    def schema(self) -> Dict[str, Any]:
        props = {}
        for n, p in self.params.items():
            q = {'type': p.get('type', 'string'), 'description': p.get('description', '')}
            if 'enum' in p:
                q['enum'] = p['enum']
            props[n] = q
        return {'type': 'function', 'function': {
            'name': self.name, 'description': self.description,
            'parameters': {'type': 'object', 'properties': props, 'required': list(self.required)}}}


_REGISTRY: Dict[str, Tool] = {}


def register_tool(tool: Tool):
    _REGISTRY[tool.name] = tool


def unregister_tool(name: str):
    _REGISTRY.pop(name, None)


def get_tool(name: str) -> Optional[Tool]:
    return _REGISTRY.get(name)


def all_tools() -> List[Tool]:
    return list(_REGISTRY.values())


def tool_schemas(categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    return [t.schema() for t in _REGISTRY.values() if not categories or t.category in categories]


def tool_catalog_text(tools: Optional[List[Tool]] = None) -> str:
    """Compact human/LLM-readable catalog (used by the JSON fallback protocol and /help).
    tools: only these (the JSON protocol passes the turn's selected set); default every tool."""
    lines = []
    by_cat: Dict[str, List[Tool]] = {}
    for t in (tools if tools is not None else _REGISTRY.values()):
        by_cat.setdefault(t.category, []).append(t)
    for cat in sorted(by_cat):
        lines.append(f"[{cat}]")
        for t in by_cat[cat]:
            args = ", ".join(f"{n}{'' if n in t.required else '?'}" for n in t.params)
            lines.append(f"  {t.name}({args}) - {t.description}")
    return "\n".join(lines)


def _p(desc: str, type_: str = 'string', enum: Optional[List[str]] = None) -> Dict[str, Any]:
    d = {'type': type_, 'description': desc}
    if enum:
        d['enum'] = enum
    return d


def _ok(msg: str, **data) -> Dict[str, Any]:
    out = {'ok': True, 'message': msg}
    out.update(data)
    return out


def _err(msg: str, **data) -> Dict[str, Any]:
    out = {'ok': False, 'error': msg}
    out.update(data)
    return out


def _tool(name, desc, category, params=None, required=None, confirm=False, speak_result=False):
    """Decorator: define a tool from a function."""
    def deco(func):
        register_tool(Tool(name=name, description=desc, func=func, params=params or {},
                           required=required or [], confirm=confirm, category=category,
                           speak_result=speak_result))
        return func
    return deco


# Tools every turn gets regardless of wording (speech, time, the things she is asked most).
CORE_TOOLS = ['say', 'get_time', 'get_weather', 'list_tasks', 'add_task', 'complete_task', 'set_reminder',
              'list_reminders', 'remember', 'recall_memory', 'learn', 'recall_knowledge', 'look_camera',
              'take_screenshot', 'web_search', 'open_path', 'open_in_browser', 'media_play',
              'stop_speaking', 'list_capabilities', 'get_location', 'today_events', 'add_event']

_WORD = re.compile(r"[a-z0-9]+")


def select_tools(text: str, max_tools: int = 40) -> List[Tool]:
    """The tools worth showing the model for this message: the core set plus
    the best keyword matches on name/description/category. A 9B model picks
    the right tool far more reliably from ~40 schemas than from 115."""
    # `speak` is the pre-brain voice tool; `say` (emotion + act) replaces it in what the model sees
    tools = [t for t in all_tools() if t.name != 'speak']
    if max_tools <= 0 or len(tools) <= max_tools:
        ordered = sorted(tools, key=lambda t: (t.name != 'say', t.name))
        return ordered
    words = set(_WORD.findall((text or '').lower()))
    stems = {w[:5] for w in words if len(w) > 4}

    def score(t: Tool) -> int:
        hay = f"{t.name} {t.category} {t.description}".lower().replace('_', ' ')
        hw = set(_WORD.findall(hay))
        hit = len(words & hw) * 2 + sum(1 for st in stems if any(h.startswith(st) for h in hw))
        if t.name.replace('_', ' ') in (text or '').lower():
            hit += 5
        return hit

    core = [t for t in tools if t.name in CORE_TOOLS]
    rest = sorted((t for t in tools if t.name not in CORE_TOOLS), key=lambda t: (-score(t), t.name))
    picked = core + [t for t in rest if score(t) > 0][:max(0, max_tools - len(core))]
    picked.sort(key=lambda t: (t.name != 'say', t.name not in CORE_TOOLS, t.name))
    return picked


def execute(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Run a tool by name with keyword arguments; errors come back as data."""
    tool = get_tool(name)
    if not tool:
        return _err(f"unknown tool {name}")
    kwargs = {}
    for k, v in (arguments or {}).items():
        if k in tool.params:
            kwargs[k] = v
    missing = [r for r in tool.required if r not in kwargs or kwargs[r] in (None, '')]
    if missing:
        return _err(f"missing required argument(s): {', '.join(missing)}")
    try:
        result = tool.func(**kwargs)
        if isinstance(result, dict):
            return result
        return _ok(str(result))
    except Exception as e:
        return _err(f"{type(e).__name__}: {e}")


if __name__ == '__main__':
    print(f"{len(_REGISTRY)} tools")
    print(tool_catalog_text())
    print(json.dumps(execute('get_time', {}), indent=1))
