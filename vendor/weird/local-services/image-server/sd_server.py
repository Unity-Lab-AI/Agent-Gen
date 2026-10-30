"""
sd_server.py — local uncensored image generation for the weird project.

Speaks the AUTOMATIC1111 API shape (`/sdapi/v1/options`, `/sdapi/v1/txt2img`) on
127.0.0.1:7860. The browser calls it DIRECTLY — no Node router in front — so
every response carries permissive CORS headers, and OPTIONS preflight is
answered locally. This matches the same "run-a-thing-on-localhost-and-let-the-
browser-hit-it" pattern the project already uses for Ollama (via
OLLAMA_ORIGINS=*) and Kokoro (in-browser).

⛔ NO SAFETY CHECKER. `safety_checker=None` is deliberate and load-bearing: the
default diffusers pipeline silently returns BLACK IMAGES for anything its NSFW
classifier dislikes, which for this project would mean her pictures vanishing
with no error anywhere. Uncensored is the requirement, and a silent black frame
is also exactly the kind of hidden failure this project's LAWs ban.

Everything stays on this machine. The model is a local file; nothing is fetched
at render time. Bind is loopback-only (127.0.0.1) — the browser reaches it as
same-host, and no other machine on the LAN can.
"""

import base64
import io
import json
import os
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
# models/ lives at the project root — the same tree the browser is served from,
# so a visitor drops a .safetensors into local-services/../../models and the
# next render picks it up.
ROOT = os.path.dirname(os.path.dirname(HERE))
MODELS = os.path.join(ROOT, "models")
PORT = int(os.environ.get("SD_PORT", "7860"))

_pipe = None
_lock = threading.Lock()          # one render at a time; a single GPU does not need a queue
_status = {"state": "starting", "model": None, "device": None, "error": None}


def find_checkpoint():
    """Any .safetensors/.ckpt in models/. Prefers SDXL files (filename contains
    'xl' case-insensitive) because SDXL renders coherently at 832-1024+ where
    SD1.5 hallucinates duplicate subjects. Falls back to the first-by-name if
    no SDXL file is present, so an SD1.5 drop still works."""
    if not os.path.isdir(MODELS):
        return None
    files = sorted(f for f in os.listdir(MODELS) if f.endswith((".safetensors", ".ckpt")))
    if not files:
        return None
    xl = [f for f in files if "xl" in f.lower()]
    return os.path.join(MODELS, (xl[0] if xl else files[0]))


def is_sdxl_checkpoint(path):
    """Cheap arch detection by filename — SDXL model files carry 'xl' in the
    name (RealVisXL, SDXL-Base, JuggernautXL, etc.). Avoids the ~2s cost of
    loading state-dict shapes just to sniff the arch."""
    return "xl" in os.path.basename(path).lower()


def load_pipe():
    global _pipe
    if _pipe is not None:
        return _pipe
    import torch
    from diffusers import DPMSolverMultistepScheduler

    ckpt = find_checkpoint()
    if not ckpt:
        raise RuntimeError(f"no checkpoint in {MODELS} (drop any .safetensors there)")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    sdxl = is_sdxl_checkpoint(ckpt)
    arch_label = "SDXL" if sdxl else "SD1.5"
    _status.update(state="loading", model=os.path.basename(ckpt), device=device, arch=arch_label.lower())
    print(f"[sd] loading {os.path.basename(ckpt)} on {device} as {arch_label} ...", flush=True)

    if sdxl:
        # SDXL renders coherently at 832-1216 portrait / 1024x1024 square where
        # SD1.5 tiles duplicate subjects. No safety_checker in SDXL's pipeline
        # class — the SD1.5-only kwargs would trigger unexpected-kwarg errors.
        from diffusers import StableDiffusionXLPipeline
        pipe = StableDiffusionXLPipeline.from_single_file(
            ckpt,
            torch_dtype=dtype,
            add_watermarker=False,          # no invisible watermark on outputs
        )
    else:
        from diffusers import StableDiffusionPipeline
        pipe = StableDiffusionPipeline.from_single_file(
            ckpt,
            torch_dtype=dtype,
            safety_checker=None,            # ⛔ see the module docstring — deliberate
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
    # attribute. Belt and braces, deliberately. Applied to BOTH arches — SDXL
    # doesn't ship a checker today but future variants might.
    pipe.safety_checker = None
    pipe.feature_extractor = None
    pipe.requires_safety_checker = False
    pipe.run_safety_checker = lambda image, device=None, dtype=None: (image, None)
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)

    if device == "cuda":
        if sdxl:
            # SDXL fp16 is ~7GB. Alongside Ollama's typical ~10GB dolphin-mistral
            # residency on a 16GB card, VRAM is tight. model_cpu_offload swaps
            # UNet / text-encoder stages between CPU and GPU as needed — a bit
            # slower per render but fits without OOM even when Ollama has its
            # model warm. `to(device)` is implicit inside offload, don't double it.
            pipe.enable_model_cpu_offload()
        else:
            pipe = pipe.to(device)
        pipe.enable_attention_slicing()     # comfortable headroom on modest GPUs
    else:
        pipe = pipe.to(device)
    pipe.set_progress_bar_config(disable=True)
    _pipe = pipe
    _status.update(state="ready")
    print(f"[sd] ready on {device} — http://127.0.0.1:{PORT}", flush=True)
    return _pipe


# CORS headers written on every response so a page served from GitHub Pages
# (or any origin — the browser is the boundary here, not this loopback socket)
# can call this local server directly. Matches the OLLAMA_ORIGINS=* pattern
# the launcher already sets for Ollama.
CORS = [
    ("Access-Control-Allow-Origin", "*"),
    ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
    ("Access-Control-Allow-Headers", "Content-Type"),
    ("Access-Control-Max-Age", "86400"),
]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass                                   # quiet; real events print themselves

    def _cors(self):
        for k, v in CORS:
            self.send_header(k, v)

    def _send(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        # Preflight for the POST /sdapi/v1/txt2img call. Same-origin GETs never
        # trigger this, but a cross-origin fetch with a JSON body always does.
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/sdapi/v1/options"):
            # The probe the browser (or a Node router) uses to decide
            # "is a local backend alive". Returned in the shape A1111 uses.
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
        # Facial persistence is the project's #1 image-pipeline invariant: the same girl must
        # render with the same face across every image of her. A1111 clients pass an integer
        # `seed`; we hand it to a torch.Generator on the pipeline's device so identical
        # (prompt, seed, size, steps) inputs reproduce. -1 / missing → non-deterministic.
        seed = req.get("seed")
        try:
            seed_int = int(seed) if seed is not None else -1
        except Exception:
            seed_int = -1

        try:
            pipe = load_pipe()
            import torch
            generator = None
            if seed_int >= 0:
                device_for_gen = "cuda" if torch.cuda.is_available() else "cpu"
                generator = torch.Generator(device=device_for_gen).manual_seed(seed_int & 0x7FFFFFFF)
            with _lock:
                out = pipe(
                    prompt=prompt[:1500],
                    negative_prompt=negative,
                    num_inference_steps=steps,
                    guidance_scale=cfg,
                    width=width - (width % 8),
                    height=height - (height % 8),
                    generator=generator,
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
  LOCAL IMAGE GENERATION
  ---------------------------------------------------
  port      127.0.0.1:{PORT}   (A1111-compatible API)
  models    {MODELS}
  checkpoint{'':<1}{os.path.basename(ck) if ck else 'NONE - drop a .safetensors into models/'}
  safety    DISABLED (uncensored, by design)
  CORS      * (browser-direct from any origin)
  ---------------------------------------------------
""", flush=True)
    if ck:
        # Load at boot in the background so the first picture is not the slow one.
        threading.Thread(target=lambda: (load_pipe(), None), daemon=True).start()
    else:
        _status.update(state="no-checkpoint")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
