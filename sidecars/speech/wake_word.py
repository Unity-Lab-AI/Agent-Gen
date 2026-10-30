"""Wake-word matching on transcripts (adapted from C.O.R.A voice/wake_word.py, fuzzy path only).

Works on the text the recogniser produced rather than on audio, so it needs no model. Looks for one of the
wake phrases at the start of the transcript (allowing a filler word or two before it), scores it with a
sequence ratio, and returns what was said after it.
"""
from __future__ import annotations

import difflib
import re

DEFAULT_PHRASES = ("unity", "hey unity", "yo unity", "okay unity", "ok unity")
FILLERS = {"um", "uh", "hey", "so", "okay", "ok", "yo", "oh", "hi", "hello"}


def _words(text: str):
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def match(text: str, phrases=DEFAULT_PHRASES, threshold: float = 0.78):
    """Return {"matched": bool, "phrase", "confidence", "remainder"}."""
    words = _words(text)
    best = {"matched": False, "phrase": None, "confidence": 0.0, "remainder": (text or "").strip()}
    if not words:
        return best
    phrase_words = [(p, _words(p)) for p in phrases]
    # try windows starting at 0, 1 or 2 (skipping fillers)
    for start in range(0, min(3, len(words))):
        if start and words[start - 1] not in FILLERS:
            break
        for phrase, pw in phrase_words:
            n = len(pw)
            if start + n > len(words):
                continue
            window = " ".join(words[start:start + n])
            score = difflib.SequenceMatcher(None, window, " ".join(pw)).ratio()
            # a single-word phrase inside a longer multi-word phrase should not beat it
            if score > best["confidence"]:
                best = {"matched": score >= threshold, "phrase": phrase, "confidence": round(score, 3),
                        "remainder": " ".join(words[start + n:])}
    if not best["matched"]:
        best["remainder"] = (text or "").strip()
    return best
