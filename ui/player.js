// Timed playback: WAV clips in order, with the viseme track of each clip surfaced as events while it plays.
// The M3 face renderer subscribes to `onViseme`; the placeholder mouth in app.js does the same.
export function createPlayer({ onViseme = () => {}, onSpeakingChange = () => {}, onClipStart = () => {} } = {}) {
  let ctx = null;
  const queue = [];        // decoded clips waiting or playing: {id, buffer, visemes, startAt, source, text}
  let nextAt = 0;
  let speaking = false;
  let raf = 0;
  let epoch = 0;

  function ensureCtx() {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }

  function b64ToBuf(b64) {
    const bin = atob(b64);
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return u8.buffer;
  }

  async function enqueue(clip) {
    const myEpoch = epoch;
    const c = ensureCtx();
    let buffer;
    try { buffer = await c.decodeAudioData(b64ToBuf(clip.wav_b64)); }
    catch (e) { console.warn('decode failed', e); return; }
    if (myEpoch !== epoch) return;            // interrupted while decoding
    const now = c.currentTime;
    const startAt = Math.max(now + 0.03, nextAt);
    const source = c.createBufferSource();
    source.buffer = buffer;
    source.connect(c.destination);
    const item = { id: clip.seq, buffer, visemes: clip.visemes || [], startAt, source, text: clip.text, done: false };
    source.onended = () => { item.done = true; prune(); };
    source.start(startAt);
    nextAt = startAt + buffer.duration + 0.02;
    queue.push(item);
    setSpeaking(true);
    if (!raf) tick();
  }

  function prune() {
    while (queue.length && queue[0].done) queue.shift();
    if (!queue.length) { setSpeaking(false); onViseme({ v: 'sil', open: 0 }); }
  }

  function setSpeaking(v) { if (speaking !== v) { speaking = v; onSpeakingChange(v); } }

  let lastViseme = null, lastClip = null;
  function tick() {
    raf = requestAnimationFrame(tick);
    if (!ctx || !queue.length) { if (!queue.length) { cancelAnimationFrame(raf); raf = 0; } return; }
    const now = ctx.currentTime;
    const item = queue.find(q => !q.done && now >= q.startAt && now < q.startAt + q.buffer.duration);
    if (!item) { if (lastViseme !== 'sil') { lastViseme = 'sil'; onViseme({ v: 'sil', open: 0 }); } return; }
    if (lastClip !== item) { lastClip = item; onClipStart(item); }
    const t = now - item.startAt;
    let seg = null;
    for (const s of item.visemes) { if (t >= s.t0 && t < s.t1) { seg = s; break; } }
    const v = seg ? seg.v : 'sil';
    if (v !== lastViseme || seg) { lastViseme = v; onViseme(seg || { v: 'sil', open: 0, t }); }
  }

  function stop() {
    epoch++;
    for (const q of queue) { try { q.source.stop(); } catch {} q.done = true; }
    queue.length = 0;
    nextAt = 0;
    setSpeaking(false);
    onViseme({ v: 'sil', open: 0 });
  }

  return { enqueue, stop, isSpeaking: () => speaking, unlock: ensureCtx };
}
