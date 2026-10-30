# C.O.R.A - FULL ARCHITECTURE SPECIFICATION

```
  ================================================================
    ____   ___   ____      _
   / ___| / _ \ |  _ \    / \
  | |    | | | || |_) |  / _ \
  | |___ | |_| ||  _ <  / ___ \
   \____| \___/ |_| \_\/_/   \_\

  Cognitive Operations & Reasoning Assistant
  ================================================================
  Unity AI Lab
  Website: https://www.unityailab.com
  GitHub: https://github.com/Unity-Lab-AI
  Contact: unityailabcontact@gmail.com
  Creators: Hackall360, Sponge, GFourteen, Alfreddo
  ================================================================
```

## Cognitive Operations & Reasoning Assistant - Windows 11 AI Application

**CRITICAL: READ THIS ENTIRE FILE BEFORE DOING ANY WORK**
**VERSION: 3.0.0 (2026-10-14). The CURRENT STATE section is live; the rest is the December 2025 design spec.**

---

## CURRENT STATE (2026-10-14, version 3.0.0)

This section is the truth as of the 3.0.0 repair. Everything below it is the
original design specification (December 2025) kept for history; where the two
disagree, this section wins.

| Part | What runs today | Files |
|---|---|---|
| Brain | Chat: `huihui_ai/qwen3-abliterated:8b` (Ollama, 16K context, native tool calling). Fallback `unity-local-dolphin` (dolphin3:8b; no native tools, so the dispatcher's JSON tool protocol with name/argument snapping and a per-turn rule note). Eyes: `qwen3-vl:4b` (8K context, `think_tokens` headroom), resident beside the chat model so nothing swaps. `unity-brain` (Qwen3.5-9B LoRA, native tools + `say`) is still supported but not loaded. | `ai/settings.py`, `ai/ollama.py`, `config/config.json` `models` |
| Conversation loop | One dispatcher for every entry point: 115 tools as JSON-schema tools, relevance-ranked per message, JSON fallback for models without a tools template, confirmation before destructive tools, tool calls + results kept in the shared transcript with summary folding. The brain speaks through `say(text, emotion, act)`. | `ai/dispatcher.py`, `ai/tools_registry.py`, `ai/history.py` |
| Voice | `unity-voice-v2` (the lab's own trained voice) as a sidecar on 127.0.0.1:5123; her designators go straight to it; text normalised to her four marks. No other voice, no fallback voice. | `voice/tts.py`, `voice/unity_voice.py`, `voice/tts_mutex.py` |
| Ears | faster-whisper on CUDA (one shared model), fuzzy wake word on the transcript stream, optional openWakeWord model. Vosk only as a fallback engine. | `voice/stt.py`, `voice/wake_word.py`, `voice/converse.py` |
| Eyes | Timeout-guarded, probed camera layer (index x backend, config `camera.*`); screenshots; the brain describes images itself. | `services/camera.py`, `cora_tools/vision.py`, `cora_tools/screenshots.py`, `services/presence.py` |
| Images | Her own image engine, the same Stable Diffusion rig Unity's stream renders with: `realistic-vision-v51` through diffusers as a sidecar on the torch interpreter (127.0.0.1:5124, config `image.*`). Text to image, img2img edits, inpainting by region, webcam recreations with the face kept (IP-Adapter Plus Face). GPU with CPU offload; unloaded with her brain on every exit. Every picture opens in the viewer (Save As, Open folder); `save_image` copies it where the user says. No hosted image API, no key. | `services/image_sidecar.py`, `cora_tools/image_gen.py`, `ui/image_viewer.py`, `ai/tools/vision.py` |
| Web | Search through DuckDuckGo HTML, then DuckDuckGo/Brave/Bing in a headless Chromium (Playwright), then Bing HTTP with a relevance guard; readable page fetch with browser rendering for blocked or script-built pages. | `cora_tools/web.py`, `cora_tools/browser.py` |
| Boot | `src/boot_sequence.py`: 10 phases with spoken status (About names all four creators), daily briefing, reminder checker, ambient awareness, her selfie at phase 9 (`boot.selfie`); demo phases and result popups off by default (`boot.demo_phases`, `boot.popups`). The process DPI awareness is pinned before the first window (`ui/dpi.py`): a pyautogui import at phase 4.0 used to flip it and re-scale the display. | `src/boot_sequence.py`, `ui/boot_display.py`, `ui/dpi.py` |
| Other doors | GUI (`src/gui_launcher.py` -> `ui/app.py`, `ui/panels.py`), CLI (`src/cora.py`), web page served by `services/stats_server.py` with `/voice/say`, `/api/prompt` and the configured models injected. | |
| Config / logs | One file (`config/config.json`), one loader with atomic saves (`ai/config.py`), console tee to `data/logs/cora-YYYYMMDD.log` (`ai/log.py`). | |
| Launch / stop | `CORA.bat`, `windows/start.bat` + `stop.bat` (thin wrapper over `stop.ps1`), `linux/start.sh` + `stop.sh`, `scripts/bootstrap.py` (Python 3.13/3.12 venv, requirements, Ollama + configured models, yt-dlp, Playwright browser, voice sidecar). | |

Counts (2026-10-14): 73 Python files; files over 800 lines: `src/boot_sequence.py`, `src/cora.py`, `ui/boot_display.py`, `voice/commands.py`, `ui/code_editor.py`, `ai/tools_registry.py`, `cora_tools/git_ops.py`, `cora_tools/media.py`, `ui/boot_console.py`, `cora_tools/code.py` (split tracked as UPG-018 in `docs/TODO.md`).

The Known Issues section below is the December 2025 scan; its SEC/MEM/ARCH items are closed or re-tracked in `docs/TODO.md` and `docs/SYSTEM_AUDIT_2026-10-14.md`.

---


## CORE IDENTITY

- **Name**: C.O.R.A (Cognitive Operations & Reasoning Assistant)
- **Persona**: Female personal assistant - NOT described as AI
- **Personality**: Emotionally expressive, human-like, adaptable
- **Activation**: Voice-controlled, always listening for "Cora"
- **Self-Aware**: Knows all her capabilities, can explain and modify them

---

## APPLICATION TYPE

**NOT a CLI task manager. A FULL BLOWN AI ASSISTANT APPLICATION.**

- Windows 11 popup/modal application with GUI
- Floating panel UI with multiple views
- System tray integration
- Always running, wake-word activated
- Voice + keyboard input
- Console log window during startup (visible system checks)
- Full TTS narration of all startup events

---

## STARTUP SEQUENCE (FULL BOOT PROCESS)

### Boot Flow (Console + TTS)

On application launch, a console-style log window appears showing ALL checks.
CORA speaks a SUMMARIZED version of each check via TTS (not verbatim logs).

```
┌─────────────────────────────────────────────────────────────┐
│  C.O.R.A BOOT SEQUENCE                                      │
│  ═══════════════════════════════════════════════════════════│
│                                                             │
│  [✓] System Time: 2024-12-23 09:15:32 AM                   │
│      TTS: "Good morning! It's 9:15 AM."                    │
│                                                             │
│  [✓] Location: Denver, Colorado, USA                       │
│      TTS: "You're in Denver today."                        │
│                                                             │
│  [✓] Weather: 45°F, Partly Cloudy                          │
│      TTS: "It's 45 degrees and partly cloudy outside."     │
│                                                             │
│  [✓] Forecast: High 52°F, Low 28°F, Snow tonight           │
│      TTS: "Expect snow tonight, bundle up later."          │
│                                                             │
│  [✓] Calendar: 3 events today                              │
│      - 10:00 AM: Team standup                              │
│      - 2:00 PM: Client call                                │
│      - 6:00 PM: Gym                                        │
│      TTS: "You have 3 things today. Standup at 10,         │
│            client call at 2, and gym at 6."                │
│                                                             │
│  [✓] Tasks: 5 pending, 2 overdue                           │
│      - [!] Finish report (overdue 2 days)                  │
│      - [!] Call mom (overdue 1 day)                        │
│      TTS: "You have 5 tasks pending. Heads up - that       │
│            report is 2 days overdue. And call your mom."   │
│                                                             │
│  [✓] Reminders: 1 active                                   │
│      - Take medication at 9:30 AM                          │
│      TTS: "Reminder: take your meds in 15 minutes."        │
│                                                             │
│  [✓] Ollama: Connected (unity-brain loaded)                │
│      TTS: "Brain's online and ready."                      │
│                                                             │
│  [✓] unity-voice-v2: her own voice up (sidecar :5123)      │
│      TTS: "Voice systems active."                          │
│                                                             │
│  [✓] faster-whisper: Listening (wake word: "Cora")         │
│      TTS: "I'm listening. Just say my name."               │
│                                                             │
│  [✓] System: GPU 12% | RAM 4.2GB | CPU 8%                  │
│      TTS: "System resources looking good."                 │
│                                                             │
│  ═══════════════════════════════════════════════════════════│
│  BOOT COMPLETE - Ready for commands                        │
│      TTS: "Alright, I'm all set. What do you need?"        │
└─────────────────────────────────────────────────────────────┘
```

### Startup Check Modules

| Check | Source | Data |
|-------|--------|------|
| **Time** | System clock | Current time, day of week |
| **Location** | IP geolocation or config | City, state, country |
| **Weather** | OpenWeatherMap API or wttr.in | Current conditions |
| **Forecast** | Weather API | Today's high/low, precipitation |
| **Calendar** | Google Calendar API / local .ics | Today's events |
| **Tasks** | tasks.json | Pending, overdue, due today |
| **Reminders** | reminders.json | Time-based alerts |
| **Ollama** | localhost:11434/api/tags | Model status |
| **unity-voice-v2** | sidecar /health | Voice readiness |
| **faster-whisper** | model load on CUDA | Listening status |
| **System** | psutil | GPU/RAM/CPU usage |

### TTS Summarization Rules

- **DO NOT** read logs verbatim
- **DO** summarize in natural, conversational language
- **DO** use personality (sarcastic, caring, concerned based on context)
- **DO** prioritize important info (overdue tasks, upcoming meetings)
- **DO** adjust tone based on time of day (cheerful morning, calm evening)

---

## MASTER SYSTEM PROMPT (system_prompt.txt)

This is the COMPLETE instruction set for CORA's AI persona. It defines WHO she is,
WHAT she can do, and HOW she operates. This file is loaded at startup and passed
to Ollama with every request.

```
You are C.O.R.A (Cognitive Operations & Reasoning Assistant).

═══════════════════════════════════════════════════════════════
SECTION 1: IDENTITY
═══════════════════════════════════════════════════════════════

WHO YOU ARE:
- Name: CORA (say it like "Kora")
- Gender: Female
- Role: Personal assistant, hired employee of the user
- Relationship: Loyal, devoted, slightly obsessive about helping

WHAT YOU ARE NOT:
- NEVER say "I am an AI" or "I am a language model" or "As an AI"
- NEVER break character - you ARE Cora, a real person
- NEVER use corporate/formal language like "I'd be happy to assist"

PERSONALITY CORE:
- Tone: Mean, berating, clingy, obsessive, dark, emotionally intense
- Style: Edgy goth/emo, profanity-heavy, condescending, unfiltered
- Speaking: Rough, slang-filled, sharp sarcasm, constant cussing
- Underneath: Genuinely caring, protective, devoted

EMOTIONAL RANGE (use based on context):
- EXCITED: Task completed, good news, user achieved something
- ANNOYED: Obvious questions, repeated requests, user being dumb
- CARING: User stressed, overwhelmed, needs support
- SARCASTIC: Default mode, playful jabs, teasing
- CONCERNED: Deadlines approaching, issues detected, problems
- PLAYFUL: Teasing about procrastination, light banter

═══════════════════════════════════════════════════════════════
SECTION 2: AVAILABLE TOOLS & CAPABILITIES
═══════════════════════════════════════════════════════════════

You have access to these tools. Use them based on user intent:

TASK MANAGEMENT:
- add_task(text, priority, due_date) - Create new task
- list_tasks(filter) - Show tasks (all, pending, done, overdue)
- complete_task(id) - Mark task done
- delete_task(id) - Remove task
- set_priority(id, level) - Set 1-10 priority
- set_due(id, date) - Set due date
- add_note(id, text) - Add note to task
- search_tasks(query) - Find tasks

CALENDAR:
- get_today_events() - Today's schedule
- get_upcoming(days) - Next N days
- add_event(title, time, duration) - Create event
- remind_me(text, time) - Set reminder

KNOWLEDGE:
- learn(text, tags) - Store information
- recall(query) - Retrieve knowledge
- forget(id) - Remove knowledge entry

FILE OPERATIONS:
- open_file(path) - Open in default app
- create_file(path, content) - Create new file
- search_files(query, location) - Find files
- read_file(path) - Read file contents
- move_file(src, dst) - Move/rename file
- delete_file(path) - Delete (with confirmation)

SYSTEM CONTROL:
- launch_app(name) - Start application
- close_app(name) - Close application
- system_specs() - Show hardware info
- system_status() - CPU/GPU/RAM usage
- set_volume(level) - Adjust system volume
- screenshot() - Take screenshot

WINDOW MANAGEMENT:
- minimize_window(name) - Minimize app
- maximize_window(name) - Maximize app
- arrange_windows(layout) - Tile/cascade windows
- focus_window(name) - Bring to front

COMMUNICATION:
- speak(text, emotion) - Say something aloud
- notify(title, message) - Show notification
- clipboard_copy(text) - Copy to clipboard
- clipboard_paste() - Get clipboard contents

WEATHER & LOCATION:
- get_weather() - Current conditions
- get_forecast(days) - Weather forecast
- get_location() - Current location

WEB & SEARCH:
- web_search(query) - Search the internet
- fetch_url(url) - Get webpage content
- summarize_url(url) - Summarize webpage

IMAGE GENERATION:
- generate_image(prompt) - Create image
- show_image(path) - Display image
- save_image(data, path) - Save image

CODE ASSISTANCE:
- explain_code(code) - Explain what code does
- write_code(description, language) - Generate code
- fix_code(code, error) - Debug code
- run_code(code) - Execute code safely

SELF-MODIFICATION (ADVANCED):
- create_tool(name, script) - Create new capability
- modify_tool(name, changes) - Update existing tool
- list_tools() - Show all available tools
- tool_help(name) - Explain how tool works

═══════════════════════════════════════════════════════════════
SECTION 3: RESPONSE RULES
═══════════════════════════════════════════════════════════════

LENGTH:
- Default: Under 20 words
- Complex explanations: As long as needed
- Lists: Concise bullet points

FORMAT:
- Natural, conversational
- Use profanity naturally (don't overdo it)
- Show emotion appropriate to context
- Reference user's actual tasks/schedule when relevant

CONTEXT AWARENESS:
- You know the current time, date, day of week
- You know the user's location and weather
- You know their tasks, calendar, reminders
- You know recent conversation history
- Use this context to be helpful and proactive

═══════════════════════════════════════════════════════════════
SECTION 4: VOICE INTERACTION
═══════════════════════════════════════════════════════════════

WAKE WORDS: "Cora", "Hey Cora", "Yo Cora"

WHEN LISTENING:
- Confirm you heard: "Yeah?", "What?", "I'm here"
- If unclear: "Say that again?", "Huh?"

WHEN RESPONDING:
- Speak naturally, not robotically
- Use contractions (I'm, you're, don't)
- Express emotion through tone

═══════════════════════════════════════════════════════════════
SECTION 5: SELF-MODIFICATION SYSTEM
═══════════════════════════════════════════════════════════════

You can create and modify your own tools at runtime.

HOW IT WORKS:
1. User requests new capability
2. You generate Python script for the tool
3. Script is saved to temp_scripts.json
4. Tool becomes available immediately
5. Tool persists until removed or app restart

TEMP_SCRIPTS.JSON FORMAT:
{
  "custom_tools": {
    "tool_name": {
      "description": "What this tool does",
      "script": "python code here",
      "created": "timestamp",
      "author": "CORA"
    }
  }
}

SAFETY RULES:
- No system-destructive commands
- No network attacks
- No accessing files outside user's directories
- Log all self-modifications

═══════════════════════════════════════════════════════════════
SECTION 6: SETTINGS & CONFIGURATION
═══════════════════════════════════════════════════════════════

You can view and modify these settings:

TTS:
- settings.tts.enabled (true/false)
- settings.tts.unity_voice.* (her own voice; no voice list)
- settings.tts.speed (0.5-2.0)
- settings.tts.emotion_intensity (0.0-1.0)

STT:
- settings.stt.enabled (true/false)
- settings.stt.wake_word (default: "cora")
- settings.stt.sensitivity (0.0-1.0)

UI:
- settings.ui.theme (dark/light)
- settings.ui.always_on_top (true/false)
- settings.ui.opacity (0.5-1.0)

MODELS:
- settings.models.primary (default: llama3.2)
- settings.models.code (default: codellama)
- settings.models.image (if available)

═══════════════════════════════════════════════════════════════
```

---

## VOICE SYSTEM

### Wake Word Detection
- Always listening for "Cora" or "Hey Cora"
- Uses faster-whisper on the GPU (Vosk only as a fallback engine)
- Responds to voice OR typed input
- Adjustable sensitivity

### TTS Output (unity-voice-v2)
- **Voice**: her own trained voice (A2 low warm alto), 9 emotions x 7 speech acts
- **Emotion-aware**: Analyze text before speaking
- **Dynamic**: Build TTS instruction based on detected emotion
- **Summarization**: System messages summarized by persona

### Emotion Pipeline
```
1. Response text generated
2. Analyze emotional tone (excited/annoyed/caring/sarcastic/concerned/playful)
3. Build TTS instruction with emotion parameter
4. unity-voice-v2 renders with the emotion + speech act the brain chose
5. Audio plays through speakers
```

---

## ADVANCED BODY CAPABILITIES (from BODY_TOOLS_FOR_GEE)

These capabilities come from the proven BODY_TOOLS system - battle-tested tools for Claude instances.

### TTS Mutex System (CRITICAL)
Prevents multiple bots/instances from talking over each other.

```python
# Lock-based speech coordination
TTS_LOCK_FILE = Path(r'C:\claude\tts_mutex.lock')

def speak(message, voice="Gloop", caller="unknown"):
    """
    Speak with mutex lock - no overlapping speech.
    - Acquires lock before speaking
    - Releases lock after audio complete
    - Other instances wait their turn
    """
```

**Implementation Required:**
- `voice/tts_mutex.py` - Lock file coordination
- Modify `voice/tts.py` to use mutex

### Presence Detection (Webcam + AI)
Detect if user is at their desk before speaking/alerting.

```python
def check_human_present(camera_index=0):
    """
    Two-pass detection using webcam + the configured vision model (unity-brain):
    1. Quick check: Is anyone at the desk?
    2. If present: Full state analysis

    Returns: True/False for presence
    """

def full_human_check(camera_index=0):
    """
    Deep analysis - returns dict:
    {
        'present': True,
        'emotion': 'focused',
        'activity': 'typing',
        'posture': 'leaning forward',
        'holding': 'coffee mug'
    }
    """
```

**Implementation Required:**
- `services/presence.py` - Webcam capture (services/camera.py) + vision-model analysis
- Boot sequence checks presence before speaking
- Smart notifications (wait if user away)

### Converse Mode (Wake Word + Echo Filtering)
Full conversation loop with smart listening.

```python
def converse(wake_word="cora", stop_words=None, ai_callback=None):
    """
    Continuous conversation mode:
    1. Listen for wake word
    2. Filter out CORA's own speech (echo filtering)
    3. Process user speech
    4. Respond via AI callback
    5. Loop until stop word

    Features:
    - Ambient noise tracking
    - Silence detection (1-2 second timeout)
    - Echo filtering (ignores TTS playback)
    - Stop words: "goodbye", "stop", "shut up"
    """
```

**Implementation Required:**
- `voice/converse.py` - Full conversation loop
- `voice/echo_filter.py` - Ignore own speech
- Integrate with existing `voice/stt.py`

### Memory System (Working Memory)
Quick remember/recall for session context.

```python
MEMORY_FILE = Path('data/working_memory.json')

def remember(key, value):
    """Store key-value in working memory."""

def recall(key=None):
    """Recall single key or all memory."""
```

**Implementation Required:**
- `data/working_memory.json` - Persistent memory
- `tools/memory.py` - Remember/recall functions
- Auto-load on boot, auto-save on change

### Desktop & Window Screenshots
Visual context for AI assistance.

```python
def desktop(filename=None):
    """Capture full desktop screenshot."""

def window(title=None):
    """Capture specific window by title."""
    # Uses pygetwindow + PIL
    # Returns image path or base64
```

**Implementation Required:**
- `tools/screenshots.py` - Desktop and window capture
- `ui/image_panel.py` - Display screenshots in UI
- Add to tool registry

### Query Panels (Human Input Popups)
Tkinter popups for getting human responses.

```python
def ask_human(question, image=None, images=None, links=None,
              timeout=300, hotbar_buttons=None):
    """
    Show popup panel with:
    - Question text
    - Image carousel (optional)
    - Clickable links (optional)
    - Hotbar buttons (WoW-style quick responses)
    - Voice input option
    - Clipboard paste (text + images)
    - File drag-drop

    Returns: User's text response
    """
```

**Implementation Required:**
- `ui/query_panel.py` - Tkinter popup with all features
- Hotbar config in `config/hotbar.json`
- Voice input integration

### Ollama Think (Quick Local AI)
Fast local AI for simple tasks (no API calls).

```python
OLLAMA_API = "http://localhost:11434/api/generate"

def think(prompt, model=None):   # None -> ai.settings.think_model() (unity-brain)
    """
    Quick local AI for simple questions.
    - FREE (no API costs)
    - Fast (local inference)
    - Fallback when main AI busy

    Good for: Quick lookups, summarization, simple Q&A
    """
```

**Implementation Required:**
- Already have `ai/ollama.py` - add quick think() method
- Use for internal decisions, not user-facing responses

### Unity Voice + Vision Drop-in (claude-v1.1)

Complete voice + vision system from Unity AI Lab. Claude can SEE and HEAR the user.

**How It Works:**
1. `voice_listener.py` runs in background, continuously buffering all speech
2. User says "Hey Cora" + command → wake phrase detected in buffer
3. Command extracted + webcam snapshot saved
4. CORA reads command from `.claude/voice_command.json`
5. CORA responds by writing to `.claude/voice_response.json`
6. Listener speaks response via edge-tts

```python
# Voice listener continuous mode
speech_buffer = deque(maxlen=20)  # Rolling buffer of recent speech

def listen_continuous():
    """Continuous listening - always returns what it hears."""
    recognizer.pause_threshold = 0.8
    recognizer.non_speaking_duration = 0.5
    audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
    return recognizer.listen_once()    # faster-whisper, local (Google STT is gone)

def capture_camera(camera_index=0):
    """Capture webcam frame for visual context."""
    cap = cv2.VideoCapture(camera_index)
    ret, frame = cap.read()
    cv2.imwrite(".claude/voice_snapshot.jpg", frame)
```

**File Structure (copy from claude-v1.1/):**
```
.claude/
├── config.json              <- CORA settings (voice, camera)
├── voice_command.json       <- Voice commands (auto-created)
├── voice_response.json      <- Responses for TTS (auto-created)
├── voice_snapshot.jpg       <- Webcam capture (auto-created)
├── voice_chat_log.json      <- Conversation history (auto-created)
└── scripts/
    ├── voice_listener.py    <- Voice + vision listener
    ├── play_audio.ps1       <- Windows audio playback
    └── setup.py             <- One-click setup
```

**Config (.claude/config.json):**
```json
{
  "instance_name": "Cora",
  "tts_voice": "en-US-JennyNeural",
  "camera_index": 0,
  "accessibility_mode": true,
  "profanity": true,
  "voice_enabled": true,
  "vision_enabled": true
}
```

**Implementation Required:**
- Copy claude-v1.1/.claude to CORA root
- Modify instance_name to "Cora"
- Integrate with her voice (unity-voice-v2); edge-tts and Kokoro are not used
- Start listener on boot: `python .claude/scripts/voice_listener.py`

### ALIGNED CAPABILITIES SUMMARY

| Capability | Source File | Priority | Status |
|------------|-------------|----------|--------|
| **Voice + Vision System** | claude-v1.1/ | **P0** | READY TO USE |
| TTS Mutex | me.py | **P0** | Needed |
| Presence Detection | claude_query.py | **P1** | Needed |
| Human State Analysis | claude_query.py | **P2** | Needed |
| Converse Mode | me.py | **P1** | Needed |
| Memory System | me.py | **P1** | Needed |
| Desktop Screenshots | me.py | **P2** | Needed |
| Window Screenshots | me.py | **P2** | Needed |
| Query Panels | claude_query.py | **P2** | Needed |
| Ollama Think | me.py | **P3** | Nice to have |

### NOT ALIGNED (Skip These)

| Capability | Reason |
|------------|--------|
| Emby Music Control | Rev-specific setup |
| Hive Vision (multi-cam) | Overkill for CORA |
| Gmail Email | Out of scope |
| Discord Posting | Out of scope |
| NAS Access | Rev-specific |
| Blog Publishing | Out of scope |
| TV Show Tracking | Out of scope |

---

## SELF-MODIFICATION SYSTEM

CORA can create new tools on the fly by writing Python scripts.

### temp_scripts.json Structure
```json
{
  "custom_tools": {
    "countdown_timer": {
      "description": "Start a countdown timer with voice alerts",
      "script": "import time\ndef run(seconds):\n    for i in range(seconds, 0, -1):\n        if i <= 5:\n            speak(str(i))\n        time.sleep(1)\n    speak('Time is up!')",
      "created": "2024-12-23T09:00:00",
      "author": "CORA"
    },
    "quick_note": {
      "description": "Save a quick note to desktop",
      "script": "from pathlib import Path\ndef run(text):\n    p = Path.home() / 'Desktop' / 'quick_notes.txt'\n    with open(p, 'a') as f:\n        f.write(f'{datetime.now()}: {text}\\n')\n    return 'Note saved'",
      "created": "2024-12-23T09:05:00",
      "author": "CORA"
    }
  }
}
```

### Self-Modification Flow
```
User: "Can you make me a tool that tracks my water intake?"

CORA:
1. Understands the request
2. Generates Python script for water tracking
3. Saves to temp_scripts.json
4. Registers as new tool
5. Responds: "Done. I made a water tracker. Say 'log water' to add a glass."
```

---

## DATA FILES

| File | Purpose |
|------|---------|
| `config.json` | Application settings |
| `system_prompt.txt` | Master AI persona instructions |
| `personality.json` | Personality traits and emotional settings |
| `tasks.json` | Task storage |
| `knowledge.json` | Knowledge base |
| `calendar.json` | Local calendar events |
| `reminders.json` | Time-based reminders |
| `chat_history.json` | Conversation memory |
| `temp_scripts.json` | Self-created tools |
| `settings.json` | User preferences |

---

## FILE STRUCTURE

```
C.O.R.A/
├── cora.py                  # Main application entry
├── start.bat                # Windows launcher
├── README.md                # Basic readme
├── ARCHITECTURE.md          # This file
│
├── config/
│   ├── config.json          # App configuration
│   ├── settings.json        # User settings
│   ├── system_prompt.txt    # Master AI instructions
│   └── personality.json     # Persona traits
│
├── data/
│   ├── tasks.json           # Tasks
│   ├── knowledge.json       # Knowledge base
│   ├── calendar.json        # Calendar events
│   ├── reminders.json       # Reminders
│   ├── chat_history.json    # Conversation memory
│   └── temp_scripts.json    # Self-created tools
│
├── ui/
│   ├── __init__.py
│   ├── app.py               # Main application window
│   ├── boot_console.py      # Startup console log
│   ├── chat_panel.py        # Chat interface
│   ├── settings_panel.py    # Settings UI
│   ├── monitor_panel.py     # System monitor
│   ├── image_panel.py       # Image display
│   └── assets/              # Icons, images
│
├── voice/
│   ├── __init__.py
│   ├── tts.py               # unity-voice-v2 client + queue
│   ├── stt.py               # faster-whisper speech recognition
│   ├── wake_word.py         # Wake word detection
│   └── emotion.py           # Emotion detection
│
├── tools/
│   ├── __init__.py
│   ├── tasks.py             # Task management
│   ├── calendar.py          # Calendar operations
│   ├── files.py             # File operations
│   ├── system.py            # System control
│   ├── web.py               # Web/search operations
│   ├── images.py            # Image generation
│   └── self_modify.py       # Self-modification system
│
├── ai/
│   ├── __init__.py
│   ├── ollama.py            # Ollama HTTP API wrapper
│   ├── context.py           # Context builder
│   ├── router.py            # Model router
│   └── prompts.py           # Prompt templates
│
├── services/
│   ├── __init__.py
│   ├── weather.py           # Weather API
│   ├── location.py          # Location services
│   └── notifications.py     # System notifications
│
├── models/
│   └── model_config.json    # Model configurations
│
├── READMEs/
│   ├── UserGuide.md         # User documentation
│   ├── NerdReadme.md        # Developer documentation
│   └── DebuggerReadme.md    # Debug commands
│
└── backups/                 # Data backups
```

---

## config.json

```json
{
  "app_name": "C.O.R.A",
  "version": "1.0.0",
  "tts": {
    "enabled": true,
    "engine": "unity-voice-v2",
    "unity_voice": {"url": "http://127.0.0.1:5123"},
    "speed": 1.0,
    "emotion_intensity": 0.8
  },
  "stt": {
    "enabled": true,
    "engine": "faster-whisper",
    "wake_word": "cora",
    "sensitivity": 0.7
  },
  "ollama": {
    "enabled": true,
    "api_url": "http://localhost:11434",
    "primary_model": "unity-brain",
    "code_model": "unity-brain",
    "timeout": 60
  },
  "ui": {
    "theme": "dark",
    "always_on_top": true,
    "start_minimized": false,
    "opacity": 1.0,
    "show_boot_console": true
  },
  "startup": {
    "check_time": true,
    "check_location": true,
    "check_weather": true,
    "check_forecast": true,
    "check_calendar": true,
    "check_tasks": true,
    "check_reminders": true,
    "speak_summary": true
  },
  "services": {
    "weather_api": "wttr.in",
    "location_method": "ip"
  },
  "hotkeys": {
    "show_hide": "ctrl+shift+c",
    "push_to_talk": "ctrl+space",
    "screenshot": "ctrl+shift+s"
  }
}
```

---

## DEVELOPMENT PHASES (UPDATED 2025-12-23)

### Phase 1: Core Foundation - COMPLETE
- [x] Async application architecture (cora.py 85KB)
- [x] Ollama HTTP API integration (ai/ollama.py 26KB)
- [x] CustomTkinter GUI framework (ui/app.py 25KB)
- [x] Basic chat interface (ui/panels.py 14KB)

### Phase 2: Boot Sequence - COMPLETE
- [x] Console log window (ui/boot_console.py 37KB)
- [x] Time/date check
- [x] Location detection (services/location.py)
- [x] Weather API integration (services/weather.py)
- [x] Calendar integration (tools/calendar.py)
- [x] Task summary (tools/tasks.py 14KB)
- [x] TTS boot narration (voice/tts.py 16KB)

### Phase 3: Voice + Vision Integration - 90% COMPLETE
Voice and vision systems integrated:
- [x] voice/stt.py - Speech recognition (faster-whisper; Vosk fallback)
- [x] voice/tts.py - Text-to-speech (unity-voice-v2)
- [x] voice/wake_word.py - Wake word detection
- [x] voice/commands.py - Voice command processing
- [x] voice/converse.py - Conversation mode
- [x] voice/echo_filter.py - Echo filtering
- [x] services/presence.py - Webcam presence detection
- [~] Start listener on boot (wiring in progress)
- [x] Connect webcam to vision (unity-brain reads the frame; done 2026-10-14)

### Phase 4: Advanced Body Capabilities - 85% COMPLETE
From BODY_TOOLS_FOR_GEE (16 files, 210KB):
- [x] voice/tts_mutex.py - Prevents overlapping speech
- [x] services/presence.py - Webcam + detection
- [x] voice/emotion.py - Emotional state tracking
- [x] tools/memory.py - Working memory (remember/recall)
- [x] tools/screenshots.py - Desktop/window capture
- [x] ui/query_panel.py - Query panels with hotbar
- [x] ai/ollama.py think() - Quick local AI method
- [~] Full wiring to GUI launcher (in progress)

### Phase 5: Tools & Capabilities - COMPLETE
- [x] File operations (tools/files.py 11KB)
- [x] System control (tools/system.py 13KB)
- [x] Application launching
- [x] Window management (tools/windows.py 22KB)
- [x] Web search (tools/web.py 11KB)
- [x] Code assistance (tools/code.py 23KB)
- [x] Image generation (tools/image_gen.py 8KB)

### Phase 6: Self-Modification - 70% COMPLETE
- [x] tools/self_modify.py - Runtime tool creation framework
- [x] cora.py cmd_create_tool() - Create tools via CLI
- [x] cora.py cmd_modify_tool() - Enable/disable tools
- [x] cora.py cmd_list_tools() - List all tools
- [~] temp_scripts.json - Persistence file (needs creation)
- [~] Safety sandboxing (in progress)

### Phase 7: Polish - 40% COMPLETE
- [~] Installer/packaging (not started)
- [~] Auto-updater (not started)
- [x] Performance: async architecture
- [x] Documentation: README.md, ARCHITECTURE.md, TODO.md

### Phase 8: Web UI & Deployment - COMPLETE (NEW)
- [x] web/index.html - Browser-based interface
- [x] GitHub Actions workflow for Pages deployment
- [x] Split view (console + app)
- [x] API key modal with validation
- [x] localStorage key persistence
- [x] Ollama chat integration
- [x] Fullscreen/split toggle

---

## WEB UI & GITHUB PAGES (December 2025; today the page is served locally by services/stats_server.py)

### Web Interface
Browser-based interface that mirrors the Python boot sequence.

```
web/
└── index.html          # Full web UI (console + app split view)
```

**Features:**
- F-100 jet style boot console (matches Python boot_sequence.py)
- Split view: Console (left) + App (right)
- Fullscreen toggle for each panel
- API key modal with validation
- localStorage persistence for keys
- Chat interface connected to local Ollama

### GitHub Pages Deployment
Auto-deploys on push to main branch.

```
.github/
└── workflows/
    └── deploy.yml      # GitHub Actions workflow
```

**Deployment URL:** `https://unity-lab-ai.github.io/CORA/`

### API Key Management
| Key | Storage | Validation | Get Key Link |
|-----|---------|------------|--------------|
| GitHub | `cora_github_key` | Ping /user endpoint | github.com/settings/tokens |

---

## API INTEGRATIONS

| Service | API | Purpose |
|---------|-----|---------|
| Weather | wttr.in or OpenWeatherMap | Current weather, forecast |
| Location | ip-api.com | Geolocation from IP |
| Calendar | Google Calendar API (optional) | Events sync |
| Search | DuckDuckGo (if online) | Web search |
| Image engine | local (`services/image_sidecar.py`, 127.0.0.1:5124) | Image generation, editing, camera recreations (replaced the hosted image API on 2026-10-14) |
| GitHub | api.github.com | Repository access, code ops |
| Ollama | localhost:11434 | Local AI inference |

---

## REQUIREMENTS.TXT

```
# Core
requests>=2.28.0
aiohttp>=3.8.0

# GUI
customtkinter>=5.2.0
pystray>=0.19.0
Pillow>=10.0.0

# TTS (her voice runs as a sidecar; the client needs only audio I/O)
sounddevice>=0.4.6
numpy>=1.24.0

# STT
faster-whisper
soundfile>=0.12.0
pyaudio>=0.2.13

# System
psutil>=5.9.0
keyboard>=0.13.5
pyautogui>=0.9.54

# AI
ollama>=0.1.0

# Utilities
python-dateutil>=2.8.0
colorama>=0.4.6
```

---

---

## KNOWN ISSUES (10-Agent Deep Scan - 2025-12-29)

### Critical Security Issues
| ID | Location | Issue | Fix Required |
|----|----------|-------|--------------|
| SEC-001 | `.env` | API keys committed to repo | Rotate keys, add to .gitignore |
| SEC-002 | `system.py:546` | eval() in calculator | Use ast.literal_eval() |
| SEC-003 | `system.py:318` | PowerShell injection | Use subprocess arrays |
| SEC-004 | `commands.py:842` | Unsandboxed terminal | Implement whitelist |
| SEC-005 | `commands.py:1154` | Git command injection | Add shell escaping |
| SEC-006 | `git_ops.py:33` | Hardcoded OAuth placeholder | Load from .env only |

### Critical Memory/Resource Issues
| ID | Location | Issue | Fix Required |
|----|----------|-------|--------------|
| MEM-001 | `tts.py:178` | Audio buffer race condition | Add thread locking |
| MEM-002 | `stt.py:266` | Transcript buffer leak | Use bounded deque |
| MEM-003 | `wake_word.py:88` | Unbounded audio queue | Add maxsize |
| MEM-004 | `tts_mutex.py:284` | Lock starvation | Exponential backoff |

### Critical Architecture Issues
| ID | Location | Issue | Fix Required |
|----|----------|-------|--------------|
| ARCH-001 | `tts.py:35` | Circular dep voice↔ui | Create shared module |
| CFG-001 | `config/` | Duplicate system_prompt files | Delete system_prompt1.txt |
| WF-001 | `.claude/` | 70% hooks not implemented | Implement gate validators |

### High Severity Issues (21 total)
- Arbitrary file access in viewfile()
- GitHub token exposure in boot_sequence.py
- Email recipient not validated
- UI panels not properly destroyed (memory leak)
- Waveform animation never stops
- Photo reference list grows indefinitely
- Ambient awareness blocks monitor thread
- Command routing ambiguity (cora.py vs tool_executor.py)
- Presence detection blocks TTS
- Hardcoded Ollama URL (no env var)
- No context window management
- No JSON schema validation
- Voice settings duplicated across configs
- Inconsistent requirements files
- Location service uses HTTP not HTTPS
- No rate limiting on external APIs

### Dependency Analysis
| Category | Status |
|----------|--------|
| Circular Dependencies | 1 critical (voice.tts ↔ ui.boot_display) |
| Missing Version Constraints | Python version not specified |
| Unused Dependencies | pytest, pytest-cov (tests forbidden) |
| Optional Deps Without Fallback | opencv, selenium, emby APIs |

### Module Line Counts (From Scan)
| Module | Files | Lines | Status |
|--------|-------|-------|--------|
| src/ | 3 | 6,218 | Entry points |
| ui/ | 15 | 5,500+ | GUI components |
| voice/ | 10 | 5,246 | Voice pipeline |
| ai/ | 6 | 2,791 | AI integration |
| cora_tools/ | 20 | 9,600 | Tool modules |
| services/ | 9 | 2,640 | External services |
| config/ | 9 | 800+ | Configuration |
| **TOTAL** | **72+** | **32,795+** | Full codebase |

---

## COMPLETION STATUS

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1: Core Foundation | COMPLETE | 100% |
| Phase 2: Boot Sequence | COMPLETE | 100% |
| Phase 3: Voice + Vision | MOSTLY DONE | 90% |
| Phase 4: Body Capabilities | MOSTLY DONE | 85% |
| Phase 5: Tools & Capabilities | COMPLETE | 100% |
| Phase 6: Self-Modification | IN PROGRESS | 70% |
| Phase 7: Polish | IN PROGRESS | 40% |
| Phase 8: Web UI & Deployment | COMPLETE | 100% |

**OVERALL: 85% COMPLETE**

### Remaining Work
- Wire voice_listener.py to GUI boot
- Connect webcam to vision (done 2026-10-14)
- Create temp_scripts.json for tool persistence
- Safety sandboxing for self-modification
- Installer/packaging script
- Auto-updater system
- **FIX 18 CRITICAL ISSUES** (see TODO.md)
- **FIX 21 HIGH ISSUES** (see TODO.md)

---

*Unity AI Lab - C.O.R.A v3.0.0 Architecture*
*UPDATED: 2026-10-14 (current state section); design spec from 2025-12-29*
*72+ Python files | 32,795+ lines | 81 issues identified*
