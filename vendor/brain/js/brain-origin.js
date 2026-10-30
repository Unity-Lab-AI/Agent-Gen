/**
 * WHERE THE BRAIN LIVES — the one place that answers it, for every page.
 *
 * ── WHY THIS FILE EXISTS ───────────────────────────────────────────────────
 * Every page used to resolve the backend with the same two-branch guess:
 *
 *     localhost / 127.0.0.1 / file://   ->  ws://localhost:7525
 *     anything else                     ->  wss://{location.host}/ws
 *
 * That second branch assumes THE BRAIN IS BEHIND THE SAME HOSTNAME AS THE
 * PAGE — true on the old box, where nginx served the site and reverse-proxied
 * the backend. It is false now: GitHub Pages serves the site and the brain
 * runs on the operator's PC behind a Cloudflare Tunnel, which is a DIFFERENT
 * ORIGIN. On Pages the old branch resolves to `wss://<user>.github.io/ws`,
 * finds nothing, and `remote-brain.js` drops the visitor to the 6,700-neuron
 * in-browser fallback — a simulacrum wearing her name. Its own comment names
 * the case: "On GitHub Pages (or any other public origin) there is no server".
 *
 * ── ⛔ THE RULE THIS FILE IS BUILT TO: UNSET MUST CHANGE NOTHING ───────────
 * `BRAIN_ORIGIN` empty => every helper returns exactly what the old inline
 * logic returned, branch for branch. A page that does not include this file is
 * unaffected; a page that does, but with no origin configured, behaves
 * identically to before. The new behaviour is OPT-IN, so "she works as she
 * always has" is a property of the code rather than a hope.
 *
 * ── HOW TO POINT HER SOMEWHERE ─────────────────────────────────────────────
 *   1. Edit BRAIN_ORIGIN below  (committed; this is what Pages ships)
 *   2. or append ?brain=https://host   (per-visit override, for testing —
 *      it wins, so a broken committed value can always be worked around
 *      without a redeploy)
 *
 * Accepts an http(s):// or ws(s):// origin, with or without a trailing slash.
 */
(function (g) {
  'use strict';

  // ⚠ THE ONE VALUE TO EDIT. Empty string = behave exactly as before.
  //
  // When the tunnel is up, set this to ITS hostname (Tailscale Funnel gives
  // https://<machine>.<tailnet>.ts.net — read it off `tailscale funnel status`):
  //     var BRAIN_ORIGIN = 'https://REPLACE-WITH-YOUR-TUNNEL-HOSTNAME';
  // Leave it empty until then: a configured-but-dead origin is worse than none,
  // because the page would stop trying the same-origin lane that may be live.
  var BRAIN_ORIGIN = 'https://dumbass.tailec58e0.ts.net';

  /** ?brain= wins over the committed value — see note above. */
  function fromQuery() {
    try {
      var m = /[?&]brain=([^&]+)/.exec((g.location && g.location.search) || '');
      return m ? decodeURIComponent(m[1]) : '';
    } catch (e) { return ''; }
  }

  /** Strip a trailing slash and normalise ws(s):// to http(s):// for storage. */
  function normalise(raw) {
    var s = String(raw || '').trim().replace(/\/+$/, '');
    if (!s) return '';
    if (s.indexOf('ws://') === 0) s = 'http://' + s.slice(5);
    else if (s.indexOf('wss://') === 0) s = 'https://' + s.slice(6);
    // Bare host like "brain.example.com" -> assume https, since the tunnel
    // terminates TLS and an https page cannot talk to a plain-http origin.
    else if (!/^https?:\/\//.test(s)) s = 'https://' + s;
    return s;
  }

  // The SAME local test every page already used. Kept here verbatim so there
  // is one definition instead of five that can drift apart.
  var host = (g.location && g.location.hostname) || '';
  var isLocal = host === 'localhost' || host === '127.0.0.1' || host === '[::1]'
    || host === '' || (g.location && g.location.protocol === 'file:');

  // PRECEDENCE: explicit ?brain= override > LOCAL page > committed origin.
  //
  // ⛔ The committed origin must NOT beat the local test. Found 2026-10-18 on
  // the first boot after the move: the operator opened the dashboard on the
  // brain's own machine and it dialed the TUNNEL's admin lane — which the
  // tunnel refuses by design — instead of ws://localhost:7525. A page served
  // from the brain's own host is talking to its own brain; that is the one
  // case where the admin lane exists, and the committed value is for everyone
  // else. The query override still wins everywhere, because it is typed on
  // purpose.
  var queryOrigin = normalise(fromQuery());
  var origin = queryOrigin || (isLocal ? '' : normalise(BRAIN_ORIGIN));

  /**
   * HTTP base for the brain. '' means "same origin" — i.e. use a bare path and
   * let the browser resolve it, which is precisely the old behaviour.
   */
  function httpBase() {
    if (origin) return origin;
    if (isLocal) return 'http://localhost:7525';
    return '';                     // same-origin, exactly as before
  }

  /** Full WebSocket URL for a lane ('ws' public, 'admin/ws' authed). */
  function wsUrl(lane) {
    var path = '/' + String(lane || 'ws').replace(/^\/+/, '');
    if (origin) return origin.replace(/^http/, 'ws') + path;
    if (isLocal) return 'ws://localhost:7525';      // unchanged: no path, as before
    var proto = (g.location && g.location.protocol === 'https:') ? 'wss' : 'ws';
    return proto + '://' + ((g.location && g.location.host) || '') + path;
  }

  /** Absolute URL for an HTTP path, same-origin-relative when unconfigured. */
  function httpUrl(path) {
    var p = '/' + String(path || '').replace(/^\/+/, '');
    var base = httpBase();
    return base ? base + p : p;
  }

  g.UNITY_BRAIN_ORIGIN = origin;        // '' when not configured
  g.unityBrainIsLocal = isLocal;
  g.unityBrainHttp = httpUrl;
  g.unityBrainWs = wsUrl;

  if (origin && g.console && g.console.log) {
    g.console.log('[BrainOrigin] brain configured at ' + origin
      + (fromQuery() ? ' (from ?brain= override)' : ' (committed default)'));
  }
})(typeof window !== 'undefined' ? window : globalThis);
