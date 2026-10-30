/**
 * latency.js — `U3E-8.10`. Speech end -> her first sound, broken down by stage.
 *
 * ⛔ WHY THIS IS A ROW AND NOT A NICETY
 *   Conversation is a LATENCY PRODUCT. Past roughly a second of dead air an orb
 *   stops feeling alive however good the voice is, and no amount of model
 *   quality buys that back. A single end-to-end number cannot be acted on —
 *   only a breakdown tells you which stage to fix.
 *
 * ⛔ ABSENT STAGES ARE LISTED, NOT OMITTED.
 *   STT (`U3E-4B.3`) and voice-out (`U3E-3.5`) do not exist yet. A breakdown
 *   that silently skipped them would report a flatteringly small total and
 *   imply the budget is nearly met — when in fact the two stages most likely to
 *   dominate have never run. They appear with `absent: true` and are excluded
 *   from the total, and the total says so.
 *
 * ⚠ AND THE ENDPOINT SILENCE IS COUNTED, because it is real dead air.
 *   `U3E-8.5`'s silence timer (default 900 ms) is time the person spends
 *   waiting after they stopped talking. It is the single largest known cost in
 *   the whole chain today and it is a TUNING CHOICE, not a physical limit —
 *   which is exactly the kind of thing a breakdown exists to make visible.
 *
 * ⛔ PLATFORM LAW: no dependencies, `performance.now()` only. Runs on the S23.
 */

/** The stages, in the order a turn passes through them. */
export const STAGES = [
  { id: 'endpoint', label: 'silence before she answers', absent: false },
  // ⚠ `U3E-8.32` — `row` is RENDERED (`${s.id} (${s.row})`), so it says why the
  //   stage is absent in plain words instead of naming an internal board row.
  { id: 'stt', label: 'transcription', absent: true, row: 'awaiting the trained model' },
  { id: 'compose', label: 'turn assembled', absent: false },
  { id: 'wire', label: 'request -> first byte', absent: false },
  { id: 'model', label: 'her answer', absent: false },
  { id: 'speak', label: 'voice out', absent: true, row: 'awaiting the trained model' },
];

const CAP = 32;

export function createLatency() {
  let open = null;
  const history = [];

  return {
    /** A turn begins. `endpointMs` is the silence already spent (U3E-8.5). */
    begin(endpointMs = 0) {
      open = { at: Date.now(), t0: performance.now(), marks: {}, endpointMs };
      return open;
    },

    /** Stage `id` has just finished. */
    mark(id) {
      if (!open) return;
      open.marks[id] = performance.now() - open.t0;
    },

    /**
     * The turn is done. Returns the breakdown.
     * ⚠ Deltas, not cumulative marks — a cumulative list looks like a breakdown
     * and answers a different question, and mistaking one for the other is how
     * a slow stage hides behind an earlier one.
     */
    end() {
      if (!open) return null;
      const order = ['compose', 'wire', 'model'];
      const rows = [];
      let prev = 0;
      if (open.endpointMs) rows.push({ id: 'endpoint', ms: open.endpointMs });
      for (const id of order) {
        if (open.marks[id] == null) continue;
        rows.push({ id, ms: Math.max(0, open.marks[id] - prev) });
        prev = open.marks[id];
      }
      const measured = rows.reduce((a, r) => a + r.ms, 0);
      const rec = {
        at: open.at,
        rows,
        measuredMs: measured,
        // ⛔ Named, so the total is never read as complete.
        absent: STAGES.filter(s => s.absent).map(s => ({ id: s.id, row: s.row })),
      };
      history.unshift(rec);
      if (history.length > CAP) history.length = CAP;
      open = null;
      return rec;
    },

    /** For the `U3E-8.11` diagnostics panel. */
    report() {
      if (!history.length) return { n: 0, note: 'no turns measured yet' };
      const byStage = new Map();
      for (const h of history) {
        for (const r of h.rows) {
          if (!byStage.has(r.id)) byStage.set(r.id, []);
          byStage.get(r.id).push(r.ms);
        }
      }
      const stat = (a) => {
        const s = a.slice().sort((x, y) => x - y);
        return {
          n: s.length,
          median: Math.round(s[(s.length - 1) >> 1]),
          // ⚠ Worst case, not mean. A mean hides the turn that felt broken, and
          //   the felt experience of a conversation is set by its worst pauses.
          max: Math.round(s[s.length - 1]),
        };
      };
      const stages = [...byStage.entries()].map(([id, a]) => ({ id, ...stat(a) }));
      const totals = history.map(h => h.measuredMs);
      return {
        n: history.length,
        stages,
        total: stat(totals),
        absent: STAGES.filter(s => s.absent).map(s => `${s.id} (${s.row})`),
        note: 'MEASURED stages only. STT and voice-out have never run, and they ' +
              'are the two most likely to dominate — this total is a floor.',
      };
    },
  };
}
