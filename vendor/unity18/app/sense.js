/**
 * sense.js — `U3E-5.5` / `5.6` / `8.8`. What she is shown and what she hears,
 * turned into equations ON THE DEVICE.
 *
 * ⭐ THE PROPERTY THAT MAKES THIS WORTH BUILDING BEFORE THE MODEL EXISTS
 *   The picture becomes coefficients **before it is ever sent**. The wire
 *   carries a field, never a photograph; the microphone's output leaves as
 *   field A, never as audio. On a phone that is a privacy property and a
 *   bandwidth property at once, and it is true today regardless of whether
 *   anything can yet understand the result.
 *
 * ⛔ AND THE HALF THAT DOES NOT EXIST IS SAID OUT LOUD
 *   `see` and `hear` are ABSENT capabilities. This module produces a perfectly
 *   good field and the model refuses it with 501. That is the honest state:
 *   the input path is real, the understanding is not trained. Nothing here
 *   pretends otherwise, and nothing silently drops the field to make the UI
 *   look successful.
 *
 * ⚠ Vision is the input side of drawing and STT the input side of speaking —
 *   free in REPRESENTATION, not in training. `U3E-4B.1` and `U3E-4B.3` still
 *   need paired data.
 *
 * ⛔ PLATFORM LAW: browser APIs only, no dependencies. Runs on the S23.
 */

import { equationalize, perceiveAudio, describeEquational } from '/codec/js/index.js';

/**
 * Long edge cap for anything encoded on-device.
 * ⚠ Not a style choice: a 12-megapixel phone photo at full size would take a
 * very long time in `fwd2d` on a handset and teach nothing a 1024px one does
 * not. `U3E-0.7` replaces this guess with a measured ladder.
 */
export const LONG_EDGE = 1024;

/** A bitmap source (File, Blob, ImageBitmap, video frame) -> field C. */
export async function imageToField(src, { longEdge = LONG_EDGE } = {}) {
  const bitmap = src instanceof ImageBitmap ? src : await createImageBitmap(src);
  const s = Math.min(1, longEdge / Math.max(bitmap.width, bitmap.height));
  const w = Math.max(1, Math.round(bitmap.width * s));
  const h = Math.max(1, Math.round(bitmap.height * s));

  const cv = new OffscreenCanvas(w, h);
  const cx = cv.getContext('2d');
  cx.imageSmoothingEnabled = true;
  cx.drawImage(bitmap, 0, 0, w, h);
  const id = cx.getImageData(0, 0, w, h);

  const t0 = performance.now();
  const field = equationalize({ width: w, height: h, data: id.data });
  const encodeMs = performance.now() - t0;

  if (bitmap.close) bitmap.close();
  return {
    field,
    encodeMs,
    percept: describeEquational(field, 64),
    // ⭐ what the wire would carry, versus what it would have carried
    wireBytes: JSON.stringify(field).length,
    rawBytes: w * h * 3,
  };
}

/**
 * `U3E-8.8` — camera. ⛔ OFF BY DEFAULT and the caller must show an
 * unmistakable indicator while it runs; a camera that can be on without being
 * obviously on is not a feature.
 */
export function createCamera() {
  let stream = null, video = null;

  return {
    async start(facing = 'user') {
      if (stream) return { ok: true };
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        return { ok: false, reason: 'this browser has no camera API' };
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: facing, width: { ideal: 1280 } }, audio: false,
        });
      } catch (e) {
        return { ok: false, reason: e.name === 'NotAllowedError'
          ? 'camera permission was refused' : `camera unavailable: ${e.message}` };
      }
      video = document.createElement('video');
      video.srcObject = stream;
      video.playsInline = true;
      video.muted = true;
      await video.play();
      return { ok: true };
    },

    /** One frame -> field C, encoded here. The frame never leaves as pixels. */
    async grab() {
      if (!video) throw new Error('camera is not running');
      const bmp = await createImageBitmap(video);
      return imageToField(bmp);
    },

    isRunning() { return !!stream; },

    stop() {
      if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
      if (video) { video.srcObject = null; video = null; }
    },
  };
}

/**
 * `U3E-5.6` — push-to-talk. Captured PCM -> field A, encoded on the device.
 *
 * ⚠ Resamples to 24 kHz because the codec's chunking and the voice bank are
 * defined at that rate. A 48 kHz field would be a different thing wearing the
 * same shape.
 */
export function createRecorder({ sampleRate = 24000 } = {}) {
  let ctx = null, stream = null, node = null, source = null;
  let chunks = [], recording = false;

  return {
    async start() {
      if (recording) return { ok: true };
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        return { ok: false, reason: 'this browser has no microphone API' };
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
        });
      } catch (e) {
        return { ok: false, reason: e.name === 'NotAllowedError'
          ? 'microphone permission was refused' : `microphone unavailable: ${e.message}` };
      }
      ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate });
      source = ctx.createMediaStreamSource(stream);
      // ScriptProcessor is deprecated but universally present, including on the
      // S23's browser; an AudioWorklet needs a separate module file for no gain
      // at this buffer size.
      node = ctx.createScriptProcessor(4096, 1, 1);
      chunks = [];
      node.onaudioprocess = e => {
        if (!recording) return;
        chunks.push(Float32Array.from(e.inputBuffer.getChannelData(0)));
      };
      source.connect(node);
      node.connect(ctx.destination);
      recording = true;
      return { ok: true, sampleRate: ctx.sampleRate };
    },

    /** Stop and encode. Returns the field, never the audio. */
    stop() {
      if (!recording) return null;
      recording = false;
      let n = 0;
      for (const c of chunks) n += c.length;
      const pcm = new Float32Array(n);
      let off = 0;
      for (const c of chunks) { pcm.set(c, off); off += c.length; }

      const rate = ctx ? ctx.sampleRate : sampleRate;
      if (node) { node.disconnect(); node.onaudioprocess = null; node = null; }
      if (source) { source.disconnect(); source = null; }
      if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
      if (ctx) { ctx.close().catch(() => {}); ctx = null; }
      chunks = [];

      if (!n) return null;
      const t0 = performance.now();
      const field = perceiveAudio(pcm, rate);
      return {
        field,
        encodeMs: performance.now() - t0,
        seconds: n / rate,
        wireBytes: JSON.stringify(field).length,
        rawBytes: n * 4,
      };
    },

    isRecording() { return recording; },
  };
}
