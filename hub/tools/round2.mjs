// The round-two prompts exactly as they ran (the operator's winners), new seeds each time.
// Usage: node hub/tools/round2.mjs [count] [outDir]
import fs from 'node:fs';
import path from 'node:path';
import { cfg, REPO } from '../config.mjs';

const n = Number(process.argv[2] || 9);
const out = process.argv[3] || path.join(REPO, '.run', 'candidates', 'round2-again');
fs.mkdirSync(out, { recursive: true });
const LIKE = {
  L2: 'shoulder length black bob with a pink fringe, soft round face, big green eyes, button nose, light freckles, pale skin',
  L4: 'wavy black hair with pastel pink tips, strong brows, almond-shaped brown eyes, full pouty lips, fair skin with a warm flush',
  L8: 'messy black shag cut with pink highlights, sleepy hooded green eyes, sharp nose, wide smirk, fair skin, ink tattoos down her arms',
};
const BODY = 'slim fit body, natural medium breasts, toned flat stomach with soft subtle abs, narrow waist, gently rounded hips, ' +
  'round firm butt, long slender toned legs, slender arms, delicate collarbones';
const FULL = ['full body head to toe, standing facing the camera, arms relaxed at her sides, feet visible',
  'full body head to toe, standing, hands on her hips, feet visible', 'full body head to toe, three-quarter turn, weight on one leg, feet visible'];
const NEG = 'child, teen, underage, childlike, young girl, two people, multiple people, twins, duplicate, cropped body, out of frame, phone, holding phone, camera, selfie, hands covering face, raised hand, ' +
  'middle finger, gesture, holding object, extra hands, floating hands, towel, towel on head, hat, hood, headwear, cropped feet, ' +
  'cut off legs, black eyes, all black eyes, black sclera, dark sclera, empty eye sockets, heavy mascara clumps, extra fingers, ' +
  'missing fingers, fused fingers, mutated hands, deformed hands';
// SEED=n holds one winner's seed; SIZES=portrait,landscape renders each pose in both
const SIZE = { portrait: [512, 896], landscape: [768, 512] };   // 896 wide drew two of her
// REF=<png> holds the winner's look through the face adapter at a light scale while the seed changes, so the
// poses really differ (a fixed seed gave three identical copies of the original)
const REF = process.env.REF ? fs.readFileSync(process.env.REF).toString('base64') : null;
const sizes = (process.env.SIZES || 'portrait').split(',');
const keys = (process.env.PICK || 'L2,L4,L8').split(',');
for (let i = 0; i < n; i++) {
  const k = keys[i % keys.length];
  const sz = sizes[Math.floor(i / keys.length) % sizes.length];
  const pose = FULL[Math.floor(i / (keys.length * sizes.length)) % FULL.length];
  const prompt = `photo of one 25 year old American woman alone, solo, ${LIKE[k]}, ${BODY}, ${pose}, photo shoot, bedroom, soft pink neon light, ` +
    `bright clear eyes with clean white sclera, ${cfg.lookSuffix}`;
  const body = { prompt, width: SIZE[sz][0], height: SIZE[sz][1], ...(process.env.SEED ? { seed: Number(process.env.SEED) } : {}), ...(REF ? { face: REF, face_scale: Number(process.env.REF_SCALE || 0.4) } : {}), steps: cfg.lookSteps, guidance: cfg.lookGuidance, negative: NEG };
  const r = await fetch(`${cfg.imageUrl}/txt2img`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal: AbortSignal.timeout(300000) });
  if (!r.ok) { console.error(`#${i + 1} failed: ${r.status} ${await r.text()}`); continue; }
  const file = path.join(out, `r2-${k}-${sz}-${String(i + 1).padStart(2, '0')}-seed${r.headers.get('x-seed')}.png`);
  fs.writeFileSync(file, Buffer.from(await r.arrayBuffer()));
  console.log(file);
}
