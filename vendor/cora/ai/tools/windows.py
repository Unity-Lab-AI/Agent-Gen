#!/usr/bin/env python3
"""C.O.R.A tools: windows. Registered on import (see ai/tools/__init__.py)."""

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

# =========================================================================== windows
@_tool('list_windows', 'List open application windows.', 'windows')
def t_list_windows():
    from cora_tools.windows import list_windows
    return _ok('windows', windows=list_windows()[:60])


@_tool('focus_window', 'Bring a window to the front.', 'windows', {'name': _p('Window/app title fragment')}, ['name'])
def t_focus_window(name: str):
    from cora_tools.windows import focus_window
    return _ok('focused') if focus_window(name) else _err('window not found')


@_tool('minimize_window', 'Minimize a window.', 'windows', {'name': _p('Title fragment')}, ['name'])
def t_minimize_window(name: str):
    from cora_tools.windows import minimize_window
    return _ok('minimized') if minimize_window(name) else _err('window not found')


@_tool('maximize_window', 'Maximize a window.', 'windows', {'name': _p('Title fragment')}, ['name'])
def t_maximize_window(name: str):
    from cora_tools.windows import maximize_window
    return _ok('maximized') if maximize_window(name) else _err('window not found')


@_tool('close_window', 'Close a window.', 'windows', {'name': _p('Title fragment')}, ['name'], confirm=True)
def t_close_window(name: str):
    from cora_tools.windows import close_window
    return _ok('closed') if close_window(name) else _err('window not found')


@_tool('arrange_windows', 'Tile/arrange open windows.', 'windows',
       {'layout': _p('Layout', enum=['tile_horizontal', 'tile_vertical', 'cascade', 'grid'])})
def t_arrange_windows(layout: str = 'tile_horizontal'):
    from cora_tools.windows import arrange_windows
    return _ok('arranged') if arrange_windows(layout or 'tile_horizontal') else _err('arrange failed')
