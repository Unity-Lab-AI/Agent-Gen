// Pick how a sentence is delivered: emotion, speech act, intensity. The model may lead a sentence with an
// emotion tag (<amused>); otherwise a small lexicon decides. The voice sidecar clamps anything outside the
// recorded support, so this only has to be reasonable, not exact.
import { cfg } from '../config.mjs';

export const EMOTIONS = ['neutral', 'warm', 'happy', 'amused', 'excited', 'sad', 'concerned', 'frustrated', 'surprised'];
const ALIASES = {
  joy: 'happy', glad: 'happy', cheerful: 'happy', angry: 'frustrated', annoyed: 'frustrated', mad: 'frustrated',
  worried: 'concerned', anxious: 'concerned', serious: 'concerned', curious: 'surprised', shocked: 'surprised',
  calm: 'neutral', playful: 'amused', teasing: 'amused', smug: 'amused', loving: 'warm', tender: 'warm', soft: 'warm',
  flirty: 'warm', hyped: 'excited', thrilled: 'excited', down: 'sad', hurt: 'sad', lonely: 'sad',
};
const TAG = /^\s*(?:<\s*([a-z]+)\s*>|\[\s*([a-z]+)\s*\]|\(\s*([a-z]+)\s*\))\s*/i;
const WH = new Set(['what', 'who', 'where', 'when', 'why', 'how', 'which', 'whose']);
const LEX = [
  [/\b(haha|lol|lmao|heh|giggl|snicker|pfft)\b/i, 'amused', 0.5],
  [/\b(sorry|worried|careful|be safe|are you ok|you okay|hurt)\b/i, 'concerned', 0.45],
  [/\b(ugh|damn|dammit|shit|fuck(?!ing (great|yes))|annoying|seriously\?)\b/i, 'frustrated', 0.5],
  [/\b(wow|whoa|no way|what\?!|really\?|wait what)\b/i, 'surprised', 0.5],
  [/\b(miss you|lonely|sad|cry|tears|hurts|lost)\b/i, 'sad', 0.45],
  [/\b(fuck yes|hell yes|let's go|can't wait|so good|amazing|love this)\b/i, 'excited', 0.6],
  [/\b(love you|baby|sweetheart|babe|honey|c'?mere|hold you)\b/i, 'warm', 0.5],
  [/\b(yay|great|awesome|nice|perfect|happy)\b/i, 'happy', 0.45],
];

export function pickDelivery(sentence) {
  let text = String(sentence || '');
  let emotion = null, intensity = null;
  const m = TAG.exec(text);
  if (m) {
    const tag = (m[1] || m[2] || m[3]).toLowerCase();
    const e = EMOTIONS.includes(tag) ? tag : ALIASES[tag];
    if (e) { emotion = e; text = text.slice(m[0].length); }
  }
  const hadBang = /!/.test(text);
  const trimmed = text.trim();
  if (!trimmed) return { text: '', emotion: emotion || cfg.defaultEmotion, speech_act: 'statement', intensity: null };
  if (!emotion) {
    for (const [rx, e, i] of LEX) if (rx.test(trimmed)) { emotion = e; intensity = i; break; }
  }
  if (!emotion) { emotion = cfg.defaultEmotion; }
  let act = 'statement';
  const lower = trimmed.toLowerCase();
  const first = lower.split(/\s+/)[0]?.replace(/[^a-z']/g, '') || '';
  if (/\?\s*$/.test(trimmed)) act = WH.has(first) ? 'wh_question' : 'yes_no_question';
  else if (hadBang) act = 'exclamation';
  else if (/^(please |go |come |look |listen |stop |wait |try |open |close |tell me|show me|give me|let me)/.test(lower)) act = 'instruction';
  else if (/\b(it'?s okay|it'?s alright|don'?t worry|you'?re fine|i'?m here|we'?ll figure)\b/.test(lower)) act = 'reassurance';
  if (hadBang && emotion === cfg.defaultEmotion) { emotion = 'excited'; intensity = 0.5; }
  return { text: trimmed, emotion, speech_act: act, intensity };
}
