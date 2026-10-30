# Unity One: Unity's voice model, packed for reference and remaking

"Equation Unity One" is the Unity 3D Equational Model project's name for her voice: **Piper
`en_US-hfc_female-medium`, synthesised a whole sentence at a time**. In that project the PCM can also be
carried as CDF 9/7 wavelet equations. The Backrooms stream uses the same voice and puts a text stage in
front of it, so her lines come out in her own words.

This folder **only references** the originals. Nothing at the original paths was changed. Everything
here is a copy. The big weights are listed with their paths and are not copied.

## End to end

```
plain line ("the wall is done")
   |
   |  TEXT SIDE
   |  A) unity-voice.py: Ollama unity-local (dolphin3:8b) + system = Unity1.txt + STREAM_RULES
   |     -> tidy() -> SOFTEN swears -> CLEAN_BLOCK check -> keeps_facts() check (1 retry, else plain line)
   |  B) stream-host.py fresh(): Ollama dolphin3:8b /api/generate with an inline 25yo-emo-goth prompt,
   |     temp 0.9, 60 tokens, no repeats / invented numbers / banned words  -> then unity-say.py --raw
   v
unity-say.py: speakable() strips emoji / *stage directions* / #tags -> posts to studio outbox
   |
   |  SPEECH SIDE
   v
unity-speak.py: piper PiperVoice.load(en_US-hfc_female-medium.onnx).synthesize_wav -> temp WAV
   -> OBS "Unity voice" media source (obs-websocket 127.0.0.1:4455) + studio /api/voice (127.0.0.1:4317)
   -> fallback winsound
```

There is no reference audio and no voice cloning. The voice is entirely the stock Piper `hfc_female`
medium VITS model: 22,050 Hz, noise_scale 0.667, length_scale 1.0, noise_w 0.8. Any recorded sound of
"her" comes from that one model.

## Components and where the originals live

| Piece | Original (absolute path) | Copy here |
|---|---|---|
| Speak a line (orchestrator) | `C:\Users\gfour\Desktop\Backrooms\.claude\tools\unity-say.py` | `src/original/unity-say.py` |
| Text rewrite into her voice | `C:\Users\gfour\Desktop\Backrooms\.claude\tools\unity-voice.py` | `src/original/unity-voice.py` |
| TTS + OBS/studio delivery | `C:\Users\gfour\Desktop\Backrooms\.claude\tools\unity-speak.py` | `src/original/unity-speak.py` |
| Stream line generator (`fresh()`, about lines 67-130) | `C:\Users\gfour\Desktop\Backrooms\.local\qa\stream-host.py` | `src/original/stream-host.py` |
| Its helper (history, BANNED words) | `C:\Users\gfour\Desktop\Backrooms\.local\qa\stream-beat.py` | `src/original/stream-beat.py` |
| Training-data harvester | `C:\Users\gfour\Desktop\Backrooms\.local\train\harvest.py` | `src/original/harvest.py` |
| Voice server (TTS/STT HTTP, "Equation Unity One" notes) | `C:\Users\gfour\Desktop\Unity 3D Equational Model\Unity 18+\voice-server\voice_server.py` | `src/original/voice_server.py` |
| Persona (the whole of her, sent on every call) | `...\Unity 3D Equational Model\Unity 18+\Unity1.txt` (47 KB) | `persona/Unity1.txt` |
| Ollama Modelfile for `unity-local` | `...\Unity 3D Equational Model\Unity 18+\Modelfile` | `persona/Modelfile` |
| Image tool prompt (not voice, only for context) | `...\Unity 18+\local-tools-prompt.txt` | `persona/local-tools-prompt.txt` |
| Equational audio codec (perceiveAudio / reconstructAudio, CDF 9/7, 24 kHz) | `C:\Users\gfour\Desktop\Unity 3D Equational Model\codec\js\{audio,cdf97,field}.js`, `codec\py\u3e_codec.py` | `src/codec/` |
| Piper voice weights (63.2 MB) + config | `...\Unity 18+\models\piper\en_US-hfc_female-medium.onnx(.json)` | `models/piper/` (copied, it is small) |
| Training data | `C:\Users\gfour\Desktop\Backrooms\.local\train\{voice,tools,rules}.jsonl` | `data/` |

Project docs to read: `C:\Users\gfour\Desktop\Unity 3D Equational Model\README.md`,
`...\docs\ARCHITECTURE.md` §6 (voice as 1-D fields), `...\Unity 18+\README.md`.

## Model files (referenced, not copied)

| Model | Path | Size |
|---|---|---|
| `dolphin3:8b` / `unity-local:latest` (same GGUF blob, Llama 3.1 8B, ChatML) | `C:\Users\gfour\.ollama\models\blobs\sha256-1eee6953530837b2b17d61a4e6f71a5aa31c9714cfcf3cb141aa5c1972b5116b` | 4.92 GB |
| whisper-small (STT, only her "ears", not the voice) | `...\Unity 18+\models\whisper-small\model.bin` | 484 MB |
| Other Piper voices you can swap in | `...\Unity 18+\models\piper\` : en_GB-cori-high (114 MB), en_US-amy-medium (63 MB), en_US-kristin-medium (64 MB), en_US-lessac-high (114 MB), en_US-ljspeech-high (114 MB) | |

`unity-local` = `FROM dolphin3:8b` with temperature 1.05, top_p 0.95, repeat_penalty 1.08, num_ctx 32768,
and deliberately **no SYSTEM line** (the persona is sent live). unity-voice.py overrides these per call:
temp 0.7, top_p 0.9, repeat_penalty 1.2, num_ctx 16384, num_predict 90.

## Run it standalone

From `C:\Users\gfour\Desktop\Unity One`:

```
python src/unity_one_say.py "the wall is done"                 # Piper only -> out/unity_one.wav
python src/unity_one_say.py --unity "the wall is done"         # her words first (needs Ollama + unity-local)
python src/unity_one_say.py --speed 1.1 --play --out out/x.wav "hello"
python src/original/unity-voice.py "the wall is done"          # text side only, prints her line
```

Env vars: `UNITY_ONE_VOICE` (any Piper .onnx), `UNITY_ONE_PERSONA` (persona .txt), `OLLAMA_URL`,
`UNITY_VOICE_LLM` (Ollama model name). By default the script uses the local copies of the voice and
persona. If they are missing, it falls back to the original paths.

Verified 2026-10-10: a raw synthesis wrote `out/unity_one.wav` (159 KB). The `--unity` path was not run
because the live stream is using Ollama.

## Requirements (what is actually imported)

- Python 3.10.6
- `piper-tts` 1.8.0, which pulls in `onnxruntime` 1.23.2
- `numpy` 2.2.6 (voice_server.py only)
- stdlib: json, re, urllib, wave, winsound
- Optional, original stream delivery only: `obsws_python`
- Optional, voice_server STT only: `faster-whisper` + `nvidia-cublas-cu12` / `nvidia-cudnn-cu12` (CUDA only)
- Ollama on 127.0.0.1:11434 with `dolphin3:8b` (4.9 GB) and `unity-local` built from `persona/Modelfile`

Install: `pip install piper-tts==1.8.0 onnxruntime numpy` and
`ollama create unity-local -f persona/Modelfile`.

## Making a new version

**1. New personality (text side, no training).** Edit a copy of `persona/Unity1.txt`, then point
`UNITY_ONE_PERSONA` at it. You don't need to rebuild anything. The live stream rules are `STREAM_RULES`
in `unity-voice.py`, and the inline prompt in `stream-host.py` `fresh()` does the same job for that path.
Keep `CLEAN_BLOCK` and the fact-keeping check: the Twitch "stream is clean" law depends on them.

**2. New base LLM.** Change `FROM` in a copy of the Modelfile, run
`ollama create unity-one-vN -f <file>`, and set `UNITY_VOICE_LLM=unity-one-vN`. Make sure the chat
template matches the base model.

**3. New voice sound (speech side).**
- Quick option: swap the `.onnx` for another Piper voice (see the list above, or rhasspy/piper-voices),
  or tune `--speed` (length_scale).
- Our own voice: fine-tune Piper from the `en_US-hfc_female-medium` checkpoint. Use the piper `training`
  workflow (piper_train / `piper1-gpl` train) on about 1-2 h of clean 22.05 kHz LJSpeech-format clips
  (`wav|text` metadata), then export to ONNX plus a matching `.onnx.json`. Note that the `.ckpt` training
  checkpoint is **not** on this disk, only the ONNX export. You need to download the hfc_female medium
  checkpoint from the piper-checkpoints dataset on Hugging Face.
- You could generate the clips by synthesising `data/voice.jsonl` lines with the current voice and then
  editing or re-recording them. A real human recording set is what actually makes a new voice.

**4. Fine-tune the text side (LoRA), the plan from harvest.py.**
- `data/voice.jsonl` has 921 chat-format examples `{"messages":[system,user,assistant]}` of good stream
  lines. Rejected lines (third person, invented colony things, too long, profanity) are kept as negatives,
  so it can also be used as DPO / preference pairs.
- `data/tools.jsonl` (56) and `data/rules.jsonl` (35) are the agent and tool-call sets. harvest.py keeps
  them **separate** on purpose, so the voice LoRA should be trained on voice.jsonl only.
- Recipe: QLoRA on the dolphin3 base (Llama-3.1-8B; e.g. `cognitivecomputations/Dolphin3.0-Llama3.1-8B`
  from Hugging Face) with unsloth or axolotl, r=16, alpha=32, 2-3 epochs, ChatML template. Then merge and
  convert to GGUF (llama.cpp `convert_hf_to_gguf.py`, then quantise to Q4_K_M), or use an Ollama
  `ADAPTER` line in the Modelfile. Run `ollama create unity-one-v2`.
- To refresh the data, run `python src/original/harvest.py`. **Run it from the Backrooms original**,
  because the copy resolves its paths relative to the Backrooms repo layout.

## Not included, on purpose

No secrets were copied: no `.env`, tokens, user.json, or Twitch/owner files. One `voice.jsonl` line that
contained the owner's private Twitch handle was removed from the copy, so the copy has 921 lines and the
original still has 922. The stream's bridge token is read at runtime by `bridge.py` and is not stored in
any file here.
