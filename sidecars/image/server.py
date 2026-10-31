#!/usr/bin/env python3
"""
C.O.R.A image engine sidecar: local Stable Diffusion, the same rig Unity's
stream renders with (the realistic-vision-v51 checkpoint through diffusers,
DPM++ sampling, img2img, inpainting, and the IP-Adapter face lock so a person
in a source photo stays themselves).

Why a sidecar: CORA's own venv is Python 3.13 without torch. The engine runs
on the interpreter that carries torch + diffusers (the voice sidecar's one),
found by cora_tools/image_gen.py, and talks plain HTTP on 127.0.0.1. Nothing
leaves the machine; there is no hosted image API and no key anywhere.

    python services/image_sidecar.py --port 5124 --checkpoint <file> --device auto

API (every POST takes JSON, every image comes back as image/png with headers
X-Seed, X-Seconds and X-Size):
  GET  /health   -> {"ok": true, "loaded": bool, "device", "checkpoint", "face_adapter"}
  POST /txt2img  {"prompt", "negative"?, "width"?, "height"?, "steps"?, "guidance"?, "seed"?,
                  "face"?: base64 image, "face_scale"?}
  POST /img2img  {"prompt", "image": base64, "strength"? (0.2-0.95), "negative"?, "steps"?,
                  "guidance"?, "seed"?, "max_side"?, "face"?: base64 | true, "face_scale"?}
  POST /inpaint  {"prompt", "image": base64, "mask"?: base64 (white = repaint) |
                  "box"?: [x0, y0, x1, y1] as fractions of the image, "strength"?, ...}
  POST /unload   -> drops the pipelines and frees the GPU (the process stays)
  POST /shutdown -> exits the process

The checkpoint loads on the first render (not at start), so /health answers
at once and the GPU is only taken when a picture is actually asked for.
"""
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

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# the installed location (the app's data root) or the repo's models/; scripts/fetch-models.py puts it there
DEFAULT_CKPT = next((p for p in (
    os.path.join(os.environ.get("AGENTGEN_MODELS") or os.path.join(_REPO, "models"), "sd", "realistic-vision-v51.safetensors"),
    os.path.join(_REPO, "models", "sd", "realistic-vision-v51.safetensors")) if os.path.exists(p)),
    os.path.join(_REPO, "models", "sd", "realistic-vision-v51.safetensors"))
FACE_REPO, FACE_SUBFOLDER, FACE_WEIGHTS = "h94/IP-Adapter", "models", "ip-adapter-plus-face_sd15.safetensors"

# no default negative: the caller sends what it needs (the hub sends only the adult-age terms)
NEG = ""

CKPT = DEFAULT_CKPT
DEVICE_ARG = "auto"
OFFLOAD = True

_lock = threading.Lock()
_state = {"t2i": None, "i2i": None, "inpaint": None, "device": None, "face": False, "loaded_at": 0.0}


# --------------------------------------------------------------------------- helpers
def _log(msg):
    print(time.strftime("%H:%M:%S"), "image:", msg, flush=True)


def _device():
    if _state["device"]:
        return _state["device"]
    import torch
    dev = DEVICE_ARG
    if dev == "auto":
        dev = "cuda" if torch.cuda.is_available() else "cpu"
    _state["device"] = dev
    return dev


def _round8(n, lo=256, hi=1024):
    n = int(n)
    n = max(lo, min(hi, n))
    return n - (n % 8)


def _fit(img, max_side):
    """Resize keeping aspect so the long side is max_side, both sides multiples of 8."""
    w, h = img.size
    scale = float(max_side) / float(max(w, h))
    nw, nh = _round8(w * scale), _round8(h * scale)
    return img.resize((nw, nh)) if (nw, nh) != (w, h) else img


def _b64_image(s):
    from PIL import Image
    raw = base64.b64decode(s.split(",", 1)[1] if isinstance(s, str) and s.startswith("data:") else s)
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _png(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _dummy_face():
    from PIL import Image
    return Image.new("RGB", (224, 224), (127, 127, 127))


# --------------------------------------------------------------------------- pipelines
def _load():
    if _state["t2i"] is not None:
        return
    import torch
    from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler
    if not os.path.exists(CKPT):
        raise FileNotFoundError("checkpoint not found: %s" % CKPT)
    dev = _device()
    t0 = time.time()
    _log("loading %s on %s%s" % (os.path.basename(CKPT), dev, " (cpu offload)" if dev == "cuda" and OFFLOAD else ""))
    dtype = torch.float16 if dev == "cuda" else torch.float32
    t2i = StableDiffusionPipeline.from_single_file(CKPT, torch_dtype=dtype, safety_checker=None)
    t2i.scheduler = DPMSolverMultistepScheduler.from_config(t2i.scheduler.config)
    if dev == "cuda":
        # the pipeline lives in system RAM and only the layer being executed rides the GPU:
        # her brain and her voice keep their room on the card (the stream runs the same way)
        if OFFLOAD:
            t2i.enable_model_cpu_offload()
        else:
            t2i.to("cuda")
    else:
        t2i.to("cpu")
    _state["t2i"] = t2i
    _state["face"] = False
    _rebuild_siblings()
    _state["loaded_at"] = time.time()
    _log("loaded in %.1fs" % (time.time() - t0))


def _rebuild_siblings():
    from diffusers import StableDiffusionImg2ImgPipeline, StableDiffusionInpaintPipeline
    comps = _state["t2i"].components
    _state["i2i"] = StableDiffusionImg2ImgPipeline(**comps)
    _state["inpaint"] = StableDiffusionInpaintPipeline(**comps)


def _load_face():
    """IP-Adapter Plus Face: the person in the reference image stays themselves while the
    picture changes around them. Loaded on the first request that asks for it."""
    if _state["face"]:
        return
    _load()
    t2i = _state["t2i"]
    t0 = time.time()
    _log("loading the face adapter")
    t2i.load_ip_adapter(FACE_REPO, subfolder=FACE_SUBFOLDER, weight_name=FACE_WEIGHTS)
    if getattr(t2i, "feature_extractor", None) is None:
        from transformers import CLIPImageProcessor
        t2i.feature_extractor = CLIPImageProcessor()
    if _device() == "cuda" and OFFLOAD:
        t2i.enable_model_cpu_offload()   # again: the adapter's image encoder came after the first set-up
    _state["face"] = True
    _rebuild_siblings()                  # the siblings must share the adapter-bearing unet and encoder
    _log("face adapter ready in %.1fs" % (time.time() - t0))


def _face_kwargs(req, source_img=None):
    """ip_adapter kwargs for this request. Once the adapter is loaded every call must carry an
    image, so a request without a face sends a grey square at scale 0."""
    face = req.get("face")
    scale = float(req.get("face_scale") or 0.6)
    if face:
        _load_face()
        img = source_img if face is True and source_img is not None else _b64_image(face)
        for p in ("t2i", "i2i", "inpaint"):
            _state[p].set_ip_adapter_scale(scale)
        return {"ip_adapter_image": img.resize((224, 224))}
    if _state["face"]:
        for p in ("t2i", "i2i", "inpaint"):
            _state[p].set_ip_adapter_scale(0.0)
        return {"ip_adapter_image": _dummy_face()}
    return {}


def _common(req):
    import torch
    dev = _device()
    steps = int(req.get("steps") or (25 if dev == "cuda" else 12))
    steps = max(4, min(60, steps))
    seed = req.get("seed")
    seed = int(seed) if seed not in (None, "", 0) else random.randint(1, 2 ** 31 - 1)
    gen = torch.Generator(dev).manual_seed(seed)
    guidance = float(req.get("guidance") or 6.5)
    negative = str(req.get("negative") or NEG)
    return steps, seed, gen, guidance, negative


def _tokens_fit(text, limit=75):
    """CLIP reads 77 tokens and drops the rest without a word; cut by the real tokenizer."""
    try:
        tok = _state["t2i"].tokenizer
        ids = tok(text).input_ids
        if len(ids) <= limit + 2:
            return text
        return tok.decode(ids[1:limit + 1]).strip()
    except Exception:
        words = text.split()
        return " ".join(words[:55]) if len(words) > 55 else text


def render_txt2img(req):
    import torch
    _load()
    dev = _device()
    big = dev == "cuda"
    w = _round8(req.get("width") or (768 if big else 512))
    h = _round8(req.get("height") or (768 if big else 512))
    steps, seed, gen, guidance, negative = _common(req)
    extra = _face_kwargs(req)
    t0 = time.time()
    if dev == "cuda":
        torch.cuda.empty_cache()
    out = _state["t2i"](prompt=_tokens_fit(str(req.get("prompt") or "")), negative_prompt=_tokens_fit(negative),
                        width=w, height=h, num_inference_steps=steps, guidance_scale=guidance,
                        generator=gen, **extra).images[0]
    return out, seed, time.time() - t0


def render_img2img(req):
    import torch
    _load()
    dev = _device()
    src = _b64_image(req["image"])
    src = _fit(src, int(req.get("max_side") or (768 if dev == "cuda" else 512)))
    strength = float(req.get("strength") or 0.55)
    strength = max(0.15, min(0.95, strength))
    steps, seed, gen, guidance, negative = _common(req)
    extra = _face_kwargs(req, src)
    t0 = time.time()
    if dev == "cuda":
        torch.cuda.empty_cache()
    out = _state["i2i"](prompt=_tokens_fit(str(req.get("prompt") or "")), negative_prompt=_tokens_fit(negative),
                        image=src, strength=strength, num_inference_steps=steps, guidance_scale=guidance,
                        generator=gen, **extra).images[0]
    return out, seed, time.time() - t0


def _mask_for(req, size):
    from PIL import Image, ImageDraw, ImageFilter
    w, h = size
    if req.get("mask"):
        m = _b64_image(req["mask"]).convert("L").resize((w, h))
        return m
    box = req.get("box")
    if box == "body":
        box = _body_box(req, size)
    if not box or len(box) != 4:
        raise ValueError("inpaint needs a mask (base64, white = repaint) or a box [x0, y0, x1, y1] in fractions")
    x0, y0, x1, y1 = [max(0.0, min(1.0, float(v))) for v in box]
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rectangle((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)), fill=255)
    return m.filter(ImageFilter.GaussianBlur(6))


def _body_box(req, size):
    """Everything below her chin, so an outfit or skin edit never touches her face, hair or the room above it.
    Finds the biggest face with OpenCV; without one, the top 30 % is kept."""
    try:
        import cv2
        import numpy as np
        img = _fit(_b64_image(req["image"]), max(size)).convert("L")
        g = np.array(img)
        det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = det.detectMultiScale(g, scaleFactor=1.1, minNeighbors=5, minSize=(g.shape[1] // 12, g.shape[1] // 12))
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            chin = (y + h * 1.12) / g.shape[0]
            return [0.0, min(0.9, chin), 1.0, 1.0]
    except Exception as e:
        _log(f"body box: {e}")
    return [0.0, 0.3, 1.0, 1.0]


def render_inpaint(req):
    import torch
    _load()
    dev = _device()
    src = _b64_image(req["image"])
    src = _fit(src, int(req.get("max_side") or (768 if dev == "cuda" else 512)))
    mask = _mask_for(req, src.size)
    strength = float(req.get("strength") or 0.9)
    strength = max(0.2, min(1.0, strength))
    steps, seed, gen, guidance, negative = _common(req)
    extra = _face_kwargs(req, src)
    t0 = time.time()
    if dev == "cuda":
        torch.cuda.empty_cache()
    out = _state["inpaint"](prompt=_tokens_fit(str(req.get("prompt") or "")), negative_prompt=_tokens_fit(negative),
                            image=src, mask_image=mask, width=src.size[0], height=src.size[1], strength=strength,
                            num_inference_steps=steps, guidance_scale=guidance, generator=gen, **extra).images[0]
    return out, seed, time.time() - t0


# --------------------------------------------------------------------------- marker on skin
# The model cannot spell or put a mark where it is told, so the ink is drawn (a handwriting font or strokes),
# as a multiply over her skin with grain, so her light and shading show through. No model pass by default: every
# blend strength either respelled the words or, with the ink laid back on, ghosted them.
INK = {"black": (18, 16, 20), "red": (150, 18, 24), "pink": (205, 40, 120), "blue": (20, 40, 140),
       "purple": (90, 30, 120), "green": (20, 100, 40), "white": (235, 235, 235), "lipstick": (172, 22, 58)}
FONT = os.path.join(os.environ.get("WINDIR", "C:\Windows"), "Fonts", "Inkfree.ttf")


def _stroke(th, item):
    """Letter line weight, varied per request. Lipstick tops out at 1/12 of the letter height: 1/9 made "MINE"
    hard to read."""
    if item.get("tool") == "lipstick":
        return max(1, int(th / random.uniform(12, 16)))
    return max(1, int(th / random.uniform(20, 30)))


def _mark_layer(size, item, fh):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    w, h = size
    cx, cy = item["x"] * w, item["y"] * h
    lay = Image.new("L", size, 0)
    shape = item.get("shape")
    angle = float(item.get("angle", 0))
    if item.get("text"):
        text = str(item["text"])[:24]
        th = max(14, int(fh * (0.42 if len(text) <= 5 else 0.3)))
        try:
            f = ImageFont.truetype(FONT, th)
        except Exception:
            f = ImageFont.load_default()
        tmp = Image.new("L", (int(th * (len(text) + 2) * 1.1), int(th * 2)), 0)
        ImageDraw.Draw(tmp).text((th // 2, 0), text, font=f, fill=255, stroke_width=_stroke(th, item), stroke_fill=255)
        tmp = tmp.crop(tmp.getbbox()).rotate(angle, expand=True, resample=Image.BICUBIC)
        lay.paste(tmp, (int(cx - tmp.width / 2), int(cy - tmp.height / 2)), tmp)
        return lay.filter(ImageFilter.GaussianBlur(0.8))
    d = ImageDraw.Draw(lay)
    lip = item.get("tool") == "lipstick"
    sw = max(3, int(fh * random.uniform(0.05, 0.075) if lip else fh * random.uniform(0.045, 0.065)))
    L = fh * 0.5
    if shape == "arrow":
        top, bot = (cx, cy - L), (cx - 2, cy + L)
        d.line([top, bot], fill=255, width=sw, joint="curve")
        for sgn in (-1, 1):
            d.line([bot, (bot[0] + sgn * L * 0.32, bot[1] - L * 0.45)], fill=255, width=sw)
    elif shape == "heart":
        import math
        pts = [(cx + L * 0.55 * 16 * math.sin(t) ** 3 / 16, cy - L * 0.55 * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 16)
               for t in [i * 2 * math.pi / 60 for i in range(61)]]
        d.line(pts, fill=255, width=sw, joint="curve")
    elif shape == "x":
        r = L * 0.45
        d.line([(cx - r, cy - r), (cx + r, cy + r)], fill=255, width=sw)
        d.line([(cx + r, cy - r), (cx - r, cy + r)], fill=255, width=sw)
    elif shape == "star":
        import math
        pts = [(cx + L * 0.5 * math.sin(i * 4 * math.pi / 5), cy - L * 0.5 * math.cos(i * 4 * math.pi / 5)) for i in range(6)]
        d.line(pts, fill=255, width=sw, joint="curve")
    elif shape == "smiley":
        r = L * 0.5
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=255, width=sw)
        d.arc((cx - r * 0.55, cy - r * 0.5, cx + r * 0.55, cy + r * 0.55), 20, 160, fill=255, width=sw)
        for sgn in (-1, 1):
            d.ellipse((cx + sgn * r * 0.35 - sw, cy - r * 0.3 - sw, cx + sgn * r * 0.35 + sw, cy - r * 0.3 + sw), fill=255)
    elif shape == "tally":
        for i in range(4):
            x = cx - L * 0.4 + i * L * 0.22
            d.line([(x, cy - L * 0.4), (x + 2, cy + L * 0.4)], fill=255, width=sw)
        d.line([(cx - L * 0.55, cy + L * 0.3), (cx + L * 0.45, cy - L * 0.3)], fill=255, width=sw)
    return lay.filter(ImageFilter.GaussianBlur(1.2))


def _ink(img, lay, color, opacity=0.88):
    """Ink as a multiply over her skin: the skin's light, shadow and sheen show through it like real marker or
    lipstick, and a little grain breaks the edges so it is not a flat decal."""
    import numpy as np
    from PIL import Image
    base = np.asarray(img).astype(np.float32) / 255.0
    a = np.asarray(lay).astype(np.float32)[..., None] / 255.0
    rng = np.random.default_rng(len(color) * 7919 + int(a.sum()) % 9973)
    grain = 0.82 + 0.18 * rng.random(a.shape[:2])[..., None]
    a = np.clip(a * grain * opacity, 0, 1)
    tint = np.array(color, dtype=np.float32) / 255.0
    lum = base.mean(axis=2, keepdims=True)
    inked = base * tint * 0.55 + tint * lum * 0.45   # multiply, with some of the skin's brightness carried through
    out = base * (1 - a) + inked * a
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def render_mark(req):
    """POST /mark {"image", "items": [{"text"|"shape", "x", "y" (fractions), "angle"?, "color"?}], "face_h" (fraction)}"""
    from PIL import Image, ImageDraw, ImageFilter
    src = _fit(_b64_image(req["image"]), int(req.get("max_side") or 768)).convert("RGB")
    fh = float(req.get("face_h") or 0.18) * src.size[1]
    t0 = time.time()
    out, words = src, False
    layers = []
    for it in req.get("items") or []:
        lay = _mark_layer(src.size, it, fh)
        if not lay.getbbox():
            continue
        color = INK.get(str(it.get("color") or "black").lower(), INK["black"])
        out = _ink(out, lay, color, opacity=0.8 if it.get("tool") == "lipstick" else 0.88)
        layers.append((lay, color))
        words = words or bool(it.get("text"))
    if not layers:
        raise ValueError("nothing to draw")
    if not req.get("blend"):   # ink only (the default): a model blend respelled every word ("Shit" -> "Surit")
        return out, 0, time.time() - t0
    mask = Image.new("L", src.size, 0)
    for lay, _ in layers:
        b = lay.getbbox()
        ImageDraw.Draw(mask).rectangle((b[0] - 24, b[1] - 24, b[2] + 24, b[3] + 24), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(10))
    _load()
    steps, seed, gen, guidance, negative = _common({**req, "guidance": req.get("guidance") or 6})
    tool = "lipstick" if any(it.get("tool") == "lipstick" for it in req.get("items") or []) else "marker"
    prompt = "photo, %s drawn on her skin in %s, skin texture, natural light" % ("handwriting" if words else "a drawing", tool)
    blended = _state["inpaint"](prompt=prompt, negative_prompt=_tokens_fit(negative), image=out, mask_image=mask,
                                width=out.size[0], height=out.size[1], strength=0.3,
                                num_inference_steps=steps, guidance_scale=guidance, generator=gen,
                                **_face_kwargs({}, out)).images[0]
    blended = blended.convert("RGB").resize(src.size)
    # the blend gives it skin texture and light but respells words and melts thin lines; the exact strokes go back
    # on as a multiply over the blended skin, so the letters read and still sit in the skin
    for lay, color in layers:
        blended = _ink(blended, lay, color, opacity=0.75)
    return blended, seed, time.time() - t0


def unload():
    had = _state["t2i"] is not None
    for k in ("t2i", "i2i", "inpaint"):
        _state[k] = None
    _state["face"] = False
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    if had:
        _log("unloaded")
    return had


# --------------------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "CORA-image/1.0"

    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            return self._json({"ok": True, "loaded": _state["t2i"] is not None, "device": _state["device"] or DEVICE_ARG,
                               "checkpoint": os.path.basename(CKPT), "checkpoint_present": os.path.exists(CKPT),
                               "face_adapter": _state["face"], "busy": _lock.locked()})
        self._json({"error": "unknown endpoint"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception as e:
            return self._json({"error": "bad json: %s" % e}, 400)
        if path == "/unload":
            with _lock:
                return self._json({"ok": True, "unloaded": unload()})
        if path == "/shutdown":
            self._json({"ok": True})
            threading.Timer(0.3, lambda: os._exit(0)).start()
            return
        fn = {"/txt2img": render_txt2img, "/img2img": render_img2img, "/inpaint": render_inpaint, "/mark": render_mark}.get(path)
        if fn is None:
            return self._json({"error": "unknown endpoint"}, 404)
        if not str(req.get("prompt") or "").strip() and path == "/txt2img":
            return self._json({"error": "prompt is empty"}, 422)
        try:
            with _lock:
                img, seed, secs = fn(req)
        except FileNotFoundError as e:
            return self._json({"error": str(e)}, 503)
        except (KeyError, ValueError) as e:
            return self._json({"error": str(e)}, 422)
        except Exception as e:
            _log("render failed: %r" % (e,))
            return self._json({"error": "%s: %s" % (type(e).__name__, str(e)[:300])}, 500)
        body = _png(img)
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Seed", str(seed))
        self.send_header("X-Seconds", "%.2f" % secs)
        self.send_header("X-Size", "%dx%d" % img.size)
        self.end_headers()
        self.wfile.write(body)
        _log("%s %dx%d seed %d in %.1fs" % (path[1:], img.size[0], img.size[1], seed, secs))


def main():
    global CKPT, DEVICE_ARG, OFFLOAD
    ap = argparse.ArgumentParser(description="CORA image engine sidecar")
    ap.add_argument("--port", type=int, default=int(os.environ.get("CORA_IMAGE_PORT", "5124")))
    ap.add_argument("--checkpoint", default=os.environ.get("CORA_IMAGE_CHECKPOINT", DEFAULT_CKPT))
    ap.add_argument("--device", default=os.environ.get("CORA_IMAGE_DEVICE", "auto"), choices=["auto", "cuda", "cpu"])
    ap.add_argument("--no-offload", action="store_true", help="keep the whole model on the GPU (faster, ~3 GB more VRAM)")
    ap.add_argument("--preload", action="store_true", help="load the checkpoint at start instead of on the first render")
    a = ap.parse_args()
    CKPT, DEVICE_ARG, OFFLOAD = a.checkpoint, a.device, not a.no_offload
    if a.preload:
        _load()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    _log("serving on 127.0.0.1:%d  checkpoint=%s  present=%s" % (a.port, os.path.basename(CKPT), os.path.exists(CKPT)))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
