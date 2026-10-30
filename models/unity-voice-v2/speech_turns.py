"""Bounded turn planning and literal phrase pauses, without fabricated emotional controls.

Controls are out-of-band. They never enter G2P or teacher transcripts. Explicit
focus is refused: no word-level emphasis supervision is established. Silence and
chunk joins are engineering timing, not learned acting or guaranteed naturalness.
"""
import math
import re

from speech_text import EVENT_PATTERN, parse_speech_text

MAX_TURN_CHARS, MAX_TURN_CHUNKS, MAX_TURN_SECONDS = 12000, 64, 120.0
CHUNK_CHARS, JOIN_SECONDS, MAX_PAUSES = 240, 0.08, 16


def phrase_end(text, phrase):
    if not isinstance(phrase, str) or not phrase.strip() or len(phrase) > 240:
        raise ValueError("Pause phrase must be an exact nonempty phrase of at most 240 characters")
    if any(kind == "event" for kind, _ in parse_speech_text(phrase)):
        raise ValueError("Phrase pause anchors must use lexical words, not event markers")
    matches = []
    for match in re.finditer(re.escape(phrase), text, re.IGNORECASE):
        before = text[match.start() - 1] if match.start() else ""
        after = text[match.end()] if match.end() < len(text) else ""
        if (not phrase[0].isalnum() or not before.isalnum()) and (not phrase[-1].isalnum() or not after.isalnum()):
            matches.append(match.end())
    if len(matches) != 1:
        raise ValueError("Pause phrase is missing/ambiguous; use a unique exact lexical phrase")
    end = matches[0]
    while end < len(text) and text[end] in ".,!?;:\"'”’":
        end += 1  # retain the phrase's question/terminal punctuation on its spoken side
    return end


def plan_turn(text, pauses=None, focus=None):
    if focus is not None:
        raise ValueError("Explicit word focus is unsupported without word-level performed supervision; ordinary lexical stress remains")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TURN_CHARS:
        raise ValueError("Turn must contain 1..12000 characters; split longer turns explicitly")
    parse_speech_text(text)  # unsupported markup still fails before any synthesis
    if pauses is None:
        pauses = []
    if not isinstance(pauses, (list, tuple)) or len(pauses) > MAX_PAUSES:
        raise ValueError("At most 16 explicit phrase pauses are supported")
    anchors = {}
    for pause in pauses:
        if not isinstance(pause, dict) or set(pause) != {"after", "seconds"}:
            raise ValueError("Each phrase pause needs exactly 'after' and 'seconds'")
        seconds = pause["seconds"]
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not .05 <= seconds <= 2.0:
            raise ValueError("Phrase pause must be finite in 0.05..2.0 seconds")
        end = phrase_end(text, pause["after"])
        if end in anchors:
            raise ValueError("Duplicate pause anchor; use one duration per phrase")
        anchors[end] = float(seconds)
    event_spans = [marker.span() for marker in EVENT_PATTERN.finditer(text)]

    def safe(position):
        return not any(start < position < end for start, end in event_spans)

    if any(not safe(end) for end in anchors):
        raise ValueError("Pause anchor would split a nonverbal event marker")
    chunks, start = [], 0
    while start < len(text):
        while start < len(text) and text[start].isspace():
            start += 1
        if start == len(text):
            break
        next_anchor = min((end for end in anchors if end > start), default=len(text))
        target = min(next_anchor, len(text))
        if target - start > CHUNK_CHARS:
            upper = start + CHUNK_CHARS
            punctuation = [match.end() for match in re.finditer(r"[.!?;,:](?:[\"'”’])?(?=\s|$)", text[start:upper])
                           if safe(start + match.end())]
            if punctuation:
                target = start + punctuation[-1]
            else:
                spaces = [position for position in range(start + 1, upper + 1) if text[position - 1].isspace() and safe(position)]
                if not spaces:
                    raise ValueError("Turn contains an overlong unsplittable token; repair it instead of truncating")
                target = spaces[-1]
        if target <= start or not safe(target):
            raise ValueError("Unable to plan a bounded speech chunk safely")
        value = text[start:target].strip()
        if not value:
            raise ValueError("Empty planned speech chunk")
        chunks.append({"text": value, "pause_seconds": anchors.get(target, JOIN_SECONDS if target < len(text) else 0.0)})
        if len(chunks) > MAX_TURN_CHUNKS:
            raise ValueError("Turn exceeds 64 bounded chunks; split it explicitly")
        start = target
    return chunks
