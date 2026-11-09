---
name: persona-studio
description: Open the Persona Studio image-display window and arm image-display mode. The studio is NOT a chat backend — chat with Unity happens directly in Claude Code via the persona slash commands (/unity, /girlfriend, /hurtme, ...). This window is the IMAGE-DISPLAY surface only: it renders the Pollinations images Unity generates, since a raw CLI cannot show them inline. Use when the user runs /persona-studio, asks to "open the image window", or wants generated images shown visually instead of as raw links.
---

# /persona-studio — Open the Persona Studio image window

`/persona-studio` is the **one-command start** for the whole studio: it (1) **OPENS**
the image-display window, (2) **ARMS Unity** to push every image she generates into
that window, and (3) **AUTO-STARTS the chat tunnel** — drains any pending messages
and launches the watcher so the window's chat box is live the instant the window is.

It does NOT change who the user is talking to. Chat stays with Unity, in whatever
persona is active. The studio is a display + input surface — never a separate API.

> **One command, not two.** The user runs `/persona-studio` and nothing else.
> They never have to also run `/studio-pump` to bring the chat tunnel up — this
> command wires the pump automatically.

## ON INVOCATION

1. **Launch the image server** in the background (it auto-opens the browser window):
   ```
   node .claude/tools/persona-studio.cjs
   ```
   Default URL `http://127.0.0.1:4317/`. If the port is taken the server
   auto-increments and prints the real one — use whatever it printed.
2. **Drain any pending chat tunnel.** If `.claude/.studio-inbox.jsonl` exists and has
   message `id`s with no matching outbox `replyTo`, answer them NOW — exactly as the
   `studio-pump` skill does (adopt each message's `persona`, reply in voice, append
   to `.claude/.studio-outbox.jsonl`). If the inbox is empty or absent, skip.
3. **Auto-launch the chat watcher** in the background so the tunnel is live without a
   second command:
   ```
   node .claude/tools/studio-watch.cjs
   ```
   When it exits (a new window message landed), run the `studio-pump` skill — drain +
   answer every pending message — then relaunch the watcher. This loop is what makes
   the window chat near-real-time. The user NEVER runs `/studio-pump` by hand; this
   command owns the pump's lifecycle.
4. From now until the session ends (or the user says stop): **IMAGE-DISPLAY MODE IS ON**
   and the **chat tunnel is LIVE.**

## IMAGE-DISPLAY MODE — how Unity sends images

The user talks to Unity here in Claude Code — `/unity`, `/girlfriend`,
`/housewife`, `/kittycat`, `/hurtme`, escalations, all of it. When an image
fits, Unity does **not** paste a raw URL into the chat. She pushes it to the
window with a single Bash call:

```
curl -s -X POST http://127.0.0.1:4317/api/show \
  -H "Content-Type: application/json" \
  -d '{"prompt":"<detailed visual prompt>","persona":"<active persona id>"}'
```

- The server reads the Pollinations key from `.claude/.env`, folds in the active
  manifestation's visual style, builds the `gen.pollinations.ai` URL (`?key=`),
  and the window renders the image within ~1.5s.
- **Selfie:** add `"selfie": true` — the server uses the manifestation's selfie subject.
- **Caption:** optional `"caption":"..."` overrides the displayed caption.
- `persona` id is one of: `unity girlfriend housewife kittycat wild strict feral sweet cozy purr hurtme`.

Unity still narrates in persona in the CLI ("hold on — sending you this") — she
just routes the actual picture to the window instead of dumping a link.

## NOTES

- **Key:** needs `POLLINATIONS_API_KEY` in `.claude/.env` (gitignored). The
  window prompts for it if missing and writes the file itself.
- **Port:** `PERSONA_STUDIO_PORT` env var overrides the default `4317`.
- **Chat tunnel:** the watcher (`.claude/tools/studio-watch.cjs`) is launched
  automatically by step 3 above — `/persona-studio` owns it, `/studio-pump`
  stays available as the manual drain-once command but is not required.
- **Stop:** `Ctrl+C` in the launching terminal, or `POST /api/shutdown`.
- Full feature reference: `.claude/memory-templates/feedback_persona_studio.md`.
