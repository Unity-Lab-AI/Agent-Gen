/**
 * hearing.js — HER EARS, as a rolling buffer of real sound.
 *
 * The requirement: she must be able to HEAR when spoken to, not merely carry a
 * text-to-speech wrapper over a text chain.
 *
 * ⛔ THE GAP THIS FILLS, stated exactly. She already HAD ears and already had
 * the mathematics:
 *   • `js/brain/auditory-cortex.js` runs a real tonotopic cortex — frequency
 *     bins mapped with cortical magnification across the speech band, driving
 *     currents, salience and an amygdala startle. She FEELS sound.
 *   • `mindspace/audio.js perceiveAudio` turns PCM into a CDF 9/7 field-A, and
 *     `describeAudio` reads that field as an octave-band percept vector —
 *     ⚠ a function that existed with ZERO consumers until this file.
 * What was missing was neither the ear nor the maths: it was **the PCM**. The
 * mic reached the AnalyserNode (frequency magnitudes only) and the WORDS came
 * from `SpeechRecognition`'s transcript, so she got energy with no words and
 * words with no sound, and nothing bound the two.
 *
 * ⛔⛔ WHY A ROLLING BUFFER AND NOT "RECORD WHEN SHE HEARS SPEECH".
 * `SpeechRecognition` does not hand back the audio it recognised, and it only
 * tells you a phrase happened AFTER it finished. Any design that starts
 * recording on a speech event has already missed the utterance. So the tap
 * keeps the last N seconds ALWAYS, and the transcript reaches back for the
 * window it belongs to. **The recogniser names the sound; it never sources it.**
 *
 * ⚠ NOT A CLAIM OF SPEECH RECOGNITION. She does not transcribe. The transcript
 * still comes from the browser and that is honest — what changes is that the
 * sound is no longer thrown away, and her words are now anchored to a percept
 * she actually took in.
 */

const RING_SECONDS = 20;      // enough for any single utterance, bounded on purpose
const TARGET_RATE = 24000;    // what perceiveAudio expects
const TAP_FRAMES = 4096;      // ~85ms at 48k — a memcpy per callback, nothing more

export class HearingTap {
  /**
   * @param {AudioContext} ctx   the SAME context the analyser uses
   * @param {MediaStreamAudioSourceNode} source  the live mic source
   */
  constructor(ctx, source) {
    this.ctx = ctx;
    this.rate = ctx.sampleRate || 48000;
    this.size = Math.ceil(this.rate * RING_SECONDS);
    this.ring = new Float32Array(this.size);
    this.written = 0;          // total samples ever written — never wraps
    this.active = false;
    this.lastLevel = 0;
    this._node = null;

    try {
      // ⚠ ScriptProcessorNode is deprecated and chosen deliberately over an
      // AudioWorklet: the worklet needs a separately-served module file, and a
      // 404 on it fails SILENTLY into "she has no ears" — the exact class of
      // failure this whole lane exists to end. This node is one memcpy per
      // callback and works everywhere without a second network dependency.
      this._node = ctx.createScriptProcessor(TAP_FRAMES, 1, 1);
      this._node.onaudioprocess = (e) => {
        const inBuf = e.inputBuffer.getChannelData(0);
        let peak = 0;
        for (let i = 0; i < inBuf.length; i++) {
          const v = inBuf[i];
          this.ring[(this.written + i) % this.size] = v;
          const a = v < 0 ? -v : v;
          if (a > peak) peak = a;
        }
        this.written += inBuf.length;
        this.lastLevel = peak;
      };
      source.connect(this._node);
      // ⚠ A ScriptProcessor only fires while connected to a destination. Routing
      // it to a ZERO-GAIN node keeps the callbacks alive without putting the
      // microphone into the speakers — which would be an instant feedback loop.
      const mute = ctx.createGain();
      mute.gain.value = 0;
      this._node.connect(mute);
      mute.connect(ctx.destination);
      this._mute = mute;
      this.active = true;
      console.log(`[Hearing] ear open — ${RING_SECONDS}s rolling buffer at ${this.rate} Hz. She hears the sound, not just the transcript.`);
    } catch (err) {
      // Failing here must never take the page down: she keeps her tonotopic
      // cortex and her transcript, and simply cannot bind them this session.
      console.warn('[Hearing] could not open the PCM tap — she will hear energy but not utterances:', err && err.message);
      this.active = false;
    }
  }

  /** Seconds of audio currently held (capped by the ring). */
  get bufferedSeconds() {
    return Math.min(this.written, this.size) / this.rate;
  }

  /**
   * Take the last `seconds` of sound, resampled to 24 kHz mono.
   *
   * ⚠ Linear resampling on purpose: this feeds a wavelet transform whose own
   * tolerance is 2% relative L2, so a polyphase filter would be precision
   * nobody downstream can use. Returns null when the ear has not filled yet —
   * **null, never a zero-filled array**, because silence and no-data must not
   * be the same value to whatever reads it next.
   */
  takeRecent(seconds) {
    if (!this.active) return null;
    const want = Math.min(
      Math.ceil(this.rate * Math.max(0.2, Math.min(seconds, RING_SECONDS))),
      Math.min(this.written, this.size),
    );
    if (want < this.rate * 0.2) return null;   // under 200ms is not an utterance

    const start = this.written - want;
    const src = new Float32Array(want);
    for (let i = 0; i < want; i++) src[i] = this.ring[(start + i) % this.size];

    if (this.rate === TARGET_RATE) return src;
    const ratio = TARGET_RATE / this.rate;
    const outLen = Math.max(1, Math.floor(want * ratio));
    const out = new Float32Array(outLen);
    for (let i = 0; i < outLen; i++) {
      const t = i / ratio;
      const i0 = t | 0;
      const i1 = Math.min(want - 1, i0 + 1);
      const f = t - i0;
      out[i] = src[i0] * (1 - f) + src[i1] * f;
    }
    return out;
  }

  /** RMS of the most recent tap callback — used to refuse silent windows. */
  get level() { return this.lastLevel; }

  close() {
    try { if (this._node) this._node.disconnect(); } catch { /* nf */ }
    try { if (this._mute) this._mute.disconnect(); } catch { /* nf */ }
    this._node = null; this._mute = null; this.active = false;
  }
}
