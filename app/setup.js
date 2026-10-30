// First-run installer: everything she runs on, into one folder, removable in one go.
// Operator, verbatim: "the .exe has to install all things it needs to run with option to uninstall oall things
// also if wanted".
//
// Steps (each skipped when already satisfied, dev checkouts included):
//   python   Python 3.10 runtime (python-build-standalone, has pip)        -> DATA/runtime/python
//   base     torch cu118 + voice/speech/image/video requirements           -> into that runtime
//   face     venv on top of it with Ditto's requirements                   -> DATA/venvs/face
//   ollama   Ollama server binaries (portable zip, no tray app, no service) -> DATA/runtime/ollama
//   models   Ditto, LTX-Video, Realistic Vision, IP-Adapter, Whisper, her voice -> DATA/models
//   brain    dolphin3:8b pulled + unity-local built from her Modelfile      -> DATA/ollama-models
// Nothing touches the registry or PATH; the uninstaller (and the in-app button) removes DATA whole.
'use strict';
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const https = require('node:https');
const { spawn, execSync } = require('node:child_process');
const { DATA, RUNTIME, resolve, exists, freeBytes } = require('./paths');

const DL = path.join(DATA, 'downloads');
const STATE = path.join(DATA, 'state.json');
const TORCH = ['torch==2.7.1', 'torchvision==0.22.1', 'torchaudio==2.7.1', '--index-url', 'https://download.pytorch.org/whl/cu118'];
const BRAIN_BASE = 'dolphin3:8b';
const SETUP_PORT = 11436;    // the temporary brain server used only while installing models
const tar = 'C:\\Windows\\System32\\tar.exe';   // bsdtar, in every Windows 10+/11: reads .tar.gz and .zip

function readState() { try { return JSON.parse(fs.readFileSync(STATE, 'utf8')); } catch { return {}; } }
function writeState(patch) { fs.mkdirSync(DATA, { recursive: true }); fs.writeFileSync(STATE, JSON.stringify({ ...readState(), ...patch }, null, 2)); }

function fetchJson(url) {
  return new Promise((res, rej) => {
    https.get(url, { headers: { 'User-Agent': 'agent-gen-setup', Accept: 'application/vnd.github+json' } }, r => {
      if ([301, 302, 307, 308].includes(r.statusCode)) return fetchJson(r.headers.location).then(res, rej);
      let b = ''; r.on('data', d => b += d); r.on('end', () => { try { res(JSON.parse(b)); } catch (e) { rej(e); } });
    }).on('error', rej);
  });
}

function download(url, dest, onProgress = () => {}) {
  return new Promise((res, rej) => {
    const part = dest + '.part';
    https.get(url, { headers: { 'User-Agent': 'agent-gen-setup' } }, r => {
      if ([301, 302, 307, 308].includes(r.statusCode)) return download(r.headers.location, dest, onProgress).then(res, rej);
      if (r.statusCode !== 200) return rej(new Error(`${url}: HTTP ${r.statusCode}`));
      const total = Number(r.headers['content-length'] || 0); let got = 0, last = 0;
      const f = fs.createWriteStream(part);
      r.on('data', d => { got += d.length; if (Date.now() - last > 500) { last = Date.now(); onProgress(got, total); } });
      r.pipe(f);
      f.on('finish', () => { f.close(() => { fs.renameSync(part, dest); onProgress(total, total); res(dest); }); });
      f.on('error', rej);
    }).on('error', rej);
  });
}

/** Run a child with a hidden console, streaming its lines to `log`. Resolves on exit 0. */
function run(cmd, args, { env = {}, cwd, log = () => {} } = {}) {
  return new Promise((res, rej) => {
    const c = spawn(cmd, args, { cwd, env: { ...process.env, ...env }, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
    let tail = '';
    const onData = d => { const s = d.toString(); tail = (tail + s).slice(-2000); for (const l of s.split(/\r?\n/)) if (l.trim()) log(l.trimEnd()); };
    c.stdout.on('data', onData); c.stderr.on('data', onData);
    c.on('error', rej);
    c.on('exit', code => code === 0 ? res() : rej(new Error(`${path.basename(cmd)} ${args.slice(0, 3).join(' ')} exited ${code}\n${tail}`)));
  });
}

async function ghAsset(repo, test) {
  const rel = await fetchJson(`https://api.github.com/repos/${repo}/releases/latest`);
  const a = (rel.assets || []).find(x => test(x.name));
  if (!a) throw new Error(`no matching asset in ${repo} ${rel.tag_name}`);
  return { url: a.browser_download_url, name: a.name, tag: rel.tag_name };
}

function fmt(n) { return n > 1e9 ? (n / 1e9).toFixed(2) + ' GB' : (n / 1e6).toFixed(0) + ' MB'; }

// what the voice, speech, image and video sidecars import (face has its own venv and its own requirements)
const PROBE_IMPORTS = ['torch', 'torchaudio', 'numpy', 'soundfile', 'misaki.en', 'numba', 'faster_whisper', 'diffusers', 'transformers', 'accelerate', 'safetensors', 'sentencepiece', 'ftfy', 'cv2', 'PIL', 'huggingface_hub', 'packaging'];

// minimum versions the sidecars are written against (Wan 2.2 needs diffusers 0.41 / transformers 5): when these
// move, the installer upgrades the interpreter it uses, whether that is its own runtime or the machine's Python
const PROBE_VERSIONS = { diffusers: '0.41', transformers: '5.20', huggingface_hub: '1.0' };

/** Can this interpreter import all of these, at or above the pinned versions? */
function probe(pyExe, mods) {
  const checks = Object.entries(PROBE_VERSIONS).filter(([m]) => mods.includes(m))
    .map(([m, v]) => `assert V(${m}.__version__) >= V('${v}'), '${m} too old'`);
  const code = `import importlib; ${mods.map(m => `importlib.import_module('${m}')`).join('; ')}; ` +
    (checks.length ? `from packaging.version import Version as V; import ${Object.keys(PROBE_VERSIONS).filter(m => mods.includes(m)).join(', ')}; ${checks.join('; ')}` : 'pass');
  return run(pyExe, ['-c', code], {}).then(() => true, () => false);
}

/** Does the Ollama on `port` (if any) have `name`? */
function tagsHave(port, name) {
  return new Promise(res => {
    const req = require('node:http').get(`http://127.0.0.1:${port}/api/tags`, { timeout: 800 }, r => {
      let b = ''; r.on('data', d => b += d);
      r.on('end', () => { try { res((JSON.parse(b).models || []).some(m => m.name === name || m.name === `${name}:latest`)); } catch { res(false); } });
    });
    req.on('error', () => res(false)); req.on('timeout', () => { req.destroy(); res(false); });
  });
}

/** The steps, against a repo/resources root. Each `done` is a capability check so a dev box with the lab's own
 *  Python, venv, Ollama and models is already complete. */
function plan(root) {
  const P = () => resolve(root);
  const py = () => P().pythonExe;
  const ollama = () => P().ollamaExe;
  const dlDir = () => { fs.mkdirSync(DL, { recursive: true }); return DL; };
  return [
    {
      gb: 0.1, id: 'python', title: 'Python 3.10 runtime',
      done: () => !!py(),
      async run(log, progress) {
        const a = await ghAsset('astral-sh/python-build-standalone', n => /^cpython-3\.10\.\d+\+\d+-x86_64-pc-windows-msvc-install_only\.tar\.gz$/.test(n));
        log(`downloading ${a.name} (${a.tag})`);
        const f = path.join(dlDir(), a.name);
        if (!exists(f)) await download(a.url, f, (g, t) => progress(g, t));
        fs.mkdirSync(RUNTIME, { recursive: true });
        await run(tar, ['-xzf', f, '-C', RUNTIME], { log });     // extracts to RUNTIME/python
        if (!exists(path.join(RUNTIME, 'python', 'python.exe'))) throw new Error('python.exe not found after extract');
      },
    },
    {
      gb: 6, id: 'base', title: 'PyTorch (CUDA 11.8) and the voice, speech, image and video requirements',
      // a real probe, not a marker: every library the four sidecars import must load in that interpreter,
      // so a machine with its own Python (a dev box) gets missing pieces installed too (ftfy taught us that)
      done: async () => !!py() && await probe(py(), PROBE_IMPORTS),
      async run(log) {
        const p = py();
        await run(p, ['-m', 'pip', 'install', '--upgrade', 'pip', 'wheel'], { log });
        if (!(await probe(p, ['torch']))) await run(p, ['-m', 'pip', 'install', ...TORCH], { log });
        await run(p, ['-m', 'pip', 'install', '-r', path.join(root, 'sidecars', 'requirements-base.txt')], { log });
        writeState({ base: p });
      },
    },
    {
      gb: 2, id: 'face', title: 'Face engine environment (Ditto)',
      done: () => !!P().facePy,
      async run(log) {
        const venv = path.join(DATA, 'venvs', 'face');
        await run(py(), ['-m', 'venv', '--system-site-packages', venv], { log });
        const vpy = path.join(venv, 'Scripts', 'python.exe');
        await run(vpy, ['-m', 'pip', 'install', '-r', path.join(root, 'sidecars', 'face', 'requirements.txt')], { log });
      },
    },
    {
      gb: 1.5, id: 'ollama', title: 'Ollama server (her brain\'s runtime)',
      done: () => !!ollama(),
      async run(log, progress) {
        const a = await ghAsset('ollama/ollama', n => n === 'ollama-windows-amd64.zip');
        log(`downloading ${a.name} (${a.tag})`);
        const f = path.join(dlDir(), `ollama-${a.tag}.zip`);
        if (!exists(f)) await download(a.url, f, (g, t) => progress(g, t));
        const dest = path.join(RUNTIME, 'ollama'); fs.mkdirSync(dest, { recursive: true });
        await run(tar, ['-xf', f, '-C', dest], { log });
        if (!exists(path.join(dest, 'ollama.exe'))) throw new Error('ollama.exe not found after extract');
      },
    },
    {
      gb: 72, id: 'models', title: 'Model weights (face, motion, looks, hearing, her voice)',
      done: () => { const h = P().have; return h.ditto && h.ltx && h.wan && h.voice && h.sd; },
      async run(log) {
        const models = path.join(DATA, 'models');
        fs.mkdirSync(models, { recursive: true });
        await run(py(), ['-u', path.join(root, 'scripts', 'fetch-models.py'), '--models', models, '--voice-src', path.join(root, 'models', 'unity-voice-v2')], { log, env: { HF_HOME: path.join(models, 'hf') } });
      },
    },
    {
      gb: 5.5, id: 'brain', title: `Her brain (${BRAIN_BASE} + unity-local)`,
      // the manifest on disk, or any Ollama already serving on this box (tray app or ours) that lists it
      done: async () => P().have.brain || (await tagsHave(11434, 'unity-local')) || (await tagsHave(11435, 'unity-local')),
      async run(log) {
        const exe = ollama();
        // a portable runtime keeps its models under DATA; a machine's own Ollama keeps using ~/.ollama
        const store = P().ollamaModels || (exe.startsWith(RUNTIME) ? path.join(DATA, 'ollama-models') : null);
        if (store) fs.mkdirSync(store, { recursive: true });
        const env = { OLLAMA_HOST: `127.0.0.1:${SETUP_PORT}`, ...(store ? { OLLAMA_MODELS: store } : {}) };
        const srv = spawn(exe, ['serve'], { env: { ...process.env, ...env }, stdio: 'ignore', windowsHide: true });
        try {
          await new Promise(r => setTimeout(r, 2500));
          log(`pulling ${BRAIN_BASE} (about 5 GB)`);
          await run(exe, ['pull', BRAIN_BASE], { log, env });
          log('building unity-local from her Modelfile');
          await run(exe, ['create', 'unity-local', '-f', path.join(root, 'vendor', 'local-unity-ollama', 'Modelfile')], { log, env });
        } finally {
          try { execSync(`taskkill /PID ${srv.pid} /T /F`, { stdio: 'ignore', windowsHide: true }); } catch {}
        }
      },
    },
  ];
}

async function missing(root) { const out = []; for (const s of plan(root)) if (!(await s.done())) out.push(s); return out; }

/** Run every unsatisfied step in order. `emit(ev)` gets {step, status, line?, got?, total?}. */
async function install(root, emit = () => {}) {
  fs.mkdirSync(DATA, { recursive: true });
  for (const s of plan(root)) {
    if (await s.done()) { emit({ step: s.id, status: 'done' }); continue; }
    emit({ step: s.id, status: 'running' });
    try {
      await s.run(line => emit({ step: s.id, status: 'running', line }), (got, total) => emit({ step: s.id, status: 'running', got, total, line: `${fmt(got)} / ${fmt(total)}` }));
      if (!(await s.done())) throw new Error(`${s.title}: finished but still not satisfied`);
      emit({ step: s.id, status: 'done' });
    } catch (e) {
      emit({ step: s.id, status: 'failed', line: String(e.message || e) });
      throw e;
    }
  }
}

/** Remove everything the installer put on this machine. The app's own files go with the NSIS uninstaller. */
function uninstallData() {
  if (exists(DATA)) fs.rmSync(DATA, { recursive: true, force: true });
  return !exists(DATA);
}

module.exports = { plan, missing, install, uninstallData, DATA, freeBytes, homedir: os.homedir };
