// Appearance engine, image half: render what she asked to show, with her face locked to her likeness, and
// save it where the UI and the face sidecar can read it.
import fs from 'node:fs';
import path from 'node:path';
import { cfg, REPO } from '../config.mjs';

// the app keeps renders in its data root (AGENTGEN_RUN); a dev checkout under .run/
const OUT = process.env.AGENTGEN_RUN ? path.join(process.env.AGENTGEN_RUN, 'looks') : path.join(REPO, '.run', 'looks');
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
// adult-age terms only; anatomy and quality negatives removed
const NEG = 'child, teen, underage, childlike, young girl';

/** True when the look changes who she looks like (hair colour, makeup, skin, ethnicity, "no goth"), not just what
 *  she wears or does. Then the old face lock and the old picture must not carry over: they kept the goth hair and
 *  makeup through "naturally brown without any streaks". */
const RESTYLE = new RegExp([
  /\b(brown|blonde?|black|red|auburn|grey|gray|silver|pink|blue|green|purple|white|ginger|dark|light|platinum|copper|chestnut|honey)[- ](hair|haired)\b/,
  /\bhair (is|that is)\b/, /\b(no|without( any)?) (streaks|goth|makeup|make-up|eyeliner)\b/,
  /\b(blonde|brunette|redhead|ginger)\b/, /\b(makeup|make-up|eyeliner|mascara|lipstick|freckles)\b/,
  /\b(skin|complexion)\b/, /\b(caucasian|african|asian|latina|hispanic|indian|arab|nubian|nile|ebony|ethnicity)\b/,
  /\b(white|black|brown) (woman|girl|lady|beauty)\b/, /\bnatural look\b/,
  // someone else entirely: another sex, age or kind of body ("a 40 year old man")
  /\b(man|men|male|guy|dude|boy|gentleman|husband|father|dad|grandpa|grandfather|grandma|grandmother|elderly|beard|bearded)\b/,
  /\b\d{2}[- ]year[- ]old\b/, /\b(old|older|middle[- ]aged) (woman|lady|man)\b/,
].map(r => r.source).join('|'), 'i');
export const isRestyle = prompt => RESTYLE.test(String(prompt || ''));

/** Render a look, fresh from her words. Her face lock (her likeness, or `faceFile` after a restyle) keeps her her;
 *  a restyle renders without it and `faceFile` then carries the new face into later looks. */
export async function render(prompt, { width, height, seed, strength, sourceFile, restyle = false, faceFile, plain = false, faceBox } = {}) {
  // plain = a picture of anything ([[pic]]): exactly her words, no identity, no face lock. A restyle drops the
  // identity prefix too: "a 40 year old man" must not be glued to "photo of Unity".
  const full = (plain ? prompt : restyle ? `${prompt}, ${cfg.lookSuffix}` : `${cfg.lookPrefix} ${prompt}, ${cfg.lookSuffix}`).replace(/\s+/g, ' ').trim();
  const face = faceFile && fs.existsSync(faceFile) ? fs.readFileSync(faceFile).toString('base64') : faceRef();
  const body = { prompt: full, width: width || cfg.lookWidth, height: height || cfg.lookHeight, steps: cfg.lookSteps,
    guidance: cfg.lookGuidance, seed: seed || undefined, face: restyle || plain ? undefined : (face || undefined), face_scale: cfg.lookFaceScale, negative: NEG };
  // A look change that keeps who she is ("take your top off", a new outfit, writing on her skin) repaints only her
  // body below the chin (OpenCV finds her face in the sidecar): face, hair and the room stay pixel for pixel. Plain
  // img2img at 0.75 repainted the whole frame and gave the operator a different woman every time.
  // A restyle (someone else entirely) and a [[pic]] render fresh.
  let endpoint = '/txt2img';
  const src = editSource(sourceFile, plain || restyle);
  if (src) {
    body.image = fs.readFileSync(src).toString('base64');
    body.strength = strength ?? cfg.lookStrength;
    body.max_side = cfg.lookMaxSide;
    // below her chin (her face box from the face sidecar); without one the image sidecar guesses
    body.box = faceBox ? [0, Math.min(0.9, faceBox[3] + (faceBox[3] - faceBox[1]) * 0.12), 1, 1] : 'body';
    endpoint = '/inpaint';
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

/** The picture an edit starts from (her current look, else her default one); null for a fresh render. */
export const editSource = (sourceFile, fresh) => fresh ? null : [sourceFile, cfg.lookBase].find(f => f && fs.existsSync(f)) || null;

export const looksDir = OUT;
