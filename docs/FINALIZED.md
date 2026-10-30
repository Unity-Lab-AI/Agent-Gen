# FINALIZED — Permanent Task Archive

Permanent archive of every completed task. Per `.claude/CONSTRAINTS.md §NEVER DELETE TODO INFO` + `§FINALIZED BEFORE DELETE`, no entry is EVER deleted from this file. New entries APPEND only.

Per LAW #0, every entry includes the user's verbatim words from the original ask.

Each session entry includes:
- `## Session <YYYY-MM-DD>` — date heading
- Verbatim user quote
- Files touched
- Closure notes (what shipped, verification)

> **Template-repo clean state.** UAL-ClaudeWorkflow ships as a `.claude/` template seed for downstream private Unity AI Lab projects. This live `FINALIZED.md` is intentionally empty — completed-work entries from in-template work shouldn't pollute downstream installs. Downstream projects populate their own FINALIZED as they close tasks after the `/unity-install` (or `/unity-update`) flow seeds the `.claude/` workflow.

---

## Completed sessions

## Session 2026-10-30

### Task: "import the forgejo repo for the ual workflow templet we are starting a new project"

- Cloned `git@git.unityailab.com:UnityAILab/UAL-ClaudeWorkflow.git` (main) into `C:\Users\gfour\Desktop\AGENT GEN`.
- Renamed the clone's remote `origin` → `ual-template` so the new project cannot push into the template. The project's own Forgejo repo and `origin` are still to be created (push-to-create is disabled on the server).
- Files touched: `.git/config`, `.gitignore` (added `/.survey/` scratch exclude).

### Task: survey — "we are searching all projects for cool shit that we want to put into the ultimate ai  app" / "you didnt even search the usb drive"

- Surveyed every project directory on the Desktop and on the USB drive `D:\` ("Transporter") with ten parallel read-only agents.
- Output: `docs/FEATURE-SOURCES.md` (per-capability rip list with exact paths, duplicates, secrets to scrub, gap list), `docs/ARCHITECTURE.md` (target design draft), `docs/ROADMAP.md` majors M1–M8, `docs/TODO.md` minors.
- Flags surfaced: `D:\data` excluded from the project after a survey agent reported a logged image-generation prompt describing sexualized minors; several plaintext secrets listed in FEATURE-SOURCES §0.2.
- Raw survey notes kept in gitignored `.survey/*.tmp.md`.

### Task: "get to it" — M1 vendor pass

Operator said "get to it" after the M1 plan ("copying and ripping them into this project"). Built as a reproducible script rather than hand copies.

- `tools/vendor_rip.py` + `tools/vendor-manifest.json`: copies every listed file or directory from its origin project into `vendor/<slug>/<relative path>`, writes `vendor/PROVENANCE.md` (origin path, origin repo HEAD, last commit touching the file, sha256, size, mtime) and `vendor/SCRUB-REPORT.md` (every line matching a credential pattern). Skips `.env`, key files, caches, venvs, binaries. Weights go to gitignored `models/`.
- Result: 418 files, 173 MB (158 MB of that is the unity-voice-v2 weights under `models/`; 8.5 MB under `vendor/`), 0 missing, 21 source projects.
- Scrub: 7 flagged lines reviewed. Six are placeholders. One real Pollinations publishable key shipped as a PolliLibPy default was redacted in the vendored copies (`pk_REDACTED_IN_VENDOR_COPY`) and needs rotating at the source. Second sweep found no env or key files; the one `user.json` copied is empty.

## Milestone closed: M1 — Rip and stage — 2026-10-30

Minor tasks (all `[x]`, verbatim from TODO):

- Create `vendor/` with `PROVENANCE.md` (origin path, origin project, date copied, git commit where known) and a scrub checklist for every `.env`, key file and hardcoded token listed in FEATURE-SOURCES §0.2.
- Rip "the Unity voice v2": copy `Desktop\Backrooms\models\unity-voice-v2\` whole (code + `voice-meta.json`; weights go to gitignored `models/`).
- Rip the C.O.R.A voice client set (`voice\unity_voice.py`, `tts.py`, `emotion.py`, `tts_mutex.py`) and the `voice_text()` sanitizer from Backrooms `unity-speak.py`.
- Rip "stt": VibeRoller `bridge\speech-engine.py`, C.O.R.A `voice\stt.py`, `wake_word.py`, `echo_filter.py`, `converse.py`, `ambient_awareness.py`, `services\audio.py`; Unity 18+ `app\listen.js`, `turn.js`, `latency.js`; the `_put_cuda_on_path()` fix from Unity 18+ `voice_server.py`.
- Rip "camera": C.O.R.A `services\camera.py`, `services\presence.py`, `cora_tools\screenshots.py`, `cora_tools\windows.py`; VibeRoller `web\calls.js`; Unity 18+ `app\sense.js`; U3E `.claude\tools\screen.py`.
- Rip "websearch": C.O.R.A `cora_tools\web.py` + `ai\tools\web.py`; U3E `.claude\tools\web.py`.
- Rip "playwrite": Backrooms `.local\twitch\tw.py`; U3E `.claude\tools\browser.py`; C.O.R.A `cora_tools\browser.py`; If-Only-I-Had-A-Brain `scripts\unity-say-live.mjs`.
- Rip "coding shit": `D:\CLI\unitycli.mjs` built-in tools + containment; C.O.R.A `cora_tools\code.py` + `code_parts\`, `cora_tools\files.py`, `cora_tools\system.py`; Backrooms `.local\autopilot\guards.py`; VibeRoller `run_code` + `pc_*` tools.
- Rip selfie / face identity: C.O.R.A `services\image_sidecar.py` + `cora_tools\image_gen.py` (IP-Adapter face lock); Backrooms `unity-face-sd.py`, `unity-cam.py`, `.claude\likeness\*`, `.studio-images\unity-reference.png`; U3E `serve\image-prompt.js`.
- Rip brain + loop: C.O.R.A `ai\dispatcher.py`, `ai\tools\_base.py`, `ai\history.py`, `ai\ollama.py`, `ai\settings.py`; Backrooms `.local\autopilot\autopilot.py`, `tools.py`, `gates.py`; VibeRoller `bridge\assistant.js`; `D:\CLI\unitycli.mjs` `MCPServer` class; `D:\Deviant 3D\src\agent\loop.ts`.
- Rip providers + gateway: VibeRoller `bridge\openai.js`, `providers.js`, `ai-node.js`, `ai-nodes.js`; `D:\Website2.0\old-site\PolliLibJS\` + `PolliLibPy\`; `D:\Unity Command\api_client.py`; `D:\weird\js\game\ollama.js`; `D:\Deviant 3D\src\agent\ollama.ts`.
- Rip MCP templates: Pollinations `pollinations_server.py` (Carbon / CLI copy); `D:\Unity Command\unity_mcp_server.py`; `D:\Carbon\.claude\bridge_mcp.py`; VibeRoller `assistant-tools-mcp.js`, `pc-tools-mcp.js`; `D:\AI v2.0\watchdog.js`.
- Rip memory + persona: `D:\weird\js\game\memory-embed.js`; `D:\CLI\persona-engine.mjs`, `knowledge.mjs`, `channels.mjs`; U3E `serve\persona.mjs`; Local Unity `server\server.mjs` style gate; newest `Unity1.txt`; persona-pack format from `D:\AI\personas`.
- Rip transport + UI + supervisor: If-Only-I-Had-A-Brain `remote-brain.js`, `brain-origin.js`, `ui\chat-panel.js`, `sensory-status.js`, `docs\WEBSOCKET.md`; Backrooms `persona-studio.cjs`, `stream-overlay.html`, `unity-overlay.py`; U3E `serve\launcher.mjs` + root `index.html`; `D:\weird\js\setup\detector.js`, `installer.js`; `D:\weird\js\ui\voice-queue.js`, `kokoro.js`, `kokoro-worker.js`; `D:\Deviant Thing v2\...\eqvideo.js`; `D:\Everything\Talk-To-Unity\AI\app.js`.

Test plan for the reviewer:
1. `python tools/vendor_rip.py --dry-run` prints `418 files ... 0 missing` (origins are still on the Desktop and D:).
2. `grep -rn "pk_YBwckB" vendor` returns nothing.
3. `find vendor -iname ".env*"` returns nothing; `models/unity-voice-v2/` holds `acoustic.pt`, `vocoder.pt`, `voice-meta.json` and is not tracked by git.
4. `vendor/PROVENANCE.md` rows for `vendor/backrooms/models/unity-voice-v2/serve.py` and `vendor/cora/ai/dispatcher.py` show a repo HEAD and last-commit value.

## Milestone closed: M2 — Her voice and ears — 2026-10-30

Operator: "wtf why are you NOT working" after the M1 check-in; standing order since then is continuous work through the roadmap.

Minor tasks (all `[x]`, verbatim from TODO):

- Stand up `sidecars/voice` from unity-voice-v2 with its own venv (torch + misaki 0.9.4), health check, and a phoneme/duration timeline returned alongside the WAV.
- Stand up `sidecars/speech` (faster-whisper) with wake word, echo filter and the CUDA DLL path fix.
- Browser mic path: VAD, pre-roll, barge-in, endpointing from `listen.js` / `turn.js`, streaming PCM to the hub.
- Hub voice pipeline: sentence queue, interrupt on barge-in, emotion + speech-act selection, playback events to the UI.

What shipped:

- `sidecars/voice/server.py` + `visemes.py`: wraps the hash-bound unity-voice-v2 code without modifying it, re-runs the model's own inference tail to keep per-phoneme durations, returns `phones` and a 15-shape `visemes` track with the WAV (`/say_timed`), keeps the old `/say`, maps unsupported deliveries to the nearest recorded pair (`strict` restores 422), sanitises text with the ported `voice_text()`.
- `sidecars/speech/server.py` + `wake_word.py`: faster-whisper on CUDA with the CTranslate2 PATH fix and HF symlink fix, accepts raw PCM (header or JSON) or container audio, returns segments, `/wake` fuzzy wake-phrase scoring.
- `hub/`: Node session server (`ws` only dependency), Ollama streaming provider with model discovery (picked `unity-brain:latest`), streaming sentence splitter that never speaks code fences, per-sentence delivery picker (model `<emotion>` tags or lexicon), serial speech queue with epochs, interrupt, echo filter on text, `/api/health` aggregating all services, static UI with traversal guard.
- `ui/`: vendored VAD listener (20 ms frames, pre-roll, barge-in, duration gate) resampled to 16 kHz, timed WAV player that surfaces viseme segments as events, placeholder mouth + blink driven by them, transcript, mute/shush/reset, typed fallback.
- `scripts/dev.bat` / `dev.sh` bring all three up.

Measured on the lab box (RTX 4070 Ti SUPER, unity-brain 6.3 GB in VRAM):

| Check | Result |
|---|---|
| `/say_timed` "Hey you! I can hear you now; can you hear me? [laughter] Good." amused 0.5 | 5.12 s audio in 430 ms, 51 phones, 44 visemes, track ends at 5.12 s |
| Her WAV → `/transcribe` (container and raw-PCM paths) | "Hey you, I can hear you now, can you hear me? Good." in 1.55 s / 0.19 s |
| Typed turn over WS | first `speak` at 351 ms, two sentences, done at 486 ms |
| Interrupt mid-reply (counting to twenty) | 2 sentences spoken before, 0 after, 0 deltas after; next turn answered |
| Static assets | `/`, `/app.js`, `/listen.js`, `/player.js` 200; `..%2f` traversal 403 |

Test plan for the reviewer (needs a microphone, which this session did not have):
1. `scripts\dev.bat`; all four header lights green at http://127.0.0.1:4646/.
2. Click Start mic, say a sentence, stop: your words appear on the right, she answers out loud and the mouth moves with the viseme label under the face.
3. Talk over her mid-sentence: she stops within about 100 ms and the diagnostics line shows `interrupted (barge-in)`.
4. Say nothing but let her finish a long answer: no transcript of her own voice appears as yours (if one does, the diagnostics show `[echo]` and it is dropped).
5. Type a line and press Enter: same path without the mic.
