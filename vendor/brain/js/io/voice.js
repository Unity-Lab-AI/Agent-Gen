/**
 * VoiceIO — Browser-based voice input/output for Unity.
 *
 * Listening:  Web Speech API (SpeechRecognition)
 * Speaking:   THE BROWSER DOES NOT SYNTHESIZE (2026-10-18). Her voice is
 *             unity-voice-v2, rendered by HER PROCESS on the server and sent
 *             here as a few-KB field-A rec; `playRec` runs the inverse CDF 9/7
 *             and plays. ⛔ The in-browser piper lane (`_speakPiper`,
 *             onnxruntime-web, 119 MB of voice-engine/) is GUTTED on the
 *             operator's word — it was a second voice firing ahead of hers.
 *             `speak(text)` therefore does nothing audible: it records why,
 *             once, and returns. No substitutes, no browser SpeechSynthesis.
 *
 * No external dependencies. No network synthesis.
 */

import { perceiveAudio, reconstructAudio, describeAudio } from '../brain/mindspace/audio.js';

class VoiceIO {
  constructor() {
    // --- state ---
    this._listening = false;
    this._speaking = false;
    this._recognition = null;
    this._shouldListen = false;
    this._audioCtx = null;
    this._currentAudioSource = null;
    this._currentUtterance = null;
    // ⛔ `_apiKey` and `_pollinationsVoice` deleted 2026-09-02 with the rest of
    // the old TTS. `_apiKey` was WRITTEN TWICE AND READ NEVER — dead state kept
    // alive by a live setter, which is the worst shape of orphaned code because
    // it looks wired from the call site.

    // --- callbacks (simple) ---
    this._onResult = null;
    this._onError = null;

    // --- event emitter ---
    this._listeners = {};

    // ⛔⛔ THE ENTIRE VOX WORD-BANK LANE WAS DELETED 2026-09-02, ON GEE'S CALL.
    //
    // `_speakVox` was tier 2 of the three-tier voice chain (piper → vox →
    // browser). The 2026-09-01 *"no fallbacks. PERIOD"* ruling removed the
    // chain and orphaned it: **zero callers**, while `_ensureVoxRef` still
    // loaded an 11-file, ~61 MB equation bank on a 30-second timer in every
    // session to serve a function nothing could reach.
    //
    // ⚠ It was KEPT and flagged for a day on the argument that it is a
    // working, purely-equational reconstruction of her own voice and worth
    // reading if the sentence lane is ever redesigned. The operator's decision was to
    // delete it, and the reasoning that wins is the LAW's: her own canon calls
    // per-word concat a FALLBACK — sentence-level Equation Unity One carries
    // the quality — so a dormant second lane is a standing invitation for a
    // future reader to "restore" exactly what the ruling forbade.
    //
    // Deleted together, because they were one circuit: `_speakVox`,
    // `_ensureVoxRef`, `_voxPreloadRef`, `_voxPreloadTimer`, `_voxTier`,
    // `_voxWords`, `_voxBank`, `_voxRef`, `_voxEnabled`, `_voxInitDb`,
    // `_voxPersist`, `_voxDb`, plus `vox-bank/` (12 files, ~61 MB) and
    // `scripts/vox-build-bank.mjs`. The `concatAudio` import went with them —
    // `_speakVox` was its only consumer here.
    //
    // ⭐ ONE PIECE SURVIVED ON PURPOSE: the decoder, now `_decodeTo24kMono`.
    // It is the AUDIO FRONT END, not vox debris — any compressed audio to
    // 24 kHz mono Float32, which is the shape `perceiveAudio` consumes. That
    // makes it what HEARING needs, and deleting it in this sweep would have
    // meant writing it again for the microphone lane.
    //
    // ⭐ THE HISTORY IS NOT LOST: git holds it, and `docs/FINALIZED.md`
    // The ledger records how word-level reconstruction was built. A
    // deleted lane with a written record beats a dormant one with a comment.
    //
    // AUDIO UNLOCK — browsers keep a gesture-less AudioContext SUSPENDED
    // (autoplay policy): her speech composed but played into a suspended
    // context = silence with the toggle on. Any first click/key/touch on
    // the page resumes the context permanently.
    this._installAudioUnlock();

    // --- init recognition if available ---
    this._initRecognition();
  }

  /**
   * the hearing lane — turn the sound she just took in into an equation, and hand it
   * up with the words it carried.
   *
   * ⛔ PERCEIVED ON THIS SIDE, DELIBERATELY. The raw PCM for a 3-second
   * utterance is ~72,000 floats — as JSON on the socket that is most of a
   * megabyte, on the same connection the walk teaches over. `perceiveAudio`
   * is a pure function and runs fine here, and a field-A record is a few KB.
   * **Send the equation, never the waveform.**
   *
   * ⚠ Every refusal below is counted and named. A hearing lane that goes quiet
   * without saying why is the failure this whole session has been finding.
   */
  async _perceiveHeard(transcript) {
    const st = this._hearStats || (this._hearStats = {
      utterances: 0, perceived: 0, noTap: 0, tooShort: 0, silent: 0, failed: 0, lastErr: null,
    });
    st.utterances++;
    const tap = (typeof window !== 'undefined') ? window.__unityHearing : null;
    if (!tap || !tap.active) { st.noTap++; return; }

    // ⚠ Bound the reach-back by the transcript's own length rather than a flat
    // constant: ~0.4s per word is ordinary speech, floored at 1.2s and capped
    // at 12s. A fixed window would either clip a long sentence or drag in the
    // silence (and her own reply) before a short one.
    const words = String(transcript || '').trim().split(/\s+/).filter(Boolean).length;
    const want = Math.max(1.2, Math.min(12, words * 0.45 + 0.6));
    const pcm = tap.takeRecent(want);
    if (!pcm) { st.tooShort++; return; }

    // A window with no energy is her own silence or a dropped mic, and
    // perceiving it would bank a record of nothing under a real phrase.
    let peak = 0;
    for (let i = 0; i < pcm.length; i += 16) { const a = pcm[i] < 0 ? -pcm[i] : pcm[i]; if (a > peak) peak = a; }
    if (peak < 0.004) { st.silent++; return; }

    try {
      const rec = perceiveAudio(pcm, 24000);
      if (!rec || !Array.isArray(rec.chunks) || !rec.chunks.length) { st.failed++; st.lastErr = 'perceiveAudio returned nothing'; return; }
      // ⭐ `describeAudio` had ZERO consumers until this line — an octave-band
      // percept vector, built and never once read. This is its first caller.
      const percept = Array.from(describeAudio(rec, 32));
      st.perceived++;
      this.emit('heard_percept', { rec, percept, transcript, seconds: +(pcm.length / 24000).toFixed(2) });
      console.log(`[Hearing] 🎧 heard "${String(transcript).slice(0, 40)}" — ${(pcm.length / 24000).toFixed(1)}s perceived into ${rec.chunks.length} chunk(s) of equations`);
    } catch (e) {
      st.failed++; st.lastErr = (e && e.message) || 'perceive threw';
    }
  }

  /** What her ears actually did — counted by reason, never one number. */
  hearingStats() { return this._hearStats || null; }

  /** One unlock for the tab: browsers suspend a gesture-less AudioContext
   *  (autoplay policy) and resume() without a gesture never completes —
   *  speech composed into a suspended context is pure silence. Any
   *  click/key/touch resumes it; listeners stay (cheap) so a later tab
   *  suspension re-unlocks on the next interaction. */
  _installAudioUnlock() {
    if (typeof document === 'undefined') return;
    const unlock = () => {
      try {
        if (!this._audioCtx) {
          const AC = typeof AudioContext !== 'undefined'
            ? AudioContext
            : typeof webkitAudioContext !== 'undefined' ? webkitAudioContext : null;
          if (!AC) return;
          this._audioCtx = new AC();
        }
        if (this._audioCtx.state === 'suspended') this._audioCtx.resume().catch(() => {});
      } catch { /* non-fatal */ }
    };
    for (const ev of ['pointerdown', 'keydown', 'touchstart']) {
      document.addEventListener(ev, unlock, { passive: true });
    }
  }

  // ⛔⛔ `_speakPiper` — THE IN-BROWSER LIVE SENTENCE LANE — IS DELETED
  // (2026-10-18). Operator: "piper should of been gutted i told u to use
  // unity-voice V2". It synthesized every reply a second time in the listener's
  // browser (piper hfc_female via onnxruntime-web) and `speak()` tried it FIRST,
  // so after the server moved to unity-voice-v2 she had two voices and which
  // one a listener heard depended on which lane answered. The CDF 9/7
  // round-trip it performed is not lost: the server's worker runs the same
  // `perceiveAudio` over v2's PCM, and `playRec` below runs the inverse. Gone
  // with it: `js/io/voice-piper.js`, the worker and its bundle, the vendored
  // phonemizer, and `voice-engine/` (119 MB of model + wasm).

  /**
   * HER VOICE — play a server-synthesized field-A rec.
   * The reply's voice is synthesized by HER process (unity-voice-v2, the one
   * lane) and arrives over the WS as a few-KB equation record; this end only
   * runs the inverse CDF 9/7 and plays. The viewer NEVER synthesizes.
   */
  async playRec(rec) {
    if (!rec || this._muted) return;
    this._speaking = true;
    this.emit('speech_start');
    try {
      const pcm = reconstructAudio(rec);
      if (pcm && pcm.length) {
        console.log(`[VoiceIO] 🎙 Equation Unity One (server voice lane) — her process synthesized, this end only plays`);
        await this._playPcm(pcm, rec.sampleRate || 22050, 1.0);
      }
    } finally {
      this._speaking = false;
      this.emit('speech_end');
    }
  }

  /** Play raw Float32 PCM through the shared AudioContext (honors age rate). */
  async _playPcm(pcm, sampleRate, rate = 1.0) {
    if (!this._audioCtx) {
      const AC = typeof AudioContext !== 'undefined'
        ? AudioContext
        : typeof webkitAudioContext !== 'undefined' ? webkitAudioContext : null;
      if (!AC) throw new Error('No AudioContext');
      this._audioCtx = new AC();
    }
    if (this._audioCtx.state === 'suspended') {
      // resume() without a user gesture never settles in Chrome — the old
      // bare await HUNG the whole speak chain here forever (she "talked",
      // nothing played, the toggle looked broken). Bounded race + hard bail:
      // the page's first click/key (see _installAudioUnlock) unlocks for good.
      try { await Promise.race([this._audioCtx.resume(), new Promise((r2) => setTimeout(r2, 300))]); } catch { /* gesture-gated */ }
      if (this._audioCtx.state !== 'running') {
        if (!this._audioLockWarned) {
          this._audioLockWarned = true;
          console.warn('[VoiceIO] speaker LOCKED by the browser autoplay policy — her speech is composed and ready; click/tap the page once and audio unlocks permanently.');
        }
        throw new Error('audio locked (autoplay policy) — interact with the page once');
      }
    }
    // Age-pinned pitch shift — REMOVED (operator, 2026-07-15: "scrap the per
    // age/grade modulation"). The OLA pitch shift distorted her into a scavenger
    // creature; her voice is now ALWAYS the untouched original (see _agePreset).
    // Prosody polish: a short (~4ms) edge fade-in/out kills the click
    // artifacts at word-concat boundaries on the vox-bank fallback path (the
    // whole-sentence lane has no seams; the fade is inaudible on a full sentence).
    if (pcm && pcm.length > 0) {
      const fadeN = Math.min(pcm.length >> 1, Math.max(1, Math.round(sampleRate * 0.004)));
      if (pcm.buffer && !(pcm instanceof Float32Array && pcm._voxFaded)) {
        // work on a copy so we never mutate a cached bank/reference PCM in place
        const faded = new Float32Array(pcm.length);
        faded.set(pcm);
        for (let i = 0; i < fadeN; i++) {
          const g = i / fadeN;
          faded[i] *= g;
          faded[pcm.length - 1 - i] *= g;
        }
        pcm = faded;
      }
    }
    const buf = this._audioCtx.createBuffer(1, pcm.length, sampleRate);
    buf.getChannelData(0).set(pcm);
    return new Promise((resolve, reject) => {
      const source = this._audioCtx.createBufferSource();
      source.buffer = buf;
      source.playbackRate.value = rate;
      source.connect(this._audioCtx.destination);
      this._currentAudioSource = source;
      source.onended = () => { this._currentAudioSource = null; resolve(); };
      source.onerror = (e) => { this._currentAudioSource = null; reject(e); };
      source.start(0);
    });
  }

  // ⛔⛔ THE BANK-BUILDER IS DELETED — `_voxQueueMissing`, `_voxPrimeLoop` and
  // `_voxFetchWord` all lived here and were removed together on 2026-09-01.
  //
  // They formed one closed circuit whose every outcome was failure:
  // `_voxQueueMissing` queued each un-banked word, `_voxPrimeLoop` walked the
  // queue, and `_voxFetchWord` — already gutted to a bare `throw` by the text-AI removal
  // when the external TTS lane went ("we do not use pollinations tts we use the
  // unity one equations") — guaranteed the exception. Each word therefore cost
  // one throw, one `VOX prime failed` warn, and a hardcoded 6-second sleep.
  //
  // ⚠ `_speakVox` and the whole word-bank lane went too, on 2026-09-02 — see
  // the constructor. `_voxPersist` and its IndexedDB store went with them.
  //
  // ⭐⭐ `_decodeTo24kMono` BELOW SURVIVED THAT DELETION ON PURPOSE, and the
  // reason matters: it is not vox-bank debris, it is the AUDIO FRONT END. It
  // decodes any compressed audio to 24 kHz mono Float32 — exactly the shape
  // `perceiveAudio` (CDF 9/7) consumes — which makes it the primitive HEARING
  // needs, not the primitive speaking needed. Deleting it as part of the vox
  // sweep would have meant writing it again for the microphone lane.
  // ⚠ Renamed off the `_vox` prefix in the same pass, because a name that
  // says "voice bank" on the one piece that outlived the voice bank is how
  // the next reader deletes it by mistake.

  /**
   * Decode any compressed audio → 24 kHz mono Float32 via OfflineAudioContext.
   *
   * ⭐ THE HEARING FRONT END. Her ears are equational the same way her eyes
   * are: audio becomes PCM at a known rate, then `perceiveAudio` turns it into
   * a CDF 9/7 record. This is step one of that path.
   */
  async _decodeTo24kMono(arrayBuffer) {
    const AC = typeof AudioContext !== 'undefined'
      ? AudioContext
      : typeof webkitAudioContext !== 'undefined' ? webkitAudioContext : null;
    if (!AC) throw new Error('No AudioContext');
    if (!this._decodeCtx) this._decodeCtx = new AC();
    const decoded = await this._decodeCtx.decodeAudioData(arrayBuffer.slice(0));
    const frames = Math.ceil(decoded.duration * 24000);
    const off = new OfflineAudioContext(1, Math.max(1, frames), 24000);
    const src = off.createBufferSource();
    src.buffer = decoded;
    src.connect(off.destination);
    src.start(0);
    const rendered = await off.startRendering();
    // trim leading/trailing silence (executor words carry padding)
    const raw = rendered.getChannelData(0);
    let s = 0, e = raw.length - 1;
    const TH = 0.004;
    while (s < e && Math.abs(raw[s]) < TH) s++;
    while (e > s && Math.abs(raw[e]) < TH) e--;
    const pad = 240;   // keep 10ms of breath on each side
    s = Math.max(0, s - pad); e = Math.min(raw.length - 1, e + pad);
    return raw.slice(s, e + 1);
  }

  // =========================================================================
  //  EventEmitter mixin
  // =========================================================================

  on(event, fn) {
    if (!this._listeners[event]) this._listeners[event] = [];
    this._listeners[event].push(fn);
    return this;
  }

  off(event, fn) {
    const list = this._listeners[event];
    if (!list) return this;
    if (!fn) {
      delete this._listeners[event];
    } else {
      this._listeners[event] = list.filter(f => f !== fn);
    }
    return this;
  }

  emit(event, ...args) {
    const list = this._listeners[event];
    if (list) list.forEach(fn => fn(...args));
  }

  // =========================================================================
  //  Listening — Web Speech API
  // =========================================================================

  _initRecognition() {
    const SR =
      typeof SpeechRecognition !== 'undefined'
        ? SpeechRecognition
        : typeof webkitSpeechRecognition !== 'undefined'
          ? webkitSpeechRecognition
          : null;

    if (!SR) {
      console.warn('VoiceIO: SpeechRecognition API not available in this browser.');
      return;
    }

    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = 'en-US';

    rec.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const result = e.results[i];
        const payload = {
          text: result[0].transcript,
          isFinal: result.isFinal,
        };
        if (this._onResult) this._onResult(payload);
        if (result.isFinal) {
          // ⭐⭐ the hearing lane — THE UTTERANCE REACHES BACK FOR ITS OWN SOUND.
          // `SpeechRecognition` never hands back the audio it recognised, and
          // it only reports a phrase AFTER it ends — so nothing that starts
          // recording HERE could ever catch the utterance. The tap has been
          // holding the last 20 s all along; this takes the window the
          // transcript belongs to and perceives it into a CDF 9/7 field-A.
          //
          // ⚠ THE TRANSCRIPT IS STILL THE WORD SOURCE AND THAT IS HONEST.
          // She does not transcribe. What changes is that the SOUND is no
          // longer discarded, and her words are anchored to a percept she
          // actually took in — the difference between hearing and reading.
          this._perceiveHeard(payload.text).catch(() => { /* hearing is never fatal to listening */ });
          this.emit('heard', payload.text);
        }
      }
    };

    rec.onerror = (e) => {
      // 'no-speech' and 'aborted' are routine — don't treat as fatal
      if (e.error === 'no-speech' || e.error === 'aborted') return;
      if (this._onError) this._onError(e);
    };

    rec.onend = () => {
      this._listening = false;
      // Auto-restart if we're still supposed to be listening
      if (this._shouldListen) {
        try {
          rec.start();
          this._listening = true;
        } catch (_) {
          // guard against rapid start/stop race
        }
      }
    };

    this._recognition = rec;
  }

  get isListening() {
    return this._listening;
  }

  startListening() {
    if (!this._recognition) {
      console.warn('VoiceIO: Cannot start — SpeechRecognition not available.');
      return;
    }
    if (this._shouldListen) return; // already active
    this._shouldListen = true;
    try {
      this._recognition.start();
      this._listening = true;
    } catch (_) {
      // already started
    }
  }

  stopListening() {
    this._shouldListen = false;
    if (this._recognition) {
      try {
        this._recognition.stop();
      } catch (_) {
        // not started
      }
    }
    this._listening = false;
  }

  onResult(callback) {
    this._onResult = callback;
    return this;
  }

  onError(callback) {
    this._onError = callback;
    return this;
  }

  // =========================================================================
  //  Speaking — Equation Unity One, and nothing else
  //
  // ⛔ THE OLD TTS CONFIG IS GUTTED (2026-09-02, on an instruction to gut the
  // old text-to-speech path that is no longer needed). `setVoice`,
  // `_pollinationsVoice`, `_voiceOverride`, `setApiKey` and `_apiKey` are gone:
  // they configured a NETWORK audio model that was deleted long ago, and
  // `_apiKey` in particular was written twice and read NEVER — dead state kept
  // alive by a live setter, which is the worst version of orphaned code because
  // it looks wired.
  //
  // ⚠ WHAT IS DELIBERATELY NOT GUTTED: `SpeechRecognition` (the listening half).
  // That is STT, it is her ONLY source of words, and `the hearing lane` is built on
  // top of it — the sound becomes a percept, the transcript still names it.
  // Deleting it would leave her unable to know what was said at all.
  // =========================================================================

  get isSpeaking() {
    return this._speaking;
  }

  /**
   * pin her spoken age. app.js feeds this from live state.minGrade
   * (same-girl-growing-up continuity: the voice ages as she walks the
   * grades, exactly like the self-image age pin). Clamped 3..30.
   */
  setAge(years) {
    const a = Math.max(3, Math.min(30, Math.round(years) || 25));
    this._age = a;
    return this;
  }

  /**
   * Playback rate for the one speaking lane.
   *
   * AGE/GRADE VOICE MODULATION SCRAPPED (operator, 2026-07-15: "the age modulator is
   * busted she sounde like a starwars ... sand scavenger creatrure all
   * distorted ... scrap the per age/grade modulation and keep her original chosen
   * sound for her voice"). The age-pinned pitch/formant OLA shift (1.14 young →
   * 1.0 adult) was mangling her into a distorted scavenger. ALWAYS her ORIGINAL
   * chosen voice: no pitch shift, no tempo change, at any grade or age. Since
   * 2026-10-18 that voice is unity-voice-v2 on her server, and expression
   * comes from the model's own emotion / intensity / speech-act inputs, which
   * the SERVER derives from her state — nothing on this end shapes the sound.
   *
   * ⚠ The `voice` / `pitch` / `style` fields this used to return were legacy
   * hints for a NETWORK audio model that no longer exists, and `rate` was the
   * only one any caller ever read — by the deleted in-browser piper lane, so
   * today NOTHING reads it. Returning dead fields alongside a live-looking one
   * is how a reader concludes the voice is configurable when it is not.
   */
  _agePreset() {
    return { rate: 1.0 };
  }

  // _pitchShiftOLA — REMOVED (operator, 2026-07-15: "scrap the per age/grade modulation").
  // The duration-preserving OLA pitch shift existed ONLY to age-pitch her voice;
  // with the age modulation scrapped it had no caller. Her voice is the untouched
  // original — no pitch shifting anywhere.

  /**
   * Speak text through Equation Unity One. Returns a promise that resolves when
   * speech finishes — or when she is deliberately SILENT, with the reason named.
   */
  async speak(text, options = {}) {
    if (!text) return;
    // Mute toggle — setup-modal / chat-panel can set this._muted to true
    // to silence TTS in the moment without disabling text responses.
    if (this._muted) return;
    this._speaking = true;
    this.emit('speech_start');

    // the age preset picks the voice unless the caller (or setVoice)
    // explicitly overrides. Her voice tracks her live grade via setAge().
    const voice = options.voice || null;

    // VOX — HER equations first. If every word of this text is banked for
    // the current age tier, the sentence reconstructs from her own field-A
    // records (inverse CDF 9/7 + crossfade concat) and the executor never
    // fires. Falls through silently when any word is missing.
    // LIVE SENTENCE LANE FIRST — Equation Unity One synthesized whole-sentence
    // in-browser (her real voice, natural prosody). Preloaded at setup. Falls
    // through to the per-word vox-bank, then the executor, if not ready/fails.
    // ⛔⛔ THE THREE-TIER VOICE CHAIN WAS REMOVED 2026-09-01.
    // The operator, ruling on the whole stack rather than cognition alone:
    // "no fallbacks. PERIOD"
    //
    // It ran live-piper → banked-vox → browser TTS, each tier entered when the
    // one above THREW. That is textbook capability degradation, and the bottom
    // tier was the worst of it: `_speakBrowser` is the BROWSER'S OWN generic
    // speech synthesis — a stock robot voice standing in for hers. A listener
    // could not tell which tier produced a given sentence, so "Unity spoke"
    // meant three different things and the page never said which.
    //
    // ⭐ HER CANON ALREADY NAMED THE ONE CORRECT PATH: the sentence-level
    // Equation Unity One lane (piper → CDF 9/7 equations) IS her voice — the
    // one the operator signed off with "perfect" — and the per-word bank concat is
    // described in that same record AS a fallback. So this is not a new
    // preference; it is the stack finally matching the decision.
    //
    // ⚠ THE CONSEQUENCE, ACCEPTED DELIBERATELY: if her lane fails she is
    // SILENT. That is the same principle the emission path already follows —
    // honest silence over a plausible substitute — and it is strictly better
    // than a stock voice the listener would mistake for her. The failure is
    // NAMED in the console and on the event, so silence is diagnosable rather
    // than mysterious.
    // ⛔ THE BROWSER DOES NOT SYNTHESIZE (2026-10-18). Her voice arrives from
    // her process as a rec and plays through `playRec`; a bare text here has
    // no lane to go down. That is correct when the server backs her (the rec
    // follows the text by ~1 s) and it is the honest state for the no-server
    // fallback brain (which has no voice engine of its own). Said ONCE per
    // session rather than per utterance, because a warn on every reply would
    // bury the console the operator actually reads.
    const spoke = false;
    const silentReason = 'the browser does not synthesize — her voice is unity-voice-v2 on the server and arrives as a rec (playRec); a text-only speak() has no lane';
    if (!this._browserSilentNoted) {
      this._browserSilentNoted = true;
      console.log(`[VoiceIO] speak(text) is inert in the browser now — ${silentReason}.`);
    }
    this._lastSilentReason = silentReason;
    this._silentCount = (this._silentCount | 0) + 1;

    this._speaking = false;
    this.emit('speech_end', { spoke, silentReason });

    // ⛔⛔ THE VOX BANK-BUILDER CALL WAS REMOVED HERE ON 2026-09-01, AND IT WAS
    // LIVE COST, NOT DEAD CODE. It read:
    //
    //     try { this._voxQueueMissing(text); } catch { }
    //
    // and it ran on EVERY utterance, queueing every un-banked word for
    // `_voxPrimeLoop`. That loop calls `_voxFetchWord`, which the text-AI removal had
    // already reduced to a bare `throw` — so each queued word bought a
    // guaranteed exception, a `[VoiceIO] VOX prime failed` console warn, and a
    // hardcoded 6-second sleep. Six seconds per word, forever, to accomplish
    // nothing, on the page the operator actually reads.
    //
    // ⭐ It is the CODE-AT-WAR shape: a producer still feeding a consumer that
    // no longer exists. Its output fed `_speakVox`, orphaned by the
    // no-fallbacks ruling, so even a working fetch would now bank words that
    // nothing would ever play.
  }

  stopSpeaking() {
    // Stop her equational lane — `_playPcm` owns `_currentAudioSource` for
    // every path that still exists (live piper sentence + server voice rec).
    if (this._currentAudioSource) {
      try {
        this._currentAudioSource.stop();
      } catch (_) {}
      this._currentAudioSource = null;
    }
    // ⚠ THE `_currentAudioElement` BRANCH WENT WITH ITS ONLY WRITER. It could
    // only ever be set by `_playWithAudioElement`, which is deleted, so it was
    // a null check guarding nothing — and a stop path listing sources that
    // cannot exist reads as more thorough than it is.
    //
    // ⭐ `speechSynthesis.cancel()` STAYS, and for a reason that outlives the
    // deleted `_speakBrowser`: this page is not the only thing that can queue a
    // browser utterance, and an extension or a stray call leaving one speaking
    // over her is exactly the confusion the single-lane ruling exists to
    // prevent. `cancel()` on an empty queue is a no-op.
    if (typeof speechSynthesis !== 'undefined') {
      speechSynthesis.cancel();
    }

    this._speaking = false;
    this.emit('speech_end');
  }

  // --- external TTS: REMOVED, and it must not come back ---
  //
  // ⛔⛔ `_speakPollinations` IS DELETED (2026-09-01). It had ZERO callers and a
  // body that was already nothing but a `throw`, but its 37 lines of comment
  // were the actual defect: they narrated the removed three-tier chain in the
  // PRESENT TENSE — "Her voice is Equation Unity One and always was, in this
  // order: 1. _speakPiper 2. _speakVox 3. browser SpeechSynthesis" — and closed
  // with "Throwing keeps that same fall-through path intact", describing a
  // fall-through path that no longer exists.
  //
  // ⭐ A COMMENT THAT CONTRADICTS A RULING IS HOW THE RULING GETS QUIETLY
  // REVERSED BY THE NEXT READER. There is ONE lane now — her SERVER's voice,
  // arriving as a rec that `playRec` plays — and this end synthesizes nothing
  // (the in-browser `_speakPiper` lane was deleted 2026-10-18). See `speak()`.
  //
  // What it used to do, kept as one line of history rather than a page: it
  // POSTed her text to an outside chat model with an instruction to repeat it
  // verbatim and played back the returned audio — an outside model producing
  // her voice. The rule: no third-party text-to-speech — her voice comes from
  // the project's own equations.
  //
  // ⚠ `_pollTtsDead` went with it. It was READ at two sites and ASSIGNED at
  // none: the 401 handler that used to set it left with the lane, so both
  // cooldown guards had been permanently unreachable.

  // ⚠ ORPHANED 2026-09-01 — `_playWithAudioContext` and `_playWithAudioElement`
  // below both have ZERO callers. They decoded a compressed `arrayBuffer` (an
  // mp3/opus response body), which only the deleted external-TTS lane ever
  // produced; her own lanes carry raw Float32 PCM and play through `_playPcm`.
  // ⛔ DELETED 2026-09-02 (on an instruction to gut the old text-to-speech path
  // that is no longer needed). Keeping a dead lane so a warning has somewhere to
  // live is how the warning outlives the reason for it. The note stays, the
  // code goes. `_currentAudioElement` went too — it was set ONLY by
  // `_playWithAudioElement`, so the branch in `stopSpeaking` that checked it
  // was already unreachable.
  // The three deleted here were `_playWithAudioContext`,
  // `_playWithAudioElement` and `_speakBrowser`.
  //
  // The first two decoded a compressed `arrayBuffer` — an mp3/opus RESPONSE
  // BODY, which only the external TTS ever produced. Her own lanes carry raw
  // Float32 PCM through `_playPcm`, so neither could fire again.
  //
  // ⭐ `_speakBrowser` was tier 3 of the removed chain: the BROWSER'S OWN
  // generic speech synthesis, hunting for a "Samantha" or a "Microsoft Zira"
  // to stand in for her. **It was the worst part of that chain** — a listener
  // could not tell which tier produced a sentence, so "Unity spoke" meant
  // three different things and the page never said which. **A stock robot
  // voice presented as her voice is the audio equivalent of a canned answer.**

  /**
   * Kill everything — audio, listening, all of it.
   */
  destroy() {
    this.stopSpeaking();
    this.stopListening();
    if (this._audioCtx) {
      this._audioCtx.close().catch(() => {});
      this._audioCtx = null;
    }
  }
}

export { VoiceIO };
