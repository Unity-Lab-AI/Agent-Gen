"""Versioned, source-only contracts for Unity's own-weight speech student.

No old metadata.csv, globbed feature leftovers, or smoke checkpoints are v2 inputs.
An accepted teacher dataset uses metadata.jsonl: one exact JSON object per clip.
Labels describe the recorded performance; labeling neutral audio 'sad' is not supervision.
Known [laughter]/[breath] markers require matching nonverbal source performances;
manifest counts only record supervision claims, while source QA establishes audibility.
This module uses only the standard library so the teacher builder can share it.
"""
import hashlib
import importlib.metadata
import json
import math
import os
import re
import unicodedata
import uuid
from pathlib import Path
from speech_text import (EVENT_MARKERS, EVENT_NAMES, FRONTEND_VERSION, event_counts,
                         event_only_group, lexical_text)

DATASET_SCHEMA = "unity-voice-dataset-v2"
FEATURE_SCHEMA = "unity-voice-features-v2"
CHECKPOINT_SCHEMA = "unity-voice-checkpoint-v2"
EMOTIONS = ("neutral", "warm", "happy", "amused", "excited", "sad", "concerned", "frustrated", "surprised")
SPEECH_ACTS = ("statement", "yes_no_question", "wh_question", "exclamation", "instruction", "reassurance", "aside")
MIN_PACE, MAX_PACE = 0.75, 1.35  # multiplier of the intended natural duration, not teacher-specific speed
MAX_PHONEMES, MAX_FRAMES, MAX_PHONE_FRAMES = 512, 3000, 256
FEATURES = {
    "sample_rate": 24000, "n_fft": 1024, "hop": 256, "n_mels": 80,
    "f_min": 0, "f_max": 12000, "power": 1.0, "center": False,
    "reflect_pad": 384, "log_floor": 1e-5, "mel_scale": "htk", "mel_norm": None,
    "g2p": "misaki.en.G2P", "misaki_version": "0.9.4", "british": False, "trf": False,
    "speech_frontend_version": FRONTEND_VERSION, "event_vocabulary": EVENT_MARKERS,
    "tokenization": "ordinary G2P character phonemes plus single dedicated event tokens",
    "pitch": "WORLD dio plus stonemask; nearest mel-window center; separate voiced mask",
    "energy": "mean linear mel amplitude", "min_seconds": 0.25, "max_seconds": 30.0,
}
ACOUSTIC_CONFIG = {"n_mels": 80, "d": 256, "enc": 4, "dec": 4, "conditioning": "emotion-act-intensity-pace-v2", "voicing": True}
VOCODER_CONFIG = {"n_mels": 80, "ch": 512, "rates": [8, 8, 2, 2], "kernels": [16, 16, 4, 4],
                  "rk": [3, 7, 11], "rd": [[1, 3, 5], [1, 3, 5], [1, 3, 5]]}
ROW_FIELDS = {"schema", "id", "text", "audio", "sha256", "sample_rate", "voice_id", "source_id",
              "emotion", "intensity", "pace", "speech_act"}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_transcript(text):
    """One split group for lexical duplicates, including punctuation/style variants."""
    text = unicodedata.normalize("NFKC", lexical_text(text)).casefold().replace("’", "'")
    return " ".join(re.sub(r"[^\w']+", " ", text, flags=re.UNICODE).split())


def split_for(text):
    group = normalize_transcript(text)
    if not group:
        group = event_only_group(text)
    if not group:
        raise ValueError("Transcript has no lexical content or supported event")
    return "heldout" if int(hashlib.sha256(group.encode("utf-8")).hexdigest()[:8], 16) % 50 == 0 else "train"


def finite_number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("%s must be finite in [%s, %s]" % (name, low, high))
    return float(value)


def delivery(emotion="neutral", intensity=0.0, pace=1.0, speech_act="statement"):
    if emotion not in EMOTIONS or speech_act not in SPEECH_ACTS:
        raise ValueError("Unknown spoken emotion/speech act; supported nonverbal events use exact text markers")
    return {"emotion": emotion, "intensity": finite_number(intensity, "intensity", 0, 1),
            "pace": finite_number(pace, "pace", MIN_PACE, MAX_PACE), "speech_act": speech_act}


def local_path(root, relative):
    """All manifest files must remain under the supplied root, including symlink targets."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("Manifest paths must be nonempty relative paths using '/' separators")
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or ":" in relative:
        raise ValueError("Unsafe manifest path: " + relative)
    root = Path(root).resolve()
    path = (root / rel).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Manifest path escapes its root: " + relative)
    return path


def load_dataset(root, verify_audio=True):
    """Return exact manifest rows and an immutable identity. No CSV compatibility path."""
    root = Path(root)
    path = root / "metadata.jsonl"
    if not path.is_file():
        raise ValueError("v2 requires labeled metadata.jsonl; old unlabeled metadata.csv is rejected")
    rows, ids, audio_paths = [], set(), set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError("Blank metadata line %d" % number)
        row = json.loads(line)
        if not isinstance(row, dict) or set(row) != ROW_FIELDS or row.get("schema") != DATASET_SCHEMA:
            raise ValueError("Line %d must contain exactly the v2 row fields: %s" % (number, sorted(ROW_FIELDS)))
        if not isinstance(row["id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", row["id"]) or row["id"] in ids:
            raise ValueError("Duplicate or unsafe clip id at line %d" % number)
        if (not isinstance(row["text"], str) or len(row["text"]) > 4000
                or not (normalize_transcript(row["text"]) or event_only_group(row["text"]))):
            raise ValueError("Missing/overlong transcript at line %d" % number)
        for field in ("voice_id", "source_id"):
            if not isinstance(row[field], str) or not row[field].strip() or len(row[field]) > 256:
                raise ValueError("Missing %s at line %d" % (field, number))
        if row["sample_rate"] != FEATURES["sample_rate"] or isinstance(row["sample_rate"], bool):
            raise ValueError("Every source WAV must be 24000 Hz")
        if not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError("Expected lowercase WAV SHA256 at line %d" % number)
        delivery(row["emotion"], row["intensity"], row["pace"], row["speech_act"])
        audio = local_path(root, row["audio"])
        if audio.suffix.lower() != ".wav" or row["audio"] in audio_paths or not audio.is_file():
            raise ValueError("Missing/duplicate WAV at line %d" % number)
        if verify_audio and file_hash(audio) != row["sha256"]:
            raise ValueError("WAV hash mismatch: " + row["id"])
        ids.add(row["id"]); audio_paths.add(row["audio"]); rows.append(row)
    if not rows or len({r["voice_id"] for r in rows}) != 1:
        raise ValueError("Dataset must contain one nonempty approved voice identity")
    if {split_for(r["text"]) for r in rows} != {"train", "heldout"}:
        raise ValueError("Dataset needs both grouped train and heldout transcripts")
    return rows, {"schema": DATASET_SCHEMA, "dataset_id": canonical_hash(rows), "metadata_sha256": file_hash(path),
                  "voice_id": rows[0]["voice_id"], "source_ids": sorted({r["source_id"] for r in rows}), "clips": len(rows)}


def frontend_identity():
    """Record exact installed feature extraction dependencies, not a guessed source version."""
    versions = {name: importlib.metadata.version(name) for name in ("misaki", "torch", "torchaudio", "pyworld", "soundfile", "numpy")}
    if versions["misaki"] != FEATURES["misaki_version"]:
        raise ValueError("v2 phoneme frontend requires misaki==" + FEATURES["misaki_version"])
    config = {"features": FEATURES, "versions": versions,
              "speech_text_sha256": file_hash(Path(__file__).with_name("speech_text.py"))}
    return {"config": config, "frontend_id": canonical_hash(config)}


def delivery_support(entries):
    """Actual training coverage, not a promise that every declared style has been learned."""
    grouped = {}
    for entry in entries:
        if entry["split"] != "train":
            continue
        key = (entry["emotion"], entry["speech_act"])
        grouped.setdefault(key, []).append(entry)
    return [{"emotion": emotion, "speech_act": act, "clips": len(rows),
             "transcripts": len({normalize_transcript(row["text"]) or event_only_group(row["text"]) for row in rows}),
             "intensity_min": min(row["intensity"] for row in rows), "intensity_max": max(row["intensity"] for row in rows),
             "pace_min": min(row["pace"] for row in rows), "pace_max": max(row["pace"] for row in rows)}
            for (emotion, act), rows in sorted(grouped.items())]


def event_support(entries):
    """Count accepted-manifest TRAIN event labels; the source QA gate owns audible verification."""
    support = {}
    for name in EVENT_NAMES.values():
        rows = [entry for entry in entries if entry["split"] == "train" and event_counts(entry["text"])[name] > 0]
        support[name] = {"train_clips": len(rows),
                         "train_occurrences": sum(event_counts(row["text"])[name] for row in rows),
                         "delivery_support": delivery_support(rows)}
    return support


def support_identity(entries):
    return {"delivery_support": delivery_support(entries), "event_support": event_support(entries)}


def pair_identity(feature_manifest):
    return {"schema": CHECKPOINT_SCHEMA, "feature_id": feature_manifest["feature_id"],
            "dataset_id": feature_manifest["dataset"]["dataset_id"], "voice_id": feature_manifest["dataset"]["voice_id"],
            "frontend_id": feature_manifest["frontend"]["frontend_id"], "vocab_id": canonical_hash(feature_manifest["vocab"]),
            "stats_id": canonical_hash(feature_manifest["stats"]), "support_id": canonical_hash(support_identity(feature_manifest["entries"])),
            "acoustic_config": ACOUSTIC_CONFIG, "vocoder_config": VOCODER_CONFIG,
            "emotions": list(EMOTIONS), "speech_acts": list(SPEECH_ACTS)}


def load_features(root, verify_files=True):
    root = Path(root)
    path = root / "features-manifest.json"
    if not path.is_file():
        raise ValueError("v2 features-manifest.json missing; legacy globbed features are refused")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != FEATURE_SCHEMA:
        raise ValueError("Unsupported feature schema")
    body = {k: v for k, v in manifest.items() if k != "feature_id"}
    if canonical_hash(body) != manifest.get("feature_id"):
        raise ValueError("Feature manifest identity mismatch")
    if manifest["frontend"]["config"]["features"] != FEATURES:
        raise ValueError("Feature/frontend configuration differs; preserve the cache and prepare a fresh feature directory")
    if canonical_hash(manifest["frontend"]["config"]) != manifest["frontend"]["frontend_id"]:
        raise ValueError("Feature frontend identity mismatch")
    if manifest["frontend"]["config"].get("speech_text_sha256") != file_hash(Path(__file__).with_name("speech_text.py")):
        raise ValueError("Speech-event parser source changed; preserve this cache and prepare a fresh feature directory")
    if manifest.get("emotions") != list(EMOTIONS) or manifest.get("speech_acts") != list(SPEECH_ACTS):
        raise ValueError("Feature delivery vocabulary mismatch")
    entries, ids, expected = manifest["entries"], set(), set()
    if not entries or {e["split"] for e in entries} != {"train", "heldout"}:
        raise ValueError("Empty features or missing grouped split")
    stats = manifest["stats"]
    if stats.get("normalization_split") != "train":
        raise ValueError("Normalization must use the training split only")
    for field in ("lf0_mean", "lf0_std", "e_mean", "e_std"):
        value = stats.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Invalid normalization statistic: " + field)
    if min(stats["lf0_std"], stats["e_std"]) <= 1e-6:
        raise ValueError("Normalization variance is degenerate")
    vocab = manifest["vocab"]
    if (vocab.get("<pad>") != 0 or vocab.get(" ") != 1 or set(vocab.values()) != set(range(len(vocab)))
            or any(type(index) is not int for index in vocab.values())
            or any(not isinstance(token, str) or (len(token) != 1 and token not in {"<pad>", *EVENT_NAMES}) for token in vocab)):
        raise ValueError("Feature phoneme vocabulary is invalid")
    expected_event_tokens = {token for entry in entries for token, name in EVENT_NAMES.items() if event_counts(entry["text"])[name] > 0}
    if set(vocab).intersection(EVENT_NAMES) != expected_event_tokens:
        raise ValueError("Event vocabulary differs from the exact recorded-manifest event inventory")
    for entry in entries:
        if entry["id"] in ids or entry["split"] != split_for(entry["text"]):
            raise ValueError("Duplicate feature id or invalid grouped split")
        ids.add(entry["id"]); expected.add(entry["feature"])
        if entry.get("events") != event_counts(entry["text"]):
            raise ValueError("Feature event counts differ from their exact marked transcript")
        if entry.get("text_group") != (normalize_transcript(entry["text"]) or event_only_group(entry["text"])):
            raise ValueError("Feature lexical split group differs from its event-free transcript")
        delivery(entry["emotion"], entry["intensity"], entry["pace"], entry["speech_act"])
        file = local_path(root, entry["feature"])
        if not file.is_file() or (verify_files and file_hash(file) != entry["sha256"]):
            raise ValueError("Feature hash mismatch/missing: " + entry["id"])
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*.npz")}
    if actual != expected:
        raise ValueError("Unmanifested feature leftovers/missing files; create a fresh feature directory")
    return manifest


def require_checkpoint(checkpoint, identity, kind):
    if checkpoint.get("schema") != CHECKPOINT_SCHEMA or checkpoint.get("kind") != kind or checkpoint.get("identity") != identity:
        raise ValueError("Checkpoint is legacy or belongs to a different dataset/frontend/config/model pair; use a fresh v2 checkpoint directory")


def voice_metadata(manifest):
    return {"schema": CHECKPOINT_SCHEMA, "identity": pair_identity(manifest), "pair_id": canonical_hash(pair_identity(manifest)),
            "vocab": manifest["vocab"], "stats": manifest["stats"], "frontend": manifest["frontend"],
            "delivery_support": delivery_support(manifest["entries"]),
            "event_support": event_support(manifest["entries"])}


def ensure_voice_metadata(directory, manifest):
    """Both parallel trainers publish the same complete record using unique temporary names."""
    path = Path(directory) / "voice-meta.json"
    metadata = voice_metadata(manifest)
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != metadata:
            raise ValueError("Checkpoint directory metadata is legacy or belongs to another pair")
        return metadata
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != metadata:
        raise ValueError("Another trainer published a different metadata identity; preserve the new temporary record")
    os.replace(temporary, path)
    return metadata
