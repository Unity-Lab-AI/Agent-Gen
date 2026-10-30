/**
 * mindspace/audio.js — Unity's equational AUDIO substrate (ESM).
 *
 * The same univsmatics mathematics that runs her vision, in the wavelet's
 * NATIVE habitat: 1-D signals. A spoken word is perceived through the
 * forward CDF 9/7 lifting into a sparse quantized field-A record — the
 * word's equation — and re-spoken through the inverse transform. Storage,
 * recall, morphing and percept-reading all live in the equation domain,
 * exactly like the visual field C (transform.js is the shared primitive
 * layer for both senses).
 *
 * VOX pipeline (voice.js drives it):
 *   BANK-BUILD — the TTS executor speaks a word ONCE; the decoded PCM is
 *     perceived here into a field-A record and banked (the executor is a
 *     bank-builder the way Pollinations renders feed her visual memory).
 *   SPEAK — a sentence whose words are all banked reconstructs from HER
 *     equations alone: per-word inverse transform + short crossfade concat.
 *     No executor in the loop. The bank grows until the executor is silent.
 *   HEAR — describeAudio reads a field-A as an octave-band percept vector
 *     (the describeEquationalAudio layout) for auditory-region injection.
 *
 * BOUNDS: mono Float32 PCM, target 24 kHz, chunked at 32768 samples
 * (~1.37 s) so fwd1d lifts full pow-2 lines; energy-target sparsification
 * (content decides the term count, same idiom as the image encoder);
 * int16 quantization + LEB128 delta positions via the shared codecs.
 * No fractalize, no unbounded growth — a word is a few KB of equations.
 */

import {
  fwd1d, inv1d, encPos, decodePositions,
  bytesToB64, i16ToB64, b64i16,
} from './transform.js';

export const VOX_BANK_VERSION = 1;

const CHUNK = 32768;              // pow-2 lift window @24kHz ≈ 1.37s
const AUDIO_TOL = 0.02;           // target relative L2 error (speech-tight)
const AUDIO_KMIN = 256;           // floor terms per chunk
const MAX_SECONDS = 30;           // hostile-input bound on a single perceive

// ── forward: PCM → field-A record (SPEAKING material perceived) ─────────────
export function perceiveAudio(pcm, sampleRate = 24000) {
  if (!pcm || !pcm.length) return null;
  const n = Math.min(pcm.length, sampleRate * MAX_SECONDS);
  const chunks = [];
  for (let off = 0; off < n; off += CHUNK) {
    const len = Math.min(CHUNK, n - off);
    // zero-pad the tail chunk to the full pow-2 window
    const buf = new Float64Array(CHUNK);
    for (let i = 0; i < len; i++) buf[i] = pcm[off + i];
    fwd1d(i => buf[i], (i, v) => { buf[i] = v; }, CHUNK, new Float64Array(CHUNK));
    // energy-target selection — content decides the term count
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
      const v = Math.round(buf[idx[i]] / qscale);
      q[i] = Math.max(-32767, Math.min(32767, v));
    }
    chunks.push({
      keep: k, qscale, pos_enc: 'dv1', len,
      pos_b64: bytesToB64(new Uint8Array(encPos(idx))),
      val_b64: i16ToB64(q),
    });
  }
  let terms = 0;
  for (const c of chunks) terms += c.keep;
  return {
    model: 'cdf97_audio_native_quantized', wavelet: 'cdf97', v: VOX_BANK_VERSION,
    sampleRate, length: n, chunkSize: CHUNK, chunks, equation_count: terms,
  };
}

// ── inverse: field-A record → PCM (SPEAKING from her own equations) ─────────
export function reconstructAudio(rec) {
  if (!rec || !Array.isArray(rec.chunks)) return null;
  const out = new Float32Array(rec.length);
  let off = 0;
  for (const c of rec.chunks) {
    const flat = new Float64Array(rec.chunkSize);
    const val = b64i16(c.val_b64);
    const pos = decodePositions(c, val.length);
    for (let i = 0; i < pos.length; i++) {
      const p = pos[i];
      if (p >= 0 && p < rec.chunkSize) flat[p] = val[i] * c.qscale;
    }
    inv1d(i => flat[i], (i, v) => { flat[i] = v; }, rec.chunkSize, new Float64Array(rec.chunkSize));
    const len = Math.min(c.len ?? rec.chunkSize, rec.length - off);
    for (let i = 0; i < len; i++) out[off + i] = flat[i];
    off += len;
  }
  return out;
}

// ── concat word PCMs with a short linear crossfade (her sentence-mouth) ─────
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
      // crossfade region — previous tail fades out, this head fades in
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

// ── percept: field-A → octave-band value vector (HEARING) ────────────────────
// Mirrors describeEquationalAudio: band = ⌊log2(position-in-chunk + 1)⌋,
// amplitude mass per band, L2-normalised. Injectable into the auditory region.
export function describeAudio(rec, bins = 32) {
  const out = new Float64Array(bins);
  if (!rec || !Array.isArray(rec.chunks)) return out;
  for (const c of rec.chunks) {
    let val, pos;
    try { val = b64i16(c.val_b64); pos = decodePositions(c, val.length); } catch { continue; }
    for (let i = 0; i < val.length; i++) {
      const p = pos[i];
      if (p < 0) continue;
      const band = Math.min(bins - 1, Math.max(0, Math.log2(p + 1) | 0));
      out[band] += Math.abs(val[i] * c.qscale);
    }
  }
  let norm = 0;
  for (let i = 0; i < bins; i++) norm += out[i] * out[i];
  norm = Math.sqrt(norm) || 1;
  for (let i = 0; i < bins; i++) out[i] /= norm;
  return out;
}
