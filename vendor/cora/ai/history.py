#!/usr/bin/env python3
"""
C.O.R.A conversation history — one shared, persisted transcript used by every
entry point (boot display, CLI, GUI app, voice loop).

Storage: data/chat_history.json as a list of
    {"role": "user"|"assistant"|"tool", "content": "...", "timestamp": iso,
     "tool_calls": [...]?, "tool_name": "..."?}
which is the same shape src/cora.py has always written, so old files load.
Tool calls and their results are KEPT in the transcript: the model was trained
on multi-turn conversations where every action is a tool call, and when the
history shows only plain-text answers she stops calling tools and riffs on
stale answers instead (seen live 2026-10-14).

The context sent to the model is bounded two ways:
  * by turn count (settings.history_turns), and
  * by a character budget derived from num_ctx so the system prompt + history
    always fit inside the model's window with room for the answer.
When the transcript grows past the budget, the oldest turns are folded into a
short running summary (kept at the top of the context as a system note) so
long conversations keep their thread without blowing the context window.
"""

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ai import settings as _settings

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / 'data'
# CORA_HISTORY_FILE points a scratch session (a check, a demo) at its own file so
# nothing but real use ever lands in her transcript.
HISTORY_FILE = Path(os.environ.get('CORA_HISTORY_FILE') or (DATA_DIR / 'chat_history.json'))
SUMMARY_FILE = HISTORY_FILE.with_name(HISTORY_FILE.stem + '_summary.json') if os.environ.get('CORA_HISTORY_FILE') else (DATA_DIR / 'chat_summary.json')

# ~4 characters per token is a safe average for English chat.
_CHARS_PER_TOKEN = 4


class ConversationHistory:
    """Thread-safe persisted transcript with context-window budgeting."""

    def __init__(self, path: Path = HISTORY_FILE, summary_path: Path = SUMMARY_FILE):
        self.path = Path(path)
        self.summary_path = Path(summary_path)
        self._lock = threading.RLock()
        self._messages: List[Dict] = []
        self._summary: str = ''
        self._load()

    # ----------------------------------------------------------------- storage
    def _load(self):
        try:
            if self.path.exists():
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._messages = [m for m in data
                                      if isinstance(m, dict) and m.get('role') and 'content' in m]
        except Exception:
            self._messages = []
        try:
            if self.summary_path.exists():
                with open(self.summary_path, 'r', encoding='utf-8') as f:
                    self._summary = (json.load(f) or {}).get('summary', '') or ''
        except Exception:
            self._summary = ''

    def _save(self):
        """Atomic write: tmp file + replace so a crash never corrupts the log."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix('.json.tmp')
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self._messages[-400:], f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
            tmp2 = self.summary_path.with_suffix('.json.tmp')
            with open(tmp2, 'w', encoding='utf-8') as f:
                json.dump({'summary': self._summary, 'updated': datetime.now().isoformat()}, f, indent=2)
            os.replace(tmp2, self.summary_path)
        except Exception as e:
            print(f"[HISTORY] save failed: {e}")

    # ----------------------------------------------------------------- editing
    def add(self, role: str, content: str, **extra):
        """Append a message and persist."""
        if content is None:
            content = ''
        with self._lock:
            msg = {'role': role, 'content': str(content), 'timestamp': datetime.now().isoformat()}
            msg.update(extra)
            self._messages.append(msg)
            self._save()

    def add_exchange(self, user_text: str, assistant_text: str, turn_messages: Optional[List[Dict]] = None):
        """One turn: the user line, the tool calls/results she made on the way
        (assistant messages with tool_calls + role=tool results), her final line."""
        with self._lock:
            self.add('user', user_text)
            for m in turn_messages or []:
                role = m.get('role')
                if role == 'assistant' and m.get('tool_calls'):
                    self.add('assistant', m.get('content', ''), tool_calls=m['tool_calls'])
                elif role == 'tool':
                    self.add('tool', m.get('content', ''), tool_name=m.get('tool_name', ''))
            self.add('assistant', assistant_text)

    def clear(self):
        with self._lock:
            self._messages = []
            self._summary = ''
            self._save()

    @property
    def summary(self) -> str:
        return self._summary

    def set_summary(self, text: str):
        with self._lock:
            self._summary = (text or '').strip()
            self._save()

    def __len__(self):
        return len(self._messages)

    def last(self, n: int = 10) -> List[Dict]:
        with self._lock:
            return list(self._messages[-n:])

    # ----------------------------------------------------------------- context
    def budget_chars(self, system_prompt: str = '', reserve_tokens: int = 1024) -> int:
        """Characters of history that fit beside the system prompt and an answer."""
        total = _settings.num_ctx() * _CHARS_PER_TOKEN
        return max(2000, total - len(system_prompt or '') - reserve_tokens * _CHARS_PER_TOKEN)

    def messages_for_model(self, system_prompt: str = '', max_turns: Optional[int] = None,
                           include_summary: bool = True) -> List[Dict[str, str]]:
        """History as Ollama messages (role/content only), trimmed to budget.

        The newest messages are always kept. When older ones are dropped and a
        running summary exists, it is prepended as a system note so the model
        still knows what happened before.
        """
        max_turns = max_turns or _settings.history_turns()
        budget = self.budget_chars(system_prompt)
        with self._lock:
            msgs = [m for m in self._messages if m.get('role') in ('user', 'assistant', 'tool')]
        msgs = msgs[-max_turns:]
        out: List[Dict[str, str]] = []
        used = 0
        for m in reversed(msgs):
            c = m.get('content', '') or ''
            entry: Dict = {'role': m['role'], 'content': c}
            if m.get('tool_calls'):
                entry['tool_calls'] = m['tool_calls']
                c += json.dumps(m['tool_calls'])
            if m.get('tool_name'):
                entry['tool_name'] = m['tool_name']
            if used + len(c) > budget and out:
                break
            out.append(entry)
            used += len(c)
        out.reverse()
        # never start the context with an assistant turn (confuses some templates)
        while out and out[0]['role'] != 'user':
            out.pop(0)
        if include_summary and self._summary and len(out) < len(msgs):
            out.insert(0, {'role': 'system',
                           'content': f"Earlier in this conversation (summary): {self._summary}"})
        return out

    def needs_summary(self, system_prompt: str = '') -> bool:
        """True when the transcript no longer fits the budget (time to fold)."""
        with self._lock:
            total = sum(len(m.get('content', '') or '') for m in self._messages)
        return total > self.budget_chars(system_prompt) * 0.75

    def fold_into_summary(self, summarizer, keep_last: int = 12) -> bool:
        """Summarize everything except the last `keep_last` messages using
        `summarizer(text) -> str` (e.g. ai.ollama.summarize). Returns True on success."""
        with self._lock:
            if len(self._messages) <= keep_last:
                return False
            old = self._messages[:-keep_last]
            transcript = '\n'.join(f"{m['role']}: {m.get('content', '')}" for m in old)
            prefix = f"Previous summary: {self._summary}\n\n" if self._summary else ''
        try:
            new_summary = summarizer(prefix + transcript)
        except Exception as e:
            print(f"[HISTORY] summarizer failed: {e}")
            return False
        if not new_summary or new_summary.startswith('[Error'):
            return False
        with self._lock:
            self._summary = new_summary.strip()[:4000]
            self._messages = self._messages[-keep_last:]
            self._save()
        return True


_shared: Optional[ConversationHistory] = None
_shared_lock = threading.Lock()


def get_history() -> ConversationHistory:
    """The process-wide shared transcript."""
    global _shared
    if _shared is None:
        with _shared_lock:
            if _shared is None:
                _shared = ConversationHistory()
    return _shared


if __name__ == '__main__':
    h = get_history()
    print(f"{len(h)} messages on disk; summary={h.summary[:80]!r}")
    for m in h.messages_for_model('x' * 1000)[-4:]:
        print(m['role'], ':', m['content'][:60])
