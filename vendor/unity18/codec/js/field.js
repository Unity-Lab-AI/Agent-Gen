/**
 * field.js — image <-> field C. The 2-D half of the codec.
 *
 * ⛔ VENDORED, NOT IMPORTED.
 *   Source:    If-Only-I-Had-A-Brain :: js/brain/mindspace/transform.js
 *              (equationalizeImageData, reconstructImageData,
 *               termsAboveThreshold, describeEquational)
 *   At commit: c21660a1a2a85ab486048e7c17a163c2176d325d (2026-08-21)
 *   Copied on: 2026-08-29 for U3E-0.2
 *
 * ⛔ PLATFORM LAW: zero dependencies, zero `node:` imports, no DOM.
 *   ⚠ ONE DELIBERATE DIVERGENCE FROM THE SOURCE: the source returned a browser
 *   `ImageData` from reconstruct. `ImageData` does not exist in Node, so this
 *   copy returns a plain `{width, height, data}` with the identical RGBA byte
 *   layout. `new ImageData(w, h)` is a one-line wrap at a browser call site.
 *   **No arithmetic changed.**
 *
 * DELIBERATELY NOT VENDORED (they live in the source engine and this project
 * does not need them yet): the drawing lane (traceField / traceLineArt /
 * traceColorFill / stylizeField), the thought-medium operators (abstract /
 * morphField), and the browser canvas helper. If a later phase wants one, copy
 * it then, with its own provenance line — do not reach across.
 */

import { fwd2d, idwt2, rgbToYCbCr, ycbcrToRGB, padDim } from './cdf97.js';
import {
  bytesToB64, i16ToBytes, encPos, chanVal, chanHasVal, decodePositions,
} from './bytes.js';

/** The record's `model` string. Anything else is a different format. */
export const FIELD_MODEL = 'cdf97_wavelet_native_quantized';

/**
 * Per-channel target relative L2 error and minimum kept coefficients, for
 * [Y, Cb, Cr]. These are the source engine's CORPUS-quality constants (not its
 * looser in-browser preview values) and they set the fidelity every later
 * measurement is taken at. ⛔ Changing them invalidates every banked field and
 * every number measured against it.
 */
export const EQ_TOL = [0.018, 0.032, 0.032];
export const EQ_KMIN = [500, 150, 150];

/** Longest edge the source engine drew to before encoding. Kept for parity. */
export const EQ_LONG_EDGE = 1536;

/**
 * ⛔ THE ROUNDING TRAP — the single most likely cause of a Python twin that is
 * "almost" right.
 *
 * JavaScript `Math.round` rounds a half AWAY from... no: toward POSITIVE
 * infinity. Math.round(2.5) === 3 and Math.round(-2.5) === -2.
 * Python's built-in round() and numpy.round both use BANKER'S rounding:
 * round(2.5) == 2. They disagree on every exact half.
 *
 * Coefficient/qscale ratios land on exact halves far more often than intuition
 * suggests, because qscale is derived from a max that is itself one of the
 * values. The Python twin must implement JS semantics explicitly — see
 * codec/py/u3e_codec.py :: js_round — and codec/verify/ proves it.
 */

/**
 * Quantise real coefficients to int16 with a shared scale.
 * qscale is chosen so the largest magnitude lands at 32000, leaving headroom
 * below the 32767 clamp.
 */
function quantise(reals) {
  const k = reals.length;
  let maxAbs = 1e-8;
  for (let i = 0; i < k; i++) maxAbs = Math.max(maxAbs, Math.abs(reals[i]));
  const qscale = maxAbs / 32000;
  const q = new Int16Array(k);
  for (let i = 0; i < k; i++) {
    const v = Math.round(reals[i] / qscale);
    q[i] = Math.max(-32767, Math.min(32767, v));
  }
  return { qscale, q };
}

/**
 * RGBA image -> field C.
 *
 * @param img {{width:number, height:number, data:Uint8ClampedArray|Uint8Array}}
 *            RGBA8, row-major, length >= width*height*4.
 * @returns the field record (see docs/FIELD-FORMAT.md).
 *
 * Padding uses REFLECTION, not zero-fill: a zero-filled border would put a hard
 * edge into the transform and spend coefficients describing the padding.
 */
export function equationalize(img) {
  return equationalizeStaged(img).rec;
}

/**
 * The same encode, returning its INTERMEDIATES alongside the record.
 *
 * ⛔ This exists so the parity gate measures the REAL encode path rather than a
 * replica of it written inside the harness. A harness that reimplements the
 * thing it is checking will agree with itself and prove nothing; that is the
 * "a test that passes because it compared the wrong thing" failure, and it is
 * worse than no check at all.
 *
 * `stages[ci]` carries, per channel: the full padded coefficient plane, the
 * sequential energy total, the target, the selected ascending index set, the
 * chosen qscale and the int16 values. Every one of them is compared.
 *
 * ⚠ Holds the three coefficient planes alive. Use `equationalize` in
 * production; this is for the gate and for diagnosis.
 */
export function equationalizeStaged(img) {
  const W0 = img.width, H0 = img.height, d = img.data;
  if (!W0 || !H0) throw new Error('equationalize: image has no dimensions');
  if (d.length < W0 * H0 * 4) throw new Error('equationalize: RGBA data is short');

  const W2 = padDim(W0), H2 = padDim(H0);
  const names = ['Y', 'Cb', 'Cr'], chans = {};
  const planes = [
    new Float64Array(W2 * H2), new Float64Array(W2 * H2), new Float64Array(W2 * H2),
  ];

  // reflect a padded coordinate back into the source image
  const refl = (i, n) => {
    if (i < n) return i;
    let r = 2 * (n - 1) - i;
    if (r < 0) r = 0;
    return r;
  };

  for (let y = 0; y < H2; y++) {
    const sy = refl(y, H0);
    for (let x = 0; x < W2; x++) {
      const sx = refl(x, W0), o = (sy * W0 + sx) * 4;
      const ycc = rgbToYCbCr(d[o] / 255, d[o + 1] / 255, d[o + 2] / 255);
      const p = y * W2 + x;
      planes[0][p] = ycc[0]; planes[1][p] = ycc[1]; planes[2][p] = ycc[2];
    }
  }

  let totalEq = 0;
  const stages = [];
  for (let ci = 0; ci < 3; ci++) {
    const co = fwd2d(planes[ci], H2, W2);
    const n = co.length;

    // Sequential energy accumulation. ⛔ The Python twin must accumulate in this
    // same order — a pairwise or vectorised sum (numpy's np.sum) gives a
    // different total and can select a different k.
    let total = 0;
    for (let i = 0; i < n; i++) total += co[i] * co[i];
    total = total || 1;

    // Descending by magnitude. Array.prototype.sort has been stable since
    // ES2019, so equal magnitudes keep ascending index order — the Python twin
    // must use a STABLE argsort to match.
    const order = Array.from({ length: n }, (_, i) => i)
      .sort((a, b) => Math.abs(co[b]) - Math.abs(co[a]));

    // Keep coefficients until the retained energy meets the tolerance target.
    // Content decides the count; the constant only sets the target.
    const target = (1 - EQ_TOL[ci] * EQ_TOL[ci]) * total;
    let acc = 0, k = 0;
    while (k < n && acc < target) { acc += co[order[k]] * co[order[k]]; k++; }
    k = Math.max(EQ_KMIN[ci], Math.min(k, n));

    const idx = order.slice(0, k).sort((a, b) => a - b);
    const reals = new Float64Array(k);
    for (let i = 0; i < k; i++) reals[i] = co[idx[i]];
    const { qscale, q } = quantise(reals);

    const posBytes = encPos(idx);
    chans[names[ci]] = {
      keep: k,
      qscale,
      pos_enc: 'dv1',
      pos_b64: bytesToB64(posBytes),
      val_b64: bytesToB64(i16ToBytes(q)),
    };
    stages.push({ coeffs: co, total, target, idx: Uint32Array.from(idx), qscale, q, posBytes, k });
    totalEq += k;
  }

  const rec = {
    model: FIELD_MODEL, colorspace: 'YCbCr', wavelet: 'cdf97',
    width: W0, height: H0, pad_w: W2, pad_h: H2,
    channels: chans, equation_count: totalEq,
    fidelity: { psnr_db: null, source: 'u3e' },
  };
  return { rec, stages };
}

/**
 * Field C -> RGBA image (the plain-object stand-in for ImageData).
 *
 * @param dev  0..1 deviation: drops coefficients below `dev * max * 0.6`, which
 *             is how a field is "abstracted" without re-encoding. 0 = faithful.
 *
 * ⭐ PROGRESSIVE DECODE lives here in embryo: a prefix of the coefficient stream
 * reconstructs a coarse whole image, because the coarse subbands come first in
 * position order. `U3E-5.3` is this property turned into a streaming emission.
 */
export function reconstruct(rec, dev) {
  const W = rec.width, H = rec.height, W2 = rec.pad_w, H2 = rec.pad_h;
  const f = Math.max(0, Math.min(1, dev || 0));
  const chans = {};

  for (const name of ['Y', 'Cb', 'Cr']) {
    const c = rec.channels[name];
    const val = chanVal(c), qs = c.qscale, pos = decodePositions(c, val.length);
    let mx = 0;
    if (f > 0) for (let i = 0; i < val.length; i++) {
      const a = Math.abs(val[i] * qs); if (a > mx) mx = a;
    }
    const thr = f > 0 ? f * mx * 0.6 : 0;
    const flat = new Float64Array(W2 * H2), SIZE = W2 * H2;
    for (let i = 0; i < pos.length; i++) {
      const p = pos[i];
      if (p < 0 || p >= SIZE) continue;           // integrity bound, always on
      const v = val[i] * qs;
      if (thr && Math.abs(v) < thr) continue;
      flat[p] = v;
    }
    idwt2(flat, H2, W2);
    chans[name] = flat;
  }

  const data = new Uint8ClampedArray(W * H * 4);
  const Y = chans.Y, Cb = chans.Cb, Cr = chans.Cr;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const gi = y * W2 + x, o = (y * W + x) * 4;
    const rgb = ycbcrToRGB(Y[gi], Cb[gi], Cr[gi]);
    data[o] = Math.max(0, Math.min(255, rgb[0] * 255));
    data[o + 1] = Math.max(0, Math.min(255, rgb[1] * 255));
    data[o + 2] = Math.max(0, Math.min(255, rgb[2] * 255));
    data[o + 3] = 255;
  }
  return { width: W, height: H, data };
}

/** How many coefficients survive a given deviation. The cost side of `dev`. */
export function termsAboveThreshold(rec, dev) {
  const f = Math.max(0, Math.min(1, dev || 0));
  let n = 0;
  for (const name of ['Y', 'Cb', 'Cr']) {
    const c = rec.channels[name], val = chanVal(c), qs = c.qscale;
    if (!f) { n += val.length; continue; }
    let mx = 0;
    for (let i = 0; i < val.length; i++) {
      const a = Math.abs(val[i] * qs); if (a > mx) mx = a;
    }
    const thr = f * mx * 0.6;
    for (let i = 0; i < val.length; i++) if (Math.abs(val[i] * qs) >= thr) n++;
  }
  return n;
}

/**
 * Field C -> the percept value-vector: deterministic, L2-normalised, fixed-dim.
 *
 * ⭐ This is the metric `U3E-1.2` measures perceptual agreement with. It is not
 * a generic image embedding — it is the specific vector the sibling engine
 * already uses, which is why a number measured with it is comparable to that
 * project's own numbers.
 *
 * Layout (dim 64 default): [0..7] Y octave-band energy, [8..15] Cb, [16..23] Cr,
 * [24..47] the first 24 raw Y coefficients, [48..50] per-channel mean |value|,
 * [51] high-frequency energy fraction, [52] log-scaled equation count.
 */
export function describeEquational(rec, dim) {
  dim = dim || 64;
  const out = new Float64Array(dim);
  if (!rec || !rec.channels) return out;

  const W2 = rec.pad_w || rec.width || 1;
  const NB = 8;
  const names = ['Y', 'Cb', 'Cr'];
  const bandBase = [0, 8, 16];
  const coarseN = 24, coarseAt = 24;
  const chanMeanAbs = [0, 0, 0];
  let loEnergy = 0, hiEnergy = 0;

  for (let ci = 0; ci < 3; ci++) {
    const c = rec.channels[names[ci]];
    if (!c || !chanHasVal(c)) continue;
    let val, pos;
    try { val = chanVal(c); pos = decodePositions(c, val.length); } catch (e) { continue; }
    const qs = c.qscale || 1, base = bandBase[ci];
    const coarse = (ci === 0) ? [] : null;
    let mAbs = 0;
    for (let i = 0; i < val.length; i++) {
      const p = pos[i] | 0; if (p < 0) continue;
      const x = p % W2, y = (p / W2) | 0;
      // floor(log2(m)) by bit length, NOT Math.log2(m)|0.
      // ⛔ MEASURED: V8's Math.log2 and numpy's log2 disagree by one ULP on 2 of
      // the first 300,000 integers. A transcendental whose floor we then take is
      // a language-boundary hazard for no benefit — 31 - clz32 is the exact
      // integer answer in both languages, and faster.
      const band = Math.min(NB - 1, 31 - Math.clz32(Math.max(x, y) + 1));
      const v = val[i] * qs, e = v * v;
      out[base + band] += e;
      mAbs += Math.abs(v);
      if (band <= 1) loEnergy += e; else hiEnergy += e;
      if (coarse && coarse.length < coarseN) coarse.push(v);
    }
    chanMeanAbs[ci] = val.length ? mAbs / val.length : 0;
    if (coarse) for (let k = 0; k < coarse.length; k++) out[coarseAt + k] = coarse[k];
  }

  out[48] = chanMeanAbs[1]; out[49] = chanMeanAbs[2]; out[50] = chanMeanAbs[0];
  out[51] = (loEnergy + hiEnergy) > 0 ? hiEnergy / (loEnergy + hiEnergy) : 0;
  out[52] = Math.log2((rec.equation_count || 0) + 1) / 24;

  let norm = 0;
  for (let i = 0; i < dim; i++) norm += out[i] * out[i];
  norm = Math.sqrt(norm) || 1;
  for (let i = 0; i < dim; i++) out[i] /= norm;
  return out;
}

/** Cosine similarity of two percept vectors. 1 = identical direction. */
export function perceptCosine(a, b) {
  const n = Math.min(a.length, b.length);
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < n; i++) { dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i]; }
  const d = Math.sqrt(na) * Math.sqrt(nb);
  return d > 0 ? dot / d : 0;
}
