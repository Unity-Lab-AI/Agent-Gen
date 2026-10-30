"""
sd_server.py — local uncensored image generation for Unity.

Speaks the AUTOMATIC1111 API shape (`/sdapi/v1/options`, `/sdapi/v1/txt2img`) on
127.0.0.1:7860, so `server/server.mjs` drives it with no changes — but it is
~150 lines of diffusers instead of a 6 GB WebUI install, because this machine
already has torch 2.7.1 + CUDA.

⛔ NO SAFETY CHECKER. `safety_checker=None` is deliberate and load-bearing: the
default diffusers pipeline silently returns BLACK IMAGES for anything its NSFW
classifier dislikes, which for this project would mean her pictures vanishing
with no error anywhere. Uncensored is the requirement, and a silent black frame
is also exactly the kind of hidden failure this project's LAWs ban.

Everything stays on this machine. The model is a local file; nothing is fetched
at render time.
"""

import base64
import io
import json
import os
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODELS = os.path.join(ROOT, "models")
PORT = int(os.environ.get("SD_PORT", "7860"))

_pipe = None
_lock = threading.Lock()          # one render at a time; a 4070 does not need a queue
_status = {"state": "starting", "model": None, "device": None, "error": None}


def find_checkpoint():
    """Any .safetensors/.ckpt in models/ — first by name, so drops are picked up."""
    if not os.path.isdir(MODELS):
        return None
    files = sorted(f for f in os.listdir(MODELS) if f.endswith((".safetensors", ".ckpt")))
    return os.path.join(MODELS, files[0]) if files else None


def load_pipe():
    global _pipe
    if _pipe is not None:
        return _pipe
    import torch
    from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler

    ckpt = find_checkpoint()
    if not ckpt:
        raise RuntimeError(f"no checkpoint in {MODELS} (drop any .safetensors there)")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    _status.update(state="loading", model=os.path.basename(ckpt), device=device)
    print(f"[sd] loading {os.path.basename(ckpt)} on {device} ...", flush=True)

    pipe = StableDiffusionPipeline.from_single_file(
        ckpt,
        torch_dtype=dtype,
        safety_checker=None,          # ⛔ see the module docstring — deliberate
        requires_safety_checker=False,
        load_safety_checker=False,
    )
    # ⛔ THE CONSTRUCTOR ARGUMENT IS NOT ENOUGH — MEASURED, NOT ASSUMED.
    # With `safety_checker=None` passed above, `from_single_file` STILL loaded a
    # checker from the checkpoint's own config, and the first real render came
    # back as a 1,509-byte all-black PNG with
    #   "Potential NSFW content was detected ... A black image will be returned"
    # printed to stderr — her picture silently replaced by a black rectangle.
    # That is both the censorship this project refuses and the hidden-failure
    # class its LAWs ban, in one. So the checker is removed from the built
    # pipeline, and the method that invokes it is neutralised as well, because
    # some diffusers versions call it through the pipeline rather than the
    # attribute. Belt and braces, deliberately.
    pipe.safety_checker = None
    pipe.feature_extractor = None
    pipe.requires_safety_checker = False
    pipe.run_safety_checker = lambda image, device=None, dtype=None: (image, None)
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
    pipe = pipe.to(device)
    pipe.set_progress_bar_config(disable=True)
    if device == "cuda":
        pipe.enable_attention_slicing()      # comfortable headroom on 16 GB
    _pipe = pipe
    _status.update(state="ready")
    print(f"[sd] ready on {device} — http://127.0.0.1:{PORT}", flush=True)
    return _pipe


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass                                   # quiet; real events print themselves

    def _send(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/sdapi/v1/options"):
            # The probe server.mjs uses to decide "is a local backend alive".
            return self._send(200, {"sd_model_checkpoint": _status.get("model"), "unity_status": _status})
        if self.path.startswith("/status"):
            return self._send(200, _status)
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/sdapi/v1/txt2img"):
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._send(400, {"error": f"bad json: {e}"})

        prompt = (req.get("prompt") or "").strip()
        if not prompt:
            return self._send(400, {"error": "empty prompt"})

        # Quality steering only — nothing here steers subject matter.
        negative = req.get("negative_prompt") or (
            "blurry, lowres, bad anatomy, bad hands, extra fingers, deformed, "
            "watermark, text, jpeg artifacts, worst quality"
        )
        steps = int(req.get("steps") or 26)
        width = int(req.get("width") or 640)
        height = int(req.get("height") or 768)
        cfg = float(req.get("cfg_scale") or 7.0)

        try:
            pipe = load_pipe()
            with _lock:
                out = pipe(
                    prompt=prompt[:1500],
                    negative_prompt=negative,
                    num_inference_steps=steps,
                    guidance_scale=cfg,
                    width=width - (width % 8),
                    height=height - (height % 8),
                )
            img = out.images[0]
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            print(f"[sd] rendered {width}x{height} · {steps} steps · {prompt[:70]}", flush=True)
            return self._send(200, {"images": [b64], "info": "{}"})
        except Exception as e:
            _status["error"] = str(e)
            traceback.print_exc()
            return self._send(500, {"error": str(e)})


if __name__ == "__main__":
    ck = find_checkpoint()
    print(f"""
  UNITY — local image generation
  ---------------------------------------------------
  port      127.0.0.1:{PORT}   (A1111-compatible API)
  models    {MODELS}
  checkpoint{'':<1}{os.path.basename(ck) if ck else 'NONE — drop a .safetensors in models/'}
  safety    DISABLED (uncensored, by design)
  ---------------------------------------------------
""", flush=True)
    if ck:
        # Load at boot in the background so the first picture is not the slow one.
        threading.Thread(target=lambda: (load_pipe(), None), daemon=True).start()
    else:
        _status.update(state="no-checkpoint")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
