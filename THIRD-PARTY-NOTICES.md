# Third-party notices

Agent Gen's own code is MIT licensed (see `LICENSE`). It ships or installs the software and model weights below, each under its own license. The model weights are downloaded by first-run setup from their publishers; they are not part of the MIT grant, and their terms (including any use restrictions) apply to you as the person running them.

## Shipped with the app

| Component | License | Notes |
|---|---|---|
| Electron (and Chromium, Node.js) | MIT (Chromium: BSD-3-Clause and others, see `LICENSES.chromium.html` in the install folder) | the app window and the hub runtime |
| `ws` (Node WebSocket library) | MIT | hub |
| Ditto talking-head code (`third_party/ditto-talkinghead`, Ant Group) | Apache-2.0 | live face; its `LICENSE` file ships alongside it |
| unity-voice-v2 (her voice model) | MIT, Unity AI Lab | the lab's own model |

## Installed on first run

| Component | License |
|---|---|
| Python 3.10 (python-build-standalone) | PSF License |
| Ollama | MIT |
| PyTorch, torchaudio | BSD-3-Clause |
| diffusers, transformers, accelerate, huggingface_hub, safetensors | Apache-2.0 |
| faster-whisper | MIT |
| OpenCV | Apache-2.0 |
| NumPy, Pillow, soundfile and other Python packages | their own permissive licenses (see each package's metadata in `data\runtime\python`) |

## Model weights (downloaded on first run)

| Model | Publisher | License |
|---|---|---|
| Ditto talking-head weights | Ant Group (`digital-avatar/ditto-talkinghead`) | Apache-2.0 |
| Wan 2.2 TI2V-5B | Wan-AI (`Wan-AI/Wan2.2-TI2V-5B-Diffusers`) | Apache-2.0 |
| LTX-Video 2B 0.9.8 distilled | Lightricks (`Lightricks/LTX-Video`) | LTX-Video Open Weights License |
| Realistic Vision V5.1 (Stable Diffusion 1.5) | SG161222 | CreativeML OpenRAIL-M |
| Stable Diffusion 1.5 configs | `stable-diffusion-v1-5` | CreativeML OpenRAIL-M |
| IP-Adapter Plus Face (SD 1.5) and image encoder | h94 (`h94/IP-Adapter`) | Apache-2.0 |
| faster-whisper small (Whisper) | Systran / OpenAI | MIT |
| Dolphin 3.0 Llama 3.1 8B (`dolphin3:8b`, base of `unity-local`) | Cognitive Computations, built on Meta Llama 3.1 | Llama 3.1 Community License. Built with Llama. |

The CreativeML OpenRAIL-M and Llama 3.1 licenses include use restrictions that bind whoever runs the models. Read them before you do: they ship with the weights, and the publishers' model pages link them.
