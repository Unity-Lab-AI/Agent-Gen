// DUNGEON MASTER: THE HUNT — Kokoro TTS loader + speak proxy.
//
// Kokoro inference happens in a Web Worker (js/setup/kokoro-worker.js) so the
// browser's "Page unresponsive" detector never fires during synthesis. The main
// thread stays free for clicks, scrolls, ticks, and animations while audio is
// being generated. If worker spawn fails (file:// origin / strict CSP / older
// browser), falls back to main-thread synthesis transparently.

(function () {
  'use strict';

  const cfg = () => window.DMTHConfig;

  let worker = null;
  let ready = false;
  let loading = false;
  let lastError = null;
  let progress = 0;
  let nextReqId = 0;
  const pending = new Map();   // reqId → { resolve, reject }

  // Main-thread fallback state (only used if Worker spawn fails)
  let mainTts = null;
  let mainLoading = false;
  let warmedUp = false;
  let keepWarmTimer = null;

  // Hard DISABLE (distinct from the transient mute toggle): when set, Kokoro never loads, never
  // warms, never speaks. The chrome 🔊 button is a MUTE (silences playback but the engine stays
  // resident + warm); this flag is the real OFF switch for users who don't want the model at all.
  function isDisabled() {
    try { return window.localStorage && window.localStorage.getItem('dmth_kokoro_disabled') === '1'; }
    catch { return false; }
  }

  // Fire ONE tiny throwaway synth the instant the model is ready so the FIRST real line skips the
  // cold-inference penalty (WASM kernel compile + default-voice load) that otherwise stacks on top
  // of the model load and delays the first spoken response. Result discarded; failures ignored.
  function maybeWarmup() {
    if (warmedUp) return;
    warmedUp = true;
    setTimeout(() => {
      try {
        const voice = cfg().KOKORO.defaultFemaleVoice;
        if (worker && !mainTts) {
          const id = ++nextReqId;
          pending.set(id, { resolve: () => {}, reject: () => {} });
          worker.postMessage({ type: 'speak', id, text: 'mm', voice, speed: 1.0 });
        } else if (mainTts) {
          mainTts.generate('mm', { voice, speed: 1.0 }).catch(() => {});
        }
      } catch (e) { /* warmup is best-effort */ }
    }, 0);
  }

  const listeners = new Set();
  function emit() {
    const snapshot = { ready, loading, error: lastError, progress };
    for (const fn of listeners) { try { fn(snapshot); } catch {} }
  }

  function initWorker() {
    if (worker) return true;
    try {
      worker = new Worker('js/setup/kokoro-worker.js', { type: 'module' });
    } catch (err) {
      console.warn('[kokoro] worker spawn failed, falling back to main thread:', err);
      worker = null;
      return false;
    }
    worker.onmessage = (e) => {
      const m = e.data || {};
      if (m.type === 'progress') {
        progress = (m.payload && m.payload.progress) || progress;
        emit();
      } else if (m.type === 'ready') {
        ready = true;
        loading = false;
        emit();
        maybeWarmup();
      } else if (m.type === 'error') {
        lastError = new Error(m.message);
        loading = false;
        ready = false;
        emit();
      } else if (m.type === 'speakResult') {
        const p = pending.get(m.id);
        if (!p) return;
        pending.delete(m.id);
        if (m.error) { p.reject(new Error(m.error)); return; }
        if (m.format === 'blob') {
          p.resolve(new Blob([m.bytes], { type: m.mime || 'audio/wav' }));
        } else if (m.format === 'pcm') {
          p.resolve(pcmToWavBlob(new Float32Array(m.bytes), m.sampleRate));
        } else {
          p.reject(new Error('unknown speak result format'));
        }
      }
    };
    worker.onerror = (e) => {
      console.warn('[kokoro] worker error:', e);
      lastError = new Error('worker crashed: ' + (e.message || 'unknown'));
      ready = false;
      // Reset loading flag — without this the "already loading" wait path traps the next
      // retry attempt indefinitely. The button "Load Kokoro" → "Loading…" → never recovers.
      loading = false;
      emit();
    };
    return true;
  }

  // Worker init must produce a 'ready' or 'error' message within this window or we
  // abandon the worker and fall back to main-thread synthesis. Silent worker failures
  // (CDN import hung, WASM blocked, HuggingFace model fetch stuck) were leaving the UI
  // in a "0% progress, no button" state with no way to recover.
  const WORKER_INIT_TIMEOUT_MS = 60_000;

  async function ensureLoaded(onProgress) {
    if (isDisabled()) return;   // hard-disabled — never load the model at all
    if (ready) return;
    if (loading) {
      // Already loading — wait until ready or errored.
      return new Promise((res, rej) => {
        const check = () => {
          if (ready) return res();
          if (lastError) return rej(lastError);
          setTimeout(check, 200);
        };
        check();
      });
    }
    loading = true;
    lastError = null;
    emit();

    // Wrap the whole load in try/finally so loading is ALWAYS reset on any exit path.
    // Without this, a thrown error left `loading=true` forever — the render loop saw
    // "loading=true" + replaced the button with a 0% progress bar that never advanced,
    // and the user had no way to retry.
    try {
      // Try worker first.
      if (initWorker()) {
        const unsub = onStateChange((s) => { if (onProgress) onProgress({ progress: s.progress }); });
        worker.postMessage({
          type: 'init',
          cdnUrl: cfg().KOKORO.cdnUrl,
          modelId: cfg().KOKORO.modelId,
          dtype: cfg().KOKORO.dtype
        });
        let timedOut = false;
        const timeoutId = setTimeout(() => {
          timedOut = true;
          lastError = new Error(`worker init timed out after ${Math.round(WORKER_INIT_TIMEOUT_MS / 1000)}s — falling back to main-thread Kokoro load`);
          emit();
        }, WORKER_INIT_TIMEOUT_MS);

        try {
          await new Promise((res, rej) => {
            const check = () => {
              if (ready) return res();
              if (lastError) return rej(lastError);
              setTimeout(check, 200);
            };
            check();
          });
          clearTimeout(timeoutId);
          return;
        } catch (err) {
          clearTimeout(timeoutId);
          unsub();
          // Tear down the failed worker so a fresh attempt isn't blocked.
          try { worker?.terminate(); } catch {}
          worker = null;
          if (timedOut) {
            // Reset error so the main-thread fallback can try fresh.
            console.warn('[kokoro] worker init timed out — falling back to main-thread load');
            lastError = null;
            await loadMainThread(onProgress);
            return;
          }
          throw err;
        } finally {
          unsub();
        }
      }

      // Worker spawn failed at construction — straight to main-thread load.
      await loadMainThread(onProgress);
    } finally {
      // Whether we resolved, rejected, or threw, clear the loading flag so the UI
      // can present a Retry button on failure or a Ready pill on success.
      loading = false;
      emit();
    }
  }

  async function loadMainThread(onProgress) {
    if (mainTts) { ready = true; loading = false; emit(); return; }
    if (mainLoading) {
      return new Promise((res, rej) => {
        const check = () => {
          if (ready) return res();
          if (lastError) return rej(lastError);
          setTimeout(check, 200);
        };
        check();
      });
    }
    mainLoading = true;
    try {
      const mod = await import(cfg().KOKORO.cdnUrl);
      const KokoroTTS = mod.KokoroTTS || (mod.default && mod.default.KokoroTTS);
      if (!KokoroTTS) throw new Error('kokoro-js did not export KokoroTTS');
      mainTts = await KokoroTTS.from_pretrained(cfg().KOKORO.modelId, {
        dtype: cfg().KOKORO.dtype,
        progress_callback: (p) => {
          progress = (p && p.progress) || progress;
          emit();
          if (onProgress) onProgress(p);
        }
      });
      ready = true;
      loading = false;
      mainLoading = false;
      emit();
      maybeWarmup();
    } catch (err) {
      lastError = err;
      loading = false;
      mainLoading = false;
      emit();
      throw err;
    }
  }

  async function speak(text, voiceId, speedOverride) {
    if (!ready) await ensureLoaded();
    const voice = voiceId || cfg().KOKORO.defaultFemaleVoice;
    const speed = speedOverride != null ? speedOverride : cfg().KOKORO.defaultSpeed;

    if (worker && !mainTts) {
      const id = ++nextReqId;
      const blob = await new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
        worker.postMessage({ type: 'speak', id, text, voice, speed });
      });
      return URL.createObjectURL(blob);
    }

    // Main-thread fallback
    const audio = await mainTts.generate(text, { voice, speed });
    let blob;
    if (audio instanceof Blob) blob = audio;
    else if (audio && typeof audio.toBlob === 'function') blob = audio.toBlob();
    else if (audio && audio.audio && audio.sampling_rate) blob = pcmToWavBlob(audio.audio, audio.sampling_rate);
    else throw new Error('unknown kokoro output shape');
    return URL.createObjectURL(blob);
  }

  // PCM → WAV blob encoder. Used by both the worker-result decoder and the
  // main-thread fallback when kokoro-js returns raw Float32Array + sample rate.
  function pcmToWavBlob(float32, sampleRate) {
    const len = float32.length;
    const buffer = new ArrayBuffer(44 + len * 2);
    const view = new DataView(buffer);
    const write = (off, str) => { for (let i = 0; i < str.length; i++) view.setUint8(off + i, str.charCodeAt(i)); };
    write(0,  'RIFF');
    view.setUint32(4, 36 + len * 2, true);
    write(8,  'WAVE');
    write(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    write(36, 'data');
    view.setUint32(40, len * 2, true);
    let off = 44;
    for (let i = 0; i < len; i++) {
      const s = Math.max(-1, Math.min(1, float32[i]));
      view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      off += 2;
    }
    return new Blob([buffer], { type: 'audio/wav' });
  }

  // Public warm ping — fire a tiny throwaway synth to keep the worker's inference HOT so the next
  // real line skips the cold-start penalty. Safe to spam; no-op when disabled or not yet ready.
  function warmPing() {
    if (isDisabled() || !ready) return;
    try {
      const voice = cfg().KOKORO.defaultFemaleVoice;
      if (worker && !mainTts) {
        const id = ++nextReqId;
        pending.set(id, { resolve: () => {}, reject: () => {} });
        worker.postMessage({ type: 'speak', id, text: 'mm', voice, speed: 1.0 });
      } else if (mainTts) {
        mainTts.generate('mm', { voice, speed: 1.0 }).catch(() => {});
      }
    } catch (e) { /* warmup is best-effort */ }
  }

  // Keep Kokoro engaged + hot while the player is inside a girl's hold: pre-load it up front (so the
  // first response doesn't eat the multi-minute model load) then heartbeat a tiny warm ping so the
  // worker never goes cold between the player's actions — every line then speaks without the
  // cold-start delay. Auto-releases when the player navigates out of any room.
  const KEEP_WARM_INTERVAL_MS = 45_000;
  function engageKeepWarm() {
    if (isDisabled()) return;
    ensureLoaded().then(() => warmPing()).catch(() => {});
    if (keepWarmTimer) return;
    keepWarmTimer = setInterval(warmPing, KEEP_WARM_INTERVAL_MS);
    const onNav = () => {
      const h = (location.hash || '').replace(/^#/, '');
      if (!h.startsWith('room')) { releaseKeepWarm(); window.removeEventListener('hashchange', onNav); }
    };
    window.addEventListener('hashchange', onNav);
  }
  function releaseKeepWarm() {
    if (keepWarmTimer) { clearInterval(keepWarmTimer); keepWarmTimer = null; }
  }

  function isReady() { return ready; }
  function isLoading() { return loading; }
  function getProgress() { return progress; }
  function getError() { return lastError; }
  function onStateChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }

  window.DMTHKokoro = Object.freeze({
    ensureLoaded,
    speak,
    isReady,
    isLoading,
    getProgress,
    getError,
    onStateChange,
    warmPing,
    engageKeepWarm,
    releaseKeepWarm,
    isDisabled
  });
})();
