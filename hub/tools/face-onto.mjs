// Put her original face and hair (assets/portrait/unity-face.jpg) onto picked base pictures: only the head
// region is repainted, the body and room stay as they are.
// Usage: node hub/tools/face-onto.mjs <outDir> <image> [image...]   (BOX=x0,y0,x1,y1 fractions, STRENGTH=0.85)
import fs from 'node:fs';
import path from 'node:path';
import { cfg } from '../config.mjs';

const [out, ...files] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const box = (process.env.BOX || '0.12,0,0.88,0.36').split(',').map(Number);
const face = fs.readFileSync(cfg.lookFaceRef).toString('base64');
const prompt = 'photo of a 25 year old American woman, long straight jet black hair with hot pink streaks framing her face, ' +
  'soft oval face, bright blue eyes with clean white sclera, thin black eyeliner, warm playful smile, fair skin with a light natural flush, natural skin texture, visible pores, ' + cfg.lookSuffix;
for (const f of files) {
  const body = { prompt, image: fs.readFileSync(f).toString('base64'), box, strength: Number(process.env.STRENGTH || 0.85),
    max_side: 896, steps: cfg.lookSteps, guidance: cfg.lookGuidance, face, face_scale: 0.5,
    negative: 'child, teen, underage, childlike, young girl, auburn hair, brown hair, blonde hair, all pink hair, black eyes, black sclera, plastic skin, porcelain skin, waxy skin, airbrushed, doll, smooth skin, cgi' };
  const r = await fetch(`${cfg.imageUrl}/inpaint`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal: AbortSignal.timeout(300000) });
  if (!r.ok) { console.error(`${path.basename(f)} failed: ${r.status} ${await r.text()}`); continue; }
  const dest = path.join(out, 'face-' + path.basename(f));
  fs.writeFileSync(dest, Buffer.from(await r.arrayBuffer()));
  console.log(dest);
}
