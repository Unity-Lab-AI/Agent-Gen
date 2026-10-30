/**
 * ai-providers.js — Sensory AI Provider Manager (Brain Peripheral)
 *
 * R4 of brain-refactor-full-control — this file used to be the general
 * AI provider manager with chat() for text generation + generateImage()
 * for visual output + speak() for TTS. Text-AI (chat) is GONE. Unity
 * speaks equationally via the language cortex, no text-AI backend.
 *
 * What's left is SENSORY AI only — peripherals that translate between
 * raw sensor data and brain state:
 *
 *   - generateImage()  — image gen through a USER-CONFIGURED browser-side
 *                         backend only (custom / auto-detected / env.js)
 *   - describer        — gone (vision is equational; see below)
 *
 * None of these drive Unity's cognition. She decides WHEN to draw / speak
 * / look, and WHAT to draw / speak about (via equational slot scoring
 * over her language cortex). These peripherals just execute the output.
 *
 * ⛔ HER EYES COME HOME (2026-10-18): THERE IS NO DEFAULT REMOTE IMAGE
 * BACKEND ANY MORE. Pollinations — the "always available" fallback this
 * file used to end on — is gone from the whole project. When Unity is backed
 * by the server, her pictures are rendered THERE, on her own card, through
 * CORA's local Stable Diffusion behind one gate
 * (`server/brain-server/image-engine.js`), and arrive at the browser as
 * `{type:'image', url}`. This file now only matters for the no-server
 * in-browser fallback, and only when a user has configured their OWN
 * backend; with none configured, `generateImage()` returns null and the
 * brain says so in words instead of calling out to a remote API.
 *
 * Multi-backend image gen (browser-side, user-opted):
 *   - Users can configure a custom image endpoint via `configureImageGen(
 *     url, model, apiKey)` — for example, a self-hosted Stable Diffusion,
 *     DALL-E, or any OpenAI-compatible /v1/images/generations endpoint
 *   - `generateImage()` tries custom first, then auto-detected locals, then
 *     env.js backends — and returns null when none answers. No remote
 *     fallback; a silent successful fallback is the trap this project keeps
 *     un-shipping.
 *   - Dead-backend tracking reuses the same cooldown pattern from the
 *     old text-chat path
 */

// ── Local image generation backends that get auto-probed on boot ──
//
// Common open-source Stable Diffusion / DALL-E-alike servers that
// users typically run on localhost. The probe URL is the lightest
// request that confirms the server is up AND supports image gen.
// If the probe succeeds, the backend gets registered and used in
// priority order (custom user-configured → local detected → Pollinations).
//
// To add a new local backend, append an entry here — no other code
// changes required. The _customGenerateImage path handles OpenAI-
// compatible / raw-URL / b64_json response shapes uniformly.
const LOCAL_IMAGE_BACKENDS = [
  { name: 'Automatic1111',  url: 'http://localhost:7860',  probe: '/sdapi/v1/sd-models',       kind: 'a1111' },
  { name: 'SD.Next / Forge', url: 'http://localhost:7861', probe: '/sdapi/v1/sd-models',       kind: 'a1111' },
  { name: 'Fooocus',        url: 'http://localhost:7865',  probe: '/ping',                     kind: 'openai' },
  { name: 'ComfyUI',        url: 'http://localhost:8188',  probe: '/system_stats',             kind: 'comfy' },
  { name: 'InvokeAI',       url: 'http://localhost:9090',  probe: '/api/v1/app/version',       kind: 'invokeai' },
  { name: 'LocalAI',        url: 'http://localhost:8081',  probe: '/v1/models',                kind: 'openai' },
  // A stale `Ollama (SD)` entry on :11434 was removed here. Ollama
  // doesn't actually serve Stable Diffusion; that was a copy-paste
  // error from an earlier commit. Ollama lives on the VISION side
  // (LOCAL_VISION_BACKENDS below) where llava/moondream/bakllava
  // actually run.
];

// ── THE VLM DESCRIBER IS GONE ────────────────────────────────────────────────
//
// `LOCAL_VISION_BACKENDS` (Ollama/llava, LM Studio, LocalAI, llama.cpp, Jan),
// `VISION_MODEL_HINTS`, `autoDetectVision()`, `describeImage()` and both
// describe transports used to live in this file. They asked an external
// vision-language model "what do you see" on camera frames and fed the answer
// back in as her sight.
//
// They are deleted because the equational MIND'S EYE replaced them — that was
// the whole point of MINDSPACE MS.I2 and the no-text-AI law — and `app.js`
// already reported the replacement ("Vision-describer auto-detect removed — no
// LLM describer to probe"). Every entry point here had ZERO call sites; the
// machinery had simply been left behind after its replacement shipped.
//
// ⛔ WHAT IS DELIBERATELY UNTOUCHED, because the operator's constraint on this
// strip was that her senses must not regress:
//   • HER VOICE — `js/io/voice.js` (Piper hfc_female, plus the Pollinations
//     audio lane). ⚠ That lane POSTs to `/v1/chat/completions`, which LOOKS
//     like an LLM artifact and is NOT: Pollinations retired
//     `/v1/audio/speech`, so TTS rides the chat endpoint with
//     `modalities: ['text','audio']` and returns base64 AUDIO.
//     It is a sensory-OUTPUT executor, which the no-text-AI law explicitly
//     permits. Gutting it would take her voice.
//   • HER IMAGE GENERATION — on the SERVER now (2026-10-18): CORA's local
//     Stable Diffusion behind `server/brain-server/image-engine.js`.
//     `generateImage()` below is only the no-server fallback's optional
//     browser-side chain.
//   • HER MIND'S EYE — `js/brain/mindspace/*` and the look lane in
//     `server/brain-server/visual-memory.js`.

// Module-level shared state — survives across SensoryAIProviders
// instances. The landing page and bootUnity both construct their own
// providers, and without a shared dead-backend map each instance would
// re-discover the same 400s from scratch. These are keyed by URL so
// every instance sees the same dead state.
const SHARED_DEAD_BACKENDS = new Map(); // url → timestamp

// `SHARED_POLL_VISION_MODEL`, `SHARED_POLL_VISION_PROBE`,
// `POLL_VISION_PREFERENCE` and `resolvePollinationsVisionModel()` deleted.
// They existed only to pick which multimodal LLM (openai-large / claude /
// gemini / qwen-vision / mistral) would describe her camera frames, by probing
// `gen.pollinations.ai/v1/models` for anything with `image` in its input
// modalities. With the describer gone there is no model to choose.

export class SensoryAIProviders {
  constructor({ storage } = {}) {
    // `pollinations` used to be the first constructor arg and the default
    // backend. Removed 2026-10-18 — see the header. Any old caller that still
    // passes it is simply ignored.
    this._storage = storage;

    // Custom image generation backend — user-configurable at runtime
    // via setup modal or env.js. If set, generateImage() tries this
    // first, before local-detected backends.
    this._customImageUrl = null;
    this._customImageModel = null;
    this._customImageKey = null;

    // Auto-detected local image backends — populated by `autoDetect()`
    // at boot. Each entry: { name, url, model, kind }. generateImage()
    // iterates this list after the custom backend; nothing follows it.
    this._localImageBackends = [];

    // Auto-detected + env.js-configured VLM backends for vision
    // describer. describeImage() iterates this list before falling
    // back to nothing — the describer and its remote fallback are gone.
    this._localVisionBackends = [];

    // Consecutive failure counter on the vision describer; after 3
    // hits we pause vision for 30s to avoid hammering a dead endpoint.
    this._visionFailCount = 0;
    this._visionPausedUntil = 0;

    // Event emitter for sensory status changes. App.js subscribes
    // to render toasts. Not a full EventTarget, just a callback list
    // to keep the peripheral layer framework-free.
    this._statusListeners = [];

    this._abortController = null;
    // Shared across every SensoryAIProviders instance (landing page +
    // bootUnity construct separate instances, but a backend's dead
    // state must be global or each instance re-learns the same 400s).
    this._deadBackends = SHARED_DEAD_BACKENDS;
    this._deadCooldown = 3600000;   // 1 hour — if a backend is dead, leave it

    // User-selected preferred backends. When set, generateImage and
    // describeImage try these FIRST before walking the priority chain.
    // Stored as { name, source, model? } — name+source uniquely pick a
    // single entry from getStatus().image / .vision. Persisted to
    // localStorage via app.js; loaded back on boot.
    this._preferredImage = null;
    this._preferredVision = null;
  }

  /**
   * Pick the active backend the user wants for one of the two kinds.
   * Called from app.js when the setup modal selector changes.
   * @param {'image'|'vision'} kind
   * @param {{name: string, source: string, model?: string}|null} pref
   */
  setPreferredBackend(kind, pref) {
    if (kind === 'image') this._preferredImage = pref;
    else if (kind === 'vision') this._preferredVision = pref;
  }

  /**
   * Look up a registered backend by (source, name) so the preferred
   * chooser can route to the right _customGenerateImage / _customDescribeImage
   * path without re-implementing each backend's dispatcher.
   */
  _findBackend(kind, source, name) {
    // 'default' / 'Pollinations' used to resolve to the remote fallback.
    // There is none now; an unknown preference resolves to nothing and the
    // caller falls through the configured backends.
    if (source === 'default' || name === 'Pollinations') return null;
    const list = kind === 'image' ? this._localImageBackends : this._localVisionBackends;
    for (const b of list) {
      if (b.name === name) return b;
    }
    if (kind === 'image' && source === 'configured' && this._customImageUrl) {
      return {
        name: 'custom',
        url: this._customImageUrl,
        model: this._customImageModel,
        key: this._customImageKey,
      };
    }
    return null;
  }

  /**
   * Subscribe to sensory status events. Fires when a backend is
   * registered, marked dead, recovered, or when a request falls through
   * the priority chain. Payload: {kind, event, backend, reason}.
   */
  onStatus(fn) {
    this._statusListeners.push(fn);
    return () => {
      const i = this._statusListeners.indexOf(fn);
      if (i >= 0) this._statusListeners.splice(i, 1);
    };
  }

  _emitStatus(payload) {
    for (const fn of this._statusListeners) {
      try { fn(payload); } catch (err) { console.warn('[SensoryAI] status listener error:', err.message); }
    }
  }

  /**
   * Return a snapshot of every registered backend for the status
   * HUD. Groups by kind (image/vision) with state dots.
   */
  getStatus() {
    const imageBackends = [];
    if (this._customImageUrl) {
      imageBackends.push({
        name: 'custom',
        url: this._customImageUrl,
        source: 'configured',
        state: this._isBackendDead(this._customImageUrl) ? 'dead' : 'alive',
      });
    }
    for (const b of this._localImageBackends) {
      imageBackends.push({
        name: b.name,
        url: b.url,
        source: b.fromEnv ? 'env' : (b.detected ? 'auto' : 'config'),
        state: this._isBackendDead(b.url) ? 'dead' : 'alive',
      });
    }
    // Her OWN engine — on the server, not in this browser. Listed so the
    // inventory tells the truth about where pictures come from; it is not a
    // browser-side backend and generateImage() never calls it from here.
    imageBackends.push({ name: 'Unity (her own engine, on the server)', url: 'server', source: 'default', state: 'alive' });

    const visionBackends = [];
    for (const b of this._localVisionBackends) {
      visionBackends.push({
        name: b.name,
        url: b.url,
        model: b.model,
        source: b.fromEnv ? 'env' : (b.detected ? 'auto' : 'config'),
        state: this._isBackendDead(b.url) ? 'dead' : 'alive',
      });
    }
    // No vision backend of any kind: her sight is the equational mind's eye.

    return {
      image: imageBackends,
      vision: visionBackends,
      visionPaused: Date.now() < this._visionPausedUntil,
    };
  }

  /**
   * Auto-detect local image gen servers running on the user's machine.
   * Probes known ports for popular SD / DALL-E backends in parallel
   * with a short timeout. Any server that responds gets registered.
   *
   * Called on brain boot from app.js. Non-blocking: returns a promise
   * but the brain keeps running (server-side rendering needs none of this) while the
   * probe runs. Detected backends become available when their probe
   * resolves.
   *
   * @param {object} opts
   * @param {number} opts.timeoutMs — per-probe timeout (default 1500)
   * @returns {Promise<Array>} — list of detected backends
   */
  async autoDetect(opts = {}) {
    const timeoutMs = opts.timeoutMs ?? 1500;
    const probes = LOCAL_IMAGE_BACKENDS.map(async (backend) => {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), timeoutMs);
        const res = await fetch(backend.url + backend.probe, {
          method: 'GET',
          signal: controller.signal,
        });
        clearTimeout(timeout);
        if (res.ok) {
          console.log(`[SensoryAI] Detected local image backend: ${backend.name} at ${backend.url}`);
          return { ...backend, detected: true };
        }
      } catch {
        // Probe failed — backend not running. Silent, this is expected.
      }
      return null;
    });

    const results = await Promise.all(probes);
    this._localImageBackends = results.filter(r => r !== null);
    if (this._localImageBackends.length > 0) {
      console.log(`[SensoryAI] ${this._localImageBackends.length} local image backend(s) registered:`,
        this._localImageBackends.map(b => b.name).join(', '));
    }
    this._emitStatus({ kind: 'image', event: 'autodetect-complete', backends: this._localImageBackends });
    return this._localImageBackends;
  }

  // `autoDetectVision()` deleted. It probed localhost for Ollama /
  // LM Studio / LocalAI / llama.cpp / Jan and registered whichever
  // vision-language model was loaded, so an external LLM could act as her eyes.
  // Zero call sites; her sight is the equational mind's eye.
  //
  // Kept as a no-op rather than removed from the class, because `app.js`
  // documents this name in its boot comments and a future caller landing on
  // `undefined` would be a silent break instead of an obvious one.
  async autoDetectVision() {
    this._localVisionBackends = [];
    return this._localVisionBackends;
  }

  /**
   * Load image backend config from env.js-style config object.
   *
   * Expected shape in env.js:
   *   export const ENV_KEYS = {
   *     imageBackends: [               // NEW
   *       { url: 'http://my-server:7860', model: 'sdxl-turbo', key: 'optional' },
   *       { url: 'https://api.example.com', model: 'dalle-3', key: 'sk-...' },
   *     ],
   *   };
   *
   * Called from app.js boot after ENV_KEYS is loaded.
   */
  loadEnvConfig(envKeys) {
    if (!envKeys) return;
    const imageBackends = Array.isArray(envKeys.imageBackends) ? envKeys.imageBackends : [];
    for (const b of imageBackends) {
      if (b.url) {
        this._localImageBackends.push({
          name: b.name || `env:${b.url}`,
          url: b.url,
          model: b.model || 'default',
          kind: b.kind || 'openai',
          key: b.key || null,
          detected: false,
          fromEnv: true,
        });
      }
    }
    if (imageBackends.length > 0) {
      console.log(`[SensoryAI] Loaded ${imageBackends.length} image backend(s) from env.js`);
    }

    // env.js-configured vision backends
    const visionBackends = Array.isArray(envKeys.visionBackends) ? envKeys.visionBackends : [];
    for (const b of visionBackends) {
      if (b.url) {
        this._localVisionBackends.push({
          name: b.name || `env:${b.url}`,
          url: b.url,
          model: b.model || 'gpt-4-vision-preview',
          kind: b.kind || 'openai-vision',
          key: b.key || null,
          detected: false,
          fromEnv: true,
        });
      }
    }
    if (visionBackends.length > 0) {
      console.log(`[SensoryAI] Loaded ${visionBackends.length} vision backend(s) from env.js`);
    }
  }

  /**
   * Configure a custom image generation backend. Call this from the
   * setup modal when the user adds their own image provider.
   *
   * @param {string} url — base URL of the custom backend
   * @param {string} model — model name to request
   * @param {string} apiKey — bearer token (optional)
   */
  configureImageGen(url, model, apiKey) {
    this._customImageUrl = url;
    this._customImageModel = model;
    this._customImageKey = apiKey;
    console.log('[SensoryAI] Custom image backend configured:', url, model);
  }

  /**
   * Generate an image. Priority order:
   *   1. Custom backend (configured via configureImageGen — e.g. user's
   *      own OpenAI-compatible /v1/images/generations endpoint)
   *   2. Auto-detected local backends (Automatic1111, ComfyUI,
   *      InvokeAI, LocalAI, etc. — whichever responded to probes at boot)
   *   3. env.js-configured backends (from ENV_KEYS.imageBackends)
   *   4. — nothing. Returns null. (Pollinations used to be the always-
   *      available fallback here; removed 2026-10-18. The server renders
   *      her pictures on her own card; this browser-side chain exists only
   *      for a user who configured their own backend.)
   *
   * Each backend can fail independently — if one is down or returns an
   * error, we try the next, and when none answers the caller gets null and
   * says so in words.
   *
   * @param {string} prompt — the image description
   * @param {object} opts — { model, width, height, seed, ... }
   * @returns {string|Promise<string>} — image URL (or promise of one)
   */
  async generateImage(prompt, opts = {}) {
    // 0. User-preferred backend (if set via setPreferredBackend). This
    // wins over auto-priority so when the user picks "Stability AI" in
    // the setup modal dropdown, every image call routes there first —
    // regardless of local auto-detection. Falls through on failure.
    if (this._preferredImage) {
      const pref = this._preferredImage;
      const target = this._findBackend('image', pref.source, pref.name);
      if (target && !this._isBackendDead(target.url)) {
        const url = await this._customGenerateImage(
          target.url,
          pref.model || target.model || opts.model || 'default',
          target.key || null,
          prompt,
          opts,
        );
        if (url) return url;
      }
    }

    // 1. Custom backend first if configured and alive
    if (this._customImageUrl && !this._isBackendDead(this._customImageUrl)) {
      const url = await this._customGenerateImage(
        this._customImageUrl,
        this._customImageModel,
        this._customImageKey,
        prompt,
        opts,
      );
      if (url) return url;
    }

    // 2. + 3. Auto-detected + env.js-configured local backends
    for (const backend of this._localImageBackends) {
      if (this._isBackendDead(backend.url)) continue;
      const url = await this._customGenerateImage(
        backend.url,
        backend.model || opts.model || 'default',
        backend.key || null,
        prompt,
        opts,
      );
      if (url) return url;
    }

    // 4. Nothing answered and there is no remote fallback (removed
    // 2026-10-18). null, honestly — the caller says so in words.
    return null;
  }

  // `describeImage()` deleted. It sent a webcam frame plus the
  // prompt "Describe what you see through a webcam… 1 sentence" to a local VLM
  // or to Pollinations and returned the model's sentence AS HER SIGHT. That is
  // an external text model doing her perceiving, which is the exact thing the
  // equational mind's eye was built to replace and the no-text-AI law forbids.
  // Zero call sites — the replacement had already shipped and this was left
  // behind. Returns null so any future caller gets "no description" rather
  // than an exception.
  async describeImage() {
    return null;
  }

  /**
   * Speak via TTS. Pollinations has an audio endpoint (35+ voices).
   *
   * @param {string} text
   * @param {string} voice — voice name (default 'shimmer')
   */
  // This was a one-line passthrough to `PollinationsAI.speak()`,
  // which is deleted. It had no callers: her voice is Equation Unity One
  // (unity-voice-v2 on the server → CDF 9/7 rec → js/io/voice.js plays; the old piper lane and the banked word
  // equations). Kept as a null-returning stub so a stray caller gets "no
  // audio" instead of a TypeError on a removed method.
  async speak() {
    return null;
  }

  /**
   * Abort any in-flight sensory AI request. Called on interrupt.
   */
  abort() {
    if (this._abortController) {
      try { this._abortController.abort(); } catch {}
      this._abortController = null;
    }
  }

  // ── Private ────────────────────────────────────────────────────

  // `_customDescribeImage()` deleted. It POSTed a camera frame to
  // Ollama's `/api/chat` (llava/moondream/bakllava) or to an OpenAI-compatible
  // `/v1/chat/completions` with multimodal content, and returned the model's
  // words as her perception. Unreachable once `describeImage()` went.

  // `_pollinationsDescribeImage()` — the last Pollinations-named stub — was
  // removed 2026-10-18 along with the provider itself. (It had already been a
  // body-less `return null` since the VLM describer was deleted: an external
  // text model doing her perceiving is what the equational mind's eye
  // replaced.)

  _isBackendDead(url) {
    const deadTime = this._deadBackends.get(url);
    if (!deadTime) return false;
    if (Date.now() - deadTime > this._deadCooldown) {
      this._deadBackends.delete(url);
      return false;
    }
    return true;
  }

  _markBackendDead(url) {
    this._deadBackends.set(url, Date.now());
    console.warn(`[SensoryAI] Backend marked dead for ${this._deadCooldown / 1000}s:`, url);
    this._emitStatus({ kind: 'any', event: 'backend-dead', url, cooldownMs: this._deadCooldown });
  }

  /**
   * POST to an arbitrary image generation URL. Supports multiple
   * response shapes for wide backend compatibility:
   *   - OpenAI: { data: [{ url }] } or { data: [{ b64_json }] }
   *   - Automatic1111: { images: ['<base64>'] }
   *   - Generic: { url: '...' } or { image_url: '...' }
   *
   * Marks the backend dead on auth/payment failures so we don't hammer
   * a broken endpoint. Network errors fall through to the next one.
   */
  async _customGenerateImage(backendUrl, model, apiKey, prompt, opts = {}) {
    if (this._abortController) this._abortController.abort();
    this._abortController = new AbortController();
    const signal = opts.signal || this._abortController.signal;

    const headers = { 'Content-Type': 'application/json' };
    if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`;

    // OpenAI-compatible body (primary shape)
    const openaiBody = JSON.stringify({
      model: opts.model || model || 'default',
      prompt,
      n: 1,
      size: opts.size || `${opts.width || 768}x${opts.height || 768}`,
      ...(opts.seed != null ? { seed: opts.seed } : {}),
      ...(opts.steps != null ? { steps: opts.steps } : {}),
    });

    // Automatic1111 body shape (sdapi/v1/txt2img)
    const a1111Body = JSON.stringify({
      prompt,
      negative_prompt: opts.negativePrompt || '',
      width: opts.width || 768,
      height: opts.height || 768,
      steps: opts.steps || 20,
      cfg_scale: opts.cfgScale || 7,
      sampler_name: opts.sampler || 'Euler a',
      ...(opts.seed != null ? { seed: opts.seed } : {}),
    });

    const endpoints = [
      { path: '/v1/images/generations',  body: openaiBody },
      { path: '/images/generations',     body: openaiBody },
      { path: '/sdapi/v1/txt2img',       body: a1111Body },
      { path: '',                        body: openaiBody },
    ];

    for (const { path: epPath, body } of endpoints) {
      try {
        const res = await fetch(backendUrl + epPath, { method: 'POST', headers, body, signal });
        if (res.ok) {
          const data = await res.json().catch(() => null);
          if (!data) continue;
          // OpenAI shape: { data: [{ url }] }
          if (data.data?.[0]?.url) return data.data[0].url;
          // OpenAI b64 shape: { data: [{ b64_json }] }
          if (data.data?.[0]?.b64_json) return `data:image/png;base64,${data.data[0].b64_json}`;
          // Automatic1111 shape: { images: ['<base64>'] }
          if (Array.isArray(data.images) && data.images[0]) {
            return `data:image/png;base64,${data.images[0]}`;
          }
          // Generic URL shapes
          if (data.image_url) return data.image_url;
          if (data.url) return data.url;
        } else {
          if (res.status === 401 || res.status === 402 || res.status === 403) {
            this._markBackendDead(backendUrl);
            return null;
          }
        }
      } catch (err) {
        if (err.name === 'AbortError') throw err;
      }
    }
    return null;
  }
}

// Backward-compat export alias. The old class was `AIProviders`. Any
// import still using that name gets the new sensory-only class without
// breaking. Once the last `new AIProviders(...)` call site is migrated
// in a follow-up commit, this alias can be removed.
export { SensoryAIProviders as AIProviders };
