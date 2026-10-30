/**
 * turn.js — `U3E-8.6` + `U3E-8.7`. The turn is not committed until it is.
 *
 * ⭐ THESE TWO ROWS ARE ONE RULE, AND FINDING THAT IS MOST OF THE DESIGN
 *   `8.6` is "reformulates based on updating inputs of stt" — the recogniser
 *   revises what it thought you said. `8.7` is "takes additional comments into
 *   consideration" — you say more while she is working. They arrive from
 *   different places and they mean the same thing:
 *
 *       **the input a generation was built on is no longer the input.**
 *
 *   So there is ONE rule, applied to both: any change to the utterance while a
 *   generation is in flight **aborts that generation and re-runs on the new
 *   text**. The only difference is what the transcript shows — a revision
 *   REPLACES the recognised words, an amendment APPENDS to them.
 *
 * ⛔ THE WRONG DESIGN, NAMED BEFORE ANYONE BUILDS IT
 *   Queueing the new input as a second question. `U3E-8.7` says it outright:
 *   that "makes her answer a question the person has already amended". It is
 *   the obvious design and it is wrong. One utterance is one turn.
 *
 * ⛔ THE OTHER WRONG DESIGN
 *   Letting the in-flight generation finish because it "might still be fine".
 *   It answers the old sentence. `U3E-8.6`: discard the draft rather than speak
 *   a stale answer.
 *
 * ⚠ GENERATION IS HELD UNTIL THE ENDPOINT, deliberately.
 *   Starting on the first partial would mean aborting on almost every frame,
 *   because partials revise constantly. `listen.js` decides when speech ended
 *   (`U3E-8.5`); until then this only accumulates. That is why `settle()` is a
 *   separate call and not a side-effect of `revise()`.
 *
 * ⛔ THIS MODULE OWNS NO I/O AND NO BROWSER API, ON PURPOSE.
 *   It decides; the caller fetches. That is what lets the whole state machine
 *   be run and measured in Node (`app/turn-selftest.mjs`) instead of only being
 *   reasoned about in a browser. PLATFORM LAW: it also means it loads on an S23
 *   with nothing to provide.
 */

/** What the caller should do next. The builder never acts, it only decides. */
export const ACT = {
  HOLD: 'hold',        // accumulate; nothing to run yet
  RUN: 'run',          // start a generation for `text` at `epoch`
  RERUN: 'rerun',      // ⛔ abort the in-flight generation, then run `text`
  IGNORE: 'ignore',    // no material change — do not disturb a running generation
};

export function createTurnBuilder(opts = {}) {
  const now = opts.now || (() => Date.now());

  let recognised = '';      // what STT currently believes was said (U3E-8.6)
  let amendments = [];      // what was added on top, in order (U3E-8.7)
  let phase = 'idle';       // idle | forming | generating
  let epoch = 0;            // bumped on every (re)run; stale replies check it
  let runText = null;       // the exact text the in-flight generation was given
  let runStartedAt = 0;

  const log = {
    revisions: 0,
    amendments: 0,
    aborts: 0,
    ignored: 0,
    runs: 0,
    // ⭐ the honest instrument: how LATE the invalidations land. A mean hides
    //   the tail, so every window is kept and reported.
    stalenessMs: [],
    lastDivergenceAt: null,
  };

  /** Full utterance = what was recognised, plus anything added after it. */
  function text() {
    return [recognised, ...amendments].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
  }

  /**
   * Where two utterances first differ, in words.
   * ⚠ Word index, not character index — a character index moves when the
   * recogniser re-spaces a word it already had, which is not a divergence.
   * Returns -1 when `a` is a prefix of `b` (a pure extension).
   */
  function divergenceWord(a, b) {
    const x = a ? a.split(' ') : [];
    const y = b ? b.split(' ') : [];
    const n = Math.min(x.length, y.length);
    for (let i = 0; i < n; i++) if (x[i] !== y[i]) return i;
    return x.length === y.length ? -1 : (x.length < y.length ? -1 : n);
  }

  function decide() {
    const t = text();
    if (phase !== 'generating') return { act: ACT.HOLD, text: t, epoch };

    // ⛔ In flight, and the input moved. Compare against exactly what the
    //    generation was given — never against the previous partial, or a
    //    revision that reverts to an earlier guess would look like a change.
    if (t === runText) {
      log.ignored++;
      return { act: ACT.IGNORE, text: t, epoch };
    }
    const at = divergenceWord(runText || '', t);
    log.lastDivergenceAt = at;
    const staleness = now() - runStartedAt;
    log.stalenessMs.push(staleness);
    log.aborts++;
    epoch++;
    runText = t;
    runStartedAt = now();
    log.runs++;
    return { act: ACT.RERUN, text: t, epoch, divergenceWord: at, stalenessMs: staleness };
  }

  return {
    /**
     * `U3E-8.6` — STT revised what it thinks was said. REPLACES the recognised
     * words; amendments made on top of them survive, because the person still
     * said those.
     */
    revise(t, { final = false } = {}) {
      const next = String(t || '').replace(/\s+/g, ' ').trim();
      if (next !== recognised) log.revisions++;
      recognised = next;
      if (phase === 'idle') phase = 'forming';
      const d = decide();
      return { ...d, final, phase };
    },

    /**
     * `U3E-8.7` — something said (or typed) on top of the utterance. APPENDS.
     * ⛔ It does NOT create a second turn. That is the whole row.
     */
    amend(t) {
      const add = String(t || '').replace(/\s+/g, ' ').trim();
      if (!add) return { act: ACT.IGNORE, text: text(), epoch, phase };
      amendments.push(add);
      log.amendments++;
      if (phase === 'idle') phase = 'forming';
      const d = decide();
      return { ...d, phase };
    },

    /**
     * `U3E-8.5` said the utterance ended. THIS is what starts a generation —
     * never a partial.
     */
    settle() {
      const t = text();
      if (!t) { phase = 'idle'; return { act: ACT.HOLD, text: '', epoch, phase }; }
      if (phase === 'generating') return decide();
      phase = 'generating';
      epoch++;
      runText = t;
      runStartedAt = now();
      log.runs++;
      return { act: ACT.RUN, text: t, epoch, phase };
    },

    /**
     * A generation came back. ⛔ The caller MUST pass the epoch it was started
     * with: a reply from an aborted generation is not an answer to the current
     * utterance, and rendering it is exactly the stale answer `8.6` forbids.
     */
    accept(replyEpoch) {
      if (replyEpoch !== epoch) return { stale: true, epoch, replyEpoch };
      phase = 'idle';
      recognised = '';
      amendments = [];
      runText = null;
      return { stale: false, epoch };
    },

    /** Abandon whatever is pending — the caller cancelled, or the mic stopped. */
    reset() {
      phase = 'idle'; recognised = ''; amendments = []; runText = null; epoch++;
    },

    text,
    phase: () => phase,
    epoch: () => epoch,

    /**
     * ⛔ For diagnostics (`U3E-8.11`). Reports the DISTRIBUTION of how late
     * invalidations landed, not a mean — a mean of staleness is the same lie as
     * a mean of GPU utilisation, and this project has already been bitten by
     * that one (`train/saturation.py`, mean 82.8% hiding two 88 s stalls).
     */
    stats() {
      const s = log.stalenessMs.slice().sort((a, b) => a - b);
      return {
        ...log,
        stalenessMs: undefined,
        staleness: s.length
          ? { n: s.length, min: s[0], median: s[(s.length - 1) >> 1], max: s[s.length - 1] }
          : { n: 0 },
        note: 'aborts are HEALTHY — they are amendments arriving in time to matter.',
      };
    },
  };
}
