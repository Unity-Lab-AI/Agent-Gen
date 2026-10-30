#!/usr/bin/env python3
"""
C.O.R.A Wake Word Detection
Always-listening detector for "Cora", "Hey Cora", "Yo Cora".

Since 2026-10-14 this module is a thin layer over voice.stt: the recognizer
(faster-whisper, Vosk fallback) streams phrases, the wake word is fuzzy-matched
on them, and an optional custom openWakeWord model (models/wakeword/cora.onnx)
is used when present. Nothing here reaches a cloud service.

API kept for existing callers:
    WakeWordResult, WakeWordDetector(wake_words, model_path, on_wake, on_command, sample_rate)
        .start() -> bool, .stop(), .is_running()
    SimpleWakeWordDetector  (same interface, now also local)
    create_wake_detector(**kwargs)
"""

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from voice import stt as _stt

# Default wake words
WAKE_WORDS = ["cora", "hey cora", "yo cora", "okay cora", "hi cora"]

# Kept for callers that import it (vosk fallback model location)
MODEL_PATH = Path(__file__).parent.parent / 'models' / 'vosk-model-small-en-us-0.15'


@dataclass
class WakeWordResult:
    """Result of wake word detection."""
    detected: bool
    word: str
    confidence: float
    full_text: str
    timestamp: float


class WakeWordDetector:
    """Always-listening wake word detector (transcript-matched or openWakeWord)."""

    def __init__(
        self,
        wake_words: Optional[List[str]] = None,
        model_path: Optional[Path] = None,
        on_wake: Optional[Callable[[WakeWordResult], None]] = None,
        on_command: Optional[Callable[[str], None]] = None,
        sample_rate: int = 16000
    ):
        self.wake_words = [w.lower() for w in (wake_words or WAKE_WORDS)]
        self.model_path = model_path or MODEL_PATH
        self.on_wake = on_wake
        self.on_command = on_command
        self.sample_rate = sample_rate
        self._running = False
        base = self.wake_words[0].split()[-1] if self.wake_words else 'cora'
        self._detector = _stt.WakeWordDetector(wake_word=base)
        self._command_recognizer: Optional[_stt.SpeechRecognizer] = None
        self._last_wake = 0.0

    def _detect_wake_word(self, text: str) -> Optional[str]:
        text_lower = text.lower().strip()
        for wake_word in self.wake_words:
            if wake_word in text_lower:
                return wake_word
        base = self.wake_words[0].split()[-1] if self.wake_words else 'cora'
        return base if _stt._fuzzy_wake_match(text_lower, base) else None

    def _handle_wake(self, wake_word: str, full_text: str):
        if time.time() - self._last_wake < 2.0:
            return
        self._last_wake = time.time()
        result = WakeWordResult(detected=True, word=wake_word, confidence=0.9,
                                full_text=full_text, timestamp=time.time())
        print(f"[WAKE] Detected: '{wake_word}' in '{full_text}'")
        self._play_wake_sound()
        if self.on_wake:
            try:
                self.on_wake(result)
            except Exception as e:
                print(f"[WAKE] on_wake error: {e}")
        if self.on_command:
            command = self._listen_for_command()
            if command:
                try:
                    self.on_command(command)
                except Exception as e:
                    print(f"[WAKE] on_command error: {e}")

    def _listen_for_command(self, timeout: float = 5.0) -> Optional[str]:
        """Listen for the command that follows the wake word."""
        if self._command_recognizer is None:
            self._command_recognizer = _stt.SpeechRecognizer()
        text = self._command_recognizer.listen_once(timeout=timeout, phrase_limit=10)
        return text or None

    def _play_wake_sound(self):
        try:
            import winsound
            winsound.Beep(800, 100)
        except Exception:
            pass

    def start(self) -> bool:
        """Start listening for wake words."""
        if self._running:
            return True

        def on_wake():
            heard = _stt.WakeWordDetector.get_last_heard() or self.wake_words[0]
            self._handle_wake(self._detect_wake_word(heard) or self.wake_words[0], heard)

        self._detector.start(on_wake)
        self._running = self._detector._running
        return self._running

    def stop(self):
        self._running = False
        self._detector.stop()

    def is_running(self) -> bool:
        return self._running


class SimpleWakeWordDetector(WakeWordDetector):
    """Kept for compatibility: same local detector (no cloud recognition)."""

    def __init__(self, wake_words: Optional[List[str]] = None, on_wake: Optional[Callable] = None,
                 on_command: Optional[Callable[[str], None]] = None):
        super().__init__(wake_words=wake_words, on_wake=on_wake, on_command=on_command)


def create_wake_detector(**kwargs) -> WakeWordDetector:
    """Create the wake word detector."""
    return WakeWordDetector(**kwargs)


if __name__ == "__main__":
    print("=== WAKE WORD DETECTOR TEST ===")

    def on_wake(result):
        print(f"Wake word detected: {result}")

    def on_command(cmd):
        print(f"Command: {cmd}")

    detector = create_wake_detector(on_wake=on_wake, on_command=on_command)
    if detector.start():
        print("Listening... Press Ctrl+C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
            detector.stop()
    else:
        print("Failed to start detector")
