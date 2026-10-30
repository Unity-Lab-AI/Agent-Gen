#!/usr/bin/env python3
"""voice.cmd_parts: git_github_commands (split from voice/commands.py on 2026-10-14)."""
from __future__ import annotations

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass
from voice.cmd_parts import _base  # noqa: F401
from voice.cmd_parts._base import CommandResult, Dict, PROJECT_DIR, register_command, sys  # noqa: F401




# ==================== GIT & GITHUB COMMANDS ====================

@register_command("git status", aliases=["git stat", "repo status"])
def cmd_git_status(args: str, context: Dict) -> CommandResult:
    """Show git repository status."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.git_ops import git_status

        result = git_status()
        if result['success']:
            return CommandResult(
                success=True,
                message=result.get('status', 'Repository is clean'),
                should_speak=True
            )
        return CommandResult(success=False, message=result.get('error', 'Git error'), should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Git error: {e}", should_speak=True)


@register_command("git pull", aliases=["pull changes", "pull from remote"])
def cmd_git_pull(args: str, context: Dict) -> CommandResult:
    """Pull latest changes from remote."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.git_ops import git_pull

        result = git_pull()
        if result['success']:
            return CommandResult(
                success=True,
                message=f"Pulled changes. {result.get('output', 'Up to date')}",
                should_speak=True
            )
        return CommandResult(success=False, message=result.get('error', 'Pull failed'), should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Pull error: {e}", should_speak=True)


@register_command("git push", aliases=["push changes", "push to remote"])
def cmd_git_push(args: str, context: Dict) -> CommandResult:
    """Push commits to remote."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.git_ops import git_push

        result = git_push()
        if result['success']:
            return CommandResult(
                success=True,
                message=f"Pushed to remote. {result.get('message', '')}",
                should_speak=True
            )
        return CommandResult(success=False, message=result.get('error', 'Push failed'), should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Push error: {e}", should_speak=True)


@register_command("git commit", aliases=["commit changes"])
def cmd_git_commit(args: str, context: Dict) -> CommandResult:
    """Commit staged changes with a message."""
    if not args:
        return CommandResult(success=False, message="Need a commit message", should_speak=True)

    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.git_ops import git_commit

        result = git_commit(args)
        if result['success']:
            return CommandResult(
                success=True,
                message=f"Committed: {args[:40]}",
                should_speak=True
            )
        return CommandResult(success=False, message=result.get('error', 'Commit failed'), should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Commit error: {e}", should_speak=True)


@register_command("git add", aliases=["stage files", "add files"])
def cmd_git_add(args: str, context: Dict) -> CommandResult:
    """Stage files for commit."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.git_ops import git_add

        files = args if args else '.'
        result = git_add(files)
        if result['success']:
            return CommandResult(
                success=True,
                message=f"Staged: {files}",
                should_speak=True
            )
        return CommandResult(success=False, message=result.get('error', 'Add failed'), should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Add error: {e}", should_speak=True)


@register_command("git branch", aliases=["list branches", "show branches"])
def cmd_git_branch(args: str, context: Dict) -> CommandResult:
    """List all branches."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.git_ops import git_branch

        result = git_branch()
        if result['success']:
            current = result.get('current', 'unknown')
            return CommandResult(
                success=True,
                message=f"On branch: {current}",
                should_speak=True
            )
        return CommandResult(success=False, message=result.get('error', 'Branch error'), should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Branch error: {e}", should_speak=True)


@register_command("git checkout", aliases=["switch branch", "change branch"])
def cmd_git_checkout(args: str, context: Dict) -> CommandResult:
    """Switch to a branch."""
    if not args:
        return CommandResult(success=False, message="Need a branch name", should_speak=True)

    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.git_ops import get_git

        git = get_git()
        # Check for -b flag for new branch
        if args.startswith('-b '):
            branch = args[3:].strip()
            result = git.checkout_new(branch)
        else:
            result = git.checkout(args)

        if result['success']:
            return CommandResult(
                success=True,
                message=result.get('message', f'Switched to {args}'),
                should_speak=True
            )
        return CommandResult(success=False, message=result.get('error', 'Checkout failed'), should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Checkout error: {e}", should_speak=True)


@register_command("git merge", aliases=["merge branch"])
def cmd_git_merge(args: str, context: Dict) -> CommandResult:
    """Merge a branch into current branch."""
    if not args:
        return CommandResult(success=False, message="Need a branch name to merge", should_speak=True)

    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.git_ops import git_merge

        result = git_merge(args)
        if result['success']:
            return CommandResult(
                success=True,
                message=f"Merged {args}",
                should_speak=True
            )
        return CommandResult(success=False, message=result.get('error', 'Merge failed'), should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Merge error: {e}", should_speak=True)


@register_command("git clone", aliases=["clone repo", "clone repository"])
def cmd_git_clone(args: str, context: Dict) -> CommandResult:
    """Clone a repository."""
    if not args:
        return CommandResult(success=False, message="Need a repository URL", should_speak=True)

    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.git_ops import git_clone

        result = git_clone(args)
        if result['success']:
            return CommandResult(
                success=True,
                message=f"Cloned repository",
                should_speak=True
            )
        return CommandResult(success=False, message=result.get('error', 'Clone failed'), should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Clone error: {e}", should_speak=True)


@register_command("git log", aliases=["commit history", "show commits"])
def cmd_git_log(args: str, context: Dict) -> CommandResult:
    """Show recent commits."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.git_ops import git_log

        count = int(args) if args and args.isdigit() else 5
        result = git_log(count)
        if result['success']:
            commits = result.get('commits', [])
            return CommandResult(
                success=True,
                message=f"Found {len(commits)} recent commits",
                should_speak=True
            )
        return CommandResult(success=False, message=result.get('error', 'Log error'), should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Log error: {e}", should_speak=True)


@register_command("github login", aliases=["login github", "github auth", "authenticate github"])
def cmd_github_login(args: str, context: Dict) -> CommandResult:
    """Login to GitHub (opens browser for token creation)."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.git_ops import github_login_browser, github_login

        if args:
            # Token provided directly
            result = github_login(args)
            if result['success']:
                return CommandResult(
                    success=True,
                    message=f"Logged in as {result.get('username', 'unknown')}",
                    should_speak=True
                )
            return CommandResult(success=False, message=result.get('error', 'Login failed'), should_speak=True)
        else:
            # Open browser
            result = github_login_browser()
            return CommandResult(
                success=True,
                message="Opening browser for GitHub authentication. Create a token and tell me the token to complete login.",
                should_speak=True
            )
    except Exception as e:
        return CommandResult(success=False, message=f"Login error: {e}", should_speak=True)


@register_command("github repos", aliases=["my repos", "list repos", "show repositories"])
def cmd_github_repos(args: str, context: Dict) -> CommandResult:
    """List your GitHub repositories."""
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.git_ops import github_repos

        result = github_repos()
        if result['success']:
            count = result.get('count', 0)
            return CommandResult(
                success=True,
                message=f"Found {count} repositories",
                should_speak=True
            )
        return CommandResult(success=False, message=result.get('error', 'Could not list repos'), should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Repos error: {e}", should_speak=True)


@register_command("github create", aliases=["create repo", "new repo", "create repository"])
def cmd_github_create(args: str, context: Dict) -> CommandResult:
    """Create a new GitHub repository."""
    if not args:
        return CommandResult(success=False, message="Need a repository name", should_speak=True)

    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools.git_ops import github_create_repo

        # Parse args: name [description] [--private]
        private = '--private' in args
        args = args.replace('--private', '').strip()
        parts = args.split(' ', 1)
        name = parts[0]
        description = parts[1] if len(parts) > 1 else ''

        result = github_create_repo(name, description, private)
        if result['success']:
            return CommandResult(
                success=True,
                message=f"Created repository: {result.get('full_name', name)}",
                should_speak=True
            )
        return CommandResult(success=False, message=result.get('error', 'Create failed'), should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Create error: {e}", should_speak=True)
