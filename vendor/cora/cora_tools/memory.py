#!/usr/bin/env python3
"""
C.O.R.A Memory System
Quick remember/recall for session context

Per ARCHITECTURE.md v1.0.0:
- Store key-value pairs in working memory
- Persist to file
- Auto-load on boot
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Any, Dict, List

# Memory file location
PROJECT_DIR = Path(__file__).parent.parent
MEMORY_FILE = PROJECT_DIR / 'data' / 'working_memory.json'


class Memory:
    """Working memory for CORA - quick remember/recall."""

    def __init__(self, memory_file: Optional[Path] = None):
        """Initialize memory system.

        Args:
            memory_file: Path to working_memory.json
        """
        self.memory_file = memory_file or MEMORY_FILE
        self._memory: Dict[str, Dict[str, Any]] = {}
        self._dirty = False

        # Load existing memory
        self.load()

    def load(self) -> bool:
        """Load memory from file.

        Returns:
            True if loaded successfully
        """
        try:
            if self.memory_file.exists():
                with open(self.memory_file) as f:
                    data = json.load(f)
                    self._memory = data.get('memory', {})
                    return True
        except Exception as e:
            print(f"[!] Memory load error: {e}")
        return False

    def save(self) -> bool:
        """Save memory to file.

        Returns:
            True if saved successfully
        """
        try:
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'version': '1.0.0',
                'description': 'CORA working memory',
                'memory': self._memory
            }
            with open(self.memory_file, 'w') as f:
                json.dump(data, f, indent=2)
            self._dirty = False
            return True
        except Exception as e:
            print(f"[!] Memory save error: {e}")
            return False

    def remember(self, key: str, value: Any) -> bool:
        """Store a value in memory.

        Args:
            key: Unique key for this memory
            value: Value to store (any JSON-serializable type)

        Returns:
            True if stored
        """
        now = datetime.now().isoformat()

        if key in self._memory:
            # Update existing
            self._memory[key]['value'] = value
            self._memory[key]['updated'] = now
        else:
            # Create new
            self._memory[key] = {
                'value': value,
                'created': now,
                'updated': now,
                'access_count': 0,
                'last_accessed': None
            }

        self._dirty = True
        self.save()  # Auto-save on change
        return True

    def recall(self, key: Optional[str] = None) -> Any:
        """Recall a value from memory.

        Args:
            key: Key to recall, or None for all memory

        Returns:
            Value if key provided, or dict of all memory
        """
        if key is None:
            # Return all memory
            return {k: v.get('value') for k, v in self._memory.items()}

        if key in self._memory:
            entry = self._memory[key]
            # Update access tracking
            entry['access_count'] = entry.get('access_count', 0) + 1
            entry['last_accessed'] = datetime.now().isoformat()
            self._dirty = True
            return entry.get('value')

        return None

    def forget(self, key: str) -> bool:
        """Remove a value from memory.

        Args:
            key: Key to forget

        Returns:
            True if removed
        """
        if key in self._memory:
            del self._memory[key]
            self._dirty = True
            self.save()
            return True
        return False

    def forget_all(self) -> bool:
        """Clear all memory.

        Returns:
            True if cleared
        """
        self._memory = {}
        self._dirty = True
        return self.save()

    def exists(self, key: str) -> bool:
        """Check if a key exists in memory.

        Args:
            key: Key to check

        Returns:
            True if exists
        """
        return key in self._memory

    def keys(self) -> List[str]:
        """Get all memory keys.

        Returns:
            List of keys
        """
        return list(self._memory.keys())

    def count(self) -> int:
        """Get number of items in memory.

        Returns:
            Count of memory entries
        """
        return len(self._memory)

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics.

        Returns:
            Dict with stats about memory usage
        """
        total_access = sum(
            e.get('access_count', 0) for e in self._memory.values()
        )

        most_accessed = None
        max_access = 0
        for k, v in self._memory.items():
            if v.get('access_count', 0) > max_access:
                max_access = v.get('access_count', 0)
                most_accessed = k

        return {
            'total_entries': len(self._memory),
            'total_accesses': total_access,
            'most_accessed': most_accessed,
            'most_accessed_count': max_access
        }

    def search(self, query: str) -> Dict[str, Any]:
        """Search memory by key or value.

        Args:
            query: Search string

        Returns:
            Dict of matching entries
        """
        query_lower = query.lower()
        results = {}

        for k, v in self._memory.items():
            # Check key
            if query_lower in k.lower():
                results[k] = v.get('value')
                continue

            # Check value (if string)
            val = v.get('value')
            if isinstance(val, str) and query_lower in val.lower():
                results[k] = val

        return results


# Global memory instance
_memory: Optional[Memory] = None


def get_memory() -> Memory:
    """Get or create the global memory instance.

    Returns:
        Memory instance
    """
    global _memory
    if _memory is None:
        _memory = Memory()
    return _memory


# Convenience functions

def remember(key: str, value: Any) -> bool:
    """Store a value in working memory.

    Args:
        key: Unique key
        value: Value to store

    Returns:
        True if stored
    """
    return get_memory().remember(key, value)


def recall(key: Optional[str] = None) -> Any:
    """Recall a value from working memory.

    Args:
        key: Key to recall, or None for all

    Returns:
        Value or dict of all values
    """
    return get_memory().recall(key)


def forget(key: str) -> bool:
    """Forget a value from working memory.

    Args:
        key: Key to forget

    Returns:
        True if forgotten
    """
    return get_memory().forget(key)


def remember_context(context: Dict[str, Any]) -> int:
    """Remember multiple values at once.

    Args:
        context: Dict of key-value pairs

    Returns:
        Number of items remembered
    """
    mem = get_memory()
    count = 0
    for k, v in context.items():
        if mem.remember(k, v):
            count += 1
    return count


def recall_context(*keys: str) -> Dict[str, Any]:
    """Recall multiple values at once.

    Args:
        *keys: Keys to recall

    Returns:
        Dict of key-value pairs
    """
    mem = get_memory()
    return {k: mem.recall(k) for k in keys if mem.exists(k)}


if __name__ == "__main__":
    print("=== MEMORY SYSTEM TEST ===")

    mem = get_memory()

    print(f"\nMemory file: {mem.memory_file}")
    print(f"Current entries: {mem.count()}")

    # Test remember/recall
    print("\n--- Remember Test ---")
    remember("test_key", "test_value")
    remember("user_name", "George")
    remember("last_topic", "CORA development")

    print(f"Entries after remember: {mem.count()}")

    print("\n--- Recall Test ---")
    print(f"test_key: {recall('test_key')}")
    print(f"user_name: {recall('user_name')}")
    print(f"all memory: {recall()}")

    print("\n--- Search Test ---")
    results = mem.search("test")
    print(f"Search 'test': {results}")

    print("\n--- Stats ---")
    stats = mem.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Cleanup test
    print("\n--- Cleanup ---")
    forget("test_key")
    print(f"After forget: {mem.count()} entries")
