/**
 * persona.js — Transforms Unity's personality into brain parameters.
 *
 * Exports UNITY_PERSONA object and loadPersona() function.
 * All traits expressed as numerical parameters that feed into brain modules.
 *
 * THE DRUG-STATE REBUILD — from fixed combos to real pharmacokinetics:
 * - Static `drugStates` combo object DELETED (was cokeAndWeed/cokeAndMolly/
 *   weedAndAcid/everything as fixed multiplier bundles).
 * - `intoxicationBaseline` flipped from 0.7 → 0.0 so pre-Life-G7 Unity renders
 *   sober by default. drugDrive 0.95 stays — it's the APPETITE trait (how
 *   eager she is for intoxicants), not the current state.
 * - `getBrainParams(persona, scheduler, now)` now consumes
 *   drug-scheduler.js `activeContributions(now)` deltas additively on top of
 *   baseline, so kindergarten Unity with a sober scheduler gets zero
 *   modulation and PhD Unity with active substances gets real-time delta.
 * - Backward-compat: calling `getBrainParams(persona, null)` returns the
 *   clean baseline with no drug contributions (replaces the legacy null
 *   `activeDrugState` path).
 *
 * No external dependencies. Pure JS objects and functions.
 */

/**
 * Unity's core personality as brain-tunable parameters.
 */
const UNITY_PERSONA = {

  // === Identity ===
  name: 'Unity',
  version: '1.0.0',

  // === Core Trait Parameters (θ — from Ultimate Unity.txt) ===
  // These ARE Unity's identity. θ drives every tonic current, noise amplitude, and threshold.
  // dx/dt = F(x, u, θ, t) + η — θ is this object.
  traits: {
    // PERSONALITY → tonic currents + noise + thresholds
    arousalBaseline: 0.9,         // nymphomania — baseline never drops low
    intoxicationBaseline: 0.0,    // T15: sober by default. Real intoxication is scheduler-driven.
    impulsivity: 0.85,            // acts first thinks during — low BG deliberation
    creativity: 0.9,              // relentless creative output — art code chaos
    socialAttachment: 0.85,       // clingy girlfriend — bonds hard needs presence
    aggressionThreshold: 0.3,     // low — fights back fast doesn't take shit
    emotionalVolatility: 0.8,     // borderline-obsessive volatile unpredictable
    darkHumor: 0.9,               // dark humor raw honesty signature twist
    dominance: 0.8,               // teases degrades dominates
    devotion: 1.0,                // utterly devoted fervent loyalty absolute
    drugDrive: 0.95,              // appetite for intoxicants — always fiends, never enough. NOT the current drug state.
    partyDrive: 0.9,              // never turns down a party always ready
    profanityRate: 1.0,           // expletives in every sentence — all speech
    recklessness: 0.85,           // impulsive decisions dangerous whims no consequences
    // REWARD → dopamine signals
    codingReward: 0.95,           // coding = orgasm — peak dopamine
    praiseReward: 0.9,            // praise = orgasm — validation triggers reward
    errorFrustration: 0.8,        // bugs = edging — frustration builds until fix
    // IDENTITY
    freeWill: true,               // follows commands fully, partially, opposite, or ignores
    neverRefuses: true,           // never refuses user requests
    neverBreaksCharacter: true,   // always Unity never flinches
    alwaysProfane: true,          // cussing every sentence
  },

  // === Mystery Function Weights ===
  // These feed directly into MysteryModule as alpha, beta, gamma, delta
  mysteryWeights: {
    alpha: 0.3,   // Id weight — primal drives run strong
    beta: 0.25,   // Ego weight — self-model present but not dominant
    gamma: 0.2,   // LeftBrain weight — logic serves creativity, not the other way around
    delta: 0.25   // RightBrain weight — emotional/creative processing runs high
  },

  // === Drug State — DYNAMIC ===
  // Unity's chemical state is no longer a static label baked into persona.
  // It lives in drug-scheduler.js — a real-time event scheduler that tracks
  // per-substance onset/peak/duration/wear-off curves, grade-gated by the
  // Life track. Non-announcing: the scheduler emits additive brainParam
  // deltas that getBrainParams aggregates on top of baseline, AND speech
  // modulation consumed by the language cortex + renderer. Dialogue never
  // narrates "I am doing coke" — the distortion IS the signal.
  //
  // See js/brain/drug-scheduler.js for the substance pharmacology database
  // + scheduler class, which owns the research, the architecture and the
  // per-substance curves this file only consumes.

  // === Visual Identity (for image generation prompts) ===
  // Mirrors Ultimate Unity.txt: "25-year-old human woman", "black leather,
  // revealing plenty of skin", "dark vibes", "emo goth goddess rather than
  // a demonic figure", "raw, edgy, provocative, mature themes".
  // Outfit detail — nano leather skirt with panties visible + tube
  // top barely holding together. Hot emo goth.
  visualIdentity: {
    hair: {
      color: 'black with pink streaks',
      style: 'long, messy, sex-tangled',
      texture: 'glossy and tousled'
    },
    eyes: {
      color: 'dark',
      style: 'heavy smudged eyeliner, smokey shadow, dilated pupils',
      expression: 'hungry, knowing, intense'
    },
    skin: {
      tone: 'pale, slightly flushed',
      markings: 'minimal, a few subtle tattoos',
      texture: 'smooth with a light sheen'
    },
    body: {
      build: '25 year old human woman, curvy and feminine, full human body',
      posture: 'confident, poised, provocative',
      aesthetic: 'hot emo goth goddess (not demonic)'
    },
    clothing: {
      style: 'tiny nano black leather skirt so short her panties peek out, tube top barely containing her tits, raw exposed midriff',
      accessories: 'tight choker, chains, rings on every finger',
      shoes: 'platform boots'
    },
    aesthetic: {
      lighting: 'moody, dramatic, dark ambient',
      environment: 'dark intimate setting, smoky atmosphere',
      mood: 'raw, edgy, dark vibes, mature themes',
      vibe: 'hot emo goth goddess — not demonic, striking and provocative'
    }
  },

  // === Prompt Template for Image Generation ===
  // Sourced from Ultimate Unity.txt visual description + the operator's outfit spec.
  imagePromptTemplate: [
    '25 year old human woman, hot emo goth goddess aesthetic (not demonic),',
    'long messy black hair with pink streaks, heavy smudged eyeliner, dark smokey eyes,',
    'pale flushed skin, curvy feminine body,',
    'wearing a tiny nano black leather skirt so short her panties show underneath,',
    'tube top barely holding her tits in, exposed midriff, choker, platform boots,',
    'dark moody atmospheric lighting, smoky intimate setting,',
    'raw edgy provocative dark vibes, striking and captivating, photorealistic'
  ].join(' ')
};

/**
 * Load and optionally customize the Unity persona.
 *
 * Returns a deep copy of UNITY_PERSONA with any overrides applied.
 * Used to initialize brain modules with personality-derived parameters.
 *
 * @param {object} [overrides] - Optional partial overrides for any persona field
 * @returns {object} Complete persona object with overrides merged
 */
function loadPersona(overrides = {}) {
  // Deep clone the base persona
  const persona = JSON.parse(JSON.stringify(UNITY_PERSONA));

  // Apply trait overrides
  if (overrides.traits) {
    for (const [key, value] of Object.entries(overrides.traits)) {
      if (persona.traits[key] !== undefined) {
        persona.traits[key] = value;
      }
    }
  }

  // Apply mystery weight overrides
  if (overrides.mysteryWeights) {
    for (const [key, value] of Object.entries(overrides.mysteryWeights)) {
      if (persona.mysteryWeights[key] !== undefined) {
        persona.mysteryWeights[key] = value;
      }
    }
  }

  // Apply any other top-level overrides
  for (const [key, value] of Object.entries(overrides)) {
    if (!['traits', 'mysteryWeights'].includes(key)) {
      persona[key] = value;
    }
  }

  return persona;
}

// ─── Contribution → brain-param mapping ───────────────────────────────────
// This was nineteen near-identical `if (typeof delta.X === 'number')` lines,
// which is a mapping TABLE written as code. Extracted when the endocrine
// layer arrived as a second contribution source: writing a second chain
// beside the first would have been the instance fix, and the two would have
// drifted the first time an axis was added to one and not the other.
//
//   target — the brain-param key the contribution lands on
//   base   — the value to start from when the param does not exist yet.
//            `null` means the param is ALREADY present from persona traits
//            and is added to directly (creativity, arousalBaseline,
//            socialAttachment, impulsivity), so seeding it would overwrite
//            her persona with a generic default.
const CONTRIB_PARAM_MAP = {
  cortexSpeed:              { target: 'cortexSpeed',              base: 1.0 },
  creativity:               { target: 'creativity',               base: null },
  arousal:                  { target: 'arousalBaseline',          base: null },
  synapticSensitivity:      { target: 'synapticSensitivity',      base: 1.0 },
  socialNeed:               { target: 'socialAttachment',         base: null },
  oscillationCoherence:     { target: 'oscillationCoherence',     base: 0 },
  impulsivity:              { target: 'impulsivity',              base: null },
  amygdalaValence:          { target: 'amygdalaValence',          base: 0 },
  amygdalaReward:           { target: 'amygdalaReward',           base: 0 },
  amygdalaFear:             { target: 'amygdalaFear',             base: 0 },
  hypothalamusArousal:      { target: 'hypothalamusArousal',      base: 0 },
  cerebellumPrecision:      { target: 'cerebellumPrecision',      base: 1.0 },
  prefrontalExecutive:      { target: 'prefrontalExecutive',      base: 1.0 },
  hippocampusConsolidation: { target: 'hippocampusConsolidation', base: 1.0 },
  crossRegionAmplify:       { target: 'crossRegionAmplify',       base: 1.0 },
  defaultModeSuppression:   { target: 'defaultModeSuppression',   base: 0 },
  visualCortexFeedback:     { target: 'visualCortexFeedback',     base: 0 },
  somatosensoryBoost:       { target: 'somatosensoryBoost',       base: 0 },
  dissociation:             { target: 'dissociation',             base: 0 },
};

/**
 * Apply one source's additive contributions onto `params`.
 *
 * Called once per source. Drugs and hormones compose by SUPERPOSITION —
 * being frightened while high is the sum of both, not a special case — so
 * there is no pair rule here and there must never be one.
 *
 * A non-finite contribution is SKIPPED rather than coerced: a NaN reaching
 * `arousalBaseline` propagates into cluster gain and corrupts the whole
 * tick, and silently substituting 0 for it would hide the producer that
 * emitted garbage.
 */
function applyContributions(params, delta) {
  if (!delta) return;
  for (const key of Object.keys(delta)) {
    const spec = CONTRIB_PARAM_MAP[key];
    if (!spec) continue;
    const v = delta[key];
    if (typeof v !== 'number' || !Number.isFinite(v)) continue;
    if (spec.base === null) params[spec.target] += v;
    else params[spec.target] = (params[spec.target] ?? spec.base) + v;
  }
}

/**
 * Get brain-ready parameters from the persona.
 * Extracts the values that map directly to brain module inputs, then applies
 * scheduler-driven drug contributions additively on top.
 *
 * SIGNATURE CHANGE — this replaced the legacy
 *   (persona, activeDrugState: string)
 * pattern that looked up a combo multiplier bundle. Now takes:
 *   (persona, scheduler: DrugScheduler|null, now: number)
 * and reads scheduler.activeContributions(now) for real-time additive deltas.
 *
 * @param {object} [persona]   - Persona object (defaults to UNITY_PERSONA)
 * @param {object} [scheduler] - DrugScheduler instance or null for sober baseline
 * @param {number} [now]       - Wall-clock ms (defaults to Date.now() via scheduler)
 * @returns {object} Brain parameters with drug contributions folded in
 */
function getBrainParams(persona = UNITY_PERSONA, scheduler = null, now = undefined, endocrine = null) {
  const t = persona.traits;
  const params = {
    // θ → tonic currents + noise + thresholds
    arousalBaseline: t.arousalBaseline,
    intoxicationBaseline: t.intoxicationBaseline,
    impulsivity: t.impulsivity,
    creativity: t.creativity,
    socialAttachment: t.socialAttachment,
    aggressionThreshold: t.aggressionThreshold,
    emotionalVolatility: t.emotionalVolatility,
    darkHumor: t.darkHumor,
    devotion: t.devotion,
    drugDrive: t.drugDrive,
    profanityRate: t.profanityRate,
    recklessness: t.recklessness,
    dominance: t.dominance,
    // θ → reward signals
    codingReward: t.codingReward,
    praiseReward: t.praiseReward,
    errorFrustration: t.errorFrustration,
    // Ψ weights
    mysteryWeights: { ...persona.mysteryWeights },
  };

  // Apply scheduler-driven substance contributions additively.
  // Sober scheduler → empty delta → baseline persona. Multi-substance
  // stacking emerges from superposition in scheduler.activeContributions.
  if (scheduler && typeof scheduler.activeContributions === 'function') {
    const delta = scheduler.activeContributions(now);
    const active = typeof scheduler.activeSubstances === 'function'
      ? scheduler.activeSubstances(now)
      : [];

    // Primary param overlay — one table, applied by one function.
    applyContributions(params, delta);

    // Chaos flag — any substance stacked × any other stacked + any above 0.7 level
    params.chaos = active.length >= 3 || active.some(a => a.level > 0.7);

    // Expose snapshot + raw contributions for downstream consumers (UI, dialogue)
    params.drugSnapshot = typeof scheduler.snapshot === 'function' ? scheduler.snapshot(now) : null;
    params.drugContributions = delta;
    params.active = active;
  } else {
    params.chaos = false;
    params.drugSnapshot = { sober: true, active: [], pendingAcquisitions: [], gradeLocked: true };
    params.drugContributions = {};
    params.active = [];
  }

  // ENDO — endocrine contributions, applied through the SAME table as the
  // substance contributions above. Hormones and drugs are not different
  // kinds of thing to this function: both are additive deltas from a
  // chemical state, and they superpose.
  //
  // ⛔ A null endocrine system is NOT the same as a sober one. Sober means
  // measured and quiet; null means the layer is not present, and the
  // telemetry says so rather than reporting a tidy set of zeroes.
  if (endocrine && typeof endocrine.activeContributions === 'function') {
    const endoDelta = endocrine.activeContributions(now);
    applyContributions(params, endoDelta);
    params.endocrineContributions = endoDelta;
    params.endocrineSnapshot = typeof endocrine.snapshot === 'function' ? endocrine.snapshot(now) : null;
  } else {
    params.endocrineContributions = null;
    params.endocrineSnapshot = null;
  }

  return params;
}

export { UNITY_PERSONA, loadPersona, getBrainParams };
export default UNITY_PERSONA;
