// Marker, paint or lipstick on her: read what the operator asked to have written or drawn, on which part of her
// (skin or a piece of clothing), in what. The image sidecar's /mark finds that part in her picture, sizes the mark to
// fit there and inks it in (the model cannot spell or aim a mark).
const ASK = /\b(write|writes|wrote|written|writing|draw|draws|drew|drawn|scribble|scrawl|sharpie|marker|doodle|lip ?stick|paint|painted|body ?paint)\b/i;
const SHAPES = [[/\barrows?\b/i, 'arrow'], [/\bhearts?\b/i, 'heart'], [/\bstars?\b/i, 'star'],
  [/\bsmil(ey|ie|y)( face)?\b/i, 'smiley'], [/\b(tally|tallies)\b/i, 'tally'], [/\b(an? )?x\b(?! ?ray)/i, 'x']];
const COLORS = ['black', 'red', 'pink', 'blue', 'purple', 'green', 'white'];
// most specific first; "left" is HER left
const PARTS = [
  [/\b(panties|underwear|undies|thong|shorts|pants|jeans|skirt|bikini bottoms?|bottoms)\b/i, 'bottoms'],
  [/\bdress\b/i, 'dress'],
  [/\b(top|shirt|t-shirt|tee|tank|bra|bikini top|blouse|hoodie|sweater|crop top)\b/i, 'top'],
  [/\bforehead\b/i, 'forehead'], [/\bcheeks?\b/i, 'cheek'], [/\b(neck|throat)\b/i, 'neck'],
  [/\bright shoulder\b/i, 'right shoulder'], [/\b(left )?shoulders?\b/i, 'left shoulder'],
  [/\bright arm\b/i, 'right arm'], [/\b(left )?arms?\b/i, 'left arm'],
  [/\bright (thigh|leg)\b/i, 'right thigh'], [/\b(left )?(thighs?|legs?)\b/i, 'left thigh'],
  [/\b(lower belly|lower stomach|pelvis|below (your|her) (navel|belly button)|bikini line)\b/i, 'lower belly'],
  [/\b(stomach|belly|tummy|abs|navel|belly button|waist)\b/i, 'stomach'],
  [/\b(cleavage|clevage|cleavege|clevige|chest|boobs?|breasts?|tits?|titties|collarbone)\b/i, 'chest'],
];

/** {items} when the operator asked for marks on her, else null. Each clause ("... and draw an arrow on your
 *  stomach") is its own item with its own part; ink and colour carry over from the clause before. */
export function parseMarks(text) {
  const t = String(text || '');
  if (!ASK.test(t)) return null;
  // double quotes only: an apostrophe ("Daddy's Girl") is part of the words
  const clauses = t.split(/\s+(?:and|then|plus|also)\s+(?=(?:write|draw|paint|scribble|put|add|a |an )\b)/i);
  const items = [];
  let tool = 'marker', color = null, part = null;
  for (const c of clauses) {
    if (/\blip ?stick\b/i.test(c)) tool = 'lipstick';
    else if (/\b(paint|painted|body ?paint|finger ?paint)\b/i.test(c)) tool = 'paint';
    else if (/\b(marker|sharpie|pen)\b/i.test(c)) tool = 'marker';
    color = COLORS.find(k => new RegExp(`\\b${k}\\b`, 'i').test(c)) || color;
    const p = PARTS.find(([re]) => re.test(c));
    if (p) part = p[1];
    const words = [...c.matchAll(/["“”]([^"“”]{1,24})["“”]/g)].map(m => m[1].trim()).filter(Boolean);
    if (!words.length) {
      const m = c.match(/\b(?:write|scribble|scrawl)\s+(?:the word\s+)?(\S+(?:\s+\S+)?)\s+(?:on|across|over|onto|down)\b/i);
      if (m && !SHAPES.some(([re]) => re.test(m[1]))) words.push(m[1].replace(/[^\w!?' -]/g, ''));
    }
    const shapes = words.length ? [] : SHAPES.filter(([re]) => re.test(c)).map(([, s]) => s);
    const ink = color || (tool === 'lipstick' ? 'lipstick' : 'black');
    const tilt = () => Math.round((Math.random() * 8 - 4) * 10) / 10;
    for (const w of words) items.push({ text: w, part: part || 'stomach', tool, color: ink, angle: tilt() });
    for (const s of shapes) items.push({ shape: s, part: part || 'stomach', tool, color: ink, angle: 0 });
  }
  if (!items.length) return null;
  if (!PARTS.some(([re]) => re.test(t)) && !/\b(skin|body|yourself|herself|on you)\b/i.test(t)) return null;
  return { items };
}
