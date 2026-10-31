// Face UI, M2 scope: mic with VAD + barge-in -> hub -> her timed voice back, with a placeholder mouth driven
// by the viseme track. The photoreal renderer (M3) replaces the #face element and subscribes to the same events.
import { createListener } from './listen.js';
import { createPlayer } from './player.js';
import { createEyes } from './eyes.js';

const $ = s => document.querySelector(s);
const log = $('#log'), diag = $('#diag'), mouth = $('#mouth'), face = $('#face'), visemeEl = $('#viseme'), stateEl = $('#state'), levelEl = $('#level i');

function addMsg(cls, text) {
  const d = document.createElement('div');
  d.className = `msg ${cls}`;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
  return d;
}
function setLight(id, ok, label) {
  const el = $(id); el.classList.toggle('ok', !!ok); el.classList.toggle('bad', ok === false);
  if (label !== undefined) el.querySelector('b') && (el.querySelector('b').textContent = label);
}
function setState(s) { stateEl.textContent = s; }

// ---- her mouth (placeholder) ---------------------------------------------------------------------------------
const WIDTH = { sil: 22, PP: 16, FF: 20, TH: 20, DD: 20, kk: 20, CH: 18, SS: 20, nn: 19, RR: 18, aa: 24, E: 24, ih: 23, oh: 16, ou: 13 };
function drawViseme(seg) {
  const v = seg?.v || 'sil', open = seg?.open ?? 0;
  mouth.style.height = `${4 + open * 16}%`;
  mouth.style.width = `${WIDTH[v] || 20}%`;
  visemeEl.textContent = v;
  window.dispatchEvent(new CustomEvent('viseme', { detail: seg || { v: 'sil', open: 0 } }));
}
// blink now and then
setInterval(() => { face.classList.add('blink'); setTimeout(() => face.classList.remove('blink'), 120); }, 3200 + Math.random() * 2000);

// ---- transport --------------------------------------------------------------------------------------------------
let ws, herLine = null, pending = '';
function connect() {
  ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
  ws.onopen = () => { setLight('#l-hub', true); addMsg('sys', 'connected'); };
  ws.onclose = () => { setLight('#l-hub', false); setTimeout(connect, 1500); };
  ws.onmessage = ev => onMsg(JSON.parse(ev.data));
}
function send(obj) { if (ws?.readyState === 1) ws.send(JSON.stringify(obj)); }

const player = createPlayer({
  onViseme: drawViseme,
  onSpeakingChange: v => { listener.setSheIsSpeaking(v); setState(v ? 'speaking' : 'idle'); },
});

function onMsg(m) {
  switch (m.type) {
    case 'hello': diagLine(`session ${m.session}${m.wakeWord?.length ? ' wake: ' + m.wakeWord.join('/') : ''}`); break;
    case 'status': setState(m.stage); break;
    case 'heard': {
      if (m.dropped) { addMsg('you dropped', `${m.text || '(nothing)'}  [${m.dropped}]`); setState('idle'); break; }
      addMsg('you', m.text); herLine = null; pending = ''; break;
    }
    case 'delta': {
      if (!herLine) herLine = addMsg('her', '');
      pending += m.text; herLine.textContent = pending; log.scrollTop = log.scrollHeight; break;
    }
    case 'speak': {
      player.enqueue(m);
      diagLine(`speak #${m.seq} ${m.delivery.emotion}/${m.delivery.speech_act} i=${m.delivery.intensity} p=${m.delivery.pace} ${m.duration}s synth ${m.synth_ms}ms${m.delivery.notes?.length ? ' (' + m.delivery.notes.join('; ') + ')' : ''}`);
      break;
    }
    case 'seen': for (const x of m.seen) diagLine(`sees ${x.source} (${x.ms} ms): ${x.text || x.error || 'nothing'}`); break;
    case 'speak_error': diagLine(`voice error: ${m.error}`); break;
    case 'look': {
      if (m.stage === 'rendering') { setState('changing…'); addMsg('sys', `rendering: ${m.prompt.slice(0, 90)}`); }
      else if (m.stage === 'live') { setState('idle'); diagLine(`look live on her face in ${m.face?.seconds}s`); }
      else if (m.stage === 'failed') { setState('idle'); addMsg('sys', `look failed: ${m.error}`); }
      else if (m.stage === 'image-only') { setState('idle'); diagLine(`look rendered; face swap: ${m.face?.error || 'face down'}`); }
      else if (m.stage === 'animating') { setState('animating…'); addMsg('sys', 'rendering her moving…'); }
      else if (m.stage === 'moving') { setState('idle'); diagLine(`clip ${m.clip?.frames} frames in ${m.clip?.seconds}s, live on her`); }
      else if (m.stage === 'clip-only') { setState('idle'); diagLine(`clip rendered; face swap: ${m.face?.error || 'face down'}`); }
      else if (m.stage === 'reel') { diagLine(`she ${m.motion} (+${m.clip?.frames} frames in ${m.clip?.seconds}s, ${m.reel} of motion)`); }
      break;
    }
    case 'image': {
      const d = document.createElement('div'); d.className = 'msg her';
      const img = document.createElement('img'); img.src = m.url; img.alt = m.prompt; img.title = m.prompt;
      img.style.cssText = 'max-width:100%;border-radius:8px;display:block;cursor:zoom-in';
      img.onclick = () => window.open(m.url, '_blank');
      d.appendChild(img); log.appendChild(d); log.scrollTop = log.scrollHeight;
      diagLine(`image seed ${m.seed} in ${m.seconds}s`);
      break;
    }
    case 'done': if (herLine) herLine.textContent = m.text; herLine = null; pending = ''; break;
    case 'interrupted': player.stop(); setState('idle'); herLine = null; pending = ''; diagLine(`interrupted (${m.reason})`); break;
    case 'error': addMsg('sys', `${m.where || 'hub'} error: ${m.error}`); setState('idle'); break;
    case 'reset': addMsg('sys', 'conversation reset'); break;
  }
}
function diagLine(s) { diag.textContent = (s + '\n' + diag.textContent).split('\n').slice(0, 40).join('\n'); }

// ---- mic ----------------------------------------------------------------------------------------------------------
function b64(int16) { const u8 = new Uint8Array(int16.buffer, int16.byteOffset, int16.byteLength); let s = ''; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return btoa(s); }

const listener = createListener({
  onLevel: rms => { levelEl.style.width = `${Math.min(100, rms * 900)}%`; },
  onSpeechStart: () => setState('listening…'),
  onSpeechEnd: ({ pcm, sampleRate, durationMs, speechMs }) => {
    setState('heard, sending');
    send({ type: 'utterance', pcm_b64: b64(pcm), sampleRate, durationMs, speechMs, frames: eyes.grab() });
  },
  onBargeIn: () => { player.stop(); send({ type: 'interrupt', reason: 'barge-in' }); },
  onTooShort: ({ speechMs }) => { diagLine(`too short to be a word (${speechMs}ms)`); setState('idle'); },
});

$('#btn-mic').onclick = async () => {
  player.unlock();
  if (listener.isRunning()) { listener.stop(); $('#btn-mic').textContent = 'Start mic'; $('#btn-mic').classList.remove('on'); $('#btn-mute').disabled = true; setLight('#l-mic', null); return; }
  const r = await listener.start();
  if (!r.ok) { addMsg('sys', r.reason); setLight('#l-mic', false); return; }
  $('#btn-mic').textContent = 'Stop mic'; $('#btn-mic').classList.add('on'); $('#btn-mute').disabled = false; setLight('#l-mic', true);
  diagLine(`mic at ${r.sampleRate} Hz; ${JSON.stringify(listener.stats())}`);
};
$('#btn-mute').onclick = () => { const m = listener.setMuted(!listener.isMuted()); $('#btn-mute').classList.toggle('on', m); $('#btn-mute').textContent = m ? 'Unmute' : 'Mute'; };
$('#btn-stop').onclick = () => { player.stop(); send({ type: 'interrupt', reason: 'shush' }); };
$('#btn-reset').onclick = () => { player.stop(); send({ type: 'reset' }); };
// inside the app window (not a plain browser on the hub) the main process can take everything down
if (window.agentgen?.isApp) {
  document.body.classList.add('app');
  $('#btn-shutdown').onclick = e => { e.target.disabled = true; e.target.textContent = 'Shutting down…'; player.stop(); window.agentgen.shutdown(); };
  $('#btn-uninstall').onclick = () => { player.stop(); window.agentgen.uninstall(); };
  const st = window.agentgen.storage;
  const size = b => b < 1024 ** 2 ? `${(b / 1024).toFixed(0)} KB` : b < 1024 ** 3 ? `${(b / 1024 ** 2).toFixed(1)} MB` : `${(b / 1024 ** 3).toFixed(2)} GB`;
  const drawStorage = async () => {
    const rows = await st.list();
    $('#storage-rows').replaceChildren(...rows.map(r => {
      const row = document.createElement('div'); row.className = 'row';
      const name = document.createElement('div'); name.textContent = r.label;
      const where = document.createElement('small'); where.textContent = r.dir; name.append(where);
      const sz = document.createElement('div'); sz.className = 'size'; sz.textContent = `${size(r.bytes)} · ${r.files} files`;
      const open = document.createElement('button'); open.textContent = 'Open folder'; open.onclick = () => st.open(r.id);
      const clr = document.createElement('button'); clr.textContent = 'Clear';
      clr.onclick = async () => { clr.disabled = true; clr.textContent = 'Clearing…'; if (r.id !== 'logs') player.stop(); await st.clear(r.id); drawStorage(); };
      row.append(name, sz, open, clr);
      return row;
    }));
  };
  $('#btn-storage').onclick = () => { $('#storage').classList.add('open'); drawStorage(); };
  $('#storage-close').onclick = () => $('#storage').classList.remove('open');
  $('#storage-fresh').onclick = async () => {
    player.stop();
    const r = await st.clear('all');
    if (r?.ok) { $('#log').replaceChildren(); addMsg('sys', 'reset to fresh: looks, clips, conversations and logs cleared'); }
    drawStorage();
  };
}
$('#text').addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target.value.trim()) { player.unlock(); send({ type: 'text', text: e.target.value.trim(), frames: eyes.grab() }); e.target.value = ''; }
});

// ---- her eyes: webcam and screen share, one still of each goes with every message -------------------------------------
const eyes = createEyes({
  preview: $('#eyes'),
  onChange: (source, on, err) => {
    const b = $(source === 'camera' ? '#btn-cam' : '#btn-screen');
    b.classList.toggle('on', on); b.textContent = `${on ? 'Stop' : 'Show'} ${source === 'camera' ? 'camera' : 'screen'}`;
    if (err) addMsg('sys', `${source}: ${err}`);
  },
});
$('#btn-cam').onclick = () => eyes.toggle('camera');
$('#btn-screen').onclick = () => eyes.toggle('screen');

// ---- health -------------------------------------------------------------------------------------------------------
async function health() {
  try {
    const h = await (await fetch('/api/health')).json();
    setLight('#l-voice', h.voice?.ok); setLight('#l-speech', h.speech?.ok); setLight('#l-brain', h.brain?.ok, h.brain?.model || '');
    setLight('#l-face', h.face?.ok, h.face?.ok ? `${h.face.fps} fps` : '');
    setLight('#l-image', h.image?.ok, h.image?.ok ? (h.image.loaded ? 'ready' : 'cold') : '');
    setLight('#l-eyes', h.vision?.ok);
    setFaceLive(!!h.face?.ok, h.face?.stream);
  } catch { setLight('#l-voice', false); setLight('#l-speech', false); setLight('#l-brain', false); setLight('#l-face', false); setLight('#l-image', false); setLight('#l-eyes', false); setFaceLive(false); }
}
const feed = $('#feed');
function setFaceLive(on, stream) {
  if (on && stream) { if (feed.getAttribute('src') !== stream) feed.src = stream; document.body.classList.add('live'); }
  else { document.body.classList.remove('live'); if (feed.getAttribute('src')) feed.removeAttribute('src'); }
}
health(); setInterval(health, 10000);
connect();
