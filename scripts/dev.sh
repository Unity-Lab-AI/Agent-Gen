#!/usr/bin/env bash
# Agent Gen dev bring-up (M2): voice sidecar, speech sidecar, hub. Ctrl-C stops all three.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY310:-python3}"
"$PY" sidecars/voice/server.py & V=$!
"$PY" sidecars/speech/server.py --preload & S=$!
( cd hub && [ -d node_modules ] || npm install --no-audit --no-fund )
( cd hub && node server.mjs ) & H=$!
trap 'kill $V $S $H 2>/dev/null' EXIT INT TERM
echo "voice :5123  speech :5125  hub http://127.0.0.1:4646/"
wait
