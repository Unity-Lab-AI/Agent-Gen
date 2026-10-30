"""Update Unity's stream webcam: python .claude/tools/unity-cam.py <mood> "caption"

mood picks the expression; the base look is always the same girl at the same desk.
Renders through the local Stable Diffusion via the studio's /api/cam. Runs in the background.
"""
import json, os, subprocess, sys, urllib.request


def studio_token():
    """Per-session token the studio server writes for its local helpers (needed for every POST)."""
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".studio-token"),
                  encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


BASE = ""   # who she is, her outfit, gaze and props are added by unity-face-sd.compose() -- the caller sends the mood only
MOODS = {
    "chill": "relaxed half smile, sleepy eyes, chin resting on her hand",
    "hype": "excited wide grin, leaning toward the camera, fist raised",
    "angry": "furious scowl, yelling at the monitor, gripping the headset",
    "focus": "intense focused stare at the screen, typing fast, lip bitten",
    "laugh": "laughing hard, head back, eyes squeezed shut, hand on her chest",
    "smug": "smug smirk at the camera, one eyebrow raised, arms crossed",
    "scared": "shocked wide eyes, hand over mouth, monitor glow on face",
    "sad": "pouting, chin on hand, glossy eyes",
    "flirty": "playful wink at the camera, finger twirling her hair, teasing smile",
}


def main():
    mood = sys.argv[1] if len(sys.argv) > 1 else "chill"
    caption = sys.argv[2] if len(sys.argv) > 2 else ""
    scene = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "--now" else ""   # her own idea of the moment
    if "--now" not in sys.argv:
        subprocess.Popen([sys.executable, __file__, mood, caption, scene, "--now"],
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    prompt = BASE + MOODS.get(mood, mood) + ", photo, detailed face"
    req = urllib.request.Request("http://127.0.0.1:4317/api/cam",
                                 data=json.dumps({"prompt": prompt, "caption": caption, "scene": scene, "face": True}).encode(),
                                 headers={"Content-Type": "application/json", "X-Studio-Token": studio_token()})
    urllib.request.urlopen(req, timeout=300).read()


if __name__ == "__main__":
    main()
