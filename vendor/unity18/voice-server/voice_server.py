"""
voice_server.py — her voice and her ears, for the development harness.

⛔ It must be OUR voice equations. Equation Unity One: piper hfc_female,
whole-sentence, carried as CDF 9/7 equations.

WHAT THIS IS AND IS NOT
    This serves RAW PCM and RAW TEXT over loopback. It does NOT produce fields.
    The equational half happens in `serve/legacy-adapter.js`, which runs the PCM
    through U3E's own `perceiveAudio()` (1-D CDF 9/7) before anything leaves the
    slot. That split is deliberate: the codec is U3E's and must stay the single
    implementation, so a harness may hand it samples but never its own encoder.

    TTS  piper en_US-hfc_female-medium  ->  int16 PCM
    STT  faster-whisper                 <-  int16 PCM

WHY WHOLE-SENTENCE
    Equation Unity One's finding was that SENTENCE-LEVEL synthesis carries the
    quality and a word-bank concatenation is the fallback, not the target. So
    the whole utterance is synthesised in one pass here and the field is taken
    from that — never assembled from per-word clips.

LOOPBACK ONLY, like the image server beside it. Nothing here binds the LAN.
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

    ⚠ `os.add_dll_directory()` was tried first and DID NOT WORK here: the DLLs
      were registered and the lazy load still missed them. What CTranslate2
      actually honours is PATH, so the `nvidia/*/bin` directories from the
      `nvidia-cublas-cu12` / `nvidia-cudnn-cu12` wheels go on PATH before any
      import that could trigger the load.

    ⛔ There is deliberately NO CPU PATH anywhere in this file. A silent CPU
      downgrade would turn a broken CUDA install into unexplained latency, which
      is precisely the NO FALLBACK THAT HIDES A FAILURE law.
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
PORT = int(os.environ.get("UNITY_VOICE_PORT", "7861"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOICE = os.path.join(ROOT, "models", "piper", "en_US-hfc_female-medium.onnx")

# U3E's audio codec runs at 24 kHz (codec/js/audio.js). Piper's medium voices
# are 22.05 kHz, so the resample happens HERE, once, rather than being a
# mismatch the field silently inherits.
TARGET_SR = 24000

# ⚠ `base` was MEASURED too weak on her reconstructed voice: "corset is laced"
#   came back "Horse it is least". `small` on a 4070 Ti SUPER costs a fraction of
#   a second and is the difference between hearing her and guessing at her.
#
# ⛔ A LOCAL DIRECTORY, NOT A HUB NAME. The HuggingFace cache symlinks its
#   blobs, and creating a symlink on Windows needs a privilege a normal account
#   does not hold — "WinError 1314: A required privilege is not held by the
#   client". ⚠ `HF_HUB_DISABLE_SYMLINKS=1` was tried and is NOT honoured by the
#   installed huggingface_hub, so the model is fetched once with
#   `local_dir_use_symlinks=False` into `models/whisper-small` and loaded from
#   that path. No symlink is ever created, so the privilege is never needed.
STT_MODEL = os.environ.get(
    "UNITY_STT_MODEL", os.path.join(ROOT, "models", "whisper-small"))

_tts = None
_stt = None


def tts():
    global _tts
    if _tts is None:
        from piper import PiperVoice
        if not os.path.exists(VOICE):
            raise RuntimeError(
                f"piper voice missing at {VOICE} — download "
                "en_US-hfc_female-medium.onnx(.json) from rhasspy/piper-voices")
        print(f"[voice] loading piper {os.path.basename(VOICE)} ...", flush=True)
        _tts = PiperVoice.load(VOICE)
    return _tts


def stt():
    """
    ⛔ CUDA OR IT FAILS. One correct architecture, per the NO FALLBACKS law.
      If the GPU cannot be used, that is a real defect in the environment and it
      must arrive as an error naming the fix — never as a quiet CPU downgrade
      that turns a broken install into mysterious latency months later.
    """
    global _stt
    if _stt is None:
        from faster_whisper import WhisperModel
        try:
            _stt = WhisperModel(STT_MODEL, device="cuda", compute_type="float16")
        except Exception as e:
            raise RuntimeError(
                f"STT cannot use the GPU: {type(e).__name__}: {e}. "
                f"CTranslate2 needs cuBLAS/cuDNN — "
                f"`pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`. "
                f"(CUDA dirs on PATH: {len(CUDA_DIRS)})") from e
        print(f"[voice] faster-whisper base ready on cuda "
              f"({len(CUDA_DIRS)} CUDA dir(s) on PATH)", flush=True)
    return _stt


def resample(pcm: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Linear resample. A harness-grade resampler, named as one."""
    if src == dst or pcm.size == 0:
        return pcm
    n = int(round(pcm.size * dst / src))
    x = np.linspace(0.0, pcm.size - 1.0, n, dtype=np.float64)
    return np.interp(x, np.arange(pcm.size, dtype=np.float64), pcm.astype(np.float64)).astype(np.int16)


def synth(text: str):
    """Whole utterance in ONE pass -> int16 PCM at TARGET_SR."""
    v = tts()
    chunks, sr = [], None
    for ch in v.synthesize(text):
        # piper returns AudioChunk objects; take int16 samples whatever the
        # attribute is called in this build rather than assuming one name.
        arr = getattr(ch, "audio_int16_array", None)
        if arr is None:
            raw = getattr(ch, "audio_int16_bytes", None)
            arr = np.frombuffer(raw, dtype=np.int16) if raw is not None else None
        if arr is None:
            continue
        chunks.append(np.asarray(arr, dtype=np.int16))
        sr = sr or getattr(ch, "sample_rate", None)
    if not chunks:
        raise RuntimeError("piper produced no audio")
    pcm = np.concatenate(chunks)
    return resample(pcm, sr or 22050, TARGET_SR), TARGET_SR


def transcribe(pcm: np.ndarray, sr: int) -> str:
    audio = pcm.astype(np.float32) / 32768.0
    if sr != 16000:
        audio = np.interp(
            np.linspace(0, audio.size - 1, int(round(audio.size * 16000 / sr))),
            np.arange(audio.size), audio).astype(np.float32)
    segs, _ = stt().transcribe(audio, language="en", beam_size=1, vad_filter=True)
    return " ".join(s.text.strip() for s in segs).strip()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/state":
            return self._send(200, {
                "ok": True, "tts": os.path.exists(VOICE),
                "voice": os.path.basename(VOICE), "sample_rate": TARGET_SR,
            })
        self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._send(400, {"error": f"bad json: {e}"})
        try:
            if self.path == "/tts":
                text = (body.get("text") or "").strip()
                if not text:
                    return self._send(400, {"error": "no text"})
                pcm, sr = synth(text)
                return self._send(200, {
                    "pcm_b64": base64.b64encode(pcm.tobytes()).decode(),
                    "sample_rate": sr, "samples": int(pcm.size),
                    "seconds": round(pcm.size / sr, 3), "voice": os.path.basename(VOICE),
                })
            if self.path == "/stt":
                sr = int(body.get("sample_rate") or TARGET_SR)
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
    if not os.path.exists(VOICE):
        print(f"  [!] piper voice missing: {VOICE}", flush=True)
        sys.exit(1)
    print(f"[voice] ready on http://{HOST}:{PORT}   (tts piper hfc_female, stt faster-whisper)", flush=True)
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
