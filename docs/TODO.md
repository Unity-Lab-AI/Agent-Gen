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

- [~] Frame transport to the UI: WS binary frames locally, WebRTC video track for remote clients; UI shows it as a video-call feed with "what she is doing" status while tools run. (2026-10-30: MJPEG stream in an `<img>` for local; hub mirrors every sentence to the face and the UI delays audio by the reported lead. WebRTC for remote clients still open.)
- [ ] Phoneme → mouth drive: use the voice model's per-phoneme durations as the primary lip signal where the renderer accepts it; audio-only drive for cloud TTS.
- [ ] Track B kept as a fallback: MuseTalk-class mouth inpainting on generated video if Ditto's warp quality on moving bodies is not enough.
- [ ] VRAM scheduling in the launcher: unload SD while the face is live, cap unity-brain context, optional second machine for the face via the ai-node pattern.
- [ ] Record-to-video of the face feed + voice (eqvideo.js pattern).
- [ ] Track C (research, after A ships): 3D Gaussian-splat head fitted from generated video of her for camera moves and parallax.

### M4 — Her eyes ("camera", "you can see and she repsondes")

- [~] Camera capture (browser `getUserMedia` and Python `camera.py`) and screen capture (`getDisplayMedia`, `screen.py`) feeding frames to the hub. (2026-10-31, 0.5.32: Show camera / Show screen in the footer, one still per source with every message; `ui/eyes.js`. Python capture not needed in the app. Awaiting the operator's visible test.)
- [~] Vision tool: local unity-brain vision / qwen-vl through Ollama, Pollinations image-to-text as cloud path. (2026-10-31, 0.5.32: `qwen3-vl:4b` via `hub/vision/client.mjs`; tested through the hub's WS with a real screenshot (she read the Discord channel on screen) and a portrait as camera (pink-streaked hair, white bikini). Cloud path still open.)
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
- [ ] Acceptance pass, visible: "when everything is complete and finished test it non headless at human viewable operations to test it and talk to her". The app window on the desktop, her voice on the speakers, a real conversation; nothing counted as tested unless the operator could see it.

---

## TOMBSTONES

_(none)_
