"""Own-student code identity and resumable random state; no model import at module load."""
from pathlib import Path
import math
import random

from dataset_contract import canonical_hash, file_hash

SOURCE_FILES = ("model.py", "vocoder.py", "prep.py", "train_acoustic.py", "train_vocoder.py", "infer.py",
                "feature_arrays.py", "speech_turns.py", "student_state.py")


def student_source_identity():
    body = {"schema": "unity-student-source-v1", "files_sha256": {
        name: file_hash(Path(__file__).with_name(name)) for name in SOURCE_FILES}}
    return dict(body, source_id=canonical_hash(body))


def require_student_checkpoint(checkpoint):
    if checkpoint.get("student_source") != student_source_identity():
        raise ValueError("Checkpoint lacks this exact student implementation identity; preserve it and use a fresh approved run")


def require_finite_state(state, label):
    import torch
    pending = [state]
    while pending:
        value = pending.pop()
        if isinstance(value, torch.Tensor):
            if not torch.isfinite(value).all().item():
                raise ValueError("Nonfinite checkpoint tensor: " + label)
        elif isinstance(value, dict):
            pending.extend(value.values())
        elif isinstance(value, (list, tuple)):
            pending.extend(value)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Nonfinite checkpoint scalar: " + label)


def capture_random_state():
    # NumPy arrays become primitive lists: torch.load(weights_only=True) stays usable.
    import numpy as np
    import torch
    state = np.random.get_state()
    return {"python": random.getstate(), "numpy": [state[0], state[1].tolist(), state[2], state[3], state[4]],
            "torch": torch.get_rng_state(), "cuda": torch.cuda.get_rng_state_all()}


def restore_random_state(state):
    import numpy as np
    import torch
    if not isinstance(state, dict) or set(state) != {"python", "numpy", "torch", "cuda"}:
        raise ValueError("Working checkpoint lacks complete random-state recovery")
    numpy_state = state["numpy"]
    if len(numpy_state) != 5 or len(state["cuda"]) != torch.cuda.device_count():
        raise ValueError("Random-state backend/device count differs from the working checkpoint")
    random.setstate(state["python"])
    np.random.set_state((numpy_state[0], np.asarray(numpy_state[1], dtype=np.uint32), *numpy_state[2:]))
    torch.set_rng_state(state["torch"].cpu())
    torch.cuda.set_rng_state_all([value.cpu() for value in state["cuda"]])


def require_data_order(order, cursor, count):
    if not isinstance(order, list) or type(cursor) is not int or not 0 <= cursor <= len(order):
        raise ValueError("Working acoustic checkpoint lacks valid batch-position recovery")
    if any(not isinstance(batch, list) or not batch or any(type(index) is not int for index in batch) for batch in order):
        raise ValueError("Malformed saved acoustic batch order")
    flattened = [index for batch in order for index in batch]
    if sorted(flattened) != list(range(count)):
        raise ValueError("Saved acoustic batch order differs from the exact TRAIN inventory")
