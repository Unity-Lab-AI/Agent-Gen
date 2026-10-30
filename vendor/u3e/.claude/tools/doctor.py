"""Dependency check and installer for the .claude/tools toolkit (stdlib only).

    python .claude/tools/doctor.py              # report what's missing
    python .claude/tools/doctor.py --install    # install everything missing
    python .claude/tools/doctor.py --json       # machine-readable report

Exit code 0 = everything required is present, 1 = something is missing.
"""
import importlib.util, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))

# (pip name, import name, what needs it, required?)
PKGS = [
    ("pillow", "PIL", "screen.py (screenshots)", True),
    ("playwright", "playwright", "browser.py (browser automation)", True),
]


def have(mod):
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def chromium_path():
    """Path to Playwright's bundled Chromium, or None if not downloaded."""
    if not have("playwright"):
        return None
    try:
        from playwright.sync_api import sync_playwright
        p = sync_playwright().start()
        try:
            exe = p.chromium.executable_path
            return exe if exe and os.path.exists(exe) else None
        finally:
            p.stop()
    except Exception:
        return None


def pip(*args):
    return subprocess.call([sys.executable, "-m", "pip", *args]) == 0


def report():
    rows = []
    for name, mod, why, req in PKGS:
        rows.append({"name": name, "kind": "pip", "ok": have(mod), "why": why, "required": req})
    rows.append({"name": "chromium browser", "kind": "playwright", "ok": bool(chromium_path()),
                 "why": "browser.py (bundled browser; not needed with --channel chrome/msedge)",
                 "required": False})
    rows.append({"name": "python>=3.8", "kind": "runtime", "ok": sys.version_info >= (3, 8),
                 "why": "all tools", "required": True})
    return rows


def install(rows):
    missing = [r for r in rows if not r["ok"]]
    if not missing:
        return True
    ok = True
    pips = [r["name"] for r in missing if r["kind"] == "pip"]
    if pips:
        print(f"\n>>> pip install {' '.join(pips)}")
        ok &= pip("install", "--upgrade", *pips)
    if any(r["kind"] == "playwright" for r in missing) and have("playwright"):
        print("\n>>> playwright install chromium")
        ok &= subprocess.call([sys.executable, "-m", "playwright", "install", "chromium"]) == 0
    if any(r["kind"] == "runtime" for r in missing):
        print(f"\n!! Python {sys.version.split()[0]} is too old; install 3.8+ yourself.")
        ok = False
    return ok


def main():
    args = sys.argv[1:]
    if "--install" in args:
        install(report())
        print("\n--- after install ---")
    rows = report()
    if "--json" in args:
        print(json.dumps(rows, indent=2))
    else:
        print(f"python {sys.version.split()[0]}  ({sys.executable})")
        print(f"tools  {HERE}\n")
        for r in rows:
            mark = "ok  " if r["ok"] else ("MISS" if r["required"] else "warn")
            print(f"  [{mark}] {r['name']:<18} {r['why']}")
        bad = [r for r in rows if not r["ok"]]
        if bad:
            print("\nFix with:  python " + os.path.join(HERE, "doctor.py") + " --install")
        else:
            print("\nAll good.")
    return 1 if any(not r["ok"] and r["required"] for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
