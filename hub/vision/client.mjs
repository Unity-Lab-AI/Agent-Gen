// Her eyes: a camera or screen frame from the UI is described by a small vision model on the same Ollama, and the
// description rides along with what the operator said, so any brain (vision or not) knows what she sees.
import { cfg } from '../config.mjs';

const ASK = {
  camera: 'This is your webcam: the person in front of it is the one talking to you. In two or three short sentences say what you see: the person (what they look like, wear, hold, do, their expression) and the place. Plain description, no greeting.',
  screen: 'This is the operator\'s computer screen. In two or three short sentences say what is on it: the app or site, what they are looking at or doing, any readable headline or text that matters. Plain description, no greeting.',
};

async function describeOne(b64, source, signal) {
  const body = {
    model: cfg.visionModel, stream: false, think: false, keep_alive: cfg.visionKeepAlive,
    messages: [{ role: 'user', content: ASK[source] || ASK.camera, images: [b64] }],
    // qwen3-vl thinks even with think:false and the thinking counts against num_predict: 160 left the answer empty
    options: { num_predict: 900, temperature: 0.2 },
  };
  // qwen3-vl answers empty on a cold load now and then; one retry, warm, costs under a second
  for (let i = 0; i < 2; i++) {
    const r = await fetch(`${cfg.ollamaUrl}/api/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body), signal: signal || AbortSignal.timeout(cfg.visionTimeoutMs) });
    if (!r.ok) throw new Error(`vision ${r.status} ${await r.text().catch(() => '')}`.trim());
    const j = await r.json();
    const t = (j.message?.content || '').replace(/<think>[\s\S]*?<\/think>/g, '').trim();
    if (t) return t;
  }
  return '';
}

/** frames: [{ source: 'camera'|'screen', b64 }] -> [{ source, text, ms }]. Never throws: a failed look is reported. */
export async function describe(frames, { signal } = {}) {
  const out = [];
  for (const f of frames || []) {
    if (!f?.b64) continue;
    const t0 = Date.now();
    try { out.push({ source: f.source, text: await describeOne(f.b64, f.source, signal), ms: Date.now() - t0 }); }
    catch (e) { out.push({ source: f.source, text: '', error: String(e.message || e), ms: Date.now() - t0 }); }
  }
  return out;
}

/** The sentence her brain gets in front of the operator's words. */
export function asContext(seen) {
  const lines = seen.filter(s => s.text).map(s => s.source === 'screen'
    ? `[What you see on their screen right now: ${s.text}]` : `[What you see through your camera right now: ${s.text}]`);
  return lines.length ? lines.join('\n') + '\n' : '';
}

export async function health() {
  try {
    const r = await fetch(`${cfg.ollamaUrl}/api/tags`, { signal: AbortSignal.timeout(3000) });
    const names = ((await r.json()).models || []).map(m => m.name);
    const ok = names.includes(cfg.visionModel) || names.includes(`${cfg.visionModel}:latest`);
    return { ok, model: cfg.visionModel, ...(ok ? {} : { error: `${cfg.visionModel} not pulled` }) };
  } catch (e) { return { ok: false, error: String(e.message || e) }; }
}

// ---- ambient: a glance now and then while the camera or screen is shared ------------------------------------
const GLANCE = {
  camera: 'This is your webcam, pointed at your friend. Answer in exactly four lines:\nPERSON: yes or no (is a person in front of the camera)\nMOOD: one word for their face and body (happy, neutral, tired, sad, upset, angry, bored, focused, laughing, none)\nDOING: a few words on what they are doing\nNOTABLE: something new or striking a friend would comment on (something held up to the camera, a new outfit, someone else there, food, a pet), or none',
  screen: 'This is your friend\'s computer screen. Answer in exactly four lines:\nPERSON: no\nMOOD: none\nDOING: a few words on the app or site and what they are doing\nNOTABLE: something on it a friend would comment on (a game won or lost, an error, a striking image or headline), or none',
};

/** One frame -> { source, person, mood, doing, notable, ms } (null fields when the model would not say). */
export async function glance(frame, { signal } = {}) {
  const t0 = Date.now();
  const body = {
    model: cfg.visionModel, stream: false, think: false, keep_alive: cfg.visionKeepAlive,
    messages: [{ role: 'user', content: GLANCE[frame.source] || GLANCE.camera, images: [frame.b64] }],
    options: { num_predict: 900, temperature: 0.1 },
  };
  const r = await fetch(`${cfg.ollamaUrl}/api/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal: signal || AbortSignal.timeout(cfg.visionTimeoutMs) });
  if (!r.ok) throw new Error(`vision ${r.status}`);
  const t = ((await r.json()).message?.content || '').replace(/<think>[\s\S]*?<\/think>/g, '');
  const field = k => (new RegExp(`^\s*\**${k}\**\s*:\s*(.+)$`, 'im').exec(t)?.[1] || '').replace(/\*+/g, '').trim();
  const none = v => !v || /^(none|nothing|n\/a|no)\.?$/i.test(v);
  const mood = field('MOOD').toLowerCase().split(/[\s,.]/)[0];
  return { source: frame.source, person: /^y/i.test(field('PERSON')), mood: none(mood) ? null : mood,
    doing: field('DOING') || null, notable: none(field('NOTABLE')) ? null : field('NOTABLE'), ms: Date.now() - t0 };
}

const LOW = ['sad', 'upset', 'angry', 'crying', 'tired', 'stressed', 'frustrated', 'bored'];
/** The friend threshold: how much a close friend watching would want to say something now, 0..10, and why.
 *  prev = the last glance of the same source (or null). */
export function friendScore(g, prev, { absentGlances = 0 } = {}) {
  let score = 0; const why = [];
  if (g.source === 'camera') {
    if (g.person && prev && !prev.person && absentGlances >= 2) { score += 7; why.push('they came back'); }
    if (!g.person && prev?.person) { score += 3; why.push('they walked away'); }
    if (g.person && g.mood && LOW.includes(g.mood) && g.mood !== prev?.mood) { score += 6; why.push(`they look ${g.mood}`); }
    else if (g.person && g.mood && prev?.mood && g.mood !== prev.mood) { score += 2; why.push(`mood ${prev.mood} -> ${g.mood}`); }
  }
  if (g.notable && g.notable !== prev?.notable) { score += 5; why.push(g.notable); }
  return { score, why };
}
