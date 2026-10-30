/* D-022 — the render→critique→revise loop. The program renders the brain's SceneScript, captures
 * turntable views, the brain critiques its own output against the source image, revises the script,
 * and converges. Act, verify from the actual render, iterate — never a blind one-shot.
 *
 * Renderer-agnostic by construction: render + critique are injected. Today the classical/ollama
 * brains author the first script and a trivial critique can pass it through; when the WebGPU
 * renderer (D-060) and a real critic land, they drop straight into these callback slots with no
 * change to the loop itself. */

import type { AgentBriefing, SceneScript, RenderCritique, Segment } from './schema';
import { validateSceneScript } from './schema';

/** produce the first SceneScript from a briefing (agent / ollama / classical all fit this shape) */
export type SceneAuthor = (briefing: AgentBriefing) => Promise<SceneScript> | SceneScript;

/** render the current script to turntable/orbit view data URLs (WebGPU renderer plugs in here) */
export type RenderFn = (script: SceneScript) => Promise<string[]> | string[];

/** judge the rendered views against the source and return per-segment verdicts */
export type CritiqueFn = (
  script: SceneScript,
  views: string[],
  briefing: AgentBriefing,
) => Promise<RenderCritique> | RenderCritique;

export interface SceneLoopOptions {
  author: SceneAuthor;
  render: RenderFn;
  critique: CritiqueFn;
  /** hard cap on revise rounds (default 3) — convergence usually comes sooner */
  maxRounds?: number;
}

export interface SceneLoopResult {
  script: SceneScript;
  converged: boolean;
  rounds: number;
  /** the render views from the final accepted round (for the UI to show / capture) */
  finalViews: string[];
}

/** apply a critique's verdicts to a script, swapping in each revised segment by id.
 * Unknown ids and malformed revisions are ignored — the loop never corrupts a valid script. */
export function applyVerdicts(script: SceneScript, critique: RenderCritique): SceneScript {
  const revisedById = new Map<string, Segment>();
  for (const v of critique.verdicts) {
    if (v.verdict === 'revise' && v.revised && v.revised.id === v.id) {
      revisedById.set(v.id, v.revised);
    }
  }
  if (revisedById.size === 0) return script;
  return {
    ...script,
    segments: script.segments.map(s => revisedById.get(s.id) ?? s),
  };
}

/** run the full author → (render → critique → revise)* loop until converged or maxRounds hit. */
export async function runSceneLoop(
  briefing: AgentBriefing,
  opts: SceneLoopOptions,
): Promise<SceneLoopResult> {
  const maxRounds = Math.max(1, Math.floor(opts.maxRounds ?? 3));

  let script = await opts.author(briefing);
  if (!validateSceneScript(script)) {
    throw new Error('scene author produced an invalid SceneScript');
  }

  let views: string[] = [];
  let converged = false;
  let round = 0;

  for (; round < maxRounds; round++) {
    views = await opts.render(script);
    const critique = await opts.critique(script, views, briefing);
    if (critique.converged) { converged = true; break; }

    const next = applyVerdicts(script, critique);
    // no changes accepted this round → nothing more to gain, stop honestly (not "converged")
    if (next === script) break;
    script = next;
  }

  return { script, converged, rounds: round + 1, finalViews: views };
}

/** a pass-through critic: accepts the script as-is on the first render. Useful for the walking
 * skeleton (classical author + no real critic yet) and as the default when no critic is wired. */
export const acceptFirstRender: CritiqueFn = (script) => ({
  views: [],
  verdicts: script.segments.map(s => ({ id: s.id, verdict: 'keep' as const, reason: 'no critic wired — accepted as authored' })),
  converged: true,
});
