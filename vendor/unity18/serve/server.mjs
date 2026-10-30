/**
 * serve/server.mjs — `U3E-5.1`. The inference server.
 *
 * ⛔ NO OLLAMA, NO THIRD-PARTY RUNTIME, NO EXTERNAL WEIGHTS.
 *   The finished model needs no Ollama — the whole stack is our own. What is kept from the
 *   sibling project is the **wire shape** (`/api/chat`, `/api/image`,
 *   `/api/state`) so its chat page and Android APK keep working — that is a
 *   contract, not a dependency.
 *
 * ⭐ IT SERVES A MODEL-SHAPED HOLE.
 *   Whatever satisfies `serve/slot.js` gets served. Today that is the stand-in;
 *   after the pod run it is her, and **nothing else changes**. The slot is
 *   validated at boot on whatever is plugged in, so a bad swap fails loudly here
 *   rather than subtly three surfaces away.
 *
 * ⭐ THE CLIENT RECONSTRUCTS.
 *   The wire carries COEFFICIENTS, never a picture. `/api/image` returns a field
 *   record and the browser runs `idwt2` on it. Her image is an equation right up
 *   to the screen — and on the phone that also means far less over the wire.
 *
 * Run:
 *   node serve/server.mjs                    loopback
 *   node serve/server.mjs --host 0.0.0.0     reachable from the phone on the LAN
 */

import { createServer } from 'node:http';
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { join, dirname, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { networkInterfaces } from 'node:os';

import { validateSlot, call, CapabilityAbsent, SLOT_VERSION } from './slot.js';
/**
 * ⛔ `U3E-8.33` — THE STAND-IN IS IMPORTED ONLY IF IT IS CHOSEN. None of the
 *   training-side material ships with the application.
 *
 * ⚠ It replays banked CORPUS fields, so it belongs to the training project, not
 *   to the shipped application — but a STATIC import made the file mandatory at
 *   boot even when `U3E_MODEL=legacy` meant it could never be selected. So the
 *   product could not simply omit it without forking this file, and a product
 *   that diverges from its source is a product that drifts.
 *
 * ⭐ The import moved to the branch that uses it. Both trees run the same code;
 *   the application ships without a corpus replayer, and the development tree
 *   still selects it with `U3E_MODEL=standin`.
 */
// ⚠ Development harness, opt-in via U3E_MODEL=legacy. Delete with U3E-4.6.
import { createLegacyAdapter } from './legacy-adapter.js';
import { sliceField } from './progressive.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '..');
const CORPUS = join(ROOT, 'data', 'corpus');
const APP = join(ROOT, 'app');

const arg = (n, d) => { const i = process.argv.indexOf(n); return i >= 0 ? process.argv[i + 1] : d; };
const PORT = Number(arg('--port', 8790));
const HOST = arg('--host', '127.0.0.1');

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.webmanifest': 'application/manifest+json',
};

// ── load whatever fills the slot ─────────────────────────────────────────────
function loadBankedFields(limit = 64) {
  const mf = join(CORPUS, 'manifest.json');
  if (!existsSync(mf)) return [];
  const m = JSON.parse(readFileSync(mf, 'utf8'));
  const out = [];
  for (const e of m.entries.slice(0, limit)) {
    const p = join(CORPUS, `${e.name}.field.json`);
    if (existsSync(p)) out.push({ name: e.name, rec: JSON.parse(readFileSync(p, 'utf8')) });
  }
  return out;
}

/**
 * ⛔ THE SWAP POINT. When the trained model exists, it is constructed here and
 * nothing else in the project changes. `U3E-4.6` is the check that this stayed
 * true — if a real swap needs edits elsewhere, the slot was wrong.
 */
/**
 * ⭐ THE ONE SWAP POINT. `U3E-0.8` promised the trained model replaces whatever
 * is here at exactly one place, and this is that place.
 *
 * THE REQUIREMENT: swapping the trained model for the combined image-and-text
 * model has to be simple, and happen in one place.
 *
 *     U3E_MODEL=standin   replay banked corpus fields          (default)
 *     U3E_MODEL=legacy    the working image+text model, over HTTP
 *     (trained)           chosen automatically once weights exist — it wins
 *
 * ⛔ SELECTION IS EXPLICIT AND NEVER FALLS BACK. If `legacy` is asked for and
 * the wrapper is not running, this REFUSES to boot rather than quietly serving
 * the stand-in — a server that silently answers with something other than what
 * was requested is the exact failure `NO FALLBACK THAT HIDES A FAILURE` names,
 * and it would make every downstream measurement untrustworthy.
 */
// ⚠ async since `U3E-8.33`: the stand-in is imported only if it is chosen.
async function loadModel() {
  const weights = join(ROOT, 'serve', 'weights');
  if (existsSync(join(weights, 'model.json'))) {
    // Deliberately not implemented yet, and it THROWS rather than silently
    // continuing with the stand-in: weights on disk that are not being served
    // is exactly the kind of quiet wrongness this project refuses.
    throw new Error(
      'serve/weights/model.json exists but the trained-model loader is not built yet (U3E-4.6). ' +
      'Refusing to serve the stand-in while real weights sit unused — that would look like success.'
    );
  }

  const pick = (process.env.U3E_MODEL || 'standin').toLowerCase();
  if (pick === 'legacy') {
    // ⚠ Development harness only — see serve/legacy-adapter.js for the full
    //   U3E-5.0 reasoning. `standIn` stays true on every response.
    return createLegacyAdapter();
  }
  if (pick !== 'standin') {
    throw new Error(
      `U3E_MODEL="${pick}" is not a thing. Use "standin" or "legacy". ` +
      `Refusing to guess — a server that picks its own model makes every ` +
      `measurement taken against it meaningless.`);
  }
  // ⚠ Dynamic, and awaited — see the note where the static import used to be.
  //   A missing file here is an honest error naming the model that was asked
  //   for, not a boot failure for a model nobody selected.
  const { createStandIn } = await import('./stand-in.js').catch(() => {
    throw new Error(
      'U3E_MODEL="standin" was asked for, but serve/stand-in.js is not in this ' +
      'build — the shipped application ships without the corpus replayer. Use ' +
      'U3E_MODEL=legacy, or run from the development tree.');
  });
  return createStandIn({ fields: loadBankedFields() });
}

const model = await loadModel();
const problems = validateSlot(model);
if (problems.length) {
  console.error('\n⛔ SLOT VALIDATION FAILED — refusing to serve:\n');
  for (const p of problems) console.error('   ' + p);
  process.exit(1);
}

// ── plumbing ─────────────────────────────────────────────────────────────────
function json(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store',
  });
  res.end(body);
}

function serveFile(res, path) {
  if (!existsSync(path)) { res.writeHead(404); res.end('not found'); return; }
  res.writeHead(200, { 'content-type': MIME[extname(path)] || 'application/octet-stream' });
  res.end(readFileSync(path));
}

async function readBody(req, limit = 32 * 1024 * 1024) {
  const chunks = [];
  let n = 0;
  for await (const c of req) {
    n += c.length;
    if (n > limit) throw new Error('body too large');
    chunks.push(c);
  }
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : {};
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const p = url.pathname;

  try {
    // the app, and the SAME codec/tokenizer sources Node runs — no build step,
    // no copy to drift out of sync
    if (p === '/' || p === '/index.html') return serveFile(res, join(APP, 'index.html'));
    if (p.startsWith('/app/')) return serveFile(res, join(ROOT, p.slice(1)));
    // ⭐ The SAME sources Node runs — no build step, no copy to drift.
    //   `/serve/progressive.js` is shared: the server slices, the client merges.
    if (p.startsWith('/codec/') || p.startsWith('/tokenizer/') || p === '/serve/progressive.js') {
      return serveFile(res, join(ROOT, p.slice(1)));
    }
    // the docs Settings links to — read-only, and they are the project's own
    if (p.startsWith('/docs/') && p.endsWith('.md')) {
      const f = join(ROOT, p.slice(1));
      if (!existsSync(f)) { res.writeHead(404); res.end('not found'); return; }
      res.writeHead(200, { 'content-type': 'text/plain; charset=utf-8' });
      return res.end(readFileSync(f));
    }

    if (p === '/api/state') {
      const d = model.describe();
      return json(res, 200, {
        ok: true,
        slot: SLOT_VERSION,
        model: d,
        capabilities: model.capabilities(),
        // ⛔ Surfaced, not buried: the client renders a banner from this and the
        // banner is not dismissible while it is true.
        standIn: d.standIn,
        corpus: { banked: loadBankedFields(1).length > 0 },
      });
    }

    if (p === '/api/chat' && req.method === 'POST') {
      const body = await readBody(req);
      return json(res, 200, await call(model, 'chat', body));
    }

    if (p === '/api/image' && req.method === 'POST') {
      const body = await readBody(req);
      const out = await call(model, 'image', body);

      // ⭐ U3E-5.3 — progressive emission. Coarse scales first, as NDJSON, so
      //   the picture APPEARS and SHARPENS instead of arriving at once.
      //   ⛔ Not a loading animation: each line carries coefficients the client
      //   genuinely did not have. Mute the later lines and it stays coarse.
      if (body.progressive) {
        const slices = sliceField(out.field);
        res.writeHead(200, {
          'content-type': 'application/x-ndjson; charset=utf-8',
          'cache-control': 'no-store',
          'x-accel-buffering': 'no',      // some proxies would otherwise buffer the point away
        });
        res.write(JSON.stringify({
          type: 'head',
          meta: {
            width: out.field.width, height: out.field.height,
            pad_w: out.field.pad_w, pad_h: out.field.pad_h,
          },
          slices: slices.length,
          total: out.field.equation_count,
          model: out.model,
        }) + '\n');
        for (const s of slices) {
          res.write(JSON.stringify({ type: 'slice', ...s }) + '\n');
        }
        res.end(JSON.stringify({ type: 'done', note: out.note || null }) + '\n');
        return;
      }

      return json(res, 200, out);
    }

    if (p === '/api/speak' && req.method === 'POST') {
      return json(res, 200, await call(model, 'speak', await readBody(req)));
    }
    if (p === '/api/see' && req.method === 'POST') {
      return json(res, 200, await call(model, 'see', await readBody(req)));
    }
    if (p === '/api/hear' && req.method === 'POST') {
      return json(res, 200, await call(model, 'hear', await readBody(req)));
    }

    res.writeHead(404); res.end('not found');
  } catch (e) {
    if (e instanceof CapabilityAbsent) {
      // ⛔ 501, and the body says ABSENT rather than FAILED. The client shows
      // "she cannot do this yet", never a spinner that never resolves.
      return json(res, 501, { error: e.message, absent: true, method: e.method });
    }
    json(res, 500, { error: e.message });
  }
});

function lanAddress() {
  for (const list of Object.values(networkInterfaces())) {
    for (const i of list || []) {
      if (i.family === 'IPv4' && !i.internal) return i.address;
    }
  }
  return null;
}

server.listen(PORT, HOST, () => {
  const d = model.describe();
  console.log(`\nU3E serving  —  http://${HOST}:${PORT}`);
  if (HOST === '0.0.0.0') {
    const lan = lanAddress();
    if (lan) console.log(`  phone on the same network:  http://${lan}:${PORT}`);
  }
  console.log(`\n  model: ${d.name}  (${d.kind})`);
  const caps = model.capabilities();
  console.log(`  can:   ${Object.entries(caps).filter(([, v]) => v).map(([k]) => k).join(', ') || 'nothing'}`);
  const absent = Object.entries(caps).filter(([, v]) => !v).map(([k]) => k);
  if (absent.length) console.log(`  cannot: ${absent.join(', ')}  (absent, not failed — /api/* returns 501)`);
  if (d.standIn) {
    console.log('\n  ⛔ STAND-IN. This is NOT Unity. Every response says so and the page');
    console.log('     shows a banner. Swap the trained model in at serve/server.mjs::loadModel.');
  }
  console.log('');
});
