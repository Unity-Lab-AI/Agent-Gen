/* Scene RECOGNITION — the measurement that tells the equational engine WHAT the subject is, so it
 * builds the CORRECT back (a person's rear, an apple's revolved reverse, a flatscreen's walk-behind
 * box) instead of one dumb mirror-shell for everything (the "chocolate Easter bunny" — right on the
 * front, wrong on the back). This is a MEASUREMENT model, exactly like the depth model: it MEASURES
 * what/where, it does NOT generate. The back is still synthesized EQUATIONALLY (mode-E from the
 * image's own field) — recognition only chooses which continuation EQUATION to run.
 *
 * Runs an object-detection model (COCO-80) IN THE BROWSER via transformers.js on WebGPU, no server.
 * NO FALLBACKS (LAW): WebGPU required; absent → THROWS. Lazy dynamic import so it's code-split and
 * only downloads when an image is actually built. */

/** one detected object — box is normalized [xmin, ymin, xmax, ymax] in 0..1 */
export interface Detection { label: string; score: number; box: [number, number, number, number] }
/** the chosen main subject. `fullness` is a continuous ROUNDNESS BIAS in [0,1] the label suggests
 * (how much the reverse bulges beyond the object's own medial surface): organic bodies bulge full,
 * flat panels stay thin. It is only a BIAS — the back SHAPE is built dynamically from the object's
 * OWN measured geometry (depthMesh), so ANY object is handled. `fullness=null` (unknown label) →
 * depthMesh derives the roundness entirely from the measured convexity. No preset per-class shapes. */
export interface Subject extends Detection { fullness: number | null }
export interface RecognitionResult { detections: Detection[]; subject: Subject | null }

export type RecogProgress = (msg: string, frac: number) => void;

/** the selectable recognition models — auto-downloaded on first use of each. */
export interface RecogModelDef { id: string; label: string; repo: string; note: string }
export const RECOGNITION_MODELS: RecogModelDef[] = [
  { id: 'yolos-tiny', label: 'YOLOS · Tiny (COCO-80)', repo: 'Xenova/yolos-tiny', note: 'fast, ~26 MB — good default' },
  { id: 'detr-r50', label: 'DETR · ResNet-50 (COCO-80)', repo: 'Xenova/detr-resnet-50', note: 'sharper, ~160 MB' },
];

// COCO-80 label → a ROUNDNESS BIAS in [0,1]. This is NOT a shape bucket — it only nudges how much the
// dynamically-built back (the object's own measured medial surface continued) bulges. A label we don't
// have an opinion on returns null → depthMesh reads the roundness straight off the measured geometry,
// so the pipeline handles ANY object, listed or not. High = organic/round, low = flat panel.
const ROUND = new Set(['person', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'bird', 'teddy bear', 'potted plant', 'apple', 'orange', 'sports ball', 'donut']);
const MID = new Set(['banana', 'wine glass', 'cup', 'bottle', 'vase', 'bowl', 'backpack', 'umbrella', 'handbag', 'carrot', 'hot dog', 'fire hydrant']);
const FLAT = new Set(['tv', 'laptop', 'cell phone', 'book', 'microwave', 'oven', 'refrigerator', 'keyboard', 'remote', 'toaster', 'suitcase', 'monitor', 'traffic light', 'stop sign', 'dining table', 'bench', 'surfboard', 'skateboard', 'frisbee']);

/** the label's roundness BIAS in [0,1], or null when we have no opinion (→ measure it in depthMesh). */
export function fullnessBias(label: string): number | null {
  const l = label.toLowerCase();
  if (ROUND.has(l)) return 0.9;
  if (MID.has(l)) return 0.55;
  if (FLAT.has(l)) return 0.12;
  return null;                                          // unknown → depthMesh derives it from geometry
}

type DetOut = Array<{ score: number; label: string; box: { xmin: number; ymin: number; xmax: number; ymax: number } }>;
type DetPipe = (input: unknown, opts: { threshold: number; percentage: boolean }) => Promise<DetOut>;

const pipes = new Map<string, Promise<unknown>>();

/** true only when the browser exposes WebGPU — the required backend (no fallback) */
export function recognitionAvailable(): boolean {
  return typeof navigator !== 'undefined' && 'gpu' in navigator;
}

/** download + warm a chosen recognition model (idempotent per model). Reports progress. */
export async function loadRecognitionModel(modelId: string, onProgress?: RecogProgress): Promise<void> {
  if (!recognitionAvailable()) throw new Error('scene recognition needs WebGPU — this browser has none. Use a WebGPU browser (recent Chrome/Edge). No fallback by design.');
  const def = RECOGNITION_MODELS.find(m => m.id === modelId);
  if (!def) throw new Error(`unknown recognition model "${modelId}"`);
  if (pipes.has(modelId)) { await pipes.get(modelId); return; }
  const tf = await import('@huggingface/transformers');
  const p = tf.pipeline('object-detection', def.repo, {
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

/** recognise the objects in an image + choose the main subject (largest confident detection).
 * A landscape with no confident foreground object returns subject=null — that's a real measurement
 * (scenery), not a failure: the world builds as relief + 360 environment with no closed solid. */
export async function recognize(img: ImageData, modelId: string, onProgress?: RecogProgress): Promise<RecognitionResult> {
  await loadRecognitionModel(modelId, onProgress);
  const tf = await import('@huggingface/transformers');
  const pipe = (await pipes.get(modelId)!) as unknown as DetPipe;

  const raw = new tf.RawImage(new Uint8ClampedArray(img.data), img.width, img.height, 4);
  const out = await pipe(raw, { threshold: 0.35, percentage: true });
  if (!Array.isArray(out)) throw new Error('recognition model returned an unexpected shape');

  const detections: Detection[] = out.map(o => ({
    label: o.label,
    score: o.score,
    box: [o.box.xmin, o.box.ymin, o.box.xmax, o.box.ymax],
  }));

  // main subject = the detection that dominates the frame (area × confidence) — the "main focus"
  let subject: Subject | null = null;
  let best = 0;
  for (const d of detections) {
    const area = Math.max(0, d.box[2] - d.box[0]) * Math.max(0, d.box[3] - d.box[1]);
    const w = area * d.score;
    if (w > best) { best = w; subject = { ...d, fullness: fullnessBias(d.label) }; }
  }
  return { detections, subject };
}
