#!/usr/bin/env bash
# Offline smoke test for her face: Ditto renders .run/say.wav onto the portrait -> .run/ditto-test.mp4
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${FACE_PY:-sidecars/face/.venv/bin/python}"; [ -x "$PY" ] || PY="sidecars/face/.venv/Scripts/python.exe"
[ -f .run/say.wav ] || curl -s -X POST http://127.0.0.1:5123/say -H 'Content-Type: application/json' \
  -d '{"text":"Hey you. I can see you now, can you see me? Good.","emotion":"amused","intensity":0.5}' -o .run/say.wav
R="$(pwd)"
( cd third_party/ditto-talkinghead && "$R/$PY" inference.py --data_root "$R/models/ditto/ditto_pytorch" \
    --cfg_pkl "$R/models/ditto/ditto_cfg/v0.4_hubert_cfg_pytorch.pkl" --audio_path "$R/.run/say.wav" \
    --source_path "$R/assets/portrait/unity-likeness.png" --output_path "$R/.run/ditto-test.mp4" )
# Ditto shells out to a system ffmpeg for the audio mux; use the one bundled with imageio-ffmpeg instead
if [ ! -f .run/ditto-test.mp4 ] && [ -f .run/ditto-test.mp4.tmp.mp4 ]; then
  FF="$("$PY" -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
  "$FF" -loglevel error -y -i .run/ditto-test.mp4.tmp.mp4 -i .run/say.wav -map 0:v -map 1:a -c:v copy -c:a aac .run/ditto-test.mp4
fi
ls -la .run/ditto-test.mp4
