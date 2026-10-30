#!/usr/bin/env python3
"""
C.O.R.A TTS Handler
Threaded text-to-speech handler for non-blocking UI.

Since 2026-10-14 this is a thin adapter over voice.tts (unity-voice-v2 queue)
so every caller that used TTSHandler / TTSManager / speak_async shares the one
voice, the one queue and the one waveform. No engine code lives here.
"""

from typing import Optional, Callable


class TTSHandler:
    """Threaded TTS handler for non-blocking speech (adapter over voice.tts)."""

    def __init__(self, on_start: Optional[Callable] = None, on_complete: Optional[Callable] = None):
        self.on_start = on_start
        self.on_complete = on_complete
        self._running = False
        self._config = {"volume": 1.0, "engine": "unity-voice-v2"}

    def start(self):
        """Start (the shared queue starts lazily on first speak)."""
        from voice import tts
        q = tts.get_tts_queue()
        if self.on_start:
            q.on_speak_start = lambda _t: self.on_start()
        if self.on_complete:
            q.on_speak_end = lambda _t: self.on_complete()
        self._running = True

    def stop(self):
        """Stop speaking; the shared queue keeps running for other callers."""
        from voice import tts
        tts.stop_speaking()
        self._running = False

    def speak(self, text: str, emotion: str = "neutral"):
        """Queue text to be spoken."""
        if not self._running:
            self.start()
        from voice import tts
        tts.queue_speak(text, emotion)

    def configure(self, rate: int = None, volume: float = None, engine: str = None):
        """Only volume is meaningful now (applied by the engine from config)."""
        if volume is not None:
            self._config["volume"] = volume
            from voice import tts
            q = tts.get_tts_queue()
            if q.engine:
                q.engine.volume = float(volume)


class TTSManager:
    """Singleton manager for TTS operations."""

    _instance: Optional["TTSManager"] = None
    _handler: Optional[TTSHandler] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._handler is None:
            self._handler = TTSHandler()
            self._handler.start()

    def speak(self, text: str, emotion: str = "neutral"):
        if self._handler:
            self._handler.speak(text, emotion)

    def configure(self, **kwargs):
        if self._handler:
            self._handler.configure(**kwargs)

    def shutdown(self):
        if self._handler:
            self._handler.stop()


def speak_async(text: str, emotion: str = "neutral"):
    """Speak text asynchronously using the shared voice queue."""
    TTSManager().speak(text, emotion)
