#!/usr/bin/env python3
"""
C.O.R.A voice client for unity-voice-v2 — Unity AI Lab's own trained TTS.

The model (Backrooms/models/unity-voice-v2) runs as a sidecar HTTP server
(serve.py, 127.0.0.1:5123) in its own Python environment (torch 2.7.1+cu118,
misaki 0.9.4, numpy 2.x). CORA never imports the model; it POSTs text and
plays the WAV that comes back.

Contract (from serve.py / voice-meta.json, read 2026-10-14):
  POST /say  {"text", "emotion", "intensity", "speech_act"} -> audio/wav 24 kHz PCM16
  GET  /health -> {"ok": true}
  emotions: neutral warm happy amused excited sad concerned frustrated surprised
  speech acts: statement yes_no_question wh_question exclamation instruction
               reassurance aside
  events: [laughter] [breath]
  Only (emotion, act) pairs present in voice-meta.json delivery_support are
  accepted; anything else is HTTP 422. The phoneme vocabulary holds only
  space , . ?  so every other mark must be normalised first (voice_text()).
  There is no fallback voice by design: a refused line is reported, never
  faked.

Configuration (env > config.json tts.unity_voice > defaults):
  UNITY_VOICE_TTS_URL    http://127.0.0.1:5123
  UNITY_VOICE_MODEL_DIR  C:\\Users\\gfour\\Desktop\\Backrooms\\models\\unity-voice-v2
  UNITY_VOICE_PYTHON     interpreter that has the sidecar's deps (auto-detected)
  tts.unity_voice.autostart   start serve.py if it is not running (default true)
"""

import io
import json
import os
import re
import unicodedata
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent.parent

EMOTIONS = ("neutral", "warm", "happy", "amused", "excited", "sad", "concerned", "frustrated", "surprised")
SPEECH_ACTS = ("statement", "yes_no_question", "wh_question", "exclamation", "instruction", "reassurance", "aside")

_DEFAULT_MODEL_DIR = r"C:\Users\gfour\Desktop\Backrooms\models\unity-voice-v2"


# --------------------------------------------------------------------------- config
def _cfg() -> dict:
    try:
        with open(PROJECT_DIR / 'config' / 'config.json', 'r', encoding='utf-8') as f:
            return (json.load(f).get('tts') or {}).get('unity_voice') or {}
    except Exception:
        return {}


_c = _cfg()
VOICE_URL = (os.environ.get('UNITY_VOICE_TTS_URL') or _c.get('url') or 'http://127.0.0.1:5123').rstrip('/')
MODEL_DIR = Path(os.environ.get('UNITY_VOICE_MODEL_DIR') or _c.get('model_dir') or _DEFAULT_MODEL_DIR)
AUTOSTART = bool(_c.get('autostart', True))
DEFAULT_INTENSITY = float(_c.get('default_intensity', 0.5))
SIDECAR_LOG = PROJECT_DIR / 'data' / 'voice-sidecar.log'
PYTHON_CACHE = PROJECT_DIR / 'data' / '.voice_python'
TURN_LOCK = Path(tempfile.gettempdir()) / 'unity-voice.lock'   # same lock unity-speak.py uses


# --------------------------------------------------------------------------- text
def voice_text(text: str) -> str:
    """The line as her voice can take it.

    Ported verbatim in behaviour from Backrooms/.claude/tools/unity-speak.py:
    her phoneme vocabulary holds exactly four marks (space , . ?) and the
    server refuses the WHOLE line on any other mark. So every mark she lacks
    becomes the pause she has: a comma. "!" speaks as "." (the exclamation act
    keeps the energy). Words are never dropped; only [laughter] and [breath]
    keep their brackets.
    """
    t = str(text)
    # accented letters -> their base letter (cafe, naive, resume); symbols she can say -> words
    t = ''.join(c for c in unicodedata.normalize('NFKD', t) if not unicodedata.combining(c))
    t = t.replace('&', ' and ').replace('%', ' percent ').replace('+', ' plus ').replace('=', ' equals ')
    t = t.replace('@', ' at ').replace('$', ' dollars ').replace('#', ' number ')
    keep = {}
    for i, m in enumerate(re.findall(r"\[(?:laughter|breath)\]", t, flags=re.I)):
        key = "\x00%d\x00" % i
        keep[key] = m.lower()
        t = t.replace(m, key, 1)
    t = t.replace("\u2026", "...")
    t = re.sub(r"\.{2,}", ".", t)
    t = re.sub(r"[?!]*!+[?!]*", lambda m: "?" if "?" in m.group() else ".", t)
    t = re.sub(r"[\"\u201c\u201d\u201e\u00ab\u00bb]", "", t)                       # double quotes: silent
    t = re.sub(r"(?<![A-Za-z0-9])['\u2018\u2019`]+|['\u2018\u2019`]+(?![A-Za-z0-9])", "", t)   # quotes, not don't
    t = t.replace("\u2019", "'").replace("\u2018", "'")
    # every dash-like code point (em/en/figure/horizontal bar/minus/fullwidth, soft hyphen), bullets,
    # a spaced hyphen and a leading "- " list marker all become the pause she has
    t = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\u2043\ufe58\ufe63\uff0d\u00ad]", " - ", t)
    t = re.sub(r"[\u2022\u25cf\u25e6\u2023\u2219\u00b7]", ", ", t)
    t = re.sub(r"(^|\n)\s*-\s+", r"\1", t)
    t = re.sub(r"\s+-\s+", ", ", t)
    t = re.sub(r"\s*(?:[;:]|--+|[()\[\]{}<>]|\*+|_+|\|+|\^+|~+|\\+|/(?!\d))\s*", ", ", t)
    t = re.sub(r"\s*([,.?])", r"\1", t)                                              # no space before a mark
    t = re.sub(r"([,.?])(?=[^\s,.?])", r"\1 ", t)                                    # one space after a mark
    for _ in range(3):
        t = re.sub(r",(?:\s*,)+", ",", t)                                            # ", ," -> ","
        t = re.sub(r",\s*([.?])", r"\1", t)                                          # ", ." -> "."
        t = re.sub(r"([.?])\s*,", r"\1", t)                                          # ". ," -> "."
        t = re.sub(r"\.(?:\s*\.)+", ".", t)
        t = re.sub(r"\?(?:\s*[?.])+", "?", t)
    t = re.sub(r"\s+", " ", t).strip().lstrip(",.? ").strip()
    # last guard: her vocabulary is letters, digits, apostrophes inside words and the four marks.
    # Anything else that slipped through (a stray symbol, an accent she has no phoneme for) becomes
    # a space so the WHOLE line is not refused; words are never dropped.
    t = re.sub(r"[^A-Za-z0-9 ,.?'\x00]", " ", t)
    t = re.sub(r"(?<![A-Za-z0-9])'|'(?![A-Za-z0-9])", "", t)
    t = re.sub(r"\s*([,.?])", r"\1", t)
    t = re.sub(r",(?:\s*,)+", ",", t)
    for key, m in keep.items():
        t = t.replace(key, " " + m + " ")
    t = re.sub(r"\s+", " ", t).strip().lstrip(",.? ").strip()
    return t


_URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.I)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_ACTION_RE = re.compile(r"\*[^*\n]{1,80}\*")
_ITALIC_RE = re.compile(r"(?<!\w)_[^_\n]{1,80}_(?!\w)")
_CODE_RE = re.compile(r"```.*?```", re.S)
_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]+")


def prepare_text(text: str) -> str:
    """Strip what should not be spoken (action markers, code, URLs, emoji),
    then normalise to the voice's four marks. Markdown digits/decimals kept."""
    t = str(text or '')
    t = _CODE_RE.sub(' code block ', t)
    t = _ACTION_RE.sub(' ', t)
    t = _ITALIC_RE.sub(lambda m: m.group(0).strip('_'), t)
    t = _URL_RE.sub(' link ', t)
    t = _EMAIL_RE.sub(' email address ', t)
    t = _EMOJI_RE.sub(' ', t)
    t = re.sub(r"#+\s*", "", t)                 # markdown headings
    t = re.sub(r"^\s*[-*]\s+", "", t, flags=re.M)   # bullets
    return voice_text(t)


_SENT_SPLIT = re.compile(r"(?<=[.?])\s+")


def split_sentences(text: str, max_len: int = 400) -> List[str]:
    """Split normalised text into sentences; long ones are cut at commas."""
    out: List[str] = []
    for s in _SENT_SPLIT.split(text.strip()):
        s = s.strip()
        if not s:
            continue
        while len(s) > max_len:
            cut = s.rfind(',', 0, max_len)
            if cut < max_len // 3:
                cut = s.rfind(' ', 0, max_len)
            if cut <= 0:
                cut = max_len
            out.append(s[:cut].strip(' ,') + '.')
            s = s[cut:].strip(' ,')
        if s:
            out.append(s)
    return out


# --------------------------------------------------------------------------- delivery
_WH = ("what", "who", "where", "when", "why", "how", "which", "whose", "whom")
_IMPERATIVE = ("open", "run", "check", "tell", "show", "remember", "don't", "do not", "go", "stop", "look",
               "listen", "try", "make", "get", "put", "take", "send", "call", "set", "turn", "close", "start")
_REASSURE = ("it's okay", "its okay", "don't worry", "dont worry", "you're fine", "youre fine", "i got you",
             "i'm here", "im here", "no big deal", "you'll be fine", "we're good")

# CORA emotion names (voice/emotion.py) -> V2 (emotion, intensity)
_EMOTION_MAP: Dict[str, Tuple[str, float]] = {
    'neutral': ('neutral', 0.0),
    'excited': ('excited', 0.8),
    'concerned': ('concerned', 0.55),
    'satisfied': ('happy', 0.5),
    'urgent': ('concerned', 0.8),
    'questioning': ('neutral', 0.3),
    'warm': ('warm', 0.5),
    'caring': ('warm', 0.55),
    'gentle': ('warm', 0.3),
    'annoyed': ('frustrated', 0.55),
    'frustrated': ('frustrated', 0.8),
    'angry': ('frustrated', 0.85),
    'playful': ('amused', 0.55),
    'sarcastic': ('amused', 0.45),
    'happy': ('happy', 0.6),
    'amused': ('amused', 0.55),
    'sad': ('sad', 0.55),
    'tired': ('sad', 0.3),
    'bored': ('neutral', 0.2),
    'engaged': ('warm', 0.4),
    'surprised': ('surprised', 0.6),
    'thinking': ('neutral', 0.2),
}

_support_cache: Optional[Set[Tuple[str, str]]] = None
_support_loaded = False


def delivery_support() -> Optional[Set[Tuple[str, str]]]:
    """(emotion, speech_act) pairs the installed pair was trained on, from
    voice-meta.json. None when the file is not readable (then we trust the
    server and fall back on 422)."""
    global _support_cache, _support_loaded
    if _support_loaded:
        return _support_cache
    _support_loaded = True
    try:
        meta = json.loads((MODEL_DIR / 'voice-meta.json').read_text(encoding='utf-8'))
        rows = meta.get('delivery_support') or []
        pairs = {(r.get('emotion'), r.get('speech_act')) for r in rows if r.get('emotion') and r.get('speech_act')}
        _support_cache = pairs or None
    except Exception:
        _support_cache = None
    return _support_cache


def _supported(emotion: str, act: str) -> bool:
    sup = delivery_support()
    return True if sup is None else (emotion, act) in sup


def _fallback_pair(emotion: str, act: str) -> Tuple[str, str]:
    """Nearest supported pair: same emotion/statement, neutral/same act, neutral/statement."""
    for e, a in ((emotion, act), (emotion, 'statement'), ('neutral', act), ('neutral', 'statement')):
        if _supported(e, a):
            return e, a
    return 'neutral', 'statement'


def speech_act_for(sentence: str, original_had_bang: bool = False) -> str:
    s = sentence.strip().lower()
    if not s:
        return 'statement'
    first = s.split(maxsplit=1)[0].strip(",.?")
    if s.endswith('?'):
        return 'wh_question' if first in _WH else 'yes_no_question'
    if original_had_bang:
        return 'exclamation'
    if any(s.startswith(k) for k in _IMPERATIVE):
        return 'instruction'
    if any(k in s for k in _REASSURE):
        return 'reassurance'
    return 'statement'


def map_emotion(emotion: Optional[str]) -> Tuple[str, float]:
    e, i = _EMOTION_MAP.get((emotion or 'neutral').lower(), ('neutral', 0.0))
    scale = 1.0
    try:
        with open(PROJECT_DIR / 'config' / 'config.json', 'r', encoding='utf-8') as f:
            scale = float((json.load(f).get('emotion') or {}).get('intensity', 1.0))
    except Exception:
        pass
    if e == 'neutral':
        return e, 0.0
    return e, max(0.1, min(1.0, i * scale if scale else i))


def plan_delivery(sentence: str, emotion: Optional[str], original_had_bang: bool = False) -> Dict[str, object]:
    e, intensity = map_emotion(emotion)
    act = speech_act_for(sentence, original_had_bang)
    e, act = _fallback_pair(e, act)
    body: Dict[str, object] = {"text": sentence, "emotion": e, "speech_act": act}
    if e != 'neutral':
        body["intensity"] = round(intensity, 2)
    return body


# --------------------------------------------------------------------------- sidecar
def is_up(timeout: float = 2.0) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{VOICE_URL}/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _validate_python(exe: str) -> bool:
    try:
        r = subprocess.run([exe, '-c', 'import torch, misaki, soundfile, numpy'],
                           capture_output=True, text=True, timeout=120)
        return r.returncode == 0
    except Exception:
        return False


def find_sidecar_python() -> Optional[str]:
    """Interpreter that can import the sidecar's deps. Cached in data/.voice_python."""
    cands: List[str] = []
    for c in (os.environ.get('UNITY_VOICE_PYTHON'), _c.get('python')):
        if c:
            cands.append(c)
    try:
        if PYTHON_CACHE.exists():
            cached = PYTHON_CACHE.read_text(encoding='utf-8').strip()
            if cached and Path(cached).exists():
                return cached
    except Exception:
        pass
    cands += [
        r"C:\Program Files\Python310\python.exe",
        str(MODEL_DIR.parent.parent / '.local' / 'voice-lab' / '.venv-cosy' / 'Scripts' / 'python.exe'),
        shutil.which('python') or '',
        sys.executable,
    ]
    for c in cands:
        if c and Path(c).exists() and _validate_python(c):
            try:
                PYTHON_CACHE.parent.mkdir(parents=True, exist_ok=True)
                PYTHON_CACHE.write_text(c, encoding='utf-8')
            except Exception:
                pass
            return c
    return None


_start_lock = threading.Lock()


def ensure_sidecar(timeout: float = 45.0) -> Tuple[bool, str]:
    """Make sure serve.py answers. Starts it (detached) when autostart is on."""
    if is_up():
        return True, "running"
    if not AUTOSTART:
        return False, "down (autostart disabled)"
    serve = MODEL_DIR / 'serve.py'
    if not serve.exists():
        return False, f"serve.py not found in {MODEL_DIR}"
    with _start_lock:
        if is_up():
            return True, "running"
        py = find_sidecar_python()
        if not py:
            return False, "no Python with torch+misaki found (set UNITY_VOICE_PYTHON)"
        port = VOICE_URL.rsplit(':', 1)[-1]
        try:
            SIDECAR_LOG.parent.mkdir(parents=True, exist_ok=True)
            log = open(SIDECAR_LOG, 'ab', buffering=0)
            flags = 0
            if os.name == 'nt':
                flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, 'DETACHED_PROCESS', 0)
            proc = subprocess.Popen([py, '-u', str(serve), '--port', str(port)], cwd=str(MODEL_DIR),
                                    stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=flags)
            # stop.bat / stop.sh end only sidecars CORA started herself (the stream has its own)
            try:
                run_dir = PROJECT_DIR / 'data' / 'run'
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / 'voice-sidecar.pid').write_text(str(proc.pid), encoding='utf-8')
            except Exception:
                pass
        except Exception as e:
            return False, f"could not start sidecar: {e}"
        deadline = time.time() + timeout
        while time.time() < deadline:
            if is_up(1.0):
                return True, f"started with {py}"
            time.sleep(0.5)
        return False, f"started but no /health answer in {timeout:.0f}s (see {SIDECAR_LOG})"


# --------------------------------------------------------------------------- turn lock (shared with Unity)
def take_turn(wait: float = 90.0, stale: float = 120.0) -> bool:
    """One line at a time across every process that uses her voice."""
    end = time.time() + wait
    while True:
        try:
            fd = os.open(str(TURN_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            try:
                if time.time() - TURN_LOCK.stat().st_mtime > stale:
                    TURN_LOCK.unlink(missing_ok=True)
                    continue
            except OSError:
                continue
            if time.time() > end:
                return False
            time.sleep(0.2)
        except OSError:
            return True   # lock dir unusable: don't block speech


def give_turn():
    try:
        TURN_LOCK.unlink(missing_ok=True)
    except OSError:
        pass


# --------------------------------------------------------------------------- synthesis
class VoiceRefused(Exception):
    """The server rejected the line (HTTP 422) — reported, never faked."""


class VoiceDown(Exception):
    """The sidecar is not reachable."""


def synth(body: Dict[str, object], timeout: float = 60.0) -> np.ndarray:
    """POST one line; returns float32 mono samples at 24 kHz."""
    import urllib.request
    import urllib.error
    import soundfile as sf
    req = urllib.request.Request(f"{VOICE_URL}/say", json.dumps(body).encode('utf-8'),
                                 {'Content-Type': 'application/json'})
    try:
        wav = urllib.request.urlopen(req, timeout=timeout).read()
    except urllib.error.HTTPError as e:
        raise VoiceRefused(e.read().decode('utf-8', 'replace')[:300])
    except OSError as e:
        raise VoiceDown(f"voice server not reachable at {VOICE_URL} ({e})")
    data, sr = sf.read(io.BytesIO(wav), dtype='float32')
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 24000:
        # simple linear resample (the server is fixed at 24 kHz, this is a guard)
        n = int(len(data) * 24000 / sr)
        data = np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data).astype('float32')
    return data


def synth_with_fallback(sentence: str, emotion: Optional[str], original_had_bang: bool = False) -> np.ndarray:
    """Synth one sentence; on a 422 for the delivery, retry once as neutral/statement."""
    body = plan_delivery(sentence, emotion, original_had_bang)
    try:
        return synth(body)
    except VoiceRefused as e:
        if body.get('emotion') != 'neutral' or body.get('speech_act') != 'statement':
            retry = {"text": sentence, "emotion": "neutral", "speech_act": "statement"}
            try:
                return synth(retry)
            except VoiceRefused as e2:
                raise VoiceRefused(f"{e2}")
        raise


def synth_delivery(sentence: str, emotion: Optional[str], speech_act: Optional[str],
                   intensity: Optional[float] = None) -> np.ndarray:
    """Synth one sentence with the designators her brain chose (a say() call:
    emotion + act, the exact names the voice was trained on). Unknown names
    fall to neutral/statement, an untrained pair goes to the nearest trained
    one, and a 422 retries once as neutral/statement."""
    e = (emotion or 'neutral').strip().lower()
    a = (speech_act or 'statement').strip().lower()
    if e not in EMOTIONS:
        e = 'neutral'
    if a not in SPEECH_ACTS:
        a = 'statement'
    e, a = _fallback_pair(e, a)
    body: Dict[str, object] = {"text": sentence, "emotion": e, "speech_act": a}
    if e != 'neutral':
        i = DEFAULT_INTENSITY if intensity is None else float(intensity)
        body["intensity"] = round(max(0.1, min(1.0, i)), 2)
    try:
        return synth(body)
    except VoiceRefused:
        if e != 'neutral' or a != 'statement':
            return synth({"text": sentence, "emotion": "neutral", "speech_act": "statement"})
        raise


if __name__ == '__main__':
    print("URL:", VOICE_URL, " model dir:", MODEL_DIR, " exists:", MODEL_DIR.exists())
    print("support pairs:", len(delivery_support() or []))
    print("voice_text:", voice_text('Hey! "Scar" is out -- planting (crops); honestly? [laughter] cool...'))
    ok, msg = ensure_sidecar()
    print("sidecar:", ok, msg)
    if ok:
        a = synth_with_fallback("Voice synthesis online. Her own voice, version two.", 'excited', True)
        print("samples:", len(a), f"{len(a)/24000:.2f}s")
