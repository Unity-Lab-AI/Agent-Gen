---
# Provenance. See docs/ARCHITECTURE.md for the full note.
# ⚠ `last-verified` is the commit that last TOUCHED THIS PAGE.
# ⛔ Per-pass history lives in the body under `## Verification history`, newest
# first — never concatenated onto the `last-verified` line.
# `status` stays `draft`: the WIRE CONTRACT was checked exhaustively (every frame
# type the encoder can emit, the version/capability gates, the admission floor),
# but the JSON message schemas in the first half of this page were not re-read
# field by field. `verified-scope` says which is which, so `draft` is a
# boundary, not a shrug.
status: draft
verified-scope: >
  Binary frame table checked EXHAUSTIVELY: every `_encodeSparseHeader(N` site in
  server/brain-server/gpu.js was enumerated and diffed against the documented
  set — that is how the undocumented type 6 was found. Version-negotiation gates
  and DREAM_MIN_DONOR_VERSION checked against brain-server.js:10959 (line
  re-read 2026-08-29: default still 0.3.26, the check moved down the file).
  PhaseTimingMs checked against donor-app/src/protocol.rs.
  NOT re-read field-by-field: the `welcome` / `state` / `response` / `build` /
  `image` JSON schemas, rate limiting, reconnection behaviour.
sources:
  - server/brain-server.js
  - server/brain-server/gpu.js
  - js/brain/remote-brain.js
  - donor-app/src/protocol.rs
  # ADDED 2026-08-30 with the values-readback opcode, and the drift checker caught its absence on
  # the very edit that documents this trap: the hebbian_ranges section makes
  # line-precise claims about donor.rs:912 and donor.rs:1249 — the two sites that
  # bound that verb differently — while donor.rs was not a declared source, so
  # check 8 could never have flagged the claim that turned out to be false.
  - donor-app/src/donor.rs
  # CHECKED 2026-08-31 (doc sweep) and deliberately NOT restamped. This page was
  # examined against that batch's changes — the episodic/consolidation gate, the
  # declared-roster training-card fields, and the academic-corpus coverage — and
  # is UNAFFECTED by all three: none of them touch the wire protocol, the frame
  # types, or the client contract. ⛔ Saying so explicitly because a silent
  # omission from a sweep reads as "checked and clean" when it usually means
  # "not opened". ⚠ last-verified stays at the older commit ON PURPOSE: its
  # sources HAVE moved for unrelated reasons and this pass did not re-verify the
  # protocol claims themselves, so the drift check should keep reporting it.
last-verified: "0ee5ac68 2026-08-29"
---

# WEBSOCKET — Unity Brain Server Wire Protocol

> Complete reference for the WebSocket protocol between `server/brain-server.js` and its clients.
> Every message type, every payload shape, every state broadcast, every reconnection rule.
>
> Unity AI Lab — 2026-04-13

---

## Endpoint

### Local dev

| | |
|---|---|
| **Default URL** | `ws://localhost:7525` |
| **Env override** | `PORT=xxxx node server/brain-server.js` (bumps both HTTP and WebSocket to the same port) |
| **Library** | [`ws`](https://github.com/websockets/ws) on the server, browser-native `WebSocket` API on the client |
| **Handshake** | Plain HTTP upgrade on the same port as the dashboard/health/compute endpoints |
| **Content type** | JSON, UTF-8, one message per frame |
| **Compression** | None — `ws` default is to negotiate permessage-deflate if both ends offer it |

Local dev connects the browser directly to `ws://localhost:7525` — no proxy, no auth (see the hostname gate under "Client Reconnection Behavior").

### Deployed (tunnel lanes)

In production the Node brain-server binds to loopback only (`127.0.0.1:7525`) on the lab's own machine and is never exposed directly. A **Tailscale Funnel** fronts it and forwards exactly these paths; anything else answers 404 from the tunnel itself:

| Lane | URL | Auth | Who connects |
|---|---|---|---|
| **Public donor/viewer** | `wss://<brain>/ws` | None | `compute.html` donor GPUs, the native donor, chat clients, read-only viewers |
| **Public reads** | `https://<brain>/public-state.json`, `/minds-eye.json`, `/health`, `/image/<id>.png` | None | the public pages (CORS `*`) |
| **Admin** | `ws://127.0.0.1:7525/admin/ws` | Loopback only — `requireLoopback` on the brain | The operator, on the brain's own machine. **Not forwarded by the tunnel.** |

The page learns `<brain>` from `js/brain-origin.js`. The brain's WebSocket server accepts an Upgrade on any path, so the "public lane is `/ws` only" rule is enforced by what the tunnel forwards — the route list in `deploy/tailscale-funnel.bat` is the security control. Admin REST control endpoints live at `/admin/<endpoint>` and are reachable only on loopback (see "Server Endpoints").

**R14 note (2026-04-13):** Unity's brain server used to bind to port `8080`, which collides with llama.cpp's default, is one of the most commonly-used ports, and was a port R13 explicitly wanted to auto-detect for vision describer backends. R14 moved Unity to `7525` — not used by any backend Unity probes, so Unity never fights its own vision detection. If you're still running an old deployment on `8080`, set the `PORT` env var on `node brain-server.js` to keep the old behavior.

---

## Connection Lifecycle

```
Client opens ws://localhost:7525
    ↓
Server accepts, assigns unique id: "user_<timestamp36>_<rand4>"
    ↓
Server sends { type: 'welcome', id, state, emotionHistory }
    ↓
Client holds connection open, receives state broadcasts (10 Hz)
    ↓
Client sends { type: 'text', text: '...' } on user input
    ↓
Server runs equational response pipeline, sends back { type: 'response'|'build'|'image', ... }
    ↓
(No broadcast to other clients — user text is PRIVATE between the user and Unity. See "Privacy model" below.)
    ↓
On disconnect: server removes client from brain.clients map
```

`brain.clients` is a `Map<WebSocket, {id, lastInput, inputCount, name, isGPU?}>`. The server tracks every connected client for rate limiting and GPU compute dispatch. **No cross-client broadcast of user text happens** — see "Privacy model" below.

---

## Messages: Server → Client

Every message is a JSON object with a `type` discriminator. Clients should switch on `msg.type` and ignore unknown types (forward-compat rule — new types will be added in future releases).

### `welcome`

Sent once, immediately after connection is accepted.

```json
{
  "type": "welcome",
  "id": "user_1mz8r4k_9f2x",
  "state": { /* brain.getState() snapshot */ },
  "emotionHistory": [ /* last 300 emotion data points */ ]
}
```

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Unique client id assigned by the server for rate-limiting / log tagging. No longer used for cross-client broadcast filtering — the `conversation` broadcast was removed 2026-04-13 per the privacy model. |
| `state` | object | Full brain state snapshot (same shape as the per-frame `state` broadcast). Used to hydrate the client HUD immediately on connect. |
| `emotionHistory` | array | Last 300 entries from `brain._emotionHistory`, so a freshly-connected dashboard can render the emotion chart without waiting for new data. |

### `state`

Broadcast to every connected client every `STATE_BROADCAST_MS` (100 ms → 10 Hz).

```json
{
  "type": "state",
  "state": {
    "time":      12345.67,
    "frameCount": 67890,
    "reward":    0.12,
    "clusters": { "cortex": {...}, "hippocampus": {...}, ... },
    "modules":  { "amygdala": {...}, ... },
    "oscillations": [...],
    "mystery":  { "psi": 1.34, "id": ..., "ego": ..., ... },
    "motor":    { "selectedAction": "respond_text", "channelRates": [...] },
    "drugState": "sober",
    "drugSnapshot": {
      "sober": true,
      "active": [],
      "combos": [],
      "riskFlags": {},
      "pendingDesires": [],
      "pendingAcquisitions": [],
      "gradeLocked": false
    },
    "cortexDivergence": 0.0,
    "cortexDivergenceByRegion": {
      "auditory": { "standRate": 0.0, "mainRate": 0.0, "divergence": 0.0 },
      "letter":   { "standRate": 0.0, "mainRate": 0.0, "divergence": 0.0 }
    },
    "profiling": {
      "host":       { "loadAvg": [1.4,1.3,1.4], "cpuCount": 16, "sysMemUsedPct": 41, "osUptimeS": 0 },
      "process":    { "rssMB": 6822, "heapUsedMB": 18, "heapLimitMB": 16384, "heapUsedPct": 0, "cpuPercent": 42, "voluntaryCtxSwitches": 0, "uptimeS": 0 },
      "throughput": { "stepTimeMs": 8.5, "stepsPerSec": 16, "eventLoopLagMs": 8, "eventLoopDelay": {"meanMs":1.2,"p50Ms":0.8,"p99Ms":7.1,"maxMs":9.5}, "gpuDispatchPerSec": 1, "totalSpikes": 0, "defsLearnedPerHour": 0 },
      "network":    { "bytesInTotalMB": 0.03, "bytesInPerSecKB": 0, "bytesOutPerSecKB": 0, "msgInTotal": 0, "donorCount": 1, "aggGneuronsPerSec": 0, "wsPressure": { "...": "see _getWsPressureState" } },
      "clients":    { "total": 4, "admins": 1, "viewers": 2, "donors": 1, "totalConnectionsEver": 4, "avgRttMs": null, "unhealthyCount": 0, "shown": 4, "list": [ { "id": "user_…", "type": "donor", "rttMs": 35, "bytesInMB": 0, "bufferedKB": 0, "unhealthy": false } ] }
    },
    "clientCount": 3
  }
}
```

The exact shape comes from `brain.getState()` in `server/brain-server.js` — it's the full live snapshot the dashboard renders. This is the highest-traffic message by volume (10 Hz × every client).

`profiling` (`server/brain-server/state.js _getProfilingState()`) is the admin Application Profiling payload — **host** hardware, **process** resource usage, **throughput** (incl. a `perf_hooks.monitorEventLoopDelay` percentile histogram + GPU dispatch rate), **network** (per-WS byte totals + live rates, reuses `wsPressure`), and **clients** (per-connection health — type/RTT/bytes/buffered, `unhealthy`-flagged + sorted first, list capped at 24 + `shown`). Per-client byte/RTT counters are instrumented in `brain-server.js` (send-wrapper + inbound listener + heartbeat ping/pong). The dashboard renders it in an `admin-only` Profiling card; public viewers receive it in `/public-state.json` but the panel is admin-gated. Full field reference: `docs/ADMIN-CONTROLS.md`.

`consciousness` (`server/brain-server/state.js _getConsciousnessState()`) is the equational-consciousness telemetry block — GlobalWorkspace ignition (current broadcast + strength + rate% + history), predictive-coding error sparkline, Ψ consciousness gain, Dictionary-API status, K-wiring assertion, cortical microstructure, defs-learned-per-hour. **`consciousness.speechHealth` (2026-07-01)** — per-subject speech separability for the dashboard's speech-health card: for each bucketable subject, the FROZEN `cellSize` (vocab-growth-invariant geometry) + the `sem_to_word_motor` weight-mass ratio (max/mean |W| — the separability proxy), plus the coherence-floor stats (`_coherenceFloorStats {total, rejected}`) and best-of-N rerank stats (`_coherenceRerankStats`). Surfaces basin-separability regression at G4 instead of G9. All fields bounded/aggregate (no per-word enumeration) per the dashboard-discipline constraints.

`utilization` (`server/brain-server/state.js _getUtilizationState()`, 2026-07-10) is the neuron-utilization telemetry block — `langEverFired` (LIFETIME unique-fired coverage over the CPU-owned language cortex: total/size/pct + per-region breakdown + since-stamp; `lastSpikes` OR'd into a persistent bitset every ≥5s) and `weightRecruitment` (throttled 5-min rowPtr-diff scan over the authoritative CPU CSR master: per tracked projection, rows/recruitedRows/pct). Distinguishes per-tick sparse coding (healthy ~1-2%/tick) from never-recruited dead volume. Main-brain lifetime bitsets await donor-side spike-bitset readback (GPU owns main-brain spikes as counts only). Rendered by the dashboard '🧮 Neuron Utilization' card; all fields bounded/aggregate per the dashboard-discipline constraints.

`drugSnapshot` is `DrugScheduler.snapshot(now)`. `active` carries per-substance `{substance, displayName, level, phase}` where phase ∈ {onset, peak, plateau, tail, sober}. `combos` carries per-pair `{key: 'a+b', displayName, level: min(level_a, level_b)}` for the 7 synergy entries in the COMBOS table. `riskFlags` maps axis name → cumulative intensity across active combos (e.g., `physicalStrain`). `pendingDesires` maps substance → `{delta, expiresAt}` from sensory-trigger cravings. `pendingAcquisitions` tracks substances Unity is waiting on (dealer / friend / party source).

`cortexDivergenceByRegion` is the sparse-dispatch Phase C follow-up telemetry — per-region `{standRate, mainRate, divergence}` between standalone `cortexCluster.lastSpikes` and main-cortex GPU spike slices. Rates in [0, 1] (spike fraction); divergence rounds to 5 decimals. Empty during GPU warmup.

The sparse-dispatch + slice-access wire protocol adds binary frames (type=1 upload / type=2 propagate / type=3 hebbian / type=4 chunked-upload) plus JSON messages `write_spike_slice` / `write_current_slice` (sparse `sparseIndices`/`sparseValues` carrier — the dense `values` form is retired: the native donor's deserializer never had a dense field, and the chat text-injection's dense send measured 23.4MB/message and was the drop-on-speak killer; sparse ships ~160 bytes) / `clear_spike_region` / `rebind_sparse` / `readback_letter_buckets` / `readback_matrix_checksum`. All are server → compute.html; each has a matching `*_ack` response. Handled in `js/brain/gpu-compute.js` + `compute.html` onmessage dispatcher + `server/brain-server.js` ack-switch (`case 'sparse_upload_ack' | 'sparse_propagate_ack' | 'sparse_hebbian_ack' | 'rebind_sparse_ack' | 'readback_letter_buckets_ack' | 'readback_matrix_checksum_ack'`).

**`readback_matrix_checksum` — GPU↔CPU parity.** `{ type:"readback_matrix_checksum", reqId, name, sampleCount }` → the donor reads its ACTUAL resident sparse-matrix `values` buffer and replies `{ type:"readback_matrix_checksum_ack", reqId, name, found, nnz, checksum, samples:[{idx,val}] }`. `checksum` is FNV-1a-64 over the bit-exact little-endian f32 value bytes, returned as a **DECIMAL STRING** (it survives JSON's number range). It is byte-identical across all three donor implementations — native wgpu (`donor-app` ComputeEngine), native CUDA (`memcpy_dtov`), and browser (`gpu-compute.js checksumSparseMatrix`, BigInt FNV) — all x86-64 LE with LE GPU buffers.

The server compares it against a digest of its CPU-master matrix **in the same f32 representation it uploaded** (`_cpuMasterMatrixChecksum`), and `parityCheckMatrix` returns one of four verdicts. ⭐ **They are separate verdicts because they want OPPOSITE responses:**

| Verdict | Means | What to do |
|---|---|---|
| `CLEAN` | the two agree | nothing |
| `STALE` | weights differ — dropped uploads | **re-send fixes it** |
| `GPU-DIVERGENT` | weights match, but the same input propagates differently — shader/precision bug | ⛔ **a real bug; re-sending will NOT help** |
| `MATH-ERROR` | the CPU reference propagate is wrong | look at the server, not the donor |

Exposed via the loopback `GET /diag/parity?name=<matrix>&samples=<n>`. ⚠ Requires the values buffer to carry `COPY_SRC` usage — added on both donor paths so the resident weights are readable at all.

**`readback_matrix_values` (donor v0.3.36, 2026-08-30) — THE CHECKPOINT NOW SAVES THE WEIGHTS THE GPU ACTUALLY TRAINED.** `{ type:"readback_matrix_values", reqId, name, chunkBytes }` → the donor streams the resident values buffer back as **type=7 SPRR binary chunks** in ascending order, then closes with `{ type:"readback_matrix_values_ack", reqId, name, found, nnz, byteLen, chunks, chunkBytes, checksum, error? }`.

⛔ **Why it had to exist.** The brain's checkpoint has always been written from its CPU arrays, and those are **not a lagging copy of the resident weights — they are a different brain**: 94% of plasticity arrives via `hebbian_bound`, which trains on the donor's RESIDENT spike state the host never sees, at ~49× the host's update rate, and the two were measured drifting apart at **+0.0124 mean-magnitude ratio per minute** with no reconvergence. Until this opcode, every Savestart restored weights that had not done the learning. ⭐ Both kernels were read to rule the alternative out first: `plasticity.wgsl` computes `w = w*(1-eta) + eta*x` and `ojaUpdate` computes `w += lr*y*x - lr*y²*w`, which with `lastSpikes` a `Uint8Array` (`y²=y`) is the **identical function**, with `reward` hardcoded `1.0` and clamps `-2.0/+2.0` on both sides. **The math agrees; the inputs and the counts do not.**

**Frame layout — 32-byte header so the f32 payload lands 4- AND 8-byte aligned** (a misaligned typed-array view is exactly how the ALIGNKILL crash presented): `'SPRR' | 7 | pad(3) | reqId@8 | chunkIdx@12 | totalChunks@16 | byteOffsetLo@20 | byteOffsetHi@24 | payloadBytes@28 | payload@32`. ⚠ **`byteOffset` is split across TWO u32 deliberately** — the intra matrix is already ~1.81 GB and the language cortex is on a growth ladder; a u32 byte offset wraps silently at 4 GiB and would reassemble two chunks onto the same destination, and **no per-chunk check would catch it because each chunk is individually valid.**

**Chunked, and applied streaming.** ~452M nnz is too big for one frame (~16 MiB donor ceiling), too big for one staging allocation, and too big to buffer host-side (1.81 GB as f32 — and since 2026-09-05 that is also what it costs in host RAM, because the CPU master narrowed to Float32 too; it used to double to 3.6 GB on arrival). Each chunk carries its absolute offset, is written straight into `matrix.values` at the same width it arrived in, and is dropped. ⭐ The receive loop indexes by ELEMENT, never by byte offset into the values array, which is why it needed no change when the store's width did. The donor slices on the device in both backends — wgpu via `copy_buffer_to_buffer` at an offset into a chunk-sized staging buffer, CUDA via a `CudaSlice` view, never `memcpy_dtov` of the whole buffer (which would allocate 1.81 GB per chunk, the exact cost chunking exists to avoid).

**Completeness is a CHECKSUM, not a byte count.** The donor accumulates FNV-1a-64 over exactly the bytes it puts on the wire, in send order, and ships it in the closing ack — the same digest `readback_matrix_checksum` returns, so server and donor compare without a second read. The transfer FAILS on any of: not-found, chunk-count mismatch, out-of-order arrival, overrun past the CPU array, or digest mismatch. ⛔ **On failure the server does NOT save** — a partial transfer leaves `matrix.values` a mix of old-CPU and new-GPU rows, and a checkpoint written from that is a *third* brain; the existing CHECKROT slots stay coherent instead.

**Cadence, priced before it shipped:** the pull is ~2.3 GB ≈ 59 s at the measured 39 MB/s. **Hourly** (`DREAM_READBACK_MIN_GAP_MS`, default 3600000) = **1.6% of wall clock** and bounds crash loss to an hour; every-save (~5 min) would be **20%** on the same socket the walk teaches over. Plus a **pre-stop pull on SIGTERM** (`DREAM_READBACK_STOP_BUDGET_MS`, default 120000) so a *planned* stop loses nothing — budgeted because the shutdown save already pins the loop ~112 s and an unbounded transfer could turn a clean stop into a SIGKILL, which the clean-exit stamp would then correctly record as a hard death. The tick is deliberately not paused: values arrive with per-value age skew, the same tolerance `_collectBinarySections` already documents for the CPU-side save. Version-gated ≥ 0.3.36 per socket — an older donor silently ignores the opcode, so the request would ride its timeout proving nothing.

**Verified:** frame layout is a TEST in `frames.rs` (including a 5,000,000,000-byte offset to prove the split u64 does not wrap), and the **donor's own emitted bytes are parsed by the server's exact arithmetic** — a wire format verified only inside the language that wrote it is not verified at all. Reassembly harnessed on the real mixin: happy path widens f32→f64 bit-exactly, and a single flipped byte, a dropped chunk, an overrun, and a not-found are each caught with the reason named.

**The parity verdict became reachable, and got a cheap mode (2026-08-30).** Two things were wrong with the above in practice.

**① It was loopback-only on a box that deploys by dashboard press and takes no shell — so the harness had never once been run against the live brain.** ⛔ **An instrument nobody can reach is the same as an instrument that does not exist**, and the question it answers — *does the CPU master still match the weights the donor is actually training?* — was worth hours of walk time per boot. It now rides the same query-string tunnel as the console ring, for the same reason: **the public origin forwards only routes it already knows**, so a brand-new path is SPA-swallowed and answers 200-with-HTML, which is a lie.

**② The full digest is not a free read.** `_cpuMasterMatrixChecksum` walks every weight byte with BigInt arithmetic:

```
  intra matrix   ~452M nnz x 4B  =  ~1.8 billion byte steps
  measured                          ~5 minutes   (+ a full CPU propagate in mode 2)
```

**So the tunnel offers a cheap mode, `?parity=samples`.** The donor already ships up to 64 sampled `{idx,val}` beside its digest, and the CPU half of that comparison is **64 array reads**. It reports `maxRelDiff`, `worstSample`, and ⭐ **`cpuOverGpu`** — the ratio of mean weight magnitudes, which is the number that actually answers *"is the copy we SAVE under-trained relative to the copy that is training?"*

⚠ **Why the comparison happens in `Math.fround` space:** the CPU kept Float64 while the upload downcast, so comparing raw f64 would report a divergence **that is only the wire format.** ⭐ **Since 2026-09-05 both sides are Float32**, making the `fround` a no-op rather than a correction — so a reported divergence is now unambiguously a real one. **The call is kept anyway:** it costs nothing, and it is what keeps the comparison correct if either side's width ever moves again.

The full run stays behind `?parity=run` — one at a time, floored by `DREAM_PARITY_MIN_GAP_MS` (default 30 min), reporting its own `costMs`.

⛔ **A yield cadence in that digest was never a cadence.** `_cpuMasterMatrixChecksum` yielded on `(i & (CHUNK - 1)) === (CHUNK - 1)` with `CHUNK = 1_000_000` — the power-of-two mask idiom applied to a decimal constant. 999,999 is `0xF423F` with twelve bits set, so the test is not "every millionth step", it is "i has all twelve of those bits set": true about 1 step in 4,096, and clustered (999999, 1000063, 1000127, …). Over the intra matrix's ~1.8 billion steps that is **~440,000 yields where ~1,700 were intended**, each paying the event loop's full backlog. Now `1 << 20`. Hash output is unchanged — the cadence governs only when the walk gets a slot back.

⛔⛔ **THE PARAGRAPH BELOW IS WRONG ON ITS CENTRAL CLAIM AND IS KEPT ONLY AS THE RECORD OF HOW (corrected 2026-08-30).**

**`hebbian_ranges` is bounded by the donor at TWO sites, not one:**

```
  executor        donor.rs:912    total expanded indices <= 2M      <- the one that was read
  msg handler     donor.rs:1249   reps <= 1000
                                  pre_ranges.len()  <= 16
                                  post_ranges.len() <= 16           <- the one that was missed
```

Over the handler's limit the `if` **never pushes the work.** The verb is fire-and-forget, so there is no ack to be missing and **the drop is completely silent** — meanwhile `gpuSparseHebbianRanges` returns `true` the moment the frame leaves the socket, the caller stores that as `_gpuCarried`, and the CPU pass then runs only every 5th call.

⛔ **So every frame above 16 runs was discarded by the donor AND skipped by the CPU.** `RANGE_MAX_RUNS` is now **16**, matching the peer.

⚠ **The real contract was in the ledger the day the opcode shipped** — *"defensive caps (reps ≤1000, ≤16 ranges, ≤2M expansion)"* — and it was **re-derived from one code site instead of read from the record.**

⚠ The wire-cost arithmetic below is still correct arithmetic. It was simply answering a question that could not arise, because the donor was never going to accept those frames.

**The `hebbian_ranges` run cap was OURS, and it was sending a quarter of the heaviest op to the CPU (2026-08-30).**

**The measurement that opened it:** with the counter awake, the live box reported `rangesNullPost` on **24.2% of intra Oja calls (176 of 727)**, and every refusal becomes a full CPU pass — **176 full passes against 109 sampled shadows.** So most of the CPU time in the walk's heaviest op **was never the shadow cadence at all.**

**Then the cap was read against the donor's own source instead of assumed.** `Work::HebbianRanges` in `donor-app/src/donor.rs` expands with:

```rust
if len == 0 || len > 2_000_000 || v.len() + len > 2_000_000 { continue; }
```

- That is a cap on **total expanded indices** and on **any single range** — with **no cap whatsoever on the NUMBER of ranges** (`pre_ranges: Vec<[u32; 2]>` is an unbounded `Vec`).
- ⛔ **So `RANGE_MAX_TOTAL` mirrors a real donor limit and must stay exactly where it is.** Past it the donor **silently skips ranges and trains truncated math with no loud failure** — which is why refusing to dispatch is the only honest move on that side.
- **`RANGE_MAX_RUNS = 512` was a wire-size judgement with nothing on the other side enforcing it.** Raised to **8,192** (`DREAM_RANGE_MAX_RUNS` overrides).

**RE-PRICE — measured, not estimated:**

```
  8,192 runs on BOTH sides   208.1 KB   5.46 ms  @ 39 MB/s measured uplink
    512 runs (the old cap)    13.1 KB   0.34 ms
  the CPU pass it replaces              123.8 ms  (cpuMs 35,288 over 285 passes)
                                        -> 23x cheaper
```

Donor-side work is **unchanged**, because the expanded index count is still capped at 2M.

⭐ **The arithmetic was verified against the donor's own expansion logic transcribed from the Rust** — 1 run, 600 runs, 5,000 runs, 8,191 runs (at the cap), mixed run lengths, and a 3,000-run dense pattern all re-expand to **byte-identical index sets.**

⚠ **And the refusals are now NAMED:** `rangesFail_empty` / `rangesFail_runs` / `rangesFail_total`, plus `rangesRunsMax` and `rangesRunsOkMax`. **An empty pattern's "full CPU pass" is a no-op while a scattered one is the most expensive thing in the walk, and the aggregate could not tell them apart.** `cpuFullMs` and `cpuShadowMs` are split for the same reason — aiming a fix at the wrong half is exactly what the undifferentiated total invited once already.

**The run counter must not saturate at the cap, or it answers "did the raise help?" with the one number that cannot (2026-08-30).** Recording `runs = RANGE_MAX_RUNS` on every refusal reports "at least this many" forever. Both helpers now finish counting runs **without building them** (no push, no allocation) before refusing, so the TRUE run count is what lands in `rangesRunsMax`. The caller is about to spend >100 ms on a full CPU pass; walking the remaining indices costs microseconds beside it. ⚠ Caught by the harness: the index-side continuation was off by exactly one on every refusal — `out` holds the COMPLETED runs, the run `[runStart..prev]` has not been pushed yet, and the boundary value opens another, so it is `+2`, not `+1`. Verified against an independent run counter across stride-3 at 9,000 and 140,500, mixed run lengths, one-long-plus-many, both sides of the cap boundary, and a 30,000-run dense pattern.

⛔ **Why this matters more than the raise itself.** Sixteen minutes into the same boot the refusal rate had climbed from 24.2% to **70.4%** (1,366 of 1,939 calls) with mean active set 140,500 — **92.4% of all CPU passes in the heaviest op are now refusals, not shadows.** If those patterns are genuinely scattered (each index its own run), 8,192 will not clear them, and ranges are simply the wrong carrier: at ~140,500 runs a frame is ~4.5 MB, ~115 ms of wire against the 124 ms CPU pass it would replace, and it would flood the donor uplink. `rangesRunsMax` is what decides between "raise the cap again" and "this lane needs a different verb" — the donor already carries an index-river (SPRS type 3) and a masked form (type 13) for exactly that shape.

### `response`

Sent in reply to a `text` message when Unity's BG motor channel selects `respond_text` (or any default action).

```json
{
  "type": "response",
  "text": "whatever unity equationally generated",
  "action": "respond_text"
}
```

`text` is produced by `brain.processAndRespond(msg.text, id)`, which calls `languageCortex.generateAsync()` — the async emission path, introduced to stop the 3D brain freezing on a synchronous emission.

- **The slot scorer is DELETED.** Every word comes from a motor-region readout over learned cortex attractor basins — **zero dictionary iteration, zero softmax top-K, zero n-gram table lookup at emission time, and no AI prompt at any point.**
- **Output length is capped by the multi-subject grade word cap:** the cap reads `cluster.grades = {ela, math, science, social, art, …}` and returns the **minimum** across subjects that have advanced past pre-K, so she never speaks past her weakest trained subject. A legacy scalar `cluster.grade` is still honoured for brains saved before the per-subject ladder existed.

> ⛔ **TWO CLAIMS IN THIS PARAGRAPH WERE STALE AND ARE CORRECTED HERE (2026-09-08), both verified by reading `js/brain/language-cortex.js`:**
>
> **① It called `LanguageCortex.generate` "a 68-line delegate". It is ~421 lines** (1510 → 1931). A reader looking for a thin pass-through would not have recognised the function they found.
>
> **② And a code comment inside it still advertises a fallback that no longer exists.** `:1511` describes a *"pre-curriculum dictionary-cosine fallback … just enough to give Unity a voice from cold boot"* — while `:1506` in the same docblock says **the hand-off and the lane it fed are both gone.** Read at the branch: the only guard left is *no cluster → warn and return `''`*. **Honest silence, exactly as the no-fallbacks ruling requires.** ⚠ **The stale comment is a code finding, not a doc one**, and is filed as such — but it is worth naming here because a comment promising a fallback is how a fallback gets re-added.

**Equation references:** `docs/EQUATIONS.md § T14 Cortex Sub-Region Substrate` for the cortex equations, and `§ T14.24` for the per-subject grade-cap equation. ⚠ **Those two pointers still carry legacy identifiers because the headings they target still do** — renaming one side alone breaks the link, so both move together or neither does.

`action` may be any of the 6 motor channels — `respond_text`, `generate_image`, `speak`, `build_ui`, `listen`, `idle` — though `build_ui` and `generate_image` get split into their own dedicated message types below.

### `build`

Sent when Unity's motor channel selects `build_ui` AND the equational component synthesizer finds a matching primitive.

```json
{
  "type": "build",
  "component": {
    "id": "counter_a3f9b2c1",
    "html": "<div class='...'>...</div>",
    "css":  ".counter_a3f9b2c1 { ... }",
    "js":   "(function() { ... })();"
  }
}
```

Routed ONLY to the client who sent the triggering `text` message (per-user sandbox) — NOT broadcast. The client's sandbox layer injects the component into its own live DOM.

See `docs/EQUATIONS.md § 14. Equational Component Synthesis` for the math: user request → GloVe embedding → cosine match against `component-templates.txt` corpus → best primitive selected if `cosine ≥ 0.40`, else brain falls through to `respond_text`. `id` suffix is an 8-character hash derived from the cortex pattern at build time, so the same user request under different brain state produces a different id.

### `image`

Sent when the motor channel selects `generate_image`. The *prompt* is generated equationally on the server side (language cortex picks every word); the actual image rendering happens on the client so each user paints with their own configured image gen backend (see `docs/SENSORY.md § The Sensory AI Provider — 4-Level Priority`).

```json
{
  "type": "image",
  "prompt": "the full equational image prompt unity generated"
}
```

Routed only to the triggering client. ⭐ **Since 2026-10-18 the SERVER renders the picture** — on her own card through `image-engine.js` — and sends `{type:'image', url:'/image/<id>.png', prompt}` (a picture already made, from a bounded cache), or `{type:'response', text:'(my image engine is not answering right now — no picture this time)'}` when the engine is down. The old prompt-only message that had the visitor's browser render it via Pollinations is gone; a browser-side `SensoryAIProviders.generateImage` chain survives only for the no-server fallback brain and ends in `null`.

### `conversation` — REMOVED 2026-04-13

This message type used to broadcast `{userId, text (first 200 chars), response (first 500 chars)}` to every connected client after any `text` request completed. It was fed into the dashboard's live conversation feed.

**Removed** to enforce the privacy model: user text is PRIVATE between the user and Unity, never broadcast to other clients. The shared brain still benefits from every conversation (dictionary growth, bigrams, embedding refinements) because those all live in the singleton brain instance, but the raw text + response stay in the one client ↔ server channel.

Any client that used to subscribe to this message type will stop receiving it. `dashboard.html`'s conversation feed now shows per-session stats only (no cross-user text display).

### `error`

Sent when a client message fails validation or rate limiting.

```json
{ "type": "error", "message": "Rate limited — slow down" }
```

Currently only fires for `text` rate limiting (`MAX_TEXT_PER_SEC = 2`, so minimum 500 ms between text messages per client), but the shape is general-purpose. Clients should surface these in the UI as warnings, not fatal errors — the connection stays open.

### `speak`

Reserved. `js/brain/remote-brain.js` has a handler for this type (so clients are forward-compatible) but the current server code doesn't emit it — TTS motor actions currently route through `response` with `action: 'speak'` and the client decides whether to call its TTS peripheral. A future refactor may split speak into its own dedicated message type for TTS-only clients that don't render text.

### `innerThought`

Broadcast to all clients (not gated) on the inner-voice cadence (Hurlburt natural rhythm, ~6-75s gaps). Payload `{ type:'innerThought', word, sentence, seed, seedLabel, ts }` — her live inner monologue for the dashboard popup stream. At biological scale on the no-GPU box the `sentence` is the loop-safe showcase (now a GloVe-cosine-COHERENT trained-vocab fragment, not random word-salad); when `DREAM_INNERVOICE_GPU_GEN=1` and data-parallel donors are present it's REAL `composeSentence` generation.

### `imagine` (2026-06-27)

Broadcast to all clients when Unity imagines (server `_imagineTick`, idle-gated). Payload `{ type:'imagine', terms, source, ts }` — METADATA only (equation-term count + source `mindspace-denovo`); a dashboard "mind's-eye active" indicator. The actual field C is NOT on this message — it's served as a single cached snapshot at `GET /minds-eye.json` so the public Mind's-Eye viewer (`html/minds-eye.html`) polls one shared blob and reconstructs the image client-side (no per-viewer payload, no lag). See "Server Endpoints".

### GPU compute messages

`brain-server.js` offloads all Rulkov-map neuron iteration and synapse propagation to a browser GPU compute client running `compute.html`. The live neural rule is the Rulkov 2002 2D chaotic map (`x_{n+1} = α/(1+x²) + y`, `y_{n+1} = y − μ(x − σ)`) running as a WGSL compute shader in `js/brain/gpu-compute.js` — the `LIF_SHADER` constant name is historical, the kernel body is the Rulkov iteration. Server talks to the GPU client via four WebSocket message types on the same connection (two each way — the table below lists all four; it said "three" until 2026-08-27):

| Direction | Type | Payload | Meaning |
|---|---|---|---|
| Server → GPU | `gpu_init` | `{clusterName, size, tonicDrive, noiseAmp, lifParams, ...}` | Create GPU buffers for a cluster (one-time per cluster on boot). Neuron state is seeded on the GPU via golden-ratio quasi-random (x, y) pairs inside the Rulkov bursting attractor basin — no voltage array transferred from the server |
| Server → GPU | `compute_request` | `{clusterName, tonicDrive, noiseAmp, gainMultiplier, emotionalGate, driveBaseline, errorCorrection}` | Request one Rulkov step. GPU collapses the modulation scalars to `effectiveDrive` then `σ = −1 + clamp(effectiveDrive/40, 0, 1)·1.5` and iterates the map |
| GPU → Server | `gpu_init_ack` | `{clusterName, size}` | GPU confirms cluster is initialized |
| GPU → Server | `compute_result` | `{clusterName, spikeCount}` | GPU returns atomic-counted spike count after running one Rulkov step. Spike edge = (x_n ≤ 0) ∧ (x_{n+1} > 0) — one spike per action potential |

Why this architecture: state is `vec2<f32>` per neuron (12 bytes/neuron total including spikes u32) and stays resident on the GPU after init. Sending full state arrays every step at 60 Hz × 10 substeps × 8 clusters would be prohibitive at the auto-scaled N. Keeping state + spikes on the GPU and sending only scalar modulation inputs + a single `spikeCount` readback per step keeps WebSocket traffic under 100 KB/step regardless of cluster size. The GPU client is a regular WebSocket client from the server's perspective, just marked with `isGPU: true` in the client record after it sends `gpu_register`.

#### Distributed donor compute (data-parallel replica pool)

On the public donor lane (`wss://<host>/ws`), any number of `compute.html` donor GPUs can `gpu_register` and join a **data-parallel replica pool.**

- **Each donor gets the FULL brain** — a complete replica, not a sharded slice — and the auto-scaled N it runs is the same biological-scale brain the master holds.
- **The server periodically re-broadcasts the master via a Hebbian-delta merge:** every replica's learned deltas fold back into the master, then the merged master pushes back out.
- ⭐ **Donors never see user text.** They iterate neuron state and report spike counts and learned deltas. That is the whole of what crosses the wire.

**The re-broadcast cadence is DUTY-CYCLE BOUNDED, not fixed (2026-08-19).** A full sweep is ~4.2 GB / ~11.5 min at the ~4 MB/s the pump used to sustain, so the pool must idle `ratio × lastSweepDuration` (default 3) before the next. ⛔ **A fixed 60 s interval scheduled sweeps 11× faster than they could complete and pinned the event loop continuously.**

> **⭐ AND THE ~4 MB/s WAS THE PUMP, NOT THE PORT (2026-08-21).** The chunk loop kept only ~14 MB in flight on an event loop the gates pinned in 3–4 s slabs, **so the wire idled through most of every slab.**
>
> - **Native donors drain on a dedicated thread** and now get a **96 MB** in-flight low-water (`DREAM_UPLOAD_PACE_LOWATER_MB` overrides).
> - **Browser donors keep the 8 MB protection** their busy tab needs — ⛔ **though not until 2026-08-25.** The native test was `if (client.donorAppVersion)`, **which is truthy for a browser donor too**, so browser donors were handed the 96 MB window and lost exactly the protection this sentence promised.
> - The gate/probe propagates are chunked so the slabs shrink, and every upload logs `UPLINK measured … MB/s` on dispatch-complete, **so the real rate is a console read rather than an inference.**

| Direction | Type | Payload | Meaning |
|---|---|---|---|
| Donor → Server | `gpu_register` | `{ …, appVersion }` (native binary) | Donor joins the replica pool; server uploads the full brain to it. **Version gate:** a native binary sends `appVersion` (Cargo pkg version); if it's below `DREAM_MIN_DONOR_VERSION` (**default `0.3.26` as of `brain-server.js:10959`** — ⛔ this doc said `0.3.7` until 2026-08-27, which is a materially wrong admission floor: it *"sat at 0.3.7 for 22 releases"* and has since been raised) the server replies `{type:"incompatible_version", yourVersion, minVersion, message}` + closes (code 4001) and does NOT admit it. Browser donors omit `appVersion` → exempt. The refused donor stops reconnecting + shows "Brain status: refused — update". |
| Server → Donor | (full-brain upload + periodic master re-broadcast) | weights | Replica receives the complete brain on join, then periodic merged-master pushes |

Admin-only telemetry rides the admin lane (loopback `/admin/ws`, never forwarded by the tunnel): the live server console stream and auto-scale telemetry (replica count, per-replica throughput, scaling decisions) are pushed only to authed admin clients, never to donors/viewers.

#### Binary sparse frames (SPRS → donor, SPRR ← donor)

Bulk teach + matrix traffic rides BINARY WebSocket frames, not JSON — they bypass V8's JSON string limit and the stringify/parse round-trip (10-20× faster for typed-array payloads). Every request frame starts with the same header: `'SPRS' | typeByte(u8) | reqId(u32 LE) | nameLen(u16 LE) | name(UTF-8) | pad→4B` (the pad keeps typed-array views aligned). Acks come back as `SPRR | typeByte | reqId`. Encoders/decoders: server `server/brain-server/gpu.js` (`_encodeSparseHeader` / `_sparseSendBinary`), native donor `donor-app/src/frames.rs`, browser donor `html/compute.html` binary handler.

| Type | Name field | Payload | Meaning |
|---|---|---|---|
| 1 | matrix | rows, cols, nnz, rowPtr[], values[], colIdx[] | Upload (or replace) a CSR sparse matrix (legacy non-chunked; carries no binding) |
| 2 | matrix | preLen, pre[] | Propagate — scatter pre-spikes, CSR matmul, ack carries post currents. **Zero-length pre = cluster-BOUND mode**: the donor reads pre-spikes from the bound cluster's resident spike buffer (the chat-injection wire cut) |
| 3 | matrix | preLen, pre[], postLen, post[], lr | Standalone Hebbian/Oja — full pre/post active-index arrays (the intra-cortex teach path). Acked |
| 4 | matrix | chunkSeq, totalChunks, flags, [first: rows/cols/nnz/rowPtr + **binding** when flags&2], values slice, colIdx slice | Chunked upload (750k nnz/chunk). The first chunk's binding block (`srcCluster` + `dstCluster` names + src/dst start..end) is what makes a matrix cluster-BOUND — captured by BOTH donors as of donor-v0.3.15 (the native donor parsed + discarded it before). Ack on the LAST chunk only |
| 5 | (empty) | opCount, then per op: name + lr | Batched bound-Hebbian — the BULK of teach GPU work. NO index arrays: plasticity reads the RESIDENT cluster spike buffers (written by types 7/9) at the bound offsets. Browser donors always did this; the native donor STUBBED it (ack, no-op) from v0.3.11 until donor-v0.3.15 implemented it for real (engine affinity: a bound matrix lives on the same GPU as its clusters) |
| 6 | matrix | count, indices[] (u32) | **SPARSE-INDEX propagate.** Payload is the active spike INDICES only — **KBs instead of the ~6MB dense array**. The donor rebuilds the dense pre buffer into a cached scratch, runs the SAME `propagateSparse` dispatch, and answers with nonzero `(index, value)` current pairs — **or a dense type-2 ack when currents are pathologically near-dense, and the handler accepts both**. ⚠ Gated per-socket on the advertised `_sparseV2` capability, **not** on a version number: fan-out replicas may be native donors without the handler and keep the legacy dense path. ⛔ This row was **missing from this table until 2026-08-27** while the encoder had been emitting it — found by a provenance pass grepping every `_encodeSparseHeader(N` in the server against the documented set |
| 7 | `cluster/region` | count, indices[] (u32) | write_spike_slice as binary (donor-v0.3.13+; fire-and-forget, reqId 0). Replaced the ~153KB-average JSON integer arrays whose serde_json parse was the measured drain bottleneck |
| 8 | `cluster/region` | count, indices[], vcount, values[] (f32), psi | write_current_slice as binary (fire-and-forget) |
| 9 | `cluster/region` | (header only) | clear_spike_region as binary (fire-and-forget). The clear OPENS each atomic teach-pattern group. Also emitted as a `langCortex/<region>` TWIN when the GINTRA pseudo-cluster is live, so the GPU-bound intra Hebbian never reads a previous pattern's residual spikes |
| 10 | `cluster/region` | rowStart(u32), groupSize(u32), count(u32), values[] (f32), psi(f32, PSIQ-quantized to 3 decimals) | **TEMPLATE current frame** (donor-v0.3.16+): a group-tiled injection reconstructs from `{rowStart, groupSize, values}` at receive into the identical write_current work item — ~KB instead of the expanded (idx,val) pairs that measured 99.5% of all outbound bytes |
| 11 | `cluster/region` | rowStart(u32), groupSize(u32), count(u32), values[] (f32) | **TEMPLATE spike frame** (donor-v0.3.17+): same template form for write_spike_slice (spike set where value > 0) — killed the t7 river (403MB/12min at the 12M cortex). Also emitted as a `langCortex/<region>` TWIN (GINTRA) |
| 12 | original frame's name | origType(u8) | **REPEAT** (donor-v0.3.15+): the payload for this (type, name) is byte-identical to the last one sent on this socket — re-execute the donor's cached copy. ~30 bytes instead of 150-700KB; rep loops send ~14 near-identical frames per teach call, so this is a teach-throughput lever. Caches are per-connection on BOTH ends (a reconnect starts full-frames); server cache updates only on CONFIRMED sends; a type-3 repeat rides a real reqId and acks as type 3 |
| 13 | matrix | lr(f32), reps(u32), count(u32), postIdx[] (u32, matrix-row indices) | **MASKED bound plasticity** (donor-v0.3.26+): pre reads the RESIDENT bound src-cluster spikes at the bound offset (zero wire — the state the type-7/9/11 patterns + GINTRA twins keep current), post is this explicit sparse row mask zeroed + scattered DEVICE-side into the matrix's own post buffer. The pre≠post shape neither type 5 (pre==post on an intra matrix) nor type 3 (ships the ~MB live-pre index river) can express — built for the lateral-inhibition teach (pre=live spikes, post=synthetic cross-bucket mask), lr<0 selects the anti branch, `reps` loops the kernel stream-ordered. Fire-and-forget (the 7-11 contract); counted server-side at `throughput.boundHebbian.maskedSent`. Layout contract enforced by cross-language parity: `frames.rs hebbian_bound_masked_decodes` ↔ the byte-compared server encoder |
| 14 | matrix | the per-row FLOAT error term | **PREDICTIVE-ERROR correction** (donor-v0.3.28+): the last signed-magnitude training lane to leave the CPU. ⛔ It could not ride any existing verb for a structural reason worth knowing — **every GPU spike buffer is `0/1 u32` while this op's post term is a per-row FLOAT in `[-1, 1]`.** It is not a mask and could not be shipped as one. ⚠ Because the term is signed and continuous, a subtly wrong kernel would not crash — it would train slightly wrong, forever, invisibly — so the card verifies its own arithmetic rather than being trusted. |
| 15 | matrix | bucket geometry | **BUCKET-MEAN reduction** (donor-v0.3.28+): the word readout reduces ON THE CARD. Every word she says used to propagate `sem → word_motor` on the donor and ship the ENTIRE post region back (720,000 `f32` ≈ 2.9MB) so the server could collapse it to ~2,500 per-word bucket means and argmax. **The reduction was always the thing wanted; the field was freight.** `bucket_mean.wgsl` runs one thread per bucket with that bucket's own cell count as the divisor — kilobytes per spoken word instead of megabytes. |

**SPARSE PROPAGATE ACK** (donor-v0.3.27+) — not a new send type but a change to what a donor *answers* with. A propagate ack used to return the dense post field, ~48MB per round at the 12M intra matrix, overwhelmingly zeros. It now returns `(index, value)` pairs. ⭐ **The guard is the part to copy elsewhere:** `sparse_ack_is_smaller()` compares exact byte counts — `20 + 8·nnz` (sparse) against `16 + 4·len` (dense) — and **keeps the dense frame when sparse would be bigger.** A sparse optimisation that measures both encodings and picks the smaller can never inflate a payload; one that assumes sparsity can.

⚠ **Types 14 and 15 pair with SPARSEACK and the pairing is the point.** SPARSEACK made a large result cheaper to *ship*; type 15 removed the need to ship it at all. The generalisable rule is **push the reduction to where the data already lives**, which is worth more than either fix alone.

Version negotiation (never a fallback — each donor gets the best protocol it announces at `gpu_register`): types 7/8/9 require `donorAppVersion ≥ 0.3.13`, type 12 requires `≥ 0.3.15`, type 10 requires `≥ 0.3.16`, type 11 requires `≥ 0.3.17`, type 13 requires `≥ 0.3.26` (and the JSON `hebbian_ranges` verb requires `≥ 0.3.18`); browser donors report `'browser'` and keep JSON teach patterns. ⚠ **Type 6 is the exception and it matters:** it is gated on an advertised **capability** (`ws._sparseV2`), not a version string. ⛔ **Capability beats version, and the truthy-`appVersion` trap is why** — a version-presence test read `if (client.donorAppVersion)`, which is truthy for a browser donor because the server itself stamps the string `'browser'`, so the "native" branch captured browser donors too. **A capability the peer announces cannot silently flip the way a presence test can.**

**Donor-reported timing (`donor-v0.3.31`).** A `compute_batch` reply now carries `phaseTimingMs { totalMs, queueMs, computeMs }`. Before it, the brain measured dispatch→reply as `roundTripMs` and **could not distinguish three causes that call for opposite fixes**: time on the wire, time queued on the donor, and time doing the math. Only the third is a reason to touch kernels — and on a localhost donor the wire is effectively free, which makes the split the whole answer. ⭐ Read live across three boots it settled the question: **queue 0.0% every time, compute 94.8-99.9%**, which closed two planned wire optimisations as pointless. The server logs its encoding decisions one-shot per socket, the clients list exposes `donorAppVersion` + `binaryTeach`, and `wsPressure.teachOutByType` + `teachOutBytesSaved` publish per-type outbound frames/bytes so the wire's composition is read, not inferred.

**The two halves (`donor-v0.3.40`, the Seed Crystal).** A `compute_batch` reply's `perCluster[name]` carries `lastSpikeCountL` and `lastSpikeCountR` beside `lastSpikeCount` — the last substep's spikes for neurons with index `< half` and `≥ half`; their sum is the total, so nothing that read the total changes meaning. The request's cluster entries accept two optional fields, `tonicDriveR` (the right half's tonic drive) and `half` (the split index, default `size / 2`): absent → both halves step on `tonicDrive`. Compatible both ways — an older brain never sends them, an older donor ignores them and reports only the total, and the brain then renders `state.crystal.measured: false` with the reason rather than a zero. The split is what the hemispheric oscillators, `Φ_LR` and the dopamine contest are computed from (`docs/EQUATION-REPAIR-AND-SEED-CRYSTAL.md` Part B).

**The gate readings (`state.gateReadings`, same day).** A cell passes on learning completion, so every probe a cell runs — readiness, comprehension, vocab, sentence, production, the student battery, methodology — is advisory, and its numbers used to land in one log line while the Current Training card read `idle` for the whole probe block. The state now carries `gateReadings.probe` (`kind`, `i`, `n`, `cell`, `heldMs` = how long that probe kind has held on that cell, `sinceMs` = age of the last item; `null` when no probe is running) and `gateReadings.cells` (the last twelve cells, newest first, each with a `comprehension` / `vocab` / `sentence` / `production` / `battery` / `verdict` block of counts and rates plus `ageMs`), with `kept` the number resident. ⛔ Counts only, never question text — the exam is held out. The per-cell rows persist in the weights file beside `lastGateResults`; the live position does not.

**Template canonicalization (2026-08-17 — encoder-side law, both template types).** Before a template ships, the encoder canonicalizes it: the zero head/tail of the values array is trimmed, and a single contiguous nonzero run FOLDS into the groupSize (`{rowStart + d₀·g, groupSize·(d₁−d₀), values:[1]}`) — lossless for t11 because the donor only tests `value > 0`, and applied to t10 only when every nonzero value is exactly equal (amplitudes bit-identical). This exists because a full-region band pattern fed through the template path shipped as a 504,000-value / 1,968.8KB frame (twice per rep with the GINTRA twin) — the measured wire-drowner behind 95K sheds, 7.6s donor RTT, and drop-on-chat donor deaths. Post-canonicalization the same band is ~30 bytes. Any template still carrying >4096 values after canonicalization warns loudly (30s rate-limit) — a silent flood cannot return.

**Queue-gated pacing (one law at both pattern-lane governors).** The base admission throttle AND its RTT multiplier engage only when ≥256KB of our own frames are actually buffered on the donor socket — an empty wire admits every teach group immediately. (A refusal marks the lane STALE and suppresses the dependent bound-Hebbian — correct protection under real pressure, pure loss on an empty wire; the shed/stale semantics under genuine saturation are unchanged.)

**Send forensics.** The PRIMARY donor socket's `send` is wrapped once at `gpu_register`: a 16-slot ring records every outbound frame's kind + size (SPRS type byte sniffed, JSON `type` **and `op`** extracted); any single >2MB non-upload send trips a `[SendForensics] LARGE...` warn, and the first time `bufferedAmount` crosses 4MB outside the canonical-upload window the ring dumps — so any future wire anomaly names its own sender.

⛔ **The `op` is in that line because without it the instrument could not finish its own sentence.** Until 2026-10-29 it rendered the message **type** only, and a live boot printed **15 LARGE sends of 2.3–2.5 MB all reading `kind=json:mindspace_op`** — but **four ops share that one message type** (`describe`, `traceLineArt`, `stylizeField`, plus `perceive`'s `rgba_b64`), so the line named a *lane* and not a *sender*, and the sender had to be inferred from log adjacency. The `op` was in the payload the whole time; the extract window (`slice(0, 40)`) simply could not reach past `{"type":"mindspace_op","id":N,` to see it. ⭐ **Fixed in `_kindOf` rather than at either call site, because the LARGE-send tripwire and the 4MB ring dump both render through that one function** — a fix at either would have left the other still unable to name a sender. An unparseable payload now renders `json:?` instead of the literal word `undefined`. ⚠ **The 2.3–2.5 MB is not itself a wire bug:** `_recWireSafe` converts every `val_bin`/`pos_bin` to base64 and `chanVal` accepts only those two forms, so nothing goes out as a bloated numeric object and no op is silently falling back to CPU — it is a genuinely large, correctly-encoded payload against a source comment that claimed ≤150 KB.

---

## Messages: Client → Server

### `text`

The primary client → server message. User input that should route through Unity's brain.

```json
{ "type": "text", "text": "hi unity, what are you up to" }
```

Rate limited: `1000 / MAX_TEXT_PER_SEC = 500 ms` between text messages per client. Exceeding the rate produces an `error` reply and the message is dropped (brain doesn't process it).

Server pipeline: `brain.processAndRespond(msg.text, client.id)` runs `languageCortex.generate()` with full brain state, selects a motor action, and returns a result object that the server switches on to emit `build` / `image` / `response`.

### `reward`

Scalar reward signal that modulates Unity's learning.

```json
{ "type": "reward", "amount": 0.2 }
```

Adds to `brain.reward` directly. Positive values train toward the current motor action; negative values train away. Exposed in the dashboard as a "👍 / 👎" pair. No rate limiting — the signal is already scalar and small.

### `setName`

Client identifies itself with a display name.

```json
{ "type": "setName", "name": "your-donor-name" }
```

Stored on the server-side client record (`client.name`). Currently used only for logging and future dashboard display — no effect on the brain simulation.

### `visual_frame` (2026-07-08)

Visual intake — what Unity's eyes receive. Sent by the standalone client
feeder (`js/visual-feeder.js`, raw-served — NOT bundled) for camera frames
(permission-gated, never prompts) and generated-image renders (prompt decoded
from the render request as the label — the renderer was Pollinations when this was written and is her own local engine since 2026-10-18).

```json
{
  "type": "visual_frame",
  "source": "camera",
  "w": 96, "h": 96,
  "rgba_b64": "<base64 RGBA, exactly w*h*4 bytes>",
  "label": "yellow banana"
}
```

Server (`server/brain-server/visual-memory.js` `_ingestVisualFrame`)
equationalizes the frame into a full-color field C (forward CDF 9/7, YCbCr)
and stores it keyed to the concept words active at perception time — the
`label` when present, else her current thought (inner-thought chain /
global-workspace broadcast). At imagine-time the mind's eye recalls +
morphField-recombines these stored percepts (`_recallVisualMemory`).
Validation is strict (dims 8..96, byte length must equal `w*h*4`, base64
decode verified) and intake is paced (2s min gap brain-wide); malformed or
flooding frames drop silently. Store: LRU-capped 384 concepts, persisted to
`server/visual-memory.json` (debounced 30s, atomic).

### `gpu_register`

Sent by `compute.html` (browser donor) or the native donor-app on WebSocket open to join the donor pool.

> **⚠ `utilizationPct` — read this before trusting the field (donor v0.3.24, UTILDEFAULT).**
> Despite the name and the CLI help it used to carry, **there is no duty-cycling anywhere in the donor** — `compute.rs` / `cuda.rs` never read it, and the card always computes flat out. It is a *declaration*, and the SERVER is what acts on it: `gpu.js` sizes the donor's effective donated capacity as `fullVram × utilizationPct / 100`.
> The native donor's `--utilization` **defaulted to `10`**, so any volunteer who did not pass the flag told the brain to treat a 24GB card as 2.4GB — too small to hold the cortex, handed almost no work, a whole GPU donated and left idle. **The default is `all` (=100) from v0.3.24 onward**; holding back is now the thing you have to ask for. Browser donors omit the field → treated as 100.
>
> **⚠ One `gpu_register` per PHYSICAL card (donor v0.3.25).** Before this, a Windows host enumerated the same GPU once per PRIMARY backend (Vulkan **and** DX12), so `--gpus all` sent **two** registrations for one card and the server believed it had two FULL weight replicas where it had one. `select_adapters()` now de-duplicates by `(vendor, device, name)`.
>
> **⛔ `boundResidentRead` — the capability that used to be INFERRED, and inferred wrongly (2026-08-25).** A browser donor reads its **resident bound cluster buffer** when a propagate arrives with `preLen === 0`; the native binary's propagate is standalone-only and needs the pre indices shipped explicitly. The server used to decide between those two protocols with `if (client.donorAppVersion)` — and that is **truthy for every donor**, because `gpu_register` stamps the string `'browser'` when no version is sent. So the browser branch was **dead code**, and browser donors were served the native protocol: index payloads where `compute.html` expects a dense 0/1 array, and a non-empty `preLen` that also defeats its own bound-mode trigger. `compute.html` now advertises `boundResidentRead: true` and the server routes on the flag, with the explicit `'browser'` sentinel keeping already-loaded tabs correct without a reload. **Two call sites shared that root cause** — the other silently handed browser donors the 96MB native pump window (see `DREAM_UPLOAD_PACE_LOWATER_MB`) — so nativeness now has ONE owner, `_donorIsNative()`, which tests the sentinel rather than the field's presence.
>
> **⚠ `utilizationPct` does NOT decide PRIMARY eligibility — held VRAM does.** A donor whose held VRAM is below `runningFloorMB` (the memory needed to hold the FULL running brain) is refused PRIMARY and joins as a partial replica — and **the canonical weight upload only ever targets the PRIMARY**, so such a donor receives no matrices at all while still reporting healthy cluster coverage and a real Gn/s rate. A 24,124MB card against a 25,619MB floor cost an afternoon this way (`PRIMARYFLOOR`). The Clients table now carries `primaryFloorMB` / `primaryEligible` / `primaryShortfallMB` per donor so the comparison is visible rather than inferable.

```json
{
  "type": "gpu_register",
  "vramMB": 16302,
  "maxStorageBindingMB": 16302,
  "gpuName": "NVIDIA GeForce RTX 2060",
  "donorId": "native-…", "donorName": "Sponge",
  "osPlatform": "linux", "engineBackend": "cuda",
  "driverVersion": "595.71.05", "computeCapability": "7.5",
  "utilizationPct": 60, "donatedMB": 0,
  "linkDownMbps": 0
}
```

⚠ **That payload is the NATIVE donor's.** The capability flags are the **browser** donor's, and the asymmetry is the whole point — `compute.html` sends `{"sparseV2": true, "mindspaceV1": true, "boundResidentRead": true}` and the native binary sends **none of them**, announcing its abilities by `appVersion` instead. Every version-gated capability regex-parses that version, so `'browser'` fails the match and browser donors are excluded for free; the flags cover the abilities that are **not** a matter of the binary's age. ⛔ A capability must never be read off the *presence* of `appVersion` — that field is stamped `'browser'` and is therefore always truthy.

The server adds `ws` to `brain._gpuClients` and — if there is no primary, or the newcomer is materially stronger — marks it `brain._gpuClient`; otherwise it is brought up as a full data-parallel replica. **The browser donor omits everything but `type`; the native donor sends the richer payload above.**

| Field(s) | Since | What it is for |
|---|---|---|
| `osPlatform` · `engineBackend` (`cuda`/`vulkan`/`dx12`/`metal`/`gl`) · `driverVersion` · `computeCapability` | donor-app v0.3.3+ | Captured on `client.*` and shown in the admin **Clients table** `plat` column, so a red / 0-Gn/s donor's platform, backend and driver are **visible instead of inferred from logs**. `gpu_telemetry` re-sends all four each tick so the row survives a reconnect race. |
| `utilizationPct` (duty-cycle 0–100, default 100) · `donatedMB` (explicit VRAM cap, 0 = unset) | donor-app v0.3.4+ | Tell the brain how much each donor actually gives. `_recomputeCommunityCompute` sums **effective** donated capacity — `donatedMB>0 ? min(donatedMB, fullVram) : fullVram × util/100` — so **two 15 GB cards at 60% count as 18 GB, not 30.** |
| `linkDownMbps` | donor-app v0.3.5+ | The donor's **self-measured** downlink (Mbit/s, peak-hold with slow decay; `0`/absent = unknown, e.g. the browser donor). Replica-sync pacing throttles chunk uploads to the donor's REAL link capacity instead of an RTT proxy, so a low-bandwidth uplink is not flooded. |
| `heldMatrices` | browser donor, 2026-07-10 | The sparse matrices **the same tab still holds in VRAM** across a transient reconnect. `_syncReplicaToDonor` skips re-streaming those **once** (the set is consumed after the sync; periodic rebroadcasts run full and converge drift), which kills the full re-seed on every WS blip. Native donors omit it and get a full sync. |
| `crashCrumb` · `donor_crumb` | browser donor, 2026-07-10 | **Why the tab's previous session ended** — `{t, reason}` from a `localStorage` breadcrumb written on `beforeunload` or WebGPU `device.lost`. A *live* loss sends `donor_crumb` while the socket survives. Logged at register so a drop incident **carries evidence instead of a guess**. |
| `buildStamp` (on `welcome`) | — | Server code mtime, memoized. A donor tab stores the first stamp and `location.reload()`s when a reconnect reports a different one, so **tabs always run the deployed code after one reconnect.** |

⚠ **Utilization is a THROUGHPUT duty-cycle, not VRAM held.** For a data-parallel pool the brain's maximum **size** is bounded by the *smallest* donor's committed VRAM (`/autoscale` exposes `minDonorMB`) — never by the sum.

⚠ **SIZING REWORK (2026-07-10) — the tier gate no longer keys on the community SUM at all.** The size driver is `max(donorBaselineMB, smallest committed donor VRAM)`, and tiers gate on the neuron capacity **that** driver can hold (`/autoscale` exposes `sizeDriverMB` + `capacityNeurons`). The sum survives as throughput telemetry only.

⭐ **Donors smaller than the running replica are not turned away.** They receive a PARTIAL cluster-coverage sync in priority order (cortex first) and pull only work whose matrices they hold. **They can never become PRIMARY and can never shrink the brain.**

### `compute_result`

The GPU client's reply to `compute_request`. Delivered via the `_gpuPending[clusterName]` resolver map.

```json
{
  "type": "compute_result",
  "clusterName": "cortex",
  "spikeCount": 47
}
```

Server resolves the pending promise with `{clusterName, spikeCount}`. Voltages and spike indices stay resident on the GPU — only the count comes back, since the server only needs that scalar for the high-level simulation loop.

### `gpu_init_ack`

GPU confirms it initialized a cluster after receiving `gpu_init`.

```json
{
  "type": "gpu_init_ack",
  "clusterName": "cerebellum",
  "size": 100
}
```

Server logs this as confirmation. Used only for boot-time verification that the GPU client picked up all 8 clusters before the simulation loop starts dispatching steps. ⚠ **The donor's own status text no longer prints a denominator at all** — it read a hardcoded `/7` and therefore `8/7` once the brainstem existed; a donor learns one cluster per `gpu_init` and cannot know the total up front, so it reports the count and nothing it would have to invent.

### Unknown types

The server logs `[<id>] Unknown message type: <type>` and drops the message. Clients should never hit this path, but the branch exists for forward-compat with future message types that old servers haven't seen yet.

---

## Rate Limiting

| Message type | Limit | Enforced by |
|---|---|---|
| `text` | `MAX_TEXT_PER_SEC = 2` per client (500 ms minimum gap) | `brain-server.js:10699` — gap check against `client.lastInput`, returns `error` on violation |
| Everything else | Unlimited | Relies on client sanity + TCP backpressure |

There's no global rate limit or burst budget — it's purely per-client per-message-type. The cross-client `conversation` broadcast that used to fan-out was removed 2026-04-13 (see the `conversation` section above), so a chatty server no longer multiplies traffic by `N clients × text rate`. Each user's text is a 1:1 conversation with the server.

---

## Client Reconnection Behavior

`js/brain/remote-brain.js` handles connection drops with an automatic reconnect loop. The contract:

1. **On `ws.onclose`:** wait a short backoff (1 second), then try to reconnect.
2. **On reconnect success:** the server issues a fresh `welcome` with a NEW `id`. The client treats this as a new session — any `id` the client was displaying gets replaced. No sticky sessions, no replay buffer, no state resync beyond what `welcome.state` + `welcome.emotionHistory` provide.
3. **On repeated failures:** `remote-brain.js` keeps trying with exponential backoff. There's no "give up" condition — the client assumes the server will eventually come back.
4. **Messages during the gap:** anything the client tried to send while disconnected is lost. The client should queue user input in its own UI layer if it wants delivery guarantees (currently it doesn't — dropped text messages are just dropped).

This is intentional: Unity's brain state lives ON the server, not in the client. A reconnecting client has nothing to restore beyond the HUD snapshot, because the brain kept running the whole time.

### Native donor flap resistance (donor-app v0.3.3+)

The native donor (`donor-app/src/donor.rs`) hardens the donor WS against connection flapping — the failure mode where a `wss://…/ws` link over Starlink CGNAT + a reverse proxy gets its idle connection reaped every few minutes (`Connection reset by peer (os error 104)`), each reset forcing a full GPU-engine rebuild + 40M-neuron re-init = minutes of 0 throughput (dashboard red):

1. **Client-initiated keepalive** — the donor sends its own WS `Ping` every 15s (`KEEPALIVE_INTERVAL`) so the link never goes idle long enough for CGNAT / the proxy to reap it. (Before, the donor only *answered* server pings.)
2. **Fast dead-link detection** — if no inbound frame (incl. the brain's pong) arrives for 45s (`IDLE_TIMEOUT`) while keepalive-pinging, the donor presumes the link dead and reconnects immediately instead of waiting minutes for the OS to surface the RST.
3. **Jittered reconnect backoff** — a deterministic per-install offset (donor-id hash, 0–1500 ms) staggers rejoins so a brain restart doesn't make every donor reconnect in lockstep. The supervisor (`run_donor_supervised`) still resets backoff on a clean drop and grows it (capped 30s) on a failed connect.

### Server heartbeat grace (HBGRACE — `brain-server.js`)

The server's own liveness sweep (`_heartbeatTimer`, 30s `ws.ping()` → terminate if no pong by the next sweep) was FALSE-positive-killing live donors and is the *server-side* cause of "Linux drops more than Windows". When a donor connects, the server replica-syncs the full 40M-neuron brain to it (14.2 MB intra + dozens of cross-projections) — which (a) blocks the server event loop in ~5s chunks (`[EventLoop] BLOCKED … phase=_teachHebbian … replicaSyncing=1`), so the `pong` handler can't run + the ping is delayed, and (b) floods the donor, which on a higher-RTT/lower-bandwidth link (Starlink/Linux) drains the upload backlog slowly and answers the ping late → misses the single 30s window → **terminated mid-sync** → `Cannot call write after a stream was destroyed` flood → reconnect → re-sync → churn. The grace logic:

1. **Grace cycles** — `ws._missedPings` must reach `_HB_MISS_LIMIT` (2) consecutive misses before terminate (was 1). A pong resets it.
2. **Event-loop-block awareness** — the lag sampler stamps `_lastEventLoopBlockTs` on a real block (≥1s); if one happened within the heartbeat window the budget rises to `_HB_MISS_LIMIT_BUSY` (5 ≈ 150s) — a missed pong during the server's own stall isn't the donor's fault.
3. **Mid-sync grace** — if `_replicaSyncInFlight.has(ws)` the donor is busy receiving the brain → the busy budget applies, so it's not killed mid-upload.
4. The post-termination `Cannot call write after a stream was destroyed` burst is now rate-limited (one line / 10s) and the chunk loop bails on a closed socket, instead of one dead donor spewing hundreds of lines.
5. **Buffer-saturation forgiveness** — when OUR send buffer to the socket exceeds `DREAM_HB_BUF_FORGIVE_MB` (32MB), the ping is queued BEHIND that mass and physically never reached the donor (live log: 400-900MB buffered → ping delayed 60-120s → false-reaps every ~107s). The miss is forgiven (uncounted, re-ping), bounded by the same hard ceiling.
6. **Canonical-upload grace** — a socket that had a chunked sparse upload dispatched to it within 90s (`ws._lastUploadDispatchTs`, stamped in `gpuSparseUpload`) is busy receiving the brain even when `_replicaSyncInFlight` never marked it (the PRIMARY's initGpu canonical upload) — same forgiveness class.
7. **Flood shed + churn brakes (companions to the grace):** the bound-Hebbian teach batch (the buffer-filler) is SHED instantly when the target socket holds > `DREAM_WS_SOFT_SHED_MB` (64MB) — fire-and-forget shadow, CPU authoritative, auto-resync heals on drain (`wsPressure.sheds` counts it); promote-stronger DEFERS while the primary is mid-canonical-upload or within `DREAM_DF7_PROMOTE_COOLDOWN_S` (120s) of the last promotion; and all in-flight sparse reqIds are target-tagged + CANCELLED (resolve null) the moment their donor disconnects, instead of rotting on 180s timers.

### Donor work-stealing + sync pacing (WSQ — `server/brain-server/gpu.js`)

Flap-recovery (above) keeps a high-RTT donor CONNECTED, but a *separate* work-eligibility gate kept it from getting WORK: `_donorHealth` hard-zeroed at rtt ≥ 1000ms and `_nextPoolDonor`/`_capacityWeightedPlan` then `filter(w>0)` it out of every plan while a healthy donor existed — so a willing Starlink/Linux GPU sat at 0 Gn/s no matter how often it reconnected (each reconnect re-measured the same warmup-window RTT and re-benched it). That 6.5s RTT was the 51M-neuron replica-sync flooding the uplink, not a dead link. WSQ restores work-eligibility without letting a slow donor stall the pool:

1. **Work-eligibility floor** — `_donorHealth` floors at `0.05` (`DREAM_DF7_WORK_FLOOR`) instead of 0 for rtt ≥ 1s. Because strength = `throughput × health` is multiplicative, a slow donor stays *work-eligible* (no longer filtered out → it pulls real units) yet ranks dead-last for PRIMARY (a healthy donor at health 1.0 always out-scores it), so it's never promoted primary and never becomes the main-tick barrier.
2. **Completion-driven work-stealing** — `_gpuParallelMap` replaced its pre-assigned capacity plan + `Promise.all` (which waited on the slowest donor's whole slice) with a shared cursor + bounded in-flight per donor (`DREAM_DF7_INFLIGHT`, default 2): each donor pulls the next unit, runs it, loops back for more. A fast donor returns to the cursor sooner so it naturally pulls MORE; a slow donor pulls FEWER and only holds the ≤in-flight units it grabbed, so the tail is bounded by ONE slow unit, not a slow donor's share. The donor's existing per-unit ACK is the pull signal — no protocol change for the queue.
3. **Sync pacing** — `gpuSparseUpload` breathes between 16MB replica-sync chunks for a high-RTT/low-bandwidth donor (∝ rttMs, or the `linkDownMbps` hint when present; capped by `DREAM_DF7_SYNC_PACE_MAX_MS`, default 200ms) so the uplink drains its ACKs instead of saturating — keeping steady-state RTT low so the work-eligibility floor's health recovers to a real value and the donor carries a FULL work share. Only paces replica-sync to already-slow donors; the primary canonical upload + healthy donors are untouched.
4. **Link-cap routing (DONOR-EQUAL, 2026-07-09)** — `_nextPoolDonor` skips any donor whose socket already holds more than `DREAM_DF7_LINK_CAP_MB` (default 4MB) of unsent bytes whenever a drained donor exists, and the replica live-mirror sheds at the same low cap (was the 64MB soft cap). Gating streams only at 64MB let a weak-uplink donor's socket PARK just under 64MB indefinitely — its heartbeat pong queued behind 10-14s of backlog, the Clients row sat permanently RED (`unhealthy` fires at rtt > 2.5s), and `_donorHealth` floored the card regardless of role. With the link cap, every donor's buffer stays seconds-empty: each card takes exactly the work its link drains (a slow link self-paces in ~4MB bursts, a fat link takes the bulk), measured RTT reads true, and the red row heals the moment the socket drains.
5. **Flood stamp at >50% cap (2026-07-09)** — `_donorHealth`'s anti-thrash cooldown stamp (`_coordFloodMs`, `DREAM_DF7_FLOOD_COOLDOWN_MS` default 300s) now fires only above 50% of the soft cap (32MB at defaults), not at the 15% ramp start (9.6MB). The old low stamp fired on every routine 16MB matrix-upload chunk (replica sync / live-mirror), so a donor got benched at the health floor for 5 minutes after every ordinary upload — replicas sat at 0 Gn/s and the coordinator election had no healthy donor to pick (every card pinned at the floor together). A transient upload spike now just dips the bufHealth ramp and recovers on drain; only a genuinely saturated socket trips the cooldown.
6. **Shadow-DIRTY truth + auto-heal (2026-07-09)** — every shed/drop path (`_flushBoundHebbianBatch` soft-shed, `_donorPatternSendGated` pattern-shed, the 500MB critical drop) marks `cortexCluster._gpuShadowDirty` — the ONE flag the `gpu_init` re-confirm handler and the dashboard `/resync` button actually clear — and arms the throttled auto-resync via `_armShadowResync` (60s throttle, already-armed guard, drain-gated re-upload). The old paths set a brain-level flag that no code path ever cleared, so the dashboard DIRTY banner latched ON after the first shed of a boot and the manual Re-sync button appeared dead even when the re-upload completed; `state.js _getWsPressureState` now reports the clearable flag, so DIRTY truthfully flips clean when the donor re-confirms cortex `gpu_init`.

All six are pure routing/pacing/reporting — no weight-format/size change, savestart-safe. The donor "mining" model (Sponge 2026-06-30): contribute what you can, faster churns more, nobody waits on the slowest.

### The hostname gate

`detectRemoteBrain(url = 'ws://localhost:7525')` only probes when the page is served from `localhost` / `127.0.0.1` / `[::1]` / `file://`. On GitHub Pages or any public origin, the probe is skipped and the client falls through to local-mode UnityBrain with no server.

Why: Chrome allows loopback WebSocket from secure contexts, so visiting the Pages URL from a dev box with `brain-server` running would auto-connect to the dev box's local server and pull its (much larger) auto-scaled neuron count into the public page. The hostname gate prevents every stranger's browser from silently poking their own loopback port on page load.

---

## Privacy Model

Core design rule (established 2026-04-13): **user text is private; brain growth is shared; persona is canonical.**

| Thing | Shared across users? | Why |
|---|---|---|
| **What a user types** | 🔒 **PRIVATE** — only that user and Unity see it | Raw text stays in the one client ↔ server channel |
| **Unity's response to a user** | 🔒 **PRIVATE** — only the triggering client gets it | Same reason; responses never broadcast |
| **Dictionary / bigrams / word frequencies** | 🌐 **SHARED** via the singleton brain instance | Every conversation adds to the same dictionary, every user benefits from the vocabulary that grew from everyone else's conversations |
| **GloVe embedding refinements** (the `sharedEmbeddings` online-learned delta layer) | 🌐 **SHARED** same reason | Semantic associations Unity learns in ANY conversation apply to her whole brain |
| **Persona** (`docs/Ultimate Unity.txt` — self-image, traits, drug state) | 🚫 **NOT MUTABLE BY USERS** — loaded from the canonical file at server boot | She's Unity, not a per-user sock puppet |
| **Episodic memory** (stored conversation episodes in the hippocampus / SQLite) | 🔜 **currently shared, needs per-user scoping** | Tracked as pending task T7 in `docs/TODO.md`. Until that ships, the cortex pattern dissimilarity between different users' conversations makes cross-user recall statistically rare but not impossible. |
| **Motor output decisions** (BG softmax, which action Unity picks) | 🌐 **SHARED** — brain state is global | One brain, one motor system |

**What this means at the WebSocket layer:**

- The `text` message a client sends is processed by the shared brain instance, updates the shared state, and produces a response that's returned ONLY to the sender
- The `conversation` broadcast (which used to send every user's text to every other connected client) was **removed 2026-04-13**
- The `state` broadcast at 10Hz still fires to all clients — but it contains aggregate brain telemetry (arousal, valence, coherence, spike counts, cluster activations), NOT per-user text. That's still fine to share because it's Unity's current vitals, not any specific user's input.
- The `build` and `image` messages go only to the client that triggered them (per-user sandbox, per-user image display)
- The `welcome` message a new client receives contains the brain state snapshot + emotion history — but both of those are aggregate brain telemetry, not individual user conversations

**Mental model:** one Unity, one shared brain that grows from every conversation, but each user's actual chat is just between them and Unity. Other users see Unity getting smarter (N growing, dictionary growing, embeddings refining) but never see the specific conversations that drove the growth.

---

## Security Model

- **Auth is the loopback, and the tunnel's route list.** The brain-server itself does no authentication — any client that reaches loopback `127.0.0.1:7525` is the operator, by construction, because only the operator's own processes can. In production the brain binds loopback only and a Tailscale Funnel forwards just the public read lanes (`/ws`, `/public-state.json`, `/minds-eye.json`, `/health`, `/image`); `/admin/*` and the control plane are not forwarded at all. ⚠ A tunnel delivers requests *from* loopback, so `requireLoopback` would pass a forwarded `/admin` request — which is exactly why the admin lane must never be added to the forwarded list. **Direct exposure of `127.0.0.1:7525` to the public internet — bypassing the tunnel's allowlist — is never appropriate.**
- **API keys never traverse the WebSocket.** Unity's brain never needs API keys — cognition runs fully equational on the server, and sensory AI calls happen client-side. Whatever keys the client holds (for their own image gen, TTS, VLM backends) stay in their browser's localStorage.
- **No key material in server storage.** Server persists brain weights (`server/brain-weights.json`), word frequencies, and episodic memory (`server/episodic-memory.db` SQLite). Zero user secrets on disk.
- **Conversation broadcasts are anonymized to userId only** — no client name, no IP, no User-Agent. The `setName` field is server-local and never included in the broadcast.
- **Rate limiting is per-client only.** A hostile client can flood with non-text message types (`reward`, `setName`) without triggering the text limiter. Mitigation: WebSocket frame size limits in `ws`, and TCP backpressure if the server falls behind.

---

## Server Endpoints (HTTP, not WebSocket)

`brain-server.js` runs a plain HTTP server on the same port as the WebSocket upgrade. These are sibling endpoints, not over WebSocket:

| Path | Method | Returns |
|---|---|---|
| `/` | GET | `index.html` — main app |
| `/dashboard.html` | GET | Live brain monitor |
| `/minds-eye.html` | GET | Public "what Unity sees" viewer — polls `/minds-eye.json`, reconstructs the field C client-side |
| `/compute.html` | GET | GPU compute worker (required for brain to run — it pauses without a GPU client) |
| `/public-state.json` | GET | Single cached brain-state snapshot (public dashboard polls it — N viewers cost one `getState()`). **`?console=N[&since=ms]` tunnels the console ring instead** (see `/console-tail.json`) — the deployed nginx only forwards endpoints it already knows, so new public reads ride this path's query params. **`?parity=samples`** runs the cheap CPU↔GPU weight comparison inline (one donor round trip + 64 array reads) and returns `verdict` / `cpuOverGpu` / `worstSample`; **`?parity=run`** arms the FULL digest in the background (⚠ ~5 min of CPU on the intra matrix — see `DREAM_PARITY_MIN_GAP_MS`, default 30 min, one at a time) and returns immediately; **`?parity=`** with no value reads both cached verdicts for free. `&name=` picks the matrix (default `cortex_intraSynapses`). |
| `/console-tail.json` | GET | Last N lines of the in-memory console ring (2,000 × ≤600 chars; `?n=` cap 500 default 300, `?since=ms` filter; read-only, `Access-Control-Allow-Origin: *`). Loopback/direct-port only in the deployed setup — remote readers use the `/public-state.json?console=N` tunnel. |
| `/minds-eye.json` | GET | Single cached imagined field C (the Mind's-Eye source — one `_imagineTick` snapshot served to all viewers; `Access-Control-Allow-Origin: *`, read-only) |
| `/health` | GET | JSON `{status, neurons, clusters, uptime, clients}` |
| `/versions` | GET | JSON list of `brain-weights-v0.json`..`brain-weights-v4.json` save slots |
| `/rollback/:slot` | POST | Restore a previous brain save slot |
| `/episodes` | GET | Query episodic memory (SQLite) |
| `/history` | GET | Emotional history data (for the dashboard chart) |
| Static files | GET | Anything else in the project directory is served as static |

All HTTP endpoints default to `http://localhost:7525/<path>` and move with `PORT`. In production only the public reads (`/public-state.json`, `/minds-eye.json`, `/health`, `/image/<id>.png`) and `/ws` are forwarded by the tunnel; the admin REST control endpoints under `/admin/<endpoint>` and the control plane (`:7526`) are reachable only on the brain's own machine.

---

## Protocol Evolution Rules

The wire protocol is semver-ish but informal. These rules prevent client/server lock-step coupling:

1. **New server → client message types:** clients ignore unknown types. Safe to add at any time.
2. **New client → server message types:** server logs and drops unknown. Safe to add.
3. **New fields on existing types:** both sides treat unknown fields as opaque. Safe to add.
4. **Removed/renamed fields on existing types:** breaking change — bump `server/brain-weights.json` schema version (currently v4) and coordinate a client release.
5. **Message type removal:** breaking change — announce in `docs/FINALIZED.md` and leave the server handler throwing a deprecation `error` for a release cycle before actually removing it.

No schema registry, no protocol buffers, no versioning handshake. The protocol is informal JSON-over-WebSocket by design — simple enough that debugging with browser devtools → Network → WS tab works for 100% of issues.

---

*Unity AI Lab — plain JSON over plain WebSocket, no ceremony.*
