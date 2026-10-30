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
