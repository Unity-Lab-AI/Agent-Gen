#!/usr/bin/env python3
"""C.O.R.A tools: email. Registered on import (see ai/tools/__init__.py)."""

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

# =========================================================================== email
@_tool('send_email', 'Compose an email to a saved contact or address (opens the mail app).', 'email',
       {'to': _p('Contact name or email'), 'message': _p('Body'), 'subject': _p('Subject, optional')}, ['to', 'message'])
def t_send_email(to: str, message: str, subject: str = None):
    from cora_tools.email_tool import email_send
    return _ok(email_send(to, message, subject))


@_tool('check_email', 'Open the inbox in the mail app.', 'email')
def t_check_email():
    from cora_tools.email_tool import email_read
    return _ok(email_read())


@_tool('add_contact', 'Save an email contact.', 'email', {'name': _p('Name'), 'email': _p('Address')}, ['name', 'email'])
def t_add_contact(name: str, email: str):
    from cora_tools.email_tool import add_contact
    r = add_contact(name, email)
    return r if isinstance(r, dict) else _ok(str(r))


@_tool('list_contacts', 'List saved contacts.', 'email')
def t_list_contacts():
    from cora_tools.email_tool import list_contacts
    r = list_contacts()
    return r if isinstance(r, dict) else _ok(str(r))
