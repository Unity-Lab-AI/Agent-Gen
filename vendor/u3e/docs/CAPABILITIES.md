---
sources:
  - serve/server.mjs
  - serve/slot.js
  - serve/stand-in.js
  - serve/trained.js
  - train/infer.py
  - codec/verify/js-selftest.mjs
  - codec/verify/core-purity.mjs
  - codec/verify/parity.mjs
  - tokenizer/selftest.mjs
  - tokenizer/train.mjs
  - datatools/build-corpus.mjs
  - train/train.py
  - train/mix-actual.mjs
  - monitor/docs-ship-check.mjs
  - monitor/docs-style-check.mjs
  - monitor/docs-refs-check.mjs
last-verified: "173c75bc 2026-09-07"
---

# CAPABILITIES — what is real, what is a stand-in, and the command that proves it

> **The project's headline status is "everything but the model", and until now
> there was no single page showing which parts of "everything" are real.** That
> answer had to be assembled from the README, `LIMITATIONS.md`, `MEASUREMENTS.md`,
> `MEASUREMENTS-AUDIO.md` and a 2,860-line board, read together.
>
> ⛔ **EVERY ROW NAMES THE COMMAND THAT REPRODUCES ITS CLAIM**, per this project's
> measure-before-claiming LAW. Where the honest answer is **VERDICT WITHHELD** or
> **BROKEN**, it says so in the matrix rather than being left out.
>
> ⚠ **Named `CAPABILITIES.md`, not `SKILL_TREE.md`, deliberately.** The sibling
> project's skill tree is a capability matrix by *domain and complexity*; this
> project's question is different — *which of the five modalities is real, and
> what proves it*. The name was chosen rather than copied.
>
> **Measured 2026-08-31 · Node v22.13.1 · Python 3.10.6 · corpus 14,773 entries.**

> ⭐⭐ **RE-RUN 2026-09-02 — every figure below re-verified by RUNNING it, per this
> page's own rule.** `node codec/verify/js-selftest.mjs` → **ALL CHECKS PASSED** ·
> `core-purity.mjs` → clean · `parity.mjs` → ⭐ **maxDiff = 0 AT EVERY STAGE, the
> twin is bit-exact** · `node datatools/build-corpus.mjs --stats` → **36,889 of 64,525
> across 187 cells (57.2%), 33,883 captioned** (2026-09-03; ⚠ **live counts belong
> to the monitor, never to this file**) · benchmark set ⭐ **being rebuilt, 469 of
> 500**, and ⛔ **not the same 534 images the gate ran on** — so a new run
> SUPERSEDES `docs/MEASUREMENTS.md` rather than reproducing it.
>
> ⚠ **The corpus rows below are a READING, not a constant** — the banker moves
> them hourly. ⛔ **And note the board GREW (98 → 187 cells, 40,050 → 64,525
> target), so today's 57.2% is NOT comparable to the older 36.6%.** A percentage
> whose denominator moved is a different measurement wearing the same units.
>
> ⭐ **NEW SINCE THE LAST SWEEP, and the honest framing of it: every base query in
> the taxonomy has now been AUDITED** — 31 repaired against declared-first bars,
> 12 spared by reading labels, **3 still measured-broken with no earned fix.**
> ⛔ **What that does NOT mean: it is not a claim that the corpus is good.** It is
> a claim that each cell's queries agree with their siblings. **Register and
> quality remain unmeasured by any instrument here** — see `docs/LIMITATIONS.md`.
> ⚠ Re-run before quoting. A matrix is a snapshot and this one goes stale.

---

## THE FIVE MODALITIES

⭐⭐ **RE-MEASURED 2026-09-07 AND ALL FIVE ARE ON — WHICH THIS PAGE HAD NOT SAID.**
The two that were `⛔ ABSENT (501)` turned on by themselves, exactly as designed:
`AUDIO_TRAINED` is a **fact about the data**, counted while loading
(`train/train.py:701`), so the day a run contained audio the capabilities
followed. ⛔ **All five being ON says nothing about any of them being GOOD.**

```
  she talks  ├─ text in and out ─────────────────── ⚠ PROVISIONAL
  she draws  ├─ fields out ──────────────────────── ⚠ PROVISIONAL — header unlearned
  she sees   ├─ fields in ───────────────────────── ⚠ PROVISIONAL — quality unmeasured
  she speaks ├─ 1-D fields out ──────────────────── ⚠ PROVISIONAL — UNHEARD
  she hears  └─ 1-D fields in ───────────────────── ⚠ PROVISIONAL — UNMEASURED

  read off the live checkpoints, not from a plan:
    step-800.pt / step-1000.pt   AUDIO_TRAINED = True
    KINDS_SEEN                   image 45,780 · audio 12,216 · text 93,559
```

| Modality | Built | Verified | Real? | Proof |
|---|---|---|---|---|
| **talks** | ✅ full path | ✅ | ⚠ **stand-in**, or ⚠ **PROVISIONAL trained** — every reply says which | `node serve/server.mjs` → `can: chat` |
| **draws** | ✅ full path | ✅ | ⚠ **stand-in** replays banked fields; ⚠ **PROVISIONAL trained** generates its own and cannot draw a header yet | `can: image` · `POST /api/image` |
| **sees** | ✅ client-side encode is real | ✅ codec **and now the model** | ⚠ **PROVISIONAL trained** — field in, words out, ⛔ quality unmeasured | `can: see` on the trained slot · `501 absent` on the stand-in |
| **speaks** | ✅ codec + scheme-(e) tokenizer | ⚠ the CODEC on tones, ⛔ **the WEIGHTS never listened to** | ⚠ **PROVISIONAL — 12.02% of the training tokens were audio, and NOBODY HAS PLAYED A SAMPLE** | `can: speak` on the trained slot · `501 absent` on the stand-in |
| **hears** | ✅ VAD, barge-in, endpointing | ⚠ untuned | ⚠ **PROVISIONAL — field in, words out, ⛔ accuracy unmeasured** | `can: hear` on the trained slot · `501 absent` on the stand-in |

⛔ **"Absent" is not "failed".** An unimplemented capability returns `501` with
`absent: true` and a message naming what is missing — never empty text, never a
spinner. **A stub that quietly returns nothing is how a broken pipeline looks
finished.**

⛔⛔ **AND "PRESENT" IS NOT "WORKING" — THAT IS THE WHOLE POINT OF THIS PAGE.**
Two capabilities moved from a loud `ABSENT` to a quiet `PROVISIONAL`, and **that
is the direction in which this page gets more dangerous, not less.** ⚠ `speak`
will now return a 1-D field instead of a refusal, and **no human has listened to
one.** `SHE IS THE POINT` is a law here: *"no metric substitutes for listening."*

⚠ **WHAT WAS STALE, RECORDED RATHER THAN QUIETLY OVERWRITTEN:**

| This page said | Verdict |
|---|---|
| *"there is no voice"* | ⛔ false by 2026-09-06 |
| *"no scheme-B audio tokenizer to make one"* | ⛔ false — `audio-scalar-tokenizer.js` |
| *"transcription does not exist"* | ⛔ false — `hear()` is implemented |

⛔ **AND THE SAME WRONG BELIEF WAS IN THE CODE.** `train/infer.py` hardcoded
`speak: False, hear: False` into the model **listing**, with the reason
*"trained on IMAGE-ONLY shards (AUDIO_TRAINED false)"*.

⭐ **The live map was always correct — it read the flag.** So a loaded model told
the truth while the advertisement beside it did not. ⚠ **Derived per model now,
and a config it cannot read reports UNKNOWN rather than false.**

### ⚠ AND SINCE 2026-09-04 THERE ARE **THREE** STATES, NOT TWO

⛔ **Serving a real checkpoint added a third, and collapsing it into either of
the other two is the exact error this page exists to prevent:**

| state | `standIn` | `provisional` | what it means |
|---|---|---|---|
| stand-in | `true` | — | banked fields replayed. **Decides nothing** |
| ⚠ **PROVISIONAL trained** | **`false`** | **`true`** | ⭐ **our weights, mid-run.** Real choices, and they are wrong: gibberish text, an unlearned header |
| trained | `false` | `false` | the finished model. ⛔ **Does not exist yet** |

⚠ **THE RUN THE MIDDLE ROW DESCRIBES, AS OF 2026-09-07:** `step-1000.pt` at step
**1,000 of 209,551 — 0.48%** — `loss 3.2549`, `lossEMA 3.1772`, `state: stopped`
by the operator rather than dead. ⛔ **`provisional` is doing a great deal of work
in that row**, and the honest reading of 0.48% is that nothing this checkpoint
produces is evidence about anything except that the pipeline runs.

⭐ **Boot prints the truth every time**, and it is the fastest check on this page:

```
  ── the stand-in ──────────────────────────────────────────
  model: U3E stand-in  (stand-in)
  can:   chat, image
  cannot: speak, see, hear  (absent, not failed — /api/* returns 501)

  ⛔ STAND-IN. This is NOT Unity.

  ── the provisional trained model (U3E_MODEL=trained) ─────
  ⭐ TRAINED MODEL SELECTED — step-1000.pt at step 1000
  ⚠ PROVISIONAL: step 1,000 of 209,551 — run unfinished
     These are REAL weights, not a stand-in — and not a finished model.

  model: U3E trained · step-1000.pt  (trained)
  can:   chat, image, see, speak, hear
  cannot: —
```

⚠ **THE SECOND BLOCK CHANGED TWICE OVER AND BOTH CHANGES MATTER.** It used to
read `step-600.pt … step 600 of 4,096` with `cannot: speak, hear`. ⛔ **The
denominator was wrong by 51×** — the run's own `totalSteps` is **209,551**, not
4,096 — and `cannot` is now empty because the flag turned. ⭐ **Read the boot
line, never this page**, which is what the sentence above it already said.

⛔ **Note what the trained boot line does NOT say: `⛔ STAND-IN`.** That is
correct and it is also the moment the danger moves — the loud banner is gone
precisely when the output is still worthless. **`provisional` is what carries the
warning now, and it rides every response, not just the boot line.**

---

## THE FOUNDATION — measured today

### The codec, the corpus and the gates

| Capability | State | Command | Result |
|---|---|---|---|
| The codec round-trips | ✅ **REAL** | `node codec/verify/js-selftest.mjs` | **ALL CHECKS PASSED** |
| The core is portable to a phone | ✅ **REAL** | `node codec/verify/core-purity.mjs` | **CORE IS PORTABLE** |
| The Python twin is bit-exact | ✅ **REAL** | `node codec/verify/parity.mjs` | ⭐ **maxDiff = 0 at every stage** · 52 image + 5 audio cases · ten stages compared |
| Audio round-trips | ✅ **REAL** | `node codec/verify/js-selftest.mjs` | **1.515%** relative L2 against a 2% target |
| The turn lifecycle | ✅ **REAL** | `node app/turn-selftest.mjs` | **44 passed, 0 failed** |
| Corpus provenance + stats | ✅ **REAL** | `node datatools/build-corpus.mjs --stats` | **36,889 fields · 57.2% of a 64,525 target · 33,883 captioned** (re-run 2026-09-03) |
| Base-query audit, all groups | ✅ **REAL** | `node datatools/base-query-audit.mjs --all --cells <ids> --per-query 12` | 31 queries repaired · metric-fit gate refuses cells it cannot judge |
| Operator keep population | ✅ **REAL** | `node datatools/keep-derive.mjs` | **6,293 operator-implied keeps across 35 cells, zero clicks** |
| Gate false-refusal rate | ✅ **MEASURED 2026-09-03** | `python datatools/gate-hindsight.py --n 50` | ⭐ **junk 94.0% refused (bar ≥50%) · keeps 6.0% refused (bar ≤25%) — BOTH PASS.** ⚠ n=50/direction. The earlier 66.7% failure was the POPULATION (*"not yet deleted"*), confirmed by measurement: same bar, same gates, 66.7% → 6.0% on the operator-implied keeps |
| Training shards build | ✅ **RUNS** (2026-09-03) | `node train/shard.mjs` | ⛔ **REFUSES** — 3,029 uncaptioned. That is the gate working; it had been unreachable code since ~5,000 entries |
| Tokens/image at matched fidelity | ⚠ **RE-RUNNABLE, NOT RE-RUN** | `node tokenizer/measure.mjs` | harness fixed and split honest; ⛔ **the real run waits on the benchmark rebuild** |
| Pod cost arithmetic | ✅ **REAL** | `node train/budget.mjs` | runs; ⚠ *"RE-PRICE on the day"* |
### The documentation's own instruments

⭐ Four, answering four disjoint questions. ⚠ They audit the PRODUCT's pages,
not this one — and the boundary between the two is itself checked.

| Capability | State | Command | Result |
|---|---|---|---|
| Shipped docs carry no in-house material | ✅ **REAL** | `node monitor/docs-ship-check.mjs` | audits every document in the ship list and names each finding. **0 findings over 17 documents.** ⛔ **And it REFUSES (exit 2) if any `docs/*.md` is on neither the ship list nor its declared not-shipped reasons** — a new document cannot land unclassified |
| Shipped docs match the house format | ✅ **REAL (2026-09-07)** | `node monitor/docs-style-check.mjs` | 12 checks over the ship list — front matter, one title, block length, heading depth, emphasis density, marker grammar. ⛔ **35 findings against a written bar**, 6 documents clean. ⚠ Two earlier versions of the marker check reported **16 then 45 findings, all false** — a lint that cries wolf audits nothing, so every category was opened and read before the count was recorded |
| The modality mix is ENFORCED, not planned | ✅ **MEASURED 2026-09-07** | `node train/mix-actual.mjs --shards <set>` | ⭐ **image 84.98% · audio 12.02% · text 3.00%** against a plan of 85/12/3 — **within 0.02%** on 598 shard files, **3.54 B tokens per epoch.** ⚠ And the axis that is a rule: **text 100% VOICED, 0 unvoiced.** ⛔ For two whole runs this was a document nothing built to, at a measured `text 0.06%` |
| Every control says what it does | ✅ **REAL (2026-09-07)** | `node monitor/tooltip-check.mjs` | ⭐ **56 of 56 controls — 100%** across the switchboard, the app, the docs viewer and the corpus portal. ⛔ **It was 13 of 57 (23%) before this row.** ⚠ A tooltip here states what the control DOES and what happens IF IT FAILS — never its own label, which would spend a hover and return nothing |
| Every code reference in a shipped doc exists | ✅ **REAL (2026-09-07)** | `node monitor/docs-refs-check.mjs` | **294 references · 90 distinct · 10 `path:line` citations — all resolve or carry a named exemption.** ⭐ Exemptions are classes with reasons, not a suppression list: an HTTP route, a path at the relocatable data root, a glob, a path the code **refuses on by design**, and another project's files this repo documents on purpose. `--why` prints every one |

⛔ **`maxDiff = 0` proves two implementations AGREE. It says nothing about whether
the maths is good** — that is the tokenizer, below, and its answer was no.

---

## ⭐ WAS BROKEN, FIXED 2026-09-03 — found by running it, and fixed by running it

| Command | State | What happens |
|---|---|---|
| `node tokenizer/selftest.mjs` | ⭐ **FIXED 2026-09-03** | runs to the end — *"PLUMBING IS CORRECT"* |
| `node tokenizer/measure.mjs` | ⭐ **FIXED 2026-09-03** | completes the full sweep and prints its corpus split |
| `node tokenizer/train.mjs` | ⭐ **FIXED 2026-09-03** | streams; refuses loudly if nothing matches its corpus filter |
| `node train/shard.mjs` | ⭐ **FIXED 2026-09-03** | ran for the first time since ~5,000 entries; every refusal inside it fired |
| `node datatools/caption-gate-selftest.mjs` | ⚠ **54/58** | 4 failures, all in the HEDGED/audit group |

### The cause, named — and now removed

```
  was:  tokenizer/train.mjs:45   loadCorpus(limit = Infinity)
                                 → reads EVERY field file into memory at once
        selftest.mjs:171 · measure.mjs:89 · train.mjs:172 · shard.mjs:100
                                 → all called it with no limit
```

⭐ **Nothing was broken by a code change — the CORPUS GREW PAST IT.** These
commands ran when the corpus was 654 fields; by 2026-09-03 it was **36,302
fields at ~2.68 MB each ≈ 97 GB**, against V8's ~4 GB default heap.

⭐⭐ **FIXED WITH A STREAMING, RE-ITERABLE LOADER** (`streamCorpus`). The corpus
is never resident — **measured at 6.29 GB of coefficient payload streamed
against a 0.20 GB peak heap.** ⚠ It returns a *re-iterable*, not a generator,
because `measure.mjs` trains codebooks in a nested loop and **a generator is
consumed once — the other eleven books would have trained on an empty corpus and
reported success.**

⚠ **The earlier refusal to fix this is kept, because it was right at the time:**
*"Bounding or sampling the corpus load changes which images the codebooks are
trained on... That is a research decision."* ⭐ **The reasoning came back**
— *"read out stack of what an EDM model ... needs"* — and
the requirements decided it: **train on `trn_*`, measure on held-out `real_*`,
print the split.** ⛔ `train/shard.mjs` needed no streaming at all in the end —
every exclusion in it reads manifest metadata and none touches a field, so it
was loading 97 GB to filter JSON it already had.

⚠ **The 4 caption-gate failures are in files I have not modified**
(`datatools/caption-gate.mjs` and its self-test are byte-identical to before this
session's changes), so they pre-date the caption work and are recorded rather
than attributed.

---

## THE TOKENIZER — ⛔ built, measured, and the bet lost

| Claim | State | Proof |
|---|---|---|
| The plumbing is lossless | ✅ **REAL** | `tokenizer/selftest.mjs` — **maxDiff 0** on the sections that run |
| Coarse-to-fine ordering | ✅ **REAL** | same — *"64 subbands (tensor layout, NOT 3-per-level)"*, subbands tile exactly, 0 uncovered, 0 double-covered |
| Progressive decode | ✅ **REAL and structural** | the 25/50/75% columns of `docs/MEASUREMENTS.md` |
| Fewer tokens than pixel VQ | ⛔ **FALSE below 27.49 dB — MEASURED** | ⭐ **RE-MEASURED on 120 spread benchmark images — BENCHMARK key `c6efe4290157`, CORPUS key `bc7a9982f6e5` — superseding the contaminated 144×.** Scheme A: pixel wins **126.65×** at 20 dB, **31.92×** at 25 dB. Scheme B ((e), vocab 167): **6.0×** at 25.29 dB. ⛔ **ABOVE 27.49 dB THE QUESTION DOES NOT APPLY — the pixel family cannot reach it at any token count, and (e) sits at 29.80 dB for 120,357 tokens.** ⚠ **TWO KEYS, TWO DIFFERENT FACTS, and reading either as the other is a provenance error:** the *benchmark* key says WHICH IMAGES WERE SCORED, the *corpus* key says WHAT THE CODEBOOKS TRAINED ON. **The whole point of this row is that those two sets are DISJOINT** — see `MEASUREMENTS.md`, which is regenerated and authoritative |
| Higher ceiling than pixel VQ | ✅ **REAL** | above ~33 dB the field reaches fidelity the baseline **cannot reach at any rate** (41.43 dB at B=2) |
| Scheme B (scalar + entropy) | ⭐ **MEASURED, AND IT IS THE ONE THAT SHIPS** | ⚠ **this row said *"exists; unmeasured"* until 2026-09-07 and had been wrong for four days.** On 120 held-out images (corpus key `bc7a9982f6e5`): **120,357 tokens at 29.80 dB**, where the pixel family **cannot be bought past 27.49 dB at any token count**. Where they overlap the gap collapses **126.65× → 6.0×** |
| The voice tokenizer | ⚠ **VERDICT WITHHELD — and the reason CHANGED** | **5.7%** relative error vs a **3.04%** floor, ⛔ *on synthesised tones, not on her voice*. ⭐ **But the weights have now heard her**: 12.02% of the training tokens were audio, drawn from the 8,203 banked clips. ⛔⛔ **NOBODY HAS PLAYED A SAMPLE BACK**, so the withheld verdict stands on a different question than it used to — it was *"can the codec carry a voice"*, it is now *"does the model produce one"* |

⚠ **Reproducing the gate's numbers is currently blocked twice over:** the commands
above are out of memory, **and** `--stats` reports the benchmark set as
**`0 of 500`** — the 534-real set those numbers were measured on is no longer in
the manifest (all 14,773 entries carry `role: training`).

⛔ **That is the sharpest instance of this project's own rule.** *"Every number
should be reachable by running something. If one is not, that is the bug."*
`docs/MEASUREMENTS.md` currently holds numbers that cannot be re-run.

---

## THE APPLICATION SURFACES

| Surface | State | Proof |
|---|---|---|
| The model slot | ✅ **REAL** | `validateSlot` runs at boot and **exits 1** on a bad implementation |
| Explicit model selection | ✅ **REAL** | `U3E_MODEL=legacy` with no wrapper **refuses to boot** — it will not substitute |
| Weights-on-disk guard | ✅ **REAL** | boot **throws** if `serve/weights/model.json` exists without a loader |
| Progressive emission | ✅ **REAL** | `POST /api/image {progressive:true}` → NDJSON, coarse first |
| Client-side reconstruction | ✅ **REAL** | the wire carries **coefficients**; the browser runs `idwt2` |
| Same sources in Node and browser | ✅ **REAL** | `core-purity` + `/codec/*` served from disk, **no build step** |
| The orb, transcript, revision | ✅ **REAL** | `node app/turn-selftest.mjs` → 44/44 |
| Gallery stores fields, not PNGs | ✅ **REAL** | kilobytes per entry, re-renderable at any size |
| The corpus portal | ✅ **REAL** | `node datatools/portal/server.mjs` → **:8788** |
| The bank + model monitors | ✅ **REAL** | **:8795** / **:8796** |
| Android APK | ⚠ **a client onto a PC** | ⛔ not on-device inference |

---

## THE CORPUS

| | Measured |
|---|---|
| **Training corpus** | **14,675 of 40,050** across **98 cells** — 36.6% |
| **Captioned** | 10,397 of 14,773 |
| **Benchmark set** | ⛔ **0 of 500** — see the warning above |
| On disk | **36.90 GB** · mean 657,139 coefficients per image · mean ratio **1.9×** |
| Disk to finish | **~119 GB** more (band 112–138) · **~156 GB** total at target · see below |
| Provenance | ✅ source · `source_url` · sha256 · licence · query · cell · date, enforced |
| Caption openers | ⚠ **3,425 re-queued** — ⛔ the prompt fix alone left **29.6%** still opening `I'm <verb>in'`; the rule is enforced on the output now (`--dry --limit 8`: **0.0% shipped posture-led**) |
| **Intake gate** | ✅ **REAL** — every candidate for one of the **50** adult/explicit cells is looked at by a vision model and refused unless it reads `adult` or `none`. Proves its own sight against a **no-image control** first; refuses the whole cell rather than guessing when it cannot run (`guardUnavailable`, published separately from `minorBlocked`). ⚠ **Minors only — it does NOT check subject match**, and it is **forward-only** |
| **Sight gate** | ✅ **REAL** — the captioner refuses a model that is not looking, decided against its own **no-image invention** rather than by comparing two answers to each other. Measured both ways: `llava:7b` passes at **20% / 20%**, `dolphin3:8b` refused at **100% / 100%** |
| **Cells reachable** | ✅ **184 of 184.** ⛔ Was **121 of 184** — six `animation-adult` cells raised in `expand_queries` and killed the process at round-1 position 122, every run. Of positions 1–121, 100% had been searched; of 122–184, **2%** |
| **Bank rate** | **14.2–15.5 /min** sustained on the fixed code, against **2.07 /min** before it — acceptance **0.37% → 8.6%** |
| **Drift sweep** | ⚠ **PARTIAL** — `datatools/drift-sweep.mjs --watch` follows the captioner and flags adult/explicit entries whose observation describes a child. **A tripwire, not a classifier: a flag means go and look.** Idempotent on a version stamp so a watch loop converges; merges only `cell_drift`/`cell_drift_reason` because there are now **three writers on one manifest**. ⛔ **The write path is unexercised** — no new entry has tripped it yet |

⛔ **Benchmark and training are two different numbers and conflating them is a
documented mistake here.** The benchmark is a fixed measuring stick — *measured
on, never trained on*. A met benchmark once read as a finished corpus.

⚠ **`mean round-trip PSNR: NaN dB`** in the current `--stats` output. Recorded as
observed; not diagnosed in this pass.

### DISK — what the finished corpus costs

**Measured 2026-08-31** by walking `data/corpus/` and the manifest, not estimated
from a target:

```
banked now      15,056 entries              36.90 GB     2.509 MB each
  field files   15,056 × .field.json        36.88 GB     2.508 MB each
  manifest      all captions + metadata     18.1 MB      1,263 B each

① remaining     48,619 entries        →     ~119 GB      band 112 – 138 GB
② at target     63,675 entries        →     ~156 GB      band 148 – 175 GB
③ free after    180 GB free today     →     ~61 GB left  worst case ~42 GB
```

⭐ **Captions are a rounding error.** All 9,224 of them are **1.25 MB of text**
(mean 142 characters) inside an 18 MB manifest. The cost of this corpus is
entirely coefficient fields.

⚠ **WHY THE BAND, AND IT IS NOT PADDING.** The 2.509 MB mean comes from what is
banked, and across those ten groups it is tight — **2.348 to 2.911 MB, ±12%**
(`places` 2.911 · `living` 2.735 · `objects` 2.682 · `abstract` 2.622 ·
`children` 2.599 · `adult` 2.553 · `unity` 2.548 · `outfits` 2.464 · `people`
2.348 · `command` 2.330).

⛔ **But 23,625 of the 48,619 remaining — 49% — sit in ten groups with ZERO
banked yet**: `animation` · `animation-adult` · `decay` · `humour` · `world` ·
`authority` · `weapons` · `nightlife` · `vices` · `substances`. About half of
those are **drawn art**, which is a different animal in a wavelet field: flat
colour and clean linework are **sparser → smaller**, while `anim-manga-lineart`
screentone and the `decay` macro textures are dense high-frequency → **larger**.
They plausibly cancel. **The band is the honest width until a few thousand of
them are on disk**, at which point this line becomes a measurement rather than a
projection — ⚠ **re-run it then rather than quoting this.**

⚠ **An I/O note that is not a disk note:** `manifest.json` reaches **~77 MB** at
target and is a single JSON file **rewritten on every image by two processes**
(see the merge rule in `docs/CORPUS.md §7`).

⛔ **NOTHING WATCHES THIS.** There is no free-space guard in `datatools/bulk-bank.py`,
`monitor/bank.mjs` or `datatools/caption-run.mjs` — grep-verified. The corpus fits
today with room to spare; it fits because the drive is large, not because
anything is checking.

---

## ⛔ WHAT IS NOT CLAIMED, AND WILL NOT BE

- **"Vision and STT come free."** Free in *representation* — the same transform
  runs inwards. ⛔ **Not free in training:** both directions still need paired
  data. Blurring those two is the unearned claim this project's first law exists
  to prevent.
- **"3D."** The coefficient tensor — channel × space × **scale**. ⛔ Not
  volumetric geometry. A 2-D field is flat, and with snap off, moving off-axis
  reveals a card. That is the truth of the representation, not a bug.
- **Progressive decoding is ours alone.** ⛔ It is not. JPEG2000 has SNR and
  resolution scalability natively. Ours is structural and free; it is **not
  unique**.
- **Per-example provenance at inference.** A trained model does not retain where
  an output came from. Corpus-level attribution is what is achievable.
- **She will sound like herself.** ⚠ The voice numbers are on tones. **No metric
  substitutes for listening.**

---

## RUN THE WHOLE MATRIX

```bash
node codec/verify/js-selftest.mjs      # ✅ ALL CHECKS PASSED
node codec/verify/core-purity.mjs      # ✅ CORE IS PORTABLE
node codec/verify/parity.mjs           # ✅ maxDiff = 0 at every stage
node app/turn-selftest.mjs             # ✅ 44 passed, 0 failed
node datatools/build-corpus.mjs --stats     # ✅ both corpus numbers
node train/budget.mjs                  # ✅ runs
node monitor/docs-ship-check.mjs       # ✅ shipped docs carry no in-house material
node monitor/docs-style-check.mjs      # ⛔ 35 style findings · 6 documents clean
node monitor/docs-style-check.mjs --stats   # ✅ the measured basis, no verdicts
node monitor/docs-refs-check.mjs       # ✅ 294 refs · 10 citations · all resolve
node monitor/docs-refs-check.mjs --why      # ✅ every exemption and what it caught
node datatools/caption-gate-selftest.mjs    # ⚠ 54/58
node tokenizer/selftest.mjs            # ⛔ heap OOM
node tokenizer/measure.mjs             # ⛔ heap OOM (same call)
node serve/server.mjs                  # ✅ prints can / cannot / STAND-IN
node train/eval-five.mjs --dry         # ⚠ needs the player up; measures what it can
```

⛔ **`eval-five.mjs` REFUSES TO WRITE A RECEIPT WHEN THE PLAYER IS DOWN**, and it
records `standIn` on every run. ⚠ **A measurement taken against the stand-in is
evidence about the harness and about nothing else** — the pipeline's step 17 will
not tick on one, and the row says so in words rather than going quietly green.

⭐ **If a row on this page cannot be reproduced by the command beside it, the row
is the bug — not the command.**
