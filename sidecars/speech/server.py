#!/usr/bin/env python3
"""Her ears: faster-whisper behind loopback HTTP, with wake-word scoring.

    python sidecars/speech/server.py [--port 5125] [--model small|<folder>] [--device auto|cuda|cpu]

Lineage: VibeRoller bridge/speech-engine.py (server shape) + Unity 18+ voice_server.py (the Windows CUDA
DLL fix and the HuggingFace symlink fix) + C.O.R.A voice/wake_word.py (fuzzy wake phrase).

API (127.0.0.1 only)
  GET  /health                       -> {"ok", "loaded", "device", "model"}
  POST /transcribe                   body: raw audio. Three accepted shapes:
         Content-Type: audio/pcm  + X-Sample-Rate: 16000   int16 little-endian mono PCM
         Content-Type: application/json                    {"pcm_b64", "sample_rate", "language"?}
         anything else                                     a container file (webm / ogg / wav / mp3 bytes)
                                     -> {"text", "language", "seconds", "segments": [{"t0","t1","text"}]}
  POST /wake  {"text", "phrases"?, "threshold"?} -> {"matched", "phrase", "confidence", "remainder"}
The model loads on the first request (or at start with --preload).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))

# HuggingFace symlinks need a privilege a normal Windows account lacks (WinError 1314). Set before any import
# that could pull huggingface_hub in.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import numpy as np   # noqa: E402
import wake_word     # noqa: E402


def put_cuda_on_path():
    """CTranslate2 resolves cuBLAS / cuDNN by NAME, LAZILY, at first inference, and honours PATH rather than
    os.add_dll_directory. Put the nvidia-*-cu12 wheel bin folders on PATH before the first transcribe."""
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
                except OSError:
                    pass
    return dirs


def default_model():
    env = os.environ.get("UNITY_STT_MODEL")
    if env:
        return env
    local = REPO / "models" / "whisper-small"
    return str(local) if (local / "model.bin").exists() else "small"


ap = argparse.ArgumentParser(description="Unity speech sidecar")
ap.add_argument("--port", type=int, default=int(os.environ.get("UNITY_STT_PORT", "5125")))
ap.add_argument("--model", default=default_model())
ap.add_argument("--device", default=os.environ.get("UNITY_STT_DEVICE", "auto"), choices=["auto", "cuda", "cpu"])
ap.add_argument("--preload", action="store_true")
ARGS = ap.parse_args()

_lock = threading.Lock()
_state = {"model": None, "device": None, "load_error": None}


def load():
    if _state["model"] is not None:
        return _state["model"]
    from faster_whisper import WhisperModel
    dev = ARGS.device
    if dev == "auto":
        try:
            import torch
            dev = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            dev = "cpu"
    if dev == "cuda":
        put_cuda_on_path()
    t0 = time.time()
    _state["model"] = WhisperModel(ARGS.model, device=dev, compute_type="float16" if dev == "cuda" else "int8")
    _state["device"] = dev
    print(time.strftime("%H:%M:%S"), "speech: loaded", ARGS.model, "on", dev, "in %.1fs" % (time.time() - t0), flush=True)
    return _state["model"]


def pcm_to_float(raw: bytes, rate: int) -> np.ndarray:
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if rate != 16000 and len(a) > 1:
        n = int(round(len(a) * 16000 / rate))
        a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)
    return a


def transcribe(source, language=None):
    t0 = time.time()
    with _lock:
        segments, info = load().transcribe(source, beam_size=5, vad_filter=True, language=language or None)
        segs = [{"t0": round(s.start, 2), "t1": round(s.end, 2), "text": s.text.strip()} for s in segments]
    text = " ".join(s["text"] for s in segs).strip()
    return {"text": text, "language": getattr(info, "language", None), "seconds": round(time.time() - t0, 2), "segments": segs}


class Handler(BaseHTTPRequestHandler):
    server_version = "unity-speech/1.0"

    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Sample-Rate")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            return self._json({"ok": True, "loaded": _state["model"] is not None, "device": _state["device"] or ARGS.device,
                               "model": os.path.basename(ARGS.model.rstrip("/\\")), "load_error": _state["load_error"]})
        self._json({"error": "unknown endpoint"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 25 * 1024 * 1024:
            return self._json({"error": "send 1 byte to 25 MB"}, 422)
        body = self.rfile.read(n)
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        try:
            if path == "/wake":
                req = json.loads(body or b"{}")
                return self._json(wake_word.match(str(req.get("text", "")), tuple(req.get("phrases") or wake_word.DEFAULT_PHRASES),
                                                  float(req.get("threshold", 0.78))))
            if path != "/transcribe":
                return self._json({"error": "unknown endpoint"}, 404)
            if ctype == "audio/pcm":
                rate = int(self.headers.get("X-Sample-Rate") or 16000)
                return self._json(transcribe(pcm_to_float(body, rate), self.headers.get("X-Language")))
            if ctype == "application/json":
                req = json.loads(body)
                raw = base64.b64decode(req["pcm_b64"])
                return self._json(transcribe(pcm_to_float(raw, int(req.get("sample_rate", 16000))), req.get("language")))
            fd, tmp = tempfile.mkstemp(suffix=".audio")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(body)
                return self._json(transcribe(tmp, self.headers.get("X-Language")))
            finally:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        except Exception as e:
            _state["load_error"] = _state["load_error"] if _state["model"] is not None else "%s: %s" % (type(e).__name__, str(e)[:200])
            self._json({"error": "%s: %s" % (type(e).__name__, str(e)[:300])}, 500)


if __name__ == "__main__":
    if ARGS.preload:
        load()
    srv = ThreadingHTTPServer(("127.0.0.1", ARGS.port), Handler)
    print(time.strftime("%H:%M:%S"), "speech: serving on 127.0.0.1:%d model=%s device=%s" % (ARGS.port, os.path.basename(ARGS.model), ARGS.device), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
