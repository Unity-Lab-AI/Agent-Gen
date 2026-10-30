"""Desktop control: screenshot, mouse, keyboard, window focus (Windows; ctypes + Pillow).

    python .claude/tools/screen.py shot [out.png] [--region X,Y,W,H] [--full]
    python .claude/tools/screen.py click X Y [right|middle|double]  # screenshot coords
    python .claude/tools/screen.py move X Y
    python .claude/tools/screen.py drag X1 Y1 X2 Y2
    python .claude/tools/screen.py type "text"
    python .claude/tools/screen.py paste "long text"      # via clipboard, fast + exact
    python .claude/tools/screen.py key ctrl+l | enter | alt+tab | ctrl+shift+n ...
    python .claude/tools/screen.py scroll N               # +up / -down, in notches
    python .claude/tools/screen.py focus "window title part"
    python .claude/tools/screen.py windows                # list visible windows
    python .claude/tools/screen.py pos                    # cursor position

Coordinates are in the coordinate space of the last `shot`: screenshots are
downscaled to <=1600px wide and the scale/offset is remembered, so you can read
X,Y straight off the image you just looked at and click it.

Use this for anything with a GUI - Firefox, Edge, a game, an installer, a native
app. For scriptable browser work prefer browser.py; for plain HTTP use web.py.
"""
import ctypes, json, os, subprocess, sys, time

try:  # Windows consoles default to cp1252 and would die on non-Latin titles
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

if os.name != "nt":
    sys.exit("screen.py is Windows-only. On macOS/Linux use browser.py (web) or "
             "install a platform tool such as `cliclick`/`xdotool` for GUI control.")

try:
    from PIL import ImageGrab
except ImportError:
    sys.exit("Missing Pillow. Run: python " +
             os.path.join(os.path.dirname(os.path.abspath(__file__)), "doctor.py") + " --install")

from ctypes import wintypes

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, ".screen-state.json")
MAXW = int(os.environ.get("CLAUDE_SCREEN_MAXW", "1600"))

VK = {"enter": 0x0D, "return": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B, "backspace": 0x08,
      "delete": 0x2E, "del": 0x2E, "insert": 0x2D, "ctrl": 0x11, "control": 0x11, "shift": 0x10,
      "alt": 0x12, "win": 0x5B, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
      "home": 0x24, "end": 0x23, "pgup": 0x21, "pgdn": 0x22, "space": 0x20, "capslock": 0x14,
      "printscreen": 0x2C, "menu": 0x5D}
VK.update({f"f{i}": 0x6F + i for i in range(1, 25)})  # f1=0x70 .. f24

ULONG_PTR = ctypes.c_size_t


class KI(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MI(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class U(ctypes.Union):
    _fields_ = [("ki", KI), ("mi", MI), ("pad", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", U)]


KEYUP, UNICODE, EXTENDED = 0x0002, 0x0004, 0x0001
EXT_KEYS = {0x26, 0x28, 0x25, 0x27, 0x24, 0x23, 0x21, 0x22, 0x2D, 0x2E, 0x5B, 0x5D}


def send(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def key_ev(vk=0, scan=0, flags=0):
    i = INPUT(type=1)
    i.u.ki = KI(vk, scan, flags, 0, 0)
    return i


def mouse_ev(flags, data=0):
    i = INPUT(type=0)
    i.u.mi = MI(0, 0, data, flags, 0, 0)
    return i


def load_state():
    try:
        with open(STATE) as f:
            s = json.load(f)
        return float(s.get("scale", 1.0)), int(s.get("ox", 0)), int(s.get("oy", 0))
    except (OSError, ValueError):
        return 1.0, 0, 0


def to_screen(x, y):
    """Map coordinates from the last screenshot back to real screen pixels."""
    s, ox, oy = load_state()
    return int(ox + x / s), int(oy + y / s)


def shot(out, region=None, full=False):
    if region:
        x, y, w, h = region
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
        ox, oy = x, y
    else:
        img = ImageGrab.grab(all_screens=full)
        ox, oy = 0, 0
        if full:  # virtual desktop can start at negative coords
            ox = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            oy = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
    s = min(1.0, MAXW / img.width)
    if s < 1.0:
        img = img.resize((int(img.width * s), int(img.height * s)))
    img.save(out)
    with open(STATE, "w") as f:
        json.dump({"scale": s, "ox": ox, "oy": oy}, f)
    print(out, img.size, f"scale={s:.4f}", f"origin=({ox},{oy})")


def click(x, y, mode="left"):
    rx, ry = to_screen(x, y)
    user32.SetCursorPos(rx, ry)
    time.sleep(0.05)
    down, up = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010),
                "middle": (0x0020, 0x0040), "double": (0x0002, 0x0004)}[mode]
    for _ in range(2 if mode == "double" else 1):
        send(mouse_ev(down), mouse_ev(up))
        time.sleep(0.05)


def move(x, y):
    rx, ry = to_screen(x, y)
    user32.SetCursorPos(rx, ry)


def drag(x1, y1, x2, y2):
    ax, ay = to_screen(x1, y1)
    bx, by = to_screen(x2, y2)
    user32.SetCursorPos(ax, ay)
    time.sleep(0.08)
    send(mouse_ev(0x0002))
    steps = 24
    for i in range(1, steps + 1):
        user32.SetCursorPos(int(ax + (bx - ax) * i / steps), int(ay + (by - ay) * i / steps))
        time.sleep(0.012)
    time.sleep(0.08)
    send(mouse_ev(0x0004))


def type_text(t):
    for ch in t:
        cp = ord(ch)
        if cp == 10:
            key("enter")
            continue
        send(key_ev(scan=cp, flags=UNICODE), key_ev(scan=cp, flags=UNICODE | KEYUP))
        time.sleep(0.005)


def paste(t):
    """Put text on the clipboard and press ctrl+v - instant and exact for long text."""
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "$i=[Console]::In.ReadToEnd(); Set-Clipboard -Value $i"],
                   input=t, text=True, check=True)
    time.sleep(0.1)
    key("ctrl+v")


def key(combo):
    vks = [VK[k] if k in VK else ord(k.upper()) for k in combo.lower().split("+")]
    down = [key_ev(v, flags=EXTENDED if v in EXT_KEYS else 0) for v in vks]
    up = [key_ev(v, flags=KEYUP | (EXTENDED if v in EXT_KEYS else 0)) for v in reversed(vks)]
    send(*down)
    send(*up)


def enum_windows(part=None):
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        n = user32.GetWindowTextLengthW(h)
        if n and user32.IsWindowVisible(h):
            b = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(h, b, n + 1)
            if part is None or part.lower() in b.value.lower():
                found.append((h, b.value))
        return True

    user32.EnumWindows(cb, 0)
    return found


def focus(part):
    found = enum_windows(part)
    for _, t in found:
        print(t)
    if not found:
        print("no window matched")
        return
    h = found[0][0]
    user32.ShowWindow(h, 9)  # SW_RESTORE
    key("alt")               # releases foreground lock
    user32.SetForegroundWindow(h)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help", "help"):
        sys.exit(__doc__)
    c = a[0]
    if c == "shot":
        out = a[1] if len(a) > 1 and not a[1].startswith("--") else os.path.join(HERE, "shot.png")
        region = None
        if "--region" in a:
            region = [int(v) for v in a[a.index("--region") + 1].split(",")]
        shot(out, region, "--full" in a)
    elif c == "click":
        click(float(a[1]), float(a[2]), a[3] if len(a) > 3 else "left")
    elif c == "move":
        move(float(a[1]), float(a[2]))
    elif c == "drag":
        drag(float(a[1]), float(a[2]), float(a[3]), float(a[4]))
    elif c == "type":
        type_text(a[1])
    elif c == "paste":
        paste(a[1])
    elif c == "key":
        key(a[1])
    elif c == "scroll":
        send(mouse_ev(0x0800, ctypes.c_uint32(int(a[1]) * 120).value))
    elif c == "focus":
        focus(a[1])
    elif c == "windows":
        for _, t in enum_windows():
            print(t)
    elif c == "pos":
        p = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(p))
        s, ox, oy = load_state()
        print(f"screen=({p.x},{p.y}) shot=({int((p.x - ox) * s)},{int((p.y - oy) * s)})")
    else:
        sys.exit(__doc__)
    time.sleep(0.25)
