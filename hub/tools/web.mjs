// Her hands, web half: search and fetch. Ported from C.O.R.A cora_tools/web.py (vendor/cora): DuckDuckGo's HTML
// results first, Bing's HTML page when DDG answers with a challenge (it did, 2026-10-14), a relevance check because
// Bing answers non-browser clients for the first word only, and a real browser (Playwright, when it is installed) as
// the last resort. Fetch pulls a page and keeps its readable text. No keys, nothing logged outside the hub.
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36';
const HEADERS = { 'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9', Accept: 'text/html,application/xhtml+xml' };

const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', '#39': "'", '#x27': "'", '#x2F': '/' };
const decode = s => String(s || '').replace(/&(#x[0-9a-f]+|#\d+|[a-z]+\d*);/gi, (m, e) =>
  ENT[e] ?? (e[0] === '#' ? String.fromCodePoint(e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : +e.slice(1)) : m));
const strip = html => decode(String(html || '').replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();

// two requests a second at most, across every caller (the source's token bucket)
let nextAt = 0;
async function pace() {
  const now = Date.now(), wait = Math.max(0, nextAt - now);
  nextAt = Math.max(now, nextAt) + 500;
  if (wait) await new Promise(r => setTimeout(r, wait));
}

async function get(url, { signal, timeoutMs = 12000 } = {}) {
  await pace();
  const r = await fetch(url, { headers: HEADERS, redirect: 'follow', signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(timeoutMs)]) : AbortSignal.timeout(timeoutMs) });
  return { status: r.status, url: r.url, type: r.headers.get('content-type') || '', text: await r.text() };
}

function ddgLink(href) {
  // DDG wraps results as //duckduckgo.com/l/?uddg=<real url>
  try { const u = new URL(decode(href), 'https://duckduckgo.com'); return u.searchParams.get('uddg') || u.href; } catch { return href; }
}

async function searchDdg(query, n, signal) {
  const r = await get(`https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`, { signal });
  if (r.status !== 200) return [];
  const links = [...r.text.matchAll(/<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/g)];
  const snips = [...r.text.matchAll(/<a[^>]+class="result__snippet"[^>]*>([\s\S]*?)<\/a>/g)];
  return links.slice(0, n).map((m, i) => ({ title: strip(m[2]), url: ddgLink(m[1]), snippet: strip(snips[i]?.[1]) }))
    .filter(x => /^https?:/.test(x.url) && !/duckduckgo\.com\/y\.js/.test(x.url));
}

async function searchBing(query, n, signal) {
  const r = await get(`https://www.bing.com/search?q=${encodeURIComponent(query)}&setlang=en&count=${Math.max(5, n)}`, { signal });
  if (r.status !== 200) return [];
  const out = [];
  for (const block of r.text.split('<li class="b_algo"').slice(1)) {
    const m = /<a[^>]+href="(https?:\/\/[^"]+)"[^>]*>([\s\S]*?)<\/a>/.exec(block);
    if (!m) continue;
    const p = /<p[^>]*>([\s\S]*?)<\/p>/.exec(block);
    out.push({ title: strip(m[2]), url: decode(m[1]), snippet: p ? strip(p[1]) : '' });
    if (out.length >= n) break;
  }
  return out;
}

/** A result set that ignores the query is no result (keep it if any result names a 4+ letter query word after the first). */
function relevant(results, query) {
  const words = (query.toLowerCase().match(/[a-z0-9]+/g) || []).filter(w => w.length >= 4);
  if (words.length < 2) return results;
  const rest = words.slice(1);
  return results.some(r => rest.some(w => `${r.title} ${r.snippet}`.toLowerCase().includes(w))) ? results : [];
}

let pw;   // Playwright, if it is installed next to the hub; undefined = not looked for yet, null = not there
async function browser() {
  if (pw === undefined) { try { pw = (await import('playwright')).chromium; } catch { pw = null; } }
  return pw;
}

const ENGINES = [
  ['duckduckgo', 'https://duckduckgo.com/?q={q}&ia=web&kl=us-en', 'li[data-layout="organic"], [data-testid="result"], article', 'h2', '[data-result="snippet"], .result__snippet'],
  ['brave', 'https://search.brave.com/search?q={q}&source=web', '#results [data-type="web"], #results .snippet', '.title, .snippet-title', '.snippet-description, .snippet-content, .desc'],
  ['bing', 'https://www.bing.com/search?q={q}&setlang=en', 'li.b_algo', 'h2 a', '.b_caption p, p'],
];

async function searchRendered(query, n) {
  const chromium = await browser();
  if (!chromium) return { results: [], engine: null };
  const b = await chromium.launch({ headless: true });
  try {
    const page = await (await b.newContext({ userAgent: UA, locale: 'en-US' })).newPage();
    for (const [name, tpl, box, title, snip] of ENGINES) {
      try {
        await page.goto(tpl.replace('{q}', encodeURIComponent(query)), { timeout: 20000, waitUntil: 'domcontentloaded' });
        await page.waitForSelector(box, { timeout: 8000 }).catch(() => {});
        const rows = await page.$$eval(box, (els, [t, s, n]) => els.slice(0, n * 2).map(e => {
          const a = e.querySelector('a[href^="http"]');
          return { title: (e.querySelector(t)?.textContent || '').trim(), url: a?.href || '', snippet: (e.querySelector(s)?.textContent || '').trim() };
        }), [title, snip, n]);
        const ok = relevant(rows.filter(r => r.title && /^https?:/.test(r.url)).slice(0, n), query);
        if (ok.length) return { results: ok, engine: `${name} (browser)` };
      } catch {}
    }
    return { results: [], engine: null };
  } finally { await b.close().catch(() => {}); }
}

/** Search the web. -> { ok, query, engine, results: [{title, url, snippet}] } or { ok: false, error }. */
export async function search(query, { n = 5, signal } = {}) {
  query = String(query || '').trim();
  if (!query) return { ok: false, error: 'empty query' };
  const tried = [];
  for (const [name, fn] of [['duckduckgo', searchDdg], ['bing', searchBing]]) {
    try {
      const res = relevant(await fn(query, n, signal), query);
      if (res.length) return { ok: true, query, engine: name, results: res };
      tried.push(`${name}: nothing`);
    } catch (e) { if (signal?.aborted) throw e; tried.push(`${name}: ${e.message}`); }
  }
  try {
    const r = await searchRendered(query, n);
    if (r.results.length) return { ok: true, query, engine: r.engine, results: r.results };
    tried.push(pw ? 'browser: nothing' : 'browser: playwright not installed');
  } catch (e) { tried.push(`browser: ${e.message}`); }
  return { ok: false, query, error: `no results (${tried.join('; ')})`, results: [] };
}

/** Readable text of an HTML page: scripts, styles, navigation and markup gone, block breaks kept. */
export function pageText(html) {
  const title = strip(/<title[^>]*>([\s\S]*?)<\/title>/i.exec(html)?.[1]);
  const body = String(html)
    .replace(/<(script|style|noscript|svg|nav|footer|header|form|iframe|template)\b[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<(br|\/p|\/div|\/li|\/h[1-6]|\/tr|\/section|\/article)\b[^>]*>/gi, '\n');
  const text = decode(body.replace(/<[^>]+>/g, ' ')).split('\n').map(l => l.replace(/\s+/g, ' ').trim()).filter(l => l.length > 1).join('\n');
  return { title, text };
}

/** Fetch a URL. -> { ok, url, title, text } (text capped at `maxChars`), falling back to a rendered page when the
 *  plain one is empty (a JavaScript-only site) and Playwright is installed. */
export async function fetchPage(url, { maxChars = 12000, signal } = {}) {
  url = String(url || '').trim();
  if (!url) return { ok: false, error: 'empty url' };
  if (!/^https?:\/\//i.test(url)) url = `https://${url}`;
  let u;
  try { u = new URL(url); } catch { return { ok: false, url, error: 'not a url' }; }
  // her hands reach the web, not this machine or its network
  if (/^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|0\.|\[?::1\]?$|169\.254\.)/i.test(u.hostname)) return { ok: false, url, error: 'local addresses are not fetched' };
  try {
    const r = await get(u.href, { signal, timeoutMs: 15000 });
    if (r.status >= 400) return { ok: false, url: r.url, error: `HTTP ${r.status}` };
    let { title, text } = /html|xml/.test(r.type) ? pageText(r.text) : { title: '', text: /text|json/.test(r.type) ? r.text : '' };
    if (text.length < 200 && /html/.test(r.type)) {
      const chromium = await browser();
      if (chromium) {
        const b = await chromium.launch({ headless: true });
        try {
          const page = await (await b.newContext({ userAgent: UA, locale: 'en-US' })).newPage();
          await page.goto(u.href, { timeout: 20000, waitUntil: 'networkidle' }).catch(() => {});
          ({ title, text } = pageText(await page.content()));
        } finally { await b.close().catch(() => {}); }
      }
    }
    if (!text) return { ok: false, url: r.url, error: `nothing readable (${r.type || 'unknown type'})` };
    return { ok: true, url: r.url, title, text: text.length > maxChars ? text.slice(0, maxChars) + ' …' : text, chars: text.length };
  } catch (e) {
    if (signal?.aborted) throw e;
    return { ok: false, url: u.href, error: String(e.message || e) };
  }
}
