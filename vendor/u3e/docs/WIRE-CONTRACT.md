---
sources:
  - serve/server.mjs
  - serve/slot.js
  - serve/progressive.js
  - serve/stand-in.js
  - serve/trained.js
  - train/infer.py
  # ⭐ §3.7 specifies `turn`, and the shapes it names come from
  #   these two: the builder that emits them and the falsifier that counts them.
  - train/vocab.py
  - train/probe-prompt-shapes.py
  - app/sw.js
last-verified: "65c9e207 2026-09-07"
---

# WIRE CONTRACT — the HTTP shape, specified

> **The README states the case for this file exactly:** the only thing carried
> over from the parent project is the HTTP shape (`/api/chat`, `/api/image`) —
> *"a wire contract so the existing chat page and the Android app keep working,
> not a dependency."*
>
> ⛔ **A contract with two external consumers and no specification is a contract
> nobody can check.** This file is the specification. `serve/server.mjs` is the
> implementation and `serve/slot.js` is the interface behind it; where they
> disagree with this page, **the code wins and this page is the bug.**
>
> ⚠ **Frozen vs ours to change is marked on every route.** Guessing wrong in
> either direction is expensive: changing a frozen field breaks the APK silently,
> and freezing a field that was never frozen means carrying a mistake forever.

---

## CONTENTS

```
 1  WHO CONSUMES THIS ........... three clients, two of them outside this repo
 2  THE SHAPE OF EVERY RESPONSE . the envelope, and why `standIn` rides on it
 3  ROUTES ...................... state · chat · image · speak · see · hear
    3.7 `turn` .................. ⭐ the same four routes, as a conversation
 4  THE FIELD ON THE WIRE ....... ⭐ coefficients, never a picture
 5  ERRORS ...................... ⛔ 501 ABSENT is not 500 FAILED
 6  STATIC ROUTES ............... the app, the codec sources, the docs
 7  WHAT IS FROZEN .............. and what is ours
 8  HOW TO CHECK IT
```

---

## 1. WHO CONSUMES THIS

| Consumer | Where | Can we change the contract under it? |
|---|---|---|
| **The U3E app** (`app/`) | in this repo, served by this server | ✅ yes — same commit |
| **The legacy chat page** | ⛔ **the parent project** | ❌ no. This is why the shape was kept at all |
| **The Android APK** (`android/`) | in this repo, but **ships independently** | ⚠ only with a release. Assume an old build is in the field |

⭐ **The reason the shape was kept is worth restating**, because it is the only
thing this project inherited: her `[[img: …]]` convention stops being a *parsed
instruction* and becomes a *native emission*, and the existing surfaces keep
working while that changes underneath them.

⛔ **It is a contract, not a dependency.** No Ollama, no external runtime, no
third-party weights at inference. Nothing on this page implies otherwise.

---

## 2. THE SHAPE OF EVERY RESPONSE

Every model call returns through one envelope (`serve/slot.js:93-99`):

```jsonc
{
  // ── the route's own payload, spread in at the top level ──
  "text": "...",                    // or "field", "audioField", …

  // ── and ALWAYS this ──
  "model": {
    "name":   "U3E stand-in",
    "kind":   "stand-in",           // "stand-in" | "trained"
    "standIn": true,                // ⛔ boolean, never absent, never defaulted
    "slot":    1                    // SLOT_VERSION
  }
}
```

### ⛔ `standIn` rides on EVERY response, not just on `/api/state`

This is the single most load-bearing field on the wire, and it is duplicated
deliberately. **A client that only checked state at boot would happily render
stand-in output as hers for the rest of the session.**

⛔ **CORRECTED 2026-08-31 — do not repeat the claim this file first carried.**
The U3E app **no longer renders an on-screen banner**: it was removed 2026-08-29
on the operator's call (*"get rid of that i dont need that on the screen forever"*) and
`showStandIn()` hides the element unconditionally. ⚠ Four other documents and
source comments still asserted the banner two days later, which is why it is
called out here rather than quietly corrected.

⭐ **What the flag is still for, and where it must be honoured:** the server
prints `⛔ STAND-IN. This is NOT Unity.` at boot, and the app's **diagnostics
panel renders it in red**. ⛔ **A client that ignores `standIn` entirely is not
conforming** — it must surface it *somewhere* a user or an auditor can reach,
even if not as a permanent strip of screen.

`describe().standIn` is also validated at boot: the slot validator rejects a
model that does not declare, explicitly, whether it is real
(`slot.js:63-68`) — *"a model that does not declare whether it is real is exactly
the thing that lets a stand-in be mistaken for the model."*

---

## 3. ROUTES

### 3.1 `GET /api/state`

Boot probe. No body.

```jsonc
{
  "ok": true,
  "slot": 1,
  "model": {                          // whatever describe() returns
    "name": "U3E stand-in",
    "kind": "stand-in",
    "standIn": true,
    "fields": 64,
    "note": "Replays banked corpus fields. Exercises every surface; decides nothing."
  },
  "capabilities": { "chat": true, "image": true,      // ⚠ THE STAND-IN's answer
                    "speak": false, "see": false, "hear": false },
  "standIn": true,                    // ⛔ hoisted deliberately — see §2
  "corpus": { "banked": true }
}
```

⭐ **`capabilities` is the routing table, and it is checked before every call.**
A client should grey out what is `false` rather than discovering it as an error —
but §5 means discovering it as an error is also safe and informative.

⛔⛔ **THE VALUES ABOVE ARE THE STAND-IN'S, AND THE TRAINED SLOT ANSWERS
DIFFERENTLY — A CLIENT MUST NOT HARDCODE EITHER SET.**

| Slot | `chat` | `image` | `see` | `speak` | `hear` |
|---|---|---|---|---|---|
| `standin` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `trained`, as of 2026-09-07 | ✅ | ✅ | ✅ | ✅ | ✅ |

⚠ **`speak` and `hear` flipped on 2026-09-06 with no code change**, because
`AUDIO_TRAINED` is derived from what the shards contained
(`train/train.py:701`). ⛔ **Which is precisely why this is a routing table read
at runtime and not a constant** — a client that cached the first set would refuse
two capabilities the model has.

⚠ `capabilities()` and the methods that exist must agree. The validator flags
**both** directions at boot, including a method that exists while capabilities
denies it: *"a caller trusting the map will never route to a method that works"*
(`slot.js:70-79`).

---

### 3.2 `POST /api/chat` — ⛔ FROZEN SHAPE

**Request:**

```jsonc
{
  "messages": [                       // ⛔ frozen — the legacy page sends this
    { "role": "user",  "content": "…" },
    { "role": "unity", "content": "…" }
  ],
  "appearance": {                     // ⚠ ours. Optional, may be null
    "slots":         { "…": { "text": "…", "origin": "said" } },
    "manifestation": "base",          // base | girlfriend | housewife | kittycat
    "intensity":     "default"
  }
}
```

**Response:**

```jsonc
{ "text": "…", "model": { … } }       // envelope per §2
```

⛔ **`appearance` is a documented parameter that once had no producer**, so
manifestation steered every picture and never a sentence — she would look like a
catgirl and talk like base Unity. ⭐ The stand-in **echoes the register it
received** on every reply precisely so the fix stays verifiable *without a
trained model*: if the conditioning stops arriving, that line goes quiet
(`stand-in.js:78-87`).

⚠ **The client sends a TRIMMED transcript**, not the whole history, and it says
so on screen when it drops turns. Silently shortening someone's conversation is
how *"she forgot what I told her"* becomes unexplainable. A re-run from an edited
turn sends `appearanceAt(turnId)` — the register **in force at that point in the
branch**, not the current one.

⚠ `onToken` appears in the slot signature (`slot.js:29`) as a **streaming
callback inside the process**. It is not a wire feature; `/api/chat` returns one
JSON object. Streaming on the wire exists only for `/api/image` (§3.3).

---

### 3.3 `POST /api/image` — ⛔ FROZEN ROUTE, two response modes

**Request:**

```jsonc
{
  "prompt": "…",                      // ⛔ frozen
  "appearance": { … },                // ⚠ ours, optional
  "progressive": true,                // ⭐ ours — changes the response format
  "turn": false                       // ⭐ ours — see §3.7
}
```

#### Mode A — one JSON object (`progressive` absent or false)

```jsonc
{
  "field":  { … },                    // a field record, docs/FIELD-FORMAT.md §1
  "source": "<banked name>",          // ⚠ stand-in only
  "note":   "…",                      // ⚠ optional, human-readable
  "model":  { … }
}
```

#### Mode B — NDJSON stream (`progressive: true`)

`content-type: application/x-ndjson`, plus `x-accel-buffering: no` because some
proxies would otherwise buffer the entire point away.

```jsonc
// line 1 — exactly one
{ "type": "head",
  "meta":   { "width": 1024, "height": 768, "pad_w": 1024, "pad_h": 768 },
  "slices": 8,
  "total":  61234,                    // equation_count of the whole field
  "model":  { … } }

// lines 2..n — one per scale, COARSE FIRST
{ "type": "slice", "scale": 0, "coefficients": 18,
  "channels": { "Y": {…}, "Cb": {…}, "Cr": {…} } }   // channel shape per §4

// last line — exactly one
{ "type": "done", "note": "…" }       // note may be null
```

⭐ **Each slice carries ONLY the coefficients introduced at that scale.** The
client accumulates (`mergeSlice`, `serve/progressive.js:106-145`). Re-sending
everything each time would make the stream quadratic **and would hide a bug where
later slices add nothing.**

⛔ **This is not a loading animation.** The honest test is written into the
source: mute the later slices and the image must stay coarse forever. If it
sharpens anyway, something is sending the whole field and fading it in.

⛔ **Wait for all three channels before the first render** (`renderable`,
`progressive.js:152-154`). Painting on Y alone shows a grey picture that then
colours, which reads as a bug even though it is not.

⚠ **Each slice is re-quantised against its own scale.** A slice of tiny
fine-scale coefficients would otherwise be crushed by the coarse scale's
`qscale`. So `qscale` differs per slice per channel — a client must use the one
on the slice it is reading, never a remembered one.

---

### 3.4 `POST /api/speak` — ⚠ ours

```jsonc
// request
{ "text": "…", "turn": false }            // ⭐ turn — see §3.7
// response
{ "audioField": { … }, "turn": false, "model": { … } }   // field A, docs/FIELD-FORMAT.md §6
```

⛔ **Today: `501 absent`.** The voice codec and tokenizer exist. There is no
voice.

---

### 3.5 `POST /api/see` — ⚠ ours

```jsonc
// request
{ "field": { … }, "turn": false }     // field C — the CLIENT encodes it · ⭐ turn, §3.7
// response
{ "text": "…", "turn": false, "model": { … } }
```

⭐ **The client encodes.** A dropped or pasted image becomes coefficients **on the
device** and the picture never crosses the wire. That path is built and real.

⛔ **Today: `501 absent`.** Nothing understands the coefficients yet — which is a
*training* gap, not a representation gap (`docs/EQUATIONS.md §5`).

---

### 3.6 `POST /api/hear` — ⚠ ours

```jsonc
// request
{ "audioField": { … }, "turn": false } // field A — the CLIENT encodes it · ⭐ turn, §3.7
// response
{ "text": "…", "turn": false, "model": { … } }
```

⛔ **Today: `501 absent`.** Voice activity detection, barge-in and endpointing all
work. Transcription does not exist.

---

### 3.7 ⭐⭐ `turn` — THE SAME FOUR ROUTES, PROMPTED AS A CONVERSATION

⛔ **IT IS ONE OPTIONAL FIELD ON FOUR EXISTING ROUTES, NOT FOUR NEW ROUTES, AND
NOT A `want` PARAMETER ON `/api/chat`.** Two entry points to one generation path
is a defect this project has already paid for once. ⚠ `turn` DEFAULTS FALSE, so
every existing caller is byte-for-byte unaffected.

The flag changes the prompt the model is asked to continue, and nothing else:

```
  route          turn: false (default)                turn: true
  /api/image     [text] prompt [/text] [image]        [text][you] prompt [/text] [image][me]
  /api/speak     [text] said   [/text] [audio]        [text][you] said   [/text] [audio][me]
  /api/see       [image] toks [/image] [text]         [image][you] toks [/image] [text][me]
  /api/hear      [audio] toks [/audio] [text]         [audio][you] toks [/audio] [text][me]
```

⭐ **`turn: true` on `/api/image` IS "chat answers with a picture."** The speaker
marker sits immediately inside whichever content marker opens the turn, exactly
where `train/vocab.py::build_dialogue` puts it — *"the training order must match
the serving order"*.

⛔ **AND IT DEPENDS ON A CORPUS, WHICH IS WHY THE RESPONSE ECHOES `turn`.** The
conversational shapes exist only in a shard set built from a dialogue manifest
carrying `draw`/`see`/`speak`/`hear` exchanges. **A `turn: true` request against
a set without them is a prompt the model has never seen** — precisely the state
`/api/chat` was in for two whole training runs, when `[/text][text]` occurred
**zero** times across all 598 shards. ⚠ The falsifier is
`node train/probe-prompt-shapes.py --shards <set>`, which reports all nine shapes
PRESENT or ABSENT off the real rows. `turn` is echoed on failure responses too,
because *"the plain shape failed"* and *"the conversational shape failed"* are
different facts.

---

## 4. ⭐ THE FIELD ON THE WIRE — coefficients, never a picture

**This is the design decision that shapes the whole contract.**

```
   ┌────────────────────┐                     ┌────────────────────┐
   │      SERVER        │                     │      CLIENT        │
   │                    │  ── coefficients ─► │                    │
   │  emits a FIELD     │     (kilobytes)     │  runs idwt2 ITSELF │
   │  never a PNG       │                     │  → the picture     │
   └────────────────────┘                     └────────────────────┘
        ⭐ her image is an equation right up to the screen
        ⭐ and on a phone that is far less over the wire
```

A channel object on the wire (`docs/FIELD-FORMAT.md §1` is normative):

```jsonc
{ "keep": 37629, "qscale": 3.05e-5, "pos_enc": "dv1",
  "pos_b64": "…", "val_b64": "…" }
```

⚠ **A server-side store may carry `pos_bin` / `val_bin` (raw bytes) instead.**
**Readers must accept either** — `codec/js/bytes.js :: chanVal` and
`decodePositions` are the single choke point where that is decided. The lesson
behind that choke point is recorded: in the sibling project a consumer read only
`val_b64`, so every record restored from the binary store **silently scored zero**
and recall quietly refused to fire. Nothing failed. Nothing logged.

⛔ **The client needs the codec, and gets the identical source** — `/codec/*`,
`/tokenizer/*` and `/serve/progressive.js` are served from disk unmodified
(`server.mjs:186-188`). **No build step, no copy to drift.**

---

## 5. ERRORS — ⛔ 501 ABSENT is not 500 FAILED

| Status | Body | Means |
|---|---|---|
| **200** | the envelope | fine |
| **501** | `{ "error": "…", "absent": true, "method": "see" }` | ⛔ **the capability does not exist.** Not a failure — a gap |
| **500** | `{ "error": "…" }` | something actually went wrong |
| **404** | `not found` (text) | unknown route or missing static file |

⭐ **The distinction is the contract's most important honesty property.** The
message reads *"<model> cannot see() — capability absent, not failed"*
(`slot.js:106-113`), and the client shows **"she cannot do this yet"**, never a
spinner that never resolves.

⛔ **`NO FALLBACK THAT HIDES A FAILURE`** is a LAW here. The server will not substitute a different modality,
will not return empty text, and will not quietly serve the stand-in when a
different model was requested. **It refuses at boot instead**, which is why §3's
capability map can be trusted.

⚠ **Request bodies are capped at 32 MB** (`server.mjs:164`) — enough for a large
field, and a bound rather than an invitation.

---

## 6. STATIC ROUTES

| Path | Serves | Note |
|---|---|---|
| `/` · `/index.html` | `app/index.html` | |
| `/app/*` | the app sources | |
| `/codec/*` · `/tokenizer/*` | ⭐ **the same sources Node runs** | no build step, no drift |
| `/serve/progressive.js` | shared: server slices, client merges | |
| `/docs/*.md` | read-only, `text/plain` | what Settings links to |
| anything else | `404` | |

⚠ **`/api/*` and `/docs/*` are never cached by the service worker**
(`app/sw.js:59`) — a cached chat reply or a cached field would be a lie about the
present state.

---

## 7. WHAT IS FROZEN, AND WHAT IS OURS

```
 ⛔ FROZEN — an external consumer depends on it
 ────────────────────────────────────────────────────────────────
   the ROUTE NAMES          /api/chat  /api/image  /api/state
   chat  request            { messages: [ { role, content } ] }
   chat  response           { text }
   image request            { prompt }
   HTTP status semantics    200 ok · 501 absent · 500 failed

 ⚠ OURS TO CHANGE — but change them in the same commit as their consumer
 ────────────────────────────────────────────────────────────────
   appearance               shape, slots, manifestation, intensity
   progressive              the flag and the entire NDJSON format
   /api/speak /see /hear    ⛔ absent today; the shape is not yet load-bearing
   the model envelope       EXCEPT `standIn`, which is frozen by honesty
   /api/state extras        corpus{}, model.note, model.fields
   the static route list
```

⛔ **`standIn` is frozen for a different reason than the others.** Nothing
external depends on it — the project's honesty claim does. Removing it, defaulting
it, or making it optional would be the change that lets a stand-in pass for her.

⭐ **When the trained model arrives, NOTHING on this page changes.** That is the
model-slot law (`serve/slot.js:4-16`): every surface talks to that one interface,
so the swap happens at `serve/server.mjs :: loadModel` and nowhere else. **If a
real swap needs edits anywhere else, the slot was wrong** — and we would find that
out at the most expensive possible moment, holding a trained model and a pod bill.

### ⭐⭐ IT ARRIVED 2026-09-04, AND THE CLAIM ABOVE WAS TESTED RATHER THAN TRUSTED

**The swap cost exactly two things: `serve/trained.js`, and one
branch in `serve/server.mjs :: loadModel`.** Nothing else in the project moved —
not the orb, not the gallery, not the viewer, not the progressive NDJSON, not the
APK. **Verified end to end on `step-600.pt`:**

```
  /api/state    ok true · slot 1 · standIn FALSE · kind "trained"
  /api/chat     text through · model envelope unchanged
  /api/image    progressive NDJSON: head + 4 slices + done, same shape
  /api/speak    HTTP 501 · {absent:true, method:"speak"}   ⭐ not 500
```

⛔ **ONE FIELD WAS ADDED, AND THE SENTENCE ABOVE IS NOW *ALMOST* TRUE RATHER
THAN TRUE. Saying so is the point of this page.** `standIn: false` is correct for
a real checkpoint — and it is **not sufficient**, because a 600-step model on a
partial corpus is real weights that do not work. So the envelope gained a
sibling:

```json
  "provisional": true,
  "provisionalWhy": [
    "trained on a PARTIAL corpus in bank order",
    "step 1,000 of 209,551 — run unfinished"
  ]
```

⚠ **THE EXAMPLE ABOVE IS AN EXAMPLE, AND IT WENT STALE BY 51×.**

| | |
|---|---|
| Read until 2026-09-07 | `step 600 of 4,096` |
| The run's own `totalSteps` | **209,551** |
| So 600 looked like | **14.6%** of a run, against the **0.29%** it was |

⭐ **The CODE is right and always was** — `train/infer.py:497` formats it from
`total_steps`. ⛔ **This page is a CONTRACT, so a reader may reasonably copy a
shape out of it, which is exactly why a plausible wrong number inside one is
worth correcting.**

⭐ **It is FROZEN for the same reason `standIn` is** — nothing external depends
on it, the project's honesty claim does. ⚠ And it rides on **every** response for
the same reason `standIn` does: *a client that only checks state at boot would
happily render provisional output as hers for the rest of the session.*

⚠ **`U3E_MODEL` gained a third value:** `trained` (explicit) · `standin` ·
`legacy`. ⛔ **With a checkpoint on disk and no `U3E_MODEL` set, `trained` wins
automatically and the server REFUSES TO BOOT if the sidecar is unreachable** —
it will not quietly serve the stand-in in its place, because that *"would look
like success"*. `U3E_MODEL=standin` still overrides, which is how a surface gets
exercised during a four-day run without competing for the card.

---

## 8. HOW TO CHECK IT

```bash
node serve/server.mjs                                   # → :8790

curl -s localhost:8790/api/state | head -c 400

curl -s localhost:8790/api/chat -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"hello"}]}'

curl -s localhost:8790/api/image -H 'content-type: application/json' \
  -d '{"prompt":"a test","progressive":true}' | head -3

curl -s -o /dev/null -w '%{http_code}\n' localhost:8790/api/see \
  -H 'content-type: application/json' -d '{"field":{}}'      # expect 501
```

⭐ **The last one is the check that matters most**, because a `501` with
`absent: true` is the difference between an honest gap and a silent one — and
this project has a LAW about which of those is acceptable.

⚠ **`node app/turn-selftest.mjs`** exercises the turn lifecycle around
`/api/chat` (revision, amendment, abort-and-re-run) without a network.
