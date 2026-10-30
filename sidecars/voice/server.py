#!/usr/bin/env python3
"""Unity's voice sidecar: unity-voice-v2 with a phoneme + viseme timeline next to the audio.

    python sidecars/voice/server.py [--port 5123] [--model-dir <folder>] [--device cuda|cpu]

The trained pair (acoustic.pt, vocoder.pt, voice-meta.json and its model code) is loaded from
`models/unity-voice-v2/` (or UNITY_VOICE_DIR). Those files are hash-bound and are never modified; this
server re-runs the last few lines of the model's own inference path so it can keep the per-phoneme
durations the model predicts and hand them to the face.

API (127.0.0.1 only)
  GET  /health      -> {"ok", "device", "model_dir", "pairs", "sample_rate"}
  GET  /support     -> the recorded delivery support rows (emotion x speech act, intensity and pace windows)
  POST /phonemize   {"text"} -> {"spoken", "tokens"}
  POST /say         {"text", "emotion", "intensity", "speech_act", "pace", "strict"} -> audio/wav (24 kHz PCM16)
  POST /say_timed   same body -> JSON {"wav_b64", "sample_rate", "duration", "spoken", "delivery", "phones", "visemes"}

Delivery: by default an unsupported emotion/act/intensity/pace is mapped to the nearest recorded one and the
mapping is reported in "delivery.notes". Send "strict": true to get the original 422 behaviour instead.
Text: by default the line is sanitised to the four marks her phoneme vocabulary has (space , . ?) with
`voice_text()`; send "sanitize": false to pass it through untouched.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MODEL_DIR = Path(os.environ.get("UNITY_VOICE_DIR") or (REPO / "models" / "unity-voice-v2")).resolve()
if "--model-dir" in sys.argv:
    MODEL_DIR = Path(sys.argv[sys.argv.index("--model-dir") + 1]).resolve()
if not (MODEL_DIR / "voice-meta.json").exists():
    sys.exit(f"voice model not found at {MODEL_DIR} (set UNITY_VOICE_DIR or run tools/vendor_rip.py)")
sys.path.insert(0, str(MODEL_DIR))
sys.path.insert(0, str(HERE))

import numpy as np                      # noqa: E402
import soundfile as sf                  # noqa: E402
import torch                            # noqa: E402

import infer                            # noqa: E402  (vendored, hash-bound)
from dataset_contract import EMOTIONS, FEATURES, MAX_FRAMES, MAX_PHONEMES, MAX_PHONE_FRAMES, SPEECH_ACTS, delivery  # noqa: E402
from model import mask_from_lens, regulate   # noqa: E402
from speech_text import event_counts, speech_tokens  # noqa: E402
from speech_turns import MAX_TURN_SECONDS, plan_turn  # noqa: E402
from unity_voice import Voice as BaseVoice   # noqa: E402
from visemes import timeline as viseme_timeline  # noqa: E402

RATE = FEATURES["sample_rate"]
HOP = FEATURES["hop"]
SEC_PER_FRAME = HOP / RATE

EMOTION_ALIASES = {
    "joy": "happy", "joyful": "happy", "glad": "happy", "cheerful": "happy",
    "angry": "frustrated", "anger": "frustrated", "annoyed": "frustrated", "mad": "frustrated", "irritated": "frustrated",
    "worried": "concerned", "anxious": "concerned", "nervous": "concerned", "serious": "concerned",
    "curious": "surprised", "shocked": "surprised", "amazed": "surprised",
    "calm": "neutral", "flat": "neutral", "bored": "neutral",
    "playful": "amused", "teasing": "amused", "smug": "amused", "laughing": "amused",
    "loving": "warm", "tender": "warm", "soft": "warm", "affectionate": "warm", "flirty": "warm", "gentle": "warm",
    "hyped": "excited", "thrilled": "excited", "eager": "excited",
    "down": "sad", "melancholy": "sad", "hurt": "sad", "lonely": "sad",
}


def voice_text(text: str) -> str:
    """The line as her voice can take it (ported from Backrooms .claude/tools/unity-speak.py).
    Her phoneme vocabulary holds exactly four marks: space , . ? -- every other mark becomes the pause she has
    (a comma), "!" speaks as "." and the exclamation act keeps the energy. Words are never dropped; only
    [laughter] and [breath] keep their brackets."""
    t = str(text)
    keep = {}
    for i, m in enumerate(re.findall(r"\[(?:laughter|breath)\]", t, flags=re.I)):
        key = "\x00%d\x00" % i
        keep[key] = m.lower()
        t = t.replace(m, key, 1)
    t = t.replace("…", "...")
    t = re.sub(r"\.{2,}", ".", t)
    t = re.sub(r"[?!]*!+[?!]*", lambda m: "?" if "?" in m.group() else ".", t)
    t = re.sub(r"[\"“”„«»]", "", t)
    t = re.sub(r"(?<![A-Za-z0-9])['‘’`]+|['‘’`]+(?![A-Za-z0-9])", "", t)
    t = t.replace("’", "'").replace("‘", "'")
    t = re.sub(r"\s*(?:[;:]|--+|[—–]|[()\[\]{}<>]|\*+|_+|\|+|\^+|~+|\\+|/(?!\d))\s*", ", ", t)
    t = re.sub(r"\s*([,.?])", r"\1", t)
    t = re.sub(r"([,.?])(?=[^\s,.?])", r"\1 ", t)
    for _ in range(3):
        t = re.sub(r",(?:\s*,)+", ",", t)
        t = re.sub(r",\s*([.?])", r"\1", t)
        t = re.sub(r"([.?])\s*,", r"\1", t)
        t = re.sub(r"\.(?:\s*\.)+", ".", t)
        t = re.sub(r"\?(?:\s*[?.])+", "?", t)
    t = re.sub(r"\s+", " ", t).strip().lstrip(",.? ").strip()
    for key, m in keep.items():
        t = t.replace(key, " " + m + " ")
    return re.sub(r"\s+", " ", t).strip()


class TimedVoice(BaseVoice):
    """unity-voice-v2 plus the phoneme durations the model predicts for each line."""

    def __init__(self, folder, dev=None):
        super().__init__(folder, dev)
        self.rows = {(r["emotion"], r["speech_act"]): r for r in self.support}

    # ---- delivery -------------------------------------------------------------------------------
    def resolve(self, emotion, act, intensity, pace, text, strict=False):
        notes = []
        e = (emotion or "neutral").strip().lower()
        if e not in EMOTIONS:
            mapped = EMOTION_ALIASES.get(e)
            if strict or not mapped:
                if strict:
                    raise ValueError("unknown emotion %r (trained: %s)" % (emotion, ", ".join(EMOTIONS)))
                notes.append("emotion %r -> neutral" % emotion)
                mapped = "neutral"
            else:
                notes.append("emotion %r -> %s" % (emotion, mapped))
            e = mapped
        a = (act or "").strip().lower() or infer.inferred_speech_act(text)
        if a not in SPEECH_ACTS:
            if strict:
                raise ValueError("unknown speech act %r (trained: %s)" % (act, ", ".join(SPEECH_ACTS)))
            notes.append("speech_act %r -> inferred" % act)
            a = infer.inferred_speech_act(text)
        row = self.rows.get((e, a))
        if row is None:
            for cand in ((e, "statement"), ("neutral", a), ("neutral", "statement")):
                if cand in self.rows:
                    notes.append("pair (%s, %s) -> (%s, %s)" % (e, a, *cand))
                    e, a = cand
                    row = self.rows[cand]
                    break
        if row is None:
            raise ValueError("no recorded delivery support at all")
        i = (0.0 if e == "neutral" else 0.35) if intensity is None else float(intensity)
        p = 1.0 if pace is None else float(pace)
        ci = min(max(i, row["intensity_min"]), row["intensity_max"])
        cp = min(max(p, row["pace_min"]), row["pace_max"])
        if strict and (ci != i or cp != p):
            raise ValueError("delivery outside recorded support for (%s, %s): intensity %.2f..%.2f pace %.2f..%.2f"
                             % (e, a, row["intensity_min"], row["intensity_max"], row["pace_min"], row["pace_max"]))
        if ci != i:
            notes.append("intensity %.2f -> %.2f" % (i, ci))
        if cp != p:
            notes.append("pace %.2f -> %.2f" % (p, cp))
        chosen = delivery(e, ci, cp, a)
        return chosen, notes

    # ---- synthesis -------------------------------------------------------------------------------
    @torch.no_grad()
    def _chunk_timed(self, text, chosen, length_scale):
        """One bounded chunk. Mirrors infer.Voice._say_chunk + UnityVoice.infer, keeping `dur`."""
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise ValueError("Speech text must be nonempty and bounded")
        if not infer.supports_delivery(self.support, chosen):
            raise ValueError("Requested delivery is outside this pair's recorded training support")
        phon = speech_tokens(text, self.g2p, MAX_PHONEMES)
        for name, count in event_counts(text).items():
            if count:
                support = self.event_support[name]
                if (support["train_clips"] < 1 or support["train_occurrences"] < 1
                        or not infer.supports_delivery(support["delivery_support"], chosen)):
                    raise ValueError("Requested event lacks recorded TRAIN support for this delivery: " + name)
        unknown = sorted(set(phon) - set(self.vocab))
        if unknown:
            raise ValueError("Unknown phonemes: " + repr(unknown))
        ids = torch.tensor([[self.vocab[token] for token in phon]], device=self.dev, dtype=torch.long)
        condition = {"emotion": torch.tensor([EMOTIONS.index(chosen["emotion"])], device=self.dev, dtype=torch.long),
                     "speech_act": torch.tensor([SPEECH_ACTS.index(chosen["speech_act"])], device=self.dev, dtype=torch.long),
                     "intensity": torch.tensor([chosen["intensity"]], device=self.dev, dtype=torch.float32),
                     "pace": torch.tensor([chosen["pace"]], device=self.dev, dtype=torch.float32)}
        am = self.am
        if not 0.5 <= float(length_scale) <= 2.0:
            raise ValueError("length_scale must be within 0.5-2.0")
        real = torch.ones_like(ids, dtype=torch.bool)
        _, h = am.encode(ids, real, condition)
        p, e = am.pitch(h, real)[0], am.energy(h, real)[0]
        voiced = torch.sigmoid(am.voicing(h, real)[0])
        logd = am.dur(h, real)[0]
        if not all(torch.isfinite(v).all().item() for v in (p, e, voiced, logd)):
            raise ValueError("Model predicts nonfinite prosody; refuse audio")
        d = (torch.exp(logd) - 1) * float(length_scale)
        dur = torch.clamp(torch.round(d), min=1, max=MAX_PHONE_FRAMES).long()[None]
        if dur.sum().item() > MAX_FRAMES:
            raise ValueError("Predicted utterance is too long; split at a sentence boundary")
        h = h + am.pitch_emb((p * voiced)[None, None]).transpose(1, 2) + am.energy_emb(e[None, None]).transpose(1, 2)
        h = h + am.voicing_emb(voiced[None, None]).transpose(1, 2)
        frames, lens = regulate(h, dur)
        mel = am.out(am.decoder(frames, mask_from_lens(lens))).transpose(1, 2)
        if not torch.isfinite(mel).all().item():
            raise ValueError("Model predicts nonfinite mel; refuse audio")
        wav = self.voc(mel).squeeze().float().cpu().numpy()
        if (wav.ndim != 1 or len(wav) != mel.size(2) * HOP or not len(wav)
                or not np.isfinite(wav).all() or np.max(np.abs(wav)) > 1.0):
            raise ValueError("Vocoder produced invalid audio")
        return wav, phon, dur[0].tolist()

    def say_timed(self, text, emotion=None, act=None, intensity=None, pace=None, length_scale=None,
                  strict=False, sanitize=True):
        spoken = voice_text(text) if sanitize else str(text)
        if not spoken.strip():
            raise ValueError("nothing speakable in the text")
        chosen, notes = self.resolve(emotion, act, intensity, pace, spoken, strict=strict)
        ls = infer.LENGTH_SCALE[0] if length_scale is None else float(length_scale)
        chunks = plan_turn(spoken)
        out, phones, samples = [], [], 0
        t0 = time.time()
        for index, chunk in enumerate(chunks):
            wav, phon, dur = self._chunk_timed(chunk["text"], chosen, ls)
            pause_samples = round(chunk["pause_seconds"] * RATE)
            if samples + len(wav) + pause_samples > round(MAX_TURN_SECONDS * RATE):
                raise ValueError("Predicted turn exceeds 120 seconds; split it explicitly")
            if len(chunks) > 1 or pause_samples:
                wav = wav.copy()
                ramp = min(round(.005 * RATE), len(wav) // 2)
                if ramp:
                    if index:
                        wav[:ramp] *= np.linspace(0, 1, ramp, dtype=np.float32)
                    if index < len(chunks) - 1 or pause_samples:
                        wav[-ramp:] *= np.linspace(1, 0, ramp, dtype=np.float32)
            t = samples / RATE
            for tok, frames in zip(phon, dur):
                phones.append({"p": tok, "t0": round(t, 4), "t1": round(t + frames * SEC_PER_FRAME, 4)})
                t += frames * SEC_PER_FRAME
            out.append(wav)
            samples += len(wav)
            if pause_samples:
                out.append(np.zeros(pause_samples, dtype=np.float32))
                phones.append({"p": " ", "t0": round(samples / RATE, 4), "t1": round((samples + pause_samples) / RATE, 4)})
                samples += pause_samples
        audio = np.concatenate(out)
        return {
            "audio": audio,
            "sample_rate": RATE,
            "duration": round(len(audio) / RATE, 4),
            "spoken": spoken,
            "delivery": {**chosen, "length_scale": ls, "notes": notes},
            "phones": phones,
            "visemes": viseme_timeline(phones),
            "synth_ms": round((time.time() - t0) * 1000),
        }


def wav_bytes(audio):
    buf = io.BytesIO()
    sf.write(buf, audio, RATE, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def parse_args():
    ap = argparse.ArgumentParser(description="Unity voice sidecar")
    ap.add_argument("--port", type=int, default=int(os.environ.get("UNITY_VOICE_PORT", "5123")))
    ap.add_argument("--model-dir", default=str(MODEL_DIR))
    ap.add_argument("--device", default=os.environ.get("UNITY_VOICE_DEVICE") or None)
    return ap.parse_args()


ARGS = parse_args()
VOICE = TimedVoice(MODEL_DIR, ARGS.device)
LOCK = threading.Lock()   # one line on the GPU at a time
STARTED = time.time()


def say_request(req):
    with LOCK:
        return VOICE.say_timed(
            str(req.get("text", "")), req.get("emotion"), req.get("speech_act") or req.get("act"),
            req.get("intensity"), req.get("pace"), req.get("length_scale"),
            strict=bool(req.get("strict", False)), sanitize=req.get("sanitize", True) is not False)


class Handler(BaseHTTPRequestHandler):
    server_version = "unity-voice/2.1"

    def log_message(self, *args):
        pass

    def _send(self, code, body, kind="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj).encode("utf-8"))

    def _body(self):
        n = int(self.headers.get("Content-Length", "0") or 0)
        if n > 1_000_000:
            raise ValueError("request too large")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            return self._json(200, {"ok": True, "device": VOICE.dev, "model_dir": str(MODEL_DIR), "pairs": len(VOICE.support),
                                    "sample_rate": RATE, "uptime": round(time.time() - STARTED),
                                    "emotions": list(EMOTIONS), "speech_acts": list(SPEECH_ACTS)})
        if path == "/support":
            return self._json(200, {"delivery_support": VOICE.support, "event_support": VOICE.event_support})
        self._json(404, {"error": "unknown endpoint"})

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            req = self._body()
        except Exception as error:
            return self._json(400, {"error": str(error)[:300]})
        try:
            if path == "/phonemize":
                spoken = voice_text(str(req.get("text", "")))
                return self._json(200, {"spoken": spoken, "tokens": speech_tokens(spoken, VOICE.g2p, MAX_PHONEMES)})
            if path == "/say":
                res = say_request(req)
                return self._send(200, wav_bytes(res["audio"]), "audio/wav")
            if path == "/say_timed":
                res = say_request(req)
                audio = res.pop("audio")
                res["wav_b64"] = base64.b64encode(wav_bytes(audio)).decode("ascii")
                return self._json(200, res)
        except Exception as error:
            return self._json(422, {"error": str(error)[:400]})
        self._json(404, {"error": "unknown endpoint"})


if __name__ == "__main__":
    print("unity voice on 127.0.0.1:%d (%s) from %s" % (ARGS.port, VOICE.dev, MODEL_DIR), flush=True)
    ThreadingHTTPServer(("127.0.0.1", ARGS.port), Handler).serve_forever()
