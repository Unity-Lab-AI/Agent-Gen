import http from 'node:http';
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
    // ask, then make sure: a brain left on the card (9 GB) next to Wan filled the 16 GB and the render sat at step 0
    for (let i = 0; i < 15; i++) {
      await fetch(`${cfg.ollamaUrl}/api/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, keep_alive: 0 }), signal: AbortSignal.timeout(10000) });
      const ps = await (await fetch(`${cfg.ollamaUrl}/api/ps`, { signal: AbortSignal.timeout(5000) })).json();
      if (!(ps.models || []).length) break;
      for (const m of ps.models) {              // whatever is loaded goes, not just the model the hub picked
        await fetch(`${cfg.ollamaUrl}/api/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model: m.name, keep_alive: 0 }), signal: AbortSignal.timeout(10000) }).catch(() => {});
      }
      await new Promise(r => setTimeout(r, 1000));
    }
  } catch {}
}

let abortedAt = 0;
/** Health, waiting up to `timeoutMs` for the engine to come back (it restarts after an abort). */
export async function ready(timeoutMs = 60000) {
  let h = await health();
  for (const until = Date.now() + timeoutMs; !h.ok && Date.now() < until;) { await new Promise(r => setTimeout(r, 1000)); h = await health(); }
  return h;
}

/** Free the card now: cancel, and if the render has not stopped within `graceMs`, abort the engine (it exits and
 *  the app restarts it). Resolves once nothing is rendering. */
export async function stopRender(graceMs = 3000) {
  const { gpu } = await import('../providers/ollama.mjs');
  if (gpu.rendering <= 0) return;
  await cancel();
  for (const until = Date.now() + graceMs; gpu.rendering > 0 && Date.now() < until;) await new Promise(r => setTimeout(r, 100));
  if (gpu.rendering <= 0) return;
  abortedAt = Date.now();
  try { await fetch(`${cfg.videoUrl}/abort`, { method: 'POST', signal: AbortSignal.timeout(3000) }); } catch {}
  for (const until = Date.now() + 10000; gpu.rendering > 0 && Date.now() < until;) await new Promise(r => setTimeout(r, 100));
}

/** Stop the clip in flight at its next step; its clip() call rejects with "cancelled". */
export async function cancel() {
  try { await fetch(`${cfg.videoUrl}/cancel`, { method: 'POST', signal: AbortSignal.timeout(2000) }); } catch {}
}

/** Render a clip from `lookFile` acting out `prompt`. Returns the sidecar's answer ({path, seconds, ...}). */
export async function clip(lookFile, prompt, { frames, seed, fromClip, engine } = {}) {
  const { gpu } = await import('../providers/ollama.mjs');
  gpu.rendering++;                                 // background brain calls wait until this render is done
  try { return await clipRender(lookFile, prompt, { frames, seed, fromClip, engine }); }
  catch (e) { if (Date.now() - abortedAt < 20000) throw new Error('cancelled: video engine aborted'); throw e; }
  finally { gpu.rendering--; }
}
async function clipRender(lookFile, prompt, { frames, seed, fromClip, engine } = {}) {
  const image_b64 = fromClip ? undefined : fs.readFileSync(lookFile).toString('base64');
  // node:http, not fetch: fetch gives up waiting for response headers after 5 minutes ("fetch failed"), and a Wan
  // clip on a fresh look takes longer than that. The render itself is capped by the sidecar; 15 minutes here.
  const body = JSON.stringify({ image_b64, from_clip: fromClip, engine, prompt: `${cfg.clipPrefix} ${prompt}`.trim(), frames: frames || cfg.clipFrames, seed, width: cfg.clipWidth, height: cfg.clipHeight });
  const r = await postLong(`${cfg.videoUrl}/i2v`, body, 900000);
  let j; try { j = JSON.parse(r.text); } catch { j = { error: `video ${r.status}` }; }
  r.ok = r.status >= 200 && r.status < 300;
  if (!r.ok || !j.ok) throw new Error(j.error || `video ${r.status}`);
  return j;
}

/** POST JSON and wait as long as the render takes (no 300 s header timeout). Resolves {status, text}. */
function postLong(url, body, timeoutMs) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const req = http.request({ hostname: u.hostname, port: u.port, path: u.pathname, method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) } }, res => {
      let text = ''; res.setEncoding('utf8');
      res.on('data', d => { text += d; }); res.on('end', () => resolve({ status: res.statusCode, text }));
      res.on('error', reject);
    });
    req.setTimeout(timeoutMs, () => req.destroy(new Error(`video: no answer in ${Math.round(timeoutMs / 60000)} min`)));
    req.on('error', reject);
    req.end(body);
  });
}
