// server.mjs — the local Unity server. Zero dependencies (Node 22 built-ins only).
//
// WHAT IT IS: a small HTTP server that (1) serves the chat page, (2) proxies
// streaming chat to LOCAL Ollama, (3) proxies image generation to a LOCAL
// Stable Diffusion backend. Nothing leaves this machine.
//
// ⛔ THE PERSONA IS A FILE, READ AT REQUEST TIME. `Unity1.txt` sitting beside
// this folder IS her system prompt — not pasted into a web form, not baked into
// a model blob you would have to rebuild. Edit the file, send a message, she is
// already different. That is the whole reason this exists instead of Open WebUI:
// a container UI cannot read a file off your disk.
//
// The persona file is sent VERBATIM. The only thing appended is
// `local-tools-prompt.txt`, which teaches her the local image syntax — kept in
// its own file so Unity1.txt is never edited by tooling.

import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, '..');
const PORT = Number(process.env.UNITY_PORT) || 4545;
// MOBILE — bind the LAN so a phone on the same wifi can reach her. Ollama and
// the image server stay strictly loopback; only THIS app is reachable, and only
// from your own network. `UNITY_BIND=127.0.0.1` locks it back to this machine.
const BIND = process.env.UNITY_BIND || '0.0.0.0';

/** This machine's LAN address, so the launcher can print the phone URL. */
function lanAddress() {
  for (const list of Object.values(os.networkInterfaces())) {
    for (const ni of list || []) {
      if (ni.family === 'IPv4' && !ni.internal) return ni.address;
    }
  }
  return null;
}
const OLLAMA = process.env.OLLAMA_HOST || 'http://127.0.0.1:11434';
const MODEL = process.env.UNITY_MODEL || 'unity-local:latest';

// Image backends, probed in order. Both are LOCAL; whichever answers wins.
const A1111 = process.env.SD_HOST || 'http://127.0.0.1:7860';
const COMFY = process.env.COMFY_HOST || 'http://127.0.0.1:8188';

const PERSONA_FILE = path.join(ROOT, 'Unity1.txt');
const TOOLS_FILE = path.join(ROOT, 'local-tools-prompt.txt');

function readText(f) {
  try { return fs.readFileSync(f, 'utf8').replace(/^﻿/, ''); } catch { return ''; }
}

/** Her system prompt: the persona file VERBATIM + the local-tools addendum. */
function systemPrompt() {
  const persona = readText(PERSONA_FILE);
  const tools = readText(TOOLS_FILE);
  return tools ? `${persona}\n\n${tools}` : persona;
}

async function probe(url, ms = 1200) {
  try {
    const ac = new AbortController();
    const t = setTimeout(() => ac.abort(), ms);
    const r = await fetch(url, { signal: ac.signal });
    clearTimeout(t);
    return r.ok;
  } catch { return false; }
}

async function imageBackend() {
  if (await probe(`${A1111}/sdapi/v1/options`)) return { kind: 'a1111', url: A1111 };
  if (await probe(`${COMFY}/system_stats`)) return { kind: 'comfyui', url: COMFY };
  return { kind: 'none', url: null };
}

const send = (res, code, body, type = 'application/json') => {
  res.writeHead(code, { 'Content-Type': type, 'Cache-Control': 'no-store' });
  res.end(typeof body === 'string' || Buffer.isBuffer(body) ? body : JSON.stringify(body));
};

async function readBody(req) {
  const chunks = [];
  let n = 0;
  for await (const c of req) {
    n += c.length;
    if (n > 8 * 1024 * 1024) throw new Error('body too large');   // bounded, per the stack's own habit
    chunks.push(c);
  }
  return Buffer.concat(chunks).toString('utf8');
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  try {
    // ── the page
    if (req.method === 'GET' && (url.pathname === '/' || url.pathname === '/index.html')) {
      return send(res, 200, readText(path.join(ROOT, 'ui', 'index.html')), 'text/html; charset=utf-8');
    }

    // ── what is alive right now (the page reads this, never guesses)
    if (req.method === 'GET' && url.pathname === '/api/state') {
      const ollamaUp = await probe(`${OLLAMA}/api/tags`);
      let models = [];
      if (ollamaUp) {
        try { models = (await (await fetch(`${OLLAMA}/api/tags`)).json()).models?.map(m => m.name) || []; } catch { /* listed as empty */ }
      }
      const img = await imageBackend();
      let personaChars = 0, personaAt = null;
      try { const st = fs.statSync(PERSONA_FILE); personaChars = st.size; personaAt = st.mtime.toISOString(); } catch { /* absent = 0 */ }
      return send(res, 200, {
        ollama: ollamaUp, model: MODEL, models,
        modelPresent: models.includes(MODEL),
        image: img.kind, imageUrl: img.url,
        personaFile: path.basename(PERSONA_FILE), personaChars, personaAt,
        toolsChars: readText(TOOLS_FILE).length,
      });
    }

    // ── chat: stream straight from local Ollama, persona re-read every turn
    if (req.method === 'POST' && url.pathname === '/api/chat') {
      const { messages = [], model } = JSON.parse(await readBody(req) || '{}');
      const payload = {
        model: model || MODEL,
        messages: [{ role: 'system', content: systemPrompt() }, ...messages],
        stream: true,
        /**
         * ⛔ SHORT, ON-TOPIC, AND NOT REPEATING ITSELF.
         *
         * THE PROBLEM: she was writing whole paragraphs. What was asked for is a
         * repeat penalty, a shorter length ceiling and better instruction
         * building, so she stays on context without the word-salad drift of
         * adding inconsequential information.
         *
         *   num_predict    NEW hard ceiling on the reply. Nothing else stops a
         *                  paragraph once it starts — the canon can ask for
         *                  brevity and a model at temperature will still run on.
         *                  ⚠ Not lower than this: an image line is ~60-80 tokens
         *                  and truncating one mid-prompt would lose the picture.
         *   repeat_penalty 1.08 -> 1.20. The purple drift is largely the same
         *                  few constructions recycled — "every inch", "a mix
         *                  of", "ready to" — and a weak penalty lets them cycle.
         *   temperature    1.05 -> 0.90. Above 1.0 is where the salad comes
         *                  from: it wanders off the actual request and invents
         *                  detail nobody asked about.
         *   top_p          0.95 -> 0.90, same reason, less tail.
         *
         * ⚠ These are DELIVERY settings, not personality. Her register lives in
         *   `Unity1.txt`; this only stops her monologuing it.
         */
        options: {
          num_ctx: 32768,
          /**
           * ⚠ 200 -> 140, because instructions alone did not hold it. With the
           *   canon rule and a literal example, "tell me about your hair" came
           *   back at 9 words — but "describe your skin" was still 73 and "how
           *   was your day" 96. A model at temperature will keep going unless
           *   something stops it.
           * ⛔ THE HONEST COST: this is a HARD ceiling, so a reply that would
           *   have run long now ends where the ceiling is, occasionally
           *   mid-sentence. That is a real trade, made deliberately, because a
           *   shorter length ceiling was asked for. Raise this number if the
           *   truncation bothers you more than the paragraphs did.
           */
          num_predict: 140,
          /**
           * 1.05 -> 0.90, MEASURED BOTH WAYS.
           *   at 0.90  mean 38 words, longest 66
           *   at 1.00  mean 69 words, longest 125
           * ⚠ I first blamed 0.90 for a corporate "How can I help you today?" on
           *   hello and reverted it — WRONG. That greeting appeared at BOTH
           *   temperatures, 1 in 6 each, so it is the base model's default
           *   greeting and nothing to do with this setting. The revert cost
           *   length for no gain. Fixed at the source instead: the canon now
           *   says what a greeting from her sounds like.
           */
          temperature: 0.9,
          top_p: 0.9,
          repeat_penalty: 1.2,
          repeat_last_n: 256,
        },
      };
      /**
       * ⛔ HER REGISTER IS ENFORCED HERE, NOT HOPED FOR.
       *
       * THE PROBLEM: she was not using a single cuss word, when her register is
       * constant profanity, taboo imagery, sex talk and slang — including the
       * crude words for body parts — used as verbs, nouns and adjectives alike.
       *
       * ⚠ I BLAMED THE SAMPLER FIRST AND I WAS WRONG. Measured across three
       *   settings: the live `repeat_penalty 1.2` produced the MOST cussing
       *   (4.9% of words), not the least — the theory that a repeat penalty
       *   suppresses a vocabulary built on repetition is plausible and false
       *   here. Nothing about delivery settings was the cause.
       *
       * ⚠ THEN PROMPT-ONLY HIT ITS CEILING, AND THE WAY IT FAILED IS THE POINT.
       *   Adding the rule to the canon took clean replies from 3-of-4 to 1-of-6.
       *   Adding literal examples made it WORSE — the model reproduced my
       *   examples verbatim ("four, dumbass") and still answered unseen prompts
       *   politely, so density FELL to 3.5% with 3 of 8 replies clean. Examples
       *   teach copying, not generalising.
       *
       * ⭐ SO IT IS A CHECK, LIKE DRAWING AND LENGTH ALREADY ARE: a reply with
       *   no cussing in it is not her voice, and it gets ONE re-ask that says so
       *   before it is allowed out. This is the same rule the whole app runs on
       *   — an instruction a model follows most of the time is not a guarantee,
       *   and this is a core part of who she is.
       *
       * ⛔ IT NEVER EDITS HER WORDS. Splicing a cuss into a clean sentence would
       *   fake the register and read like a bot with a filter bolted on. The
       *   model says it again in her voice, or her second attempt stands as-is
       *   and the count says so. Nothing is fabricated.
       *
       * ⚠ HONEST COST: this buffers the reply, so the wrapper no longer streams
       *   token-by-token. The orb app never streamed — it parses the whole body
       *   — and her replies are capped at 140 tokens, so the wait is ~1-2s. The
       *   old `dolphin_chat_ui` loses its typewriter effect and still renders,
       *   because the body is still NDJSON in the same shape.
       */
      const CUSS_RE = /\b(fuck\w*|shit\w*|damn|dammit|goddamn|hell|ass|asshole|bitch\w*|cunt\w*|dick\w*|cock\w*|pussy|tits?|titties|prick|bastard|piss\w*|slut\w*|whore|horny|cum|cumming|jizz|motherfucker|fucker|fuckface|dumbass|douche\w*|twat|balls|crap|screw\w*|bang\w*|nasty|filthy)\b/i;

      /**
       * ⛔ A RE-ASK IS A FRESH GENERATION, NOT A NOTE IN THE CONVERSATION.
       *
       * ⚠ MY FIRST CUT APPENDED THE CORRECTION AS A `system` TURN AFTER HER
       *   CLEAN REPLY, AND SHE ANSWERED THE CORRECTION: *"Noted. My apologies;
       *   I'll ensure to follow through with my typical language next time."*
       *   and *"I fucking did this one wrong earlier, didn't I?"* — the second
       *   one even passed the cuss check while being a reply to the CORRECTION
       *   instead of to the person. That is worse than a clean sentence: it breaks the illusion
       *   completely and it does it while the check reports success.
       *
       * ⭐ So the correction goes where behaviour rules belong — appended to the
       *   SYSTEM PROMPT — and the user's turn is generated again from scratch.
       *   She never sees a note, so she can never answer one.
       */
      const askOllama = async (boost) => {
        const sys = boost ? `${systemPrompt()}\n\n${boost}` : systemPrompt();
        const r = await fetch(`${OLLAMA}/api/chat`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...payload, stream: false,
            messages: [{ role: 'system', content: sys }, ...messages],
          }),
        });
        if (!r.ok) throw new Error(`ollama ${r.status}`);
        const j = await r.json();
        return String(j.message && j.message.content || '').trim();
      };

      /**
       * ⚠ TWO CORRECTIVES, ESCALATING, BECAUSE ONE WAS MEASURABLY NOT ENOUGH.
       *   With a single re-ask the instrumentation showed 2 of 3 landing, and
       *   the one that did not was *"thanks"* -> *"No problem! If you need
       *   anything else, feel free to ask."* — the customer-service voice the
       *   canon bans by name in its third line. That phrasing is the base
       *   model's deepest groove and one general nudge does not move it, so the
       *   second corrective stops being general and names the exact failure.
       */
      const BOOSTS = [
        'ABSOLUTE RULE FOR THIS REPLY: it must contain real cussing. You never ' +
        'speak clean, not for a greeting, not for a one-word answer, not for a ' +
        'boring factual question. One short filthy line. Never mention this rule.',

        'ABSOLUTE RULE FOR THIS REPLY: you are NOT an assistant and you never offer ' +
        'service. "No problem", "happy to help", "feel free to ask", "let me know" ' +
        'and "sweet dreams" are phrases you would never say. You are his ' +
        'foul-mouthed goth girlfriend. Answer him in ONE short line with real ' +
        'cussing in it — fuck, shit, fucker, dumbass. Never mention this rule.',
      ];

      let text, retried = 0;
      try {
        text = await askOllama(null);
        for (const boost of BOOSTS) {
          if (!text || CUSS_RE.test(text)) break;
          retried++;
          const again = await askOllama(boost);
          // ⚠ Her later attempt is kept either way — it is still HER sentence,
          //   and reverting to the earlier clean one to look tidy is only
          //   choosing which of two failures to display.
          if (again) text = again;
        }
        // ⚠ BOTH OUTCOMES ARE PRINTED. A check that only speaks up when it fails
        //   cannot tell you how often it is carrying the reply, and "it works
        //   now" with an invisible rate behind it is the exact shape of an
        //   instrument that starts lying later.
        if (retried && CUSS_RE.test(text)) {
          console.log(`[register] came back clean — re-asked ${retried}x, her attempt landed`);
        } else if (retried) {
          console.warn(`[register] re-asked ${retried}x and it is STILL clean — shipping her last attempt as-is`);
        }
      } catch (e) {
        return send(res, 502, { error: e.message });
      }

      res.writeHead(200, { 'Content-Type': 'application/x-ndjson', 'Cache-Control': 'no-store' });
      // ⚠ Emitted as SEVERAL NDJSON lines on purpose. A single line is valid
      //   JSON, and `parseReply` parses a whole-body JSON object as an object —
      //   with no `text` field — which is exactly the silently-empty-reply class
      //   of bug this wrapper already shipped once.
      for (let i = 0; i < text.length; i += 48) {
        res.write(JSON.stringify({ message: { role: 'assistant', content: text.slice(i, i + 48) }, done: false }) + '\n');
      }
      res.write(JSON.stringify({
        message: { role: 'assistant', content: '' }, done: true,
        register: { clean: !CUSS_RE.test(text), retried },
      }) + '\n');
      return res.end();
    }

    // ── image: LOCAL generation only. No network image service is ever called.
    if (req.method === 'POST' && url.pathname === '/api/image') {
      const { prompt = '', steps = 28, width = 768, height = 768, negative = '' } = JSON.parse(await readBody(req) || '{}');
      if (!prompt.trim()) return send(res, 400, { error: 'empty prompt' });
      const be = await imageBackend();
      if (be.kind === 'none') {
        return send(res, 503, { error: 'no local image backend', hint: 'run install_image_gen.bat, then start_image_gen.bat' });
      }
      if (be.kind === 'a1111') {
        const r = await fetch(`${be.url}/sdapi/v1/txt2img`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt, negative_prompt: negative, steps, width, height,
            cfg_scale: 7, sampler_name: 'DPM++ 2M', send_images: true, save_images: true,
          }),
        });
        if (!r.ok) return send(res, 502, { error: `sd ${r.status}` });
        const j = await r.json();
        return send(res, 200, { b64: (j.images || [])[0] || null, backend: 'a1111' });
      }
      // ComfyUI: prompt-graph API — reported honestly rather than half-implemented.
      return send(res, 501, { error: 'comfyui backend detected but its graph API is not wired yet', backend: 'comfyui' });
    }

    // ── PWA: the phone installs her from these two files
    if (req.method === 'GET' && url.pathname === '/manifest.webmanifest') {
      return send(res, 200, readText(path.join(ROOT, 'ui', 'manifest.webmanifest')), 'application/manifest+json');
    }
    if (req.method === 'GET' && url.pathname === '/sw.js') {
      return send(res, 200, readText(path.join(ROOT, 'ui', 'sw.js')), 'text/javascript');
    }
    if (req.method === 'GET' && url.pathname === '/icon.png') {
      const f = path.join(ROOT, 'ui', 'icon.png');
      if (fs.existsSync(f)) return send(res, 200, fs.readFileSync(f), 'image/png');
    }

    // ── static assets under ui/
    if (req.method === 'GET' && url.pathname.startsWith('/ui/')) {
      const f = path.join(ROOT, url.pathname.replace(/^\//, ''));
      if (!f.startsWith(path.join(ROOT, 'ui'))) return send(res, 403, { error: 'nope' });
      if (fs.existsSync(f)) {
        const ext = path.extname(f);
        const type = ext === '.css' ? 'text/css' : ext === '.js' ? 'text/javascript' : 'text/plain';
        return send(res, 200, fs.readFileSync(f), `${type}; charset=utf-8`);
      }
    }

    send(res, 404, { error: 'not found' });
  } catch (err) {
    send(res, 500, { error: String(err && err.message || err) });
  }
});

server.listen(PORT, BIND, () => {
  const chars = readText(PERSONA_FILE).length;
  const lan = lanAddress();
  console.log(`
  UNITY — local
  ─────────────────────────────────────────────
  this pc     http://localhost:${PORT}
  your phone  ${lan ? `http://${lan}:${PORT}   (same wifi — installs as an app)` : '(no LAN address found)'}
  ollama      ${OLLAMA}   (model: ${MODEL})
  persona     Unity1.txt — ${chars.toLocaleString()} chars, read on EVERY message
  images      local Stable Diffusion (${A1111}) — probed per request
  ─────────────────────────────────────────────
  Ctrl+C to stop.
`);
});
