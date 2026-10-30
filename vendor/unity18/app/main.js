/**
 * main.js — wiring. The orb, the transcript, the gallery, the viewer, settings.
 *
 * ⭐ EVERYTHING HERE TALKS TO `serve/slot.js` AND NOTHING ELSE. When the trained
 * model replaces the stand-in, this file does not change — that is `U3E-4.6`'s
 * proof that the "pod is last" law was honoured.
 *
 * ⛔ The client RECONSTRUCTS. The wire carries coefficients; `reconstruct()` runs
 * here, in the page, on the phone. Her picture is an equation right up to the
 * screen.
 */

import { reconstruct, describeEquational, perceiveAudio, reconstructAudio } from '/codec/js/index.js';
import { createStore } from '/app/state.js';
import { createOrb } from '/app/orb.js';
import { createViewer } from '/app/viewer.js';
import { createListener } from '/app/listen.js';
import { createTurnBuilder, ACT } from '/app/turn.js';
import { createLatency } from '/app/latency.js';
import { imageToField, createCamera, createRecorder } from '/app/sense.js';
import { resolve as resolveAppearance, summarise, provenance } from '/app/appearance.js';
import { mergeSlice, renderable } from '/serve/progressive.js';

const $ = id => document.getElementById(id);
const store = createStore();
const orb = createOrb($('orb'));
let viewer = null;
let caps = {};
let modelInfo = { standIn: true, name: 'unknown' };
let busy = false;

// ── boot ─────────────────────────────────────────────────────────────────────
async function boot() {
  orb.start();
  setStatus('connecting…');
  try {
    const s = await (await fetch(api('/api/state'))).json();
    caps = s.capabilities || {};
    modelInfo = s.model || modelInfo;
    // ⛔ The banner is rendered from the model's OWN flag, on every boot AND on
    // every response — a client that only checks at boot would happily render
    // stand-in output as hers for the rest of the session.
    showStandIn(s.standIn);
    setStatus(idleHint());
  } catch (e) {
    setStatus('cannot reach the server — is `node serve/server.mjs` running?');
  }
  render();
  watchForVoice();
}

/**
 * ⛔ `U3E-8.26` — THE CLIENT HALF. Capabilities were read exactly once, at boot,
 *   and the launcher opens this page IMMEDIATELY while `install_voice` is still
 *   downloading in the background. So on a first run the page latched
 *   `speak:false` in its first second and held it for the session: her voice
 *   arrived minutes later and nothing on screen ever noticed. The server half
 *   re-attaches the methods; without this the page still would not ask again.
 *
 * ⚠ It stops the moment voice is present, and it never runs at all when voice
 *   was already up at boot — a poll that outlives its question is just noise on
 *   the loop.
 */
function watchForVoice() {
  if (caps.speak) return;
  const t = setInterval(async () => {
    try {
      const s = await (await fetch(api('/api/state'))).json();
      if (!s.capabilities || !s.capabilities.speak) return;
      caps = s.capabilities;
      clearInterval(t);
      setStatus('her voice just came up');
      syncMuteButton();
      render();
    } catch { /* server not answering yet — keep waiting, it is a fresh install */ }
  }, 6000);
}

function api(path) {
  const ep = store.get().settings.endpoint;
  return (ep ? ep.replace(/\/$/, '') : '') + path;
}

/**
 * ⛔ THE PERMANENT ON-SCREEN BANNER IS GONE, ON GEE'S CALL 2026-08-29:
 *   *"wtf is up with this header 'STAND IN' get rid of that i dont need that on
 *   the screen forever"*.
 *
 * ⭐ WHAT THE BANNER WAS FOR STILL HOLDS, and is kept where it costs nothing:
 *   `standIn` still rides EVERY `/api/state`, `/api/chat` and `/api/image`
 *   response, the server still prints it at boot, and the diagnostics panel
 *   still reads it in red. So nothing can mistake harness output for hers in a
 *   log, an audit or a bug report — the flag was never the thing he objected to,
 *   a strip of screen he cannot dismiss was.
 *
 * ⚠ The tracking is kept live rather than deleted: `modelInfo.standIn` is what
 *   the diagnostics panel renders, so it must stay current on every response.
 */
function showStandIn(on) {
  if (typeof on === 'boolean') modelInfo = { ...modelInfo, standIn: on };
  const el = $('standin');
  if (el) el.hidden = true;
}

/**
 * ⛔ SHE SAYS "DRAW THIS" AND NOTHING WAS LISTENING.
 *
 * Found by running Gate A against the legacy models. Her canon (`Unity1.txt`)
 * defines an inline image line — `[[img: full prompt]]` on its own line — and
 * she uses it constantly. U3E had **no image-line convention anywhere**
 * (grepped: zero hits), so a reply arrived as literal text on screen:
 *
 *     [[img: a darkly gothic Unity, wearing a black leather corset ...]]
 *
 * ⭐ THIS IS A CONTRACT THE TRAINED MODEL WILL NEED TOO, which is why it belongs
 *   here and not in the harness. A model that can draw has to be able to say
 *   WHEN to draw and WHAT — otherwise drawing is only ever something the person
 *   asks for by pressing a button, and she can never illustrate her own reply.
 *
 * ⚠ Returns the spoken text with the marker REMOVED. The prompt is hers to draw,
 *   not hers to read out — leaving it in means the voice path speaks a prompt.
 */
/**
 * ⛔⛔ SHE WAS EMITTING IMAGE LINES AND THE PARSER WAS REJECTING THEM.
 *
 * Reported from use: she described the picture in text instead of generating it,
 * as if the words that should trigger a drawing were not registering.
 *
 * ⚠ MEASURED, and the answer was the opposite of the complaint. Asked "show me
 *   your tits", she replied:
 *
 *       [img: An edgy, provocative selfie of Unity, with black h...
 *
 *   **SINGLE brackets.** The canon specifies `[[img: ...]]` and she writes
 *   `[img: ...]` a good share of the time — so the line was correct in intent,
 *   wrong by one character, and went to the screen as literal text. She had the
 *   catch word all along; the client refused to hear it.
 *
 * ⭐ A PARSER FOR A MODEL'S OUTPUT MUST BE GENEROUS ABOUT FORM AND STRICT ABOUT
 *   MEANING. Requiring an exact token from something that generates text is a
 *   losing bet — one bracket, a stray space, `image:` instead of `img:`, and the
 *   feature silently disappears with no error anywhere. Accept every shape that
 *   unambiguously means "draw this"; the payload is what matters.
 */
const IMG_LINE = /(?:\[\[|\[|\(\()\s*(?:img|image|pic|photo|generate|draw)\s*[:：]\s*([\s\S]*?)(?:\]\]|\]|\)\))/gi;

export function splitImageLines(raw) {
  const text = String(raw || '');
  const prompts = [];
  const spoken = text.replace(IMG_LINE, (_, p) => {
    const t = String(p || '').trim();
    if (t) prompts.push(t);
    return '';
  })
    // The wrapper often trails "Please provide any additional details…" after an
    // image line; that is addressed to a tool, not to the person.
    .replace(/^\s*Please provide any additional details[^\n]*$/gim, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  return { spoken, prompts };
}

// ── chat (U3E-8.14) ──────────────────────────────────────────────────────────
/**
 * ⭐ ONE TIMELINE. Pictures sit in their proper order inside the conversation
 *   chain, not in a separate stream beside it.
 *
 * Turns and pictures are separate stores with separate ids, so the only honest
 * ordering is the one that actually happened — both carry `at`, and they are
 * merged on it. ⚠ NOT by `turnId` association: a picture she drew unprompted
 * has no turn to hang off, and ordering by association would silently drop it
 * out of the conversation or stack it in the wrong place.
 *
 * ⚠ Ties break with the picture AFTER the words, because the reply is what
 *   caused the draw — `[[img: ...]]` is parsed out of a message that already
 *   exists, and the two can land in the same millisecond.
 */
function chatTimeline() {
  const s = store.get();
  const items = [
    ...s.turns.map(t => ({ kind: 'turn', at: t.at, id: t.id, t })),
    ...(s.gallery || []).map(g => ({ kind: 'art', at: g.at, id: g.id, g })),
  ];
  items.sort((a, b) => (a.at - b.at) || (a.kind === b.kind ? a.id - b.id : a.kind === 'turn' ? -1 : 1));
  return items;
}

const shortTime = ms => new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

function renderChat() {
  const body = $('chatBody');
  if (!body || $('sheetChat').hidden) return;
  // ⚠ Stick to the bottom only if the reader is ALREADY there. Yanking someone
  //   back down while they are reading history is the rudest thing a chat does.
  const atBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 80;
  body.textContent = '';

  for (const it of chatTimeline()) {
    if (it.kind === 'turn') {
      const d = document.createElement('div');
      d.className = `msg ${it.t.role}`;
      // ⭐ An attached picture renders in the bubble, on the sender's side —
      //   hers left, yours right — reconstructed from the field, same as her own.
      if (it.t.attachment && it.t.attachment.field) {
        const cv = document.createElement('canvas');
        cv.className = 'att';
        try {
          const img = reconstruct(it.t.attachment.field, 0);
          cv.width = img.width; cv.height = img.height;
          cv.getContext('2d').putImageData(new ImageData(img.data, img.width, img.height), 0, 0);
          cv.onclick = () => openViewer({ ...it.t.attachment, prompt: it.t.attachment.name, id: 'att' + it.t.id });
          d.appendChild(cv);
        } catch { /* an unreadable field shows nothing rather than a broken frame */ }
      }
      const b = document.createElement('div');
      b.className = 'bub';
      b.textContent = it.t.text;
      if (!it.t.text && it.t.attachment) b.textContent = `(${it.t.attachment.name})`;
      const w = document.createElement('div');
      w.className = 'when';
      w.textContent = shortTime(it.at) + (it.t.amendedAt ? ' · amended' : '');
      d.append(b, w);
      body.appendChild(d);
    } else {
      const g = it.g;
      const d = document.createElement('div');
      d.className = 'msg unity art';
      const cv = document.createElement('canvas');
      try {
        // ⭐ Reconstructed in the page from the coefficients, same as everywhere
        //   else. Her picture is an equation right up to the screen.
        const img = reconstruct(g.field, 0);
        cv.width = img.width; cv.height = img.height;
        cv.getContext('2d').putImageData(new ImageData(img.data, img.width, img.height), 0, 0);
      } catch { /* a field that will not decode is shown as an empty frame, below */ }
      cv.onclick = () => openViewer(g);
      const cap = document.createElement('div');
      cap.className = 'cap';
      cap.textContent = `${g.prompt || 'drawn'} · ${(g.coefficients || 0).toLocaleString()} coefficients · ${shortTime(it.at)}`;
      d.append(cv, cap);
      body.appendChild(d);
    }
  }

  // The generation in flight, so the conversation never looks stalled.
  if (busy) {
    const d = document.createElement('div');
    d.className = 'msg unity pend';
    const b = document.createElement('div');
    b.className = 'bub';
    b.textContent = '…';
    d.append(b);
    body.appendChild(d);
  }
  if (atBottom) body.scrollTop = body.scrollHeight;
}

/**
 * Her latest picture, on the main screen beside the orb.
 *
 * ⭐ IT HANDS OVER TO THE GALLERY AFTER 5 s — a picture shows on the main screen
 *   briefly, then moves aside to make room for the next one. Nothing is lost —
 *   it is already in the
 *   gallery the moment it is drawn; this only clears the orb screen so the next
 *   one has room and the words are readable.
 *
 * ⚠ The timer is keyed to the picture's id and cleared on every re-render, so a
 *   second picture arriving at 4 s does not inherit the first one's countdown
 *   and vanish after one.
 */
let recentTimer = 0;

function renderRecent() {
  const el = $('recent');
  if (!el) return;
  const g = (store.get().gallery || []).filter(x => !x.orphaned).slice(-1)[0];
  const hide = () => {
    el.hidden = true;
    el.dataset.id = '';
    $('orbscreen').classList.remove('withart');
  };
  if (!g || !$('sheetChat').hidden || !$('sheetGal').hidden) { hide(); return; }
  if (el.dataset.id === String(g.id)) { return; }   // already showing, timer running
  el.textContent = '';
  const cv = document.createElement('canvas');
  try {
    const img = reconstruct(g.field, 0);
    cv.width = img.width; cv.height = img.height;
    cv.getContext('2d').putImageData(new ImageData(img.data, img.width, img.height), 0, 0);
  } catch { el.hidden = true; return; }
  cv.onclick = () => openViewer(g);
  const cap = document.createElement('div');
  cap.className = 'cap';
  cap.textContent = g.prompt || 'drawn';
  el.append(cv, cap);
  el.dataset.id = String(g.id);
  el.hidden = false;
  $('orbscreen').classList.add('withart');

  clearTimeout(recentTimer);
  recentTimer = setTimeout(() => {
    // ⚠ Only clear if this is STILL the picture on screen. A newer one has its
    //   own timer and must not be cancelled by an older one expiring.
    if (el.dataset.id === String(g.id)) hide();
  }, 5000);
}

/**
 * ⚠ The hint used to ADVERTISE the workaround — "tap the orb to have her draw" —
 *   which is how it was found in use. A hint that names a mechanism teaches people the
 *   mechanism IS the interface. Just tell her.
 */
/**
 * Did the person ask to SEE something? Used only to decide whether to chase a
 * missing image line — see the backstop in `runGeneration`.
 *
 * ⚠ Deliberately narrow. It reads the PERSON'S words, never hers, and only the
 *   verbs that mean "put a picture in front of me". A loose match here would
 *   fire a second request on ordinary conversation, which costs a round trip and
 *   produces pictures nobody asked for.
 */
const PICTURE_ASK = /\b(show|see|look at|send|draw|paint|generate|make|take)\b[^.?!]{0,40}\b(me|us|it|you|your|yourself|pic|picture|photo|image|selfie|shot|portrait|drawing)\b|\b(pic|picture|photo|image|selfie)\b/i;

/**
 * ⚠ "see" is the ambiguous one and it has to be handled or the backstop fires
 *   on ordinary agreement. "I SEE WHAT YOU MEAN" is not a request for a
 *   picture; "let me see YOU" is. The difference is what follows the verb —
 *   a clause opener means understanding, an object means show me.
 */
const SEE_AS_UNDERSTANDING = /\b(see|understand)\s+(what|why|how|that|if|where|when)\b/i;

function wantsPicture(text) {
  const t = String(text || '');
  if (SEE_AS_UNDERSTANDING.test(t) && !/\b(pic|picture|photo|image|selfie|draw)\b/i.test(t)) return false;
  return PICTURE_ASK.test(t);
}

/** The most recent thing the PERSON said, for the backstop above. */
function lastUserText() {
  const turns = store.get().turns;
  for (let i = turns.length - 1; i >= 0; i--) if (turns[i].role === 'user') return turns[i].text;
  return '';
}

/**
 * ⛔ THREE SENTENCES, ENFORCED. She kept producing run-ons when the requirement
 *   is a maximum of three concise sentences, and normally everything she has to
 *   say in one normal-sized sentence.
 *
 * ⚠ THE CANON ALREADY ASKS FOR THIS and it does not hold. It says "ONE to THREE
 *   sentences, most of the time one", and replies still ran to a hundred words —
 *   the same shape as the image line: an instruction a model follows most of the
 *   time is not a guarantee, and the feature needs one.
 *
 * ⭐ So the ceiling is applied here, at a SENTENCE BOUNDARY, so a trimmed reply
 *   still reads as a finished thought rather than stopping mid-word the way a
 *   raw token cap does. `num_predict` stays generous enough that her image lines
 *   survive; this is what actually holds the length.
 *
 * ⚠ Abbreviations are handled — splitting naively on a full stop turns "Mr." and
 *   "3 a.m." into sentence ends and would cut her off after two words.
 */
const ABBREV = /\b(mr|mrs|ms|dr|st|vs|etc|inc|jr|sr|a\.m|p\.m|e\.g|i\.e)\.$/i;

function trimToSentences(text, max = 3) {
  const t = String(text || '').trim();
  if (!t) return t;
  const parts = t.split(/(?<=[.!?…])\s+/);
  const out = [];
  for (const p of parts) {
    if (out.length >= max) break;
    // An abbreviation is not the end of a sentence — glue it to the next piece.
    if (out.length && ABBREV.test(out[out.length - 1])) out[out.length - 1] += ' ' + p;
    else out.push(p);
  }
  return out.join(' ').trim();
}

function idleHint() {
  return caps.hear ? 'tap talk, or 💬 to chat — ask her for a picture and she draws it'
                   : 'tap 💬 to chat — ask her for a picture and she draws it';
}

function setStatus(t) { $('status').textContent = t; }
function setLast(t) { $('lastline').textContent = t || ''; }

// ── talking (U3E-8.6 / 8.7) ──────────────────────────────────────────────────
/**
 * ⛔ THE BUG THIS REPLACED, NAMED SO IT DOES NOT COME BACK
 *   This function opened `if (!text || busy) return;` — so anything said while
 *   she was working was **silently dropped**. That is exactly the failure
 *   `U3E-8.7` exists to prevent, sitting in the code the whole time.
 *
 * ⭐ `8.6` and `8.7` are ONE rule (see `app/turn.js`): when the input a
 *   generation was built on changes, abort and re-run. A revision REPLACES the
 *   recognised words; an amendment APPENDS. Neither ever makes a second turn.
 */
const turnBuilder = createTurnBuilder();
const latency = createLatency();          // U3E-8.10
let inflight = null;      // AbortController for the generation in flight
let userTurnId = null;    // the ONE turn this utterance owns
// ⚠ The endpoint silence (U3E-8.5, default 900 ms) is real dead air the person
//   spends waiting, so it counts toward the budget — and it is a TUNING CHOICE,
//   not a physical limit, which is exactly what a breakdown should expose.
let lastEndpointMs = 0;

/** Everything said or typed enters here. Nothing is dropped. */
function submit(text) {
  const t = String(text || '').trim();
  if (!t) return;
  const decision = turnBuilder.phase() === 'generating'
    ? turnBuilder.amend(t)                                  // U3E-8.7
    : (turnBuilder.revise(t, { final: true }), turnBuilder.settle());
  applyDecision(decision);
}

// ⚠ There is deliberately NO `reviseFromSpeech` wrapper here. `U3E-8.6`'s
//   partial-transcript entry point is `turnBuilder.revise()`, and nothing
//   produces partials until STT exists (`U3E-4B.3`). A wrapper with no caller
//   reads as wired when it is not — the dormant-code failure this family has
//   already audited once. It gets written when it has a producer.

function applyDecision(d) {
  if (d.act === ACT.HOLD || d.act === ACT.IGNORE) return;

  // ⛔ Appearance re-resolves on the FINAL text, not the first guess — an
  //   appearance set from a sentence that was then corrected would dress her
  //   from words nobody said.
  const changed = resolveAppearance(d.text, store.appearanceAt(null));
  const extra = changed ? { appearance: changed } : {};

  if (d.act === ACT.RERUN) {
    if (inflight) inflight.abort();
    // ⛔ UPDATE the same turn. A second turn here is the queue-it design the
    //   row forbids: it makes her answer a question already amended.
    if (userTurnId != null) store.updateTurn(userTurnId, { text: d.text, amendedAt: Date.now(), ...extra });
    setStatus(d.divergenceWord === -1
      ? `you added to that — re-running (${d.stalenessMs} ms in)`
      : `you changed word ${d.divergenceWord + 1} — re-running (${d.stalenessMs} ms in)`);
  } else {
    // ⭐ The attachment rides the turn it was sent with, so the conversation
    //   keeps them together and a reload still shows the picture beside the
    //   words it came with.
    if (attachNext) { extra.attachment = attachNext; attachNext = null; }
    const t = store.addTurn('user', d.text, extra);
    userTurnId = t.id;
    setLast('');
  }

  if (changed) { const s = summarise(changed); if (s) setStatus('now: ' + s); }
  render();
  runGeneration(d.epoch);
}

async function runGeneration(epoch) {
  const ctrl = new AbortController();
  inflight = ctrl;
  busy = true;
  orb.setState('thinking');
  // ⛔ U3E-8.10 — conversation is a LATENCY PRODUCT. The breakdown is measured
  //   per turn, and the stages that do not exist yet (STT, voice) are NAMED in
  //   the report rather than omitted, so the total reads as the floor it is.
  latency.begin(lastEndpointMs);
  lastEndpointMs = 0;
  latency.mark('compose');
  try {
    // ⛔ U3E-9B.3 — THE CONDITIONING GOES TO HER WORDS TOO, not just her
    //   pictures. `serve/slot.js` has always documented `chat({ messages,
    //   appearance })`, and nothing sent it: manifestation steered every image
    //   and never a single sentence, so she would look like a catgirl and talk
    //   like base Unity. A documented parameter with no producer and no
    //   consumer is the same class as the capability map that claimed methods
    //   it did not have.
    const sent = store.prefixFor(null);
    // ⚠ Dropping turns is a real change to what she is answering, so it is SAID.
    //   Silently shortening someone's conversation is how "she forgot what I
    //   told her" becomes unexplainable.
    const dropped = store.trimmedTurns ? store.trimmedTurns() : 0;
    if (dropped) setStatus(`thinking… (kept the last ${sent.length} turns, dropped ${dropped} older — her persona stays in context)`);
    const r = await post('/api/chat', {
      messages: sent,
      appearance: store.appearanceAt(null),
    }, ctrl.signal);
    latency.mark('wire');
    // ⛔ A reply from a superseded generation is not an answer to what was
    //   actually said. Rendering it is the stale answer `8.6` forbids.
    if (turnBuilder.accept(epoch).stale) return;
    userTurnId = null;
    showStandIn(r.model && r.model.standIn);
    // ⛔ Her image lines are DRAWN, not printed. See `splitImageLines`.
    const split = splitImageLines(r.text);
    const prompts = split.prompts;
    // ⛔ Three sentences maximum — see `trimToSentences`. Applied AFTER the image
    //   lines are pulled out, so a picture is never lost to the trim.
    const spoken = trimToSentences(split.spoken, 3);
    const turn = store.addTurn('unity', spoken);
    setLast(spoken);

    /**
     * ⛔⛔ DRAWING COMES FIRST, AND SPEECH DOES NOT GATE IT.
     *
     * Reported from use: it generated one picture, then never generated another
     * while still saying it was about to.
     *
     * The order was speak-then-draw, with `await speakIfPossible(...)` in front
     * of the draw loop — and `speakIfPossible` now awaits real audio playback.
     * **An `AudioContext` that will not start resolves NOTHING**: `src.onended`
     * never fires, the await never returns, the draw loop is never reached, and
     * `busy` stays true for every turn after it. One picture, then silence
     * forever, with her still saying she is about to draw.
     *
     * ⚠ MEASURED AROUND IT FIRST: the model emits `[[img: ...]]` on every turn
     *   including with full history (4 of 4), and the server generated three
     *   images back to back — so neither of the two obvious suspects was it.
     *
     * ⭐ They are independent actions and are now ordered by what the person is
     *   waiting for: the picture, then the voice.
     */
    /**
     * ⛔ IF YOU ASKED TO SEE SOMETHING, YOU GET A PICTURE. NOT A PARAGRAPH.
     *
     * Reported from use: no picture, just a huge write-up — a full prose
     * description of an image that was never drawn.
     *
     * ⚠ MEASURED AND THE SINGLE-MESSAGE CASE IS FINE: 8 of 8 show/draw phrasings
     *   emit an image line on a fresh turn. **It fails once there is CONVERSATION
     *   HISTORY** — she reads her own previous descriptive replies and continues
     *   the pattern, so the failure appears in real use and never in a test that
     *   sends one message.
     *
     * ⛔ SO COMPLIANCE IS NOT RELIED ON. A core feature cannot rest on a model
     *   choosing the right output shape every time. When the person's words ask
     *   to SEE something and nothing came back to draw, the client asks once
     *   more for the image line ALONE — short, low temperature, no history to
     *   drift against. That is deterministic where it needs to be.
     *
     * ⚠ It fires only on an explicit request, so ordinary talk never triggers a
     *   surprise picture or a second round trip.
     */
    let toDraw = prompts;
    if (!toDraw.length && wantsPicture(lastUserText())) {
      /**
       * ⛔ THE PICTURE IS BUILT FROM YOUR WORDS, NOT FROM HER COOPERATION.
       *
       * Still failing after the previous attempt: the reply was a long prose
       * description offering to paint the picture, with no image line anywhere.
       *
       * ⚠ THE FIRST BACKSTOP ASKED THE MODEL AGAIN, which was the same weakness
       *   taking a second turn: once there is conversation history she settles
       *   into describing pictures instead of drawing them, and asking the same
       *   model to comply once more inherits exactly that. Verified current
       *   before concluding it — canon loaded, parser and backstop both served —
       *   so this is behaviour, not stale code.
       *
       * ⭐ SO NOTHING IS ASKED. The request itself becomes the prompt: her
       *   identity is added server-side when the picture is of her, attire comes
       *   from what you actually said, and the adapter strips her name and the
       *   words that wreck a generation. **A core feature cannot depend on a
       *   language model choosing to emit a token.**
       *
       * ⚠ Her words still stand as her reply — she says what she says, and the
       *   picture happens regardless.
       */
      setStatus('drawing what you asked for…');
      toDraw = [lastUserText()];
    }

    for (const p of toDraw) {
      try { await drawWith(p, turn.id); }
      catch (e) { setStatus(e.absent ? e.message : `she tried to draw: ${e.message}`); }
    }
    // ⚠ Never allowed to take the turn down with it — see the bound in playField.
    try { await speakIfPossible(spoken, turn); }
    catch (e) { setStatus(`spoke, but: ${e.message}`); }
  } catch (e) {
    if (e.name === 'AbortError') return;   // superseded on purpose — not a failure
    setLast('');
    setStatus(e.absent ? e.message : `error: ${e.message}`);
  } finally {
    // ⚠ Only the CURRENT generation may clear the shared state. An aborted one
    //   settles later and would otherwise switch the orb off underneath its
    //   own replacement.
    if (inflight === ctrl) {
      inflight = null; busy = false;
      latency.mark('model');
      latency.end();
      orb.setState('idle'); setStatus(idleHint()); render();
    }
  }
}

/**
 * ⛔ Absent is not failed. With no `speak` capability the orb does NOT mime
 * speaking — it stays idle and says the capability is absent, because an orb
 * that animates silently is a lie about what the system can do.
 */
/**
 * ⛔⛔ SHE COMPUTED BANDS AND NEVER MADE A SOUND.
 *
 * This function asked for the audio field, ran `describeAudioBands()` on it, and
 * **stopped**. Nothing was ever played. The orb pulsed off a static summary of a
 * clip nobody heard — which looked exactly like working speech, because the orb
 * moved. ⚠ Fifth defect of this shape today: a surface that animates is not
 * evidence the thing behind it happened.
 *
 * ⭐ NOW: the field is reconstructed to PCM in the page, played through Web
 *   Audio, and the orb is driven by an `AnalyserNode` ON THE PLAYING AUDIO.
 *   THE REQUIREMENT: an equaliser-like orb that actively moves with the spoken
 *   voice's pitch, tone, frequency and volume — so the orb reads the REAL
 *   signal, frame by frame, rather than
 *   a precomputed average. Pitch and volume move it because they are in the
 *   audio, not because a curve was faked from a number.
 */
let voiceCtx = null;

/**
 * ⭐ HER VOICE, MUTED SEPARATELY FROM YOUR MICROPHONE — her speech has its own
 *   mute, independent of yours.
 *
 * ⚠ Two different things a single "mute" would conflate: `btnMute` is YOUR
 *   microphone, this is HER voice. Muting one must never silence the other.
 *
 * ⛔ MUTED MEANS THE REQUEST IS NEVER MADE. Fetching the audio and then not
 *   playing it would still cost a GPU synthesis and a round trip on every turn,
 *   for something nobody is going to hear.
 */
let voiceMuted = false;
let playing = null;        // the source currently sounding, so mute can stop it

function setVoiceMuted(v) {
  voiceMuted = !!v;
  // Silence anything already in the air — muting mid-sentence should be
  // immediate, not "from the next reply onward".
  if (voiceMuted && playing) { try { playing.stop(); } catch { /* already ended */ } }
  const el = $('btnVoice');
  if (el) {
    el.classList.toggle('muted', voiceMuted);
    el.textContent = voiceMuted ? '🔈' : '🔊';
    el.title = voiceMuted ? 'Unmute her voice' : 'Mute her voice';
  }
  return voiceMuted;
}

$('btnVoice').onclick = () => {
  const m = setVoiceMuted(!voiceMuted);
  setStatus(m ? 'her voice is muted — she still talks, you just will not hear it'
              : 'her voice is on');
};

async function speakIfPossible(text, turn) {
  if (voiceMuted) return;
  if (!caps.speak || !String(text || '').trim()) return;
  orb.setState('speaking');
  let r;
  try {
    r = await post('/api/speak', { text });
  } catch (e) {
    orb.setState('idle');
    setStatus(e.absent ? e.message : `could not speak: ${e.message}`);
    return;
  }
  if (!r || !r.audioField) { orb.setState('idle'); return; }
  try {
    await playField(r.audioField);
  } catch (e) {
    setStatus(`spoke, but playback failed: ${e.message}`);
  } finally {
    orb.setState('idle');
    if (listener) listener.setSheIsSpeaking(false);
  }
}

/**
 * Reconstruct → play → analyse. ⚠ The analyser runs on the SAME node chain that
 * reaches the speakers, so what the orb shows is what is audible. Tapping a
 * different source would drift and nobody would notice.
 */
async function playField(field) {
  const pcm = reconstructAudio(field);
  if (!pcm || !pcm.length) throw new Error('no samples in the audio field');
  voiceCtx = voiceCtx || new (window.AudioContext || window.webkitAudioContext)();
  if (voiceCtx.state === 'suspended') await voiceCtx.resume();

  const rate = field.sampleRate || 24000;
  const buf = voiceCtx.createBuffer(1, pcm.length, rate);
  const ch = buf.getChannelData(0);
  for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 32768;

  const src = voiceCtx.createBufferSource();
  src.buffer = buf;
  const an = voiceCtx.createAnalyser();
  an.fftSize = 1024;                // 512 bins -> 32 bands, and 1024 samples of
                                    // waveform: a coarse trace looks like a
                                    // zigzag, not a voice.
  an.smoothingTimeConstant = 0.75;  // the orb should breathe, not strobe
  src.connect(an);
  an.connect(voiceCtx.destination);

  // ⛔ Tell the listener she has the floor so barge-in can arm and she does not
  //   hear herself and interrupt her own sentence.
  if (listener) listener.setSheIsSpeaking(true);

  const freq = new Uint8Array(an.frequencyBinCount);
  // ⛔ THE TIME DOMAIN — the actual pressure samples. Without these the orb has
  //   no waveform to draw and falls back to a shape that merely reacts. The FFT
  //   gives the equaliser and the colour; THIS gives the wave.
  const time = new Float32Array(an.fftSize);
  const bands = new Float64Array(32);
  const per = Math.max(1, Math.floor(freq.length / bands.length));
  let raf = 0;
  const pump = () => {
    an.getByteFrequencyData(freq);
    an.getFloatTimeDomainData(time);
    for (let b = 0; b < bands.length; b++) {
      let acc = 0;
      for (let k = 0; k < per; k++) acc += freq[b * per + k] || 0;
      bands[b] = (acc / per) / 255;
    }
    orb.setBands(bands);
    orb.setWave(time);
    raf = requestAnimationFrame(pump);
  };

  /**
   * ⛔ THIS PROMISE IS BOUNDED. It used to resolve only on `src.onended`, and an
   *   `AudioContext` that will not start never fires it — so the await hung
   *   forever and took the whole turn loop with it. **A promise with exactly one
   *   resolution path, owned by something outside our control, is a deadlock
   *   waiting for the right browser state.**
   *
   * ⚠ The bound is the clip's own duration plus 2 s, so it never truncates real
   *   speech; it only catches the case where playback never happens at all. The
   *   timeout path SAYS it timed out rather than pretending she finished.
   */
  const seconds = pcm.length / rate;
  await new Promise((resolve, reject) => {
    let settled = false;
    const done = (why) => {
      if (settled) return;
      settled = true;
      playing = null;
      clearTimeout(guard);
      cancelAnimationFrame(raf);
      orb.setBands(new Float64Array(32));   // settle, do not freeze mid-pulse
      try { src.stop(); } catch { /* not started, or already stopped */ }
      try { src.disconnect(); an.disconnect(); } catch { /* already gone */ }
      if (why) setStatus(why);
      resolve();
    };
    const guard = setTimeout(
      () => done(`voice did not play (${voiceCtx.state}) — carried on without it`),
      Math.ceil(seconds * 1000) + 2000);
    src.onended = () => done(null);
    // ⚠ Held so muting mid-sentence can stop it immediately. Cleared in `done`
    //   so a stale reference can never be stopped after it has already ended.
    playing = src;
    try { src.start(); pump(); }
    catch (e) { clearTimeout(guard); cancelAnimationFrame(raf); playing = null; reject(e); }
  });
}

function describeAudioBands(field) {
  // field A -> 32 band amplitudes, normalised. Mirrors codec describeAudio.
  const out = new Float64Array(32);
  if (!field || !Array.isArray(field.chunks)) return out;
  for (const c of field.chunks) {
    const n = c.keep || 0;
    for (let i = 0; i < n; i++) out[i % 32] += Math.abs(c.qscale || 0);
  }
  let mx = 0; for (const v of out) if (v > mx) mx = v;
  if (mx) for (let i = 0; i < out.length; i++) out[i] /= mx;
  return out;
}

async function post(path, body, signal) {
  const r = await fetch(api(path), {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body), signal,
  });
  const j = await r.json();
  if (!r.ok) {
    const err = new Error(j.error || `HTTP ${r.status}`);
    err.absent = !!j.absent;
    throw err;
  }
  return j;
}

// ── drawing ──────────────────────────────────────────────────────────────────
/**
 * ⭐ THE ONLY WAY A PICTURE HAPPENS: she asked for it. Called from
 *   `splitImageLines` when her reply carries `[[img: ...]]`, so the picture is
 *   attached to the turn that produced it and lands in the gallery with the
 *   same progressive render the person-initiated path used to use.
 *
 * ⚠ It does NOT guard on `busy` — a draw she requested happens INSIDE the
 *   generation that produced it, where `busy` is already true by construction.
 *   Guarding here would silently drop every picture she ever asks for, which is
 *   the same silent-drop bug `submit()` used to have.
 */
async function drawWith(prompt, turnId) {
  if (!caps.image) { setStatus('she cannot draw yet — capability absent'); return null; }
  const wasBusy = busy;
  busy = true;
  orb.setState('thinking');
  setStatus('drawing…');
  try {
    // ⭐ U3E-5.3 — progressive. The picture appears coarse and sharpens, because
    //   each slice carries coefficients we genuinely did not have.
    const field = await drawProgressive(prompt);
    const entry = store.addArt({
      prompt,
      field,
      coefficients: field.equation_count,
      w: field.width, h: field.height,
      turnId,
      appearance: store.appearanceAt(null),
    });
    setStatus(`drawn — ${field.equation_count.toLocaleString()} coefficients`);
    openViewer(entry);
    return entry;
  } finally {
    if (!wasBusy) { orb.setState('idle'); busy = false; }
    render();
  }
}

/**
 * `U3E-5.3` — read the NDJSON slice stream and re-render as each arrives.
 *
 * ⛔ The first frame waits for all three channels (`renderable`). Rendering on Y
 * alone would show a grey picture that then colours, which reads as a bug even
 * though it is not.
 */
async function drawProgressive(prompt) {
  const r = await fetch(api('/api/image'), {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      prompt, progressive: true, appearance: store.appearanceAt(null),
    }),
  });
  if (!r.ok || !r.body) {
    const j = await r.json().catch(() => ({}));
    const e = new Error(j.error || `HTTP ${r.status}`); e.absent = !!j.absent; throw e;
  }

  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = '', meta = null, acc = null, shown = 0, total = 0;

  const paint = () => {
    if (!renderable(acc)) return;
    const img = reconstruct(acc, 0);
    if (viewer && viewer.supported && !$('sheetView').hidden) viewer.setImage(img);
    shown++;
    setStatus(`sharpening — ${acc.equation_count.toLocaleString()} of ${total.toLocaleString()} coefficients`);
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let nl;
    while ((nl = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      const d = JSON.parse(line);
      if (d.type === 'head') {
        meta = d.meta; total = d.total;
        showStandIn(d.model && d.model.standIn);
        if (!$('sheetView').hidden === false) open$('sheetView');
      } else if (d.type === 'slice') {
        acc = mergeSlice(acc, d, meta);
        paint();
        // yield so the browser actually paints between slices — without this
        // the whole stream lands in one frame and the property is invisible
        await new Promise(res => setTimeout(res, 0));
      }
    }
  }
  if (!acc) throw new Error('stream carried no coefficients');
  return acc;
}

// ── transcript, with edit-and-regenerate (U3E-8.14) ──────────────────────────
function renderLog() {
  const body = $('logBody');
  const st = store.get();
  $('logUndo').hidden = !st.lastDiscarded;
  body.innerHTML = '';
  if (!st.turns.length) {
    body.innerHTML = '<p class="muted">Nothing said yet. The transcript is kept even when you only use the orb.</p>';
    return;
  }
  for (const t of st.turns) {
    const d = document.createElement('div');
    d.className = 'turn ' + t.role;
    d.innerHTML = `<div class="who">${t.role === 'user' ? 'you' : 'unity'}${t.editedAt ? ' <span class="edited">· edited</span>' : ''}</div>
                   <div class="txt"></div>`;
    d.querySelector('.txt').textContent = t.text;
    if (t.role === 'user') {
      const act = document.createElement('div');
      act.className = 'act';
      const b = document.createElement('button');
      b.className = 'txt'; b.textContent = 'Edit & regenerate';
      b.onclick = () => beginEdit(t, d);
      act.appendChild(b);
      d.appendChild(act);
    }
    body.appendChild(d);
  }
}

function beginEdit(turn, node) {
  const ta = document.createElement('textarea');
  ta.value = turn.text;
  const act = document.createElement('div');
  act.className = 'act';
  const save = document.createElement('button');
  save.className = 'txt'; save.textContent = 'Save & re-run';
  const cancel = document.createElement('button');
  cancel.className = 'txt'; cancel.textContent = 'Cancel';
  act.append(save, cancel);
  node.querySelector('.txt').replaceWith(ta);
  node.querySelector('.act').replaceWith(act);

  cancel.onclick = renderLog;
  save.onclick = async () => {
    // ⛔ Dry run first: say exactly what will be lost. "every since get rest" is
    // destructive and a thumb on a phone must not trigger it blind.
    const pre = store.rewindTo(turn.id, ta.value, false);
    if (pre && (pre.turnsLost || pre.artOrphaned)) {
      const ok = confirm(
        `Re-running from here discards ${pre.turnsLost} later turn(s)` +
        (pre.artOrphaned ? ` and orphans ${pre.artOrphaned} picture(s) in the gallery` : '') +
        '.\n\nThe last discarded branch stays recoverable for one step.\n\nContinue?'
      );
      if (!ok) return;
    }
    store.rewindTo(turn.id, ta.value, true);
    renderLog();
    await regenerateFrom(turn.id);
  };
}

/** Generation is a pure function of the prefix — that is what makes this work. */
async function regenerateFrom(turnId) {
  busy = true;
  orb.setState('thinking');
  setStatus('re-running from the edit…');
  try {
    // ⛔ The rewind path carries it too. `appearanceAt(turnId)` reads the LIST,
    //   so a re-run gets the register in force at that point in the branch —
    //   not whatever is current. Sending the current one would make a rewind
    //   answer in a voice the prefix cannot explain (U3E-8.14).
    const r = await post('/api/chat', {
      messages: store.prefixFor(turnId),
      appearance: store.appearanceAt(turnId),
    });
    showStandIn(r.model && r.model.standIn);
    store.addTurn('unity', r.text || '');
    setLast(r.text || '');
  } catch (e) {
    setStatus(e.absent ? e.message : `error: ${e.message}`);
  } finally {
    orb.setState('idle'); busy = false; setStatus(idleHint()); render();
  }
}

// ── gallery ──────────────────────────────────────────────────────────────────
function renderGallery() {
  const grid = $('grid');
  const st = store.get();
  grid.innerHTML = '';
  $('galNote').textContent =
    `${st.gallery.length} of ${st.settings.galleryCap} kept. Stored as fields (kilobytes), not pictures — ` +
    `each one re-renders at whatever size this screen wants.`;
  if (!st.gallery.length) {
    grid.innerHTML = '<p class="muted">Nothing drawn yet.</p>';
    return;
  }
  for (const g of st.gallery) {
    const card = document.createElement('div');
    card.className = 'card' + (g.orphaned ? ' orphan' : '');
    const cv = document.createElement('canvas');
    card.appendChild(cv);
    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.innerHTML = `<b></b>${g.w}×${g.h} · ${(g.coefficients || 0).toLocaleString()} coefficients` +
      (g.orphaned ? '<br><span style="color:var(--warn)">orphaned by an edit</span>' : '');
    meta.querySelector('b').textContent = g.prompt || '(untitled)';
    card.appendChild(meta);

    const row = document.createElement('div');
    row.className = 'row';
    const open = document.createElement('button');
    open.className = 'txt'; open.textContent = 'View';
    open.onclick = () => openViewer(g);
    const save = document.createElement('button');
    save.className = 'txt'; save.textContent = 'Save as…';
    save.onclick = () => saveArt(g, save);
    const del = document.createElement('button');
    del.className = 'txt danger'; del.textContent = 'Delete';
    del.onclick = () => { store.deleteArt(g.id); render(); };
    row.append(open, save, del);
    card.appendChild(row);
    grid.appendChild(card);

    // draw the thumbnail from the FIELD, in the page
    try {
      const img = reconstruct(g.field, 0);
      cv.width = img.width; cv.height = img.height;
      cv.getContext('2d').putImageData(new ImageData(img.data, img.width, img.height), 0, 0);
    } catch (e) {
      meta.innerHTML += '<br><span style="color:var(--bad)">field failed to decode</span>';
    }
  }
}

/**
 * ⭐ `U3E-8.27` — SAVE AS, beside View and Delete: every picture needs a download
 *   / save-as option alongside the other two buttons.
 *
 * ⛔ IT SAVES THE FULL FIELD, NOT THE THUMBNAIL. The card shows a small canvas,
 *   but `reconstruct(field, 0)` returns the picture at its native size and full
 *   fidelity — `0` is the deviation factor, and anything above it discards
 *   coefficients. Encoding the on-screen element would have quietly written a
 *   downscaled copy, and a save that silently loses detail is worse than none.
 *
 * ⚠ A REAL Save As DIALOG WHERE THE BROWSER HAS ONE. `showSaveFilePicker` is
 *   what lets you choose the folder and the name, which is what was asked for;
 *   the anchor path underneath it is the same save minus the dialog, for a
 *   browser that does not implement the picker (every phone, today). That is
 *   the browser's own limit, not a capability we degrade on purpose.
 *
 * ⚠ The `AbortError` branch is a person clicking Cancel. It is not a failure and
 *   it does not get reported as one.
 */
async function saveArt(g, btn) {
  const label = btn ? btn.textContent : null;
  if (btn) { btn.disabled = true; btn.textContent = 'saving…'; }
  try {
    const img = reconstruct(g.field, 0);
    const cv = document.createElement('canvas');
    cv.width = img.width; cv.height = img.height;
    cv.getContext('2d').putImageData(new ImageData(img.data, img.width, img.height), 0, 0);
    const blob = await new Promise((res, rej) =>
      cv.toBlob(b => b ? res(b) : rej(new Error('could not encode the picture')), 'image/png'));

    // Her own words for the file name, so a folder of these is readable later.
    const stem = (g.prompt || 'unity')
      .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'unity';
    const name = `${stem}-${img.width}x${img.height}.png`;

    if (window.showSaveFilePicker) {
      const h = await window.showSaveFilePicker({
        suggestedName: name,
        types: [{ description: 'PNG image', accept: { 'image/png': ['.png'] } }],
      });
      const w = await h.createWritable();
      await w.write(blob);
      await w.close();
    } else {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    }
    setStatus(`saved ${name}`);
  } catch (e) {
    if (e && e.name === 'AbortError') setStatus(idleHint());   // cancelled, not failed
    else setStatus(`could not save: ${e.message}`);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = label; }
  }
}

/**
 * `U3E-7.6` — walk the gallery. Her recent fields hang in one space.
 * ⛔ Bounded: every frame held is a live GPU texture, and the drop count is
 * reported rather than hidden — a silent cap reads as "that is all there is".
 */
$('galSpace').onclick = () => {
  const st = store.get();
  if (!st.gallery.length) { setStatus('nothing to walk yet'); return; }
  $('sheetGal').hidden = true;
  open$('sheetView');
  $('vTitle').textContent = 'Gallery in space';
  if (!viewer) viewer = createViewer($('vcanvas'));
  if (!viewer.supported) { $('vnote').textContent = viewer.reason; return; }

  const imgs = [];
  for (const g of st.gallery) {
    try { imgs.push(reconstruct(g.field, 0)); } catch (e) { /* a bad field is skipped, and counted below */ }
  }
  const r = viewer.setScene(imgs);
  viewer.setSnap(false);          // a scene only makes sense with snap off
  syncSnapButton();
  viewer.start();
  const skipped = st.gallery.length - imgs.length;
  $('vnote').textContent =
    `${r.shown} of ${st.gallery.length} hanging` +
    (r.dropped ? ` · ${r.dropped} beyond the ${r.cap}-frame cap` : '') +
    (skipped ? ` · ${skipped} failed to decode` : '') +
    ' — drag to look, stick to move';
};

$('galClear').onclick = () => {
  const n = store.get().gallery.length;
  if (!n) return;
  // ⛔ Irreversible, and it says so with the count before it runs.
  if (confirm(`Delete all ${n} picture(s)? This cannot be undone.`)) {
    store.clearGallery(); render();
  }
};

// ── viewer ───────────────────────────────────────────────────────────────────
function openViewer(entry) {
  open$('sheetView');
  $('vTitle').textContent = entry.prompt || 'Viewer';
  if (!viewer) viewer = createViewer($('vcanvas'));
  if (!viewer.supported) {
    $('vnote').textContent = viewer.reason + ' — showing nothing rather than pretending.';
    return;
  }
  // ⛔ Leaving a previous scene up would show her gallery behind a single
  //   picture and hold every one of those textures alive.
  viewer.clearScene();
  viewer.setImage(reconstruct(entry.field, 0));
  viewer.setSnap(true);
  syncSnapButton();
  viewer.start();
  $('vnote').textContent = '';
}

function syncSnapButton() {
  const on = viewer && viewer.isSnapped();
  $('vSnap').textContent = 'Snap: ' + (on ? 'on' : 'off');
  $('stick').hidden = on || !isTouch();
  updateViewerHud();
}

/**
 * ⚠ THE MAGNIFICATION IS STATED, because "infinite zoom" is not what this is
 *   and a viewer that implies it would be lying. Past 1:1 the picture is being
 *   ENLARGED — the field holds a finite number of coefficients at a banked size
 *   and cannot be asked for detail nobody banked. The number lets you see
 *   exactly where that line is instead of wondering why it went soft.
 */
function updateViewerHud() {
  if (!viewer || !viewer.supported) return;
  const on = viewer.isSnapped();
  const z = viewer.zoomLevel ? viewer.zoomLevel() : 1;
  const zt = z > 1.05 ? `  ·  ${z.toFixed(1)}× — enlarging what was banked` : '';
  $('vnote').textContent = on
    ? (z > 1.05 ? zt.trim() : '')
    // ⚠ Honest about flatness. No fake bevel, no canned parallax.
    : 'Snap off — WASD move, mouse look (click to capture, Esc to release), Shift sprint, '
      + 'Space/C up-down, wheel zoom. A 2-D field is genuinely flat, so off-axis shows a card.'
      + zt;
}

const isTouch = () => matchMedia('(pointer: coarse)').matches;

$('vSnap').onclick = () => { if (viewer && viewer.supported) { viewer.setSnap(!viewer.isSnapped()); syncSnapButton(); } };
// ⛔ Two distinct actions, never disabled.
$('vResnap').onclick = () => viewer && viewer.supported && viewer.resnap();
$('vRecenter').onclick = () => viewer && viewer.supported && viewer.recenter();

// desktop: drag to look, wheel to dolly
(() => {
  const cv = $('vcanvas');
  let dragging = false, lx = 0, ly = 0;
  cv.addEventListener('pointerdown', e => {
    if (!viewer || viewer.isSnapped()) return;
    dragging = true; lx = e.clientX; ly = e.clientY;
    /**
     * ⛔ `setPointerCapture` THROWS on a pointer that is no longer active, and
     *   an uncaught throw here reached the page-level error handler and painted
     *   the boot-failure banner over the Close button.
     *
     * Reported from use: errors popping up that blocked the close button on the
     * image viewer — `InvalidStateError: Failed to execute 'setPointerCapture'`.
     *
     * ⚠ It is expected, not exceptional: pointer LOCK is now available on this
     *   same canvas, and once the pointer is locked the browser considers it
     *   gone for capture purposes. Capture is an optimisation — it keeps a drag
     *   alive if the cursor leaves the element — so failing to get it costs
     *   nothing and must never take the page down.
     */
    try { cv.setPointerCapture(e.pointerId); } catch { /* locked, or already released */ }
  });
  cv.addEventListener('pointermove', e => {
    if (!dragging || !viewer) return;
    viewer.look(e.clientX - lx, e.clientY - ly);
    lx = e.clientX; ly = e.clientY;
  });
  cv.addEventListener('pointerup', e => { dragging = false; });

  /**
   * ⭐ POINTER LOCK — exactly like the PC controls of a multiplayer shooter.
   *   Click the canvas with snap off and the mouse is captured: the cursor
   *   disappears, look is unlimited in every direction, and Esc releases it.
   *   Drag-to-look still works untouched, because an S23 has no pointer to lock
   *   and touch is a first-class equal here, not a fallback.
   */
  cv.addEventListener('click', () => {
    if (viewer && !viewer.isSnapped() && cv.requestPointerLock &&
        document.pointerLockElement !== cv) {
      cv.requestPointerLock();
    }
  });
  document.addEventListener('mousemove', e => {
    // ⚠ Only while LOCKED. Reading movementX unlocked would spin the camera
    //   whenever the mouse crossed the canvas without a button down.
    if (document.pointerLockElement === cv && viewer) viewer.look(e.movementX, e.movementY);
  });
  document.addEventListener('pointerlockchange', () => {
    if (document.pointerLockElement !== cv && viewer) viewer.key('__release', false);
  });

  cv.addEventListener('wheel', e => {
    if (!viewer) return;
    e.preventDefault();
    // ⛔ The wheel works SNAPPED TOO. It used to be ignored unless snap was off,
    //   so the only way to look closer at a picture was to unsnap and fly at
    //   it — which is exactly how you end up passing through it. `dolly()`
    //   holds at the plane and turns further scrolling into magnification.
    if (viewer.isSnapped()) viewer.setSnap(false);
    // ⭐ Zoom toward the CURSOR, not the centre. NDC: -1..1 with +y up, which is
    //   why the y term is flipped — client coords grow downward.
    const r = cv.getBoundingClientRect();
    const nx = r.width ? ((e.clientX - r.left) / r.width) * 2 - 1 : 0;
    const ny = r.height ? 1 - ((e.clientY - r.top) / r.height) * 2 : 0;
    viewer.dolly(-e.deltaY * 0.002, nx, ny);
    updateViewerHud();
  }, { passive: false });

  addEventListener('keydown', e => {
    if (!viewer || $('sheetView').hidden) return;
    // ⚠ Never steal typing. The composer and the transcript editor are real
    //   inputs and WASD in them must be letters, not movement.
    const t = e.target && e.target.tagName;
    if (t === 'INPUT' || t === 'TEXTAREA') return;
    viewer.key(e.key.length === 1 ? e.key.toLowerCase() : e.key, true);
  });
  addEventListener('keyup', e => viewer && viewer.key(e.key.length === 1 ? e.key.toLowerCase() : e.key, false));
})();

// touch: the thumb stick — an equal input path, not a fallback
(() => {
  const s = $('stick'), knob = s.querySelector('i');
  let id = null, cx = 0, cy = 0;
  s.addEventListener('pointerdown', e => {
    const r = s.getBoundingClientRect();
    cx = r.left + r.width / 2; cy = r.top + r.height / 2;
    id = e.pointerId; s.setPointerCapture(id);
  });
  s.addEventListener('pointermove', e => {
    if (e.pointerId !== id) return;
    const dx = Math.max(-1, Math.min(1, (e.clientX - cx) / 44));
    const dy = Math.max(-1, Math.min(1, (e.clientY - cy) / 44));
    knob.style.transform = `translate(${dx * 30}px, ${dy * 30}px)`;
    if (viewer) viewer.setStick(dx, -dy, true);
  });
  const end = () => { id = null; knob.style.transform = ''; if (viewer) viewer.setStick(0, 0, false); };
  s.addEventListener('pointerup', end);
  s.addEventListener('pointercancel', end);
})();

// ── settings (U3E-8.11) ──────────────────────────────────────────────────────
const SETTINGS_SPEC = [
  ['Personal', [
    ['name', 'text', 'What she calls you', ''],
  ]],
  ['Voice and listening', [
    ['micEnabled', 'bool', 'Microphone', 'Off until she can hear — capability is absent today'],
    ['vadSensitivity', 'range', 'Voice detection sensitivity', 'Runs on a ~20-30 ms frame, not the codec’s 1.37 s storage chunk'],
    ['endpointSilenceMs', 'number', 'Silence before she answers (ms)', 'Both failure directions are rude: cutting in, and sitting there'],
    ['bargeIn', 'bool', 'She stops when you start', ''],
  ]],
  ['Vision', [
    ['cameraEnabled', 'bool', 'Camera', 'Off by default. Frames become coefficients on the device before anything is sent'],
  ]],
  ['Model and serving', [
    ['endpoint', 'text', 'Server', 'Blank = same origin'],
    ['resolution', 'number', 'Preferred resolution', 'The device ladder is measured on this device, not assumed'],
  ]],
  ['Gallery', [
    ['galleryCap', 'number', 'Keep at most', 'Stated, so nothing is evicted silently'],
  ]],
];

const DOCS = [
  ['Architecture', '/docs/ARCHITECTURE.md'],
  ['Field format', '/docs/FIELD-FORMAT.md'],
  ['Measurements', '/docs/MEASUREMENTS.md'],
  ['The board', '/docs/TODO.md'],
];

// ⚠ async since `U3E-8.32`: the doc links are probed before they are offered.
// The sections still append in source order because the await is inside the
// same function — the panel does not reshuffle itself as the probe lands.
async function renderSettings() {
  const b = $('setBody');
  const st = store.get();
  b.innerHTML = '';
  for (const [group, rows] of SETTINGS_SPEC) {
    const h = document.createElement('div'); h.className = 'grp'; h.textContent = group;
    b.appendChild(h);
    for (const [key, type, label, hint] of rows) {
      const row = document.createElement('div'); row.className = 'set';
      const l = document.createElement('label');
      l.innerHTML = `${label}${hint ? `<span class="hint">${hint}</span>` : ''}`;
      row.appendChild(l);
      let input;
      if (type === 'bool') {
        input = document.createElement('input'); input.type = 'checkbox';
        input.checked = !!st.settings[key];
        input.onchange = () => store.setSetting(key, input.checked);
      } else if (type === 'range') {
        input = document.createElement('input'); input.type = 'range';
        input.min = 0; input.max = 1; input.step = 0.05; input.value = st.settings[key];
        input.oninput = () => store.setSetting(key, Number(input.value));
      } else {
        input = document.createElement('input'); input.type = type === 'number' ? 'number' : 'text';
        input.value = st.settings[key];
        input.onchange = () => store.setSetting(key, type === 'number' ? Number(input.value) : input.value);
      }
      row.appendChild(input);
      b.appendChild(row);
    }
  }

  // diagnostics — technical, therefore here and not on the orb screen
  const dh = document.createElement('div'); dh.className = 'grp'; dh.textContent = 'Diagnostics';
  b.appendChild(dh);
  const diag = document.createElement('div');
  diag.className = 'muted';
  const appearance = store.appearanceAt(null);
  const prov = appearance ? provenance(appearance) : null;
  diag.innerHTML =
    `model: <b>${modelInfo.name}</b> (${modelInfo.kind || '?'})<br>` +
    `stand-in: <b style="color:${modelInfo.standIn ? 'var(--warn)' : 'var(--ok)'}">${modelInfo.standIn}</b><br>` +
    `can: ${Object.entries(caps).filter(([, v]) => v).map(([k]) => k).join(', ') || 'nothing'}<br>` +
    `cannot: ${Object.entries(caps).filter(([, v]) => !v).map(([k]) => k).join(', ') || '—'} (absent, not failed)<br>` +
    `turns: ${st.turns.length} · gallery: ${st.gallery.length}<br>` +
    // ⛔ U3E-8.5 — the endpointing numbers actually in force, not the ones
    //   someone remembers choosing. Both failure directions are rude.
    (listener && listener.isRunning()
      ? `listening: ${JSON.stringify(listener.stats())}<br>`
      : 'listening: off<br>') +
    // ⛔ U3E-8.10 — the breakdown, with the absent stages NAMED. A total that
    //   quietly omitted STT and voice would read as nearly meeting the budget
    //   while the two stages most likely to dominate have never run.
    `latency: ${JSON.stringify(latency.report())}<br>` +
    // ⛔ U3E-9.6 — every word the CODE contributed to her appearance, visible.
    //   A project lost a day to a style word nobody had declared.
    (prov
      ? `appearance now: ${summarise(appearance) || '(none set)'}<br>` +
        `code-authored terms: ${prov.codeAuthored.map(c => `${c.text} (${c.why})`).join('; ') || 'none'}<br>` +
        (prov.unlabelled ? `<b style="color:var(--bad)">${prov.unlabelled} UNLABELLED code term(s) — that is a bug</b><br>` : '')
      : 'appearance: nothing set<br>');
  b.appendChild(diag);

  // ── U3E-8.8 camera, driven from the setting, with a live indicator ────────
  const ch = document.createElement('div'); ch.className = 'grp'; ch.textContent = 'Camera';
  b.appendChild(ch);
  const camRow = document.createElement('div'); camRow.className = 'set';
  const camBtn = document.createElement('button');
  camBtn.className = 'txt';
  camBtn.textContent = camera && camera.isRunning() ? 'Turn camera off' : 'Turn camera on';
  camBtn.onclick = async () => {
    if (camera && camera.isRunning()) {
      camera.stop(); $('camlive').hidden = true; renderSettings(); return;
    }
    camera = camera || createCamera();
    const r = await camera.start();
    if (!r.ok) { setStatus(r.reason); return; }   // refusal is an answer
    $('camlive').hidden = false;
    renderSettings();
  };
  const grabBtn = document.createElement('button');
  grabBtn.className = 'txt';
  grabBtn.textContent = 'Show her a frame';
  grabBtn.disabled = !(camera && camera.isRunning());
  grabBtn.onclick = async () => {
    $('sheetSet').hidden = true;
    await showHerCameraFrame();
  };
  camRow.append(camBtn, grabBtn);
  b.appendChild(camRow);

  /**
   * ⛔ `U3E-8.32` — THE DOC LINKS ARE PROBED, NOT ASSUMED. The shipped product
   *   carries setup and layout documentation only; no in-house documents go out.
   *
   * ⚠ These four point at in-house development documents that are stripped from
   *   the shipped product, so hard-coding them put four dead links in a
   *   stranger's settings panel — and naming an internal board in the UI of a
   *   product is its own leak.
   *
   * ⭐ Same code everywhere, no divergence between the trees: a link appears if
   *   and only if the file it points at is actually served. The heading only
   *   renders when at least one survives, so the product shows no empty section.
   */
  const present = [];
  for (const [name, href] of DOCS) {
    try {
      const r = await fetch(api(href), { method: 'HEAD' });
      if (r.ok) present.push([name, href]);
    } catch { /* not served in this build — the link simply is not offered */ }
  }
  if (present.length) {
    const lh = document.createElement('div'); lh.className = 'grp'; lh.textContent = 'Docs';
    b.appendChild(lh);
    for (const [name, href] of present) {
      const a = document.createElement('div'); a.className = 'set';
      a.innerHTML = `<label><a href="${href}" target="_blank" rel="noopener">${name}</a></label>`;
      b.appendChild(a);
    }
  }

  const rh = document.createElement('div'); rh.className = 'grp'; rh.textContent = 'Reset';
  b.appendChild(rh);
  const wipe = document.createElement('button');
  wipe.className = 'txt danger'; wipe.textContent = 'Erase everything';
  wipe.onclick = () => {
    if (confirm('Erase the whole transcript and gallery? This cannot be undone.')) {
      store.clearAll(); render();
    }
  };
  b.appendChild(wipe);
}

// ── sheets ───────────────────────────────────────────────────────────────────
function open$(id) { $(id).hidden = false; }
for (const btn of document.querySelectorAll('[data-close]')) {
  btn.onclick = () => {
    $(btn.dataset.close).hidden = true;
    if (btn.dataset.close === 'sheetView' && viewer && viewer.supported) viewer.stop();
  };
}
$('btnLog').onclick = () => { renderLog(); open$('sheetLog'); };
$('btnGal').onclick = () => { renderGallery(); open$('sheetGal'); };
$('btnSet').onclick = () => { renderSettings(); open$('sheetSet'); };
$('logUndo').onclick = () => { store.undoRewind(); renderLog(); render(); };

/**
 * ⛔⛔ THE ⌨ POPUP IS GONE AND THIS BINDING KILLED THE WHOLE APP.
 *
 * Reported from use: no orb on the screen at all. `btnType` was
 * replaced by `btnChat` in the controls bar when the chat shipped, and this line
 * still read `$('btnType').onclick` — **null** — so the module threw at load,
 * `orb.start()` never ran, and the screen was simply empty.
 *
 * ⚠ THE FAILURE HAD NO SURFACE. One uncaught error in a module takes every
 *   feature with it and reports nothing except in a console nobody has open. The
 *   app could report a missing model, a refused microphone and a dead backend —
 *   and had no way to report that IT ITSELF did not start. `#bootfail` in
 *   `index.html` now catches `error` and `unhandledrejection` and paints them on
 *   screen, plus a 4-second "boot did not complete" watchdog for the case where
 *   nothing throws but `boot()` never lands.
 *
 * ⭐ Its job is done properly by the chat composer, which is persistent rather
 *   than a `prompt()` box, which was explicitly not wanted — and
 *   which is available WHILE she works, so typing mid-answer is an amendment
 *   (`U3E-8.7`) rather than a dropped input. Removed, not re-pointed: a button
 *   that no longer exists should not keep a handler.
 */

// ── chat wiring (U3E-8.14) ───────────────────────────────────────────────────
$('btnChat').onclick = () => {
  $('sheetChat').hidden = false;
  renderChat();
  renderRecent();
  $('cText').focus();
};

/**
 * ⛔ FULLSCREEN IS A REQUEST, NOT A GUARANTEE — a browser can refuse it and iOS
 *   Safari has no element fullscreen at all. So the failure is SHOWN rather than
 *   swallowed, and the chat is already a full-inset sheet, which means refusing
 *   costs appearance and not function.
 */
$('chatFull').onclick = async () => {
  const el = $('sheetChat');
  try {
    if (document.fullscreenElement) { await document.exitFullscreen(); $('chatFull').textContent = '⛶ Fullscreen'; }
    else if (el.requestFullscreen) { await el.requestFullscreen(); $('chatFull').textContent = '⤢ Exit'; }
    else setStatus('this browser has no fullscreen API — the chat is already full-screen as a panel');
  } catch (e) {
    setStatus(`fullscreen refused: ${e.message}`);
  }
};

const cText = $('cText');
function autoGrow() { cText.style.height = 'auto'; cText.style.height = Math.min(cText.scrollHeight, window.innerHeight * 0.34) + 'px'; }
cText.addEventListener('input', autoGrow);

function sendFromComposer() {
  const t = cText.value.trim();
  // ⚠ An attachment alone is a message. Requiring text would silently discard a
  //   picture someone pasted with nothing to say about it.
  if (!t && !pendingAttachment) return;
  cText.value = '';
  autoGrow();
  if (pendingAttachment) {
    attachNext = pendingAttachment;
    pendingAttachment = null;
  }
  // ⭐ The SAME door as speech. Amendments, re-runs and appearance resolution
  //   behave identically whether the words were typed or spoken.
  submit(t);
  renderChat();
}
/**
 * ⭐ ATTACH A PICTURE FOR HER — people need a way to give her an image, which she
 *   takes in as waveform equations like everything else.
 *
 * ⛔ THE CONVERSION HAPPENS HERE, IN THE PAGE. `imageToField` runs the same
 *   CDF 9/7 the rest of the system uses, so what leaves this device is a
 *   COEFFICIENT FIELD and never your photograph. Same law as her own pictures:
 *   the wire carries equations.
 *
 * ⚠ SHE CANNOT LOOK AT IT YET AND THE UI SAYS SO. `see` is absent on the legacy
 *   harness — nothing behind the slot has vision — so the attachment is
 *   equationalized, stored and shown in the conversation, and she is told it is
 *   there in words. This was expected up front: fully implementing it waits on
 *   the trained model. The moment `see` reports true this
 *   path sends the field and needs no other change.
 */
let pendingAttachment = null;
let attachNext = null;

$('cAttach').onclick = () => $('cFile').click();

$('cFile').onchange = async (e) => {
  const f = e.target.files && e.target.files[0];
  e.target.value = '';                       // so the same file can be picked twice
  if (!f) return;
  setStatus('equationalizing…');
  try {
    const field = await imageToField(f);
    pendingAttachment = { field, name: f.name };
    setStatus(`attached ${f.name} — ${(field.equation_count || 0).toLocaleString()} coefficients`
      + (caps.see ? '' : ' · she cannot look at it yet (vision is absent), but it is in the conversation'));
    renderChat();
  } catch (err) {
    // ⛔ A picture that could not be read is said so, not silently dropped.
    setStatus(`could not read that image: ${err.message}`);
  }
};

/**
 * ⭐ PASTE A PICTURE STRAIGHT INTO THE BAR — copy an image anywhere and paste it
 *   into the chat bar. Ctrl-V of a screenshot
 *   or any copied image goes through the exact same path as the paperclip —
 *   equationalized here, never uploaded as a picture.
 *
 * ⚠ Also accepts DRAG AND DROP onto the composer, because someone who can paste
 *   an image will also try dragging one, and a drop that does nothing reads as
 *   broken rather than unimplemented.
 */
async function acceptImage(file, how) {
  if (!file) return false;
  setStatus('equationalizing…');
  try {
    const field = await imageToField(file);
    pendingAttachment = { field, name: file.name || `${how} image` };
    setStatus(`${how} — ${(field.equation_count || 0).toLocaleString()} coefficients`
      + (caps.see ? '' : ' · she cannot look at it yet (vision is absent), but it is in the conversation'));
    renderChat();
    return true;
  } catch (err) {
    setStatus(`could not read that image: ${err.message}`);
    return false;
  }
}

cText.addEventListener('paste', (e) => {
  const items = (e.clipboardData && e.clipboardData.items) || [];
  for (const it of items) {
    if (it.kind === 'file' && /^image\//.test(it.type)) {
      e.preventDefault();                    // do not also paste a filename
      acceptImage(it.getAsFile(), 'pasted');
      return;
    }
  }
  // no image in the clipboard — let the normal text paste happen untouched
});

const composerEl = $('composer');
composerEl.addEventListener('dragover', e => { e.preventDefault(); composerEl.style.borderTopColor = 'var(--accent)'; });
composerEl.addEventListener('dragleave', () => { composerEl.style.borderTopColor = ''; });
composerEl.addEventListener('drop', e => {
  e.preventDefault();
  composerEl.style.borderTopColor = '';
  const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
  if (f && /^image\//.test(f.type)) acceptImage(f, 'dropped');
  else setStatus('that is not an image — drop a picture file');
});

$('cSend').onclick = sendFromComposer;
cText.addEventListener('keydown', e => {
  // Enter sends, Shift-Enter is a newline — what every real chat does.
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendFromComposer(); }
});
$('cMic').onclick = () => {
  toggleTalk().catch(e => setStatus(e.message));
  $('cMic').classList.toggle('on', !!(listener && listener.isRunning()));
};

/**
 * ⭐ MUTE, distinct from stopping: mute yourself without stopping her generating
 *   or tearing down the listener.
 *
 * ⚠ Two different actions that were one control:
 *     `talk`     starts and ENDS the session — mic released, noise floor lost.
 *     `btnMute`  keeps the session and silences the input at the track.
 *   Muting used to require ending the session, so coming back cost a pause and
 *   a floor that had to relearn the room.
 *
 * ⛔ It does not stop HER. She keeps talking and drawing while you are muted —
 *   this is your microphone, not her mouth.
 */
$('btnMute').onclick = () => {
  if (!listener || !listener.isRunning()) {
    setStatus('not listening yet — tap talk first, then mute holds the session open');
    return;
  }
  const m = listener.setMuted(!listener.isMuted());
  syncMuteButton();
  setStatus(m ? 'muted — she cannot hear you, and the session is still open'
              : 'unmuted — listening again');
};

function syncMuteButton() {
  const m = !!(listener && listener.isMuted());
  const live = !!(listener && listener.isRunning());
  for (const id of ['btnMute', 'cMute']) {
    const el = $(id);
    if (!el) continue;
    el.classList.toggle('muted', m);
    el.textContent = m ? '🔇' : '🎙';
    el.title = m ? 'Unmute microphone' : 'Mute microphone';
    el.disabled = !live;
    el.style.opacity = live ? '' : '.4';
  }
}

/**
 * ⛔ THE ORB IS NOT A DRAW BUTTON. Tapping the circle to generate a picture is
 *   wrong — asking her for one is how it happens.
 *
 * It used to be `$('orb').onclick = () => draw()`, which force-drew from
 * whatever the person last said. ⚠ That is a WORKAROUND FOR A MISSING CONTRACT
 * wearing the costume of a feature: it existed because nothing let HER decide to
 * draw, so the person had to decide for her, and the picture was never
 * connected to anything she meant.
 *
 * ⭐ She decides now. Her reply carries `[[img: ...]]` and `splitImageLines`
 *   routes it to `drawWith()` — verified live: "draw me a black cat" comes back
 *   with the marker and draws; "what do you look like right now" comes back as
 *   words and does not. **That is the correct behaviour: drawing is something
 *   she does, not something the UI does to her.**
 *
 * ⚠ `draw()` — the person-initiated wrapper — was DELETED with this binding
 *   rather than left uncalled. A function with no caller reads as wired when it
 *   is not, which is the dormant-code failure this session has already hit four
 *   times.
 */

/**
 * `U3E-8.3` / `8.4` / `8.5` — listening.
 *
 * ⚠ The mic runs even though `hear` (STT) is absent, and that is deliberate:
 *   VAD, barge-in and endpointing are testable NOW against real speech, and
 *   they are what make the orb feel alive. What is missing is transcription, so
 *   the app says exactly that rather than pretending either way.
 */
let listener = null;

async function toggleTalk() {
  if (listener && listener.isRunning()) {
    listener.stop();
    $('talk').classList.remove('on');
    orb.setState('idle');
    orb.muteMapping();
    setStatus(idleHint());
    return;
  }

  listener = createListener({
    endpointSilenceMs: store.get().settings.endpointSilenceMs,
    sensitivity: store.get().settings.vadSensitivity,
    bargeIn: store.get().settings.bargeIn,
    onBands: b => orb.setBands(b),
    // ⭐ Your voice drives the same visualiser hers does — one renderer, one
    //   signal path, whoever is talking.
    onWave: w => orb.setWave(w),
    onSpeechStart: () => {
      orb.setState('listening');
      setStatus('listening…');
    },
    /**
     * ⛔ THIS BRANCH SETTLED AN EMPTY TURN AND SAT ON "transcribing…" FOREVER.
     *   Reported from use: pressing talk and speaking left it saying
     *   "transcribing" forever. It called `turnBuilder.settle()` expecting text that STT
     *   would have produced — and there was no STT and no producer. ⚠ The bug
     *   was invisible while `hear` was absent, because the else-branch below
     *   answered instead. **Turning a capability on is what made dead code
     *   live.**
     */
    onSpeechEnd: async ({ durationMs, speechMs, endedBy, pcm, sampleRate }) => {
      orb.setState('idle');
      if (!caps.hear) {
        setStatus(`heard ${(durationMs / 1000).toFixed(1)}s (${endedBy}) — but she cannot transcribe yet: STT is absent`);
        return;
      }
      if (!pcm || !pcm.length) {
        // ⛔ Never spin. If nothing was captured, say exactly that.
        setStatus(`heard ${(speechMs / 1000).toFixed(1)}s but captured no audio — the microphone produced no samples`);
        return;
      }
      setStatus(`transcribing ${(speechMs / 1000).toFixed(1)}s…`);
      lastEndpointMs = store.get().settings.endpointSilenceMs || 0;
      try {
        // ⭐ Her ears run on the SAME codec as her voice: the utterance becomes
        //   a 1-D CDF 9/7 field before it is sent, so STT reads exactly what
        //   the codec kept. The wire carries a field, never a WAV.
        const audioField = perceiveAudio(pcm, sampleRate);
        const r = await post('/api/hear', { audioField });
        const text = String(r.text || '').trim();
        if (!text) {
          setStatus(`heard ${(speechMs / 1000).toFixed(1)}s — nothing recognisable in it`);
          return;
        }
        // ⭐ `U3E-8.5` decided the utterance ended; `U3E-8.6` says THIS is where
        //   generation may start — never on a partial. The recognised words
        //   enter through the SAME door as typing.
        submit(text);
      } catch (e) {
        setStatus(e.absent ? e.message : `could not transcribe: ${e.message}`);
      }
    },

    /**
     * ⛔ The gate firing is REPORTED, not swallowed. It was triggering on typing
     *   and on a squeaking chair, and saying so out loud is what distinguishes
     *   "it ignored me" from "it never heard
     *   me" — two different bugs with one symptom.
     */
    onTooShort: ({ speechMs, minUtteranceMs }) => {
      orb.setState('idle');
      setStatus(`ignored ${Math.round(speechMs)}ms of noise (under the ${minUtteranceMs}ms gate)`);
    },
    onBargeIn: () => {
      // she stops. With no voice output yet this is a state change only, but
      // the path is real and the moment it can speak it will already work.
      setStatus('you started — she stopped');
      orb.setState('listening');
    },
  });

  const r = await listener.start();
  if (!r.ok) {
    setStatus(r.reason);          // refused permission is an answer, not a spinner
    listener = null;
    return;
  }
  $('talk').classList.add('on');
  orb.setState('listening');
  setStatus('listening — tap talk again to stop');
}

/**
 * `U3E-5.6` — push-to-talk, on the SAME button, without colliding with
 * toggle-listening.
 *
 * ⛔ THE COLLISION THIS RESOLVES, which is why the row sat open
 *   `talk` already meant "toggle continuous listening" (VAD, `8.3`-`8.5`).
 *   Push-to-talk is a different job — a bounded recording that becomes field A —
 *   and giving it a second button on a one-orb screen contradicts `8.1`.
 *
 * ⭐ TAP toggles listening. HOLD (>350 ms) records until release. One control,
 *   two intents, distinguished by duration — thumb-reachable on the S23 and
 *   unambiguous with a mouse.
 *
 * ⚠ The recorder and the VAD listener both want the microphone, so holding
 *   stops the listener first and restores it on release. Two `getUserMedia`
 *   streams on one device is how a phone starts refusing both.
 */
const HOLD_MS = 350;
let holdTimer = 0, holding = false, recorder = null, resumeListening = false;

$('talk').addEventListener('pointerdown', e => {
  e.preventDefault();
  try { $('talk').setPointerCapture(e.pointerId); } catch (_) {}
  holdTimer = setTimeout(() => { holding = true; startPushToTalk(); }, HOLD_MS);
});

$('talk').addEventListener('pointerup', () => {
  if (holdTimer) { clearTimeout(holdTimer); holdTimer = 0; }
  if (holding) { holding = false; stopPushToTalk().catch(e => setStatus(e.message)); }
  else toggleTalk().catch(e => setStatus(e.message));      // it was a tap
});

// ⛔ A cancelled pointer must NOT fall through to the tap branch — dragging off
//   the button would silently toggle listening.
$('talk').addEventListener('pointercancel', () => {
  if (holdTimer) { clearTimeout(holdTimer); holdTimer = 0; }
  if (holding) { holding = false; stopPushToTalk().catch(() => {}); }
});

async function startPushToTalk() {
  resumeListening = !!(listener && listener.isRunning());
  if (resumeListening) { listener.stop(); $('talk').classList.remove('on'); }
  recorder = createRecorder();
  const r = await recorder.start();
  if (!r.ok) {                       // a refusal is an answer, not a spinner
    setStatus(r.reason); recorder = null; holding = false; return;
  }
  $('talk').classList.add('on');
  orb.setState('listening');
  setStatus('recording — release to send');
}

async function stopPushToTalk() {
  if (!recorder) return;
  const captured = recorder.stop();
  recorder = null;
  $('talk').classList.remove('on');
  orb.setState('idle');
  if (!captured) { setStatus('nothing recorded — held too briefly'); return; }
  await offerAudioToHer(captured);
  if (resumeListening) { resumeListening = false; toggleTalk().catch(() => {}); }
}

/**
 * ⭐ The audio twin of `offerToHer`. The microphone's output leaves as field A,
 * never as audio — true today whether or not anything can read it.
 * ⛔ And it ends in an honest 501, naming the row, rather than dropping the
 * field to make the UI look successful.
 */
async function offerAudioToHer(captured) {
  const ratio = (captured.rawBytes / captured.wireBytes).toFixed(1);
  setStatus(
    `heard ${captured.seconds.toFixed(1)}s → field A in ${captured.encodeMs.toFixed(0)} ms · ` +
    `wire ${(captured.wireBytes / 1024).toFixed(0)} KB vs ${(captured.rawBytes / 1024).toFixed(0)} KB raw (${ratio}×)`);
  try {
    const r = await post('/api/hear', { audioField: captured.field });
    if (r.text) submit(r.text);        // ⭐ straight into U3E-8.6's path
  } catch (e) {
    if (!e.absent) throw e;
    // ⚠ `U3E-8.32`: says the same true thing without naming an internal row —
    //   the honesty is "absent, not failed", not the task number behind it.
    setStatus(`encoded fine — but she cannot transcribe yet: STT is absent, not failed. ` +
      `${captured.seconds.toFixed(1)}s of field A ready for the moment it is trained.`);
  }
}

/**
 * `U3E-5.5` / `8.8` — show her something. Drop or paste an image anywhere.
 *
 * ⭐ It becomes coefficients HERE, on the device. The wire carries a field,
 * never a photograph — true today whether or not anything can yet read it.
 *
 * ⛔ And `see` is an ABSENT capability, so this ends in an honest 501. The field
 * is still produced, still measured, and still reported — nothing is dropped to
 * make the UI look successful.
 */
let camera = null;

/** One reporter for every sensory path, so they cannot drift apart. */
async function offerToHer(sensed, label) {
  const ratio = (sensed.rawBytes / sensed.wireBytes).toFixed(1);
  setStatus(
    `${label}: ${sensed.field.width}×${sensed.field.height} → ${sensed.field.equation_count.toLocaleString()} coefficients ` +
    `in ${sensed.encodeMs.toFixed(0)} ms · wire ${(sensed.wireBytes / 1024).toFixed(0)} KB vs ` +
    `${(sensed.rawBytes / 1024).toFixed(0)} KB raw (${ratio}×)`);

  try {
    const r = await post('/api/see', { field: sensed.field });
    store.addTurn('unity', r.text || '');
    setLast(r.text || '');
  } catch (e) {
    if (!e.absent) throw e;
    // ⛔ Absent, not broken, and it names the row.
    setStatus(`encoded fine — but she cannot see yet: vision is absent, not failed. ` +
      `${sensed.field.equation_count.toLocaleString()} coefficients ready for the moment it is trained.`);
  }
}

async function showHer(src, label) {
  if (busy) return;
  busy = true;
  orb.setState('thinking');
  setStatus('encoding on this device…');
  try {
    await offerToHer(await imageToField(src), label);
  } catch (e) {
    setStatus(`could not encode: ${e.message}`);
  } finally {
    orb.setState('idle'); busy = false; render();
  }
}

/** The camera already returns an encoded field — do NOT re-encode it. */
async function showHerCameraFrame() {
  if (busy || !camera || !camera.isRunning()) return;
  busy = true;
  orb.setState('thinking');
  try {
    await offerToHer(await camera.grab(), 'camera frame');
  } catch (e) {
    setStatus(`camera frame failed: ${e.message}`);
  } finally {
    orb.setState('idle'); busy = false; render();
  }
}

addEventListener('paste', e => {
  const item = [...(e.clipboardData?.items || [])].find(i => i.type.startsWith('image/'));
  if (item) { e.preventDefault(); showHer(item.getAsFile(), 'pasted'); }
});
addEventListener('dragover', e => e.preventDefault());
addEventListener('drop', e => {
  const f = [...(e.dataTransfer?.files || [])].find(x => x.type.startsWith('image/'));
  if (f) { e.preventDefault(); showHer(f, 'dropped'); }
});

function render() {
  if (!$('sheetLog').hidden) renderLog();
  if (!$('sheetGal').hidden) renderGallery();
  if (!$('sheetSet').hidden) renderSettings();
  if (!$('sheetChat').hidden) renderChat();
  renderRecent();
  // The mic pip on the composer must track the listener, not the last click —
  // push-to-talk and the orb screen can both change it underneath us.
  syncMuteButton();
  const mic = $('cMic');
  if (mic) mic.classList.toggle('on', !!(listener && listener.isRunning()));
}

store.subscribe(() => {});
// ⭐ Proof of life for the boot-failure catcher in index.html. If this flag is
//   never set, the page says so instead of showing an empty screen.
boot().then(() => { window.__u3eBooted = true; })
  .catch(e => {
    window.__u3eBooted = true;   // it ran; it failed. Different facts.
    setStatus('boot failed: ' + e.message);
    throw e;
  });
