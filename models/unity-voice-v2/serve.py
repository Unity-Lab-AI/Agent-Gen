"""Unity's own voice as a small local server: the model loads once, every line is one POST.

    python serve.py [--port 5123]

POST /say  {"text": "...", "emotion": "amused", "intensity": 0.35, "speech_act": "statement", "pace": 1.0}  -> audio/wav
GET  /health                                                                                                 -> {"ok": true}

`pace` is optional and defaults to 1.0 (unchanged behaviour for callers that never send it). It is the trained
delivery pace, checked against each (emotion, speech_act) pair's recorded pace window in voice-meta.json — 20 of
the 63 pairs were recorded only at 0.9 or 1.05/1.12, so a caller that cannot send a pace can never reach them.
This is NOT pace.txt, which is the post-hoc length scale applied to every line.

Listens on 127.0.0.1 only. There is no fallback (owner 2026-10-13: fallbacks are against the
laws): an unknown emotion/act or a delivery outside the pair's recorded support is a 422 with the reason, and the
caller logs it.
"""
import io, json, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import soundfile as sf                       # noqa: E402
from dataset_contract import EMOTIONS, FEATURES, SPEECH_ACTS   # noqa: E402
from unity_voice import Voice                # noqa: E402

CKPT = HERE
import infer                                 # noqa: E402
PACE_FILE = os.path.join(HERE, "pace.txt")


def pace():
    """Her speed, read before every line so a change is heard on the next one (owner 2026-10-13: "can we easily turn
    down her speed ... in some easiy weay , NOW"). pace.txt holds one number: 1.0 natural, higher is slower (1.2 = 20%
    slower), lower is faster. No file: UNITY_VOICE_LENGTH_SCALE, else 1.0."""
    try:
        v = float(open(PACE_FILE, encoding="utf-8").read().strip())
        if 0.6 <= v <= 1.8:
            return v
    except (OSError, ValueError):
        pass
    return float(os.environ.get("UNITY_VOICE_LENGTH_SCALE", "1.0"))
PORT = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else int(os.environ.get("UNITY_VOICE_PORT", "5123"))
VOICE = Voice(CKPT)
LOCK = threading.Lock()                      # one line on the GPU at a time


def render(text, emotion=None, intensity=None, act=None, delivery_pace=None):
    emotion = emotion or "neutral"
    if emotion not in EMOTIONS:
        raise ValueError("unknown emotion %r (trained: %s)" % (emotion, ", ".join(EMOTIONS)))
    if act is not None and act not in SPEECH_ACTS:
        raise ValueError("unknown speech act %r (trained: %s)" % (act, ", ".join(SPEECH_ACTS)))
    try:
        delivery_pace = 1.0 if delivery_pace is None else float(delivery_pace)
    except (TypeError, ValueError):
        raise ValueError("pace must be a number (the pair's recorded delivery pace), got %r" % (delivery_pace,))
    with LOCK:
        infer.LENGTH_SCALE[0] = pace()
        return VOICE.say(text, emotion, intensity, delivery_pace, act)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, kind="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, b'{"ok": true}')
        else:
            self._send(404, b"{}")

    def do_POST(self):
        if self.path != "/say":
            return self._send(404, b"{}")
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0") or 0)) or b"{}")
            wav = render(str(req.get("text", "")), req.get("emotion"), req.get("intensity"), req.get("speech_act"),
                         req.get("pace"))
        except Exception as error:
            return self._send(422, json.dumps({"error": str(error)[:300]}).encode())
        buf = io.BytesIO()
        sf.write(buf, wav, FEATURES["sample_rate"], format="WAV", subtype="PCM_16")
        self._send(200, buf.getvalue(), "audio/wav")


if __name__ == "__main__":
    print("unity voice on 127.0.0.1:%d (%s)" % (PORT, VOICE.dev), flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
