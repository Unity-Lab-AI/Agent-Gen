#!/usr/bin/env node
// Agent Gen hub, M2 scope: serves the face UI, holds one WebSocket session per tab, and runs the voice loop
// (hear -> think -> speak with timing). Tool registry, MCP and the HTTP gateway arrive in M5/M6 on top of this.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { WebSocketServer } from 'ws';
import { cfg } from './config.mjs';
import { chatStream, chatOnce, health as brainHealth } from './providers/ollama.mjs';
import { SentenceSplitter } from './voice/sentences.mjs';
import { TagFilter, unstaged } from './voice/tags.mjs';
import { SpeechQueue } from './voice/pipeline.mjs';
import { EchoFilter } from './speech/echo-filter.mjs';
import * as face from './face/client.mjs';
import * as image from './image/client.mjs';
import * as video from './video/client.mjs';

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' };

function readPersona() {
  try { return fs.readFileSync(cfg.personaFile, 'utf8').trim(); } catch { return 'You are Unity. Speak briefly.'; }
}

async function probe(url, ms = 2500) {
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(ms) });
    const j = await r.json().catch(() => ({}));
    return { ok: r.ok && j.ok !== false, ...j };
  } catch (e) { return { ok: false, error: String(e.message || e) }; }
}

async function healthAll() {
  const [voice, speech, brain, faceH, img, vid] = await Promise.all([probe(`${cfg.voiceUrl}/health`), probe(`${cfg.speechUrl}/health`), brainHealth(), face.health(), image.health(), video.health()]);
  return { ok: true, hub: { port: cfg.port, persona: path.basename(cfg.personaFile), wakeWord: cfg.wakeWord }, voice, speech, brain, face: faceH, image: img, video: vid };
}

async function transcribe(pcm_b64, sampleRate) {
  const r = await fetch(`${cfg.speechUrl}/transcribe`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pcm_b64, sample_rate: sampleRate }), signal: AbortSignal.timeout(60000),
  });
  const j = await r.json().catch(() => ({ error: `speech ${r.status}` }));
  if (!r.ok) throw new Error(j.error || `speech ${r.status}`);
  return j;
}

async function wakeCheck(text) {
  if (!cfg.wakeWord.length) return { matched: true, remainder: text };
  const r = await fetch(`${cfg.speechUrl}/wake`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, phrases: cfg.wakeWord }) });
  return r.json();
}

class Session {
  constructor(ws, id) {
    this.ws = ws; this.id = id;
    this.history = [];
    this.epoch = 0;
    this.abort = null;
    this.echo = new EchoFilter();
    this.queue = new SpeechQueue(m => this.send(m));
    this.queue.onSpoken = t => this.echo.remember(t);
    this.busy = false;
    this.lookSeq = 0;
  }
  send(obj) { if (this.ws.readyState === 1) this.ws.send(JSON.stringify(obj)); }
  log(...a) { console.log(new Date().toISOString().slice(11, 19), `[${this.id}]`, ...a); }

  interrupt(reason = 'barge-in') {
    if (this.abort) { this.abort.abort(); this.abort = null; }
    this.queue.cancel();
    this.epoch++;
    this.busy = false;
    this.send({ type: 'interrupted', epoch: this.epoch, reason });
  }

  async onUtterance({ pcm_b64, sampleRate = 16000, durationMs }) {
    if (!pcm_b64) return;
    this.send({ type: 'status', stage: 'transcribing' });
    let heard;
    try { heard = await transcribe(pcm_b64, sampleRate); }
    catch (e) { return this.send({ type: 'error', where: 'speech', error: String(e.message || e) }); }
    const text = (heard.text || '').trim();
    if (!text) return this.send({ type: 'heard', text: '', dropped: 'empty', seconds: heard.seconds });
    const echo = this.echo.check(text);
    if (echo.echo) { this.log('echo dropped:', text, echo); return this.send({ type: 'heard', text, dropped: 'echo', echo }); }
    const wake = await wakeCheck(text);
    if (!wake.matched) return this.send({ type: 'heard', text, dropped: 'no-wake-word', wake });
    const utter = (wake.remainder || text).trim() || text;
    this.send({ type: 'heard', text: utter, seconds: heard.seconds, durationMs });
    await this.respond(utter);
  }

  async onText({ text }) {
    text = String(text || '').trim();
    if (!text) return;
    this.send({ type: 'heard', text, typed: true });
    await this.respond(text);
  }

  async respond(userText) {
    if (this.busy) this.interrupt('new-input');
    if (this.reelBusy) { video.cancel(); face.resume(); }   // her lips come first; the idle clip dies at its next step
    const epoch = ++this.epoch;
    this.queue.epoch = epoch;
    const ac = new AbortController();
    this.abort = ac;
    this.busy = true;
    this.history.push({ role: 'user', content: userText });
    while (this.history.length > cfg.historyTurns * 2) this.history.shift();
    const messages = [{ role: 'system', content: readPersona() }, ...this.history];
    const splitter = new SentenceSplitter();
    const tags = new TagFilter(tag => this.onTag(tag, epoch));
    let full = '';
    this.send({ type: 'status', stage: 'thinking', epoch });
    try {
      for await (const delta of chatStream(messages, { signal: ac.signal })) {
        if (epoch !== this.epoch) return;
        full += delta;
        this.send({ type: 'delta', epoch, text: delta });
        for (const s of splitter.push(tags.push(delta))) this.say(s, epoch);
      }
      for (const s of splitter.push(tags.flush())) this.say(s, epoch);
      for (const s of splitter.flush()) this.say(s, epoch);
      await this.queue.drain();               // looks and clips keep rendering in the background (onTag)
    } catch (e) {
      if (!ac.signal.aborted) { this.log('brain error', e.message); this.send({ type: 'error', where: 'brain', error: String(e.message || e), epoch }); }
    } finally {
      if (this.abort === ac) this.abort = null;
    }
    if (epoch === this.epoch) {
      if (full.trim()) this.history.push({ role: 'assistant', content: full.trim() });
      this.busy = false;
      this.send({ type: 'done', epoch, text: full.trim() });
    }
  }

  /** A sentence to her voice, minus any stage direction in it (those become looks, not words). */
  say(sentence, epoch) {
    const s = unstaged(sentence);
    if (s.replace(/<[^>]+>/g, '').trim()) this.queue.enqueue(s, epoch);
  }

  /** [[img: ...]] / [[look: ...]] from her stream: a new picture of her, then a clip, then her live face.
   *  [[do: ...]] / [[action: ...]] (and a stage direction with no line): a clip of her CURRENT look doing it; no
   *  new picture. Operator: "she should only change or take off outfits when told to, just telling her to
   *  bounce or jiggle or dance should not instanty generate a new self image unless told that". */
  onTag(tag, epoch) {
    const prompt = tag.text;
    if (!prompt) return;
    this.log(`tag ${tag.kind}: ${prompt.slice(0, 120)}`);
    const lookId = ++this.lookSeq;                 // a newer look stops the older one's reel from growing
    this.idleActions = [];                         // and what she had planned to do in the old look
    if (tag.kind === 'do' || tag.kind === 'action') {
      const job = this.motion(prompt, lookId, epoch);
      this.looks = (this.looks || Promise.resolve()).then(() => job);
      return;
    }
    this.send({ type: 'look', stage: 'rendering', kind: tag.kind, prompt, epoch });
    const job = (async () => {
      try {
        // every look evolves from the current one (her likeness photo at first), so she stays herself
        // a look she was told to take is finished even if the conversation moves on; only a reset cancels.
        // The face holds its last frame while the image/video engines own the GPU (no 2 fps stutter).
        await face.pause();
        const res = await image.render(prompt, { sourceFile: this.currentLook });
        if (this.closed) return;
        this.currentLook = res.file;
        this.currentLookPrompt = prompt;           // the idle reel keeps describing THIS look, not a later motion
        this.send({ type: 'image', url: res.url, prompt, seed: res.seed, seconds: res.seconds, kind: tag.kind, epoch });
        if (cfg.lookDrivesFace) {
          const f = await face.appearance(res.file);
          this.send({ type: 'look', stage: f?.ok ? 'live' : 'image-only', kind: tag.kind, prompt, face: f, epoch });
        }
        // motion: when the video engine is up, every look also becomes a clip of her doing it
        const vh = await video.health();
        if (vh.ok && vh.model_present) {
          this.send({ type: 'look', stage: 'animating', kind: tag.kind, prompt, epoch });
          await face.pause();
          await video.makeRoom();
          const c = await video.clip(res.file, prompt);
          if (this.closed) return;
          this.currentClip = c.path;
          const f2 = await face.appearance(c.path);
          this.send({ type: 'look', stage: f2?.ok ? 'moving' : 'clip-only', kind: tag.kind, prompt, clip: { seconds: c.seconds, frames: c.frames }, face: f2, epoch });
          if (f2?.ok) await this.extendReel(c.path, prompt, lookId);
        }
      } catch (e) {
        this.log('look failed', e.message);
        this.send({ type: 'look', stage: 'failed', kind: tag.kind, prompt, error: String(e.message || e), epoch });
      } finally {
        await face.resume();
      }
    })();
    this.looks = (this.looks || Promise.resolve()).then(() => job);
  }

  /** A movement in the look she already has: clip from where she is now (the current clip's last frame, else
   *  her current look image, else her base portrait), swapped onto her face, then the reel continues from it. */
  async motion(prompt, lookId, epoch) {
    this.send({ type: 'look', stage: 'animating', kind: 'do', prompt, epoch });
    try {
      const vh = await video.health();
      if (!vh.ok || !vh.model_present) { this.send({ type: 'look', stage: 'failed', kind: 'do', prompt, error: 'video engine down', epoch }); return; }
      await face.pause();
      await video.makeRoom();
      const c = this.currentClip
        ? await video.clip(null, prompt, { fromClip: this.currentClip })
        : await video.clip(this.currentLook || cfg.lookBase, prompt);
      if (this.closed || this.lookSeq !== lookId) return;
      this.currentClip = c.path;
      const f = await face.appearance(c.path);
      this.send({ type: 'look', stage: f?.ok ? 'moving' : 'clip-only', kind: 'do', prompt, clip: { seconds: c.seconds, frames: c.frames }, face: f, epoch });
      if (f?.ok) await this.extendReel(c.path, this.currentLookPrompt || prompt, lookId);
    } catch (e) {
      if (!/cancelled/.test(e.message)) { this.log('motion failed', e.message); this.send({ type: 'look', stage: 'failed', kind: 'do', prompt, error: String(e.message || e), epoch }); }
    } finally {
      await face.resume();
    }
  }

  /** Whenever she is idle, grow the current look's reel: clips chained from the last frame, each a thing she
   *  decided to do, appended to her live face. Open-ended (reelClips 0) or capped. Stays in the GPU chain, so a
   *  newer look preempts it after at most one clip; waits while she is thinking or speaking, and a new message
   *  cancels the clip in flight (see respond) so her lips never wait on it. */
  async extendReel(clipPath, prompt, lookId) {
    const chain = [clipPath];                      // clips she can continue from; a clip that ends faceless is popped
    let misses = 0;
    for (let i = 0; cfg.reelClips === 0 || i < cfg.reelClips; i++) {
      while (this.busy && !this.closed && this.lookSeq === lookId) await new Promise(r => setTimeout(r, 1000));
      if (this.closed || this.lookSeq !== lookId) return;
      const motion = await this.nextIdleAction(prompt, lookId);
      if (this.closed || this.lookSeq !== lookId || this.busy) { i--; continue; }
      this.reelBusy = true;
      try {
        await face.pause();
        await video.makeRoom();
        const c = await video.clip(null, `${prompt}, ${motion}, her face stays visible to the camera`, { fromClip: chain[chain.length - 1] });
        if (this.closed || this.lookSeq !== lookId) return;
        const f = await face.appearance(c.path, { extend: true });
        if (!f?.ok) {
          // the chain point lost her face (turned away, walked out of frame): step back to the previous good clip
          this.log('reel append failed', f?.error);
          if (!/no face/i.test(f?.error || '') || ++misses > 4 || chain.length === 0) return;
          if (chain.length > 1) chain.pop();
          continue;
        }
        chain.push(c.path);
        this.log(`reel +${c.frames} (${f.reel_frames} frames): ${motion}`);
        this.send({ type: 'look', stage: 'reel', prompt, motion, clip: { seconds: c.seconds, frames: c.frames }, reel: f.reel_frames, epoch: this.epoch });
      } catch (e) {
        if (!/cancelled/.test(e.message)) { this.log('reel failed', e.message); return; }
      } finally {
        this.reelBusy = false;
        await face.resume();
      }
    }
  }

  /** What she does next while nobody is talking to her: her own brain decides, a batch at a time (one brain
   *  load per batch, since the brain is unloaded for every clip). Falls back to the config motions. */
  async nextIdleAction(prompt, lookId) {
    if (!this.idleActions?.length) {
      try {
        const ask = `You are standing there in this look: "${prompt}". Nobody is talking to you. List ${cfg.reelBatch} short physical things you do next, whatever you feel like, one per line, present tense, third person "she", staying in frame with your face toward the camera, no words spoken, no numbering, no commentary.`;
        const text = await chatOnce([{ role: 'system', content: readPersona() }, ...this.history, { role: 'user', content: ask }]);
        if (this.lookSeq !== lookId) return cfg.reelMotions[0];
        this.idleActions = text.split('\n').map(s => s.replace(/^[\s\-*\d.)]+/, '').replace(/\[\[.*?\]\]/g, '').trim()).filter(s => s.length > 8 && s.length < 200);
        this.log(`idle plan (${this.idleActions.length}): ${this.idleActions.slice(0, 3).join(' | ')}`);
      } catch (e) { this.log('idle plan failed', e.message); }
      if (!this.idleActions?.length) this.idleActions = [...cfg.reelMotions];
    }
    return this.idleActions.shift();
  }

  async onMessage(raw) {
    let m;
    try { m = JSON.parse(raw); } catch { return; }
    switch (m.type) {
      case 'utterance': return this.onUtterance(m);
      case 'text': return this.onText(m);
      case 'interrupt': return this.interrupt(m.reason || 'barge-in');
      case 'reset': this.interrupt('reset'); this.history = []; this.lookSeq++; this.idleActions = []; return this.send({ type: 'reset' });
      case 'ping': return this.send({ type: 'pong', t: m.t });
      default: return this.send({ type: 'error', error: `unknown message type ${m.type}` });
    }
  }
}

// ---- http ------------------------------------------------------------------------------------------------
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (url.pathname === '/api/health') {
    const h = await healthAll();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify(h));
  }
  if (url.pathname === '/api/text' && req.method === 'POST') {
    // Loopback only: say something to her as if typed in the newest open window (used by tests and tools).
    let body = '';
    req.on('data', d => { body += d; if (body.length > 65536) req.destroy(); });
    req.on('end', () => {
      let text = '';
      try { text = String(JSON.parse(body || '{}').text || ''); } catch {}
      const s = [...sessions].pop();
      res.writeHead(s && text ? 200 : 409, { 'Content-Type': 'application/json' });
      if (s && text) { s.onText({ text }); return res.end(JSON.stringify({ ok: true, session: s.id })); }
      res.end(JSON.stringify({ ok: false, error: s ? 'empty text' : 'no open window' }));
    });
    return;
  }
  let p = decodeURIComponent(url.pathname);
  if (p === '/') p = '/index.html';
  let base = cfg.uiDir;
  if (p.startsWith('/looks/')) { base = image.looksDir; p = p.slice('/looks'.length); }   // her rendered looks
  const file = path.normalize(path.join(base, p));
  if (!file.startsWith(path.normalize(base))) { res.writeHead(403); return res.end(); }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); return res.end('not found'); }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
    res.end(data);
  });
});

const wss = new WebSocketServer({ server, path: '/ws', maxPayload: 32 * 1024 * 1024 });
const sessions = new Set();
let nextId = 1;
wss.on('connection', ws => {
  const s = new Session(ws, nextId++);
  sessions.add(s);
  s.log('connected');
  s.send({ type: 'hello', session: s.id, wakeWord: cfg.wakeWord });
  ws.on('message', raw => s.onMessage(raw.toString()));
  ws.on('close', () => { s.closed = true; s.interrupt('closed'); sessions.delete(s); s.log('closed'); });
});

setInterval(() => face.health(), 5000);   // keeps face.isLive() current so sentences get mirrored when she is up
face.health();

server.listen(cfg.port, cfg.host, () => {
  console.log(`agent-gen hub on http://${cfg.host}:${cfg.port}  ui=${cfg.uiDir}`);
  console.log(`voice=${cfg.voiceUrl} speech=${cfg.speechUrl} ollama=${cfg.ollamaUrl} models=${cfg.brainModels.join(',')}`);
});
