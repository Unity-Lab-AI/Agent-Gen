#!/usr/bin/env python3
"""Her motion engine: image-to-video, locally, so "put on boxing gloves" becomes a clip of her doing it.

Two engines behind one API, picked per request (`engine`):
  ltx   LTX-Video 2B 0.9.8 distilled (8 steps, ~15 s a clip). Fast, timid with bodies. The idle reel.
  wan   Wan 2.2 TI2V-5B (diffusers). Slow (minutes), real body physics: a slap lands, flesh moves and settles.
        Commanded motions and new looks. Operator: "we need giggle physics, this is a adult app".
Weights: models/ltx-video and models/wan2.2-ti2v-5b. An engine loads on first use, offloads layers through the
card (model_cpu_offload), and the other engine is dropped when switching so the two never share the card.

    python sidecars/video/server.py [--port 5127] [--model-dir models/ltx-video] [--wan-dir models/wan2.2-ti2v-5b]

API (127.0.0.1 only)
  GET  /health   -> {"ok", "loaded", "engine", "engines": {"ltx": present, "wan": present}, "busy", ...}
  POST /i2v      {"image_b64" | "from_clip" (path: continue from that clip's last frame), "prompt", "negative"?,
                  "engine"? ("wan"|"ltx", default ltx), "frames"?, "fps"?, "width"?, "height"?,
                  "steps"?, "guidance"?, "seed"?} -> {"ok", "path", "seconds", "frames", "fps", "seed", "engine"}
  POST /cancel   -> the clip in flight stops at its next step and /i2v answers 409 {"cancelled": true}
  POST /unload   -> frees the GPU
The clip is written as mp4 under the app's run folder and the path returned; the face sidecar takes that path
as a video source (/appearance) and the window plays it.
"""
from __future__ import annotations

import argparse
import base64
import gc
import io
import json
import os
import random
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
ap = argparse.ArgumentParser(description="Unity video sidecar (image-to-video: LTX 2B fast, Wan 2.2 5B physics)")
ap.add_argument("--port", type=int, default=int(os.environ.get("UNITY_VIDEO_PORT", "5127")))
ap.add_argument("--model-dir", default=os.environ.get("UNITY_VIDEO_MODEL_DIR") or str(REPO / "models" / "ltx-video"))
ap.add_argument("--single-file", default=os.environ.get("UNITY_VIDEO_SINGLE_FILE", "ltxv-2b-0.9.8-distilled.safetensors"))
ap.add_argument("--wan-dir", default=os.environ.get("UNITY_VIDEO_WAN_DIR") or str(REPO / "models" / "wan2.2-ti2v-5b"))
ap.add_argument("--device", default=os.environ.get("UNITY_VIDEO_DEVICE", "auto"), choices=["auto", "cuda", "cpu"])
ap.add_argument("--out", default=os.path.join(os.environ.get("AGENTGEN_RUN") or str(REPO / ".run"), "clips"))   # the app keeps renders in its data root
ARGS = ap.parse_args()
MODEL_DIR = Path(ARGS.model_dir)
SINGLE = MODEL_DIR / ARGS.single_file
WAN_DIR = Path(ARGS.wan_dir)
OUT = Path(ARGS.out)
OUT.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()
_state = {"pipe": None, "engine": None, "device": None, "busy": False, "last_error": None, "cancel": False}

# per-engine defaults: LTX wants 8k+1 frames at 25 fps and no guidance (distilled); Wan wants 4k+1 at 24 fps
ENGINES = {
    "ltx": {"present": lambda: SINGLE.exists(), "frames": 73, "fps": 25, "steps": 8, "guidance": 1.0, "frame_step": 8, "max_frames": 257},
    # measured on the 4070 Ti SUPER: ~0.6 s a step warm at 352x640, so 49 frames x 20 steps is about a minute
    "wan": {"present": lambda: (WAN_DIR / "model_index.json").exists() and (WAN_DIR / "transformer").exists() and not any((WAN_DIR / ".cache").rglob("*.incomplete")), "frames": 49, "fps": 24, "steps": 20, "guidance": 5.0, "frame_step": 4, "max_frames": 161},
}
NEG = ("camera movement, camera pan, zoom, shaky camera, moving background, worst quality, inconsistent motion, blurry, jittery, distorted, extra limbs, extra arms, deformed hands, "
       "morphing face, flicker, watermark, text, static, still image")


class Cancelled(Exception):
    pass


def _step_cb(pipe, step, timestep, kw):
    if _state["cancel"]:
        raise Cancelled("cancelled at step %d" % step)
    return kw


def log(*a):
    print(time.strftime("%H:%M:%S"), "video:", *a, flush=True)


def device():
    if _state["device"]:
        return _state["device"]
    import torch
    d = ARGS.device if ARGS.device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")
    _state["device"] = d
    return d


def pick_engine(req):
    want = str(req.get("engine") or os.environ.get("UNITY_VIDEO_ENGINE") or "ltx").lower()
    if want not in ENGINES or not ENGINES[want]["present"]():
        want = "ltx" if ENGINES["ltx"]["present"]() else ("wan" if ENGINES["wan"]["present"]() else want)
    return want


def load(engine):
    if _state["pipe"] is not None and _state["engine"] == engine:
        return _state["pipe"]
    if _state["pipe"] is not None:
        unload()                                    # one engine on the card at a time
    import torch
    t0 = time.time()
    dev = device()
    dtype = torch.bfloat16 if dev == "cuda" else torch.float32
    if engine == "wan":
        from diffusers import WanImageToVideoPipeline
        if not (WAN_DIR / "model_index.json").exists():
            raise FileNotFoundError(f"Wan weights not found: {WAN_DIR}")
        log("loading Wan 2.2 TI2V-5B on", dev)
        pipe = WanImageToVideoPipeline.from_pretrained(str(WAN_DIR), dtype=dtype)   # diffusers >= 0.41: Wan 2.2 TI2V through the image pipeline
    else:
        from diffusers import LTXImageToVideoPipeline, AutoencoderKLLTXVideo, LTXVideoTransformer3DModel
        from transformers import T5EncoderModel, T5Tokenizer   # model_index expects the slow T5Tokenizer class
        if not SINGLE.exists():
            raise FileNotFoundError(f"LTX weights not found: {SINGLE}")
        log("loading", SINGLE.name, "on", dev)
        transformer = LTXVideoTransformer3DModel.from_single_file(str(SINGLE), torch_dtype=dtype)
        vae = AutoencoderKLLTXVideo.from_single_file(str(SINGLE), torch_dtype=dtype)
        text_encoder = T5EncoderModel.from_pretrained(str(MODEL_DIR), subfolder="text_encoder", torch_dtype=dtype)
        tokenizer = T5Tokenizer.from_pretrained(str(MODEL_DIR), subfolder="tokenizer")
        pipe = LTXImageToVideoPipeline.from_pretrained(str(MODEL_DIR), transformer=transformer, vae=vae,
                                                       text_encoder=text_encoder, tokenizer=tokenizer, torch_dtype=dtype)
    if dev == "cuda":
        pipe.enable_model_cpu_offload()      # the text encoders alone are ~9-11 GB; stream layers through the card
        try:
            pipe.vae.enable_tiling()
        except Exception:
            pass
    else:
        pipe.to("cpu")
    _state["pipe"], _state["engine"] = pipe, engine
    log("%s loaded in %.1fs" % (engine, time.time() - t0))
    return pipe


def unload():
    had = _state["pipe"] is not None
    _state["pipe"], _state["engine"] = None, None
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    if had:
        log("unloaded")
    return had


def round32(n, lo=256, hi=1024):
    n = max(lo, min(hi, int(n)))
    return n - (n % 32)


def write_mp4(frames, path, fps):
    """mp4 via OpenCV, in-process: no ffmpeg child process (a console flash on Windows every time)."""
    import cv2
    import numpy as np
    first = np.asarray(frames[0])
    h, w = first.shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    try:
        for fr in frames:
            a = np.asarray(fr)
            if a.dtype != np.uint8:
                a = (np.clip(a, 0, 1) * 255).astype(np.uint8)
            vw.write(cv2.cvtColor(a, cv2.COLOR_RGB2BGR))
    finally:
        vw.release()


def stabilize(frames):
    """Pin the room to the first frame so only she moves. The video models pan and zoom on their own, and the face
    plays a clip forward and back, so any camera drift reads as the whole scene wobbling. The camera's motion is
    the dominant similarity transform of features tracked in the frame's edge bands (the room around her, not her
    body), chained frame to frame and undone by warping each frame back onto the first."""
    import cv2
    import numpy as np
    arr = [np.asarray(f) for f in frames]
    arr = [(np.clip(a, 0, 1) * 255).astype(np.uint8) if a.dtype != np.uint8 else a for a in arr]
    h, w = arr[0].shape[:2]
    mask = np.zeros((h, w), np.uint8)
    bw, bh = max(8, w // 5), max(8, h // 6)
    mask[:, :bw] = 255; mask[:, w - bw:] = 255; mask[:bh, :] = 255
    gray = [cv2.cvtColor(a, cv2.COLOR_RGB2GRAY) for a in arr]
    acc = np.eye(3)                                   # frame i -> frame 0
    out = [arr[0]]
    for i in range(1, len(arr)):
        pts = cv2.goodFeaturesToTrack(gray[i - 1], 300, 0.01, 6, mask=mask)
        m = None
        if pts is not None and len(pts) >= 12:
            nxt, st, _ = cv2.calcOpticalFlowPyrLK(gray[i - 1], gray[i], pts, None)
            good = st.ravel() == 1
            if good.sum() >= 10:
                m, _ = cv2.estimateAffinePartial2D(nxt[good], pts[good], method=cv2.RANSAC, ransacReprojThreshold=2.0)
        step = np.vstack([m, [0, 0, 1]]) if m is not None else np.eye(3)
        acc = acc @ step
        out.append(cv2.warpAffine(arr[i], acc[:2], (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE))
    return out


def release_gpu(pipe):
    """After a run the offload hooks leave the last modules parked on the card; send everything back and
    return the cached blocks, so the live face and the brain get the room back immediately."""
    try:
        pipe.maybe_free_model_hooks()
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def i2v(req):
    import torch
    from PIL import Image
    engine = pick_engine(req)
    E = ENGINES[engine]
    pipe = load(engine)
    if req.get("from_clip") and not req.get("image_b64"):
        # continue a clip: its last frame is the new start, so her motion chains instead of restarting
        import cv2
        cap = cv2.VideoCapture(req["from_clip"])
        last = None
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            last = fr
        cap.release()
        if last is None:
            raise ValueError("from_clip has no frames: %s" % req["from_clip"])
        img = Image.fromarray(cv2.cvtColor(last, cv2.COLOR_BGR2RGB))
    else:
        raw = base64.b64decode(req["image_b64"].split(",", 1)[1] if str(req["image_b64"]).startswith("data:") else req["image_b64"])
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    w = round32(req.get("width") or 768)
    h = round32(req.get("height") or 512)
    # keep her aspect: fit the requested box
    ar = img.width / img.height
    if ar < w / h:
        w = round32(h * ar)
    else:
        h = round32(w / ar)
    img = img.resize((w, h), Image.LANCZOS)
    step = E["frame_step"]
    frames = int(req.get("frames") or E["frames"])
    frames = max(step + 1, min(E["max_frames"], (frames - 1) // step * step + 1))
    fps = int(req.get("fps") or E["fps"])
    steps = int(req.get("steps") or E["steps"])
    guidance = float(req.get("guidance") or E["guidance"])
    seed = int(req.get("seed") or random.randint(1, 2 ** 31 - 1))
    gen = torch.Generator(device()).manual_seed(seed)
    prompt = str(req.get("prompt") or "").strip() or "a woman moving naturally, cinematic, realistic"
    t0 = time.time()
    if device() == "cuda":
        torch.cuda.empty_cache()
    _state["cancel"] = False
    try:
        out = pipe(image=img, prompt=prompt, negative_prompt=str(req.get("negative") or NEG), width=w, height=h,
                   num_frames=frames, num_inference_steps=steps, guidance_scale=guidance, generator=gen,
                   callback_on_step_end=_step_cb).frames[0]
    finally:
        release_gpu(pipe)
    path = OUT / ("clip-%d-%s.mp4" % (int(time.time() * 1000), seed))
    if req.get("stabilize", True):
        out = stabilize(out)
    write_mp4(out, path, fps)
    return {"ok": True, "path": str(path), "seconds": round(time.time() - t0, 1), "frames": frames, "fps": fps,
            "seed": seed, "width": w, "height": h, "prompt": prompt, "engine": engine}


class Handler(BaseHTTPRequestHandler):
    server_version = "unity-video/0.2"

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

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            present = {k: bool(v["present"]()) for k, v in ENGINES.items()}
            return self._json({"ok": True, "loaded": _state["pipe"] is not None, "engine": _state["engine"], "engines": present,
                               "device": _state["device"] or ARGS.device, "model_present": any(present.values()),
                               "model": SINGLE.name, "busy": _state["busy"], "last_error": _state["last_error"]})
        self._json({"error": "unknown endpoint"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}") if n else {}
        except Exception as e:
            return self._json({"error": str(e)}, 400)
        if path == "/unload":
            with _lock:
                return self._json({"ok": True, "unloaded": unload()})
        if path == "/cancel":                       # stop the clip in flight at its next step (she has something to say)
            _state["cancel"] = True
            return self._json({"ok": True, "busy": _state["busy"]})
        if path != "/i2v":
            return self._json({"error": "unknown endpoint"}, 404)
        if not req.get("image_b64") and not req.get("from_clip"):
            return self._json({"error": "image_b64 or from_clip required"}, 422)
        try:
            with _lock:
                _state["busy"] = True
                try:
                    res = i2v(req)
                finally:
                    _state["busy"] = False
            log("clip %s [%s] %dx%d %d frames in %.1fs" % (os.path.basename(res["path"]), res["engine"], res["width"], res["height"], res["frames"], res["seconds"]))
            return self._json(res)
        except FileNotFoundError as e:
            return self._json({"error": str(e)}, 503)
        except Cancelled as e:
            log("clip cancelled:", e)
            return self._json({"error": "cancelled", "cancelled": True}, 409)
        except Exception as e:
            _state["last_error"] = "%s: %s" % (type(e).__name__, str(e)[-600:])
            log("failed:", _state["last_error"])
            return self._json({"error": _state["last_error"]}, 500)


if __name__ == "__main__":
    log("serving on 127.0.0.1:%d ltx=%s wan=%s" % (ARGS.port, SINGLE.exists(), (WAN_DIR / "model_index.json").exists()))
    ThreadingHTTPServer(("127.0.0.1", ARGS.port), Handler).serve_forever()
