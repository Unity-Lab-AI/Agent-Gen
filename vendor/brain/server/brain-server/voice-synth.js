// VoiceSynthProxy — her voice lane. ONE lane (2026-10-18).
//
// Wraps server/voice-synth-worker.mjs — unity-voice-v2 (her trained voice,
// with emotion) + the field-A perceive, on a worker THREAD — behind one async
// call: synthesizeRec(text, feel) → { rec, sampleRate, voice } | null. Same
// worker-proxy shape as MindSpaceWorkerProxy. ⛔ There is no donor voice lane
// and no piper floor any more: a donor's voiceSynth was piper, and piper is
// gutted. If v2 is down, null — and that reply is silent with the reason
// counted. The worker respawns itself if the thread ever dies.
const { Worker } = require('worker_threads');
const path = require('path');

class VoiceSynthProxy {
  constructor() {
    this._pending = new Map();
    this._seq = 0;
    this._worker = null;
    this._dead = false;
    this._spawn();
  }

  _spawn() {
    this._dead = false;
    this._worker = new Worker(path.join(__dirname, '..', 'voice-synth-worker.mjs'));
    // Her voice must never hold the process open past shutdown.
    this._worker.unref();
    this._worker.on('message', (m) => {
      if (m && m.ready !== undefined) {
        if (m.ready) console.log(`[VoiceSynth] voice lane READY (${m.voice || 'v2'}) — her replies synthesize in HER process (worker thread), viewers only play.`);
        else console.warn('[VoiceSynth] voice lane NOT ready — she is silent until unity-voice-v2 answers:', m.error || 'unknown');
        this.lastVoice = m.voice || null;
        return;
      }
      if (!m || !this._pending.has(m.id)) return;
      const p = this._pending.get(m.id);
      this._pending.delete(m.id);
      // Which voice spoke, and the v2 tallies, kept on the proxy so a dashboard
      // field can show "v2 has never once run" instead of everyone assuming it
      // did because she is audibly speaking.
      if (m.voice) this.lastVoice = m.voice;
      if (m.v2) this.v2 = m.v2;
      if (m.error) p.resolve(null);
      else p.resolve({ rec: m.rec, sampleRate: m.sampleRate, voice: m.voice });
    });
    this._worker.on('error', (e) => {
      console.warn('[VoiceSynth] worker error:', e?.message || e);
      for (const p of this._pending.values()) p.resolve(null);
      this._pending.clear();
      this._dead = true;
    });
    this._worker.on('exit', (code) => {
      if (code !== 0) console.warn(`[VoiceSynth] worker exited (${code}) — respawns on the next reply.`);
      for (const p of this._pending.values()) p.resolve(null);
      this._pending.clear();
      this._dead = true;
    });
  }

  /**
   * text (+ how she feels) → { rec, sampleRate, voice } | null (never rejects —
   * a mute reply is the worst case; the text was already delivered).
   *
   * `feel` is optional and carries unity-voice-v2's trained parameters:
   *   { emotion, intensity, speechAct }
   * ⛔ THESE COME FROM HER STATE, NEVER FROM THE TEXT. The caller reads her
   * amygdala valence/arousal and the endocrine layer; nothing here inspects a
   * word. A word-list that decided she sounds frustrated would be both the
   * banned shape and a lie, since her chemistry is already the ground truth and
   * is computed every tick. Omitted entirely → v2 uses its own default.
   */
  synthesizeRec(text, feel = null, timeoutMs = 30_000) {
    if (!text || typeof text !== 'string') return Promise.resolve(null);
    if (this._dead) this._spawn();
    // Back-compat: the old signature was (text, timeoutMs).
    if (typeof feel === 'number') { timeoutMs = feel; feel = null; }
    return new Promise((resolve) => {
      const id = ++this._seq;
      const timeout = setTimeout(() => {
        this._pending.delete(id);
        resolve(null);
      }, timeoutMs);
      this._pending.set(id, { resolve: (v) => { clearTimeout(timeout); resolve(v); } });
      try {
        this._worker.postMessage({
          id, text,
          emotion: feel && feel.emotion,
          intensity: feel && feel.intensity,
          speechAct: feel && feel.speechAct,
        });
      } catch (e) { clearTimeout(timeout); this._pending.delete(id); resolve(null); }
    });
  }
}

module.exports = { VoiceSynthProxy };
