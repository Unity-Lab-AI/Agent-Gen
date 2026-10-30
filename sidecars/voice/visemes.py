"""Phoneme timeline -> viseme timeline for Unity's voice.

The acoustic model speaks misaki (American English) phoneme characters. Every character gets a predicted
duration in mel frames at synthesis time, so mouth timing comes straight from the model instead of from
audio analysis. This module maps those characters onto a small, renderer-neutral viseme set (the Oculus /
Apple-style 15) and merges neighbours.

Inventory in voice-meta.json (52 tokens): space , . ? A I O T W Y b d f h i j k l m n p s t u v w z
æ ð ŋ ɐ ɑ ɔ ə ɛ ɜ ɡ ɪ ɹ ʃ ʊ ʌ ʒ ʤ ʧ ˈ ˌ θ ᵊ ᵻ  plus <event:laughter>.
Capitals are misaki's diphthong / flap shorthands: A=eɪ I=aɪ O=oʊ W=aʊ Y=ɔɪ T=ɾ.
"""

VISEMES = ("sil", "PP", "FF", "TH", "DD", "kk", "CH", "SS", "nn", "RR", "aa", "E", "ih", "oh", "ou")

# How open the mouth is for each viseme, 0..1. A cheap single-channel drive for renderers without shapes.
OPENNESS = {"sil": 0.0, "PP": 0.05, "FF": 0.2, "TH": 0.3, "DD": 0.3, "kk": 0.35, "CH": 0.3, "SS": 0.25,
            "nn": 0.3, "RR": 0.35, "aa": 1.0, "E": 0.7, "ih": 0.45, "oh": 0.8, "ou": 0.5}

VISEME_OF = {
    " ": "sil", ",": "sil", ".": "sil", "?": "sil",
    "p": "PP", "b": "PP", "m": "PP",
    "f": "FF", "v": "FF",
    "θ": "TH", "ð": "TH",
    "t": "DD", "d": "DD", "T": "DD",
    "n": "nn", "l": "nn", "ŋ": "nn",
    "k": "kk", "ɡ": "kk", "g": "kk", "h": "kk",
    "ʧ": "CH", "ʤ": "CH", "ʃ": "CH", "ʒ": "CH",
    "s": "SS", "z": "SS",
    "ɹ": "RR", "r": "RR",
    "ɑ": "aa", "æ": "aa", "ʌ": "aa", "ɐ": "aa", "a": "aa",
    "ɛ": "E", "ə": "E", "ɜ": "E", "ᵊ": "E", "e": "E",
    "ɪ": "ih", "i": "ih", "ᵻ": "ih", "j": "ih",
    "ɔ": "oh", "o": "oh",
    "u": "ou", "ʊ": "ou", "w": "ou",
    "<event:laughter>": "aa", "<event:breath>": "sil",
}
# Two-shape phonemes: (first, second, share of the duration given to the first).
DIPHTHONG = {"A": ("E", "ih", 0.6), "I": ("aa", "ih", 0.6), "O": ("oh", "ou", 0.6),
             "W": ("aa", "ou", 0.6), "Y": ("oh", "ih", 0.6)}
# Zero-width marks: stress. Their frames are folded into the neighbouring viseme.
MARKS = {"ˈ", "ˌ"}


def timeline(phones, merge=True):
    """phones: [{"p": token, "t0": s, "t1": s}] in order -> [{"v": viseme, "t0", "t1", "open"}]."""
    out = []

    def push(v, t0, t1):
        if t1 <= t0:
            return
        if merge and out and out[-1]["v"] == v and abs(out[-1]["t1"] - t0) < 1e-6:
            out[-1]["t1"] = round(t1, 4)
            return
        out.append({"v": v, "t0": round(t0, 4), "t1": round(t1, 4), "open": OPENNESS[v]})

    pending_mark = 0.0  # seconds of stress-mark time to hand to the next phoneme
    for ph in phones:
        tok, t0, t1 = ph["p"], float(ph["t0"]), float(ph["t1"])
        if tok in MARKS:
            if out:
                out[-1]["t1"] = round(t1, 4)   # fold into the previous shape
            else:
                pending_mark += t1 - t0
            continue
        if pending_mark:
            t0 -= pending_mark
            pending_mark = 0.0
        if tok in DIPHTHONG:
            a, b, share = DIPHTHONG[tok]
            mid = t0 + (t1 - t0) * share
            push(a, t0, mid)
            push(b, mid, t1)
            continue
        push(VISEME_OF.get(tok, "E"), t0, t1)
    return out


def openness_curve(visemes, fps=30, attack=0.03, release=0.05):
    """Sample the viseme track into a per-frame mouth-open value with short attack/release ramps.
    Handy for a renderer that only takes a scalar. Returns [open_0, open_1, ...] at `fps`."""
    if not visemes:
        return []
    end = visemes[-1]["t1"]
    n = int(end * fps) + 1
    curve = [0.0] * n
    for seg in visemes:
        target = seg["open"]
        for i in range(n):
            t = i / fps
            if seg["t0"] - attack <= t < seg["t1"] + release:
                if t < seg["t0"]:
                    w = (t - (seg["t0"] - attack)) / attack
                elif t >= seg["t1"]:
                    w = 1 - (t - seg["t1"]) / release
                else:
                    w = 1.0
                curve[i] = max(curve[i], target * max(0.0, min(1.0, w)))
    return [round(v, 3) for v in curve]
