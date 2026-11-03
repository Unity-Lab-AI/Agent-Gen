# Privacy

Short version: **nothing you say, type, show or make leaves your computer**, except the words she searches the web for and the pages she opens when she looks something up (below). No account, no telemetry, no analytics, no cloud AI, no update checks.

## While she runs

Every part of Agent Gen runs on your own machine and talks to the others only over `127.0.0.1` (loopback). Nothing listens on your network.

| What | Where it goes |
|---|---|
| Your voice (mic) | transcribed locally by faster-whisper; the audio is not saved |
| What you type or say | her local brain (Ollama on `127.0.0.1:11435`); kept in memory for the conversation only |
| Her replies and voice | made locally, played on your speakers |
| Her looks and pictures | rendered locally, saved in `<install folder>\data\run\looks` |
| Her clips | rendered locally, saved in `<install folder>\data\run\clips` |
| Logs | `<install folder>\data\logs` |
| Window cache | `%APPDATA%\Agent Gen` |

Her engines start with Hugging Face offline mode on (`HF_HUB_OFFLINE`), so no model library checks huggingface.co for updates, and the app window's spellchecker is off, so Chromium does not fetch dictionaries.

Conversations are never written to disk by the app. **Storage → Reset to fresh** in the app clears her looks, clips, conversations, window cache and logs at any time, without reinstalling.

## Her web search

When you ask about the weather, news, scores or something to look up (or her brain writes a search line), the hub sends **those search words** to DuckDuckGo (and Bing if DuckDuckGo returns nothing), or fetches **the page address** she asked for. Asked about the weather, she asks ip-api.com for this computer's rough location (city, from your IP) unless you name a place, and Open-Meteo for the weather there. That is a normal web request from your computer: those sites see your IP address and the query, nothing else (no conversation, no pictures, no camera). Every search and page she opens is listed in the chat. Local and private-network addresses are never fetched. To turn it off entirely, start Agent Gen with the environment variable `WEB=0`.

## First-run setup

The first launch downloads what she runs on. These are plain downloads: nothing about you is sent, only the requests for the files.

| What | From |
|---|---|
| Python 3.10 runtime | GitHub releases (`astral-sh/python-build-standalone`) |
| Ollama server | GitHub releases (`ollama/ollama`) |
| PyTorch | `download.pytorch.org` |
| Python packages | PyPI |
| Model weights (Ditto, Wan 2.2, LTX-Video, Realistic Vision 5.1, IP-Adapter, faster-whisper) | Hugging Face |
| Her brain's base model (`dolphin3:8b`) | the Ollama registry |

After setup she needs no internet at all, except for her web search above.

## Uninstall

The uninstaller (or **Uninstall everything** in the app) can remove the `data` folder with every runtime, model, render and log in it.
