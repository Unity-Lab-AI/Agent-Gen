"""Unity's voice: load the trained pair in this folder and turn text into a wav.

    python unity_voice.py "Hello chat." out.wav --emotion amused --intensity .35

    from unity_voice import Voice
    wav = Voice().say("Hello chat.", "amused")        # float32 numpy array at 24 kHz

Uses only this folder: acoustic.pt, vocoder.pt, voice-meta.json and the model code beside them. A delivery
she was never trained on (an unknown emotion/speech act, or an intensity/pace outside her recorded range) is
refused with the reason, never faked.
"""
import argparse, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import soundfile as sf                                                     # noqa: E402
import torch                                                               # noqa: E402
from misaki import en, espeak                                              # noqa: E402

import infer                                                               # noqa: E402
from dataset_contract import ACOUSTIC_CONFIG, CHECKPOINT_SCHEMA, EMOTIONS, FEATURES, SPEECH_ACTS, VOCODER_CONFIG  # noqa: E402
from model import UnityVoice                                               # noqa: E402
from student_state import require_finite_state                             # noqa: E402
from vocoder import Generator                                              # noqa: E402

# Natural pace. UNITY_VOICE_LENGTH_SCALE above 1.0 slows her down, below speeds her up.
infer.LENGTH_SCALE[0] = float(os.environ.get("UNITY_VOICE_LENGTH_SCALE", "1.0"))


class Voice(infer.Voice):
    def __init__(self, folder=HERE, dev=None):
        self.dev = dev or ("cuda" if torch.cuda.is_available() else "cpu")
        folder = Path(folder)
        meta = json.loads((folder / "voice-meta.json").read_text(encoding="utf-8"))
        identity = meta.get("identity", {})
        if (meta.get("schema") != CHECKPOINT_SCHEMA or identity.get("acoustic_config") != ACOUSTIC_CONFIG
                or identity.get("vocoder_config") != VOCODER_CONFIG or identity.get("emotions") != list(EMOTIONS)
                or identity.get("speech_acts") != list(SPEECH_ACTS)):
            raise ValueError("voice-meta.json does not match this model code")
        acoustic = torch.load(folder / "acoustic.pt", map_location=self.dev, weights_only=True)
        vocoder = torch.load(folder / "vocoder.pt", map_location=self.dev, weights_only=True)
        if acoustic.get("identity") != identity or vocoder.get("identity") != identity:
            raise ValueError("acoustic.pt and vocoder.pt are not the pair described by voice-meta.json")
        if acoustic.get("n_symbols") != len(meta["vocab"]):
            raise ValueError("acoustic.pt has the wrong phoneme count for voice-meta.json")
        require_finite_state(acoustic["model"], "acoustic weights")
        require_finite_state(vocoder["G"], "vocoder weights")
        self.vocab = meta["vocab"]
        self.support = meta["delivery_support"]
        self.event_support = meta["event_support"]
        self.am = UnityVoice(len(self.vocab), **ACOUSTIC_CONFIG).to(self.dev).eval()
        self.am.load_state_dict(acoustic["model"])
        self.voc = Generator(**VOCODER_CONFIG).to(self.dev).eval()
        self.voc.load_state_dict(vocoder["G"])
        self.g2p = en.G2P(trf=False, british=False, fallback=espeak.EspeakFallback(british=False))


def main():
    parser = argparse.ArgumentParser(description="Unity's voice: text in, wav out")
    parser.add_argument("text"); parser.add_argument("out")
    parser.add_argument("--emotion", default="neutral", choices=EMOTIONS)
    parser.add_argument("--intensity", type=float, help="0..1; default 0.35 (0 for neutral)")
    parser.add_argument("--speech-act", choices=SPEECH_ACTS, help="default: guessed from the punctuation")
    args = parser.parse_args()
    wav = Voice().say(args.text, args.emotion, args.intensity, 1.0, args.speech_act)
    sf.write(args.out, wav, FEATURES["sample_rate"], subtype="PCM_16")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
