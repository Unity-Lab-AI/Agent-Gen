"""
voice_server.py — local speech-to-text for the weird project.

STT ONLY. The upstream reference (Unity 18+ voice-server) ships both Piper TTS
and faster-whisper STT; weird already synthesises speech in-browser via
Kokoro-js, so the TTS half is intentionally omitted here to shave the install
footprint (no Piper voice download, no piper package). If weird ever needs a
local TTS backend, wire it back in from that reference.

Speaks on 127.0.0.1:7861:
    POST /stt       — {pcm_b64|wav_b64, sample_rate?} -> {text, seconds}
    GET  /state     — health/readiness probe (browser polls this from the setup wizard)
    OPTIONS *       — CORS preflight for browser-direct POSTs

Runs faster-whisper on the visitor's GPU. Same CORS-anywhere pattern as the
image server — the browser talks straight to loopback; no Node router in
between.
"""

import base64
import io
import json
import os
import sys
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

# ⛔ Windows: the HuggingFace cache symlinks its blobs, and creating a symlink
#   needs a privilege a normal account does not hold — the model download dies
#   with "WinError 1314: A required privilege is not held by the client".
#   Set BEFORE huggingface_hub is imported anywhere or it is read too late.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


def _put_cuda_on_path():
    """
    ⛔ THE REAL FIX, AND IT HAD TO BE MEASURED TWICE TO FIND.

    CTranslate2 (what faster-whisper runs on) resolves cuBLAS and cuDNN by
    NAME, LAZILY, AT FIRST INFERENCE — not at model construction. So:

      · `torch.cuda.is_available()` was True
      · the model reported "ready on cuda"
      · and the first transcribe still died with
        "Library cublas64_12.dll is not found or cannot be loaded"

    ⚠ `os.add_dll_directory()` was tried first and DID NOT WORK: the DLLs were
      registered and the lazy load still missed them. What CTranslate2 actually
      honours is PATH, so the `nvidia/*/bin` directories from the
      `nvidia-cublas-cu12` / `nvidia-cudnn-cu12` wheels go on PATH before any
      import that could trigger the load.
    """
    dirs = []
    try:
        import nvidia
        for root in getattr(nvidia, "__path__", []):
            for sub in os.listdir(root):
                b = os.path.join(root, sub, "bin")
                if os.path.isdir(b):
                    dirs.append(b)
    except Exception:
        pass
    if dirs:
        os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            for d in dirs:
                try:
                    os.add_dll_directory(d)
                except Exception:
                    pass
    return dirs


CUDA_DIRS = _put_cuda_on_path()

HOST = "127.0.0.1"
PORT = int(os.environ.get("VOICE_PORT", "7861"))
# models/ lives at the project root — two levels up from this script.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ⚠ `base` was measured too weak — a phrase like "corset is laced" came back
#   as "Horse it is least" on the reference build. `small` on a modern GPU
#   costs a fraction of a second and is the difference between hearing her
#   and guessing at her.
#
# ⛔ A LOCAL DIRECTORY, NOT A HUB NAME. The HuggingFace cache symlinks its
#   blobs, and creating a symlink on Windows needs a privilege a normal
#   account does not hold. The model is fetched once with
#   `local_dir_use_symlinks=False` into `models/whisper-small` and loaded
#   from that path. No symlink is ever created, so the privilege is never
#   needed. Setting HF_HUB_DISABLE_SYMLINKS=1 above is a belt-and-braces
#   fallback for versions that honour it.
STT_MODEL = os.environ.get(
    "STT_MODEL", os.path.join(ROOT, "models", "whisper-small"))

_stt = None


def stt():
    """
    ⛔ CUDA-FIRST WITH A NAMED CPU FALLBACK. The upstream reference is
      CUDA-or-fail; weird ships to visitors who may not have a modern GPU, so
      a CPU path IS provided — but only after the CUDA attempt logs its exact
      failure. That way a broken CUDA install still surfaces as an error you
      can act on, rather than a silent slow downgrade.
    """
    global _stt
    if _stt is None:
        from faster_whisper import WhisperModel
        try:
            _stt = WhisperModel(STT_MODEL, device="cuda", compute_type="float16")
            print(f"[voice] faster-whisper ready on cuda "
                  f"({len(CUDA_DIRS)} CUDA dir(s) on PATH)", flush=True)
        except Exception as e:
            print(f"[voice] cuda unavailable ({type(e).__name__}: {e}) — "
                  f"falling back to CPU int8", flush=True)
            _stt = WhisperModel(STT_MODEL, device="cpu", compute_type="int8")
            print(f"[voice] faster-whisper ready on cpu (int8, slower)", flush=True)
    return _stt


def transcribe(pcm: np.ndarray, sr: int) -> str:
    audio = pcm.astype(np.float32) / 32768.0
    if sr != 16000:
        audio = np.interp(
            np.linspace(0, audio.size - 1, int(round(audio.size * 16000 / sr))),
            np.arange(audio.size), audio).astype(np.float32)
    segs, _ = stt().transcribe(audio, language="en", beam_size=1, vad_filter=True)
    return " ".join(s.text.strip() for s in segs).strip()


# CORS on every response — matches the image server pattern. The browser is
# the security boundary; the socket stays loopback.
CORS = [
    ("Access-Control-Allow-Origin", "*"),
    ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
    ("Access-Control-Allow-Headers", "Content-Type"),
    ("Access-Control-Max-Age", "86400"),
]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass                                   # quiet

    def _cors(self):
        for k, v in CORS:
            self.send_header(k, v)

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self._cors()
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("content-length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path == "/state":
            return self._send(200, {
                "ok": True,
                "stt_model_dir": STT_MODEL,
                "stt_model_present": os.path.isdir(STT_MODEL) and any(os.scandir(STT_MODEL)),
                "cuda_dirs": len(CUDA_DIRS),
            })
        self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._send(400, {"error": f"bad json: {e}"})
        try:
            if self.path == "/stt":
                sr = int(body.get("sample_rate") or 24000)
                if body.get("pcm_b64"):
                    pcm = np.frombuffer(base64.b64decode(body["pcm_b64"]), dtype=np.int16)
                elif body.get("wav_b64"):
                    with wave.open(io.BytesIO(base64.b64decode(body["wav_b64"]))) as w:
                        sr = w.getframerate()
                        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
                else:
                    return self._send(400, {"error": "no pcm_b64 or wav_b64"})
                if pcm.size == 0:
                    return self._send(400, {"error": "empty audio"})
                return self._send(200, {
                    "text": transcribe(pcm, sr),
                    "seconds": round(pcm.size / sr, 3),
                })
            self._send(404, {"error": "not found"})
        except Exception as e:
            # Loud, named, never a silent empty success.
            self._send(500, {"error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    if not os.path.isdir(STT_MODEL) or not any(os.scandir(STT_MODEL)):
        print(f"  [!] whisper-small model missing at {STT_MODEL}", flush=True)
        print(f"      run scripts/install_voice.bat (or .sh) to download it", flush=True)
        sys.exit(1)
    print(f"""
  LOCAL SPEECH-TO-TEXT
  ---------------------------------------------------
  port      http://{HOST}:{PORT}   (STT via faster-whisper)
  model     {STT_MODEL}
  cuda      {len(CUDA_DIRS)} DLL dir(s) on PATH (CPU fallback available)
  CORS      * (browser-direct from any origin)
  ---------------------------------------------------
""", flush=True)
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
