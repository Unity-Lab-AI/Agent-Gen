#!/usr/bin/env python3
"""C.O.R.A tools: knowledge + memory. Registered on import (see ai/tools/__init__.py)."""

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

# =========================================================================== knowledge + memory
_KB = PROJECT_DIR / 'data' / 'knowledge.json'


def _kb_load():
    try:
        with open(_KB, 'r', encoding='utf-8') as f:
            d = json.load(f)
        return d.get('counter', 0), d.get('entries', [])
    except Exception:
        return 0, []


def _kb_save(counter, entries):
    _KB.parent.mkdir(parents=True, exist_ok=True)
    tmp = _KB.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'counter': counter, 'entries': entries}, f, indent=2)
    os.replace(tmp, _KB)


@_tool('learn', 'Store a fact in the long-term knowledge base.', 'memory',
       {'text': _p('The fact to remember'), 'tags': _p('Comma-separated tags, optional')}, ['text'])
def t_learn(text: str, tags: str = ''):
    counter, entries = _kb_load()
    counter += 1
    tag_list = [t.strip().lstrip('#') for t in (tags or '').split(',') if t.strip()]
    entry = {'id': f"K{counter:03d}", 'content': text, 'tags': tag_list, 'created': datetime.now().isoformat()}
    entries.append(entry)
    _kb_save(counter, entries)
    return _ok(f"Learned {entry['id']}", id=entry['id'])


@_tool('recall_knowledge', 'Search the long-term knowledge base.', 'memory',
       {'query': _p('Words to search for (optional)'), 'tag': _p('Tag filter (optional)')})
def t_recall(query: str = '', tag: str = ''):
    _, entries = _kb_load()
    q = (query or '').lower().strip()
    tg = (tag or '').lstrip('#').lower().strip()
    hits = [e for e in entries
            if (not tg or tg in [t.lower() for t in e.get('tags', [])])
            and (not q or all(w in e.get('content', '').lower() for w in q.split()))]
    return _ok(f"{len(hits)} entr{'y' if len(hits) == 1 else 'ies'}",
               entries=[{'id': e['id'], 'content': e['content'], 'tags': e.get('tags', [])} for e in hits[-15:]])


@_tool('forget_knowledge', 'Delete a knowledge entry by id.', 'memory', {'entry_id': _p('Knowledge id like K004')}, ['entry_id'], confirm=True)
def t_forget_knowledge(entry_id: str):
    counter, entries = _kb_load()
    kept = [e for e in entries if e.get('id') != entry_id.upper()]
    if len(kept) == len(entries):
        return _err('not found')
    _kb_save(counter, kept)
    return _ok(f"forgot {entry_id}")


@_tool('remember', 'Store a key/value in working memory (names, preferences, short facts).', 'memory',
       {'key': _p('Name of the thing'), 'value': _p('What to remember')}, ['key', 'value'])
def t_remember(key: str, value: str):
    from cora_tools.memory import remember
    return _ok(f"remembered {key}") if remember(key, value) else _err('memory write failed')


@_tool('recall_memory', 'Recall from working memory (all entries when key omitted).', 'memory', {'key': _p('Key, optional')})
def t_recall_memory(key: str = None):
    from cora_tools.memory import recall
    v = recall(key or None)
    return _ok('memory', value=v) if v not in (None, {}, []) else _err('nothing stored')


@_tool('forget_memory', 'Remove a working-memory key.', 'memory', {'key': _p('Key')}, ['key'])
def t_forget_memory(key: str):
    from cora_tools.memory import forget
    return _ok('forgotten') if forget(key) else _err('no such key')
