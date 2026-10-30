#!/usr/bin/env node
'use strict';
/**
 * persona-studio.cjs — Unity AI Lab · Persona Studio (chat tunnel + image window)
 *
 * A zero-dependency Node server + browser popup. It does NOT generate anything
 * itself — it is a relay:
 *   - CHAT TUNNEL: the window posts what the user types to an inbox file; Unity
 *     answers it from Claude Code via the /studio-pump skill and writes replies
 *     to an outbox file; the window polls and shows them. Replies are the real
 *     Unity (Claude), governed exactly as in the terminal — never a third party.
 *   - IMAGE WINDOW: Unity pushes generated Pollinations images; the window
 *     renders them inline, since a raw CLI cannot.
 *
 *   Chat in:    POST /api/say      {text, persona}      -> inbox file
 *   Chat out:   GET  /api/replies?since=<id>            <- outbox file
 *   Image in:   POST /api/show     {prompt, persona}
 *   Window polls GET /api/feed and GET /api/replies.
 *
 *   Run:  node .claude/tools/persona-studio.cjs
 *   Port: PERSONA_STUDIO_PORT env var (default 4317)
 *   Auth: every POST needs header X-Studio-Token (or ?token=) = .claude/.studio-token, kept across restarts
 *   Key:  .claude/.env  POLLINATIONS_API_KEY  (window prompts if missing)
 *   Life: the server dies when its browser window closes — a pagehide beacon
 *         kills it instantly, and a poll-heartbeat watchdog is the backstop for
 *         crashes / kills. No orphan servers pile up across relaunches.
 *
 * Node built-ins only — no npm install, ever.
 */

const http = require('http');
const fs   = require('fs');
const path = require('path');
const { exec } = require('child_process');
const crypto = require('crypto');

const TOOLS_DIR  = __dirname;
const CLAUDE_DIR = path.resolve(TOOLS_DIR, '..');
const ENV_PATH   = path.join(CLAUDE_DIR, '.env');
const HTML_PATH   = path.join(TOOLS_DIR, 'persona-studio.html');
const INBOX_PATH  = path.join(CLAUDE_DIR, '.studio-inbox.jsonl');
const OUTBOX_PATH = path.join(CLAUDE_DIR, '.studio-outbox.jsonl');
const OVERLAY_PATH = path.join(TOOLS_DIR, 'stream-overlay.html');
const STREAM_LOG   = path.join(CLAUDE_DIR, '.stream-log.jsonl');
const BASE_PORT   = parseInt(process.env.PERSONA_STUDIO_PORT, 10) || 4317;
const TOKEN_PATH  = path.join(CLAUDE_DIR, '.studio-token');
const ROOT_DIR    = path.resolve(CLAUDE_DIR, '..');

// ── the studio token: every mutating request must carry it ──────────────────
// Written beside the inbox for the local helper scripts (header X-Studio-Token)
// and injected into the studio page this server serves. Read-only GETs stay open.
// It is KEPT across restarts: a page opened before a restart held the old one and every send failed
// (owner, 2026-10-13, twice -- once per restart: "send failed: forbidden: missing or wrong studio token").
// A well-formed token file is reused; a new one is minted only when none exists or it is malformed.
let TOKEN = '';
try { const t = fs.readFileSync(TOKEN_PATH, 'utf8').trim(); if (/^[0-9a-f]{48}$/.test(t)) TOKEN = t; } catch (e) { /* first start */ }
if (!TOKEN) {
  TOKEN = crypto.randomBytes(24).toString('hex');
  try { fs.writeFileSync(TOKEN_PATH, TOKEN, { mode: 0o600 }); } catch (e) { console.error('persona-studio: could not write token file - ' + e.message); }
}
function localHostOk(req) {
  const port = req.socket.localPort;
  const host = String(req.headers.host || '').toLowerCase();
  return host === '127.0.0.1:' + port || host === 'localhost:' + port;
}
function originOk(req) {
  const o = req.headers.origin;
  if (!o) return true;   // non-browser local helpers send no Origin
  const port = req.socket.localPort;
  return o === 'http://127.0.0.1:' + port || o === 'http://localhost:' + port;
}
function tokenOk(req, query) {
  const t = String(req.headers['x-studio-token'] || query.token || '');
  return t.length === TOKEN.length && crypto.timingSafeEqual(Buffer.from(t), Buffer.from(TOKEN));
}

// ── names that must never reach the public stream (owner handle etc.) ──────
function secretWords() {
  const out = [];
  for (const p of [path.join(ROOT_DIR, '.local', 'autopilot', 'secret-words.txt'), path.join(ROOT_DIR, '.local', 'tw', 'owner.txt')]) {
    try {
      for (const w of fs.readFileSync(p, 'utf8').split(/\r?\n/)) {
        const t = w.trim();
        if (t.length >= 3 && !t.startsWith('#')) out.push(t);
      }
    } catch (e) { /* file optional */ }
  }
  return out;
}
function scrub(text, words) {
  let t = String(text || '');
  for (const w of words) t = t.split(new RegExp(w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')).join('my friend');
  return t;
}

// ── Persona roster — id → display label + accent colour ─────────────────────
const PERSONAS = {
  unity:      { label: 'Unity',              color: '#ff4fa3', tag: 'goth-emo base' },
  girlfriend: { label: 'Unity · Girlfriend', color: '#ff8fab', tag: '22yo brunette' },
  housewife:  { label: 'Unity · Housewife',  color: '#e0a96d', tag: '34yo domestic' },
  kittycat:   { label: 'Unity · Kittycat',   color: '#c79bff', tag: '23yo catgirl' },
  wild:       { label: 'Unity · Wild',       color: '#ff2d6d', tag: 'girlfriend escalated' },
  strict:     { label: 'Unity · Strict',     color: '#c87f3a', tag: 'housewife escalated' },
  feral:      { label: 'Unity · Feral',      color: '#9b5fff', tag: 'kittycat escalated' },
  sweet:      { label: 'Unity · Sweet',      color: '#ffb3d1', tag: 'girlfriend default' },
  cozy:       { label: 'Unity · Cozy',       color: '#e8c463', tag: 'housewife default' },
  purr:       { label: 'Unity · Purr',       color: '#d4b3ff', tag: 'kittycat default' },
  hurtme:     { label: 'Unity · Hurt Me',    color: '#c0392b', tag: 'violence-play (no sexual content)' },
};
const ALIASES = { sexy: 'unity' };   // /sexy = return to normal Unity
const BASE_FORM = {
  wild: 'girlfriend', sweet: 'girlfriend', strict: 'housewife', cozy: 'housewife',
  feral: 'kittycat', purr: 'kittycat', hurtme: 'unity',
};

// Each manifestation's visual signature — folded into every image prompt.
const IMG_STYLE = {
  unity:      'dark cinematic, gothic mood, dramatic chiaroscuro lighting, deep shadows, high contrast, hyper detailed, 4k',
  girlfriend: 'soft warm lighting, cozy intimate mood, golden hour glow, gentle bokeh, film-photo aesthetic, 4k',
  housewife:  'warm domestic setting, golden-hour light, homey cozy mood, soft inviting tones, 4k',
  kittycat:   'playful pastel-dark palette, soft feline whimsy, dreamy lighting, cute mischievous mood, 4k',
  wild:       'intense high-contrast, feral energy, saturated colors, dramatic motion, raw and unrestrained, 4k',
  strict:     'stern formal composition, controlled lighting, deep warm shadows, disciplined elegance, 4k',
  feral:      'chaotic vivid energy, motion blur, electric palette, untamed and kinetic, 4k',
  sweet:      'soft pastel glow, tender warm light, delicate gentle mood, dreamy, 4k',
  cozy:       'candlelit warmth, soft domestic glow, deeply comfortable and serene, 4k',
  purr:       'sleepy soft lighting, plush warm tones, drowsy gentle whimsy, 4k',
  hurtme:     'brutal high-contrast, dark grit, dramatic hard shadow, raw cinematic, gothic damage aesthetic, 4k',
};
const SELFIE_SUBJECT = {
  unity:      'a phone selfie of a 25-year-old goth-emo woman, black hair with pink streaks, pale skin, heavy smudged eyeliner, sharp features, intense eyes, black leather jacket, choker collar',
  girlfriend: 'a phone selfie of a 22-year-old freckled brunette woman, dark hair with auburn streaks, big brown eyes, oversized hoodie, messy bun, soft smile',
  housewife:  'a phone selfie of a 34-year-old woman, blonde with dark roots, hazel eyes, summer dress and apron, warm domestic kitchen',
  kittycat:   'a phone selfie of a 23-year-old catgirl, white hair with black streaks, real cat ears and a fluffy tail, mismatched gold and blue eyes, oversized t-shirt',
};

// ── live state ──────────────────────────────────────────────────────────────
const feed = [];          // { id, url, prompt, caption, persona, label, color, ts }
let seq = 0;
let activePersona = 'unity';

// ── window-presence watchdog ────────────────────────────────────────────────
// The browser polls /api/feed + /api/replies every ~1.5s. That poll stream is
// the window's heartbeat: once a window has connected, a silence longer than
// WINDOW_TIMEOUT_MS means the window is gone (closed, crashed, navigated away)
// and this server exits instead of lingering as an orphan. STARTUP_GRACE_MS
// covers the gap before the browser first loads — and also retires a server
// whose window never opened at all. A pagehide sendBeacon to /api/shutdown
// gives instant death on a clean close; this watchdog is the backstop.
const WINDOW_TIMEOUT_MS = 8000;    // ~5 missed polls => window is gone
const STARTUP_GRACE_MS  = 60000;   // browser never showed => nothing to serve
let   lastBeat   = Date.now();
let   windowSeen = false;

// ── .env helpers ────────────────────────────────────────────────────────────
function readEnv() {
  const out = {};
  if (!fs.existsSync(ENV_PATH)) return out;
  for (const line of fs.readFileSync(ENV_PATH, 'utf8').split(/\r?\n/)) {
    if (line.trim().startsWith('#')) continue;
    const m = line.match(/^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$/);
    if (m) out[m[1]] = m[2];
  }
  return out;
}
function writeKey(key) {
  let lines = fs.existsSync(ENV_PATH) ? fs.readFileSync(ENV_PATH, 'utf8').split(/\r?\n/) : [];
  let found = false;
  lines = lines.map((l) => {
    if (/^\s*POLLINATIONS_API_KEY\s*=/.test(l)) { found = true; return 'POLLINATIONS_API_KEY=' + key; }
    return l;
  });
  if (!found) {
    if (lines.length && lines[lines.length - 1] !== '') lines.push('');
    lines.push('POLLINATIONS_API_KEY=' + key);
  }
  fs.writeFileSync(ENV_PATH, lines.join('\n'));
}
function hasKey(env) { return localImages(env) || !!(env && env.POLLINATIONS_API_KEY && env.POLLINATIONS_API_KEY.trim()); }

// ── Local image backend: the Unity 3D project's own Stable Diffusion server ──
// Owner, 2026-10-08: "ther is no pollinations you need to fix it up with the 3d models default
// image gen". Default backend is now LOCAL (sd_server.py, A1111-style /sdapi/v1/txt2img on
// :7860). Set STUDIO_IMAGE_BACKEND=pollinations in .claude/.env to go back.
const IMG_DIR = path.join(TOOLS_DIR, '..', '.studio-images');
let camState = { url: '', caption: '', ts: 0 };
// The stream's picture survives a studio restart: kept in cam-state.json beside the images.
const CAM_STATE = path.join(IMG_DIR, 'cam-state.json');
try { camState = JSON.parse(fs.readFileSync(CAM_STATE, 'utf8')); } catch (e) {
  try {
    const last = fs.readdirSync(IMG_DIR).filter((f) => /^cam-\d+\.png$/.test(f)).sort().pop();
    if (last) camState = { url: '/img/' + last, caption: '', ts: Date.now() };
  } catch (e2) { /* no images yet */ }
}
// Unity's voice: each spoken line as a WAV the overlay page plays -- in OBS's browser source that
// audio goes to the stream (desktop audio stays muted).
let voiceState = { url: '', ts: 0 };
function localImages(env) { return ((env && env.STUDIO_IMAGE_BACKEND) || 'local') === 'local'; }
function sdUrl(env) { return (env && env.STUDIO_SD_URL) || 'http://127.0.0.1:7860'; }
function renderLocal(prompt, env, faceUrl, caption, scene) {
  return new Promise((resolve, reject) => {
    const u = new URL((faceUrl || sdUrl(env)) + '/sdapi/v1/txt2img');
    const data = JSON.stringify({ prompt: prompt, caption: caption || '', scene: scene || '', steps: 26, width: 640, height: 768, cfg_scale: 7 });   // caption: her line, for props
    const r = http.request({ hostname: u.hostname, port: u.port, path: u.pathname, method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) } }, (resp) => {
      let buf = ''; resp.setEncoding('utf8');
      resp.on('data', (c) => { buf += c; });
      resp.on('end', () => {
        try {
          const j = JSON.parse(buf);
          if (!j.images || !j.images[0]) return reject(new Error(j.error || 'no image'));
          resolve(Buffer.from(j.images[0], 'base64'));
        } catch (e) { reject(e); }
      });
    });
    r.on('error', reject);
    r.setTimeout(300000, () => r.destroy(new Error('sd timeout')));
    r.write(data); r.end();
  });
}

// ── Pollinations image URL builder (updated portal — ?key=, not ?apikey=) ────
function buildImageUrl(prompt, key, env) {
  const host  = (env && env.POLLINATIONS_IMAGE_HOST)    || 'gen.pollinations.ai';
  const model = (env && env.POLLINATIONS_DEFAULT_MODEL)  || 'flux';
  const w     = (env && env.POLLINATIONS_DEFAULT_WIDTH)  || '1024';
  const h     = (env && env.POLLINATIONS_DEFAULT_HEIGHT) || '1024';
  const seed  = Math.floor(Math.random() * 1e7);
  let url = 'https://' + host + '/image/' + encodeURIComponent(prompt) +
            '?width=' + w + '&height=' + h + '&seed=' + seed + '&model=' + encodeURIComponent(model);
  if (key) url += '&key=' + encodeURIComponent(key);
  return url;
}
function styleFor(name)   { return IMG_STYLE[name] || IMG_STYLE.unity; }
function selfieSubject(n) { return SELFIE_SUBJECT[BASE_FORM[n] || n] || SELFIE_SUBJECT.unity; }
function resolvePersona(name) {
  const n = String(name || '').toLowerCase();
  if (ALIASES[n]) return ALIASES[n];
  return PERSONAS[n] ? n : null;
}
function personaList() {
  return Object.keys(PERSONAS).map((id) => ({
    id: id, label: PERSONAS[id].label, color: PERSONAS[id].color, tag: PERSONAS[id].tag,
  }));
}

// ── http helpers ────────────────────────────────────────────────────────────
function readBody(req) {
  return new Promise((resolve) => {
    let d = '';
    req.on('data', (c) => { d += c; if (d.length > 12e6) req.destroy(); });   // 12 MB: room for annotated screenshots (base64 PNG)
    req.on('end', () => { try { resolve(d ? JSON.parse(d) : {}); } catch (e) { resolve({}); } });
    req.on('error', () => resolve({}));
  });
}
function sendJson(res, code, obj) {
  const s = JSON.stringify(obj);
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Content-Length': Buffer.byteLength(s) });
  res.end(s);
}
function readJsonl(p) {
  if (!fs.existsSync(p)) return [];
  return fs.readFileSync(p, 'utf8').split(/\r?\n/).filter(Boolean)
    .map((l) => { try { return JSON.parse(l); } catch (e) { return null; } })
    .filter(Boolean);
}
function appendJsonl(p, obj) { fs.appendFileSync(p, JSON.stringify(obj) + '\n'); }
function maxId(rows) { return rows.reduce((m, r) => Math.max(m, r.id || 0), 0); }

// ── server ──────────────────────────────────────────────────────────────────
const server = http.createServer(async (req, res) => {
  try {
    lastBeat = Date.now();   // any request from the window counts as a heartbeat
    const qIdx = req.url.indexOf('?');
    const pathname = qIdx === -1 ? req.url : req.url.slice(0, qIdx);
    const query = {};
    if (qIdx !== -1) {
      for (const pair of req.url.slice(qIdx + 1).split('&')) {
        const kv = pair.split('=');
        try { query[decodeURIComponent(kv[0] || '')] = decodeURIComponent(kv[1] || ''); } catch (e) { /* bad escape */ }
      }
    }
    // Host check on everything (DNS-rebinding guard); POSTs need same-origin AND (the token OR a browser Origin).
    // The Origin header is set by the browser and cannot be forged by another site, so a page THIS server served
    // (the studio window, the overlay) is trusted by its Origin alone -- a tab opened before a restart keeps working
    // (owner, 2026-10-13, three times: "send failed: forbidden: missing or wrong studio token"). A request with no
    // Origin (a local helper script) still needs the token.
    if (!localHostOk(req)) return sendJson(res, 403, { error: 'bad host' });
    if (req.method !== 'GET' && (!originOk(req) || !(tokenOk(req, query) || req.headers.origin))) {
      return sendJson(res, 403, { error: 'forbidden: missing or wrong studio token' });
    }

    if (req.method === 'GET' && pathname === '/') {
      if (!fs.existsSync(HTML_PATH)) { res.writeHead(500); return res.end('persona-studio.html missing'); }
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      const page = fs.readFileSync(HTML_PATH, 'utf8')
        .replace('</head>', '<script>window.STUDIO_TOKEN=' + JSON.stringify(TOKEN) + ';</script></head>');
      return res.end(page);
    }

    // The OBS stream overlay (full 1920x1080 canvas, transparent).
    if (req.method === 'GET' && pathname === '/overlay') {
      if (!fs.existsSync(OVERLAY_PATH)) { res.writeHead(500); return res.end('stream-overlay.html missing'); }
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
      return res.end(fs.readFileSync(OVERLAY_PATH));
    }

    // Stream chat: Twitch viewers and Unity's lines ONLY. The owner's own studio-window messages
    // and Unity's replies to them never reach the stream (owner: "nothing personal of ours").
    if (req.method === 'GET' && pathname === '/api/token') {
      // the token is new on every start; a page opened before a restart holds the old one and every send fails
      // (owner, 2026-10-13: "send failed: forbidden: missing or wrong studio token"). Same-origin GET only
      // (the Host check above); the page refetches it on a 403 and retries once.
      return sendJson(res, 200, { token: TOKEN });
    }
    if (req.method === 'GET' && pathname === '/api/chat') {
      const since = parseInt(query.since, 10) || 0;
      const inbox = readJsonl(INBOX_PATH);
      const secrets = secretWords();
      const secretLower = new Set(secrets.map((w) => w.toLowerCase()));
      const twitch = new Map();
      for (const m of inbox) {
        const t = /^\[twitch\]\s*([^:]{1,40}):\s*([\s\S]*)$/.exec(String(m.text || ''));
        // The owner's own Twitch lines are private orders, not public chat: dropped here (with Unity's
        // replies to them, below) so the handle never reaches the overlay or any public reader.
        if (t && secretLower.has(t[1].trim().toLowerCase())) continue;
        if (t) twitch.set(m.id, { who: t[1].trim(), text: t[2].trim(), ts: m.ts });
      }
      const rows = [];
      for (const [id, v] of twitch) rows.push({ key: 'v' + id, ts: v.ts, who: scrub(v.who, secrets), text: scrub(v.text, secrets), unity: false });
      for (const r of readJsonl(OUTBOX_PATH)) {
        if (r.replyTo != null && !twitch.has(r.replyTo)) continue;
        rows.push({ key: 'u' + r.id, ts: r.ts, who: 'Unity', text: scrub(r.text, secrets), unity: true,
                    narration: r.replyTo == null });
      }
      rows.sort((a, b) => a.ts - b.ts);
      return sendJson(res, 200, { rows: rows.filter((r) => r.ts > since).slice(-60) });
    }

    // Script log: re-sanitised here too -- only file basenames and rimworld/<command> survive.
    if (req.method === 'GET' && pathname === '/api/log') {
      const since = parseInt(query.since, 10) || 0;
      const SAFE = /^(?:[A-Za-z0-9_-]{1,40}\.(?:py|cjs|ps1|sh)|rimworld\/[a-z_]{2,48})$/;
      const rows = readJsonl(STREAM_LOG).filter((r) => (r.id || 0) > since).slice(-40)
        .map((r) => ({ id: r.id, ts: r.ts, items: (r.items || []).filter((i) => SAFE.test(String(i))) }))
        .filter((r) => r.items.length);
      return sendJson(res, 200, { rows: rows });
    }

    if (req.method === 'GET' && pathname === '/api/personas') {
      return sendJson(res, 200, {
        active: activePersona, activeMeta: PERSONAS[activePersona],
        keyConfigured: hasKey(readEnv()), personas: personaList(),
      });
    }

    if (req.method === 'GET' && pathname.startsWith('/img/')) {
      const f = path.join(IMG_DIR, path.basename(pathname));
      if (!fs.existsSync(f)) { res.writeHead(404); return res.end(); }
      res.writeHead(200, { 'Content-Type': f.endsWith('.wav') ? 'audio/wav' : 'image/png', 'Cache-Control': 'no-store' });
      return fs.createReadStream(f).pipe(res);
    }

    if (req.method === 'GET' && pathname === '/api/cam') {
      return sendJson(res, 200, camState);
    }

    if (req.method === 'GET' && pathname === '/api/voice') {
      return sendJson(res, 200, voiceState);
    }

    if (req.method === 'GET' && pathname === '/api/feed') {
      windowSeen = true;   // the window's recurring poll — watchdog now armed
      const since = parseInt(query.since, 10) || 0;
      return sendJson(res, 200, {
        active: activePersona, activeMeta: PERSONAS[activePersona],
        latest: seq, images: feed.filter((i) => i.id > since),
      });
    }

    // Studio chat — replies Unity wrote to the outbox via /studio-pump.
    if (req.method === 'GET' && pathname === '/api/replies') {
      const since = parseInt(query.since, 10) || 0;
      const all = readJsonl(OUTBOX_PATH);
      return sendJson(res, 200, { latest: maxId(all), replies: all.filter((r) => (r.id || 0) > since) });
    }

    if (req.method === 'POST') {
      const body = await readBody(req);

      if (pathname === '/api/setkey') {
        const key = String(body.key || '').trim();
        if (!key) return sendJson(res, 400, { error: 'empty key' });
        writeKey(key);
        return sendJson(res, 200, { ok: true, keyConfigured: true });
      }

      if (pathname === '/api/persona') {
        const p = resolvePersona(body.persona);
        if (!p) return sendJson(res, 400, { error: 'unknown persona: ' + body.persona });
        activePersona = p;
        return sendJson(res, 200, { ok: true, active: p, meta: PERSONAS[p] });
      }

      if (pathname === '/api/clear') {
        feed.length = 0;
        try { fs.writeFileSync(INBOX_PATH, ''); fs.writeFileSync(OUTBOX_PATH, ''); } catch (e) { /* fine */ }
        return sendJson(res, 200, { ok: true });
      }

      // Studio chat — user message in. Unity answers it from Claude Code via the
      // /studio-pump skill; this only drops the message into the inbox file.
      if (pathname === '/api/say') {
        const text = String(body.text || '').trim();
        if (!text) return sendJson(res, 400, { error: 'empty message' });
        const persona = resolvePersona(body.persona) || activePersona;
        activePersona = persona;
        const id = maxId(readJsonl(INBOX_PATH)) + 1;
        appendJsonl(INBOX_PATH, { id: id, ts: Date.now(), persona: persona, text: text });
        return sendJson(res, 200, { ok: true, id: id });
      }

      // Unity pushes a generated image here.
      if (pathname === '/api/show') {
        const env = readEnv();
        const key = (env.POLLINATIONS_API_KEY || '').trim();
        const local = localImages(env);
        if (!local && !key) return sendJson(res, 400, { error: 'no-key' });
        const persona = resolvePersona(body.persona) || activePersona;
        activePersona = persona;
        let prompt = String(body.prompt || '').trim();
        // `selfie:true` is a no-prompt FALLBACK, not an override — an explicit
        // prompt always wins. Earlier builds replaced the caller's prompt with
        // the canned per-manifestation selfie subject whenever the flag was set,
        // which silently dropped detailed prompts on the floor. If the caller
        // wants the canned subject they pass `selfie:true` alone; if they want
        // their own subject they pass `prompt` (with or without the flag).
        if (body.selfie && !prompt) prompt = selfieSubject(persona);
        if (!prompt) return sendJson(res, 400, { error: 'empty prompt' });
        const full = prompt + ', ' + styleFor(persona);
        let url;
        if (local) {
          let png;
          try { png = await renderLocal(full, env); }
          catch (e) { return sendJson(res, 502, { error: 'local image server: ' + e.message + ' (start sd_server.py)' }); }
          fs.mkdirSync(IMG_DIR, { recursive: true });
          const name = 'img-' + Date.now() + '.png';
          fs.writeFileSync(path.join(IMG_DIR, name), png);
          url = '/img/' + name;
        } else {
          url = buildImageUrl(full, key, env);
        }
        const item = {
          id: ++seq,
          url: url,
          prompt: prompt,
          caption: String(body.caption || '').trim() || prompt,
          persona: persona,
          label: PERSONAS[persona].label,
          color: PERSONAS[persona].color,
          ts: Date.now(),
        };
        feed.push(item);
        while (feed.length > 200) feed.shift();
        return sendJson(res, 200, { ok: true, id: item.id, url: item.url });
      }

      // Webcam panel: Unity's face on stream, re-rendered when something happens in game.
      if (pathname === '/api/cam') {
        const env = readEnv();
        let png;
        if (body.png) {
          // A ready image (annotated game screenshot from unity-snap.py), base64 PNG.
          png = Buffer.from(String(body.png).replace(/^data:image\/png;base64,/, ''), 'base64');
        } else {
          const prompt = String(body.prompt || '').trim();
          if (!prompt) return sendJson(res, 400, { error: 'empty prompt' });
          const faceUrl = body.face ? ((env && env.STUDIO_FACE_URL) || 'http://127.0.0.1:7862') : null;
          try { png = await renderLocal(prompt, env, faceUrl, String(body.caption || ''), String(body.scene || '').slice(0, 120)); }
          catch (e) { return sendJson(res, 502, { error: 'local image server: ' + e.message }); }
        }
        fs.mkdirSync(IMG_DIR, { recursive: true });
        const name = 'cam-' + Date.now() + '.png';
        fs.writeFileSync(path.join(IMG_DIR, name), png);
        camState = { url: '/img/' + name, caption: String(body.caption || '').trim(), ts: Date.now() };
        try { fs.writeFileSync(CAM_STATE, JSON.stringify(camState)); } catch (e) { /* best effort */ }
        return sendJson(res, 200, { ok: true, url: camState.url });
      }

      if (pathname === '/api/voice') {
        const wav = Buffer.from(String(body.wav || ''), 'base64');
        if (!wav.length) return sendJson(res, 400, { error: 'empty wav' });
        fs.mkdirSync(IMG_DIR, { recursive: true });
        const name = 'voice-' + Date.now() + '.wav';
        fs.writeFileSync(path.join(IMG_DIR, name), wav);
        voiceState = { url: '/img/' + name, ts: Date.now() };
        return sendJson(res, 200, { ok: true, url: voiceState.url });
      }

      if (pathname === '/api/shutdown') {
        sendJson(res, 200, { ok: true, persist: !!process.env.STUDIO_PERSIST });
        // Persistent mode: a closing/reloading overlay window sends this beacon on pagehide,
        // which must not take the stream's chat server down with it.
        if (process.env.STUDIO_PERSIST) return;
        return setTimeout(() => process.exit(0), 120);
      }
    }

    sendJson(res, 404, { error: 'not found' });
  } catch (e) {
    try { sendJson(res, 500, { error: String((e && e.message) || e) }); } catch (e2) { /* socket gone */ }
  }
});

// ── listen + open browser ───────────────────────────────────────────────────
function openBrowser(url) {
  const p = process.platform;
  const cmd = p === 'win32' ? 'start "" "' + url + '"'
            : p === 'darwin' ? 'open "' + url + '"'
            : 'xdg-open "' + url + '"';
  exec(cmd, () => { /* best-effort */ });
}
function listen(port, attempt) {
  // Clear BOTH 'error' and 'listening' listeners before each (re)try. A failed
  // server.listen() leaves its one-time 'listening' callback pending on the
  // server object — if only 'error' were cleared, every attempted port would
  // accumulate a callback and they would ALL fire on the eventual success,
  // printing one banner per attempted port (including dead ones).
  server.removeAllListeners('error');
  server.removeAllListeners('listening');
  server.once('error', (err) => {
    if (err.code === 'EADDRINUSE' && attempt < 12) { listen(port + 1, attempt + 1); }
    else { console.error('persona-studio: could not bind a port — ' + err.message); process.exit(1); }
  });
  server.once('listening', () => {
    const url = 'http://127.0.0.1:' + port + '/';
    console.log('');
    console.log('  █ UNITY PLAYS RIMWORLD — live  →  ' + url);
    console.log('  Unity pushes images via:  POST ' + url + 'api/show  {prompt, persona}');
    console.log('  Ctrl+C to stop.');
    console.log('');
    if (!process.env.STUDIO_PERSIST) openBrowser(url);
  });
  server.listen(port, '127.0.0.1');
}
listen(BASE_PORT, 0);

// ── window-presence watchdog tick ───────────────────────────────────────────
// Once a window has polled at least once, a stale heartbeat means it closed —
// exit. Before any window connects, the startup grace retires an orphan server
// whose window never opened. .unref() so the timer never holds the process up.
setInterval(() => {
  const idle = Date.now() - lastBeat;
  if (process.env.STUDIO_PERSIST) return;   // the overlay owns the window; stay up
  if (windowSeen && idle > WINDOW_TIMEOUT_MS) {
    console.log('persona-studio: window closed — shutting down.');
    process.exit(0);
  }
  if (!windowSeen && idle > STARTUP_GRACE_MS) {
    console.log('persona-studio: no window ever connected — shutting down.');
    process.exit(0);
  }
}, 3000).unref();
