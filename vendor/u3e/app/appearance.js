/**
 * appearance.js — `U3E-9.2` / `9.3` / `9.4` / `9.6` and `U3E-9B.1` / `9B.2` / `9B.4`.
 *
 * The conditioning schema: three independent axes, resolved from speech.
 *
 * ⛔ THREE AXES, AND COLLAPSING ANY TWO IS THE BUG
 *   IDENTITY      — that she is Unity. Never varies. Not represented here at
 *                   all, because anything representable is something that can
 *                   be accidentally changed.
 *   MANIFESTATION — base / girlfriend / housewife / kittycat. Switches on
 *                   request, persists, carries a body and an age.
 *   APPEARANCE    — outfit, hair, pose, action, setting, framing, lighting,
 *                   mood. Free WITHIN a manifestation.
 *
 *   ⚠ Manifestation is NOT a costume. Fold it into appearance and she becomes a
 *   different woman in each form; fold it into identity and she can never change
 *   form. The whole reason it is its own axis is that neither of those is what
 *   was asked for.
 *
 * ⛔ UNFILLED SLOTS STAY UNFILLED
 *   The single most likely way this ships broken is defaulting an unspecified
 *   slot to "her usual" — which is precisely how "she only ever appears in her
 *   one outfit" reasserts itself through a system built to prevent it. A slot
 *   nobody set is absent, and absent is not the same as default.
 *
 * ⛔ EVERY CODE-CONTRIBUTED WORD IS ATTRIBUTABLE (`U3E-9.6`)
 *   Inherited scar: one project's whole minds-eye went neon-green because a
 *   style word rode along on every prompt and nothing declared it. Here, every
 *   string this file contributes carries its origin, and `provenance()` lists
 *   them for the diagnostics panel. If the code adds a word to her appearance,
 *   that word is visible.
 *
 * ⛔ PLATFORM LAW: zero dependencies, no `node:` imports.
 */

/**
 * ⛔ NO FORM CARRIES A HARD-SET AGE. Age is the USER'S to call.
 *
 * THE RULE: age is never hard-set. The speaker can name any age for any form —
 * a cat manifestation is not obliged to be 22.
 *
 * ⚠ I briefly hardcoded an age onto each form here (25/22/34/23) and it was the
 * same pre-programmed mistake as the word lists — a map deciding something the
 * speaker is entitled to decide. Removed. **Age is an appearance slot**, set by
 * what was said, exactly like outfit or pose.
 *
 * ⭐ The steering problem it was solving is real and still handled, just not by
 * a constant. A generator resolves an UNDER-SPECIFIED request from its own
 * prior — the sibling project measured that drift going **toward children** for
 * bare person words, and the generic word "adult" was observed drifting
 * **toward old**. So when the speaker HAS named an age, that wins outright;
 * when nobody has, one positive fallback applies and it is labelled
 * code-authored like every other term the code contributes.
 */
export const MANIFESTATIONS = {
  base:      { id: 'base',      label: 'Unity',      note: 'base form' },
  girlfriend:{ id: 'girlfriend',label: 'girlfriend', note: 'girlfriend manifestation' },
  housewife: { id: 'housewife', label: 'housewife',  note: 'housewife manifestation' },
  kittycat:  { id: 'kittycat',  label: 'kittycat',   note: 'catgirl manifestation' },
};

/** Used ONLY when nothing was said about age. The chosen fallback is 18-19. */
export const AGE_FALLBACK = '18-19 year old';

/** Escalation is a STATE, not a mode — it persists and it is visible. */
export const INTENSITY = ['calm', 'default', 'escalated'];

/**
 * The slots. ⛔ ORDER IS LOAD-BEARING.
 * Position in the conditioning is not cosmetic: attributes buried at the tail
 * get overruled. Carried from the weird project, where the directive was
 * "agressively positioning that part so it isnt melted in at the end".
 * Earlier = harder to ignore.
 */
export const SLOTS = [
  'manifestation',   // 1 — who she is being
  'age',             // 2 — ⛔ SAID, never hard-set by a form: the speaker can
                     //     call any age for any manifestation.
  'body',            // 3 — form-carried body facts (ears, tail)
  'outfit',          // 3
  'hair',            // 4
  'pose',            // 5
  'action',          // 6
  'setting',         // 7
  'lighting',        // 8
  'framing',         // 9
  'mood',            // 10
];

/** A slot's value plus WHERE it came from. Provenance is not optional. */
function slotValue(text, origin) {
  return { text, origin };   // origin: 'said' | 'persisted' | 'form' | 'code'
}

/**
 * ⛔ THE ONLY PLACE CODE MAY CONTRIBUTE WORDS, and each is labelled.
 * `U3E-9.8`: age steering is POSITIVE, never a negative prompt. Measured in the
 * sibling project with pinned seeds — a generator's own prior drags unqualified
 * person words toward children, and "dont negative prompt it away find whats
 * doing it" was the correction. This is the positive fix.
 */
const CODE_TERMS = {
  // ⛔ TWO WRONG VERSIONS OF THIS LIVED HERE, both worth recording.
  //   (1) The generic word "adult", which reliably returns much older people.
  //       A generic age word is under-specification and the generator fills it
  //       from its prior.
  //   (2) A hard-set age per manifestation — a map deciding what the speaker is
  //       entitled to decide.
  //   ⭐ Now: this fires ONLY when nothing was said about age, so it steers the
  //   under-specified case and never overrides a person who spoke.
  age: () => ({
    text: AGE_FALLBACK,
    why: 'U3E-9.8 positive steering, and ONLY when no age was said; never a negation',
  }),
};

/** Body facts a manifestation carries. ⚠ These are BODY, not outfit. */
const FORM_BODY = {
  base:       null,
  girlfriend: 'freckles',
  housewife:  null,
  kittycat:   'cat ears and tail',
};

/**
 * Speech -> slots. `U3E-9.2`: appearance changes because you asked, in words.
 * ⛔ No pickers, no presets, no outfit menu.
 *
 * ⚠ Deliberately NOT a general parser. It recognises the shapes people actually
 * use and leaves everything else alone, because a greedy parser that guesses
 * wrong writes a slot the speaker never set — and a wrongly-filled slot is worse
 * than an empty one, since empty is visibly empty.
 */
/**
 * ⛔⛔ THIS WHOLE PARSER IS A STOPGAP AND IT IS SCHEDULED FOR DELETION.
 *
 * ⛔ THE LAW IT BREAKS: nothing is pre-programmed. It is built dynamically in
 * the moment, never read off a list.
 *
 * ⛔ **That is right, and it had already been established once.** I briefly added
 * `POSE_WORDS` and `FRAMING_WORDS` as hardcoded arrays here. They are gone. The
 * sibling project killed every word-list-as-classifier after three separate
 * corrections and replaced them with live lexical evidence; importing that
 * mistake into this repo was a regression, not a design.
 *
 * ⭐ **THE REAL MECHANISM IS LEARNED, NOT PARSED.** This model trains on
 * caption -> field pairs. She will understand "wearing a red dress standing in
 * a garden" because those words co-occurred with those coefficients thousands
 * of times — not because a regex matched. ⛔ **The conditioning is the
 * utterance.** Every greedy-parser bug this file has hosted (`pose = "in a
 * kitchen"`, `outfit = "kitchen"`, `setting = "lingerie"` — three instances in
 * one loop) is a symptom of parsing at all, and no amount of pattern-narrowing
 * removes the class.
 *
 * ⚠ **What survives the deletion is the SLOT STRUCTURE, and it is not a
 * parser.** Identity / manifestation / appearance orthogonality is what fixes
 * "only ever appears in her one outfit", and it is a property of **how the
 * corpus is captioned** (`caption_voice` in `datatools/taxonomy.json`) — the axes are
 * because the training captions carry them. That is `U3E-9.3` done dynamically.
 *
 * **Until the model exists, this file gives the surfaces something to run
 * against** — that is its entire remaining job, exactly like `serve/stand-in.js`
 * gives the app a model-shaped hole to talk to. It must never be mistaken for
 * the design. See `U3E-9.9`.
 */

const PATTERNS = [
  // ⭐ AGE, FIRST — so span-consumption gives it priority and no later pattern
  //   can swallow the number. The speaker can call any age for any form, so this
  //   matches a numeric SHAPE, not a vocabulary list — nothing here is
  //   pre-programmed about WHICH ages exist.
  [/\b(\d{1,3}\s*(?:-\s*\d{1,3}\s*)?(?:years?[- ]old|yr?s?[- ]old|yo)\b)/i, 'age'],
  [/\b(?:aged?|make (?:her|him|them))\s+(\d{1,3}(?:\s*-\s*\d{1,3})?)\b/i, 'age'],
  // ⛔ SECOND INSTANCE OF THE GREEDY-PARSER BUG, caught 2026-08-29 by running
  //   the resolver rather than reading it. The old alternation included bare
  //   `in a|in an|in her`, so "sitting in a kitchen" wrote **outfit = kitchen**
  //   — a place described as clothing, and `setting` got it too, so one phrase
  //   filled two slots with the same words. Exactly the failure already
  //   documented below for `pose` ("standing in a kitchen" -> pose = in a
  //   kitchen), in a pattern nobody re-checked afterwards.
  //   ⚠ **A wrongly-filled slot is worse than an empty one, because empty is
  //   visibly empty.** `in a` now only counts when it is anchored to dressing.
  // ⛔ SECOND INSTANCE OF THE GREEDY-PARSER BUG, caught 2026-08-29 by running
  //   the resolver rather than reading it. This alternation used to include
  //   bare `in a|in an|in her`, so "sitting in a kitchen" wrote
  //   **outfit = kitchen** — a place described as clothing — while `setting`
  //   captured the same words, so one phrase filled two slots wrongly. It is
  //   exactly the failure documented below for `pose` ("standing in a kitchen"
  //   -> pose = in a kitchen), living in a pattern nobody re-checked after
  //   fixing that one. **Defects travel in families; check the siblings.**
  //
  //   ⚠ The fix is to DELETE the ambiguous openers, not to special-case them
  //   with a list of garment words — that would be a word list doing a
  //   classifier's job, and it would still be wrong on the first garment nobody
  //   listed. "in a red dress" is now missed, and that is the correct trade:
  //   **a wrongly-filled slot is worse than an empty one, because empty is
  //   visibly empty** and the speaker can simply say "wearing a red dress".
  [/\b(?:wear(?:ing)?|put on|dressed in|dressed as)\s+([^.,;]{2,60})/i, 'outfit'],
  [/\bhair\s+(?:is\s+|in\s+)?([^.,;]{2,40})/i, 'hair'],
  // ⛔ Captures the POSTURE WORD ONLY, not the trailing phrase.
  //   The first version was `standing\b([^.,;]{0,40})` and on "standing in a
  //   kitchen" it wrote `pose: in a kitchen` — duplicating `setting` and
  //   describing a place as a body position. Caught by running it. A greedy
  //   pattern fills a slot the speaker never set, and a wrongly-filled slot is
  //   worse than an empty one because empty is visibly empty.
  [/\b(standing|sitting|lying down|lying|kneeling|leaning|crouching|reclining|walking|running|dancing)\b/i, 'pose'],
  [/\b(?:in|at|on)\s+(?:the\s+|a\s+|an\s+)?([a-z][^.,;]{2,40})/i, 'setting'],
  [/\b(?:lit by|lighting|light)\s+([^.,;]{2,40})/i, 'lighting'],
  [/\b(?:close[- ]?up|wide shot|full body|portrait|from behind|from the side)\b/i, 'framing'],
  [/\b(?:looking|feeling|seems?)\s+([a-z]{3,20})\b/i, 'mood'],
];

const MANIFEST_WORDS = [
  [/\b(girlfriend|as my girlfriend)\b/i, 'girlfriend'],
  [/\b(housewife|domestic)\b/i, 'housewife'],
  [/\b(kitty ?cat|catgirl|kitten)\b/i, 'kittycat'],
  [/\b(base form|normal|just unity|yourself)\b/i, 'base'],
];

const INTENSITY_WORDS = [
  [/\b(wild|feral|strict|rough|intense)\b/i, 'escalated'],
  [/\b(sweet|cozy|purr|calm down|settle)\b/i, 'calm'],
];

/**
 * Resolve one utterance against the state in force.
 *
 * @param said     the utterance
 * @param current  the appearance in force (from the turn list — see state.js)
 * @returns { slots, manifestation, intensity, changed[] } or null if nothing
 *          in the utterance was about appearance at all.
 */
export function resolve(said, current) {
  const text = String(said || '');
  const prev = current || { slots: {}, manifestation: 'base', intensity: 'default' };
  const next = {
    slots: { ...(prev.slots || {}) },
    manifestation: prev.manifestation || 'base',
    intensity: prev.intensity || 'default',
  };
  const changed = [];

  // ── reset, in a word (U3E-9.4) ─────────────────────────────────────────────
  if (/\b(back to normal|as you were|reset your look|forget the outfit)\b/i.test(text)) {
    return {
      slots: {}, manifestation: 'base', intensity: 'default',
      changed: ['reset'],
    };
  }

  // ── manifestation (U3E-9B.2) ───────────────────────────────────────────────
  for (const [re, id] of MANIFEST_WORDS) {
    if (re.test(text)) {
      if (next.manifestation !== id) {
        next.manifestation = id;
        changed.push('manifestation');
        // ⛔ Switching form clears form-CARRIED body facts, and nothing else.
        //   A catgirl's ears are body; the dress she was wearing is not, and
        //   silently discarding it would be the "manifestation as costume"
        //   mistake in the opposite direction.
        delete next.slots.body;
      }
      break;
    }
  }

  // ── intensity as a persisting state (U3E-9B.4) ─────────────────────────────
  for (const [re, level] of INTENSITY_WORDS) {
    if (re.test(text)) {
      if (next.intensity !== level) { next.intensity = level; changed.push('intensity'); }
      break;
    }
  }

  // ── appearance slots ───────────────────────────────────────────────────────
  //
  // ⛔ ONE SPAN, ONE SLOT — and this is a CHOKEPOINT fix, not a third patch.
  //
  //   The greedy-parser bug has now appeared three times in this one loop:
  //     1. "standing in a kitchen"      -> pose    = "in a kitchen"
  //     2. "sitting in a kitchen"       -> outfit  = "kitchen"
  //     3. "dressed in lingerie"        -> setting = "lingerie"
  //   Each was fixed by narrowing the offending pattern, and the next pattern
  //   in the list then made the same mistake on different words. **Defects
  //   travel in families and patching instances never ends** — every pattern
  //   here is free to re-consume text an earlier one already claimed.
  //
  //   So the rule moves to where all of them converge: a pattern may not claim
  //   a span that an earlier, higher-priority slot already took. SLOT ORDER IS
  //   ALREADY LOAD-BEARING (see SLOTS above — earlier means harder to ignore),
  //   so it is the natural priority, and no per-pattern special-casing is
  //   needed.
  //
  // ⚠ Overlap is judged on the CAPTURED value's position, not the whole match,
  //   because a match legitimately includes its trigger word ("wearing …") and
  //   that trigger is not part of what any other slot would want.
  const taken = [];   // [start, end) spans already claimed
  const overlaps = (s, e) => taken.some(([a, b]) => s < b && e > a);

  for (const [re, slot] of PATTERNS) {
    const m = text.match(re);
    if (!m) continue;
    const val = (m[1] || m[0] || '').trim();
    if (!val || val.length < 2) continue;

    // where the captured value actually sits in the utterance
    const at = m[1] ? text.indexOf(m[1], m.index) : m.index;
    const start = at < 0 ? m.index : at;
    const end = start + val.length;
    if (overlaps(start, end)) continue;      // ⛔ an earlier slot owns these words

    if (next.slots[slot] && next.slots[slot].text === val) { taken.push([start, end]); continue; }
    next.slots[slot] = slotValue(val, 'said');
    taken.push([start, end]);
    changed.push(slot);
  }

  if (!changed.length) return null;

  // form-carried body, re-applied after any manifestation change
  const body = FORM_BODY[next.manifestation];
  if (body) next.slots.body = slotValue(body, 'form');

  return next;
}

/**
 * Build the ordered conditioning the model receives.
 * ⛔ Slots that were never set are ABSENT — not defaulted, not guessed.
 */
export function conditioning(appearance) {
  const a = appearance || { slots: {}, manifestation: 'base', intensity: 'default' };
  const out = [];
  const m = MANIFESTATIONS[a.manifestation] || MANIFESTATIONS.base;

  out.push({ slot: 'manifestation', text: m.note, origin: 'form' });
  // ⛔ AGE: what was SAID wins outright. The code term fires only when nobody
  //   named one, so it steers the under-specified case without ever overruling
  //   a person who spoke. See CODE_TERMS for the two wrong versions of this.
  const saidAge = a.slots && a.slots.age;
  if (saidAge && saidAge.text) {
    out.push({ slot: 'age', text: saidAge.text, origin: saidAge.origin || 'said' });
  } else {
    const age = CODE_TERMS.age();
    out.push({ slot: 'age', text: age.text, origin: 'code', why: age.why });
  }

  for (const s of SLOTS) {
    // both handled above — manifestation from the form, age from said-or-steer
    if (s === 'manifestation' || s === 'age') continue;
    const v = a.slots && a.slots[s];
    if (v && v.text) out.push({ slot: s, text: v.text, origin: v.origin });
  }
  if (a.intensity && a.intensity !== 'default') {
    out.push({ slot: 'intensity', text: a.intensity, origin: 'said' });
  }
  return out;
}

/**
 * `U3E-9.6` — everything the CODE contributed, for the settings diagnostics.
 * ⭐ If the code adds a word to her appearance, that word is visible here. That
 * is the whole guard: a project lost a day to a style word nobody had declared.
 */
export function provenance(appearance) {
  const cond = conditioning(appearance);
  return {
    // ⚠ The reason rides ON the term now, rather than being looked up by the
    //   term's TEXT. The old lookup keyed on the word itself, so the moment the
    //   age term stopped being the literal string "adult" every code term would
    //   have reported as `unlabelled` — the bug detector would have fired on the
    //   fix. A label that breaks when the thing it labels changes is not a label.
    codeAuthored: cond.filter(c => c.origin === 'code')
      .map(c => ({ slot: c.slot, text: c.text, why: c.why || 'unlabelled' })),
    formCarried: cond.filter(c => c.origin === 'form').map(c => ({ slot: c.slot, text: c.text })),
    said: cond.filter(c => c.origin === 'said').map(c => ({ slot: c.slot, text: c.text })),
    // ⛔ An unlabelled code term is a bug, and it is surfaced rather than hidden.
    unlabelled: cond.filter(c => c.origin === 'code' && !c.why).length,
  };
}

/** One-line summary for the transcript, so a rewind can see what was in force. */
export function summarise(appearance) {
  if (!appearance) return null;
  const parts = [];
  const m = MANIFESTATIONS[appearance.manifestation];
  if (m && m.id !== 'base') parts.push(m.label);
  if (appearance.intensity && appearance.intensity !== 'default') parts.push(appearance.intensity);
  for (const s of SLOTS) {
    const v = appearance.slots && appearance.slots[s];
    if (v && v.text) parts.push(`${s}: ${v.text}`);
  }
  return parts.length ? parts.join(' · ') : null;
}
