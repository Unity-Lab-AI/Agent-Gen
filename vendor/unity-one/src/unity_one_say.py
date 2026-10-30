"""Unity One voice, standalone: text in, Unity's spoken WAV out.

Same pipeline as the Backrooms stream, minus Twitch/OBS/studio plumbing:
  1. (optional) TEXT SIDE  - the plain line is rewritten in Unity's words by Ollama
     `unity-local` (dolphin3:8b) with persona Unity1.txt + stream rules + clean filter
     (logic imported from the copy of unity-voice.py in src/original/).
  2. SPEECH SIDE           - Piper en_US-hfc_female-medium (22.05 kHz) synthesises the
     whole sentence in one pass ("Equation Unity One": whole-sentence, not word bank).

    python src/unity_one_say.py "the wall is done"                 # raw text -> out/unity_one.wav
    python src/unity_one_say.py --unity "the wall is done"         # rewrite in her voice first (needs Ollama)
    python src/unity_one_say.py --out my.wav --play "hello"        # custom path, play it after

Env overrides: UNITY_ONE_VOICE (path to .onnx), OLLAMA_URL, UNITY_VOICE_LLM, UNITY_ONE_PERSONA.
"""
import argparse, importlib.util, os, sys, wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOCAL_VOICE = os.path.join(ROOT, "models", "piper", "en_US-hfc_female-medium.onnx")
ORIGINAL_VOICE = os.path.expanduser(
    r"~\Desktop\Unity 3D Equational Model\Unity 18+\models\piper\en_US-hfc_female-medium.onnx")
VOICE = os.environ.get("UNITY_ONE_VOICE") or (LOCAL_VOICE if os.path.exists(LOCAL_VOICE) else ORIGINAL_VOICE)
LOCAL_PERSONA = os.path.join(ROOT, "persona", "Unity1.txt")


def unity_words(line):
    """Rewrite `line` in Unity's own voice via the stream's exact logic; falls back to `line`."""
    spec = importlib.util.spec_from_file_location("unity_voice", os.path.join(HERE, "original", "unity-voice.py"))
    uv = importlib.util.module_from_spec(spec); spec.loader.exec_module(uv)
    uv.PERSONA = os.environ.get("UNITY_ONE_PERSONA") or (
        LOCAL_PERSONA if os.path.exists(LOCAL_PERSONA) else uv.PERSONA)
    return uv.voice(line)


def synth(text, out, length_scale=None):
    from piper import PiperVoice
    voice = PiperVoice.load(VOICE)
    with wave.open(out, "wb") as wav:
        if hasattr(voice, "synthesize_wav"):          # piper-tts >= 1.3
            kw = {}
            if length_scale:
                from piper import SynthesisConfig
                kw["syn_config"] = SynthesisConfig(length_scale=length_scale)
            voice.synthesize_wav(text, wav, **kw)
        else:                                          # older piper-tts
            voice.synthesize(text, wav)
    return out


def main():
    ap = argparse.ArgumentParser(description="Unity One voice: text -> WAV")
    ap.add_argument("text", nargs="+")
    ap.add_argument("--unity", action="store_true", help="rewrite in Unity's words via Ollama first")
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "unity_one.wav"))
    ap.add_argument("--speed", type=float, default=None, help="piper length_scale (1.0 = stock; >1 slower)")
    ap.add_argument("--play", action="store_true", help="play the WAV after (Windows winsound)")
    a = ap.parse_args()
    text = " ".join(a.text).strip()
    if a.unity:
        text = unity_words(text)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    synth(text, a.out, a.speed)
    print(text)
    print("wrote", os.path.abspath(a.out), "voice", VOICE)
    if a.play:
        import winsound
        winsound.PlaySound(a.out, winsound.SND_FILENAME)


if __name__ == "__main__":
    sys.exit(main())
