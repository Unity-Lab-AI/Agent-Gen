/**
 * listen.js — `U3E-8.3` / `8.4` / `8.5`. Knowing when someone is talking,
 * when to stop, and when to answer.
 *
 * ⛔ THE TRAP, AND IT IS WRITTEN HERE BECAUSE IT IS EASY TO "SIMPLIFY" INTO
 *   The codec's audio chunk is 32768 samples ≈ 1.37 s. That is a STORAGE
 *   window, chosen so the wavelet ladder has every level available. It is NOT a
 *   latency window. Judging barge-in on a 1.37 s chunk would take over a second
 *   to notice a person started talking, which reads as her ignoring them.
 *
 *   So VAD runs on its own **~20 ms frame**, alongside. Same audio, different
 *   window, and the two must not be merged by anyone tidying up later.
 *
 * ⛔ ECHO: she speaks into the same room she listens to.
 *   Without cancellation she hears herself and barges in on her own voice. The
 *   `getUserMedia` constraints below are the first line; the `speaking` flag is
 *   the second, because browser AEC is good and not perfect.
 *
 * ⛔ BOTH ENDPOINTING FAILURES ARE RUDE
 *   Cutting in early and sitting there after someone has clearly finished are
 *   equally wrong, and tuning only against one produces the other. The
 *   thresholds are named, adjustable in settings, and the numbers chosen get
 *   recorded rather than buried.
 *
 * ⛔ PLATFORM LAW: Web Audio only. No dependencies. Works on the S23.
 */

const FRAME_MS = 20;              // ⛔ the VAD window. NOT the codec's 1.37 s.
const NOISE_ADAPT = 0.995;        // slow floor tracker
const SPEECH_FACTOR = 3.5;        // energy multiple over the floor to call speech
const SPEECH_ONSET_FRAMES = 3;    // ~60 ms — rejects clicks and door bumps
const BARGE_IN_FRAMES = 5;        // ~100 ms of speech while she talks -> stop her

/**
 * ⛔⛔ THIS FILE ONLY EVER MEASURED ENERGY. IT CAPTURED NOTHING.
 *
 * Reported from use: pressing talk and speaking left it saying "transcribing"
 * forever. The cause was structural, not a tuning miss: there was an
 * `AnalyserNode` for level and **no capture node of any kind** — no worklet, no
 * ScriptProcessor, no MediaRecorder. `onSpeechEnd` reported a duration and there
 * were never any samples behind it.
 *
 * ⚠ It read as working for as long as `hear` was ABSENT, because the caller's
 *   else-branch just said "STT is absent" and everyone believed it. The moment
 *   the capability went true the empty path became live, settled a turn with no
 *   text, and sat on "transcribing…" forever. **A capability flag flipping is
 *   what exposed dead code that had been dead since it was written.**
 *
 * ⛔ ScriptProcessor is deprecated and is used deliberately: an AudioWorklet
 *   needs a separately-served module file, and the PLATFORM LAW here is Web
 *   Audio with zero dependencies that works on an S23. Revisit only with a
 *   worklet that ships in this repo.
 */
const CAPTURE_BUF = 4096;

/**
 * ⭐ PRE-ROLL. Onset needs 3 frames (~60 ms) to be *sure* someone is talking,
 *   so capturing from the moment of certainty clips the start of the first
 *   word — "hello" arrives as "ello". This keeps a rolling ~300 ms so the
 *   utterance handed over begins BEFORE the detection did.
 */
const PREROLL_MS = 300;

export function createListener(opts = {}) {
  let ctx = null, stream = null, source = null, analyser = null;
  let capture = null, mute = null;
  let chunks = [], captured = 0;
  let preroll = [], prerollLen = 0, prerollMax = 0;
  let timer = 0;
  let running = false;

  let noiseFloor = 0.0008;
  let speechFrames = 0, silenceFrames = 0;
  let inSpeech = false;
  let sheIsSpeaking = false;
  let muted = false;
  let lastLevel = 0;

  const cb = {
    onSpeechStart: opts.onSpeechStart || (() => {}),
    onSpeechEnd: opts.onSpeechEnd || (() => {}),
    onBargeIn: opts.onBargeIn || (() => {}),
    onLevel: opts.onLevel || (() => {}),
    onBands: opts.onBands || (() => {}),
    onWave: opts.onWave || (() => {}),
    onTooShort: opts.onTooShort || (() => {}),
  };

  // tuning, all overridable from settings
  const cfg = {
    endpointSilenceMs: opts.endpointSilenceMs ?? 900,
    sensitivity: opts.sensitivity ?? 0.5,   // 0..1, scales SPEECH_FACTOR
    bargeIn: opts.bargeIn ?? true,
    maxUtteranceMs: opts.maxUtteranceMs ?? 30000,

    /**
     * ⛔ THE GATE. A level range has to be cleared before it starts listening —
     *   without one it triggers on a squeaking chair and on typing.
     *
     * ⚠ THE OLD ABSOLUTE FLOOR WAS 0.0015, which is roughly nothing. The
     *   adaptive floor made it worse rather than better: in a quiet room it
     *   tracks DOWN toward silence, so `noiseFloor * factor` collapses and a
     *   keystroke clears the bar easily. An adaptive threshold with no absolute
     *   minimum will always eventually trigger on room noise.
     *
     * Two independent gates, because one cannot do both jobs:
     *   `minLevel`       — an ABSOLUTE floor. A keyboard click is short and
     *                      sharp but not loud; speech at a desk mic sits well
     *                      above this.
     *   `minUtteranceMs` — a DURATION floor. A chair squeak or a key clears an
     *                      energy bar for a few frames and then stops; a word
     *                      does not. This is the one that kills squeaks, and no
     *                      amount of level tuning substitutes for it.
     */
    minLevel: opts.minLevel ?? 0.012,
    minUtteranceMs: opts.minUtteranceMs ?? 350,
  };

  let utteranceStart = 0;
  const bands = new Float64Array(32);

  async function start() {
    if (running) return { ok: true };
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      // ⛔ Absent, not broken. Say which.
      return { ok: false, reason: 'this browser has no microphone API' };
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          // ⛔ First line against hearing herself. See the header.
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      });
    } catch (e) {
      // A refused permission is a legitimate answer, not an error state to
      // spin on — the caller shows it and the app keeps working typed.
      return { ok: false, reason: e.name === 'NotAllowedError'
        ? 'microphone permission was refused'
        : `microphone unavailable: ${e.message}` };
    }

    ctx = new (window.AudioContext || window.webkitAudioContext)();
    source = ctx.createMediaStreamSource(stream);
    analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    analyser.smoothingTimeConstant = 0.2;
    source.connect(analyser);

    // ── capture (the thing this file never did) ──────────────────────────────
    capture = ctx.createScriptProcessor(CAPTURE_BUF, 1, 1);
    prerollMax = Math.ceil((PREROLL_MS / 1000) * ctx.sampleRate);
    capture.onaudioprocess = (ev) => {
      if (!running) return;
      const inp = ev.inputBuffer.getChannelData(0);
      if (inSpeech) {
        chunks.push(new Float32Array(inp));
        captured += inp.length;
      } else {
        // rolling pre-roll so the first word is not clipped
        preroll.push(new Float32Array(inp));
        prerollLen += inp.length;
        while (prerollLen - preroll[0].length >= prerollMax) {
          prerollLen -= preroll.shift().length;
        }
      }
      // ⚠ ScriptProcessor only runs while connected to a destination. A muted
      //   gain node keeps it alive without playing the microphone back into the
      //   room — which would be an instant feedback loop.
      ev.outputBuffer.getChannelData(0).fill(0);
    };
    mute = ctx.createGain();
    mute.gain.value = 0;
    source.connect(capture);
    capture.connect(mute);
    mute.connect(ctx.destination);

    const time = new Float32Array(analyser.fftSize);
    const freq = new Uint8Array(analyser.frequencyBinCount);

    running = true;
    timer = setInterval(() => tick(time, freq), FRAME_MS);
    return { ok: true, sampleRate: ctx.sampleRate };
  }

  /** Flatten pre-roll + utterance and resample to the codec's rate. */
  function takeUtterance(targetRate = 24000) {
    const all = [...preroll, ...chunks];
    let n = 0;
    for (const c of all) n += c.length;
    const flat = new Float32Array(n);
    let o = 0;
    for (const c of all) { flat.set(c, o); o += c.length; }
    resetCapture();

    const src = ctx ? ctx.sampleRate : targetRate;
    // ⛔ Linear resample. The mic is 48 kHz on almost every machine and the
    //   codec is 24 kHz; handing it the wrong rate makes her voice a chipmunk
    //   and whisper hear gibberish.
    let out = flat;
    if (src !== targetRate && n > 1) {
      const m = Math.max(1, Math.round(n * targetRate / src));
      out = new Float32Array(m);
      for (let i = 0; i < m; i++) {
        const x = i * (n - 1) / (m - 1);
        const i0 = Math.floor(x), i1 = Math.min(n - 1, i0 + 1);
        out[i] = flat[i0] + (flat[i1] - flat[i0]) * (x - i0);
      }
    }
    const pcm = new Int16Array(out.length);
    for (let i = 0; i < out.length; i++) {
      const v = Math.max(-1, Math.min(1, out[i]));
      pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
    }
    return { pcm, sampleRate: targetRate };
  }

  function resetCapture() {
    chunks = []; captured = 0;
    preroll = []; prerollLen = 0;
  }

  function tick(time, freq) {
    if (!running || !analyser) return;
    /**
     * ⛔ MUTED MEANS NOTHING IS HEARD — AND THE SESSION STAYS UP.
     *
     * THE REQUIREMENT: mute yourself without stopping the conversation.
     * Stopping the listener was the only control, and it tears down the
     * microphone, the
     * adaptive noise floor and the whole conversation footing — so coming back
     * costs a permission-shaped pause and a floor that has to relearn the room.
     *
     * ⚠ THE REAL MUTE IS ON THE TRACK (see `setMuted`), so the browser's own
     *   microphone indicator goes dark and nothing reaches the page at all. This
     *   early return is the second line: no VAD, no onset, no capture, and the
     *   orb is told the room is silent rather than left frozen at its last
     *   level, which would read as still listening.
     */
    if (muted) {
      if (inSpeech) { inSpeech = false; speechFrames = 0; resetCapture(); }
      cb.onLevel(0);
      cb.onBands(bands.fill(0));
      return;
    }
    analyser.getFloatTimeDomainData(time);
    analyser.getByteFrequencyData(freq);

    // RMS over the 20 ms frame
    let s = 0;
    for (let i = 0; i < time.length; i++) s += time[i] * time[i];
    const rms = Math.sqrt(s / time.length);
    lastLevel = rms;

    // ⭐ Feed the orb the same octave-band layout the codec produces, so
    //   "listening" is driven by your actual voice rather than animated.
    const per = Math.max(1, Math.floor(freq.length / bands.length));
    for (let b = 0; b < bands.length; b++) {
      let acc = 0;
      for (let k = 0; k < per; k++) acc += freq[b * per + k] || 0;
      bands[b] = (acc / per) / 255;
    }
    cb.onBands(bands);
    // ⭐ The same waveform the speaking path uses, so the visualiser is the
    //   real signal whoever is talking — her voice or yours.
    cb.onWave(time);
    cb.onLevel(rms);

    // adaptive noise floor — only tracked while NOT in speech, or a long
    // utterance would raise the floor until it swallowed itself
    if (!inSpeech) noiseFloor = noiseFloor * NOISE_ADAPT + rms * (1 - NOISE_ADAPT);

    const factor = SPEECH_FACTOR * (1.6 - cfg.sensitivity);   // higher sensitivity -> lower bar
    // ⛔ THE ABSOLUTE FLOOR IS THE GATE. `noiseFloor * factor` alone collapses
    //   in a quiet room — the adaptive floor tracks toward silence, so the bar
    //   drops until a keystroke clears it. `cfg.minLevel` is the thing a chair
    //   and a keyboard sit under and a voice sits over.
    const isSpeech = rms > Math.max(noiseFloor * factor, cfg.minLevel);

    if (isSpeech) {
      speechFrames++;
      silenceFrames = 0;
    } else {
      silenceFrames++;
      if (!inSpeech) speechFrames = 0;
    }

    // ── barge-in (U3E-8.4) ───────────────────────────────────────────────────
    if (sheIsSpeaking && cfg.bargeIn && speechFrames >= BARGE_IN_FRAMES) {
      // ⚠ 100 ms of sustained speech, not one loud frame. A cough should not
      //   stop her mid-sentence, and a person starting to talk should.
      cb.onBargeIn();
      sheIsSpeaking = false;
    }

    // ── onset ────────────────────────────────────────────────────────────────
    if (!inSpeech && speechFrames >= SPEECH_ONSET_FRAMES) {
      inSpeech = true;
      utteranceStart = Date.now();
      cb.onSpeechStart();
    }

    // ── the duration gate, applied to the WHOLE utterance ────────────────────
    // ⚠ Nothing below this point can fire for a squeak, because a squeak never
    //   lasts `minUtteranceMs`. It is enforced at the END rather than the start
    //   so a real word is never truncated waiting to qualify.

    // ── endpoint (U3E-8.5) ───────────────────────────────────────────────────
    if (inSpeech) {
      const silentMs = silenceFrames * FRAME_MS;
      const tooLong = Date.now() - utteranceStart > cfg.maxUtteranceMs;
      if (silentMs >= cfg.endpointSilenceMs || tooLong) {
        inSpeech = false;
        speechFrames = 0;
        // The speech itself, minus the trailing silence that ended it.
        const durationMs = Date.now() - utteranceStart;
        const speechMs = Math.max(0, durationMs - silentMs);

        if (speechMs < cfg.minUtteranceMs) {
          // ⛔ TOO SHORT TO BE A WORD — dropped, and SAID so rather than
          //   silently swallowed. This is the keyboard and the chair. Reporting
          //   it means "it ignored me" is distinguishable from "it never heard
          //   me", which are different bugs with the same symptom.
          resetCapture();
          cb.onTooShort({ speechMs, minUtteranceMs: cfg.minUtteranceMs, level: lastLevel });
          return;
        }

        const { pcm, sampleRate } = takeUtterance();
        cb.onSpeechEnd({
          durationMs, speechMs, silentMs,
          endedBy: tooLong ? 'max-length' : 'silence',
          pcm, sampleRate,
        });
      }
    }
  }

  function stop() {
    running = false;
    if (timer) { clearInterval(timer); timer = 0; }
    if (capture) { try { capture.disconnect(); } catch {} capture.onaudioprocess = null; capture = null; }
    if (mute) { try { mute.disconnect(); } catch {} mute = null; }
    resetCapture();
    if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
    if (ctx) { ctx.close().catch(() => {}); ctx = null; }
    analyser = null; source = null;
    inSpeech = false; speechFrames = 0; silenceFrames = 0;
  }

  return {
    start, stop,
    isRunning: () => running,
    isSpeaking: () => inSpeech,
    /** Tell the listener she has the floor, so barge-in can arm. */
    setSheIsSpeaking(v) { sheIsSpeaking = !!v; },

    /**
     * ⭐ Mute the microphone WITHOUT ending the session. The track is disabled at
     *   source, so the browser stops delivering audio and its own recording
     *   indicator goes dark — a mute that only ignored samples would leave the
     *   indicator lit and the person rightly not believing it.
     *
     * ⚠ Anything half-captured is dropped on the way in, not kept and resumed.
     *   Splicing the two halves of a sentence around a mute produces a
     *   transcript of something nobody said.
     */
    setMuted(v) {
      muted = !!v;
      if (stream) for (const t of stream.getAudioTracks()) t.enabled = !muted;
      if (muted) { inSpeech = false; speechFrames = 0; silenceFrames = 0; resetCapture(); }
      return muted;
    },
    isMuted() { return muted; },
    setConfig(patch) { Object.assign(cfg, patch || {}); },
    /**
     * ⛔ For the diagnostics panel — the numbers actually in force, not the
     * ones someone remembers choosing. Both endpointing failures are rude, and
     * tuning is only defensible if the values are visible.
     */
    stats() {
      return {
        frameMs: FRAME_MS,
        noiseFloor: Number(noiseFloor.toFixed(6)),
        level: Number(lastLevel.toFixed(6)),
        inSpeech,
        muted,
        endpointSilenceMs: cfg.endpointSilenceMs,
        minLevel: cfg.minLevel,
        minUtteranceMs: cfg.minUtteranceMs,
        capturedSamples: captured,
        sensitivity: cfg.sensitivity,
        bargeIn: cfg.bargeIn,
        note: 'VAD runs at 20 ms. The codec chunk is 1.37 s and is a STORAGE window — not this.',
      };
    },
  };
}
