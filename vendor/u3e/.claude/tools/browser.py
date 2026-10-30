"""Browser automation over CDP: one long-lived browser, many CLI calls, logins persist.

    python .claude/tools/browser.py start [--headless] [--channel chrome|msedge|chromium]
    python .claude/tools/browser.py open https://example.com
    python .claude/tools/browser.py text [SELECTOR] [--max 20000]
    python .claude/tools/browser.py html [SELECTOR]
    python .claude/tools/browser.py shot [out.png] [--full]
    python .claude/tools/browser.py click  "SELECTOR | text=Sign in"
    python .claude/tools/browser.py fill   "#email" "me@example.com"
    python .claude/tools/browser.py select "#country" "Canada"
    python .claude/tools/browser.py upload "input[type=file]" C:\\path\\file.pdf
    python .claude/tools/browser.py press enter | Tab | Control+a
    python .claude/tools/browser.py type "typed into the focused field"
    python .claude/tools/browser.py wait "SELECTOR" [--timeout 30000]
    python .claude/tools/browser.py eval "document.title"
    python .claude/tools/browser.py links [--filter substring]
    python .claude/tools/browser.py scroll N            # screens, +down / -up
    python .claude/tools/browser.py back | forward | reload
    python .claude/tools/browser.py tabs | tab N | newtab [URL] | closetab
    python .claude/tools/browser.py cookies [--out cookies.json]
    python .claude/tools/browser.py pdf [out.pdf]       # headless only
    python .claude/tools/browser.py status | stop

Global flags:
    --profile NAME    separate identity/login set (default: "default")
    --port N          CDP port (default 9222, or $CLAUDE_BROWSER_PORT)
    --window WxH      window size at start (default 1440x900)

The browser stays running between commands, so a login you do once - by hand in
the visible window, or scripted - holds for every later call. Profiles live in
~/.claude/browser-profiles/NAME and are shared by every project on the machine.

Any Chromium-based browser works: --channel chrome/msedge, or point
$CLAUDE_BROWSER_EXE at Brave/Vivaldi/Opera. Firefox has no CDP - drive it with
screen.py instead.
"""
import json, os, shutil, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

try:  # page titles and text are full of non-Latin characters
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))

try:
    from playwright.sync_api import Error as PWError, sync_playwright
except ImportError:
    sys.exit("Missing playwright. Run: python " + os.path.join(HERE, "doctor.py") + " --install")


def arg_val(args, flag, default=None):
    return args[args.index(flag) + 1] if flag in args and len(args) > args.index(flag) + 1 else default


ARGS = sys.argv[1:]
PROFILE = arg_val(ARGS, "--profile", os.environ.get("CLAUDE_BROWSER_PROFILE", "default"))
PORT = int(arg_val(ARGS, "--port", os.environ.get("CLAUDE_BROWSER_PORT", "9222")))
PROFILE_DIR = Path.home() / ".claude" / "browser-profiles" / PROFILE
PIDFILE = PROFILE_DIR / ".cdp.json"
CDP = f"http://127.0.0.1:{PORT}"

CHROME_PATHS = {
    "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
               r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
               "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
               "google-chrome", "chromium"],
    "msedge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
               r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
               "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
               "microsoft-edge"],
}


def resolve_exe(channel):
    if os.environ.get("CLAUDE_BROWSER_EXE"):
        return os.environ["CLAUDE_BROWSER_EXE"]
    if channel in CHROME_PATHS:
        for c in CHROME_PATHS[channel]:
            if os.path.exists(c) or shutil.which(c):
                return c if os.path.exists(c) else shutil.which(c)
        sys.exit(f"Could not find {channel}. Install it, set $CLAUDE_BROWSER_EXE, or drop --channel.")
    p = sync_playwright().start()
    try:
        exe = p.chromium.executable_path
    finally:
        p.stop()
    if not exe or not os.path.exists(exe):
        sys.exit("Playwright's Chromium is not downloaded. Run: python " +
                 os.path.join(HERE, "doctor.py") + " --install")
    return exe


def alive():
    try:
        with urllib.request.urlopen(f"{CDP}/json/version", timeout=1) as r:
            return json.load(r)
    except (urllib.error.URLError, OSError, ValueError):
        return None


def start(headless=False, channel=None, quiet=False):
    info = alive()
    if info:
        if not quiet:
            print(f"already running on {PORT}: {info.get('Browser')}  profile={PROFILE}")
        return info
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    exe = resolve_exe(channel)
    win = arg_val(ARGS, "--window", os.environ.get("CLAUDE_BROWSER_WINDOW", "1440,900"))
    cmd = [exe, f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE_DIR}",
           f"--window-size={win.replace('x', ',')}",
           "--remote-allow-origins=*", "--no-first-run", "--no-default-browser-check",
           "--disable-session-crashed-bubble", "--restore-last-session=false", "about:blank"]
    if headless:
        cmd.insert(1, "--headless=new")
    kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kw)
    PIDFILE.write_text(json.dumps({"pid": proc.pid, "port": PORT}))
    for _ in range(80):
        time.sleep(0.25)
        info = alive()
        if info:
            if not quiet:
                print(f"started {info.get('Browser')} on {PORT}  profile={PROFILE} ({PROFILE_DIR})")
            return info
    sys.exit(f"Browser did not open a CDP port on {PORT}. Try --port 9333, or close other "
             f"instances using this profile.")


class Session:
    """Connects over CDP without ever closing the user's browser."""

    def __enter__(self):
        if not alive():
            start(headless="--headless" in ARGS, channel=arg_val(ARGS, "--channel"), quiet=True)
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.connect_over_cdp(CDP)
        ctx = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
        self.ctx = ctx
        self.page = ctx.pages[-1] if ctx.pages else ctx.new_page()
        return self

    def __exit__(self, *exc):
        try:
            self.pw.stop()   # drops the connection; the browser keeps running
        except Exception:
            pass
        return False


def pid_on_port(port):
    """Whoever is listening on the CDP port - fallback when no pid was recorded."""
    try:
        if os.name == "nt":
            out = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True,
                                 text=True).stdout
            for line in out.splitlines():
                f = line.split()
                if len(f) >= 5 and f[3].upper() == "LISTENING" and f[1].endswith(f":{port}"):
                    return int(f[4])
        else:
            out = subprocess.run(["lsof", "-ti", f"tcp:{port}"], capture_output=True,
                                 text=True).stdout.strip()
            if out:
                return int(out.splitlines()[0])
    except (OSError, ValueError):
        pass
    return None


def stop():
    """Close the pages, then make sure the process is really gone.

    Playwright's browser.close() over CDP only drops our connection - the
    browser keeps running - so fall back to the pid recorded at start.
    """
    if not alive():
        print("not running")
        PIDFILE.unlink(missing_ok=True)
        return
    try:
        with Session() as s:
            for p in list(s.ctx.pages):
                try:
                    p.close()
                except Exception:
                    pass
    except Exception:
        pass
    time.sleep(0.6)
    if alive():
        try:
            pid = json.loads(PIDFILE.read_text()).get("pid")
        except (OSError, ValueError, AttributeError):
            pid = pid_on_port(PORT)   # started by other means: find whoever holds the port
        if pid:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                import signal
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
    for _ in range(20):
        if not alive():
            break
        time.sleep(0.25)
    if alive():
        print(f"could not stop the browser on port {PORT} - close its window, or kill it manually")
    else:
        print(f"stopped (profile={PROFILE})")
        PIDFILE.unlink(missing_ok=True)


def describe(page):
    print(f"{page.title()}\n{page.url}")


def main():
    a = [x for x in ARGS]
    for flag in ("--profile", "--port", "--channel", "--window"):   # strip global flag+value
        if flag in a:
            i = a.index(flag)
            del a[i:i + 2]
    a = [x for x in a if x != "--headless"]
    if not a or a[0] in ("-h", "--help", "help"):
        sys.exit(__doc__)
    c = a[0]

    if c == "start":
        start(headless="--headless" in ARGS, channel=arg_val(ARGS, "--channel"))
        return
    if c == "status":
        info = alive()
        print(f"running: {info.get('Browser')} on {PORT}, profile={PROFILE}" if info
              else f"not running (port {PORT}, profile {PROFILE})")
        if info:
            with Session() as s:
                for i, p in enumerate(s.ctx.pages):
                    print(f"  [{i}] {p.title()[:60]!r} {p.url}")
        return
    if c == "stop":
        stop()
        return

    with Session() as s:
        page = s.page
        if c == "open":
            page.goto(a[1], wait_until="domcontentloaded", timeout=60000)
            describe(page)
        elif c == "text":
            sel = a[1] if len(a) > 1 and not a[1].startswith("--") else "body"
            mx = int(arg_val(a, "--max", "20000"))
            t = page.inner_text(sel)
            print(t[:mx] + (f"\n... [{len(t) - mx} more chars]" if len(t) > mx else ""))
        elif c == "html":
            sel = a[1] if len(a) > 1 else None
            print(page.inner_html(sel) if sel else page.content())
        elif c == "shot":
            out = a[1] if len(a) > 1 and not a[1].startswith("--") else os.path.join(HERE, "page.png")
            page.screenshot(path=out, full_page="--full" in a)
            print(out)
        elif c == "click":
            page.click(a[1], timeout=30000)
            print(f"clicked {a[1]}")
        elif c == "fill":
            page.fill(a[1], a[2], timeout=30000)
            print(f"filled {a[1]}")
        elif c == "select":
            page.select_option(a[1], a[2], timeout=30000)
            print(f"selected {a[2]}")
        elif c == "upload":
            page.set_input_files(a[1], a[2:])
            print(f"attached {a[2:]}")
        elif c == "press":
            page.keyboard.press(a[1])
            page.wait_for_timeout(400)
            describe(page)
        elif c == "type":
            page.keyboard.type(a[1])
            print(f"typed {len(a[1])} chars")
        elif c == "wait":
            page.wait_for_selector(a[1], timeout=int(arg_val(a, "--timeout", "30000")))
            print(f"present: {a[1]}")
        elif c == "eval":
            js = a[1].strip()
            if js.startswith(("(", "function", "async", "=>")):
                expr = js                              # already a function
            elif ";" in js.rstrip(";") or "\n" in js:
                expr = "() => { " + js + " }"          # statements: `return` yourself
            else:
                expr = f"() => ({js})"                 # a bare expression
            print(json.dumps(page.evaluate(expr), indent=2, default=str))
        elif c == "links":
            sub = arg_val(a, "--filter")
            rows = page.evaluate(
                "() => [...document.querySelectorAll('a[href]')]"
                ".map(e => ({t: e.innerText.trim().slice(0,80), h: e.href}))")
            for r in rows:
                if not sub or sub.lower() in (r["h"] + r["t"]).lower():
                    print(f"{r['t'] or '-'}\t{r['h']}")
        elif c == "scroll":
            h = page.viewport_size["height"] * 0.9 if page.viewport_size else 800
            page.mouse.wheel(0, int(float(a[1]) * h))
            print(f"scrolled {a[1]} screen(s)")
        elif c in ("back", "forward", "reload"):
            getattr(page, "go_" + c if c != "reload" else "reload")()
            describe(page)
        elif c == "tabs":
            for i, p in enumerate(s.ctx.pages):
                print(f"[{i}] {p.title()[:60]!r} {p.url}")
        elif c == "tab":
            p = s.ctx.pages[int(a[1])]
            p.bring_to_front()
            describe(p)
        elif c == "newtab":
            p = s.ctx.new_page()
            if len(a) > 1:
                p.goto(a[1], wait_until="domcontentloaded", timeout=60000)
            describe(p)
        elif c == "closetab":
            page.close()
            print("closed")
        elif c == "cookies":
            ck = s.ctx.cookies()
            out = arg_val(a, "--out")
            if out:
                Path(out).write_text(json.dumps(ck, indent=2))
                print(f"{len(ck)} cookies -> {out}")
            else:
                print(json.dumps(ck, indent=2))
        elif c == "pdf":
            out = a[1] if len(a) > 1 else os.path.join(HERE, "page.pdf")
            page.pdf(path=out)
            print(out)
        else:
            sys.exit(__doc__)


if __name__ == "__main__":
    try:
        main()
    except PWError as e:
        # one readable line instead of a 20-frame Playwright traceback
        first = str(e).splitlines()[0].strip()
        sys.exit(f"error: {first}\nhint: `browser.py shot` and `browser.py text` show what the "
                 f"page actually looks like right now.")
    except (IndexError, KeyError):
        sys.exit("error: missing or bad argument.\n\n" + __doc__)
    except KeyboardInterrupt:
        sys.exit(130)
