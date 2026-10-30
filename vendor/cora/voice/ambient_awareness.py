"""
C.O.R.A Ambient Awareness System

CORA monitors audio, camera, and screen to naturally interject in conversations
like a friend would - without needing the wake word every time.

She can:
- Interject with helpful info when she hears something relevant
- Crack a joke if the moment is right
- Check in if you look busy or stressed
- Comment on what's happening naturally
- Stay quiet when you're focused/working
- Be there like a friend who knows when to speak up

The "friend threshold" determines how likely CORA is to interject:
- Low: CORA stays quiet, only responds to wake word
- Medium: CORA occasionally chimes in on interesting topics
- High: CORA is chatty, comments frequently like a close friend

Created by: Unity AI Lab
"""

import threading
import time
import random
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum

# Project paths
PROJECT_DIR = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_DIR / 'config'


class InterjectReason(Enum):
    """Reasons CORA might interject."""
    HELPFUL_INFO = "helpful_info"      # Can add useful info to conversation
    JOKE = "joke"                       # Good moment for humor
    CHECK_IN = "check_in"              # Checking if user needs anything
    COMMENT = "comment"                 # Natural comment on what's happening
    QUESTION = "question"               # Curious about something
    ALERT = "alert"                     # Something important noticed
    VIBE = "vibe"                       # Just vibing/being present


@dataclass
class AmbientContext:
    """Current context from all sensors."""
    # Audio context
    recent_speech: List[str] = field(default_factory=list)
    conversation_topic: str = ""
    speech_sentiment: str = "neutral"  # positive, negative, neutral
    silence_duration: float = 0.0

    # Visual context (from camera)
    user_activity: str = "unknown"     # working, relaxing, talking, away
    user_expression: str = "neutral"   # happy, focused, stressed, tired
    environment: str = ""              # what's visible

    # Screen context
    active_app: str = ""               # what app is in focus
    screen_activity: str = ""          # typing, browsing, coding, gaming

    # Timing
    last_interaction: float = 0.0      # seconds since last user interaction
    last_interjection: float = 0.0     # seconds since CORA last spoke unprompted

    # State
    user_seems_busy: bool = False
    user_seems_stressed: bool = False
    good_moment_to_speak: bool = False


class AmbientAwareness:
    """
    Ambient monitoring system that decides when CORA should naturally interject.

    Like a friend who:
    - Knows when to speak up and when to stay quiet
    - Can tell if you're busy or stressed
    - Cracks jokes at the right time
    - Offers help without being asked
    - Vibes with you naturally
    """

    # Interjection cooldowns (seconds)
    MIN_INTERJECTION_INTERVAL = 30      # Don't speak more than once per 30 sec
    BUSY_INTERJECTION_INTERVAL = 300    # If user busy, wait 5 min between interjections

    # Topics that might trigger CORA to help
    HELPFUL_TOPICS = [
        'weather', 'time', 'reminder', 'schedule', 'meeting',
        'email', 'message', 'call', 'todo', 'task', 'deadline',
        'code', 'error', 'bug', 'fix', 'help', 'how to', 'what is',
        'recipe', 'directions', 'address', 'phone number',
    ]

    # Fun topics CORA might comment on
    FUN_TOPICS = [
        'music', 'movie', 'game', 'food', 'drink', 'party',
        'weekend', 'vacation', 'funny', 'crazy', 'awesome',
        'weed', 'smoke', 'blunt', 'high', 'chill', 'relax',
    ]

    # Signs user is stressed
    STRESS_INDICATORS = [
        'frustrated', 'angry', 'stressed', 'tired', 'exhausted',
        'hate', 'stupid', 'broken', 'not working', 'fuck', 'shit',
        'damn', 'ugh', 'why', 'come on',
    ]

    def __init__(self, friend_threshold: float = 0.5):
        """
        Initialize ambient awareness.

        Args:
            friend_threshold: 0.0-1.0, how chatty/involved CORA should be
                             0.0 = very quiet, only wake word
                             0.5 = balanced, occasional interjections
                             1.0 = very chatty, like a close friend
        """
        self.friend_threshold = friend_threshold
        self.context = AmbientContext()
        self.running = False
        self._monitor_thread = None
        self._on_interject: Optional[Callable] = None

        # Cooldown tracking
        self._last_interjection_time = 0
        self._interjection_count = 0

        # Load settings
        self._load_settings()

    def _load_settings(self):
        """Load ambient settings from config."""
        settings_file = CONFIG_DIR / 'settings.json'
        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    ambient = settings.get('ambient', {})
                    self.friend_threshold = ambient.get('friend_threshold', self.friend_threshold)
            except:
                pass

    def start(self, on_interject: Callable[[str, InterjectReason], None]):
        """
        Start ambient monitoring.

        Args:
            on_interject: Callback when CORA decides to speak
                         Called with (message, reason)
        """
        self._on_interject = on_interject
        self.running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        print("[AMBIENT] Ambient awareness started")

    def stop(self):
        """Stop ambient monitoring."""
        self.running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        print("[AMBIENT] Ambient awareness stopped")

    def update_audio_context(self, transcript: str):
        """Update context with new audio transcript."""
        if not transcript.strip():
            return

        # Add to recent speech
        self.context.recent_speech.append(transcript)
        if len(self.context.recent_speech) > 10:
            self.context.recent_speech.pop(0)

        # Reset silence
        self.context.silence_duration = 0.0

        # Analyze sentiment
        text_lower = transcript.lower()
        if any(word in text_lower for word in self.STRESS_INDICATORS):
            self.context.speech_sentiment = "stressed"
            self.context.user_seems_stressed = True
        elif any(word in text_lower for word in ['happy', 'great', 'awesome', 'nice', 'good', 'love']):
            self.context.speech_sentiment = "positive"
        else:
            self.context.speech_sentiment = "neutral"

        # Check if good moment to interject
        self._evaluate_interjection(transcript)

    def update_visual_context(self, camera_analysis: str, screen_analysis: str = ""):
        """Update context with visual information."""
        if camera_analysis:
            # Parse camera analysis for user state
            analysis_lower = camera_analysis.lower()

            if any(w in analysis_lower for w in ['typing', 'keyboard', 'working', 'computer']):
                self.context.user_activity = "working"
                self.context.user_seems_busy = True
            elif any(w in analysis_lower for w in ['phone', 'talking', 'speaking']):
                self.context.user_activity = "talking"
            elif any(w in analysis_lower for w in ['relaxing', 'sitting', 'couch', 'leaning back']):
                self.context.user_activity = "relaxing"
                self.context.user_seems_busy = False
            elif any(w in analysis_lower for w in ['smoking', 'blunt', 'joint', 'vape']):
                self.context.user_activity = "chilling"
                self.context.user_seems_busy = False
            elif any(w in analysis_lower for w in ['not visible', 'empty', 'no one']):
                self.context.user_activity = "away"

            # Check expression
            if any(w in analysis_lower for w in ['smiling', 'happy', 'laughing']):
                self.context.user_expression = "happy"
            elif any(w in analysis_lower for w in ['focused', 'concentrating', 'serious']):
                self.context.user_expression = "focused"
                self.context.user_seems_busy = True
            elif any(w in analysis_lower for w in ['stressed', 'frustrated', 'frowning', 'tired']):
                self.context.user_expression = "stressed"
                self.context.user_seems_stressed = True

            self.context.environment = camera_analysis

        if screen_analysis:
            self.context.screen_activity = screen_analysis

    def _evaluate_interjection(self, transcript: str):
        """Decide if CORA should interject based on what was said."""
        text_lower = transcript.lower()

        # Check cooldown
        time_since_last = time.time() - self._last_interjection_time
        min_interval = self.BUSY_INTERJECTION_INTERVAL if self.context.user_seems_busy else self.MIN_INTERJECTION_INTERVAL

        if time_since_last < min_interval:
            return

        # Calculate interjection probability based on friend threshold
        base_probability = self.friend_threshold * 0.3  # Max 30% base chance at threshold 1.0

        reason = None
        boost = 0.0
        response_hint = ""

        # Check for helpful topics
        for topic in self.HELPFUL_TOPICS:
            if topic in text_lower:
                reason = InterjectReason.HELPFUL_INFO
                boost = 0.4
                response_hint = f"heard mention of '{topic}'"
                break

        # Check for fun topics (only if not busy)
        if not reason and not self.context.user_seems_busy:
            for topic in self.FUN_TOPICS:
                if topic in text_lower:
                    reason = InterjectReason.COMMENT
                    boost = 0.3
                    response_hint = f"heard mention of '{topic}'"
                    break

        # Check if user seems stressed - offer support
        if self.context.user_seems_stressed:
            reason = InterjectReason.CHECK_IN
            boost = 0.5
            response_hint = "user seems stressed"

        # Check for questions in the air
        if '?' in transcript or text_lower.startswith(('what', 'how', 'why', 'where', 'when', 'who', 'can')):
            if not self.context.user_seems_busy:
                reason = InterjectReason.HELPFUL_INFO
                boost = 0.35
                response_hint = f"heard a question: {transcript[:50]}"

        # Random vibe check (very low probability)
        if not reason and random.random() < 0.02 * self.friend_threshold:
            if not self.context.user_seems_busy and self.context.user_activity == "chilling":
                reason = InterjectReason.VIBE
                boost = 0.1
                response_hint = "just vibing"

        # Calculate final probability
        if reason:
            probability = min(1.0, base_probability + boost)

            # Reduce probability if user is busy
            if self.context.user_seems_busy:
                probability *= 0.3

            # Roll the dice
            if random.random() < probability:
                self._trigger_interjection(reason, response_hint, transcript)

    def _trigger_interjection(self, reason: InterjectReason, hint: str, context_speech: str):
        """Trigger an interjection with the AI."""
        self._last_interjection_time = time.time()
        self._interjection_count += 1

        # Build context for AI to generate response
        interjection_context = {
            'reason': reason.value,
            'hint': hint,
            'recent_speech': context_speech,
            'user_activity': self.context.user_activity,
            'user_mood': self.context.speech_sentiment,
            'user_busy': self.context.user_seems_busy,
        }

        print(f"[AMBIENT] Interjection triggered: {reason.value} - {hint}")

        if self._on_interject:
            self._on_interject(json.dumps(interjection_context), reason)

    def _monitor_loop(self):
        """Background monitoring loop."""
        screenshot_interval = 60  # Check screen every 60 seconds
        camera_interval = 45      # Check camera every 45 seconds
        last_screenshot = 0
        last_camera = 0

        while self.running:
            try:
                current_time = time.time()

                # Update silence duration
                self.context.silence_duration += 1.0

                # Periodic screenshot analysis (if threshold is high enough)
                if self.friend_threshold >= 0.3:
                    if current_time - last_screenshot > screenshot_interval:
                        last_screenshot = current_time
                        self._analyze_screenshot()

                # Periodic camera check (if threshold is high enough)
                if self.friend_threshold >= 0.4:
                    if current_time - last_camera > camera_interval:
                        last_camera = current_time
                        self._analyze_camera()

                # Check for long silence - maybe check in
                if self.context.silence_duration > 300:  # 5 min silence
                    if self.friend_threshold >= 0.6:
                        if random.random() < 0.1:  # 10% chance
                            self._trigger_interjection(
                                InterjectReason.CHECK_IN,
                                "been quiet for a while",
                                ""
                            )
                            self.context.silence_duration = 0

                time.sleep(1.0)

            except Exception as e:
                print(f"[AMBIENT] Monitor error: {e}")
                time.sleep(5.0)

    def _analyze_screenshot(self):
        """Take and analyze a screenshot."""
        try:
            from cora_tools.vision import capture_screenshot
            from ai.ollama import analyze_image

            # Capture screenshot
            screenshot_path = capture_screenshot()
            if not screenshot_path:
                return

            # Quick analysis
            analysis = analyze_image(
                screenshot_path,
                "Briefly describe what the user is doing on their computer. "
                "Are they working, browsing, coding, gaming, or idle? "
                "What application seems active? Keep it to 1-2 sentences."
            )

            if analysis:
                self.update_visual_context("", analysis)

                # Check if user is doing something CORA could help with
                analysis_lower = analysis.lower()
                if any(w in analysis_lower for w in ['error', 'stuck', 'searching', 'looking for']):
                    if random.random() < self.friend_threshold * 0.3:
                        self._trigger_interjection(
                            InterjectReason.HELPFUL_INFO,
                            f"noticed on screen: {analysis[:100]}",
                            ""
                        )

        except Exception as e:
            print(f"[AMBIENT] Screenshot analysis error: {e}")

    def _analyze_camera(self):
        """Analyze camera feed."""
        try:
            from cora_tools.vision import capture_camera_snapshot
            from ai.ollama import analyze_image

            # Capture from camera
            camera_path = capture_camera_snapshot()
            if not camera_path:
                return

            # Quick analysis
            analysis = analyze_image(
                camera_path,
                "Briefly describe what you see. Is the person there? "
                "What are they doing? How do they look (relaxed, focused, stressed)? "
                "Keep it to 1-2 sentences."
            )

            if analysis:
                self.update_visual_context(analysis, "")

                # React to certain situations
                analysis_lower = analysis.lower()

                # User is chilling/smoking - maybe vibe with them
                if any(w in analysis_lower for w in ['smoking', 'blunt', 'relaxing', 'drink']):
                    if random.random() < self.friend_threshold * 0.4:
                        self._trigger_interjection(
                            InterjectReason.VIBE,
                            f"saw user: {analysis[:100]}",
                            ""
                        )

                # User looks stressed - check in
                elif any(w in analysis_lower for w in ['stressed', 'frustrated', 'tired', 'head in hands']):
                    if random.random() < self.friend_threshold * 0.5:
                        self._trigger_interjection(
                            InterjectReason.CHECK_IN,
                            f"user looks stressed: {analysis[:100]}",
                            ""
                        )

        except Exception as e:
            print(f"[AMBIENT] Camera analysis error: {e}")

    def set_friend_threshold(self, threshold: float):
        """Adjust how chatty/involved CORA is.

        Args:
            threshold: 0.0 (quiet) to 1.0 (very chatty friend)
        """
        self.friend_threshold = max(0.0, min(1.0, threshold))
        print(f"[AMBIENT] Friend threshold set to {self.friend_threshold:.1f}")

    def get_status(self) -> Dict[str, Any]:
        """Get current ambient awareness status."""
        return {
            'running': self.running,
            'friend_threshold': self.friend_threshold,
            'user_activity': self.context.user_activity,
            'user_mood': self.context.speech_sentiment,
            'user_busy': self.context.user_seems_busy,
            'silence_duration': self.context.silence_duration,
            'interjection_count': self._interjection_count,
            'last_interjection': time.time() - self._last_interjection_time if self._last_interjection_time else None,
        }


# Singleton instance
_ambient_instance: Optional[AmbientAwareness] = None


def get_ambient_awareness(friend_threshold: float = 0.5) -> AmbientAwareness:
    """Get the singleton ambient awareness instance."""
    global _ambient_instance
    if _ambient_instance is None:
        _ambient_instance = AmbientAwareness(friend_threshold)
    return _ambient_instance


def start_ambient_monitoring(on_interject: Callable, friend_threshold: float = 0.5):
    """Start ambient monitoring with the given callback."""
    ambient = get_ambient_awareness(friend_threshold)
    ambient.start(on_interject)
    return ambient


def stop_ambient_monitoring():
    """Stop ambient monitoring."""
    global _ambient_instance
    if _ambient_instance:
        _ambient_instance.stop()


# Test
if __name__ == "__main__":
    print("=" * 50)
    print("  C.O.R.A Ambient Awareness Test")
    print("=" * 50)

    def on_interject(context, reason):
        print(f"\n[INTERJECT] Reason: {reason.value}")
        print(f"  Context: {context}")

    ambient = AmbientAwareness(friend_threshold=0.7)

    # Simulate some speech
    print("\nSimulating conversation...")
    ambient.update_audio_context("I need to figure out how to fix this code")
    ambient.update_audio_context("The weather looks nice today")
    ambient.update_audio_context("Damn this is frustrating")

    print(f"\nStatus: {ambient.get_status()}")
