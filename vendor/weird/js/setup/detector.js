// DUNGEON MASTER: THE HUNT — runtime detector.
// Checks the status of every prerequisite on every visit:
//   - Ollama reachable?
//   - Preset models pulled?
//   - Kokoro loaded in-browser?
//   - IndexedDB initialized?
//   - Local SD image server reachable + checkpoint ready?
//   - Local voice server reachable + STT model ready?

(function () {
  'use strict';

  const cfg = () => window.DMTHConfig;

  // --- OS detection ---
  function detectOS() {
    const ua = navigator.userAgent || '';
    if (/Windows/i.test(ua)) return 'windows';
    if (/Macintosh|Mac OS X/i.test(ua)) return 'mac';
    if (/Linux/i.test(ua)) return 'linux';
    return 'unknown';
  }

  // --- Ollama probe ---
  async function probeOllama() {
    try {
      const res = await fetch(`${cfg().OLLAMA.endpoint}/api/tags`, {
        method: 'GET',
        mode: 'cors'
      });
      if (!res.ok) {
        return { reachable: false, reason: `HTTP ${res.status}`, models: [] };
      }
      const data = await res.json();
      const models = (data.models || []).map(m => m.name || m.model).filter(Boolean);
      return { reachable: true, models };
    } catch (err) {
      // Usually: CORS block or connection refused
      const msg = String(err?.message || err);
      const looksLikeCors = /Failed to fetch|NetworkError|CORS/i.test(msg);
      return {
        reachable: false,
        reason: looksLikeCors ? 'not-reachable-or-cors' : msg,
        models: []
      };
    }
  }

  async function probeOllamaModelPresent(modelId) {
    const probe = await probeOllama();
    if (!probe.reachable) return { present: false, reason: probe.reason };
    const present = probe.models.includes(modelId);
    return { present, models: probe.models };
  }

  // --- Kokoro probe ---
  // Kokoro-js loaded state lives on window.DMTHKokoro (see setup/kokoro.js)
  function probeKokoro() {
    const k = window.DMTHKokoro;
    if (!k) return { loaded: false, reason: 'not-loaded' };
    return {
      loaded: k.isReady(),
      loading: k.isLoading(),
      progress: k.getProgress ? k.getProgress() : null
    };
  }

  // --- Storage probe ---
  async function probeStorage() {
    try {
      await window.DMTHStorage.save.put('__probe__', { at: Date.now() });
      await window.DMTHStorage.save.del?.('__probe__');
      return { ready: true };
    } catch (err) {
      return { ready: false, reason: String(err?.message || err) };
    }
  }

  // --- Local Stable Diffusion probe ---
  // GET /sdapi/v1/options returns { sd_model_checkpoint, unity_status: {state, model, device, error} }
  // where state is 'starting' | 'loading' | 'ready' | 'no-checkpoint'. A reachable server but
  // no checkpoint is a specific fixable state (drop a .safetensors into models/), so the probe
  // surfaces it distinctly instead of collapsing every unhappy state to 'not reachable'.
  async function probeLocalImage() {
    const c = cfg().LOCAL_IMAGE;
    try {
      const res = await fetch(c.endpoint + c.options, { method: 'GET' });
      if (!res.ok) {
        return { reachable: false, reason: `HTTP ${res.status}`, ready: false };
      }
      const data = await res.json().catch(() => ({}));
      const s = data.unity_status || {};
      return {
        reachable: true,
        state: s.state || 'unknown',
        ready: s.state === 'ready',
        model: s.model || data.sd_model_checkpoint || null,
        device: s.device || null,
        error: s.error || null
      };
    } catch (err) {
      const msg = String(err?.message || err);
      const looksLikeCors = /Failed to fetch|NetworkError|CORS/i.test(msg);
      return {
        reachable: false,
        reason: looksLikeCors ? 'not-reachable-or-cors' : msg,
        ready: false
      };
    }
  }

  // --- Local voice server (STT) probe ---
  // GET /state → { ok, stt_model_present, stt_model_dir, cuda_dirs }.
  async function probeLocalVoice() {
    const c = cfg().LOCAL_VOICE;
    try {
      const res = await fetch(c.endpoint + c.state, { method: 'GET' });
      if (!res.ok) {
        return { reachable: false, reason: `HTTP ${res.status}`, ready: false };
      }
      const data = await res.json().catch(() => ({}));
      return {
        reachable: true,
        ready: !!data.stt_model_present,
        modelDir: data.stt_model_dir || null,
        cudaDirs: data.cuda_dirs || 0
      };
    } catch (err) {
      const msg = String(err?.message || err);
      const looksLikeCors = /Failed to fetch|NetworkError|CORS/i.test(msg);
      return {
        reachable: false,
        reason: looksLikeCors ? 'not-reachable-or-cors' : msg,
        ready: false
      };
    }
  }

  // --- Full status snapshot ---
  // If `opts.skipHealthProbe` is true, we only check that the model is listed
  // by /api/tags (fast path for repeated polling). When false (default), we
  // also fire a 1-token chat probe to verify the weights blob actually loads —
  // catching the case where Storage Sense / cleanup tools deleted the multi-GB
  // blob file but left the manifest intact.
  async function fullStatus(opts = {}) {
    const [ollama, storage, localImage, localVoice] = await Promise.all([
      probeOllama(),
      probeStorage(),
      probeLocalImage(),
      probeLocalVoice()
    ]);
    const preset = cfg().OLLAMA.activeModel;
    const modelPresent = ollama.reachable && ollama.models.includes(preset);

    // Health probe — only meaningful if the manifest claims the model is there.
    // Result codes: 'ok' | 'corrupt' | 'missing' | 'unreachable' | 'unknown' | 'skipped' | 'no-probe-module'
    let activeModelHealth = 'skipped';
    let healthDiagnosis = null;
    if (modelPresent && !opts.skipHealthProbe) {
      if (window.DMTHOllamaRepair) {
        try {
          const probe = await window.DMTHOllamaRepair.probeModelHealth(preset);
          activeModelHealth = probe.status;
          healthDiagnosis = probe.diagnosis;
        } catch (err) {
          activeModelHealth = 'unknown';
          healthDiagnosis = { code: 'unknown', label: 'probe failed', detail: String(err?.message || err) };
        }
      } else {
        activeModelHealth = 'no-probe-module';
      }
    }

    const kokoro = probeKokoro();

    // "Green" for the whole stack. Local SD + voice are IMAGE/VOICE features — the game
    // is still playable without them (text+emoji fallback), so they don't gate allGreen;
    // the landing wizard still surfaces their status individually.
    const modelHealthOk = activeModelHealth === 'ok'
      || activeModelHealth === 'skipped'
      || activeModelHealth === 'no-probe-module';
    const allGreen = ollama.reachable && modelPresent && modelHealthOk && kokoro.loaded && storage.ready;

    return {
      os: detectOS(),
      ollama: {
        ...ollama,
        activeModel: preset,
        activeModelPresent: modelPresent,
        activeModelHealth,
        healthDiagnosis
      },
      kokoro,
      storage,
      localImage,
      localVoice,
      allGreen,
      checkedAt: Date.now()
    };
  }

  window.DMTHDetector = Object.freeze({
    detectOS,
    probeOllama,
    probeOllamaModelPresent,
    probeKokoro,
    probeStorage,
    probeLocalImage,
    probeLocalVoice,
    fullStatus
  });
})();
