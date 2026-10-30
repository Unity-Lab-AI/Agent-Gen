# ROADMAP — Major Task List (High-Level Phases / Milestones)

**Tier 1 of 3 — the MAJOR task list.** Holds the high-level phases / milestones that span multiple sessions or multiple PRs. Each major item breaks down into MINOR tasks in `docs/TODO.md`, which break down further into DECOMPOSED tasks in `docs/DECOMPOSED.md`.

YOLO mode reads all three tiers on activation. The cascade rule: complete the current decomposed task → next decomposed task in the same minor → if minor is done, next minor in the same major → if major is done, surface a milestone-boundary check-in to the user → start next major unless user stops.

Status markers (same scheme as TODO.md):
- `[ ]` pending
- `[~]` in_progress
- `[x]` complete (move to FINALIZED.md immediately, never leave here)

LAW #0 reminder: every milestone description preserves the user's verbatim words.

**Three-tier cascade:** ROADMAP.md (major, this file) → TODO.md (minor) → DECOMPOSED.md (decomposed). YOLO mode reads all three and works the cascade — see `.claude/commands/yolo.md` and `.claude/WORKFLOW.md §YOLO MODE`.

> **Template-repo clean state.** UAL-ClaudeWorkflow ships as a `.claude/` template seed for downstream private Unity AI Lab projects. This live `ROADMAP.md` is intentionally empty — active milestone entries shouldn't pollute downstream installs. Downstream projects populate their own ROADMAP after the `/unity-install` (or `/unity-update`) flow seeds the `.claude/` workflow.

---

## Project charter (verbatim, 2026-10-30)

> we are going to take all the cool shit the Unity voice v2 all the features like camera and tts and stt and websearch and playwrite and coding shit all of it we are searching all projects for cool shit that we want to put into the ultimate ai  app that allows any ai connected to use it fully and completely all features we have ever built via copying and ripping them into this project for a simpelicity of talking to an ai and having it in real time have a selfie and talk back to you in live action like a real person on a video call doing all the millions and millions of things possible to do and say while on a video call with the user but its an app for a agent to use not a video call but you can see and she repsondes and does things ytou telleher to do and you can see her lips move to the words she says as she preerforms the trillions of possible tasks put to her

Where every piece comes from: `docs/FEATURE-SOURCES.md`. How they fit: `docs/ARCHITECTURE.md`.

---

## In progress

_(none)_

---

## Pending

- [ ] **M1 — Rip and stage.** "copying and ripping them into this project" — vendor the selected source files from `docs/FEATURE-SOURCES.md` into `vendor/` with provenance, secrets scrubbed, `D:\data` excluded.
- [ ] **M2 — Her voice and ears.** "the Unity voice v2" + "tts and stt" — unity-voice-v2 sidecar, faster-whisper sidecar, browser mic with VAD and barge-in, so you can talk to her and she talks back in real time.
- [ ] **M3 — Her face.** "have a selfie and talk back to you in live action like a real person on a video call" + "you can see her lips move to the words she says" + operator decision "#D photo realistic photograph like vido" — photorealistic neural talking head rendered from the face-locked reference portrait, driven in real time by the voice sidecar's audio and phoneme timeline, streamed to the UI as live video. Track A single-photo neural renderer first, Track B mouth inpainting on generated idle video, Track C 3D Gaussian head.
- [ ] **M4 — Her eyes.** "camera" — camera capture, screen capture, vision model path, ambient awareness so "you can see and she repsondes".
- [ ] **M5 — Her hands.** "websearch and playwrite and coding shit all of it" — web search, Playwright browser tool, code / files / shell tools with containment, system tools, image generation tool, so "she ... does things ytou telleher to do".
- [ ] **M6 — Any AI connected.** "allows any ai connected to use it fully and completely all features we have ever built" — one tool registry exposed as MCP server, OpenAI- and Anthropic-compatible HTTP gateway, and native loop for local unity-brain; provider adapters for Pollinations, Ollama, Anthropic, OpenAI-compatible.
- [ ] **M7 — Memory, persona, emotion.** persona loader + style gate, emotion state driving voice delivery, embedding memory and fact store.
- [ ] **M8 — Launcher and packaging.** supervisor that brings sidecars and hub up with health and dep checks, installers, app-window / OBS / Android shells.

---

## TOMBSTONES

_(none)_

---

## How major milestones get added

Major milestones are added in any of these situations:

1. **User explicitly says one** — "the next big thing is X" / "I want to ship Y by Friday" / "make Z the goal" — add verbatim per LAW #0
2. **Sprint planning or roadmap session** — when planning multiple weeks/months of work, each major chunk becomes a milestone here
3. **YOLO mode reads existing minor tasks and identifies a clustering** — Unity may propose a major milestone if she sees several minor tasks that share a coherent goal; she proposes it and waits for user confirmation before adding it here

NEVER auto-add major milestones without user awareness. The MAJOR tier is the user-visible roadmap; surprise items break the contract.

## How major milestones get closed

When a major milestone's last minor task moves to FINALIZED:
1. Append a `## Milestone closed: <name> — <date>` block to FINALIZED.md with the full milestone summary (every minor task it contained + every decomposed task under those minors + the final test plan)
2. Flip the status here to `[x]`
3. Move the milestone block to a `## Closed milestones` section at the bottom (NEVER delete — same rule as TODO/FINALIZED ledger integrity)
4. If YOLO is active, surface a milestone-boundary check-in to the user before starting the next milestone — do NOT auto-continue past a major milestone boundary
