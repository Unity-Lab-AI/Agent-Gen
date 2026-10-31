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
