// Candidate base pictures of her: fresh txt2img with her face lock, no clothing words, for the operator to pick one
// as the image every start is built from. Usage: node hub/tools/gen-selfies.mjs [count] [outDir]
import fs from 'node:fs';
import path from 'node:path';
import { cfg, REPO } from '../config.mjs';

const n = Number(process.argv[2] || 8);
// PICK=2,4,8 renders only those likenesses (1-based), each head to toe; FULL=1 forces head-to-toe standing poses
const PICK = (process.env.PICK || '').split(',').filter(Boolean).map(x => Number(x) - 1);
// KNEES=1 frames her from the top of her head down to her knees; SEED=n repeats a picture's seed
const KNEES = ['three-quarter shot framed from the top of her head down to just below her knees, standing facing the camera, arms relaxed at her sides',
  'three-quarter shot from the top of her head to her knees, standing, hands on her hips',
  'three-quarter shot from head to knees, slight turn, weight on one leg'];
// VARY=1: one picture's seed (SEED, held fixed) in a spread of poses, angles, stances and zooms, never a tight mug shot
// written exactly like the round-two winners (the operator: "round two winners are how the prompts should be styled"):
// "full body head to toe, <stance>, feet visible"; only the stance and camera angle change
const VARY = ['full body head to toe, standing facing the camera, arms relaxed at her sides, feet visible',
  'full body head to toe, standing, hands on her hips, feet visible', 'full body head to toe, three-quarter turn, weight on one leg, feet visible',
  'full body head to toe, turned to the left, looking at the camera, feet visible', 'full body head to toe, turned to the right, one hand on her hip, feet visible',
  'full body head to toe, seen from slightly above, standing, feet visible', 'full body head to toe, seen from slightly below, standing, feet visible',
  'full body head to toe, leaning one shoulder against the wall, feet visible'];
const FULL = ['full body head to toe, standing facing the camera, arms relaxed at her sides, feet visible',
  'full body head to toe, standing, hands on her hips, feet visible', 'full body head to toe, three-quarter turn, weight on one leg, feet visible'];
const out = process.argv[3] || path.join(REPO, '.run', 'candidates');
fs.mkdirSync(out, { recursive: true });
// a different her in each picture (the operator is choosing her likeness): face, hair cut, eyes and build vary,
// the goth raven-and-pink core stays. No face lock, so the faces really differ.
const BODY = 'slim fit body, natural medium breasts, toned flat stomach with soft subtle abs, flat smooth lower belly, narrow waist, gently rounded hips, ' +
  'round firm butt, long slender toned legs, slender arms, delicate collarbones';
const LIKENESS = [
  'long messy raven hair with hot pink streaks, sharp jaw, high cheekbones, pale grey-blue eyes, full lips, fair skin with a light natural flush',
  'long straight jet black hair with light pink streaks, soft oval face, bright blue eyes, thin black eyeliner, warm playful smile, fair skin with a light natural flush, natural skin texture',
  'long straight jet black hair with pink underneath, narrow heart-shaped face, hazel eyes, thin arched brows, ivory skin',
  'wavy black hair with pastel pink tips, strong brows, almond-shaped brown eyes, full pouty lips, fair skin with a warm flush',
  'black pixie cut with a hot pink streak, angular face, ice blue eyes, small septum ring, pale skin, defined cheekbones',
  'very long black hair in loose waves with magenta streaks, oval face, grey eyes, soft dimples, light olive skin',
  'black hair in two loose space buns with pink strands, cute round cheeks, bright blue eyes, upturned nose, rosy pale skin',
  'messy black shag cut with pink highlights, sleepy hooded green eyes, sharp nose, wide smirk, fair skin, ink tattoos down her arms',
];
// clean base poses: face and whole body in view, both hands at her sides or on her body, nothing held. A phone or a
// raised middle finger covered her and left floating phones and hands in every look built on top.
const POSES = ['lying on her side on the bed, propped on one elbow', 'kneeling on the bed, back arched, hands on her thighs',
  'lying on her stomach on the bed, legs kicked up behind her, chin on her hands', 'stretched out on her back across the bed, hair fanned out',
  'standing against the wall, hip pushed out, looking over her shoulder', 'sitting on the edge of the bed leaning back on her hands',
  'reclining on a couch, one knee up, arm over her head', 'standing, hands on her hips, weight on one leg'];
// FACE=1 locks her original face (assets/portrait/unity-face.jpg) onto every picture
const FACE = process.env.FACE === '1' ? fs.readFileSync(cfg.lookFaceRef).toString('base64') : null;
// short on purpose: no clothing words (the operator: naming clothes in the negatives is "giving him matches"), and
// the sidecar cuts a negative at CLIP's 77 tokens anyway, so a long list loses its tail
const NEG_EXTRA = ', phone, extra fingers, mutated hands, black sclera, plastic skin, tight close up, auburn hair, brown hair, blonde hair';
for (let i = 0; i < n; i++) {
  const li = PICK.length ? PICK[i % PICK.length] : i % LIKENESS.length;
  const pose = process.env.VARY === '1' ? VARY[i % VARY.length] : PICK.length ? (process.env.KNEES === '1' ? KNEES : FULL)[Math.floor(i / PICK.length) % FULL.length] : POSES[i % POSES.length];
  const prompt = `photo of a 25 year old American woman, ${LIKENESS[li]}, ${BODY}, ${pose}, photo shoot, bedroom, soft pink neon light, bright clear eyes with clean white sclera, ${cfg.lookSuffix}`;
  const body = { prompt, width: cfg.lookWidth, height: PICK.length ? 896 : cfg.lookHeight, steps: cfg.lookSteps, guidance: cfg.lookGuidance, ...(process.env.SEED ? { seed: Number(process.env.SEED) + (process.env.VARY === '1' ? 0 : i) } : {}), ...(FACE ? { face: FACE, face_scale: 0.5 } : {}),
    negative: 'child, teen, underage, childlike, young girl' + NEG_EXTRA };
  const r = await fetch(`${cfg.imageUrl}/txt2img`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal: AbortSignal.timeout(300000) });
  if (!r.ok) { console.error(`#${i + 1} failed: ${r.status} ${await r.text()}`); continue; }
  const file = path.join(out, `candidate-${PICK.length ? 'L' + (li + 1) + '-' : ''}${String(i + 1).padStart(2, '0')}-seed${r.headers.get('x-seed')}.png`);
  fs.writeFileSync(file, Buffer.from(await r.arrayBuffer()));
  console.log(file);
}
