/**
 * serve/image-prompt.js — the rules that turn what somebody TYPED into what an
 * image generator is actually sent. `U3E-5.53` ①.
 *
 * ⛔⛔ WHY THIS FILE EXISTS: IT HAS TO HAVE EXACTLY ONE OWNER.
 *   Every rule below was found by generating a picture and LOOKING at it, and
 *   each one cost a real debugging session — the leathers on every nude request,
 *   the substance rendered as scenery, `dark` read as an exposure instruction,
 *   her name dragging a diffusion model toward a game engine. ⚠ They lived
 *   inside `serve/legacy-adapter.js`, which is a **development harness whose own
 *   header says "delete this file the day `U3E-4.6` lands"**.
 *
 *   ⭐ The moment a SECOND image backend arrived (`serve/pollinations.js`) that
 *   became a live problem in two directions at once: importing them from a file
 *   marked for deletion makes the deletion break the new backend, and copying
 *   them makes two divergent copies of rules that were each paid for once.
 *   **Fix the chokepoint, not the instance.** So they moved here, verbatim, and
 *   the harness now imports them like everyone else.
 *
 * ⚠ WHAT THIS FILE IS NOT: it is not for the TRAINED model. She will learn
 *   conditioning from a corpus captioned with it (`U3E-9.9`: the conditioning IS
 *   the utterance). These rules exist because a DIFFUSION model reads a
 *   description of a finished picture and cannot take an instruction — which is
 *   a fact about them, not about her.
 *
 * ⛔ PLATFORM: `node:fs` only, for the taxonomy. Nothing the browser loads may
 *   import this.
 */

import { readFileSync } from 'node:fs';
/**
 * ⭐⭐ `U3E-9.1` — THE PRONOUNS COME FROM THE PROFILE, NOT FROM THIS FILE.
 *   Gee: *"from renaming her even to her being a guy named jjohn"*. Seventeen
 *   gendered words reached the image model from here; every one is a lookup now,
 *   so the same prompt renders correctly for any profile.
 * ⚠ Resolved ONCE at module load: an image request must not change who the
 *   subject is halfway through a batch.
 * ⚠ The literal fallback is kept for the case where `datatools/persona.json` is
 *   absent — this file must still produce a prompt, and behaving exactly as it
 *   did before is the only safe thing to do when nobody has said who she is.
 */
import { persona as u3ePersona } from './persona.mjs';
const P = u3ePersona();
const PR = P.ok ? P.pronouns
  : { subject: 'she', object: 'her', possessive: 'her', possessivePronoun: 'hers', reflexive: 'herself' };
const NOUN = P.ok ? P.nouns : { person: 'woman', youngPerson: 'girl', adjective: 'female' };

/**
 * Her look, read from the corpus's own `persona` field so every backend steers
 * with the same words the training data was collected under. ⚠ Absent is
 * tolerated: a missing taxonomy must not stop the app booting — it degrades to
 * the prompt as given, which is visible in the picture rather than hidden in a
 * flag.
 */
const TAX = (() => {
  try { return JSON.parse(readFileSync(new URL('../data/taxonomy.json', import.meta.url), 'utf8')); }
  catch { return {}; }
})();

/**
 * ⛔ IDENTITY IS ALWAYS SENT. ATTIRE ONLY WHEN THE REQUEST IS SILENT ABOUT IT.
 *
 * Reported from use: asking for a different outfit, or none at all, still
 * produced her in the canon leathers every time.
 *
 * The whole `persona` string was appended to every picture of her, and it ends
 * "black leather and fishnets by default" — so "nude" and "black leather" went
 * to the generator together and the default won. ⚠ `persona_note` in the
 * taxonomy already said attire is a FREE VARIABLE; the code appended the
 * definition regardless.
 */
export const PERSONA = TAX.persona_identity || TAX.persona || '';
export const PERSONA_ATTIRE = TAX.persona_attire || '';

/**
 * ⭐ THE GARMENT VOCABULARY IS THE TAXONOMY'S OWN, not a list of clothes I wrote.
 *   Every `outfits` cell plus the nude and explicit cells already name what
 *   people wear and do not wear, in their `queries` — the same words the corpus
 *   was collected under. So "does this request specify attire" is answered by
 *   the corpus, and it grows when the corpus does.
 */
const ATTIRE_WORDS = (() => {
  const out = new Set(['nude', 'naked', 'topless', 'bottomless', 'undressed', 'clothed', 'wearing', 'dressed']);
  /**
   * ⚠ THE `outfits` GROUP ONLY, plus the seeded nudity words above.
   *   Pulling the whole `adult` group was tried and MEASURED WRONG: it carries
   *   poses and acts as well as garments, so "standing" (from `act-positions`)
   *   made "standing in the rain" read as an attire request and suppressed her
   *   default outfit. The `outfits` group is garments by construction.
   */
  for (const c of TAX.cells || []) {
    const grp = c.group || '';
    if (grp !== 'outfits' && !/^unity-outfits$/.test(c.id)) continue;
    for (const q of [...(c.queries || []), c.label || '']) {
      for (const w of String(q).toLowerCase().split(/[^a-z0-9]+/)) {
        if (w.length > 3 && !/^(photo|photography|woman|women|girl|adult|range|full|closeup|shot|style|every|their|with)$/.test(w)) out.add(w);
      }
    }
  }
  return out;
})();

/**
 * ⛔ `U3E-8.30` — A SUBSTANCE ON HER BODY IS ALSO THE REQUEST SETTING WHAT IS ON
 *   HER BODY, and missing that dropped the substance from every such picture.
 *
 * Reported from use: telling her to cover herself in a liquid, or smear
 * something on herself, produced a picture with the substance missing — the
 * modifier was always dropped.
 *
 * ⭐ THE MECHANISM, and it is the leathers bug wearing a different coat: a
 *   covering is not a garment, so `ATTIRE_WORDS` never matched, so the default
 *   outfit — bra, micro skirt, leather, fishnets — was appended anyway. The
 *   prompt then said both *coated in something* AND *wearing a full outfit*, and
 *   a generator resolves that conflict by painting the clothes and dropping the
 *   coating. Same root cause as every picture coming back in her leathers:
 *   **a suffix describing the body competes with the request instead of tinting
 *   it.**
 *
 * ⚠ IT MATCHES THE CONSTRUCTION, NOT THE SUBSTANCE. What she can be covered in
 *   is unbounded and a list of it would be wrong the first time something new is
 *   named; the way English says it is a small closed set. STRONG participles
 *   stand alone because they cannot mean anything else on a body; the WEAK ones
 *   are ordinary verbs that need "in", "with" or "all over" before they mean a
 *   coating — otherwise "painted" catches a painted wall.
 */
const SURFACE_STRONG = /\b(soak(?:ed|ing)|drench(?:ed|ing)|dripping|glistening|slather(?:ed|ing)|smear(?:ed|ing)|coated|doused|lathered|sticky|oiled|greased|caked|splatter(?:ed|ing)|splash(?:ed|ing)|drooling|messy)\b/i;
const SURFACE_WEAK = /\b(cover(?:ed|ing)?|paint(?:ed|ing)?|glaze[d]?|bathed|wet|damp|submerged|dunked|dipped|pour(?:ed|ing)?|spray(?:ed|ing)?|rubbed?)\b[^.?!]{0,24}\b(in|with|all over|head to toe|from head)\b/i;

/**
 * ⚠ THE THIRD SHAPE, ADDED BECAUSE THE HARNESS CAUGHT IT MISSING: *"pour X on
 *   yourself"* puts the substance on her just as much as "covered in X" does,
 *   and neither pattern above sees it. ⛔ The preposition alone is not enough —
 *   it must land on A BODY, or "a painting on the wall" would read as a coating
 *   and strip her outfit off a picture of a wall.
 */
const SURFACE_ONTO = /\b(pour|spray|squirt|drip|dump|rub|smother|slather|paint|spread|lick|drizzle|smear|spill|splash|coat|glaze|tip|empty)\w*\b[^.?!]{0,24}\b(on|onto|over)\s+(your|yourself|you|her|herself|my|me|his|him|their)\b/i;

export function requestSpecifiesAttire(text) {
  const t = String(text || '');
  if (SURFACE_STRONG.test(t) || SURFACE_WEAK.test(t) || SURFACE_ONTO.test(t)) return true;
  const words = t.toLowerCase().split(/[^a-z0-9]+/);
  return words.some(w => ATTIRE_WORDS.has(w));
}

/**
 * ⛔⛔ `U3E-8.31` — AND SUPPRESSING THE OUTFIT WAS ONLY HALF OF IT. I GENERATED
 *   ONE AND LOOKED, AND THE COATING STILL WAS NOT ON HER.
 *
 * ⭐ THE PICTURE SHOWED HER STANDING IN A MUDDY FIELD, CLEAN. The substance had
 *   survived into the prompt intact — it was not stripped by anything — and the
 *   generator rendered it as SCENERY. The reason is grammatical: what gets sent
 *   is an INSTRUCTION addressed to her (*"cover yourself in X and show me"*),
 *   and a diffusion model does not take instructions. It reads a description of
 *   a finished picture, so an imperative degrades into a bag of nouns and the
 *   noun lands wherever it fits — usually the background.
 *
 * ⚠ **THIS IS WHY "THE MODIFIER IS ALWAYS DROPPED" LOOKED LIKE STRIPPING AND WAS
 *   NOT.** Every layer I audited was innocent, and the word was in the prompt
 *   the whole time. Grepping for where a word gets removed would never have
 *   found this; rendering it and looking did.
 *
 * ⭐ SO THE REQUEST IS RESTATED AS A DESCRIPTION:
 *   1. The camera boilerplate goes — "show me", "send me a pic of", "generate".
 *   2. Second person becomes third: what he says to her, the generator hears
 *      about her.
 *   3. When a coating IS named, it is restated in the form a generator honours —
 *      the substance ON THE BODY, said once more, plainly.
 *
 * ⚠ IT NEVER INVENTS A SUBSTANCE. The restatement is built from the words that
 *   were actually captured; when the pattern catches nothing, nothing is added.
 */
const CAMERA_ASK = /\b(?:can you\s+)?(?:show|send|give|draw|paint|generate|make|take|get)\s+(?:me|us)\b\s*(?:a|an|the)?\s*(?:pic(?:ture)?|photo|image|selfie|shot|portrait)?\s*(?:of)?\s*/gi;
const TRAILING_ASK = /\s*\b(?:and|then)?\s*(?:show|send)\s+(?:me|us)\b\s*[.!]?\s*$/i;

/** ⚠ Whole words only, and possessive before plain, or "your" becomes "her"
 *  with a stray "s" left behind on "yours". */
const SECOND_PERSON = [
  [/\byourselves\b/gi, `${PR.possessive} body`], [/\byourself\b/gi, `${PR.possessive} body`],
  [/\byour\b/gi, PR.possessive], [/\byours\b/gi, PR.possessivePronoun],
  [/\byou\b/gi, PR.object],
];

/**
 * The substance, captured from the same three constructions the predicate uses.
 * ⚠ Bounded to a short noun phrase: past that it starts swallowing the rest of
 *   the sentence and restating half the request as if it were a coating.
 */
const SUBSTANCE = [
  /\b(?:cover(?:ed|ing)?|coat(?:ed|ing)?|soak(?:ed|ing)?|drench(?:ed|ing)?|smear(?:ed|ing)?|slather(?:ed|ing)?|douse[d]?|glaze[d]?|bathed|dunked|dipped|splatter(?:ed)?|caked|lathered)\s+(?:her body|herself|yourself|her|you|your\s+\w+)?\s*(?:in|with)\s+([a-z][a-z\s-]{1,28}?)(?=\s*(?:,|\.|!|\?|$|\band\b|\ball\b|\bfrom\b|\bhead\b))/i,
  /\b(?:pour|spray|squirt|drip|dump|rub|smother|slather|spread|drizzle|smear|spill|splash|coat|glaze|tip|empty)\w*\s+([a-z][a-z\s-]{1,28}?)\s+(?:on|onto|over|all over)\b/i,
];

export function describeForImage(text) {
  let t = String(text || '').replace(TRAILING_ASK, ' ').replace(CAMERA_ASK, ' ');
  for (const [re, to] of SECOND_PERSON) t = t.replace(re, to);

  let substance = null;
  for (const re of SUBSTANCE) {
    const m = String(text || '').match(re);
    if (m && m[1] && m[1].trim().length > 1) { substance = m[1].trim(); break; }
  }
  if (substance) {
    // ⚠ Said once more, not five times. Repetition is weight, and too much of it
    //   turns the whole picture into the substance with no person left in it.
    t += `, ${PR.possessive} entire body covered in ${substance}, thick ${substance} coating ${PR.possessive} skin, glistening and dripping`;
  }
  t = t.replace(/\s{2,}/g, ' ').replace(/\s+,/g, ',').replace(/^[\s,]+/, '').trim();
  return { text: t, substance, changed: t !== String(text || '').trim() };
}

/**
 * ⛔ HER NAME NEVER GOES TO AN IMAGE GENERATOR. HER DESCRIPTION DOES.
 *
 * THE RULE: her name is never used when generating an image — her DESCRIPTION
 * is, built from what was actually asked for. This is `name_rule`, which has said since
 * the corpus was designed that searching the name *"returns a game engine, not a
 * person"* — and the same is true of generating on it: a diffusion model has no
 * idea who she is, so the name is either noise or it drags toward the logo.
 *
 * ⚠ THE VIOLATION WAS HERS, WHICH IS WHY I MISSED IT. `name_rule` was enforced
 *   on the corpus queries (verified: 0 of 293 carry it) and nothing enforced it
 *   at GENERATION time — and the legacy model writes her name into its own image
 *   lines unprompted: `[[img: a darkly gothic Unity, wearing a black leather
 *   corset ...]]`. That went straight to SD as written.
 *
 * ⭐ So the name is replaced by what she actually looks like, from
 *   `taxonomy.persona` — the same words the corpus was collected under. The
 *   caption keeps the name (that is where identity is bound); the PROMPT never
 *   sees it.
 *
 * ⚠ Possessives handled explicitly: "Unity's corset" must become "her corset",
 *   not "<description>'s corset".
 */
const NAME = /\bunity\b/gi;
const NAME_POSSESSIVE = /\bunity['’]s\b/gi;

export function deNameForImage(prompt, persona) {
  const p = String(prompt || '');
  if (!NAME.test(p)) { NAME.lastIndex = 0; return { text: p, renamed: false }; }
  NAME.lastIndex = 0;
  const text = p
    .replace(NAME_POSSESSIVE, PR.possessive)
    // ⛔ THE LAST HARDCODED DESCRIPTION OF HER IN THIS FILE. It falls back to
    //   the ACTIVE PROFILE's own appearance and nouns now, so a buyer's John is
    //   not described as "a sexy emo goth woman" by a default nobody chose.
    .replace(NAME, persona || (P.ok && P.appearance && P.appearance !== 'unset'
      ? `${P.appearance}, a ${NOUN.adjective} ${NOUN.person}`
      : `a ${NOUN.adjective} ${NOUN.person}`));
  return { text, renamed: true };
}

/**
 * ⛔ TWO WORDS THAT WRECK HER PICTURES, fixed where every prompt passes.
 *
 * THE RULE: "dark" is not used as a mood word — it simply darkens the picture —
 * and "gothic" on its own pulls the wrong way. The look is sexy emo goth, which
 * is a different thing from gothic.
 *
 * ⭐ 'dark' AS MOOD IS AN EXPOSURE INSTRUCTION. A diffusion model obeys it by
 *   underexposing the whole frame, so "darkly gothic" costs the picture its
 *   light before anything else is decided.
 * ⚠ SCOPE, corrected after the first cut went too far: **hair colour stays.**
 *   'dark hair', 'dark eyes', 'dark skin' are descriptions of a person, not of
 *   the lighting, and stripping them was my over-correction. Only the free mood
 *   uses go.
 *
 * ⭐ 'gothic' PULLS TO A DIFFERENT CENTURY than 'emo goth' — cathedrals, lace
 *   and funeral dress rather than eyeliner, leather and fishnets. The words look
 *   adjacent and are not.
 *
 * ⚠ This runs on prompts headed for the GENERATOR only. It never touches what
 *   she says, what is captioned, or what the person typed in the chat.
 */
const MOOD_DARK = /\bdark(?:ly|ness)?\b(?!\s+(?:hair|eyes?|skin|brown|red|blonde|blue|green|lipstick|nail))/gi;
const GOTHIC = /\b(?:darkly\s+)?gothic\b/gi;

/**
 * ⛔ THE LAST PLACE 'pale' SURVIVED, and it was hers.
 *
 * Fixing the canon (`Unity1.txt`) took her TEXT from 4-in-5 pale-family words to
 * 0 — but she still wrote it into her own `[[img: ...]]` line:
 * `[img: 25-year-old goth woman, black hair with pink streaks, pale ...]`.
 *
 * ⚠ THIS IS DELETION, NOT A NEGATIVE PROMPT. Negative prompting is banned here,
 *   twice over, and for a real reason — a denied word still steers, which is why
 *   `taxonomy.persona_note` keeps that field free of negations. Removing a word
 *   from a positive prompt is the opposite operation: the generator never sees
 *   it at all. Same mechanism already applied to 'dark' and 'gothic'.
 *
 * ⭐ Her skin is then stated POSITIVELY by the persona substitution — "warm
 *   healthy flesh-toned skin" — so the slot is filled rather than left open for
 *   the model's goth-is-pale prior to fill again.
 */
const PALE = /\b(?:pale|pallid|pallor|porcelain|alabaster|ashen|ghostly|sickly)\s*(?:white|skin|complexion|-skinned)?\b/gi;

export function cleanImagePrompt(prompt) {
  const before = String(prompt || '');
  const text = before
    .replace(GOTHIC, 'sexy emo goth')
    .replace(MOOD_DARK, '')
    .replace(PALE, '')
    // ⛔ COLLAPSE THE PHRASE IF IT NOW APPEARS TWICE IN A ROW. "a darkly gothic
    //   Unity" becomes "a [sexy emo goth] [sexy emo goth woman, ...]" — the
    //   rewrite above and the persona substitution both supply it. Measured on
    //   her real image line; a doubled descriptor is a prompt arguing with
    //   itself and it costs weight that should be on the subject.
    .replace(/\b(sexy emo goth)(\s+\1)+\b/gi, '$1')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+,/g, ',')
    .replace(/,\s*,/g, ',')
    .trim()
    .replace(/^,\s*/, '');
  return { text, changed: text !== before };
}

/**
 * ⭐ THE WHOLE PIPELINE IN ONE CALL, so a second backend cannot get the ORDER
 *   wrong — and the order is load-bearing. `U3E-8.31` first, so every stage
 *   below reads the same words the generator will; then the name swap, because
 *   a prompt naming her IS a prompt about her; then the attire decision; then
 *   the cleaner, last, so it also catches whatever the persona suffix dragged
 *   in.
 *
 * ⚠ Returns the parts as well as the text. A backend that cannot explain what
 *   it sent cannot be debugged by looking at the picture, which is the only way
 *   any of these rules were ever found.
 */
export function composeImagePrompt(prompt, appearance) {
  const parts = [prompt];
  if (appearance && appearance.slots) {
    for (const v of Object.values(appearance.slots)) {
      if (v && v.text) parts.push(v.text);
    }
  }
  const described = describeForImage(parts.join(', '));
  const named = deNameForImage(described.text, PERSONA);
  /**
   * ⛔ THE PERSONA SUFFIX APPLIES ONLY WHEN THE PICTURE IS OF HER. Appending a
   *   whole-person description to a generic subject does not tint it, it
   *   COMPETES with it and wins — measured: "a nude goth woman, full body" came
   *   back in a fishnet bodysuit, clothed. `appearance` is the app's signal that
   *   a manifestation is in force; her name in the prompt is the other signal.
   */
  const aboutHer = named.renamed
    || !!(appearance && (appearance.manifestation || appearance.slots));
  const askedAttire = requestSpecifiesAttire(named.text);
  const persona = aboutHer
    ? [PERSONA, !askedAttire && PERSONA_ATTIRE ? PERSONA_ATTIRE : ''].filter(Boolean).join(', ')
    : '';
  const composed = named.renamed
    ? [named.text, !askedAttire && PERSONA_ATTIRE ? PERSONA_ATTIRE : ''].filter(Boolean).join(', ')
    : [named.text, persona].filter(Boolean).join(', ');
  const cleaned = cleanImagePrompt(composed);
  return {
    text: cleaned.text,
    aboutHer,
    renamed: named.renamed,
    askedAttire,
    substance: described.substance,
  };
}
