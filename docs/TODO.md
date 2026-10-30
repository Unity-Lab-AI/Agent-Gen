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

All M1 minors completed 2026-10-30 and moved to `docs/FINALIZED.md` (§Milestone closed: M1). Manifest: `tools/vendor-manifest.json`; copies under `vendor/`; weights under gitignored `models/`.

### M2 — Her voice and ears ("the Unity voice v2", "tts and stt", "talk back to you in real time")

All M2 minors completed 2026-10-30 and moved to `docs/FINALIZED.md` (§Milestone closed: M2). Code: `sidecars/voice`, `sidecars/speech`, `hub/`, `ui/`, `scripts/dev.*`. Open follow-up carried into M8: the browser mic path has only been exercised by code review and the hub's typed path; a human with a microphone confirms VAD, barge-in and echo filtering.

### M3 — Her face ("have a selfie", "like a real person on a video call", "you can see her lips move to the words she says", operator decision: "#D photo realistic photograph like vido")

- [~] Reference portrait set: photoreal, face-locked (IP-Adapter) frontal portraits of her at 512 and 1024, neutral plus a few moods, from the existing `unity-reference.png` likeness. These are the identity the renderer drives. (2026-10-30: the locked Backrooms likeness, frontal 512×640 neutral + smiling, staged in `assets/portrait/`. The IP-Adapter mood set comes with the image sidecar in M5.)
- [~] Evaluate and pick the Track A renderer on the 4070 Ti SUPER: LivePortrait-class renderer with an audio-to-motion front end (JoyVASA / Ditto class). Measure fps, latency from audio start to first frame, VRAM. (2026-10-30: picked **Ditto** (Ant Group, Apache-2.0): streaming online mode, 10 diffusion steps, LivePortrait renderer, prebuilt Ampere+ TensorRT engines. Repo cloned to `third_party/`, weights in `models/ditto` (PyTorch 2.2 GB, ONNX 2.4 GB, TensorRT 2.1 GB), venv built. Measured 2026-10-30 on the 4070 Ti SUPER, PyTorch path: offline render 28 fps; live sidecar ~20 fps while speaking, ~1.9 GB VRAM, per frame warp 35 ms / decode 63 ms / putback 24 ms, motion diffusion 1.2–1.8 s per 1.2 s clip; lead 1.4–1.8 s at overlap 50. Decode is the ceiling. Fewer diffusion steps (5, 3) did not raise fps. The TensorRT path (Ditto's intended real-time route, fp16 engines, ~3x) needs NVIDIA's TensorRT 8.6.1 Windows zip since the pip wheel is Linux-only; parked as the upgrade.)
- [~] `sidecars/face`: takes audio + phoneme timeline from the voice sidecar, emits frames at 25 fps; idle motion, blink, gaze toward camera when nobody is speaking; eye/lip retargeting knobs wired to the emotion state. (2026-10-30: `sidecars/face/server.py` written: wraps Ditto's StreamSDK live, silence-fed idle loop, 25 fps JPEG playout, `/speak` with `lead_ms`, `/emotion` live, `/pose` + idle sway, `/interrupt`. Running 2026-10-30: she idles, blinks, sways, and spoke two fresh lines through the speakers in a visible window (`scripts/face-view.py`) with lips moving; per-stage timers in `/health`.)
- [~] Frame transport to the UI: WS binary frames locally, WebRTC video track for remote clients; UI shows it as a video-call feed with "what she is doing" status while tools run. (2026-10-30: MJPEG stream in an `<img>` for local; hub mirrors every sentence to the face and the UI delays audio by the reported lead. WebRTC for remote clients still open.)
- [ ] Phoneme → mouth drive: use the voice model's per-phoneme durations as the primary lip signal where the renderer accepts it; audio-only drive for cloud TTS.
- [ ] Appearance engine ("she shouldnt only use one image she should generate an appearance and stick to it wether told to take off her undies or pick her nose all trillions of options are available and should work dynamicly"; "i should be able to tell her how to appear wether nude or as a black nile beauty is so told"; "that image is just her likeness not the one to always use"): identity = likeness refs; look = generated base image with face lock + fixed seed, regenerated on command; action = image-to-video clips from the look, cached by (look, action), Ditto lips/head live on top of the clip (video source, mirror loop). Idle + common actions pre-generated; new actions announced while rendering.
- [ ] Body motion ("shes not even moving her body or arms or legs or standing or moving aqround"): first action clips = idle breathing, shift in seat, stand up, walk a few steps, turn, sit; evaluate local image-to-video (Wan / LTX small) against Pollinations video for speed and identity hold on the 4070 Ti SUPER.
- [ ] Face renderer on video sources: `sidecars/face` `/appearance {image|video}` re-registers Ditto's source without restarting; crossfade between clips.
- [ ] Track B kept as a fallback: MuseTalk-class mouth inpainting on generated video if Ditto's warp quality on moving bodies is not enough.
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
- [ ] System tools (apps, windows, processes, media, notifications) and image generation tool with selfie mode. Per the operator ("she should be a slut sending dirt images of her self and like doing strip teases"; corrected: "dirty* not dirt.. i dont want to see dirty girls i want to see girls doing the dirty"), the selfie tool runs with the safety checker off as the vendored SD sidecars already do, with the face lock keeping her identity; no app-side filter ("the model handels all the safties already we dont need to double up").

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
- [ ] Supervisor: start / stop / health / deps for sidecars and hub, with the detector + installer onboarding pattern. Lives inside the app exe ("that starts when opened and shuts all down when closed").
- [ ] Shells: our own app window, not a browser ("we dont want this to run in a browser we want owur own app not a browser", "an .exe will work"): Electron shell + electron-builder exe; OBS overlay and Android WebView stay as secondary surfaces.
- [~] One exe ("this all needs to work as one sole .exe"): electron-builder NSIS + portable targets, hub on Electron's own node, Ditto source + voice model + Modelfile shipped as resources. Built; the installer exe itself has not yet been produced on this machine (`npm run dist` in app/).
- [~] Installer ("the .exe has to install all things it needs to run with option to uninstall oall things also if wanted"): app/setup.js steps python / base / face / ollama / models / brain into %LOCALAPPDATA%\AgentGen with capability checks; app/installer.nsh asks to remove the data root on uninstall; in-app Uninstall everything. Built; not yet exercised on a clean machine.
- [x] No console windows ("the .exe prperly runs everything without fucking cmd windows poping open and closed all the fucking time", "wtf just had 50 fucking cmd windows open and close i told you to stop that shit and fiox it"): private Ollama server under the app's hidden console (:11435), OpenCV instead of ffmpeg children in the video and face sidecars. Measured: no OpenConsole per runner.
- [x] Looks vs motion ("she should only change or take off outfits when told to, just telling her to bounce or jiggle or dance should not instanty generate a new self image unless told that"): [[img]] only for appearance changes, [[do]] renders a clip of the current look.
- [x] Everything in both remotes ("everyhting the project has shall be put in both remotes you fuck! minue chaches logs and gernations attempted already so full ship clean slate of the full stack and everything needed to make the .exe"): Ditto source un-ignored, her voice model via Git LFS, fetch-models.py for every other weight, project README.
- [ ] Acceptance pass, visible: "when everything is complete and finished test it non headless at human viewable operations to test it and talk to her". The app window on the desktop, her voice on the speakers, a real conversation; nothing counted as tested unless the operator could see it.

---

## TOMBSTONES

_(none)_
