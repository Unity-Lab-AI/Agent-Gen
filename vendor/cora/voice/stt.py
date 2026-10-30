"""
C.O.R.A Speech-to-Text Module

Local speech recognition. Since 2026-10-14 the primary engine is
faster-whisper (CUDA on the RTX card, int8 on CPU); Vosk remains as a
fallback engine when faster-whisper is not installed.

Public API (unchanged for every caller):
    load_stt_settings()                      -> dict
    SpeechRecognizer(model_path=None, sample_rate=16000)
        .initialize() .recognize(bytes) .start_listening(cb) .stop_listening()
        .listen_once(timeout, phrase_limit)
    WakeWordDetector(wake_word=None, sensitivity=None)
        .start(on_wake) .stop()
        class-level transcript buffer + callbacks (ambient awareness)
    transcribe_file(path) / list_microphones()
New:
    stt_status() -> {'engine', 'installed', 'model_found', 'status', 'device'}

Wake word: the detector runs the continuous recognizer and fuzzy-matches the
wake word on the transcript stream (so "Cora", "Kora", "core-a" all trigger),
and the same stream feeds ambient awareness. If openWakeWord is installed AND
a custom keyword model exists at models/wakeword/<wake_word>.onnx (config
stt.wake_model_path), that dedicated KWS model is used instead and the
recognizer is only started after the wake.
"""

import json
import os
import queue
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent.parent

_WAKE_VARIANTS = {'cora': ['cora', 'kora', 'korra', 'quora', 'cora.', 'core a', 'cor a', 'cor-a', 'koura', 'corah']}


# --------------------------------------------------------------------------- settings
def load_stt_settings() -> dict:
    """STT settings from config/config.json `stt` (falls back to legacy
    config/settings.json `voice` keys)."""
    defaults = {
        'stt_enabled': True,
        'engine': 'faster-whisper',
        'whisper_model': 'base.en',
        'device': 'auto',
        'stt_sensitivity': 0.5,
        'wake_word': 'cora',
        'wake_engine': 'auto',
        'wake_model_path': None,
        'model_path': None,
        'push_to_talk_key': 'ctrl+shift+space',
    }
    out = dict(defaults)
    try:
        with open(PROJECT_DIR / 'config' / 'config.json', 'r', encoding='utf-8') as f:
            stt = json.load(f).get('stt') or {}
        out['stt_enabled'] = bool(stt.get('enabled', out['stt_enabled']))
        for k in ('engine', 'whisper_model', 'device', 'wake_word', 'wake_engine', 'wake_model_path', 'model_path'):
            if stt.get(k) is not None:
                out[k] = stt[k]
        if stt.get('sensitivity') is not None:
            out['stt_sensitivity'] = float(stt['sensitivity'])
    except Exception:
        pass
    try:
        with open(PROJECT_DIR / 'config' / 'settings.json', 'r', encoding='utf-8') as f:
            voice = json.load(f).get('voice', {}) or {}
        if voice.get('push_to_talk_key'):
            out['push_to_talk_key'] = voice['push_to_talk_key']
    except Exception:
        pass
    out['wake_word'] = str(out['wake_word'] or 'cora').lower()
    return out


_dlls_registered = False


def _register_nvidia_dlls():
    """Make the CUDA 12 runtime DLLs from the `nvidia-*-cu12` pip wheels
    loadable (ctranslate2 on Windows needs cublas64_12 / cudnn in the DLL
    search path; the system toolkit may be a different CUDA major)."""
    global _dlls_registered
    if _dlls_registered or os.name != 'nt':
        return
    _dlls_registered = True
    try:
        import site
        roots = []
        for sp in site.getsitepackages() + [site.getusersitepackages()]:
            roots.append(Path(sp) / 'nvidia')
        for root in roots:
            if not root.exists():
                continue
            for sub in root.iterdir():
                for binp in (sub / 'bin', sub / 'lib'):
                    if binp.exists():
                        try:
                            os.add_dll_directory(str(binp))
                        except Exception:
                            pass
                        os.environ['PATH'] = str(binp) + os.pathsep + os.environ.get('PATH', '')
    except Exception:
        pass


def _cuda_available() -> bool:
    try:
        _register_nvidia_dlls()
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def stt_status() -> Dict:
    """Which engine will be used and whether it is ready (no audio opened)."""
    s = load_stt_settings()
    engine = s['engine']
    if engine in ('faster-whisper', 'auto'):
        try:
            import faster_whisper  # noqa: F401
            dev = 'cuda' if (s['device'] in ('auto', 'cuda') and _cuda_available()) else 'cpu'
            return {'engine': 'faster-whisper', 'installed': True, 'model_found': True,
                    'status': 'ready', 'device': dev, 'model': s['whisper_model']}
        except ImportError:
            if engine == 'faster-whisper':
                engine = 'vosk'
    try:
        import vosk  # noqa: F401
        mp = s.get('model_path')
        found = bool(mp and Path(mp).exists()) or (PROJECT_DIR / 'models' / 'vosk-model-small-en-us-0.15').exists()
        return {'engine': 'vosk', 'installed': True, 'model_found': found,
                'status': 'ready' if found else 'partial', 'device': 'cpu'}
    except ImportError:
        return {'engine': None, 'installed': False, 'model_found': False, 'status': 'unavailable', 'device': None}


# --------------------------------------------------------------------------- audio helpers
def _rms(int16_bytes: bytes) -> float:
    if not int16_bytes:
        return 0.0
    a = np.frombuffer(int16_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(a * a))) if a.size else 0.0


def _to_float32(int16_bytes: bytes) -> np.ndarray:
    return np.frombuffer(int16_bytes, dtype=np.int16).astype(np.float32) / 32768.0


class _BoundedQueue(queue.Queue):
    """Queue that drops the oldest item instead of growing without bound."""

    def put(self, item, block=True, timeout=None):
        while True:
            try:
                return super().put(item, block=False)
            except queue.Full:
                try:
                    self.get_nowait()
                except queue.Empty:
                    pass


# --------------------------------------------------------------------------- recognizer
# One loaded WhisperModel per (name, device, compute) for the whole process.
_WHISPER_CACHE: Dict[tuple, object] = {}
_WHISPER_LOCK = threading.Lock()


class SpeechRecognizer:
    """Speech recognition: faster-whisper (default) or Vosk. Instances are cheap:
    the Whisper weights are loaded once per process and shared."""

    SILENCE_RMS = 0.012          # below this is silence (quiet room ~0.003-0.008)
    SPEECH_RMS = 0.02            # above this counts as speech
    END_SILENCE_S = 0.8          # silence after speech that ends a phrase

    def __init__(self, model_path=None, sample_rate=16000, engine: Optional[str] = None):
        s = load_stt_settings()
        self.settings = s
        self.engine_name = engine or s['engine'] or 'faster-whisper'
        self.model_path = model_path or s.get('model_path')
        self.sample_rate = sample_rate
        self.recognizer = None          # vosk KaldiRecognizer
        self.model = None               # vosk Model or faster-whisper WhisperModel
        self.audio_queue: queue.Queue = _BoundedQueue(maxsize=64)
        self.is_listening = False
        self._thread = None
        self._stop = threading.Event()
        self.device = 'cpu'
        self._lock = threading.Lock()
        self.sensitivity = float(s.get('stt_sensitivity', 0.5) or 0.5)
        # sensitivity 0..1 -> speech threshold 0.035..0.012
        self.SPEECH_RMS = max(0.008, 0.035 - 0.023 * self.sensitivity)
        self.SILENCE_RMS = self.SPEECH_RMS * 0.6

    # -- init ------------------------------------------------------------------
    def initialize(self) -> bool:
        if self.model is not None:
            return True
        with self._lock:
            if self.model is not None:
                return True
            if self.engine_name in ('faster-whisper', 'auto'):
                if self._init_whisper():
                    return True
                if self.engine_name == 'faster-whisper':
                    print("[STT] faster-whisper unavailable, trying vosk")
            return self._init_vosk()

    def _init_whisper(self) -> bool:
        try:
            _register_nvidia_dlls()
            from faster_whisper import WhisperModel
        except ImportError:
            return False
        name = self.settings.get('whisper_model') or 'base.en'
        want = self.settings.get('device', 'auto')
        attempts = []
        if want in ('auto', 'cuda') and _cuda_available():
            attempts.append(('cuda', 'int8_float16'))
        attempts.append(('cpu', 'int8'))
        with _WHISPER_LOCK:
            for device, compute in attempts:
                key = (name, device, compute)
                cached = _WHISPER_CACHE.get(key)
                if cached is not None:
                    # the wake-word detector, the command recognizer, converse mode
                    # and the GUI all share ONE set of weights on the GPU
                    self.model, self.device, self.engine_name = cached, device, 'faster-whisper'
                    return True
                try:
                    model = WhisperModel(name, device=device, compute_type=compute)
                    # a tiny real inference proves the runtime libraries load (cuBLAS/cuDNN)
                    list(model.transcribe(np.zeros(16000, dtype=np.float32), language='en', beam_size=1)[0])
                    _WHISPER_CACHE[key] = model
                    self.model = model
                    self.device = device
                    self.engine_name = 'faster-whisper'
                    print(f"[STT] faster-whisper {name} on {device}")
                    return True
                except Exception as e:
                    print(f"[STT] faster-whisper on {device} failed: {str(e)[:120]}")
                    self.model = None
        return False

    def _init_vosk(self) -> bool:
        try:
            from vosk import Model, KaldiRecognizer, SetLogLevel
            SetLogLevel(-1)
            mp = self.model_path
            local = PROJECT_DIR / 'models' / 'vosk-model-small-en-us-0.15'
            if not mp and local.exists():
                mp = str(local)
            self.model = Model(mp) if mp else Model(lang="en-us")
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
            self.engine_name = 'vosk'
            self.device = 'cpu'
            return True
        except ImportError:
            print("[!] Neither faster-whisper nor vosk is installed")
            return False
        except Exception as e:
            print(f"[!] Failed to initialize STT: {e}")
            return False

    # -- transcription ---------------------------------------------------------
    def transcribe_audio(self, int16_bytes: bytes) -> str:
        """Transcribe a complete utterance (int16 mono at self.sample_rate)."""
        if not int16_bytes or self.model is None:
            return ""
        if self.engine_name == 'faster-whisper':
            try:
                audio = _to_float32(int16_bytes)
                if audio.size < self.sample_rate * 0.3:
                    return ""
                segments, _ = self.model.transcribe(
                    audio, language='en', beam_size=1, vad_filter=True,
                    condition_on_previous_text=False, without_timestamps=True)
                return " ".join(seg.text.strip() for seg in segments).strip()
            except Exception as e:
                print(f"[STT] transcribe error: {e}")
                return ""
        # vosk
        try:
            self.recognizer.Reset()
            self.recognizer.AcceptWaveform(int16_bytes)
            return json.loads(self.recognizer.FinalResult()).get('text', '')
        except Exception as e:
            print(f"[STT] vosk error: {e}")
            return ""

    def recognize(self, audio_data: bytes) -> str:
        """Legacy streaming API: feed a chunk, get text when a phrase completes
        (vosk) or the chunk's text (whisper). Prefer start_listening()."""
        if self.model is None:
            return ""
        if self.engine_name == 'vosk':
            if self.recognizer.AcceptWaveform(audio_data):
                return json.loads(self.recognizer.Result()).get('text', '')
            return json.loads(self.recognizer.PartialResult()).get('partial', '')
        return self.transcribe_audio(audio_data)

    # -- listening -------------------------------------------------------------
    def start_listening(self, callback: Callable[[str], None]):
        """Continuous listening: phrases are segmented by silence and passed
        to callback(text) as they complete."""
        if self.is_listening:
            return
        if not self.initialize():
            print("[!] STT not initialized")
            return
        self.is_listening = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._listen_loop, args=(callback,), daemon=True, name='stt-listen')
        self._thread.start()

    def stop_listening(self):
        self.is_listening = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _open_stream(self, blocksize: int):
        import sounddevice as sd

        def cb(indata, frames, time_info, status):
            self.audio_queue.put(bytes(indata))
        return sd.RawInputStream(samplerate=self.sample_rate, blocksize=blocksize, dtype='int16',
                                 channels=1, callback=cb)

    def _listen_loop(self, callback):
        """Energy-gated phrase segmentation -> transcribe -> callback."""
        try:
            with self._open_stream(blocksize=1600):      # 100 ms blocks
                phrase: List[bytes] = []
                in_speech = False
                silence_blocks = 0
                max_blocks = int(12 / 0.1)               # hard cap 12 s per phrase
                end_blocks = int(self.END_SILENCE_S / 0.1)
                while self.is_listening and not self._stop.is_set():
                    try:
                        data = self.audio_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    level = _rms(data)
                    if in_speech:
                        phrase.append(data)
                        if level < self.SILENCE_RMS:
                            silence_blocks += 1
                        else:
                            silence_blocks = 0
                        if silence_blocks >= end_blocks or len(phrase) >= max_blocks:
                            text = self.transcribe_audio(b''.join(phrase))
                            phrase, in_speech, silence_blocks = [], False, 0
                            if text.strip():
                                try:
                                    callback(text)
                                except Exception as e:
                                    print(f"[STT] callback error: {e}")
                    else:
                        if level >= self.SPEECH_RMS:
                            in_speech = True
                            phrase = [data]
                            silence_blocks = 0
        except ImportError:
            print("[!] sounddevice not installed. Run: pip install sounddevice")
        except Exception as e:
            print(f"[!] Listening error: {e}")
        finally:
            self.is_listening = False

    def listen_once(self, timeout=5, phrase_limit=10) -> str:
        """Listen for a single phrase and return its text.

        Waits up to `timeout` seconds for speech to start, then records until
        END_SILENCE_S of silence or `phrase_limit` seconds.
        """
        if not self.initialize():
            return ""
        try:
            local_q: "queue.Queue[bytes]" = _BoundedQueue(maxsize=400)
            import sounddevice as sd

            def cb(indata, frames, time_info, status):
                local_q.put(bytes(indata))

            phrase: List[bytes] = []
            started = None
            silence = 0
            t0 = time.time()
            with sd.RawInputStream(samplerate=self.sample_rate, blocksize=1600, dtype='int16',
                                   channels=1, callback=cb):
                while True:
                    now = time.time()
                    if started is None and now - t0 > timeout:
                        break
                    if started is not None and now - started > phrase_limit:
                        break
                    try:
                        data = local_q.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    level = _rms(data)
                    if started is None:
                        if level >= self.SPEECH_RMS:
                            started = now
                            phrase.append(data)
                        continue
                    phrase.append(data)
                    if level < self.SILENCE_RMS:
                        silence += 1
                        if silence >= int(self.END_SILENCE_S / 0.1):
                            break
                    else:
                        silence = 0
            if not phrase:
                return ""
            return self.transcribe_audio(b''.join(phrase))
        except ImportError:
            print("[!] sounddevice not installed")
            return ""
        except Exception as e:
            print(f"[!] Listen error: {e}")
            return ""


# --------------------------------------------------------------------------- wake word
def _fuzzy_wake_match(text: str, wake_word: str) -> bool:
    import difflib
    t = text.lower()
    variants = set(_WAKE_VARIANTS.get(wake_word, [])) | {wake_word}
    for v in variants:
        if v in t:
            return True
    for tok in ''.join(ch if ch.isalnum() else ' ' for ch in t).split():
        if difflib.SequenceMatcher(None, tok, wake_word).ratio() >= 0.8:
            return True
    return False


class WakeWordDetector:
    """Detect the wake word on the live transcript stream (or via a custom
    openWakeWord model when one is configured)."""

    _recent_transcripts: List[Dict] = []
    _max_transcripts = 20
    _transcript_lock = threading.Lock()
    _transcript_callbacks: List[Callable] = []
    _callback_lock = threading.Lock()

    def __init__(self, wake_word=None, sensitivity=None):
        settings = load_stt_settings()
        self.wake_word = (wake_word or settings['wake_word']).lower()
        self.sensitivity = sensitivity if sensitivity is not None else settings['stt_sensitivity']
        self.recognizer = SpeechRecognizer()
        self.settings = settings
        self._oww = None
        self._oww_thread = None
        self._running = False
        self.mode = 'transcript'

    # -- openWakeWord (only with a custom model file) -----------------------
    def _try_openwakeword(self):
        if self.settings.get('wake_engine') not in ('auto', 'openwakeword'):
            return None
        mp = self.settings.get('wake_model_path') or str(PROJECT_DIR / 'models' / 'wakeword' / f'{self.wake_word}.onnx')
        if not Path(mp).exists():
            return None
        try:
            from openwakeword.model import Model as OWWModel
            return OWWModel(wakeword_models=[mp], inference_framework='onnx')
        except Exception as e:
            print(f"[WAKE] openWakeWord unavailable: {e}")
            return None

    def start(self, on_wake: Callable[[], None]):
        """Start listening for the wake word."""
        if self._running:
            return
        if not self.recognizer.initialize():
            print("[!] Cannot start wake word detection")
            return
        self._running = True
        self._oww = self._try_openwakeword()
        if self._oww is not None:
            self.mode = 'openwakeword'
            self._oww_thread = threading.Thread(target=self._oww_loop, args=(on_wake,), daemon=True, name='wake-oww')
            self._oww_thread.start()
            print(f"[WAKE] openWakeWord model active for '{self.wake_word}'")
            return

        def check_wake(text):
            text_lower = text.lower().strip()
            if text_lower and not _fuzzy_wake_match(text_lower, self.wake_word):
                with WakeWordDetector._transcript_lock:
                    WakeWordDetector._recent_transcripts.append({'text': text, 'time': time.time()})
                    if len(WakeWordDetector._recent_transcripts) > WakeWordDetector._max_transcripts:
                        WakeWordDetector._recent_transcripts.pop(0)
                WakeWordDetector._notify_transcript_callbacks(text)
            if _fuzzy_wake_match(text_lower, self.wake_word):
                WakeWordDetector.last_wake_time = time.time()
                on_wake()

        self.recognizer.start_listening(check_wake)
        print(f"[WAKE] transcript wake detection active for '{self.wake_word}' ({self.recognizer.engine_name})")

    def _oww_loop(self, on_wake):
        try:
            import sounddevice as sd
            threshold = 0.5 + (0.5 - float(self.sensitivity)) * 0.6   # sensitivity 1 -> 0.2, 0 -> 0.8
            last = 0.0
            with sd.RawInputStream(samplerate=16000, blocksize=1280, dtype='int16', channels=1) as stream:
                while self._running:
                    data, _ = stream.read(1280)
                    frame = np.frombuffer(bytes(data), dtype=np.int16)
                    scores = self._oww.predict(frame)
                    if scores and max(scores.values()) >= threshold and time.time() - last > 2.0:
                        last = time.time()
                        WakeWordDetector.last_wake_time = time.time()
                        on_wake()
        except Exception as e:
            print(f"[WAKE] openWakeWord loop error: {e}")

    def stop(self):
        self._running = False
        self.recognizer.stop_listening()

    @classmethod
    def get_recent_transcripts(cls, seconds: float = 30.0) -> list:
        cutoff = time.time() - seconds
        with cls._transcript_lock:
            return [t['text'] for t in cls._recent_transcripts if t['time'] > cutoff]

    @classmethod
    def get_last_heard(cls) -> str:
        transcripts = cls.get_recent_transcripts(seconds=30.0)
        if transcripts:
            seen = set()
            unique = []
            for t in transcripts:
                t_clean = t.strip().lower()
                if t_clean and t_clean not in seen:
                    seen.add(t_clean)
                    unique.append(t.strip())
            if unique:
                return ' '.join(unique[-5:])
        return ""

    @classmethod
    def clear_transcripts(cls):
        with cls._transcript_lock:
            cls._recent_transcripts.clear()

    @classmethod
    def add_transcript_callback(cls, callback):
        with cls._callback_lock:
            cls._transcript_callbacks.append(callback)

    @classmethod
    def remove_transcript_callback(cls, callback):
        with cls._callback_lock:
            if callback in cls._transcript_callbacks:
                cls._transcript_callbacks.remove(callback)

    @classmethod
    def _notify_transcript_callbacks(cls, text: str):
        with cls._callback_lock:
            callbacks = list(cls._transcript_callbacks)
        for callback in callbacks:
            try:
                callback(text)
            except Exception as e:
                print(f"[!] Transcript callback error: {e}")


# --------------------------------------------------------------------------- utilities
def transcribe_file(audio_file, model_path=None) -> str:
    """Transcribe an audio file (WAV) with the configured engine."""
    rec = SpeechRecognizer(model_path=model_path)
    if not rec.initialize():
        return ""
    try:
        if rec.engine_name == 'faster-whisper':
            segments, _ = rec.model.transcribe(str(audio_file), language='en', beam_size=1, vad_filter=True)
            return " ".join(s.text.strip() for s in segments).strip()
        import wave
        wf = wave.open(str(audio_file), "rb")
        from vosk import KaldiRecognizer
        r = KaldiRecognizer(rec.model, wf.getframerate())
        results = []
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            if r.AcceptWaveform(data):
                results.append(json.loads(r.Result()).get('text', ''))
        results.append(json.loads(r.FinalResult()).get('text', ''))
        return ' '.join(x for x in results if x).strip()
    except Exception as e:
        print(f"[!] Transcription error: {e}")
        return ""


def list_microphones():
    """List available microphones."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        return [{'id': i, 'name': d['name'], 'channels': d['max_input_channels'],
                 'sample_rate': d['default_samplerate']}
                for i, d in enumerate(devices) if d['max_input_channels'] > 0]
    except ImportError:
        return []


if __name__ == '__main__':
    print("status:", stt_status())
    print("mics:", [m['name'] for m in list_microphones()][:3])
    r = SpeechRecognizer()
    print("init:", r.initialize(), r.engine_name, r.device)
    print("say something (5 s)...")
    print("heard:", repr(r.listen_once(timeout=5, phrase_limit=8)))
