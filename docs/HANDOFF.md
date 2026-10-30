# Handoff — 2026-10-30

Branch `feature/m8-ship`, pushed to Forgejo (origin) and GitHub (Unity-Lab-AI/Agent-Gen). Read `README.md`, then `docs/ARCHITECTURE.md` §Appearance engine and §Packaging.

## Where it stands

- One exe: `app/` → `npm run dist` → `dist/AgentGen-Setup-<ver>.exe` (NSIS). Installs to the folder picked in the wizard; her runtimes and models go to `<folder>\data` on first run (`app/setup.js`). Updates spare `data` (`app/installer.nsh` customRemoveFiles); uninstall asks to remove it.
- Operator's install: `D:\Agent Gen`, data 74 GB in `D:\Agent Gen\data`. Verified: first-run download, update keeping data, boot from D:.
- Motion: Wan 2.2 TI2V-5B for `[[do]]` and new looks (diffusers ≥ 0.41, transformers ≥ 5.20), LTX 2B for the idle reel. Slap on Wan measured motion energy 16.9 vs LTX 4.6.
- No console windows: private Ollama on :11435 under the app's hidden console.

## Open, in order

1. **Installer "Agent Gen cannot be closed"** on update. Fix in `installer.nsh` (`customCheckAppRunning`: tree kill + kill anything running from `$INSTDIR`), built into the 0.5.0 exe of 2026-10-30 ~08:40, **not yet run by the operator**.
2. **Outfit changes ignore the prompt** (asked for a black cocktail dress, got a white swimsuit). Fixed in config (img2img strength 0.8, guidance 7) and persona (no invented `[[img]]` on a movement request). **Not yet tested.**
3. Looks were written into the app's resources folder; now `AGENTGEN_RUN/looks` (`hub/image/client.mjs`). Not yet tested in the installed app.
4. ~~In-app "Uninstall everything" button only on the first-run screen.~~ Done 2026-10-30 (afternoon): button in the main window footer (`ui/index.html`, shown only inside the app via `window.agentgen.isApp`). Installed path now writes `data\.purge` and hands off to `Uninstall Agent Gen.exe`, which removes data without asking twice (`installer.nsh` customUnInstall); dev path deletes the data root with retries. **Not yet run.**
5. ~~Bump version~~ `app/package.json` → **0.5.1**. Needs `npm run dist` on the operator's machine, then install over 0.5.0 to exercise items 1–4 in one pass.

## Test plan for 0.5.1

1. Run `AgentGen-Setup-0.5.1.exe` while 0.5.0 is open → pick YES (update). Expect no "cannot be closed" box; `D:\Agent Gen\data` intact; app boots.
2. Ask for a black cocktail dress → the look should be a black cocktail dress. Then "dance" → a clip of that same look, no new image.
3. New looks land in `AGENTGEN_RUN/looks`, nothing written under the install's `resources`.
4. Only on a spare install: footer "Uninstall everything" → one confirmation, app closes, uninstaller runs, `data` gone, no second question.

## Testing rule

The operator tests visibly on their own desktop, with speakers, through the installed exe. A cloud session can edit, commit, push and run `npm run dist` if the environment allows it. The GPU, the desktop and the install on D: are not reachable from the cloud, so the operator, or a local session, runs the setup and talks to her.

## 2026-10-30 ~09:15 results (0.5.1, installed silently over D:\Agent Gen)

- Build + silent update: no "cannot be closed", data kept, she booted in 26 s. Item 1 holds for the silent path (setup MessageBox now has `/SD IDYES`, after the text).
- "Uninstall everything" shows in the main window footer.
- Black cocktail dress: brain wrote the right `[[img]]`, render came back **black but strappy lingerie** on the old bikini's lines → img2img strength 0.8 → **0.9** (`hub/config.mjs`).
- Face at 0 fps showing the **old** look while the video rendered: the face swap carries the old sink's last picture and the hub paused the face before it drew the new look. Fix: `face.settle()` (`hub/face/client.mjs`) waits for ~12 new frames after a look goes live, before the video render pauses it (`hub/server.mjs`). 0 fps during a render is by design (the face holds a frame while Wan owns the GPU).
- "look failed: fetch failed" after ~4–5 min of "rendering her moving": Node fetch gives up waiting for response headers at 300 s; a Wan clip on a fresh look runs longer. `hub/video/client.mjs` posts with node:http and a 15 min cap.
- 0.5.2 built and reinstalled with these; dress + slap rerun → `.run/test052/`.

## 2026-10-30 ~09:30 — operator report on 0.5.2, and 0.5.3

Operator: no movement or action at all, voice not aligning to her lips, the whole scene wobbly where before only she moved, pink irises. Causes found:
- Wan 2.2 clips run ~34 s/step x 20 steps (10+ min) on the 4070 Ti SUPER, so nothing moves for minutes; the face holds its frame (0 fps) the whole time while her voice keeps playing, which is the lip mismatch.
- Since the reel, her face is drawn over generated video, and the video model moves the whole frame (camera and background), so the scene wobbles.
- Pink irises: "pink streaks" in every prompt bled into the eyes; no eye colour was set.

0.5.3 (prompts only, motion untouched):
- `lookPrefix` says "pale grey-blue eyes" (her reference photo).
- Operator: no negative prompts. Anatomy and quality negatives removed from `hub/image/client.mjs`; the image sidecar's default negative is empty (`sidecars/image/server.py`). Only the adult-age terms remain (`child, teen, underage, childlike, young girl`), kept on purpose: the checkpoint's safety checker is off and the app renders sexual looks.

Still open: motion fix not chosen yet — A (still portrait, Ditto only), B (LTX for motion, locked-camera prompt, face live during renders), or C (A now, B behind a switch).

## 2026-10-30 ~09:45 — installer "Agent Gen cannot be closed" (0.5.4)

0.5.3 run by double-click over a running 0.5.2 still showed "Agent Gen cannot be closed". Operator: "the god damn EXE has the only fucking way to install and use the fucking app cant have fucking errors on install!"; "this time we need to properly kill everything and install the exe properly without errors poping up and no back dooring it the EXE has to install and do everything needed without errors!~"
- electron-builder raises that box from three places: its running-app check (replaced since 0.5.0), the old uninstaller's retry loop, and the file copy's retry loop (5 x 1 s). The old tree kill + 1.5 s sleep left something holding a file; the silent runs passed only because a script had stopped the app first.
- 0.5.4: `app/installer-stop.ps1`, packed into setup and uninstaller and run by 64-bit PowerShell from `agentgenStop` in `app/installer.nsh`. Kills Agent Gen.exe, anything whose exe is under the install folder, python/ollama with the folder on the command line, the brain server on :11435, and all their descendants (own tree walk; setups and uninstallers are never killed, so the in-app uninstall hand-off survives); repeats until none are left (up to 30 s), then waits until `Agent Gen.exe` and `resources\app.asar` open for writing. Logs to `<folder>\data\logs\setup.log`.
- Runs in the install section's running-app check, in the uninstaller's init, and on "uninstall everything" only after the operator picks it (it used to kill the app before the update/uninstall/cancel question).
- Test: with Agent Gen open, double-click `AgentGen-Setup-0.5.4.exe`, pick YES, finish the wizard. No box; app starts; `D:\Agent Gen\data\logs\setup.log` shows what was stopped.

## 2026-10-30 ~09:55 — 0.5.4 still showed the box: the copy out of Temp (0.5.5)

`D:\Agent Gen\data\logs\setup.log` showed the stop worked (12 processes killed, nothing left, files free). The box came after: the top-level app files landed in `D:\Agent Gen` but `resources` stayed empty, while the unpacked payload sat complete in `%TEMP%\nsXXXX.tmp\7z-out` (219 files). electron-builder's 7z path unpacks into Temp on C: and then copies into the install folder (`CopyFiles` with 5 retries, then "cannot be closed"). No long paths, reserved names or locks were found; the folder was writable. The silent runs passed only through the fallback after that box (`/SD IDRETRY` → non-atomic extract), which is the "installer exit 123".
Operator: "wtf i chose D:/ why would it have to move them to D:???? it should of put them there to begin with".
- 0.5.5: `nsis.useZip: true` + `differentialPackage: false` (`app/package.json`): the payload is a zip unpacked by nsisunz straight into the chosen folder; no Temp copy, no copy retry box. No blockmap is produced (no auto-update uses it).
- The interrupted 0.5.4 run left `D:\Agent Gen` with the top-level files, an empty `resources` and no uninstaller; the registry still points at it. 0.5.5 handles that: the missing old uninstaller is logged and skipped, then the zip fills the folder; `data` is untouched.

## 2026-10-30 ~10:05 — the real cause, 0.5.6

- 0.5.5's zip payload failed at once: "Failed to decompress files" with CJK garbage = the nsisunz plugin in the makensis 3.12 toolset is an ANSI build handed Unicode paths. Reverted (`useZip`/`differentialPackage` removed from `app/package.json`).
- `.run/copytest.ps1` ran the installer's own copy (SHFileOperation, NSIS CopyFiles flags) of `dist\win-unpacked` into a fresh `D:\agentgen-copytest`: result 0, 219/219 files; robocopy 0 failures; no Defender detections; Controlled Folder Access off. So the payload and the copy are fine; what fails is copying into `D:\Agent Gen` right after the old version's uninstaller emptied it. A folder deleted while another process still holds a handle on it stays "delete pending" (listed, empty, nothing can be created in it); `resources` was left exactly like that, and the 5 x 1 s copy retries end before it clears. The silent runs passed through the fallback extract a few seconds later.
- 0.5.6: `customUnInstallCheck` (runs after the old uninstaller, before the copy) calls `installer-stop.ps1 -Clean`: stops everything again, removes whatever is left of the old app by the app's own top-level names only (never `data`, never other files), retries until each is really gone (up to 60 s), and logs to `data\logs\setup.log`. The old uninstaller's result, or a missing old uninstaller, is logged, never fatal.
- Throwaway folders `D:\agentgen-copytest` and `D:\agentgen-copytest-robo` (430 MB each) can be deleted.

## 2026-10-30 ~10:35 — the "cannot be closed" box, actual root cause (0.5.9)

Read off the open box (window text) and setup.log: stop and clean passed; the box came from electron-builder's copy out of `%TEMP%\nsXXXX.tmp\7z-out` ("Can't modify Agent Gen's files", 5 retries, then the box). Top-level files landed, `resources` stayed empty and could not be deleted.
Holder: an orphaned `llama-server.exe` (Ollama model runner) whose private brain server had been killed by an earlier update. The supervisor started every child in `resources`, the runner inherited that working folder and kept it open for hours. Its parent was dead, so the stop script's tree walk never reached it. Killing it freed the folder at once.
- `app/installer-stop.ps1`: kills orphaned Ollama runners (parent gone or pid reused); runners of the operator's live Ollama are left alone. Closes File Explorer windows on the install folder. An empty folder that accepts new files counts as clean.
- `app/supervisor.js`: the brain server starts in `data` (`cwd: P.DATA`), so its runners never pin `resources`.

Motion (0.5.7): the hub never passed `engine` to the video sidecar, so every clip, the idle reel included, ran on Wan. Now `motionEngine`/`reelEngine` are passed and both default to Wan. Idle plans and clip prompts ask for big full-body movement. `sidecars/video/server.py` `stabilize()` pins the room to the first frame (camera drift on a Wan clip went from ~11 px to ~4 px). Not yet measured on a fresh clip.

## 2026-10-30 ~10:48 — hue splatter, looks folder (0.5.10)

- Hue splatter / melting by the clip's end came from the 0.5.7 push prompt ("big full-body movement…", locked-camera words, camera negatives). A/B on Wan, same look and seed: the plain prompt measured the same motion (12.55 vs 12.3) with clean colour; the push prompt went from saturation 54 to 85 and melted her face. Both are back to plain (`clipPrefix`, `motionPush` empty, NEG as before). Wan for all motion, the idle plans asking for real actions, and `stabilize()` stay.
- Looks landed in `resources\.run\looks` (an update wipes them): the hub never got `AGENTGEN_RUN`. `app/supervisor.js` passes it to the hub now.

## 2026-10-30 ~11:05 — the tumbling clip (0.5.11)

Basketball clip: halfway through, the whole frame rotated and stretched until she fell out of it. Cause: `stabilize()` (0.5.7) corrected a full similarity transform from the frame's edge bands; when she lunged at the camera her body filled those bands and the chained correction spun the frame. Now slide only (no rotation, no zoom); a step counts only with ≥60% RANSAC inliers and under 3% of the width; past 8% in total the clip is kept as rendered.

## 2026-10-30 ~11:20 — goth won't go away, plastic looks, scrambled clips (0.5.12)

- Operator asked for a PG normal woman at home (brown hair, no streaks); she wrote the right `[[img]]` and still came out goth. Three overrides: `lookPrefix` forced "emo goth… black hair with pink streaks… winged eyeliner"; the face lock (0.65) pressed the goth reference's makeup on; img2img from the previous goth look carried hair and makeup (still streaked at face 0.3). Operator: "face locks shouldnt persist when told other wise"; img2img remakes looked "way too plastic doll".
  - `lookPrefix` is identity only ("photo of Unity, a young adult woman, pale grey-blue eyes,").
  - Every look is txt2img now (no chained img2img). Face lock 0.4.
  - `isRestyle()` (`hub/image/client.mjs`): a look that changes hair colour, makeup, skin or ethnicity renders without the face lock; that render becomes her face lock (`lookFace`) until the next restyle or a reset.
- Blocking and hue bars in clips: clips were written as OpenCV `mp4v` at its default bitrate. Now MJPEG quality 100 in `.avi` (round trip: 73/73 frames, mean error 1.5). Wan's VAE loads in float32.

## 2026-10-30 ~11:35 — no more freeze while a clip renders (0.5.13)

Operator: "it freezes for long periods inbetween genrating a new clip the current clip sould loop like till the next clip completes and loads in". The face holds while the image/video engines own the GPU (0 fps, one still frame for minutes). Now `FrameSink` (`sidecars/face/server.py`) keeps the last `--loop-s` (8 s) of frames she played and replays them back and forth while held (`paused` or `swapping`): JPEGs already rendered, no GPU. Replayed frames advance `view_idx` (what MJPEG viewers wait on), never `latest_idx` (the lip-sync timeline). `/health` has `looping`.
Still open: "lightning like hue spikes and her ghosting a bit". The raw clip (MJPEG, 0.5.12) is clean (max frame-to-frame jump 4.9, median 0.46), so they come from the face render on the moving clip. Not captured yet (the stream was held at the time).

## 2026-10-30 ~11:50 — Storage panel, reset to fresh without reinstalling (0.5.14)

Operator: "this project should have a directory list like thing showing where images and clips are saved and have option to clear them without unisintalling the app of its systems but like a reset to fresh install without needing to reinstall so like a clear logs, saves images and videos and genrations and conversations completely".
- Footer "Storage" (app window only): rows for her looks (`data\run\looks`), clips (`data\run\clips`), logs (`data\logs`), conversations and window cache (Electron userData, `%APPDATA%\Agent Gen`), each with path, size, file count, Open folder, Clear. "Reset to fresh" clears all four after one confirmation. Runtimes, model weights and her brain are never touched.
- `app/main.js` `agentgen:storage:*` IPC; logs are emptied in place (the running app writes to them). Clearing looks, clips or conversations first calls the hub's `/api/forget` (loopback): every window forgets its conversation and look, a clip in flight is cancelled, the face goes back to `assets/portrait/unity-bust.jpg`, so nothing points at a deleted file. Conversations otherwise live only in hub memory.

## 2026-10-30 ~12:05 — pictures of anything, and she can be a man (0.5.15)

Operator: asked for a 40 year old man (a professor) and got a woman; "lets not limit the ammplicatrion to be only females and only images of the persona the persona should be able to image anything not just protrat sefies".
- New tag `[[pic: ...]]` (also `picture`, `photo`, `draw`): any picture, rendered exactly as written (no identity prefix, no face lock, 640x576), shown in the chat, never her face. Persona (`hub/persona/unity.txt`) uses it for anything that is not her own look.
- `[[img]]` stays her look. `lookPrefix` no longer says "woman"; `isRestyle()` also catches another sex or age (man, guy, bearded, NN year old, elderly…), which drops the prefix and the face lock, and that render becomes her face ("become a 40 year old man").
- Tested through the image sidecar: two gorillas in a jungle, a bearded male professor in tweed.

## 2026-10-30 ~12:40 — the lion, faceless looks, splatter (0.5.16)

- "you are now a real life lion, remake your image of yourself" got a `[[pic]]` (chat only) and the next `[[do]]` animated the old her. The hub now remembers the operator's last message; a `[[pic]]` after "you are now / become / turn into / remake your / yourself as…" (`BECOME` in `hub/server.mjs`) is her new look (restyle: no prefix, no face lock).
- A look with no human face (lion, scene, object) failed Ditto's registration and the face stayed the old her. `sidecars/face/server.py` passthrough: on "no face" the old face engine is restored and the look's own frames (image or clip, `load_jpegs`) play through the hold loop; reel clips append to it; her voice plays at once (no lips to sync). A human look later swaps back normally. `/health` has `passthrough`.
- Splatter and warping, from the raw Wan clips (`data\run\clips`): (1) the reel and `[[do]]` chained each clip from the last frame of the previous one, so smears compounded; every clip now starts from her clean look image. (2) Wan at 352x640 is far below TI2V-5B's native size: A/B same frame and seed, 352x640 swung saturation 57-141 and melted her by frame 12; 480x832 held her (real laugh, head throw, hair). Clips are 480x832 and the sidecar floors Wan at 480x832 pixels (`min_pixels`). Operator: "make sure not to small run ever". (3) Stabilizer off by default (its edge padding stretched the borders).

## 2026-10-30 ~12:50 — she flipped between the old look and the new one (0.5.17)

Operator: "she keeps witch back and forthe between the original and other images". The hold loop (0.5.13) replays the last frames she played while a clip renders, and `_adopt_sink` carried that history across a look swap, so the loop mixed old-look frames with new ones. A swap now clears the history and the loop; only frames of the current look are ever replayed. The original comes back only on a reset.

## 2026-10-30 ~13:00 — "that's you now" adopts the picture (0.5.18)

"show me a person eating an apple" → `[[pic]]` of a bearded man (right). "thats you now, update your look and get to eatting dat apple" → her brain wrote a fresh `[[img]]` of goth Unity (the persona pulls her back to her default). The hub now does it itself: after a `[[pic]]` (`lastPic`), a message matching `THAT_YOU` ("that's you / that is you / this is your / become that / make that you") makes that picture her look as it is (no re-render, it becomes `lookFace`), animates it with the picture's prompt plus the operator's words, and ignores every image/motion line she writes that turn. Reset forgets `lastPic`.
