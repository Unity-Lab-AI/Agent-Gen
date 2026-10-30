"""A picture with every line: the game as the stream sees it now, ZOOMED on the crew, Unity's line in a band under it.

    python .claude/tools/unity-glance.py "caption" [--mark x,z,label]...

Owner, 2026-10-08: *"and make some images more offten like as much as you talk"*. unity-say.py runs
this after each spoken line. Unlike unity-snap.py it never moves the camera -- it shoots the current
view -- so it can run on every line without fighting play.py's framing. The caption is a spoken
line that already passed the stream filter (THE STREAM IS CLEAN).

Owner, 2026-10-13: "the highlights ... are just all the same resolution and zoom and no one can see them whats being
pointed out ... the text needs to be like 50% bigger and properly aligned ... all cut off". So: the shot is CROPPED
to half the screen around the colonists (or the marks) -- a 2x zoom -- fitted into the panel's own shape
(unity-panel.py), the rings and names drawn after the fit at full sharpness, the caption in a band UNDER the
picture (never over it), and the overlay gets no caption of its own (it used to print the line a second time
across the picture's bottom edge).
"""
import base64, io, json, os, subprocess, sys, urllib.request
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("unity_panel", os.path.join(HERE, "unity-panel.py"))
panel = _ilu.module_from_spec(_spec); _spec.loader.exec_module(panel)


def studio_token():
    """The studio's token for its local helpers (every POST without a browser Origin needs it)."""
    try:
        with open(os.path.join(os.path.dirname(HERE), ".studio-token"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""

BRIDGE = os.path.join(ROOT, ".local", "qa", "bridge.py")
PINK = (255, 70, 160)
HOSTILE = (255, 40, 40)
MARK = (90, 220, 255)
ZOOM = 2.0                       # the crop is 1/ZOOM of the screen each way


def _mark_highlight():
    """The webcam panel shows a highlight for at most ~20 s, then cam-director.py puts Unity back up (owner,
    2026-10-09: "leave the profile pic of ur up more and the slide show highlights just intermittently for liek
    20 second max so it settle on a new you doing things")."""
    try:
        import time as _t
        json.dump({"ts": _t.time()}, open(os.path.join(ROOT, ".claude", ".cam-highlight.json"), "w"))
    except Exception:
        pass


def call(tool, args=None):
    o = subprocess.run([sys.executable, BRIDGE, "call", tool, json.dumps(args or {})],
                       capture_output=True, text=True, timeout=60).stdout
    try: return json.loads(o[o.find("{"):])
    except Exception: return {}


def find(n, k):
    if isinstance(n, dict):
        if k in n: return n[k]
        for v in n.values():
            r = find(v, k)
            if r is not None: return r
    return None


def subjects(marks):
    """[(x, z, label, colour)] in view: every colonist by name, hostiles in red, the caller's marks in blue."""
    out = []
    for c in call("rimworld/list_colonists").get("colonists", []):
        p = c.get("position") or {}
        if "x" in p: out.append((p["x"], p["z"], c.get("name", ""), PINK))
    mine = {(x, z) for x, z, _, _ in out}
    try:
        import ast
        o = subprocess.run([sys.executable, os.path.join(ROOT, ".local", "qa", "live-hostiles.py")],
                           capture_output=True, text=True, timeout=60).stdout
        for x, z in ast.literal_eval(o.strip() or "[]"):
            if (x, z) not in mine: out.append((x, z, "HOSTILE", HOSTILE))
    except Exception:
        pass
    for x, z, label in marks: out.append((x, z, label, MARK))
    return out


def main():
    args = sys.argv[1:]; marks = []
    while "--mark" in args:
        i = args.index("--mark"); x, z, *lab = args[i + 1].split(",", 2); marks.append((int(x), int(z), lab[0] if lab else ""))
        del args[i:i + 2]
    caption = " ".join(args).strip()
    o = subprocess.run([sys.executable, BRIDGE, "call", "rimworld/take_screenshot", "{}"],
                       capture_output=True, text=True, timeout=120).stdout
    path = json.loads(o[o.find("{"):]).get("path")
    if not path:
        return
    im = Image.open(path).convert("RGB")
    W, H = im.size
    cam = call("rimworld/get_camera_state")
    x0, x1, z0, z1 = (find(cam, k) for k in ("minX", "maxX", "minZ", "maxZ"))
    have_cam = None not in (x0, x1, z0, z1)
    cw = W / (x1 - x0 + 1.0) if have_cam else 0; ch = H / (z1 - z0 + 1.0) if have_cam else 0
    def px(x, z): return ((x - x0 + 0.5) * cw, (z1 - z + 0.5) * ch)
    subs = subjects(marks) if have_cam else []
    inview = [(x, z, l, c) for x, z, l, c in subs if x0 <= x <= x1 and z0 <= z <= z1]
    # the crop: 1/ZOOM of the screen, the panel's picture shape, centred on the marks (else the crew, else the screen)
    pw, ph = panel.picture_box(caption, [])
    cw_px = W / ZOOM; ch_px = cw_px * ph / pw
    if ch_px > H: ch_px = H; cw_px = ch_px * pw / ph
    centre = [(x, z) for x, z, l, c in inview if c == MARK] or [(x, z) for x, z, l, c in inview if c == PINK] or []
    if centre:
        pts = [px(x, z) for x, z in centre]
        cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    else:
        cx, cy = W / 2, H / 2
    left = int(min(max(0, cx - cw_px / 2), W - cw_px)); top = int(min(max(0, cy - ch_px / 2), H - ch_px))
    crop = im.crop((left, top, left + int(cw_px), top + int(ch_px)))
    canvas, (s, dx, dy) = panel.compose(crop, caption, [], mode="cover")
    d = ImageDraw.Draw(canvas)
    r = max(12, cw * s * 0.8)
    for x, z, label, col in inview:
        sx, sy = px(x, z)
        gx, gy = (sx - left) * s + dx, (sy - top) * s + dy
        if -r <= gx <= pw + r and -r <= gy <= ph + r:
            panel.ring(d, gx, gy, r, col, label, bounds=(pw, ph))
    buf = io.BytesIO(); canvas.save(buf, "PNG")
    req = urllib.request.Request("http://127.0.0.1:4317/api/cam",
                                 data=json.dumps({"png": base64.b64encode(buf.getvalue()).decode(),
                                                  "caption": ""}).encode(),   # the band carries it; no second print
                                 headers={"Content-Type": "application/json", "X-Studio-Token": studio_token()})
    urllib.request.urlopen(req, timeout=60).read()
    _mark_highlight()


if __name__ == "__main__":
    main()
