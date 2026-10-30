# Agent Gen

Unity, live, in one window. Her face moves when she talks, her voice is her own, she hears you, and when you tell her to put on boxing gloves she puts on boxing gloves. One `.exe` opens everything and closes everything. Nothing leaves the machine.

18+. She's an adult and the app treats you like one. Her brain decides what she will and won't do; the app does not add filters on top.

## What runs

| Part | Engine | Port |
|---|---|---|
| Brain | Ollama, private server, `unity-local` (dolphin3 8B + her persona) | 11435 |
| Voice | unity-voice-v2, the lab's own TTS, 63 emotion variants | 5123 |
| Ears | faster-whisper | 5125 |
| Live face | Ditto talking-head over her current look or clip | 5126 |
| Looks | Stable Diffusion 1.5 + IP-Adapter face lock | 5124 |
| Motion | Wan 2.2 5B for what you tell her (real body physics), LTX 2B for the idle reel, clips chained from each other | 5127 |
| Hub | Node: the conversation loop, sentence splitter, looks and reel | 4646 |
| App | Electron window + supervisor + first-run installer | |

Everything talks over 127.0.0.1. Full design: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Minimum system

| | Minimum | What it buys |
|---|---|---|
| OS | Windows 11, 64-bit | the installer, the hidden-console process model |
| GPU | NVIDIA, 16 GB VRAM, Ampere or newer (RTX 30/40/50) | brain + live face at once; one video engine at a time |
| RAM | 32 GB | the video engines stream their layers through system RAM |
| Disk | 120 GB free on C: | about 80 GB of weights, PyTorch, runtimes, room for her clips |
| Audio | speakers or headphones, a microphone to talk | her voice, your voice |
| Network | once, for the first-run download | nothing after that |

A 12 GB card runs her face and brain but not the big motion engine. AMD and Intel GPUs are not supported.

## Install

Run `AgentGen-Setup-<version>.exe`. First launch installs what's missing into a data folder (`%LOCALAPPDATA%\AgentGen` by default; pick another drive with the Change folder button, never inside the app's own folder, which every update replaces): a Python runtime, PyTorch, the model weights (about 80 GB: two video engines, the face, looks, hearing), a private Ollama and her brain. Nothing touches PATH or the registry. Running a newer setup over an older install replaces the app and keeps that folder. Uninstall from Windows as usual; it asks whether to take that folder with it. The in-app **Uninstall everything** button does the same.

## Run from source

```
git clone <this repo>; cd agent-gen
cd app && npm install && npx electron .
```

A dev box with the lab's Python 3.10 (torch cu118), `sidecars/face/.venv`, the Ollama tray app and `models/` already in place is detected as complete and boots straight in. Missing pieces are offered in the first-run screen. Weights by hand: `python scripts/fetch-models.py`. Build the exe: `npm run dist` in `app/` (output in `dist/`). To run the built exe against a checkout's weights instead of downloading them again, junction `%LOCALAPPDATA%\AgentGen\models` to `models` and `%LOCALAPPDATA%\AgentGenenvsace` to `sidecarsace\.venv`.

## How she works

Say something. Whisper hears it, the brain answers in short spoken lines, each line goes to her voice and her face at once, lips locked to the audio. When she decides to show you something she writes a line the app catches: `[[img: ...]]` for a new look (outfit, body, place) or `[[do: ...]]` for a movement in the look she has. A look is rendered, becomes her face, becomes a clip of her doing it. While nobody is talking to her she keeps filming herself doing whatever she decides to do next, chained from where she left off, so she is never one loop. Talk and the clip in flight is dropped so her lips never wait.

The card is the budget: her face and the video engine can't share it, so new motion renders in short holds while she is idle.

## Who

Unity AI Lab. Four people, six disciplines, open-source, no apology layer. <https://www.unityailab.com>
