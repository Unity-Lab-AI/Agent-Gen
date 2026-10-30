#!/usr/bin/env python3
"""C.O.R.A tools: files. Registered on import (see ai/tools/__init__.py)."""

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

# =========================================================================== files
@_tool('read_file', 'Read a text file (inside allowed folders).', 'files', {'path': _p('File path')}, ['path'])
def t_read_file(path: str):
    from cora_tools.files import read_file
    c = read_file(path)
    return _ok('read', content=c[:8000], truncated=len(c) > 8000) if c is not None else _err('cannot read')


@_tool('write_file', 'Create or overwrite a text file.', 'files',
       {'path': _p('File path'), 'content': _p('Text content'), 'overwrite': _p('Overwrite if exists', 'boolean')}, ['path', 'content'])
def t_write_file(path: str, content: str, overwrite: bool = True):
    from cora_tools.files import create_file
    return _ok(f"wrote {path}") if create_file(path, content, overwrite=bool(overwrite)) else _err('write refused')


@_tool('append_file', 'Append text to a file.', 'files', {'path': _p('File path'), 'content': _p('Text')}, ['path', 'content'])
def t_append_file(path: str, content: str):
    from cora_tools.files import append_file
    return _ok('appended') if append_file(path, content) else _err('append refused')


@_tool('list_directory', 'List files in a folder.', 'files',
       {'path': _p('Folder path'), 'recursive': _p('Include subfolders', 'boolean')}, ['path'])
def t_list_directory(path: str, recursive: bool = False):
    from cora_tools.files import list_directory
    files = list_directory(path, recursive=bool(recursive))
    return _ok(f"{len(files)} file(s)", files=files[:200])


@_tool('file_info', 'Size/dates of a file.', 'files', {'path': _p('Path')}, ['path'])
def t_file_info(path: str):
    from cora_tools.files import get_file_info
    i = get_file_info(path)
    return _ok('info', **i) if i else _err('not found')


@_tool('search_in_file', 'Find lines containing text in a file.', 'files', {'path': _p('Path'), 'query': _p('Text')}, ['path', 'query'])
def t_search_in_file(path: str, query: str):
    from cora_tools.files import search_in_file
    hits = search_in_file(path, query)
    return _ok(f"{len(hits)} line(s)", lines=hits[:50])


@_tool('search_files', 'Find files by name under a folder.', 'files',
       {'query': _p('Name fragment'), 'path': _p('Folder (optional)')}, ['query'])
def t_search_files(query: str, path: str = None):
    from cora_tools.system import search_files
    r = search_files(query, path)
    return _ok('results', results=(r or [])[:100]) if r is not None else _err('search failed')


@_tool('delete_file', 'Delete a file.', 'files', {'path': _p('Path')}, ['path'], confirm=True)
def t_delete_file(path: str):
    from cora_tools.files import delete_file
    return _ok('deleted') if delete_file(path) else _err('delete refused')


@_tool('move_file', 'Move/rename a file.', 'files', {'source': _p('From'), 'destination': _p('To')}, ['source', 'destination'], confirm=True)
def t_move_file(source: str, destination: str):
    from cora_tools.files import move_file
    return _ok('moved') if move_file(source, destination, overwrite=False) else _err('move refused')


@_tool('copy_file', 'Copy a file.', 'files', {'source': _p('From'), 'destination': _p('To')}, ['source', 'destination'])
def t_copy_file(source: str, destination: str):
    from cora_tools.files import copy_file
    return _ok('copied') if copy_file(source, destination) else _err('copy refused')


@_tool('create_directory', 'Create a folder.', 'files', {'path': _p('Folder path')}, ['path'])
def t_create_directory(path: str):
    from cora_tools.files import create_directory
    return _ok('created') if create_directory(path) else _err('refused')


@_tool('open_path', 'Open a file, folder, or launch an application by name.', 'files', {'target': _p('Path or app name')}, ['target'])
def t_open_path(target: str):
    from cora_tools.system import open_file, open_folder, launch_app
    if os.path.isdir(target):
        return _ok('opened folder') if open_folder(target) else _err('could not open folder')
    if os.path.exists(target):
        return _ok('opened file') if open_file(target) else _err('could not open file')
    return _ok(f"launched {target}") if launch_app(target) else _err(f"could not open or launch {target}")
