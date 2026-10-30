#!/usr/bin/env python3
"""C.O.R.A tools: git / github. Registered on import (see ai/tools/__init__.py)."""

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

# =========================================================================== git / github
def _git(fn, *a):
    from cora_tools import git_ops as G
    r = getattr(G, fn)(*a)
    return r if isinstance(r, dict) else _ok(str(r))


@_tool('git_status', 'Git status of the project repo.', 'git')
def t_git_status():
    return _git('git_status')


@_tool('git_pull', 'git pull.', 'git')
def t_git_pull():
    return _git('git_pull')


@_tool('git_push', 'git push.', 'git', confirm=True)
def t_git_push():
    return _git('git_push')


@_tool('git_commit', 'Commit staged changes.', 'git', {'message': _p('Commit message')}, ['message'])
def t_git_commit(message: str):
    return _git('git_commit', message)


@_tool('git_add', 'Stage files.', 'git', {'files': _p('Paths or "." for all')})
def t_git_add(files: str = '.'):
    return _git('git_add', files or '.')


@_tool('git_branch', 'List branches.', 'git')
def t_git_branch():
    return _git('git_branch')


@_tool('git_checkout', 'Switch branch (create with create=true).', 'git',
       {'branch': _p('Branch name'), 'create': _p('Create new', 'boolean')}, ['branch'])
def t_git_checkout(branch: str, create: bool = False):
    from cora_tools.git_ops import get_git
    g = get_git()
    r = g.checkout_new(branch) if create else g.checkout(branch)
    return r if isinstance(r, dict) else _ok(str(r))


@_tool('git_log', 'Recent commits.', 'git', {'count': _p('How many', 'integer')})
def t_git_log(count: int = 10):
    return _git('git_log', int(count or 10))


@_tool('git_diff', 'Unstaged diff.', 'git')
def t_git_diff():
    r = _git('git_diff')
    if isinstance(r, dict) and isinstance(r.get('diff'), str):
        r['diff'] = r['diff'][:6000]
    return r


@_tool('github_repos', "List the user's GitHub repositories.", 'git')
def t_github_repos():
    return _git('github_repos')


@_tool('github_create_repo', 'Create a GitHub repository.', 'git',
       {'name': _p('Repo name'), 'description': _p('Description'), 'private': _p('Private', 'boolean')}, ['name'], confirm=True)
def t_github_create_repo(name: str, description: str = '', private: bool = False):
    return _git('github_create_repo', name, description or '', bool(private))
