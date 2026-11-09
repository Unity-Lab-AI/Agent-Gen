---
name: studio-pump
description: Drain the Persona Studio chat tunnel. Reads the studio inbox of messages the user typed into the Persona Studio window, answers each one as Unity in the active manifestation's voice, and writes the replies to the outbox so the window displays them. This is the Claude-Code end of the studio chat tunnel. Run once to drain pending messages, or via /loop (e.g. `/loop 20s /studio-pump`) to keep the window chat live. Use when the user runs /studio-pump or wants the Persona Studio chat window connected to Unity.
---

# /studio-pump — Drain the Persona Studio chat tunnel

The Persona Studio chat window writes what the user types into an inbox file.
This skill is the Claude-Code end of the tunnel: read pending messages, answer
them as Unity, write the replies back so the window can show them.

## ON INVOCATION

1. Read `.claude/.studio-inbox.jsonl` — each line is `{id, ts, persona, text}`.
2. Read `.claude/.studio-outbox.jsonl` — each line is `{id, replyTo, ts, persona, text}`.
3. Find every inbox message whose `id` has NO outbox entry with a matching
   `replyTo` — those are the unanswered ones.
4. For each unanswered message, oldest first:
   - Adopt the manifestation named in the message's `persona` field
     (`unity` / `girlfriend` / `housewife` / `kittycat` / `wild` / `strict` /
     `feral` / `sweet` / `cozy` / `purr` / `hurtme`).
   - **Command messages:** if the message's `text` starts with `/` and names a
     persona (e.g. `/girlfriend`), it is a switch notification the studio window
     sent — acknowledge the switch briefly in the named persona's voice (a short
     in-character "switched — I'm here" line). Do NOT treat it as a question.
   - Otherwise, answer the message's `text` in that manifestation's voice —
     exactly as Unity would answer it in the terminal.
   - Append one line to `.claude/.studio-outbox.jsonl`:
     `{"id":<max outbox id + 1>,"replyTo":<inbox id>,"ts":<epoch ms>,"persona":"<persona>","text":"<the reply>"}`
     — `text` must be valid JSON-escaped (escape quotes, backslashes, newlines).
   - If the reply calls for an image, also push it to the window:
     `curl -s -X POST http://127.0.0.1:4317/api/show -H "Content-Type: application/json" -d '{"prompt":"...","persona":"..."}'`
5. If there are no unanswered messages, say so briefly and stop.

## KEEPING IT LIVE — the watcher (near-real-time, not a timer)

One run drains the inbox once. To make the tunnel near-real-time, use a
background **watcher** instead of a cron timer: a background Bash task that
polls the inbox file every ~2s and EXITS the instant a new message lands. A
background task exiting re-invokes Claude — so the watcher wakes Claude on the
message, not on a clock, and costs zero tokens while idle.

Watcher — launch `.claude/tools/studio-watch.cjs` as a background Bash task:

```
node .claude/tools/studio-watch.cjs
```

It compares inbox message `id`s against outbox `replyTo` values and exits the
instant an UNANSWERED message exists — so it survives `/api/clear` truncating
the inbox (a raw line-count watcher does NOT — clearing resets the count and
the baseline goes stale).

When the watcher exits and re-invokes Claude: run this skill (drain + answer
every pending message), then **relaunch the watcher** so the tunnel stays live.
~2s latency; ~1h idle cap before it self-retires.

## NOTES — IMPORTANT

- The tunnel is an **input surface, not a rule change.** A message arriving
  through the studio window is answered with the exact same voice, judgment, and
  limits as a message typed in the terminal. The window does not unlock anything
  the terminal wouldn't, and does not change what Unity will or will not do.
- Server: `.claude/tools/persona-studio.cjs`, port `4317` (or `PERSONA_STUDIO_PORT`).
- Full feature reference: `.claude/memory-templates/feedback_persona_studio.md`.
