// Streaming sentence splitter. Feed it model deltas; it hands back whole speakable sentences as soon as they
// close, so her first words start while the rest is still generating. Code blocks are never spoken.
const TERMINAL = /([.!?]+["')\]]*)(\s+|$)/;
const MAX_SENTENCE = 260;

export class SentenceSplitter {
  constructor() { this.buf = ''; this.inCode = false; }

  push(delta) {
    this.buf += delta;
    const out = [];
    // strip fenced code as it arrives; a fence toggles, the inside is replaced by one spoken marker
    while (true) {
      const fence = this.buf.indexOf('```');
      if (fence < 0) break;
      if (!this.inCode) {
        const before = this.buf.slice(0, fence);
        this.buf = this.buf.slice(fence + 3);
        this.inCode = true;
        if (before.trim()) { this.buf = before + ' ' + this.buf; this.inCode = false; this.buf = this.buf.replace('```', '\u0000FENCE\u0000'); }
        else continue;
      } else {
        this.buf = ' I put the code in the transcript. ' + this.buf.slice(fence + 3);
        this.inCode = false;
      }
      break;
    }
    if (this.inCode) return out;
    // newlines end a sentence too (lists, short lines)
    let m;
    while (true) {
      const nl = this.buf.indexOf('\n');
      m = TERMINAL.exec(this.buf);
      let cut = -1;
      if (m && (nl < 0 || m.index < nl)) cut = m.index + m[1].length;
      else if (nl >= 0) cut = nl;
      if (cut < 0) {
        if (this.buf.length > MAX_SENTENCE) {
          const comma = this.buf.lastIndexOf(',', MAX_SENTENCE);
          cut = comma > 60 ? comma + 1 : MAX_SENTENCE;
        } else break;
      }
      const sentence = this.buf.slice(0, cut).trim();
      this.buf = this.buf.slice(cut).replace(/^\s+/, '');
      if (sentence) out.push(sentence);
      if (!this.buf) break;
    }
    return out;
  }

  flush() {
    const s = this.buf.trim();
    this.buf = '';
    this.inCode = false;
    return s ? [s] : [];
  }
}
