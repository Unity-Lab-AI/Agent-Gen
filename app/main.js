// Agent Gen app: our own window, not a browser. Opens -> (first run: installs what she needs) -> supervisor starts
// everything -> her face fills the window. Closes -> everything she runs on is shut down with it.
'use strict';
const { app, BrowserWindow, session, ipcMain, dialog, shell } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const { Supervisor } = require('./supervisor');
const setup = require('./setup');

const DEV = !app.isPackaged;
const ROOT = DEV ? path.join(__dirname, '..') : process.resourcesPath;
const HUB = 'http://127.0.0.1:4646/';

let win = null;
let sup = null;
const status = {};

function log(...a) { console.log(new Date().toISOString().slice(11, 19), ...a); if (win && !win.isDestroyed()) win.webContents.send('agentgen:log', a.join(' ')); }

function createWindow() {
  win = new BrowserWindow({
    width: 1280, height: 860, minWidth: 720, minHeight: 540,
    backgroundColor: '#0b0b0f', title: 'Agent Gen',
    autoHideMenuBar: true, show: false,
    // spellcheck off: Chromium would download its dictionaries from Google; nothing leaves the machine
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, backgroundThrottling: false, spellcheck: false },
  });
  win.setMenuBarVisibility(false);
  // mic + camera + screen without a prompt: it is her app, on your machine
  session.defaultSession.setPermissionRequestHandler((wc, permission, cb) => cb(['media', 'display-capture', 'notifications', 'clipboard-read'].includes(permission)));
  session.defaultSession.setPermissionCheckHandler(() => true);
  win.once('ready-to-show', () => front());
  win.on('closed', () => { win = null; });
}

function front() {
  // A window opened by a process that is not in the foreground is not brought forward by Windows; insist.
  if (!win || win.isDestroyed()) return;
  win.show(); win.restore();
  // toggle on-top once: raises the window above everything, then releases it so other windows can take focus
  win.setAlwaysOnTop(true); win.moveTop(); win.focus(); win.setAlwaysOnTop(false);
  app.focus({ steal: true });
}

function bootHtml() {
  return `<!doctype html><meta charset="utf-8"><title>Agent Gen</title>
  <style>body{margin:0;background:#0b0b0f;color:#e8e6f0;font:15px system-ui;display:flex;align-items:center;justify-content:center;height:100vh}
  .box{width:460px}h1{font-size:14px;letter-spacing:.14em;text-transform:uppercase;color:#8c8aa0;margin:0 0 14px}
  .row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #262633}.ok{color:#39d98a}.bad{color:#ff5c5c}.wait{color:#8c8aa0}
  pre{font:11px ui-monospace,monospace;color:#8c8aa0;max-height:160px;overflow:auto;white-space:pre-wrap}</style>
  <div class="box"><h1>Agent Gen · waking her up</h1><div id="rows"></div><pre id="log"></pre></div>
  <script>
  const names=['brain','voice','speech','image','video','face','hub'];const rows=document.getElementById('rows');
  for(const n of names){rows.insertAdjacentHTML('beforeend','<div class="row"><span>'+n+'</span><span id="s-'+n+'" class="wait">waiting</span></div>')}
  window.agentgen.onStatus((n,s)=>{const e=document.getElementById('s-'+n);if(!e)return;e.textContent=s;e.className=s==='ready'||s==='adopted'?'ok':(s.startsWith('exited')||s==='failed'?'bad':'wait')});
  window.agentgen.onLog(l=>{const p=document.getElementById('log');p.textContent=(l+'\\n'+p.textContent).slice(0,4000)});
  </script>`;
}

async function boot() {
  await win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(bootHtml()));
  sup = new Supervisor(ROOT, log, { nodeBin: DEV ? null : process.execPath });
  await sup.start((name, s) => { status[name] = s; if (win && !win.isDestroyed()) win.webContents.send('agentgen:status', name, s); });
  if (status.hub === 'ready' || status.hub === 'adopted') {
    await win.loadURL(HUB);
    front();
  } else {
    dialog.showErrorBox('Agent Gen', `The hub did not come up. See ${path.join(sup.logDir || setup.DATA, 'hub.log')}`);
  }
}

app.whenReady().then(async () => {
  createWindow();
  const need = await setup.missing(ROOT);
  if (need.length) {
    log(`first run: missing ${need.map(s => s.id).join(', ')}`);
    await win.loadFile(path.join(__dirname, 'setup.html'));   // its Install button drives setup, then boot()
    return;
  }
  await boot();
});

app.on('window-all-closed', () => { shutdown(); app.quit(); });
app.on('before-quit', shutdown);
process.on('SIGINT', () => { shutdown(); process.exit(0); });
process.on('SIGTERM', () => { shutdown(); process.exit(0); });

let down = false;
function shutdown() { if (down) return; down = true; try { sup && sup.stop(); } catch {} }

ipcMain.handle('agentgen:status', () => status);
ipcMain.handle('agentgen:quit', () => app.quit());
ipcMain.handle('agentgen:setup:plan', async () => ({
  data: setup.DATA, free: setup.freeBytes(setup.DATA),
  steps: await Promise.all(setup.plan(ROOT).map(async s => ({ id: s.id, title: s.title, gb: s.gb, done: !!(await s.done()) }))),
}));
ipcMain.handle('agentgen:setup:start', async () => {
  try {
    await setup.install(ROOT, ev => { if (win && !win.isDestroyed()) win.webContents.send('agentgen:setup:event', ev); });
  } catch (e) {
    log('setup failed:', e.message);
    return { ok: false, error: String(e.message || e) };
  }
  await boot();
  return { ok: true };
});
// ---- storage: where her renders, logs and conversations live; clear any of them without reinstalling ----------------
// Runtimes, model weights and her brain (dataenvs, data\models, ...) are never touched here.
function storageDirs() {
  return [
    { id: 'looks', label: 'Her looks (images)', dir: path.join(setup.DATA, 'run', 'looks') },
    { id: 'clips', label: 'Her clips (videos)', dir: path.join(setup.DATA, 'run', 'clips') },
    { id: 'logs', label: 'Logs', dir: path.join(setup.DATA, 'logs') },
    { id: 'chat', label: 'Conversations and window cache', dir: app.getPath('userData') },
  ];
}
function du(dir) {
  let bytes = 0, files = 0;
  const walk = d => { let ents = []; try { ents = fs.readdirSync(d, { withFileTypes: true }); } catch { return; }
    for (const e of ents) { const f = path.join(d, e.name);
      if (e.isDirectory()) walk(f); else { try { bytes += fs.statSync(f).size; files++; } catch {} } } };
  walk(dir);
  return { bytes, files };
}
async function hubForget() {
  try { await fetch(HUB + 'api/forget', { method: 'POST', signal: AbortSignal.timeout(70000) }); } catch {}
}
function emptyDir(dir) {
  let left = 0;
  let ents = []; try { ents = fs.readdirSync(dir); } catch { return 0; }
  for (const n of ents) { try { fs.rmSync(path.join(dir, n), { recursive: true, force: true }); } catch { left++; } }
  return left;
}
async function clearStorage(id) {
  const d = storageDirs().find(x => x.id === id);
  if (!d) return { ok: false, error: `unknown ${id}` };
  if (id === 'logs') {
    // the running app and her engines are writing into these: empty them in place instead of deleting
    let left = 0;
    for (const n of (() => { try { return fs.readdirSync(d.dir); } catch { return []; } })()) {
      try { fs.truncateSync(path.join(d.dir, n), 0); } catch { left++; }
    }
    return { ok: true, left };
  }
  await hubForget();                                   // nothing may point at a file about to go
  if (id === 'chat') {
    await session.defaultSession.clearStorageData();
    await session.defaultSession.clearCache();
    return { ok: true, left: 0 };
  }
  return { ok: true, left: emptyDir(d.dir) };
}
ipcMain.handle('agentgen:storage:list', () => storageDirs().map(d => ({ id: d.id, label: d.label, dir: d.dir, ...du(d.dir) })));
ipcMain.handle('agentgen:storage:open', (_e, id) => {
  const d = storageDirs().find(x => x.id === id);
  if (!d) return false;
  fs.mkdirSync(d.dir, { recursive: true });
  shell.openPath(d.dir);
  return true;
});
ipcMain.handle('agentgen:storage:clear', async (_e, id) => {
  if (id !== 'all') return clearStorage(id);
  const r = await dialog.showMessageBox(win, {
    type: 'warning', buttons: ['Reset to fresh', 'Cancel'], defaultId: 1, cancelId: 1, title: 'Reset Agent Gen',
    message: 'Clear everything she made and said?',
    detail: 'Deletes her looks, her clips, every conversation and the window cache, and empties the logs. ' +
      'Her runtimes, model weights and brain stay installed: no reinstall, no downloads.',
  });
  if (r.response !== 0) return { ok: false, cancelled: true };
  const out = {};
  for (const id of ['looks', 'clips', 'chat', 'logs']) out[id] = await clearStorage(id);
  return { ok: true, out };
});

ipcMain.handle('agentgen:uninstall', async () => {
  const r = await dialog.showMessageBox(win, {
    type: 'warning', buttons: ['Remove everything', 'Cancel'], defaultId: 1, cancelId: 1, title: 'Uninstall Agent Gen',
    message: 'Remove everything Agent Gen installed for itself?',
    detail: `Deletes ${setup.DATA}: the Python runtime, model weights, her brain's models and logs (tens of gigabytes). ` +
      (app.isPackaged ? 'The app uninstaller runs afterwards.' : 'Dev checkout files are not touched.'),
  });
  if (r.response !== 0) return { ok: false };
  shutdown();
  const un = path.join(path.dirname(process.execPath), 'Uninstall Agent Gen.exe');
  if (app.isPackaged && fs.existsSync(un)) {
    // Installed: the NSIS uninstaller takes the app tree down and removes the app files; the marker tells it the
    // operator already said yes to the data folder, so it does not ask a second time (installer.nsh customUnInstall).
    // Deleting data from here would race the sidecars still letting go of files inside it.
    try { fs.mkdirSync(setup.DATA, { recursive: true }); fs.writeFileSync(path.join(setup.DATA, '.purge'), new Date().toISOString()); } catch {}
    spawn(un, [], { detached: true, stdio: 'ignore', windowsHide: false }).unref();
    app.quit();
    return { ok: true };
  }
  const ok = setup.uninstallData();
  app.quit();
  return { ok };
});
