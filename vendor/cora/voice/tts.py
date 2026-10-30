"""
C.O.R.A Text-to-Speech Module

CORA speaks with unity-voice-v2 — Unity AI Lab's own trained voice — through
the sidecar client in voice/unity_voice.py. There is no other engine and no
fallback voice: if the sidecar is down or refuses a line, that is reported.

Keeps the module API every caller uses:
    set_boot_display / process_speech_queue   (UI text updates)
    TTSEngine, UnityVoiceTTS, get_tts_engine, speak
    TTSQueue, get_tts_queue, queue_speak, speak_interrupt
and adds the two symbols callers always imported but never existed:
    stop_speaking(), speak_async()
"""

import json
import queue
import threading
import time
from pathlib import Path
from typing import Optional, Callable, List

import numpy as np

from voice import unity_voice as uv

PROJECT_DIR = Path(__file__).resolve().parent.parent

# Cross-process TTS mutex (CORA instances)
try:
    from voice.tts_mutex import get_mutex, heartbeat as _mutex_heartbeat
    TTS_MUTEX_AVAILABLE = True
except ImportError:
    TTS_MUTEX_AVAILABLE = False

# Presence (non-blocking cached answer from a background monitor)
try:
    from services.presence import user_is_present, get_monitor
    PRESENCE_AVAILABLE = True
except ImportError:
    PRESENCE_AVAILABLE = False

# Waveform audio buffer shared with the boot display
try:
    from ui.boot_display import _audio_buffer_singleton
    WAVEFORM_AVAILABLE = True
except ImportError:
    _audio_buffer_singleton = None
    WAVEFORM_AVAILABLE = False


# --------------------------------------------------------------------------- UI text bridge
_boot_display = None
_speech_queue = queue.Queue()


def set_boot_display(display):
    """Set the boot display reference for UI text updates."""
    global _boot_display
    _boot_display = display


def _update_speech_text(text: str):
    _speech_queue.put(('start', text))


def _clear_speech_text():
    _speech_queue.put(('stop', None))


def process_speech_queue():
    """Process pending speech text updates (call from the Tk main thread)."""
    try:
        while not _speech_queue.empty():
            action, text = _speech_queue.get_nowait()
            if _boot_display:
                if action == 'start' and text:
                    _boot_display.start_speaking(text)
                elif action == 'stop':
                    _boot_display.stop_speaking()
    except Exception:
        pass


# --------------------------------------------------------------------------- playback state
_stop_event = threading.Event()
_speaking = threading.Event()


def is_speaking() -> bool:
    return _speaking.is_set()


def stop_speaking():
    """Barge-in: stop the current line and drop everything queued."""
    _stop_event.set()
    q = _tts_queue
    if q is not None:
        q.clear()


def _tts_config() -> dict:
    try:
        with open(PROJECT_DIR / 'config' / 'config.json', 'r', encoding='utf-8') as f:
            return json.load(f).get('tts') or {}
    except Exception:
        return {}


# --------------------------------------------------------------------------- engine
class TTSEngine:
    """Base TTS engine interface."""

    def __init__(self):
        self.is_initialized = False

    def initialize(self):
        raise NotImplementedError

    def speak(self, text, emotion='neutral'):
        raise NotImplementedError

    def get_audio(self, text, emotion='neutral'):
        raise NotImplementedError


class UnityVoiceTTS(TTSEngine):
    """unity-voice-v2 over HTTP, sentence by sentence, with the Tk waveform fed
    from the playback callback (same contract the old engine had)."""

    SAMPLE_RATE = 24000

    def __init__(self, volume: Optional[float] = None):
        super().__init__()
        cfg = _tts_config()
        self.volume = float(cfg.get('volume', 1.0)) if volume is None else float(volume)
        self.sd = None
        self.last_error: Optional[str] = None

    # -- lifecycle ----------------------------------------------------------
    def initialize(self) -> bool:
        try:
            import sounddevice as sd
            self.sd = sd
        except ImportError as e:
            self.last_error = f"sounddevice missing: {e}"
            print(f"[!] {self.last_error}")
            return False
        ok, msg = uv.ensure_sidecar()
        if not ok:
            self.last_error = f"unity-voice-v2 unavailable: {msg}"
            print(f"[!] {self.last_error}")
            self.is_initialized = False
            return False
        self.is_initialized = True
        return True

    # -- synthesis ----------------------------------------------------------
    def _sentences(self, text: str) -> List[tuple]:
        """[(sentence, had_bang)] after cleaning + normalisation."""
        raw = str(text or '')
        had_bang = '!' in raw
        clean = uv.prepare_text(raw)
        return [(s, had_bang and i == 0) for i, s in enumerate(uv.split_sentences(clean))], clean

    def _synth_fn(self, emotion, speech_act):
        """How one sentence is synthesised: with the brain's designators (a say
        call) or with CORA's mood name mapped onto the voice (streamed text)."""
        if speech_act:
            return lambda s, b: uv.synth_delivery(s, emotion, speech_act)
        return lambda s, b: uv.synth_with_fallback(s, emotion, b)

    def get_audio(self, text, emotion='neutral', speech_act=None):
        """All sentences synthesised and concatenated (no playback)."""
        if not self.is_initialized and not self.initialize():
            return None
        parts = []
        sents, _ = self._sentences(text)
        synth_fn = self._synth_fn(emotion, speech_act)
        for s, bang in sents:
            try:
                parts.append(synth_fn(s, bang))
            except (uv.VoiceRefused, uv.VoiceDown) as e:
                self.last_error = str(e)
                print(f"[TTS] {e}")
        return np.concatenate(parts) if parts else None

    # -- playback -----------------------------------------------------------
    def _play(self, audio: np.ndarray) -> bool:
        """Play float32 mono at 24 kHz, feeding the waveform. Returns False if stopped."""
        sd = self.sd
        audio = (audio * self.volume).astype('float32') if self.volume != 1.0 else audio
        if WAVEFORM_AVAILABLE and _audio_buffer_singleton is not None:
            with _audio_buffer_singleton.data_lock:
                _audio_buffer_singleton.data = audio
                _audio_buffer_singleton.start_time = time.time()
                _audio_buffer_singleton.sample_rate = self.SAMPLE_RATE
                _audio_buffer_singleton.active = True
        position = [0]
        stopped = [False]

        def callback(outdata, frames, time_info, status):
            if _stop_event.is_set():
                stopped[0] = True
                outdata.fill(0)
                raise sd.CallbackStop()
            start = position[0]
            end = start + frames
            if end <= len(audio):
                outdata[:, 0] = audio[start:end]
            elif start < len(audio):
                valid = len(audio) - start
                outdata[:valid, 0] = audio[start:]
                outdata[valid:, 0] = 0
            else:
                outdata.fill(0)
                raise sd.CallbackStop()
            if WAVEFORM_AVAILABLE and _audio_buffer_singleton is not None:
                try:
                    chunk = audio[start:end] if end <= len(audio) else audio[start:]
                    with _audio_buffer_singleton.data_lock:
                        _audio_buffer_singleton.current_chunk = np.array(chunk, dtype=np.float32, copy=True)
                        _audio_buffer_singleton.chunk_time = time.time()
                        _audio_buffer_singleton.active = True
                except Exception:
                    pass
            position[0] = end

        with sd.OutputStream(samplerate=self.SAMPLE_RATE, channels=1, callback=callback, blocksize=1024):
            while position[0] < len(audio) and not stopped[0] and not _stop_event.is_set():
                sd.sleep(10)
        if WAVEFORM_AVAILABLE and _audio_buffer_singleton is not None:
            with _audio_buffer_singleton.data_lock:
                _audio_buffer_singleton.active = False
                _audio_buffer_singleton.data = None
                _audio_buffer_singleton.current_chunk = None
        return not stopped[0]

    def speak(self, text, emotion='neutral', speech_act=None) -> bool:
        """Speak a reply: sentences are synthesised one ahead of playback so
        the first audio starts fast and a refused sentence costs one sentence,
        not the whole reply."""
        if not self.is_initialized and not self.initialize():
            return False
        sents, clean = self._sentences(text)
        if not sents:
            return True
        _stop_event.clear()
        _speaking.set()
        _update_speech_text(clean)
        spoke_any = False
        synth_fn = self._synth_fn(emotion, speech_act)
        from concurrent.futures import ThreadPoolExecutor
        try:
            if not uv.take_turn():
                self.last_error = "voice busy (another process holds the turn)"
                print(f"[TTS] {self.last_error}")
                return False
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    futures = [pool.submit(synth_fn, s, b) for s, b in sents[:1]]
                    for i, (s, b) in enumerate(sents):
                        if _stop_event.is_set():
                            break
                        if i + 1 < len(sents):
                            futures.append(pool.submit(synth_fn, sents[i + 1][0], sents[i + 1][1]))
                        try:
                            audio = futures[i].result()
                        except uv.VoiceDown as e:
                            self.last_error = str(e)
                            print(f"[TTS] {e}")
                            self.is_initialized = False
                            break
                        except uv.VoiceRefused as e:
                            self.last_error = f"refused: {e}"
                            print(f"[TTS] line refused by her voice: {e} :: {s[:240]}")
                            continue
                        if not self._play(audio):
                            break
                        spoke_any = True
                        if TTS_MUTEX_AVAILABLE:
                            try:
                                _mutex_heartbeat()
                            except Exception:
                                pass
            finally:
                uv.give_turn()
        except Exception as e:
            self.last_error = str(e)
            print(f"[!] unity-voice TTS error: {e}")
        finally:
            _speaking.clear()
            _clear_speech_text()
        return spoke_any


# Compatibility names: code that still says KokoroTTS gets her voice.
KokoroTTS = UnityVoiceTTS
Pyttsx3TTS = UnityVoiceTTS


def get_tts_engine(config=None):
    """The one engine. Returns None when the sidecar cannot be reached."""
    engine = UnityVoiceTTS()
    return engine if engine.initialize() else None


def speak(text, emotion='neutral', config=None, speech_act=None) -> bool:
    """Blocking speak."""
    engine = get_tts_engine(config)
    return engine.speak(text, emotion, speech_act) if engine else False


def list_voices():
    """Only one voice exists: hers."""
    return [{'id': 'unity-voice-v2', 'name': 'Unity voice v2 (A2 low warm alto)', 'languages': ['en-US']}]


# --------------------------------------------------------------------------- queue
class TTSQueue:
    """Queue-based TTS for non-blocking speech (one background thread)."""

    def __init__(self, config=None, use_mutex: bool = True, check_presence: Optional[bool] = None):
        self.config = config or {}
        self.queue: "queue.Queue" = queue.Queue()
        self.engine: Optional[UnityVoiceTTS] = None
        self.is_running = False
        self._thread = None
        self._stop_event = threading.Event()
        self.on_speak_start: Optional[Callable] = None
        self.on_speak_end: Optional[Callable] = None
        self.use_mutex = use_mutex and TTS_MUTEX_AVAILABLE
        self._mutex = get_mutex("CORA") if self.use_mutex else None
        if check_presence is None:
            check_presence = bool(_tts_config().get('presence_gate', False))
        self.check_presence = check_presence and PRESENCE_AVAILABLE
        self._init_failures = 0

    def start(self):
        if self.is_running:
            return
        self.engine = UnityVoiceTTS()
        if not self.engine.initialize():
            print("[!] TTS engine failed to initialize (unity-voice-v2 sidecar down)")
        if self.check_presence:
            try:
                get_monitor(start=True)
            except Exception:
                pass
        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._process_queue, name='tts-queue', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self.is_running = False
        self.queue.put(None)
        if self._thread:
            self._thread.join(timeout=2.0)

    def speak(self, text: str, emotion: str = 'neutral', priority: int = 5, skip_presence: bool = False,
              speech_act: Optional[str] = None):
        if not self.is_running:
            self.start()
        self.queue.put({'text': text, 'emotion': emotion, 'priority': priority, 'skip_presence': skip_presence,
                        'speech_act': speech_act})

    def speak_now(self, text: str, emotion: str = 'neutral', speech_act: Optional[str] = None):
        """Interrupt the current line and speak this next."""
        stop_speaking()
        self.speak(text, emotion, priority=1, skip_presence=True, speech_act=speech_act)

    def clear(self):
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

    def pending_count(self) -> int:
        return self.queue.qsize()

    def _is_user_present(self) -> bool:
        if not self.check_presence:
            return True
        try:
            return user_is_present()
        except Exception:
            return True

    def _process_queue(self):
        while not self._stop_event.is_set():
            try:
                item = self.queue.get(timeout=0.5)
                if item is None:
                    continue
                text = item.get('text', '')
                emotion = item.get('emotion', 'neutral')
                speech_act = item.get('speech_act')
                if not item.get('skip_presence') and not self._is_user_present():
                    print(f"[TTS] User not present, skipping: {text[:30]}...")
                    continue
                if not text:
                    continue
                if self.engine is None or not self.engine.is_initialized:
                    if self.engine is None:
                        self.engine = UnityVoiceTTS()
                    if not self.engine.initialize():
                        self._init_failures += 1
                        if self._init_failures <= 3:
                            print(f"[TTS] dropped (voice down): {text[:40]}")
                        continue
                    self._init_failures = 0
                if self.on_speak_start:
                    try:
                        self.on_speak_start(text)
                    except Exception:
                        pass
                if self.use_mutex and self._mutex:
                    with self._mutex.locked(timeout=10) as acquired:
                        if acquired:
                            self.engine.speak(text, emotion, speech_act)
                        else:
                            print(f"[TTS] Skipped (someone else speaking): {text[:30]}...")
                else:
                    self.engine.speak(text, emotion, speech_act)
                if self.on_speak_end:
                    try:
                        self.on_speak_end(text)
                    except Exception:
                        pass
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[!] TTS queue error: {e}")


_tts_queue: Optional[TTSQueue] = None
_tts_queue_lock = threading.Lock()


def get_tts_queue(config=None) -> TTSQueue:
    """Get or create the global TTS queue."""
    global _tts_queue
    if _tts_queue is None:
        with _tts_queue_lock:
            if _tts_queue is None:
                _tts_queue = TTSQueue(config)
                _tts_queue.start()
    return _tts_queue


def queue_speak(text: str, emotion: str = 'neutral', priority: int = 5, speech_act: Optional[str] = None):
    """Queue text for speaking (non-blocking). speech_act = the brain's act designator
    (statement, wh_question, ...) when the line came from a say() call."""
    get_tts_queue().speak(text, emotion, priority, speech_act=speech_act)


def speak_async(text: str, emotion: str = 'neutral', speech_act: Optional[str] = None):
    """Non-blocking speak (what cli_popup and the handlers always imported)."""
    queue_speak(text, emotion, speech_act=speech_act)


def speak_interrupt(text: str, emotion: str = 'neutral', speech_act: Optional[str] = None):
    """Clear the queue and speak immediately."""
    get_tts_queue().speak_now(text, emotion, speech_act)


def voice_status() -> dict:
    """For boot checks: is her voice reachable, which URL, last error."""
    up = uv.is_up()
    return {'engine': 'unity-voice-v2', 'url': uv.VOICE_URL, 'up': up,
            'model_dir': str(uv.MODEL_DIR), 'model_present': uv.MODEL_DIR.exists()}
