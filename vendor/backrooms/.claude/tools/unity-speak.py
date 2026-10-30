"""Unity's voice: her own trained voice (models/unity-voice-v2 since 2026-10-13; v1 kept in models/unity-voice), served by its serve.py on :5123.

    python .claude/tools/unity-speak.py "text to say"          # speak and wait
    python .claude/tools/unity-speak.py --bg "text to say"     # speak, return at once

Delivery comes from UNITY_SPEAK_EMOTION / UNITY_SPEAK_ACT (set by the autopilot from the brain's say/reply_chat call).
There is no fallback voice (owner 2026-10-13: fallbacks are against the laws; Piper is retired): if her voice
server is down or refuses the line, this exits non-zero with the reason on stderr and the caller logs it.
Punctuation her voice has no phoneme for (; : -- dashes brackets quotes !) is spoken as the pause it has (a comma,
or a full stop) before the request -- see voice_text(); words are never dropped. An exact repeat of one of the
last 20 lines that played exits non-zero with "REPEAT: ..." so the caller rephrases (.local/tmp/unity-spoken-recent.txt).
Writes a temp WAV and hands it to OBS's "Unity voice" media source and the stream studio (POST /api/voice).
"""
import os, re, sys, time, wave, tempfile, subprocess

VOICE_URL = os.environ.get("UNITY_VOICE_TTS_URL", "http://127.0.0.1:5123")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # the project root


def voice_text(text):
    """The line as her voice can take it. Her phoneme vocabulary holds exactly four marks -- space , . ? -- and the
    frontend (speech_text.py) is sha256-bound into voice-meta.json, so it cannot grow a pause entry without a
    re-export; the server refuses the WHOLE line on any other mark (2026-10-13: every ";" and ":" line was silent on
    stream, logged as said). misaki passes : ; ( ) and em/en dashes through as-is, turns straight and single quotes
    into curly ones, and drops "--" without a pause. So here every mark she lacks becomes the pause she has: a
    comma. "!" speaks as "." (owner-approved; the exclamation act keeps the energy). Words are never dropped --
    only [laughter] and [breath], her two recorded events, keep their brackets."""
    t = str(text)
    keep = {}
    for i, m in enumerate(re.findall(r"\[(?:laughter|breath)\]", t, flags=re.I)):
        key = "\x00%d\x00" % i
        keep[key] = m.lower()
        t = t.replace(m, key, 1)
    t = t.replace("…", "...")
    t = re.sub(r"\.{2,}", ".", t)
    t = re.sub(r"[?!]*!+[?!]*", lambda m: "?" if "?" in m.group() else ".", t)
    t = re.sub(r"[\"“”„«»]", "", t)                       # double quotes: silent
    t = re.sub(r"(?<![A-Za-z0-9])['‘’`]+|['‘’`]+(?![A-Za-z0-9])", "", t)   # quotes, not don't
    t = t.replace("’", "'").replace("‘", "'")
    t = re.sub(r"\s*(?:[;:]|--+|[—–]|[()\[\]{}<>]|\*+|_+|\|+|\^+|~+|\\+|/(?!\d))\s*", ", ", t)
    t = re.sub(r"\s*([,.?])", r"\1", t)                                              # no space before a mark
    t = re.sub(r"([,.?])(?=[^\s,.?])", r"\1 ", t)                                    # one space after a mark
    for _ in range(3):
        t = re.sub(r",(?:\s*,)+", ",", t)                                            # ", ," -> ","
        t = re.sub(r",\s*([.?])", r"\1", t)                                          # ", ." -> "."
        t = re.sub(r"([.?])\s*,", r"\1", t)                                          # ". ," -> "."
        t = re.sub(r"\.(?:\s*\.)+", ".", t)
        t = re.sub(r"\?(?:\s*[?.])+", "?", t)
    t = re.sub(r"\s+", " ", t).strip().lstrip(",.? ").strip()
    for key, m in keep.items():
        t = t.replace(key, " " + m + " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


RECENT = os.path.join(ROOT, ".local", "tmp", "unity-spoken-recent.txt")
RECENT_KEEP = 20


def _recent_key(text):
    return " ".join(re.findall(r"[a-z0-9']+", voice_text(text).lower()))


def is_repeat(text):
    """Owner's rule: nothing goes out on stream twice. The last 20 lines actually played live in a small file; an
    exact repeat (same words, ignoring case and marks) is refused before it is made, and the caller tells the
    brain to rephrase."""
    key = _recent_key(text)
    if not key:
        return False
    try:
        with open(RECENT, encoding="utf-8") as f:
            return key in [line.rstrip("\n") for line in f]
    except OSError:
        return False


def remember(text):
    key = _recent_key(text)
    if not key:
        return
    try:
        os.makedirs(os.path.dirname(RECENT), exist_ok=True)
        try:
            with open(RECENT, encoding="utf-8") as f:
                lines = [line.rstrip("\n") for line in f if line.strip()]
        except OSError:
            lines = []
        lines = [line for line in lines if line != key] + [key]
        with open(RECENT, "w", encoding="utf-8") as f:
            f.write("\n".join(lines[-RECENT_KEEP:]) + "\n")
    except OSError:
        pass


def synth(text, out):
    import json, urllib.request, urllib.error
    body = {"text": voice_text(text)}
    if os.environ.get("UNITY_SPEAK_EMOTION"):
        body["emotion"] = os.environ["UNITY_SPEAK_EMOTION"]
    if os.environ.get("UNITY_SPEAK_ACT"):
        body["speech_act"] = os.environ["UNITY_SPEAK_ACT"]
    req = urllib.request.Request(VOICE_URL + "/say", json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        wav = urllib.request.urlopen(req, timeout=60).read()
    except urllib.error.HTTPError as e:
        raise SystemExit("her voice refused the line: %s" % e.read().decode(errors="replace")[:300])
    except OSError as e:
        raise SystemExit("her voice server is not reachable at %s (%s)" % (VOICE_URL, e))
    with open(out, "wb") as f:
        f.write(wav)


LOCK = os.path.join(tempfile.gettempdir(), "unity-voice.lock")


def take_turn(wait=90, stale=120):
    """One line at a time across processes: parallel calls queue here instead of talking over each other."""
    end = time.time() + wait
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode()); os.close(fd)
            return True
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(LOCK) > stale:
                    os.remove(LOCK); continue
            except OSError:
                continue
            if time.time() > end:
                return False
            time.sleep(0.2)


def give_turn():
    try:
        os.remove(LOCK)
    except OSError:
        pass


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
    if not take_turn():
        # exit 0 here told the caller the line was said when nothing was ever made
        raise SystemExit("her voice was busy for 90 s and this line was never made")
    out = os.path.join(tempfile.gettempdir(), "unity-voice-%d-%d.wav" % (os.getpid(), int(time.time() * 1000)))
    try:
        if is_repeat(text):            # checked under the turn lock, so two speakers with one line cannot both pass
            raise SystemExit("REPEAT: that exact line already went out on stream (one of the last %d); say it differently"
                             % RECENT_KEEP)
        speak(text, out)
    finally:
        give_turn()
        try:
            os.remove(out)
        except OSError:
            pass


def studio_token():
    tok = os.environ.get("STUDIO_TOKEN")
    if tok:
        return tok
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".studio-token"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def wav_seconds(path):
    try:
        with wave.open(path, "rb") as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except Exception:
        return 0.0


class _OneVoice:
    """One line plays at a time across EVERY speaker (her turns, the host voice, the switch). Owner, 2026-10-13: "she is
    talking all over herself not letting the tts finish". The audio is made in parallel; playing waits its turn on a
    lock file and holds it until the line has finished. A holder that dies releases it with its process."""
    PATH = os.path.join(tempfile.gettempdir(), "unity-voice-playing.lock")

    def __enter__(self):
        import msvcrt
        self.f = open(self.PATH, "a+b")
        deadline = time.time() + 180
        while True:
            try:
                self.f.seek(0); msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1); return self
            except OSError:
                if time.time() > deadline: return self      # never hang a speaker forever
                time.sleep(0.2)

    def __exit__(self, *a):
        import msvcrt
        try: self.f.seek(0); msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError: pass
        self.f.close()


def post_chat():
    """The chat/overlay row for this line, written the moment it starts playing -- not when it was written (owner,
    2026-10-13: "she is still sending like 3-4 messages at once"). Callers hand the shown text and reply id over in
    UNITY_SPEAK_CHAT / UNITY_SPEAK_REPLY_TO; without them nothing is posted (a caller that posts itself)."""
    shown = os.environ.get("UNITY_SPEAK_CHAT", "").strip()
    if not shown:
        return
    import json
    box = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".studio-outbox.jsonl")   # .claude/.studio-outbox.jsonl
    last = 0
    if os.path.exists(box):
        for line in open(box, encoding="utf-8"):
            try: last = max(last, int(json.loads(line).get("id", 0)))
            except Exception: pass
    reply = os.environ.get("UNITY_SPEAK_REPLY_TO", "")
    with open(box, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": last + 1, "replyTo": int(reply) if reply.isdigit() else None,
                            "ts": int(time.time() * 1000), "persona": "unity", "text": shown}) + "\n")


def speak(text, out):
    synth(text, out)
    if os.name != "nt":
        post_chat()
        _play(out)
        remember(text)
        return
    with _OneVoice():
        post_chat()
        _play(out)
        remember(text)           # only a line that actually played counts as said
        time.sleep(0.4)          # a breath between lines


def _play(out):
    # The stream hears the voice through OBS's "Unity voice" media source, which plays this file:
    # OBS decodes it itself (the browser-source audio route crackled to static on stream).
    try:
        import shutil, obsws_python as obs
        live = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".studio-images",
                            "obs-voice-%d-%d.wav" % (int(time.time() * 1000), os.getpid()))
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
                               headers={"Content-Type": "application/json", "X-Studio-Token": studio_token()}),
                               timeout=10).read()
        # The overlay page only STORES the line (its /api/voice is a state endpoint, not a player), so the owner
        # heard nothing at his desk -- "get her speech working wtf did we make V2 if its not goning to work"
        # (2026-10-13). Play it here on the default output as well: OBS's Desktop Audio is muted, so this never
        # reaches the stream; the stream hears the OBS media source above. Playing blocks for the line's length,
        # which is the hold the next line needs.
    except Exception:
        pass
    import winsound
    winsound.PlaySound(out, winsound.SND_FILENAME)


if __name__ == "__main__":
    main()
