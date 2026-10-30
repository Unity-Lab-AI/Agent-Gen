#!/usr/bin/env python3
"""Fetch every model Agent Gen runs on into one models folder. Idempotent: finished files are skipped, partial
downloads resume. Run by the app's first-run installer, or by hand:

    python scripts/fetch-models.py [--models models] [--only ditto,ltx,sd,ipadapter,whisper,voice] [--voice-src DIR]

  ditto      digital-avatar/ditto-talkinghead  cfg + PyTorch + ONNX weights (live face)         ~4.6 GB
  ltx        Lightricks/LTX-Video              2B 0.9.8 distilled + T5-XXL text encoder (motion) ~26 GB
  sd         SG161222/Realistic_Vision_V5.1_noVAE  (her looks)                                   ~2.1 GB
  ipadapter  h94/IP-Adapter plus-face + image encoder, into the HF cache (face lock)             ~1.3 GB
  whisper    Systran/faster-whisper-small, into the HF cache (her ears)                          ~0.5 GB
  voice      unity-voice-v2 (the lab's own voice), copied from --voice-src when it is elsewhere   ~160 MB
The HF cache is <models>/hf (HF_HOME) so an uninstall removes it with the rest.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
ap = argparse.ArgumentParser(description="fetch Agent Gen model weights")
ap.add_argument("--models", default=str(REPO / "models"))
ap.add_argument("--only", default="ditto,ltx,sd,ipadapter,whisper,voice")
ap.add_argument("--voice-src", default=str(REPO / "models" / "unity-voice-v2"))
ARGS = ap.parse_args()
M = Path(ARGS.models)
M.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(M / "hf"))
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

from huggingface_hub import hf_hub_download, snapshot_download  # noqa: E402  (after HF_HOME)


def log(*a):
    print("fetch:", *a, flush=True)


def ditto():
    if (M / "ditto" / "ditto_cfg" / "v0.4_hubert_cfg_pytorch.pkl").exists() and (M / "ditto" / "ditto_pytorch").exists():
        return log("ditto present")
    log("ditto: cfg + pytorch + onnx weights")
    snapshot_download("digital-avatar/ditto-talkinghead", local_dir=str(M / "ditto"),
                      allow_patterns=["ditto_cfg/*", "ditto_pytorch/**", "ditto_onnx/*", "README.md"])


def ltx():
    d = M / "ltx-video"
    if (d / "ltxv-2b-0.9.8-distilled.safetensors").exists() and (d / "text_encoder" / "config.json").exists():
        return log("ltx present")
    log("ltx: 2B 0.9.8 distilled + text encoder + tokenizer (this is the big one)")
    hf_hub_download("Lightricks/LTX-Video", "ltxv-2b-0.9.8-distilled.safetensors", local_dir=str(d))
    snapshot_download("Lightricks/LTX-Video", local_dir=str(d),
                      allow_patterns=["model_index.json", "scheduler/*", "text_encoder/*", "tokenizer/*"])


def sd():
    target = M / "sd" / "realistic-vision-v51.safetensors"
    if target.exists():
        return log("sd present")
    log("sd: Realistic Vision 5.1")
    f = hf_hub_download("SG161222/Realistic_Vision_V5.1_noVAE", "Realistic_Vision_V5.1.safetensors", local_dir=str(M / "sd"))
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(f, target)


def ipadapter():
    log("ip-adapter: plus-face + image encoder (HF cache)")
    snapshot_download("h94/IP-Adapter", allow_patterns=["models/ip-adapter-plus-face_sd15.safetensors", "models/image_encoder/*"])


def whisper():
    log("whisper: faster-whisper small (HF cache)")
    snapshot_download("Systran/faster-whisper-small")


def voice():
    target = M / "unity-voice-v2"
    if (target / "acoustic.pt").exists():
        return log("voice present")
    src = Path(ARGS.voice_src)
    if not (src / "acoustic.pt").exists():
        raise SystemExit("unity-voice-v2 not found at %s (it ships with the app / repo under models/unity-voice-v2)" % src)
    log("voice: copying unity-voice-v2 from", src)
    shutil.copytree(src, target, ignore=shutil.ignore_patterns("__pycache__"))


STEPS = {"ditto": ditto, "ltx": ltx, "sd": sd, "ipadapter": ipadapter, "whisper": whisper, "voice": voice}
for name in [s.strip() for s in ARGS.only.split(",") if s.strip()]:
    if name not in STEPS:
        raise SystemExit("unknown model group: %s" % name)
    STEPS[name]()
log("done ->", M)
