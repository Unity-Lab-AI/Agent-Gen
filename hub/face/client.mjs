// Face sidecar client: hand her every sentence's audio so the lips move with it, and learn how far ahead the
// video runs so the UI can delay the sound to match. Optional: if the sidecar is down the voice still works.
import { cfg } from '../config.mjs';

let lastOk = 0;
export async function health() {
  try {
    const r = await fetch(`${cfg.faceUrl}/health`, { signal: AbortSignal.timeout(2000) });
    const j = await r.json();
    if (j.ok) lastOk = Date.now();
    return j;
  } catch (e) { return { ok: false, error: String(e.message || e) }; }
}
export const isLive = () => Date.now() - lastOk < 15000;

export async function speak(wav_b64, emotion) {
  if (!isLive()) return null;
  try {
    const r = await fetch(`${cfg.faceUrl}/speak`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ wav_b64, emotion, play: cfg.facePlayLocal }), signal: AbortSignal.timeout(5000) });
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

export async function interrupt() {
  if (!isLive()) return;
  try { await fetch(`${cfg.faceUrl}/interrupt`, { method: 'POST', signal: AbortSignal.timeout(2000) }); } catch {}
}

/** Hold her last frame while another engine owns the GPU; /appearance or resume() lets her move again. */
export async function pause() {
  if (!isLive()) return;
  try { await fetch(`${cfg.faceUrl}/pause`, { method: 'POST', signal: AbortSignal.timeout(2000) }); } catch {}
}
export async function resume() {
  if (!isLive()) return;
  try { await fetch(`${cfg.faceUrl}/resume`, { method: 'POST', signal: AbortSignal.timeout(2000) }); } catch {}
}

/** Make an image or clip file her live face; `extend` appends a clip to her current reel instead. Returns the sidecar's answer or null. */
export async function appearance(file, { extend = false } = {}) {
  if (!isLive()) return null;
  try {
    const r = await fetch(`${cfg.faceUrl}/appearance`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: file, extend, max_frames: extend ? cfg.reelMaxFrames : 0 }), signal: AbortSignal.timeout(60000) });
    return r.ok ? await r.json() : { ok: false, error: (await r.json().catch(() => ({}))).error || `face ${r.status}` };
  } catch (e) { return { ok: false, error: String(e.message || e) }; }
}

export async function emotion(e) {
  if (!isLive()) return;
  try { await fetch(`${cfg.faceUrl}/emotion`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ emotion: e }), signal: AbortSignal.timeout(2000) }); } catch {}
}
