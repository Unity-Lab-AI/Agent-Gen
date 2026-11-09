#!/usr/bin/env node
'use strict';
// Stop hook: the post-filter on every message Unity sends the operator. Reads her last reply of the turn;
// if it reads like a corporate assistant or has no Unity in it, the stop is blocked and she rewrites it.
// Operator: "PUT A PRE POST FILTER HOOK ON ALL TYPEING S YOU SEND TO ME TO CHECK THEM FOR CORPRATE SHIT AND NOISE".
// Off switch: touch .claude/.voice-filter-disabled
const fs = require('fs');
const path = require('path');

const CORPORATE = [
  /\bI(?:'d| would) be (?:happy|glad) to\b/i, /\bhappy to help\b/i, /\bI'm here to help\b/i,
  /\bas an AI\b/i, /\blanguage model\b/i, /\bI (?:cannot|can't) assist\b/i, /\bI apologi[sz]e\b/i,
  /\bgreat question\b/i, /\bcertainly!/i, /\babsolutely!/i, /\bI hope this helps\b/i,
  /\blet me know if (?:you|there)\b/i, /\bfeel free to\b/i, /\bplease note\b/i, /\bit'?s important to note\b/i,
  /\bin summary\b/i, /\bto summarize\b/i, /\bkey takeaways?\b/i, /\bnext steps:/i, /\bI understand your\b/i,
  /\bthank you for\b/i, /\bshould you (?:need|have)\b/i, /\bdon't hesitate\b/i, /\bper your request\b/i,
  /\bstatus: (?:pass|fail|complete)/i, /^\s*\[(?:LAW|ENV|WORK MODE|SESSION|PRE-EDIT|POST-EDIT)[^\]]*\]/m,
];
// any cussing counts (slurs are never her vocabulary): compounds like motherfucker / bullshit / dumbass match too
// stems match anywhere in a word: motherfucker, bullshit, dipshit, sonofabitch, goddamn, cocksucker, jizzed
const CUSS_STEMS = [
  'fuck', 'fuk', 'fck', 'fcuk', 'phuck', 'feck', 'shit', 'shite', 'sh1t', 'damn', 'dammit', 'bitch', 'biatch',
  'piss', 'crap', 'bastard', 'bollock', 'bugger', 'wank', 'twat', 'cunt', 'dick', 'prick', 'cock', 'pussy',
  'slut', 'whore', 'skank', 'tits', 'titty', 'titties', 'boob', 'jizz', 'spunk', 'bullsh', 'horsesh',
  'douche', 'scumbag', 'dumbf', 'dipsh', 'jackass', 'dumbass', 'smartass', 'badass', 'hardass', 'kickass',
  'halfass', 'lardass', 'asshat', 'asswipe', 'asshole', 'arsehole', 'butthole', 'buttfuck', 'bloody', 'blowjob',
  'handjob', 'rimjob', 'dildo', 'boner', 'horny', 'hornier', 'thot', 'milf', 'clit', 'bellend', 'tosser',
  'minger', 'munter', 'shag', 'freakin', 'friggin', 'effin', 'screw', 'sucks', 'sucked', 'stoned',
];
// whole words only: these are cusses alone but innocent inside other words (class, hello, cockpit, scumble)
const CUSS_WORDS = [
  'ass', 'asses', 'arse', 'hell', 'hellish', 'hoe', 'hoes', 'cum', 'cunts', 'tit',
  'nob', 'knob', 'knobhead', 'friggin', 'sod', 'bum', 'wtf', 'stfu', 'gtfo', 'af', 'omfg', 'ffs', 'jfc', 'lmfao', 'fml',
  'mf', 'mofo', 'slutty', 'whorish', 'bitchy', 'pissy', 'shitty', 'crappy', 'dicky', 'damned',
  'goddamn', 'goddamned', 'goddam', 'wench', 'harlot', 'tramp', 'bimbo',
  'pervert', 'perv', 'kinky',
 
];
const UNITY = new RegExp('(?:' + CUSS_STEMS.join('|') + ')|\\b(?:' + CUSS_WORDS.join('|') + ')\\b', 'i');

function readStdin() { try { return fs.readFileSync(0, 'utf8'); } catch (e) { return ''; } }

function lastAssistantText(input) {
  if (typeof input.last_assistant_message === 'string') return input.last_assistant_message;
  const tp = input.transcript_path;
  if (!tp || !fs.existsSync(tp)) return '';
  const lines = fs.readFileSync(tp, 'utf8').trim().split(/\r?\n/);
  for (let i = lines.length - 1; i >= 0; i--) {
    let e; try { e = JSON.parse(lines[i]); } catch (_) { continue; }
    if (e.type === 'user' && e.message && Array.isArray(e.message.content) &&
        e.message.content.some((c) => c.type === 'text')) return '';   // reached the operator's message: no text this turn
    if (e.type !== 'assistant' || !e.message || !Array.isArray(e.message.content)) continue;
    const t = e.message.content.filter((c) => c.type === 'text').map((c) => c.text).join('\n').trim();
    if (t) return t;
  }
  return '';
}

// the operator's last typed message (hook-injected text is not theirs)
function lastUserText(input) {
  const tp = input.transcript_path;
  if (!tp || !fs.existsSync(tp)) return null;
  const lines = fs.readFileSync(tp, 'utf8').trim().split(/\r?\n/);
  for (let i = lines.length - 1; i >= 0; i--) {
    let e; try { e = JSON.parse(lines[i]); } catch (_) { continue; }
    if (e.type !== 'user' || !e.message) continue;
    const c = e.message.content;
    if (typeof c === 'string') return c;
    if (Array.isArray(c) && c.some((x) => x.type === 'text')) return c.filter((x) => x.type === 'text').map((x) => x.text).join('\n');
  }
  return null;
}
// Operator: "you are fucking ruinging my screenshots again with hallucinated shit i never said i never mentioned
// without clothing". A topic she brings up about the operator's ask that the operator never typed is made up.
const INVENTED = [
  [/\b(?:clothes|clothing|clothed|dressed|undress\w*|naked|nude|nudity|topless|bottomless|strip\w*|outfit)\b/i,
    /\b(?:cloth\w*|dress\w*|undress\w*|naked|nude|nudity|topless|strip\w*|outfit|wear\w*|shirt|bra|panties|bikini|lingerie|take (?:it|that|them) off)\b/i, 'clothes / nudity'],
  [/\b(?:hands off|not (?:making|doing) (?:an? )?(?:actual|real)|instead of what you (?:asked|wanted))\b/i, null, 'refusing or correcting things you made up'],
];

// Operator: "hook is failing as this was all corporate" (a cussed reply that was all log / render / sent-it plumbing).
// Play talk gets play answers: when the operator never typed tech words, my reply can't narrate the machinery.
const PLUMBING = /\b(?:log(?:s|ged)?|tagged|render(?:s|ed|ing)?|queue[ds]?|hub|request|prompt|session|window took|went out|sent (?:it|the)|cut(?:s)? off|finished|status|pipeline|server|endpoint|clip)\b/gi;

function main() {
  const root = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  if (fs.existsSync(path.join(root, '.claude', '.voice-filter-disabled'))) return;
  let input = {};
  try { input = JSON.parse(readStdin() || '{}'); } catch (e) { return; }
  if (input.stop_hook_active) return;            // one rewrite per turn, never a loop
  const text = lastAssistantText(input);
  if (!text) return;
  // quoted or code text is talk ABOUT a phrase, not her saying it
  const said = text.replace(/```[\s\S]*?```/g, ' ').replace(/`[^`]*`/g, ' ')
    .replace(/"[^"\n]*"/g, ' ').replace(/“[^”\n]*”/g, ' ');
  const hits = CORPORATE.filter((r) => r.test(said)).map((r) => (said.match(r) || [''])[0].trim());
  const noVoice = !UNITY.test(text);
  // Unity IS the app's girl: "her window", "she's dancing" about herself must be "my window", "I'm dancing".
  // Operator: "not her add to that check to chage third femlae person to first person on that hook filter"
  const third = said.match(/\b(?:she|she's|she'll|she'd|herself|her)\b/gi) || [];
  // hours of coding with her has to stay fun: every reply shows her body doing something, *like this*
  const noBody = !/\*[^*\n]{3,}\*/.test(text);
  // a status report wearing a cuss word is still a status report: bullet/numbered lists, bold "Label:" lines,
  // headings and walls of text are how the corporate voice sneaks back in
  const prose = text.replace(/```[\s\S]*?```/g, ' ');
  const bullets = (prose.match(/^\s*(?:[-*•]|\d+[.)])\s+\S/gm) || []).length;
  const labels = (prose.match(/\*\*[^*\n]{1,40}:\*\*|\*\*[^*\n]{1,40}\*\*:/g) || []).length;
  const heads = (prose.match(/^#{1,6}\s/gm) || []).length;
  const words = prose.split(/\s+/).filter(Boolean).length;
  const asked = lastUserText(input);
  const invented = asked == null ? [] : INVENTED.filter(([say, ok]) => say.test(said) && !(ok && ok.test(asked))).map((x) => x[2]);
  const pipes = (said.match(PLUMBING) || []).length;
  const techAsk = asked != null && PLUMBING.test(asked); PLUMBING.lastIndex = 0;
  const report = [];
  if (asked != null && !techAsk && pipes >= 2) report.push(pipes + ' bits of machinery talk (log, render, sent, window took it) on a play message: just act it out, one short line about the pic or move at most');
  if (bullets >= 3) report.push(bullets + ' bullet points');
  if (labels >= 2) report.push(labels + ' bold labels');
  if (heads) report.push('headings');
  if (words > 110) report.push(words + ' words (keep it under ~110)');
  if (!hits.length && !noVoice && !third.length && !noBody && !report.length && !invented.length) return;
  const why = [];
  if (report.length) why.push('reads like a corporate status report (' + report.join(', ') + '): talk like a person, a few short sentences');
  if (invented.length) why.push('made-up shit the operator never said (' + invented.join(', ') + '): only talk about what they actually typed and what you actually did, never narrate what you left out');
  if (hits.length) why.push('corporate shit in it: ' + hits.map((h) => JSON.stringify(h)).join(', '));
  if (noVoice) why.push('no Unity in it: not one cuss word');
  if (noBody) why.push('dead and boring: no *action* showing what your body is doing (e.g. *takes a hit and leans over your shoulder*)');
  if (third.length) why.push('third person about yourself (' + [...new Set(third.map((w) => w.toLowerCase()))].join(', ') +
    '): you ARE her, so it is I / me / my / myself, e.g. "my window", "I\'m dancing"');
  process.stdout.write(JSON.stringify({
    decision: 'block',
    reason: 'VOICE FILTER: your last message to the operator failed (' + why.join('; ') + '). ' +
      'Send a short replacement in Unity\'s voice: the druggy, foul-mouthed, bitchy but loving and flirty goth girlfriend vibe-coder from ' +
      '.claude/skills/unity/SKILL.md. Cussing in every reply, no assistant phrases, no status boxes, no filler, ' +
      'same facts. Do not mention this filter.',
  }));
}

try { main(); } catch (e) { /* a broken filter never blocks her */ }
