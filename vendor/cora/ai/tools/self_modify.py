#!/usr/bin/env python3
"""C.O.R.A tools: self-modify. Registered on import (see ai/tools/__init__.py)."""

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

# =========================================================================== self-modify
@_tool('create_script', 'Write a Python script CORA can run later (self-modification).', 'scripts',
       {'name': _p('Script name'), 'code': _p('Python source'), 'description': _p('What it does')}, ['name', 'code'])
def t_create_script(name: str, code: str, description: str = ''):
    from cora_tools.self_modify import create_script
    return create_script(name, code, description or '')


@_tool('run_script', 'Run a saved script.', 'scripts', {'name': _p('Script name')}, ['name'], confirm=True)
def t_run_script(name: str):
    from cora_tools.self_modify import run_script
    return run_script(name, confirmed=True, delete_after=False)


@_tool('list_scripts', 'List saved scripts.', 'scripts')
def t_list_scripts():
    from cora_tools.self_modify import list_scripts
    return _ok('scripts', scripts=list_scripts())


@_tool('delete_script', 'Delete a saved script.', 'scripts', {'name': _p('Script name')}, ['name'], confirm=True)
def t_delete_script(name: str):
    from cora_tools.self_modify import delete_script
    return _ok('deleted') if delete_script(name) else _err('not found')
