// voice-synth-worker.mjs — HER VOICE, synthesized by HER OWN PROCESS. ONE LANE.
//
// ⛔⛔ PIPER IS GONE (2026-10-18). Operator: "piper should of been gutted i told
// u to use unity-voice V2". The first cut of the v2 swap kept piper as a
// "never-mute floor" — a fallback by another name, against the 2026-09-01
// ruling ("no fallbacks. PERIOD") and against the instruction itself ("get rid
// of the Unity one voice model"). It left the browser's piper lane firing first
// on every reply, so she had two voices. This file now has one.
//
// Pipeline:
//   text (+ how she feels) --POST--> unity-voice-v2 --> 24 kHz PCM (image/wav)
//        --perceiveAudio--> field-A rec  (1-D CDF 9/7 — her voice AS equations)
//
// `perceiveAudio` STAYS. It is the percept transport, not the old model: it
// takes raw PCM and never knew which synthesizer made it. Viewers still
// receive a few KB of equations and run the inverse transform to play.
//
// If v2 is not answering, `synthRec` returns null and the reply is SILENT —
// counted on `v2stat.engineDown`, never a substitute voice. Same principle as
// the emission path: honest silence over a plausible stand-in.
//
// The engine: `models/unity-voice-v2/serve.py` — 127.0.0.1 only, one line on
// the GPU at a time, `POST /say {text, emotion, intensity, speech_act}` ->
// audio/wav PCM_16 @ 24000 Hz, `GET /health`. Deliveries outside the trained
// (emotion x act x intensity) support are a 422 WITH A REASON, so intensity is
// clamped from `voice-meta.json` at runtime (see loadV2Support).
import { parentPort } from 'worker_threads';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

const V2_URL = (process.env.UNITY_VOICE_V2_URL || 'http://127.0.0.1:5123').replace(/\/+$/, '');
const V2_TIMEOUT_MS = parseInt(process.env.UNITY_VOICE_V2_TIMEOUT_MS || '20000', 10);
const V2_DIR = process.env.UNITY_VOICE_V2_DIR || '';

// ⛔ COUNTED, NOT SWALLOWED. A voice lane that goes quiet without saying why
// is the failure this project keeps paying for. Published to the proxy on
// every reply so "she has been silent for an hour" is a readable number.
const v2stat = { ok: 0, refused: 0, engineDown: 0, unreachable: 0, lastError: null, lastErrorAt: 0 };

// ── THE DELIVERY SUPPORT ENVELOPE — read, never guessed ──────────────────────
// `voice-meta.json` publishes 63 rows (9 emotions x 7 acts), each with an
// intensity window AND a pace window. Measured on the shipped file: every
// non-neutral emotion 0.25..0.85, `neutral` exactly 0.00 — and ⛔ 20 of the 63
// pairs have a pace window that does NOT contain 1.0 (sad/aside is 0.9..0.9,
// happy/instruction 1.05..1.05). The model's support check is the PRODUCT of
// both windows, so a caller that never sends a pace is refused on a third of
// the grid while believing it only had intensity to get right — which is
// exactly how the first grid harness read ok=45 / silent=21. Both windows are
// read from the file so a retrain widens them by itself; a literal here would
// keep refusing deliveries a new model supports. Bounds DERIVED from data, as
// docs/THRESHOLD-DERIVATION.md asks.
let v2support = null;   // Map "emotion|act" -> { min, max, paceMin, paceMax } | false when absent

function loadV2Support() {
  const candidates = [
    process.env.UNITY_VOICE_V2_META,
    V2_DIR && path.join(V2_DIR, 'voice-meta.json'),
    path.join(ROOT, 'voice-engine', 'unity-voice-v2', 'voice-meta.json'),
  ].filter(Boolean);
  for (const p of candidates) {
    try {
      const meta = JSON.parse(fs.readFileSync(p, 'utf8'));
      const rows = Array.isArray(meta.delivery_support) ? meta.delivery_support : [];
      if (!rows.length) continue;
      const map = new Map();
      for (const r of rows) {
        if (!r || !r.emotion || !r.speech_act || !r.clips) continue;
        map.set(`${r.emotion}|${r.speech_act}`, {
          min: Number(r.intensity_min), max: Number(r.intensity_max),
          paceMin: Number(r.pace_min), paceMax: Number(r.pace_max),
        });
      }
      if (map.size) {
        console.log(`[VoiceV2] delivery support loaded: ${map.size} (emotion x act) pairs from ${p}`);
        return map;
      }
    } catch { /* try the next candidate */ }
  }
  // Reported, never assumed-permissive-and-silent: without the envelope an
  // out-of-range intensity 422s, and the refusal counter tells that story.
  console.warn('[VoiceV2] no voice-meta.json found (set UNITY_VOICE_V2_DIR or UNITY_VOICE_V2_META) — '
    + 'intensity cannot be clamped to the trained support, so out-of-range deliveries will 422.');
  return false;
}

/** PLACE a delivery inside the trained support for this (emotion, act).
 *  Intensity: a strength in [0, 1] → the window, linear (0 = floor, 1 =
 *  ceiling). Pace: her natural 1.0, pulled to the nearest edge of the pair's
 *  recorded pace window when 1.0 lies outside it — a pair recorded only at
 *  0.9 is delivered at 0.9, because that is the only pace the model has ever
 *  SEEN for it and asking for 1.0 is asking for unseen acting (a 422, by the
 *  model's own rule). The brain says HOW STRONGLY she feels it; the model's
 *  own voice-meta.json says what voltage and what pace that is — so nothing
 *  upstream knows 0.25 / 0.85 / 0.9, a retrain widens the range by itself,
 *  and an out-of-support 422 is impossible by construction (a surviving 422
 *  can only be an unknown emotion or act, i.e. a real mapping bug).
 *  `neutral` is trained at exactly 0.00, so any strength maps to 0.
 *  Returns { intensity, pace } — `pace` is null when the file has no window,
 *  and is then simply not sent. */
function placeDelivery(emotion, act, strength) {
  const m = Number.isFinite(strength) ? Math.min(1, Math.max(0, strength)) : 0;
  if (!v2support || typeof v2support.get !== 'function') return { intensity: strength, pace: null };
  const w = v2support.get(`${emotion}|${act}`);
  if (!w || !Number.isFinite(w.min) || !Number.isFinite(w.max)) return { intensity: strength, pace: null };
  const intensity = +(w.min + m * (w.max - w.min)).toFixed(3);
  const pace = (Number.isFinite(w.paceMin) && Number.isFinite(w.paceMax))
    ? +Math.min(w.paceMax, Math.max(w.paceMin, 1.0)).toFixed(3) : null;
  return { intensity, pace };
}

/** Decode a RIFF/WAVE buffer to { pcm: Float32Array, sampleRate }. Chunks are
 *  WALKED, not read at byte 44 — soundfile may emit a LIST chunk first, and
 *  assuming the offset is how you get a burst of noise at the head of a line. */
function decodeWav(buf) {
  if (buf.length < 12 || buf.toString('ascii', 0, 4) !== 'RIFF' || buf.toString('ascii', 8, 12) !== 'WAVE') {
    throw new Error('v2 did not return a RIFF/WAVE body');
  }
  let fmt = null;
  let data = null;
  let off = 12;
  while (off + 8 <= buf.length) {
    const id = buf.toString('ascii', off, off + 4);
    const size = buf.readUInt32LE(off + 4);
    const body = off + 8;
    if (id === 'fmt ') {
      fmt = { audioFormat: buf.readUInt16LE(body), channels: buf.readUInt16LE(body + 2), sampleRate: buf.readUInt32LE(body + 4), bits: buf.readUInt16LE(body + 14) };
    } else if (id === 'data') {
      data = buf.subarray(body, Math.min(body + size, buf.length));
    }
    off = body + size + (size & 1);
  }
  if (!fmt || !data) throw new Error('v2 WAV missing fmt or data chunk');
  const ch = Math.max(1, fmt.channels);
  let mono;
  if (fmt.audioFormat === 1 && fmt.bits === 16) {
    const n = Math.floor(data.length / 2 / ch);
    mono = new Float32Array(n);
    for (let i = 0; i < n; i++) { let s = 0; for (let c = 0; c < ch; c++) s += data.readInt16LE((i * ch + c) * 2); mono[i] = (s / ch) / 32768; }
  } else if (fmt.audioFormat === 3 && fmt.bits === 32) {
    const n = Math.floor(data.length / 4 / ch);
    mono = new Float32Array(n);
    for (let i = 0; i < n; i++) { let s = 0; for (let c = 0; c < ch; c++) s += data.readFloatLE((i * ch + c) * 4); mono[i] = s / ch; }
  } else {
    throw new Error(`v2 WAV subtype not handled (format ${fmt.audioFormat}, ${fmt.bits}-bit)`);
  }
  if (!mono.length) throw new Error('v2 WAV decoded to zero samples');
  return { pcm: mono, sampleRate: fmt.sampleRate };
}

/** Ask unity-voice-v2 for a line. Returns { pcm, sampleRate } or null.
 *  ⛔ A 422 is NOT a transport failure: serve.py answers 422 with a reason for
 *  an unknown emotion/act — that is OUR mapping being wrong, counted apart. */
async function synthV2(text, emotion, intensity, speechAct) {
  if (v2support === null) v2support = loadV2Support();
  const placed = (emotion && speechAct && v2support)
    ? placeDelivery(emotion, speechAct, intensity) : { intensity, pace: null };
  const body = JSON.stringify({
    text: String(text),
    ...(emotion ? { emotion } : {}),
    ...(Number.isFinite(placed.intensity) ? { intensity: placed.intensity } : {}),
    ...(speechAct ? { speech_act: speechAct } : {}),
    // Honoured by serve.py when present (an optional field; absent = its own
    // 1.0 default, so an older shim behaves exactly as before).
    ...(Number.isFinite(placed.pace) ? { pace: placed.pace } : {}),
  });
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), V2_TIMEOUT_MS);
  try {
    const res = await fetch(`${V2_URL}/say`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, signal: ctl.signal });
    if (res.status === 422) {
      const why = await res.text().catch(() => '');
      v2stat.refused++;
      v2stat.lastError = `422 ${why.slice(0, 200)}`;
      v2stat.lastErrorAt = Date.now();
      console.warn(`[VoiceV2] REFUSED (422) — our emotion/act mapping sent something it was not trained on: ${why.slice(0, 200)}`);
      return null;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const got = decodeWav(Buffer.from(await res.arrayBuffer()));
    v2stat.ok++;
    return got;
  } catch (err) {
    v2stat.unreachable++;
    v2stat.lastError = String((err && err.message) || err);
    v2stat.lastErrorAt = Date.now();
    return null;
  } finally {
    clearTimeout(t);
  }
}

// `perceiveAudio` — the CDF 9/7 — loaded once. It is a dependency of the ONLY
// lane, so it is loaded eagerly at start, not behind anything.
let perceiveAudio = null;
const audioReady = import(new URL('../js/brain/mindspace/audio.js', import.meta.url).href)
  .then((m) => { perceiveAudio = m.perceiveAudio; });

/** text (+ how she feels) → { rec, sampleRate, voice:'v2' } | null (silent). */
async function synthRec(text, emotion, intensity, speechAct) {
  const got = await synthV2(text, emotion, intensity, speechAct);
  if (!got) return null;
  await audioReady;
  const rec = perceiveAudio(got.pcm, got.sampleRate);
  if (!rec) {
    v2stat.lastError = 'perceiveAudio produced no rec from a decoded v2 WAV';
    v2stat.lastErrorAt = Date.now();
    return null;
  }
  return { rec, sampleRate: got.sampleRate, voice: 'v2' };
}

parentPort.on('message', async (m) => {
  const { id, text, emotion, intensity, speechAct } = m || {};
  try {
    const out = await synthRec(text, emotion, intensity, speechAct);
    if (out) parentPort.postMessage({ id, rec: out.rec, sampleRate: out.sampleRate, voice: out.voice, v2: { ...v2stat } });
    else parentPort.postMessage({ id, error: `silent — ${v2stat.lastError || 'v2 produced nothing'}`, v2: { ...v2stat } });
  } catch (err) {
    parentPort.postMessage({ id, error: String((err && err.message) || err), v2: { ...v2stat } });
  }
});

// Readiness = the ONE voice answering. Not ready = she is silent, and the
// log says exactly what to start.
(async () => {
  await audioReady.catch(() => {});
  try {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 4000);
    const res = await fetch(`${V2_URL}/health`, { signal: ctl.signal }).finally(() => clearTimeout(t));
    if (res.ok) {
      console.log(`[VoiceSynth] unity-voice-v2 READY at ${V2_URL} — her voice, with emotion. The only lane.`);
      parentPort.postMessage({ ready: true, voice: 'v2' });
      return;
    }
    throw new Error(`health HTTP ${res.status}`);
  } catch (err) {
    v2stat.engineDown++;
    console.warn(`[VoiceSynth] unity-voice-v2 NOT reachable at ${V2_URL} (${String((err && err.message) || err)}) — `
      + 'she will be SILENT until it answers. Start it: python serve.py --port 5123 from models/unity-voice-v2 '
      + '(windows/start.bat does this). Every reply re-tries, so she speaks the moment it is up.');
    parentPort.postMessage({ ready: false, voice: 'v2', error: 'unity-voice-v2 not reachable' });
  }
})();
