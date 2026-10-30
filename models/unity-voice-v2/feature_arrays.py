"""Shared strict feature-array checks, independent of Torch/model execution."""
from pathlib import Path

import numpy as np
from dataset_contract import MAX_FRAMES, MAX_PHONEMES, FEATURES, file_hash
from speech_text import EVENT_NAMES


def require_prepared_frontend(manifest):
    config = manifest["frontend"]["config"]
    expected = {"prep_sha256": Path(__file__).with_name("prep.py"),
                "feature_arrays_sha256": Path(__file__)}
    if any(config.get(key) != file_hash(path) for key, path in expected.items()):
        raise ValueError("Feature preparation/array-validation code changed; preserve old features and prepare a fresh directory")


def read_feature(path, entry, vocab):
    """Refuse truncated/floating token IDs and inconsistent pitch/voicing before casting."""
    with np.load(path, allow_pickle=False) as stored:
        if set(stored.files) != {"phon", "mel", "f0", "energy", "voiced"}:
            raise ValueError("Unexpected feature array inventory: " + entry["id"])
        values = {key: stored[key].copy() for key in stored.files}
    phon, mel = values["phon"], values["mel"]
    frames, tokens = entry["frames"], entry["phonemes"]
    if (type(frames) is not int or type(tokens) is not int or not 1 <= tokens <= MAX_PHONEMES
            or not tokens <= frames <= MAX_FRAMES or phon.dtype != np.int64 or phon.shape != (tokens,)
            or mel.dtype != np.float32 or mel.shape != (FEATURES["n_mels"], frames)
            or (phon <= 0).any() or (phon >= len(vocab)).any()):
        raise ValueError("Invalid feature shapes/token dtype/range: " + entry["id"])
    for key in ("f0", "energy", "voiced"):
        if values[key].dtype != np.float32 or values[key].shape != (frames,):
            raise ValueError("Invalid feature curve shape/dtype: " + entry["id"])
    if not all(np.isfinite(value).all() for value in values.values()):
        raise ValueError("Nonfinite feature arrays: " + entry["id"])
    if ((values["f0"] < 0).any() or (values["energy"] < 0).any()
            or not np.array_equal(values["voiced"], (values["f0"] > 0).astype(np.float32))):
        raise ValueError("Pitch/voicing/energy feature mismatch: " + entry["id"])
    if (type(entry["samples"]) is not int or type(entry["original_samples"]) is not int
            or entry["samples"] != frames * FEATURES["hop"]
            or not 0 < entry["original_samples"] <= entry["samples"]
            or not 0 <= entry["samples"] - entry["original_samples"] < FEATURES["hop"]):
        raise ValueError("Feature waveform/frame extent mismatch: " + entry["id"])
    for token, name in EVENT_NAMES.items():
        actual = int(np.count_nonzero(phon == vocab[token])) if token in vocab else 0
        if actual != entry["events"][name]:
            raise ValueError("Feature event token count differs from marked transcript: " + entry["id"])
    return values
