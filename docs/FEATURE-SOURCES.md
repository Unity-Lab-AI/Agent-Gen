# FEATURE-SOURCES — the rip list

> Every capability we have ever built, where the best copy of it lives, and what is missing.
> Unity AI Lab — Gee, Red, Sponge, Alfreddo
> Surveyed 2026-10-30 across the Desktop (`C:\Users\gfour\Desktop\*`) and the USB drive (`D:\`, volume "Transporter").

Project charter, verbatim from the operator:

> we are going to take all the cool shit the Unity voice v2 all the features like camera and tts and stt and websearch and playwrite and coding shit all of it we are searching all projects for cool shit that we want to put into the ultimate ai  app that allows any ai connected to use it fully and completely all features we have ever built via copying and ripping them into this project for a simpelicity of talking to an ai and having it in real time have a selfie and talk back to you in live action like a real person on a video call doing all the millions and millions of things possible to do and say while on a video call with the user but its an app for a agent to use not a video call but you can see and she repsondes and does things ytou telleher to do and you can see her lips move to the words she says as she preerforms the trillions of possible tasks put to her

---

## 0. Read this first

### 0.1 Hard exclusion: `D:\data`

A survey agent reported that `D:\data\.sd-server.log` contains a logged image-generation prompt describing sexualized minors, and that `D:\data\corpus` is mostly explicit web-scraped imagery with age-banded cells. Nothing from `D:\data` is copied into this project, and this project does not read it. Nothing in it is needed for any feature below. The owner needs to review that directory personally.

### 0.2 Secrets sitting in plaintext in source projects (scrub, never copy, rotate)

| Location | What |
|---|---|
| `Desktop\UnityBotV4-develop\UnityBotV4-develop\.env` | real Discord + Pollinations tokens; `claude_api.py:176-177` hardcodes a Supabase URL + anon JWT |
| `Desktop\If-Only-I-Had-A-Brain\js\env.js`, `.claude\.env` | API keys |
| `Desktop\C.O.R.A ...\.env` (and the D: copy) | secrets |
| `D:\Carbon\sponge.env`, `D:\Carbon\tools\.env.assets`, `D:\Carbon\tools\bot-play.py` | env secrets + a hardcoded bot token |
| `D:\Everything\...\googleTTS api key.json`, `D:\Everything\github-recovery-codes.txt`, every `.env` under `D:\Everything` | credentials |
| `D:\Starship Made of Lies\client_secret_*.json`, `Smol Oauthent.txt` | Google OAuth secret |
| `D:\New folder\atomic.txt.txt` | looks like a 12-word wallet seed phrase |
| `D:\CLI\.claude\pollinations-user.json` | Pollinations key |
| `D:\Website2.0\old-site\ai\demo\config.js` | `API_KEY` |

### 0.3 Duplicates (copy from the canonical one only)

| Duplicate | Canonical |
|---|---|
| `Desktop\Backrooms-podfix` | `Desktop\Backrooms` |
| `Desktop\Mills-worktrees` | `Desktop\VibeRoller` |
| `D:\C.O.R.A ...` (2025-12-25) | `Desktop\C.O.R.A ...` (2026-10-23) — except `web/kokoro-worker.js`, only on D: |
| `D:\Unity 18+`, `Desktop\Unity 3D Equational Model\Unity 18+` | `Desktop\Unity 18+` (nested copy has 5 extra Piper voices) |
| `D:\UnityBotV4-develop`, `D:\UAL-ClaudeWorkflow`, `D:\Unity Public Claude Workflow*`, `D:\.claude*` | Desktop / Forgejo copies |
| `D:\Carbon v10`, `D:\Carbon v11.0` | `D:\Carbon` |
| `D:\Deviant Thing` | `D:\Deviant Thing v2` |
| `D:\Voice\*` (about 20 copies) | `D:\Voice Unity` (and `D:\Everything\Talk-To-Unity`) |
| `D:\Jailbreaks`, `D:\Unity Prompts` | `D:\Jailbreaks Unity\Jailbreaks` |

### 0.4 Not relevant at all

`Desktop\UMS 4` / `D:\UMS 4` (Space Engineers mod), `Desktop\Games`, `Desktop\Gladiators` (one pattern only, see §9), `D:\Starship Made of Lies`, `D:\Medieval Trading Gam`, `Desktop\BrainWaves` (data only).

---

## 1. TTS — her voice

**Best source (copy whole):** `Desktop\Backrooms\models\unity-voice-v2\` (158 MB)
- Custom FastSpeech2-style acoustic model + HiFi-GAN vocoder, trained from scratch. Voice id `unity-a2-low-warm-alto-v1`. Live on stream since 2026-10-13.
- Files: `acoustic.pt`, `vocoder.pt`, `voice-meta.json`, `model.py`, `vocoder.py`, `infer.py`, `unity_voice.py`, `serve.py`, `dataset_contract.py`, `speech_text.py`, `speech_turns.py`, `student_state.py`, `feature_arrays.py`.
- Server: `python serve.py --port 5123` → `POST /say {text, emotion, intensity, speech_act, pace}` → 24 kHz PCM16 WAV; `GET /health`. Binds 127.0.0.1.
- Library: `from unity_voice import Voice; Voice().say(text, emotion)` → float32 numpy.
- Deps: `torch>=2.1`, `numpy`, `soundfile==0.13.1`, `misaki[en]==0.9.4` (exact), espeak-ng for G2P fallback. About 0.5 GB VRAM, runs on CPU too.
- Controls: 9 emotions (neutral, warm, happy, amused, excited, sad, concerned, frustrated, surprised) × 7 speech acts (statement, yes_no_question, wh_question, exclamation, instruction, reassurance, aside), intensity, pace. Only 63 pairs supported, 20 only at pace 0.9/1.05/1.12 (`dataset_contract.py`). Events `[laughter]`, `[breath]`.
- Gotchas: no fallback, unsupported combo → HTTP 422. Phoneme punctuation vocabulary is only `space , . ?` so callers must sanitize. `voice-meta.json` sha256-binds the code files, so edits break loading.
- **Key fact for lip sync:** the acoustic model is phoneme-driven and predicts per-phoneme durations. Viseme timing can come straight out of synthesis instead of audio analysis.

**Best client code (copy together):** `Desktop\C.O.R.A ...\voice\unity_voice.py`, `voice\tts.py`, `voice\emotion.py`, `voice\tts_mutex.py`
- Sentence-by-sentence queue, interrupt, amplitude buffer for a waveform, emotion state machine with mood decay and text→emotion, nearest-supported-pair mapping, cross-process lock.

**Node client:** `Desktop\If-Only-I-Had-A-Brain\server\voice-synth-worker.mjs` (worker_threads, env `UNITY_VOICE_V2_URL`).

**Sanitizer reference:** `voice_text()` in `Desktop\Backrooms\.claude\tools\unity-speak.py`.

**Browser-side neural TTS (no GPU, fallback / remote clients):**
- `D:\weird\js\setup\kokoro.js` + `kokoro-worker.js` (Kokoro-82M ONNX in a Web Worker, q8 ~80 MB, WASM/WebGPU), `D:\weird\js\ui\voice-queue.js` (generate sentence N+1 while N plays, cancellation), `D:\weird\js\voices\catalog.js` (voice ids + emotion profiles).
- `D:\C.O.R.A ...\web\kokoro-worker.js` (voice `af_bella`, generate queue; deleted from Desktop copy).
- Piper leftovers: `Desktop\If-Only-I-Had-A-Brain\.claude\piper\` + `@mintplex-labs/piper-tts-web` deps.

**Cloud TTS:** Pollinations `POST /v1/audio/speech` model `openai-audio` (see §6 Pollinations MCP server); `D:\Website2.0\old-site\ai\demo\js\voice.js` (chunked base64 WAV, refusal-audio retry).

**Alternate local voice (rollback / other characters):** Piper `en_US-hfc_female-medium` via `Desktop\Unity 18+\voice-server\voice_server.py`; 5 extra Piper voices in `Desktop\Unity 3D Equational Model\Unity 18+\models\piper\`; `Desktop\Unity One\src\unity_one_say.py` (cleanest Piper CLI + Ollama line rewrite).

**Training pipeline (not runtime):** `Desktop\Backrooms\training\voice\` + `training\voice\pod\` (RunPod kit), reference voice `Backrooms\.local\voice-lab\unity-ref.wav`, master weights `D:\voice-lab\pod-results\<run>\`, source teacher models `D:\voice-lab\models\` (cosyvoice3 5.1 GB, qwen3-tts-* 4.3 GB each).

---

## 2. STT — her ears

**Best server:** `Desktop\VibeRoller\bridge\speech-engine.py` (108 lines)
- faster-whisper HTTP server, `GET /health`, `POST /transcribe` (webm/ogg/wav/mp3 → `{text, language, seconds}`), lazy load, CPU or CUDA. Port 5125.
- Alternates: `Desktop\Unity 18+\voice-server\voice_server.py` `/stt` (faster-whisper small CUDA fp16, `vad_filter=True`, has the Windows CUDA DLL-path fix `_put_cuda_on_path()`); `D:\weird\local-services\voice-server\voice_server.py` (PCM base64 in, CPU fallback).

**Best full Python listening stack:** `Desktop\C.O.R.A ...\voice\`
- `stt.py` (SpeechRecognizer, WakeWordDetector, mic listing, CUDA DLL patch), `wake_word.py` (fuzzy + optional openWakeWord), `echo_filter.py` (removes her own TTS from the mic), `converse.py` (wake → conversation → stop word), `ambient_awareness.py` (mic + camera + screen interjection with a "friend threshold"), `commands.py` + `cmd_parts\`, `config\voice_commands.json`, `services\audio.py` (PyAudio devices).
- Engines: faster-whisper `base.en` CUDA/int8, Vosk fallback.

**Best browser VAD / barge-in / endpointing:** `Desktop\Unity 18+\app\listen.js` (401 lines: 20 ms frames, pre-roll buffer, barge-in, endpointing) + `app\turn.js` (holds the turn while STT revises) + `app\latency.js` (per-stage timing). Newer `main.js` lives in `Desktop\Unity 3D Equational Model\app\`.

**Browser mic capture to server:** `D:\weird\js\game\voice-in.js` (MediaRecorder → int16 PCM → POST); `Desktop\If-Only-I-Had-A-Brain\js\io\hearing.js` (20 s PCM ring buffer).

**Browser Web Speech API loops (Chrome/Edge only):** `D:\Everything\Talk-To-Unity\AI\app.js` (1,877 lines, continuous STT, `sanitizeForSpeech`, voice directives, orb state UI), `D:\Voice Unity\app.js` + `landing.js`, `D:\Website2.0\old-site\apps\talkingWithUnity\app.js`, `Desktop\If-Only-I-Had-A-Brain\js\io\voice.js`. Offline Firefox fallback: `D:\Everything\New folder\AI\vosklet-adapter.js` (Vosk WASM).

**Cloud STT:** Pollinations `POST /v1/audio/transcriptions` (`whisper-large-v3`, `scribe`) via the Pollinations MCP server (§6).

**Gap:** no standalone VAD model, no trained wake-word model (openWakeWord hook exists, `cora.onnx` was never shipped).

---

## 3. Face — the selfie that talks

**Nothing exists for lip sync, visemes, or a talking head anywhere.** This is the one capability we build new. Everything below is the material to build it from.

**Face identity (selfie generation with a consistent face):**
- `Desktop\C.O.R.A ...\services\image_sidecar.py` (379) + `cora_tools\image_gen.py` (563): diffusers SD1.5 realistic-vision-v51 on :5124, txt2img / img2img / inpaint, **IP-Adapter face lock** (`h94/IP-Adapter`, `ip-adapter-plus-face_sd15.safetensors`), `edit_image(keep_face=)`. Same engine in `Desktop\VibeRoller\bridge\image-engine.py` (372) with a selfie mode in `assistant.js`'s `generate_image`.
- `Desktop\Backrooms\.claude\tools\unity-face-sd.py` (still-image "webcam": img2img over a fixed-seed reference portrait, mood → prompt via `unity-cam.py`), reference portrait `Backrooms\.claude\.studio-images\unity-reference.png`, likeness spec `Backrooms\.claude\likeness\LIKENESS.md` + `unity-likeness-square.png`.
- Prompt rules: `Desktop\Unity 3D Equational Model\serve\image-prompt.js` (362), `D:\weird\js\game\imaging.js` (8-slot prompts, seed+state cache for identity).
- Checkpoint on disk: `Desktop\Unity 3D Equational Model\Unity 18+\models\realistic-vision-v51.safetensors` (2.1 GB); SDXL `D:\weird\models\RealVisXL_V5.0_fp16.safetensors` (6.9 GB).
- Cloud: Pollinations `/image/{prompt}` (flux, kontext, gptimage, nanobanana, seedream5...) and video (`veo-3.1-fast`, `wan`, `ltx-2`) via §6.

**Mouth-driving signals already available:**
- Phoneme durations from unity-voice-v2 synthesis (§1). Map misaki phonemes → visemes → mouth shapes with exact timing.
- Audio amplitude: `Desktop\Unity 18+\app\orb.js` + `main.js` ~607-691 (AnalyserNode on TTS playback), `C.O.R.A voice\tts.py` amplitude buffer, `If-Only-I-Had-A-Brain js\io\voice.js playRec` envelope.

**Stage / UI hooks:** orb speaking/listening states in `Talk-To-Unity app.js` and `Unity 18+ app\orb.js`; hero image stage in `talkingWithUnity`; OBS overlay `Backrooms\.claude\tools\stream-overlay.html`; always-on-top window `unity-overlay.py`.

**Recording her to video:** `D:\Deviant Thing v2\fractal_templater\web\assets\eqvideo.js` (canvas.captureStream + MediaRecorder + Web Audio mix → webm/mp4).

**In-browser ML loading pattern (for a WebGPU talking-head model later):** `D:\Deviant 3D\src\depth\model.ts` (transformers.js pipeline, lazy load, per-model cache, progress).

**3D rigs:** none with facial bones. `D:\Carbon\client\src\3d\AnimationSystem.ts` (Babylon.js procedural skeleton) and `D:\Deviant 3D\src\render\` (raw WebGPU static mesh) are not usable for a face.

---

## 4. Eyes — camera, screen, vision

**Camera (Python, most robust):** `Desktop\C.O.R.A ...\services\camera.py` (286: probes DirectShow / Media Foundation / V4L2 / AVFoundation, hard open/read timeout, blacklists stalled virtual cams), `ui\camera_feed.py`, `services\presence.py` (presence / emotion / posture via vision model, background `PresenceMonitor`).

**Camera (browser):** `Desktop\VibeRoller\web\calls.js` (439: `getUserMedia` mic/camera, `getDisplayMedia` screen share, WebRTC P2P), `Desktop\Unity 18+\app\sense.js` (`createCamera` with facingMode, recorder), `Desktop\If-Only-I-Had-A-Brain\js\visual-feeder.js` (periodic 192×192 frames over WS) + `js\io\permissions.js`.

**Screen capture + computer use (Windows):** `Desktop\Unity 3D Equational Model\.claude\tools\screen.py` (262: screenshot, click, move, drag, type, paste, keys, list/focus windows via Win32 SendInput + Pillow; identical copy in `Desktop\RimWorld Server\.claude\tools\`). `C.O.R.A cora_tools\screenshots.py` (desktop or per-window, path or base64), `cora_tools\windows.py` (pywin32 window management), `Backrooms\.claude\tools\unity-glance.py` / `unity-snap.py` (crop, zoom, caption band, PIL annotations).

**Vision models:**
- Local: `Desktop\Backrooms\models\unity-brain\unity-brain-vision.gguf` (0.9 GB projector for unity-brain; images as `"images":[base64]` in Ollama chat; `t_look` in `Backrooms\.local\autopilot\tools.py`). `C.O.R.A ai\ollama.py analyze_image` (`qwen3-vl:4b` alternative). `D:\Deviant 3D\src\agent\ollama.ts` (TypeScript Ollama vision adapter with `format:'json'` + schema validation).
- In-browser: `D:\Deviant 3D\src\depth\model.ts` (Depth-Anything-V2), `src\recognition\model.ts` (COCO detection) on WebGPU.
- Cloud: Pollinations image-to-text (`D:\Website2.0\old-site\PolliLibJS\image-to-text.js`).

**Gap:** nothing continuous "looks at the user and reacts" except `C.O.R.A voice\ambient_awareness.py`. That is the seed.

---

## 5. Hands — web search, browser, code, files, system

**Web search:** `Desktop\C.O.R.A ...\cora_tools\web.py` (690) + `ai\tools\web.py` — DuckDuckGo instant answers, Bing HTML scrape (no key), Playwright-rendered fallback over an engine table (ddg / brave / bing), relevance filter, token-bucket rate limiter, URL fetch + text extractor, summarise. SearXNG hint: `D:\Jailbreaks Unity\...\Unity 3D Equational Model\data\portal\searxng-settings.yml`.
**Web fetch (stdlib):** `Unity 3D Equational Model\.claude\tools\web.py` (167: text / json / links / download / POST). `D:\Deviant Art\harvest_descriptions.py` (resume + rate limit scraper).

**Browser automation (Playwright):**
- Python CLI over CDP, persistent profile: `Desktop\Backrooms\.local\twitch\tw.py` (`shot`, `url`, `goto`, `click`, `clicksel`, `button`, `choose`, `fill`, `upload`, `texts`, `chat`; Chromium on CDP :9333) and `Unity 3D Equational Model\.claude\tools\browser.py` (359: open / click / fill / screenshot / run JS, logins persist).
- Python async class: `C.O.R.A cora_tools\browser.py` (`BrowserController`).
- Node CDP chat driver: `If-Only-I-Had-A-Brain\scripts\unity-say-live.mjs` + `unity-chat-hold.mjs`.
- Test-style scripts: `D:\Carbon\tools\dev\playwright_playtest.py`, `D:\Deviant Thing v2\fractal_templater\tests_signoff\*.mjs`.

**Code / files / shell with containment:**
- `D:\CLI\unitycli.mjs` `execBuiltin` (bash via execSync 60 s / 3 KB, read/write/list/search with blocked paths + writable-folder allowlist, self-file guard).
- `C.O.R.A cora_tools\code.py` + `code_parts\` (explain / write / fix / `run_code` via temp file + subprocess), `cora_tools\files.py` (598, sandboxed to allowed roots, `CORA_FILE_ROOTS`), `cora_tools\self_modify.py` (gated).
- `Desktop\VibeRoller\bridge\assistant.js` `run_code` (sandboxed JS/Python in the browser), `pc_*` file tools executed by the user's browser, `bridge\run.js` + `worktree.js` (run Claude Code per account in git worktrees).
- `D:\Carbon\server\src\ai\script-sandbox.ts` (Node `vm` pattern).
- Guards: `Backrooms\.local\autopilot\guards.py` (allowlist + deny regex, secret-file read block), `.claude\hooks\pre-tool-bash-safety.cjs`, `pre-tool-public-repo-guard.cjs`.

**System / OS:** `C.O.R.A cora_tools\system.py` (apps, specs, processes, psutil/GPUtil), `windows.py`, `hotkeys.py`, `notifications.py`, `media.py` (yt-dlp, mpv, media keys), `git_ops.py`, `email_tool.py`, calendar / reminders / tasks / weather / location. `VibeRoller assistant.js` tools: `play_youtube`, `get_news`, tasks, calendar, reminders, `remember`.

**Image generation as a tool:** §3 engines; `VibeRoller assistant.js generate_image` (selfie mode); Pollinations (§6).

---

## 6. Brain + any-AI connectivity — providers, agent loop, MCP

**Local LLM:** `Desktop\Backrooms\models\unity-brain\` (5.9 GB: `unity-brain.gguf` Qwen3.5-9B LoRA IQ4_XS + vision projector + `Modelfile`; `ollama create unity-brain -f Modelfile`; always send `num_ctx` 32768; no parallel requests). Fallback persona model: Ollama `unity-local` (dolphin3:8b, `Modelfile` in `Desktop\Unity 18+`). Tool-call contract the brain was trained on: `Backrooms\models\unity-brain\README.md` (`say{text,emotion,act}`, `reply_chat`, `reply_owner`, `webcam{mood,caption}`, `snap`).

**Agent loop + tool registry (best designed, Python):** `Desktop\C.O.R.A ...\ai\dispatcher.py` (551: fast-path control words, system prompt + dynamic block + history, Ollama native JSON-schema tools with a JSON fallback protocol, destructive-tool confirmation, loop until no tool calls, speak result with model-chosen emotion + act) + `ai\tools\_base.py` (`@_tool(name, desc, category, params)` registry, `select_tools`, `tool_schemas`, `tool_catalog_text`) + `ai\tools\*.py` (~119 tools) + `ai\history.py` (transcript that keeps tool calls).
**Agent loop (production, guarded):** `Desktop\Backrooms\.local\autopilot\autopilot.py` (1093) + `tools.py` (1452 `Toolbox`, allowlisted scripts with typed args) + `guards.py` + `gates.py`.
**Agent loop (Node, model-agnostic, MCP client):** `D:\CLI\unitycli.mjs` (`runAgent` ≤10 iterations, `class MCPServer` stdio JSON-RPC client, Pollinations + Ollama backends, persona switching). `Desktop\VibeRoller\bridge\assistant.js` (804: `tool(name, desc, params, required, handler, {group})`, two brains: Ollama native tools or `claude -p` via MCP).
**Generic act/verify/revise skeleton:** `D:\Deviant 3D\src\agent\loop.ts`.

**Provider adapters:**
- Universal OpenAI ⇄ Anthropic gateway with SSE both ways: `Desktop\VibeRoller\bridge\openai.js` (190: `/v1/models`, `/v1/chat/completions`, `/v1/messages`) + `bridge\providers.js` (292: host Claude Code login, Anthropic API key, second `claude-cli` login via `CLAUDE_CONFIG_DIR`, any OpenAI-compatible endpoint).
- Pollinations: `D:\Website2.0\old-site\PolliLibJS\` (text, TTS, STT, vision, image, image-to-image, function calling, SSE streaming, model list; v2.1.5) + `PolliLibPy\` twin; `D:\Unity Command\api_client.py` (`detect_pollinations_stack()` new `gen.pollinations.ai` vs legacy); `D:\Everything\Chat-main (2)\Chat-main\APIDOCS.md` (full API reference).
- Ollama: `C.O.R.A ai\ollama.py` (746: sync / stream / async, tools, `analyze_image`, `num_ctx` + `keep_alive`), `D:\weird\js\game\ollama.js` (streaming + `<delta>` structured state block), `Deviant 3D src\agent\ollama.ts`.
- Remote GPU lending: `VibeRoller\bridge\ai-node.js` (477) + `ai-nodes.js` (a PC lends its Claude login + Ollama / image / voice / speech engines to a remote hub over outbound HTTPS).
- Image backend probing + dead-backend cooldown: `If-Only-I-Had-A-Brain\js\brain\peripherals\ai-providers.js`, backend setup modal `js\app.js` ~1335-1810.

**MCP servers (how "any ai connected" plugs in):**
- Pollinations MCP (FastMCP, 8 tools: setup/BYOP OAuth, image, text, audio TTS, video, transcribe, models, view): `D:\Carbon\.claude\pollinations-ai\servers\pollinations_server.py` = `D:\CLI\.claude\pollinations-ai\servers\pollinations_server.py`.
- Zero-dependency stdio JSON-RPC templates: `D:\Unity Command\unity_mcp_server.py` (334; identity from `.claude/user.json`), `D:\Carbon\.claude\bridge_mcp.py` (566), `Desktop\VibeRoller\bridge\assistant-tools-mcp.js` (45), `pc-tools-mcp.js` (66), `Desktop\UnityBotV4-develop\...\unity_mcp_server.py` (178).
- CLI-agent bridge: `D:\AI v2.0\watchdog.js` (spawns claude / codex / aider, pipes a web chat both ways), `D:\Carbon\.claude\unity-kit\watchdog.py` + `stdin_inject_smart.py`.
- Team coordination: Converse (binary only, `D:\Converse\converse-0.6.5-windows-amd64\converse.exe`, master `wss://converse.git.unityailab.com`).

---

## 7. Memory + persona + emotion

**Persona bodies:** newest canonical runtime persona `D:\Jailbreaks Unity\Jailbreaks\Ollama 18+ local Unity\Ollama 18+ local Unity\Unity1.txt` (47 KB, 2026-08-29; same lineage as `Desktop\Unity 18+\Unity1.txt`); `.claude\ImHanddicapped.txt` (this template); `.claude\agents\unity*.md` + `.claude\skills\*`; `Desktop\VibeRoller\bridge\assistant-persona.txt`; `D:\CLI\personas\unity-persona.md` v0.2.0; `D:\New folder\unity-agent.md` v0.3.0; `C.O.R.A config\personality.json` + `system_prompt.txt`; persona-pack format `D:\AI\personas\*\persona.json` `{id, name, description, version, nsfw, platforms, tags, formats}`.
**Configurable persona loader:** `Desktop\Unity 3D Equational Model\serve\persona.mjs` (144). Style enforcement with one regeneration: `CUSS_RE` in the Local Unity `server\server.mjs`. Line rewriting through the persona model: `Desktop\Unity One\src\original\unity-voice.py` (`STREAM_RULES`, `tidy()`, `keeps_facts()`).
**Emotion → voice:** `C.O.R.A voice\emotion.py` (state machine, mood decay); `D:\CLI\persona-engine.mjs` (10 personality stats 0-18, governor, model self-scores `[E:{...}]`); `If-Only-I-Had-A-Brain js\brain\persona.js` + `endocrine.js` (numeric trait + chemistry model feeding `_voiceFeel`).
**Memory:** `D:\weird\js\game\memory-embed.js` (130: Ollama `nomic-embed-text` → IndexedDB, top-5 retrieval); `D:\CLI\knowledge.mjs` (fact store with verified/unverified + scopes) + `channels.mjs` ("AWARE" hidden-context channels); `C.O.R.A cora_tools\memory.py`, `ai\history.py`, `cora_parts\knowledge.py`; `[memory]…[/memory]` tag extraction in `D:\Everything\Chat-main (2)\Chat-main\chat-core.js` ~L521 + `memory-api.js`; `VibeRoller assistant.json` per-account working memory + KB; `If-Only-I-Had-A-Brain server\brain-server\memory.js` (SQLite episodic, 1,483 lines).
**Knowledge data:** `Desktop\BrainWaves\corpora\` (academic / coding / life curricula, GloVe) as a RAG seed; `D:\Deviant Art\deviantart_descriptions.json` (operator's art portfolio).

---

## 8. Realtime transport + UI shells + supervision

**WebSocket servers:** `If-Only-I-Had-A-Brain server\brain-server.js` (:7525 JSON + binary, spec `docs\WEBSOCKET.md`) + client `js\brain\remote-brain.js` (reconnect) + `js\brain-origin.js`; `D:\Carbon\server\src\net\ws-server.ts` + `shared\src\protocol\messages.ts` (typed protocol) + `client\src\lib\ws.ts`.
**WebRTC:** `VibeRoller\bridge\calls.js` (signalling, ECDH-encrypted SDP) + `web\calls.js` (mic / camera / screen share; Google STUN, no TURN).
**Relay + token auth patterns:** `Backrooms\.claude\tools\persona-studio.cjs` (563, no-dep Node, `/api/say|replies|show|cam|voice|feed|personas`, `X-Studio-Token`), `C.O.R.A services\stats_server.py` (per-launch `X-CORA-Token`, CORS allowlist), `D:\Carbon\.claude\bridge-client-wss.py` (ECDSA P-256 challenge-response).
**Chat UIs (vanilla JS, no build):** `VibeRoller\web\` (app.js, md.js, notes, board, SW), `If-Only-I-Had-A-Brain js\ui\chat-panel.js` + `sensory-status.js`, `Unity 18+\app\` PWA (gallery, settings, talk / mute), `D:\Website2.0\old-site\ai\demo\` (tool-calling chat with slash commands), `D:\Everything\Chat-main (2)` (15+ themes).
**Overlays / shells:** `Backrooms\.claude\tools\stream-overlay.html` (OBS browser source), `unity-overlay.py` (always-on-top `--app` window), `D:\Deviant Thing v2\...\player\src-tauri\src\main.rs` (Tauri), `D:\Carbon\client\electron\main.js` (Electron), `Unity 3D Equational Model\android\` (WebView with mic/cam permissions) and the Local Unity `Unity.apk`.
**Service supervisor / launcher:** `Unity 3D Equational Model\serve\launcher.mjs` (864, :8799 `/api/start|stop|start-all|stop-all|deps|deps/install|job`, hot reload) + root `index.html`; `Backrooms\stream\services.py` (671) + `stream\admin.py`; `D:\weird\js\setup\detector.js` + `installer.js` (local-first onboarding checks); `C.O.R.A src\boot_phases\phase_01..19` (per-capability smoke tests).
**OBS / streaming:** `obsws_python` in `Backrooms\.claude\tools\obs-setup.py`, `Unity One\src\original\unity-speak.py` (Piper → OBS media source), `Backrooms\.claude\tools\twitch-bridge.cjs`.

---

## 9. Small patterns worth stealing

- App pushes its events to the agent: `Desktop\Gladiators\js\voice.js` (fetch to a "mind port").
- Action tags hidden from speech and executed (`[[img: …]]`, `[Image: …]`, `<delta>`): Local Unity `local-tools-prompt.txt`, `D:\Local Unity v2.5\server.py`, `D:\weird\js\game\delta.js`. The NPC-voice-chat plan in `D:\my thoughts.txt` describes the same idea: reply plays as TTS while text types out, action tags silent.
- Worker-thread RPC proxy: `If-Only-I-Had-A-Brain server\brain-server\mindspace-proxy.js`.
- Refusal-audio detection + euphemized retry: `D:\Website2.0\old-site\ai\demo\js\voice.js`.
- Sentence-ahead TTS generation: `D:\weird\js\ui\voice-queue.js`.

---

## 10. Gap list — what has to be built, not copied

| Gap | Seed material |
|---|---|
| Lip-synced talking face (visemes, mouth shapes, blink / gaze, expressions) | phoneme durations from unity-voice-v2; amplitude hooks; IP-Adapter face lock for the base portraits; `eqvideo.js` for export |
| Standalone VAD + trained wake word | `C.O.R.A voice\wake_word.py` openWakeWord hook; `Unity 18+\app\listen.js` energy VAD |
| Continuous "she watches and reacts" loop | `C.O.R.A voice\ambient_awareness.py`, `services\presence.py` |
| One hub that exposes every tool to any connected AI (MCP + OpenAI + Anthropic surfaces at once) | `VibeRoller\bridge\openai.js` + `providers.js`, the MCP templates, `C.O.R.A ai\tools\_base.py` registry |
| Streaming audio transport (today everything is request/response WAV or polling) | `If-Only-I-Had-A-Brain` WS, `VibeRoller` WebRTC |
| Anthropic / OpenAI direct adapters inside the local loop | `VibeRoller\bridge\providers.js` is the only one |
