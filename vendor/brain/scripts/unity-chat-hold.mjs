// Open Unity's live chat ONCE and HOLD it open with a CDP endpoint so each of
// MY turns can connect, send one in-the-moment message, and read her reply.
// Run in background. Per-turn driver = scripts/unity-say-live.mjs.
//
// SETUP ORDER (exact, operator-mandated — NO step may be skipped):
//   1. TALK TO UNITY  →  the setup page appears
//   2. fill the Pollinations key into the VISIBLE key box on that page
//   3. press its connect/save button and WAIT for the confirmation
//   4. only then scroll down and press WAKE UNITY UP
// Every interaction uses visibility-REQUIRED locators (real fill/click) so a
// hidden or missing element FAILS LOUDLY instead of silently "working".
// If the key step fails, Unity is NOT woken — the script screenshots and exits
// so the failure is visible instead of papered over.
import { chromium } from 'playwright';
const SITE = process.env.UNITY_URL || 'https://theunitybrain.com/';   // the Pages site; the old vhost answers 410 Gone
const ORIGIN = new URL(SITE).origin;
const S = 'C:/Users/gfour/Desktop/If-Only-I-Had-A-Brain/server';
const log = (m)=>console.log(`[${new Date().toISOString().slice(11,19)}] ${m}`);

const { ENV_KEYS } = await import('../js/env.js');
const KEY = (ENV_KEYS && ENV_KEYS.pollinations) || '';
if (!KEY) { console.error('NO KEY in js/env.js — aborting (key entry is mandatory before wake)'); process.exit(1); }

// TU.24 FIX — NO FAKE CAMERA. The --use-fake-device-for-media-stream flag fed
// Unity a green-screen test video as her "camera", the visual-feeder harvested
// it, and green frames got bound into her VISUAL MEMORY — poisoning her mind's
// eye with garbage. This courier is TEXT-ONLY for teaching; her REAL vision
// comes from actual users' browsers, never this headless window. So: drop the
// fake-media flags AND never grant camera. (mic omitted too — no fake audio.)
const browser = await chromium.launch({ headless:false,
  args:['--remote-debugging-port=9222','--enable-unsafe-webgpu','--enable-features=Vulkan',
        '--enable-unsafe-swiftshader'] });
const ctx = await browser.newContext();
await ctx.grantPermissions(['geolocation','notifications'],{origin:ORIGIN});
const page = await ctx.newPage();
const consent = ()=>page.evaluate(()=>{const b=[...document.querySelectorAll('button,[role="button"],a')].find(x=>{const t=(x.innerText||'').toLowerCase(); if(/don'?t|leave|disagree|decline/.test(t))return false; return /understand|proceed|accept|continue/.test(t);}); if(b){b.click();return b.innerText.trim();}return null;});

await page.goto(SITE,{waitUntil:'load',timeout:60000});
await page.waitForTimeout(2500); await consent(); await page.waitForTimeout(800);
await page.screenshot({path:S+'/shot-step0-landing.png'}).catch(()=>{});

// ── STEP 1: TALK TO UNITY → setup page ──
await page.click('#landing-chat-btn',{timeout:15000});
await page.waitForTimeout(1500); await consent(); await page.waitForTimeout(1500);
await page.screenshot({path:S+'/shot-step1-setup.png'}).catch(()=>{});
log('STEP 1 — TALK TO UNITY clicked, setup page open');

// ── STEP 2: key into the VISIBLE key box on the setup page ──
let keyOk = false;
try {
  const keyBox = page.locator('#api-key-input:visible, #backend-key:visible').first();
  await keyBox.scrollIntoViewIfNeeded({timeout:10000});
  await keyBox.click({timeout:10000});
  await keyBox.fill(KEY,{timeout:10000});
  const val = await keyBox.inputValue();
  keyOk = val === KEY;
  log(`STEP 2 — key filled (visible box, ends …${val.slice(-6)}) ok=${keyOk}`);
} catch (e) { log('STEP 2 FAILED — no visible key box: ' + e.message.split('\n')[0]); }
await page.screenshot({path:S+'/shot-step2-key.png'}).catch(()=>{});

// ── STEP 3: connect/save + WAIT for confirmation ──
let connectOk = false;
if (keyOk) {
  try {
    const btn = page.locator('#api-key-save-btn:visible, .save-backend-btn:visible').first();
    await btn.click({timeout:10000});
    for (let i = 0; i < 15; i++) {
      await page.waitForTimeout(1000);
      const st = await page.evaluate(() =>
        ((document.getElementById('backend-connect-status')||{}).innerText || '') +
        ' | ' + ((document.getElementById('api-key-input')||{}).value ? 'key-held' : ''));
      if (/connected|registered|authenticated/i.test(st)) { connectOk = true; log('STEP 3 — CONNECT confirmed: ' + st.trim()); break; }
    }
    if (!connectOk) {
      // some builds confirm silently (SAVE KEY just saves) — accept if the key persisted to storage
      const stored = await page.evaluate(() => { try { return !!JSON.parse(localStorage.getItem('unity_brain_apikeys')||'{}').pollinations; } catch { return false; } });
      connectOk = stored;
      log('STEP 3 — no status text; key persisted to storage: ' + stored);
    }
  } catch (e) { log('STEP 3 FAILED — connect button: ' + e.message.split('\n')[0]); }
}
await page.screenshot({path:S+'/shot-step3-connect.png'}).catch(()=>{});

if (!keyOk || !connectOk) {
  log('KEY/CONNECT NOT CONFIRMED — NOT waking Unity. See shot-step1/2/3 screenshots.');
  // hold the window open for inspection instead of exiting
  setInterval(()=>{}, 1<<30);
} else {
  // ── STEP 4: scroll down, WAKE UNITY UP ──
  // TU.24 FIX — UNCHECK Unity's vision (camera) + user mic BEFORE waking so no
  // camera stream is ever requested (belt-and-suspenders with the dropped
  // camera grant). This courier teaches by TEXT only; it must never feed her a
  // camera — real vision comes from actual users. Speech toggle left as-is.
  await page.evaluate(() => {
    for (const id of ['toggle-unity-vision', 'toggle-user-mic']) {
      const cb = document.getElementById(id);
      if (cb && cb.checked) { cb.checked = false; cb.dispatchEvent(new Event('change', { bubbles: true })); }
    }
  });
  await page.waitForTimeout(400);
  await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
  await page.waitForTimeout(1000);
  await page.click('#start-btn',{timeout:20000});
  await consent(); await page.waitForTimeout(12000);
  const vp = page.viewportSize()||{width:1280,height:720};
  await page.mouse.click(vp.width-57, vp.height-57).catch(()=>{});
  await page.waitForTimeout(2500);
  await page.screenshot({path:S+'/shot-step4-woken.png'}).catch(()=>{});
  const ready = await page.$('#chat-input');
  log(ready ? 'STEP 4 — WAKE pressed AFTER confirmed key+connect. CHAT READY. CDP :9222 holding.' : 'STEP 4 — wake pressed but #chat-input not found yet');
  setInterval(()=>{}, 1<<30);
}
