# sidecars/speech — her ears

faster-whisper on loopback, plus wake-word scoring on the transcript.

```
"C:\Program Files\Python310\python.exe" sidecars\speech\server.py --preload
python3 sidecars/speech/server.py --port 5125 --model small --device auto
```

Model resolution: `--model` / `UNITY_STT_MODEL`, else `models/whisper-small/` if present, else the `small` name
(downloaded on first load). Device `auto` picks CUDA when torch sees it; on Windows the nvidia cu12 wheel bin
folders are put on PATH first, which is the fix CTranslate2 actually honours.

| Call | Body | Returns |
|---|---|---|
| `GET /health` | | loaded, device, model |
| `POST /transcribe` | `audio/pcm` + `X-Sample-Rate` (int16 mono), or JSON `{pcm_b64, sample_rate}`, or a container file | `text`, `language`, `seconds`, `segments` |
| `POST /wake` | `{text, phrases?, threshold?}` | `matched`, `phrase`, `confidence`, `remainder` |

Default wake phrases: unity, hey unity, yo unity, okay unity. The hub only uses them when `WAKE_WORD` is set; in
the normal face-to-face session the VAD endpoint is the trigger and no wake word is required.
