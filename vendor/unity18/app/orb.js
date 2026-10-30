/**
 * orb.js — `U3E-8.1` / `U3E-8.2` / `U3E-8.29`. ONE VIBRATING STRING, BENT INTO A
 * CIRCLE, HARPING THE SPEECH.
 *
 * ⛔⛔ WHAT THIS IS, IN GEE'S WORDS:
 *   *"i like the wavy circle like string we just need to change it abit so that
 *   other part doesnt happend and its just the string circle moving and spiking
 *   all crazy like in pattern with tts and user speach as the string harps the
 *   waves of the speech"*.
 *
 *   "That other part" is GONE — the open left-to-right oscilloscope the ring
 *   used to unfurl into, and the equaliser bars that sat behind it. There is one
 *   shape now and it is always the closed string.
 *
 * ⭐ WHAT IS ACTUALLY DRAWN, and every part of it is the audio:
 *   1. THE STRING — the real time-domain samples wrapped around a ring, each
 *      sample pushing the string out or pulling it in at that angle. Loud
 *      transients SPIKE it. These are the pressure-wave numbers, not a sine.
 *   2. IT HARPS — the pattern travels around the ring, faster the louder she is,
 *      so a held note keeps moving instead of standing still.
 *   3. COLOUR FROM PITCH — hue follows the SPECTRAL CENTROID, the brightness
 *      weighted mean of the spectrum. Low voice reads warm, higher reads cool.
 *      Her tone changes the colour because the tone IS the colour.
 *   4. INTENSITY FROM VOLUME — RMS drives spike height, glow, line width and
 *      how fast the pattern travels.
 *
 * ⚠ THE ONE THING A RING NEEDS THAT A FLAT TRACE DOES NOT: the samples must
 *   MEET where the circle closes. Sample 0 and sample N-1 are unrelated numbers,
 *   so joining them raw puts a permanent kink at three o'clock that reads as a
 *   rendering bug. The tail is cross-faded into the head so the loop closes on
 *   itself — the string is continuous, the way a real one is.
 *
 * ⚠ THE TEST THAT SEPARATES THIS FROM DECORATION (`U3E-8.2`) STILL APPLIES:
 *   mute the mapping and it must visibly stop meaning anything. A CSS pulse
 *   that runs while audio plays looks similar and means nothing.
 *
 * ⛔ PLATFORM LAW: canvas at devicePixelRatio, crisp on an S23 and a desktop
 * without a second code path.
 */

/** The four states, legible at a glance without a label. */
export const STATES = ['idle', 'listening', 'thinking', 'speaking'];

/**
 * Hue range walked by the spectral centroid. Not a decoration choice: the whole
 * point is that a change in her tone is visible as a change in colour, so the
 * span has to be wide enough to see and narrow enough to stay hers.
 */
const HUE_LOW = 275;    // violet — chest, low tones
const HUE_HIGH = 185;   // cyan — bright, sibilant

const STATE_TINT = {
  idle:      { hue: 268, sat: 42, glow: 0.16 },
  listening: { hue: 196, sat: 62, glow: 0.30 },
  thinking:  { hue: 42,  sat: 60, glow: 0.24 },
  speaking:  { hue: null, sat: 78, glow: 0.46 },   // null = take it from the audio
};

export function createOrb(canvas) {
  const ctx = canvas.getContext('2d');
  let state = 'idle';

  // ⚠ The bins are still read — they are what the spectral centroid, and so the
  //   COLOUR, is computed from. Only their drawn form (the bars) is gone.
  const N_BANDS = 32;
  let bands = new Float64Array(N_BANDS);   // frequency — now colour only
  let wave = new Float32Array(256);        // time domain — the string itself
  let level = 0, levelSmooth = 0;          // RMS — intensity
  let centroid = 0.5, centroidSmooth = 0.5;// spectral centre — the colour
  let phase = 0;                           // travel around the ring, sped by volume
  let idleLife = 1;                        // self-motion when there is no audio
  let t0 = performance.now();
  let raf = 0;
  let dpr = 1, W = 0, H = 0;

  function resize() {
    dpr = Math.min(3, window.devicePixelRatio || 1);
    const r = canvas.getBoundingClientRect();
    W = Math.max(1, Math.round(r.width * dpr));
    H = Math.max(1, Math.round(r.height * dpr));
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
  }

  function draw(now) {
    resize();
    const dt = Math.min(0.05, (now - t0) / 1000);
    t0 = now;
    const secs = now / 1000;

    // Ease toward the live values. Fast enough to feel connected to the sound,
    // slow enough not to strobe.
    levelSmooth += (level - levelSmooth) * 0.25;
    centroidSmooth += (centroid - centroidSmooth) * 0.12;

    // ⭐ SPEED FROM VOLUME. The trace scrolls faster the louder she is.
    phase += dt * (0.6 + levelSmooth * 5.5);

    // ⚠ Declared before it is used. It was below the old morph block and every
    //   frame threw a TDZ ReferenceError — which, in a requestAnimationFrame
    //   loop, shows up as a blank canvas rather than as an error anyone sees.
    const drive = Math.min(1, levelSmooth * 2.2);

    /**
     * ⭐ HOW MUCH OF THE MOTION IS HERS. A settled orb must not be totally
     *   static, so with no audio the string still drifts and breathes, and that
     *   self-motion FADES OUT as real sound arrives. It can never be mistaken
     *   for the signal, because the moment there is a signal it is gone.
     *
     * ⚠ Driven by SOUND, not by the state flag: `speaking` through a silence
     *   should look settled, and a loud moment while listening should spike.
     */
    idleLife += (Math.max(0, 1 - drive * 2.4) - idleLife) * 0.06;

    const tint = STATE_TINT[state] || STATE_TINT.idle;
    // ⭐ COLOUR FROM PITCH — the centroid walks the hue. Only while she speaks;
    //    the other states keep their own identity so the screen still reads at
    //    a glance when there is no audio.
    const hue = tint.hue == null
      ? HUE_LOW + (HUE_HIGH - HUE_LOW) * centroidSmooth
      : tint.hue;
    const sat = tint.sat;

    ctx.clearRect(0, 0, W, H);
    const cx = W / 2, cy = H / 2;
    const halfH = H * 0.42;

    // ── the string ───────────────────────────────────────────────────────────
    // ⛔ THESE ARE THE ACTUAL SAMPLES. Not a sine, not a spring, not noise — the
    //    pressure wave coming out of the speaker (or into the microphone) at
    //    this instant, bent into a ring.
    const n = wave.length;
    const R = Math.min(W, H) * 0.30;

    /**
     * ⭐ SPIKE HEIGHT. A quiet ring stays close to its circle; a loud one throws
     *   the string out and in hard, which is the wild spiking the design calls
     *   for. The floor is deliberately not zero — even a whisper should
     *   visibly move it, or the picture stops reporting anything at low volume.
     */
    const spike = R * (0.16 + drive * 0.62);

    const trace = (dir, alpha, width) => {
      ctx.beginPath();
      for (let i = 0; i <= n; i++) {
        const idx = i % n;
        const t = i / n;

        /**
         * ⚠ CLOSING THE LOOP HONESTLY. Sample 0 and sample n-1 are unrelated, so
         *   a raw wrap leaves a permanent kink at one angle that reads as a bug.
         *   The last 12% cross-fades into the head, so the string meets itself.
         *   ⛔ It blends REAL sample against REAL sample — it never substitutes
         *   a made-up value to smooth the join.
         */
        const SEAM = 0.12;
        let s = wave[idx];
        if (t > 1 - SEAM) {
          const k = (t - (1 - SEAM)) / SEAM;          // 0 → 1 across the seam
          s = s * (1 - k) + wave[Math.round(k * (n - 1) * SEAM)] * k;
        }

        /**
         * ⭐ IT HARPS. The pattern travels around the ring — `phase` advances
         *   with volume — so a held note keeps moving instead of freezing, and
         *   the whole string reads as plucked rather than posed.
         */
        const a = t * Math.PI * 2 + phase * 0.25;

        // ⚠ Self-motion, and it is gone the moment there is sound: three slow
        //   lobes and a breath so a silent orb is alive but never pretending.
        const life = idleLife * (
          0.055 * Math.sin(a * 3 + secs * 0.85) +
          0.035 * Math.sin(a * 5 - secs * 0.55) +
          0.030 * Math.sin(secs * 1.1)
        );

        const raw = R + s * spike * dir + R * life + R * levelSmooth * 0.30;

        /**
         * ⚠ A SOFT CEILING, BECAUSE THE ARITHMETIC SAYS THIS LEAVES THE FRAME.
         *   At a full-scale sample with the drive maxed, `raw` reaches ~2.08 R =
         *   0.62 of the short side, and the edge is at 0.50 — so the loudest
         *   transients would have been CLIPPED OFF by the canvas, and a spike
         *   that is cut flat at the top stops reporting how loud it was.
         * ⭐ It compresses instead of clipping: below the knee nothing is touched
         *   at all, above it the excess is squashed asymptotically, so a peak
         *   still reads as bigger than the one before it.
         */
        const LIM = Math.min(W, H) * 0.46;
        const rr = raw <= LIM * 0.82
          ? raw
          : LIM * 0.82 + (LIM - LIM * 0.82) * (1 - Math.exp(-(raw - LIM * 0.82) / (LIM * 0.30)));

        const x = cx + Math.cos(a) * rr;
        const y = cy + Math.sin(a) * rr;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.closePath();                                  // ALWAYS a closed string
      ctx.strokeStyle = `hsla(${hue}, ${sat}%, ${62 + drive * 22}%, ${alpha})`;
      ctx.lineWidth = Math.max(1, width * dpr);
      ctx.lineJoin = 'round';
      ctx.stroke();
    };

    // Layered: a soft wide ghost, its inward twin, then the bright core. The
    // twin spikes the opposite way, so a loud transient opens the string in both
    // directions at once instead of only bulging outward.
    ctx.globalCompositeOperation = 'lighter';
    trace(1, 0.20, 6 + drive * 10);
    trace(-1, 0.12, 5 + drive * 8);
    trace(1, 0.95, 1.6 + drive * 2.2);
    trace(-1, 0.38, 1.2 + drive * 1.4);

    // ── 3. the glow, tied to loudness ────────────────────────────────────────
    const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(W, H) * 0.55);
    g.addColorStop(0, `hsla(${hue}, ${sat}%, 60%, ${tint.glow * (0.35 + drive)})`);
    g.addColorStop(1, 'hsla(0,0%,0%,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'source-over';

    // ── 4. thinking: one slow sweep, no spinner clatter ──────────────────────
    if (state === 'thinking') {
      const x = ((secs * 0.35) % 1) * W;
      const sg = ctx.createLinearGradient(x - W * 0.12, 0, x + W * 0.12, 0);
      sg.addColorStop(0, 'hsla(0,0%,0%,0)');
      sg.addColorStop(0.5, `hsla(${hue}, ${sat}%, 62%, 0.20)`);
      sg.addColorStop(1, 'hsla(0,0%,0%,0)');
      ctx.fillStyle = sg;
      ctx.fillRect(x - W * 0.12, cy - halfH, W * 0.24, halfH * 2);
    }

    raf = requestAnimationFrame(draw);
  }

  return {
    start() { if (!raf) raf = requestAnimationFrame(draw); },
    stop() { if (raf) { cancelAnimationFrame(raf); raf = 0; } },

    setState(s) { if (STATES.includes(s)) state = s; },
    getState() { return state; },

    /**
     * The frequency bins — the equaliser, and the colour.
     * ⚠ The spectral centroid is computed HERE rather than passed in, so every
     *   producer (her voice, the microphone) gets the same colour mapping
     *   without having to know about it.
     */
    setBands(b) {
      if (!b) return;
      const n = Math.min(N_BANDS, b.length);
      let num = 0, den = 0;
      for (let i = 0; i < n; i++) {
        const v = b[i] || 0;
        bands[i] = v;
        num += v * i; den += v;
      }
      for (let i = n; i < N_BANDS; i++) bands[i] = 0;
      centroid = den > 0.0001 ? Math.min(1, (num / den) / (N_BANDS - 1)) : centroid;
    },

    /**
     * ⛔ THE ACTUAL SAMPLES. -1..1 time domain. Without this there is no
     *   waveform and the thing on screen is decoration.
     */
    setWave(w) {
      if (!w || !w.length) return;
      if (wave.length !== w.length) wave = new Float32Array(w.length);
      wave.set(w);
      let s = 0;
      for (let i = 0; i < w.length; i++) s += w[i] * w[i];
      level = Math.sqrt(s / w.length);
    },

    /** Overall drive, when a caller has a level but no samples. */
    setLevel(v) { level = Math.max(0, Math.min(1, v || 0)); },

    /**
     * ⛔ `U3E-8.2` — cut the mapping and it must visibly stop meaning anything.
     *   If it still looks right after this, it was never driven by her.
     */
    muteMapping() {
      bands.fill(0); wave.fill(0);
      level = 0; levelSmooth = 0;
    },
  };
}
