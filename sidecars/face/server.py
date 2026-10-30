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
ap.add_argument("--portrait", default=os.environ.get("UNITY_PORTRAIT") or str(REPO / "assets" / "portrait" / "unity-bust.jpg"),
                help="her portrait: assets/portrait/unity-bust.jpg (head and shoulders, default), unity-face.jpg (tight), unity-full.jpg (full body)")
ap.add_argument("--backend", default=os.environ.get("DITTO_BACKEND", "pytorch"), choices=["pytorch", "trt"])
ap.add_argument("--steps", type=int, default=int(os.environ.get("DITTO_STEPS", "5")), help="diffusion sampling steps per motion clip (Ditto's online config uses 10; 5 keeps the 4070 Ti SUPER's PyTorch path real-time)")
ap.add_argument("--overlap", type=int, default=int(os.environ.get("DITTO_OVERLAP", "50")),
                help="motion clip overlap (Ditto online default 70 = new motion every 10 frames / 400 ms; 50 = every 30 frames, a third of the diffusion cost, ~1.2 s more lead)")
ap.add_argument("--emo", default=os.environ.get("DITTO_EMO", "4"), help="default emotion class or name")
ap.add_argument("--jpeg", type=int, default=int(os.environ.get("UNITY_FACE_JPEG", "80")))
ap.add_argument("--fp16", default=os.environ.get("DITTO_FP16", "0"), help="1 = wrap warp/decode in an extra fp16 autocast. Off by default: Ditto's PyTorch warp/decode already autocast fp16 internally")
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
        self.latest_idx = 0         # == number of frames published so far; frame k of the feed timeline is published when latest_idx becomes k+1
        self.cues = []              # [(frame_index, callback)] fired the moment that frame is published
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
        fire = []
        with self.cond:
            self.latest = jpg
            self.latest_idx += 1
            self.frames_out += 1
            now = time.time()
            self.fps_out = 0.9 * self.fps_out + 0.1 * (1.0 / max(1e-3, now - self.t_last))
            self.t_last = now
            keep = []
            for frame_index, cb in self.cues:
                (fire if self.latest_idx > frame_index else keep).append((frame_index, cb))
            self.cues = keep
            self.cond.notify_all()
        for _, cb in fire:
            try:
                cb()
            except Exception:
                pass

    def cue(self, frame_index, callback):
        with self.cond:
            self.cues.append((frame_index, callback))

    def clear_cues(self):
        with self.cond:
            self.cues = []

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
        # Block until a NEW frame exists. Before the first frame is published this must wait too, or a viewer
        # that connects at startup spins here holding the GIL and starves the motion thread (seen as a
        # minutes-long stall at 0 fps whenever the app connected before the first clip rendered).
        with self.cond:
            if self.latest is None or self.latest_idx == last_idx:
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
                            overlap_v2=ARGS.overlap, fix_kp_cond=1, smo_k_d=3, N_d=FPS * 3600 * 8)
        self.valid_clip_frames = 80 - ARGS.overlap     # frames of audio features Ditto waits for before each motion clip
        self.sdk.setup(ARGS.portrait, tmp_out, **setup_kwargs)
        self.sdk.setup_Nd(N_d=FPS * 3600 * 8, ctrl_info=self.ctrl)
        self.sink: FrameSink = self.sdk.writer
        self.stage_ms = {}
        self._instrument()
        self.load_s = round(time.time() - t0, 1)
        self.device = "cuda"
        # audio queue (16 kHz float32)
        self.lock = threading.Lock()
        self.pending = np.zeros((0,), dtype=np.float32)
        self.hist = np.zeros((self.HIST,), dtype=np.float32)
        self.fed_samples = 0          # feed-timeline position: samples handed to Ditto so far (speech or silence)
        self.spoken_s = 0.0
        self.chunks = 0
        self.t_chunk_ms = 0.0
        self.alive = True
        self.feeder = threading.Thread(target=self._feed, daemon=True)
        self.feeder.start()

    def _instrument(self):
        """Wrap each pipeline stage with a timer (EMA ms, reported by /health) and, for the two heavy
        renderer stages, fp16 autocast. Ditto's own TensorRT build runs warp/decode in fp16; the PyTorch
        path is fp32 by default, which is the difference between ~15 and ~25 fps here."""
        import torch
        torch.backends.cudnn.benchmark = True
        use_fp16 = str(ARGS.fp16) not in ("0", "false", "no") and torch.cuda.is_available()
        sdk = self.sdk
        stage_ms = self.stage_ms

        def to_f32(out):
            # fp16 results must not reach numpy/OpenCV as half
            if isinstance(out, torch.Tensor):
                return out.float() if out.dtype == torch.float16 else out
            if isinstance(out, np.ndarray) and out.dtype == np.float16:
                return out.astype(np.float32)
            if isinstance(out, (list, tuple)):
                return type(out)(to_f32(o) for o in out)
            return out

        class Stage:
            """Callable proxy: times the call, optionally autocasts, and delegates every other attribute
            (seq_frames, valid_clip_len, d0, set_Nd, ...) to the real Ditto component."""
            def __init__(self, name, inner, autocast):
                object.__setattr__(self, "_name", name)
                object.__setattr__(self, "_inner", inner)
                object.__setattr__(self, "_autocast", autocast)
            def __call__(self, *a, **k):
                t = time.perf_counter()
                if self._autocast:
                    with torch.autocast("cuda", dtype=torch.float16):
                        out = self._inner(*a, **k)
                    out = to_f32(out)
                else:
                    out = self._inner(*a, **k)
                ms = (time.perf_counter() - t) * 1000
                stage_ms[self._name] = round(0.9 * stage_ms.get(self._name, ms) + 0.1 * ms, 1)
                return out
            def __getattr__(self, item):
                return getattr(object.__getattribute__(self, "_inner"), item)
            def __setattr__(self, key, value):
                setattr(object.__getattribute__(self, "_inner"), key, value)

        sdk.audio2motion = Stage("audio2motion", sdk.audio2motion, False)   # per motion clip, not per frame
        sdk.motion_stitch = Stage("stitch", sdk.motion_stitch, False)
        sdk.warp_f3d = Stage("warp", sdk.warp_f3d, use_fp16)
        sdk.decode_f3d = Stage("decode", sdk.decode_f3d, use_fp16)
        sdk.putback = Stage("putback", sdk.putback, False)
        self.fp16 = use_fp16

    # audio in -------------------------------------------------------------------------------------------
    def enqueue(self, pcm16k: np.ndarray, play_wav: bytes | None = None):
        """Queue speech. Returns (queued_s, start_frame). Frame k of her video carries feed sample k*640, so the
        first frame of this clip is start_sample // 640. With play_wav the sidecar itself plays the audio the
        instant that frame is published: the tightest lip sync available, no latency estimate involved."""
        with self.lock:
            start_sample = self.fed_samples + len(self.pending)
            self.pending = np.concatenate([self.pending, pcm16k.astype(np.float32)])
            queued = len(self.pending) / self.SR
        start_frame = start_sample // 640
        if play_wav is not None:
            self.sink.cue(start_frame, lambda: play_audio(play_wav))
        return queued, start_frame

    def interrupt(self):
        with self.lock:
            self.pending = np.zeros((0,), dtype=np.float32)
        self.sink.clear_cues()
        stop_audio()

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
        """Paced at 200 ms: silence keeps her alive and blinking, speech moves her lips.
        Backpressure: the feed may lead the published picture by at most MAX_LAG frames. If the renderer
        falls behind, the feed waits (speech is delayed but stays frame-locked to the lips) instead of
        letting Ditto's internal queues pile up tens of seconds of unseen frames."""
        next_t = time.time()
        max_lag = self.valid_clip_frames * 2 + 30     # what Ditto needs in flight, plus a little
        self.swapping = False
        self.paused = False      # held while the image/video engines own the GPU: her last frame stays up
        while self.alive:
            while self.alive and (self.swapping or self.paused or (self.fed_samples // 640 - self.sink.latest_idx) > max_lag):
                time.sleep(0.02)
                next_t = time.time()
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
            with self.lock:
                self.fed_samples += self.STEP
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

    # appearance --------------------------------------------------------------------------------------
    def set_source(self, path):
        """Make a new image (or video) her face, live. Ditto re-registers the avatar: the old worker threads are
        drained and joined, the new ones start, and the frame sink carries its counters across so frame indices,
        cues and the feed timeline stay continuous. Takes a second or two; the last frame holds meanwhile."""
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        t0 = time.time()
        self.swapping = True
        try:
            old_sink = self.sink
            with self.lock:
                self.pending = np.zeros((0,), dtype=np.float32)   # speech queued for the old face is dropped
            try:
                self.sdk.close()
            except Exception as e:                                  # a worker that died earlier surfaces here; carry on
                print("face: close while swapping:", repr(e)[:200], flush=True)
            import tempfile
            tmp_out = os.path.join(tempfile.gettempdir(), "unity-face-unused.mp4")
            setup_kwargs = dict(online_mode=True, emo=self.emo, sampling_timesteps=ARGS.steps, crop_scale=ARGS.crop_scale,
                                overlap_v2=ARGS.overlap, fix_kp_cond=1, smo_k_d=3, N_d=FPS * 3600 * 8)
            self.sdk.setup(path, tmp_out, **setup_kwargs)
            self.sdk.setup_Nd(N_d=FPS * 3600 * 8, ctrl_info=self.ctrl)
            new_sink = self.sdk.writer
            with old_sink.cond:
                new_sink.latest, new_sink.latest_idx, new_sink.frames_out = old_sink.latest, old_sink.latest_idx, old_sink.frames_out
                new_sink.cues = []
            old_sink.close()
            self.sink = new_sink
            self._instrument()
            with self.lock:
                self.fed_samples = self.sink.latest_idx * 640          # re-anchor the feed timeline to the picture
                self.hist = np.zeros((self.HIST,), dtype=np.float32)
            ARGS.portrait = path
            return {"ok": True, "portrait": os.path.basename(path), "seconds": round(time.time() - t0, 2)}
        finally:
            self.swapping = False
            self.paused = False      # a new look always resumes her

    # live controls -----------------------------------------------------------------------------------
    def set_emotion(self, value):
        self.emo = parse_emo(value)
        ch = self.sdk.condition_handler
        ch.emo_lst = ch._parse_emo_seq(self.emo)
        ch.num_emo = len(ch.emo_lst)
        ch.emo_seq = np.concatenate([ch.emo_lst] * ch.seq_frames, 0) if ch.num_emo == 1 else None
        return self.emo

    def lead_ms(self):
        # how far the feed is ahead of the picture right now + queued speech ahead of this clip + hubert lookahead
        lag_frames = max(0, self.fed_samples // 640 - self.sink.latest_idx)
        return int(self.queue_s() * 1000 + lag_frames * FRAME_DT * 1000 + self.LOOK / self.SR * 1000 + 100)

    def health(self):
        return {"ok": True, "loaded": True, "backend": ARGS.backend, "device": self.device, "portrait": os.path.basename(ARGS.portrait),
                "fps": round(self.sink.fps_out, 1), "frames": self.sink.frames_out, "queue_s": round(self.queue_s(), 2),
                "chunk_ms": round(self.t_chunk_ms), "chunks": self.chunks, "emo": self.emo, "steps": ARGS.steps, "overlap": ARGS.overlap,
                "fp16": self.fp16, "stage_ms": self.stage_ms, "lag_frames": int(self.fed_samples // 640 - self.sink.latest_idx),
                "paused": getattr(self, "paused", False),
                "load_s": self.load_s, "last_error": getattr(self, "last_error", None),
                "worker_error": repr(self.sdk.worker_exception)[:300] if self.sdk.worker_exception else None,
                "stopped": self.sdk.stop_event.is_set(), "stream": f"http://127.0.0.1:{ARGS.port}/stream.mjpg"}


def decode_audio(req):
    """-> (float32 mono at 16 kHz for Ditto, original WAV bytes for playback)"""
    import soundfile as sf
    if req.get("wav_b64"):
        wav_bytes = base64.b64decode(req["wav_b64"])
        data, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=True)
        audio = data.mean(1)
    else:
        raw = base64.b64decode(req["pcm_b64"])
        sr = int(req.get("sample_rate", 16000))
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        buf = io.BytesIO()
        sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
        wav_bytes = buf.getvalue()
    if sr != 16000 and len(audio) > 1:
        n = int(round(len(audio) * 16000 / sr))
        audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)
    return audio, wav_bytes


# --- local audio out (for the native app / viewer path; remote clients play their own audio) ------------------
_audio_lock = threading.Lock()
_audio_player = {"sd": None}
try:
    import sounddevice as _sd
    _audio_player["sd"] = _sd
except Exception:
    _sd = None


def play_audio(wav_bytes: bytes):
    """Start playing a WAV now, without blocking the frame thread. sounddevice if present, else winsound."""
    def run():
        try:
            if _audio_player["sd"] is not None:
                import soundfile as sf
                data, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
                with _audio_lock:
                    _audio_player["sd"].play(data, sr)
            else:
                import winsound
                winsound.PlaySound(wav_bytes, winsound.SND_MEMORY | winsound.SND_ASYNC)
        except Exception as e:
            print("audio out failed:", e, flush=True)
    threading.Thread(target=run, daemon=True).start()


def stop_audio():
    try:
        if _audio_player["sd"] is not None:
            _audio_player["sd"].stop()
        else:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
    except Exception:
        pass


FACE: LiveFace | None = None
SWAP_LOCK = threading.Lock()
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
                        time.sleep(0.01)     # never busy-loop on the GIL
                        continue
                    last = idx
                    # X-Frame-Index lets a remote player start its audio exactly on /speak's start_frame
                    self.wfile.write(BOUNDARY + b"\r\nContent-Type: image/jpeg\r\nX-Frame-Index: " + str(idx).encode()
                                     + b"\r\nContent-Length: " + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
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
                audio, wav_bytes = decode_audio(req)
                play_here = bool(req.get("play", False))
                q, start_frame = FACE.enqueue(audio, wav_bytes if play_here else None)
                return self._json({"queued_s": round(q, 2), "lead_ms": lead, "seconds": round(len(audio) / 16000, 2),
                                   "start_frame": int(start_frame), "frames_published": FACE.sink.latest_idx, "played_here": play_here})
            if path == "/interrupt":
                FACE.interrupt()
                return self._json({"ok": True})
            if path == "/pause":
                FACE.paused = True
                return self._json({"ok": True, "paused": True})
            if path == "/resume":
                FACE.paused = False
                return self._json({"ok": True, "paused": False})
            if path == "/appearance":
                src = req.get("path")
                if req.get("image_b64") and not src:
                    import tempfile
                    src = os.path.join(tempfile.gettempdir(), "unity-look-%d.png" % int(time.time() * 1000))
                    open(src, "wb").write(base64.b64decode(req["image_b64"]))
                with SWAP_LOCK:
                    return self._json(FACE.set_source(src))
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
