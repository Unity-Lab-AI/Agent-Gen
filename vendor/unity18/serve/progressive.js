/**
 * progressive.js — `U3E-5.3`. Stream the coarse prefix first, so a picture
 * appears and sharpens.
 *
 * ⭐ THIS IS THE PROPERTY THAT JUSTIFIES THE WHOLE REPRESENTATION.
 *   If the token count only ties the pixel baseline, this is still a reason to
 *   prefer a wavelet field: a PREFIX of the stream is a whole coarse image, not
 *   a sharp fragment of one. A pixel tokenizer emits patches — stop halfway and
 *   you have half a picture. Stop halfway here and you have all of the picture,
 *   blurry.
 *
 * ⛔ IT IS NOT A LOADING ANIMATION.
 *   Each slice is real coefficients the client genuinely did not have. The
 *   honest test: mute the later slices and the image must stay coarse forever.
 *   If it sharpens anyway, something is sending the whole field and fading it in.
 *
 * ⛔ PLATFORM LAW: zero dependencies, no `node:` imports. Shared by the server
 * and, if ever wanted, the client.
 */

import { bandsFor } from '../tokenizer/geometry.js';
import { chanVal, decodePositions, encPos, bytesToB64, i16ToBytes } from '../codec/js/bytes.js';

const CHANNELS = ['Y', 'Cb', 'Cr'];

/** Which 1-D band each coordinate falls in — the scale ladder, coarse first. */
function bandIndexMap(N) {
  const bands = bandsFor(N);
  const map = new Int32Array(N);
  for (let b = 0; b < bands.length; b++) {
    for (let i = bands[b][0]; i < bands[b][1] && i < N; i++) map[i] = b;
  }
  return { map, count: bands.length };
}

/**
 * Split a field into coarse-to-fine slices.
 *
 * @returns [{ scale, channels: { Y: {...}, ... }, coefficients }] where each
 *          entry holds ONLY the coefficients introduced at that scale. The
 *          client accumulates.
 *
 * ⚠ Slices are cumulative in EFFECT, not in content — each carries only its own
 * new coefficients, because re-sending everything each time would make the
 * stream quadratic and would also hide a bug where later slices add nothing.
 */
export function sliceField(rec) {
  const W2 = rec.pad_w, H2 = rec.pad_h;
  const bx = bandIndexMap(W2), by = bandIndexMap(H2);
  const maxScale = Math.max(bx.count, by.count);

  // bucket every coefficient by its scale
  const buckets = [];
  for (let s = 0; s < maxScale; s++) buckets.push({ Y: [], Cb: [], Cr: [] });

  for (const name of CHANNELS) {
    const c = rec.channels[name];
    if (!c) continue;
    const val = chanVal(c);
    const pos = decodePositions(c, val.length);
    const qs = c.qscale;
    for (let i = 0; i < pos.length; i++) {
      const p = pos[i];
      const x = p % W2, y = (p / W2) | 0;
      const s = Math.max(bx.map[x] || 0, by.map[y] || 0);
      buckets[Math.min(s, maxScale - 1)][name].push([p, val[i], qs]);
    }
  }

  const slices = [];
  for (let s = 0; s < maxScale; s++) {
    const channels = {};
    let n = 0;
    for (const name of CHANNELS) {
      const items = buckets[s][name];
      if (!items.length) continue;
      items.sort((a, b) => a[0] - b[0]);           // dv1 requires ascending
      const idx = items.map(it => it[0]);
      // re-quantise this slice against its own scale, so a slice of tiny
      // fine-scale coefficients keeps its precision instead of being crushed
      // by the coarse scale's qscale
      const reals = items.map(it => it[1] * it[2]);
      let maxAbs = 1e-8;
      for (const v of reals) maxAbs = Math.max(maxAbs, Math.abs(v));
      const qscale = maxAbs / 32000;
      const q = new Int16Array(reals.length);
      for (let i = 0; i < reals.length; i++) {
        q[i] = Math.max(-32767, Math.min(32767, Math.round(reals[i] / qscale)));
      }
      channels[name] = {
        keep: idx.length, qscale, pos_enc: 'dv1',
        pos_b64: bytesToB64(encPos(idx)),
        val_b64: bytesToB64(i16ToBytes(q)),
      };
      n += idx.length;
    }
    if (n) slices.push({ scale: s, channels, coefficients: n });
  }
  return slices;
}

/**
 * Merge a slice into an accumulating field record (client side).
 * Returns a NEW record that reconstructs to everything received so far.
 */
export function mergeSlice(acc, slice, meta) {
  const out = acc || {
    model: 'cdf97_wavelet_native_quantized', colorspace: 'YCbCr', wavelet: 'cdf97',
    width: meta.width, height: meta.height, pad_w: meta.pad_w, pad_h: meta.pad_h,
    channels: {}, equation_count: 0,
    fidelity: { psnr_db: null, source: 'u3e-progressive' },
  };

  for (const name of CHANNELS) {
    const inc = slice.channels[name];
    if (!inc) continue;
    const have = out.channels[name];
    if (!have) { out.channels[name] = inc; continue; }

    // union the two coefficient sets, in real value space
    const a = chanVal(have), ap = decodePositions(have, a.length), aq = have.qscale;
    const b = chanVal(inc), bp = decodePositions(inc, b.length), bq = inc.qscale;
    const m = new Map();
    for (let i = 0; i < ap.length; i++) m.set(ap[i], a[i] * aq);
    for (let i = 0; i < bp.length; i++) m.set(bp[i], b[i] * bq);

    const keys = Array.from(m.keys()).sort((x, y) => x - y);
    let maxAbs = 1e-8;
    for (const k of keys) maxAbs = Math.max(maxAbs, Math.abs(m.get(k)));
    const qscale = maxAbs / 32000;
    const q = new Int16Array(keys.length);
    for (let i = 0; i < keys.length; i++) {
      q[i] = Math.max(-32767, Math.min(32767, Math.round(m.get(keys[i]) / qscale)));
    }
    out.channels[name] = {
      keep: keys.length, qscale, pos_enc: 'dv1',
      pos_b64: bytesToB64(encPos(keys)),
      val_b64: bytesToB64(i16ToBytes(q)),
    };
  }

  out.equation_count = CHANNELS.reduce(
    (s, n) => s + (out.channels[n] ? out.channels[n].keep : 0), 0);
  return out;
}

/**
 * ⛔ Every channel must be present before the first render, or the picture
 * arrives grey and then colours — which looks like a bug even though it is not.
 * The caller waits for this before drawing the first frame.
 */
export function renderable(rec) {
  return !!(rec && rec.channels && rec.channels.Y && rec.channels.Cb && rec.channels.Cr);
}
