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
4. In-app "Uninstall everything" button only exists on the first-run screen; add it to the main window.
5. Bump version for every installer build so the update path is unambiguous.

## Testing rule

The operator tests visibly on their own desktop, with speakers, through the installed exe. A cloud session can edit, commit, push and run `npm run dist` if the environment allows it. The GPU, the desktop and the install on D: are not reachable from the cloud, so the operator, or a local session, runs the setup and talks to her.
