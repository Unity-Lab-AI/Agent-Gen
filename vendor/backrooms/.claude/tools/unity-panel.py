"""The stream's REPRESENTATION panel, drawn to fit: one canvas shaped exactly like the overlay's picture box
(481 x 326 at 2x = 962 x 652, `object-fit: cover` crops nothing), the picture on top, a band under it with the
caption and a numbered legend. Shared by unity-glance.py (every spoken line) and unity-snap.py (a marked rect).

Owner, 2026-10-13: "the highlights she does on the screen captures are just all the same resolution and zoom and no
one can see them whats being pointed out and highlightd and the text needs to be like 50% bigger and properly aligned
in the image as currently the writeup highlights are all cut off backause she is just doing screen shots and writing
on it but when displayed its all cut off ... we need it to peroply align and save zoomed in possibly screencapturues
with text not cut off in the display window and 50% bigger so it can be read" / "wtf u didnt fix the shit i said
about the twitch stream highlight images".

Sizes are in canvas pixels; the panel shows them at half: caption 40 px -> 20 px on screen (the old on-picture caption
was 34 px on a 1024 frame -> ~13 px on screen), legend and names 32 px -> 16 px.
"""
from PIL import Image, ImageDraw, ImageFont

PANEL_W, PANEL_H = 962, 652            # 2 x the overlay's #cam img box (481 x 326)
FONT = "C:/Windows/Fonts/Inkfree.ttf"
INK = [(255, 70, 160), (255, 220, 60), (120, 220, 255)]
BAND_BG = (12, 10, 14)
CAP_PX, CAP_LH = 40, 46
LEG_PX, LEG_LH = 32, 38
MAX_CAP_LINES, MAX_LEG_LINES = 3, 3


def font(px):
    return ImageFont.truetype(FONT, px)


def wrap(d, txt, f, width):
    words, lines, cur = str(txt or "").split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            if cur: lines.append(cur)
            cur = wd
    if cur: lines.append(cur)
    return lines or [""]


def outlined(d, xy, s, f, color, pad=2):
    x, y = xy
    for dx, dy in ((-pad, 0), (pad, 0), (0, -pad), (0, pad)):
        d.text((x + dx, y + dy), s, font=f, fill=(0, 0, 0))
    d.text((x, y), s, font=f, fill=color)


def band_lines(caption, legend):
    """The wrapped caption and legend lines for the band (a scratch draw context measures them)."""
    d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    cap = wrap(d, caption, font(CAP_PX), PANEL_W - 40)[:MAX_CAP_LINES]
    leg = []
    for n, note in enumerate(legend or []):
        leg += wrap(d, "%d  %s" % (n + 1, note), font(LEG_PX), PANEL_W - 40)
    leg = leg[:MAX_LEG_LINES]
    return cap, leg


def band_height(cap, leg):
    return 14 + len(cap) * CAP_LH + len(leg) * LEG_LH + 10


def picture_box(caption, legend):
    """(width, height) of the picture area above the band for this caption and legend."""
    cap, leg = band_lines(caption, legend)
    return PANEL_W, max(300, PANEL_H - band_height(cap, leg))


def fit(picture, box, mode):
    """The picture into box: 'cover' fills and crops the edges (the subject is already centred), 'contain'
    letterboxes in the band colour (marks must stay inside)."""
    bw, bh = box
    pw, ph = picture.size
    if mode == "cover":
        s = max(bw / pw, bh / ph)
        im = picture.resize((max(1, int(pw * s + 0.5)), max(1, int(ph * s + 0.5))), Image.LANCZOS)
        ox, oy = (im.size[0] - bw) // 2, (im.size[1] - bh) // 2
        return im.crop((ox, oy, ox + bw, oy + bh)), (s, -ox, -oy)
    s = min(bw / pw, bh / ph)
    im = picture.resize((max(1, int(pw * s + 0.5)), max(1, int(ph * s + 0.5))), Image.LANCZOS)
    canvas = Image.new("RGB", (bw, bh), BAND_BG)
    ox, oy = (bw - im.size[0]) // 2, (bh - im.size[1]) // 2
    canvas.paste(im, (ox, oy))
    return canvas, (s, ox, oy)


def compose(picture, caption, legend=(), mode="cover"):
    """The panel canvas: picture fitted into the area above the band, the band with caption + legend.
    Returns (canvas, transform) where transform = (scale, dx, dy) maps picture pixels to canvas pixels
    (canvas_x = px * scale + dx) so callers can draw rings AFTER the fit at full sharpness."""
    cap, leg = band_lines(caption, legend)
    bh = band_height(cap, leg)
    pic, (s, dx, dy) = fit(picture, (PANEL_W, PANEL_H - bh), mode)
    canvas = Image.new("RGB", (PANEL_W, PANEL_H), BAND_BG)
    canvas.paste(pic, (0, 0))
    d = ImageDraw.Draw(canvas)
    y = PANEL_H - bh + 14
    for ln in cap:
        outlined(d, (20, y), ln, font(CAP_PX), INK[0]); y += CAP_LH
    for ln in leg:
        n = int(ln.split()[0]) - 1 if ln[:1].isdigit() else 1
        outlined(d, (20, y), ln, font(LEG_PX), INK[min(len(INK) - 1, max(0, n))]); y += LEG_LH
    return canvas, (s, dx, dy)


def ring(d, cx, cy, r, color, label=None, label_px=LEG_PX, bounds=None):
    """A double ring (black under colour) and an outlined label to its right, kept inside bounds."""
    for w, col in ((6, (0, 0, 0)), (4, color)):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=col, width=w)
    if label:
        f = font(label_px)
        tw = d.textlength(label, font=f)
        W, H = bounds or (PANEL_W, PANEL_H)
        x = cx + r + 6 if cx + r + 6 + tw < W - 6 else cx - r - 6 - tw
        y = min(max(4, cy - label_px * 0.6), H - label_px - 6)
        outlined(d, (x, y), label, f, color)


def badge(d, x, y, n, color):
    """A numbered badge (the words go in the legend)."""
    d.ellipse((x, y, x + 46, y + 46), fill=(0, 0, 0), outline=color, width=4)
    d.text((x + 13, y + 1), str(n), font=font(38), fill=color)
