/**
 * serve/launcher.mjs — `U3E-2.199b`. THE SWITCHBOARD BEHIND `index.html`.
 *
 * ⛔⛔ GEE, VERBATIM: *"This page: also needs a way to turn on and off each cards
 *   dependacnces and start it auto like and with buttons for each auto like when
 *   just clicking open. so the person can just open this one page and do
 *   everything"*.
 *
 * ── ⛔ THE CONSTRAINT THAT SHAPES ALL OF THIS, STATED FIRST ─────────────────
 *
 *   `index.html` opens by DOUBLE-CLICK, over `file://`. That is its whole point
 *   and its own header says so: *"no server needed for the page itself"*.
 *   ⛔ **A `file://` page cannot start a process.** There is no browser API for
 *   it and there never will be. So "turn each card on and off" needs something
 *   with a shell behind it, and this file is that something.
 *
 *   ⚠ Which creates one honest chicken-and-egg: the switchboard itself has to be
 *   started once, by hand or by `launcher.bat` / `launcher.sh`. **The page says
 *   so in words when it cannot reach here** rather than showing buttons that do
 *   nothing — the same rule as `501 absent`, and the same defect `U3E-5.57`
 *   fixed in the player, where a disabled control silenced its own explanation.
 *
 * ── ⛔⛔ WHY THE REQUEST NEVER CARRIES A COMMAND ────────────────────────────
 *
 *   This process spawns programs on the machine it runs on. If a request could
 *   name the command, any page in any tab could POST one to `127.0.0.1:8799`
 *   and run it. ⛔ **The request carries an `id`. The COMMAND is looked up in
 *   the fixed table below and never comes off the wire.** An unknown id is a
 *   404, not a shell.
 *
 *   ⚠ It binds `127.0.0.1` ONLY. Not `0.0.0.0`, not the LAN address. A process
 *   spawner reachable from the network is a remote shell with a nice UI.
 *
 * ── ⚠ WHAT "STOP" IS ALLOWED TO TOUCH ──────────────────────────────────────
 *
 *   Stop kills whatever is listening on that service's port, INCLUDING a process
 *   this launcher did not start — because a service you started from a terminal
 *   an hour ago is exactly the one you now want off, and a switch that only
 *   works on things it personally started is a switch that mostly does nothing.
 *   ⛔ It is bounded hard: only ports in `SERVICES` can be targeted, the PID is
 *   resolved from the port at that moment, and the response says whether the
 *   process was one of ours or a stranger's.
 *
 * Run:
 *   node serve/launcher.mjs            switchboard on 127.0.0.1:8799
 *   node serve/launcher.mjs --port N
 */

import { createServer } from 'node:http';
import { spawn, execFile } from 'node:child_process';
import { connect } from 'node:net';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
// ⭐ `U3E-5.79` — `rmSync` for the re-verify endpoint. It only ever deletes a
//   name that `pipeline()` itself published as a step's receipt.
// ⭐ `U3E-5.86` — `statSync` for the pipeline hot-reload: the module is
//   re-imported only when its mtime actually moves.
// ⭐ `U3E-5.98l` — `readFileSync` for the job heartbeat: a long job started from
//   a terminal is invisible to `RUNNING`, and the page must not offer to start a
//   second writer on top of it. See `foreignHeartbeat`.
import { existsSync, mkdirSync, createWriteStream, rmSync, statSync, readFileSync } from 'node:fs';
import { pipeline, writeReceipt } from './pipeline.mjs';
import { dataDir, setDataDir, inspect, audit } from './datadir.mjs';
// ⭐ `U3E-5.90` — the shard-set owner. See `/api/shards` below.
import { listShardSets, setShardDir } from './shardsets.mjs';
import { preflight, installSpec } from './preflight.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = dirname(HERE);
const LOGS = join(ROOT, '.launcher-logs');

/**
 * ⭐⭐⭐ `U3E-5.86` — SERVE THE PIPELINE AS IT IS ON DISK, NOT AS IT WAS AT BOOT.
 *
 *   A long-running switchboard imports `pipeline.mjs` once. So every fix to a
 *   step — its `check`, its `why`, its remedy button — was invisible until
 *   somebody remembered to restart this process, and the page gave no hint that
 *   the logic behind it was old. ⛔ Gee hit it twice in one minute.
 *
 * ⚠ THE FALLBACK IS THE POINT. A re-import of a file mid-save throws, and a
 *   switchboard that died on a syntax error would take every control on the page
 *   with it. On failure it keeps serving the last good module and REPORTS the
 *   error in `logic.reloadError` — absent says absent, here as on the wire.
 */
const PIPE_FILE = join(HERE, 'pipeline.mjs');
let pipeCache = { fn: pipeline, mtime: 0, loadedAt: new Date().toISOString(),
                  source: 'boot import', error: null };
async function pipelineFresh() {
  let m = 0;
  try { m = statSync(PIPE_FILE).mtimeMs; } catch { return pipeCache; }
  if (m === pipeCache.mtime) return pipeCache;
  try {
    // ⚠ The query string is what makes Node fetch it again; an ESM module
    //   specifier is cached by URL and the path alone never changes.
    const mod = await import(`./pipeline.mjs?t=${m}`);
    pipeCache = { fn: mod.pipeline, mtime: m, loadedAt: new Date().toISOString(),
                  source: 'reloaded from disk', error: null };
  } catch (e) {
    // ⛔ KEEP THE LAST GOOD ONE AND SAY WHY. Do NOT update `mtime`, so the next
    //   request retries once the file is saveable again.
    pipeCache = { ...pipeCache, error: `${e.name}: ${e.message}` };
  }
  return pipeCache;
}

const argv = process.argv.slice(2);
const flag = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
const PORT = parseInt(flag('--port', '8799'), 10);

/**
 * ⛔ THE FIXED TABLE. Every command this process is capable of running is here,
 *   in the source, reviewable. Nothing else can ever be spawned.
 *
 * ⚠ `probe` is the path a health check hits. `/` for a page, `/state` for a
 *   service that has one — the same paths `index.html` already lists, because
 *   two lists of the same thing drift and the drift is invisible.
 */
const SERVICES = [
  // ⭐ "Talker" — Gee, 2026-09-05. The `id` stays `player` on purpose: it is
  //   what `.u3e-paths.json`, the pipeline steps and any saved auto-start
  //   preference already key on, and renaming an ID to match a label breaks
  //   state somebody else stored.
  { id: 'player', name: 'Talker', port: 8790, probe: '/',
    cmd: 'node', args: ['serve/server.mjs'] },
  { id: 'sidecar', name: 'Inference sidecar', port: 8797, probe: '/state',
    cmd: 'python', args: ['train/infer.py', '--model', 'models/unity-tiny-v1'] },
  { id: 'voice', name: 'Unity One voice', port: 7861, probe: '/state',
    cmd: 'python', args: ['Unity 18+/voice-server/voice_server.py'] },
  { id: 'teechuh', name: 'Teechuh', port: 8796, probe: '/',
    cmd: 'node', args: ['monitor/model.mjs'] },
  // ⭐ `U3E-5.98m` — the voicing run's own viewer, so step 8 can be watched the
  //   way banking and training already can. ⚠ It is read-only; this table owns
  //   the `rewrite` job and must remain the only thing that can start it.
  // ⛔⛔ `U3E-5.98x` — 8793, NOT 8794. `datatools/label-band.mjs` defaults to
  //   8794 and was there first; registering the voicing monitor on the same
  //   port meant whichever started first held it and **the switchboard
  //   reported BOTH as `up` because it only probes the port, not the
  //   process.** ⚠ Found by reading this table while debugging the Talker.
  { id: 'voicemon', name: 'Voicing monitor', port: 8794, probe: '/',
    cmd: 'node', args: ['monitor/voice.mjs'] },
  { id: 'bank', name: 'Bank monitor', port: 8795, probe: '/',
    cmd: 'node', args: ['monitor/bank.mjs'] },
  { id: 'wrapper', name: 'Local wrapper', port: 4545, probe: '/api/state',
    cmd: 'node', args: ['Unity 18+/server/server.mjs'] },
  /**
   * ⛔⛔⛔ `U3E-5.103` — THE TALKER HAS THREE DEPENDENCIES AND ONLY TWO OF THEM
   *   COULD BE STARTED FROM THE PAGE.
   *
   *   Gee: *"so why did the run button not start it up correctly on the main
   *   index.html page?"*, with the Talker card reading `● running`.
   *
   * ⭐ **THE BUTTON WORKED. IT STARTED THE TALKER AND THE TALKER ALONE**, which
   *   is all that card has ever claimed to do — `:8790` really was up. What was
   *   down was the stack BEHIND it, and `/api/models` said so precisely:
   *   *"Default — 0/3 services up"*.
   *
   *   ```
   *     :4545  wrapper      had a card
   *     :7861  Unity One    had a card
   *     :7860  Stable Diffusion   ⛔ NOT IN THIS TABLE AT ALL
   *   ```
   *
   * ⛔ **So `▶ Start everything` iterates `SERVICES` and could never start the
   *   image model.** Pressing every control on the page left the Talker unable
   *   to draw, with no card, no switch and no `start it:` line anywhere saying
   *   the missing piece even existed. ⚠ Same class as the writer having no card
   *   (`U3E-5.102`): **a required thing with no front door.** The operator had
   *   to be told the command by someone who read the source.
   *
   * ⚠ `/sdapi/v1/options` is the probe, not `/` — `sd_server.py` speaks the
   *   AUTOMATIC1111 shape and answers 404 on the root, which would have drawn a
   *   red dot over a perfectly healthy service.
   * ⚠ THE PATH IS QUOTED IN `args` because it contains a space. `startService`
   *   passes the array straight to `spawn` so this is safe here — but note that
   *   `Start-Process` in a shell DOES re-split it, which is exactly how this
   *   service failed to launch by hand the first time.
   */
  { id: 'sd', name: 'Image model (Stable Diffusion)', port: 7860,
    probe: '/sdapi/v1/options',
    cmd: 'python', args: ['-u', 'Unity 18+/image-server/sd_server.py'] },
  { id: 'portal', name: 'Banking portal', port: 8788, probe: '/',
    cmd: 'node', args: ['datatools/portal/server.mjs', '--searx', 'http://127.0.0.1:8888'] },
  { id: 'corpus', name: 'Corpus viewer', port: 8789, probe: '/',
    cmd: 'node', args: ['datatools/corpus-review.mjs'] },
  /**
   * ⛔⛔ `U3E-2.221c` — REGISTERED, BECAUSE A TOOL THE SWITCHBOARD CANNOT SEE IS
   *   A TOOL THAT GETS ORPHANED.
   *
   * Gee: *"why are you running shells for those? i have them open on theri
   * porsts"* — and he was right about this one. `label-band.mjs` was started
   * detached and appeared on NO front door: not startable, not stoppable, not
   * visible as up or down. **The operator could not turn off something I had
   * turned on.**
   *
   * ⚠ IT DEPENDS ON THE CORPUS VIEWER and says so rather than failing oddly —
   *   it proxies `/field/` and `/codec/` to :8789 rather than re-implementing
   *   the decode and the traversal guard, so with that down it answers
   *   `502 the review viewer did not answer` instead of a blank page.
   */
  // ⛔ `U3E-5.98z` — MOVED TO 8792, NOT THE MONITOR. This collided with the
  //   voicing monitor on 8794. My first fix moved the MONITOR because this
  //   tool was there first — ⚠ and that broke the URL Gee actually watches,
  //   which is the wrong tiebreak: one side is a surface a human has open,
  //   the other is a one-off dev script that is not even running.
  { id: 'labels', name: 'Dedup-band labeller', port: 8792, probe: '/',
    cmd: 'node', args: ['datatools/label-band.mjs'] },
  /**
   * ⛔ `U3E-2.199c` — SWEEP REVIEW (:8787) IS DELIBERATELY NOT HERE. Gee: *"wtf
   *   is 8787??? we have 8795 running already doing this"*. ⚠ It is not the same
   *   tool as :8795 — it shows what a SEARCH LANE returns before banking — but
   *   its own header states the premise it was built on: *"there is no real
   *   training corpus to sweep yet"*. There are 41,319 banked images now.
   *   ⭐ The file still runs and is still the right instrument the day a new
   *   cell is added to `taxonomy.json`. It is simply not a front door.
   */
];
const BY_ID = new Map(SERVICES.map(s => [s.id, s]));

/**
 * ⛔ `U3E-2.199d` — THE PIPELINE JOBS. Same fixed-table rule as `SERVICES`, for
 *   the same reason: the request names an id, never a command.
 *
 * ⚠ `heavy` marks a job that eats the card for hours. The page CONFIRMS those
 *   before firing and the automatic run refuses to start one on its own —
 *   *"automatic with user input where needed"* cuts both ways, and a page that
 *   silently began a training run because a box was ticked would be the worst
 *   kind of helpful.
 */
const JOBS = [
  { id: 'codec-parity', label: 'codec parity, JS to Python',
    cmd: 'node', args: ['codec/verify/parity.mjs'] },
  { id: 'bank', label: 'bank more images', cmd: 'python', args: ['datatools/bulk-bank.py'] },
  { id: 'caption', label: 'caption the uncaptioned', cmd: 'node', args: ['datatools/caption-run.mjs'] },
  { id: 'figures', label: 'bank the cited figures', cmd: 'node', args: ['datatools/figures-bank.mjs'] },
  /**
   * ⛔⛔ `U3E-5.98q` — PASSES ARE NOT THE RETRY MECHANISM ANY MORE, AND THEY
   *   NEVER SHOULD HAVE BEEN. Gee: *"we dont need to do 40 fucking passes once
   *   gets it done thats all we need"*.
   *
   *   ⛔ He was right about the shape. The single-call path had ONE attempt per
   *   record and then moved on, so its only retry was the NEXT PASS — arriving
   *   after all 5,350 records had cycled. **`--passes N` was a retry loop with
   *   a five-thousand-record delay between iterations.**
   *   ⭐ `--tries 6` now retries a short record IN PLACE with the reason fed
   *   back, which is the same iteration the chunked path always had.
   *
   * ⚠ SO WHY NOT `--passes 1`? Because passes still do ONE job that tries
   *   cannot: **chunk-bank accumulation.** A 16-chunk record that earns 14
   *   chunks and runs out of chunk-tries banks those 14, and the next pass only
   *   pays for the 2 that are left — measured going 1/10 -> 2/10 -> 7/10 on the
   *   same records. ⭐ **Every pass after the first is therefore CHEAP**, which
   *   is the opposite of what 40 blind passes were.
   * ⚠ 4 is a judgement, not a measurement: enough for a long record to
   *   accumulate, few enough that the run ends rather than spinning. The old 6
   *   was never justified anywhere and the 40 on the command line was worse.
   */
  /**
   * ⭐⭐ `U3E-5.100` — **2**, AND IT IS A DECISION WITH A NUMBER BEHIND IT.
   *
   *   The comment above argues for passes and names 4 as *"a judgement"*; the
   *   args said `1`, from Gee on 2026-09-08: *"ONE PASS!!!! 1/4 pass"*.
   *   ⛔ **So the comment and the code disagreed, and the code was the one that
   *   ran.** A reader of this block would have concluded 4.
   *
   * ⭐ THE NUMBER THAT SETTLED IT — the chunk-bank census, n=856:
   *   **528 records (61.7%) sit PARTIAL**, holding fewer chunks than their key
   *   demands, at **5,560 of 9,025 chunks = 61.6% complete**. Under one pass
   *   every one of them is abandoned for the run. ⚠ Put to Gee with that
   *   measurement, his call was **`--passes 2`** — not the 1 he set blind and
   *   not the 4 this comment recommends.
   * ⚠ WHAT PASS 2 ACTUALLY RECOVERS IS STILL UNMEASURED. The 1/10 -> 2/10 ->
   *   7/10 figure quoted for accumulation is from a DIFFERENT run, and these
   *   stalls are led by `opener-stamp`, which a retry does not obviously fix.
   * ⛔ `python -u`, NOT `python`. Block-buffered stdout froze the run log at
   *   1,014 bytes while the run reached index 16 — a log that looks live and is
   *   two hours stale is the instrument that lies.
   */
  { id: 'rewrite', label: 'put the lessons in her voice',
    cmd: 'python',
    args: ['-u', 'datatools/curriculum-rewrite.py', '--passes', '2', '--tries', '6'] },
  { id: 'voice', label: 'bank her voice', cmd: 'python', args: ['datatools/voice-bank.py'] },
  { id: 'mix-plan', label: 'derive the modality mix', cmd: 'node', args: ['train/mix-plan.mjs'] },
  /**
   * ⛔⛔ `U3E-5.76` — THE PLAN AND THE SHARDS ARE TWO DIFFERENT FACTS, AND ONLY
   *   ONE OF THEM TRAINS THE MODEL. `mix-plan` DECIDES 50/40/10; nothing builds
   *   to it, and step 11 ticked green because the plan FILE existed. Measured:
   *   `image 91.29% · audio 8.65% · text 0.06%` — against the 0.47% that left
   *   her unable to spell. ⭐ This job writes the receipt step 11 now judges on.
   */
  { id: 'mix-actual', label: 'measure the mix the shards ACTUALLY have',
    cmd: 'node', args: ['train/mix-actual.mjs'] },
  { id: 'shard', label: 'build the shards', cmd: 'node', args: ['train/shard.mjs'], heavy: true },
  /**
   * ⭐⭐ `U3E-5.79` — A SEPARATE JOB WITH THE FLAG BAKED IN, NOT A FLAG FROM THE
   *   BROWSER. Gee: *"need way to redo them as currently once something is in i
   *   cant tell it to reverify or start new."*
   *
   * ⛔ THE FIRST CUT OF THIS SENT `--rebuild` AS A QUERY PARAMETER, and that is a
   *   shell hole wearing a feature's name. `/api/job` accepts an ID and looks it
   *   up — *"UNKNOWN ID IS A 404, NOT A SHELL"* — so the honest way to offer a
   *   rebuild is to REGISTER one.
   * ⚠ `--rebuild` discards the frozen `build-plan.json` (`U3E-5.34`) and does NOT
   *   delete the old shards: they are overwritten as the new plan reaches them.
   *   The page's confirmation says so in those words.
   */
  { id: 'shard-rebuild', label: 'rebuild the shards FROM SCRATCH',
    cmd: 'node', args: ['train/shard.mjs', '--rebuild'], heavy: true },
  { id: 'fitcheck', label: 'measure VRAM on the real card', cmd: 'python', args: ['train/fitcheck.py'] },
  { id: 'train', label: 'THE RUN', cmd: 'python', args: ['train/train.py'], heavy: true },
  /**
   * ⛔⛔ `U3E-2.209` — THE JOB STEP 17 HAS BEEN ASKING FOR ALL ALONG. Step 17
   *   carried `run: 'eval'` and this table had no such id, so the row drew an
   *   empty action cell forever. ⚠ Registering the id was only half of it —
   *   `train/eval-five.mjs` did not exist either, and `startJob`'s
   *   `script-missing` refusal would have caught the second half only after
   *   somebody pressed a button that was never drawn.
   */
  { id: 'eval', label: 'measure all five modalities', cmd: 'node', args: ['train/eval-five.mjs'] },
];
const JOB_BY_ID = new Map(JOBS.map(j => [j.id, j]));
/** jobs this launcher has running, so the page can show one is already going. */
const RUNNING = new Map();

/**
 * ⛔⛔⛔ `U3E-5.98l` — A JOB STARTED FROM A TERMINAL IS STILL RUNNING, AND THIS
 *   TABLE COULD NOT SEE IT.
 *
 *   `RUNNING` holds only the children THIS process spawned. ⚠ So a rewriter
 *   started by hand — which is how every long run in this project has actually
 *   been started — reported `running: false`, and the page drew a live
 *   **"▶ put the lessons in her voice"** button beside it.
 *
 * ⛔ PRESSING IT WOULD HAVE STARTED A SECOND REWRITER ON THE SAME MANIFEST, and
 *   `index.html`'s own tooltip on that button says what that costs: *"two
 *   writers on one manifest is how 43 captions were lost once."* Both processes
 *   do a whole-file load-modify-write of a 68 MB file, so the second to flush
 *   erases the first's work — see `U3E-5.98j` and
 *   `wiki/gotchas/an-accept-must-be-durable-before-it-is-counted.md`.
 *
 * ⭐ THE DETECTOR ALREADY EXISTED. `curriculum-rewrite.py` writes a progress
 *   file with a `pid` and an `updated` HEARTBEAT on every record, and
 *   `rewriter_is_live()` reads it. This is the same test in the only other
 *   language that needs it.
 * ⛔ IT KEYS ON THE HEARTBEAT, NOT ON `state`. This project's progress file once
 *   read `state: "running"` for TWENTY-FOUR HOURS behind a pid that no longer
 *   existed (`wiki/gotchas/silent-job-death.md`), so `state` alone is a claim
 *   and the timestamp is the evidence.
 * ⚠ AND IT REPORTS **WHOSE** IT IS. `running` alone would say a job is going;
 *   `foreign` says nobody on this page can stop it, which is a different fact
 *   and the one the operator needs before they go looking for an off switch.
 */
const HEARTBEATS = {
  rewrite: '.curriculum-rewrite-progress.json',
};
const HEARTBEAT_STALE_MS = 180000;

function foreignHeartbeat(id) {
  const rel = HEARTBEATS[id];
  if (!rel) return null;
  try {
    const p = JSON.parse(readFileSync(join(dataDir().dir, rel), 'utf8'));
    if (p.state !== 'running' && p.state !== 'starting') return null;
    const age = Date.now() - Number(p.updated || 0) * 1000;
    if (!(age >= 0) || age > HEARTBEAT_STALE_MS) return null;
    return { pid: p.pid || null, ageMs: Math.round(age), note: p.note || null };
  } catch { return null; }
}

/**
 * ⛔⛔⛔ `U3E-5.100` — THE CARD GRID WAS STRUCTURALLY BLIND TO JOBS, AND THE ONE
 *   THING RUNNING FOR 88 HOURS IS A JOB.
 *
 *   Gee, looking at the page with the writer alive at pid 9544: *"i dont swee
 *   the writter is on"* — and he was reading it correctly. ⛔ **`/api/state`
 *   returned `services` and nothing else.** A service is a PORT; the rewriter
 *   has no port, so it could never appear on the grid however long it ran.
 *
 *   ⚠ The information existed the whole time — `/api/steps` reported
 *   `running:true, pid:9544, foreign:true, heartbeatAgeMs:548` — but only the
 *   numbered pipeline consumed it. **A fact that reaches one surface and not
 *   the surface somebody actually opens is a fact nobody has.**
 *
 * ⭐ ONE FUNCTION, BOTH ROUTES. The mapping used to live inline inside
 *   `/api/steps`; two copies of it would drift, and the drift is invisible —
 *   the same argument `probe` carries at the top of `SERVICES`.
 */
function jobsSnapshot() {
  return JOBS.map(j => {
    const hb = foreignHeartbeat(j.id);
    return {
      id: j.id, label: j.label, heavy: !!j.heavy,
      // ⭐ `U3E-5.98l` — OURS **OR** ANYBODY'S. `RUNNING` sees only this
      //   process's children, so a job started from a terminal read as idle
      //   and the page drew a start button next to a live writer.
      running: RUNNING.has(j.id) || !!hb,
      pid: RUNNING.get(j.id)?.pid || hb?.pid || null,
      // ⚠ A DIFFERENT FACT, SAID SEPARATELY: this page cannot stop it.
      foreign: !RUNNING.has(j.id) && !!hb,
      heartbeatAgeMs: hb?.ageMs ?? null,
      note: hb?.note ?? null,
      // ⛔ `U3E-2.209` — DOES THE SCRIPT EXIST. `startJob` already refuses a
      //   missing script, but it refuses at PRESS TIME into a log. Reporting
      //   it here puts the absence on the row before anyone presses.
      exists: jobTargetExists(j),
      // ⭐ THE COMMAND, so a card can print what to run when it is NOT running —
      //   the same rule every service card follows.
      cmd: `${j.cmd} ${j.args.map(a => (a.includes(' ') ? `"${a}"` : a)).join(' ')}`,
    };
  });
}

/**
 * ⛔⛔ `U3E-2.209` — THE AUDIT THAT WAS MISSING, AND STEP 17 IS WHY IT EXISTS.
 *
 *   `serve/pipeline.mjs` step 17 carries `run: 'eval'`. **There has never been an
 *   `eval` job in the table above, and no script anywhere in this repository
 *   writes an `eval-five` receipt.** So the step drew an empty action cell
 *   forever, and Gee found it by looking: *"some #ed items in the main page of
 *   check list dont even have an option to rectify it"*.
 *
 * ⛔ THE INSTRUMENT THAT SHOULD HAVE CAUGHT IT LOOKED AT THE WRONG THING.
 *   `pipeline()`'s own `missingCmds` audits `node`/`python` paths printed inside
 *   DETAIL TEXT — it never checked the `run` id, which is the actual contract
 *   between a step and this table. It reported `[]` about a permanently dead row.
 *
 * ⭐ THE TWO TABLES ARE CROSS-CHECKED ON EVERY REQUEST, in both directions:
 *   a step naming a job that does not exist, and a job no step ever asks for.
 *   ⚠ The second is not an error — it is reported as `orphan` and nothing acts
 *   on it, because a job can legitimately be runnable without owning a step.
 */
function auditJobIds(steps) {
  const named = new Set();
  const missing = [];
  for (const s of steps) {
    if (!s.run) continue;
    named.add(s.run);
    if (!JOB_BY_ID.has(s.run)) missing.push({ step: s.n, run: s.run, name: s.name });
  }
  const orphan = JOBS.filter(j => !named.has(j.id)).map(j => j.id);
  return { missing, orphan };
}

/**
 * ⛔ THE SCRIPT A JOB WOULD RUN, CHECKED ON DISK. Same rule and same reason as
 *   `cmdTargetExists` does for services — an absence belongs on the card, not in
 *   a log opened after the button did nothing.
 */
function jobTargetExists(j) {
  const target = j.args.find(a => /\.(mjs|js|py)$/.test(a));
  return target ? existsSync(join(ROOT, target)) : true;
}

function startJob(j) {
  if (RUNNING.has(j.id)) return { ok: false, why: 'already-running', pid: RUNNING.get(j.id).pid };
  const target = j.args.find(a => /\.(mjs|js|py)$/.test(a));
  // ⛔ A JOB WHOSE SCRIPT IS NOT THERE IS A REFUSAL WITH A NAME, not a spawn that
  //   fails into a log nobody opens.
  if (target && !existsSync(join(ROOT, target)))
    return { ok: false, why: 'script-missing', target };
  mkdirSync(LOGS, { recursive: true });
  const log = createWriteStream(join(LOGS, `job-${j.id}.log`), { flags: 'a' });
  log.write(`\n--- ${new Date().toISOString()} ${j.cmd} ${j.args.join(' ')}\n`);
  const child = spawn(j.cmd, j.args, {
    cwd: ROOT, detached: process.platform !== 'win32', windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
    // ⭐ Same inheritance as a service — see startService.
    env: { ...process.env, U3E_DATA: dataDir().dir },
  });
  child.stdout.pipe(log); child.stderr.pipe(log);
  child.on('exit', (code) => {
    log.write(`--- exited code ${code}\n`);
    const r = RUNNING.get(j.id);
    if (r) { r.exited = code; r.endedAt = Date.now(); }
    RUNNING.delete(j.id);
  });
  RUNNING.set(j.id, { pid: child.pid, at: Date.now() });
  return { ok: true, pid: child.pid };
}

/** processes THIS launcher started, so the UI can say which are ours. */
const OURS = new Map();

/**
 * ⛔ IS SOMETHING LISTENING — asked by opening a TCP connection, not by fetching.
 *   A service that is booting answers the socket before it answers HTTP, and a
 *   launcher that called it DOWN for those seconds would send you to start a
 *   second copy of a thing that is already coming up.
 */
function listening(port, timeout = 900) {
  return new Promise((res) => {
    const s = connect({ host: '127.0.0.1', port });
    const done = (v) => { s.destroy(); res(v); };
    s.setTimeout(timeout);
    s.once('connect', () => done(true));
    s.once('timeout', () => done(false));
    s.once('error', () => done(false));
  });
}

/**
 * The PID holding a port, or null.
 * ⚠ Two implementations because the tool differs, and the parse is written out
 *   rather than assumed: `netstat` columns on Windows, `lsof` elsewhere. A wrong
 *   column index here kills the wrong process, so it matches on the ADDRESS as
 *   well as the state rather than trusting position alone.
 */
function pidOnPort(port) {
  return new Promise((res) => {
    if (process.platform === 'win32') {
      execFile('netstat', ['-ano', '-p', 'TCP'], { windowsHide: true }, (e, out) => {
        if (e || !out) return res(null);
        for (const line of out.split(/\r?\n/)) {
          const p = line.trim().split(/\s+/);
          if (p.length < 5) continue;
          if (p[3] !== 'LISTENING') continue;
          if (!/^(127\.0\.0\.1|0\.0\.0\.0|\[::\]|\[::1\]):/.test(p[1])) continue;
          if (p[1].split(':').pop() !== String(port)) continue;
          const pid = parseInt(p[4], 10);
          if (pid > 0) return res(pid);
        }
        res(null);
      });
    } else {
      execFile('lsof', ['-nP', `-iTCP:${port}`, '-sTCP:LISTEN', '-t'], (e, out) => {
        const pid = parseInt(String(out || '').trim().split(/\s+/)[0], 10);
        res(e || !pid ? null : pid);
      });
    }
  });
}

function killPid(pid) {
  return new Promise((res) => {
    if (process.platform === 'win32') {
      execFile('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true },
               (e) => res(!e));
    } else {
      try { process.kill(pid, 'SIGTERM'); res(true); } catch { res(false); }
    }
  });
}

async function startService(s) {
  if (await listening(s.port)) return { ok: false, why: 'already-listening' };
  mkdirSync(LOGS, { recursive: true });
  // ⭐ THE OUTPUT GOES TO A FILE, NOT TO NOWHERE. A service that dies three
  //   seconds after starting looks identical to one that never started, and the
  //   difference is always in the first ten lines it printed.
  const log = createWriteStream(join(LOGS, `${s.id}.log`), { flags: 'a' });
  log.write(`\n--- ${new Date().toISOString()} launcher start: ${s.cmd} ${s.args.join(' ')}\n`);
  const child = spawn(s.cmd, s.args, {
    cwd: ROOT, detached: process.platform !== 'win32', windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
    // ⭐⭐ `U3E-2.199f` — EVERY CHILD INHERITS THE DATA ROOT. This is what makes
    //   the setting reach a tool without editing it: the switchboard exports
    //   `U3E_DATA` and anything that resolves through `serve/datadir.mjs` or
    //   `datatools/corpus-index.mjs` picks it up. ⚠ A tool that still joins 'data'
    //   itself does NOT, which is exactly why the page prints the coverage
    //   fraction instead of implying the move is global.
    env: { ...process.env, U3E_DATA: dataDir().dir },
  });
  child.stdout.pipe(log);
  child.stderr.pipe(log);
  child.on('exit', (code) => {
    log.write(`--- exited code ${code}\n`);
    if (OURS.get(s.id)?.pid === child.pid) OURS.delete(s.id);
  });
  OURS.set(s.id, { pid: child.pid, at: Date.now() });
  return { ok: true, pid: child.pid };
}

async function stopService(s) {
  const pid = await pidOnPort(s.port);
  if (!pid) return { ok: false, why: 'not-listening' };
  const mine = OURS.get(s.id)?.pid === pid;
  const ok = await killPid(pid);
  if (ok) OURS.delete(s.id);
  // ⚠ `mine` is REPORTED. Killing a process somebody started in their own
  //   terminal is a legitimate thing to want and a rude thing to do silently.
  return { ok, pid, startedByLauncher: mine };
}

async function snapshot() {
  const out = [];
  for (const s of SERVICES) {
    const up = await listening(s.port);
    out.push({
      id: s.id, name: s.name, port: s.port, up,
      startedByLauncher: OURS.has(s.id),
      cmd: `${s.cmd} ${s.args.map(a => (a.includes(' ') ? `"${a}"` : a)).join(' ')}`,
      exists: cmdTargetExists(s),
    });
  }
  return out;
}

/**
 * ⛔ DOES THE THING IT WOULD RUN ACTUALLY EXIST ON DISK. A start button for a
 *   script that is not there fails in a log nobody opens; this makes the absence
 *   visible on the card BEFORE it is pressed.
 */
function cmdTargetExists(s) {
  const target = s.args.find(a => /\.(mjs|js|py)$/.test(a));
  return target ? existsSync(join(ROOT, target)) : true;
}

function send(res, code, body) {
  const b = Buffer.from(JSON.stringify(body));
  res.writeHead(code, {
    'content-type': 'application/json',
    'content-length': b.length,
    // ⚠ `*` is correct here and only here: the page is `file://`, whose Origin
    //   is the opaque string "null", so an origin allowlist cannot name it. The
    //   real protection is the 127.0.0.1 bind and the fixed command table above.
    'access-control-allow-origin': '*',
    'access-control-allow-headers': 'content-type',
    'access-control-allow-methods': 'GET,POST,OPTIONS',
  });
  res.end(b);
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1');
  if (req.method === 'OPTIONS') return send(res, 204, {});

  if (url.pathname === '/api/state') {
    return send(res, 200, {
      ok: true, launcher: 'u3e', port: PORT,
      services: await snapshot(),
      // ⭐ `U3E-5.100` — JOBS RIDE HERE TOO. See `jobsSnapshot`: the card grid
      //   polls this route and only this route, so a portless job was invisible
      //   on it no matter how long it had been running.
      jobs: jobsSnapshot(),
    });
  }

  /**
   * ⭐ `U3E-2.199d` — THE WHOLE ROAD, NUMBERED, EACH TICK CARRYING ITS NUMBER.
   *   ⚠ Recomputed on every request from the filesystem rather than cached: a
   *   pipeline view that goes stale is a pipeline view that reports a step done
   *   after somebody deleted its evidence.
   */
  if (url.pathname === '/api/steps') {
    /**
     * ⛔⛔⛔ `U3E-5.86` — THE PAGE WAS SERVING CODE FROM WHENEVER THIS PROCESS
     *   BOOTED, AND NOTHING SAID SO.
     *
     *   Gee, twice: *"thats why i told you the dasshboard of index is wrong"* —
     *   pointing at step 13 still printing *"Shards built before the four-source
     *   change contain images only"* **after that text had been replaced on
     *   disk** — and *"and i have no remedy options"*.
     *
     * ⛔ **BOTH ARE ONE ROOT CAUSE.** `pipeline.mjs` is imported ONCE at boot, so
     *   every fix to a step's logic needed a manual restart of this process, and
     *   the page had no way to know it was reading an hour-old module. ⚠ A
     *   dashboard whose own logic is stale is worse than a stale number: the
     *   number at least came off disk.
     *
     * ⭐ RE-IMPORTED PER REQUEST WHEN THE FILE'S mtime MOVES, with a cache-busting
     *   query so Node's ESM loader actually fetches it again. `pipelineFresh()`
     *   falls back to the boot-time import if a re-import throws — a half-edited
     *   file must not take the switchboard down with it, and the response SAYS
     *   which one answered.
     * ⚠ It reloads `pipeline.mjs` only. A change to THIS file still needs a
     *   restart, and `logicLoadedAt` on every response is how you can tell.
     */
    const pf = await pipelineFresh();
    const p = pf.fn();
    return send(res, 200, {
      ok: true, ...p,
      logic: { source: pf.source, loadedAt: pf.loadedAt, mtime: pf.mtime,
               reloadError: pf.error || null },
      missingJobs: auditJobIds(p.steps),
      // ⭐ `U3E-5.100` — ONE SOURCE. This was an inline map that read the
      //   heartbeat file FIVE times per job per request; `jobsSnapshot` reads it
      //   once, and both routes now answer from the same shape.
      jobs: jobsSnapshot(),
    });
  }

  /**
   * ⭐ `U3E-2.199f` — WHERE `/data` LIVES. Gee: *"we need to be able to set in
   *   the main page where the /data folder is being saved to"*.
   * ⛔ The COVERAGE fraction rides on every response. A page that offered the
   *   setting without it would imply a move is global when 39 of 43 tools still
   *   join 'data' themselves — and a half-honoured move splits the corpus.
   */
  if (url.pathname === '/api/datadir') {
    const probe = url.searchParams.get('probe');
    return send(res, 200, {
      ok: true, ...dataDir(), audit: audit(),
      probe: probe ? inspect(probe, { create: false }) : null,
    });
  }

  if (url.pathname === '/api/datadir/set' && req.method === 'POST') {
    const to = url.searchParams.get('to');
    const create = url.searchParams.get('create') === '1';
    const r = setDataDir(to, { create });
    return send(res, r.ok ? 200 : 400, { ...r, audit: audit() });
  }

  /**
   * ⭐⭐⭐ `U3E-5.90` — WHICH SHARD SET THE RUN EATS, CHOSEN FROM WHAT IS ON DISK.
   *   Gee: *"our shard is done but #13 isnt updateing and i dont correctly have
   *   to option to select them"*.
   *
   * ⛔ THE COUNT OF WAYS TO SELECT ONE WAS ZERO. `shardDir` is `frozen: true` in
   *   `monitor/model.mjs`'s knob registry and that page correctly draws no control
   *   on a frozen knob, so the only way to move the pointer was hand-editing a
   *   git-tracked JSON file.
   *
   * ⚠ MODELLED EXACTLY ON `/api/datadir` ABOVE, including its shape: a GET that
   *   enumerates and probes, a POST that points. Inventing a different contract
   *   for the same kind of act would make the page carry two idioms.
   */
  if (url.pathname === '/api/shards') {
    return send(res, 200, { ok: true, ...listShardSets() });
  }

  if (url.pathname === '/api/shards/set' && req.method === 'POST') {
    const to = url.searchParams.get('to');
    const by = url.searchParams.get('by') || 'operator';
    /**
     * ⛔⛔ `force` IS DELIBERATELY NOT REACHABLE FROM THE WIRE.
     *   `setShardDir` refuses any directory that does not hold BOTH
     *   `build-plan.json` and `build-progress.json`, and `force` exists only for
     *   the CLI, where the operator is already at a shell. ⚠ Exposing it here
     *   would turn a validated pointer into an arbitrary-string write into the
     *   file the trainer reads — and the validation is the entire reason this
     *   route is not that.
     * ⭐ Same standing as `/api/datadir/set`, which accepts a path and lets
     *   `inspect()` refuse it: *"a typo'd path silently mkdir'd is how a corpus
     *   ends up in E:/u3e-dat, half-populated, with nothing wrong on any screen."*
     */
    const r = setShardDir(to, { by });
    return send(res, r.ok ? 200 : 400, r);
  }

  /**
   * ⭐ `U3E-9.0` — WHAT THIS MACHINE HAS, AND A BUTTON FOR WHAT IT DOES NOT.
   *   Gee: *"need to install all dependancyies too"* · *"on auto like"*.
   * ⚠ Slow by nature — it starts a python interpreter and shells out to four
   *   tools — so the page asks for it once and on demand, not on a poll.
   */
  if (url.pathname === '/api/deps') {
    return send(res, 200, { ok: true, ...(await preflight()) });
  }

  if (url.pathname === '/api/deps/install') {
    const spec = installSpec(url.searchParams.get('id'));
    // ⛔ UNKNOWN ID IS A 404, NOT A SHELL. Same rule as every other route here.
    if (!spec || !spec.cmd) return send(res, 404, { ok: false, why: 'unknown-or-not-installable' });
    const r = startJob({ id: `install-${spec.id}`, cmd: spec.cmd, args: spec.args });
    return send(res, r.ok ? 200 : 409, { ...r, id: spec.id,
      cmd: `${spec.cmd} ${spec.args.join(' ')}` });
  }

  if (url.pathname === '/api/job') {
    const j = JOB_BY_ID.get(url.searchParams.get('id'));
    if (!j) return send(res, 404, { ok: false, why: 'unknown-job' });
    const r = startJob(j);
    return send(res, r.ok ? 200 : 409, { ...r, id: j.id, heavy: !!j.heavy });
  }

  /**
   * ⛔⛔ A RECEIPT IS EVIDENCE, AND THESE TWO ARE GEE'S SIGNATURE. The size
   *   approval and the user test are judgements; the page cannot infer them and
   *   no job may write them. ⚠ Only these two names are accepted here — a
   *   measurement receipt (parity, fitcheck, eval) is written by the thing that
   *   took the measurement, never by a click.
   */
  if (url.pathname === '/api/receipt' && req.method === 'POST') {
    const name = url.searchParams.get('name');
    /**
     * ⭐ `U3E-5.79` — `accepted-<n>` JOINS THE TWO SIGNATURES, and only for the
     *   steps that declare themselves acceptable. Gee: *"4,5,&8 nered option for
     *   user to accept as is so they go green."*
     * ⛔ THE ALLOWLIST IS STILL THE POINT. A click may write a JUDGEMENT and may
     *   never write a MEASUREMENT — `codec-parity`, `fitcheck`, `mix-actual` and
     *   `eval-five` are written by the thing that took the number, or not at all.
     * ⚠ Derived from `pipeline()` rather than typed, so a step gaining or losing
     *   `acceptable` cannot leave a stale name writable here.
     */
    const acceptables = pipeline().steps.filter(s => s.acceptable).map(s => `accepted-${s.n}`);
    if (!['size-approved', 'user-test', ...acceptables].includes(name))
      return send(res, 403, { ok: false, why: 'receipt-not-user-writable', name, acceptables });
    let body = '';
    for await (const c of req) body += c;
    let doc = {};
    try { doc = body ? JSON.parse(body) : {}; } catch { /* empty is fine */ }
    return send(res, 200, { ok: true, receipt: writeReceipt(name, doc) });
  }

  /**
   * ⛔⛔⛔ `U3E-5.79` — RE-VERIFY. Gee: *"once something is in i cant tell it to
   *   reverify or start new."*
   *
   *   A receipt-backed step was a ONE-WAY LATCH: `fitcheck` measured VRAM once,
   *   against a different `seqLen` and a different shard set, and nothing on the
   *   page could ask it to look again. **A measurement with no way to invalidate
   *   it is a cache pretending to be a fact.**
   *
   * ⛔ IT DELETES EVIDENCE AND NEVER WRITES ANY. The step drops to `unverified`
   *   — *"nothing has measured this"*, which is the honest state — and its own
   *   runner takes the number again. ⚠ `unverified` is deliberately NOT `open`:
   *   a cleared step is unmeasured, not failing.
   * ⛔ ALLOWLISTED FROM `pipeline()`'s OWN `receiptName` FIELDS. An unfiltered
   *   name here would be an arbitrary-file-delete endpoint reachable from a
   *   browser.
   */
  if (url.pathname === '/api/receipt/clear' && req.method === 'POST') {
    const name = url.searchParams.get('name');
    const known = pipeline().steps.map(s => s.receiptName).filter(Boolean);
    if (!known.includes(name))
      return send(res, 403, { ok: false, why: 'not-a-pipeline-receipt', name, known });
    const f = join(ROOT, '.receipts', name + '.json');
    if (!existsSync(f)) return send(res, 200, { ok: true, cleared: false, why: 'was-not-there', name });
    try {
      rmSync(f);
      return send(res, 200, { ok: true, cleared: true, name });
    } catch (e) {
      return send(res, 500, { ok: false, why: e.code || e.message, name });
    }
  }

  if (url.pathname === '/api/start' || url.pathname === '/api/stop') {
    const id = url.searchParams.get('id');
    const s = BY_ID.get(id);
    // ⛔ UNKNOWN ID IS A 404, NOT A SHELL.
    if (!s) return send(res, 404, { ok: false, why: 'unknown-service', id });
    const r = url.pathname === '/api/start' ? await startService(s) : await stopService(s);
    return send(res, r.ok ? 200 : 409, { ...r, id, port: s.port });
  }

  if (url.pathname === '/api/start-all') {
    const started = [], skipped = [];
    for (const s of SERVICES) {
      const r = await startService(s);
      (r.ok ? started : skipped).push({ id: s.id, why: r.why });
    }
    return send(res, 200, { ok: true, started, skipped });
  }

  if (url.pathname === '/api/stop-all') {
    const stopped = [];
    for (const s of SERVICES) {
      const r = await stopService(s);
      if (r.ok) stopped.push({ id: s.id, startedByLauncher: r.startedByLauncher });
    }
    return send(res, 200, { ok: true, stopped });
  }

  send(res, 404, { ok: false, why: 'no-such-route', path: url.pathname });
});

// ⛔ 127.0.0.1 EXPLICITLY. See the header note — this process spawns programs.
server.listen(PORT, '127.0.0.1', () => {
  console.log(`\nU3E SWITCHBOARD — http://127.0.0.1:${PORT}\n`);
  console.log(`  ${SERVICES.length} services it can start, and NOTHING else.`);
  console.log(`  logs        .launcher-logs/<id>.log`);
  console.log(`  bound to    127.0.0.1 only`);
  console.log(`\n  Open index.html — its cards now have on/off switches.\n`);
});
