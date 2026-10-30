#!/usr/bin/env python3
"""
Pollinations AI MCP Server for Claude Code CLI Plugin.
BYOP (Bring Your Own Pollen) — users authenticate with their own Pollinations account.
Developer pays nothing. User's pollen credits fund requests.

Base URL: https://gen.pollinations.ai
Image URL: https://image.pollinations.ai
Auth: Bearer token from BYOP OAuth flow
"""
import json
import os
import sys
import time
import re
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mcp", "-q"])
    from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pollinations")

PLUGIN_DIR = Path(__file__).parent.parent
CONFIG_DIR = PLUGIN_DIR / "config"
# User config (keys) stored in project dir so it survives plugin updates
PROJECT_DIR = Path(os.getcwd())
USER_CONFIG_FILE = PROJECT_DIR / ".claude" / "pollinations-user.json"
IMAGE_URL = "https://gen.pollinations.ai/image"  # GET /image/{prompt} for images and video
BASE_URL = "https://gen.pollinations.ai"
BYOP_AUTH_URL = "https://enter.pollinations.ai/authorize"
API_KEY = ""  # Key comes from user.json via BYOP OAuth, not env vars

# Developer app key — registered at enter.pollinations.ai
APP_KEY = os.environ.get("POLLINATIONS_APP_KEY", "")


def _load_config():
    config = {}
    # Load plugin defaults
    defaults = CONFIG_DIR / "defaults.json"
    if defaults.exists():
        try:
            config.update(json.loads(defaults.read_text(encoding="utf-8")))
        except Exception:
            pass
    # Load user config from project dir (survives plugin updates)
    if USER_CONFIG_FILE.exists():
        try:
            config.update(json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return config


def _save_user_config(data):
    existing = {}
    if USER_CONFIG_FILE.exists():
        try:
            existing = json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing.update(data)
    USER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    USER_CONFIG_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def _load_styles():
    f = CONFIG_DIR / "styles.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _headers(config=None):
    if config is None:
        config = _load_config()
    h = {"Content-Type": "application/json"}
    key = config.get("api_key", "")
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def _http_get(url, timeout=120, config=None):
    if config is None:
        config = _load_config()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "image/*, */*"
    }
    key = config.get("api_key", "")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.headers.get("Content-Type", "")


def _http_json(url, method="GET", data=None, headers=None, timeout=60):
    if headers is None:
        headers = {}
    if "User-Agent" not in headers:
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    req = urllib.request.Request(url, method=method, headers=headers)
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body[:500]}
    except Exception as e:
        return 0, {"error": str(e)}


# --- Auth Check ---

NO_KEY_MSG = ("Not connected to Pollinations. Run /pollinations-setup to connect your Pollinations account.")


def _require_key(config=None):
    if config is None:
        config = _load_config()
    key = config.get("api_key", "")
    if not key:
        return NO_KEY_MSG
    return None


# --- Tools ---

@mcp.tool()
def pollinations_setup(api_key: str = "") -> str:
    """Connect to Pollinations via BYOP. Opens browser for login, catches the key automatically. If user already has a key they can pass it directly.

    Args:
        api_key: Optional — pass a key directly if user has one. Otherwise leave empty to start BYOP login flow.
    """
    if api_key:
        _save_user_config({"api_key": api_key})
        return f"Connected. Key saved. Ready to generate."

    # BYOP OAuth flow — spin up localhost server, open browser, catch redirect
    import threading
    import http.server
    import webbrowser

    captured_key = [None]
    server_ready = threading.Event()

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            # Serve a page that extracts the key from the URL fragment
            # Fragment (#api_key=...) never hits the server, so we use JS to POST it back
            if self.path.startswith("/capture"):
                # JS posted the key to us
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8") if length else ""
                try:
                    data = json.loads(body)
                    captured_key[0] = data.get("api_key", "")
                except Exception:
                    pass
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"<html><body><h2>Connected! You can close this tab.</h2></body></html>")
                return

            if self.path.startswith("/options") or self.path == "/capture":
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()
                return

            # Main callback page — extracts fragment and POSTs key back to /capture
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            page = """<html><body>
<h2>Connecting to Pollinations...</h2>
<script>
var key = new URLSearchParams(window.location.hash.slice(1)).get('api_key');
if (key) {
    fetch('/capture', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({api_key:key})})
    .then(function(){document.body.innerHTML='<h2>Connected! You can close this tab.</h2>';});
} else {
    document.body.innerHTML='<h2>No key received. Try again.</h2>';
}
</script>
</body></html>"""
            self.wfile.write(page.encode("utf-8"))

        def do_POST(self):
            self.do_GET()

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def log_message(self, format, *args):
            pass  # silence logs

    # Find a free port
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    redirect_url = f"http://localhost:{port}"

    # Build auth URL
    app_key = APP_KEY or _load_config().get("app_key", "")
    params = {"redirect_url": redirect_url}
    if app_key:
        params["app_key"] = app_key
    auth_url = f"{BYOP_AUTH_URL}?{urllib.parse.urlencode(params)}"

    # Start server in background
    server = http.server.HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = 120

    def serve():
        server_ready.set()
        for _ in range(60):  # wait up to 2 min
            server.handle_request()
            if captured_key[0]:
                break

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    server_ready.wait()

    # Open browser
    webbrowser.open(auth_url)

    # Wait for key (up to 2 min)
    t.join(timeout=120)

    try:
        server.server_close()
    except Exception:
        pass

    if captured_key[0]:
        _save_user_config({"api_key": captured_key[0]})
        return f"Connected! Key saved. Ready to generate."
    else:
        return "Timed out waiting for login. Run /pollinations-setup to try again."


@mcp.tool()
def pollinations_image(prompt: str, model: str = "", style: str = "",
                       negative: str = "", width: int = 0, height: int = 0,
                       ratio: str = "", seed: int = -1) -> str:
    """Generate an image via Pollinations AI. Requires connection — run /pollinations-setup first.

    Args:
        prompt: Image description
        model: Model name (flux, flux-2-dev, gptimage, imagen-4, kontext, nanobanana, seedream5, dirtberry, klein, zimage). Default: flux
        style: Style preset (photorealistic, anime, oil-painting, pixel-art, watercolor, cinematic, sketch, cyberpunk)
        negative: What to exclude from the image
        width: Image width (default 1024). Ignored if ratio is set.
        height: Image height (default 1024). Ignored if ratio is set.
        ratio: Aspect ratio preset (1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3, 21:9). Overrides width/height.
        seed: Seed for reproducibility (-1 for random)
    """
    config = _load_config()
    gate = _require_key(config)
    if gate:
        return gate

    styles = _load_styles()
    model = model or config.get("default_image_model", "flux")
    if ratio and ratio in RATIO_PRESETS:
        width, height = RATIO_PRESETS[ratio]
    else:
        width = width or config.get("default_image_width", 1024)
        height = height or config.get("default_image_height", 1024)

    full_prompt = prompt
    full_negative = negative
    if style and style in styles:
        preset = styles[style]
        full_prompt = f"{prompt}, {preset.get('suffix', '')}"
        if not negative and preset.get("negative"):
            full_negative = preset["negative"]
    if full_negative:
        full_prompt = f"{full_prompt} --no {full_negative}"

    # GET /image/{prompt} with Bearer auth
    encoded = urllib.parse.quote(full_prompt)
    params = {
        "model": model,
        "width": str(width),
        "height": str(height),
        "nologo": "true"
    }
    if seed >= 0:
        params["seed"] = str(seed)

    query = urllib.parse.urlencode(params)
    url = f"{IMAGE_URL}/{encoded}?{query}"

    try:
        image_data, ct = _http_get(url, timeout=120, config=config)
        ext = "png"
        if "jpeg" in ct or "jpg" in ct:
            ext = "jpg"
        elif "webp" in ct:
            ext = "webp"

        out_dir = Path(config.get("output_dir", "./pollinations-output"))
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        safe_name = re.sub(r'[^\w\s-]', '', prompt[:40]).strip().replace(' ', '_')
        out_path = out_dir / f"{safe_name}_{ts}.{ext}"
        out_path.write_bytes(image_data)

        size_kb = len(image_data) / 1024
        return (f"Image saved: {out_path}\n"
                f"Model: {model} | Size: {width}x{height} | Format: {ext} | {size_kb:.0f}KB\n"
                f"Style: {style or 'none'} | Seed: {seed if seed >= 0 else 'random'}")
    except urllib.error.HTTPError as e:
        return f"Error: HTTP {e.code} — {e.read().decode('utf-8', errors='replace')[:300]}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def pollinations_text(prompt: str, model: str = "", system: str = "",
                      temperature: float = -1, seed: int = -1) -> str:
    """Chat with a Pollinations AI text model. Requires connection — run /pollinations-setup first.

    Args:
        prompt: Your message
        model: Model name (openai, deepseek, mistral, claude-fast, etc). Default: openai
        system: System prompt to set behavior
        temperature: 0.0-2.0 (-1 for default)
        seed: Seed for reproducibility (-1 for random)
    """
    config = _load_config()
    gate = _require_key(config)
    if gate:
        return gate

    model = model or config.get("default_text_model", "openai")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {"model": model, "messages": messages}
    if temperature >= 0:
        body["temperature"] = temperature
    if seed >= 0:
        body["seed"] = seed

    url = f"{BASE_URL}/v1/chat/completions"
    status, data = _http_json(url, method="POST", data=body, headers=_headers(config), timeout=300)

    if status == 200 and isinstance(data, dict):
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            tokens = usage.get("total_tokens", "?")
            return f"[{model}]: {content}\n\n(tokens: {tokens})"
    return f"Error (HTTP {status}): {json.dumps(data, indent=2)[:500]}"


@mcp.tool()
def pollinations_audio(text: str, voice: str = "", output_path: str = "", autoplay: bool = True) -> str:
    """Generate speech from text via Pollinations TTS. Requires connection — run /pollinations-setup first.

    Args:
        text: Text to speak
        voice: Voice name (alloy, echo, fable, onyx, nova, shimmer, etc). Default: nova
        output_path: Custom save path (optional)
        autoplay: Auto-play the audio after generating (default: true)
    """
    config = _load_config()
    gate = _require_key(config)
    if gate:
        return gate

    voice = voice or config.get("default_voice", "nova")
    body = {"model": "openai-audio", "input": text, "voice": voice}
    url = f"{BASE_URL}/v1/audio/speech"

    try:
        hdrs = _headers(config)
        hdrs["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        req = urllib.request.Request(url, method="POST", headers=hdrs)
        req.data = json.dumps(body).encode("utf-8")
        with urllib.request.urlopen(req, timeout=60) as resp:
            audio_data = resp.read()
            if not output_path:
                out_dir = Path(config.get("output_dir", "./pollinations-output"))
                out_dir.mkdir(parents=True, exist_ok=True)
                ts = int(time.time())
                output_path = str(out_dir / f"speech_{ts}.mp3")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_bytes(audio_data)
            size_kb = len(audio_data) / 1024
            # Auto-play if enabled
            if autoplay:
                try:
                    if sys.platform == "win32":
                        os.startfile(str(Path(output_path)))
                    elif sys.platform == "darwin":
                        import subprocess
                        subprocess.Popen(["open", str(output_path)])
                    else:
                        import subprocess
                        subprocess.Popen(["xdg-open", str(output_path)])
                except Exception:
                    pass
            return f"Audio saved and playing: {output_path}\nVoice: {voice} | {size_kb:.0f}KB"
    except urllib.error.HTTPError as e:
        return f"Error: HTTP {e.code} — {e.read().decode('utf-8', errors='replace')[:300]}"
    except Exception as e:
        return f"Error: {e}"


RATIO_PRESETS = {
    "1:1": (1024, 1024),
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "4:3": (1024, 768),
    "3:4": (768, 1024),
    "3:2": (1200, 800),
    "2:3": (800, 1200),
    "21:9": (1344, 576),
}


@mcp.tool()
def pollinations_video(prompt: str, model: str = "veo-3.1-fast",
                       ratio: str = "16:9", duration: int = 5,
                       seed: int = -1) -> str:
    """Generate a video via Pollinations AI. Requires connection — run /pollinations-setup first.

    Args:
        prompt: Video description
        model: Video model (veo-3.1-fast, seedance, seedance-1080p, wan, grok-video, ltx-2, p-video). Default: veo-3.1-fast
        ratio: Aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4). Default: 16:9
        duration: Duration in seconds (2-15 depending on model). Default: 5
        seed: Seed for reproducibility (-1 for random)
    """
    config = _load_config()
    gate = _require_key(config)
    if gate:
        return gate

    # Use GET /image/{prompt} with video model — returns video binary
    encoded = urllib.parse.quote(prompt)
    w, h = RATIO_PRESETS.get(ratio, (1280, 720))
    params = {
        "model": model,
        "width": str(w),
        "height": str(h),
        "duration": str(duration),
        "nologo": "true"
    }
    if seed >= 0:
        params["seed"] = str(seed)

    query = urllib.parse.urlencode(params)
    url = f"{IMAGE_URL}/{encoded}?{query}"

    try:
        video_data, ct = _http_get(url, timeout=300, config=config)

        out_dir = Path(config.get("output_dir", "./pollinations-output"))
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        safe_name = re.sub(r'[^\w\s-]', '', prompt[:40]).strip().replace(' ', '_')
        ext = "mp4"
        out_path = out_dir / f"{safe_name}_{ts}.{ext}"
        out_path.write_bytes(video_data)

        size_mb = len(video_data) / (1024 * 1024)
        return (f"Video saved: {out_path}\n"
                f"Model: {model} | Size: {w}x{h} | Duration: {duration}s | {size_mb:.1f}MB")
    except urllib.error.HTTPError as e:
        return f"Error: HTTP {e.code} — {e.read().decode('utf-8', errors='replace')[:300]}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def pollinations_transcribe(audio_path: str, model: str = "whisper-large-v3") -> str:
    """Transcribe audio to text via Pollinations. Requires connection — run /pollinations-setup first.

    Args:
        audio_path: Path to audio file to transcribe
        model: Transcription model (whisper-large-v3, scribe). Default: whisper-large-v3
    """
    config = _load_config()
    gate = _require_key(config)
    if gate:
        return gate

    p = Path(audio_path)
    if not p.exists():
        return f"File not found: {audio_path}"

    # POST /v1/audio/transcriptions with file upload
    import mimetypes
    content_type = mimetypes.guess_type(str(p))[0] or "audio/mpeg"

    # Build multipart form data manually
    boundary = f"----PollBoundary{int(time.time())}"
    body = b""
    # file field
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="file"; filename="{p.name}"\r\n'.encode()
    body += f"Content-Type: {content_type}\r\n\r\n".encode()
    body += p.read_bytes()
    body += b"\r\n"
    # model field
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="model"\r\n\r\n'.encode()
    body += model.encode()
    body += b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    url = f"{BASE_URL}/v1/audio/transcriptions"
    hdrs = _headers(config)
    hdrs["Content-Type"] = f"multipart/form-data; boundary={boundary}"

    req = urllib.request.Request(url, method="POST", headers=hdrs, data=body)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            text = result.get("text", "")
            return f"Transcription:\n{text}"
    except urllib.error.HTTPError as e:
        return f"Error: HTTP {e.code} — {e.read().decode('utf-8', errors='replace')[:300]}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def pollinations_models(model_type: str = "all") -> str:
    """List available Pollinations AI models.

    Args:
        model_type: Filter by type: all, text, image, video, audio
    """
    result = []

    if model_type in ("all", "text"):
        status, data = _http_json(f"{BASE_URL}/v1/models")
        if status == 200 and isinstance(data, dict):
            models = data.get("data", [])
            result.append(f"=== Text Models ({len(models)}) ===")
            for m in models:
                paid = " [PAID]" if m.get("paid") else ""
                result.append(f"  {m.get('id', '?'):25s} {m.get('description', '')[:50]}{paid}")

    if model_type in ("all", "image", "video"):
        status, data = _http_json(f"{IMAGE_URL}/models")
        if status == 200 and isinstance(data, list):
            images = [m for m in data if m.get("type") != "video"]
            videos = [m for m in data if m.get("type") == "video"]

            if model_type in ("all", "image"):
                result.append(f"\n=== Image Models ({len(images)}) ===")
                for m in images:
                    mid = m.get("id", m.get("name", "?"))
                    paid = " [PAID]" if m.get("paid") else ""
                    result.append(f"  {mid:25s} {m.get('description', '')[:50]}{paid}")

            if model_type in ("all", "video"):
                result.append(f"\n=== Video Models ({len(videos)}) ===")
                for m in videos:
                    mid = m.get("id", m.get("name", "?"))
                    paid = " [PAID]" if m.get("paid") else ""
                    result.append(f"  {mid:25s} {m.get('description', '')[:50]}{paid}")

    if not result:
        return "No models found or API unavailable."
    return "\n".join(result)


@mcp.tool()
def pollinations_view(file_path: str) -> str:
    """Open a generated image or media file in the system default viewer.

    Args:
        file_path: Path to the file to open
    """
    import subprocess
    p = Path(file_path)
    if not p.exists():
        return f"File not found: {file_path}"
    try:
        if sys.platform == "win32":
            os.startfile(str(p))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
        return f"Opened: {p.name}"
    except Exception as e:
        return f"Error opening file: {e}"


if __name__ == "__main__":
    mcp.run()
