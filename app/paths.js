// Where everything she runs on lives. One data root per machine (%LOCALAPPDATA%\AgentGen by default) that the
// installer fills and the uninstaller can remove in one go; a dev checkout with the lab's own Python, venv and
// models still works unchanged because every lookup falls back to the repo / system locations.
'use strict';
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const exists = p => { try { return !!p && fs.existsSync(p); } catch { return false; } };

// Where the data root lives is the user's choice (operator: "i want it on D:/ drive the whole install and models
// as C:/ drive is getting full"). A one-line pointer file next to the default location remembers it; the env var
// wins for dev runs. Nothing else (registry, PATH) is touched.
const LOCAL = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
const POINTER = path.join(LOCAL, 'AgentGen.location');
function readPointer() { try { const p = fs.readFileSync(POINTER, 'utf8').trim(); return p || null; } catch { return null; } }
function setDataRoot(dir) { fs.mkdirSync(dir, { recursive: true }); fs.writeFileSync(POINTER, dir); }
function freeBytes(dir) {
  // walk up until a folder exists, then ask the volume
  let d = path.resolve(dir);
  while (!exists(d) && path.dirname(d) !== d) d = path.dirname(d);
  try { const s = fs.statfsSync(d); return s.bavail * s.bsize; } catch { return null; }
}
// a half-downloaded model folder keeps *.incomplete parts under .cache; it is not present until those are gone
const hasIncomplete = dir => { try { return fs.readdirSync(path.join(dir, '.cache', 'huggingface', 'download'), { recursive: true }).some(f => String(f).endsWith('.incomplete')); } catch { return false; } };
const DATA = process.env.AGENTGEN_DATA || readPointer() || path.join(LOCAL, 'AgentGen');
const RUNTIME = path.join(DATA, 'runtime');

/** @param {string} root  repo root (dev) or the packaged app's resources dir */
function resolve(root) {
  const pythonExe = [path.join(RUNTIME, 'python', 'python.exe'), process.env.PY310, 'C:\\Program Files\\Python310\\python.exe'].find(exists) || null;
  const facePy = [path.join(DATA, 'venvs', 'face', 'Scripts', 'python.exe'), path.join(root, 'sidecars', 'face', '.venv', 'Scripts', 'python.exe')].find(exists) || null;
  const ollamaExe = [path.join(RUNTIME, 'ollama', 'ollama.exe'), path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Ollama', 'ollama.exe'), 'C:\\Program Files\\Ollama\\ollama.exe'].find(exists) || null;
  const models = exists(path.join(DATA, 'models')) ? path.join(DATA, 'models') : path.join(root, 'models');
  const ollamaModels = exists(path.join(DATA, 'ollama-models')) ? path.join(DATA, 'ollama-models') : null;
  const ditto = path.join(root, 'third_party', 'ditto-talkinghead');
  const sdCkpt = [path.join(models, 'sd', 'realistic-vision-v51.safetensors')].find(exists) || null;
  return {
    DATA, RUNTIME, pythonExe, facePy, ollamaExe, models, ollamaModels, ditto, sdCkpt,
    hf: path.join(models, 'hf'),
    have: {
      ditto: exists(path.join(models, 'ditto', 'ditto_cfg')) && exists(ditto),
      ltx: exists(path.join(models, 'ltx-video', 'ltxv-2b-0.9.8-distilled.safetensors')),
      wan: exists(path.join(models, 'wan2.2-ti2v-5b', 'model_index.json')) && exists(path.join(models, 'wan2.2-ti2v-5b', 'transformer')) && !hasIncomplete(path.join(models, 'wan2.2-ti2v-5b')),
      voice: exists(path.join(models, 'unity-voice-v2', 'acoustic.pt')),
      sd: !!sdCkpt,
      // Ollama's store moved layouts in 2026 (manifests-v2/ollama.com); accept either
      brain: ['manifests-v2/ollama.com/library/unity-local', 'manifests/registry.ollama.ai/library/unity-local']
        .some(rel => exists(path.join(ollamaModels || path.join(os.homedir(), '.ollama', 'models'), rel))),
    },
  };
}

module.exports = { DATA, RUNTIME, POINTER, resolve, exists, setDataRoot, freeBytes };
