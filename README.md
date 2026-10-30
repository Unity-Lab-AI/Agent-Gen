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
| Motion | LTX-Video image-to-video, clips chained from each other | 5127 |
| Hub | Node: the conversation loop, sentence splitter, looks and reel | 4646 |
| App | Electron window + supervisor + first-run installer | |

Everything talks over 127.0.0.1. Full design: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Install

Needs Windows 11 and an NVIDIA card with 16 GB. Run `AgentGen-Setup-<version>.exe`. First launch installs what's missing into `%LOCALAPPDATA%\AgentGen`: a Python runtime, PyTorch, the model weights (about 45 GB), a private Ollama and her brain. Nothing touches PATH or the registry. Uninstall from Windows as usual; it asks whether to take that folder with it. The in-app **Uninstall everything** button does the same.

## Run from source

```
git clone <this repo>; cd agent-gen
cd app && npm install && npx electron .
```

A dev box with the lab's Python 3.10 (torch cu118), `sidecars/face/.venv`, the Ollama tray app and `models/` already in place is detected as complete and boots straight in. Missing pieces are offered in the first-run screen. Weights by hand: `python scripts/fetch-models.py`. Build the exe: `npm run dist` in `app/` (output in `dist/`).

## How she works

Say something. Whisper hears it, the brain answers in short spoken lines, each line goes to her voice and her face at once, lips locked to the audio. When she decides to show you something she writes a line the app catches: `[[img: ...]]` for a new look (outfit, body, place) or `[[do: ...]]` for a movement in the look she has. A look is rendered, becomes her face, becomes a clip of her doing it. While nobody is talking to her she keeps filming herself doing whatever she decides to do next, chained from where she left off, so she is never one loop. Talk and the clip in flight is dropped so her lips never wait.

The card is the budget: her face and the video engine can't share it, so new motion renders in short holds while she is idle.

## Who

Unity AI Lab. Four people, six disciplines, open-source, no apology layer. <https://www.unityailab.com>
