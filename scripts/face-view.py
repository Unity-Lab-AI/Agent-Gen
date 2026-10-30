#!/usr/bin/env python3
"""Watch her live: a native always-on-top window showing the face sidecar's stream, with fps and queue
overlaid. The human-viewable test surface until the app shell exists. Not a browser. Tk + Pillow only,
so it runs on the stock Python (the base OpenCV here is the headless build).

    python scripts/face-view.py [--url http://127.0.0.1:5126] [--scale 1.2]      (Esc or q closes)
"""
import argparse
import io
import json
import threading
import time
import tkinter as tk
import urllib.request

from PIL import Image, ImageTk

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://127.0.0.1:5126")
ap.add_argument("--title", default="Unity — live face")
ap.add_argument("--scale", type=float, default=1.0)
args = ap.parse_args()

state = {"img": None, "fps": 0.0, "t_last": time.time(), "health": {}, "alive": True, "frames": 0}


def reader():
    while state["alive"]:
        try:
            stream = urllib.request.urlopen(args.url + "/stream.mjpg", timeout=30)
            buf = b""
            while state["alive"]:
                chunk = stream.read(16384)
                if not chunk:
                    break
                buf += chunk
                while True:
                    a = buf.find(b"\xff\xd8")
                    b = buf.find(b"\xff\xd9", a + 2) if a >= 0 else -1
                    if a < 0 or b < 0:
                        break
                    jpg, buf = buf[a:b + 2], buf[b + 2:]
                    try:
                        img = Image.open(io.BytesIO(jpg)).convert("RGB")
                    except Exception:
                        continue
                    now = time.time()
                    state["fps"] = 0.9 * state["fps"] + 0.1 * (1.0 / max(1e-3, now - state["t_last"]))
                    state["t_last"] = now
                    state["frames"] += 1
                    state["img"] = img
        except Exception as e:
            state["health"] = {"error": str(e)[:80]}
            time.sleep(1.0)


def health_poll():
    while state["alive"]:
        try:
            state["health"] = json.loads(urllib.request.urlopen(args.url + "/health", timeout=2).read())
        except Exception as e:
            state["health"] = {"error": str(e)[:80]}
        time.sleep(1.0)


root = tk.Tk()
root.title(args.title)
root.configure(bg="#0b0b0f")
root.attributes("-topmost", True)
root.geometry("+120+80")


def force_front():
    """A window created by a background process is not brought forward by Windows; do it by hand."""
    try:
        root.deiconify(); root.state("normal"); root.lift(); root.focus_force()
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        SW_RESTORE, HWND_TOPMOST, SWP_NOSIZE, SWP_NOMOVE = 9, -1, 0x0001, 0x0002
        ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
        ctypes.windll.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception as e:
        print("force_front:", e)
label = tk.Label(root, bg="#0b0b0f", bd=0)
label.pack()
status = tk.Label(root, bg="#0b0b0f", fg="#ff5ab4", font=("Segoe UI", 10), anchor="w")
status.pack(fill="x")
root.bind("<Escape>", lambda e: root.destroy())
root.bind("q", lambda e: root.destroy())
photo = None


def tick():
    global photo
    img = state["img"]
    if img is not None:
        if args.scale != 1.0:
            img = img.resize((int(img.width * args.scale), int(img.height * args.scale)), Image.BILINEAR)
        photo = ImageTk.PhotoImage(img)
        label.configure(image=photo)
    h = state["health"]
    status.configure(text="  %.1f fps shown  |  sidecar fps %s  queue %ss  emo %s  steps %s / overlap %s  %s" % (
        state["fps"], h.get("fps", "?"), h.get("queue_s", "?"), h.get("emo", "?"), h.get("steps", "?"), h.get("overlap", "?"),
        ("ERROR " + h["error"]) if "error" in h else ""))
    root.after(33, tick)


threading.Thread(target=reader, daemon=True).start()
threading.Thread(target=health_poll, daemon=True).start()
root.after(33, tick)
root.after(300, force_front)
root.after(1500, force_front)
print("viewer window up", flush=True)
try:
    root.mainloop()
finally:
    state["alive"] = False
