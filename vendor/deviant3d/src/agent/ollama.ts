/* D-023 — the OLLAMA-LOCAL alternative brain. The exact same briefing→SceneScript contract the
 * coding agent speaks, spoken instead to a local vision model (llava / qwen-vl class) over the
 * ollama HTTP API. Fully offline batch path for when no agent is at the keyboard.
 *
 * NO FALLBACK (LAW): ollamaSceneScript returns a validated SceneScript or THROWS. There is no silent
 * classical substitute; a failed/absent brain surfaces loudly to the caller. */

import type { AgentBriefing, SceneScript } from './schema';
import { validateSceneScript } from './schema';

export interface OllamaOptions {
  /** base URL of the ollama server (default the local daemon) */
  endpoint?: string;
  /** vision model tag (must be pulled locally, e.g. 'llava', 'qwen2.5vl') */
  model?: string;
  /** abort the request after this many ms (default 120s — vision on CPU is slow) */
  timeoutMs?: number;
}

const DEFAULT_ENDPOINT = 'http://localhost:11434';
const DEFAULT_MODEL = 'llava';

/** the schema contract, spelled out for the model — the same geometry/occlusion vocabulary as schema.ts */
function systemPrompt(): string {
  return [
    'You are the scene-understanding brain for a photo-to-3D engine. You receive one image plus',
    'measured maths about it, and you must author a SceneScript: a segmentation of the image into',
    '3D geometry so the scene can be flown through and objects circled behind.',
    '',
    'Reply with ONE JSON object, no prose, matching exactly:',
    '{',
    '  "schema": "deviant3d-scene@1",',
    '  "author": "ollama",',
    '  "segments": [{',
    '    "id": string, "label": string,',
    '    "geometry": "ground-plane"|"sky-dome"|"billboard"|"relief"|"revolution"|"box"|"freeform",',
    '    "polygon": [{"x":0..1,"y":0..1}, ...>=3 points, normalized, origin top-left],',
    '    "depth": [{"x":0..1,"y":0..1,"z":0..1}, ...]  (z: 0=nearest, 1=farthest),',
    '    "axis": [{"x","y"},{"x","y"}] (only for revolution/box),',
    '    "occlusion": "revolve-profile"|"mirror-vary"|"extend-texture"|"none",',
    '    "layer": number (lower = nearer),',
    '    "note": string',
    '  }],',
    '  "horizon": {"y":0..1,"tilt":radians} | null,',
    '  "camera": {"z":0..1,"lookAt":{"x","y"}},',
    '  "depthScale": number,',
    '  "reading": string (one paragraph: what you see)',
    '}',
    '',
    'Geometry guide: fruit/vases/bottles = "revolution" (back = profile revolved, occlusion',
    '"revolve-profile"); people = "billboard" or "relief" (occlusion "mirror-vary"); floors/roads/',
    'water = "ground-plane"; sky/distant backdrop = "sky-dome" (occlusion "none"); rooms/buildings =',
    '"box"; anything else = "freeform". Give each real object its own segment with enough depth',
    'control points to shape it. Be decisive and concrete.',
  ].join('\n');
}

function userPrompt(b: AgentBriefing): string {
  const pal = b.palette
    .slice(0, 6)
    .map(p => `[${p.rgb.map(v => Math.round(v * 255)).join(',')}]@${(p.weight * 100).toFixed(0)}%`)
    .join(' ');
  return [
    `Image is ${b.width}x${b.height}. Dominant palette: ${pal}.`,
    `Edge density ${b.edgeDensity.toFixed(3)}, mean luminance ${b.meanLuminance.toFixed(3)}.`,
    `Gradient collapse: mag ${b.collapse.mag.toFixed(3)}, angle ${b.collapse.ang.toFixed(3)} rad, ` +
      `angular entropy ${b.collapse.aEntropy.toFixed(3)}.`,
    `${b.lines.length} strong structural lines provided as vanishing/perspective evidence.`,
    'Entropy grid (detail map) and luminance-density grid (below) are row-major, top-left origin.',
    `entropy: ${JSON.stringify(b.entropyGrid.map(r => r.map(v => +v.toFixed(2))))}`,
    `lumen: ${JSON.stringify(b.lumenDensityGrid.map(r => r.map(v => +v.toFixed(2))))}`,
    'Author the SceneScript JSON now.',
  ].join('\n');
}

/** strip the data-URL header so ollama gets raw base64 image bytes */
function rawBase64(dataUrl: string): string {
  const comma = dataUrl.indexOf(',');
  return comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
}

interface OllamaChatReply { message?: { content?: string } }

/** ask the local vision model for a SceneScript. Throws on transport/parse/validate failure
 * (callers that want a guaranteed answer should use {@link ollamaSceneScriptOrClassical}). */
export async function ollamaSceneScript(b: AgentBriefing, opts: OllamaOptions = {}): Promise<SceneScript> {
  const endpoint = (opts.endpoint ?? DEFAULT_ENDPOINT).replace(/\/$/, '');
  const model = opts.model ?? DEFAULT_MODEL;
  const timeoutMs = opts.timeoutMs ?? 120_000;

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let reply: OllamaChatReply;
  try {
    const res = await fetch(`${endpoint}/api/chat`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        model,
        stream: false,
        format: 'json',
        messages: [
          { role: 'system', content: systemPrompt() },
          { role: 'user', content: userPrompt(b), images: [rawBase64(b.imageDataUrl)] },
        ],
      }),
      signal: ctrl.signal,
    });
    if (!res.ok) throw new Error(`ollama HTTP ${res.status}`);
    reply = (await res.json()) as OllamaChatReply;
  } finally {
    clearTimeout(timer);
  }

  const content = reply.message?.content;
  if (!content) throw new Error('ollama returned no content');

  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch {
    throw new Error('ollama content was not valid JSON');
  }
  if (!validateSceneScript(parsed)) throw new Error('ollama SceneScript failed validation');
  // provenance: force the author to 'ollama' regardless of what the model claimed
  return { ...parsed, author: 'ollama' };
}
// NO FALLBACK (LAW): ollamaSceneScript throws loud on any failure — there is no silent classical
// substitute. The caller decides what a missing/failed brain means; nothing is faked.
