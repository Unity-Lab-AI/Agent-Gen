#!/usr/bin/env node
// Agent Gen hub, M2 scope: serves the face UI, holds one WebSocket session per tab, and runs the voice loop
// (hear -> think -> speak with timing). Tool registry, MCP and the HTTP gateway arrive in M5/M6 on top of this.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { WebSocketServer } from 'ws';
import { cfg, REPO } from './config.mjs';
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

const BECOME = /\b(you are now|you're now|youre now|become|turn into|turn yourself|transform into|change (yourself|your (image|look|self))|remake your|your (image|look) (of|as)|yourself as|be an? )/i;

// "that's you now" after a picture: the picture she just made IS her new look. Her brain re-described her default
// goth self instead (the persona pulls her home), so the hub adopts the picture itself.
const THAT_YOU = /\b(that'?s|that is|thats|this is|this'?s|thiss) (you|your)\b|\b(become|be) (that|this|them|him|her|it)\b|\bmake (that|this|it) (you|your)/i;

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
    this.jobs = 0;                 // looks, pictures and clips in flight (a look's job lasts as long as its reel)
    this.lastActive = Date.now();
    // she lives on her own: with nothing to do for a while (fresh start, after a reset, a reel that ended), she
    // starts her idle routine from her current look instead of sitting there blinking
    this.idleTimer = setInterval(() => this.idleCheck(), 5000);
  }
  queueJob(job) {
    this.jobs++;
    job.finally(() => { this.jobs--; this.lastActive = Date.now(); });
    this.looks = (this.looks || Promise.resolve()).then(() => job);
  }
  idleCheck() {
    if (this.closed) return clearInterval(this.idleTimer);
    if (this.busy || this.jobs > 0 || Date.now() - this.lastActive < cfg.idleStartMs) return;
    this.lastActive = Date.now();
    this.queueJob(this.startIdle());
  }
  /** Her idle routine from the look she has (her default full-body look on a fresh start): a first clip of
   *  something she decides to do, then the open-ended reel. Any message, look or reset preempts it. */
  async startIdle() {
    const lookId = ++this.lookSeq;
    const look = this.currentLook || cfg.lookBase;
    const lookPrompt = this.currentLookPrompt || cfg.idleLookPrompt;
    if (!this.currentLook) { this.currentLook = look; this.currentLookPrompt = lookPrompt; }
    this.log('idle: she starts doing her own thing');
    try {
      const vh = await video.health();
      if (!vh.ok || !vh.model_present) return;
      const motion = await this.nextIdleAction(lookPrompt, lookId);
      if (this.closed || this.busy || this.lookSeq !== lookId) return;
      this.reelBusy = true;
      await face.pause();
      await video.makeRoom();
      const c = await video.clip(look, `${lookPrompt}, ${motion}, her face stays visible to the camera`, { engine: cfg.reelEngine });
      this.reelBusy = false;
      if (this.closed || this.lookSeq !== lookId) return;
      this.currentClip = c.path;
      const f = await face.appearance(c.path);
      this.send({ type: 'look', stage: f?.ok ? 'reel' : 'clip-only', prompt: lookPrompt, motion, clip: { seconds: c.seconds, frames: c.frames }, epoch: this.epoch });
      if (f?.ok) await this.extendReel(c.path, lookPrompt, lookId);
    } catch (e) {
      if (!/cancelled/.test(e.message)) this.log('idle failed', e.message);
    } finally {
      this.reelBusy = false;
      await face.resume();
    }
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
    this.lastActive = Date.now();
    this.history.push({ role: 'user', content: userText });
    this.lastUserText = userText;
    if (this.lastPic && THAT_YOU.test(userText)) {
      // the last picture becomes her look as it is; image lines she writes this turn are ignored so she cannot
      // redraw herself back to her default
      this.adoptEpoch = epoch;
      const job = this.adopt(this.lastPic, this.lastPicPrompt, userText, epoch);
      this.queueJob(job);
    }
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
    if (this.adoptEpoch === epoch && ['img', 'image', 'selfie', 'look', 'pic', 'picture', 'photo', 'draw', 'do', 'action'].includes(tag.kind)) {
      this.log(`tag ${tag.kind} ignored: this turn adopts the last picture as her look`);
      return;
    }
    this.log(`tag ${tag.kind}: ${prompt.slice(0, 120)}`);
    const lookId = ++this.lookSeq;                 // a newer look stops the older one's reel from growing
    this.idleActions = [];                         // and what she had planned to do in the old look
    // told to BE the thing ("you are now a real life lion, remake your image of yourself"): whatever line she wrote,
    // it is her new look, so it goes to her face and the next [[do]] animates it, not the old her
    if (['pic', 'picture', 'photo', 'draw'].includes(tag.kind) && BECOME.test(this.lastUserText || '')) {
      this.log(`pic is her new look (told to become it)`);
      tag = { ...tag, kind: 'img', restyle: true };
    }
    if (['pic', 'picture', 'photo', 'draw'].includes(tag.kind)) {
      // a picture of anything (two gorillas, a dinosaur, a professor): exactly as written, in the chat, never her face
      const job = (async () => {
        this.send({ type: 'look', stage: 'rendering', kind: tag.kind, prompt, epoch });
        try {
          await face.pause();
          const res = await image.render(prompt, { plain: true, width: cfg.picWidth, height: cfg.picHeight });
          if (this.closed) return;
          this.send({ type: 'image', url: res.url, prompt, seed: res.seed, seconds: res.seconds, kind: tag.kind, epoch });
          this.send({ type: 'look', stage: 'image-only', kind: tag.kind, prompt, epoch });
          this.lastPic = res.file; this.lastPicPrompt = prompt;   // "that's you now" can adopt it
        } catch (e) {
          this.log('picture failed', e.message);
          this.send({ type: 'look', stage: 'failed', kind: tag.kind, prompt, error: String(e.message || e), epoch });
        } finally { await face.resume(); }
      })();
      this.queueJob(job);
      return;
    }
    if (tag.kind === 'do' || tag.kind === 'action') {
      const job = this.motion(prompt, lookId, epoch);
      this.queueJob(job);
      return;
    }
    this.send({ type: 'look', stage: 'rendering', kind: tag.kind, prompt, epoch });
    const job = (async () => {
      try {
        // every look evolves from the current one (her likeness photo at first), so she stays herself
        // a look she was told to take is finished even if the conversation moves on; only a reset cancels.
        // The face holds its last frame while the image/video engines own the GPU (no 2 fps stutter).
        await face.pause();
        // told to look like someone else: render fresh, then that face is hers until the next restyle or a reset
        const restyle = tag.restyle || image.isRestyle(prompt);
        const res = await image.render(prompt, { sourceFile: this.currentLook, restyle, faceFile: this.lookFace });
        if (this.closed) return;
        if (restyle) this.lookFace = res.file;
        this.currentLook = res.file;
        this.currentLookPrompt = prompt;           // the idle reel keeps describing THIS look, not a later motion
        this.send({ type: 'image', url: res.url, prompt, seed: res.seed, seconds: res.seconds, kind: tag.kind, epoch });
        if (cfg.lookDrivesFace) {
          const f = await face.appearance(res.file);
          this.send({ type: 'look', stage: f?.ok ? 'live' : 'image-only', kind: tag.kind, prompt, face: f, epoch });
          if (f?.ok) await face.settle();          // the new look on screen before the video render holds the frame
        }
        // motion: when the video engine is up, every look also becomes a clip of her doing it
        const vh = await video.health();
        if (vh.ok && vh.model_present) {
          this.send({ type: 'look', stage: 'animating', kind: tag.kind, prompt, epoch });
          await face.pause();
          await video.makeRoom();
          const c = await video.clip(res.file, prompt, { engine: cfg.motionEngine });
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
    this.queueJob(job);
  }

  /** The picture she just made becomes her look as it is (no re-render), then a clip of it doing what was asked. */
  async adopt(file, picPrompt, userText, epoch) {
    const lookId = ++this.lookSeq;
    this.idleActions = [];
    this.log(`adopting the last picture as her look`);
    try {
      this.currentLook = file; this.currentLookPrompt = picPrompt; this.lookFace = file; this.currentClip = null;
      this.send({ type: 'look', stage: 'rendering', kind: 'img', prompt: picPrompt, epoch });
      if (cfg.lookDrivesFace) {
        const f = await face.appearance(file);
        this.send({ type: 'look', stage: f?.ok ? 'live' : 'image-only', kind: 'img', prompt: picPrompt, face: f, epoch });
        if (f?.ok) await face.settle();
      }
      const vh = await video.health();
      if (!vh.ok || !vh.model_present || this.lookSeq !== lookId) return;
      this.send({ type: 'look', stage: 'animating', kind: 'img', prompt: picPrompt, epoch });
      await face.pause();
      await video.makeRoom();
      const c = await video.clip(file, `${picPrompt}, ${userText}`, { engine: cfg.motionEngine });
      if (this.closed || this.lookSeq !== lookId) return;
      this.currentClip = c.path;
      const f2 = await face.appearance(c.path);
      this.send({ type: 'look', stage: f2?.ok ? 'moving' : 'clip-only', kind: 'img', prompt: picPrompt, clip: { seconds: c.seconds, frames: c.frames }, face: f2, epoch });
      if (f2?.ok) await this.extendReel(c.path, picPrompt, lookId);
    } catch (e) {
      if (!/cancelled/.test(e.message)) { this.log('adopt failed', e.message); this.send({ type: 'look', stage: 'failed', kind: 'img', prompt: picPrompt, error: String(e.message || e), epoch }); }
    } finally {
      await face.resume();
    }
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
      // LTX 2B is timid with bodies; a pushier description measured +40% motion. The big-motion engine is a model swap, not a prompt.
      const p = cfg.motionPush ? `${prompt}, ${cfg.motionPush}` : prompt;
      // always from her clean look image: chaining from a clip's last frame carried every smear and colour
      // blotch into the next clip, and they piled up until she melted
      const c = await video.clip(this.currentLook || cfg.lookBase, p, { engine: cfg.motionEngine });
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
        const c = this.currentLook
          ? await video.clip(this.currentLook, `${prompt}, ${motion}, her face stays visible to the camera`, { engine: cfg.reelEngine })
          : await video.clip(null, `${prompt}, ${motion}, her face stays visible to the camera`, { fromClip: chain[chain.length - 1], engine: cfg.reelEngine });
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
        const ask = `You are standing there in this look: "${prompt}". Nobody is talking to you. List ${cfg.reelBatch} big physical things you do next with your whole body (bounce, jump, dance, spin, stretch, pose, strut, play with your hair, whatever you feel like), never just standing or small movements, one per line, present tense, third person "she", staying in frame with your face toward the camera, no words spoken, no numbering, no commentary.`;
        const text = await chatOnce([{ role: 'system', content: readPersona() }, ...this.history, { role: 'user', content: ask }]);
        if (this.lookSeq !== lookId) return cfg.reelMotions[0];
        // one per line is what we asked for; an 8B model sometimes answers in a paragraph, so split on sentences too
        this.idleActions = text.replace(/\[\[.*?\]\]/g, '').split(/\n|(?<=[.!?])\s+(?=[A-Z])/).map(s => s.replace(/^[\s\-*\d.)]+/, '').replace(/<[^>]+>/g, '').trim()).filter(s => s.length > 8 && s.length < 200);
        this.log(`idle plan (${this.idleActions.length}): ${this.idleActions.slice(0, 3).join(' | ')}`);
      } catch (e) { this.log('idle plan failed', e.message); }
      if (!this.idleActions?.length) this.idleActions = [...cfg.reelMotions];
    }
    return this.idleActions.shift();
  }

  /** Forget the conversation and her current look, clip and restyled face (the files may be about to go). */
  reset() {
    this.interrupt('reset'); this.history = []; this.lookSeq++; this.idleActions = [];
    this.lookFace = null; this.currentLook = null; this.currentLookPrompt = null; this.currentClip = null;
    this.lastPic = null; this.lastPicPrompt = null; this.adoptEpoch = null;
  }

  async onMessage(raw) {
    let m;
    try { m = JSON.parse(raw); } catch { return; }
    switch (m.type) {
      case 'utterance': return this.onUtterance(m);
      case 'text': return this.onText(m);
      case 'interrupt': return this.interrupt(m.reason || 'barge-in');
      case 'reset': this.reset(); return this.send({ type: 'reset' });
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
  if (url.pathname === '/api/forget' && req.method === 'POST') {
    // Loopback only: the app's Storage panel clears her looks, clips or conversations. Every open window forgets
    // its conversation and look, a clip in flight is cancelled, and her face goes back to her own portrait so
    // nothing points at a deleted file.
    for (const s of sessions) { s.reset(); s.send({ type: 'reset' }); }
    await video.cancel();
    const f = await face.appearance(path.join(REPO, 'assets', 'portrait', 'unity-bust.jpg'));
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ ok: true, sessions: sessions.size, face: f?.ok ?? null }));
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
