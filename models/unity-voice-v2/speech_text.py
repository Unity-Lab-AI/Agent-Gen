"""Small shared speech-event frontend; labels are never pronounced as words.

Only [laughter] and [breath] are supported. They denote recorded nonverbal events,
not learned giggle/belly-laugh subtypes or automatic acting. Ordinary spans retain
the existing G2P phonemes and stress marks. No pause, word-focus or SSML controls.
"""
import re

FRONTEND_VERSION = "speech-events-v1"
EVENT_MARKERS = {"[laughter]": "<event:laughter>", "[breath]": "<event:breath>"}
EVENT_NAMES = {"<event:laughter>": "laughter", "<event:breath>": "breath"}
EVENT_PATTERN = re.compile(r"\[laughter\]|\[breath\]")
PAREN_STAGE = re.compile(
    r"\(\s*(?:laugh(?:s|ing|ter)?|giggles?|chuckles?|breath(?:ing)?|sighs?|pauses?|"
    r"whisper(?:s|ing)?|soft(?:ly)?|loud(?:ly)?|angry|angrily|happy|happily|sad|sadly|"
    r"excited|excitedly|crying|sobbing)(?:\b[^()\r\n]*)?\)",
    flags=re.IGNORECASE)


def parse_speech_text(text):
    """Return ('speech', unchanged span) / ('event', dedicated token) parts."""
    if not isinstance(text, str):
        raise ValueError("Speech text must be a string")
    if any(ord(char) < 32 and char not in "\t\r\n" for char in text):
        raise ValueError("Speech text contains an unsupported control character")
    parts, offset = [], 0
    for marker in EVENT_PATTERN.finditer(text):
        if marker.start() > offset:
            parts.append(("speech", text[offset:marker.start()]))
        parts.append(("event", EVENT_MARKERS[marker.group()]))
        offset = marker.end()
    if offset < len(text):
        parts.append(("speech", text[offset:]))
    for kind, value in parts:
        if kind == "speech" and (any(char in value for char in "[]<>{}`*") or PAREN_STAGE.search(value)):
            raise ValueError("Unsupported stage/control markup; only exact [laughter] and [breath] markers are supported")
    return parts


def lexical_text(text):
    """Remove supported event markers for transcript grouping and intent fallback."""
    return "".join(value if kind == "speech" else " " for kind, value in parse_speech_text(text))


def event_counts(text):
    counts = {name: 0 for name in EVENT_NAMES.values()}
    for kind, value in parse_speech_text(text):
        if kind == "event":
            counts[EVENT_NAMES[value]] += 1
    return counts


def event_only_group(text):
    """A reserved split group for a standalone event turn; never the spoken word 'laughter'."""
    tokens = [value for kind, value in parse_speech_text(text) if kind == "event"]
    return "<event-only:" + ",".join(EVENT_NAMES[token] for token in tokens) + ">" if tokens else ""


def speech_tokens(text, g2p, max_tokens):
    """One token per ordinary phoneme character, one whole token per supported event."""
    tokens = []
    for kind, value in parse_speech_text(text):
        if kind == "event":
            tokens.append(value)
        elif value.strip():
            phonemes = g2p(value)[0]
            if not isinstance(phonemes, str) or not phonemes or "❓" in phonemes:
                raise ValueError("Speech span contains missing/unknown phonemes")
            tokens.extend(phonemes)
    if not tokens or len(tokens) > max_tokens:
        raise ValueError("No usable speech tokens or utterance too long; split it into natural turns")
    return tokens
