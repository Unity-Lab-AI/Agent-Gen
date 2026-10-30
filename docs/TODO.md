# TODO — Minor Task List (Active Tasks)

**Tier 2 of 3** — the MINOR task list. Holds active tasks (pending + in_progress) at the day-to-day work grain. Each minor task lives under a major milestone in `docs/ROADMAP.md` and decomposes further into entries in `docs/DECOMPOSED.md` when YOLO mode picks it up.

Completed tasks move to `docs/FINALIZED.md` per `.claude/CONSTRAINTS.md §FINALIZED BEFORE DELETE`. Never delete a task description; only flip status (LAW: NEVER DELETE TODO INFO).

Status markers:
- `[ ]` pending
- `[~]` in_progress
- `[x]` complete (move to FINALIZED.md immediately, never leave here)

LAW #0 reminder: every task description preserves the user's verbatim words.

**Three-tier cascade:** ROADMAP.md (major) → TODO.md (minor, this file) → DECOMPOSED.md (decomposed). YOLO mode reads all three and works the cascade — see `.claude/commands/yolo.md` and `.claude/WORKFLOW.md §YOLO MODE`.

> **Template-repo clean state.** UAL-ClaudeWorkflow ships as a `.claude/` template seed for downstream private Unity AI Lab projects. This live `TODO.md` is intentionally empty — active task entries shouldn't pollute downstream installs. Downstream projects populate their own TODO after the `/unity-install` (or `/unity-update`) flow seeds the `.claude/` workflow.

---

## In progress

_(none)_

---

## Pending

Charter quote (verbatim) lives at the top of `docs/ROADMAP.md`. Each task below quotes the words it serves. Source paths for every item are in `docs/FEATURE-SOURCES.md`.

### M1 — Rip and stage ("copying and ripping them into this project")

- [ ] Create `vendor/` with `PROVENANCE.md` (origin path, origin project, date copied, git commit where known) and a scrub checklist for every `.env`, key file and hardcoded token listed in FEATURE-SOURCES §0.2.
- [ ] Rip "the Unity voice v2": copy `Desktop\Backrooms\models\unity-voice-v2\` whole (code + `voice-meta.json`; weights go to gitignored `models/`).
- [ ] Rip the C.O.R.A voice client set (`voice\unity_voice.py`, `tts.py`, `emotion.py`, `tts_mutex.py`) and the `voice_text()` sanitizer from Backrooms `unity-speak.py`.
- [ ] Rip "stt": VibeRoller `bridge\speech-engine.py`, C.O.R.A `voice\stt.py`, `wake_word.py`, `echo_filter.py`, `converse.py`, `ambient_awareness.py`, `services\audio.py`; Unity 18+ `app\listen.js`, `turn.js`, `latency.js`; the `_put_cuda_on_path()` fix from Unity 18+ `voice_server.py`.
- [ ] Rip "camera": C.O.R.A `services\camera.py`, `services\presence.py`, `cora_tools\screenshots.py`, `cora_tools\windows.py`; VibeRoller `web\calls.js`; Unity 18+ `app\sense.js`; U3E `.claude\tools\screen.py`.
- [ ] Rip "websearch": C.O.R.A `cora_tools\web.py` + `ai\tools\web.py`; U3E `.claude\tools\web.py`.
- [ ] Rip "playwrite": Backrooms `.local\twitch\tw.py`; U3E `.claude\tools\browser.py`; C.O.R.A `cora_tools\browser.py`; If-Only-I-Had-A-Brain `scripts\unity-say-live.mjs`.
- [ ] Rip "coding shit": `D:\CLI\unitycli.mjs` built-in tools + containment; C.O.R.A `cora_tools\code.py` + `code_parts\`, `cora_tools\files.py`, `cora_tools\system.py`; Backrooms `.local\autopilot\guards.py`; VibeRoller `run_code` + `pc_*` tools.
- [ ] Rip selfie / face identity: C.O.R.A `services\image_sidecar.py` + `cora_tools\image_gen.py` (IP-Adapter face lock); Backrooms `unity-face-sd.py`, `unity-cam.py`, `.claude\likeness\*`, `.studio-images\unity-reference.png`; U3E `serve\image-prompt.js`.
- [ ] Rip brain + loop: C.O.R.A `ai\dispatcher.py`, `ai\tools\_base.py`, `ai\history.py`, `ai\ollama.py`, `ai\settings.py`; Backrooms `.local\autopilot\autopilot.py`, `tools.py`, `gates.py`; VibeRoller `bridge\assistant.js`; `D:\CLI\unitycli.mjs` `MCPServer` class; `D:\Deviant 3D\src\agent\loop.ts`.
- [ ] Rip providers + gateway: VibeRoller `bridge\openai.js`, `providers.js`, `ai-node.js`, `ai-nodes.js`; `D:\Website2.0\old-site\PolliLibJS\` + `PolliLibPy\`; `D:\Unity Command\api_client.py`; `D:\weird\js\game\ollama.js`; `D:\Deviant 3D\src\agent\ollama.ts`.
- [ ] Rip MCP templates: Pollinations `pollinations_server.py` (Carbon / CLI copy); `D:\Unity Command\unity_mcp_server.py`; `D:\Carbon\.claude\bridge_mcp.py`; VibeRoller `assistant-tools-mcp.js`, `pc-tools-mcp.js`; `D:\AI v2.0\watchdog.js`.
- [ ] Rip memory + persona: `D:\weird\js\game\memory-embed.js`; `D:\CLI\persona-engine.mjs`, `knowledge.mjs`, `channels.mjs`; U3E `serve\persona.mjs`; Local Unity `server\server.mjs` style gate; newest `Unity1.txt`; persona-pack format from `D:\AI\personas`.
- [ ] Rip transport + UI + supervisor: If-Only-I-Had-A-Brain `remote-brain.js`, `brain-origin.js`, `ui\chat-panel.js`, `sensory-status.js`, `docs\WEBSOCKET.md`; Backrooms `persona-studio.cjs`, `stream-overlay.html`, `unity-overlay.py`; U3E `serve\launcher.mjs` + root `index.html`; `D:\weird\js\setup\detector.js`, `installer.js`; `D:\weird\js\ui\voice-queue.js`, `kokoro.js`, `kokoro-worker.js`; `D:\Deviant Thing v2\...\eqvideo.js`; `D:\Everything\Talk-To-Unity\AI\app.js`.

### M2 — Her voice and ears ("the Unity voice v2", "tts and stt", "talk back to you in real time")

- [ ] Stand up `sidecars/voice` from unity-voice-v2 with its own venv (torch + misaki 0.9.4), health check, and a phoneme/duration timeline returned alongside the WAV.
- [ ] Stand up `sidecars/speech` (faster-whisper) with wake word, echo filter and the CUDA DLL path fix.
- [ ] Browser mic path: VAD, pre-roll, barge-in, endpointing from `listen.js` / `turn.js`, streaming PCM to the hub.
- [ ] Hub voice pipeline: sentence queue, interrupt on barge-in, emotion + speech-act selection, playback events to the UI.

### M3 — Her face ("have a selfie", "like a real person on a video call", "you can see her lips move to the words she says", operator decision: "#D photo realistic photograph like vido")

- [ ] Reference portrait set: photoreal, face-locked (IP-Adapter) frontal portraits of her at 512 and 1024, neutral plus a few moods, from the existing `unity-reference.png` likeness. These are the identity the renderer drives.
- [ ] Evaluate and pick the Track A renderer on the 4070 Ti SUPER: LivePortrait-class renderer with an audio-to-motion front end (JoyVASA / Ditto class). Measure fps, latency from audio start to first frame, VRAM.
- [ ] `sidecars/face`: takes audio + phoneme timeline from the voice sidecar, emits frames at 25 fps; idle motion, blink, gaze toward camera when nobody is speaking; eye/lip retargeting knobs wired to the emotion state.
- [ ] Frame transport to the UI: WS binary frames locally, WebRTC video track for remote clients; UI shows it as a video-call feed with "what she is doing" status while tools run.
- [ ] Phoneme → mouth drive: use the voice model's per-phoneme durations as the primary lip signal where the renderer accepts it; audio-only drive for cloud TTS.
- [ ] Track B: generate idle video of her from the portrait (Pollinations video / local image-to-video), MuseTalk-class real-time mouth inpainting on top; compare realism and VRAM against Track A.
- [ ] VRAM scheduling in the launcher: unload SD while the face is live, cap unity-brain context, optional second machine for the face via the ai-node pattern.
- [ ] Record-to-video of the face feed + voice (eqvideo.js pattern).
- [ ] Track C (research, after A ships): 3D Gaussian-splat head fitted from generated video of her for camera moves and parallax.

### M4 — Her eyes ("camera", "you can see and she repsondes")

- [ ] Camera capture (browser `getUserMedia` and Python `camera.py`) and screen capture (`getDisplayMedia`, `screen.py`) feeding frames to the hub.
- [ ] Vision tool: local unity-brain vision / qwen-vl through Ollama, Pollinations image-to-text as cloud path.
- [ ] Ambient awareness loop with a friend threshold (presence, emotion, interjection).

### M5 — Her hands ("websearch and playwrite and coding shit all of it", "does things ytou telleher to do")

- [ ] Web search tool (DDG + Bing scrape + Playwright-rendered fallback) and web fetch tool.
- [ ] Browser tool over persistent CDP Chromium (open, click, fill, screenshot, run JS, read text).
- [ ] Code / files / shell tools with containment (blocked paths, writable roots, timeouts, danger levels needing confirmation).
- [ ] System tools (apps, windows, processes, media, notifications) and image generation tool with selfie mode.

### M6 — Any AI connected ("allows any ai connected to use it fully and completely all features we have ever built")

- [ ] One tool registry in the hub: name, description, JSON schema, handler, group, danger level.
- [ ] MCP stdio server over the registry.
- [ ] HTTP gateway: `/v1/chat/completions` and `/v1/messages` with SSE, running the loop against a chosen provider.
- [ ] Provider adapters: Ollama (unity-brain, native tools), Pollinations (BYOP), Anthropic, OpenAI-compatible, remote ai-node.
- [ ] Shared session so the face shows whatever brain is connected.

### M7 — Memory, persona, emotion

- [ ] Persona loader + style gate (one regeneration) + persona-pack format.
- [ ] Emotion state machine mapped to voice delivery and facial expression.
- [ ] Embedding memory (nomic-embed-text) + fact store + transcript with tool calls.

### M8 — Launcher and packaging

- [ ] Age gate at first launch ("fyi this is a 18plus application so chick can be full on 18+ type of lewdish"): adults-only confirmation before the UI loads, seeded from `D:\Deviant Thing v2\fractal_templater\web\assets\age-verification.js`; adult content allowed past the gate, minors never, anywhere.
- [ ] Supervisor: start / stop / health / deps for sidecars and hub, with the detector + installer onboarding pattern.
- [ ] Shells: always-on-top app window, OBS overlay, Android WebView.

---

## TOMBSTONES

_(none)_
