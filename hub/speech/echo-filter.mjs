// Echo filter: she speaks into the room she listens to. Browser AEC catches most of it; what leaks through
// shows up as a transcript that matches what she just said. Those are dropped here, on text, with a note.
// (Idea from C.O.R.A voice/echo_filter.py, done on words instead of audio.)
const KEEP = 20;
const words = t => (String(t || '').toLowerCase().match(/[a-z0-9']+/g) || []);

export class EchoFilter {
  constructor() { this.recent = []; }
  remember(text) { const w = words(text); if (w.length) { this.recent.push(w); if (this.recent.length > KEEP) this.recent.shift(); } }
  /** Returns {echo: bool, score, against} */
  check(text) {
    const w = words(text);
    if (w.length < 2) return { echo: false, score: 0 };
    const set = new Set(w);
    let best = { echo: false, score: 0, against: null };
    for (const line of this.recent) {
      const lset = new Set(line);
      let inter = 0;
      for (const x of set) if (lset.has(x)) inter++;
      const jaccard = inter / (set.size + lset.size - inter);
      const containment = inter / set.size;   // heard words mostly inside a spoken line
      const score = Math.max(jaccard, w.length >= 3 ? containment * 0.9 : 0);
      if (score > best.score) best = { echo: score >= 0.6, score: Number(score.toFixed(2)), against: line.join(' ') };
    }
    return best;
  }
}
