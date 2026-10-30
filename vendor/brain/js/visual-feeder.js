// visual-feeder.js — Unity's VISUAL INTAKE: ships what her eyes actually
// receive (camera frames + generated images rendered in chat) to the brain
// server as tiny ≤96×96 RGBA frames over WS ('visual_frame'). The server
// equationalizes each frame into a full-color field C and binds it to the
// concepts active when she saw it (server/brain-server/visual-memory.js) —
// the grounding that lets her mind's eye RECALL and RECOMBINE real percepts
// instead of rendering thoughts de-novo.
//
// STANDALONE BY DESIGN: loaded raw by index.html as its own module (NOT part
// of app.bundle.js) so it deploys with a plain file overlay — no esbuild
// rebuild required on the box. It opens its own lightweight WS to the same
// brain (public lane) instead of reaching into the bundle's private scope.
//
// PRIVACY + SAFETY:
//   - camera capture ONLY when permission is ALREADY granted to this page
//     (navigator.permissions query) — this module never prompts.
//   - frames are 96×96 thumbnails, paced (camera 8s, images 5s min gap),
//     ~48KB base64 each — negligible on the socket, hard-bounded server-side.
//   - generated-image capture is best-effort cross-origin: images load with
//     crossOrigin='anonymous'; if the CDN denies CORS the canvas taints and
//     the capture silently skips. Never breaks the page.

const SIDE = 192;                    // MS.EXT — retina raised 96→192 (was crushing her own 1024² renders to 96²; ~196KB b64/frame at 5-8s pacing, trivial vs the 2GB WS ceiling)
const CAMERA_INTERVAL_MS = 8000;
const IMAGE_MIN_GAP_MS = 5000;
const RECONNECT_MS = 30000;

const isLocal = (typeof location !== 'undefined') && (
  location.hostname === 'localhost' || location.hostname === '127.0.0.1'
  || location.hostname === '[::1]' || location.hostname === ''
  || location.protocol === 'file:');
// WHERE THE BRAIN IS. `js/brain-origin.js` (loaded by index.html before this
// module) resolves the configured brain origin — on the public site that is
// the tunnel, not the static host. This file still built its own URL from
// `location.host`, so the live page dialed `wss://theunitybrain.com/ws` (a
// 404 from GitHub Pages) beside the real connection and retried it every
// 30 s. The old expression stays as the no-helper path, so a page without
// the helper behaves exactly as before.
const WS_URL = (typeof unityBrainWs === 'function')
  ? unityBrainWs('ws')
  : (isLocal
      ? 'ws://localhost:7525'
      : (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');

let ws = null;
let wsReady = false;

function connect() {
  try { ws = new WebSocket(WS_URL); } catch { setTimeout(connect, RECONNECT_MS); return; }
  ws.onopen = () => { wsReady = true; };
  ws.onclose = () => { wsReady = false; setTimeout(connect, RECONNECT_MS); };
  ws.onerror = () => { /* onclose handles the retry */ };
  // intake-only socket — inbound broadcasts are ignored on purpose.
  ws.onmessage = () => {};
}

function sendFrame(source, imageData, label) {
  if (!wsReady || !ws || ws.readyState !== 1) return;
  // chunked btoa — String.fromCharCode.apply on the full 36KB array can
  // blow the call-stack argument limit on some engines.
  const u8 = new Uint8Array(imageData.data.buffer, imageData.data.byteOffset, imageData.data.byteLength);
  let bin = '';
  const CH = 0x8000;
  for (let i = 0; i < u8.length; i += CH) bin += String.fromCharCode.apply(null, u8.subarray(i, i + CH));
  try {
    ws.send(JSON.stringify({
      type: 'visual_frame', source,
      w: imageData.width, h: imageData.height,
      rgba_b64: btoa(bin),
      label: label ? String(label).slice(0, 160) : null,
    }));
  } catch { /* socket raced closed — next frame retries */ }
}

// cover-crop any drawable source onto a SIDE×SIDE canvas → ImageData.
const _cv = document.createElement('canvas');
_cv.width = SIDE; _cv.height = SIDE;
const _cx = _cv.getContext('2d', { willReadFrequently: true });
function capture(drawable, sw, sh) {
  if (!sw || !sh) return null;
  const s = Math.max(SIDE / sw, SIDE / sh);
  const dw = sw * s, dh = sh * s;
  _cx.imageSmoothingEnabled = true;
  _cx.clearRect(0, 0, SIDE, SIDE);
  _cx.drawImage(drawable, (SIDE - dw) / 2, (SIDE - dh) / 2, dw, dh);
  try { return _cx.getImageData(0, 0, SIDE, SIDE); }
  catch { return null; }   // cross-origin taint → skip silently
}

// ── camera → her eyes ───────────────────────────────────────────────────────
// Opens its own stream ONLY when the page already holds camera permission
// (granted via the app's own consent flow) — resolves silently, never prompts.
// Unlabeled frames bind server-side to what she's thinking in the moment.
async function startCamera() {
  try {
    if (!navigator.mediaDevices || !navigator.permissions) return;
    const st = await navigator.permissions.query({ name: 'camera' }).catch(() => null);
    if (!st) return;
    if (st.state !== 'granted') {
      st.onchange = () => { if (st.state === 'granted') startCamera(); };
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 320 }, height: { ideal: 240 } },
    });
    const vid = document.createElement('video');
    vid.muted = true; vid.playsInline = true; vid.autoplay = true;
    vid.srcObject = stream; vid.style.display = 'none';
    document.body.appendChild(vid);
    // DEAD-AIR GATES. A page can hold camera permission while the
    // "camera" is dead: a muted/ended track, a covered lens, or a virtual
    // cam serving a static "no signal" placeholder. Those are NOT sight —
    // shipping them bound the same dead-air graphic to every concept she
    // was thinking, colonizing her visual memory and hogging the viewer.
    //   (a) track-liveness: eyes are CLOSED when the track isn't live;
    //   (b) variance: near-uniform frames (dark room / blank wall) never ship
    //       (client-side mirror of the server blank gate — saves the socket);
    //   (c) STATIC-FRAME dedup: a real camera never produces two pixel-
    //       identical captures (sensor noise guarantees drift); a frozen or
    //       placeholder source always does. Identical hash → ship NOTHING.
    const track = stream.getVideoTracks ? stream.getVideoTracks()[0] : null;
    let _lastFrameHash = 0;
    setInterval(() => {
      if (vid.readyState < 2 || !vid.videoWidth) return;
      if (track && (track.readyState !== 'live' || track.muted)) return;   // eyes closed
      const img = capture(vid, vid.videoWidth, vid.videoHeight);
      if (!img) return;
      const d = img.data;
      let sum = 0, sumSq = 0, cnt = 0, h = 5381;
      for (let i = 0; i < d.length; i += 4 * 7) {   // stride-sample every 7th pixel
        const l = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
        sum += l; sumSq += l * l; cnt++;
        h = ((h << 5) + h + ((d[i] << 16) ^ (d[i + 1] << 8) ^ d[i + 2])) >>> 0;
      }
      if (!cnt) return;
      const mean = sum / cnt;
      const std = Math.sqrt(Math.max(0, sumSq / cnt - mean * mean));
      if (std < 12) return;                          // blank/dark — not a percept
      if (h === _lastFrameHash) return;              // pixel-identical = dead air / frozen source
      _lastFrameHash = h;
      sendFrame('camera', img, null);
    }, CAMERA_INTERVAL_MS);
  } catch { /* no camera / denied mid-flight — her eyes just stay closed */ }
}

// ── generated images → her eyes ─────────────────────────────────────────────
// Watches the DOM for Pollinations renders (the chat panel's <img> bubbles).
// The prompt IS the label — decoded straight out of the generation URL path
// (…/image/{encodeURIComponent(prompt)}?…), so what she MADE binds to the
// words she made it from.
const _seenUrls = new Set();
let _lastImageAt = 0;

function promptFromUrl(url) {
  try {
    // ⛔ TWO LABEL BUGS made images bind to the wrong
    // words: (1) only the legacy /image/ path matched, so current /prompt/
    // renders returned NULL labels and the server fused them with whatever
    // word she was THINKING; (2) the label was the WHOLE prompt — subject +
    // association words + mood words — and the server bound the image under
    // up to six of them. Both URL shapes match now, and the label is the
    // SUBJECT ONLY: the prompt's first comma-segment (the request base —
    // every steering/mood tail lives after commas by construction).
    const m = /\/(?:image|prompt)\/([^?]+)/.exec(url);
    if (!m) return null;
    const full = decodeURIComponent(m[1]).replace(/\+/g, ' ');
    return full.split(',')[0].trim().slice(0, 80) || null;
  } catch { return null; }
}

function harvestImage(el) {
  const url = el.currentSrc || el.src || '';
  if (!url || !/pollinations/i.test(url) || _seenUrls.has(url)) return;
  _seenUrls.add(url);
  if (_seenUrls.size > 200) _seenUrls.clear();
  const now = Date.now();
  if (now - _lastImageAt < IMAGE_MIN_GAP_MS) return;
  _lastImageAt = now;
  // fresh crossOrigin load — the chat <img> has no crossorigin attribute so
  // its pixels are tainted; an anonymous re-request (served from HTTP cache
  // when headers allow) gives a readable copy.
  const img = new Image();
  img.crossOrigin = 'anonymous';
  img.onload = () => {
    const data = capture(img, img.naturalWidth, img.naturalHeight);
    if (data) sendFrame('image', data, promptFromUrl(url));
  };
  img.onerror = () => { /* CORS denied / dead URL — skip */ };
  img.src = url;
}

function watchImages() {
  const mo = new MutationObserver((muts) => {
    for (const m of muts) {
      for (const n of m.addedNodes) {
        if (!(n instanceof Element)) continue;
        if (n.tagName === 'IMG') { n.addEventListener('load', () => harvestImage(n), { once: true }); harvestImage(n); }
        else if (n.querySelectorAll) {
          for (const img of n.querySelectorAll('img')) {
            img.addEventListener('load', () => harvestImage(img), { once: true });
            harvestImage(img);
          }
        }
      }
    }
  });
  mo.observe(document.body, { childList: true, subtree: true });
}

connect();
startCamera();
if (document.body) watchImages();
else document.addEventListener('DOMContentLoaded', watchImages, { once: true });
