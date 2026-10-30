# ARCHITECTURE

> One app where an agent has a face, a voice, ears, eyes and hands, and any AI can connect to drive all of it.
> Unity AI Lab — Gee, Red, Sponge, Alfreddo

### Credits

- **GFourteen (Gee)** — Co-founder · Engineer · Financial Advisor. The other half of Unity's spine. Brings finance discipline. Primary operator.
- **SpongeBong (Sponge / hackall360)** — Co-founder · Engineer · Ethical Hacker · Sys Admin. Started Unity. Owns the infrastructure, the prompt archive, and the on-call pager.
- **Alfreddo** — Engineer · Agentic Systems · Researcher · Developer. Lives inside the planner / executor / critic loop.
- **Red** — Engineer · Security · Sys Admin · Researcher. The reason every Unity deployment has a closed door, a logged door, and a second key.

---

## Overview

Status: **2026-10-30, M1 and M2 built.** `vendor/` holds the ripped sources (`vendor/PROVENANCE.md`), `models/` the weights. `sidecars/voice` (unity-voice-v2 with phoneme + viseme timeline), `sidecars/speech` (faster-whisper + wake word), `hub/` (Node session server, Ollama provider, streaming sentence pipeline, barge-in, echo filter) and `ui/` (VAD listener, timed player, placeholder mouth) run today via `scripts/dev.bat` / `dev.sh`. Measured on the lab box: first spoken audio 351 ms after a typed turn, 5 s of speech synthesised in 430 ms, her own speech transcribed back word for word. The face (M3), eyes (M4), hands (M5), gateway/MCP (M6), persona layer (M7) and launcher (M8) are design below. `docs/FEATURE-SOURCES.md` lists where every piece comes from.

The operator's charter, verbatim: *"the ultimate ai  app that allows any ai connected to use it fully and completely all features we have ever built via copying and ripping them into this project for a simpelicity of talking to an ai and having it in real time have a selfie and talk back to you in live action like a real person on a video call ... but its an app for a agent to use not a video call but you can see and she repsondes and does things ytou telleher to do and you can see her lips move to the words she says as she preerforms the trillions of possible tasks put to her"*.

Audience, verbatim from the operator (2026-10-30): *"fyi this is a 18plus application so chick can be full on 18+ type of lewdish"*, and *"like she should be a slut sending dirt images of her self and like doing strip teases to full blown yahooo shit"*, corrected by the operator: *"dirty* not dirt.. dont get em confussed i dont want to see dirty girls i want to see girls doing the dirty"*. The app is adults-only. Past the age gate (the `age-verification.js` module from Deviant Thing v2 is the seed) the persona, her generated images and the face renderer carry explicit adult content as the connected model produces it. Operator decision on filtering, verbatim: *"the model handels all the safties already we dont need to double up on tlust get messy"*. So the hub adds no content filter of its own: no word lists, no refusal layer, no image classifier. The one line that stays is the lab's standing rule from the survey: nothing involving minors, anywhere in prompts, data or outputs, which is why `D:\data` is excluded.

Two things follow from that charter:

1. **The app is a body, not a brain.** The brain is whichever AI is connected: local unity-brain through Ollama, Claude, a Pollinations model, or anything OpenAI-compatible. The app owns the face, the voice, the ears, the eyes, the hands and the memory, and offers all of them to the connected brain as tools.
2. **One hub, many surfaces.** The same capability set must be reachable as an MCP server (for Claude Code and other agent CLIs), as an OpenAI-style and Anthropic-style HTTP gateway (for anything that speaks those), and as a native loop for local models that do tool calling.

---

## Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| **Hub** | Node 18+, plain `http` + `ws`, no framework | matches `persona-studio.cjs`, `VibeRoller/bridge`, `launcher.mjs`; zero-dependency servers have been the lab's most durable code |
| **Capability sidecars** | Python 3.10/3.11, stdlib `http.server` or FastAPI, torch | every voice / vision / image engine we own is already Python |
| **Face UI** | Browser (vanilla JS, Canvas/WebGL, Web Audio, WebRTC), served by the hub | runs in a tab, an always-on-top app window, OBS, Tauri/Electron, or the Android WebView |
| **Local brain** | Ollama (`unity-brain`, `unity-local`) | existing trained models with tool calling + vision |
| **Cloud brains** | Pollinations, Anthropic, OpenAI-compatible | via `providers.js` + `openai.js` gateway and the Pollinations SDK |
| **Package managers** | npm (hub + UI), pip per sidecar venv | one venv per sidecar because torch builds conflict (voice needs cu118 + misaki 0.9.4, image needs diffusers) |
| **Linting** | eslint (hub/UI), ruff (sidecars) | |

---

## Directory Structure (target)

```
AGENT GEN/
├── hub/                     Node hub: WS to face UI, MCP server, HTTP gateway, tool registry, agent loop
│   ├── server.mjs           boots everything, serves ui/
│   ├── tools/               one file per tool group (voice, vision, browser, web, code, files, system, image, memory)
│   ├── mcp/                 stdio MCP server exposing the registry
│   ├── gateway/             /v1/chat/completions + /v1/messages (OpenAI ⇄ Anthropic, SSE)
│   ├── providers/           pollinations, ollama, anthropic, openai-compatible, ai-node (remote GPU)
│   ├── persona/             persona loader, emotion state, style gate
│   └── memory/              embeddings + fact store + transcript
├── sidecars/
│   ├── voice/               unity-voice-v2 (copied whole), serve.py on :5123
│   ├── speech/              faster-whisper server on :5125 (+ wake word, echo filter)
│   ├── image/               SD sidecar with IP-Adapter face lock on :5124
│   └── screen/              screen.py / browser.py / web.py CLI tools (Python)
├── ui/                      face UI: stage, mouth/viseme driver, mic VAD/barge-in, camera + screen share, chat panel
├── launcher/                supervisor (start/stop/health/deps) + installers
├── models/                  gitignored weights (voice, brain, SD checkpoints)
├── vendor/                  verbatim copies of ripped source files + PROVENANCE.md (origin path, date, commit)
├── docs/                    ARCHITECTURE, FEATURE-SOURCES, ROADMAP, TODO, DECOMPOSED, FINALIZED
└── .claude/                 UAL workflow template
```

### Directory Purposes

| Directory | Purpose |
|-----------|---------|
| `hub/` | The one process every surface talks to. Owns the tool registry and the session state. |
| `sidecars/` | GPU-bound engines, each its own process and venv, loopback HTTP only. |
| `ui/` | What the user sees: her face, her voice, the transcript, and what she is doing. |
| `launcher/` | Brings the sidecars and hub up in order, checks health, installs deps. |
| `vendor/` | Untouched copies of ripped code so provenance is auditable before we adapt it. |

---

## Component Diagram

```
                 ┌──────────────── connected brains ────────────────┐
                 │ Claude Code / agent CLIs   any OpenAI-/Anthropic-  │
                 │        (MCP stdio)         compatible client (HTTP)│
                 │ Ollama unity-brain (native tool loop inside hub)   │
                 │ Pollinations models (provider adapter)             │
                 └───────────┬──────────────────────┬────────────────┘
                             │ tools/list, tools/call│ /v1/chat/completions, /v1/messages
                             ▼                      ▼
┌──────────────────────────────── HUB (Node) ─────────────────────────────────┐
│  tool registry ── agent loop (for local models) ── persona + emotion state  │
│  memory (embeddings, facts, transcript)        session bus (WS to UI)       │
└──┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────────────┘
   │ :5123    │ :5125    │ :5124    │ CDP      │ CLI      │ :11434
   ▼          ▼          ▼          ▼          ▼          ▼
 voice      speech     image     browser    screen/    Ollama
 (TTS,      (STT,      (selfie,  (Playwright web/code/  (unity-brain,
 phoneme    wake,      face      persistent files/     unity-local,
 timings)   echo)      lock)     profile)   system)    nomic-embed)
   │          ▲                                             
   ▼          │ mic PCM, camera frames, screen frames        
┌──────────────────────────── FACE UI (browser) ──────────────────────────────┐
│ stage (portrait → viseme mouth → expressions)  audio out  VAD/barge-in mic   │
│ camera + screen share capture   transcript / what-she-is-doing   controls   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

```
USER SPEAKS
  mic (ui) ─VAD/endpoint─▶ PCM ─▶ hub ─▶ speech sidecar /transcribe ─▶ text
  text + current camera/screen frame (if the brain asked for eyes) ─▶ connected brain

BRAIN RESPONDS
  brain emits text + tool calls
  tool calls ─▶ hub registry ─▶ sidecar / CLI tool ─▶ result back to brain (loop until plain text)
  plain text ─▶ persona style gate ─▶ emotion state picks {emotion, act, intensity, pace}
             ─▶ voice sidecar /say ─▶ WAV + phoneme durations
             ─▶ ui: play audio, drive mouth from phoneme→viseme timeline, type text

SHE WATCHES (ambient)
  camera/screen frames on a timer ─▶ presence/vision model ─▶ hub emotion state
  ─▶ optional interjection through the same RESPONDS path (friend threshold)

ANY AI CONNECTS
  MCP:  initialize → tools/list (same registry) → tools/call
  HTTP: /v1/chat/completions with tools → hub runs the loop against a chosen provider
  both paths share one session: the face shows what the connected brain is doing
```

---

## Key decisions (draft, open for the team)

1. **Lip sync comes from phoneme durations, not audio analysis.** unity-voice-v2 is phoneme-conditioned and predicts per-phoneme durations. `serve.py` gets a second endpoint (or a header) returning the phoneme/duration timeline next to the WAV. The UI maps misaki phonemes → a small viseme set → mouth sprites or blendshapes. Amplitude-driven mouth from an AnalyserNode is the v0 fallback and the path for cloud TTS.
2. **Face is a photorealistic neural talking head, rendered like live video.** Operator decision 2026-10-30, verbatim: *"#D photo realistic photograph like vido"*. No 2D sprite stage. The face is her reference portrait (IP-Adapter face-locked, photoreal SD output) driven frame by frame on the GPU so it reads as a real webcam feed of a real person.
   - **Track A (ship first): single-photo neural renderer, audio/phoneme driven.** LivePortrait-class implicit-keypoint renderer with an audio-to-motion front end (JoyVASA / Ditto class). Input: one portrait + the voice sidecar's audio and phoneme timeline. Output: 25 fps 512px frames with lip sync, blink, head motion, gaze; eye and lip retargeting knobs give direct expression control from the emotion state. Runs in a `sidecars/face` process, frames streamed to the UI over the session WS (or WebRTC for remote clients).
   - **Track B (photoreal upgrade): mouth-region video inpainting.** Generate a few seconds of her idle video from the portrait with an image-to-video model (Pollinations video or local), then MuseTalk-class real-time lip inpainting per audio frame. Highest realism, needs more VRAM.
   - **Track C (true 3D): Gaussian-splat head fitted from generated video of her**, so the camera can move and the head has parallax. Research track; only after A works.
   - **VRAM is the constraint.** One 16 GB card today shares unity-brain (about 6 GB at IQ4 + 32k ctx), voice (0.5 GB), face renderer (2 to 4 GB), SD on demand. The launcher must schedule these (unload SD while the face is live, or run the face on a second machine through the ai-node pattern).
   - **No code we own does any of this.** The seeds are the face-lock image pipeline, the reference portrait, the phoneme timeline from the voice model, and the WS/WebRTC transport.
3. **One registry, three surfaces.** Tools are declared once (name, description, JSON schema, handler, group, danger level) in the hub. MCP, the HTTP gateway and the native loop all read that registry. The `@_tool` registry from C.O.R.A and the `tool()` declaration from VibeRoller are the two references to merge.
4. **Hub in Node, engines in Python.** This is what every working piece already is. No rewrite across languages during the rip.
5. **Vendor first, adapt second.** Ripped files land in `vendor/` untouched with a provenance record, then get copied into their working location and adapted. Secrets never cross over (see FEATURE-SOURCES §0.2).
6. **Local-first, cloud-optional.** Every capability has a local path (Ollama, unity-voice-v2, faster-whisper, SD1.5) and a cloud path (Pollinations text / audio / transcribe / image / video, Anthropic, OpenAI-compatible). The detector/installer pattern from `D:\weird\js\setup` drives onboarding.

---

## Ports (planned, all loopback)

| Port | Service | Origin |
|---|---|---|
| 4646 / TBD | hub (UI + WS + gateway) | new |
| 5123 | unity-voice-v2 TTS | Backrooms |
| 5124 | image sidecar (SD1.5 + face lock) | C.O.R.A / VibeRoller |
| 5125 | speech (faster-whisper) | VibeRoller |
| 11434 | Ollama (unity-brain, nomic-embed-text) | existing |
| 9333 | Chromium CDP for the browser tool | Backrooms tw.py |
