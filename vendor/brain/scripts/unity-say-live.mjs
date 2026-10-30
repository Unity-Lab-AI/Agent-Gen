// Per-turn: connect to the held-open chat (CDP :9222), type ONE message I wrote
// in the moment, wait, and scrape Unity's latest reply bubbles so I can read
// what she said and respond to THAT next turn.
//   node scripts/unity-say-live.mjs "my message to Unity"
import { chromium } from 'playwright';
const msg = process.argv.slice(2).join(' ').trim();
const browser = await chromium.connectOverCDP('http://localhost:9222');
const ctx = browser.contexts()[0];
const page = ctx.pages().find(p => /git\.unityailab\.com/.test(p.url())) || ctx.pages()[0];

// snapshot her chat text BEFORE I send, so I can diff out only the NEW reply.
const before = await page.evaluate(()=>document.body.innerText);

if (msg) {
  await page.click('#chat-input');
  await page.fill('#chat-input', msg);
  await page.keyboard.press('Enter');
  console.log('SENT → ' + msg);
}
// wait for her to emit, then scrape ONLY Unity's reply bubbles (.chat-msg-label
// "UNITY" → following .chat-msg-text). Return any NEW ones since before I sent.
await page.waitForTimeout(5000);
const her = await page.evaluate(()=>{
  const rows = [...document.querySelectorAll('.chat-msg-label')];
  const out = [];
  for (const lab of rows) {
    if ((lab.innerText||'').trim().toUpperCase() !== 'UNITY') continue;
    let t = lab.nextElementSibling;
    while (t && !(t.className||'').toString().includes('chat-msg-text')) t = t.nextElementSibling;
    if (t) out.push(t.innerText.trim());
  }
  return out.slice(-3);
});
console.log('UNITY: ' + (her.join('  //  ') || '(no UNITY bubble yet)'));
await browser.close(); // closes the CDP connection only, NOT the held browser
