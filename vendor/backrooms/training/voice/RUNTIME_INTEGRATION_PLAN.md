# A2 runtime integration plan

Prepared 2026-10-11 by source inspection. **Plan only; live speech is still Piper.** No live code, service, OBS configuration, game files or models were changed for this document. No trained A2 student exists, and neither training nor deployment is authorized. This plan closes a preparation design gap; implementation and runtime acceptance remain open in [the working TODO](../../docs/TODO.md).

## Read first

- [Current handoff](../../docs/NOW.md), [voice plan](VOICE_PLAN.md) and [preparation review](../../docs/implementation/VOICE_PRESPEND_REVIEW_2026-10-11.md).
- [Selected identity](SELECTED_VOICE.json), [approved source routing](SOURCE_DELIVERY_POLICY.json), [reference profiles](REFERENCE_PROFILES.json) and [source decision receipt](receipts/source-auditions.json).
- [Student source readiness](../../docs/implementation/evidence/voice-prespend-2026-10-11/architecture-readiness.md), [independent listening plan](EVALUATION_PLAN.md), [quality gate](VOICE_QUALITY_GATE.json) and [gate validator](quality_gate.py).

The fixed identity is `unity-a2-low-warm-alto-v1`: original A2's comfortable low, warm adult American register. Ordinary conversation should feel familiar and relaxed. Happy, amused, concerned and other deliveries should follow the meaning of the words. No pitch maximization, time stretching, sarcastic B2, cartoon D1 or rejected Cosy `1-neutral` substitution. Qwen/Cosy are source preparation tools; the intended live synthesizer is our own acoustic/vocoder pair.

**Later owner refinement, 2026-10-11:** expand source material to at least 5,000 varied recordings and several speech hours before considering a pod. Longest training replies are three to five medium sentences. Longer live pages remain allowed: an open-ended logical reply streams bounded paragraph subturns with backpressure/cancellation. The existing `Voice.say` bounds remain low-level call bounds; they are not a 120-second cap on the entire logical message. See [the source throughput/expansion plan](SOURCE_THROUGHPUT_PLAN.md).

## 1. Actual current call chain

Paths and line references below describe the files inspected at this checkpoint, not an observed running-service trace.

| Existing file | Current interface and responsibility |
| --- | --- |
| [.claude/agents/rimworld-player.md](../../.claude/agents/rimworld-player.md), lines 19–26 | Documents `python .claude/tools/unity-say.py "<line>"` for narration, the Persona Studio window and chat watcher. |
| [.claude/tools/unity-say.py](../../.claude/tools/unity-say.py), lines 1–7, 37–67 | Joins CLI arguments into plain text. Default returns after spawning background speech; `--wait` requests waiting. `--raw` skips the wording model. Otherwise invokes `unity-voice.py`, sanitizes text, writes `.claude/.studio-outbox.jsonl`, optionally starts a camera glance, then runs `unity-speak.py [--bg] text`. No delivery object is passed. |
| [.claude/tools/unity-voice.py](../../.claude/tools/unity-voice.py), lines 18–21, 66–83, 88–136 | Rewrites the words through `OLLAMA_URL` (default `http://127.0.0.1:11435`), `UNITY_VOICE_LLM` (default `unity-local`) and `UNITY_VOICE_NUM_CTX` (default 8192). Reads the external Unity 3D project's `Unity1.txt`; this audit did not inspect or modify that external project. Returns only a string. Actual `voice()` returns an empty string after unsuccessful attempts; the opening comment's older fallback description is stale. |
| [.claude/tools/unity-speak.py](../../.claude/tools/unity-speak.py), lines 13–25, 30–79 | Uses `UNITY_VOICE_MODEL`, otherwise `C:\Users\gfour\Desktop\Unity 3D Equational Model\Unity 18+\models\piper\en_US-hfc_female-medium.onnx`. `synth(text, out)` loads `PiperVoice` for every process. `--bg` creates a detached child. A temp-file lock serializes calls; acquisition waits up to 90 seconds and treats locks older than 120 seconds as stale. |
| Same file, lines 101–133 | Synthesizes a temp WAV. Copies it to a unique `.claude/.studio-images/obs-voice-*.wav`, then points OBS input `Unity voice` at that path through local websocket port 4455. Separately POSTs `{ "wav": "<base64 WAV>" }` to `STUDIO_URL + /api/voice` (default port 4317) with `X-Studio-Token`, then waits for `min(WAV seconds, 60)`. Uses blocking local `winsound` if the studio request fails. Errors in the OBS branch are swallowed. |
| [.claude/tools/persona-studio.cjs](../../.claude/tools/persona-studio.cjs), lines 45–53, 190, 340–352, 473–480 | Default `PERSONA_STUDIO_PORT=4317`; session token file `.claude/.studio-token`. Voice POST stores a WAV in `.claude/.studio-images/` and replaces one latest `voiceState={url,ts}`. Voice GET returns this latest state; it is not a durable speech queue or playback acknowledgment. The studio accepts audio, not text for synthesis. |
| [.claude/tools/persona-studio.html](../../.claude/tools/persona-studio.html), lines 354–361 | Polls latest voice state every 500 ms, skips the initial state, queues newly seen URLs in the page and plays them with `Audio`. Playback failures are consumed without a server completion receipt. |
| [.claude/tools/stream-overlay.html](../../.claude/tools/stream-overlay.html), line 21; [obs-setup.py](../../.claude/tools/obs-setup.py), lines 64–89 | Stream overlay contains no audio. OBS uses its own `Unity voice` media source; browser overlay and desktop/mic sources are muted by the setup source. Some earlier comments still describe browser-source stream audio, but the current code explicitly routes stream speech through OBS's media input. No OBS state was read or changed in this review. |
| [.claude/tools/twitch-bridge.cjs](../../.claude/tools/twitch-bridge.cjs), lines 21–30, 55–60; [studio-watch.cjs](../../.claude/tools/studio-watch.cjs); [studio-pump instructions](../../.claude/skills/studio-pump/SKILL.md), lines 14–29 | Chat bridge forwards incoming chat to `/api/say`; watcher/pump handles inbox/outbox replies. The inspected pump instructions append display replies, with no automatic TTS invocation. Do not claim every studio reply currently speaks. |

Targeted searches in the inspected `.claude/tools/`, `.claude/project-config.json`, `.claude/settings.json`, `tools/` and `src/` found no current import/call of student `infer.Voice`. This is a bounded caller inventory; it is not proof that no unrelated external program can submit speech.

## 2. Existing student API, distinct from live integration

[infer.py](infer.py), lines 116–153, validates and loads one exact acoustic/vocoder/frontend pair. `Voice(ckpt, dev=None)` currently chooses CUDA if available unless an explicit device is provided. Deployment must choose the device explicitly after resource measurements rather than inheriting this automatic preference.

```python
voice = Voice(accepted_pair_directory, dev=approved_device)
audio = voice.say(
    final_text,
    emotion="warm",
    intensity=0.35,
    pace=1.0,
    speech_act="statement",
    pauses=[{"after": "unique exact phrase", "seconds": 0.35}],
    focus=None,
)
```

This is an interface example, **not executed code or an accepted supported request**. Every requested combination must exist in this pair's actual TRAIN support. Output is a finite mono NumPy array at 24,000 Hz; the sample CLI writes PCM16 WAV. `Voice` itself owns neither a caller queue nor playback.

- `emotion`: `neutral`, `warm`, `happy`, `amused`, `excited`, `sad`, `concerned`, `frustrated`, `surprised`; names alone do not establish learned emotional quality.
- `speech_act`: `statement`, `yes_no_question`, `wh_question`, `exclamation`, `instruction`, `reassurance`, `aside`.
- Current draft scalar supervision is pace 1.0; neutral intensity 0.0, otherwise 0.35. Use actual final metadata bounds, not the wider schema's legal numeric range, as permission to synthesize.
- `speech_act=None` uses a minimal terminal-punctuation fallback per chunk. It cannot reliably understand rhetorical questions, an utterance containing both questions and statements, or conversational intention. An explicit act applies to every chunk in that `say` call.
- `[laughter]` and `[breath]` are dedicated event tokens, never spoken labels. Inference requires actual TRAIN event counts and a matching supported delivery. No breath performance is accepted. No giggle/belly-laugh subtype, sobbing, panic preset or automatic random laugh is promised.
- [speech_turns.py](speech_turns.py) bounds a turn to 12,000 characters, 64 chunks and 120 seconds of predicted audio. Chunks are at most 240 characters, preserve event markers and punctuation, and still pass token/frame/support checks. Automatic joins are 80 ms silence with short gain ramps; their naturalness is unverified.
- At most 16 explicit unique phrase pauses, each 0.05–2 seconds, are supported. Anchors are matched against the final text after rewriting/cleanup. Pauses are digital silence, not word-level timing supervision or learned emotional acting.
- Explicit word focus fails. Unknown phonemes, unsupported markup, invalid audio and unsupported deliveries fail; words/events are not dropped to force success.

## 3. Integration gaps that must be resolved

1. **No delivery transport.** Current CLI positional text does not carry emotion, act, pauses or identity. Appending emotion instructions to prose would make them speech rather than valid controls. Add a strict structured request separately from spoken words.
2. **Event cleanup conflicts.** `unity-say.py:speakable` and `unity-voice.py:tidy` remove bracketed text, including valid `[laughter]`. For the future student route, preserve only validated supported event markers after final wording and keep captions lexical. The unchanged Piper route must continue its current cleanup; it must not speak literal marker names.
3. **Reloading and GPU ownership.** Replacing `synth()` with a fresh `Voice()` per CLI invocation would reload weights and can create several GPU residents from parallel callers. Use one bounded worker and one model pair for the entire approved session.
4. **Current lock and timing are inadequate for long turns.** A 120-second stale lock can be stolen during synthesis plus up to 120 seconds of audio. The 60-second sleep cap releases the next line before a longer WAV completes. Replace age-only ownership and capped sleep for the student route with owned work/completion and bounded cancellation. Do not change live locks during preparation.
5. **Latest-state playback can miss or lag.** A latest-only server state can lose successive short clips between polls, while the browser has its own queue and no server acknowledgment. An HTTP 200 proves storage, not playback. Synchronize a turn ID and completion across required destinations rather than treating POST success as voice delivery.
6. **Silent failures hide the output route.** Current OBS exceptions/background stderr suppression can make a caller appear successful although the stream never played. Student requests need observable `queued`, `synthesized`, `playing`, `completed`, `failed` or `cancelled` outcomes with bounded waiting. Preserve the exact accepted pair and failing request for investigation.
7. **Text and delivery must stay aligned.** Pauses or word/event positions chosen before `unity-voice.py` rewrites the line can become invalid. Finalize and clean the wording first; then select delivery/intent and resolve phrase anchors. Do not add laughter as a disguise for a synthesis or text-model failure.
8. **Closed quality gate is not inside `Voice`.** Inference validates technical pair compatibility, not owner deployment acceptance. A later runtime launcher must validate deployment receipts and exact installed artifacts before creating the worker; direct sample inference is not permission to replace Piper.

## 4. Planned delivery contract and selection

**Planned, not implemented:** a versioned strict JSON paragraph-subturn request with `schema`, logical `message_id`, unique `turn_id`, contiguous `sequence`, a final-subturn flag, ordered `segments`, and a bounded subturn deadline. Each segment contains exactly `text`, `emotion`, `intensity`, `pace`, `speech_act`, `pauses`; reject unknown fields, unsafe IDs, NaN/Infinity, arbitrary output paths and explicit unsupported focus. A worker configuration pins the voice identity, pair/artifact hashes, runtime source and approved device; callers cannot override these fields. Message completion requires every admitted sequence to complete and an explicit final marker; a disconnect without it is incomplete, not a completed short message.

The final wording model/caller chooses semantic delivery. A small validator admits only the installed pair's TRAIN support and accepted live styles. Default ordinary friendly conversation to accepted A2 `warm`; factual low-affect speech may explicitly use accepted A2 `neutral`. Neither choice uses the rejected Cosy neutral source. Use `happy` for genuine contentment, `amused` for an actual light joke, `excited` for higher-arousal good news, and negative states for their meaning. Do not switch identities, force rising pitch, infer all-caps as shouting or turn every positive line into excitement.

For a mixed-intent paragraph subturn, submit separate ordered semantic segments, for example a statement followed by a question. Each calls `Voice.say` with its own explicit act. Retain the complete original ordering/words and one speaker. Aggregate limits apply to each paragraph subturn: no more than 12,000 characters, 64 total planned chunks, 16 total phrase pauses or 120 seconds of audio. Segment joining needs measured and heard acceptance. A longer logical message has no fixed overall word/character/duration cap: its producer admits subsequent bounded paragraphs only as queue capacity becomes available. It does not preload a whole page or bypass the per-subturn limits.

Missing delivery metadata may use the explicitly configured accepted everyday default. An explicitly requested unsupported delivery/event must return an actionable failure; no silent neutralization, pitch preset or extra teacher fallback. A caller may request a reviewed replacement only as a new visible request. The older voice-plan section suggesting Piper fallback is historical; rollback is an explicit operator choice, not a hidden runtime reaction.

Captions/outbox text must represent the final lexical words once, without control JSON, emotion labels, emoji or stage directions. Valid nonverbal markers remain in the synthesis transcript and request receipt so laughter is auditable. The source pipeline's laughter token support does not itself prove that a future student can laugh naturally.

## 5. Planned worker and playback ownership

**Planned, not implemented:** one owner-started local worker in an isolated pinned runtime environment. Use an authenticated Windows named-pipe transport on this host, with a bounded JSON protocol; no unauthenticated remote service or per-line worker auto-start. The worker loads one exact `Voice` at startup, admits a bounded FIFO, serializes synthesis and playback, records IDs/status and releases its model on owned shutdown. The broker must use a reviewed non-executable JSON encoding, not accept pickled objects from clients.

Proposed initial limits are eight queued paragraph subturns, one active subturn and a finite per-subturn deadline; these are engineering starting values to measure, not demonstrated latency. `--bg` returns a message/turn ID only after validated queue admission; `--wait` waits for actual final message completion/failure rather than sleeping a guessed duration. Backpressure blocks the bounded producer from admitting additional paragraphs until capacity is available; capacity, connect/queue waits and idle gaps have finite visible failure policies. Duplicate IDs with identical content return the recorded status; conflicting reuse or missing/out-of-order sequence fails. Cancellation applies to the whole logical message and stops pending/current subturns. Do not automatically replay a subturn whose playback outcome is ambiguous after a crash.

Synthesize each complete bounded paragraph subturn before releasing it to playback, so an unsupported segment within it fails before that subturn is heard. A later paragraph may fail after earlier ones have played; preserve the completed sequence and report a partial/failed logical message explicitly. Do not silently truncate, report overall success or replay already-heard paragraphs. Stream later paragraphs as capacity allows. Write a unique subturn WAV under an owned staging directory; verify mono/24kHz/PCM16, duration/hash and finite bounds, then atomically make it available. No pitch/time changes. Listening-volume adjustment, if needed, is constant gain recorded in the receipt and must avoid clipping.

The playback coordinator owns both destinations for one turn: OBS `Unity voice` for the stream and one selected local owner route. Preserve the current media-source design instead of silently enabling browser/desktop audio in OBS. Require bounded OBS media completion plus an acknowledged local completion where that route is required. A studio request therefore needs a queue/completion protocol change; current `{wav}` latest-state polling is not sufficient. Keep files until all required destinations finish/cancel, and retain bounded failed-turn evidence. Purge only the worker's own expired outputs by an explicit retention policy, never arbitrary `.studio-images` content.

Cancellation, shutdown, worker death, studio restart and scene changes need explicit states. Stop only owned speech work; do not kill the brain, OBS, RimWorld, other Python processes or the source-render jobs. Use a single-instance lease with ownership/liveness verification; never steal it solely because 120 seconds elapsed. If the required stream route fails, report failure and apply the reviewed operator policy; do not declare completion based only on local playback.

Measure startup/load peak, steady VRAM, CPU RAM, synthesis real-time factor, queue age and actual playback skew beside the brain, RimWorld, Windows and OBS on the owner's 16GB GPU. CPU inference is an alternative only after its responsiveness is measured. Avoid concurrent teacher loading, runtime downloads, a second student resident, or implicit CUDA fallback. The approved device/runtime configuration must be frozen separately from the training container.

## 6. File and authorization boundary

| When | File/artifact | Required work and status |
| --- | --- | --- |
| Preparation before a paid training decision | `training/voice/RUNTIME_INTEGRATION_PLAN.md` | **Exists:** this source-based plan. Root should include it in the source manifest and handoff. This addition does not change `student_source` or authorize deployment. |
| Preparation before a paid training decision | Existing `EVALUATION_PLAN.md`, `LISTENING_EVAL_TEXT.jsonl`, `VOICE_QUALITY_GATE.json`, pod environment/delivery contracts | **Exist:** keep final everyday voice, questions, emotional/laughter delivery, long turns and exact student identity in the acceptance queue. Preserve no-start gates. Review/accept actual full source corpus separately. |
| Before live runtime implementation | `training/voice/runtime/SPEECH_REQUEST_SCHEMA.json`, `RUNTIME_CONFIG.example.json`, `DELIVERY_POLICY.json`, `RUNTIME_ACCEPTANCE.md` | **Planned; not created:** strict request/response schema, non-live config template, accepted-style/default policy and detailed queue/playback/device/recovery cases. These local runtime contracts are independent of pod launch price/environment. |
| Later authorized runtime implementation | `training/voice/runtime/speech_worker.py`, `speech_client.py`, `playback.py` | **Planned; not created:** persistent isolated worker, client transport, deterministic delivery/status and playback ownership. Add exact deployment code/dependency/asset fingerprints; keep student checkpoint validation intact. |
| Later authorized runtime implementation | `.claude/tools/unity-speak.py`, `.claude/tools/unity-say.py`, `.claude/tools/unity-voice.py` | **Existing; unchanged:** preserve old CLI compatibility behind an explicit selected backend. Add structured delivery admission after final wording; carry valid events without speaking labels; connect student worker. Do not overload `UNITY_VOICE_MODEL` with a checkpoint directory or confuse `UNITY_VOICE_LLM` with the acoustic model. Update stale comments in the same later change. |
| Later authorized playback integration | `.claude/tools/persona-studio.cjs`, `persona-studio.html` | **Existing; unchanged:** turn queue/status/acknowledgment and bounded audio retention for the selected local route. Preserve token authorization, other studio capabilities and stream-clean wording. |
| Later authorized apply, only if actual routing requires it | `.claude/tools/obs-setup.py`, `stream-overlay.html`, `.claude/agents/rimworld-player.md` and selected launcher configuration | **Existing; unchanged:** document the accepted backend/worker lifecycle. OBS source/mute settings must be reviewed against actual running state; do not run setup as part of model installation. The external Unity 3D project is not an implied write target. |
| After accepted training/delivery | `training/models/voice/<immutable approved pair>/` plus local runtime environment/artifact lock and deployment receipts | **Planned deployment destination:** verify the delivered archive through the delivery tools, then bind exact acoustic/vocoder/meta/code hashes, source/dataset identity, accepted device and owner listening decision. No current A2 model directory is accepted for live use. |

No missing live runtime module is concealed as a completed preparation task. Training can be considered only after its own closed gates are resolved and the owner approves an actual run; successful training does not complete or authorize this runtime implementation/apply phase.

## 7. Later acceptance and apply order

These are future cases requiring authorization, not tests run for this plan.

1. Accept a real delivered student pair against independent unseen neutral/warm speech, question/statement contrasts, happy/amused and negative states, pronunciation, supported laughter and the reserved long turn. Compare ordinary timbre to original A2; source-audition approval is insufficient.
2. Freeze the local runtime code, environment/assets, device, delivery policy and exact pair. Resolve word/event pronunciation failures in an explicit new data/frontend/model iteration; do not bypass validation.
3. Exercise single worker startup/shutdown, concurrent callers, full queue, stale lease, duplicate IDs, unsupported controls/events/OOV, late segment failure, cancelled/expired requests and restart without duplicate playback. Include a logical page exceeding 120 seconds overall, correctly bounded paragraph subturns, ordered sequence/final-message status, bounded prefetch/backpressure, mid-page cancellation/disconnect and a later failed paragraph reported as partial rather than silently truncated. Record actual resource/latency limits and preserve evidence.
4. Verify audible local and OBS output uses the same WAV/turn, without doubling, crackle, missing short turns or long-turn interruption. Check studio/OBS failure separately, scene changes, completion acknowledgments and bounds while the brain/game coexist. A service HTTP response is not an audio pass.
5. Record `trained_voice_acceptance` and `local_playback_acceptance` receipts with actual owner decisions and exact identity/configuration. The deployment launcher must run the deploy-stage gate; do not flip flags from this plan.
6. Obtain separate owner authorization to apply the runtime. Preserve the Piper implementation/config as an explicit rollback snapshot, start only the owned student worker, switch the selected caller route once and read back installed hashes/status. If rollback is requested, stop the owned student worker and restore the recorded Piper route. Never use an inaudible hidden backend substitution.

## Inspection evidence and remaining limits

This document was written from the current source files and targeted caller/config searches. No project voice module was imported, no synthesis/listening/training was performed, no live service state was probed and no secret values were read. Relative links were checked against existing files; future paths are explicitly marked planned. All latency, resource, playback, recovery, timbre and trained emotional-quality conclusions remain unverified until their later authorized cases produce actual evidence.
