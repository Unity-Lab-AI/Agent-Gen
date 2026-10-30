/**
 * cdf97.js — CDF 9/7 biorthogonal wavelet lifting. The mathematical core.
 *
 * ⛔ VENDORED, NOT IMPORTED.
 *   Source:    If-Only-I-Had-A-Brain :: js/brain/mindspace/transform.js
 *   At commit: c21660a1a2a85ab486048e7c17a163c2176d325d (2026-08-21)
 *   Copied on: 2026-08-29 for U3E-0.2
 *   That project owns its original under different laws and versions it
 *   independently. This is a COPY. It must never become a live dependency, and
 *   a change there is not a change here — see .claude/CONSTRAINTS.md.
 *
 * ⛔ PLATFORM LAW: zero dependencies, zero `node:` imports, no DOM, no
 *   filesystem. This exact file runs in a phone browser and in Node. Anything
 *   that cannot is a tool and lives in codec/tools/.
 *
 * WHY THE NUMBERS MUST NOT DRIFT
 *   The lifting steps below are a fixed sequence of IEEE-754 double operations.
 *   Reordering them, folding `x / K97` into `x * (1/K97)`, or letting a
 *   compiler contract a multiply-add changes the low bits — and the Python twin
 *   (codec/py/) has to reproduce this to maxDiff = 0. Every apparent
 *   simplification below is deliberate.
 */

// The 9/7 lifting coefficients (Cohen-Daubechies-Feauveau) and the scaling
// constant. Verbatim from the source engine — do not re-derive, do not round.
export const A97 = -1.586134342059924;
export const B97 = -0.052980118572961;
export const G97 = 0.882911075530934;
export const D97 = 0.443506852043971;
export const K97 = 1.230174104914001;

/**
 * Level sizes for a signal of length N: the transform recurses on the
 * approximation half while it stays even and at least 4 long.
 * N=512 -> [512,256,128,64,32,16,8,4] (8 levels). An odd or short N simply
 * yields fewer levels; it is not an error.
 */
export function levelSizes(N) {
  const sizes = [];
  let sz = N;
  while (sz >= 4 && sz % 2 === 0) { sizes.push(sz); sz >>= 1; }
  return sizes;
}

/**
 * FORWARD 1-D multi-level lifting, strided and in place.
 * Reads/writes a[off + i*stride] for i in [0,N).
 *
 * Each lifting pass touches only opposite-parity neighbours, so every pass is
 * data-parallel across i — that property is what lets the Python twin
 * vectorise with numpy slices and still match bit for bit.
 */
export function fwd1d(a, off, stride, N, tmp) {
  const sizes = levelSizes(N);
  for (let si = 0; si < sizes.length; si++) {
    const size = sizes[si], half = size >> 1;
    for (let i = 0; i < size; i++) tmp[i] = a[off + i * stride];

    // predict/update ladder: alpha, beta, gamma, delta, then scaling
    tmp[size - 1] += 2 * A97 * tmp[size - 2];
    for (let i = 1; i < size - 1; i += 2) tmp[i] += A97 * (tmp[i - 1] + tmp[i + 1]);
    for (let i = 2; i < size; i += 2) tmp[i] += B97 * (tmp[i - 1] + tmp[i + 1]);
    tmp[0] += 2 * B97 * tmp[1];
    tmp[size - 1] += 2 * G97 * tmp[size - 2];
    for (let i = 1; i < size - 1; i += 2) tmp[i] += G97 * (tmp[i - 1] + tmp[i + 1]);
    for (let i = 2; i < size; i += 2) tmp[i] += D97 * (tmp[i - 1] + tmp[i + 1]);
    tmp[0] += 2 * D97 * tmp[1];
    for (let i = 0; i < size; i += 2) tmp[i] /= K97;   // division, NOT * (1/K97)
    for (let i = 1; i < size; i += 2) tmp[i] *= K97;

    // deinterleave: approximation into the first half, detail into the second
    for (let k = 0; k < half; k++) {
      a[off + k * stride] = tmp[2 * k];
      a[off + (half + k) * stride] = tmp[2 * k + 1];
    }
  }
}

/**
 * INVERSE 1-D multi-level lifting, strided and in place.
 * The exact reverse of fwd1d: levels walked outwards, every sign flipped.
 */
export function inv1d(a, off, stride, N, tmp) {
  const sizes = levelSizes(N);
  for (let si = sizes.length - 1; si >= 0; si--) {
    const size = sizes[si], half = size >> 1;

    // interleave: approximation and detail halves back into one line
    for (let k = 0; k < half; k++) {
      tmp[2 * k] = a[off + k * stride];
      tmp[2 * k + 1] = a[off + (half + k) * stride];
    }

    for (let i = 0; i < size; i += 2) tmp[i] *= K97;
    for (let i = 1; i < size; i += 2) tmp[i] /= K97;   // division, NOT * (1/K97)
    tmp[0] -= 2 * D97 * tmp[1];
    for (let i = 2; i < size; i += 2) tmp[i] -= D97 * (tmp[i - 1] + tmp[i + 1]);
    for (let i = 1; i < size - 1; i += 2) tmp[i] -= G97 * (tmp[i - 1] + tmp[i + 1]);
    tmp[size - 1] -= 2 * G97 * tmp[size - 2];
    tmp[0] -= 2 * B97 * tmp[1];
    for (let i = 2; i < size; i += 2) tmp[i] -= B97 * (tmp[i - 1] + tmp[i + 1]);
    for (let i = 1; i < size - 1; i += 2) tmp[i] -= A97 * (tmp[i - 1] + tmp[i + 1]);
    tmp[size - 1] -= 2 * A97 * tmp[size - 2];

    for (let i = 0; i < size; i++) a[off + i * stride] = tmp[i];
  }
}

/**
 * FORWARD 2-D separable transform, in place on a row-major H x W Float64Array.
 * ⛔ ROWS THEN COLUMNS. idwt2 undoes it columns then rows. Swapping the order
 * produces a plausible-looking image that is not the inverse of anything.
 */
export function fwd2d(a, H, W) {
  const tmpR = new Float64Array(W);
  for (let r = 0; r < H; r++) fwd1d(a, r * W, 1, W, tmpR);
  const tmpC = new Float64Array(H);
  for (let c = 0; c < W; c++) fwd1d(a, c, W, H, tmpC);
  return a;
}

/** INVERSE 2-D separable transform, in place. Columns then rows. */
export function idwt2(a, H, W) {
  const tmpC = new Float64Array(H);
  for (let c = 0; c < W; c++) inv1d(a, c, W, H, tmpC);
  const tmpR = new Float64Array(W);
  for (let r = 0; r < H; r++) inv1d(a, r * W, 1, W, tmpR);
  return a;
}

// ── colour ───────────────────────────────────────────────────────────────────
// Full-range JPEG-style YCbCr on [0,1] components with chroma centred at 0.5.
// Verbatim from the source engine; the constants are load-bearing for parity
// with fields the brain's browser already reconstructs.

export function rgbToYCbCr(r, g, b) {
  return [
    0.299 * r + 0.587 * g + 0.114 * b,
    0.5 - 0.168736 * r - 0.331264 * g + 0.5 * b,
    0.5 + 0.5 * r - 0.418688 * g - 0.081312 * b,
  ];
}

export function ycbcrToRGB(y, cb, cr) {
  return [
    y + 1.402 * (cr - 0.5),
    y - 0.344136 * (cb - 0.5) - 0.714136 * (cr - 0.5),
    y + 1.772 * (cb - 0.5),
  ];
}

/**
 * Pad a dimension up to a multiple of `m` (default 64) so the transform has
 * levels to recurse through. 64 is the source engine's value and changing it
 * changes every field's pad_w/pad_h, hence every stored position.
 */
export function padDim(n, m) { m = m || 64; return Math.ceil(n / m) * m; }
