/**
 * state.js — the conversation, the gallery, and the settings.
 *
 * ⛔ THE ARCHITECTURE IS FORCED BY ONE REQUIREMENT (`U3E-8.14`)
 *   THE REQUIREMENT: any past input can be edited, everything after it resets,
 *   and generation continues from that edit.
 *
 *   Editing any past turn and re-running from there is only possible if the
 *   conversation is an **ordered, replayable list** and generation is a **pure
 *   function of the prefix before it**. So there is no hidden state accumulated
 *   anywhere else — no running summary, no sticky flags outside the list, no
 *   "current appearance" variable that survives a rewind. If any existed, a
 *   rewind would produce something the prefix cannot explain, and it would look
 *   like the model misbehaving rather than like our bug.
 *
 *   ⭐ That is why appearance (`U3E-9.4`) lives ON turns rather than beside
 *   them: rewinding the conversation rewinds what she is wearing, automatically,
 *   because there is nowhere else for it to hide.
 *
 * ⛔ PLATFORM LAW: zero dependencies. Persists to localStorage, which the S23
 * has as much as the desktop.
 */

const LS_KEY = 'u3e.state.v1';

/** A turn: { id, role:'user'|'unity', text, at, appearance?, artId?, audioId? } */

/**
 * ⛔ THE HISTORY BUDGET EXISTS TO PROTECT THE SYSTEM MESSAGE. See `prefixFor`.
 *
 * Measured against the real deployment: her canon is ~42,000 characters and the
 * window is 32,768 tokens (~130,000 characters). Persona ~10.5k tokens leaves
 * roughly 22k for everything else — history, her reply, and any image line.
 * 40,000 characters of history is about a third of that, which is deliberate
 * headroom rather than a tight fit: a budget that only just works is one long
 * reply away from evicting the persona again.
 *
 * ⚠ Whatever runs behind the slot later has a different window. This number is
 *   a property of the DEPLOYMENT, not of the app — revisit it when the trained
 *   model lands, and re-measure rather than assuming it grew.
 */
const HISTORY_BUDGET = 40000;

export function createStore() {
  let lastTrim = 0;
  let state = load() || {
    turns: [],
    gallery: [],          // { id, prompt, style, at, coefficients, w, h, turnId, orphaned }
    settings: defaults(),
    lastDiscarded: null,  // one step of undo for U3E-8.14's destructive rewind
    nextId: 1,
  };
  const listeners = new Set();

  function defaults() {
    return {
      // personal
      name: '',
      // voice & listening
      micEnabled: false,
      vadSensitivity: 0.5,
      endpointSilenceMs: 900,
      bargeIn: true,
      // vision
      cameraEnabled: false,      // ⛔ off by default, always
      // model & serving
      endpoint: '',              // blank = same origin
      resolution: 512,
      // viewer
      snapToPlane: true,
      // gallery
      galleryCap: 500,
    };
  }

  function load() {
    try {
      const raw = localStorage.getItem(LS_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }

  function persist() {
    try { localStorage.setItem(LS_KEY, JSON.stringify(state)); }
    catch (e) { /* quota — the session still works, it just will not survive reload */ }
  }

  function emit() { persist(); for (const fn of listeners) fn(state); }

  return {
    subscribe(fn) { listeners.add(fn); fn(state); return () => listeners.delete(fn); },
    get() { return state; },

    // ── turns ────────────────────────────────────────────────────────────────
    addTurn(role, text, extra = {}) {
      const t = { id: state.nextId++, role, text, at: Date.now(), ...extra };
      state.turns.push(t);
      emit();
      return t;
    },

    updateTurn(id, patch) {
      const t = state.turns.find(x => x.id === id);
      if (t) { Object.assign(t, patch); emit(); }
      return t;
    },

    /**
     * ⛔ THE DESTRUCTIVE ONE. Edit turn `id`, discard everything after it.
     *
     * Everything after the edit resets — and that includes ARTIFACTS. Images made
     * after the edited turn belong to a history that no longer happened. They
     * are not deleted silently: they are marked `orphaned` in the gallery, so
     * the work is still there and honestly labelled rather than vanishing.
     *
     * Returns what WILL be lost so the caller can confirm before committing —
     * `commit: false` is a dry run.
     */
    rewindTo(id, newText, commit = false) {
      const idx = state.turns.findIndex(t => t.id === id);
      if (idx < 0) return null;
      const lost = state.turns.slice(idx + 1);
      const orphanedArt = state.gallery.filter(g => lost.some(t => t.id === g.turnId));
      if (!commit) return { turnsLost: lost.length, artOrphaned: orphanedArt.length };

      // one step of undo — a thumb on a phone should not be able to erase a
      // branch with no way back
      state.lastDiscarded = {
        at: Date.now(),
        fromIndex: idx + 1,
        turns: JSON.parse(JSON.stringify(lost)),
        editedTurn: JSON.parse(JSON.stringify(state.turns[idx])),
      };

      state.turns[idx].text = newText;
      state.turns[idx].editedAt = Date.now();
      state.turns.length = idx + 1;
      for (const g of orphanedArt) g.orphaned = true;
      emit();
      return { turnsLost: lost.length, artOrphaned: orphanedArt.length };
    },

    undoRewind() {
      const d = state.lastDiscarded;
      if (!d) return false;
      state.turns.length = d.fromIndex - 1;
      state.turns.push(d.editedTurn, ...d.turns);
      for (const g of state.gallery) {
        if (d.turns.some(t => t.id === g.turnId)) g.orphaned = false;
      }
      state.lastDiscarded = null;
      emit();
      return true;
    },

    /** The prefix a generation is a pure function of. */
    /**
     * ⛔⛔ THE HISTORY IS CAPPED, AND IT IS CAPPED TO SAVE HER PERSONA.
     *
     * Caught from use: she suddenly answered with "Hello there, I'm happy to
     * assist you with your request. Please remember to always be responsible and
     * respectful in your interactions." — that is the bare base model with no
     * persona at all.
     *
     * ⛔ THE CAUSE IS EVICTION, NOT CORRUPTION. This function used to return the
     *   ENTIRE conversation, every turn ever, persisted across reloads. Her
     *   canon is ~42,000 characters — about 10.5k tokens — and it is sent as the
     *   FIRST message on every turn. When persona + history exceeds the context
     *   window, the runtime truncates FROM THE FRONT, so **the first thing
     *   discarded is the persona**. She does not degrade gradually; she vanishes,
     *   and what answers is the base model's safety voice.
     *
     * ⚠ IT NEVER SHOWED UP IN TESTING because a test sends one message. This
     *   only appears after a real conversation has run a while — which is
     *   exactly when it is hardest to attribute.
     *
     * ⭐ So the recent window is bounded in characters, keeping the NEWEST turns
     *   and dropping the oldest. `HISTORY_BUDGET` is deliberately well under the
     *   space left by the persona, because the reply and any image line have to
     *   fit too.
     */
    prefixFor(turnId) {
      const idx = state.turns.findIndex(t => t.id === turnId);
      const upto = idx < 0 ? state.turns : state.turns.slice(0, idx + 1);
      const msgs = upto.map(t => ({ role: t.role === 'unity' ? 'assistant' : 'user', content: t.text }));

      let budget = HISTORY_BUDGET;
      const kept = [];
      for (let i = msgs.length - 1; i >= 0; i--) {
        const cost = (msgs[i].content || '').length + 8;
        if (kept.length && cost > budget) break;   // always keep at least the last turn
        budget -= cost;
        kept.unshift(msgs[i]);
      }
      lastTrim = msgs.length - kept.length;
      return kept;
    },

    /** ⚠ How many turns the last send dropped. Reported, never silent. */
    trimmedTurns() { return lastTrim; },

    /** Appearance in force at a point — read from the LIST, never from a variable. */
    appearanceAt(turnId) {
      const idx = turnId == null ? state.turns.length - 1 : state.turns.findIndex(t => t.id === turnId);
      for (let i = Math.min(idx, state.turns.length - 1); i >= 0; i--) {
        if (state.turns[i].appearance) return state.turns[i].appearance;
      }
      return null;
    },

    // ── gallery (U3E-8.12) ───────────────────────────────────────────────────
    /**
     * ⭐ Stores the FIELD, not a PNG. Kilobytes instead of megabytes, so a long
     * history is affordable on a phone, and every entry can be re-rendered at
     * whatever resolution the device wants instead of being frozen at the size
     * it was made.
     */
    addArt(entry) {
      const g = { id: state.nextId++, at: Date.now(), orphaned: false, ...entry };
      state.gallery.unshift(g);
      // ⚠ Bounded, and the bound is STATED in settings — never a silent
      // eviction that makes her look like she forgot.
      const cap = state.settings.galleryCap;
      if (state.gallery.length > cap) state.gallery.length = cap;
      emit();
      return g;
    },

    deleteArt(id) {
      state.gallery = state.gallery.filter(g => g.id !== id);
      emit();
    },

    /** ⛔ Irreversible. The caller MUST confirm first. */
    clearGallery() { state.gallery = []; emit(); },

    /**
     * Clear the CONVERSATION and keep her pictures.
     *
     * ⭐ `U3E-8.12` gave the gallery its own clear controls and the transcript
     *   had none — the only way to empty a chat was `clearAll()`, which takes
     *   the pictures with it. **Those are different intentions and conflating
     *   them costs work that cannot be got back.**
     *
     * ⛔ HER ART IS ORPHANED, NEVER DELETED. Exactly what `rewindTo` does: a
     *   picture whose turn is gone is still a picture she made, so it is
     *   labelled rather than vanished. ⚠ Silently deleting her work as a
     *   side-effect of clearing text would be the destructive-by-accident
     *   failure `U3E-8.12` was written against.
     *
     * ⭐ It reuses `lastDiscarded`, so the SAME one-step undo that covers a
     *   rewind covers this — a thumb on a phone should not be able to erase a
     *   conversation with no way back.
     *
     * ⛔ Irreversible beyond that one step. The caller MUST confirm first.
     */
    clearTurns() {
      const lost = state.turns;
      const orphanedArt = state.gallery.filter(g => lost.some(t => t.id === g.turnId));
      state.lastDiscarded = {
        turns: JSON.parse(JSON.stringify(lost)),
        at: Date.now(),
        reason: 'chat cleared',
      };
      for (const g of orphanedArt) g.orphaned = true;
      state.turns = [];
      emit();
      return { turnsLost: lost.length, artOrphaned: orphanedArt.length };
    },

    // ── settings ─────────────────────────────────────────────────────────────
    setSetting(k, v) { state.settings[k] = v; emit(); },
    resetSettings() { state.settings = defaults(); emit(); },

    /** ⛔ Irreversible. The caller MUST confirm first. */
    clearAll() {
      state = { turns: [], gallery: [], settings: state.settings, lastDiscarded: null, nextId: 1 };
      emit();
    },
  };
}
