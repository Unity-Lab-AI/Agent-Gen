"""Open "Unity Plays RimWorld" as a small always-on-top window over the game.

    python .claude/tools/unity-overlay.py [width] [height]

Launches Edge (or Chrome) in --app mode on the studio URL, then pins that window topmost in the
top-right corner of the primary screen so RimWorld and the stream are both visible.
"""
import ctypes, os, subprocess, sys, time
from ctypes import wintypes

URL = "http://127.0.0.1:4317/"
TITLE = "Unity Plays RimWorld"
W = int(sys.argv[1]) if len(sys.argv) > 1 else 560
H = int(sys.argv[2]) if len(sys.argv) > 2 else 1300
u = ctypes.WinDLL("user32")
u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
u.SetWindowPos.restype = wintypes.BOOL
try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception: pass

BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]


def find():
    found = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        n = u.GetWindowTextLengthW(h)
        if n and u.IsWindowVisible(h):
            b = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, b, n + 1)
            if b.value.strip() == TITLE: found.append(h)
        return True
    u.EnumWindows(cb, 0)
    return found[0] if found else None


def unpin_browsers():
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        n = u.GetWindowTextLengthW(h)
        if n:
            b = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, b, n + 1)
            if b.value.endswith("Google Chrome") or b.value.endswith("Microsoft Edge"):
                u.SetWindowPos(h, wintypes.HWND(-2), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
        return True
    u.EnumWindows(cb, 0)


def main():
    unpin_browsers()
    h = find()
    if not h:
        exe = next((b for b in BROWSERS if os.path.exists(b)), None)
        if not exe: print("no Edge/Chrome found"); return
        subprocess.Popen([exe, "--app=" + URL, "--window-size=%d,%d" % (W, H), "--autoplay-policy=no-user-gesture-required",
                          "--user-data-dir=" + os.path.join(os.environ["TEMP"], "unity-overlay-profile")])
        for _ in range(40):
            time.sleep(0.5); h = find()
            if h: break
    if not h: print("overlay window not found"); return
    sw = u.GetSystemMetrics(0)
    HWND_TOPMOST = -1
    # WS_EX_NOACTIVATE: the overlay stays on top but never takes focus from the game (its page
    # refocuses the chat box, which stole RimWorld's keyboard and broke clicks mid-play).
    u.GetWindowLongW.restype = ctypes.c_long; u.SetWindowLongW.restype = ctypes.c_long
    ex = u.GetWindowLongW(h, -20)
    u.SetWindowLongW(h, -20, ex | 0x08000000)
    ok = u.SetWindowPos(h, wintypes.HWND(HWND_TOPMOST), 10, 30, W, H, 0x0040 | 0x0010)
    if not ok: print('SetWindowPos failed')
    print("overlay pinned topmost at", 10, 30, W, H)


if __name__ == "__main__":
    main()
