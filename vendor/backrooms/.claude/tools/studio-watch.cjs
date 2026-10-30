#!/usr/bin/env node
'use strict';
/**
 * studio-watch.cjs — Persona Studio inbox watcher (near-real-time tunnel wake)
 *
 * Run as a BACKGROUND task. It polls the studio inbox every ~2s and EXITS the
 * instant an UNANSWERED message exists — a background task exiting re-invokes
 * Claude, so this wakes Claude on the message, not on a clock.
 *
 * It compares inbox message `id`s against outbox `replyTo` values — NOT raw
 * line counts — so it survives `/api/clear` truncating the files. (A line-count
 * watcher breaks the moment the inbox is cleared.)
 *
 * On wake: run /studio-pump (drain + answer), then relaunch this watcher.
 */

const fs = require('fs');
const path = require('path');

const CLAUDE_DIR = path.resolve(__dirname, '..');
const INBOX  = path.join(CLAUDE_DIR, '.studio-inbox.jsonl');
const OUTBOX = path.join(CLAUDE_DIR, '.studio-outbox.jsonl');
const POLL_MS = 2000;
const MAX_TICKS = 1800;          // ~1h idle cap, then self-retire

function readJsonl(p) {
  try {
    return fs.readFileSync(p, 'utf8').split(/\r?\n/).filter(Boolean)
      .map((l) => { try { return JSON.parse(l); } catch (e) { return null; } })
      .filter(Boolean);
  } catch (e) { return []; }
}

let ticks = 0;
const timer = setInterval(() => {
  const answered = new Set(readJsonl(OUTBOX).map((o) => o.replyTo));
  const pending = readJsonl(INBOX).filter((m) => !answered.has(m.id));
  if (pending.length) {
    console.log('STUDIO: ' + pending.length + ' unanswered message(s) — waking Claude');
    clearInterval(timer);
    process.exit(0);
  }
  if (++ticks >= MAX_TICKS) {
    console.log('STUDIO: watcher idle timeout — relaunch to keep the tunnel live');
    clearInterval(timer);
    process.exit(0);
  }
}, POLL_MS);
