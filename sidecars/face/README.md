# sidecars/face — her face, live

Photoreal talking head from one portrait, driven by the audio she speaks. Operator decision: *"#D photo
realistic photograph like vido"*. Track A renderer: **Ditto** (Ant Group, Apache-2.0): motion-space diffusion
on a LivePortrait-class renderer, built for streaming with low first-frame delay.

```
# one-time
git clone --depth 1 https://github.com/antgroup/ditto-talkinghead third_party/ditto-talkinghead
"C:\Program Files\Python310\python.exe" -m venv --system-site-packages sidecars\face\.venv
sidecars\face\.venv\Scripts\pip install -r sidecars\face\requirements.txt
sidecars\face\.venv\Scripts\python -c "from huggingface_hub import snapshot_download as s; s('digital-avatar/ditto-talkinghead', local_dir='models/ditto')"

# smoke test (offline, writes .run\ditto-test.mp4)
scripts\face-smoke.bat

# live
sidecars\face\.venv\Scripts\python sidecars\face\server.py --backend pytorch --steps 25
```

Open http://127.0.0.1:5126/stream.mjpg in a browser: she idles, blinks and sways. POST audio to `/speak` and she
says it. The hub does this automatically for every sentence and tells the UI how far to delay the audio
(`lead_ms`) so the lips and the sound line up.

| Call | Body | Returns |
|---|---|---|
| `GET /health` | | fps, frames, queue, chunk time, emotion, backend |
| `GET /stream.mjpg` | | 25 fps JPEG stream |
| `GET /frame.jpg` | | latest frame |
| `POST /speak` | `{wav_b64}` or `{pcm_b64, sample_rate}`, optional `emotion` | `queued_s`, `lead_ms` |
| `POST /interrupt` | | drops queued audio |
| `POST /emotion` | `{emotion}` name, class 0..7 or list | class in force |
| `POST /pose` | `{pitch, yaw, roll, sway}` | pose in force |

How it stays live: Ditto's online pipeline wants 6480-sample windows every 200 ms (3 frames context, 5 new,
2 lookahead). A feeder thread supplies that forever, from queued speech when there is any, from silence when
there is not, so the renderer never stops and the face never freezes. Ditto's mp4 writer is swapped for a
frame sink that paces JPEGs out at 25 fps.

Knobs that matter on a 16 GB card shared with the brain and the voice: `--steps` (diffusion steps per motion
clip; Ditto's own online config uses 10, offline 50; 10 is the default here), `--backend trt` once the TensorRT 8.6.1 runtime
is installed (prebuilt Ampere+ engines are in `models/ditto/ditto_trt_Ampere_Plus`, about 3x faster), and
`--jpeg`.

Ditto emotion classes: 0 angry, 1 disgust, 2 fear, 3 happy, 4 neutral, 5 sad, 6 surprise, 7 contempt. The
hub maps her voice emotions onto them (warm → happy+neutral, excited → happy+surprise, frustrated → angry...).

Portrait: `assets/portrait/unity-likeness.png` (the locked likeness from Backrooms, 512×640, frontal). A
smiling alternate is beside it. Nothing in `third_party/` or `models/` is edited; the only shim is a numpy
`blend_images_cy` seeded before import so Ditto's Cython blend does not need a C compiler on Windows.
