#!/usr/bin/env python3
"""Her motion engine: image-to-video, locally, so "put on boxing gloves" becomes a clip of her doing it.

Model: LTX-Video 2B distilled (Lightricks, 0.9.8, 8-step distilled) through diffusers. Weights in
models/ltx-video (single-file transformer+VAE plus the T5-XXL text encoder). Loads on the first request,
offloads to CPU between layers so the brain and the face keep their room on the card, unloads on demand.

    python sidecars/video/server.py [--port 5127] [--model-dir models/ltx-video]

API (127.0.0.1 only)
  GET  /health   -> {"ok", "loaded", "device", "model_present", "busy"}
  POST /i2v      {"image_b64" | "from_clip" (path: continue from that clip's last frame), "prompt", "negative"?,
                  "frames"? (default 97 ≈ 4 s), "fps"? 25, "width"? 768, "height"? 512,
                  "steps"? 8, "guidance"? 1.0, "seed"?} -> {"ok", "path", "seconds", "frames", "fps", "seed"}
  POST /cancel   -> the clip in flight stops at its next step and /i2v answers 409 {"cancelled": true}
  POST /unload   -> frees the GPU
The clip is written as mp4 (25 fps) under .run/clips/ and the path returned; the face sidecar takes that
path as a video source (/appearance) and the window plays it.
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
ap = argparse.ArgumentParser(description="Unity video sidecar (LTX-Video image-to-video)")
ap.add_argument("--port", type=int, default=int(os.environ.get("UNITY_VIDEO_PORT", "5127")))
ap.add_argument("--model-dir", default=os.environ.get("UNITY_VIDEO_MODEL_DIR") or str(REPO / "models" / "ltx-video"))
ap.add_argument("--single-file", default=os.environ.get("UNITY_VIDEO_SINGLE_FILE", "ltxv-2b-0.9.8-distilled.safetensors"))
ap.add_argument("--device", default=os.environ.get("UNITY_VIDEO_DEVICE", "auto"), choices=["auto", "cuda", "cpu"])
ap.add_argument("--out", default=str(REPO / ".run" / "clips"))
ARGS = ap.parse_args()
MODEL_DIR = Path(ARGS.model_dir)
SINGLE = MODEL_DIR / ARGS.single_file
OUT = Path(ARGS.out)
OUT.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()
_state = {"pipe": None, "device": None, "busy": False, "last_error": None, "cancel": False}


class Cancelled(Exception):
    pass


def _step_cb(pipe, step, timestep, kw):
    if _state["cancel"]:
        raise Cancelled("cancelled at step %d" % step)
    return kw
NEG = ("worst quality, inconsistent motion, blurry, jittery, distorted, extra limbs, extra arms, deformed hands, "
       "morphing face, flicker, watermark, text")


def log(*a):
    print(time.strftime("%H:%M:%S"), "video:", *a, flush=True)


def device():
    if _state["device"]:
        return _state["device"]
    import torch
    d = ARGS.device if ARGS.device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")
    _state["device"] = d
    return d


def load():
    if _state["pipe"] is not None:
        return _state["pipe"]
    import torch
    from diffusers import LTXImageToVideoPipeline, AutoencoderKLLTXVideo, LTXVideoTransformer3DModel
    from transformers import T5EncoderModel, T5Tokenizer   # model_index expects the slow T5Tokenizer class
    if not SINGLE.exists():
        raise FileNotFoundError(f"LTX weights not found: {SINGLE}")
    t0 = time.time()
    dev = device()
    dtype = torch.bfloat16 if dev == "cuda" else torch.float32
    log("loading", SINGLE.name, "on", dev)
    transformer = LTXVideoTransformer3DModel.from_single_file(str(SINGLE), torch_dtype=dtype)
    vae = AutoencoderKLLTXVideo.from_single_file(str(SINGLE), torch_dtype=dtype)
    text_encoder = T5EncoderModel.from_pretrained(str(MODEL_DIR), subfolder="text_encoder", torch_dtype=dtype)
    tokenizer = T5Tokenizer.from_pretrained(str(MODEL_DIR), subfolder="tokenizer")
    pipe = LTXImageToVideoPipeline.from_pretrained(str(MODEL_DIR), transformer=transformer, vae=vae,
                                                   text_encoder=text_encoder, tokenizer=tokenizer, torch_dtype=dtype)
    if dev == "cuda":
        pipe.enable_model_cpu_offload()      # T5-XXL alone is ~9 GB; stream layers through the card instead
        pipe.vae.enable_tiling()
    else:
        pipe.to("cpu")
    _state["pipe"] = pipe
    log("loaded in %.1fs" % (time.time() - t0))
    return pipe


def unload():
    had = _state["pipe"] is not None
    _state["pipe"] = None
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


def i2v(req):
    import torch
    from PIL import Image
    from diffusers.utils import export_to_video
    pipe = load()
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
    frames = int(req.get("frames") or 97)
    frames = max(9, min(257, (frames - 1) // 8 * 8 + 1))     # LTX wants 8k+1
    fps = int(req.get("fps") or 25)
    steps = int(req.get("steps") or 8)
    guidance = float(req.get("guidance") or 1.0)           # distilled: guidance 1
    seed = int(req.get("seed") or random.randint(1, 2 ** 31 - 1))
    gen = torch.Generator(device()).manual_seed(seed)
    prompt = str(req.get("prompt") or "").strip() or "a woman moving naturally, cinematic, realistic"
    t0 = time.time()
    if device() == "cuda":
        torch.cuda.empty_cache()
    _state["cancel"] = False
    out = pipe(image=img, prompt=prompt, negative_prompt=str(req.get("negative") or NEG), width=w, height=h,
               num_frames=frames, num_inference_steps=steps, guidance_scale=guidance, generator=gen,
               callback_on_step_end=_step_cb).frames[0]
    path = OUT / ("clip-%d-%s.mp4" % (int(time.time() * 1000), seed))
    export_to_video(out, str(path), fps=fps)
    return {"ok": True, "path": str(path), "seconds": round(time.time() - t0, 1), "frames": frames, "fps": fps,
            "seed": seed, "width": w, "height": h, "prompt": prompt}


class Handler(BaseHTTPRequestHandler):
    server_version = "unity-video/0.1"

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
            return self._json({"ok": True, "loaded": _state["pipe"] is not None, "device": _state["device"] or ARGS.device,
                               "model_present": SINGLE.exists(), "model": SINGLE.name, "busy": _state["busy"], "last_error": _state["last_error"]})
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
            log("clip %s %dx%d %d frames in %.1fs" % (os.path.basename(res["path"]), res["width"], res["height"], res["frames"], res["seconds"]))
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
    log("serving on 127.0.0.1:%d model=%s present=%s" % (ARGS.port, SINGLE.name, SINGLE.exists()))
    ThreadingHTTPServer(("127.0.0.1", ARGS.port), Handler).serve_forever()
