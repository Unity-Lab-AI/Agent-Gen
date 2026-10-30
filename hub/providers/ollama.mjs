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

/** Async generator of content deltas. `messages` is the full chat (system first). */
export async function* chatStream(messages, { signal, model } = {}) {
  const m = model || await pickModel();
  const body = {
    model: m, stream: true, messages, keep_alive: cfg.keepAlive,
    options: { num_ctx: cfg.numCtx, temperature: cfg.temperature, top_p: cfg.topP, repeat_penalty: cfg.repeatPenalty,
      num_predict: cfg.numPredict, stop: cfg.stop },
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

export async function health() {
  try {
    const models = await listModels();
    return { ok: true, model: await pickModel().catch(() => null), models: models.length };
  } catch (e) {
    return { ok: false, error: String(e.message || e) };
  }
}
