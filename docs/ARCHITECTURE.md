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

Status: **2026-10-30, M1 and M2 built.** `vendor/` holds the ripped sources (`vendor/PROVENANCE.md`), `models/` the weights. `sidecars/voice` (unity-voice-v2 with phoneme + viseme timeline), `sidecars/speech` (faster-whisper + wake word), `hub/` (Node session server, Ollama provider, streaming sentence pipeline, barge-in, echo filter) and `ui/` (VAD listener, timed player, placeholder mouth) run today via `scripts/dev.bat` / `dev.sh`. Measured on the lab box: first spoken audio 351 ms after a typed turn, 5 s of speech synthesised in 430 ms, her own speech transcribed back word for word. M3 is in progress: Track A renderer is **Ditto** (`third_party/ditto-talkinghead`, weights in `models/ditto`), wrapped live by `sidecars/face/server.py` (MJPEG at 25 fps, `/speak` returns the lead the UI delays audio by, live emotion and pose), hub and UI already wired to it; first run and measurements pending on the operator (`scripts\face-smoke.bat`). Eyes (M4), hands (M5), gateway/MCP (M6), persona layer (M7) and launcher (M8) are design below. `docs/FEATURE-SOURCES.md` lists where every piece comes from.

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
| **App shell** | Electron window (our own, no browser chrome) hosting the face UI, with a supervisor in the main process | Operator, verbatim: "we dont want this to run in a browser we want owur own app not a browser", "an .exe will work", "that starts when opened and shuts all down when closed". The exe spawns sidecars + hub on open and kills them on close. |
| **Face UI** | HTML/JS inside the shell (Canvas/WebGL, Web Audio, WebRTC), served by the hub | the same page also works in OBS and the Android WebView |
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

## Appearance engine (M3 redefined, 2026-10-30)

Operator, verbatim, same day: *"shes not even moving her body or arms or legs or standing or moving aqround"*; *"i should be able to tell her how to appear wether nude or as a black nile beauty is so told"*; *"she shouldnt only use one image she should generate an appearance and stick to it wether told to take off her undies or pick her nose all trillions of options are available and should work dynamicly"*; *"that image is just her likeness not the one to always use"*.

So the face is not a still portrait with moving lips. It is a generative renderer with three layers:

1. **Identity.** Her likeness references (`assets/portrait/unity-full.jpg`, `unity-carbon.jpg`, operator-picked) are the face identity only. They feed the IP-Adapter face lock and the prompt; they are never themselves the thing on screen.
2. **Look.** A session look is generated from the identity (outfit, setting, hair, ethnicity, nude or not, whatever she is told), kept as the current base, and regenerated only on command. Consistency comes from the face lock plus a fixed seed and a stored look prompt.
3. **Action.** What she is doing right now is a video clip generated from the current look (image-to-video: stand up, walk, dance, undress, pick her nose, anything), with Ditto driving the lips and head on top of the moving clip in real time. Ditto takes a video source and mirror-loops it, so each clip becomes a living idle until the next one. Clips are cached by (look, action); idle and common actions are pre-generated; a new action is announced by voice while it renders, and the previous clip keeps playing until it is ready.

What this costs: image-to-video on one 16 GB card is seconds-to-minutes per clip, never instant. Local options are the small Wan / LTX-class models; the cloud option is the Pollinations video API already vendored (veo, wan, ltx). Real-time free-form body generation is not available at this scale today; the clip engine is how "trillions of options" become reachable without pretending otherwise.

**GPU budget, measured 2026-10-30 (4070 Ti SUPER, 16 GB).** Operator: *"is it normal for it to be so laggy and her face only changeing 1 time ever like 10 seconds?"* and *"her movemments are jsut played out loops not real live action constantly changing"*. A 352x640 x 73-frame LTX clip renders in 15 s when the live face is held, and in 253 s when the face keeps running (face median 2.8 fps meanwhile, card at 15.7 GB / 100%). The live face and the video engine cannot share the card, so:

- The face **holds its last frame** (`POST /pause`, `/resume` on the face sidecar) for every image render and clip render, and resumes on the new look. The brain is unloaded (`keep_alive: 0`) before each clip.
- **Reel instead of loop, open-ended.** Operator: *"she is still looping wewhen she is suppose to be open ended doing wehat ever she wants to do when not directed"*. After a look's first clip is on her, for as long as she is idle (not thinking, not speaking; `reelClips` 0 = unbounded), the hub chains clips from the previous clip's last frame (`from_clip` on the video sidecar), each one a thing her own brain decided to do next (`nextIdleAction`: a batch of `reelBatch` actions asked of the brain per look, config `reelMotions` as fallback), and appends each one to her live reel (`/appearance` with `extend: true`: the face sidecar registers the new frames into Ditto's per-frame source lists without restarting its workers). Ditto mirror-plays the whole reel, so the body is a growing chain of distinct motion instead of one 3 s loop, with no hard seam; the newest `reelMaxFrames` (~18 s, ~8 MB RAM per frame) are kept and the oldest dropped. A newer look preempts the reel after at most one clip; a new message cancels the clip in flight at its next diffusion step (`/cancel` on the video sidecar) and resumes her face, so her lips never wait on an idle clip. Cost on this card: each 3 s of new motion is a ~15 s render plus ~5 s registration with her frame held, so while idle she alternates held and moving.
- Truly continuous new motion needs a second card (local or rented) running the video engine while this one runs the face. Not built; the hooks above are where it would plug in.

**Looks vs motion (2026-10-30).** Operator: *"she should only change or take off outfits when told to, just telling her to bounce or jiggle or dance should not instanty generate a new self image unless told that"*. Two lines in her stream: `[[img: ...]]` only when what she wears, her body, hair or place changes (new image, then clip, then face); `[[do: ...]]` for a movement in the look she already has (clip from the current clip's last frame or current look, no new image, swapped onto her face). A stage direction with no line counts as `[[do]]`. The idle reel keeps describing the look prompt, not a later motion.

## Packaging, install, uninstall (M8, 2026-10-30)

Operator, verbatim: *"this all needs to work as one sole .exe"*; *"the .exe has to install all things it needs to run with option to uninstall oall things also if wanted"*; *"the .exe prperly runs everything without fucking cmd windows poping open and closed all the fucking time"*.

- **One exe.** `app/` is the Electron shell; electron-builder makes `AgentGen-Setup-<version>.exe` (NSIS, per-user, choice of folder) and `AgentGen-portable.exe`. Resources shipped inside: hub (with node_modules), ui, sidecars (no venvs), assets, scripts, Ditto's source, her Modelfile, her voice model. The packaged hub runs on Electron's own binary (`ELECTRON_RUN_AS_NODE`), so no system Node is needed.
- **Data root** `%LOCALAPPDATA%\AgentGen` (`app/paths.js`): `runtime/python` (python-build-standalone 3.10), `venvs/face`, `runtime/ollama` (portable zip, no tray app, no service), `models/` (+ `models/hf` as HF_HOME), `ollama-models/`, `logs/`, `downloads/`. Every lookup falls back to the repo and system locations, so a dev checkout with the lab's Python, venv, tray Ollama and `models/` is complete and boots straight in.
- **First run** (`app/setup.js` + `app/setup.html`, drawn inside the app window): capability checks per step (python, base requirements + torch cu118, face venv, ollama, models via `scripts/fetch-models.py`, brain = pull dolphin3:8b + `ollama create unity-local`), each skipped when satisfied, logs streamed to the page, resumable downloads. Nothing touches PATH or the registry.
- **Uninstall.** NSIS uninstaller (`app/installer.nsh`) asks whether to remove the data root too; the in-app **Uninstall everything** button removes it and launches the uninstaller.
- **Building on Windows without admin.** electron-builder's `winCodeSign` helper pack holds macOS symlinks that 7-Zip cannot create without the symlink privilege, so the first `npm run dist` fails with "A required privilege is not held by the client". Fix once: unpack the cached `%LOCALAPPDATA%\electron-builder\Cache\winCodeSign\*.7z` into `winCodeSign-2.6.0/` with `7za x -xr!darwin`, then build again. `CSC_IDENTITY_AUTO_DISCOVERY=false` (no code signing certificate yet).
- **No console windows.** Every child is spawned with a hidden console. The brain is the app's own private Ollama server on :11435 (`app/supervisor.js`): a runner started by the tray app's console-less server gets a new console that Windows Terminal flashes on screen; under the app's hidden console it inherits and stays invisible (measured: tray app = conhost + OpenConsole per runner; private server = none). The video sidecar writes mp4 with OpenCV and the face sidecar reads clips with OpenCV, so no ffmpeg child processes either. LTX frees its GPU blocks after every run (maybe_free_model_hooks + empty_cache).

## Ports (planned, all loopback)

| Port | Service | Origin |
|---|---|---|
| 4646 / TBD | hub (UI + WS + gateway) | new |
| 5123 | unity-voice-v2 TTS | Backrooms |
| 5124 | image sidecar (SD1.5 + face lock) | C.O.R.A / VibeRoller |
| 5125 | speech (faster-whisper) | VibeRoller |
| 11434 | Ollama (unity-brain, nomic-embed-text) | existing |
| 9333 | Chromium CDP for the browser tool | Backrooms tw.py |
