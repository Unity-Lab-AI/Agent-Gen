#!/usr/bin/env python3
"""src.cora_parts: knowledge (split from src/cora.py on 2026-10-14)."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import shutil
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from src.cora_parts import _base  # noqa: F401
from src.cora_parts._base import datetime, generate_knowledge_id, load_knowledge, save_knowledge  # noqa: F401




def cmd_learn(args, tasks):
    from src.cora_parts.chat import respond
    """Add a knowledge entry. Use #tags to categorize."""
    if not args:
        respond('error', {'message': "Please provide knowledge text. Usage: learn <text> [#tag1 #tag2 ...]"})
        return tasks

    text = ' '.join(args)

    # Extract tags (words starting with #)
    tags = [word[1:] for word in args if word.startswith('#')]
    content = ' '.join(word for word in args if not word.startswith('#'))

    entries = load_knowledge()
    entry = {
        'id': generate_knowledge_id(),
        'content': content,
        'tags': tags,
        'created': datetime.now().isoformat()
    }
    entries.append(entry)
    save_knowledge(entries)

    tag_str = ', '.join(tags) if tags else '(none)'
    respond('knowledge_added', {'id': entry['id'], 'content': content[:50], 'tags': tag_str})
    return tasks


def cmd_recall(args, tasks):
    from src.cora_parts.chat import respond
    """Recall knowledge entries. Optionally filter by tag."""
    entries = load_knowledge()

    if not entries:
        respond('info', {'message': "No knowledge entries found. Use 'learn <text>' to add one."})
        return tasks

    # Filter by tag if provided
    if args:
        tag = args[0].lstrip('#').lower()
        entries = [e for e in entries if tag in [t.lower() for t in e.get('tags', [])]]
        if not entries:
            respond('no_results', {'query': f"#{tag}"})
            return tasks
        print(f"\n=== KNOWLEDGE (tag: #{tag}) ===")
    else:
        print("\n=== KNOWLEDGE BASE ===")

    print("-" * 60)
    for entry in entries[-10:]:  # Show last 10
        tags = ' '.join(f"#{t}" for t in entry.get('tags', []))
        print(f"{entry['id']}: {entry['content'][:50]}")
        if tags:
            print(f"       Tags: {tags}")
        print()

    print("-" * 60)
    print(f"Total entries: {len(entries)}")
    return tasks


def cmd_remember(args, tasks):
    """Remember/recall working memory. Usage: remember [key] [value] or remember (show all)"""
    try:
        from cora_tools.memory import get_memory, remember, recall, forget
    except ImportError:
        print("Error: Memory module not available")
        return tasks

    mem = get_memory()

    if not args:
        # Show all memory
        all_mem = recall()
        if not all_mem:
            print("Working memory is empty.")
            print("Usage: remember <key> <value> - store something")
            print("       remember <key>         - recall a specific key")
            print("       remember               - show all memory")
            return tasks

        print("\n=== WORKING MEMORY ===")
        print("-" * 40)
        for key, value in all_mem.items():
            print(f"  {key}: {value}")
        print("-" * 40)
        print(f"Total: {mem.count()} entries")
        return tasks

    key = args[0]

    if len(args) == 1:
        # Recall specific key
        value = recall(key)
        if value is not None:
            print(f"{key}: {value}")
        else:
            print(f"No memory for '{key}'")
        return tasks

    # Remember key=value
    value = ' '.join(args[1:])
    remember(key, value)
    print(f"Remembered: {key} = {value}")
    return tasks
