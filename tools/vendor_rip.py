#!/usr/bin/env python3
"""Vendor pass: copy ripped source files into vendor/ with provenance and a secret scan.

Reads tools/vendor-manifest.json, copies every listed file or directory from its
origin project into vendor/<slug>/<relative path>, records origin path, origin git
commit, sha256, size and mtime in vendor/PROVENANCE.md, and writes vendor/SCRUB-REPORT.md
listing every line that looks like a credential so it can be reviewed and redacted
before the files are adapted.

Weights (entries with "dest": "models") are copied under models/ which is gitignored.

Usage:  python tools/vendor_rip.py [--dry-run]
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "tools" / "vendor-manifest.json"
VENDOR = ROOT / "vendor"
MODELS = ROOT / "models"

SKIP_DIRS = {"__pycache__", "node_modules", ".venv", "venv", ".git", "dist", "build", ".pytest_cache"}
SKIP_GLOBS = ["*.pyc", "*.log", "*.gguf", "*.safetensors", "*.ckpt", "*.bin", "*.zip", "*.7z",
              "*.exe", "*.dll", "*.pdb", "*.mp4", "*.wav", "*.ogg", "*.mp3", ".env", ".env.*",
              "*.pem", "*.key", "*key*.json", "*secret*", "*token*.json", "*credentials*"]
# weights are only copied for entries that explicitly target models/
WEIGHT_GLOBS = ["*.pt", "*.onnx"]

SECRET_PATTERNS = [
    ("openai-style key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("pollinations key", re.compile(r"\b(?:pk|sk)_[A-Za-z0-9]{16,}")),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}")),
    ("discord token", re.compile(r"\b[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,}")),
    ("slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("assignment", re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*['\"][^'\"\s]{12,}['\"]")),
    ("bearer literal", re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{20,}")),
]
TEXT_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".json", ".md", ".txt", ".html", ".css",
            ".sh", ".bat", ".ps1", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".java", ".rs"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(args: list[str], cwd: Path) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


_git_cache: dict[Path, tuple[Path | None, str | None]] = {}


def git_info(path: Path) -> tuple[Path | None, str | None, str | None]:
    """Return (repo_root, head_commit, last_commit_touching_path)."""
    base = path if path.is_dir() else path.parent
    if base not in _git_cache:
        top = git(["rev-parse", "--show-toplevel"], base)
        root = Path(top) if top else None
        head = git(["rev-parse", "--short=12", "HEAD"], root) if root else None
        _git_cache[base] = (root, head)
    root, head = _git_cache[base]
    last = None
    if root:
        rel = os.path.relpath(path, root)
        last = git(["log", "-1", "--format=%h %cs", "--", rel], root)
    return root, head, last or None


def skip(path: Path, allow_weights: bool) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    name = path.name
    if any(fnmatch.fnmatch(name, g) for g in SKIP_GLOBS):
        return True
    if not allow_weights and any(fnmatch.fnmatch(name, g) for g in WEIGHT_GLOBS):
        return True
    return False


def scan_secrets(path: Path) -> list[tuple[int, str, str]]:
    if path.suffix.lower() not in TEXT_EXT:
        return []
    hits = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for lineno, line in enumerate(text.splitlines(), 1):
        for label, rx in SECRET_PATTERNS:
            if rx.search(line):
                hits.append((lineno, label, line.strip()[:160]))
                break
    return hits


def iter_files(src: Path, allow_weights: bool):
    if src.is_file():
        if not skip(src, allow_weights):
            yield src
        return
    for p in sorted(src.rglob("*")):
        if p.is_file() and not skip(p, allow_weights):
            yield p


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows: list[dict] = []
    scrub: list[tuple[str, int, str, str]] = []
    missing: list[str] = []
    total_bytes = 0

    for project in manifest["projects"]:
        slug = project["slug"]
        root = Path(project["root"])
        if not root.exists():
            missing.append(f"[{slug}] project root missing: {root}")
            continue
        for item in project["items"]:
            if isinstance(item, str):
                item = {"path": item}
            src = root / item["path"]
            if not src.exists():
                missing.append(f"[{slug}] {src}")
                continue
            to_models = item.get("dest") == "models"
            dest_root = (MODELS / item.get("as", slug)) if to_models else (VENDOR / slug)
            for f in iter_files(src, allow_weights=to_models):
                rel = f.relative_to(root)
                dest = (dest_root / f.relative_to(src)) if (to_models and src.is_dir()) else (dest_root / rel)
                if to_models and src.is_file():
                    dest = dest_root / f.name
                size = f.stat().st_size
                total_bytes += size
                repo, head, last = git_info(f)
                hits = scan_secrets(f)
                for lineno, label, line in hits:
                    scrub.append((str(dest.relative_to(ROOT)), lineno, label, line))
                rows.append({
                    "vendor": str(dest.relative_to(ROOT)).replace("\\", "/"),
                    "origin": str(f),
                    "project": slug,
                    "repo_head": head or "-",
                    "last_commit": last or "-",
                    "sha256": sha256(f)[:16],
                    "size": size,
                    "mtime": time.strftime("%Y-%m-%d", time.localtime(f.stat().st_mtime)),
                    "flags": len(hits),
                })
                if not dry:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dest)

    rows.sort(key=lambda r: r["vendor"])
    if not dry:
        VENDOR.mkdir(exist_ok=True)
        lines = [
            "# PROVENANCE — every vendored file and where it came from",
            "",
            f"Generated by `tools/vendor_rip.py` on {time.strftime('%Y-%m-%d %H:%M')} from `tools/vendor-manifest.json`.",
            "Files under `vendor/` are verbatim copies. Adapted versions live elsewhere in the tree; never edit `vendor/` in place.",
            "`repo_head` is the origin repository's HEAD at copy time; `last_commit` is the last commit that touched the file there.",
            "Rows with `flags` > 0 have lines that matched a credential pattern; see `SCRUB-REPORT.md`.",
            "",
            f"Files: {len(rows)}  ·  Bytes: {total_bytes:,}",
            "",
            "| vendor path | origin | repo_head | last_commit | sha256 (16) | size | mtime | flags |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            lines.append(f"| `{r['vendor']}` | `{r['origin']}` | {r['repo_head']} | {r['last_commit']} | {r['sha256']} | {r['size']} | {r['mtime']} | {r['flags']} |")
        if missing:
            lines += ["", "## Missing at copy time", ""] + [f"- {m}" for m in missing]
        (VENDOR / "PROVENANCE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

        s = ["# SCRUB-REPORT — lines that matched a credential pattern", "",
             "Review every line. Real secrets get redacted in the vendored copy and rotated at the source. False positives get a note here.", ""]
        if not scrub:
            s.append("_No matches._")
        for path, lineno, label, line in scrub:
            s.append(f"- `{path}:{lineno}` [{label}] `{line.replace('`', 'ʼ')}`")
        (VENDOR / "SCRUB-REPORT.md").write_text("\n".join(s) + "\n", encoding="utf-8")

    print(f"{'DRY RUN: ' if dry else ''}{len(rows)} files, {total_bytes/1e6:.1f} MB, {len(scrub)} flagged lines, {len(missing)} missing")
    for m in missing:
        print("  MISSING", m)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
