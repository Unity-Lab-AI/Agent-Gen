#!/usr/bin/env python3
"""voice.cmd_parts: email_commands (split from voice/commands.py on 2026-10-14)."""
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
from voice.cmd_parts._base import CommandResult, Dict, register_command  # noqa: F401




# ============ EMAIL COMMANDS ============

@register_command("send email", aliases=["email", "send message", "message"])
def handle_send_email(args: str = "", context: Dict = None) -> CommandResult:
    """Send an email using default mail app."""
    try:
        from cora_tools.email_tool import parse_email_command, send_email

        # Parse natural language command
        parsed = parse_email_command(f"send email {args}" if not args.startswith("to ") else f"send email to {args}")

        if not parsed.get('success'):
            # Try simpler parsing: "email karen saying hi"
            parsed = parse_email_command(f"email {args}")

        if parsed.get('success'):
            result = send_email(parsed['to'], parsed['message'])
            if result['success']:
                return CommandResult(
                    success=True,
                    message=f"Opening email to {parsed['to']}",
                    should_speak=True
                )
            else:
                hint = result.get('hint', '')
                return CommandResult(
                    success=False,
                    message=result.get('error', 'Email failed') + (f". {hint}" if hint else ""),
                    should_speak=True
                )
        else:
            return CommandResult(
                success=False,
                message="Tell me who to email and what to say. Like: email Karen saying hello",
                should_speak=True
            )
    except Exception as e:
        return CommandResult(success=False, message=f"Email error: {e}", should_speak=True)


@register_command("check email", aliases=["read email", "read emails", "check emails", "open email", "open inbox", "inbox"])
def handle_check_email(args: str = "", context: Dict = None) -> CommandResult:
    """Open email inbox in default mail app."""
    try:
        from cora_tools.email_tool import read_emails

        result = read_emails()
        if result['success']:
            return CommandResult(
                success=True,
                message="Opening your email inbox",
                should_speak=True
            )
        return CommandResult(success=False, message=result.get('error', 'Could not open email'), should_speak=True)
    except Exception as e:
        return CommandResult(success=False, message=f"Email error: {e}", should_speak=True)


@register_command("add contact", aliases=["save contact", "new contact"])
def handle_add_contact(args: str = "", context: Dict = None) -> CommandResult:
    """Add a contact to the address book."""
    try:
        from cora_tools.email_tool import add_contact

        # Parse: "add contact karen karen@email.com" or "karen is karen@email.com"
        parts = args.strip().split()
        if len(parts) >= 2:
            # Last part should be email
            email = parts[-1]
            name = ' '.join(parts[:-1])

            if '@' in email:
                result = add_contact(name, email)
                if result['success']:
                    return CommandResult(
                        success=True,
                        message=f"Added {name} to contacts",
                        should_speak=True
                    )
                return CommandResult(success=False, message=result.get('error', 'Failed to add contact'), should_speak=True)

        return CommandResult(
            success=False,
            message="Tell me the name and email. Like: add contact Karen karen@email.com",
            should_speak=True
        )
    except Exception as e:
        return CommandResult(success=False, message=f"Contact error: {e}", should_speak=True)


@register_command("list contacts", aliases=["show contacts", "my contacts", "contacts"])
def handle_list_contacts(args: str = "", context: Dict = None) -> CommandResult:
    """List saved email contacts."""
    try:
        from cora_tools.email_tool import list_contacts

        result = list_contacts()
        if result['count'] > 0:
            names = ', '.join(result['contacts'].keys())
            return CommandResult(
                success=True,
                message=f"You have {result['count']} contacts: {names}",
                data=result['contacts'],
                should_speak=True
            )
        return CommandResult(
            success=True,
            message="No contacts saved yet. Add one with: add contact name email",
            should_speak=True
        )
    except Exception as e:
        return CommandResult(success=False, message=f"Contacts error: {e}", should_speak=True)
