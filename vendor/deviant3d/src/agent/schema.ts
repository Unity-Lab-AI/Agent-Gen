/* The AI contract — the typed language between the program and the brain that drives it.
 *
 * IN:  AgentBriefing — the image + its measured maths, packaged for the brain to read.
 * OUT: SceneScript   — the brain's equational scene authoring: segments, geometry classes,
 *                      depth control points, occlusion directives. The program compiles this
 *                      into depth fields + back-content and renders the 3D world.
 *
 * The same contract is spoken by: the coding agent at the keyboard (primary), an
 * ollama-local vision model (offline alternative), or the classical-cues fallback
 * (no AI — honest coarse mode, labeled). */

import type { PaletteEntry, LineSegment, VectorCollapse } from '../analysis/types';

/** normalized image coordinates: x,y in [0,1] (origin top-left) */
export interface Pt { x: number; y: number }

/** a depth control point: at (x,y), the surface sits at depth z (0 = nearest, 1 = farthest) */
export interface DepthPoint extends Pt { z: number }

export type GeometryClass =
  | 'ground-plane'   // floors, roads, water — a receding plane
  | 'sky-dome'       // sky, distant backdrop — far shell
  | 'billboard'      // thin upright thing at a depth (a person at distance)
  | 'relief'         // front surface with modulated depth (faces, foliage, furniture)
  | 'revolution'     // solid of revolution — fruit, vases, bottles (its back is its profile revolved)
  | 'box'            // room interiors / buildings — planar faces meeting at edges
  | 'freeform';      // anything else — depth entirely from control points

/** how the unseen side of a segment gets its content */
export type OcclusionDirective =
  | 'revolve-profile'   // revolution class: the silhouette profile swept around the axis
  | 'mirror-vary'       // mirrored front appearance with variation (people, symmetric objects)
  | 'extend-texture'    // continue the surface statistics (ground, walls, foliage)
  | 'none';             // nothing behind (sky, background shells)

export interface Segment {
  /** stable id the critique loop refers back to */
  id: string;
  /** what the brain says this is — "apple", "woman", "dirt floor" (display + reasoning label) */
  label: string;
  geometry: GeometryClass;
  /** closed polygon mask, normalized coords, ≥3 points */
  polygon: Pt[];
  /** sparse depth control points the depth field is fitted through */
  depth: DepthPoint[];
  /** for 'revolution': the rotation axis (two points); for 'box': dominant vanishing direction */
  axis?: [Pt, Pt];
  occlusion: OcclusionDirective;
  /** rendering order hint: lower = nearer (resolves overlaps between segments) */
  layer: number;
  /** free-text note from the brain — why it read the geometry this way (provenance) */
  note?: string;
}

export interface SceneScript {
  schema: 'deviant3d-scene@1';
  /** who authored it — provenance travels with the scene */
  author: 'agent' | 'ollama' | 'classical-fallback';
  segments: Segment[];
  /** ground plane fit: horizon height y (0..1) + tilt in radians; null when no ground read */
  horizon: { y: number; tilt: number } | null;
  /** suggested camera start: position depth (0..1) + look-at point */
  camera: { z: number; lookAt: Pt };
  /** overall scene depth scale in metres-equivalent (how deep the world feels) */
  depthScale: number;
  /** free-text scene reading — one paragraph of what the brain saw */
  reading: string;
}

/** the measured-maths package the brain reads before authoring */
export interface AgentBriefing {
  width: number;
  height: number;
  /** the image itself, as a data URL (vision models + the agent both read it) */
  imageDataUrl: string;
  palette: PaletteEntry[];
  /** strongest structural lines (perspective/vanishing evidence) */
  lines: LineSegment[];
  collapse: VectorCollapse;
  /** coarse grids, row-major, for spatial reasoning without pixel access */
  entropyGrid: number[][];
  lumenDensityGrid: number[][];
  edgeDensity: number;
  meanLuminance: number;
}

/** one round of the render→critique→revise loop */
export interface RenderCritique {
  /** turntable/orbit captures of the current scene render, as data URLs */
  views: string[];
  /** the brain's verdict per segment: keep, or a revised segment */
  verdicts: Array<{ id: string; verdict: 'keep' | 'revise'; revised?: Segment; reason: string }>;
  /** true when the scene matches the source well enough to ship */
  converged: boolean;
}

/** runtime validation — a script from ANY author (agent, ollama, fallback) is checked
 * before it touches the pipeline; integrity bounds are always on. */
export function validateSceneScript(s: unknown): s is SceneScript {
  if (typeof s !== 'object' || s === null) return false;
  const o = s as Record<string, unknown>;
  if (o['schema'] !== 'deviant3d-scene@1') return false;
  if (!Array.isArray(o['segments'])) return false;
  for (const seg of o['segments'] as unknown[]) {
    if (typeof seg !== 'object' || seg === null) return false;
    const g = seg as Record<string, unknown>;
    if (typeof g['id'] !== 'string' || typeof g['label'] !== 'string') return false;
    if (!Array.isArray(g['polygon']) || (g['polygon'] as unknown[]).length < 3) return false;
    if (!Array.isArray(g['depth'])) return false;
    for (const p of g['polygon'] as Array<Record<string, unknown>>) {
      if (typeof p['x'] !== 'number' || typeof p['y'] !== 'number') return false;
      if (p['x'] < -0.5 || p['x'] > 1.5 || p['y'] < -0.5 || p['y'] > 1.5) return false;
    }
    for (const p of g['depth'] as Array<Record<string, unknown>>) {
      if (typeof p['z'] !== 'number' || p['z'] < 0 || p['z'] > 1) return false;
    }
  }
  return true;
}
