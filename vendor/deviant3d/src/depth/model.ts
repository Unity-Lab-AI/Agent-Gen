/* Real monocular DEPTH from a single image — the measurement the equational engine builds the 3D
 * from. Runs a Depth-Anything-V2 model IN THE BROWSER via transformers.js on WebGPU, no server. The
 * model gives real per-pixel relative depth; the engine fits its equations to those numbers instead
 * of guessing shape from shading. The equations stay ours — this is the tape measure.
 *
 * NO FALLBACKS (LAW): WebGPU is required; if it's absent this THROWS a clear error. There is no
 * silent WASM/CPU swap and no coarse substitute. Lazy dynamic import so the model only downloads
 * when the user asks for it; the main bundle never carries it. */

export interface DepthResult {
  /** per-pixel depth, row-major, normalized [0,1] with 0 = NEAREST, 1 = farthest */
  depth: Float32Array;
  width: number;
  height: number;
}

export type DepthProgress = (msg: string, frac: number) => void;

/** the selectable depth models — auto-downloaded on first use of each. */
export interface DepthModelDef { id: string; label: string; repo: string; note: string }
export const DEPTH_MODELS: DepthModelDef[] = [
  { id: 'da2-small', label: 'Depth-Anything v2 · Small', repo: 'onnx-community/depth-anything-v2-small', note: 'fast, ~50 MB — good default' },
  { id: 'da2-base', label: 'Depth-Anything v2 · Base', repo: 'onnx-community/depth-anything-v2-base', note: 'sharper, ~200 MB' },
  { id: 'da-small-hf', label: 'Depth-Anything v1 · Small', repo: 'Xenova/depth-anything-small-hf', note: 'v1 fallback-free alt, ~50 MB' },
];

interface RawImageLike { data: Uint8Array | Uint8ClampedArray | Float32Array; width: number; height: number; channels: number }
type DepthPipe = (input: unknown) => Promise<{ depth: RawImageLike }>;

// one cached pipeline per model id (each downloads + compiles once)
const pipes = new Map<string, Promise<unknown>>();

/** true only when the browser exposes WebGPU — the required backend (no fallback) */
export function depthAvailable(): boolean {
  return typeof navigator !== 'undefined' && 'gpu' in navigator;
}

/** download + warm a chosen model (idempotent per model). Reports progress. */
export async function loadDepthModel(modelId: string, onProgress?: DepthProgress): Promise<void> {
  if (!depthAvailable()) throw new Error('AI depth needs WebGPU — this browser has none. Use a WebGPU browser (recent Chrome/Edge). No fallback by design.');
  const def = DEPTH_MODELS.find(m => m.id === modelId);
  if (!def) throw new Error(`unknown depth model "${modelId}"`);
  if (pipes.has(modelId)) { await pipes.get(modelId); return; }
  const tf = await import('@huggingface/transformers');
  const p = tf.pipeline('depth-estimation', def.repo, {
    device: 'webgpu',
    dtype: 'fp32',
    progress_callback: (pr: unknown) => {
      const o = pr as { status?: string; file?: string; progress?: number };
      if (onProgress) onProgress(o.file ? `${o.status ?? 'loading'} ${o.file}` : (o.status ?? 'loading'), (o.progress ?? 0) / 100);
    },
  });
  pipes.set(modelId, p);
  await p;
}

/** estimate depth for an image with a chosen (already-loaded or auto-loaded) model. */
export async function estimateDepth(img: ImageData, modelId: string, onProgress?: DepthProgress): Promise<DepthResult> {
  await loadDepthModel(modelId, onProgress);
  const tf = await import('@huggingface/transformers');
  const pipe = (await pipes.get(modelId)!) as unknown as DepthPipe;

  const raw = new tf.RawImage(new Uint8ClampedArray(img.data), img.width, img.height, 4);
  const out = await pipe(raw);
  const d = out.depth;
  const ch = d.channels || 1;
  const n = d.width * d.height;

  // Depth-Anything outputs HIGHER = NEARER; normalize + invert to our 0=near..1=far convention
  let mn = Infinity, mx = -Infinity;
  for (let i = 0; i < n; i++) { const v = d.data[i * ch]!; if (v < mn) mn = v; if (v > mx) mx = v; }
  const span = mx - mn || 1;
  const depth = new Float32Array(n);
  for (let i = 0; i < n; i++) depth[i] = 1 - (d.data[i * ch]! - mn) / span;

  return { depth, width: d.width, height: d.height };
}
