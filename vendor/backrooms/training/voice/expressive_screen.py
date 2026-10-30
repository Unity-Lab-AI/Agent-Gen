"""The speech-recognition screen for the re-performed clips -- the same rule the accepted dataset went through.

The 4,845 accepted clips were screened on the pod (training/voice/pod/auto_screen.py + inspect_source_audio.py):
faster-whisper base, CPU int8; a clip was dropped on a transcript mismatch (word error > 25%, unless the words match
within 10% after normalising numbers, contractions and heard laughter), long boundary quiet (> 1.5 s), a rushed read
(> 6 words/s of speech) or a format/level outlier; every kept clip was trimmed to 0.15 s of quiet at each edge.
Cosy's re-performed clips get the identical screen here. ONE difference, on purpose: a flagged re-performed clip
falls back to its ORIGINAL recording and labels instead of being dropped, so every one of the 4,845 lines stays and
the phoneme vocabulary is exactly the live voice's (local_prosody_retrain refuses a different vocabulary).

  python training/voice/expressive_screen.py            (CPU, resumable: re-run continues; renders nothing, trains nothing)

In:  D:/voice-lab/dataset-v2-expressive-2026-10-13/   (expressive_rerender.py output, must be complete)
Out: D:/voice-lab/dataset-v2-screened-2026-10-13/     metadata.jsonl + wavs/ + screen-report.json (every fallback listed
                                                       with what the recognizer heard, so the owner can listen)
"""
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / "pod")]
from dataset_contract import load_dataset, normalize_transcript  # noqa: E402
from auto_screen import edit_rate, laugh_heard, slow_to_target  # noqa: E402

RENDERED = Path(r"D:\voice-lab\dataset-v2-expressive-2026-10-13")
OFFGAME = Path(r"D:\voice-lab\dataset-v2-offgame-2026-10-13")     # offgame_render.py output: no original to fall back to
ORIGINAL = Path(r"D:\voice-lab\pod-results\voice-2026-10-12\gen\dataset")
OUT = Path(r"D:\voice-lab\dataset-v2-screened-2026-10-13")
WHISPER = Path.home() / ".cache/huggingface/hub/models--Systran--faster-whisper-base/snapshots/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66"


def word_error(expected, actual):   # inspect_source_audio.word_error, verbatim
    left, right = expected.split(), actual.split()
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1] / max(1, len(left))


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def flags_for(audio, rate, text, transcript):
    import numpy as np
    seconds = len(audio) / rate
    loud = np.flatnonzero(np.abs(audio) > .001)
    leading = loud[0] / rate if len(loud) else seconds
    trailing = (len(audio) - loud[-1] - 1) / rate if len(loud) else seconds
    target, heard = normalize_transcript(text), normalize_transcript(transcript)
    wer = word_error(target, heard)
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    clipping = float(np.mean(np.abs(audio) >= .999))
    flags = []
    if not .25 <= seconds <= 30 or rms < 1e-5 or clipping > .001:
        flags.append("source_format_or_level_outlier")
    if not heard or wer > .25:
        # auto_screen's rescue: a words-only mismatch within 10% after normalising numbers/contractions/laughter
        if not heard or edit_rate(text, transcript) > .10:
            flags.append("possible_transcript_mismatch")
    if leading > 1.5 or trailing > 1.5:
        flags.append("long_boundary_quiet")
    if len(target.split()) / max(.1, seconds - leading - trailing) > 6:
        flags.append("possibly_rushed")
    return flags, {"word_error_rate": wer, "seconds": seconds, "laugh_heard": laugh_heard(transcript)}


def main():
    import numpy as np
    import soundfile as sf
    from faster_whisper import WhisperModel
    if not (RENDERED / "rerender-report.json").exists():
        raise SystemExit("expressive_rerender.py has not finished (no rerender-report.json); nothing screened")
    for name in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
        if not (WHISPER / name).exists():
            raise SystemExit("faster-whisper base weights missing: " + str(WHISPER / name))
    progress = {}
    for line in (RENDERED / "progress.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        progress[r["id"]] = r
    rows = [json.loads(l) for l in (RENDERED / "metadata.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    # the off-game lines (owner: "we want her to say more than just rimworld"): rendered rows join the set; a flagged
    # one is dropped, not replaced
    offgame_ids = set()
    if (OFFGAME / "render-report.json").exists():
        for l in (OFFGAME / "metadata.jsonl").read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l); rows.append(r); offgame_ids.add(r["id"])
                progress[r["id"]] = {"kept": "expressive"}
        print("off-game lines joined: %d" % len(offgame_ids), flush=True)
    elif (HERE / "OFFGAME_CORPUS.jsonl").exists() and os.environ.get("ALLOW_NO_OFFGAME") != "1":
        raise SystemExit("OFFGAME_CORPUS.jsonl exists but offgame_render.py has not finished (no render-report.json); "
                         "run it first, or ALLOW_NO_OFFGAME=1 to screen without the off-game lines")
    (OUT / "wavs").mkdir(parents=True, exist_ok=True)
    screened_path = OUT / "screening.jsonl"
    done = {}
    if screened_path.exists():
        for line in screened_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done[r["id"]] = r
    model = WhisperModel(str(WHISPER), device="cpu", compute_type="int8", cpu_threads=max(2, (os.cpu_count() or 4) - 2), num_workers=1)
    todo = [r for r in rows if r["id"] not in done]
    print("%d rows, %d screened, %d to go" % (len(rows), len(done), len(todo)), flush=True)
    started = time.monotonic()
    with open(screened_path, "a", encoding="utf-8") as log:
        for n, row in enumerate(todo, 1):
            dst = OUT / "wavs" / (row["id"] + ".wav")
            entry = {"id": row["id"], "emotion": row["emotion"], "text": row["text"]}
            if progress[row["id"]]["kept"] != "expressive":
                shutil.copy2(ORIGINAL / row["audio"], dst)      # the original A2 clip, already screened on the pod
                out_row = dict(row, audio="wavs/" + dst.name, sha256=sha(dst))
                entry.update(result="original", flags=[])
            else:
                src_dir = OFFGAME if row["id"] in offgame_ids else RENDERED
                audio, rate = sf.read(src_dir / row["audio"], dtype="float32")
                audio, trim = slow_to_target(audio, rate, row["text"])    # target 0: edges trimmed to 0.15 s, no stretch
                tmp = OUT / "wavs" / (row["id"] + ".screening.wav")
                sf.write(tmp, audio, rate, subtype="PCM_16")
                segments, _ = model.transcribe(str(tmp), language="en", beam_size=3, condition_on_previous_text=False,
                                               vad_filter=False, word_timestamps=False)
                transcript = " ".join(s.text.strip() for s in segments).strip()
                flags, meas = flags_for(audio, rate, row["text"], transcript)
                entry.update(heard=transcript, flags=flags, **meas)
                if flags and row["id"] in offgame_ids:
                    tmp.unlink()
                    out_row = None
                    entry["result"] = "dropped_offgame"
                elif flags:
                    tmp.unlink()
                    shutil.copy2(ORIGINAL / row["audio"], dst)
                    out_row = dict(row, audio="wavs/" + dst.name, sha256=sha(dst))
                    # the original clip's own labels (source_id, intensity 0.35, pace 1.0) come back with it
                    out_row.update(ORIGINAL_ROWS[row["id"]])
                    entry["result"] = "fallback_to_original"
                else:
                    os.replace(tmp, dst)
                    out_row = dict(row, audio="wavs/" + dst.name, sha256=sha(dst))
                    entry["result"] = "kept_expressive"
            entry["row"] = out_row
            log.write(json.dumps(entry, ensure_ascii=False) + "\n"); log.flush()
            done[row["id"]] = entry
            if n % 50 == 0:
                rate_ = n / (time.monotonic() - started)
                print("%d/%d  (%.1f clips/s, ~%.0f min left)" % (n, len(todo), rate_, (len(todo) - n) / rate_ / 60), flush=True)
    with open(OUT / "metadata.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            if done[row["id"]]["row"]:
                f.write(json.dumps(done[row["id"]]["row"], ensure_ascii=False) + "\n")
    rows_out, identity = load_dataset(str(OUT), verify_audio=True)   # the contract's own check of the result
    counts = {}
    for e in done.values():
        counts[e["result"]] = counts.get(e["result"], 0) + 1
    report = {"schema": "unity-voice-expressive-screen-v1", "rule": "auto_screen.py / inspect_source_audio.py rules, "
              "faster-whisper base int8; a flagged re-performed clip falls back to its original recording and labels",
              "dataset": identity, "counts": counts,
              "flag_counts": {}, "fallbacks": [], "training_started": False}
    for e in done.values():
        for fl in e.get("flags", []):
            report["flag_counts"][fl] = report["flag_counts"].get(fl, 0) + 1
        if e["result"] in ("fallback_to_original", "dropped_offgame"):
            src_dir = OFFGAME if e["result"] == "dropped_offgame" else RENDERED
            report["fallbacks"].append({"id": e["id"], "result": e["result"], "emotion": e["emotion"], "text": e["text"],
                                        "heard": e.get("heard"), "flags": e["flags"],
                                        "rendered_wav": str(src_dir / "wavs" / (e["id"] + ".wav"))})
    (OUT / "screen-report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print("DONE", json.dumps({"counts": counts, "flags": report["flag_counts"], "dataset_id": identity["dataset_id"][:12]}), flush=True)


ORIGINAL_ROWS = {}
for _line in (ORIGINAL / "metadata.jsonl").read_text(encoding="utf-8").splitlines():
    if _line.strip():
        _r = json.loads(_line)
        ORIGINAL_ROWS[_r["id"]] = {"intensity": _r["intensity"], "pace": _r["pace"], "source_id": _r["source_id"]}


if __name__ == "__main__":
    main()
