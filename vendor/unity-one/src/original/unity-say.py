"""Streamer narration: speak a line in Unity's voice AND post it to the Persona Studio chat.

    python .claude/tools/unity-say.py "line"            # speaks in the background, returns at once
    python .claude/tools/unity-say.py --wait "line"     # speaks and waits until done

The line is appended to .claude/.studio-outbox.jsonl (replyTo null = unprompted narration), so
the studio window shows what Unity is saying while she plays.
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUTBOX = os.path.join(HERE, "..", ".studio-outbox.jsonl")


def post(text, persona="unity"):
    last = 0
    if os.path.exists(OUTBOX):
        for line in open(OUTBOX, encoding="utf-8"):
            try: last = max(last, int(json.loads(line).get("id", 0)))
            except Exception: pass
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": last + 1, "replyTo": None, "ts": int(time.time() * 1000),
                            "persona": persona, "text": text}) + "\n")


def speakable(text):
    """Only words reach the voice and the chat (owner, 2026-10-09: "dont tts speak the emojis and none
    verbalized need shit"): drop emoji and pictographs, *stage directions* and (asides in brackets),
    hashtags, markdown, and stray symbols."""
    import re
    text = re.sub(r"\*[^*]{0,80}\*|\[[^\]]{0,80}\]|<[^>]{0,80}>", " ", text)          # *sighs*, [laughs], <tags>
    text = re.sub(r"#\w+", " ", text)
    text = "".join(ch for ch in text if ord(ch) < 0x2190)                                  # emoji, dingbats, arrows
    text = re.sub(r"[_~`^|\\{}]+", " ", text)
    return re.sub(r"\s+", " ", text).strip(" -")


def main():
    args = sys.argv[1:]
    wait = bool(args) and args[0] == "--wait"
    if wait: args = args[1:]
    raw = bool(args) and args[0] == "--raw"
    if raw: args = args[1:]
    text = " ".join(args).strip()
    if not text: return
    # Unity's own words: the plain line goes through the Unity 3D project's model (unity-voice.py,
    # stream-filtered); --raw skips it. Owner: "be Unity or no one will watch".
    if not raw:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("unity_voice", os.path.join(HERE, "unity-voice.py"))
            uv = importlib.util.module_from_spec(spec); spec.loader.exec_module(uv)
            text = uv.voice(text)
        except Exception:
            pass
    text = speakable(text)
    if not text: return
    post(text)
    # a picture with every line (owner: "make some images more offten like as much as you talk")
    _gl = os.path.join(HERE, "..", ".cam-highlight.json")
    try: _recent = time.time() - json.load(open(_gl)).get("ts", 0) < 90
    except Exception: _recent = False
    if not os.environ.get("UNITY_NO_GLANCE") and not _recent:   # highlights stay occasional; Unity's face holds the panel   # a caller with its own highlighted shot (tour-base.py) sets this
        subprocess.Popen([sys.executable, os.path.join(HERE, "unity-glance.py"), text],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    speak = [sys.executable, os.path.join(HERE, "unity-speak.py")] + ([] if wait else ["--bg"]) + [text]
    subprocess.run(speak)


if __name__ == "__main__":
    main()
