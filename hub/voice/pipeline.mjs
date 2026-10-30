// Voice pipeline: sentences in, timed speech out, in order, cancellable. One serial queue per session so
// the model stream is never blocked by synthesis and a barge-in drops everything not yet spoken.
import { cfg } from '../config.mjs';
import { pickDelivery } from './delivery.mjs';
import * as face from '../face/client.mjs';

export async function sayTimed(text, delivery, { signal } = {}) {
  const r = await fetch(`${cfg.voiceUrl}/say_timed`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, signal,
    body: JSON.stringify({ text, emotion: delivery.emotion, speech_act: delivery.speech_act, intensity: delivery.intensity ?? undefined }),
  });
  const j = await r.json().catch(() => ({ error: `voice ${r.status}` }));
  if (!r.ok) throw new Error(j.error || `voice ${r.status}`);
  return j;
}

export class SpeechQueue {
  /** @param {(msg: object) => void} send  */
  constructor(send) { this.send = send; this.chain = Promise.resolve(); this.epoch = 0; this.seq = 0; this.abort = null; this.onSpoken = null; }

  /** Drop everything pending and mark the epoch so in-flight results are discarded. */
  cancel() { this.epoch++; if (this.abort) { this.abort.abort(); this.abort = null; } this.chain = Promise.resolve(); face.interrupt(); }

  enqueue(sentence, epoch) {
    const d = pickDelivery(sentence);
    if (!d.text) return;
    const seq = ++this.seq;
    this.chain = this.chain.then(async () => {
      if (epoch !== this.epoch) return;
      const ac = new AbortController();
      this.abort = ac;
      try {
        const res = await sayTimed(d.text, d, { signal: ac.signal });
        if (epoch !== this.epoch) return;
        this.onSpoken?.(res.spoken || d.text);
        // the face gets the same audio; it answers with how far behind the sound must start to match the lips
        const f = await face.speak(res.wav_b64, res.delivery?.emotion);
        if (epoch !== this.epoch) return;
        const lead_ms = f ? f.lead_ms + cfg.faceLeadMs : 0;
        this.send({ type: 'speak', epoch, seq, text: d.text, spoken: res.spoken, delivery: res.delivery,
          sample_rate: res.sample_rate, duration: res.duration, wav_b64: res.wav_b64, phones: res.phones, visemes: res.visemes,
          synth_ms: res.synth_ms, face: !!f, lead_ms, start_frame: f?.start_frame, audio: f?.played_here ? 'face' : 'ui' });
      } catch (e) {
        if (ac.signal.aborted || epoch !== this.epoch) return;
        this.send({ type: 'speak_error', epoch, seq, text: d.text, error: String(e.message || e) });
      } finally {
        if (this.abort === ac) this.abort = null;
      }
    });
    return this.chain;
  }

  /** Resolves when everything queued for this epoch has been sent (or dropped). */
  drain() { return this.chain; }
}
