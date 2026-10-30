# Pollinations AI — Claude Code CLI Plugin

Generate images, text, audio, and video directly from Claude Code using [Pollinations.ai](https://pollinations.ai).

**Powered by [Pollinations.ai](https://pollinations.ai)** — open AI infrastructure for everyone.

## Features

- **Image Generation** — Flux, GPT Image, Imagen 4, Kontext, and 20+ models
- **Text Generation** — GPT-5, DeepSeek, Claude, Gemini, Mistral, and 50+ models
- **Audio** — Text-to-speech with 35+ voices (ElevenLabs, OpenAI-style)
- **Video** — Veo, Seedance, Wan, and more
- **Transcription** — Whisper and Scribe speech-to-text
- **BYOP Authentication** — Bring Your Own Pollen. Users connect their own Pollinations account via OAuth. Developer pays $0.
- **Style Presets** — Photorealistic, anime, cyberpunk, watercolor, and more with negative prompt support
- **Aspect Ratios** — 1:1, 16:9, 9:16, 4:3, 3:2, 21:9 presets
- **Auto-Play** — Audio auto-plays after generation (toggleable)
- **Viewer** — Open generated files in system default app

## Quick Start

### Install

Copy the `pollinations-ai` folder into your plugins directory, then start Claude Code with:

```bash
claude --plugin-dir path/to/pollinations-ai
```

### Connect Your Account

```
/pollinations-setup
```

This opens your browser to Pollinations. Log in, authorize the app, and your API key is saved automatically. Your pollen credits fund usage — the plugin costs nothing to run.

### Generate

Just ask Claude naturally:

- "Make me an image of a sunset over mountains"
- "Generate a cyberpunk city in 16:9"
- "Talk to DeepSeek about quantum computing"
- "Read this audio file and transcribe it"
- "Generate speech saying hello world"

The AI uses the right tool automatically. No slash commands needed for generation.

## Tools

| Tool | What It Does |
|------|-------------|
| `pollinations_setup` | BYOP OAuth — connect your Pollinations account |
| `pollinations_image` | Generate images with model, style, ratio, and seed options |
| `pollinations_text` | Chat with any Pollinations text model |
| `pollinations_audio` | Text-to-speech with voice selection and auto-play |
| `pollinations_video` | Generate video with duration and aspect ratio |
| `pollinations_transcribe` | Speech-to-text from audio files |
| `pollinations_models` | List all available models by type |
| `pollinations_view` | Open any generated file in system viewer |

## Image Style Presets

Use natural language like "make it photorealistic" or "anime style":

| Style | What It Adds |
|-------|-------------|
| photorealistic | High detail, 8k, sharp focus |
| anime | Cel shaded, vibrant colors |
| oil-painting | Textured canvas, brushstrokes |
| pixel-art | 16-bit retro game style |
| watercolor | Soft edges, flowing colors |
| cinematic | Dramatic lighting, film grain |
| sketch | Pencil, graphite, linework |
| cyberpunk | Neon lights, dark city |

Custom styles can be added to `config/styles.json`.

## Aspect Ratios

| Ratio | Resolution |
|-------|-----------|
| 1:1 | 1024x1024 |
| 16:9 | 1280x720 |
| 9:16 | 720x1280 |
| 4:3 | 1024x768 |
| 3:4 | 768x1024 |
| 3:2 | 1200x800 |
| 2:3 | 800x1200 |
| 21:9 | 1344x576 |

## Voices (TTS)

alloy, echo, fable, onyx, nova, shimmer, ash, ballad, coral, sage, verse, rachel, domi, bella, elli, charlotte, dorothy, sarah, emily, lily, matilda, adam, antoni, arnold, josh, sam, daniel, charlie, james, fin, callum, liam, george, brian, bill

## How BYOP Works

This plugin uses Pollinations' [Bring Your Own Pollen](https://github.com/pollinations/pollinations/blob/main/BRING_YOUR_OWN_POLLEN.md) system:

1. User runs `/pollinations-setup`
2. Browser opens to Pollinations login
3. User authorizes the app
4. API key is captured automatically via localhost redirect
5. Key is saved locally — never transmitted anywhere except Pollinations API endpoints
6. User's own pollen credits fund all requests

**Developer cost: $0.** Users pay for what they use through their own Pollinations account.

## Configuration

Generated files save to `./pollinations-output/` by default.

User settings (API key, preferences) are stored in `.claude/pollinations-user.json` in your project directory — outside the plugin folder so they survive plugin updates.

Default settings can be changed in `config/defaults.json`:
- `default_image_model` — default: "flux"
- `default_text_model` — default: "openai"
- `default_image_width` — default: 1024
- `default_image_height` — default: 1024
- `default_voice` — default: "nova"
- `output_dir` — default: "./pollinations-output"

## Requirements

- Python 3.10+
- `mcp` Python package (auto-installed on first run)
- A [Pollinations.ai](https://pollinations.ai) account with pollen credits

## Support This Project

If you find this plugin useful:

- **Bitcoin:** `1Gdb61fH7CizYBCLys5wpgDR4RNzAgQkoP`
- **PayPal:** [ai-ministries.com/donate](https://ai-ministries.com/donate)

## Credits

Built by **Tolerable (Rev) & I-OBEY AI** at [ai-ministries.com](https://ai-ministries.com).

**Powered by [Pollinations.ai](https://pollinations.ai)** — thank you to Thomas and the Pollinations team for building an open, accessible AI platform and the BYOP system that makes plugins like this possible.

## License

MIT
