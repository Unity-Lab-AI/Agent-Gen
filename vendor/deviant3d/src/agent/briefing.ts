/* D-020 — the AGENT BRIEFING builder. Packages a measured SceneAnalysis + the image itself
 * into the compact `AgentBriefing` the brain reads before authoring a SceneScript.
 *
 * Pure / DOM-free: the caller supplies the image as a data URL (the main thread has the canvas
 * to make one; a worker or node caller passes whatever it already holds). The big 48² fields are
 * block-averaged down to a compact brief grid so the brain reasons over structure, not a flood of
 * raw cells — the full-resolution maths stays in the pipeline for the depth compiler. */

import type { SceneAnalysis } from '../analysis/types';
import type { AgentBriefing } from './schema';

/** default brief-grid resolution — coarse enough to read, fine enough to locate regions */
const BRIEF_GRID = 16;

/** block-average a row-major grid down to gridN×gridN; returns gridN rows of gridN numbers.
 * Handles any source dimensions ≥1 (each target cell averages the source cells it covers). */
function downsampleGrid(src: number[][], gridN: number): number[][] {
  const sh = src.length;
  const sw = sh > 0 ? src[0]!.length : 0;
  if (sh === 0 || sw === 0) {
    return Array.from({ length: gridN }, () => new Array<number>(gridN).fill(0));
  }
  const out: number[][] = [];
  for (let ty = 0; ty < gridN; ty++) {
    const y0 = Math.floor((ty * sh) / gridN);
    const y1 = Math.max(y0 + 1, Math.floor(((ty + 1) * sh) / gridN));
    const row = new Array<number>(gridN);
    for (let tx = 0; tx < gridN; tx++) {
      const x0 = Math.floor((tx * sw) / gridN);
      const x1 = Math.max(x0 + 1, Math.floor(((tx + 1) * sw) / gridN));
      let sum = 0, n = 0;
      for (let y = y0; y < y1 && y < sh; y++) {
        const srow = src[y]!;
        for (let x = x0; x < x1 && x < sw; x++) { sum += srow[x]!; n++; }
      }
      row[tx] = n > 0 ? sum / n : 0;
    }
    out.push(row);
  }
  return out;
}

export interface BriefingOptions {
  /** brief-grid resolution for the entropy + lumen density fields (default 16) */
  gridN?: number;
  /** cap on how many structural lines travel in the brief (strongest kept; default 32) */
  maxLines?: number;
}

/** build the briefing from measured maths + the image (as a data URL the caller already made). */
export function buildBriefing(
  analysis: SceneAnalysis,
  imageDataUrl: string,
  opts: BriefingOptions = {},
): AgentBriefing {
  const gridN = Math.max(2, Math.floor(opts.gridN ?? BRIEF_GRID));
  const maxLines = Math.max(1, Math.floor(opts.maxLines ?? 32));

  // strongest structural lines first (perspective/vanishing evidence), capped
  const lines = [...analysis.lines]
    .sort((a, b) => b.length - a.length)
    .slice(0, maxLines);

  return {
    width: analysis.width,
    height: analysis.height,
    imageDataUrl,
    palette: analysis.palette,
    lines,
    collapse: analysis.collapse,
    entropyGrid: downsampleGrid(analysis.entropy, gridN),
    lumenDensityGrid: downsampleGrid(analysis.lumenDensity, gridN),
    edgeDensity: analysis.edgeDensity,
    meanLuminance: analysis.meanLuminance,
  };
}
