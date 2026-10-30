// Supervisor: brings her up and takes her down. Spawns her brain server, the sidecars and the hub as children of
// the app process, waits on their health endpoints, and kills the whole tree when the window closes.
// Operator, verbatim: "an .exe will work" / "that starts when opened and shuts all down when closed" /
// "the .exe prperly runs everything without fucking cmd windows poping open and closed all the fucking time".
//
// No console windows: every child is spawned with a hidden console (windowsHide). That matters most for the
// brain: Ollama starts a runner process per model load, and a runner started from a console-less parent gets a
// brand-new console that Windows Terminal flashes on screen. Under our hidden console it inherits and stays
// invisible. So the app runs its own private Ollama server on :11435 instead of talking to the tray app.
'use strict';
const { spawn, execSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { resolve, exists } = require('./paths');

function get(url, timeoutMs = 2000) {
  return new Promise(resolvePromise => {
    const req = http.get(url, { timeout: timeoutMs }, res => {
      let body = '';
      res.on('data', d => body += d);
      res.on('end', () => { try { resolvePromise({ status: res.statusCode, json: JSON.parse(body) }); } catch { resolvePromise({ status: res.statusCode, json: null }); } });
    });
    req.on('error', () => resolvePromise(null));
    req.on('timeout', () => { req.destroy(); resolvePromise(null); });
  });
}

const BRAIN_PORT = 11435;

class Supervisor {
  /** @param {string} root  repo root (dev) or resources dir (packaged) */
  constructor(root, log = console.log, { nodeBin } = {}) {
    this.root = root;
    this.log = log;
    this.children = new Map();   // name -> ChildProcess
    const P = resolve(root);
    this.paths = P;
    const py = P.pythonExe || 'python';
    // every sidecar finds its weights through these, wherever the installer put them
    const modelEnv = {
      AGENTGEN_MODELS: P.models,
      AGENTGEN_RUN: path.join(P.DATA, 'run'),          // looks and clips she renders (an uninstall removes them)
      DITTO_MODELS: path.join(P.models, 'ditto'), DITTO_DIR: P.ditto,
      UNITY_VOICE_DIR: path.join(P.models, 'unity-voice-v2'),
      UNITY_VIDEO_MODEL_DIR: path.join(P.models, 'ltx-video'),
      UNITY_VIDEO_WAN_DIR: path.join(P.models, 'wan2.2-ti2v-5b'),
      HF_HOME: P.hf,
      ...(P.sdCkpt ? { CORA_IMAGE_CHECKPOINT: P.sdCkpt } : {}),
    };
    const brainEnv = { OLLAMA_HOST: `127.0.0.1:${BRAIN_PORT}`, OLLAMA_KEEP_ALIVE: '30m', ...(P.ollamaModels ? { OLLAMA_MODELS: P.ollamaModels } : {}) };
    this.services = [
      // the brain server starts in data, not resources: its model runners inherit the folder, and a runner that
      // outlives a killed server would pin resources open and block the next update's copy
      ...(P.ollamaExe ? [{ name: 'brain', port: BRAIN_PORT, health: `http://127.0.0.1:${BRAIN_PORT}/api/tags`, cmd: P.ollamaExe, args: ['serve'], env: brainEnv, cwd: P.DATA }] : []),
      { name: 'voice',  port: 5123, health: 'http://127.0.0.1:5123/health', cmd: py, args: ['-u', path.join(root, 'sidecars', 'voice', 'server.py')], env: modelEnv },
      { name: 'speech', port: 5125, health: 'http://127.0.0.1:5125/health', cmd: py, args: ['-u', path.join(root, 'sidecars', 'speech', 'server.py'), '--preload'], env: modelEnv },
      { name: 'image',  port: 5124, health: 'http://127.0.0.1:5124/health', cmd: py, args: ['-u', path.join(root, 'sidecars', 'image', 'server.py')], env: modelEnv },
      ...(P.have.ltx ? [{ name: 'video', port: 5127, health: 'http://127.0.0.1:5127/health', cmd: py, args: ['-u', path.join(root, 'sidecars', 'video', 'server.py')], env: modelEnv }] : []),
      ...(P.facePy && P.have.ditto ? [{ name: 'face', port: 5126, health: 'http://127.0.0.1:5126/health', cmd: P.facePy, args: ['-u', path.join(root, 'sidecars', 'face', 'server.py')], env: modelEnv }] : []),
      { name: 'hub', port: 4646, health: 'http://127.0.0.1:4646/api/health',
        // the packaged app has no node on PATH: Electron's own binary runs the hub as node
        cmd: nodeBin || process.env.NODE_BIN || 'node', args: [path.join(root, 'hub', 'server.mjs')],
        env: { FACE_PLAY_LOCAL: '1', OLLAMA_URL: `http://127.0.0.1:${BRAIN_PORT}`, ...(nodeBin ? { ELECTRON_RUN_AS_NODE: '1' } : {}) } },
    ];
  }

  async portBusy(s) { const r = await get(s.health, 800); return !!(r && r.status === 200); }

  async start(onStatus = () => {}) {
    const logDir = path.join(this.paths.DATA, 'logs'); fs.mkdirSync(logDir, { recursive: true });
    this.logDir = logDir;
    for (const s of this.services) {
      if (await this.portBusy(s)) { this.log(`${s.name}: already running on :${s.port}, adopting`); onStatus(s.name, 'adopted'); continue; }
      const out = fs.openSync(path.join(logDir, `${s.name}.log`), 'a');
      const child = spawn(s.cmd, s.args, { cwd: s.cwd || this.root, env: { ...process.env, ...(s.env || {}) }, stdio: ['ignore', out, out], windowsHide: true });
      child.on('error', e => { this.log(`${s.name}: spawn failed ${e.message}`); onStatus(s.name, 'failed'); this.children.delete(s.name); });
      child.on('exit', code => { this.log(`${s.name} exited ${code}`); onStatus(s.name, `exited ${code}`); this.children.delete(s.name); });
      this.children.set(s.name, child);
      onStatus(s.name, 'starting');
      this.log(`${s.name}: spawned pid ${child.pid}`);
    }
    // wait for health, hub last
    for (const s of this.services) {
      const t0 = Date.now();
      while (Date.now() - t0 < 180000) {
        const r = await get(s.health, 3000);
        if (r && r.status === 200) { onStatus(s.name, 'ready'); this.log(`${s.name}: ready in ${((Date.now() - t0) / 1000).toFixed(1)}s`); break; }
        if (!this.children.has(s.name) && !(await this.portBusy(s))) { onStatus(s.name, 'failed'); break; }
        await new Promise(r => setTimeout(r, 700));
      }
    }
  }

  stop() {
    for (const [name, child] of this.children) {
      try {
        if (process.platform === 'win32') execSync(`taskkill /PID ${child.pid} /T /F`, { stdio: 'ignore', windowsHide: true });
        else child.kill('SIGTERM');
        this.log(`${name}: stopped`);
      } catch (e) { this.log(`${name}: stop failed ${e.message}`); }
    }
    this.children.clear();
  }
}

module.exports = { Supervisor, BRAIN_PORT, exists };
