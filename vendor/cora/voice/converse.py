#!/usr/bin/env python3
"""
C.O.R.A Conversation Mode
Hands-free back-and-forth: wake word, then an open conversation until a stop
word, with CORA's own speech filtered out of the microphone.

Everything is local since 2026-10-14:
  - recognition: voice.stt.SpeechRecognizer (faster-whisper / Vosk)
  - thinking:    ai.dispatcher (model + tools) unless an ai_callback is given
  - speaking:    voice.tts (unity-voice-v2) unless a speak_callback is given
  - echo filter: voice.echo_filter (the one the rest of CORA uses)
"""

import sys
import time
import threading
from pathlib import Path
from typing import Optional, Callable, List
from dataclasses import dataclass

PROJECT_DIR = Path(__file__).parent.parent

# Stop words to end conversation mode
STOP_WORDS = ["goodbye", "bye", "that's all", "thats all", "stop listening", "exit conversation", "end conversation"]


@dataclass
class ConversationConfig:
    """Configuration for conversation mode."""
    wake_word: str = "cora"
    stop_words: List[str] = None
    silence_timeout: float = 2.0      # seconds of silence that ends a phrase
    phrase_timeout: float = 10.0      # max phrase length
    listen_timeout: float = 6.0       # seconds to wait for speech to start
    idle_exit_turns: int = 4          # consecutive silent listens before leaving active mode
    echo_filter_duration: float = 3.0

    def __post_init__(self):
        if self.stop_words is None:
            self.stop_words = STOP_WORDS


# The echo filter CORA uses everywhere (kept importable from here for old callers)
try:
    from voice.echo_filter import EchoFilter  # noqa: F401
except Exception:  # pragma: no cover - minimal fallback
    class EchoFilter:
        def __init__(self, filter_duration: float = 3.0):
            self.filter_duration = filter_duration
            self._until = 0.0
            self._lock = threading.Lock()

        def start_speaking(self, duration: float = None, text: str = None):
            with self._lock:
                self._until = time.time() + (duration or self.filter_duration)

        def stop_speaking(self):
            with self._lock:
                self._until = 0.0

        def is_speaking(self) -> bool:
            with self._lock:
                return time.time() < self._until

        def should_process(self, text: str) -> bool:
            return not self.is_speaking()


class ConversationLoop:
    """Full conversation loop with CORA (local STT -> dispatcher -> her voice)."""

    def __init__(
        self,
        config: Optional[ConversationConfig] = None,
        ai_callback: Optional[Callable[[str], str]] = None,
        speak_callback: Optional[Callable[[str], None]] = None,
        on_wake: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        on_heard: Optional[Callable[[str], None]] = None,
    ):
        self.config = config or ConversationConfig()
        self.ai_callback = ai_callback
        self.speak_callback = speak_callback
        self.on_wake = on_wake
        self.on_stop = on_stop
        self.on_heard = on_heard
        try:
            from voice.echo_filter import get_echo_filter
            self.echo_filter = get_echo_filter(filter_duration=self.config.echo_filter_duration)
        except Exception:
            self.echo_filter = EchoFilter(self.config.echo_filter_duration)
        self._running = False
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._recognizer = None

    # -- speech -------------------------------------------------------------
    def _init_speech(self) -> bool:
        try:
            from voice.stt import SpeechRecognizer
            self._recognizer = SpeechRecognizer()
            return self._recognizer.initialize()
        except Exception as e:
            print(f"[!] Speech init error: {e}")
            return False

    def _listen_once(self) -> Optional[str]:
        try:
            text = self._recognizer.listen_once(timeout=self.config.listen_timeout,
                                                phrase_limit=self.config.phrase_timeout)
            return text.lower().strip() if text else None
        except Exception as e:
            print(f"[!] Listen error: {e}")
            return None

    def _is_wake_word(self, text: str) -> bool:
        try:
            from voice.stt import _fuzzy_wake_match
            return _fuzzy_wake_match(text, self.config.wake_word.lower())
        except Exception:
            return self.config.wake_word.lower() in text.lower()

    def _is_stop_word(self, text: str) -> bool:
        t = text.lower()
        return any(stop in t for stop in self.config.stop_words)

    # -- thinking / speaking --------------------------------------------------
    def _process_input(self, text: str) -> Optional[str]:
        if not self.echo_filter.should_process(text):
            return None
        if self.ai_callback:
            return self.ai_callback(text)
        from ai.dispatcher import get_dispatcher
        # speak=True: the dispatcher streams sentences to her voice itself
        r = get_dispatcher().handle(text, speak=self.speak_callback is None)
        if r.error:
            return f"Something broke: {r.error}"
        return r.text if self.speak_callback else None   # already spoken

    def _speak(self, text: str):
        if not text:
            return
        duration = max(1.0, len(text.split()) * 0.4)
        try:
            self.echo_filter.start_speaking(duration=duration, text=text)
        except TypeError:
            self.echo_filter.start_speaking(duration)
        try:
            if self.speak_callback:
                self.speak_callback(text)
            else:
                from voice.tts import speak
                speak(text)
        finally:
            self.echo_filter.stop_speaking()

    def _wait_for_voice_idle(self):
        """Don't listen while she is still talking (dispatcher-streamed speech)."""
        try:
            from voice.tts import is_speaking, get_tts_queue
            q = get_tts_queue()
            deadline = time.time() + 120
            while (is_speaking() or q.pending_count() > 0) and time.time() < deadline and self._running:
                time.sleep(0.1)
        except Exception:
            pass

    # -- loop ---------------------------------------------------------------
    def _conversation_loop(self):
        print(f"[CONVERSE] Listening for wake word: '{self.config.wake_word}'")
        print(f"[CONVERSE] Say {self.config.stop_words[:3]} to end")
        silent_turns = 0
        while self._running:
            self._wait_for_voice_idle()
            text = self._listen_once()
            if text is None:
                if self._active:
                    silent_turns += 1
                    if silent_turns >= self.config.idle_exit_turns:
                        self._active = False
                        silent_turns = 0
                        print("[CONVERSE] back to wake-word mode")
                continue
            silent_turns = 0
            print(f"[HEARD] {text}")
            if self.on_heard:
                try:
                    self.on_heard(text)
                except Exception:
                    pass
            if not self.echo_filter.should_process(text):
                print("[ECHO] Filtered (CORA speaking)")
                continue

            if self._is_stop_word(text):
                self._speak("Alright, catch you later.")
                self._active = False
                if self.on_stop:
                    self.on_stop()
                continue

            if not self._active:
                if self._is_wake_word(text):
                    self._active = True
                    if self.on_wake:
                        self.on_wake()
                    # command after the wake word?
                    low = text.lower()
                    idx = low.find(self.config.wake_word.lower())
                    command = text[idx + len(self.config.wake_word):].strip(" ,.?") if idx >= 0 else ''
                    if command and len(command.split()) >= 2:
                        self._speak_reply(self._process_input(command))
                    else:
                        self._speak("Yeah?")
                continue

            self._speak_reply(self._process_input(text))

    def _speak_reply(self, response: Optional[str]):
        if response:
            self._speak(response)

    def start(self) -> bool:
        if self._running:
            return True
        if not self._init_speech():
            return False
        self._running = True
        self._thread = threading.Thread(target=self._conversation_loop, daemon=True, name='converse')
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        self._active = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def is_running(self) -> bool:
        return self._running

    def is_active(self) -> bool:
        """True while in an open conversation (after the wake word)."""
        return self._active


def quick_converse(ai_callback: Optional[Callable[[str], str]] = None,
                   speak_callback: Optional[Callable[[str], None]] = None) -> ConversationLoop:
    """Start conversation mode with CORA's defaults (dispatcher + her voice)."""
    loop = ConversationLoop(ai_callback=ai_callback, speak_callback=speak_callback)
    loop.start()
    return loop


if __name__ == "__main__":
    print("=== CONVERSATION MODE TEST ===")
    sys.path.insert(0, str(PROJECT_DIR))
    loop = ConversationLoop(on_wake=lambda: print("[WAKE] Activated!"),
                            on_stop=lambda: print("[STOP] Conversation ended"))
    if loop.start():
        print("Say 'Cora' to start, 'goodbye' to stop")
        try:
            while loop.is_running():
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
            loop.stop()
    else:
        print("Failed to start")
