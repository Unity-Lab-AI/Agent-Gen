#!/usr/bin/env python3
"""voice.cmd_parts: parts of voice/commands.py; importing the package loads every part."""
from voice.cmd_parts import _base  # noqa: F401
from voice.cmd_parts import built_in_commands as _built_in_commands  # noqa: F401
from voice.cmd_parts import media_control_commands as _media_control_commands  # noqa: F401
from voice.cmd_parts import git_github_commands as _git_github_commands  # noqa: F401
from voice.cmd_parts import email_commands as _email_commands  # noqa: F401
from voice.cmd_parts import hearing_transcript_commands as _hearing_transcript_commands  # noqa: F401
