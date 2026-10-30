# C.O.R.A API Reference

## Module & Function Reference

Version 3.0.0 (2026-10-14)

---

## Current API (3.0.0)

The signatures below are the ones in the code today. The reference that follows them is the December 2025 design listing (kept; several names in it never shipped as written).

```python
# ai/dispatcher.py
get_dispatcher() -> Dispatcher
Dispatcher.handle(text, speak=True, on_event=None, stream=True, tools_enabled=True,
                  allowed_tools=None) -> DispatchResult(text, tool_calls, spoke, error, pending_confirmation, elapsed)
    # on_event(kind, payload): thinking, token, sentence, tool_call, tool_result, confirm_needed, final, error
Dispatcher.voice_mode() -> 'say_tool' | 'stream'
Dispatcher.confirm_callback = fn(question) -> True/False/None
ask(text, speak=False) -> str

# ai/tools_registry.py
@_tool(name, description, category, params={name: _p(desc, type, enum)}, required=[...], confirm=False, speak_result=False)
all_tools() / get_tool(name) / tool_schemas() / tool_catalog_text()
select_tools(text, max_tools=40) -> [Tool]        # core set + best keyword matches
execute(name, arguments) -> {'ok': bool, 'message'|'error': str, ...}
CORE_TOOLS, SAY_EMOTIONS, SAY_ACTS

# ai/history.py
get_history() -> ConversationHistory
.add_exchange(user_text, assistant_text, turn_messages=None)   # tool calls + results kept
.messages_for_model(system_prompt) / .needs_summary(system_prompt) / .fold_into_summary(summarizer) / .clear()
# env CORA_HISTORY_FILE -> scratch transcript for checks

# ai/ollama.py  (think=False by default on every call)
chat(messages, model=None, system=None, temperature=None, max_tokens=None, timeout=None, tools=None, think=False) -> OllamaResponse
chat_stream_events(...) -> yields {'type': 'token'|'tool_calls'|'done'|'error', ...}
generate(prompt, model=None, system=None, ...) -> OllamaResponse
generate_with_image(prompt, image_path, model=None, ...) -> OllamaResponse ; analyze_image(image_path, prompt) -> str
warm_up(model=None) / model_capabilities(model) / has_model(model) / list_models() / pull_model(name) / summarize(text)

# ai/settings.py
ollama_url() chat_model() vision_model() code_model() think_model() num_ctx(model=None) keep_alive()
model_options(model=None) base_options(temperature_override=None, max_tokens_override=None, model=None)
creators() -> {'lab', 'names', 'roles', 'spoken'} ; reload()

# ai/config.py
load(force=False) get(dotted, default=None) section(name) save(cfg) update(mutator) version()

# ai/log.py
setup(name='cora', keep_days=14, tee=True) -> Path ; get_logger(name) ; log_path()

# voice/tts.py
UnityVoiceTTS().speak(text, emotion='neutral', speech_act=None) -> bool
TTSQueue.speak(text, emotion, priority=5, skip_presence=False, speech_act=None)
queue_speak(text, emotion='neutral', priority=5, speech_act=None) ; speak() ; speak_async() ; speak_interrupt()
stop_speaking() ; is_speaking() ; voice_status() -> {'engine', 'url', 'up', 'model_dir', 'model_present'}

# voice/unity_voice.py
EMOTIONS, SPEECH_ACTS ; voice_text(text) ; prepare_text(text) ; split_sentences(text)
plan_delivery(sentence, emotion, had_bang) ; synth(body) ; synth_with_fallback(sentence, emotion, had_bang)
synth_delivery(sentence, emotion, speech_act, intensity=None) ; ensure_sidecar() ; is_up() ; take_turn() / give_turn()

# voice/stt.py
SpeechRecognizer(engine=None).initialize() / .listen_once(timeout, phrase_limit) / .start_listening(callback) / .transcribe_audio(bytes)
WakeWordDetector(wake_word=None).start(on_wake) / .stop() ; WakeWordDetector.add_transcript_callback(fn) ; .last_wake_time
stt_status() -> dict ; transcribe_file(path) ; list_microphones()

# services/camera.py
capture_frame(timeout=None) -> ndarray|None ; capture_to_file(path=None) -> Path|None
open_capture() -> cv2.VideoCapture|None ; working_device() -> (index, backend) ; camera_status(probe=True) ; last_error()

# cora_tools/web.py
web_search(query, num_results=5, show_window=False) -> {'success', 'results': [{title, url, snippet, answer_box?}], 'engine', 'count'}
fetch_url(url, timeout=15, show_window=False) -> {'success', 'text', 'content', 'via', 'status_code'}
summarize_url(url) ; instant_answer(query)

# cora_tools/vision.py
capture_screenshot() -> Path|None ; capture_camera_snapshot(save_path=None) -> Path|None ; describe_screen(prompt) ; describe_camera(prompt)

# cora_tools/image_gen.py  (her image engine: services/image_sidecar.py, local Stable Diffusion on 127.0.0.1:5124)
generate_image(prompt, width=None, height=None, seed=None, output_path=None, negative=None, steps=None, face=None) -> {'success', 'path', 'seed', 'width', 'height', 'inference_time', 'engine', ...}
edit_image(source, prompt, strength=0.55, box=None, keep_face=False, ...)     # source: path | 'last' | 'camera'; box -> inpaint
recreate_camera(prompt='', strength=0.6, keep_face=True, ...) ; generate_boot_image(prompt=None)
save_image(destination, source='last') ; show_image(path, caption=None, close_after=None) ; show_fullscreen_image(path, duration=None)
last_image() ; get_recent_images(limit) ; ensure_sidecar() ; sidecar_health() ; release() ; release_gpu() ; stop_sidecar()

# services/image_sidecar.py  (HTTP, JSON in, image/png out with X-Seed / X-Seconds / X-Size)
GET /health ; POST /txt2img {prompt, negative?, width?, height?, steps?, guidance?, seed?, face?, face_scale?}
POST /img2img {prompt, image(b64), strength?, ...} ; POST /inpaint {prompt, image, mask(b64)? | box?, ...} ; POST /unload ; POST /shutdown

# ai/tools (images): generate_image, edit_image, recreate_camera, save_image, show_image, recent_images
```

### config/config.json (3.0.0 blocks)

| Block | Keys |
|---|---|
| `models` | `primary`, `vision`, `code`, `fallback`, `options` ({model: {num_ctx, temperature, top_k, top_p, presence_penalty}}) |
| `ollama` | `api_url`, `num_ctx`, `keep_alive`, `timeout`, `think_timeout`, `vision_timeout` |
| `ai` | `temperature`, `max_tokens`, `history_turns` |
| `assistant` | `voice_mode` (auto / say_tool / stream), `legacy_regex`, `max_tools` |
| `tts` | `enabled`, `volume`, `presence_gate`, `unity_voice` {`url`, `model_dir`, `python`, `autostart`, `default_intensity`} |
| `stt` | `engine`, `whisper_model`, `device`, `wake_word`, `sensitivity` |
| `camera` | `enabled`, `index`, `backend`, `open_timeout` |
| `image` | `url`, `checkpoint`, `python`, `device`, `offload`, `autostart`, `steps`, `width`, `height`, `save_dir` |
| `boot` | `demo_phases`, `popups`, `github_import` |
| `web` | `allowed_origins` |

### Environment variables (3.0.0)

| Variable | Purpose |
|---|---|
| `OLLAMA_URL` / `OLLAMA_HOST` | Ollama endpoint |
| `CORA_CHAT_MODEL`, `CORA_VISION_MODEL`, `CORA_CODE_MODEL`, `CORA_THINK_MODEL`, `CORA_NUM_CTX` | model overrides |
| `CORA_HISTORY_FILE` | scratch transcript for checks |
| `UNITY_VOICE_TTS_URL`, `UNITY_VOICE_MODEL_DIR`, `UNITY_VOICE_PYTHON` | her voice sidecar |
| `CORA_IMAGE_URL`, `CORA_IMAGE_CHECKPOINT`, `CORA_IMAGE_PYTHON`, `CORA_IMAGE_DEVICE` | her image engine sidecar |
| `GITHUB_TOKEN` | optional key (`.env`) |

---

## Table of Contents (December 2025 reference)

1. [Core Modules](#core-modules)
2. [Voice Layer](#voice-layer)
3. [AI Layer](#ai-layer)
4. [Tools Layer](#tools-layer)
5. [Services Layer](#services-layer)
6. [UI Layer](#ui-layer)
7. [Data Schemas](#data-schemas)

---

## Core Modules

### cora.py - Main CLI Application

The primary command-line interface and command dispatcher.

#### Global Variables

```python
CONFIG: dict           # Global configuration dictionary
COMMANDS: dict         # Command name -> function mapping
LAST_DELETED: dict     # Last deleted task (for undo)
```

#### Command Functions

All command functions follow this signature:

```python
def cmd_name(args: str, tasks: dict) -> str:
    """
    Execute a command.

    Args:
        args: Command arguments as string
        tasks: Current tasks dictionary

    Returns:
        Response message string
    """
```

| Function | Command | Description |
|----------|---------|-------------|
| `cmd_add(args, tasks)` | `add <text>` | Create new task |
| `cmd_list(args, tasks)` | `list [pri]` | List tasks |
| `cmd_done(args, tasks)` | `done <id>` | Complete task |
| `cmd_delete(args, tasks)` | `delete <id>` | Remove task |
| `cmd_pri(args, tasks)` | `pri <id> <1-10>` | Set priority |
| `cmd_due(args, tasks)` | `due <id> <date>` | Set due date |
| `cmd_note(args, tasks)` | `note <id> <text>` | Add note |
| `cmd_edit(args, tasks)` | `edit <id> <text>` | Edit text |
| `cmd_show(args, tasks)` | `show <id>` | Show details |
| `cmd_search(args, tasks)` | `search <query>` | Find tasks |
| `cmd_today(args, tasks)` | `today` | Due/overdue |
| `cmd_undo(args, tasks)` | `undo` | Restore deleted |
| `cmd_learn(args, tasks)` | `learn <text>` | Add knowledge |
| `cmd_recall(args, tasks)` | `recall [#tag]` | Get knowledge |
| `cmd_chat(args, tasks)` | `chat <msg>` | AI chat |
| `cmd_speak(args, tasks)` | `speak <text>` | TTS output |
| `cmd_time(args, tasks)` | `time` | Current time |
| `cmd_weather(args, tasks)` | `weather` | Weather info |
| `cmd_screenshot(args, tasks)` | `screenshot` | Capture screen |
| `cmd_see(args, tasks)` | `see [prompt]` | Camera vision |
| `cmd_settings(args, tasks)` | `settings` | View/edit config |
| `cmd_backup(args, tasks)` | `backup` | Save data |
| `cmd_help(args, tasks)` | `help` | Show commands |

#### Core Functions

```python
def process_command(cmd: str, tasks: dict) -> str:
    """
    Parse and execute a command string.

    Args:
        cmd: Full command string (e.g., "add Buy groceries")
        tasks: Tasks dictionary

    Returns:
        Response message
    """

def load_tasks() -> dict:
    """
    Load tasks from tasks.json.

    Returns:
        Tasks dictionary with 'counter' and 'tasks' keys
    """

def save_tasks(tasks: dict) -> None:
    """Save tasks to tasks.json."""

def load_knowledge() -> dict:
    """
    Load knowledge base from knowledge.json.

    Returns:
        Knowledge dictionary with 'counter' and 'entries' keys
    """

def save_knowledge(knowledge: dict) -> None:
    """Save knowledge base to knowledge.json."""

def fallback_response(query: str) -> str:
    """
    Generate offline response when Ollama unavailable.

    Args:
        query: User's query

    Returns:
        Fallback response string
    """
```

---

## Voice Layer

### voice/tts.py - Text-to-Speech

#### Classes

```python
class TTSEngine:
    """Abstract base class for TTS engines."""

    def initialize(self) -> bool:
        """Initialize the engine. Returns success status."""

    def speak(self, text: str, emotion: str = 'neutral') -> bool:
        """
        Speak text synchronously.

        Args:
            text: Text to speak
            emotion: Emotion hint (neutral, excited, concerned, etc.)

        Returns:
            Success status
        """

    def get_audio(self, text: str, emotion: str = 'neutral') -> bytes:
        """
        Generate audio without playing.

        Returns:
            WAV audio bytes
        """

class KokoroTTS(TTSEngine):   # December 2025; in 3.0.0 this name is an alias of UnityVoiceTTS
    """High-quality neural TTS using Kokoro model."""

    def __init__(self, model_path: str = None):
        """
        Args:
            model_path: Path to Kokoro model (optional)
        """

class Pyttsx3TTS(TTSEngine):   # December 2025; in 3.0.0 this name is an alias of UnityVoiceTTS
    """Offline TTS using pyttsx3."""

    def __init__(self, rate: int = 150, volume: float = 1.0):
        """
        Args:
            rate: Speech rate (words per minute)
            volume: Volume 0.0 to 1.0
        """

class TTSQueue:
    """
    Non-blocking TTS with priority queue.

    Attributes:
        on_speak_start: Callable[[str], None] - Called when speech starts
        on_speak_end: Callable[[str], None] - Called when speech ends
    """

    def __init__(self, engine: TTSEngine):
        """
        Args:
            engine: TTSEngine instance to use
        """

    def queue(self, text: str, emotion: str = 'neutral', priority: int = 5):
        """
        Add text to speech queue.

        Args:
            text: Text to speak
            emotion: Emotion hint
            priority: 1 (highest) to 10 (lowest)
        """

    def speak_now(self, text: str, emotion: str = 'neutral'):
        """Clear queue and speak immediately."""

    def stop(self):
        """Stop current speech and clear queue."""

    def is_speaking(self) -> bool:
        """Check if currently speaking."""
```

#### Module Functions

```python
def get_tts_engine(config: dict = None) -> TTSEngine:
    """
    Factory function for TTS engine selection.

    Args:
        config: Configuration dict with 'tts' section

    Returns:
        Appropriate TTSEngine instance
    """

def speak(text: str, emotion: str = 'neutral') -> bool:
    """Quick synchronous speak using global engine."""

def queue_speak(text: str, emotion: str = 'neutral', priority: int = 5):
    """Queue text for async speaking."""

def speak_interrupt(text: str, emotion: str = 'neutral'):
    """Clear queue and speak immediately."""
```

---

### voice/emotion.py - Emotional State Machine

```python
class EmotionalState:
    """
    Singleton emotional state manager.

    Tracks and modifies emotional state based on events.
    """

    EMOTIONS = [
        'excited', 'concerned', 'satisfied', 'annoyed',
        'sarcastic', 'caring', 'playful', 'urgent', 'neutral'
    ]

    def apply_event(self, event: str) -> None:
        """
        Apply an event to modify emotional state.

        Events:
            - task_completed: +satisfaction
            - error: +frustration
            - greeting: +warmth
            - user_praise: +satisfaction
            - user_frustration: +concern
            - long_wait: +concern
        """

    def decay(self, amount: float = 0.1) -> None:
        """Decay all emotions toward neutral."""

    def get_mood(self) -> str:
        """Get current dominant emotion."""

    def get_intensity(self) -> float:
        """Get intensity of dominant emotion (0.0-1.0)."""

    def get_tts_modifiers(self) -> dict:
        """
        Get TTS parameters for current mood.

        Returns:
            Dict with 'rate_modifier', 'pitch_modifier', 'volume_modifier'
        """

def get_emotional_state() -> EmotionalState:
    """Get the singleton EmotionalState instance."""
```

---

### voice/stt.py - Speech-to-Text

```python
class VoskSTT:   # December 2025 design; the shipped class is SpeechRecognizer (faster-whisper, Vosk fallback)
    """Vosk-based speech recognition."""

    def __init__(self, model_path: str = None):
        """
        Args:
            model_path: Path to Vosk model directory
        """

    def recognize(self, audio_data: bytes) -> str:
        """
        Recognize speech from audio data.

        Args:
            audio_data: WAV audio bytes

        Returns:
            Recognized text
        """

    def listen(self, timeout: float = 5.0) -> str:
        """
        Listen to microphone and recognize.

        Args:
            timeout: Maximum listen time in seconds

        Returns:
            Recognized text
        """

def get_stt_engine(config: dict = None) -> VoskSTT:
    """Get STT engine instance."""

def listen_for_command(timeout: float = 5.0) -> str:
    """Listen and return recognized command."""
```

---

### voice/commands.py - Voice Command Processing

```python
def load_voice_config() -> dict:
    """
    Load config/voice_commands.json.

    Returns:
        Voice configuration dictionary
    """

def is_command_enabled(name: str) -> bool:
    """Check if a command is enabled in voice config."""

def get_wake_words() -> list:
    """Get list of active wake words."""

def parse_voice_input(text: str) -> tuple:
    """
    Parse voice input to extract command.

    Args:
        text: Raw recognized text

    Returns:
        Tuple of (command_name, arguments) or (None, None)
    """

def execute_command(cmd: str, args: str) -> str:
    """
    Execute a voice command.

    Args:
        cmd: Command name
        args: Command arguments

    Returns:
        Response text
    """
```

---

### voice/tts_mutex.py - Speech Overlap Prevention

```python
class TTSMutex:
    """
    Cross-process mutex for TTS synchronization.

    Prevents multiple processes from speaking simultaneously.
    """

    def __init__(self, name: str = "CORA"):
        """
        Args:
            name: Mutex identifier
        """

    def locked(self, timeout: float = 10.0) -> contextmanager:
        """
        Context manager for mutex acquisition.

        Args:
            timeout: Max wait time in seconds

        Yields:
            bool: True if lock acquired, False on timeout
        """

def get_mutex(name: str = "CORA") -> TTSMutex:
    """Get or create named mutex."""
```

---

## AI Layer

### ai/ollama.py - Ollama API Client

```python
# Configuration
# December 2025 design; in 3.0.0 all of this comes from ai.settings (unity-brain for chat and vision)
OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
VISION_MODEL = "llava"

def chat(messages: list, model: str = DEFAULT_MODEL,
         stream: bool = False) -> str:
    """
    Send chat completion request.

    Args:
        messages: List of {"role": str, "content": str} dicts
        model: Ollama model name
        stream: Enable streaming (not yet implemented)

    Returns:
        Assistant response text
    """

def generate(prompt: str, model: str = DEFAULT_MODEL) -> str:
    """
    Generate completion from prompt.

    Args:
        prompt: Input prompt
        model: Model name

    Returns:
        Generated text
    """

def vision(image_data: bytes, prompt: str = "What do you see?",
           model: str = VISION_MODEL) -> str:
    """
    Analyze image using vision model.

    Args:
        image_data: JPEG image bytes
        prompt: Question about the image
        model: Vision model name

    Returns:
        Description/answer text
    """

def list_models() -> list:
    """
    List available Ollama models.

    Returns:
        List of model info dicts
    """

def is_available() -> bool:
    """Check if Ollama service is running."""

def pull_model(model: str) -> bool:
    """
    Pull/download an Ollama model.

    Args:
        model: Model name to pull

    Returns:
        Success status
    """
```

---

### ai/context.py - Context Management

```python
def build_context(tasks: dict, knowledge: dict = None) -> str:
    """
    Build context string for AI prompts.

    Args:
        tasks: Current tasks dictionary
        knowledge: Knowledge base (optional)

    Returns:
        Context string including tasks, time, personality
    """

def get_conversation_history(limit: int = 10) -> list:
    """
    Get recent conversation history.

    Args:
        limit: Max messages to return

    Returns:
        List of message dicts
    """

def add_to_history(role: str, content: str) -> None:
    """
    Add message to conversation history.

    Args:
        role: 'user' or 'assistant'
        content: Message content
    """

def clear_history() -> None:
    """Clear conversation history."""
```

---

### ai/router.py - Model Routing

```python
def route_query(query: str, context: dict = None) -> str:
    """
    Route query to appropriate model.

    Args:
        query: User query
        context: Optional context dict with 'has_image', etc.

    Returns:
        Model name to use
    """

def get_model_for_task(task_type: str) -> str:
    """
    Get optimal model for task type.

    Task types:
        - chat: General conversation
        - vision: Image analysis
        - code: Code generation
        - summary: Text summarization

    Returns:
        Model name
    """
```

---

## Tools Layer

### tools/screenshots.py - Screen Capture

```python
def capture_screen(region: tuple = None) -> bytes:
    """
    Capture screenshot.

    Args:
        region: Optional (x, y, width, height) tuple

    Returns:
        PNG image bytes
    """

def capture_and_save(path: str = None) -> str:
    """
    Capture and save screenshot to file.

    Args:
        path: Output path (auto-generated if None)

    Returns:
        Path to saved file
    """
```

---

### tools/tasks.py - Task Management Module

```python
def create_task(text: str, priority: int = 5,
                due: str = None) -> dict:
    """
    Create a new task dict.

    Args:
        text: Task description
        priority: 1-10 (1=highest)
        due: Due date (YYYY-MM-DD)

    Returns:
        Task dictionary
    """

def get_pending(tasks: dict) -> list:
    """Get all pending tasks."""

def get_overdue(tasks: dict) -> list:
    """Get tasks past due date."""

def get_due_today(tasks: dict) -> list:
    """Get tasks due today."""

def sort_by_priority(task_list: list) -> list:
    """Sort tasks by priority (ascending)."""
```

---

### tools/self_modify.py - Runtime Tool Creation

```python
def create_tool(name: str, description: str,
                handler: str = None) -> dict:
    """
    Create a runtime tool.

    Args:
        name: Tool name (command)
        description: Tool description
        handler: Python code string (optional)

    Returns:
        Tool definition dict
    """

def modify_tool(name: str, action: str) -> bool:
    """
    Modify existing tool.

    Actions:
        - enable: Enable the tool
        - disable: Disable the tool
        - delete: Remove the tool

    Returns:
        Success status
    """

def list_tools() -> list:
    """Get all runtime tools."""

def execute_tool(name: str, args: str) -> str:
    """
    Execute a runtime tool.

    Args:
        name: Tool name
        args: Tool arguments

    Returns:
        Tool output
    """
```

---

### tools/image_gen.py - Image Generation

December 2025 design (a hosted image API). Since 2026-10-14 the module is the client of her local engine; the shipped signatures are in the Current API section.

```python
# (the hosted endpoint constant is gone; the engine is services/image_sidecar.py on 127.0.0.1:5124)

def generate_image(prompt: str, width: int = 512,
                   height: int = 512) -> bytes:
    """
    Generate image from text prompt.

    Args:
        prompt: Image description
        width: Output width
        height: Output height

    Returns:
        PNG image bytes
    """

def save_generated_image(prompt: str, path: str = None) -> str:
    """
    Generate and save image.

    Args:
        prompt: Image description
        path: Output path (auto-generated if None)

    Returns:
        Path to saved file
    """
```

---

## Services Layer

### services/presence.py - Webcam Presence Detection

```python
from dataclasses import dataclass

@dataclass
class PresenceResult:
    present: bool      # User detected
    confidence: float  # Detection confidence 0-1
    error: str = None  # Error message if any

def check_human_present() -> PresenceResult:
    """
    Check if human is present via webcam.

    Uses OpenCV Haar cascade for face detection.

    Returns:
        PresenceResult with detection status
    """

def capture_webcam() -> bytes:
    """
    Capture single frame from webcam.

    Returns:
        JPEG image bytes or None on failure
    """

def get_camera_info() -> dict:
    """
    Get webcam information.

    Returns:
        Dict with 'available', 'resolution', 'name'
    """
```

---

### services/weather.py - Weather API

```python
def get_weather(location: str = None) -> dict:
    """
    Get current weather conditions.

    Args:
        location: City name (auto-detect if None)

    Returns:
        Dict with 'temperature', 'conditions', 'humidity', etc.
    """

def format_weather(weather: dict) -> str:
    """Format weather dict as readable string."""
```

---

### services/location.py - Geolocation

```python
def get_location() -> dict:
    """
    Get current location via IP geolocation.

    Returns:
        Dict with 'city', 'region', 'country', 'lat', 'lon'
    """

def get_timezone() -> str:
    """Get local timezone string."""
```

---

### services/audio.py - Audio Device Management

```python
def list_microphones() -> list:
    """
    List available microphone devices.

    Returns:
        List of device info dicts
    """

def list_speakers() -> list:
    """List available speaker devices."""

def get_default_microphone() -> dict:
    """Get default microphone info."""

def test_microphone(device_id: int = None,
                    duration: float = 1.0) -> bool:
    """
    Test microphone input.

    Args:
        device_id: Device index (default if None)
        duration: Test duration in seconds

    Returns:
        True if audio detected
    """
```

---

## UI Layer

### ui/app.py - Main GUI Application

```python
class CoraApp(ctk.CTk):
    """Main GUI application window."""

    def __init__(self, skip_splash: bool = False):
        """
        Initialize the application.

        Args:
            skip_splash: Skip splash screen if True
        """

    def show_chat(self) -> None:
        """Switch to chat panel."""

    def show_tasks(self) -> None:
        """Switch to tasks panel."""

    def show_knowledge(self) -> None:
        """Switch to knowledge panel."""

    def show_settings(self) -> None:
        """Switch to settings panel."""

    def process_command(self, command: str) -> None:
        """
        Process user command asynchronously.

        Args:
            command: Command string to execute
        """

    def add_message(self, sender: str, message: str) -> None:
        """
        Add message to chat display.

        Args:
            sender: Message sender name
            message: Message content
        """

def main(skip_splash: bool = False) -> None:
    """
    Launch GUI application.

    Args:
        skip_splash: Skip splash screen
    """

def main_quick() -> None:
    """Launch GUI without splash screen."""
```

---

### ui/boot_console.py - Boot Diagnostics

```python
@dataclass
class BootCheck:
    """Single boot check definition."""
    name: str                          # Display name
    check_func: Callable[[], dict]     # Check function
    tts_func: Callable[[dict], str]    # TTS summary function

class BootConsole(ctk.CTkToplevel):
    """Boot diagnostics console window."""

    def __init__(self, master, checks: list = None,
                 on_complete: Callable = None):
        """
        Args:
            master: Parent window
            checks: List of BootCheck objects
            on_complete: Callback when boot finishes
        """

    def run_checks(self) -> None:
        """Run all boot checks sequentially."""

    def skip(self) -> None:
        """Skip remaining checks."""

def create_default_boot_checks() -> list:
    """
    Create default list of boot checks.

    Returns:
        List of BootCheck objects for all 13 checks
    """
```

---

### ui/panels.py - GUI Panels

```python
class BasePanel(ctk.CTkFrame):
    """Base class for all panels."""

class ChatPanel(BasePanel):
    """Chat interface panel."""

    def __init__(self, parent, on_send: Callable = None):
        """
        Args:
            parent: Parent widget
            on_send: Callback when message sent
        """

    def add_message(self, sender: str, message: str) -> None:
        """Add message to display."""

    def clear(self) -> None:
        """Clear all messages."""

class TasksPanel(BasePanel):
    """Task list panel with checkboxes."""

    def load_tasks(self, tasks: list) -> None:
        """Load tasks into panel."""

class SettingsPanel(BasePanel):
    """Settings configuration panel."""

    def __init__(self, parent, config: dict = None,
                 on_save: Callable = None):
        """
        Args:
            parent: Parent widget
            config: Initial configuration
            on_save: Callback when settings saved
        """

    def load_config(self, config: dict) -> None:
        """Load configuration into widgets."""

class KnowledgePanel(BasePanel):
    """Knowledge base browser panel."""

    def load_entries(self, entries: list) -> None:
        """Load knowledge entries into panel."""
```

---

## Data Schemas

### tasks.json

```json
{
  "counter": 42,
  "tasks": [
    {
      "id": "T042",
      "text": "Task description",
      "status": "pending|active|done",
      "priority": 5,
      "created": "2025-12-23T10:00:00",
      "due": "2025-12-25",
      "notes": [
        {"text": "Note text", "created": "2025-12-23T11:00:00"}
      ],
      "completed": "2025-12-24T15:00:00"
    }
  ]
}
```

### knowledge.json

```json
{
  "counter": 10,
  "entries": [
    {
      "id": "K010",
      "content": "Knowledge content here",
      "tags": ["tag1", "tag2"],
      "created": "2025-12-23T10:00:00"
    }
  ]
}
```

### config/settings.json

```json
{
  "tts": {
    "enabled": true,
    "voice": "Microsoft David",
    "rate": 150,
    "volume": 1.0
  },
  "ollama": {
    "enabled": true,
    "model": "llama3.2"
  },
  "stt": {
    "enabled": true,
    "sensitivity": 0.7
  }
}
```
(December 2025 shape; 3.0.0 uses `config/config.json`, see the Current API section.)

### config/voice_commands.json

```json
{
  "enabled": true,
  "wake_words": ["cora", "hey cora", "yo cora", "okay cora"],
  "confidence_threshold": 0.7,
  "commands": {
    "time": {"enabled": true, "aliases": ["clock", "what time"]},
    "weather": {"enabled": true, "aliases": ["forecast"]},
    "add_task": {"enabled": true, "aliases": ["add task", "new task"]}
  },
  "custom_responses": {
    "hello": ["Hello!", "Hi there!", "Hey!"],
    "goodbye": ["Goodbye!", "See you!", "Bye!"]
  }
}
```

### chat_history.json

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Hello CORA",
      "timestamp": "2025-12-23T10:00:00"
    },
    {
      "role": "assistant",
      "content": "Hello! How can I help?",
      "timestamp": "2025-12-23T10:00:01"
    }
  ]
}
```

---

## Error Codes

| Module | Error | Description |
|--------|-------|-------------|
| TTS | `TTS_NOT_AVAILABLE` | No TTS engine initialized |
| TTS | `TTS_MUTEX_TIMEOUT` | Failed to acquire speech lock |
| STT | `STT_NO_MODEL` | whisper/Vosk model not found |
| STT | `STT_NO_AUDIO` | No audio input detected |
| AI | `OLLAMA_OFFLINE` | Ollama service not running |
| AI | `MODEL_NOT_FOUND` | Requested model not available |
| Camera | `CAM_NOT_AVAILABLE` | Webcam not accessible |
| Camera | `CAM_NO_FACE` | No face detected |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `localhost:11434` | Ollama API endpoint |
| `CORA_TTS_ENGINE` | (removed) | 3.0.0 has one voice; see `UNITY_VOICE_*` above |
| `CORA_LOG_LEVEL` | `INFO` | Logging level |
| `CORA_DATA_DIR` | `.` | Data directory path |

---

*Unity AI Lab - C.O.R.A v3.0.0 API Reference*
*Last Updated: 2026-10-14*
