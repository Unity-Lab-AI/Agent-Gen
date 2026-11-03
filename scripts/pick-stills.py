"""Pick the most different stills of her from a video, for her start looks.

    python scripts/pick-stills.py <video> [--n 8] [--out assets/portrait/starts]

Every frame is read; each pick is the frame farthest (mean absolute difference on a small grey copy) from every
frame already picked, starting from the middle frame, so the set covers the most different positions in the clip.
Writes start-01.jpg .. start-NN.jpg plus contact.jpg (all picks side by side) for a look.
"""
import argparse
import os

import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("--n", type=int, default=8)
ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "assets", "portrait", "starts"))
ap.add_argument("--min-gap", type=int, default=6, help="frames apart at least (neighbours are near copies)")
a = ap.parse_args()

cap = cv2.VideoCapture(a.video)
frames = []
while True:
    ok, f = cap.read()
    if not ok:
        break
    frames.append(f)
if not frames:
    raise SystemExit(f"no frames in {a.video}")
small = [cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (48, 86)).astype(np.float32) for f in frames]

picks = [len(frames) // 2]
dist = np.array([np.abs(s - small[picks[0]]).mean() for s in small])
while len(picks) < min(a.n, len(frames)):
    d = dist.copy()
    for p in picks:
        d[max(0, p - a.min_gap):p + a.min_gap + 1] = -1
    i = int(d.argmax())
    if d[i] <= 0:
        break
    picks.append(i)
    dist = np.minimum(dist, [np.abs(s - small[i]).mean() for s in small])
picks.sort()

os.makedirs(a.out, exist_ok=True)
for old in os.listdir(a.out):
    if old.startswith("start-") and old.endswith(".jpg"):
        os.remove(os.path.join(a.out, old))
for k, i in enumerate(picks, 1):
    cv2.imwrite(os.path.join(a.out, f"start-{k:02d}.jpg"), frames[i], [cv2.IMWRITE_JPEG_QUALITY, 95])
h = 360
thumbs = [cv2.resize(frames[i], (int(frames[i].shape[1] * h / frames[i].shape[0]), h)) for i in picks]
cv2.imwrite(os.path.join(a.out, "contact.jpg"), np.hstack(thumbs))
print(f"{len(frames)} frames, picked {picks} -> {os.path.abspath(a.out)}")
