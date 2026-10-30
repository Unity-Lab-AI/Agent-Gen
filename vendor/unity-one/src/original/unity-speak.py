"""Unity's voice: Piper en_US-hfc_female-medium, the same model the Unity 3D project uses.

    python .claude/tools/unity-speak.py "text to say"          # speak and wait
    python .claude/tools/unity-speak.py --bg "text to say"     # speak, return at once

Model path: UNITY_VOICE_MODEL env var, else the Unity 3D project's copy on the desktop.
Writes a temp WAV and hands it to the stream studio (POST /api/voice): the overlay page plays it,
which is how the voice reaches Twitch (OBS browser source audio). If the studio is down it plays
locally with winsound instead.
"""
import os, sys, wave, tempfile, subprocess

MODEL = os.environ.get("UNITY_VOICE_MODEL") or os.path.expanduser(
    r"~\Desktop\Unity 3D Equational Model\Unity 18+\models\piper\en_US-hfc_female-medium.onnx")


def synth(text, out):
    from piper import PiperVoice
    voice = PiperVoice.load(MODEL)
    with wave.open(out, "wb") as wav:
        if hasattr(voice, "synthesize_wav"):
            voice.synthesize_wav(text, wav)
        else:
            voice.synthesize(text, wav)


def main():
    args = sys.argv[1:]
    bg = False
    if args and args[0] == "--bg":
        bg = True; args = args[1:]
    text = " ".join(args).strip()
    if not text:
        return
    if bg:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), text],
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    out = os.path.join(tempfile.gettempdir(), "unity-voice.wav")
    synth(text, out)
    # The stream hears the voice through OBS's "Unity voice" media source, which plays this file:
    # OBS decodes it itself (the browser-source audio route crackled to static on stream).
    try:
        import shutil, obsws_python as obs
        import time
        live = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".studio-images",
                            "obs-voice-%d.wav" % int(time.time() * 1000))
        shutil.copyfile(out, live)
        cl = obs.ReqClient(host="127.0.0.1", port=4455, timeout=5)
        # a NEW path each line: OBS re-opens the media only when the file setting changes
        cl.set_input_settings("Unity voice", {"local_file": live, "is_local_file": True}, True)
    except Exception:
        pass
    # The overlay page plays it too, so the owner hears it locally (desktop audio is muted in OBS).
    try:
        import base64, json, urllib.request
        url = os.environ.get("STUDIO_URL", "http://127.0.0.1:4317") + "/api/voice"
        data = json.dumps({"wav": base64.b64encode(open(out, "rb").read()).decode()}).encode()
        urllib.request.urlopen(urllib.request.Request(url, data=data,
                               headers={"Content-Type": "application/json"}), timeout=10).read()
        return
    except Exception:
        pass
    import winsound
    winsound.PlaySound(out, winsound.SND_FILENAME)


if __name__ == "__main__":
    main()
