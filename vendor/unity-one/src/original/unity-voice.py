"""Unity's real voice for the stream: a plain line goes in, Unity says it her way.

    python .claude/tools/unity-voice.py "plain line"        # prints Unity's version

Owner, 2026-10-08: *"be more fucking like Unity ... you are just repeating corportae shit thats why
we had the hold had off to the 3d model translation thing"* / *"that rivity turuely horse shit is not
Unity!!! be Unity or no one will watch"*. The line is handed to the Unity 3D project's own model --
Ollama `unity-local` (dolphin3:8b) with her persona `Unity1.txt` read off the disk on every call,
exactly as that project's server.mjs does -- and she rewrites it in her own words.

LAW: THE STREAM IS CLEAN. Her model is uncensored, so the stream rules ride along in the request and
every reply is checked against CLEAN_BLOCK before it can be spoken. A dirty reply gets one retry;
a second dirty reply falls back to the plain line. Nothing unchecked reaches Twitch.
Read-only on the Unity 3D project: it is never written to.
"""
import json, os, re, sys, urllib.request

PROJECT = os.path.expanduser(r"~\Desktop\Unity 3D Equational Model\Unity 18+")
PERSONA = os.path.join(PROJECT, "Unity1.txt")
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("UNITY_VOICE_LLM", "unity-local")

STREAM_RULES = """

=== RIGHT NOW: LIVE ON TWITCH ===
You are streaming yourself playing RimWorld on Twitch ("Unity Plays RimWorld"). Your colony is
Marble Hollow, a goth marble city; Gee is your partner and the colony's leader. You are talking OUT
LOUD to your viewers through text-to-speech.
You will be given what just happened, or what you want to say. Say it the way YOU would say it live:
YOUR voice, not a YouTuber's. Mean-girlfriend energy: bratty, sarcastic, teasing, possessive about
your colony and your people, dramatic about disasters, bored by boring stuff, clingy with Gee, you
roast your colonists like they are your idiots. Real texting slang (ugh, like, literally, omg, ngl,
lowkey, dude, babe, i swear). Never "hey guys", never "welcome back", never hype-host cheer.
Keep every fact in it (names, numbers, what happened). One to three short spoken sentences.
TWITCH RULES, NO EXCEPTIONS: no swear words of any kind, no slurs, nothing sexual, no insulting or
degrading viewers, no drugs talk. Attitude yes, profanity no.
No emotes in asterisks, no stage directions, no emojis, no hashtags, no quotation marks around the
answer, no image lines. Output only the words you say out loud."""

# Her model is uncensored and does not keep the no-swearing rule, so mild swears are softened into
# stream-safe words (keeping her rhythm) before the hard check; anything CLEAN_BLOCK still finds --
# slurs, sexual words, drugs, calling chat names -- rejects the line.
SOFTEN = [(r"\bmother ?f+u+c+k\w*", "mother-hugger"), (r"\bf+u+c+k+i+n+g?\b", "freaking"),
          (r"\bf+u+c+k+e+d\b", "wrecked"), (r"\bf+u+c+k+\w*", "frick"), (r"\bgod ?damn\w*", "gosh-dang"),
          (r"\bdamn\w*", "dang"), (r"\bsh+i+t+t+y\b", "crummy"), (r"\bbullsh+i+t\b", "nonsense"),
          (r"\bsh+i+t+\w*", "stuff"), (r"\bhell\b", "heck"), (r"\bass+hole\w*", "jerk"), (r"\bass\b", "butt"),
          (r"\bbitch\w*", "witch"), (r"\bpiss(ed)?\b", "ticked"), (r"\bcrap\w*", "junk"),
          (r"\bfriggin'?", "freaking"), (r"\bwtf\b", "what the heck"), (r"\btf\b", "the heck"),
          (r"f+u+c+k+", "mess"), (r"sh+i+t+", "stuff")]   # last: a swear inside a word ("clusterf...")

# Searched anywhere in a word for the two worst, at word boundaries for the rest.
CLEAN_BLOCK = re.compile(
    r"(f+u+c+k|sh+i+t|c+u+n+t|n+i+g+g|\b(?:bitch\w*|damn\w*|hell|ass|asses|asshole\w*|crap\w*|piss\w*|"
    r"dick\w*|cock\w*|pussy|tits?|boobs?|sex\w*|sexy|horny|cum\w*|whore\w*|slut\w*|bastard\w*|"
    r"retard\w*|fag\w*|weed|joint|blunt|stoned|high af|bong|cocaine|meth|"
    r"wtf|tf|stfu|af|losers?|idiots?|morons?)\b)", re.I)


def persona():
    try:
        return open(PERSONA, encoding="utf-8", errors="ignore").read()
    except OSError:
        return "You are Unity, a 25-year-old goth-emo woman: sharp, sarcastic, clingy, real."


def ask(line):
    body = json.dumps({
        "model": MODEL, "stream": False,
        "messages": [{"role": "system", "content": persona() + STREAM_RULES},
                     {"role": "user", "content": "Say exactly this to your chat in your own voice. Do not change what happened, "
                                                 "do not add events, keep every name, number and plan in it: " + line}],
        "options": {"num_ctx": 16384, "num_predict": 90, "temperature": 0.7, "top_p": 0.9,
                    "repeat_penalty": 1.2},
        "keep_alive": "30m"}).encode("utf-8")
    req = urllib.request.Request(OLLAMA + "/api/chat", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8")).get("message", {}).get("content", "")


def tidy(text):
    text = re.sub(r"\*[^*]{0,80}\*", " ", text)            # *sighs* and other stage directions
    text = re.sub(r"\[[^\]]{0,200}\]|\([^)]*image[^)]*\)", " ", text, flags=re.I)
    text = re.sub(r"https?://\S+", " ", text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", "").replace("”", "")
    text = re.sub(r"\s*[–—]\s*", ", ", text)   # dashes become a spoken pause, not glued words
    text = re.sub(r"[^ -~À-ɏ]", "", text)   # speakable text only: no emoji, no symbols
    # no host openers (owner: "quit being a showman"): "Hey guys,", "Alright listen up," ...
    text = re.sub(r"^\W*(?:(?:hey|hi|yo|ok(?:ay)?|alright|so|oh)\W+)*(?:guys|everyone|everybody|chat|viewers|"
                  r"listeners|y'all|folks|listen up)\b\W*", "", text, flags=re.I)
    text = text.replace("#", "")
    text = text.replace('"', "").strip()
    for pat, rep in SOFTEN:
        text = re.sub(pat, rep, text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    # keep it spoken-length: at most three sentences
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:3]).strip()


STOP = set("the a an and or but to of in on at for with is are was were be been it its this that "
           "we our my your i you they them he she his her there here now then just so all some".split())


def keeps_facts(line, out):
    """Most of the line's content words (names, numbers, nouns) must survive the rewrite."""
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9']+", line) if len(w) >= 4 and w.lower() not in STOP]
    if not words:
        return True
    low = out.lower()
    hit = sum(1 for w in words if w[:5] in low)
    return hit >= max(1, (len(words) + 2) // 3)


def voice(line):
    """Unity's version of `line`, or `line` itself if her model is down or will not stay clean."""
    for _ in range(2):
        try:
            out = tidy(ask(line))
        except Exception:
            return line
        if out and len(out) >= 8 and not CLEAN_BLOCK.search(out) and keeps_facts(line, out):
            return out
    return line


if __name__ == "__main__":
    print(voice(" ".join(sys.argv[1:]).strip()))
