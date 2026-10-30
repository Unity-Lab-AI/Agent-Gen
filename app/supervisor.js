// Supervisor: brings her up and takes her down. Spawns the sidecars and the hub as children of the app
// process, waits on their health endpoints, and kills the whole tree when the window closes.
// Operator, verbatim: "an .exe will work" / "that starts when opened and shuts all down when closed".
'use strict';
const { spawn, execSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');

const PY310 = process.env.PY310 || 'C:\\Program Files\\Python310\\python.exe';

function exists(p) { try { return fs.existsSync(p); } catch { return false; } }

function pick(...candidates) { return candidates.find(exists); }

function get(url, timeoutMs = 2000) {
  return new Promise(resolve => {
    const req = http.get(url, { timeout: timeoutMs }, res => {
      let body = '';
      res.on('data', d => body += d);
      res.on('end', () => { try { resolve({ status: res.statusCode, json: JSON.parse(body) }); } catch { resolve({ status: res.statusCode, json: null }); } });
    });
    req.on('error', () => resolve(null));
    req.on('timeout', () => { req.destroy(); resolve(null); });
  });
}

class Supervisor {
  /** @param {string} root  repo root (dev) or resources dir (packaged) */
  constructor(root, log = console.log) {
    this.root = root;
    this.log = log;
    this.children = new Map();   // name -> ChildProcess
    const basePy = pick(PY310, 'python');
    const facePy = pick(path.join(root, 'sidecars', 'face', '.venv', 'Scripts', 'python.exe'));
    const modelsDitto = path.join(root, 'models', 'ditto', 'ditto_cfg');
    this.services = [
      { name: 'voice',  port: 5123, health: 'http://127.0.0.1:5123/health', cmd: basePy, args: ['-u', path.join(root, 'sidecars', 'voice', 'server.py')] },
      { name: 'speech', port: 5125, health: 'http://127.0.0.1:5125/health', cmd: basePy, args: ['-u', path.join(root, 'sidecars', 'speech', 'server.py'), '--preload'] },
      { name: 'image',  port: 5124, health: 'http://127.0.0.1:5124/health', cmd: basePy, args: ['-u', path.join(root, 'sidecars', 'image', 'server.py')] },
      ...(facePy && exists(modelsDitto) ? [{ name: 'face', port: 5126, health: 'http://127.0.0.1:5126/health', cmd: facePy, args: ['-u', path.join(root, 'sidecars', 'face', 'server.py')] }] : []),
      { name: 'hub',    port: 4646, health: 'http://127.0.0.1:4646/api/health', cmd: process.env.NODE_BIN || 'node', args: [path.join(root, 'hub', 'server.mjs')],
        env: { FACE_PLAY_LOCAL: '1' } },
    ];
  }

  async portBusy(port) { return !!(await get(`http://127.0.0.1:${port}/health`, 800)) || !!(await get(`http://127.0.0.1:${port}/api/health`, 800)); }

  async start(onStatus = () => {}) {
    for (const s of this.services) {
      if (await this.portBusy(s.port)) { this.log(`${s.name}: already running on :${s.port}, adopting`); onStatus(s.name, 'adopted'); continue; }
      const logDir = path.join(this.root, '.run'); fs.mkdirSync(logDir, { recursive: true });
      const out = fs.openSync(path.join(logDir, `${s.name}.log`), 'a');
      const child = spawn(s.cmd, s.args, { cwd: this.root, env: { ...process.env, ...(s.env || {}) }, stdio: ['ignore', out, out], windowsHide: true });
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
        if (!this.children.has(s.name) && !(await this.portBusy(s.port))) { onStatus(s.name, 'failed'); break; }
        await new Promise(r => setTimeout(r, 700));
      }
    }
  }

  stop() {
    for (const [name, child] of this.children) {
      try {
        if (process.platform === 'win32') execSync(`taskkill /PID ${child.pid} /T /F`, { stdio: 'ignore' });
        else child.kill('SIGTERM');
        this.log(`${name}: stopped`);
      } catch (e) { this.log(`${name}: stop failed ${e.message}`); }
    }
    this.children.clear();
  }
}

module.exports = { Supervisor };
