#!/usr/bin/env python3
"""
C.O.R.A Echo Filter Module
Filters out CORA's own speech from microphone input.

Per ARCHITECTURE.md v1.0.0:
- Separate module for echo filtering
- Prevents TTS from being picked up by STT
- Thread-safe implementation

Created by: Unity AI Lab
Date: 2025-12-23
"""

import time
import threading
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class EchoFilterConfig:
    """Configuration for echo filtering."""
    filter_duration: float = 3.0  # Default seconds to filter after TTS
    grace_period: float = 0.5  # Extra buffer after expected speech ends
    min_confidence: float = 0.7  # Minimum confidence to accept input
    blacklist_phrases: List[str] = field(default_factory=list)  # Known TTS outputs to reject


class EchoFilter:
    """
    Filters out CORA's own speech from microphone input.

    When CORA speaks via TTS, this filter prevents the microphone
    from picking up that speech and feeding it back as user input.

    Usage:
        filter = EchoFilter(filter_duration=3.0)

        # When TTS starts speaking:
        filter.start_speaking(duration=2.5)

        # When checking if we should process input:
        if filter.should_process(recognized_text):
            # Process as user input
        else:
            # Ignore - likely echo

        # When TTS finishes (optional, clears early):
        filter.stop_speaking()
    """

    def __init__(
        self,
        filter_duration: float = 3.0,
        config: Optional[EchoFilterConfig] = None
    ):
        """Initialize echo filter.

        Args:
            filter_duration: Seconds to filter after TTS starts
            config: Optional configuration object
        """
        if config:
            self.config = config
            self.filter_duration = config.filter_duration
        else:
            self.config = EchoFilterConfig(filter_duration=filter_duration)
            self.filter_duration = filter_duration

        self._speaking_until = 0.0
        self._last_spoken_text: Optional[str] = None
        self._lock = threading.Lock()
        self._speech_history: List[str] = []
        self._max_history = 10

    def start_speaking(self, duration: float = None, text: str = None):
        """Mark that TTS is starting.

        Args:
            duration: Expected speech duration (or use default filter_duration)
            text: The text being spoken (for enhanced echo detection)
        """
        with self._lock:
            effective_duration = duration or self.filter_duration
            self._speaking_until = time.time() + effective_duration + self.config.grace_period

            if text:
                self._last_spoken_text = text.lower().strip()
                self._speech_history.append(self._last_spoken_text)
                # Trim history
                if len(self._speech_history) > self._max_history:
                    self._speech_history = self._speech_history[-self._max_history:]

    def stop_speaking(self):
        """Mark that TTS has stopped."""
        with self._lock:
            self._speaking_until = 0.0

    def is_speaking(self) -> bool:
        """Check if CORA is currently speaking.

        Returns:
            True if speaking (should filter input)
        """
        with self._lock:
            return time.time() < self._speaking_until

    def time_until_clear(self) -> float:
        """Get seconds until filter clears.

        Returns:
            Seconds remaining, or 0.0 if already clear
        """
        with self._lock:
            remaining = self._speaking_until - time.time()
            return max(0.0, remaining)

    def _is_echo_text(self, text: str) -> bool:
        """Check if text appears to be an echo of recent TTS.

        Args:
            text: Text to check

        Returns:
            True if text is likely an echo
        """
        if not text:
            return False

        text_lower = text.lower().strip()

        # Check against last spoken text
        if self._last_spoken_text:
            # Exact match
            if text_lower == self._last_spoken_text:
                return True
            # Partial match (text is subset of spoken)
            if text_lower in self._last_spoken_text:
                return True
            # Spoken is subset of text (might include wake word)
            if self._last_spoken_text in text_lower:
                return True

        # Check against speech history
        for spoken in self._speech_history:
            if text_lower == spoken or text_lower in spoken:
                return True

        # Check against blacklist phrases
        for phrase in self.config.blacklist_phrases:
            if phrase.lower() in text_lower:
                return True

        return False

    def should_process(self, text: str, confidence: float = 1.0) -> bool:
        """Check if input should be processed.

        Args:
            text: Recognized text
            confidence: Recognition confidence (0.0 to 1.0)

        Returns:
            True if should process (not echo)
        """
        # Filter during active speaking period
        if self.is_speaking():
            return False

        # Filter low confidence recognitions
        if confidence < self.config.min_confidence:
            return False

        # Check for echo patterns
        with self._lock:
            if self._is_echo_text(text):
                return False

        return True

    def add_blacklist_phrase(self, phrase: str):
        """Add a phrase to the echo blacklist.

        Args:
            phrase: Phrase that should always be filtered
        """
        with self._lock:
            if phrase.lower() not in [p.lower() for p in self.config.blacklist_phrases]:
                self.config.blacklist_phrases.append(phrase)

    def clear_history(self):
        """Clear speech history."""
        with self._lock:
            self._speech_history.clear()
            self._last_spoken_text = None

    def get_status(self) -> dict:
        """Get current filter status.

        Returns:
            Dict with current status information
        """
        with self._lock:
            return {
                'is_speaking': time.time() < self._speaking_until,
                'time_remaining': max(0.0, self._speaking_until - time.time()),
                'last_spoken': self._last_spoken_text,
                'history_count': len(self._speech_history),
                'blacklist_count': len(self.config.blacklist_phrases)
            }


class AdaptiveEchoFilter(EchoFilter):
    """
    Echo filter that learns and adapts to the environment.

    Extends EchoFilter with:
    - Automatic blacklist learning
    - Dynamic filter duration based on speech length
    - Environment noise detection
    """

    def __init__(
        self,
        filter_duration: float = 3.0,
        config: Optional[EchoFilterConfig] = None,
        learn_echoes: bool = True
    ):
        super().__init__(filter_duration, config)
        self.learn_echoes = learn_echoes
        self._echo_candidates: List[str] = []
        self._confirmed_echoes: List[str] = []

    def mark_as_echo(self, text: str):
        """Mark text as a confirmed echo.

        Args:
            text: Text that was identified as echo
        """
        if self.learn_echoes and text:
            with self._lock:
                text_lower = text.lower().strip()
                if text_lower not in self._confirmed_echoes:
                    self._confirmed_echoes.append(text_lower)
                    # Also add to blacklist
                    if text_lower not in [p.lower() for p in self.config.blacklist_phrases]:
                        self.config.blacklist_phrases.append(text_lower)

    def start_speaking(self, duration: float = None, text: str = None):
        """Start speaking with adaptive duration.

        Args:
            duration: Expected speech duration
            text: Text being spoken
        """
        # Calculate adaptive duration based on text length
        if text and not duration:
            # Rough estimate: ~100 chars per 10 seconds of speech
            word_count = len(text.split())
            estimated_duration = max(1.0, word_count * 0.4)
            duration = min(estimated_duration, 15.0)  # Cap at 15 seconds

        super().start_speaking(duration, text)


# Convenience function for getting a global filter instance
_global_filter: Optional[EchoFilter] = None


def get_echo_filter(filter_duration: float = 3.0) -> EchoFilter:
    """Get or create the global echo filter instance.

    Args:
        filter_duration: Filter duration for new instance

    Returns:
        Global EchoFilter instance
    """
    global _global_filter
    if _global_filter is None:
        _global_filter = EchoFilter(filter_duration)
    return _global_filter


def reset_echo_filter():
    """Reset the global echo filter."""
    global _global_filter
    _global_filter = None


# Module test
if __name__ == '__main__':
    import time

    print("=== ECHO FILTER TEST ===\n")

    # Create filter
    filter = EchoFilter(filter_duration=2.0)

    # Test basic functionality
    print("1. Initial state:")
    print(f"   is_speaking: {filter.is_speaking()}")
    print(f"   should_process('hello'): {filter.should_process('hello')}")

    # Start speaking
    print("\n2. After start_speaking(duration=2.0, text='Hello world'):")
    filter.start_speaking(duration=2.0, text="Hello world")
    print(f"   is_speaking: {filter.is_speaking()}")
    print(f"   should_process('hello world'): {filter.should_process('hello world')}")
    print(f"   should_process('different text'): {filter.should_process('different text')}")
    print(f"   time_until_clear: {filter.time_until_clear():.2f}s")

    # Wait for filter to clear
    print("\n3. Waiting 2.5 seconds...")
    time.sleep(2.5)
    print(f"   is_speaking: {filter.is_speaking()}")
    print(f"   should_process('hello'): {filter.should_process('hello')}")

    # Test echo detection
    print("\n4. Echo detection after speaking 'test message':")
    filter.start_speaking(duration=0.5, text="test message")
    filter.stop_speaking()  # Simulate immediate stop
    print(f"   should_process('test message'): {filter.should_process('test message')}")
    print(f"   should_process('something else'): {filter.should_process('something else')}")

    # Test adaptive filter
    print("\n5. Adaptive filter test:")
    adaptive = AdaptiveEchoFilter(learn_echoes=True)
    adaptive.start_speaking(text="This is a longer test sentence for duration estimation")
    print(f"   Auto-calculated duration: {adaptive.time_until_clear():.2f}s")

    # Status
    print("\n6. Filter status:")
    status = filter.get_status()
    for key, value in status.items():
        print(f"   {key}: {value}")

    print("\n=== TEST COMPLETE ===")
