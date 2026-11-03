#!/usr/bin/env node
// Agent Gen hub, M2 scope: serves the face UI, holds one WebSocket session per tab, and runs the voice loop
// (hear -> think -> speak with timing). Tool registry, MCP and the HTTP gateway arrive in M5/M6 on top of this.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { WebSocketServer } from 'ws';
import { cfg, REPO, estTokens } from './config.mjs';
import { chatStream, chatOnce, health as brainHealth, gpu } from './providers/ollama.mjs';
import { SentenceSplitter } from './voice/sentences.mjs';
import { TagFilter, unstaged, WEB_KINDS } from './voice/tags.mjs';
import * as web from './tools/web.mjs';
import { SpeechQueue } from './voice/pipeline.mjs';
import { EchoFilter } from './speech/echo-filter.mjs';
import * as face from './face/client.mjs';
import * as image from './image/client.mjs';
import * as video from './video/client.mjs';
import { parseMarks } from './image/marks.mjs';
import * as vision from './vision/client.mjs';

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' };

const LOOK_STATE = path.join(image.looksDir, 'current.json');   // her look across restarts
const CLOTHES = /\b(top|tops|shirt|t-shirt|tee|blouse|bra|dress|gown|skirt|pants|jeans|shorts|bikini|swimsuit|lingerie|panties|underwear|undies|thong|stockings|fishnets|corset|jacket|hoodie|sweater|coat|outfit|clothes|clothing|wearing|wears|dressed|undressed|naked|nude|topless|bottomless|bare|strip|stripped|costume|uniform|robe|towel|boots|heels)\b/i;
const ADDS = /\b(add|put on|wear|give (yourself|you)|draw|write|paint|lipstick|necklace|collar|choker|earrings?|glasses|sunglasses|hat|bow|ribbon|tattoo|piercing|bracelet|gloves|mask|makeup)\b/i;
const UNDRESS = /\b(take off|take of|remove|strip|undress|naked|nude|topless|bottomless|change (into|your)|swap|instead of)\b/i;
// told to put clothes on ("might want to put on a hoodie", "*hands Unity a hoodie* cover yourself with that"): her
// brain writes emotion cues and nothing else, so she said "now I'm all warm and cozy" and stayed topless. The
// operator's words dress her.
const WEAR = /\b(put (on|it on)|puts on|wear|try on|change into|cover (your ?self|yourself|up)|throw on|slip (on|into)|get dressed|dress (in|up)|hands? (you|unity|her)|gives? (you|unity|her)|here'?s (a|an|your|some))\b/i;
const GARMENT = /\b((?:[a-z]+[- ]){0,2}?(?:hoodie|sweatshirt|sweater|jumper|t-shirt|tee|shirt|blouse|tank top|crop top|top|jacket|coat|robe|dress|gown|skirt|jeans|pants|trousers|shorts|leggings|bikini|swimsuit|lingerie|bra|panties|underwear|thong|stockings|fishnets|corset|towel|uniform|costume|pajamas|onesie|scarf|beanie|hat|cap|gloves|boots|heels|socks)(?:[- ](?:hoodie|sweatshirt|dress|top|jacket|shirt))?)\b/i;
const NOT_WEAR = /\b(take (it |that |them )?off|take of|remove|strip|undress|without)\b/i;
/** "a Hoodie Sweatshirt" -> "hoodie sweatshirt"; null when the words do not put a garment on her. */
export function wearAsk(text) {
  const t = String(text || '');
  if (!WEAR.test(t) || NOT_WEAR.test(t)) return null;
  const g = GARMENT.exec(t);
  return g ? g[1].toLowerCase().replace(/^((unity|her|you|a|an|the|this|that|my|your|some|on|with)\s+)+/, '').trim() : null;
}

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
  const [voice, speech, brain, faceH, img, vid, eyes] = await Promise.all([probe(`${cfg.voiceUrl}/health`), probe(`${cfg.speechUrl}/health`), brainHealth(), face.health(), image.health(), video.health(), vision.health()]);
  return { ok: true, hub: { port: cfg.port, persona: path.basename(cfg.personaFile), wakeWord: cfg.wakeWord }, voice, speech, brain, face: faceH, image: img, video: vid, vision: eyes };
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
    // she keeps the look she had last time until she is told to change it (not back to the base photo on a restart)
    try {
      const k = JSON.parse(fs.readFileSync(LOOK_STATE, 'utf8'));
      if (k.look && fs.existsSync(k.look)) {
        this.currentLook = k.look; this.currentLookPrompt = k.prompt || null;
        this.lookFace = k.face && fs.existsSync(k.face) ? k.face : null;
      }
    } catch {}
  }
  saveLook() {
    try { fs.writeFileSync(LOOK_STATE, JSON.stringify({ look: this.currentLook, prompt: this.currentLookPrompt, face: this.lookFace })); } catch {}
  }
  queueJob(job) {
    this.jobs++;
    job.finally(() => {
      this.jobs--; this.lastActive = Date.now();
      // nothing else queued: SD goes off the card instead of sitting beside the face and her brain
      if (cfg.imageUnloadIdle && this.jobs === 0) image.unload().then(u => u && this.log('image engine unloaded (idle)'));
    });
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
      const vh = await video.ready();
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

  async onUtterance({ pcm_b64, sampleRate = 16000, durationMs, frames }) {
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
    await this.respond(utter, frames);
  }

  async onText({ text, frames }) {
    text = String(text || '').trim();
    if (!text) return;
    this.send({ type: 'heard', text, typed: true });
    await this.respond(text, frames);
  }

  /** A still from the shared camera / screen while nobody is talking: read it, score it against the last one, and
   *  if a friend would say something, she does. Skipped whenever she is busy, a clip renders, or it is too soon. */
  async onGlance({ frames }) {
    if (!cfg.ambient || !frames?.length || this.glancing) return;
    const now = Date.now();
    if (this.busy || gpu.rendering > 0 || this.reelBusy || now - this.lastActive < cfg.ambientQuietMs) return;
    this.glancing = true;
    try {
      this.glances ||= {}; this.absent ||= 0;
      let best = null;
      for (const f of frames.slice(0, 2)) {
        const g = await vision.glance(f);
        if (this.busy) return;                          // the operator spoke meanwhile; their turn wins
        const prev = this.glances[g.source] || null;
        const sc = vision.friendScore(g, prev, { absentGlances: this.absent });
        if (g.source === 'camera') this.absent = g.person ? 0 : this.absent + 1;
        this.glances[g.source] = g;
        this.send({ type: 'glance', glance: g, score: sc.score, why: sc.why });
        this.log(`glance ${g.source} (${g.ms} ms): person=${g.person} mood=${g.mood} doing=${g.doing} notable=${g.notable} -> ${sc.score} ${sc.why.join('; ')}`);
        if (!best || sc.score > best.sc.score) best = { g, sc };
      }
      if (!best || best.sc.score < cfg.ambientThreshold) return;
      if (Date.now() - (this.lastInterject || 0) < cfg.ambientCooldownMs || this.busy || gpu.rendering > 0) return;
      this.lastInterject = Date.now();
      const g = best.g;
      const seen = g.source === 'screen' ? `on their screen: ${g.doing}${g.notable ? `; ${g.notable}` : ''}`
        : g.person ? `through your camera: they look ${g.mood || 'the same'}, ${g.doing || ''}${g.notable ? `; ${g.notable}` : ''}` : 'through your camera: they walked away';
      await this.respond(`[Nobody said anything. You just noticed ${seen} (${best.sc.why.join('; ')}). Say one short thing about it out loud, the way a close friend would, without asking what they want.]`, null, { ambient: true });
    } catch (e) { this.log('glance failed', e.message); }
    finally { this.glancing = false; }
  }

  async respond(userText, frames, { ambient = false } = {}) {
    if (ambient && (this.busy || gpu.rendering > 0)) return;
    if (this.busy) this.interrupt('new-input');
    // the operator always wins: any clip rendering now (idle or asked for) is cancelled and the reply waits until
    // the render has really stopped, so the brain never shares the card with Wan (that jam crawled for minutes).
    // The cancelled job releases the face itself; the look it made is already on her face.
    const freeing = !ambient && gpu.rendering > 0 ? video.stopRender(3000) : null;
    const epoch = ++this.epoch;
    this.queue.epoch = epoch;
    const ac = new AbortController();
    this.abort = ac;
    this.busy = true;
    this.lastActive = Date.now();
    this.history.push({ role: 'user', content: userText });
    if (!ambient) this.lastUserText = userText;
    if (ambient) { /* her own remark: no look adoption, no marker from the note */ }
    else if (this.lastPic && THAT_YOU.test(userText)) {
      // the last picture becomes her look as it is; image lines she writes this turn are ignored so she cannot
      // redraw herself back to her default
      this.adoptEpoch = epoch;
      const job = this.adopt(this.lastPic, this.lastPicPrompt, userText, epoch);
      this.queueJob(job);
    } else if (wearAsk(userText)) {
      const g = wearAsk(userText);
      this.log('dressing her: ' + g + ' (from the operator\'s words)');
      this.onTag({ kind: 'img', text: 'Unity wearing a ' + g, wear: true }, epoch);
      this.wearEpoch = epoch;
    } else if (parseMarks(userText)) {
      // marker / paint / lipstick on her is drawn from the operator's words, whatever line her brain writes: it
      // answered "write hole with a down arrow in lipstick" with a movement clip and nothing got drawn
      this.onTag({ kind: 'img', text: userText, mark: true }, epoch);
      this.markEpoch = epoch;
    }
    while (this.history.length > cfg.historyTurns * 2) this.history.shift();
    const persona = readPersona();
    // and by tokens: past num_ctx Ollama cuts from the front, which is her persona; the oldest turns go first instead
    const room = cfg.numCtx - cfg.numPredict - 1024 - estTokens(persona);
    while (this.history.length > 1 && this.history.reduce((n, m) => n + estTokens(m.content), 0) > room) this.history.shift();
    const messages = [{ role: 'system', content: persona }, ...this.history];
    let full = '';
    const webCalls = [];
    this.send({ type: 'status', stage: frames?.length ? 'looking' : 'thinking', epoch });
    try {
      if (freeing) await freeing;           // the card is free before her brain loads
      if (frames?.length) {
        // what she sees goes in front of the operator's words for this turn only; the history keeps their words
        const seen = await vision.describe(frames, { signal: ac.signal });
        if (epoch !== this.epoch) return;
        for (const s of seen) this.log(`sees (${s.source}, ${s.ms} ms): ${s.text || s.error || 'nothing'}`);
        this.send({ type: 'seen', seen, epoch });
        const ctx = vision.asContext(seen);
        if (ctx) messages[messages.length - 1] = { role: 'user', content: userText + ctx };
        this.send({ type: 'status', stage: 'thinking', epoch });
      }
      // asked about the weather, the news, a score: looked up before she answers (her brain only writes emotion cues
      // and made up "it's fucking freezing"), and handed to her with the operator's words for this turn
      if (cfg.web && !ambient && web.needsLookup(userText)) {
        const found = await this.lookup(userText, ac.signal, epoch);
        if (epoch !== this.epoch) return;
        if (found) {
          const last = messages[messages.length - 1];
          messages[messages.length - 1] = { role: 'user', content: last.content + '\n' + found + '\n[Answer from that, in your own words, out loud and short. Never read a web address aloud.]' };
        }
        this.send({ type: 'status', stage: 'thinking', epoch });
      }
      // her hands on the web: a [[search]] / [[fetch]] line is run by the hub and the answer handed back, and she
      // goes on from there (two rounds at most, then she talks with what she has)
      for (let round = 0; round <= cfg.webRounds; round++) {
        const splitter = new SentenceSplitter();
        const tags = new TagFilter(tag => WEB_KINDS.includes(tag.kind) ? (cfg.web && round < cfg.webRounds && webCalls.push(tag)) : this.onTag(tag, epoch));
        let part = '';
        const asked = webCalls.length;
        for await (const delta of chatStream(messages, { signal: ac.signal, purpose: round ? 'reply, after the web' : `reply to: ${userText.slice(0, 60)}`, waitRenderMs: 30000 })) {
          if (epoch !== this.epoch) return;
          part += delta;
          this.send({ type: 'delta', epoch, text: delta });
          for (const s of splitter.push(tags.push(delta))) this.say(s, epoch);
        }
        for (const s of splitter.push(tags.flush())) this.say(s, epoch);
        for (const s of splitter.flush()) this.say(s, epoch);
        full += (full && part ? '\n' : '') + part;
        const calls = webCalls.slice(asked);
        if (!calls.length) break;
        const found = await this.runWeb(calls, ac.signal, epoch);
        if (epoch !== this.epoch) return;
        messages.push({ role: 'assistant', content: part }, { role: 'user', content: `${found}\n[Now answer me with what you found, in your own words. Do not write another search line unless you really need one.]` });
        this.send({ type: 'status', stage: 'thinking', epoch });
      }
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

  /** The operator asked something only the web knows: the weather from wttr.in (this computer's location unless a
   *  place is named), anything else a search on their words. -> text for her brain, or '' */
  async lookup(userText, signal, epoch) {
    const t0 = Date.now();
    if (web.isWeather(userText)) {
      this.send({ type: 'status', stage: 'checking the weather', epoch });
      const w = await web.weather(userText, { signal });
      this.log('weather: ' + (w.ok ? w.text : w.error) + ' (' + (Date.now() - t0) + ' ms)');
      this.send({ type: 'web', kind: 'weather', query: w.place || 'here', ok: w.ok, title: w.text, url: w.url, error: w.error, epoch });
      if (w.ok) return '[The weather right now, looked up just now: ' + w.text + ']';
    }
    return this.runWeb([{ kind: 'search', text: web.searchWords(userText) }], signal, epoch);
  }

  /** Run her web lines; -> the text handed back to her brain. The UI shows what she looked up. */
  async runWeb(calls, signal, epoch) {
    const out = [];
    for (const c of calls.slice(0, 3)) {
      const isFetch = ['fetch', 'open', 'read'].includes(c.kind);
      this.send({ type: 'status', stage: isFetch ? 'reading the page' : 'searching the web', epoch });
      const t0 = Date.now();
      if (isFetch) {
        const r = await web.fetchPage(c.text, { signal, maxChars: cfg.webFetchChars });
        this.log(`fetch ${c.text}: ${r.ok ? `${r.chars} chars` : r.error} (${Date.now() - t0} ms)`);
        this.send({ type: 'web', kind: 'fetch', query: c.text, ok: r.ok, title: r.title, url: r.url, error: r.error, epoch });
        out.push(r.ok ? `[Page ${r.url} "${r.title || ''}":\n${r.text}]` : `[Could not read ${c.text}: ${r.error}]`);
      } else {
        const r = await web.search(c.text, { signal, n: cfg.webResults });
        this.log(`search "${c.text}": ${r.ok ? `${r.results.length} from ${r.engine}` : r.error} (${Date.now() - t0} ms)`);
        this.send({ type: 'web', kind: 'search', query: c.text, ok: r.ok, engine: r.engine, results: r.results, error: r.error, epoch });
        out.push(r.ok ? `[Web search "${c.text}" (${r.engine}):\n${r.results.map((x, i) => `${i + 1}. ${x.title} — ${x.url}\n   ${x.snippet}`).join('\n')}]`
          : `[Web search "${c.text}" found nothing: ${r.error}]`);
      }
    }
    return out.join('\n');
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
    if (this.wearEpoch === epoch && !tag.wear && ['img', 'image', 'selfie', 'look'].includes(tag.kind)) {
      this.log('tag ' + tag.kind + ' ignored: this turn already dresses her from the operator\'s words');
      return;
    }
    if (this.markEpoch === epoch && !tag.mark && ['img', 'image', 'selfie', 'look', 'pic', 'picture', 'photo', 'draw', 'do', 'action'].includes(tag.kind)) {
      this.log(`tag ${tag.kind} ignored: this turn is marker on her, already drawn`);
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
        // decided on the operator's words, not hers: she re-describes her own hair and makeup in every tag, and
        // "black hair with pink streaks, smudged eyeliner" on a "take ur top off" made a stranger from scratch
        // a marker / paint / lipstick ask is never a restyle: "write slut across your skin" made a stranger
        const markAsk = !tag.restyle && !!parseMarks(this.lastUserText);
        const restyle = !markAsk && (tag.restyle || image.isRestyle(this.lastUserText));
        // an edit that says nothing about clothes ("write SLUT on your shoulder") keeps what she has on: her current
        // look rides along, or the model undressed her on its own
        const keep = !restyle && !CLOTHES.test(prompt) ? (this.currentLookPrompt || cfg.idleLookPrompt) : '';
        const src = image.editSource(this.currentLook, restyle);
        const faceBox = src ? await face.facebox(src) : null;
        // "write SLUT on your stomach", "draw an arrow on your belly": the ink is drawn where it was asked and blended
        // in, on her current picture (the model cannot spell or aim a mark, and redrew her clothes trying)
        const marks = src && !restyle ? parseMarks(this.lastUserText) : null;
        if (marks) this.log(`marker: ${JSON.stringify(marks.items)}`);
        const res = marks
          ? { ...(await image.mark(src, marks.items, faceBox)), prompt }
          : await image.render(keep ? `${prompt}, ${keep}` : prompt, { sourceFile: this.currentLook, restyle, faceFile: this.lookFace, faceBox,
              // adding something (a collar, glasses, a necklace) repaints lightly so her clothes come from the picture:
              // a full-strength repaint re-rolled them and she undressed or changed outfits on her own
              strength: ADDS.test(this.lastUserText || '') && !UNDRESS.test(this.lastUserText || '') ? cfg.lookAddStrength : undefined });
        if (this.closed) return;
        if (restyle) this.lookFace = res.file;
        this.currentLook = res.file;
        // the idle reel keeps describing THIS look, not a later motion; a mark keeps the look she had (with the ink)
        this.currentLookPrompt = marks ? (this.currentLookPrompt || cfg.idleLookPrompt) : prompt;
        this.saveLook();
        this.send({ type: 'image', url: res.url, prompt, seed: res.seed, seconds: res.seconds, kind: tag.kind, epoch });
        if (cfg.lookDrivesFace) {
          const f = await face.appearance(res.file);
          this.send({ type: 'look', stage: f?.ok ? 'live' : 'image-only', kind: tag.kind, prompt, face: f, epoch });
          if (f?.ok) await face.settle();          // the new look on screen before the video render holds the frame
        }
        // a mark is a still edit of the look she has: no clip of the operator's sentence (her idle reel takes it up)
        if (marks) return;
        // motion: when the video engine is up, every look also becomes a clip of her doing it
        const vh = await video.ready();
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
        if (/cancelled/.test(e.message)) { this.log('look clip cancelled: the operator spoke'); return; }   // the look itself is live
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
      this.saveLook();
      this.send({ type: 'look', stage: 'rendering', kind: 'img', prompt: picPrompt, epoch });
      if (cfg.lookDrivesFace) {
        const f = await face.appearance(file);
        this.send({ type: 'look', stage: f?.ok ? 'live' : 'image-only', kind: 'img', prompt: picPrompt, face: f, epoch });
        if (f?.ok) await face.settle();
      }
      const vh = await video.ready();
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
      const vh = await video.ready();
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
        const text = await chatOnce([{ role: 'system', content: readPersona() }, ...this.history, { role: 'user', content: ask }], { purpose: 'idle plan' });
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
    try { fs.rmSync(LOOK_STATE, { force: true }); } catch {}
    // back to her default picture on screen too, not just in memory (the face kept the last look after a reset)
    face.appearance(cfg.lookBase).catch(() => {});
  }

  async onMessage(raw) {
    let m;
    try { m = JSON.parse(raw); } catch { return; }
    switch (m.type) {
      case 'utterance': return this.onUtterance(m);
      case 'text': return this.onText(m);
      case 'glance': return this.onGlance(m);
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
  console.log(`voice=${cfg.voiceUrl} speech=${cfg.speechUrl} ollama=${cfg.ollamaUrl} models=${cfg.brainModels.join(',')} num_ctx=${cfg.numCtx}`);
});
