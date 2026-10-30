// MindSpaceWorkerProxy — the same surface as MindSpaceGPU, with the engine
// living in a worker thread (server/mindspace-worker.mjs). Heavy ops
// (imagineFromState / sketch / describe / perceive / morph) return Promises
// and execute serialized in the worker — one imagination lane, in order,
// zero event-loop time on the main thread. Governor calls stay sync-shaped
// at the call site (fire-and-forget RPC; worker message order preserves the
// governState → governTick → imagine sequence). glyphStrokes is pure
// stroke geometry (FONT5X7 → line segments, no engine state) and runs on a
// local instance so sync callers keep working unchanged.
const { Worker } = require('worker_threads');
const path = require('path');

class MindSpaceWorkerProxy {
  constructor(localPure) {
    this._local = localPure || null;
    this._pending = new Map();
    this._seq = 0;
    this.available = false;
    let readyResolve;
    this._ready = new Promise((r) => { readyResolve = r; });
    this._worker = new Worker(path.join(__dirname, '..', 'mindspace-worker.mjs'));
    // Imagination must never hold the process open past shutdown.
    this._worker.unref();
    this._worker.on('message', (m) => {
      if (m && m.ready) {
        this.available = !!m.available;
        readyResolve(true);
        return;
      }
      if (!m || !this._pending.has(m.id)) return;
      const p = this._pending.get(m.id);
      this._pending.delete(m.id);
      if (m.error) p.reject(new Error(m.error));
      else p.resolve(m.value);
    });
    this._worker.on('error', (e) => {
      console.warn('[MindSpace] worker error:', e?.message || e);
      for (const p of this._pending.values()) p.reject(e instanceof Error ? e : new Error(String(e)));
      this._pending.clear();
    });
    this._worker.on('exit', (code) => {
      if (code !== 0) console.warn(`[MindSpace] worker exited with code ${code} — imagination paused (calls reject until restart).`);
      const err = new Error('mindspace worker exited');
      for (const p of this._pending.values()) p.reject(err);
      this._pending.clear();
    });
  }

  init() { return this._ready; }

  _call(method, args) {
    return new Promise((resolve, reject) => {
      const id = ++this._seq;
      this._pending.set(id, { resolve, reject });
      try { this._worker.postMessage({ id, method, args }); }
      catch (e) { this._pending.delete(id); reject(e); }
    });
  }

  // ── ONE PROCESS — DONOR BRIDGE ─────────────────────────────────────────────
  // Her mind's eye and her voice run on the GPU, on the SAME device computing
  // her brain. They are one process, not two systems bolted together.
  // When a mindspace-capable donor is connected (compute.html / donor-v0.3.11+),
  // the heavy mind-space ops run ON THE DONOR GPU — the same device computing
  // her brain. brain-server injects the bridge after construction. The LOCAL
  // worker path below each op is the ROLLOUT RAMP ONLY (until v0.3.11 is the
  // min donor version — sparseV2 precedent; removal milestone in TODO §ONE
  // PROCESS), NOT a permanent fallback.
  setDonorBridge(dispatch, capable) {
    this._donorDispatch = dispatch;   // (op, payload, timeoutMs) => Promise<result|null>
    this._donorCapable = capable;     // () => boolean
  }

  _viaDonor(op) {
    return !!(this._donorDispatch && this._donorCapable && this._donorCapable(op));
  }

  // Heavy engine ops — async; donor GPU when capable, local worker as the ramp.
  async imagineFromState(seed, opts) {
    if (this._viaDonor('imagineFromState')) {
      const f32 = seed instanceof Float32Array ? seed : Float32Array.from(seed || []);
      const r = await this._donorDispatch('imagineFromState', {
        seed_b64: Buffer.from(f32.buffer, f32.byteOffset, f32.byteLength).toString('base64'),
        opts: opts || {},
      });
      if (r && r.rec) return r.rec;
      // fall through to the local ramp on donor miss/timeout
    }
    return this._call('imagineFromState', [seed, opts]);
  }

  sketch(...args) { return this._call('sketch', args); }

  // THE WIRE FORM. The donor lane serializes recs to JSON over the WS; resident
  // store recs hold binary Buffers, so convert to the base64 wire form at
  // this boundary (a Buffer inside JSON.stringify becomes a bloated numeric
  // object the donor's browser decoder cannot read).
  _recWireSafe(rec) {
    try {
      if (!rec || !rec.channels) return rec;
      let needs = false;
      for (const c of Object.values(rec.channels)) if (c && (c.val_bin || c.pos_bin)) { needs = true; break; }
      if (!needs) return rec;
      const chans = {};
      for (const [name, c] of Object.entries(rec.channels)) {
        if (!c) { continue; }
        const co = { ...c };
        if (c.val_bin) { co.val_b64 = Buffer.from(c.val_bin.buffer || c.val_bin, c.val_bin.byteOffset || 0, c.val_bin.byteLength ?? c.val_bin.length).toString('base64'); delete co.val_bin; }
        if (c.pos_bin) { co.pos_b64 = Buffer.from(c.pos_bin.buffer || c.pos_bin, c.pos_bin.byteOffset || 0, c.pos_bin.byteLength ?? c.pos_bin.length).toString('base64'); delete co.pos_bin; }
        chans[name] = co;
      }
      return { ...rec, channels: chans };
    } catch { return rec; }
  }
  // ⛔⛔ DELIBERATELY NOT DONOR-ROUTED AS OF 2026-10-29 — IT PAID 2.4 MB OF WIRE
  // FOR 512 BYTES OF ARITHMETIC THAT IS NOT GPU WORK.
  //
  // Found by naming the op in the donor send forensics: EVERY >2MB non-upload
  // send to the PRIMARY was `mindspace_op:describe` — 15 in four minutes on one
  // boot, then 4 of 4 on the next, 2.0-2.4 MB each, with the other four routed
  // ops contributing ZERO. The payload is the base64'd rec; the reply is a
  // 64-float percept (512 B).
  //
  // ⭐ And `describeEquational` (transform.js) is a SINGLE LINEAR PASS over the
  // rec's nonzero coefficients — band energies, mean-abs per channel, a 24-value
  // coarse window, then an L2 normalise. No lifting, no convolution, no matrix
  // work. O(nnz) scalar accumulation, milliseconds on CPU. **There was never a
  // reason for it to cross a socket.**
  //
  // ⚠ WHY THIS DOES NOT CHANGE WHAT SHE PERCEIVES, which is the only thing that
  // could have made this a curriculum change rather than an optimisation:
  // percepts feed sem, so a numerically different percept would be a change to
  // what she grounds words against. Both implementations were READ side by side
  // before this was flipped — `donor-app/src/mindspace.rs` `describe()` against
  // `transform.js` `describeEquational()`: same NB=8 bands, same band_base
  // [0,8,16], same 24-value coarse window at offset 24, same f64 accumulation,
  // same iteration order, same L2 normalise. The port is faithful.
  //
  // ⚠ ONE LATENT DIVERGENCE RECORDED RATHER THAN FIXED HERE (it lives in the
  // donor): the JS skips negative positions (`if (p < 0) continue`), the Rust
  // does `pos[i] as usize` with no such guard, so a negative would wrap to a
  // huge index and read garbage instead of being skipped. Not reachable today,
  // and it is a donor-side fix needing a release.
  //
  // ⚠ This reverses ONE PROCESS routing for THIS OP ONLY, on the operator's
  // explicit call. The ruling's subject is the heavy field math — the lifting,
  // trace, stylize and imagine ops — and those all stay on the card. Reading a
  // finished field as a percept vector is a reduction, not imagery generation.
  // The local path is the mindspace worker thread, so this does not move work
  // onto the event loop either. Same precedent and same reason as
  // `traceCentreline` below: an op belongs on the donor when the DEVICE is the
  // point, not merely because the protocol has a slot for it.
  async describe(rec, dim) {
    return this._call('describe', [rec, dim]);
  }

  async perceive(img) {
    if (this._viaDonor('perceive') && img && img.data && img.width && img.height) {
      const r = await this._donorDispatch('perceive', {
        width: img.width, height: img.height,
        rgba_b64: Buffer.from(img.data.buffer, img.data.byteOffset, img.data.byteLength).toString('base64'),
      });
      if (r && r.rec) return r.rec;
    }
    return this._call('perceive', [img]);
  }

  morph(...args) { return this._call('morph', args); }
  // Reconstruct a rec to pixels. ⛔ The COLOR pipeline
  // (palette + per-part + per-stroke sampling) checks `typeof imagine ===
  // 'function'` before sampling — this method was MISSING from the proxy, so
  // on the box every schema silently banked with NO colors and every drawing
  // rendered as monotone neutral outlines while the harness (which ran the
  // engine directly) showed full color. The worker dispatch is generic, the
  // engine has imagine() — one passthrough completes the pipeline in
  // production.
  imagine(...args) { return this._call('imagine', args); }

  // Governor state lives with the engine; call sites stay sync-shaped.
  governState(...args) { this._call('governState', args).catch(() => {}); }
  governTick(...args) { this._call('governTick', args).catch(() => {}); }

  // Pure stroke geometry — no engine state; sync on the local instance.
  // ⛔ REAL LETTERFORMS — the passthrough ships in the SAME change as the engine
  // method, because a method missing from this list does not throw: the caller's
  // `typeof` guard takes the silent branch, and it does so IN PRODUCTION ONLY
  // (an engine-direct harness never goes through the proxy). That is exactly how
  // every banked schema came out colourless for a day. These are async because
  // the worker dispatch is; the boot path awaits them.
  //
  // ⛔⛔ AND IT MUST LAND ON `_local`, NOT ONLY ON THE WORKER. `glyphStrokes` is
  // SYNC and runs on the local pure instance (see below) — a `_call()` here
  // would set the worker's engine, leave the instance that actually draws
  // letters unset, and every `real: true` caller would get [] forever while
  // the worker reported `letterformsReady: true`. Caught while writing it, not
  // after; recorded because it is the exact shape that shipped before. The
  // worker gets a copy too so any future async consumer sees the same data.
  async setLetterforms(data) {
    let local = null;
    if (this._local && typeof this._local.setLetterforms === 'function') local = this._local.setLetterforms(data);
    let worker = null;
    try { worker = await this._call('setLetterforms', [data]); } catch { worker = null; }
    return { local, worker };
  }
  letterformsReady() {
    // Report the instance that DRAWS. The worker's answer is not the one that matters.
    return (this._local && typeof this._local.letterformsReady === 'function')
      ? this._local.letterformsReady()
      : { ready: false, glyphs: 0, source: null, reason: 'no local engine' };
  }

  glyphStrokes(...args) {
    return (this._local && typeof this._local.glyphStrokes === 'function')
      ? this._local.glyphStrokes(...args)
      : [];
  }

  // Pure field-C → HER HAND'S STROKES (CDF 9/7 inverse → Sobel edges → edge-
  // follow polylines → Douglas-Peucker → field-colored). Like glyphStrokes it's
  // pure geometry over the rec with NO engine/GPU state, so it runs SYNC on the
  // local instance. It MUST stay sync: _drawConcept
  // calls it as `strokes = this.mindSpace.traceField(...)` (NOT awaited) — routing
  // it through the worker would hand back a Promise (no .length), every draw
  // would silently fall to null, and she'd look things up without ever drawing.
  // THIS omission was exactly that bug: the proxy lacked traceField, so
  // _drawConcept's guard (`typeof this.mindSpace.traceField !== 'function'`)
  // bailed on EVERY call and no drawing was ever produced — twenty reference
  // look-ups in a row with not one drawing attempted, and nothing logged.
  traceField(...args) {
    return (this._local && typeof this._local.traceField === 'function')
      ? this._local.traceField(...args)
      : [];
  }

  // Clean-ink line-art tracer (DRAW-ENGINE v2) — NOW ASYNC (ONE PROCESS):
  // donor GPU when capable (the lifting inside the trace runs on the same
  // device as her brain), local instance as the rollout ramp. ⚠ Contract
  // change from the old sync version: EVERY caller must `await` it (chat.js
  // _drawConcept/_drawImagined updated in the same batch — a non-awaited call
  // would see a Promise with no .length and silently draw nothing, the exact
  // old traceField-forward bug class).
  async traceLineArt(rec, opts) {
    if (this._viaDonor('traceLineArt')) {
      const r = await this._donorDispatch('traceLineArt', { rec: this._recWireSafe(rec), opts: opts || {} });
      if (r && Array.isArray(r.strokes)) return r.strokes;
    }
    return (this._local && typeof this._local.traceLineArt === 'function')
      ? this._local.traceLineArt(rec, opts)
      : [];
  }

  // ⛔⛔ THE PROXY PASSTHROUGH IS NOT OPTIONAL, AND THIS PROJECT HAS ALREADY PAID
  // FOR FORGETTING IT ONCE. A method absent here falls through to the caller's
  // `typeof` guard, which then takes the silent branch — in production only,
  // because an engine-direct harness never goes through the proxy. That is
  // exactly how every banked schema came out colourless while the tests passed.
  // DELIBERATELY NOT DONOR-ROUTED: the donor has no `traceCentreline` opcode, so
  // routing it would reach `_donorDispatch`, come back empty, and read as a letter
  // she could not trace. Local only, until a donor release carries it.
  traceCentreline(rec, opts = {}) {
    return (this._local && typeof this._local.traceCentreline === 'function')
      ? this._local.traceCentreline(rec, opts)
      : [];
  }

  // Color-fill draw style — flat colour-region strokes (sync-local; out of the
  // auto-rotation, explicit opts.style only — not donor-routed).
  traceColorFill(...args) {
    return (this._local && typeof this._local.traceColorFill === 'function')
      ? this._local.traceColorFill(...args)
      : [];
  }

  // Detailed styled field render — NOW ASYNC (ONE PROCESS): donor GPU when
  // capable, local as the rollout ramp. Same await-contract warning as
  // traceLineArt above.
  async stylizeField(rec, opts) {
    if (this._viaDonor('stylizeField')) {
      const o = opts || {};
      const r = await this._donorDispatch('stylizeField', {
        rec,
        opts: { traceSide: o.traceSide, bands: o.bands },
        labelStrokes: o.labelStrokes || null,
      });
      if (r && r.rec) return r.rec;
    }
    return (this._local && typeof this._local.stylizeField === 'function')
      ? this._local.stylizeField(rec, opts)
      : null;
  }

  // composeFields forward REMOVED (2026-07-16) — the collage compositor is gone;
  // imagination now field-renders ONE unified looked-up scene (see chat.js).
}

module.exports = { MindSpaceWorkerProxy };
