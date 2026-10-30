/**
 * remote-brain.js — WebSocket Client for Server-Side Brain
 *
 * Drop-in replacement for UnityBrain. Instead of running the
 * equations locally, connects to a brain server via WebSocket
 * and relays state + sensory input.
 *
 * app.js auto-detects: if server is available → RemoteBrain.
 * If not → local UnityBrain. Same API, different source.
 *
 * The visualizers, sandbox, voice, chat — all work the same.
 * They just receive state from the server instead of local math.
 *
 * NOTE: even on the server-brain path, we still instantiate a REAL
 * local InnerVoice. The server handles the N-neuron simulation but
 * the language cortex runs client-side so Unity's persona self-image
 * (docs/Ultimate Unity.txt) is loaded into the browser dictionary via
 * the same pure-equation learnSentence() pipeline used by local brain.
 */

import { InnerVoice } from './inner-voice.js';
import { VisualCortex } from './visual-cortex.js';
// RemoteBrain needs a real local NeuronCluster cortex so the brain-3d
// commentary popups (and any other local-only generate path) can run the
// brain-driven emission loop. Without this, every local generate() call
// returns '' — the slot-prior fallback was deleted, and emission now
// requires opts.cortexCluster.
import { NeuronCluster } from './cluster.js';

class EventEmitter {
  constructor() { this._listeners = {}; }
  on(event, fn) { if (!this._listeners[event]) this._listeners[event] = []; this._listeners[event].push(fn); return this; }
  off(event, fn) { const a = this._listeners[event]; if (a) this._listeners[event] = a.filter(f => f !== fn); return this; }
  emit(event, data) { const a = this._listeners[event]; if (a) for (let i = 0; i < a.length; i++) a[i](data); }
}

export class RemoteBrain extends EventEmitter {
  /**
   * @param {string} serverUrl — WebSocket URL (e.g., 'ws://localhost:7525')
   */
  constructor(serverUrl) {
    super();
    this._serverUrl = serverUrl;
    this._ws = null;
    this._connected = false;
    // Per-session id assigned by server in the `welcome` message.
    // Ephemeral — changes every reconnect.
    this._userId = null;
    // T6 2026-04-13 — stable per-user id that survives reconnects,
    // persisted in localStorage as `unity_user_id`. Generated lazily
    // on first text send so a returning user's episodes can be
    // recalled under the same id next session. This is what scopes
    // private episodic memory — the server filters the SQLite
    // episodes table by this id so Alice never gets recall hits
    // from Bob's conversation.
    this._stableUserId = null;
    this.running = false;

    // Mirror state from server
    this.state = {
      spikes: null, voltages: null, spikeCount: 0,
      clusters: {}, cortex: null, hippocampus: null,
      amygdala: null, basalGanglia: null, cerebellum: null,
      hypothalamus: null, mystery: null, oscillations: null,
      psi: 0, time: 0, reward: 0, drugState: 'sober',
      totalNeurons: 1000, motor: null, memory: null,
      innerVoice: null, connectedUsers: 0,
    };

    // Dummy subsystems for API compatibility
    this.motor = { selectedAction: 'idle', confidence: 0, isSpeaking: false, _interruptFlag: false,
      interrupt() { this._interruptFlag = true; },
      wasInterrupted() { return this._interruptFlag; },
      getState() { return { selectedAction: this.selectedAction, confidence: this.confidence }; },
    };
    this.auditoryCortex = {
      isActive() { return false; },
      setMotorOutput() {},
      clearMotorOutput() {},
      checkForInterruption() { return true; },
      getState() { return {}; },
    };
    // T4.9 — real local VisualCortex instance so the Eye widget's
    // iris actually tracks gaze from live V1 edge + salience
    // computation. Previously this was a stub plain-object with
    // static gazeX:0.5/gazeY:0.5 which is why the iris sat frozen
    // on the user's eyes. The server still runs its own vision
    // processing in parallel (for commentary generation), but the
    // Eye widget on the client reads from this local instance.
    this.visualCortex = new VisualCortex();
    this.sensory = { _cameraStream: null };
    // REAL local InnerVoice so loadPersona works and the memory tab shows
    // dictionary / bigram / usage-type stats from the actual persona file.
    // app.js fetches docs/Ultimate Unity.txt and calls loadPersona() on this.
    this.innerVoice = new InnerVoice();

    // Local cortex cluster purely for the language emission
    // loop. The actual brain sim runs server-side and reaches us via
    // websocket state messages. This cluster is for local-only
    // languageCortex.generate calls (brain-3d commentary popups,
    // /think debug, welcome speech).
    // Browser-side fallback cortex at 1500 neurons (smaller than the
    // server's 2000 because the browser is more resource-constrained).
    // 1500 neurons × 15% connectivity = ~340K synapses, deep enough
    // for measurable Hebbian basins. Hebbian-trained on persona corpus
    // when trainPersonaHebbian is called below. Exposed via
    // this.clusters.cortex. (Server tier runs the full EMBED_DIM=300
    // GloVe pipeline; the browser fallback uses a smaller groupSize so
    // the same embedding dim tiles into fewer neurons.)
    const langCortexSize = 1500;
    this._localCortex = new NeuronCluster('cortex', langCortexSize, {
      tonicDrive: 14,
      noiseAmplitude: 7,
      connectivity: 0.15,
      excitatoryRatio: 0.85,
      learningRate: 0.002,
    });
    this._langStart = Math.floor(langCortexSize / 2);
    this.clusters = { cortex: this._localCortex };

    this._connect();
  }

  /**
   * Hebbian-train the local cortex cluster on persona corpus
   * so the local generate() path (commentary popups etc) reads from a
   * Unity-voice-shaped attractor landscape instead of random noise.
   * Delegates through the local InnerVoice → LanguageCortex →
   * cluster.learnSentenceHebbian chain. Idempotent — only runs once
   * per RemoteBrain instance per persona text.
   */
  trainPersonaHebbian(text) {
    if (!text || this._hebbianTrained) return;
    if (!this.innerVoice || !this._localCortex) return;
    try {
      // Pass langStart + stronger lr + injectStrength so the
      // Hebbian pass actually shapes the bigger 1500-neuron cluster.
      this.innerVoice.trainPersonaHebbian(this._localCortex, text, {
        lr: 0.012,
        langStart: this._langStart,
        injectStrength: 0.8,
      });
      this._hebbianTrained = true;
    } catch (err) {
      console.warn('[RemoteBrain] persona Hebbian training failed:', err.message);
    }
  }

  _connect() {
    try {
      this._ws = new WebSocket(this._serverUrl);

      this._ws.onopen = () => {
        this._connected = true;
        console.log(`[RemoteBrain] Connected to ${this._serverUrl}`);
      };

      this._ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          this._handleMessage(msg);
        } catch {}
      };

      this._ws.onclose = () => {
        this._connected = false;
        console.log('[RemoteBrain] Disconnected — reconnecting in 3s...');
        setTimeout(() => this._connect(), 3000);
      };

      this._ws.onerror = () => {
        // Will trigger onclose
      };
    } catch {
      console.warn('[RemoteBrain] Connection failed');
      setTimeout(() => this._connect(), 5000);
    }
  }

  _handleMessage(msg) {
    switch (msg.type) {
      case 'welcome':
        this._userId = msg.id;
        // DEPLOY VERSION HANDSHAKE — the CHAT page now self-reloads on a build
        // change, exactly like donor tabs. A long-lived chat tab used to
        // survive every deploy running OLD bundle code — which is how the
        // in-browser voice synth (deleted server-lane-side 2026-07-17) kept
        // resurrecting from stale tabs and killing same-machine donors when
        // she spoke. The WS reconnects after every SAVESTART; a changed
        // buildStamp on the fresh welcome = this tab's code is stale → reload
        // once and run current.
        if (msg.buildStamp) {
          if (this._buildStamp && this._buildStamp !== msg.buildStamp && typeof location !== 'undefined') {
            console.warn('[RemoteBrain] deploy detected (buildStamp changed) — reloading to run current code.');
            try { location.reload(); return; } catch { /* keep going on old code if reload is blocked */ }
          }
          this._buildStamp = msg.buildStamp;
        }
        if (msg.state) this._applyState(msg.state);
        console.log(`[RemoteBrain] Welcome — user ${this._userId}, ${msg.state?.connectedUsers ?? '?'} users online`);
        // Browser-side WS roundtrip smoke test. Verifies
        // `lookupDefinition` works end-to-end (browser → WS →
        // server's definition-service → API → response → resolver).
        // Catches off-by-one in field names + dead handlers.
        if (!this._wsRoundtripTested) {
          this._wsRoundtripTested = true;
          this.lookupDefinition('test', { timeoutMs: 8000 }).then(def => {
            if (def && typeof def === 'string' && def.length > 0) {
              console.log(`[RemoteBrain] dictionary WS roundtrip ready — "test" → "${def.slice(0, 50)}${def.length > 50 ? '...' : ''}"`);
            } else {
              console.warn(`[RemoteBrain] dictionary WS roundtrip check failed — got ${def === null ? 'null' : typeof def}.`);
            }
          }).catch(err => {
            console.warn(`[RemoteBrain] dictionary WS roundtrip check threw: ${err?.message || err}`);
          });
        }
        break;

      case 'state':
        this._applyState(msg.state);
        this.emit('stateUpdate', this.state);
        break;

      case 'response':
        this.emit('response', { text: msg.text, action: msg.action });
        // ONE PROCESS voice lane — the donor connection used to drop every
        // single time she spoke, and the fix was one unified system: this end
        // NO LONGER synthesizes the reply. Her process does — the server sends
        // a follow-up 'voice' message carrying the field-A rec (donor or box
        // synthesized); the handler below just reconstructs + plays. The old
        // in-browser synth here was the donor-killer on shared-card machines
        // (a stale cached worker could still grab WebGPU) — deleted, not
        // fallback-chained.
        break;

      case 'voice':
        // Her reply's voice, synthesized by HER process — reconstruct + play.
        // No worker, no model download, no GPU touch on this end, ever.
        if (msg.rec && this._voice && !this._isSpeaking) {
          this._isSpeaking = true;
          try { this._voice.stopSpeaking(); } catch { /* nf */ }
          Promise.resolve(this._voice.playRec(msg.rec))
            .catch(() => { /* silent — playback issues log inside VoiceIO */ })
            .finally(() => { this._isSpeaking = false; });
        }
        break;

      case 'silent':
        // Server dropped the response on purpose — pre-K Unity's motor
        // region can't commit a stable letter sequence, or the language
        // subsystem isn't booted, or the motor attractor couldn't settle
        // on this input. Forward the reason + detail + minGrade to the
        // chat panel so it renders a ghost bubble instead of ghosting
        // the user. Shape: { reason, detail, minGrade }.
        this.emit('silent', {
          reason: msg.reason || 'unknown',
          detail: msg.detail || '',
          minGrade: msg.minGrade || null,
        });
        break;

      case 'build':
        // Server wants to inject a component
        this.emit('build', msg.component);
        break;

      case 'speak':
        this.emit('speak', msg.text);
        break;

      case 'image':
        // IMG-GEN — the server emits a PROMPT for the client to render (it has no
        // image backend), or occasionally a finished url. Pass both through; the
        // app handler turns a prompt into an actual image via Pollinations. (Was
        // `msg.url` only — which silently dropped every server image prompt.)
        this.emit('image', { url: msg.url || null, prompt: msg.prompt || null });
        break;

      case 'definitionResult': {
        // browser-side definition lookup response from
        // server's WS handler. Resolve the awaiting promise stored
        // in this._pendingDefLookups (keyed by reqId).
        if (this._pendingDefLookups && this._pendingDefLookups.has(msg.reqId)) {
          const resolver = this._pendingDefLookups.get(msg.reqId);
          this._pendingDefLookups.delete(msg.reqId);
          if (resolver) resolver(msg.definition || null);
        }
        break;
      }

      case 'prefetchDone': {
        if (this._pendingDefPrefetch && this._pendingDefPrefetch.has(msg.reqId)) {
          const resolver = this._pendingDefPrefetch.get(msg.reqId);
          this._pendingDefPrefetch.delete(msg.reqId);
          if (resolver) resolver({ prefetched: msg.prefetched, alreadyCached: msg.alreadyCached });
        }
        break;
      }

      case 'innerThought':
        // server-side inner voice broadcast.
        // Operator (2026-05-06): "the pop ups in her Brain fire with
        // her real actual knowldedge to that point as her real internal
        // voice in the moment" + "the pop ups are suppose to bue unitys
        // internal monolog and thoughts and self talking and contiplation"
        // + "not hard coded fallbacks Unity just speaks her mind" +
        // "might need a activator and 'Sandbox' like notice". Server
        // injects a sandbox-notice contemplation seed (learning context /
        // mood / recent memory / identity anchor) and runs the SAME
        // generateAsync chat-emission path against the live cortex.
        // What she says comes entirely from her trained mind.
        this.emit('innerThought', {
          word: msg.word || '',
          sentence: msg.sentence || msg.word || '',
          seed: msg.seed || 'baseline',
          seedLabel: msg.seedLabel || '',
          ts: msg.ts || Date.now(),
          capability: msg.capability || null,
        });
        break;

      case 'error':
        console.warn('[RemoteBrain] Server error:', msg.message);
        break;
    }
  }

  _applyState(serverState) {
    if (!serverState) return;
    // Map server state to local state format
    this.state.psi = serverState.psi ?? this.state.psi;
    this.state.time = serverState.time ?? this.state.time;
    this.state.reward = serverState.reward ?? this.state.reward;
    this.state.drugState = serverState.drugState ?? this.state.drugState;
    this.state.spikeCount = serverState.totalSpikes ?? this.state.spikeCount;
    this.state.totalNeurons = serverState.totalNeurons ?? this.state.totalNeurons;
    if (serverState.scale) this.state.scale = serverState.scale;
    if (serverState.totalSpikes !== undefined) this.state.totalSpikes = serverState.totalSpikes;
    if (serverState.time !== undefined) this.state.time = serverState.time;
    if (serverState.frameCount !== undefined) this.state.frameCount = serverState.frameCount;
    this.state.connectedUsers = serverState.connectedUsers ?? 0;

    if (serverState.clusters) this.state.clusters = serverState.clusters;
    if (serverState.motor) {
      this.state.motor = serverState.motor;
      this.motor.selectedAction = serverState.motor.selectedAction;
      this.motor.confidence = serverState.motor.confidence;
    }

    // Derive amygdala from server state
    this.state.amygdala = {
      arousal: serverState.arousal ?? 0.5,
      valence: serverState.valence ?? 0,
      fear: serverState.fear ?? 0,
    };

    this.state.oscillations = {
      coherence: serverState.coherence ?? 0.5,
      bandPower: serverState.bandPower || {},
    };

    if (serverState.innerVoice) this.state.innerVoice = serverState.innerVoice;
    if (serverState.memory) this.state.memory = serverState.memory;
    if (serverState.sharedMood) this.state.sharedMood = serverState.sharedMood;
    if (serverState.perf) this.state.perf = serverState.perf;
    if (serverState.growth) this.state.growth = serverState.growth;
    // Forward grade state (per-subject map + minGrade) so the HUD
    // can render Unity's lowest passing grade as a persistent visible element
    // instead of forcing the user to type /curriculum status.
    // `canSpeak` is GONE — it was `minGrade !== 'pre-K'` and nothing more, and
    // its name asserted a speech capability the value never measured. The
    // boolean survives under the name of what it computes; the question it was
    // mistaken for is answered by `voice`, which carries real emission
    // evidence (word_motor everFired, matrixDrivenPct, last rejection + age).
    if (serverState.grades) this.state.grades = serverState.grades;
    if (serverState.minGrade) this.state.minGrade = serverState.minGrade;
    if (typeof serverState.minGradeCleared === 'boolean') this.state.minGradeCleared = serverState.minGradeCleared;
    if (serverState.voice) this.state.voice = serverState.voice;

    // Synthesize spike array for 3D visualization.
    // Server runs millions of neurons — render shows proportional sample.
    // AMPLIFY firing rates for visual impact (2% biological rate → 15-30% visual rate).
    if (serverState.clusters) {
      // Dynamic ratios from ACTUAL server cluster sizes — not hardcoded
      const names = ['cortex', 'hippocampus', 'amygdala', 'basalGanglia', 'cerebellum', 'hypothalamus', 'mystery'];
      const totalSize = names.reduce((s, n) => s + (serverState.clusters[n]?.size || 0), 0) || 1;
      const ratios = names.map(n => (serverState.clusters[n]?.size || 0) / totalSize);
      const renderTotal = this.state.spikes?.length || 20000;
      const spikes = new Uint8Array(renderTotal);
      let offset = 0;

      for (let c = 0; c < names.length; c++) {
        const clusterRenderSize = Math.round(ratios[c] * renderTotal);
        const cluster = serverState.clusters[names[c]];

        // Firing rate normalized — all clusters render at equal visual intensity
        const rawRate = cluster ? (cluster.spikeCount || 0) / (cluster.size || 1) : 0;
        const emaRate = cluster ? (cluster.firingRate || 0) / (cluster.size || 1) : 0;
        // Scale multiplier by cluster size ratio so big clusters aren't dimmer
        const sizeRatio = (cluster?.size || 1) / (totalSize / names.length); // >1 for big clusters
        const amplify = 15 + sizeRatio * 5; // bigger cluster → bigger multiplier
        const visualRate = Math.min(0.5, rawRate * amplify + emaRate * amplify * 0.7);

        for (let i = 0; i < clusterRenderSize && offset + i < renderTotal; i++) {
          spikes[offset + i] = Math.random() < visualRate ? 1 : 0;
        }
        offset += clusterRenderSize;
      }
      this.state.spikes = spikes;
    }
  }

  // ── Public API (same as UnityBrain) ──────────────────────────

  getState() { return this.state; }

  start() { this.running = true; }
  stop() { this.running = false; }

  receiveSensoryInput(type, data) {
    if (!this._connected || !this._ws) return;
    this._ws.send(JSON.stringify({ type, [type]: data }));
  }

  /**
   *  — Browser-side dictionary definition lookup via WS
   * roundtrip. Sends 'lookupDefinition' WS message to server (handler
   * in brain-server.js calls definitionService.getDefinition); awaits
   * 'definitionResult' response. Returns definition string or null.
   *
   * @param {string} word
   * @param {{timeoutMs?: number}} [opts]
   * @returns {Promise<string|null>}
   */
  async lookupDefinition(word, opts = {}) {
    if (!this._connected || !this._ws || !word) return null;
    const reqId = `def-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
    if (!this._pendingDefLookups) this._pendingDefLookups = new Map();
    const timeoutMs = opts.timeoutMs ?? 5000;
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        this._pendingDefLookups.delete(reqId);
        resolve(null);
      }, timeoutMs);
      this._pendingDefLookups.set(reqId, (def) => {
        clearTimeout(timer);
        resolve(def);
      });
      try {
        this._ws.send(JSON.stringify({ type: 'lookupDefinition', reqId, word }));
      } catch {
        this._pendingDefLookups.delete(reqId);
        clearTimeout(timer);
        resolve(null);
      }
    });
  }

  lookupDefinitionSync(/* word */) {
    // Browser-side has no local cache (server holds it); sync read returns null.
    // Callers should use the async lookupDefinition.
    return null;
  }

  async prefetchDefinitions(words, opts = {}) {
    if (!this._connected || !this._ws || !Array.isArray(words) || words.length === 0) {
      return { prefetched: 0, alreadyCached: 0 };
    }
    const reqId = `pf-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
    if (!this._pendingDefPrefetch) this._pendingDefPrefetch = new Map();
    const timeoutMs = opts.timeoutMs ?? 60000;
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        this._pendingDefPrefetch.delete(reqId);
        resolve({ prefetched: 0, alreadyCached: 0 });
      }, timeoutMs);
      this._pendingDefPrefetch.set(reqId, (stats) => {
        clearTimeout(timer);
        resolve(stats);
      });
      try {
        this._ws.send(JSON.stringify({ type: 'prefetchDefinitions', reqId, words }));
      } catch {
        this._pendingDefPrefetch.delete(reqId);
        clearTimeout(timer);
        resolve({ prefetched: 0, alreadyCached: 0 });
      }
    });
  }

  async processAndRespond(text) {
    if (!this._connected || !this._ws) {
      return { text: 'Brain server disconnected.', action: 'respond_text' };
    }

    // T6 2026-04-13 — lazy-init the stable userId on first text send.
    // Persisted in localStorage so returning users keep the same id
    // across sessions and can recall their own episodes. Server uses
    // this to filter SQLite episode storage + recall by user, so one
    // user never gets recall hits from another user's past text.
    // crypto.randomUUID() is supported in all modern browsers; guard
    // the ls access for SSR / worker contexts just in case.
    if (!this._stableUserId) {
      try {
        if (typeof localStorage !== 'undefined') {
          let saved = localStorage.getItem('unity_user_id');
          if (!saved) {
            saved = (typeof crypto !== 'undefined' && crypto.randomUUID)
              ? crypto.randomUUID()
              : 'user_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
            localStorage.setItem('unity_user_id', saved);
          }
          this._stableUserId = saved;
        }
      } catch { /* localStorage unavailable — fall through with null */ }
    }

    // Stamp the last-text time so the visual cortex RAF
    // driver's setAttentionState call sees a small secondsSinceInput
    // and locks attention toward the user's face for the next ~10s.
    this._lastTextSendTime = Date.now();

    this._ws.send(JSON.stringify({
      type: 'text',
      text,
      userId: this._stableUserId || undefined,
    }));

    // Attach the handler BEFORE awaiting the Promise resolve
    // so a fast server response that races the ws.send can't fire
    // its 'response' event before the listener is registered.
    return new Promise((resolve) => {
      let resolved = false;
      const handler = ({ text, action }) => {
        if (resolved) return;
        resolved = true;
        clearTimeout(timeout);
        this.off('response', handler);
        resolve({ text, action });
      };
      this.on('response', handler);
      const timeout = setTimeout(() => {
        if (resolved) return;
        resolved = true;
        this.off('response', handler);
        resolve({ text: 'Brain is thinking...', action: 'respond_text' });
      }, 30000);
    });
  }

  connectLanguage() {} // handled by server
  connectVoice(v) { this._voice = v; }
  connectImageGen() {} // handled by server
  connectMicrophone() {}

  /**
   * T4.9 — real camera wiring so the local VisualCortex processes
   * frames and drives the Eye widget's iris tracking. Mirrors
   * UnityBrain.connectCamera(): creates a video element sourced
   * from the MediaStream, waits a tick for the first frame, then
   * hands the element to VisualCortex.init() which starts the
   * 60×45 V1 edge + saccade + salience loop.
   */
  /**
   * The terminal stop the old loop never had.
   *
   * ⛔ It is deliberately NOT called on a transient. The loop parks and re-arms
   * for anything temporary; this is only for a real teardown, and its one real
   * caller is `connectCamera` re-entering — without it a second call would
   * stack a second RAF loop driving the same cortex forever.
   */
  stopVisionLoop() {
    this._visionLoopStopped = true;
    try { if (this._visionRafId) cancelAnimationFrame(this._visionRafId); } catch { /* not in a DOM */ }
    try { if (this._visionParkTimer) clearTimeout(this._visionParkTimer); } catch { /* nf */ }
    this._visionRafId = null;
    this._visionParkTimer = null;
  }

  connectCamera(stream, videoElement) {
    if (!stream) return;
    // ⚠ Re-entering must not leave the previous driver running. `_visionRafId`
    // was assigned in two places and passed to `cancelAnimationFrame` in NONE,
    // so a second connect would have stacked loops silently.
    this.stopVisionLoop();
    try {
      let vid = videoElement;
      if (!vid) {
        vid = document.createElement('video');
        vid.autoplay = true;
        vid.playsInline = true;
        vid.muted = true;
        vid.srcObject = stream;
        vid.style.display = 'none';
        document.body.appendChild(vid);
      }
      this.sensory._cameraStream = stream;
      this.sensory._videoElement = vid;
      // Wait for the first frame before initializing visual cortex —
      // same 500ms delay the local-brain path uses.
      setTimeout(() => {
        if (this.visualCortex && typeof this.visualCortex.init === 'function') {
          this.visualCortex.init(vid);
          console.log('[RemoteBrain] Visual cortex connected to camera');

          // Self-driving processFrame RAF loop.

          // RemoteBrain has no tick loop (the main brain runs server-
          // side), so nothing was calling visualCortex.processFrame()
          // on the client side. VisualCortex.init() starts the video
          // element but the V1 edge + salience + saccade compute only
          // runs when processFrame() is called externally. Without a
          // driver, gazeX/gazeY stayed at their default 0.5/0.5 and
          // the Eye widget's iris rendered frozen in the center.

          // Fix: kick off a requestAnimationFrame loop that calls
          // processFrame() every frame as long as the visual cortex
          // is active. The loop self-cancels when the cortex goes
          // inactive (disconnect or destroy). ~60 Hz frame rate is
          // overkill — visualCortex.processFrame internally gates
          // real compute work via its own describeInterval and V1
          // update cadence — but RAF is the simplest way to stay in
          // sync with the display's vsync.
          // Drive setAttentionState from live RemoteBrain
          // state so the visual cortex's top-down attention lock
          // engages when the user is actively talking to Unity.
          // Without this, _attentionLock stays at 0 and the face-
          // tracking saccade's center prior stays weak, so the iris
          // wanders to whatever high-salience background edge wins
          // the raw competition. setAttentionState only needs two
          // numbers (current arousal, seconds since last input),
          // both of which we can read from local state + lastTextTime.
          // ⛔⛔ STOPPING AND PAUSING WERE THE SAME CODE PATH, AND
          // THAT IS WHY THE FOCUS TRACKER DIED. The previous loop read:
          //
          //     if (!this.visualCortex || !this.visualCortex.isActive()) return;
          //
          // — a bare `return` with NO reschedule, and `_visionRafId` is never
          // passed to `cancelAnimationFrame` anywhere in the codebase. So that
          // guard was simultaneously the only way to stop the loop and the only
          // way to break it: one frame in which the cortex was not active and
          // the eye stopped being driven FOREVER, with nothing anywhere able to
          // restart it. Reported: the focus tracker no longer moved to follow
          // what she sees — a regression that had killed it outright.
          //
          // ⭐ The two are now separate concerns:
          //   • STOP  — an explicit flag set by teardown. Terminal, on purpose.
          //   • PAUSE — the cortex is momentarily not active (camera warming,
          //     a permission re-prompt, a backgrounded tab). The loop PARKS on
          //     a slow timer and re-arms itself, because every one of those is
          //     temporary and none of them should be fatal.
          //
          // ⚠ The park uses a 500ms timer rather than re-arming RAF at 60Hz:
          // a backgrounded tab throttles RAF anyway, and spinning the frame
          // callback against a dead camera is the cost this loop exists to
          // avoid paying.
          this._visionLoopStopped = false;
          const PARK_MS = 500;
          const tick = () => {
            if (this._visionLoopStopped) return;           // terminal, and ONLY this
            const vc = this.visualCortex;
            if (!vc || typeof vc.isActive !== 'function' || !vc.isActive()) {
              this._visionParked = (this._visionParked | 0) + 1;
              this._visionParkTimer = setTimeout(() => {
                if (this._visionLoopStopped) return;
                this._visionRafId = requestAnimationFrame(tick);
              }, PARK_MS);
              return;
            }
            try {
              const arousal = this.state?.amygdala?.arousal ?? 0.5;
              const now = Date.now();
              const lastInput = this._lastTextSendTime || 0;
              const secondsSinceInput = lastInput > 0 ? (now - lastInput) / 1000 : 9999;
              if (typeof vc.setAttentionState === 'function') {
                vc.setAttentionState({ arousal, secondsSinceInput });
              }
              vc.processFrame();
              // ⭐ PUBLISH THE GAZE UPWARD, because two detectors
              // have been reading it out of SERVER state while the visual cortex
              // runs HERE, in the browser. `motionDetected` and `gazeShift` in
              // `js/ui/brain-event-detectors.js` could therefore never fire on
              // the RemoteBrain path, and `brain-3d.js` already said so in a
              // comment rather than anyone fixing it.
              //
              // ⚠ THROTTLED HARD AND ON PURPOSE. This rides the same 60 Hz loop
              // that drives perception; sending every frame would put 60 msg/s
              // of telemetry on the socket the walk teaches over. A quarter-
              // second is far finer than either detector's resolution — one
              // needs a motion SPIKE, the other a gazeTarget CHANGE — so the
              // cheaper cadence loses nothing they can measure.
              const _gnow = Date.now();
              if (_gnow - (this._gazeSentAt || 0) > 250) {
                this._gazeSentAt = _gnow;
                const g = typeof vc.getState === 'function' ? vc.getState() : null;
                if (g) this.receiveSensoryInput('gaze', {
                  gazeX: g.gazeX, gazeY: g.gazeY, gazeTarget: g.gazeTarget,
                  motionEnergy: g.motionEnergy, maxSalience: g.maxSalience,
                  frames: g.frames, framesRefused: g.framesRefused,
                });
              }
            } catch (err) {
              // ⚠ Counted, not just warned. A throw every frame used to freeze
              // the widget while filling the console, and nothing summarised it.
              this._visionErrs = (this._visionErrs | 0) + 1;
              if (this._visionErrs === 1 || this._visionErrs % 300 === 0) {
                console.warn(`[RemoteBrain] visualCortex.processFrame threw (${this._visionErrs}x):`, err?.message || err);
              }
            }
            this._visionRafId = requestAnimationFrame(tick);
          };
          this._visionRafId = requestAnimationFrame(tick);
        }
      }, 500);
    } catch (err) {
      console.warn('[RemoteBrain] connectCamera failed:', err.message);
    }
  }

  giveReward(amount) {
    if (this._connected && this._ws) {
      this._ws.send(JSON.stringify({ type: 'reward', amount }));
    }
  }

  saveBrainState() {} // server handles persistence
  loadSavedState() { return false; }
  exportBrain() { return null; }

  isConnected() { return this._connected; }
  isRemote() { return true; }
}

/**
 * Auto-detect whether a brain server is running.
 * Returns the RemoteBrain if connected, null if not.
 *
 * @param {string} url — WebSocket URL to probe
 * @param {number} timeout — ms to wait
 * @returns {Promise<RemoteBrain|null>}
 */
// PA.4.7 — bounded WebSocket reachability probe. Resolves true if the socket
// opens within timeoutMs, false on error/close/timeout. Used to decide whether
// a DEPLOYED origin has a real brain backend (operator authed at /admin/ws) vs
// is an unauthed visitor / pure static-demo deploy (→ local fallback brain).
function _probeWs(url, timeoutMs) {
  return new Promise((resolve) => {
    let done = false;
    let ws;
    const finish = (ok) => { if (done) return; done = true; try { ws && ws.close(); } catch { /* ignore */ } resolve(ok); };
    try { ws = new WebSocket(url); } catch { resolve(false); return; }
    const t = setTimeout(() => finish(false), timeoutMs);
    ws.onopen = () => { clearTimeout(t); finish(true); };
    ws.onerror = () => { clearTimeout(t); finish(false); };
    ws.onclose = () => { clearTimeout(t); finish(false); };
  });
}

export async function detectRemoteBrain(url = 'ws://localhost:7525') {
  // Default probe URL moved off port 8080 (which collides with
  // llama.cpp, LocalAI, and every other service that claims 8080).
  // Unity's brain-server now binds to 7525 by default.

  // Hostname gate: only consider the local server when the page is actually
  // served from localhost/127.0.0.1/file://. On GitHub Pages (or any other
  // public origin) there is no server — return null, let app.js fall
  // through to the local fallback UnityBrain.

  // Without this gate, visiting the Pages URL from a dev box with brain-server
  // running would connect to ws://localhost:7525 (Chrome allows loopback from
  // https secure-context) and the Pages UI would display the dev box's
  // auto-scaled neuron count (which grows with available VRAM). It also prevents
  // every stranger's browser from silently poking their own loopback on page load.
  // ── CONFIGURED BRAIN ORIGIN — the third mode (2026-10-18) ────────────────
  //
  // The two branches below assume the brain is either on loopback or behind
  // THE SAME HOSTNAME as the page. Both were true on the box, where nginx
  // served the site and reverse-proxied the backend. Neither is true now:
  // GitHub Pages serves the site and the brain runs on the operator's PC
  // behind a Cloudflare Tunnel — a different origin. Without this, a Pages
  // visitor resolves `wss://<user>.github.io/ws`, finds nothing, and lands on
  // the 6,700-neuron fallback, which is exactly what the comment above warns
  // about and exactly what we do NOT want a visitor to meet.
  //
  // ⭐ ADDITIVE BY CONSTRUCTION: `js/brain-origin.js` sets this global only
  // when an origin is configured. Unset -> this block is skipped entirely and
  // the original two branches run unchanged, branch for branch.
  const _cfgOrigin = (typeof globalThis !== 'undefined' && globalThis.UNITY_BRAIN_ORIGIN) || '';
  if (_cfgOrigin) {
    const wsBase = _cfgOrigin.replace(/^http/, 'ws');
    // Same backend-exists gate as the same-origin path, aimed at the
    // configured host. ⚠ /health must be reachable through the tunnel for
    // this to mean anything — see deploy/cloudflared-unity-brain.yml, which
    // exposes it for precisely this reason.
    let alive = false;
    try {
      const c = new AbortController();
      const t = setTimeout(() => c.abort(), 4000);
      const r = await fetch(`${_cfgOrigin}/health`, { signal: c.signal });
      clearTimeout(t);
      alive = !!(r && r.ok);
    } catch { alive = false; }
    if (!alive) {
      console.warn(`[RemoteBrain] configured brain origin ${_cfgOrigin} did not answer /health — `
        + 'falling through to the normal resolution so a dead override cannot strand the page.');
    } else {
      const url2 = `${wsBase}/ws`;
      console.log(`[RemoteBrain] using configured brain origin — ${url2}`);
      if (await _probeWs(url2, 8000)) return new RemoteBrain(url2);
      console.warn(`[RemoteBrain] ${_cfgOrigin} answered /health but ${url2} would not open — `
        + 'check the tunnel forwards /ws, not just the JSON routes.');
      return null;
    }
  }

  if (typeof location !== 'undefined') {
    const host = location.hostname;
    const isLocal =
      host === 'localhost' ||
      host === '127.0.0.1' ||
      host === '[::1]' ||
      host === '' ||
      location.protocol === 'file:';
    if (!isLocal) {
      // DEPLOYED origin. The brain backend exposes a PUBLIC observe/chat lane
      // at wss://<host>/ws (nginx reverse-proxies to brain-server — the SAME
      // lane compute.html donors connect on). Connect there so EVERY visitor,
      // not just an authed operator, attaches to the live server brain and sees
      // its real neuron count — which auto-scales up AND down with the pooled
      // donor GPU compute — instead of dropping to the tiny 6700-neuron local
      // browser fallback. The server's periodic `state` broadcast goes to all
      // connected clients (no admin gate), so a public observer gets the live
      // totalNeurons/scale every tick. Admin CONTROL actions (resize, server
      // console, auto-scale sliders) stay on the SEPARATE Forgejo-authed
      // /admin/ lane driven by the dashboard — only observation + chat are
      // public by design. Probe first: if /ws doesn't open at all (a pure
      // static-demo deploy with NO backend) → null → app.js local fallback.
      const wsProto = location.protocol === 'https:' ? 'wss' : 'ws';
      const publicUrl = `${wsProto}://${location.host}/ws`;
      // RESILIENT PROBE — retry across ~25s before falling back. A single 4s
      // probe was too fragile: during a heavy teach/probe burst the server's
      // WS-accept lags past 4s (the event loop is mid-synchronous-work), so the
      // probe timed out and the page dropped to the tiny 6700-neuron LOCAL
      // fallback brain EVEN THOUGH the backend is healthy and /ws returns 101.
      // That's why the talk page showed "7k real neurons" while the dashboard
      // (admin lane) saw the real 306M. Retrying across several attempts catches
      // the gap when the loop frees; a TRUE backend-less static mirror still
      // fails every attempt → graceful local fallback. Once RemoteBrain is
      // constructed it owns its own retry-forever reconnect, so a later burst
      // never flips the page back to the fallback — it just reconnects.
      // BACKEND-EXISTS GATE — /health is answered outside the brain's main
      // loop and responds even mid-pin. If it responds, there IS a live brain
      // behind this origin and showing the 6,700-neuron simulated fallback
      // would be a lie — so the probe retries for MINUTES (live teach pins
      // at 306M have run 25-460s; the old ~36s budget gave up inside them and
      // every visitor landing mid-pin got the fake brain). Only a true static
      // mirror — health dead too — falls back to the local demo.
      let _backendExists = false;
      try {
        const _hc = new AbortController();
        const _ht = setTimeout(() => _hc.abort(), 4000);
        const _h = await fetch('/health', { signal: _hc.signal });
        clearTimeout(_ht);
        _backendExists = !!(_h && _h.ok);
      } catch (e) { /* no health endpoint — likely a static mirror */ }
      const PROBE_ATTEMPTS = 5;
      const PROBE_TIMEOUT_MS = 6000;
      const PROBE_GAP_MS = 1500;
      const _maxAttempts = _backendExists ? 60 : PROBE_ATTEMPTS;   // ~6min patient vs quick static-mirror check
      for (let attempt = 1; attempt <= _maxAttempts; attempt++) {
        const reachable = await _probeWs(publicUrl, PROBE_TIMEOUT_MS);
        if (reachable) {
          console.log(`[RemoteBrain] Deployed origin — public brain lane reachable on attempt ${attempt}/${PROBE_ATTEMPTS}; constructing RemoteBrain ws=${publicUrl}`);
          return new RemoteBrain(publicUrl);
        }
        if (attempt < _maxAttempts) {
          console.log(`[RemoteBrain] Deployed origin — /ws probe ${attempt}/${_maxAttempts} timed out (server busy mid-teach?), server busy mid-teach — a LIVE brain exists (health OK), retrying rather than faking a simulated one...`);
          await new Promise(r => setTimeout(r, PROBE_GAP_MS));
        }
      }
      console.log(`[RemoteBrain] Deployed origin — public brain lane unreachable after ${_maxAttempts} attempts at ${publicUrl} (no backend / static-only mirror); using local fallback brain.`);
      return null;
    }
  }
  // operator (2026-05-06): "if i refresh the 3D brain html
  // page it only reloads with 7k nurons like its deployed on github".

  // Root cause: prior implementation opened a probe WebSocket, waited
  // up to 10s for `onopen`, closed it, THEN constructed `RemoteBrain`
  // which opens a SECOND WebSocket. That probe-then-reconnect dance
  // had failure modes on page refresh (rapid open/close throttled by
  // Chrome, server busy with compute_batch dispatch during heavy
  // curriculum phase, race between probe close and brain-server
  // per-client tracking). When the probe failed/timed out, the page
  // fell back to the 6700-neuron browser-side `UnityBrain` (the
  // `TOTAL_NEURONS = 6700` default in engine.js) — exactly the GitHub-
  // Pages-deployed behavior, even though the local brain-server WAS
  // running.

  // Fix: SKIP THE PROBE ENTIRELY when on a local origin. Construct
  // `RemoteBrain` directly. Its internal `_connect()` already handles
  // retry-forever-on-failure with a 3s reconnect cadence (see line ~149),
  // so a slow / busy / momentarily-unavailable server doesn't drop the
  // page into the tiny browser fallback brain. As soon as the server's
  // first state broadcast lands, `state.totalNeurons` updates from the
  // 6700 default to the server's biological-scale count.
  console.log(`[RemoteBrain] Local origin detected — constructing RemoteBrain directly (no probe), ws=${url}`);
  return new RemoteBrain(url);
}
