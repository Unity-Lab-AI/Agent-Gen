#!/usr/bin/env python3
"""
C.O.R.A image generation: her own local image engine.

The engine is services/image_sidecar.py, the same Stable Diffusion rig Unity's
stream renders with (realistic-vision-v51 through diffusers: text to image,
img2img edits, inpainting, and a face lock so the person in a camera shot stays
themselves). It runs as a sidecar on the interpreter that has torch + diffusers
(the voice sidecar's one) and answers on 127.0.0.1. Nothing is sent anywhere,
there is no hosted image API and no key.

Kept names (every caller in the project uses these):
    generate_image(prompt, width=, height=, seed=, output_path=) -> dict
    generate_boot_image(prompt=None) -> dict
    show_fullscreen_image(path, duration=None) -> bool     (opens the viewer window)
    get_recent_images(limit) -> [paths]

New:
    edit_image(source, prompt, strength=, box=, keep_face=)   source: path | "last" | "camera"
    recreate_camera(prompt, strength=, keep_face=True)       a webcam shot, recreated
    save_image(destination, source="last") -> dict           copy an image where the user wants it
    show_image(path, caption=None)                           the viewer: Save As, Open folder, Copy path
    last_image() -> path | None
    ensure_sidecar() / sidecar_health() / release() / release_gpu() / stop_sidecar()

Configuration: config.json "image" block (url, checkpoint, python, device,
autostart, steps, width, height, save_dir); env CORA_IMAGE_URL,
CORA_IMAGE_PYTHON, CORA_IMAGE_CHECKPOINT, CORA_IMAGE_DEVICE override it.
"""

import base64
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests

PROJECT_DIR = Path(__file__).resolve().parent.parent
SIDECAR = PROJECT_DIR / 'services' / 'image_sidecar.py'
SIDECAR_LOG = PROJECT_DIR / 'data' / 'image-sidecar.log'
PYTHON_CACHE = PROJECT_DIR / 'data' / '.image_python'
RUN_DIR = PROJECT_DIR / 'data' / 'run'
PID_FILE = RUN_DIR / 'image-sidecar.pid'
LAST_FILE = RUN_DIR / 'last_image.txt'
DEFAULT_CKPT = os.path.expanduser(r"~\Desktop\Unity 3D Equational Model\Unity 18+\models\realistic-vision-v51.safetensors")
ENGINE_NAME = 'realistic-vision-v51 (local Stable Diffusion)'


# --------------------------------------------------------------------------- config
def _cfg() -> Dict[str, Any]:
    try:
        with open(PROJECT_DIR / 'config' / 'config.json', 'r', encoding='utf-8') as f:
            return json.load(f).get('image') or {}
    except Exception:
        return {}


def image_url() -> str:
    return (os.environ.get('CORA_IMAGE_URL') or _cfg().get('url') or 'http://127.0.0.1:5124').rstrip('/')


def checkpoint_path() -> Path:
    return Path(os.environ.get('CORA_IMAGE_CHECKPOINT') or _cfg().get('checkpoint') or DEFAULT_CKPT)


def images_dir() -> Path:
    d = _cfg().get('save_dir') or 'data/images'
    p = Path(d)
    return p if p.is_absolute() else PROJECT_DIR / p


IMAGES_DIR = images_dir()


def _default_size() -> tuple:
    c = _cfg()
    try:
        return int(c.get('width') or 768), int(c.get('height') or 768)
    except (TypeError, ValueError):
        return 768, 768


DEFAULT_SELFIE_LOOK = "candid phone selfie of one white American woman alone, 25 years old, youthful face, caucasian, european features, girl next door with a soft emo goth style, fair skin with a warm healthy glow, grey-green eyes, black hair with bright pink streaks and bangs, winged eyeliner, dark plum lipstick, black choker, black band t-shirt, small natural smile, cozy bedroom, warm lamp light, realistic photo"
DEFAULT_SELFIE_NEGATIVE = "two people, two women, couple, group, second person, tan skin, dark skin, asian, latina, pale white skin, ghostly, black lipstick, heavy club makeup, neon lights, leather jacket, latex, tattoos, airbrushed, plastic skin, doll, cgi, render, anime, cartoon, oversaturated, blurry, lowres, deformed, bad anatomy, extra fingers, watermark, text, old, wrinkles, middle aged, child, teen"


def selfie_defaults() -> tuple:
    """(look, negative) for a picture of herself: config image.selfie_look / image.selfie_negative."""
    c = _cfg()
    return (str(c.get('selfie_look') or DEFAULT_SELFIE_LOOK), str(c.get('selfie_negative') or DEFAULT_SELFIE_NEGATIVE))


def _steps() -> Optional[int]:
    try:
        return int(_cfg().get('steps')) if _cfg().get('steps') else None
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- sidecar
def is_up(timeout: float = 2.0) -> bool:
    try:
        return requests.get(f"{image_url()}/health", timeout=timeout).status_code == 200
    except Exception:
        return False


def sidecar_health() -> Dict[str, Any]:
    try:
        r = requests.get(f"{image_url()}/health", timeout=2)
        d = r.json() if r.ok else {}
        d.setdefault('ok', r.ok)
        d['url'] = image_url()
        return d
    except Exception as e:
        return {'ok': False, 'url': image_url(), 'error': str(e)[:120]}


def _validate_python(exe: str) -> bool:
    try:
        r = subprocess.run([exe, '-c', 'import torch, diffusers, transformers, accelerate, PIL'],
                           capture_output=True, text=True, timeout=180)
        return r.returncode == 0
    except Exception:
        return False


def find_sidecar_python() -> Optional[str]:
    """Interpreter that can import torch + diffusers. Cached in data/.image_python."""
    cands: List[str] = [c for c in (os.environ.get('CORA_IMAGE_PYTHON'), _cfg().get('python')) if c]
    try:
        if PYTHON_CACHE.exists():
            cached = PYTHON_CACHE.read_text(encoding='utf-8').strip()
            if cached and Path(cached).exists():
                return cached
    except Exception:
        pass
    try:   # the voice sidecar's interpreter carries torch already
        vp = (PROJECT_DIR / 'data' / '.voice_python').read_text(encoding='utf-8').strip()
        if vp:
            cands.append(vp)
    except Exception:
        pass
    cands += [r"C:\Program Files\Python310\python.exe", r"C:\Program Files\Python311\python.exe",
              shutil.which('python') or '', shutil.which('python3') or '', sys.executable]
    seen = set()
    for c in cands:
        if not c or c in seen or not Path(c).exists():
            continue
        seen.add(c)
        if _validate_python(c):
            try:
                PYTHON_CACHE.parent.mkdir(parents=True, exist_ok=True)
                PYTHON_CACHE.write_text(c, encoding='utf-8')
            except Exception:
                pass
            return c
    return None


_start_lock = threading.Lock()


def ensure_sidecar(timeout: float = 60.0) -> tuple:
    """Make sure the engine answers. Starts it (detached) when image.autostart is on."""
    if is_up():
        return True, 'running'
    if not bool(_cfg().get('autostart', True)):
        return False, 'down (image.autostart is off)'
    if not SIDECAR.exists():
        return False, f'{SIDECAR} missing'
    ckpt = checkpoint_path()
    if not ckpt.exists():
        return False, f'checkpoint not found: {ckpt} (config image.checkpoint)'
    with _start_lock:
        if is_up():
            return True, 'running'
        py = find_sidecar_python()
        if not py:
            return False, 'no Python with torch + diffusers found (set CORA_IMAGE_PYTHON or config image.python)'
        port = image_url().rsplit(':', 1)[-1]
        device = os.environ.get('CORA_IMAGE_DEVICE') or _cfg().get('device') or 'auto'
        try:
            SIDECAR_LOG.parent.mkdir(parents=True, exist_ok=True)
            log = open(SIDECAR_LOG, 'ab', buffering=0)
            flags = 0
            if os.name == 'nt':
                flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, 'DETACHED_PROCESS', 0)
            args = [py, '-u', str(SIDECAR), '--port', str(port), '--checkpoint', str(ckpt), '--device', str(device)]
            if _cfg().get('offload') is False:
                args.append('--no-offload')
            proc = subprocess.Popen(args, cwd=str(PROJECT_DIR), stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                    creationflags=flags)
            RUN_DIR.mkdir(parents=True, exist_ok=True)
            PID_FILE.write_text(str(proc.pid), encoding='utf-8')
        except Exception as e:
            return False, f'could not start the image engine: {e}'
        deadline = time.time() + timeout
        while time.time() < deadline:
            if is_up(1.0):
                return True, f'started with {py}'
            time.sleep(0.5)
        return False, f'started but no /health answer in {timeout:.0f}s (see {SIDECAR_LOG})'


def _own_pid() -> Optional[int]:
    try:
        return int(PID_FILE.read_text(encoding='utf-8').strip())
    except Exception:
        return None


def release_gpu() -> bool:
    """Drop the pipelines (the process stays warm for the next picture)."""
    try:
        return requests.post(f"{image_url()}/unload", json={}, timeout=20).ok
    except Exception:
        return False


def release() -> str:
    """What every exit path calls: the engine CORA started herself is stopped (its CUDA context
    goes with it); one started by someone else is only asked to drop its pipelines."""
    if _own_pid() is not None:
        return 'stopped' if stop_sidecar() else 'not running'
    if is_up(1.0):
        return 'unloaded' if release_gpu() else 'unload refused'
    return 'not running'


def stop_sidecar() -> bool:
    """End the engine when CORA started it (pid file). One started by hand is left alone."""
    pid = _own_pid()
    if pid is None:
        return False
    try:
        requests.post(f"{image_url()}/shutdown", json={}, timeout=3)
    except Exception:
        pass
    time.sleep(0.5)
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, timeout=10)
        else:
            os.kill(pid, 15)
    except Exception:
        pass
    try:
        PID_FILE.unlink()
    except Exception:
        pass
    return True


# --------------------------------------------------------------------------- files
def _remember(path: Path):
    try:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        LAST_FILE.write_text(str(path), encoding='utf-8')
    except Exception:
        pass


def last_image() -> Optional[str]:
    """The image she made or edited most recently (survives a restart)."""
    try:
        p = LAST_FILE.read_text(encoding='utf-8').strip()
        if p and Path(p).exists():
            return p
    except Exception:
        pass
    recent = get_recent_images(1)
    return recent[0] if recent else None


def _new_path(kind: str, output_path: Optional[Union[str, Path]] = None) -> Path:
    if output_path:
        p = Path(output_path)
        if p.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
            p = p.with_suffix('.png')
    else:
        p = IMAGES_DIR / f"{kind}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _b64_file(path: Union[str, Path]) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode('ascii')


def _face_crop_b64(path: Union[str, Path]) -> Optional[str]:
    """The largest face in the photo (OpenCV's bundled frontal-face cascade), padded, as base64.
    None when no face is found; the caller then lets the whole frame carry the identity."""
    try:
        import cv2
        img = cv2.imread(str(path))
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        det = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = det.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        pad = int(0.4 * max(w, h))
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(img.shape[1], x + w + pad), min(img.shape[0], y + h + pad)
        ok, buf = cv2.imencode('.png', img[y0:y1, x0:x1])
        return base64.b64encode(buf.tobytes()).decode('ascii') if ok else None
    except Exception:
        return None


def _capture_camera() -> Optional[Path]:
    from services import camera
    return camera.capture_to_file(IMAGES_DIR / f"camshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")


def _resolve_source(source: Union[str, Path]) -> Path:
    s = str(source or 'last').strip()
    if s.lower() in ('last', 'latest', 'previous', ''):
        p = last_image()
        if not p:
            raise FileNotFoundError('no image has been generated yet')
        return Path(p)
    if s.lower() in ('camera', 'webcam', 'cam'):
        p = _capture_camera()
        if not p:
            from services import camera
            raise RuntimeError(f"camera: {camera.last_error() or 'no frame'}")
        return p
    p = Path(os.path.expanduser(s))
    if not p.is_absolute():
        for base in (Path.cwd(), PROJECT_DIR, IMAGES_DIR):
            if (base / p).exists():
                p = base / p
                break
    if not p.exists():
        raise FileNotFoundError(f'image not found: {s}')
    return p


# --------------------------------------------------------------------------- rendering
def _post(endpoint: str, body: Dict[str, Any], out: Path, timeout: float = 900.0) -> Dict[str, Any]:
    ok, msg = ensure_sidecar()
    if not ok:
        return {'success': False, 'error': f'image engine: {msg}'}
    t0 = time.time()
    try:
        r = requests.post(f"{image_url()}/{endpoint}", json=body, timeout=timeout)
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f'image engine unreachable: {e}', 'inference_time': time.time() - t0}
    if r.status_code != 200 or 'image' not in r.headers.get('Content-Type', ''):
        try:
            err = r.json().get('error') or r.text[:200]
        except Exception:
            err = r.text[:200]
        return {'success': False, 'error': f'image engine {r.status_code}: {err}', 'inference_time': time.time() - t0}
    out.write_bytes(r.content)
    _remember(out)
    size = r.headers.get('X-Size', '')
    w, h = (size.split('x') + ['', ''])[:2] if 'x' in size else ('', '')
    return {'success': True, 'path': str(out), 'model': ENGINE_NAME, 'engine': ENGINE_NAME,
            'width': int(w) if w.isdigit() else body.get('width'), 'height': int(h) if h.isdigit() else body.get('height'),
            'seed': int(r.headers.get('X-Seed') or 0) or None, 'format': out.suffix.lstrip('.'),
            'inference_time': float(r.headers.get('X-Seconds') or (time.time() - t0)),
            'size_bytes': len(r.content)}


def generate_image(prompt: str, model: Optional[str] = None, width: Optional[int] = None, height: Optional[int] = None,
                   seed: Optional[int] = None, output_path: Optional[str] = None, negative: Optional[str] = None,
                   steps: Optional[int] = None, face: Optional[str] = None, face_scale: Optional[float] = None,
                   selfie: bool = False, **_legacy) -> Dict[str, Any]:
    """Text to image on her own engine. `model` is accepted for the old callers and ignored
    (there is one engine). `face` = path of a photo whose person the picture should show.
    `selfie` = a picture of herself: her look (config image.selfie_look) leads the prompt and
    image.selfie_negative is banned, so she is the same girl every time."""
    dw, dh = _default_size()
    prompt = str(prompt)
    if selfie:
        look, neg = selfie_defaults()
        prompt = look + (', ' + prompt if prompt.strip() else '')
        negative = negative or neg
        if not width and not height:
            width, height = 576, 768
    body: Dict[str, Any] = {'prompt': prompt, 'width': int(width or dw), 'height': int(height or dh)}
    if seed is not None:
        body['seed'] = int(seed)
    if negative:
        body['negative'] = negative
    if steps or _steps():
        body['steps'] = int(steps or _steps())
    if face:
        body['face'] = _face_crop_b64(face) or _b64_file(face)
        body['face_scale'] = float(face_scale or 0.6)
    r = _post('txt2img', body, _new_path('selfie' if selfie else 'generated', output_path))
    r['prompt'] = prompt
    return r


def edit_image(source: Union[str, Path], prompt: str, strength: float = 0.55, box: Optional[List[float]] = None,
               keep_face: bool = False, seed: Optional[int] = None, output_path: Optional[str] = None,
               steps: Optional[int] = None, negative: Optional[str] = None) -> Dict[str, Any]:
    """Change an image with words. source: a path, "last" (the newest one) or "camera" (a fresh
    webcam shot). strength 0.2 keeps almost everything, 0.9 keeps only the layout. With `box`
    ([x0, y0, x1, y1] as fractions) only that region is repainted (inpaint). keep_face locks the
    face of whoever is in the source."""
    try:
        src = _resolve_source(source)
    except Exception as e:
        return {'success': False, 'error': str(e)}
    body: Dict[str, Any] = {'prompt': str(prompt), 'image': _b64_file(src), 'strength': float(strength)}
    if seed is not None:
        body['seed'] = int(seed)
    if steps or _steps():
        body['steps'] = int(steps or _steps())
    if negative:
        body['negative'] = negative
    if keep_face:
        body['face'] = _face_crop_b64(src) or True
        body['face_scale'] = 0.6
    endpoint = 'img2img'
    if box:
        body['box'] = [float(v) for v in box]
        endpoint = 'inpaint'
    r = _post(endpoint, body, _new_path('edited', output_path))
    r.update(prompt=prompt, source=str(src))
    return r


def recreate_camera(prompt: str = '', strength: float = 0.6, keep_face: bool = True, seed: Optional[int] = None,
                    output_path: Optional[str] = None) -> Dict[str, Any]:
    """A webcam shot, recreated through the engine: the scene and the person as the prompt says,
    the face kept when keep_face is on. An empty prompt means 'the same scene, painted'."""
    try:
        src = _resolve_source('camera')
    except Exception as e:
        return {'success': False, 'error': str(e)}
    body: Dict[str, Any] = {'prompt': str(prompt or 'the same scene, a realistic photo, detailed, natural light'),
                            'image': _b64_file(src), 'strength': float(strength)}
    if seed is not None:
        body['seed'] = int(seed)
    if _steps():
        body['steps'] = _steps()
    if keep_face:
        body['face'] = _face_crop_b64(src) or True
        body['face_scale'] = 0.65
    r = _post('img2img', body, _new_path('camera', output_path))
    r.update(prompt=prompt, source=str(src))
    return r


def generate_boot_image(prompt: str = None) -> Dict[str, Any]:
    """A boot image at 1024x576 (the engine's native range; the viewer scales it)."""
    if prompt is None:
        prompt = ("futuristic AI boot screen, holographic interface, glowing blue circuits, dark background, "
                  "sleek modern design, digital consciousness awakening")
    result = generate_image(prompt=prompt, width=1024, height=576)
    if result["success"]:
        print(f"[+] Boot image generated: {result['path']}")
        print(f"    Size: {result['width']}x{result['height']}")
        print(f"    Time: {result['inference_time']:.2f}s")
    else:
        print(f"[!] Boot image generation failed: {result.get('error')}")
    return result


# --------------------------------------------------------------------------- showing + saving
def show_image(image_path: Union[str, Path], caption: Optional[str] = None, close_after: Optional[float] = None) -> bool:
    """Open the image in CORA's viewer (its own process, never blocks, never fights the GUI
    thread): fit to screen, Save As, Open folder, Copy path, Esc closes."""
    p = Path(image_path)
    if not p.exists():
        print(f"[!] Image not found: {p}")
        return False
    viewer = PROJECT_DIR / 'ui' / 'image_viewer.py'
    py = sys.executable
    if os.name == 'nt':
        pyw = Path(py).with_name('pythonw.exe')
        if pyw.exists():
            py = str(pyw)
    args = [py, str(viewer), str(p)]
    if caption:
        args += ['--caption', str(caption)[:300]]
    if close_after:
        args += ['--close-after', str(float(close_after))]
    try:
        flags = 0
        if os.name == 'nt':
            flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(args, cwd=str(PROJECT_DIR), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=flags)
        return True
    except Exception as e:
        print(f"[!] viewer: {e}")
        return False


def show_fullscreen_image(image_path: str, duration: Optional[float] = None) -> bool:
    """Old name, kept: opens the viewer window (closes itself after `duration` seconds if given)."""
    return show_image(image_path, close_after=duration)


def save_image(destination: Union[str, Path], source: Union[str, Path] = 'last') -> Dict[str, Any]:
    """Copy an image where the user asked: a folder (the file keeps its name) or a full file path.
    ~ and relative paths are fine; the folder is created when missing."""
    try:
        src = _resolve_source(source)
    except Exception as e:
        return {'success': False, 'error': str(e)}
    dest = Path(os.path.expanduser(str(destination or '').strip().strip('"')))
    if not str(dest):
        return {'success': False, 'error': 'no destination given'}
    if not dest.is_absolute():
        dest = Path.home() / dest
    try:
        if dest.exists() and dest.is_dir() or not dest.suffix:
            dest.mkdir(parents=True, exist_ok=True)
            dest = dest / src.name
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.suffix.lower() != src.suffix.lower() and dest.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
            from PIL import Image
            img = Image.open(src)
            if dest.suffix.lower() in ('.jpg', '.jpeg'):
                img = img.convert('RGB')
            img.save(dest)
        else:
            shutil.copy2(src, dest)
        return {'success': True, 'path': str(dest), 'source': str(src), 'size_bytes': dest.stat().st_size}
    except Exception as e:
        return {'success': False, 'error': f'could not save to {dest}: {e}'}


def get_recent_images(limit: int = 10) -> list:
    """Recently generated images, newest first."""
    if not IMAGES_DIR.exists():
        return []
    images = []
    for ext in ['*.png', '*.jpg', '*.jpeg', '*.webp']:
        images.extend(IMAGES_DIR.glob(ext))
    images.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p) for p in images[:limit]]


if __name__ == "__main__":
    print("=== CORA Image Engine ===")
    print(f"url: {image_url()}  checkpoint: {checkpoint_path()}  exists: {checkpoint_path().exists()}")
    print("health:", sidecar_health())
    ok, msg = ensure_sidecar()
    print("sidecar:", ok, msg)
    if ok and '--render' in sys.argv:
        r = generate_image("a small neon test pattern on a dark desk, realistic photo", width=512, height=512)
        print(r)
        if r.get('success'):
            show_image(r['path'], caption=r['prompt'])
