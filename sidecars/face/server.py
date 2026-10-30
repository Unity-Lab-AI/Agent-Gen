#!/usr/bin/env python3
"""Her face: a live, photoreal talking head rendered from one portrait, driven by the audio she speaks.

Renderer: Ditto (Ant Group, Apache-2.0) -- motion-space diffusion on a LivePortrait-class renderer, built for
streaming. The Ditto repo lives in third_party/ditto-talkinghead and its weights in models/ditto; nothing in
there is modified. This file wraps Ditto's own StreamSDK (stream_pipeline_online.py) and keeps it running
for the whole session: silence in, idle face out; speech in, lips and head in sync out.

    sidecars/face/.venv/Scripts/python.exe sidecars/face/server.py [--port 5126] [--portrait assets/portrait/unity-likeness.png]
                                            [--backend pytorch|trt] [--steps 25] [--jpeg 80]

API (127.0.0.1 only)
  GET  /health            {"ok","loaded","backend","device","fps","frames","queue_s","clients","portrait"}
  GET  /stream.mjpg       multipart/x-mixed-replace JPEG stream at 25 fps  (put it in an <img>)
  GET  /frame.jpg         latest frame
  POST /speak             {"wav_b64"} or {"pcm_b64","sample_rate"}  [+ "emotion"]  -> {"queued_s","lead_ms"}
                          queues the audio she is about to say; lead_ms is how long until its first frame shows
  POST /interrupt         drops queued audio (she falls silent and idles)
  POST /emotion           {"emotion": "amused" | 0..7 | [3,4]}   live change of the expression prior
  POST /pose              {"pitch","yaw","roll"} degrees, live head offset; {"sway": true|false} idle motion

Ditto emotion classes: 0 Angry, 1 Disgust, 2 Fear, 3 Happy, 4 Neutral, 5 Sad, 6 Surprise, 7 Contempt.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import math
import os
import sys
import threading
import time
import types
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DITTO_DIR = Path(os.environ.get("DITTO_DIR") or (REPO / "third_party" / "ditto-talkinghead")).resolve()
MODELS = Path(os.environ.get("DITTO_MODELS") or (REPO / "models" / "ditto")).resolve()

ap = argparse.ArgumentParser(description="Unity face sidecar (Ditto live)")
ap.add_argument("--port", type=int, default=int(os.environ.get("UNITY_FACE_PORT", "5126")))
ap.add_argument("--portrait", default=os.environ.get("UNITY_PORTRAIT") or str(REPO / "assets" / "portrait" / "unity-likeness.png"))
ap.add_argument("--backend", default=os.environ.get("DITTO_BACKEND", "pytorch"), choices=["pytorch", "trt"])
ap.add_argument("--steps", type=int, default=int(os.environ.get("DITTO_STEPS", "10")), help="diffusion sampling steps per motion clip (Ditto's online config uses 10; offline uses 50)")
ap.add_argument("--emo", default=os.environ.get("DITTO_EMO", "4"), help="default emotion class or name")
ap.add_argument("--jpeg", type=int, default=int(os.environ.get("UNITY_FACE_JPEG", "80")))
ap.add_argument("--fps", type=int, default=25)
ap.add_argument("--crop-scale", type=float, default=float(os.environ.get("DITTO_CROP_SCALE", "2.3")))
ARGS = ap.parse_args()

if not (DITTO_DIR / "stream_pipeline_online.py").exists():
    sys.exit(f"Ditto not found at {DITTO_DIR}: git clone https://github.com/antgroup/ditto-talkinghead third_party/ditto-talkinghead")
if not (MODELS / "ditto_cfg").exists():
    sys.exit(f"Ditto weights not found at {MODELS}: huggingface_hub.snapshot_download('digital-avatar/ditto-talkinghead', local_dir='models/ditto')")

import numpy as np   # noqa: E402
import cv2           # noqa: E402

# --- make Ditto importable without a C compiler -------------------------------------------------------------
# core/utils/blend/__init__.py runs pyximport (needs MSVC on Windows). Seed an equivalent numpy blend first.
_blend = types.ModuleType("core.utils.blend")


def blend_images_cy(mask, fg, bg, out):
    m = mask[..., None] if mask.ndim == 2 else mask
    np.copyto(out, np.clip(m * fg + (1.0 - m) * bg, 0, 255).astype(np.uint8))


_blend.blend_images_cy = blend_images_cy
sys.modules["core.utils.blend"] = _blend
sys.path.insert(0, str(DITTO_DIR))
os.chdir(DITTO_DIR)   # Ditto resolves a few relative paths from its own folder

import stream_pipeline_online as spo   # noqa: E402

# --- frame sink replaces Ditto's mp4 writer ------------------------------------------------------------------
FPS = ARGS.fps
FRAME_DT = 1.0 / FPS


class FrameSink:
    """Receives rendered RGB frames from Ditto's writer thread, paces them out at FPS, encodes JPEG."""

    def __init__(self, video_path=None, fps=25, **kwargs):
        self.pending = deque()
        self.lock = threading.Lock()
        self.cond = threading.Condition()
        self.latest = None          # jpeg bytes
        self.latest_idx = 0
        self.frames_in = 0
        self.frames_out = 0
        self.t_last = time.time()
        self.fps_out = 0.0
        self._stop = False
        self.thread = threading.Thread(target=self._playout, daemon=True)
        self.thread.start()

    def __call__(self, img, fmt="bgr"):
        rgb = img if fmt == "rgb" else img[..., ::-1]
        ok, jpg = cv2.imencode(".jpg", np.ascontiguousarray(rgb[..., ::-1]), [int(cv2.IMWRITE_JPEG_QUALITY), ARGS.jpeg])
        if not ok:
            return
        with self.lock:
            self.pending.append(jpg.tobytes())
            self.frames_in += 1

    def _publish(self, jpg):
        with self.cond:
            self.latest = jpg
            self.latest_idx += 1
            self.frames_out += 1
            now = time.time()
            self.fps_out = 0.9 * self.fps_out + 0.1 * (1.0 / max(1e-3, now - self.t_last))
            self.t_last = now
            self.cond.notify_all()

    def _playout(self):
        next_t = time.time()
        while not self._stop:
            with self.lock:
                jpg = self.pending.popleft() if self.pending else None
                backlog = len(self.pending)
            if jpg is not None:
                self._publish(jpg)
            # catch up gently if the renderer is ahead; hold the last frame if it is behind
            step = FRAME_DT * (0.85 if backlog > FPS else 1.0)
            next_t += step
            delay = next_t - time.time()
            if delay > 0:
                time.sleep(delay)
            else:
                next_t = time.time()

    def wait_frame(self, last_idx, timeout=1.0):
        with self.cond:
            if self.latest_idx == last_idx:
                self.cond.wait(timeout)
            return self.latest, self.latest_idx

    def queued(self):
        with self.lock:
            return len(self.pending)

    def close(self):
        self._stop = True


spo.VideoWriterByImageIO = FrameSink   # must happen before StreamSDK.setup()

# --- live controls ------------------------------------------------------------------------------------------
EMO_NAMES = ["angry", "disgust", "fear", "happy", "neutral", "sad", "surprise", "contempt"]
# voice-side emotions -> Ditto classes (lists blend)
EMO_MAP = {"neutral": 4, "warm": [3, 4], "happy": 3, "amused": 3, "excited": [3, 6], "sad": 5,
           "concerned": [4, 2], "frustrated": 0, "surprised": 6, "angry": 0, "fear": 2, "disgust": 1, "contempt": 7}


def parse_emo(value):
    if isinstance(value, int):
        return max(0, min(7, value))
    if isinstance(value, list):
        return [max(0, min(7, int(v))) for v in value][:7] or 4
    s = str(value).strip().lower()
    if s.isdigit():
        return max(0, min(7, int(s)))
    if s in EMO_NAMES:
        return EMO_NAMES.index(s)
    return EMO_MAP.get(s, 4)


class LiveCtrl(dict):
    """Ditto asks ctrl_info.get(frame_idx, {}) per frame; answer with the current head offset + idle sway."""

    def __init__(self):
        super().__init__()
        self.pitch = self.yaw = self.roll = 0.0
        self.sway = True
        self.t0 = time.time()

    def get(self, fid, default=None):
        t = time.time() - self.t0
        out = {}
        p, y, r = self.pitch, self.yaw, self.roll
        if self.sway:
            y += 1.6 * math.sin(t * 0.37) + 0.6 * math.sin(t * 1.1)
            p += 0.9 * math.sin(t * 0.53 + 1.0)
            r += 0.5 * math.sin(t * 0.29 + 2.0)
        if p or y or r:
            out = {"delta_pitch": float(p), "delta_yaw": float(y), "delta_roll": float(r)}
        return out


# --- the live avatar ----------------------------------------------------------------------------------------
class LiveFace:
    SR = 16000
    STEP = 3200          # 5 frames * 640 samples = 200 ms per chunk
    HIST = 1920          # 3 frames of context
    LOOK = 1280          # 2 frames of lookahead
    CHUNK = (3, 5, 2)

    def __init__(self):
        backend = ARGS.backend
        data_root = str(MODELS / ("ditto_trt_Ampere_Plus" if backend == "trt" else "ditto_pytorch"))
        cfg_pkl = str(MODELS / "ditto_cfg" / ("v0.4_hubert_cfg_trt_online.pkl" if backend == "trt" else "v0.4_hubert_cfg_pytorch.pkl"))
        t0 = time.time()
        self.sdk = spo.StreamSDK(cfg_pkl, data_root)
        self.ctrl = LiveCtrl()
        self.emo = parse_emo(ARGS.emo)
        import tempfile
        tmp_out = os.path.join(tempfile.gettempdir(), "unity-face-unused.mp4")
        # these mirror ditto_cfg/v0.4_hubert_cfg_trt_online.pkl (online_mode, overlap_v2=70, fix_kp_cond=1, 10 steps)
        setup_kwargs = dict(online_mode=True, emo=self.emo, sampling_timesteps=ARGS.steps, crop_scale=ARGS.crop_scale,
                            overlap_v2=70, fix_kp_cond=1, smo_k_d=3, N_d=FPS * 3600 * 8)
        self.sdk.setup(ARGS.portrait, tmp_out, **setup_kwargs)
        self.sdk.setup_Nd(N_d=FPS * 3600 * 8, ctrl_info=self.ctrl)
        self.sink: FrameSink = self.sdk.writer
        self.load_s = round(time.time() - t0, 1)
        self.device = "cuda"
        # audio queue (16 kHz float32)
        self.lock = threading.Lock()
        self.pending = np.zeros((0,), dtype=np.float32)
        self.hist = np.zeros((self.HIST,), dtype=np.float32)
        self.spoken_s = 0.0
        self.chunks = 0
        self.t_chunk_ms = 0.0
        self.alive = True
        self.feeder = threading.Thread(target=self._feed, daemon=True)
        self.feeder.start()

    # audio in -------------------------------------------------------------------------------------------
    def enqueue(self, pcm16k: np.ndarray):
        with self.lock:
            self.pending = np.concatenate([self.pending, pcm16k.astype(np.float32)])
            return len(self.pending) / self.SR

    def interrupt(self):
        with self.lock:
            self.pending = np.zeros((0,), dtype=np.float32)

    def queue_s(self):
        with self.lock:
            return len(self.pending) / self.SR

    def _take(self):
        with self.lock:
            new = self.pending[: self.STEP]
            self.pending = self.pending[self.STEP:]
            look = self.pending[: self.LOOK]
        if len(new) < self.STEP:
            new = np.pad(new, (0, self.STEP - len(new)))
        if len(look) < self.LOOK:
            look = np.pad(look, (0, self.LOOK - len(look)))
        return new, look

    def _feed(self):
        """Paced at 200 ms: silence keeps her alive and blinking, speech moves her lips."""
        next_t = time.time()
        while self.alive:
            new, look = self._take()
            window = np.concatenate([self.hist, new, look]).astype(np.float32)
            t0 = time.time()
            try:
                self.sdk.run_chunk(window, self.CHUNK)
            except Exception as e:  # keep the loop alive; health reports it
                self.last_error = repr(e)[:200]
            self.t_chunk_ms = 0.8 * self.t_chunk_ms + 0.2 * (time.time() - t0) * 1000
            self.hist = new[-self.HIST:]
            self.chunks += 1
            if np.abs(new).max() > 1e-4:
                self.spoken_s += self.STEP / self.SR
            # do not run ahead of real time by more than ~1 s of frames; the sink paces playout
            while self.alive and self.sink.queued() > FPS:
                time.sleep(0.02)
            next_t += self.STEP / self.SR
            delay = next_t - time.time()
            if delay > 0:
                time.sleep(delay)
            else:
                next_t = time.time()

    # live controls -----------------------------------------------------------------------------------
    def set_emotion(self, value):
        self.emo = parse_emo(value)
        ch = self.sdk.condition_handler
        ch.emo_lst = ch._parse_emo_seq(self.emo)
        ch.num_emo = len(ch.emo_lst)
        ch.emo_seq = np.concatenate([ch.emo_lst] * ch.seq_frames, 0) if ch.num_emo == 1 else None
        return self.emo

    def lead_ms(self):
        # queue ahead of this clip + Ditto's chunk window (context + step + lookahead) + render/playout buffer
        return int(self.queue_s() * 1000 + (self.HIST + self.STEP + self.LOOK) / self.SR * 1000 + self.sink.queued() * FRAME_DT * 1000 + 120)

    def health(self):
        return {"ok": True, "loaded": True, "backend": ARGS.backend, "device": self.device, "portrait": os.path.basename(ARGS.portrait),
                "fps": round(self.sink.fps_out, 1), "frames": self.sink.frames_out, "queue_s": round(self.queue_s(), 2),
                "chunk_ms": round(self.t_chunk_ms), "chunks": self.chunks, "emo": self.emo, "steps": ARGS.steps,
                "load_s": self.load_s, "last_error": getattr(self, "last_error", None), "stream": f"http://127.0.0.1:{ARGS.port}/stream.mjpg"}


def decode_audio(req) -> np.ndarray:
    """-> float32 mono at 16 kHz"""
    if req.get("wav_b64"):
        import soundfile as sf
        data, sr = sf.read(io.BytesIO(base64.b64decode(req["wav_b64"])), dtype="float32", always_2d=True)
        audio = data.mean(1)
    else:
        raw = base64.b64decode(req["pcm_b64"])
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        sr = int(req.get("sample_rate", 16000))
    if sr != 16000 and len(audio) > 1:
        n = int(round(len(audio) * 16000 / sr))
        audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)
    return audio


FACE: LiveFace | None = None
CLIENTS = 0
BOUNDARY = b"--unityframe"


class Handler(BaseHTTPRequestHandler):
    server_version = "unity-face/0.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        global CLIENTS
        path = self.path.split("?")[0]
        if path == "/health":
            return self._json(FACE.health() if FACE else {"ok": False, "loaded": False})
        if path == "/frame.jpg":
            jpg = FACE.sink.latest if FACE else None
            if not jpg:
                return self._json({"error": "no frame yet"}, 503)
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(jpg)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return self.wfile.write(jpg)
        if path == "/stream.mjpg":
            if not FACE:
                return self._json({"error": "face not loaded"}, 503)
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=" + BOUNDARY[2:].decode())
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            CLIENTS += 1
            last = -1
            try:
                while True:
                    jpg, idx = FACE.sink.wait_frame(last)
                    if jpg is None or idx == last:
                        continue
                    last = idx
                    self.wfile.write(BOUNDARY + b"\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
                    self.wfile.flush()
            except (ConnectionError, BrokenPipeError, OSError):
                pass
            finally:
                CLIENTS -= 1
            return
        self._json({"error": "unknown endpoint"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}") if n else {}
        except Exception as e:
            return self._json({"error": str(e)}, 400)
        if not FACE:
            return self._json({"error": "face not loaded"}, 503)
        try:
            if path == "/speak":
                lead = FACE.lead_ms()
                if req.get("emotion") is not None:
                    FACE.set_emotion(req["emotion"])
                audio = decode_audio(req)
                q = FACE.enqueue(audio)
                return self._json({"queued_s": round(q, 2), "lead_ms": lead, "seconds": round(len(audio) / 16000, 2)})
            if path == "/interrupt":
                FACE.interrupt()
                return self._json({"ok": True})
            if path == "/emotion":
                return self._json({"emo": FACE.set_emotion(req.get("emotion", 4))})
            if path == "/pose":
                c = FACE.ctrl
                for k in ("pitch", "yaw", "roll"):
                    if k in req:
                        setattr(c, k, float(req[k]))
                if "sway" in req:
                    c.sway = bool(req["sway"])
                return self._json({"pitch": c.pitch, "yaw": c.yaw, "roll": c.roll, "sway": c.sway})
        except Exception as e:
            return self._json({"error": f"{type(e).__name__}: {str(e)[:300]}"}, 500)
        self._json({"error": "unknown endpoint"}, 404)


def main():
    global FACE
    print(f"face: loading Ditto ({ARGS.backend}) from {MODELS} with portrait {ARGS.portrait} ...", flush=True)
    FACE = LiveFace()
    print(f"face: ready in {FACE.load_s}s; serving http://127.0.0.1:{ARGS.port}/stream.mjpg", flush=True)
    srv = ThreadingHTTPServer(("127.0.0.1", ARGS.port), Handler)
    srv.daemon_threads = True
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        FACE.alive = False


if __name__ == "__main__":
    main()
