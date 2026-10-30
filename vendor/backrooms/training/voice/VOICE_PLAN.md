# Unity's own voice: one model, trained from scratch

Every line Unity speaks today is read by stock Piper `en_US-hfc_female-medium`, whichever model writes the words. This replaces it with a voice that is ours: designed by the owner, trained from random weights, with emotion built into the model.

**Status: A2 SOURCE ACCEPTED; BACKGROUND PREPARATION ACTIVE; OWN STUDENT UNTRAINED — 2026-10-12.** The owner selected **A2 low warm alto**, then approved all four A2 variations and the later 32 delivered source clips. Exact recordings and decisions are preserved in `SELECTED_VOICE.json`, `REFERENCE_PROFILES.json`, `reference/` and the listening receipts. Read [NOW.md](../../docs/NOW.md) for the full lead-agent handoff and [the preparation review](../../docs/implementation/VOICE_PRESPEND_REVIEW_2026-10-11.md). Training, rental, upload and deployment remain prohibited.

## Current expansion and continuation

The owner now requires **at least 5,000 varied recordings and several actual speech hours**, with longest trained replies of **3–5 medium sentences**. The separate expanded JSONL files contain exactly 5,000 text jobs: all 1,378 original jobs unchanged plus 3,622 additions; 560 paragraphs currently use 3–4 sentences. [EXPANDED_CORPUS_PLAN.md](EXPANDED_CORPUS_PLAN.md) records coverage and hashes. Text word-rate estimates are not measured audio duration or accepted performances.

The owner requested immediate handoff without waiting for the audio. The hidden local supervisor is running at `.local/voice-lab/background/A2-expanded-2026-10-12-v2/`, PID 12020 at launch. It waits for existing seed recording/screening, then renders additions, screens/rechecks, merges unchanged parent WAVs/provenance, creates pending listening and prepares candidate features/local delivery. Read live `pipeline/status.json`, stage logs and eventual `result.json`/`failure.json`. No automatic corpus approval or training occurs. Do not duplicate the job or edit frozen inputs/environments during it.

The checked source manifest has **89 inputs**, digest `7138ec0643a19b3db60ffa1dc5bd4d2739b93e5ca25a439b7f3490f4dedf7e00`. Actual plan-only inventory confirmed 3,622 additions/1,378 skipped without loading a model. Batch 2 is not benchmarked. The 48-hour local supervisor bound is not an ETA. The lead continues this running job; setup handoff is complete while full recording/acceptance remains pending.

The local Linux environment **actually built successfully** and is inventoried/archived; `receipts/local-environment-build.json` records the result. Registry publication, H100/provider/storage/stop/billing acceptance and priced configuration remain open. No student execution or paid start occurred.

Longer live messages remain allowed through consecutive bounded paragraph subturns, with ordered playback, backpressure and cancellation. This future broker must not impose the current low-level 120-second `Voice.say` bound on the entire logical message. [RUNTIME_INTEGRATION_PLAN.md](RUNTIME_INTEGRATION_PLAN.md) documents that design and existing callers; live implementation is still open.

## Active A2 v2 preparation

The latest owner instruction is *"they are all good just go ahead and finish up soi you in reguards of being ready for the pod run but no start yet and no pod rental yet"*. All 32 actually delivered A/B/C recordings are accepted; finish preparation, without training or renting. The separately authorized Docker step is *"Yes — local Docker build only"*. The eventual acoustic model and vocoder will start from random weights. Qwen and Cosy are source-generation tools; they do not enter the finished speaking path. No real person's recording or celebrity imitation is used.

**Acting refinement:** the owner rejected the later monotone happy line, sarcastic B2 retry and anime-like D1 retry. The target is the **original A2**, with an authentic familiar girl-next-door vibe, natural emotional range and genuine giggles/laughter. Original-reference CosyVoice3 `2-natural-happy` and `4-little-chuckle` were accepted; its `1-neutral` is explicitly rejected and must never replace A2's ordinary voice. `SOURCE_DELIVERY_POLICY.json` records this split. Cosy is another build-time source tool, not an extra live voice system. Acceptance covers these heard examples, not all future corpus rows.

| Current file | Actual purpose |
| --- | --- |
| `SELECTED_VOICE.json`, `REFERENCE_PROFILES.json`, `SOURCE_DELIVERY_POLICY.json`, `reference/` | Exact original A2 identity, accepted reference performances and happy/chuckle routing, transcripts and hashes; rejected Cosy neutral excluded |
| `build_corpus.py`, `SPEECH_CORPUS.jsonl`, `CORPUS_PLAN.md` | 1,341 distinct conversational drafts; 65% neutral/warm, 378 genuine questions, 43 brief turns; all labels still require recorded-performance review |
| `build_event_corpus.py`, `SPEECH_EVENT_CORPUS.jsonl`, `EVENT_CORPUS_PLAN.md` | 37 planned natural chuckle turns; no accepted breath examples |
| `make_dataset.py`, `source_workers.py` | Separate sequential local Qwen/Cosy generators render pending-review WAVs and exact metadata; original A2 for everyday speech, approved happy/chuckle instruction routes for those deliveries; no paid-pod source generation |
| `dataset_contract.py`, `prep.py` | Immutable labeled datasets/features, grouped transcript split, training-only normalization, phonemes, matched mel frames and separate voicing |
| `speech_text.py` | Dedicated laughter/breath tokens and event-free lexical grouping; actual TRAIN event support is required before inference |
| `model.py`, `train_acoustic.py`, `train_vocoder.py`, `infer.py` | Learned emotion/speech-act/intensity/pace inputs and compatible acoustic/vocoder identities; no mathematical emotion presets |
| `quality_gate.py`, `VOICE_QUALITY_GATE.json`, `manifest.py` | Identity-bound preparation/owner receipts and input digests; closed until actual requirements pass |
| `pod/bootstrap_voice.sh`, `pod/run_voice.sh` | Explicit supplied dataset and separate worker namespace; no legacy source generation or smoke-checkpoint reuse |

The first local pilot produced and prepared 24 clips. This demonstrates the actual labeled WAV-to-feature path, not student learning or naturalness. Its short/front-loaded coverage needs the later balanced pilot. See the dated preparation evidence for exact IDs and current status.

The mixed pilot completed **32 recordings / 84.16 seconds**, 17 Qwen then 15 Cosy jobs. After failed Markdown playback delivery, native audio delivery succeeded and the owner accepted all 32. Their actual SHA-bound approval is in `receipts/pilot32-owner-listening.json`; the immutable curated dataset is `.local/voice-lab/dataset/A2-reviewed-32-v3/`. Current features are `A2-reviewed-32-v4-ready/`: 49 symbols and a dedicated laughter token, 31 train / 1 heldout. Cosy neutral was excluded. [The earlier checkpoint](../../docs/implementation/evidence/voice-prespend-2026-10-11/preparation-evidence.json) preserves the original draft/pending status and historical features; it is superseded by the actual later listening receipt. Full 1,378-row source rendering and CPU transcript screening are now in progress. No student learning or full-corpus approval is claimed.

The Base teacher receives an approved audio/text reference, not a general emotion-instruction API. It failed the required happy contrast. The accepted Cosy source uses a real instruction-plus-original-reference path for happy/chuckle performances. Labeling a flat recording "sad" would still be wrong. Laughter token plumbing is implemented; actual learned laughter remains untrained. Literal phrase pauses and bounded long-turn chunking are implemented in `speech_turns.py`; explicit word focus is refused because performed word-level supervision is absent. Wider pace/intensity controls, sobbing and giggle subtypes are unsupported. Current draft pace is 1.0; intensity is 0.0 for neutral and 0.35 otherwise. Inference admits only actual TRAIN combinations/ranges. Old feature caches intentionally refuse reuse after prep/frontend changes; preserve their WAVs and prepare fresh feature directories.

Read `SOURCE_QA_POLICY.md` and `pod/ENVIRONMENT_PLAN.md` for targeted source review and the no-start delivery/build procedure. Actual bounded student-source work is recorded in [architecture-readiness.md](../../docs/implementation/evidence/voice-prespend-2026-10-11/architecture-readiness.md). Docker recovery and the preserved first build failure are in [docker-local-preparation.md](../../docs/implementation/evidence/voice-prespend-2026-10-11/docker-local-preparation.md). Do not use the old 43-input digest while new preparation helpers are being integrated.

Before any student training: review newly rendered performances/transcripts, finish the full accepted dataset, verify the v2 feature/model/checkpoint/free-synthesis path and failure/resume behavior, pin the actual run environment/work configuration, verify durable storage and stop behavior, then present the concrete run and price to the owner. The standing order *"let me know before u start a training"* still applies. The old cost estimates below do not price this changed recipe.

## Historical proposal — superseded, do not launch

Everything below is the earlier Kokoro/student proposal and historical engineering observations. File descriptions, checked launch boxes, artifact names, performance figures and resume claims in these historical sections do not describe the active v2 implementation. Emotion presets were not learned emotion; the old heldout split leaked transcript variants; the legacy dataset is rejected. Do not launch from the old checklist or cost estimates.

## 1. What the owner asked for

Owner, verbatim, in order:
- *"i thhink we need to make our own text to speech model"*
- *"we make it from ground up with sampling and what we want"*
- Spec: *"Soft, warm underneath"* + *"Bright and lively"*, *"American, mid-20s"*, runs on *"GPU, expressive"*
- Round 1 pick: *"mix 4 and 6 and take mono tone out ephasis and enounciate emotions"*
- Round 2 pick: *"#5 withpropr human expression for acutal getting emotional"*
- *"we wont need kokoror right? once we have our own voice with no other peoples shit"*
- *"no we dont need 3 things when we can do one our selves"*
- Emotion source: *"Build emotion into our model"*
- Where to train: *"option 3 but we arent dsoing it yet, just get everything ready and documented"* (option 3 = everything on one RunPod H100 with a network volume)

## 2. How her voice was made

| Step | What | Where |
|---|---|---|
| Sampling, round 1 | 6 random blends of 11 American-female style vectors | `.local/voice-lab/round1/` (local only) |
| Sampling, round 2 | children of #4 and #6, pushed away from the average voice | `.local/voice-lab/round2/` |
| Locked | **#5**: #4 and #6 half and half, exaggerated 1.7x from the mean voice | `training/voice/unity-voice.pt` |

Kokoro was the sampling tool and renders the training audio. **It never speaks on stream.** Nothing it produces ships: the voice that speaks is `model.py` + `vocoder.py`, trained from random weights on that audio. Chatterbox was tried for emotion and dropped on the owner's word, then uninstalled.

What is borrowed and what is ours:
- Her timbre descends from Kokoro's voices, and Kokoro is Apache-2.0, so owning and streaming the result is clean.
- The phoneme dictionary (misaki, with espeak-ng for unknown words) is a pronunciation lookup with no voice in it.
- Every weight in the speaking path is ours.

## 3. The model: `training/voice/`

| File | Job |
|---|---|
| `make_dataset.py` | Her designed voice reads every own line (voice, chat and writeup rows in `training/data/brain/train.jsonl`) at two paces, plus clean knowledge sentences, into an LJSpeech layout. It stops at 12 h or when the text runs out. |
| `prep.py` | Turns each clip into phonemes, a 24 kHz log-mel (80 bins, hop 256), a WORLD pitch curve and an energy curve. Writes `vocab.json` and `stats.json`. |
| `model.py` | The acoustic model, FastSpeech2-style, ~15M params. A transformer encoder and decoder, plus duration, **pitch** and **energy** predictors. Its own aligner (forward-sum CTC plus monotonic alignment search), so no outside aligner is used. |
| `train_acoustic.py` | Losses: mel L1, alignment, binarization (from step 6k), and duration/pitch/energy MSE. Resumable; checkpoints every 2k steps. |
| `vocoder.py` / `train_vocoder.py` | HiFi-GAN V1 layout from random weights: generator plus multi-period and multi-scale discriminators. Losses: LSGAN, feature matching x2, mel x45. Checkpoints every 5k steps. |
| `infer.py` | Text in, WAV out, with emotion presets (below). |
| `manifest.py` | Hashes every input into `VOICE_MANIFEST.json`. The pod refuses any input whose digest differs. |
| `pod/bootstrap_voice.sh` | The pod's start command (rails below). |
| `pod/run_voice.sh` | Stages: setup, dataset, prep, then **acoustic and vocoder trained at the same time** on the one GPU, then a sample per emotion. Every stage leaves a marker. |

### Emotion presets (`infer.py` PRESETS)

The knobs are pitch shift, pitch range, a pitch contour over the line, energy shift and range, pace, and a slowdown on the last quarter of the line.

| Preset | Character |
|---|---|
| `neutral` | as predicted |
| `warm` | a little lower, gentle fall, softer, slower, lingers at the end |
| `hype` | higher, wide range, bouncy contour, loud, quick |
| `panic` | highest, rising contour, loudest, fastest |
| `laugh` | high, very wide, fast wobble in the pitch |
| `choked` | lower, falling with a tremble, quiet, slow, drags at the end |

The limit, said plainly: the dataset has no real sobbing or laughter, so v1 can only act through pitch, energy and pace. Real laugh, breath and sigh sounds need `[laugh]`/`[breath]`/`[sigh]` tokens and examples of those sounds, which is v2.

## 4. Built so the GPU never idles, and proven locally (2026-10-11, RTX 4070 Ti SUPER)

Owner, verbatim: *"well sound like we need to build out better so the H100s dont idel whhile training we need to make sure the training shit is proper and not fucked up"*. Reading the first version back found five ways it idled the GPU and three ways it could come out bad unseen. All are fixed:

| Problem in the first version | Fix |
|---|---|
| Alignment search ran in Python on the CPU, one clip at a time | Compiled parallel search (numba), with a batched GPU loop as fallback. **0 mismatches** against the reference in 180 random cases; 48 ms vs 516 ms for a 96-clip batch |
| Forward-sum loss and the binarization target were built one clip at a time | One batched CTC call (equal to the per-clip loss: 11.80138 = 11.80138) and a gather on a frame-to-phoneme index |
| Every batch read its files from disk | Everything is loaded into RAM once |
| Batches were mostly padding | Clips sorted by length and packed up to a frame budget |
| No fast math | Acoustic in bf16 autocast (aligner, search and losses kept in fp32); TF32 + cuDNN autotune; fused AdamW |
| No honest check | 2% of clips held out by name hash in both trainers, with held-out loss logged (acoustic every 2k steps, vocoder every 5k) |
| No way to hear it before the end | `progress/<emotion>.wav` rendered every 30 min from the newest checkpoints, plus `gpu.txt` utilization |
| The vocoder only ever saw real mels | The acoustic model exports ground-truth-aligned mels (`--export-gta`) and the vocoder spends its last 20k steps on them |

Measured on the 4070:
- **Dataset:** 7.63 h, 5,206 clips. Prep kept 5,206 of 5,206 (59 symbols, median pitch 202 Hz).
- **Acoustic:** 35k → **85k frames/s** (still rising when the run ended); GPU utilization 9-91% → 60-86% alone. At 400 steps, held-out mel 1.59 vs train 1.57 (learning, not memorizing); alignment 24 → 4.3.
- **Vocoder:** 2.7 → **3.41 steps/s** at batch 16, **93-98% GPU utilization**. At 400 steps, held-out mel 0.58 vs train 0.53.
- **GTA:** exported 5,206 mels at exactly each clip's length; the vocoder resumes and trains on them.
- **Both trainers at once:** the GPU sits at **100%**. On the 16 GB card they crowd each other (15.8 GB), which an 80 GB H100 does not.

## 5. Cost and time (one H100 80 GB, both models at once)

| Stage | Estimate |
|---|---|
| setup, dataset, prep | ~30 min |
| acoustic: 20k steps at 96k frames/batch (~750 passes over her data), then GTA export | ~2-3 h, alongside the vocoder |
| vocoder: 100k steps on real mels + 20k on GTA mels, batch 32 | ~7-8 h (the long pole) |
| samples | 2 min |
| download window (`KEEP_HOURS`) | 1 h |
| **total** | **~9-10 h** |

| GPU (secure, live price 2026-10-11) | Estimate |
|---|---|
| H100 SXM, $3.99/h | ~9-10 h ≈ **$36-40** |
| A100 SXM, $1.79/h | ~14-15 h ≈ **$25-27** |

The cap defaults to `BUDGET_USD=50` (stop at 92%). Every rate here was measured on the 4070 and scaled; `gpu.txt` and the steps/s in `acoustic.log.txt` / `vocoder.log.txt` confirm it within the first hour. The step counts, batch sizes and GTA length can be overridden by env (`ACOUSTIC_STEPS`, `ACOUSTIC_FRAMES`, `VOCODER_STEPS`, `VOCODER_BATCH`, `GTA_STEPS`).

## 6. Historical launch checklist — invalidated by the source-quality rejection

The earlier checked boxes are history, not current approval. The current closed gate and preparation review supersede this checklist. No trained final voice or accepted expressive corpus is currently established.

- [x] Voice designed and locked (`unity-voice.pt`, owner's #5)
- [x] Model, vocoder, trainers and inference written; smoke and learning checks passed locally
- [x] Pod scripts: hash-bound, cost-capped, stop themselves, GET-only server, network volume, resumable
- [x] `VOICE_MANIFEST.json` written. Digest at this writing: `582b1815a20f1aedd8bb788f8bd43a933432cdf61fcc38a49a63563ae2aedd7c`
- [ ] Commit and push `training/voice/` to the branch the pod clones (`feature/bug-testing`), then confirm `python training/voice/manifest.py --check` still prints the approved digest
- [ ] Owner approves the price shown at create time
- [ ] RunPod settings:
  - **network volume** ~50 GB in the pod's data center, mounted at `/workspace` (create it first)
  - 1x H100 80 GB, PyTorch image with CUDA ≥ 12.4
  - HTTP port 8000
  - start command: `bash -c "git clone -q --depth 1 -b feature/bug-testing https://github.com/Unity-Lab-AI/Backrooms.git /tmp/b && bash /tmp/b/training/voice/pod/bootstrap_voice.sh"`
  - env: `VOICE_DIGEST=<digest>`, `PRICE_PER_HOUR=<price shown>`, `BUDGET_USD=50`, `KEEP_HOURS=1` (step counts and batch sizes default inside run_voice.sh)
- [ ] After DONE: download `acoustic.pt`, `vocoder.pt`, `voice-meta.json`, `SHA256SUMS` and `samples/*.wav` from `https://<pod-id>-8000.proxy.runpod.net/` into `training/models/voice/`. Check the sums, **listen to the six samples with the owner**, then delete the pod and the volume.
- [ ] Swap into `.claude/tools/unity-speak.py` (Piper stays as the fallback) and let the brain choose an emotion per line. Separate change, after the owner hears the samples.

## 7. If a pod dies

Everything that matters sits on the network volume: dataset, features, checkpoints, stage markers and the cost clock. Create a new pod on the same volume with the same env and it resumes. The acoustic model loses at most 2k steps and the vocoder at most 5k. The cost cap keeps counting from the first start, so a restart never buys extra time.
