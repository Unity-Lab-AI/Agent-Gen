#!/usr/bin/env python3
"""C.O.R.A tools: web. Registered on import (see ai/tools/__init__.py)."""

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

# =========================================================================== web
@_tool('web_search', 'Search the web and return the top results (title, url, snippet). Read the snippets and '
       'answer from them; use fetch_url on a result for the full page.', 'web',
       {'query': _p('Search query'), 'num_results': _p('How many', 'integer')}, ['query'])
def t_web_search(query: str, num_results: int = 5):
    from cora_tools.web import web_search
    r = web_search(query, int(num_results or 5), show_window=False)
    if not isinstance(r, dict):
        return _ok(str(r))
    if not r.get('success'):
        return _err(r.get('error') or 'search failed')
    res = r.get('results') or []
    lines = [f"{i}. {x.get('title', '')} - {x.get('snippet', '')[:200]} ({x.get('url', '')})" for i, x in enumerate(res, 1)]
    box = (res[0].get('answer_box') if res else '') or ''
    if box:
        lines.insert(0, f"Answer box from the search page: {box[:700]}")
    return _ok('\n'.join(lines) or 'no results', results=res, count=r.get('count'), answer_box=box or None)


@_tool('fetch_url', 'Fetch a web page and return its readable text (renders script-built pages in a browser when needed).',
       'web', {'url': _p('http(s) URL'), 'find': _p('Optional words to look for; the text around them is returned first')}, ['url'])
def t_fetch_url(url: str, find: str = None):
    from cora_tools.web import fetch_url
    r = fetch_url(url, show_window=False)
    if not isinstance(r, dict):
        return _ok(str(r)[:6000])
    if not r.get('success'):
        return _err(r.get('error') or 'fetch failed')
    text = r.get('text') or ''
    if find:
        import re as _re
        hits = [m.start() for m in _re.finditer(_re.escape(find.split()[0]), text, _re.I)][:4]
        if hits:
            text = ' ... '.join(text[max(0, h - 300):h + 500] for h in hits) + '\n\n' + text
    return _ok(text[:6000] or 'no readable text', url=r.get('url'), via=r.get('via'), length=r.get('length'))


@_tool('summarize_url', 'Fetch a page and summarize it.', 'web', {'url': _p('http(s) URL')}, ['url'])
def t_summarize_url(url: str):
    from cora_tools.web import summarize_url
    r = summarize_url(url)
    return r if isinstance(r, dict) else _ok(str(r))


@_tool('open_in_browser', "Open a URL in the user's default browser.", 'web', {'url': _p('URL')}, ['url'])
def t_open_in_browser(url: str):
    if not url.lower().startswith(('http://', 'https://')):
        url = 'https://' + url
    webbrowser.open(url)
    return _ok(f"opened {url}")


@_tool('browse_screenshot', 'Load a page in a headless browser and screenshot it (Playwright).', 'web', {'url': _p('URL')}, ['url'])
def t_browse_screenshot(url: str):
    from cora_tools.browser import browse_sync
    return browse_sync(url)
