// Ollama chat provider: streaming /api/chat, model discovery, health. Native tool calling lands with the
// registry in M6; M2 only needs text in, text out.
import { cfg } from '../config.mjs';

export async function listModels() {
  const r = await fetch(`${cfg.ollamaUrl}/api/tags`, { signal: AbortSignal.timeout(3000) });
  if (!r.ok) throw new Error(`ollama /api/tags ${r.status}`);
  const j = await r.json();
  return (j.models || []).map(m => m.name);
}

let _model = null;
export async function pickModel() {
  if (_model) return _model;
  const have = await listModels();
  const want = cfg.brainModels.find(m => have.includes(m) || have.includes(`${m}:latest`));
  _model = want ? (have.includes(want) ? want : `${want}:latest`) : have[0];
  if (!_model) throw new Error('ollama has no models');
  return _model;
}

// The GPU gate. A brain call that lands while a video clip renders reloads the 9 GB brain next to Wan, the 16 GB
// card fills, and both crawl (a render sat at step 0 for minutes). Unloading cannot fix it mid-request: Ollama
// finishes the request first. So background calls wait for the render to end; her replies to the operator cancel
// the clip first (hub respond), so they never wait here.
export const gpu = { rendering: 0 };
const sleep = ms => new Promise(r => setTimeout(r, ms));

/** Async generator of content deltas. `messages` is the full chat (system first). `purpose` is logged;
 *  `background` calls wait while a clip renders. */
export async function* chatStream(messages, { signal, model, numPredict, purpose = 'reply', background = false } = {}) {
  if (background) while (gpu.rendering > 0 && !signal?.aborted) await sleep(500);
  console.log(new Date().toISOString().slice(11, 19), `brain: ${purpose}${gpu.rendering ? ' (a clip is rendering)' : ''}`);
  const m = model || await pickModel();
  const body = {
    model: m, stream: true, messages, keep_alive: cfg.keepAlive,
    options: { num_ctx: cfg.numCtx, temperature: cfg.temperature, top_p: cfg.topP, repeat_penalty: cfg.repeatPenalty,
      num_predict: numPredict || cfg.numPredict, stop: cfg.stop },
  };
  const r = await fetch(`${cfg.ollamaUrl}/api/chat`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal,
  });
  if (!r.ok || !r.body) throw new Error(`ollama /api/chat ${r.status} ${await r.text().catch(() => '')}`);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let nl;
    while ((nl = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      let j;
      try { j = JSON.parse(line); } catch { continue; }
      if (j.error) throw new Error(j.error);
      const delta = j.message?.content;
      if (delta) yield delta;
      if (j.done) return;
    }
  }
}

/** One whole reply, no streaming, for side questions (e.g. what she does next while idle). */
export async function chatOnce(messages, { numPredict = 300, signal, purpose = 'side question', background = true } = {}) {
  let out = '';
  for await (const d of chatStream(messages, { signal, numPredict, purpose, background })) out += d;
  return out;
}

export async function health() {
  try {
    const models = await listModels();
    return { ok: true, model: await pickModel().catch(() => null), models: models.length };
  } catch (e) {
    return { ok: false, error: String(e.message || e) };
  }
}
