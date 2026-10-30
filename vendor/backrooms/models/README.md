# Unity's models

Every model behind "Unity Plays RimWorld". Each of our folders here is a **complete, usable model**: the weights,
only the code/config needed to run it, and a README on how to use it. Copy a folder anywhere and it works on its
own. How each one was built lives in `training/` (linked below), not here.

The weight files are git-ignored and stay on this PC: `*.gguf`, `*.pt`. The READMEs, code and small config go
to the remotes. Every trained file also has a master copy on the USB drive under
`D:\voice-lab\pod-results\<run>\`. If this folder is ever lost, copy them back from there.

## What runs during a stream

```
 Twitch chat / game events
          │
          ▼
  ┌────────────────┐   tool calls    ┌──────────────┐
  │  unity-brain   │ ──────────────▶ │  RimWorld    │  (RimBridge + RimPLC)
  │  thinks, plays │                 └──────────────┘
  └───────┬────────┘
          │ what to say
          ▼
  ┌────────────────┐  her wording   ┌──────────────┐   audio   ┌─────┐
  │  unity-local   │ ─────────────▶ │ unity-voice  │ ────────▶ │ OBS │ ──▶ Twitch
  │ (also writes   │                │  speaks it   │           └─────┘
  └────────────────┘                └──────────────┘
  realistic-vision  ──▶  her webcam pictures (on demand)
```

| Model | Its job on stream | Made by | File | Loaded as | GPU memory | Status |
|---|---|---|---|---|---|---|
| **unity-brain** | Plays the game (RimBridge tools, RimPLC), answers chat, reads screenshots, decides what to say | Us, 2026-10-12: LoRA on Qwen3.5-9B, 8,481 rows | `unity-brain/unity-brain.gguf` + `unity-brain-vision.gguf` (6.2 GB) | Ollama `unity-brain` on :11434 | ~5.3 GB + context | **Live**, replaced the 10-10 brain |
| **unity-voice** | Her actual speaking voice: turns a line into audio with emotion, laughs included | Us, 2026-10-12: trained from scratch on 4,845 clips | `unity-voice/acoustic.pt` + `vocoder.pt` (165 MB) | `unity-voice/serve.py` on :5123 | ~0.5 GB | **Live** 2026-10-13: the `voice` service in `stream/services.py`, every spoken line, natural pace (length scale 1.0) |
| **unity-local** | Rewrites each line in her own words and personality before she speaks | Us, 2026-10-10: LoRA on Qwen3-8B | `training/models/unity-voice.Q4_K_M.gguf` (5.0 GB) | Ollama `unity-local` on :11435 | ~5 GB | **Rollback only** (not loaded): the brain writes her lines now to fit 16 GB |
| **realistic-vision v5.1** | Draws her webcam pictures, always img2img from her locked likeness | Third party (Stable Diffusion 1.5 fine-tune) | `~\Desktop\Unity 3D Equational Model\Unity 18+\models\realistic-vision-v51.safetensors` | `.claude/tools/unity-face-sd.py` | ≤ ~4 GB while drawing; system RAM otherwise | **Live** |
| unity-player | The old game player before the brain | Us, 2026-10-10: LoRA on Qwen3.6-35B | `training/models/unity-player.Q4_K_M.gguf` (21.7 GB) | Ollama `unity-player` | ran on the CPU | **Retired**, kept for rollback |
| Piper hfc_female | The old voice before her own | Third party (Piper TTS) | `...\Unity 18+\models\piper\en_US-hfc_female-medium.onnx` | `.claude/tools/unity-speak.py` | CPU | **Retired** 2026-10-13: no fallback voice (owner: fallbacks are against the laws) |

The base models Ollama keeps for these (`qwen3.5:9b`, `qwen3:8b`, `qwen3.6:35b`, `dolphin3:8b`) are pulled from the
Ollama registry by `stream/services.py`. They are not stored here.

## The 16 GB budget (RTX 4070 Ti SUPER): measured 2026-10-13

`.local/qa/vram-stress.py` loads every stream model at once and exercises them together.

| Setup | Peak GPU memory (no game, no OBS) | Verdict |
|---|---|---|
| Brain + separate line writer (`unity-local`) + voice + webcam | **15.9 of 16 GB** | Does not fit once RimWorld + OBS (~2-3 GB) are open |
| **Brain writes her lines too** + voice + webcam | **11.3 GB** (5.1 GB free) | **Fits**: the setup in use |

Owner's choice, 2026-10-13: *"Brain writes lines too"* (`training/models/unity-brain/brain-voice-owner.json`). The line writer
stays installed for rollback but is not loaded. Every brain request must use the same 32K context, or Ollama reloads
the model with its huge default and it jumps to ~14 GB; the stream already sets `UNITY_VOICE_NUM_CTX=32768`.

## Rebuilding a model

- **Brain:** `training/BRAIN_PLAN.md` (data → pod → pull → `training/apply.py`). How this one was built, its
  eval and the owner's line-writer choice: `training/models/unity-brain/BUILD.md`.
- **Voice:** `training/voice/pod/LAUNCH_RUNBOOK.md` (script → on-pod recording → screening → training → pull).
  How this one was built: `training/voice/receipts/unity-voice-2026-10-12/BUILD.md`.
- **Before any pod rental:** dry-run the exact start command on one cheap GPU first. The 2026-10-12 launch lost
  about $40-50 to Linux-only setup bugs that a dry run would have caught.
