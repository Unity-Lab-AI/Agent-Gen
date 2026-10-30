/**
 * bytes.js — payload codecs: base64, little-endian int16, and the `dv1`
 * delta-varint position encoding.
 *
 * ⛔ VENDORED, NOT IMPORTED.
 *   Source:    If-Only-I-Had-A-Brain :: js/brain/mindspace/transform.js
 *   At commit: c21660a1a2a85ab486048e7c17a163c2176d325d (2026-08-21)
 *   Copied on: 2026-08-29 for U3E-0.2
 *
 * ⛔ PLATFORM LAW: zero dependencies, zero `node:` imports.
 *   ⚠ The source engine used the `atob`/`btoa` globals. They exist in browsers
 *   and in Node, but they are legacy in Node and absent in some workers. This
 *   copy implements base64 in plain arithmetic instead: one implementation,
 *   identical everywhere, and trivially mirrored by the Python twin.
 *
 * ⚠ ENDIANNESS. The source engine serialised int16 values by taking a
 *   `Uint8Array` view over an `Int16Array` buffer, which is host-endian. Every
 *   real target — x86, ARM, the S23 — is little-endian, so the bytes on disk
 *   have always been LE. This copy writes LE **explicitly** rather than
 *   inheriting it from the host, so the format is a stated fact instead of a
 *   lucky one. On any machine that has ever run the source engine the output is
 *   byte-identical.
 */

const B64_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

// Reverse lookup table, built once. 255 marks "not a base64 character".
const B64_REVERSE = (() => {
  const t = new Uint8Array(256).fill(255);
  for (let i = 0; i < B64_ALPHABET.length; i++) t[B64_ALPHABET.charCodeAt(i)] = i;
  return t;
})();

/** Uint8Array -> standard base64 string, with `=` padding. Matches btoa. */
export function bytesToB64(bytes) {
  let out = '';
  const n = bytes.length, rem = n % 3, end = n - rem;
  for (let i = 0; i < end; i += 3) {
    const v = (bytes[i] << 16) | (bytes[i + 1] << 8) | bytes[i + 2];
    out += B64_ALPHABET[(v >> 18) & 63] + B64_ALPHABET[(v >> 12) & 63]
         + B64_ALPHABET[(v >> 6) & 63] + B64_ALPHABET[v & 63];
  }
  if (rem === 1) {
    const v = bytes[end] << 16;
    out += B64_ALPHABET[(v >> 18) & 63] + B64_ALPHABET[(v >> 12) & 63] + '==';
  } else if (rem === 2) {
    const v = (bytes[end] << 16) | (bytes[end + 1] << 8);
    out += B64_ALPHABET[(v >> 18) & 63] + B64_ALPHABET[(v >> 12) & 63]
         + B64_ALPHABET[(v >> 6) & 63] + '=';
  }
  return out;
}

/**
 * Standard base64 string -> Uint8Array. Matches atob.
 * ⛔ Throws on a character outside the alphabet rather than skipping it. A
 * corrupt payload that decodes to something shorter but plausible is exactly
 * the silent-wrongness class this project refuses.
 */
export function b64ToBytes(s) {
  let len = s.length;
  while (len > 0 && s[len - 1] === '=') len--;
  const out = new Uint8Array((len * 3) >> 2);
  let o = 0, acc = 0, bits = 0;
  for (let i = 0; i < len; i++) {
    const d = B64_REVERSE[s.charCodeAt(i)];
    if (d === 255) throw new Error(`b64ToBytes: invalid character at index ${i}`);
    acc = (acc << 6) | d;
    bits += 6;
    if (bits >= 8) { bits -= 8; out[o++] = (acc >> bits) & 0xFF; }
  }
  return out;
}

/** Int16Array -> little-endian bytes. */
export function i16ToBytes(v) {
  const out = new Uint8Array(v.length * 2);
  for (let i = 0; i < v.length; i++) {
    const x = v[i];
    out[i * 2] = x & 0xFF;
    out[i * 2 + 1] = (x >> 8) & 0xFF;
  }
  return out;
}

/** Little-endian bytes -> Int16Array (sign-extended). */
export function bytesToI16(b) {
  const n = b.length >> 1, out = new Int16Array(n);
  for (let i = 0; i < n; i++) {
    const lo = b[i * 2], hi = b[i * 2 + 1];
    const u = (hi << 8) | lo;
    out[i] = u >= 0x8000 ? u - 0x10000 : u;
  }
  return out;
}

export function i16ToB64(v) { return bytesToB64(i16ToBytes(v)); }
export function b64ToI16(s) { return bytesToI16(b64ToBytes(s)); }

// ── dv1: delta + LEB128 varint position codec ────────────────────────────────
// Positions within a field are strictly ascending grid indices. Storing the gap
// to the previous position instead of the absolute index makes most gaps small,
// and LEB128 spends one byte on a gap under 128. This is why a dense subband
// costs roughly one byte per coefficient position.

/**
 * Ascending index list -> dv1 bytes.
 * ⛔ Input MUST be sorted ascending with no duplicates. A descending pair
 * produces a negative delta, which this encoder cannot represent — it is a
 * caller bug, and it is thrown rather than silently wrapped.
 * ⚠ Bound: indices must be < 2^32. Grid indices are far below that.
 */
export function encPos(idxSorted) {
  const bytes = [];
  let prev = 0;
  for (let i = 0; i < idxSorted.length; i++) {
    let d = idxSorted[i] - prev;
    if (d < 0) throw new Error(`encPos: positions must ascend (index ${i})`);
    prev = idxSorted[i];
    while (d >= 0x80) { bytes.push((d & 0x7F) | 0x80); d = Math.floor(d / 128); }
    bytes.push(d & 0x7F);
  }
  return Uint8Array.from(bytes);
}

/**
 * dv1 bytes -> absolute Uint32 positions.
 * Integrity bounds are ALWAYS on: never write past `count`, and reject a
 * pathological >35-bit varint (it cannot be a real grid index) by resetting the
 * accumulator rather than producing a garbage position.
 */
export function decPos(u8, count) {
  const out = new Uint32Array(count);
  let val = 0, acc = 0, shift = 0, n = 0;
  for (let i = 0; i < u8.length && n < count; i++) {
    const b = u8[i];
    acc += (b & 0x7F) * Math.pow(2, shift);
    if (b & 0x80) { shift += 7; if (shift > 35) { acc = 0; shift = 0; } }
    else { val += acc; out[n++] = val; acc = 0; shift = 0; }
  }
  return out;
}

/**
 * Read a channel's values, whichever payload form it carries.
 * `val_b64` is the wire/JSON form; `val_bin` is the resident binary form used
 * by a server-side store. One choke point so every consumer stays
 * payload-agnostic — the source engine learned this the hard way when a
 * consumer read only `val_b64` and silently scored restored records as zero.
 */
export function chanVal(c) {
  if (c && c.val_bin) {
    const u = c.val_bin instanceof Uint8Array ? c.val_bin : new Uint8Array(c.val_bin);
    return bytesToI16(u);
  }
  return b64ToI16(c.val_b64);
}

export function chanHasVal(c) { return !!(c && (c.val_b64 || c.val_bin)); }

/** Read a channel's positions, whichever payload form and encoding it carries. */
export function decodePositions(c, count) {
  const posBytes = c.pos_bin
    ? (c.pos_bin instanceof Uint8Array ? c.pos_bin : new Uint8Array(c.pos_bin))
    : b64ToBytes(c.pos_b64);
  if (c.pos_enc === 'dv1') return decPos(posBytes, count);
  // Legacy raw-uint32 form, little-endian, kept because old records exist.
  const out = new Uint32Array(count);
  for (let i = 0; i < count && (i * 4 + 3) < posBytes.length; i++) {
    out[i] = (posBytes[i * 4]) | (posBytes[i * 4 + 1] << 8)
           | (posBytes[i * 4 + 2] << 16) | (posBytes[i * 4 + 3] << 24);
  }
  return out;
}
