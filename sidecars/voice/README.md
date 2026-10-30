# sidecars/voice — her voice, with timing

Wraps the trained unity-voice-v2 pair (vendored from Backrooms, weights in `models/unity-voice-v2/`) and adds
what the face needs: the per-phoneme durations the acoustic model predicts, turned into a viseme timeline.

```
"C:\Program Files\Python310\python.exe" sidecars\voice\server.py          # Windows, the lab's torch+misaki install
python3 sidecars/voice/server.py --port 5123 --device cuda
```

| Call | Returns |
|---|---|
| `GET /health` | device, model dir, number of recorded delivery pairs |
| `GET /support` | the 63 (emotion, speech act) rows with intensity and pace windows |
| `POST /phonemize {"text"}` | sanitised text and misaki tokens |
| `POST /say {...}` | `audio/wav`, 24 kHz PCM16 (drop-in for the old server) |
| `POST /say_timed {...}` | JSON: `wav_b64`, `phones[{p,t0,t1}]`, `visemes[{v,t0,t1,open}]`, `delivery`, `spoken` |

Body fields: `text`, `emotion`, `speech_act`, `intensity`, `pace`, `length_scale`, `strict`, `sanitize`.

Emotions: neutral, warm, happy, amused, excited, sad, concerned, frustrated, surprised.
Speech acts: statement, yes_no_question, wh_question, exclamation, instruction, reassurance, aside.

Behaviour that differs from the Backrooms server, on purpose:
- Unsupported deliveries are mapped to the nearest recorded one and the mapping is reported in `delivery.notes`
  (aliases like `angry` → `frustrated`, pace clamped into the pair's window). `"strict": true` restores the 422.
- Text is sanitised with `voice_text()` (space `,` `.` `?` only) before synthesis. `"sanitize": false` bypasses it.

Never edit anything under `models/unity-voice-v2/`: `voice-meta.json` binds those files by hash and the voice
refuses to load if they change.
