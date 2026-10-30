/**
 * index.js — the codec's public surface.
 *
 * ⛔ PLATFORM LAW: importing this module pulls in cdf97.js, bytes.js, field.js
 * and audio.js and NOTHING ELSE. No dependencies, no `node:` builtins, no DOM,
 * no filesystem. The same file loads on an S23 browser and in Node.
 * `U3E-0.6` proves that rather than trusting it.
 *
 * Anything that needs the outside world — reading a PNG, writing a file — lives
 * in codec/tools/ and is Node-only by design. If a `node:` import ever appears
 * below this line, the phone build is broken and nobody will notice until the
 * phone loads it.
 */

export {
  A97, B97, G97, D97, K97,
  levelSizes, fwd1d, inv1d, fwd2d, idwt2,
  rgbToYCbCr, ycbcrToRGB, padDim,
} from './cdf97.js';

export {
  bytesToB64, b64ToBytes, i16ToBytes, bytesToI16, i16ToB64, b64ToI16,
  encPos, decPos, chanVal, chanHasVal, decodePositions,
} from './bytes.js';

export {
  FIELD_MODEL, EQ_TOL, EQ_KMIN, EQ_LONG_EDGE,
  equationalize, equationalizeStaged, reconstruct, termsAboveThreshold,
  describeEquational, perceptCosine,
} from './field.js';

export {
  AUDIO_MODEL, VOX_BANK_VERSION, CHUNK, AUDIO_TOL, AUDIO_KMIN, MAX_SECONDS,
  perceiveAudio, reconstructAudio, concatAudio, describeAudio,
} from './audio.js';

/**
 * Format version of the RECORD SHAPE this codec reads and writes.
 * ⛔ Bump this when the record layout changes, never when the maths is merely
 * reimplemented. Fields banked under an older version must be re-encoded, not
 * reinterpreted.
 */
export const U3E_FIELD_VERSION = 1;
