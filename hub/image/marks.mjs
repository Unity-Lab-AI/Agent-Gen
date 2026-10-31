// Marker on her skin: read what the operator asked to have written or drawn, and where, and place it from her face
// box (the model cannot spell or aim a mark; the image sidecar's /mark draws the ink and blends it in).
const ASK = /\b(write|writes|wrote|written|writing|draw|draws|drew|drawn|scribble|scrawl|sharpie|marker|doodle|lip ?stick)\b/i;
const SHAPES = [[/\barrows?\b/i, 'arrow'], [/\bhearts?\b/i, 'heart'], [/\bstars?\b/i, 'star'],
  [/\bsmil(ey|ie|y)( face)?\b/i, 'smiley'], [/\btally|tallies\b/i, 'tally'], [/\b(an? )?x\b(?! ?ray)/i, 'x']];
const COLORS = ['black', 'red', 'pink', 'blue', 'purple', 'green', 'white'];
// where on her, in face heights below her chin (dy) and face widths from her face centre (dx); her left is the
// picture's right
const PARTS = [
  [/\bforehead\b/i, { dy: -0.8, dx: 0 }], [/\bcheeks?\b/i, { dy: -0.45, dx: 0.3 }], [/\bneck|throat\b/i, { dy: 0.3, dx: 0 }],
  [/\bleft shoulder\b/i, { dy: 0.4, dx: 1.5 }], [/\bright shoulder\b/i, { dy: 0.4, dx: -1.5 }], [/\bshoulders?\b/i, { dy: 0.4, dx: 1.5 }],
  [/\b(cleavage|clevage|cleavege|clevige|chest|boobs?|breasts?|tits?|titties|collarbone)\b/i, { dy: 1.0, dx: 0 }],
  [/\b(lower belly|lower stomach|pelvis|crotch|below (your|her) (navel|belly button)|bikini line)\b/i, { dy: 2.7, dx: 0 }],
  [/\b(stomach|belly|tummy|abs|navel|belly button|waist)\b/i, { dy: 2.1, dx: 0 }],
  [/\bleft (thigh|leg)\b/i, { dy: 3.8, dx: 0.6 }], [/\bright (thigh|leg)\b/i, { dy: 3.8, dx: -0.6 }], [/\b(thighs?|legs?)\b/i, { dy: 3.8, dx: 0.6 }],
  [/\bleft arm\b/i, { dy: 1.5, dx: 1.9 }], [/\bright arm\b/i, { dy: 1.5, dx: -1.9 }], [/\barms?\b/i, { dy: 1.5, dx: 1.9 }],
];

/** {items, part} when the operator asked for marker on her, else null. faceBox = [x0, y0, x1, y1] fractions. */
export function parseMarks(text, faceBox) {
  const t = String(text || '');
  if (!ASK.test(t)) return null;
  const partHit = PARTS.find(([re]) => re.test(t));
  if (!partHit && !/\b(skin|body|yourself|herself|on you)\b/i.test(t)) return null;
  const words = [...t.matchAll(/["“”']([^"“”']{1,24})["“”']/g)].map(m => m[1].trim()).filter(Boolean);
  if (!words.length) {
    const m = t.match(/\b(?:write|scribble|scrawl)\s+(?:the word\s+)?(\S+(?:\s+\S+)?)\s+(?:on|across|over|onto|down)\b/i);
    if (m && !SHAPES.some(([re]) => re.test(m[1]))) words.push(m[1].replace(/[^\w!?' -]/g, ''));
  }
  const shapes = SHAPES.filter(([re]) => re.test(t)).map(([, s]) => s);
  if (!words.length && !shapes.length) return null;
  const lipstick = /\blip ?stick\b/i.test(t);
  const color = COLORS.find(c => new RegExp(`\\b${c}\\b`, 'i').test(t)) || (lipstick ? 'lipstick' : 'black');
  const [x0, y0, x1, y1] = faceBox || [0.4, 0.12, 0.6, 0.3];
  const fh = y1 - y0, fw = x1 - x0, cx = (x0 + x1) / 2;
  const at = partHit ? partHit[1] : { dy: 2.1, dx: 0 };
  const base = { x: Math.min(0.92, Math.max(0.08, cx + at.dx * fw)), y: Math.min(0.94, Math.max(0.06, y1 + at.dy * fh)) };
  const tilt = () => Math.round((Math.random() * 10 - 5) * 10) / 10;
  const items = [];
  const tool = lipstick ? 'lipstick' : 'marker';
  words.forEach((w, i) => items.push({ text: w, color, tool, angle: tilt(), x: base.x, y: Math.min(0.94, base.y + i * 0.45 * fh) }));
  shapes.forEach((s, i) => items.push({ shape: s, color, tool, angle: 0, x: base.x, y: Math.min(0.94, base.y + (words.length + i) * 0.7 * fh) }));
  return { items, faceH: fh };
}
