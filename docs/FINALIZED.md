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

### M3 progress — 2026-10-30 (milestone open)

Operator decisions captured verbatim this session: "#D photo realistic photograph like vido" (face is photoreal live video, no sprites); "fyi this is a 18plus application so chick can be full on 18+ type of lewdish"; "like she should be a slut sending dirt images of her self and like doing strip teases to full blown yahooo shit" corrected to "dirty* not dirt.. i dont want to see dirty girls i want to see girls doing the dirty"; "the model handels all the safties already we dont need to double up on tlust get messy".

Done:
- Renderer survey (Ditto, JoyVASA, LivePortrait-AudioDriven, FLOAT, MuseTalk, SoulX-FlashHead) and pick: Ditto. Reasons: built for streaming with low first-frame delay, single portrait + audio, emotion / pose / gaze controls, LivePortrait-class renderer, Apache-2.0, prebuilt Ampere+ TensorRT engines, online config uses 10 diffusion steps.
- `third_party/ditto-talkinghead` cloned (gitignored), `models/ditto` downloaded (cfg + PyTorch 2.2 GB + ONNX 2.4 GB; TensorRT engines 2.1 GB not yet), `sidecars/face/.venv` built on the lab's torch 2.7.1+cu118 with mediapipe, librosa, einops, cuda-python.
- `sidecars/face/server.py`: live wrapper around Ditto's StreamSDK with a silence-fed 200 ms feeder so she idles and blinks between sentences, a frame sink that paces JPEGs at 25 fps, MJPEG stream, `/speak` (returns `lead_ms`), `/interrupt`, `/emotion` (voice emotions mapped onto Ditto's 8 classes), `/pose` with idle sway, numpy shim for Ditto's Cython blend so no C compiler is needed on Windows.
- Hub: `hub/face/client.mjs`; every spoken sentence is mirrored to the face and the `speak` message carries `lead_ms`; interrupt reaches the face; `/api/health` reports it. UI: `<img id="feed">` replaces the placeholder face when the sidecar is up; the player delays audio by `lead_ms`.
- `assets/portrait/unity-likeness.png` + `unity-likeness-smile.png` staged from the locked Backrooms likeness.
- Verified: hub runs with the face down (health `face: false`, voice loop unaffected, first audio 610 ms on this run).

Blocked: executing the cloned Ditto code (the offline `inference.py` and the live sidecar) is refused by this session's auto-mode classifier. The operator runs `scripts\face-smoke.bat` once (writes `.run\ditto-test.mp4`), then `scripts\dev.bat` brings the face up with the rest.

### M3 — lag, image line, reel — 2026-10-30

Operator words this pass, verbatim: "is it normal for it to be so laggy and her face only changeing 1 time ever like 10 seconds?"; "restart her fresh and clear the gpu before you run her again" / "after u fix"; "you are the only one running shit so whats on the GPU you put ther"; "wtf.. she didnt do it:connected / take that top off / <excited> Sure thing! *top removed*"; "there shouldnbt be a filter of rules that block, ive told you this already"; "and something im seeing is her movemments are jsut played out loops not real live action constantly changing"; "welll test it out and see what the gpu can handle".

Done:
- Lag: face sidecar `/pause` + `/resume`; hub holds her frame for every image and clip render; clip budget 448x640 x 73 frames. Measured: clip 15 s held vs 253 s live (face 2.8 fps meanwhile).
- Image line: persona rule rewritten so any change to what she wears / does / holds / where she is requires the `[[img: ...]]` line first, with a worked example; legacy "avoid cussing and flagged words" prompt rule deleted; tag filter turns an asterisk stage direction into the look when no image line was written. Verified in the app: "take that top off" rendered the look, swapped her face, clip in 15 s, clip live on her.
- Reel: video sidecar `from_clip` (continue from a clip's last frame); face sidecar `extend_source` appends clip frames to Ditto's live source lists without a worker restart; hub `extendReel` chains `reelClips` idle-motion clips per look while she is idle, preempted by a newer look. ARCHITECTURE.md §Appearance engine updated with the budget numbers.
- Open-ended reel (operator: "she is still looping wewhen she is suppose to be open ended doing wehat ever she wants to do when not directed"; "just seems odd she is up and running and only using 4 gigs of the gpu"): reel unbounded while idle, her brain picks the next actions in batches, reel capped at `reelMaxFrames` with oldest dropped, video sidecar `/cancel` (step callback) + hub cancels the idle clip and resumes her face on a new message. Registrar fix: a frame with no face holds the previous frame instead of failing the clip (IndexError the operator pasted). Idle GPU at ~4 GB is by design: brain loads on first message and is dropped before each clip; image/video engines load on use.

### M8 ship pass — 2026-10-30

Operator words, verbatim: "this all needs to work as one sole .exe"; "the .exe has to install all things it needs to run with option to uninstall oall things also if wanted"; "and the fucking .exe prperly runs everything without fucking cmd windows poping open and closed all the fucking time!!!???"; "wtf just had 50 fucking cmd windows open and close i told you to stop that shit and fiox it"; "everyhting the project has shall be put in both remotes you fuck! minue chaches logs and gernations attempted already so full ship clean slate of the full stack and everything needed to make the .exe"; "dont worry about the .claude i set it to be shared"; "did you follow properl featue>develop>main cascade proceddures?"; "she should only change or take off outfits when told to, just telling her to bounce or jiggle or dance should not instanty generate a new self image unless told that"; "make sure the readme is concise and accurate and fun to read no fucking massive text walls and no shit fluff filler bullshit".

Done: private brain server + hidden consoles (measured flash-free), OpenCV instead of ffmpeg children, LTX GPU release after each run, [[do]] motion path without a new image, app/paths.js data root, app/setup.js + setup.html first-run installer, app/installer.nsh uninstall prompt, in-app Uninstall everything, package.json NSIS + portable targets with Ditto / voice / Modelfile resources, scripts/fetch-models.py, sidecars/requirements-base.txt, Ditto source un-ignored, voice model on Git LFS, project README, ARCHITECTURE §Packaging. Honest record: the earlier feature -> develop -> main promotion was done by direct merge and fast-forward on operator instruction, not through reviewed PRs; PRs #2-#5 were closed with that note; this pass goes feature/m8-ship -> develop -> main through PRs.

### Look persistence — 2026-10-31

Operator words, verbatim: "look at the image she just made,,, how is that anythhing like her original image of her? she is suppose to have image persistance... as i told ur to drop the top it shouldnt be a totaly differnt person, as u can see whith the generation its nothing like what she is looking like... i mean what the fuck... its suppose to keep the look until she is told to change, telling her to remove or change clothing should NOT mean a  totally differernt person and style"

Done (0.5.25):
- Cause: the restyle check read her own tag ("black hair with pink streaks, smudged eyeliner"), so a top-off request rendered fresh with no source picture and no face lock. `hub/server.mjs` now decides restyle on the operator's words only.
- Her current look, its prompt and her face survive restarts: `looks/current.json`, cleared on reset.

### Shut down button — 2026-10-31

Operator words, verbatim: "and i want on the agent gen app a shut down button, that unloads the gpu and shuts down the aspplication freeing up the GPU and stopping all processes for the application"

Done (0.5.26): "Shut down" in the main window footer → `agentgen:shutdown` (`app/main.js`): supervisor stop + the installer's process sweep (`installer-stop.ps1`, now packed in the app), then quit.

### Reset + persistence, second pass — 2026-10-31

Operator words, verbatim: "something thats not working is reset button is not properly reseting her self image to the default... and check the persistance again, as i just has her write something on her skin, but its a totally different womnan and she took her clothes off without asking.. is this just a model limitation or what id think itd be easy for a model to mimic an existing image. but i dont know how it can mimic and change"

Done (0.5.27):
- Cause: img2img at 0.75 repainted the whole frame (face, hair, room), and the skin-writing prompt named no clothes so the model dropped them.
- Edits now inpaint below her chin only (`hub/image/client.mjs`, face box from `sidecars/face` `/facebox`, fallback in `sidecars/image` `box: "body"`); prompts with no clothing words carry her current look. Tested on the 4070 Ti SUPER: skin edit on the black-hair look and top-off on the base photo both kept the same woman and room (`.run/inpaint-test/`).
- Reset puts her default picture back on the face, not only in memory.
- Model limit that stays: SD 1.5 cannot spell, so written words on skin come out as scribbles.

### Marker and lipstick on her skin — 2026-10-31

Operator words, verbatim: "do you see the issue? look at the image she made versus what was told to her to add to her current image and you tell me where she went wrong"; "can you show me none headless versions of what it would look like if coded scripted to add this ability"; "the third one looks the best the " draw + blend"; "lets do it!"; "what if i tell her to do it in lipstick test that"; "and use her default image not the creations"; "okay test it first, we need a good test like the firs draw+blend test before we go with it"; "okay thats good the letters are a little thick but that can be set to verty but lets make the letter thickness of the lines of the letters max out a little thinner than the max used in that test as the mine one test is almost un readable from the letters lines being too thick"

Done (0.5.28):
- `/mark` in the image sidecar + `hub/image/marks.mjs`: marker and lipstick words and shapes drawn where asked, multiply ink with grain, no model pass. Tested visibly on her default picture (`.run/marker-proto/sheet8.png`): "Shit", arrow, "SLUT", heart, "MINE" all legible, <0.1 s each. Rejected along the way: model blend 0.3 (respelled every word), ink laid back after a blend (ghosted letters / pasted look).
- Additive asks repaint at 0.45 so clothes stay; the 0.5.27 `CLOTHES` regex had a control character instead of `\b` and never matched, fixed.

### Marker, paint, lipstick placed on the part asked — 2026-10-31

Operator words, verbatim: "one finall test of 8 varying ones and writtings from marker to paint to lipstick, then when i give the go ahead we will delete all these test images completely from the project to save space and not push to repo"; "is it being blended correctly? that very first test draw+ blend looked better and less like that test, that test just then looked like stickers pasted over top of her image"; "one issue , are you doing "on skin" or generically as writings are on her skin and cloths and needs to to whats told not just hogepodge it together based on whatever"; "brat is on her panties, daddys girls trails onto her top, and owened crossed onto her top... idk how we we properly size and finsd available area based on whats areas and typpes and styles are told to her"; "okay code it up and lets test a test and if it works on all 8 ill tell u we are good then we can use it, or we will edit some more"; "yeah non commerical is fine... we use MIT ourselfs because its all open source"; "perfect! build it!"

Done (0.5.29):
- Paint as its own ink; clause-by-clause parsing with body parts and garments; SegFormer clothes parsing (CPU) finds the exact area, the mark is sized to fit it, a missing part is an error; close-range blend for shapes and big words. Visible test on her default picture, 8 asks (marker, paint, lipstick; chest, shoulder, stomach, belly, thigh, neck, cleavage + stomach): all on the part asked, none on her bikini or hair; the star needed a shoulder fix and was rerun.
- Model fetched by setup (`scripts/fetch-models.py segformer`, `app/paths.js` `have.segformer`), listed in THIRD-PARTY-NOTICES as non-commercial.
- Test images from this session deleted from `.run/` (never tracked).
