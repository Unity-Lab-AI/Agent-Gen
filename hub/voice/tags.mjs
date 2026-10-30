// Action tags in her stream. Her persona writes [[img: full prompt]] on its own line when she means to show
// something; the appearance engine renders it. Tags are lifted out of the text before anything is spoken,
// so she never reads a prompt aloud. Also understands [[look: ...]] and [[do: ...]].
const OPEN = '[[';
const CLOSE = ']]';
const KINDS = /^\s*(img|image|selfie|look|do|action)\s*:\s*/i;

export class TagFilter {
  constructor(onTag) { this.onTag = onTag; this.buf = ''; this.inTag = false; this.fired = 0; this.text = ''; }
  fire(tag) { this.fired++; this.onTag(tag); }

  /** Feed a delta; returns the speakable text (tags removed). */
  push(delta) {
    this.buf += delta; this.text += delta;
    let out = '';
    while (this.buf) {
      if (!this.inTag) {
        const i = this.buf.indexOf(OPEN);
        if (i < 0) {
          const keep = this.buf.endsWith('[') ? 1 : 0;   // a split "[[" must not leak into speech
          out += this.buf.slice(0, this.buf.length - keep);
          this.buf = this.buf.slice(this.buf.length - keep);
          break;
        }
        out += this.buf.slice(0, i);
        this.buf = this.buf.slice(i + OPEN.length);
        this.inTag = true;
      } else {
        const j = this.buf.indexOf(CLOSE);
        if (j < 0) break;                                  // wait for the rest of the tag
        const inner = this.buf.slice(0, j);
        this.buf = this.buf.slice(j + CLOSE.length);
        this.inTag = false;
        const m = KINDS.exec(inner);
        if (m) this.fire({ kind: m[1].toLowerCase(), text: inner.slice(m[0].length).trim(), raw: inner });
      }
    }
    return out;
  }

  flush() {
    let out = '';
    if (!this.inTag) out = this.buf;
    else {
      const m = KINDS.exec(this.buf);                      // reply ended mid-tag: use what we have
      if (m && this.buf.slice(m[0].length).trim()) this.fire({ kind: m[1].toLowerCase(), text: this.buf.slice(m[0].length).trim(), raw: this.buf });
    }
    // no image line but she acted it out in asterisks (*top removed*): the stage direction is the look
    if (!this.fired) { const a = /\*([^*\n]{3,200})\*/.exec(this.text); if (a) this.fire({ kind: 'do', text: a[1].trim(), raw: a[0] }); }
    this.buf = ''; this.inTag = false;
    return out;
  }
}
