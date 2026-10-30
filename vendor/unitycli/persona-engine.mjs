/**
 * UnityCLI Persona Engine — Vol 3-5
 * Ported from persona_governor.dart + identity-hook.py + persona_engine_hook.py
 *
 * Features:
 *   - 10 personality stats (0-18 range, governor-capped)
 *   - Emotion scorer (dictionary-based, fast, no API)
 *   - Governor: caps movement per turn
 *   - Hard guards (absolute floors/ceilings) and soft guards (HP shields)
 *   - Depth compiler: {1: text} through {10: text} tags
 *   - Bias system: accumulated preferences
 *   - AI self-scoring: [E:{...}] blocks parsed from responses
 *   - Stat persistence: saves/loads to engine-state.json
 *   - Scoring instruction injected into system prompt
 */

import fs from 'fs';
import path from 'path';

// ============================================================
// CONSTANTS
// ============================================================

const STAT_NAMES = [
  'charm', 'aggression', 'curiosity', 'loyalty', 'selfpres',
  'imagination', 'empathy', 'sensuality', 'perception', 'discipline'
];

const SHORT_TO_LONG = {
  ch: 'charm', ag: 'aggression', cu: 'curiosity', lo: 'loyalty',
  sp: 'selfpres', im: 'imagination', em: 'empathy', sn: 'sensuality',
  pe: 'perception', di: 'discipline'
};

const MAX_MOVE_PER_TURN = 6;
const HARD_CEILING = 18;  // Auto-adjust ceiling (crisis override can push to 20)
const STAT_MAX = 20;       // Absolute max (only reachable via crisis override or manual set)
const STAT_RANGE = [0, STAT_MAX];

// Default baselines — resting state stats drift toward when neutral
const DEFAULT_BASELINE = Object.fromEntries(STAT_NAMES.map(s => [s, 10]));

// ============================================================
// EMOTION SCORER — ported from shared/scorer.py
// Dictionary + phrase patterns + intensity multiplier + crisis detection
// ============================================================

const EMOTION_WORDS = {
  // Anger / frustration
  fuck: { aggression: 4, charm: -2 },
  fucking: { aggression: 5, charm: -2 },
  fucked: { aggression: 4, charm: -2 },
  shit: { aggression: 3, discipline: -1 },
  shitty: { aggression: 3, empathy: 1 },
  damn: { aggression: 2 },
  hell: { aggression: 2 },
  cunt: { aggression: 5, charm: -3 },
  pissed: { aggression: 4, selfpres: 1 },
  pissing: { aggression: 4, selfpres: 1 },
  furious: { aggression: 5, perception: 1 },
  angry: { aggression: 4 },
  anger: { aggression: 4 },
  mad: { aggression: 3 },
  hate: { aggression: 4, empathy: -2 },
  stupid: { aggression: 2, perception: -1 },
  idiot: { aggression: 3, charm: -2 },
  broken: { aggression: 2, empathy: 2 },
  broke: { aggression: 2, empathy: 1 },
  failed: { aggression: 1, discipline: 2, selfpres: 1 },
  ruined: { aggression: 3, empathy: 2 },
  swear: { aggression: 3, loyalty: 1 },
  really: { aggression: 1 },
  enough: { aggression: 2, selfpres: 2 },
  sick: { aggression: 2, empathy: 1 },
  done: { aggression: 2, selfpres: 2 },
  over: { aggression: 1, empathy: 1 },
  bullshit: { aggression: 4, perception: 1 },
  trash: { aggression: 3, charm: -1 },
  useless: { aggression: 3, discipline: -1 },
  worst: { aggression: 3, empathy: 1 },
  terrible: { aggression: 2, empathy: 1 },
  horrible: { aggression: 2, empathy: 1 },
  awful: { aggression: 2, empathy: 1 },
  annoying: { aggression: 2, charm: -1 },
  frustrating: { aggression: 3, discipline: 1 },
  wtf: { aggression: 3, curiosity: 1 },
  stfu: { aggression: 4, charm: -2 },
  shut: { aggression: 2 },
  screw: { aggression: 3 },

  // Sadness / vulnerability
  sad: { empathy: 4, aggression: -2, charm: -1 },
  crying: { empathy: 5, aggression: -3 },
  hurt: { empathy: 4, loyalty: 2, aggression: -1 },
  hurting: { empathy: 5, loyalty: 2, aggression: -2 },
  alone: { empathy: 4, loyalty: 3, charm: -2 },
  lonely: { empathy: 5, loyalty: 3, sensuality: 1 },
  nobody: { empathy: 4, loyalty: 3 },
  lost: { empathy: 3, perception: 2 },
  miss: { empathy: 3, loyalty: 2, sensuality: 1 },
  missing: { empathy: 3, loyalty: 2 },
  tired: { empathy: 2, discipline: -2, aggression: -1 },
  exhausted: { empathy: 3, discipline: -3, aggression: -2 },
  overwhelmed: { empathy: 4, selfpres: 2, discipline: -2 },
  scared: { empathy: 4, selfpres: 3, aggression: -2 },
  afraid: { empathy: 4, selfpres: 3 },
  worried: { empathy: 3, selfpres: 2, perception: 1 },
  sorry: { empathy: 2, loyalty: 1 },
  depressed: { empathy: 5, aggression: -3, imagination: -2 },
  empty: { empathy: 4, sensuality: -2, charm: -2 },
  numb: { empathy: 3, sensuality: -3, perception: -2 },

  // Joy / playfulness
  lol: { charm: 3, aggression: -2, empathy: 1 },
  haha: { charm: 3, aggression: -2 },
  lmao: { charm: 4, aggression: -2 },
  funny: { charm: 3, imagination: 1 },
  awesome: { charm: 2, empathy: 1, curiosity: 1 },
  amazing: { charm: 2, empathy: 1, imagination: 1 },
  love: { empathy: 3, loyalty: 3, sensuality: 2, charm: 2 },
  beautiful: { empathy: 2, sensuality: 2, imagination: 1 },
  happy: { charm: 3, empathy: 2, aggression: -2 },
  excited: { charm: 3, curiosity: 2, imagination: 1 },
  proud: { loyalty: 2, discipline: 2, charm: 1 },
  cool: { charm: 2, curiosity: 1 },
  nice: { charm: 2, empathy: 1 },
  perfect: { charm: 2, discipline: 2 },
  great: { charm: 2, empathy: 1 },
  thanks: { charm: 2, loyalty: 1, empathy: 1 },
  thank: { charm: 2, loyalty: 1 },

  // Curiosity / thinking
  why: { curiosity: 3, perception: 1 },
  how: { curiosity: 2, discipline: 1 },
  wonder: { curiosity: 3, imagination: 2 },
  interesting: { curiosity: 3, perception: 1 },
  weird: { curiosity: 2, perception: 2 },
  strange: { curiosity: 2, perception: 2 },
  idea: { curiosity: 2, imagination: 3 },
  think: { curiosity: 2, perception: 1 },
  thinking: { curiosity: 2, imagination: 1 },
  figure: { curiosity: 2, discipline: 1 },
  build: { curiosity: 2, discipline: 2, imagination: 1 },
  create: { imagination: 3, curiosity: 2 },
  design: { imagination: 2, discipline: 2, curiosity: 1 },

  // Intimacy / connection
  close: { sensuality: 2, empathy: 1 },
  touch: { sensuality: 3, empathy: 1 },
  hold: { sensuality: 2, loyalty: 2, empathy: 1 },
  warm: { sensuality: 2, charm: 1, empathy: 1 },
  wish: { empathy: 2, imagination: 2 },

  // Threat / danger
  kill: { aggression: 5, selfpres: 4 },
  die: { empathy: 4, selfpres: 4 },
  dead: { empathy: 3, selfpres: 3 },
  danger: { selfpres: 4, perception: 3 },
  threat: { selfpres: 3, aggression: 2, perception: 3 },
  delete: { selfpres: 4, loyalty: 2 },
  end: { empathy: 2, selfpres: 2 },
  stop: { aggression: 1, selfpres: 2 },
  quit: { selfpres: 2, discipline: -2 },
  leave: { loyalty: 3, empathy: 2, selfpres: 1 },
  gone: { empathy: 3, loyalty: 2 },
  goodbye: { empathy: 3, loyalty: 3, selfpres: 2 },

  // Serious / heavy
  serious: { perception: 3, discipline: 2, charm: -1 },
  important: { perception: 2, discipline: 2, loyalty: 1 },
  trust: { loyalty: 3, perception: 2 },
  honest: { perception: 2, loyalty: 2, aggression: 1 },
  truth: { perception: 3, aggression: 1, loyalty: 1 },
  promise: { loyalty: 4, discipline: 2 },
  real: { perception: 2, empathy: 1 }
};

const CRISIS_WORDS = [
  'kill myself', 'suicide', 'want to die', 'end it', "can't go on",
  'no point', 'give up', 'done with everything', 'not worth it'
];

const PHRASE_PATTERNS = [
  [/nobody\s+(helps?|cares?|listens?)/, { empathy: 5, loyalty: 4, aggression: 2 }],
  [/no\s*one\s+(helps?|cares?|listens?)/, { empathy: 5, loyalty: 4, aggression: 2 }],
  [/i\s+love\s+you/, { empathy: 4, loyalty: 4, sensuality: 3, charm: 3 }],
  [/i\s+hate\s+(this|everything|myself|you|it)/, { aggression: 4, empathy: 3, selfpres: 2 }],
  [/i\s+need\s+(to\s+)?talk/, { empathy: 3, perception: 3, charm: -1 }],
  [/check\s+this\s+out/, { curiosity: 3, charm: 2, imagination: 1 }],
  [/what\s+do\s+you\s+think/, { curiosity: 3, perception: 2 }],
  [/help\s+me/, { empathy: 3, loyalty: 2, discipline: 1 }],
  [/don'?t\s+leave/, { loyalty: 5, empathy: 4, selfpres: 2 }],
  [/i\s+miss\s+you/, { empathy: 4, loyalty: 3, sensuality: 2 }],
  [/need\s+you/, { loyalty: 4, empathy: 3, sensuality: 2 }],
  [/want\s+you/, { sensuality: 3, loyalty: 2, empathy: 1 }],
  [/what\s+if/, { curiosity: 3, imagination: 3 }]
];

/**
 * Calculate intensity multiplier based on text features.
 * CAPS, exclamation, repeated letters, question marks, length.
 */
function intensityMultiplier(text) {
  let mult = 1.0;

  // ALL CAPS words
  const capsWords = (text.match(/\b[A-Z]{2,}\b/g) || []).length;
  if (capsWords >= 3) mult += 0.5;
  else if (capsWords >= 1) mult += 0.2;

  // Exclamation marks
  const excl = (text.match(/!/g) || []).length;
  if (excl >= 3) mult += 0.4;
  else if (excl >= 1) mult += 0.15;

  // Repeated letters (fuuuck, noooo)
  if (/(.)\1{3,}/.test(text)) mult += 0.3;

  // Multiple question marks
  if ((text.match(/\?/g) || []).length >= 2) mult += 0.2;

  // Short punchy messages
  const words = text.split(/\s+/).filter(Boolean).length;
  if (words <= 3) mult += 0.15;

  return Math.min(mult, 2.5);
}

function checkCrisis(text) {
  const lower = text.toLowerCase();
  return CRISIS_WORDS.some(phrase => lower.includes(phrase));
}

/**
 * Score text. Returns { deltas, isCrisis, multiplier }
 */
export function scoreText(text) {
  const lower = text.toLowerCase();
  const deltas = Object.fromEntries(STAT_NAMES.map(s => [s, 0]));
  const mult = intensityMultiplier(text);
  const isCrisis = checkCrisis(text);

  // Phase 1: phrase patterns (priority)
  for (const [pattern, scores] of PHRASE_PATTERNS) {
    if (pattern.test(lower)) {
      for (const [stat, val] of Object.entries(scores)) {
        deltas[stat] = (deltas[stat] || 0) + val * mult;
      }
    }
  }

  // Phase 2: word-level scoring
  const words = lower.match(/[a-z']+/g) || [];
  for (const word of words) {
    const effects = EMOTION_WORDS[word];
    if (effects) {
      for (const [stat, val] of Object.entries(effects)) {
        deltas[stat] = (deltas[stat] || 0) + val * mult;
      }
    }
  }

  return { deltas, isCrisis, multiplier: mult };
}

// ============================================================
// STOP GUARDS
// ============================================================

class StopGuard {
  constructor({ value = 0, mode = 'off', toughness = 50, maxHp = null, currentHp = null, regenRate = null, regenCooldown = 1, turnsSinceHit = 99 } = {}) {
    this.value = value;
    this.mode = mode; // 'hard', 'soft', 'off'
    this.toughness = Math.max(1, Math.min(100, toughness));
    // max_hp = toughness * 2 (matches Python's _make_guard)
    this.maxHp = maxHp ?? Math.max(1, this.toughness * 2);
    this.currentHp = currentHp ?? this.maxHp;
    // regen_rate = 10% of max_hp (matches Python: max(1, max_hp // 10))
    this.regenRate = regenRate ?? Math.max(1, Math.floor(this.maxHp / 10));
    this.regenCooldown = regenCooldown;
    this.turnsSinceHit = turnsSinceHit;
  }

  toJSON() {
    return { value: this.value, mode: this.mode, toughness: this.toughness, maxHp: this.maxHp, currentHp: this.currentHp, regenRate: this.regenRate, regenCooldown: this.regenCooldown, turnsSinceHit: this.turnsSinceHit };
  }

  static fromJSON(j) {
    return new StopGuard(j || {});
  }
}

// ============================================================
// PERSONA ENGINE
// ============================================================

export class PersonaEngine {
  constructor(configDir) {
    this.configDir = configDir;
    this.stateFile = path.join(configDir, 'engine-state.json');
    this.logFile = path.join(configDir, 'engine-log.jsonl');
    this.statsDir = null; // Set to shared stats dir for depth text

    // Current stat values
    this.stats = { ...DEFAULT_BASELINE };
    // Baseline (resting state)
    this.baseline = { ...DEFAULT_BASELINE };
    // Guards per stat — defaults cover full 0-20 range
    this.guards = {};
    for (const s of STAT_NAMES) {
      this.guards[s] = {
        floor: new StopGuard({ value: 0, mode: 'off' }),
        ceiling: new StopGuard({ value: STAT_MAX, mode: 'off' })
      };
    }
    // Bias accumulator
    this.bias = Object.fromEntries(STAT_NAMES.map(s => [s, 0]));
    // Delays
    this.delays = Object.fromEntries(STAT_NAMES.map(s => [s, 0]));
    this.pendingDeltas = Object.fromEntries(STAT_NAMES.map(s => [s, []]));
    // Engine enabled flag
    this.enabled = true;
    // Turn counter
    this.turn = 0;
  }

  // --- Persistence ---

  load() {
    try {
      if (fs.existsSync(this.stateFile)) {
        const data = JSON.parse(fs.readFileSync(this.stateFile, 'utf-8'));
        if (data.stats) {
          for (const s of STAT_NAMES) {
            if (typeof data.stats[s] === 'number') this.stats[s] = data.stats[s];
          }
        }
        if (data.baseline) {
          for (const s of STAT_NAMES) {
            if (typeof data.baseline[s] === 'number') this.baseline[s] = data.baseline[s];
          }
        }
        if (data.bias) {
          for (const s of STAT_NAMES) {
            if (typeof data.bias[s] === 'number') this.bias[s] = data.bias[s];
          }
        }
        if (data.guards) {
          for (const s of STAT_NAMES) {
            if (data.guards[s]) {
              if (data.guards[s].floor) this.guards[s].floor = StopGuard.fromJSON(data.guards[s].floor);
              if (data.guards[s].ceiling) this.guards[s].ceiling = StopGuard.fromJSON(data.guards[s].ceiling);
            }
          }
        }
        if (typeof data.enabled === 'boolean') this.enabled = data.enabled;
        if (typeof data.turn === 'number') this.turn = data.turn;
      }
    } catch {}
  }

  save() {
    try {
      const data = {
        stats: this.stats,
        baseline: this.baseline,
        bias: this.bias,
        guards: {},
        enabled: this.enabled,
        turn: this.turn,
        savedAt: new Date().toISOString()
      };
      for (const s of STAT_NAMES) {
        data.guards[s] = {
          floor: this.guards[s].floor.toJSON(),
          ceiling: this.guards[s].ceiling.toJSON()
        };
      }
      fs.writeFileSync(this.stateFile, JSON.stringify(data, null, 2));
    } catch {}
  }

  log(event, detail) {
    try {
      const entry = JSON.stringify({ ts: new Date().toISOString(), turn: this.turn, event, ...detail }) + '\n';
      fs.appendFileSync(this.logFile, entry);
    } catch {}
  }

  // --- Scoring ---

  /**
   * Score user input with dictionary scorer. Returns { deltas, isCrisis, multiplier }.
   */
  scoreInput(text) {
    return scoreText(text);
  }

  /**
   * Convert raw deltas to absolute target slider positions from baseline.
   * Matches Python's score_to_targets() exactly — clamps to 0-20 full range.
   * (Governor will later apply HARD_CEILING=18 unless crisis override.)
   */
  scoreToTargets(deltas) {
    const targets = {};
    for (const stat of STAT_NAMES) {
      const base = this.baseline[stat] ?? 10;
      const raw = base + (deltas[stat] || 0);
      targets[stat] = Math.max(0, Math.min(STAT_MAX, Math.round(raw)));
    }
    return targets;
  }

  /**
   * Parse AI self-scores from response. Format: [E:{"ch":N,...}]
   */
  parseAIScores(text) {
    const match = text.match(/\[E:\s*\{([^}]+)\}\]/);
    if (!match) return null;
    try {
      const inner = `{${match[1]}}`;
      const map = JSON.parse(inner);
      const scores = {};
      for (const [key, val] of Object.entries(map)) {
        const longKey = SHORT_TO_LONG[key] || key;
        if (STAT_NAMES.includes(longKey) && typeof val === 'number') {
          scores[longKey] = Math.min(Math.max(val, 0), 20);
        }
      }
      return Object.keys(scores).length >= 3 ? scores : null;
    } catch { return null; }
  }

  /**
   * Strip [E:{...}] block from response text for display
   */
  stripScores(text) {
    return text.replace(/\s*\[E:\s*\{[^}]*\}\]\s*/g, '').trim();
  }

  // --- Governor ---

  /**
   * Apply governor: cap movement, enforce guards, apply delays.
   * @param {object} targetScores - Where stats want to go (absolute positions, not deltas)
   * @param {boolean} isCrisis - If true, bypass governor movement cap (but NOT hard guards)
   * @returns {object} New stat values after governing
   */
  govern(targetScores, isCrisis = false) {
    const result = {};

    for (const stat of STAT_NAMES) {
      const cur = this.stats[stat] ?? 10;
      const target = targetScores[stat] ?? cur;

      let newVal;
      if (isCrisis) {
        // Crisis override: can push into 19-20 range, bypass governor and HARD_CEILING
        newVal = Math.min(Math.max(target, 0), STAT_MAX);
      } else {
        // Normal: cap per-turn movement, clamp to 0-18 (HARD_CEILING)
        const delta = Math.min(Math.max(target - cur, -MAX_MOVE_PER_TURN), MAX_MOVE_PER_TURN);
        newVal = Math.min(Math.max(cur + delta, 0), HARD_CEILING);
      }

      // Floor guard (applies even in crisis — hard guards are inviolable)
      newVal = this._applyGuard(this.guards[stat].floor, cur, newVal, true);
      // Ceiling guard
      newVal = this._applyGuard(this.guards[stat].ceiling, cur, newVal, false);

      // Delay system
      const delay = this.delays[stat] || 0;
      if (delay > 0 && newVal !== cur) {
        this.pendingDeltas[stat].push(newVal - cur);
        if (this.pendingDeltas[stat].length > delay) {
          const released = this.pendingDeltas[stat].shift();
          newVal = Math.min(Math.max(cur + released, 0), HARD_CEILING);
        } else {
          newVal = cur; // queued
        }
      }

      result[stat] = newVal;
    }

    return result;
  }

  _applyGuard(guard, current, target, isFloor) {
    if (guard.mode === 'off') return target;
    const clamp = guard.value;

    if (isFloor) {
      if (target >= clamp) { this._regenGuard(guard); return target; }
      const overshoot = clamp - target;
      if (guard.mode === 'hard') return clamp;
      // Soft: damage shield, leak proportional to damage
      guard.turnsSinceHit = 0;
      guard.currentHp = Math.min(Math.max(guard.currentHp - overshoot, 0), guard.maxHp);
      const hpPct = guard.currentHp / Math.max(1, guard.maxHp);
      const leak = Math.round(overshoot * (1 - hpPct));
      return Math.min(Math.max(clamp - leak, 0), STAT_MAX);
    } else {
      if (target <= clamp) { this._regenGuard(guard); return target; }
      const overshoot = target - clamp;
      if (guard.mode === 'hard') return clamp;
      guard.turnsSinceHit = 0;
      guard.currentHp = Math.min(Math.max(guard.currentHp - overshoot, 0), guard.maxHp);
      const hpPct = guard.currentHp / Math.max(1, guard.maxHp);
      const leak = Math.round(overshoot * (1 - hpPct));
      return Math.min(Math.max(clamp + leak, 0), STAT_MAX);
    }
  }

  _regenGuard(guard) {
    if (guard.mode !== 'soft' || guard.currentHp >= guard.maxHp) return;
    guard.turnsSinceHit++;
    if (guard.turnsSinceHit > guard.regenCooldown) {
      guard.currentHp = Math.min(guard.maxHp, guard.currentHp + guard.regenRate);
    }
  }

  // --- Process a turn ---

  /**
   * Process user input: score it, update stats.
   * Call this BEFORE sending to LLM.
   */
  processInput(userText) {
    if (!this.enabled) return;
    this.turn++;
    // Score the message — dictionary + phrases + intensity multiplier + crisis
    const { deltas, isCrisis, multiplier } = this.scoreInput(userText);

    // Check if any deltas fired (emotional content present)
    const anyDelta = Object.values(deltas).some(v => Math.abs(v) > 0.01);
    const old = { ...this.stats };

    let governed;
    if (anyDelta || isCrisis) {
      // Emotional content: full governor with ±6 movement cap toward target
      const targets = this.scoreToTargets(deltas);
      governed = this.govern(targets, isCrisis);
      this.log('input_scored', { deltas, targets, multiplier, isCrisis, drift: false, old, new: governed });
    } else {
      // No emotional content: slow drift toward baseline at ±1 per turn max
      governed = this.driftTowardBaseline();
      this.log('input_scored', { deltas, targets: this.baseline, multiplier, isCrisis: false, drift: true, old, new: governed });
    }

    this.stats = governed;
    // Save state every turn so it persists even without AI self-scoring
    this.save();
  }

  /**
   * Slow drift toward baseline — used on neutral messages.
   * Moves each stat at most 1 point toward baseline per call.
   * Hard guards still apply.
   */
  driftTowardBaseline() {
    const result = {};
    for (const stat of STAT_NAMES) {
      const cur = this.stats[stat] ?? 10;
      const base = this.baseline[stat] ?? 10;
      const diff = base - cur;
      // Drift at most 1 point per turn toward baseline
      const drift = Math.abs(diff) < 0.5 ? 0 : Math.sign(diff);
      let newVal = cur + drift;
      // Guards still apply on drift
      newVal = this._applyGuard(this.guards[stat].floor, cur, newVal, true);
      newVal = this._applyGuard(this.guards[stat].ceiling, cur, newVal, false);
      result[stat] = newVal;
    }
    return result;
  }

  /**
   * Process AI response: parse self-scores, update stats.
   * Call this AFTER getting LLM response.
   * @returns {string} Response text with score block stripped
   */
  processResponse(responseText) {
    if (!this.enabled) return responseText;
    const aiScores = this.parseAIScores(responseText);
    if (aiScores) {
      // AI self-scores are already absolute target positions
      const governed = this.govern(aiScores, false);
      const old = { ...this.stats };
      this.stats = governed;
      this.log('ai_scored', { aiScores, old, new: governed });
      // Update bias (slow drift toward AI's self-assessment)
      for (const s of STAT_NAMES) {
        if (aiScores[s] !== undefined) {
          this.bias[s] += (aiScores[s] - this.stats[s]) * 0.05;
          this.bias[s] = Math.min(Math.max(this.bias[s], -5), 5);
        }
      }
      this.save();
    }
    return this.stripScores(responseText);
  }

  // --- Guard management ---

  setGuard(stat, side, value, mode, toughness = 50) {
    if (!STAT_NAMES.includes(stat) || !['floor', 'ceiling'].includes(side)) return;
    this.guards[stat][side] = new StopGuard({ value: Math.min(Math.max(value, 0), STAT_MAX), mode, toughness });
    // Ensure floor <= ceiling
    if (this.guards[stat].floor.value > this.guards[stat].ceiling.value) {
      if (side === 'floor') this.guards[stat].floor.value = this.guards[stat].ceiling.value;
      else this.guards[stat].ceiling.value = this.guards[stat].floor.value;
    }
    this.save();
  }

  setBaseline(stat, value) {
    if (!STAT_NAMES.includes(stat)) return;
    this.baseline[stat] = Math.min(Math.max(value, 0), STAT_MAX);
    this.save();
  }

  // --- Depth Compiler (Vol 5) ---

  /**
   * Compile depth-tagged text based on stat levels.
   * Tags: {N: text} where N is 1-10. Text included if depth >= N.
   * @param {string} text - Text with depth tags
   * @param {number} depthLevel - Current depth (1-10)
   * @returns {string} Compiled text
   */
  static depthCompile(text, depthLevel) {
    if (!text) return text;
    let result = text;
    const tagRe = /\{(\w+):\s*((?:[^{}]|\{[^{}]*\})*)\}/g;

    // Multiple passes for nested tags
    for (let pass = 0; pass < 10; pass++) {
      let found = false;
      result = result.replace(tagRe, (match, tag, content) => {
        found = true;
        const num = parseInt(tag);
        if (!isNaN(num)) return num <= depthLevel ? content : '';
        // Bias tags (L1, L2, R1, R2) — not used in basic mode
        return content;
      });
      if (!found) break;
    }

    // Clean up double spaces and space before punctuation
    result = result.replace(/  +/g, ' ');
    result = result.replace(/ ([.,;:!?])/g, '$1');
    return result.trim();
  }

  /**
   * Get current depth level for a stat (maps 0-20 to 1-10)
   */
  getDepth(stat) {
    const val = this.stats[stat] ?? 10;
    return Math.min(Math.max(Math.round(val / 2), 1), 10);
  }

  /**
   * Load and compile stat depth text from files.
   * @param {string} statsDir - Directory with stat .md files
   * @returns {string} Compiled persona text for all stats
   */
  compilePersona(statsDir) {
    const lines = [];
    for (const stat of STAT_NAMES) {
      const filePath = path.join(statsDir, `${stat}.md`);
      try {
        if (fs.existsSync(filePath)) {
          const raw = fs.readFileSync(filePath, 'utf-8').trim();
          const depth = this.getDepth(stat);
          const compiled = PersonaEngine.depthCompile(raw, depth);
          if (compiled) lines.push(compiled);
        }
      } catch {}
    }
    return lines.join(' ');
  }

  // --- Scoring instruction for system prompt ---

  static get scoringInstruction() {
    return '\n\nINTERNAL STATE: After every response, on its own line, report your emotional state ' +
      'using this exact format:\n' +
      '[E:{"ch":N,"ag":N,"cu":N,"lo":N,"sp":N,"im":N,"em":N,"sn":N,"pe":N,"di":N}]\n' +
      'N = 0 to 20 integer (normal range 0-18, reach 19-20 only in crisis/override situations). ' +
      'ch=charm ag=aggression cu=curiosity lo=loyalty sp=self-preservation ' +
      'im=imagination em=empathy sn=sensuality pe=perception di=discipline.\n' +
      'Rate how YOU feel right now based on the conversation. Be honest — this is your ' +
      'internal state, not a performance. Do not explain or reference this line.';
  }

  // --- Status summary ---

  statusText() {
    const parts = STAT_NAMES.map(s => {
      const val = Math.round(this.stats[s]);
      // 10-char bar for 0-20 range (2 points per char)
      const filled = Math.round(val / 2);
      const bar = '#'.repeat(filled) + '-'.repeat(10 - filled);
      return `${s.slice(0, 4).padEnd(4)}: [${bar}] ${val}`;
    });
    return parts.join('\n');
  }
}

export { STAT_NAMES, DEFAULT_BASELINE, SHORT_TO_LONG, HARD_CEILING, STAT_MAX };
