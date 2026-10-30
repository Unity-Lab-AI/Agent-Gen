// Appearance engine, motion half: turn her current look into a clip of her doing what she was told, then the
// face sidecar plays it as her live video with her lips on top.
import fs from 'node:fs';
import { cfg } from '../config.mjs';

export async function health() {
  try { const r = await fetch(`${cfg.videoUrl}/health`, { signal: AbortSignal.timeout(2000) }); return await r.json(); }
  catch (e) { return { ok: false, error: String(e.message || e) }; }
}

/** Free the GPU neighbours a clip needs: the image engine and the brain (it reloads on the next turn). */
export async function makeRoom() {
  try { await fetch(`${cfg.imageUrl}/unload`, { method: 'POST', signal: AbortSignal.timeout(10000) }); } catch {}
  try {
    const { pickModel } = await import('../providers/ollama.mjs');
    const model = await pickModel();
    await fetch(`${cfg.ollamaUrl}/api/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, keep_alive: 0 }), signal: AbortSignal.timeout(10000) });
  } catch {}
}

/** Stop the clip in flight at its next step; its clip() call rejects with "cancelled". */
export async function cancel() {
  try { await fetch(`${cfg.videoUrl}/cancel`, { method: 'POST', signal: AbortSignal.timeout(2000) }); } catch {}
}

/** Render a clip from `lookFile` acting out `prompt`. Returns the sidecar's answer ({path, seconds, ...}). */
export async function clip(lookFile, prompt, { frames, seed, fromClip, engine } = {}) {
  const image_b64 = fromClip ? undefined : fs.readFileSync(lookFile).toString('base64');
  const r = await fetch(`${cfg.videoUrl}/i2v`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_b64, from_clip: fromClip, engine, prompt: `${cfg.clipPrefix} ${prompt}`.trim(), frames: frames || cfg.clipFrames, seed, width: cfg.clipWidth, height: cfg.clipHeight }),
    signal: AbortSignal.timeout(900000) });
  const j = await r.json().catch(() => ({ error: `video ${r.status}` }));
  if (!r.ok || !j.ok) throw new Error(j.error || `video ${r.status}`);
  return j;
}
