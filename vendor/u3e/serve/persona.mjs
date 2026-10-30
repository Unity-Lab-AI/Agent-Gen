/**
 * serve/persona.mjs — `U3E-9.1`. WHO THE MODEL IS, RESOLVED RATHER THAN TYPED.
 *
 * ⛔⛔ GEE, VERBATIM: *"this is all to walk someone through there own custom set
 *   up of their own EBM model with Unity as the default but from renaming her
 *   even to her being a guy named jjohn"*.
 *
 * ── ⭐ THE SCOPE IS SMALLER THAN THE FIRST COUNT SAID, AND SAYING SO MATTERS ─
 *
 *   The roadmap recorded **297 gendered pronouns in the generation path**. That
 *   was a raw grep and it counted COMMENTS ABOUT HER. Re-measured with comments
 *   and docstrings stripped:
 *
 *       datatools/caption-run.mjs      65     serve/image-prompt.js    17
 *       datatools/caption-gate.mjs      1     data/curriculum-rewrite   1
 *       app/appearance.js          1     datatools/first_person.py      0
 *       ------------------------------------------------------------
 *       IN CODE                   85     (231 of the 297 were comments)
 *       datatools/taxonomy.json       441     ⚠ DATA, and a different problem
 *
 *   ⭐⭐ **`first_person.py` SCORES ZERO, AND THAT IS NOT LUCK.** First person
 *   has no gender in English — *"i learned this today"* is already John's
 *   sentence. **Her entire life-story and curriculum path is re-skinnable
 *   today**, which is the half of Gee's ask that sounded hardest.
 *
 *   ⚠ `taxonomy.json`'s 441 are DATA — `caption_voice`, `persona_words`,
 *   `anatomy_vocab`. Those are not converted by a resolver; they are REPLACED
 *   by a buyer, which is a per-profile overlay and a separate row.
 *
 * ── ⛔ ABSENT SAYS ABSENT, HERE MOST OF ALL ─────────────────────────────────
 *
 *   `datatools/persona.json` ships `john` with `canon: null` on purpose. ⛔ A
 *   resolver that quietly fell back to Unity's canon would hand a buyer a John
 *   who talks exactly like Unity **and no error anywhere** — the precise failure
 *   this whole epic exists to prevent. `canonText()` returns null and says so.
 */

import { readFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dataDir } from './datadir.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

function load() {
  // ⚠ Through the resolved data root, so a buyer's persona travels with their
  //   data folder rather than being stranded in the repo they cloned.
  for (const p of [join(dataDir().dir, 'persona.json'), join(ROOT, 'datatools', 'persona.json')]) {
    try { return { doc: JSON.parse(readFileSync(p, 'utf8')), path: p }; } catch { /* next */ }
  }
  return { doc: null, path: null };
}

/**
 * The active profile.
 * ⛔ `U3E_PERSONA` overrides the file, so the switchboard can render a page as
 *   John without editing anything — which is how the re-skin gets TESTED rather
 *   than asserted.
 */
export function persona(which) {
  const { doc, path } = load();
  if (!doc) {
    // ⛔ NOT A DEFAULT OBJECT. A resolver that invents a persona when the file
    //   is missing lets a corpus be written by nobody in particular.
    return { ok: false, why: 'datatools/persona.json is absent', id: null };
  }
  const id = which || process.env.U3E_PERSONA || doc.active;
  const p = (doc.profiles || {})[id];
  if (!p) return { ok: false, why: `no profile "${id}"`, id, available: Object.keys(doc.profiles || {}) };
  return {
    ok: true, id, path,
    name: p.name,
    shortName: p.shortName || p.name,
    pronouns: p.pronouns,
    nouns: p.nouns,
    age: p.age ?? null,
    register: p.register || null,
    appearance: p.appearance || null,
    canonPath: p.canon || null,
    available: Object.keys(doc.profiles || {}),
  };
}

/**
 * Her canon — or an honest null.
 * ⛔ NO FALLBACK. See the header: a John who reads Unity's canon is the failure.
 */
export function canonText(which) {
  const p = persona(which);
  if (!p.ok || !p.canonPath) return { ok: false, why: p.ok ? `profile "${p.id}" has no canon` : p.why, text: null };
  const f = join(ROOT, p.canonPath);
  if (!existsSync(f)) return { ok: false, why: `canon not found at ${p.canonPath}`, text: null };
  return { ok: true, path: p.canonPath, text: readFileSync(f, 'utf8') };
}

/**
 * ⭐ THE WORKHORSE. Every gendered literal in the generation path becomes one of
 *   these, so a prompt is written once and reads correctly for any profile.
 *
 *     say(p, 'She is wearing {her} jacket')  ->  'He is wearing his jacket'
 *
 * ⚠ Case is carried: `{Subject}` capitalises, `{subject}` does not. A template
 *   that lost the capital would start every other sentence in lower case, which
 *   reads as broken rather than as re-skinned.
 */
export function say(p, template) {
  if (!p || !p.ok) return template;
  const map = {
    subject: p.pronouns.subject, object: p.pronouns.object,
    possessive: p.pronouns.possessive, possessivePronoun: p.pronouns.possessivePronoun,
    reflexive: p.pronouns.reflexive,
    person: p.nouns.person, youngPerson: p.nouns.youngPerson, adjective: p.nouns.adjective,
    name: p.name, Name: p.name,
    // ⚠ Aliases for the words a prompt actually uses, so a template reads like
    //   English instead of like a schema.
    she: p.pronouns.subject, her: p.pronouns.possessive, hers: p.pronouns.possessivePronoun,
    herself: p.pronouns.reflexive, woman: p.nouns.person, girl: p.nouns.youngPerson,
    female: p.nouns.adjective,
  };
  return String(template).replace(/\{([A-Za-z]+)\}/g, (whole, key) => {
    const lower = key[0].toLowerCase() + key.slice(1);
    const v = map[lower];
    if (v === undefined) return whole;               // not ours — leave it alone
    return key[0] === key[0].toUpperCase() && key !== lower
      ? v[0].toUpperCase() + v.slice(1)
      : v;
  });
}

if (process.argv[1] && process.argv[1].endsWith('persona.mjs')) {
  const which = process.argv[2];
  const p = persona(which);
  console.log('\nU3E-9.1 — WHO THE MODEL IS\n');
  if (!p.ok) { console.log('  ⛔ ' + p.why); process.exit(1); }
  console.log(`  profile   ${p.id}   (available: ${p.available.join(', ')})`);
  console.log(`  name      ${p.name}`);
  console.log(`  pronouns  ${p.pronouns.subject}/${p.pronouns.object}/${p.pronouns.possessive}`);
  console.log(`  nouns     ${p.nouns.person} · ${p.nouns.youngPerson} · ${p.nouns.adjective}`);
  const c = canonText(which);
  console.log(`  canon     ${c.ok ? p.canonPath + ' (' + c.text.length.toLocaleString() + ' chars)' : '⛔ ' + c.why}`);
  console.log('\n  a template, rendered:');
  const t = '{Subject} is a {adjective} {person}. {Subject} wears {possessive} own clothes, and {subject} speaks for {reflexive}.';
  console.log(`    ${say(p, t)}\n`);
}
