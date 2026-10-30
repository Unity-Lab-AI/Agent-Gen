// Appearance engine, image half: render what she asked to show, with her face locked to her likeness, and
// save it where the UI and the face sidecar can read it.
import fs from 'node:fs';
import path from 'node:path';
import { cfg, REPO } from '../config.mjs';

const OUT = path.join(REPO, '.run', 'looks');
fs.mkdirSync(OUT, { recursive: true });

let faceRefB64 = null;
function faceRef() {
  if (faceRefB64 !== null) return faceRefB64;
  try { faceRefB64 = fs.readFileSync(cfg.lookFaceRef).toString('base64'); }
  catch { faceRefB64 = ''; }
  return faceRefB64;
}

export async function health() {
  try { const r = await fetch(`${cfg.imageUrl}/health`, { signal: AbortSignal.timeout(2000) }); return await r.json(); }
  catch (e) { return { ok: false, error: String(e.message || e) }; }
}

/**
 * Render a look. prompt = what she wrote in the tag; her identity anchors are prepended so the picture is her.
 * Returns {file, url, seed, seconds, prompt} or throws.
 */
export async function render(prompt, { width, height, seed, strength, sourceFile } = {}) {
  const full = `${cfg.lookPrefix} ${prompt}, ${cfg.lookSuffix}`.replace(/\s+/g, ' ').trim();
  const body = { prompt: full, width: width || cfg.lookWidth, height: height || cfg.lookHeight, steps: cfg.lookSteps,
    guidance: cfg.lookGuidance, seed: seed || undefined, face: faceRef() || undefined, face_scale: cfg.lookFaceScale };
  let endpoint = '/txt2img';
  if (sourceFile && fs.existsSync(sourceFile)) {       // evolve the current look instead of starting over
    body.image = fs.readFileSync(sourceFile).toString('base64');
    body.strength = strength ?? cfg.lookStrength;
    body.face = true;                                   // keep the face of the source image
    endpoint = '/img2img';
  }
  const r = await fetch(`${cfg.imageUrl}${endpoint}`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal: AbortSignal.timeout(180000) });
  if (!r.ok) { let e = `image ${r.status}`; try { e = (await r.json()).error || e; } catch {} throw new Error(e); }
  const png = Buffer.from(await r.arrayBuffer());
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const file = path.join(OUT, `look-${id}.png`);
  fs.writeFileSync(file, png);
  return { file, url: `/looks/look-${id}.png`, seed: Number(r.headers.get('x-seed')), seconds: Number(r.headers.get('x-seconds')), prompt: full };
}

export const looksDir = OUT;
