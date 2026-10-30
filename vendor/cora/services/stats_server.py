#!/usr/bin/env python3
"""
C.O.R.A Local Server
Local HTTP server (127.0.0.1:11435) that gives the web version real system
stats, setup commands, the V2 voice proxy, her image engine (/image/health,
/image/generate, the pictures under /images/) and, when hosted locally, the
web files themselves.

Security model (2026-10-14):
- Binds to 127.0.0.1 only.
- Every state-changing POST requires the per-launch token in the
  `X-CORA-Token` header. The token is written to data/.stats_token and injected
  into the locally served web page; a page on another origin never sees it.
- CORS is restricted to an allowlist: the local origins plus any origins in
  config.json `web.allowed_origins`. `*` is never sent.
- Model names for /setup/pull-model are validated against a strict pattern.
- Only the repo's own requirements.txt can be installed.
"""

import json
import os
import re
import secrets
import shutil
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

import psutil

PROJECT_DIR = Path(__file__).resolve().parent.parent
STATS_PORT = 11435
TOKEN_PATH = PROJECT_DIR / 'data' / '.stats_token'
WEB_DIR = PROJECT_DIR / 'web'

_MODEL_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/-]{0,100}(:[A-Za-z0-9._-]{1,50})?$')


def _config() -> dict:
    try:
        with open(PROJECT_DIR / 'config' / 'config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _ollama_url() -> str:
    try:
        import sys
        if str(PROJECT_DIR) not in sys.path:
            sys.path.insert(0, str(PROJECT_DIR))
        from ai import settings
        return settings.ollama_url()
    except Exception:
        return os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')


def _required_models() -> list:
    try:
        import sys
        if str(PROJECT_DIR) not in sys.path:
            sys.path.insert(0, str(PROJECT_DIR))
        from ai import settings
        s = settings.settings()
        models = [s['chat_model'], s['vision_model']]
        if s['code_model'] not in models:
            models.append(s['code_model'])
        return models
    except Exception:
        return []


def _allowed_origins(port: int) -> set:
    origins = {
        f'http://127.0.0.1:{port}', f'http://localhost:{port}',
        'http://127.0.0.1', 'http://localhost', 'null',
    }
    for o in (_config().get('web') or {}).get('allowed_origins') or []:
        origins.add(str(o).rstrip('/'))
    return origins


# ----------------------------------------------------------------------------
# Token
# ----------------------------------------------------------------------------

_TOKEN = None


def get_token() -> str:
    """Per-launch secret. Created once per process, persisted so the desktop
    app and the locally served page can read it."""
    global _TOKEN
    if _TOKEN:
        return _TOKEN
    _TOKEN = secrets.token_urlsafe(32)
    try:
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(_TOKEN, encoding='utf-8')
    except Exception:
        pass
    return _TOKEN


# ----------------------------------------------------------------------------
# Stats
# ----------------------------------------------------------------------------

def get_gpu_stats():
    """Get NVIDIA GPU stats using nvidia-smi."""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(', ')
            if len(parts) >= 5:
                return {
                    'name': parts[0],
                    'utilization': int(parts[1]),
                    'memory_used': int(parts[2]),
                    'memory_total': int(parts[3]),
                    'temperature': int(parts[4]),
                    'available': True
                }
    except Exception:
        pass
    return {'available': False}


def get_system_stats():
    """Get full system stats."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    try:
        disk = psutil.disk_usage(os.environ.get('SystemDrive', 'C:') + '\\' if os.name == 'nt' else '/')
    except Exception:
        disk = psutil.disk_usage('/')
    return {
        'cpu': {'percent': cpu_percent, 'cores': psutil.cpu_count()},
        'memory': {'percent': mem.percent, 'used_gb': round(mem.used / (1024**3), 1),
                   'total_gb': round(mem.total / (1024**3), 1)},
        'disk': {'percent': disk.percent, 'used_gb': round(disk.used / (1024**3), 1),
                 'total_gb': round(disk.total / (1024**3), 1)},
        'gpu': get_gpu_stats(),
        'network': {'connected': True},
    }


# ----------------------------------------------------------------------------
# Setup functions (same logic as CORA.bat)
# ----------------------------------------------------------------------------

def find_ollama():
    """Find the Ollama executable."""
    ollama_path = shutil.which('ollama')
    if ollama_path:
        return ollama_path
    for loc in (
        os.path.expandvars(r'%LOCALAPPDATA%\Programs\Ollama\ollama.exe'),
        os.path.expandvars(r'%ProgramFiles%\Ollama\ollama.exe'),
        os.path.expandvars(r'%ProgramFiles(x86)%\Ollama\ollama.exe'),
        os.path.expandvars(r'%USERPROFILE%\Ollama\ollama.exe'),
    ):
        if os.path.exists(loc):
            return loc
    return None


def check_ollama_running():
    """Check if the Ollama service answers."""
    try:
        import urllib.request
        req = urllib.request.urlopen(f'{_ollama_url()}/api/tags', timeout=3)
        return req.status == 200
    except Exception:
        return False


def get_ollama_models():
    """Installed Ollama model names via the HTTP API."""
    try:
        import urllib.request
        with urllib.request.urlopen(f'{_ollama_url()}/api/tags', timeout=5) as r:
            data = json.loads(r.read().decode('utf-8'))
        return [m.get('name', '') for m in data.get('models', []) if m.get('name')]
    except Exception:
        return []


def pull_ollama_model(model_name):
    """Pull an Ollama model. Returns (success, output)."""
    if not _MODEL_NAME_RE.match(model_name or ''):
        return False, "Invalid model name"
    ollama_exe = find_ollama()
    if not ollama_exe:
        return False, "Ollama not found"
    try:
        print(f"[SETUP] Pulling model: {model_name}")
        result = subprocess.run([ollama_exe, 'pull', model_name],
                                capture_output=True, text=True, timeout=1800)
        if result.returncode == 0:
            return True, result.stdout
        return False, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout - model download took too long"
    except Exception as e:
        return False, str(e)


def start_ollama_service():
    """Start the Ollama service in the background."""
    ollama_exe = find_ollama()
    if not ollama_exe:
        return False, "Ollama not found"
    try:
        if os.name == 'nt':
            subprocess.Popen([ollama_exe, 'serve'], creationflags=subprocess.CREATE_NO_WINDOW,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen([ollama_exe, 'serve'], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        return True, "Ollama service started"
    except Exception as e:
        return False, str(e)


def install_requirements():
    """Install the repo's own requirements.txt into the running interpreter."""
    import sys
    req_file = PROJECT_DIR / 'requirements.txt'
    if not req_file.exists():
        return False, "requirements.txt not found"
    try:
        print(f"[SETUP] Installing from: {req_file}")
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(req_file)],
                                capture_output=True, text=True, timeout=900)
        if result.returncode == 0:
            return True, "Requirements installed"
        return False, result.stderr[-2000:]
    except Exception as e:
        return False, str(e)


def get_setup_status():
    """Full setup status."""
    ollama_exe = find_ollama()
    ollama_running = check_ollama_running()
    models = get_ollama_models() if ollama_running else []
    required = _required_models()
    model_status = {}
    for req in required:
        base = req.split(':')[0]
        model_status[req] = any(m == req or m.split(':')[0] == base for m in models)
    return {
        'ollama_installed': ollama_exe is not None,
        'ollama_path': ollama_exe,
        'ollama_running': ollama_running,
        'models_installed': models,
        'required_models': model_status,
        'all_models_ready': all(model_status.values()) if model_status else False,
    }


def image_health():
    """Health of her image engine (services/image_sidecar.py)."""
    try:
        import sys
        if str(PROJECT_DIR) not in sys.path:
            sys.path.insert(0, str(PROJECT_DIR))
        from cora_tools import image_gen
        h = image_gen.sidecar_health()
        h['checkpoint_present'] = h.get('checkpoint_present', image_gen.checkpoint_path().exists())
        h['engine'] = image_gen.ENGINE_NAME
        # usable = the checkpoint is there and the sidecar is up or may be started on the first picture
        h['available'] = bool(h['checkpoint_present']) and (bool(h.get('ok')) or bool(image_gen._cfg().get('autostart', True)))
        return h
    except Exception as e:
        return {'ok': False, 'error': str(e)[:120]}


def image_generate(body: dict) -> dict:
    """Text to image on her engine for the web page; the file is served back under /images/."""
    import sys
    if str(PROJECT_DIR) not in sys.path:
        sys.path.insert(0, str(PROJECT_DIR))
    from cora_tools import image_gen
    prompt = str(body.get('prompt') or '').strip()
    if not prompt:
        return {'success': False, 'error': 'prompt is empty'}
    kw = {}
    for k in ('width', 'height', 'seed'):
        if body.get(k) not in (None, ''):
            try:
                kw[k] = int(body[k])
            except (TypeError, ValueError):
                pass
    r = image_gen.generate_image(prompt, **kw)
    if r.get('success'):
        r['url'] = '/images/' + Path(r['path']).name
    return r


def voice_health():
    """Health of the unity-voice-v2 sidecar."""
    try:
        import urllib.request
        url = os.environ.get('UNITY_VOICE_TTS_URL', 'http://127.0.0.1:5123').rstrip('/')
        with urllib.request.urlopen(f'{url}/health', timeout=2) as r:
            return {'ok': r.status == 200, 'url': url}
    except Exception as e:
        return {'ok': False, 'error': str(e)[:120]}


# ----------------------------------------------------------------------------
# HTTP handler
# ----------------------------------------------------------------------------

_MIME = {
    '.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8',
    '.mjs': 'application/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
    '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.txt': 'text/plain; charset=utf-8',
    '.woff2': 'font/woff2', '.woff': 'font/woff',
}


class StatsHandler(BaseHTTPRequestHandler):
    """HTTP request handler: stats, setup, voice proxy, static web files."""

    server_version = 'CORA/1.0'

    def log_message(self, format, *args):
        pass

    # -- helpers -------------------------------------------------------------
    def _origin_allowed(self) -> bool:
        origin = self.headers.get('Origin')
        if not origin:
            return True  # same-origin / non-browser client
        return origin.rstrip('/') in _allowed_origins(self.server.server_port)

    def _cors(self):
        origin = self.headers.get('Origin')
        if origin and origin.rstrip('/') in _allowed_origins(self.server.server_port):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-CORA-Token')

    def send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, body: bytes, content_type: str, status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        return secrets.compare_digest(self.headers.get('X-CORA-Token', ''), get_token())

    def _read_body(self) -> bytes:
        length = int(self.headers.get('Content-Length', 0) or 0)
        return self.rfile.read(length) if length > 0 else b''

    def _serve_static(self, path: str):
        """Serve files from web/ (locally hosted web version)."""
        rel = path.lstrip('/') or 'index.html'
        if rel.endswith('/'):
            rel += 'index.html'
        try:
            target = (WEB_DIR / rel).resolve()
            target.relative_to(WEB_DIR.resolve())
        except Exception:
            return self.send_json({'error': 'not found'}, 404)
        if not target.is_file():
            return self.send_json({'error': 'not found'}, 404)
        body = target.read_bytes()
        if target.name == 'index.html':
            # Hand the page its token + Ollama URL without exposing them to other origins.
            local = {'token': get_token(), 'ollama': _ollama_url(),
                     'stats': 'http://127.0.0.1:%d' % self.server.server_port}
            try:
                from ai import settings as _s
                local['models'] = {'chat': _s.chat_model(), 'vision': _s.vision_model(), 'code': _s.code_model()}
                local['num_ctx'] = _s.num_ctx()
                local['version'] = str((_s._read_config() or {}).get('version') or '3.0.0')
            except Exception:
                pass
            inject = '<script>window.CORA_LOCAL=%s;</script>' % json.dumps(local)
            body = body.replace(b'<head>', b'<head>' + inject.encode('utf-8'), 1)
        self.send_bytes(body, _MIME.get(target.suffix.lower(), 'application/octet-stream'))

    # -- verbs ---------------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204 if self._origin_allowed() else 403)
        self._cors()
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        if not self._origin_allowed():
            return self.send_json({'error': 'origin not allowed'}, 403)
        path = urlparse(self.path).path
        if path in ('/stats', '/api/stats'):
            self.send_json(get_system_stats())
        elif path == '/gpu':
            self.send_json(get_gpu_stats())
        elif path == '/ping':
            self.send_json({'status': 'ok', 'service': 'cora-stats'})
        elif path == '/setup/status':
            self.send_json(get_setup_status())
        elif path == '/setup/models':
            self.send_json({'models': get_ollama_models()})
        elif path == '/voice/health':
            self.send_json(voice_health())
        elif path == '/image/health':
            self.send_json(image_health())
        elif path.startswith('/images/'):
            # her generated pictures, for the web page (download link = the same URL)
            try:
                import sys
                if str(PROJECT_DIR) not in sys.path:
                    sys.path.insert(0, str(PROJECT_DIR))
                from cora_tools import image_gen
                base = image_gen.images_dir().resolve()
                target = (base / path[len('/images/'):]).resolve()
                target.relative_to(base)
                if not target.is_file():
                    raise FileNotFoundError(target)
                self.send_bytes(target.read_bytes(), _MIME.get(target.suffix.lower(), 'application/octet-stream'))
            except Exception:
                self.send_json({'error': 'not found'}, 404)
        elif path == '/api/prompt':
            # the one system prompt, so the web page and the desktop share a personality
            try:
                self.send_bytes((PROJECT_DIR / 'config' / 'system_prompt.txt').read_bytes(), 'text/plain; charset=utf-8')
            except Exception as e:
                self.send_json({'error': str(e)}, 404)
        elif path == '/' or path.startswith('/web/') or not path.startswith(('/setup', '/voice', '/api', '/image')):
            self._serve_static(path[4:] if path.startswith('/web/') else path)
        else:
            self.send_json({'error': 'unknown endpoint'}, 404)

    def do_POST(self):
        if not self._origin_allowed():
            return self.send_json({'error': 'origin not allowed'}, 403)
        path = urlparse(self.path).path
        body = self._read_body()

        # Voice proxy: the page posts {"text", "emotion", ...}; we forward to the sidecar.
        if path == '/voice/say':
            if not self._authorized():
                return self.send_json({'error': 'unauthorized'}, 401)
            try:
                import urllib.request
                url = os.environ.get('UNITY_VOICE_TTS_URL', 'http://127.0.0.1:5123').rstrip('/')
                req = urllib.request.Request(f'{url}/say', data=body,
                                             headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=60) as r:
                    return self.send_bytes(r.read(), 'audio/wav')
            except Exception as e:
                msg = getattr(e, 'read', lambda: b'')()
                return self.send_json({'error': (msg.decode('utf-8', 'replace') if msg else str(e))[:300]}, 422)

        if path == '/image/generate':
            if not self._authorized():
                return self.send_json({'error': 'unauthorized'}, 401)
            try:
                req = json.loads(body.decode('utf-8')) if body else {}
            except Exception:
                return self.send_json({'success': False, 'error': 'bad json'}, 400)
            try:
                return self.send_json(image_generate(req))
            except Exception as e:
                return self.send_json({'success': False, 'error': str(e)[:300]}, 500)

        if not path.startswith('/setup/'):
            return self.send_json({'error': 'unknown endpoint'}, 404)
        if not self._authorized():
            return self.send_json({'error': 'unauthorized'}, 401)

        if path == '/setup/start-ollama':
            success, msg = start_ollama_service()
            self.send_json({'success': success, 'message': msg})
        elif path == '/setup/install-requirements':
            success, msg = install_requirements()
            self.send_json({'success': success, 'message': msg})
        elif path.startswith('/setup/pull-model/'):
            model_name = path[len('/setup/pull-model/'):]
            if not model_name:
                return self.send_json({'success': False, 'message': 'No model specified'}, 400)
            success, msg = pull_ollama_model(model_name)
            self.send_json({'success': success, 'message': msg})
        elif path == '/setup/pull-all':
            results = {}
            for model in _required_models():
                success, msg = pull_ollama_model(model)
                results[model] = {'success': success, 'message': msg}
            self.send_json({'success': all(r['success'] for r in results.values()) if results else False,
                            'results': results})
        else:
            self.send_json({'error': 'unknown endpoint'}, 404)


def start_server(port=STATS_PORT):
    """Start the local server (blocking)."""
    get_token()
    server = HTTPServer(('127.0.0.1', port), StatsHandler)
    print(f"[STATS] Server running on http://127.0.0.1:{port}  (web UI at /)")
    print(f"[STATS] Token file: {TOKEN_PATH}")
    server.serve_forever()


def start_server_background(port=STATS_PORT):
    """Start the local server in a daemon thread."""
    thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    print("C.O.R.A Local Server")
    print("=" * 40)
    stats = get_system_stats()
    print(f"CPU: {stats['cpu']['percent']}%  RAM: {stats['memory']['percent']}%  Disk: {stats['disk']['percent']}%")
    if stats['gpu']['available']:
        print(f"GPU: {stats['gpu']['name']} - {stats['gpu']['utilization']}% ({stats['gpu']['temperature']}°C)")
    print()
    start_server()
