"""Synthesize with a matching own-weight v2 acoustic/vocoder pair.

python training/voice/infer.py <ckpt_dir> "text" <new_out.wav> --emotion warm --intensity .35
--speech-act yes_no_question --pace 1.0

These are learned spoken styles and recorded event tokens, not fabricated acting. A completed checkpoint
is not an accepted stream voice; deployment is governed by the separate quality gate.
Explicit [laughter]/[breath] require recorded TRAIN event support in this exact pair.
"""
import argparse, os
import importlib.metadata
import json
import math
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from misaki import en, espeak

from dataset_contract import (ACOUSTIC_CONFIG, CHECKPOINT_SCHEMA, EMOTIONS, FEATURES, MAX_PHONEMES,
                              SPEECH_ACTS, VOCODER_CONFIG, canonical_hash, delivery, file_hash, require_checkpoint)
from model import UnityVoice
from feature_arrays import require_prepared_frontend
from speech_text import EVENT_NAMES, event_counts, lexical_text, speech_tokens
from speech_turns import MAX_TURN_SECONDS, plan_turn
from student_state import require_finite_state, require_student_checkpoint
from vocoder import Generator


def inferred_speech_act(text):
    """Minimal punctuation fallback; callers should supply intent for ambiguous/rhetorical speech."""
    text = lexical_text(text)
    if text.rstrip().endswith("?"):
        first = text.lower().lstrip().split(maxsplit=1)[0].strip(".,?!:;")
        return "wh_question" if first in ("what", "who", "where", "when", "why", "how", "which", "whose") else "yes_no_question"
    return "exclamation" if text.rstrip().endswith("!") else "statement"


def validate_metadata(meta):
    identity = meta.get("identity", {})
    if (meta.get("schema") != CHECKPOINT_SCHEMA or identity.get("schema") != CHECKPOINT_SCHEMA
            or meta.get("pair_id") != canonical_hash(identity) or identity.get("acoustic_config") != ACOUSTIC_CONFIG
            or identity.get("vocoder_config") != VOCODER_CONFIG or identity.get("emotions") != list(EMOTIONS)
            or identity.get("speech_acts") != list(SPEECH_ACTS)):
        raise ValueError("Legacy/mismatched voice metadata; v2 needs an identity-bound trained model pair")
    vocab = meta["vocab"]
    if (vocab.get("<pad>") != 0 or vocab.get(" ") != 1 or set(vocab.values()) != set(range(len(vocab)))
            or any(type(index) is not int for index in vocab.values())
            or any(not isinstance(token, str) or (len(token) != 1 and token not in {"<pad>", *EVENT_NAMES}) for token in vocab)
            or identity.get("vocab_id") != canonical_hash(vocab)):
        raise ValueError("Phoneme vocabulary identity is invalid")
    frontend = meta["frontend"]
    if (frontend["config"]["features"] != FEATURES or canonical_hash(frontend["config"]) != frontend["frontend_id"]
            or frontend["frontend_id"] != identity.get("frontend_id")
            or frontend["config"].get("speech_text_sha256") != file_hash(Path(__file__).with_name("speech_text.py"))):
        raise ValueError("Frontend/feature configuration mismatch")
    if importlib.metadata.version("misaki") != FEATURES["misaki_version"]:
        raise ValueError("Runtime requires the same misaki==0.9.4 phoneme frontend")
    require_prepared_frontend(meta)
    supports = {"delivery_support": meta.get("delivery_support"), "event_support": meta.get("event_support")}
    if (meta["stats"].get("normalization_split") != "train" or canonical_hash(meta["stats"]) != identity.get("stats_id")
            or canonical_hash(supports) != identity.get("support_id")):
        raise ValueError("Voice normalization/delivery/event support lacks the v2 train-only identity")
    for name in ("lf0_mean", "lf0_std", "e_mean", "e_std"):
        value = meta["stats"].get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Invalid voice normalization statistic: " + name)
    if min(meta["stats"]["lf0_std"], meta["stats"]["e_std"]) <= 1e-6:
        raise ValueError("Voice normalization variance is degenerate")
    validate_support_rows(supports["delivery_support"], allow_empty=False)
    if not isinstance(supports["event_support"], dict) or set(supports["event_support"]) != set(EVENT_NAMES.values()):
        raise ValueError("Voice metadata lacks the exact supported event inventory")
    for token, name in EVENT_NAMES.items():
        support = supports["event_support"][name]
        if not isinstance(support, dict) or set(support) != {"train_clips", "train_occurrences", "delivery_support"}:
            raise ValueError("Malformed event training support: " + name)
        clips, occurrences = support["train_clips"], support["train_occurrences"]
        if (type(clips) is not int or type(occurrences) is not int or clips < 0 or occurrences < clips
                or (clips == 0) != (occurrences == 0) or not isinstance(support["delivery_support"], list)
                or (clips > 0 and (token not in vocab or not support["delivery_support"]))
                or (clips == 0 and support["delivery_support"])):
            raise ValueError("Event has inconsistent TRAIN coverage: " + name)
        validate_support_rows(support["delivery_support"], allow_empty=True)
        if sum(row["clips"] for row in support["delivery_support"]) != clips:
            raise ValueError("Event delivery counts differ from their TRAIN inventory: " + name)
    return identity


def validate_support_rows(rows, allow_empty):
    fields = {"emotion", "speech_act", "clips", "transcripts", "intensity_min", "intensity_max", "pace_min", "pace_max"}
    if not isinstance(rows, list) or (not rows and not allow_empty):
        raise ValueError("Voice metadata lacks recorded TRAIN delivery coverage")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("Malformed TRAIN delivery support record")
        key = (row["emotion"], row["speech_act"])
        if (key in seen or type(row["clips"]) is not int or type(row["transcripts"]) is not int
                or not 1 <= row["transcripts"] <= row["clips"]):
            raise ValueError("Duplicate/invalid TRAIN delivery counts")
        delivery(row["emotion"], row["intensity_min"], row["pace_min"], row["speech_act"])
        delivery(row["emotion"], row["intensity_max"], row["pace_max"], row["speech_act"])
        if row["intensity_min"] > row["intensity_max"] or row["pace_min"] > row["pace_max"]:
            raise ValueError("Reversed TRAIN delivery bounds")
        seen.add(key)


def supports_delivery(rows, chosen):
    """Require a seen emotion/act and its recorded scalar range, including for events."""
    support = next((row for row in rows if row["emotion"] == chosen["emotion"] and row["speech_act"] == chosen["speech_act"]), None)
    return (support is not None and support["intensity_min"] <= chosen["intensity"] <= support["intensity_max"]
            and support["pace_min"] <= chosen["pace"] <= support["pace_max"])


# The teacher clips run ~4.0 words/s; the owner chose ~3.3 ("Slow to about 3.3 w/s (Recommended)"). Slowing the audio
# itself smeared it ("they all sound like two recording just offset"), so the student stretches its own phoneme
# durations instead: 1.2 x. A list so the CLI flag can set it.
LENGTH_SCALE = [float(os.environ.get("UNITY_VOICE_LENGTH_SCALE", "1.2"))]

class Voice:
    def __init__(self, ckpt, dev=None):
        self.dev = dev or ("cuda" if torch.cuda.is_available() else "cpu")
        path = Path(ckpt)
        meta = json.loads((path / "voice-meta.json").read_text(encoding="utf-8"))
        identity = validate_metadata(meta)
        acoustic = torch.load(path / "acoustic.pt", map_location=self.dev, weights_only=True)
        vocoder = torch.load(path / "vocoder.pt", map_location=self.dev, weights_only=True)
        require_checkpoint(acoustic, identity, "acoustic")
        require_checkpoint(vocoder, identity, "vocoder")
        require_student_checkpoint(acoustic)
        require_student_checkpoint(vocoder)
        if (acoustic.get("n_symbols") != len(meta["vocab"])
                or any(type(checkpoint.get("step")) is not int or checkpoint["step"] < 1 for checkpoint in (acoustic, vocoder))):
            raise ValueError("Model pair is untrained or has the wrong symbol count")
        require_finite_state(acoustic["model"], "acoustic inference weights")
        require_finite_state(vocoder["G"], "vocoder inference weights")
        mode = vocoder.get("input_mode")
        provenance = vocoder.get("input_provenance")
        if mode == "source":
            if provenance != {"mode": "source", "feature_id": identity["feature_id"]}:
                raise ValueError("Vocoder source provenance differs from this pair")
        elif mode == "oracle-gta":
            acoustic_sha = acoustic.get("working_checkpoint_sha256") or file_hash(path / "acoustic.pt")
            if (not isinstance(provenance, dict) or set(provenance) != {"mode", "feature_id", "acoustic_sha256", "mel_manifest_sha256"}
                    or provenance["mode"] != mode or provenance["feature_id"] != identity["feature_id"]
                    or provenance["acoustic_sha256"] != acoustic_sha):
                raise ValueError("GTA vocoder was trained for another exact acoustic checkpoint/export")
        else:
            raise ValueError("Vocoder lacks a supported exact input provenance")
        self.vocab = meta["vocab"]
        self.support = meta["delivery_support"]
        self.event_support = meta["event_support"]
        self.am = UnityVoice(len(self.vocab), **ACOUSTIC_CONFIG).to(self.dev).eval()
        self.am.load_state_dict(acoustic["model"])
        self.voc = Generator(**VOCODER_CONFIG).to(self.dev).eval()
        self.voc.load_state_dict(vocoder["G"])
        self.g2p = en.G2P(trf=False, british=False, fallback=espeak.EspeakFallback(british=False))

    @torch.no_grad()
    def _say_chunk(self, text, emotion="neutral", intensity=None, pace=1.0, speech_act=None):
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise ValueError("Speech text must be nonempty and bounded")
        chosen = delivery(emotion, (0.0 if emotion == "neutral" else 0.35) if intensity is None else intensity,
                          pace, speech_act or inferred_speech_act(text))
        if not supports_delivery(self.support, chosen):
            raise ValueError("Requested delivery is outside this pair's recorded training support; no unseen acting is promised")
        phon = speech_tokens(text, self.g2p, MAX_PHONEMES)
        for name, count in event_counts(text).items():
            if count:
                support = self.event_support[name]
                if (support["train_clips"] < 1 or support["train_occurrences"] < 1
                        or not supports_delivery(support["delivery_support"], chosen)):
                    raise ValueError("Requested event lacks recorded TRAIN support for this delivery: " + name)
        unknown = sorted(set(phon) - set(self.vocab))
        if unknown:
            raise ValueError("Unknown phonemes must be repaired in the pronunciation/frontend data, not dropped: " + repr(unknown))
        ids = torch.tensor([[self.vocab[token] for token in phon]], device=self.dev, dtype=torch.long)
        condition = {"emotion": torch.tensor([EMOTIONS.index(chosen["emotion"])], device=self.dev, dtype=torch.long),
                     "speech_act": torch.tensor([SPEECH_ACTS.index(chosen["speech_act"])], device=self.dev, dtype=torch.long),
                     "intensity": torch.tensor([chosen["intensity"]], device=self.dev, dtype=torch.float32),
                     "pace": torch.tensor([chosen["pace"]], device=self.dev, dtype=torch.float32)}
        mel = self.am.infer(ids, condition, LENGTH_SCALE[0])
        wav = self.voc(mel).squeeze().float().cpu().numpy()
        if (wav.ndim != 1 or len(wav) != mel.size(2) * FEATURES["hop"] or not len(wav)
                or not np.isfinite(wav).all() or np.max(np.abs(wav)) > 1.0):
            raise ValueError("Vocoder produced invalid audio")
        return wav

    def say(self, text, emotion="neutral", intensity=None, pace=1.0, speech_act=None, *, pauses=None, focus=None):
        """Bounded segmented turn; pauses are silence, not learned prosody/emotional effects."""
        chunks = plan_turn(text, pauses=pauses, focus=focus)
        output, samples = [], 0
        rate = FEATURES["sample_rate"]
        for index, chunk in enumerate(chunks):
            wav = self._say_chunk(chunk["text"], emotion, intensity, pace, speech_act)
            pause_samples = round(chunk["pause_seconds"] * rate)
            samples += len(wav) + pause_samples
            if samples > round(MAX_TURN_SECONDS * rate):
                raise ValueError("Predicted turn exceeds 120 seconds; split it explicitly")
            if len(chunks) > 1 or pause_samples:
                # Short gain-only boundary ramps prevent discontinuity clicks; no pitch/time-stretch effects.
                wav = wav.copy()
                ramp = min(round(.005 * rate), len(wav) // 2)
                if ramp:
                    if index:
                        wav[:ramp] *= np.linspace(0, 1, ramp, dtype=np.float32)
                    if index < len(chunks) - 1 or pause_samples:
                        wav[-ramp:] *= np.linspace(1, 0, ramp, dtype=np.float32)
            output.append(wav)
            if pause_samples:
                output.append(np.zeros(pause_samples, dtype=np.float32))
        return np.concatenate(output)


def cli_pauses(values):
    pauses = []
    for value in values:
        phrase, separator, seconds = value.rpartition("=")
        if not separator:
            raise ValueError("--pause-after must be 'unique phrase=seconds'")
        pauses.append({"after": phrase, "seconds": float(seconds)})
    return pauses


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ckpt"); parser.add_argument("text"); parser.add_argument("out")
    parser.add_argument("--emotion", default="neutral", choices=EMOTIONS)
    parser.add_argument("--intensity", type=float)
    parser.add_argument("--pace", type=float, default=1.0)
    parser.add_argument("--length-scale", type=float, help="stretch predicted durations (default UNITY_VOICE_LENGTH_SCALE or 1.2)")
    parser.add_argument("--speech-act", choices=SPEECH_ACTS)
    parser.add_argument("--pause-after", action="append", default=[], help="Unique literal phrase=seconds; mechanical pause, 0.05..2 seconds")
    parser.add_argument("--focus", action="append", help="Unsupported: requires performed word-level supervision; fails explicitly")
    args = parser.parse_args()
    if args.length_scale is not None:
        LENGTH_SCALE[0] = args.length_scale
    destination = Path(args.out)
    if destination.exists():
        raise ValueError("Output already exists; preserve it and choose a new sample path")
    pauses = cli_pauses(args.pause_after)
    plan_turn(args.text, pauses=pauses, focus=args.focus)  # reject unsupported controls before loading any checkpoints
    wav = Voice(args.ckpt).say(args.text, args.emotion, args.intensity, args.pace, args.speech_act, pauses=pauses, focus=args.focus)
    destination.parent.mkdir(parents=True, exist_ok=True)
    sf.write(destination, wav, FEATURES["sample_rate"], subtype="PCM_16")
    print("wrote", destination, "-- sample only; no quality acceptance implied")


if __name__ == "__main__":
    main()
