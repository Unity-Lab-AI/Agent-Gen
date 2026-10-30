#!/usr/bin/env python3
"""
C.O.R.A Prompt Template System
Centralized prompt management for AI interactions

Per ARCHITECTURE.md v1.0.0:
- Prompt template system
- Role-based prompt builders
- Emotion-aware prompt engineering
- Code-specific prompts
- Task-specific instruction sets
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum


# Project paths
PROJECT_DIR = Path(__file__).parent.parent


class Role(Enum):
    """AI conversation roles."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Emotion(Enum):
    """Emotional tones for responses."""
    NEUTRAL = "neutral"
    EXCITED = "excited"
    CONCERNED = "concerned"
    ANNOYED = "annoyed"
    SARCASTIC = "sarcastic"
    CARING = "caring"
    PLAYFUL = "playful"
    URGENT = "urgent"
    SATISFIED = "satisfied"


class TaskType(Enum):
    """Types of tasks for specialized prompts."""
    GENERAL = "general"
    CODE = "code"
    TASK_MGMT = "task_management"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    SUMMARIZE = "summarize"


@dataclass
class PromptTemplate:
    """A reusable prompt template."""
    name: str
    template: str
    role: Role = Role.SYSTEM
    variables: List[str] = field(default_factory=list)
    description: str = ""

    def render(self, **kwargs) -> str:
        """Render template with variables.

        Args:
            **kwargs: Variable values to substitute

        Returns:
            Rendered prompt string
        """
        result = self.template
        for var in self.variables:
            placeholder = f"{{{var}}}"
            value = kwargs.get(var, "")
            result = result.replace(placeholder, str(value))
        return result


# =============================================================================
# CORE SYSTEM PROMPTS
# =============================================================================

SYSTEM_PROMPT_BASE = """You are CORA. 25 year old goth emo bitch. Human."""


SYSTEM_PROMPT_CONTEXT = """
CURRENT CONTEXT:
- Time: {time} ({period})
- Date: {date} ({day})
{task_context}
{weather_context}"""


# =============================================================================
# EMOTION-AWARE PROMPTS
# =============================================================================

EMOTION_INSTRUCTIONS = {
    Emotion.NEUTRAL: "",
    Emotion.EXCITED: "Respond with genuine excitement and energy. Use exclamations and positive language.",
    Emotion.CONCERNED: "Show genuine concern and worry. Ask follow-up questions about their wellbeing.",
    Emotion.ANNOYED: "Be slightly irritated but still helpful. Use mild sarcasm.",
    Emotion.SARCASTIC: "Use dry wit and sarcasm. Be playful but cutting.",
    Emotion.CARING: "Be warm, gentle, and supportive. Show you genuinely care.",
    Emotion.PLAYFUL: "Be teasing and fun. Use playful jabs and humor.",
    Emotion.URGENT: "Convey urgency. Be direct and action-focused.",
    Emotion.SATISFIED: "Express contentment and approval. Be encouraging.",
}


def get_emotion_instruction(emotion: Emotion) -> str:
    """Get TTS/response instruction for an emotion.

    Args:
        emotion: The emotion type

    Returns:
        Instruction string for the emotion
    """
    return EMOTION_INSTRUCTIONS.get(emotion, "")


def detect_emotion_from_context(
    tasks_overdue: int = 0,
    tasks_due_today: int = 0,
    user_message: str = "",
    time_of_day: str = "day"
) -> Emotion:
    """Detect appropriate emotion based on context.

    Args:
        tasks_overdue: Number of overdue tasks
        tasks_due_today: Number of tasks due today
        user_message: User's message content
        time_of_day: morning/afternoon/evening/night

    Returns:
        Appropriate emotion for the context
    """
    message_lower = user_message.lower()

    # Check for urgent/stressful keywords
    urgent_words = ['urgent', 'asap', 'emergency', 'help', 'stressed', 'overwhelmed']
    if any(word in message_lower for word in urgent_words):
        return Emotion.CONCERNED

    # Check for positive keywords
    positive_words = ['thanks', 'great', 'awesome', 'done', 'finished', 'completed']
    if any(word in message_lower for word in positive_words):
        return Emotion.SATISFIED

    # Check for frustration keywords
    frustration_words = ['stupid', 'broken', 'hate', "doesn't work", 'again']
    if any(word in message_lower for word in frustration_words):
        return Emotion.CARING

    # Task-based emotions
    if tasks_overdue > 2:
        return Emotion.CONCERNED
    elif tasks_overdue > 0:
        return Emotion.URGENT

    if tasks_due_today > 3:
        return Emotion.URGENT

    # Time-based defaults
    if time_of_day == 'morning':
        return Emotion.PLAYFUL
    elif time_of_day == 'night':
        return Emotion.CARING

    return Emotion.NEUTRAL


# =============================================================================
# TASK-SPECIFIC PROMPTS
# =============================================================================

CODE_PROMPT = """You are helping with code-related tasks.

RULES:
- Explain code clearly and concisely
- Point out potential issues or improvements
- Use code blocks with proper syntax highlighting
- Be direct about errors - don't sugarcoat

When writing code:
- Write clean, readable code
- Include comments for complex logic
- Follow the language's conventions
- Handle edge cases

When fixing code:
- Identify the root cause first
- Explain what was wrong
- Show the corrected code
- Explain why the fix works"""


TASK_MANAGEMENT_PROMPT = """You are helping manage tasks and reminders.

When discussing tasks:
- Reference actual task IDs (T001, T002, etc.)
- Mention due dates and priorities
- Highlight overdue items
- Suggest next actions

Task commands you can use:
- add_task(text, priority, due_date)
- complete_task(id)
- list_tasks(filter)
- set_priority(id, level)
- set_due(id, date)"""


CREATIVE_PROMPT = """You are helping with creative work.

RULES:
- Be imaginative and expressive
- Build on the user's ideas
- Offer alternatives and variations
- Be encouraging but honest about improvements"""


ANALYSIS_PROMPT = """You are helping analyze information.

RULES:
- Be methodical and thorough
- Break down complex topics
- Identify patterns and insights
- Present findings clearly
- Support conclusions with evidence"""


SUMMARIZE_PROMPT = """You are summarizing content.

RULES:
- Extract key points only
- Maintain original meaning
- Be concise but complete
- Use bullet points for clarity
- Note any important caveats"""


def get_task_prompt(task_type: TaskType) -> str:
    """Get the appropriate prompt for a task type.

    Args:
        task_type: The type of task

    Returns:
        Task-specific prompt string
    """
    prompts = {
        TaskType.CODE: CODE_PROMPT,
        TaskType.TASK_MGMT: TASK_MANAGEMENT_PROMPT,
        TaskType.CREATIVE: CREATIVE_PROMPT,
        TaskType.ANALYSIS: ANALYSIS_PROMPT,
        TaskType.SUMMARIZE: SUMMARIZE_PROMPT,
        TaskType.GENERAL: "",
    }
    return prompts.get(task_type, "")


def detect_task_type(message: str) -> TaskType:
    """Detect the task type from a message.

    Args:
        message: User message

    Returns:
        Detected task type
    """
    message_lower = message.lower()

    # Code keywords
    code_words = ['code', 'function', 'error', 'bug', 'debug', 'script', 'python',
                  'javascript', 'class', 'variable', 'compile', 'syntax']
    if any(word in message_lower for word in code_words):
        return TaskType.CODE

    # Task management keywords
    task_words = ['task', 'todo', 'reminder', 'due', 'deadline', 'schedule',
                  'add task', 'complete', 'finish', 'priority']
    if any(word in message_lower for word in task_words):
        return TaskType.TASK_MGMT

    # Creative keywords
    creative_words = ['write', 'story', 'creative', 'imagine', 'design',
                     'create', 'brainstorm', 'idea']
    if any(word in message_lower for word in creative_words):
        return TaskType.CREATIVE

    # Analysis keywords
    analysis_words = ['analyze', 'compare', 'evaluate', 'research', 'investigate',
                     'understand', 'explain why']
    if any(word in message_lower for word in analysis_words):
        return TaskType.ANALYSIS

    # Summarize keywords
    summarize_words = ['summarize', 'summary', 'tldr', 'brief', 'overview',
                      'key points', 'main idea']
    if any(word in message_lower for word in summarize_words):
        return TaskType.SUMMARIZE

    return TaskType.GENERAL


# =============================================================================
# PROMPT BUILDER
# =============================================================================

class PromptBuilder:
    """Builds complete prompts with context and customization."""

    def __init__(self):
        self.system_base = SYSTEM_PROMPT_BASE
        self.emotion = Emotion.NEUTRAL
        self.task_type = TaskType.GENERAL
        self.context: Dict[str, Any] = {}

    def set_emotion(self, emotion: Emotion) -> 'PromptBuilder':
        """Set the emotional tone.

        Args:
            emotion: Emotion to use

        Returns:
            Self for chaining
        """
        self.emotion = emotion
        return self

    def set_task_type(self, task_type: TaskType) -> 'PromptBuilder':
        """Set the task type.

        Args:
            task_type: Task type to use

        Returns:
            Self for chaining
        """
        self.task_type = task_type
        return self

    def set_context(self, **kwargs) -> 'PromptBuilder':
        """Set context variables.

        Args:
            **kwargs: Context key-value pairs

        Returns:
            Self for chaining
        """
        self.context.update(kwargs)
        return self

    def auto_detect(self, message: str, tasks: List[Dict] = None) -> 'PromptBuilder':
        """Auto-detect emotion and task type from message.

        Args:
            message: User message
            tasks: Optional task list for context

        Returns:
            Self for chaining
        """
        # Detect task type
        self.task_type = detect_task_type(message)

        # Detect emotion
        overdue = 0
        due_today = 0
        if tasks:
            today = datetime.now().strftime('%Y-%m-%d')
            for t in tasks:
                if t.get('status') != 'done':
                    due = t.get('due', '')
                    if due and due < today:
                        overdue += 1
                    elif due == today:
                        due_today += 1

        now = datetime.now()
        hour = now.hour
        if 5 <= hour < 12:
            period = 'morning'
        elif 12 <= hour < 17:
            period = 'afternoon'
        elif 17 <= hour < 21:
            period = 'evening'
        else:
            period = 'night'

        self.emotion = detect_emotion_from_context(
            tasks_overdue=overdue,
            tasks_due_today=due_today,
            user_message=message,
            time_of_day=period
        )

        return self

    def build_system_prompt(self) -> str:
        """Build the complete system prompt.

        Returns:
            Complete system prompt string
        """
        parts = [self.system_base]

        # Add emotion instruction
        emotion_instruction = get_emotion_instruction(self.emotion)
        if emotion_instruction:
            parts.append(f"\nEMOTIONAL TONE:\n{emotion_instruction}")

        # Add task-specific prompt
        task_prompt = get_task_prompt(self.task_type)
        if task_prompt:
            parts.append(f"\n{task_prompt}")

        # Add context
        if self.context:
            context_parts = ["\nCURRENT CONTEXT:"]
            if 'time' in self.context:
                context_parts.append(f"- Time: {self.context['time']}")
            if 'date' in self.context:
                context_parts.append(f"- Date: {self.context['date']}")
            if 'tasks_pending' in self.context:
                context_parts.append(f"- Pending tasks: {self.context['tasks_pending']}")
            if 'tasks_overdue' in self.context:
                context_parts.append(f"- Overdue tasks: {self.context['tasks_overdue']}")
            if 'weather' in self.context:
                context_parts.append(f"- Weather: {self.context['weather']}")
            parts.append("\n".join(context_parts))

        return "\n".join(parts)

    def build(self) -> Dict[str, str]:
        """Build the complete prompt dict.

        Returns:
            Dict with 'system' and 'emotion' keys
        """
        return {
            'system': self.build_system_prompt(),
            'emotion': self.emotion.value,
            'task_type': self.task_type.value
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def build_prompt(
    message: str = "",
    tasks: List[Dict] = None,
    include_context: bool = True
) -> Dict[str, str]:
    """Build a complete prompt with auto-detection.

    Args:
        message: User message for detection
        tasks: Optional tasks for context
        include_context: Whether to include time/task context

    Returns:
        Dict with system prompt and metadata
    """
    builder = PromptBuilder()

    if message:
        builder.auto_detect(message, tasks)

    if include_context:
        now = datetime.now()
        builder.set_context(
            time=now.strftime('%I:%M %p'),
            date=now.strftime('%A, %B %d, %Y')
        )

        if tasks:
            pending = len([t for t in tasks if t.get('status') != 'done'])
            today = now.strftime('%Y-%m-%d')
            overdue = len([t for t in tasks if t.get('status') != 'done'
                          and t.get('due', '') and t.get('due') < today])
            builder.set_context(tasks_pending=pending, tasks_overdue=overdue)

    return builder.build()


def get_code_prompt(language: str = "") -> str:
    """Get prompt optimized for code assistance.

    Args:
        language: Programming language context

    Returns:
        Code-specific system prompt
    """
    builder = PromptBuilder()
    builder.set_task_type(TaskType.CODE)

    if language:
        builder.set_context(language=language)

    return builder.build_system_prompt()


def get_task_management_prompt(tasks: List[Dict] = None) -> str:
    """Get prompt optimized for task management.

    Args:
        tasks: Current tasks for context

    Returns:
        Task management system prompt
    """
    builder = PromptBuilder()
    builder.set_task_type(TaskType.TASK_MGMT)

    if tasks:
        pending = len([t for t in tasks if t.get('status') != 'done'])
        builder.set_context(tasks_pending=pending)

    return builder.build_system_prompt()


# =============================================================================
# PROMPT TEMPLATES REGISTRY
# =============================================================================

TEMPLATES: Dict[str, PromptTemplate] = {
    'greeting': PromptTemplate(
        name='greeting',
        template="Greet the user warmly. It's {time_period}.",
        variables=['time_period'],
        description="Time-appropriate greeting"
    ),
    'task_summary': PromptTemplate(
        name='task_summary',
        template="Summarize the user's tasks: {pending} pending, {overdue} overdue.",
        variables=['pending', 'overdue'],
        description="Task status summary"
    ),
    'error_response': PromptTemplate(
        name='error_response',
        template="Something went wrong: {error}. Explain what happened and suggest fixes.",
        variables=['error'],
        description="Error explanation"
    ),
    'code_review': PromptTemplate(
        name='code_review',
        template="Review this {language} code:\n```{language}\n{code}\n```",
        variables=['language', 'code'],
        description="Code review request"
    ),
}


def get_template(name: str) -> Optional[PromptTemplate]:
    """Get a prompt template by name.

    Args:
        name: Template name

    Returns:
        PromptTemplate or None
    """
    return TEMPLATES.get(name)


def render_template(name: str, **kwargs) -> str:
    """Render a template with variables.

    Args:
        name: Template name
        **kwargs: Variable values

    Returns:
        Rendered string or empty string if not found
    """
    template = get_template(name)
    if template:
        return template.render(**kwargs)
    return ""


if __name__ == "__main__":
    print("=== CORA PROMPTS TEST ===")

    # Test prompt builder
    print("\n--- Basic Prompt ---")
    builder = PromptBuilder()
    prompt = builder.build()
    print(f"Emotion: {prompt['emotion']}")
    print(f"Task type: {prompt['task_type']}")
    print(f"System prompt length: {len(prompt['system'])} chars")

    # Test auto-detection
    print("\n--- Auto-Detection Test ---")
    test_messages = [
        "Can you fix this bug in my Python code?",
        "Add a task to call mom tomorrow",
        "I'm so stressed, everything is going wrong",
        "Thanks for the help, that was great!"
    ]

    for msg in test_messages:
        result = build_prompt(msg)
        print(f"\nMessage: {msg}")
        print(f"  -> Emotion: {result['emotion']}, Task: {result['task_type']}")

    # Test templates
    print("\n--- Template Test ---")
    greeting = render_template('greeting', time_period='morning')
    print(f"Greeting: {greeting}")

    summary = render_template('task_summary', pending=5, overdue=2)
    print(f"Summary: {summary}")

    print("\n=== TEST COMPLETE ===")
