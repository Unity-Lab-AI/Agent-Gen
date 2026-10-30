#!/usr/bin/env python3
"""C.O.R.A tools: code. Registered on import (see ai/tools/__init__.py)."""

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

# =========================================================================== code
@_tool('explain_code', 'Explain a code snippet.', 'code', {'code': _p('Source code'), 'detail': _p('low, medium, high', enum=['low', 'medium', 'high'])}, ['code'])
def t_explain_code(code: str, detail: str = 'medium'):
    from cora_tools.code import explain_code
    return _ok(explain_code(code, detail or 'medium'))


@_tool('write_code', 'Generate code from a description.', 'code', {'description': _p('What to build'), 'language': _p('Language')}, ['description'])
def t_write_code(description: str, language: str = 'python'):
    from cora_tools.code import write_code
    return _ok(write_code(description, language or 'python'))


@_tool('fix_code', 'Fix a code snippet (optionally given the error).', 'code', {'code': _p('Code'), 'error': _p('Error text, optional')}, ['code'])
def t_fix_code(code: str, error: str = None):
    from cora_tools.code import fix_code
    return _ok(fix_code(code, error))


@_tool('analyze_code', 'Analyze code for issues.', 'code', {'code': _p('Code')}, ['code'])
def t_analyze_code(code: str):
    from cora_tools.code import analyze_code
    a = analyze_code(code)
    return _ok('analysis', **(a.__dict__ if hasattr(a, '__dict__') else {'result': str(a)}))


@_tool('run_code', 'Execute a code snippet and return its output.', 'code',
       {'code': _p('Code'), 'language': _p('python/js/bash, optional')}, ['code'], confirm=True)
def t_run_code(code: str, language: str = None):
    from cora_tools.code import run_code
    r = run_code(code, language, safe_mode=True)
    return _ok('ran', **(r.__dict__ if hasattr(r, '__dict__') else {'result': str(r)}))


@_tool('open_code_editor', 'Open the CORA code editor (optionally on a file).', 'code', {'path': _p('File path, optional')})
def t_open_code_editor(path: str = None):
    from ui.code_editor import open_code_editor
    open_code_editor(file_path=path) if path else open_code_editor()
    return _ok('editor open')


@_tool('open_folder_in_editor', 'Open a folder tree in the code editor.', 'code', {'path': _p('Folder')}, ['path'])
def t_open_folder_in_editor(path: str):
    from ui.code_editor import open_folder
    open_folder(path)
    return _ok('folder open in editor')


@_tool('open_github_in_editor', 'Open a GitHub repository in the code editor.', 'code', {'url': _p('Repo URL')}, ['url'])
def t_open_github_in_editor(url: str):
    from ui.code_editor import open_github_repo
    open_github_repo(url)
    return _ok('repo open in editor')
