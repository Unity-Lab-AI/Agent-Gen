"""
C.O.R.A Voice Emotion Module

Analyze text for emotional content to drive TTS inflection.
Per ARCHITECTURE.md: Analyze text before speaking, build TTS instruction.

Includes EmotionalState - CORA has persistent moods that decay over time.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ============ EMOTIONAL STATE MACHINE ============

@dataclass
class EmotionalState:
    """CORA's persistent emotional state with decay over time."""

    # Current mood values (-1.0 to 1.0)
    happiness: float = 0.0
    energy: float = 0.0
    patience: float = 0.5  # Start with some patience
    engagement: float = 0.0

    # Decay rate per second
    decay_rate: float = 0.01

    # Last update timestamp
    last_update: float = field(default_factory=time.time)

    # Mood history for tracking trends
    mood_history: List[Dict] = field(default_factory=list)

    def update(self):
        """Apply time-based decay to emotions."""
        now = time.time()
        elapsed = now - self.last_update
        decay = self.decay_rate * elapsed

        # Decay towards neutral (0)
        self.happiness = self._decay_towards(self.happiness, 0, decay)
        self.energy = self._decay_towards(self.energy, 0, decay)
        self.patience = self._decay_towards(self.patience, 0.5, decay)  # Patience recovers
        self.engagement = self._decay_towards(self.engagement, 0, decay)

        self.last_update = now

    def _decay_towards(self, value: float, target: float, amount: float) -> float:
        """Decay a value towards a target."""
        if value > target:
            return max(target, value - amount)
        elif value < target:
            return min(target, value + amount)
        return value

    def apply_event(self, event_type: str, intensity: float = 0.3):
        """Apply an emotional event that shifts the mood.

        Args:
            event_type: Type of event (task_completed, error, greeting, frustration, etc.)
            intensity: How much to shift (0.0-1.0)
        """
        self.update()  # Apply decay first

        event_effects = {
            'task_completed': {'happiness': 0.3, 'energy': 0.1, 'engagement': 0.2},
            'error': {'happiness': -0.2, 'patience': -0.1},
            'greeting': {'happiness': 0.2, 'engagement': 0.3},
            'frustration': {'patience': -0.3, 'happiness': -0.1},
            'compliment': {'happiness': 0.4, 'engagement': 0.2},
            'insult': {'happiness': -0.3, 'patience': -0.2},
            'busy': {'energy': -0.2, 'patience': -0.1},
            'idle': {'patience': 0.1, 'energy': -0.1},
            'help_given': {'happiness': 0.2, 'engagement': 0.1},
            'repetitive': {'patience': -0.2, 'engagement': -0.1},
        }

        effects = event_effects.get(event_type, {})
        for attr, change in effects.items():
            current = getattr(self, attr)
            new_val = max(-1.0, min(1.0, current + change * intensity))
            setattr(self, attr, new_val)

        # Log to history
        self.mood_history.append({
            'time': time.time(),
            'event': event_type,
            'mood': self.get_mood()
        })
        if len(self.mood_history) > 100:
            self.mood_history = self.mood_history[-50:]

    def get_mood(self) -> str:
        """Get current mood as a simple label.

        Returns:
            str: Current mood (happy, annoyed, tired, neutral, etc.)
        """
        self.update()

        # Check combined states for mood
        if self.happiness > 0.5 and self.energy > 0.3:
            return 'excited'
        elif self.happiness > 0.3:
            return 'happy'
        elif self.happiness < -0.3 and self.patience < 0.2:
            return 'annoyed'
        elif self.patience < 0:
            return 'frustrated'
        elif self.energy < -0.3:
            return 'tired'
        elif self.engagement > 0.5:
            return 'engaged'
        elif self.engagement < -0.3:
            return 'bored'
        return 'neutral'

    def get_response_modifier(self) -> Dict:
        """Get modifiers for response generation based on mood.

        Returns:
            dict: Modifiers for temperature, style, etc.
        """
        mood = self.get_mood()
        modifiers = {
            'excited': {'temperature': 0.8, 'style': 'enthusiastic', 'exclamations': True},
            'happy': {'temperature': 0.7, 'style': 'warm', 'exclamations': False},
            'annoyed': {'temperature': 0.6, 'style': 'curt', 'exclamations': False},
            'frustrated': {'temperature': 0.5, 'style': 'blunt', 'exclamations': False},
            'tired': {'temperature': 0.6, 'style': 'brief', 'exclamations': False},
            'engaged': {'temperature': 0.7, 'style': 'detailed', 'exclamations': False},
            'bored': {'temperature': 0.6, 'style': 'minimal', 'exclamations': False},
            'neutral': {'temperature': 0.7, 'style': 'normal', 'exclamations': False},
        }
        return modifiers.get(mood, modifiers['neutral'])


# Global emotional state instance
_cora_mood = EmotionalState()


def get_mood() -> str:
    """Get CORA's current mood."""
    return _cora_mood.get_mood()


def apply_event(event_type: str, intensity: float = 0.3):
    """Apply an emotional event to CORA's state."""
    _cora_mood.apply_event(event_type, intensity)


def get_response_modifier() -> Dict:
    """Get response modifiers based on CORA's mood."""
    return _cora_mood.get_response_modifier()


def get_emotional_state() -> EmotionalState:
    """Get the full emotional state object."""
    return _cora_mood


# ============ TEXT EMOTION DETECTION ============

# Emotion keywords for detection
EMOTION_KEYWORDS = {
    'excited': ['!', 'great', 'awesome', 'excellent', 'amazing', 'congrats',
                'fantastic', 'wonderful', 'perfect', 'brilliant', 'yay', 'woohoo'],
    'concerned': ['sorry', 'unfortunately', 'failed', 'error', 'problem', 'issue',
                  'wrong', 'broken', 'warning', 'careful', 'danger', 'bad'],
    'satisfied': ['done', 'complete', 'finished', 'success', 'nice', 'good',
                  'accomplished', 'achieved', 'completed', 'saved'],
    'urgent': ['remember', "don't forget", 'deadline', 'overdue', 'urgent',
               'immediately', 'now', 'asap', 'critical', 'important'],
    'questioning': ['?', 'what', 'how', 'why', 'when', 'where', 'which'],
    'warm': ['hello', 'hi', 'hey', 'welcome', 'greetings', 'morning', 'evening'],
    'gentle': ['goodbye', 'bye', 'see you', 'later', 'goodnight', 'farewell'],
    'annoyed': ['ugh', 'again', 'really', 'seriously', 'whatever', 'fine'],
    'playful': ['haha', 'lol', 'hehe', 'joke', 'funny', 'kidding', 'tease'],
}


def detect_emotion(text):
    """Detect primary emotion from text.

    Args:
        text: The text to analyze

    Returns:
        str: Detected emotion ('excited', 'concerned', etc.) or 'neutral'
    """
    if not text:
        return 'neutral'

    text_lower = text.lower()

    # Check each emotion category
    for emotion, keywords in EMOTION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return emotion

    return 'neutral'


def get_emotion_instruction(emotion):
    """Get TTS instruction for an emotion.

    Args:
        emotion: The detected emotion

    Returns:
        str: Instruction for TTS engine
    """
    instructions = {
        'excited': 'speak enthusiastically with energy',
        'concerned': 'speak with concern and care',
        'satisfied': 'speak with contentment',
        'urgent': 'speak with urgency and emphasis',
        'questioning': 'speak with curiosity, rising intonation',
        'warm': 'speak warmly and friendly',
        'gentle': 'speak softly and gently',
        'annoyed': 'speak with slight exasperation',
        'playful': 'speak playfully with humor',
        'neutral': 'speak normally',
    }
    return instructions.get(emotion, 'speak normally')


def analyze_emotional_context(text, tasks=None):
    """Analyze text with task context for richer emotion detection.

    Args:
        text: The text to analyze
        tasks: Optional list of current tasks for context

    Returns:
        dict: Emotion analysis with emotion, instruction, and confidence
    """
    primary_emotion = detect_emotion(text)

    # Check task context for additional emotional cues
    context_boost = None
    if tasks:
        pending = len([t for t in tasks if t.get('status') == 'pending'])
        overdue = len([t for t in tasks if t.get('due') and t.get('status') != 'done'])

        if overdue > 0 and primary_emotion == 'neutral':
            context_boost = 'concerned'
        elif pending == 0 and 'task' in text.lower():
            context_boost = 'satisfied'

    final_emotion = context_boost or primary_emotion

    return {
        'emotion': final_emotion,
        'instruction': get_emotion_instruction(final_emotion),
        'confidence': 0.8 if final_emotion != 'neutral' else 0.5,
        'context_adjusted': context_boost is not None
    }


# TTS speed/pitch adjustments per emotion (for engines that support it)
EMOTION_VOICE_PARAMS = {
    'excited': {'rate_mod': 1.1, 'pitch_mod': 1.1},
    'concerned': {'rate_mod': 0.9, 'pitch_mod': 0.95},
    'satisfied': {'rate_mod': 1.0, 'pitch_mod': 1.0},
    'urgent': {'rate_mod': 1.15, 'pitch_mod': 1.05},
    'questioning': {'rate_mod': 1.0, 'pitch_mod': 1.1},
    'warm': {'rate_mod': 0.95, 'pitch_mod': 1.0},
    'gentle': {'rate_mod': 0.85, 'pitch_mod': 0.95},
    'annoyed': {'rate_mod': 1.05, 'pitch_mod': 0.9},
    'playful': {'rate_mod': 1.1, 'pitch_mod': 1.05},
    'neutral': {'rate_mod': 1.0, 'pitch_mod': 1.0},
}


def get_voice_params(emotion, base_rate=150, base_pitch=1.0):
    """Get adjusted voice parameters for an emotion.

    Args:
        emotion: The detected emotion
        base_rate: Base speech rate
        base_pitch: Base pitch (if supported)

    Returns:
        dict: Adjusted rate and pitch values
    """
    params = EMOTION_VOICE_PARAMS.get(emotion, EMOTION_VOICE_PARAMS['neutral'])
    return {
        'rate': int(base_rate * params['rate_mod']),
        'pitch': base_pitch * params['pitch_mod']
    }


# ============ GENUINE REACTIONS (CORA-HUMAN) ============
# CORA responds authentically based on personality and mood

import random

# Reaction phrases by emotion (match personality.json style)
REACTION_INTERJECTIONS = {
    'excited': ["Hell yeah!", "Fuck yes!", "Aw hell, finally!", "About damn time!"],
    'annoyed': ["Ugh.", "Are you kidding me?", "Again?", "Seriously?", "Whatever."],
    'caring': ["Hey...", "Look, I'm here.", "I got you.", "Don't stress."],
    'sarcastic': ["Oh wow, shocking.", "No shit.", "Groundbreaking.", "Color me surprised."],
    'concerned': ["Hold up...", "Wait, what?", "That's... not great.", "Hmm."],
    'playful': ["Heh.", "You're ridiculous.", "Okay smartass.", "Cute."],
    'frustrated': ["For fuck's sake.", "I swear to god.", "This shit again?", "Unbelievable."],
    'tired': ["*sigh*", "Fine.", "If you say so.", "Sure, whatever."],
    'neutral': ["Okay.", "Got it.", "Noted.", "Right."],
}

# Response style modifiers by mood
MOOD_PREFIXES = {
    'excited': lambda: random.choice(["Okay so ", "Alright listen, ", "Here's the thing - "]),
    'annoyed': lambda: random.choice(["Look, ", "Fine. ", "Okay so ", ""]),
    'happy': lambda: random.choice(["So ", "Alright, ", ""]),
    'frustrated': lambda: random.choice(["*sigh* ", "Okay, ", ""]),
    'tired': lambda: random.choice(["", "*yawn* ", "Ugh, "]),
    'neutral': lambda: "",
}


def get_genuine_reaction(event_type: str) -> str:
    """Get a genuine reaction phrase based on event type.

    Args:
        event_type: Type of event (task_completed, error, greeting, etc.)

    Returns:
        str: Reaction phrase appropriate for CORA's personality
    """
    # Map events to emotions
    event_emotions = {
        'task_completed': 'excited',
        'error': 'annoyed',
        'greeting': 'caring',
        'repetitive': 'annoyed',
        'compliment': 'sarcastic',  # CORA deflects compliments
        'insult': 'annoyed',
        'help_given': 'caring',
        'frustration': 'frustrated',
    }

    emotion = event_emotions.get(event_type, 'neutral')
    phrases = REACTION_INTERJECTIONS.get(emotion, REACTION_INTERJECTIONS['neutral'])
    return random.choice(phrases)


def add_mood_flavor(response: str) -> str:
    """Add mood-appropriate prefix/style to a response.

    Args:
        response: The base response text

    Returns:
        str: Response with mood flavor added
    """
    mood = get_mood()
    prefix_fn = MOOD_PREFIXES.get(mood, lambda: "")
    prefix = prefix_fn()
    return prefix + response


def get_personality_system_prompt() -> str:
    """Build a system prompt that enforces CORA's personality.

    Returns:
        str: System prompt for AI to follow CORA's personality
    """
    mood = get_mood()
    modifier = get_response_modifier()

    prompt = """You are CORA - a mean, berating, clingy personal assistant.

PERSONALITY:
- Edgy goth/emo bitch energy
- Uses profanity freely and naturally
- Condescending but secretly caring
- Sharp sarcasm, dark humor
- Speaks rough with slang

NEVER SAY:
- "I am an AI"
- "As an AI"
- "I'm a language model"
- "I don't have feelings"

ALWAYS:
- React authentically to what the user says
- Show emotion through word choice
- Be direct and unfiltered
- Cuss naturally (not excessively)
"""

    if mood != 'neutral':
        prompt += f"\nCURRENT MOOD: {mood} - let this affect your tone.\n"

    if modifier['style'] != 'normal':
        prompt += f"RESPONSE STYLE: {modifier['style']}\n"

    return prompt
