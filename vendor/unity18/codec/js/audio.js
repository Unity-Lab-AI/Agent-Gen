/**
 * audio.js — PCM <-> field A. The 1-D half of the codec.
 *
 * ⛔ VENDORED, NOT IMPORTED.
 *   Source:    If-Only-I-Had-A-Brain :: js/brain/mindspace/audio.js
 *   At commit: c21660a1a2a85ab486048e7c17a163c2176d325d (2026-08-21)
 *   Copied on: 2026-08-29 for U3E-0.2
 *
 * ⛔ PLATFORM LAW: zero dependencies, zero `node:` imports, no Web Audio.
 *   Decoding a container to PCM is a caller's job; this file starts and ends at
 *   Float32 samples.
 *
 * ⭐ THE WHOLE POINT OF THIS FILE
 *   It is the SAME CDF 9/7 lifting as the image path, in the wavelet's native
 *   1-D habitat — the same `fwd1d`, the same `dv1` positions, the same int16
 *   quantisation, the same record shape. That is what makes one vocabulary over
 *   both modalities possible instead of two embedding spaces to keep aligned.
 *   ⚠ And by symmetry it is both directions: the transform that SPEAKS is the
 *   transform that HEARS. Free in representation — not free in training
 *   (`U3E-4B.3` still needs audio->transcript pairs).
 */

import { fwd1d, inv1d } from './cdf97.js';
import { bytesToB64, i16ToBytes, encPos, b64ToI16, decodePositions } from './bytes.js';

export const AUDIO_MODEL = 'cdf97_audio_native_quantized';
export const VOX_BANK_VERSION = 1;

/** Lift window: a power of two so every level of the ladder is available. ~1.37s at 24kHz. */
export const CHUNK = 32768;
/** Target relative L2 error per chunk. Tighter than the image path — speech is unforgiving. */
export const AUDIO_TOL = 0.02;
/** Floor on kept terms per chunk. */
export const AUDIO_KMIN = 256;
/** Hostile-input bound on a single perceive call. */
export const MAX_SECONDS = 30;

/**
 * PCM -> field A (HEARING / material to speak from).
 *
 * @param pcm         mono Float32Array (or any indexable of numbers)
 * @param sampleRate  defaults to 24000
 *
 * The tail chunk is zero-padded to the full window. `len` records how much of
 * that chunk was real, so reconstruction trims it rather than emitting silence.
 */
/**
 * ⛔⛔ THE 30-SECOND BOUND WAS CUTTING HER OFF MID-SENTENCE, SILENTLY.
 *
 * Reported from use: on longer replies her spoken voice stopped partway through
 * and never finished the text.
 *
 * `MAX_SECONDS` is a HOSTILE-INPUT bound — it exists so a public door cannot be
 * handed an hour of audio in one call. ⚠ It was being applied to HER OWN
 * SYNTHESIS, which is not hostile input, and it truncated with no error, no
 * flag and no log: the field simply ended and the voice stopped mid-word.
 *
 * ⭐ Two changes, and the second matters more than the first:
 *   1. `maxSeconds` is now a parameter. Trusted callers (her voice, from our
 *      own TTS) raise it; anything reading untrusted audio keeps the default.
 *   2. **TRUNCATION IS RECORDED ON THE FIELD** — `truncated` and
 *      `truncatedFromSeconds`. A bound that silently discards data is the
 *      silent-wrongness failure this project logs everywhere else, and it hid
 *      this for as long as replies were short.
 */
export function perceiveAudio(pcm, sampleRate = 24000, opts = {}) {
  if (!pcm || !pcm.length) return null;
  const limit = Math.max(1, opts.maxSeconds || MAX_SECONDS);
  const n = Math.min(pcm.length, sampleRate * limit);
  const truncated = n < pcm.length;
  const chunks = [];

  for (let off = 0; off < n; off += CHUNK) {
    const len = Math.min(CHUNK, n - off);
    const buf = new Float64Array(CHUNK);
    for (let i = 0; i < len; i++) buf[i] = pcm[off + i];

    fwd1d(buf, 0, 1, CHUNK, new Float64Array(CHUNK));

    // Sequential energy accumulation, same ordering rule as the image path.
    let total = 0;
    for (let i = 0; i < CHUNK; i++) total += buf[i] * buf[i];
    total = total || 1;

    const order = Array.from({ length: CHUNK }, (_, i) => i)
      .sort((a, b) => Math.abs(buf[b]) - Math.abs(buf[a]));

    const target = (1 - AUDIO_TOL * AUDIO_TOL) * total;
    let acc = 0, k = 0;
    while (k < CHUNK && acc < target) { acc += buf[order[k]] * buf[order[k]]; k++; }
    k = Math.max(AUDIO_KMIN, Math.min(k, CHUNK));

    const idx = order.slice(0, k).sort((a, b) => a - b);
    let maxAbs = 1e-8;
    for (let i = 0; i < k; i++) maxAbs = Math.max(maxAbs, Math.abs(buf[idx[i]]));
    const qscale = maxAbs / 32000;
    const q = new Int16Array(k);
    for (let i = 0; i < k; i++) {
      const v = Math.round(buf[idx[i]] / qscale);        // JS rounding — see field.js
      q[i] = Math.max(-32767, Math.min(32767, v));
    }

    chunks.push({
      keep: k, qscale, pos_enc: 'dv1', len,
      pos_b64: bytesToB64(encPos(idx)),
      val_b64: bytesToB64(i16ToBytes(q)),
    });
  }

  let terms = 0;
  for (const c of chunks) terms += c.keep;
  return {
    model: AUDIO_MODEL, wavelet: 'cdf97', v: VOX_BANK_VERSION,
    sampleRate, length: n, chunkSize: CHUNK, chunks, equation_count: terms,
    seconds: +(n / sampleRate).toFixed(2),
    // ⛔ Never silent. If audio was discarded, the field says so and by how much.
    truncated,
    ...(truncated ? { truncatedFromSeconds: +(pcm.length / sampleRate).toFixed(2), limitSeconds: limit } : {}),
  };
}

/** Field A -> PCM (SPEAKING from equations alone; no executor in the loop). */
export function reconstructAudio(rec) {
  if (!rec || !Array.isArray(rec.chunks)) return null;
  const out = new Float32Array(rec.length);
  let off = 0;
  for (const c of rec.chunks) {
    const flat = new Float64Array(rec.chunkSize);
    const val = b64ToI16(c.val_b64);
    const pos = decodePositions(c, val.length);
    for (let i = 0; i < pos.length; i++) {
      const p = pos[i];
      if (p >= 0 && p < rec.chunkSize) flat[p] = val[i] * c.qscale;
    }
    inv1d(flat, 0, 1, rec.chunkSize, new Float64Array(rec.chunkSize));
    const len = Math.min(c.len ?? rec.chunkSize, rec.length - off);
    for (let i = 0; i < len; i++) out[off + i] = flat[i];
    off += len;
  }
  return out;
}

/** Concatenate word PCMs with a short linear crossfade — her sentence mouth. */
export function concatAudio(pcms, sampleRate = 24000, xfadeMs = 30) {
  const parts = (pcms || []).filter(p => p && p.length);
  if (!parts.length) return null;
  const xf = Math.max(0, Math.round(sampleRate * xfadeMs / 1000));
  let total = 0;
  for (const p of parts) total += p.length;
  total -= xf * (parts.length - 1);
  const out = new Float32Array(Math.max(1, total));
  let off = 0;
  for (let pi = 0; pi < parts.length; pi++) {
    const p = parts[pi];
    const start = pi === 0 ? 0 : xf;
    if (pi > 0) {
      for (let i = 0; i < xf && off - xf + i < out.length && i < p.length; i++) {
        const t = i / xf;
        out[off - xf + i] = out[off - xf + i] * (1 - t) + p[i] * t;
      }
    }
    for (let i = start; i < p.length && off + i - start < out.length; i++) {
      out[off + i - start] = p[i];
    }
    off += p.length - start;
  }
  return out;
}

/**
 * Field A -> octave-band percept vector. The auditory twin of
 * describeEquational: band = floor(log2(position + 1)), amplitude mass per
 * band, L2-normalised.
 */
export function describeAudio(rec, bins = 32) {
  const out = new Float64Array(bins);
  if (!rec || !Array.isArray(rec.chunks)) return out;
  for (const c of rec.chunks) {
    let val, pos;
    try { val = b64ToI16(c.val_b64); pos = decodePositions(c, val.length); } catch (e) { continue; }
    for (let i = 0; i < val.length; i++) {
      const p = pos[i];
      if (p < 0) continue;
      // exact floor(log2), for the reason given in field.js
      const band = Math.min(bins - 1, 31 - Math.clz32(p + 1));
      out[band] += Math.abs(val[i] * c.qscale);
    }
  }
  let norm = 0;
  for (let i = 0; i < bins; i++) norm += out[i] * out[i];
  norm = Math.sqrt(norm) || 1;
  for (let i = 0; i < bins; i++) out[i] /= norm;
  return out;
}
