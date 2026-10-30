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
