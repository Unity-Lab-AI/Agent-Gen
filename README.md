# Agent Gen

## ⬇️ [Releases — download the latest `AgentGen-Setup.exe`](https://github.com/Unity-Lab-AI/Agent-Gen/releases/latest)

**Current: [v0.5.31](https://github.com/Unity-Lab-AI/Agent-Gen/releases/tag/v0.5.31)** · [all releases, newest first](https://github.com/Unity-Lab-AI/Agent-Gen/releases) · mirror: [git.unityailab.com releases](https://git.unityailab.com/GFourteen/Agent-Gen/releases)

Unity, live, in one window. Her face moves when she talks, her voice is her own, she hears you, and when you tell her to put on boxing gloves she puts on boxing gloves. One `.exe` opens everything and closes everything. Nothing leaves the machine.

18+. She's an adult and the app treats you like one. Her brain decides what she will and won't do; the app does not add filters on top.

## What runs

| Part | Engine | Port |
|---|---|---|
| Brain | Ollama, private server, `unity-local` (dolphin3 8B + her persona) | 11435 |
| Voice | unity-voice-v2, the lab's own TTS, 63 emotion variants | 5123 |
| Ears | faster-whisper | 5125 |
| Eyes | `qwen3-vl:4b` on the same Ollama: describes your camera and screen | 11435 |
| Live face | Ditto talking-head over her current look or clip | 5126 |
| Looks | Stable Diffusion 1.5 + IP-Adapter face lock | 5124 |
| Motion | Wan 2.2 TI2V-5B at 480x832 for everything she does, each clip from her clean look | 5127 |
| Hub | Node: the conversation loop, sentence splitter, looks and reel | 4646 |
| App | Electron window + supervisor + first-run installer | |

Everything talks over 127.0.0.1. Full design: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Minimum system

| | Minimum | What it buys |
|---|---|---|
| OS | Windows 11, 64-bit | the installer, the hidden-console process model |
| GPU | NVIDIA, 16 GB VRAM, Ampere or newer (RTX 30/40/50) | brain + live face at once; one video engine at a time |
| RAM | 32 GB | the video engines stream their layers through system RAM |
| Storage | 100 GB free for the install folder (any drive) | about 80 GB of weights, PyTorch, runtimes, plus room for her looks and clips |
| Audio | speakers or headphones, a microphone to talk | her voice, your voice |
| Network | once, for the first-run download | nothing after that |

A 12 GB card runs her face and brain but not the big motion engine. AMD and Intel GPUs are not supported.

## Install

Run `AgentGen-Setup-<version>.exe`. Pick the install folder on a drive with room (D: if C: is tight); everything lives in that one folder. First launch installs what's missing into its `data` subfolder: a Python runtime, PyTorch, the model weights (about 80 GB: two video engines, the face, looks, hearing), a private Ollama and her brain. Nothing touches PATH or the registry. Running a newer setup over an older install asks: update (replaces the app, keeps `data`), uninstall everything, or cancel. Uninstall from Windows as usual; it asks whether to take that folder with it. The in-app **Uninstall everything** button does the same.

## Run from source

```
git clone <this repo>; cd agent-gen
cd app && npm install && npx electron .
```

A dev box with the lab's Python 3.10 (torch cu118), `sidecars/face/.venv`, the Ollama tray app and `models/` already in place is detected as complete and boots straight in. Missing pieces are offered in the first-run screen. Weights by hand: `python scripts/fetch-models.py`. Build the exe: `npm run dist` in `app/` (output in `dist/`). To run the built exe against a checkout's weights instead of downloading them again, junction `<install>\data\models` to `models` and `<install>\data\venvs\face` to `sidecars\face\.venv`.

## How she works

Say something. Whisper hears it, the brain answers in short spoken lines, each line goes to her voice and her face at once, lips locked to the audio. When she decides to show you something she writes a line the app catches: `[[img: ...]]` for a new look of herself (outfit, body, place, or someone else entirely: tell her she is a 40 year old man or a lion and she is), `[[do: ...]]` for a movement in the look she has, `[[pic: ...]]` for a picture of anything else, shown in the chat. A look is rendered, becomes her face (a look with no human face plays as it is), then a clip of her doing it. Say "that's you now" after a picture and that picture becomes her.

Left alone she does her own thing: she picks what to do, films it, and keeps going. While a clip renders she loops what she was just doing instead of freezing. Talk to her and any render in flight is dropped, so she answers right away and the card is never shared between her brain and the video engine.

Tell her to write or draw on herself ("write BRAT on your thigh in purple paint", "a heart on your chest in lipstick") and it lands on that part of her, skin or clothes, sized to fit; a part that is not in the picture is not guessed at.

**Show camera** / **Show screen** (footer) let her see you and your screen: one still of each goes with every message you say or type, so she can react to what you're wearing or what's on your screen. Nothing is streamed or saved.

**Shut down** (footer) unloads her from the GPU, stops every Agent Gen process and closes the app. **Storage** (footer) shows where her looks, clips, logs and conversations live and clears any of them, or resets her to fresh without reinstalling.

## Privacy

Nothing leaves the machine. Everything runs over `127.0.0.1`; no telemetry, no cloud, no update checks. First-run setup downloads runtimes and model weights, and that is the only time she touches the internet. Details: [`PRIVACY.md`](PRIVACY.md).

## License

MIT, Unity AI Lab: [`LICENSE`](LICENSE). The software and model weights she installs keep their own licenses: [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md).

## Who

Unity AI Lab. Four people, six disciplines, open-source, no apology layer. <https://www.unityailab.com>
