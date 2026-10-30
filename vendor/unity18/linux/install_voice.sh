#!/usr/bin/env bash
# ============================================================================
#  install_voice.sh — her voice and her ears, one time.
#
#  Installs piper (text to speech) and faster-whisper (speech to text), then
#  downloads the two models they need. Nothing is downloaded at speak time
#  afterwards, and nothing is ever sent off this machine.
#
#  ⛔ faster-whisper does NOT use torch's CUDA. It runs on CTranslate2, which
#     resolves cuBLAS/cuDNN by name at first inference — a machine with working
#     torch still fails with "libcublas.so ... not found". The nvidia-* wheels
#     provide them and voice_server.py puts their lib folders on the path.
#
#  ⚠ The HuggingFace cache symlinks its blobs. That is fine on Linux, but the
#    model is fetched into a plain folder anyway so both platforms load it by
#    the same path and there is one code path rather than two.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

echo
echo "  UNITY — voice setup (one time)"
echo "  ---------------------------------------------"
echo "  Downloads about 550MB: a voice and a listener."
echo

command -v python3 >/dev/null || { echo "  [!] python3 is not installed"; exit 1; }

echo "  [*] installing piper + faster-whisper..."
python3 -m pip install --upgrade piper-tts faster-whisper

echo "  [*] installing CUDA runtime libraries for the listener..."
# ⛔ There is deliberately no CPU fallback in the voice server: a silent CPU
#    downgrade turns a broken install into mysterious latency months later.
python3 -m pip install --upgrade nvidia-cublas-cu12 nvidia-cudnn-cu12

mkdir -p models/piper
if [ ! -f models/piper/en_US-hfc_female-medium.onnx ]; then
  echo "  [*] downloading her voice (~63MB)..."
  base="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium"
  curl -L --fail -o models/piper/en_US-hfc_female-medium.onnx      "$base/en_US-hfc_female-medium.onnx"
  curl -L --fail -o models/piper/en_US-hfc_female-medium.onnx.json "$base/en_US-hfc_female-medium.onnx.json"
else
  echo "  [*] her voice is already here."
fi

if [ ! -f models/whisper-small/model.bin ]; then
  echo "  [*] downloading the listener (~480MB)..."
  python3 -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-small', local_dir='models/whisper-small', local_dir_use_symlinks=False)"
else
  echo "  [*] the listener is already here."
fi

echo
echo "  [*] voice setup complete."
echo
