"""Unity's webcam renderer with facial retention.

    python .claude/tools/unity-face-sd.py            # serves on 127.0.0.1:7862

Loads the Unity 3D project's realistic-vision checkpoint read-only. The first request with
"reference": true (or no reference on disk) renders Unity's reference portrait with a fixed seed
and saves it to .claude/.studio-images/unity-reference.png. Every later webcam frame is an
img2img pass over that reference at moderate strength with the same seed, so the face stays hers
while the expression and pose change.

API (A1111-shaped): POST /sdapi/v1/txt2img {prompt, negative_prompt?, strength?, seed?, reference?}
"""
import base64, io, json, os, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CKPT = os.path.expanduser(r"~\Desktop\Unity 3D Equational Model\Unity 18+\models\realistic-vision-v51.safetensors")
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "..", ".studio-images", "unity-reference.png")
PORT = int(os.environ.get("UNITY_FACE_PORT", "7862"))
# Owner, 2026-10-13: "Webcam pictures on the CPU" -- with the game, OBS and the brain on the 16 GB card, a picture
# rendered on the GPU pushed it past 16 GB and every brain call timed out (she went silent). CPU by default;
# UNITY_FACE_DEVICE=cuda puts it back on the GPU.
DEVICE = os.environ.get("UNITY_FACE_DEVICE", "cpu")
# a CPU step is ~15 s while the game runs; 20 steps keeps a webcam frame near 2 minutes (the studio waits 5)
STEPS = 20 if DEVICE == "cpu" else 30
SEED = 1031  # the owner's cam image is the reference (.claude/likeness/unity-likeness-original-cam.png), 2026-10-13
NEG = ("airbrushed, plastic skin, smooth skin, doll, cgi, render, glowing eyes, bright blue eyes, oversaturated, beauty filter, perfect skin, uncanny, nipples, nude, topless, nsfw, see-through, sheer, wardrobe malfunction, tattoo, tattoos, "
       "t-shirt, sleeves, covered chest, high neckline, hat, beret, cap, beanie, black headset, black headphones, dark skin, pale white skin, black lipstick, heavy goth makeup, neon, cartoon, anime, 3d render, blurry, lowres, bad anatomy, "
       "deformed face, extra fingers, watermark, text, child, teen, old, middle aged, wrinkles, saggy breasts, chubby, chunky, fat, plump, thick arms, wide face, round face, teenager, teen girl, young looking, childlike, baby face, petite child body, asian, east asian, japanese, korean, chinese, anime face")
# Owner, 2026-10-10: "dont look like her a homie one not like currently your about 37" -- she kept reading
# mid-thirties, so the youth cues are explicit and every ageing cue is in the negatives.
# Owner, 2026-10-13: a gaming webcam, girl next door with a hint of emo, light caucasian skin (not pale), black wavy bob
# with pink ends, busty with lifted cleavage in everyday clothes, no tattoos, no lingerie
# Owner, 2026-10-13: the girl from his cam image at her desk (the original image gen, NOT SDXL -- "its fucked just cookie
# cutting images together"): the whole frame painted over that one reference, everything else is words in the prompt
REF_PROMPT = ("amateur webcam photo of a 25 year old girl next door with a hint of emo at her desk, long straight dark hair with "
              "pink-purple streaks and blunt bangs, a bright pink cat-ear gaming headset with pink cat ears, no hat, black choker, light skin, "
              "slim waist, busty, realistic")
OUTFITS = {   # owner: bikini-style tops, string straps "ARE A GO", cozy at times; skirts half the time (seen when she stands)
    "triangle": "a tiny black triangle top, deep cleavage", "string-triangle": "a tiny black string triangle top, thin string straps, deep cleavage",
    "string-halter": "a tiny black string halter top, plunging neckline, deep cleavage", "spaghetti-cami": "a tiny white spaghetti strap crop cami, deep cleavage",
    "bandeau": "a black strapless bandeau top, deep cleavage, bare shoulders", "sweetheart": "a red sweetheart crop top, deep cleavage",
    "cutout-halter": "a black keyhole cut-out halter crop top, deep cleavage", "tie-front": "a white tie-front crop top knotted under the bust, deep cleavage",
    "off-shoulder": "a loose black off-shoulder sweater pulled low, deep cleavage", "open-hoodie": "an open grey hoodie over a tiny black bandeau top, deep cleavage",
    "corset": "a black push-up corset top, deep cleavage",
    # owner 2026-10-13: "the rull randge of clothing from blanket to sweater to eating pizza all of it"
    "knit-sweater": "an oversized cream knit sweater slipping off one shoulder, low v neckline, deep cleavage",
    "cardigan": "a cropped pink cardigan half unbuttoned over a black lace bralette, deep cleavage",
    "zip-hoodie": "a black zip hoodie unzipped low over nothing but a bralette, deep cleavage",
    "sports-bra": "a black sports bra, bare stomach, deep cleavage", "tank": "a tight white ribbed tank top, low scoop neck, deep cleavage",
    "graphic-crop": "a cropped band tank top cut low at the sides, side boob, deep cleavage",
    "flannel": "an open red flannel shirt over a black bandeau top, deep cleavage", "pajama-cami": "a pink satin pajama cami, deep cleavage",
    "mesh-crop": "a black mesh long sleeve crop top over a black bra top, deep cleavage",
    "blanket": "a fuzzy blanket wrapped around her bare shoulders over a tiny black bandeau top, deep cleavage",
}
BOTTOMS = {"plaid-skirt": "a red plaid pleated mini skirt", "black-skirt": "a black pleated mini skirt", "denim-skirt": "a denim mini skirt",
           "tennis-skirt": "a white tennis skirt", "slip-skirt": "a black satin slip skirt",
           "shorts": "frayed denim short shorts", "pj-shorts": "pink pajama shorts", "joggers": "grey low-rise joggers", "jeans": "low-rise ripped jeans", "bike-shorts": "black bike shorts"}
SKIRTS = [k for k in BOTTOMS if k.endswith("skirt")]
# owner 2026-10-13: "NOT look at the viewer and look off to the left of the images where her screen would be thats off screen to the left"
GAZE_PC = "side profile, head turned left, looking left at her screen off frame"
PROPS = {   # owner: "the images can have details the tesxt model speaks of ie drinking a sods pop , she has a soda pop"
    r"\b(soda|pop|coke|can of)": "holding a can of soda", r"\b(coffee|latte)": "holding a mug of coffee", r"\btea\b": "holding a mug of tea",
    r"\b(snack|chips|crisps)": "eating chips from a bag", r"\b(pizza)": "eating a slice of pizza", r"\b(candy|gummy|chocolate)": "eating candy",
    r"\b(controller|gamepad)": "holding a game controller", r"\b(phone|text)": "holding her phone", r"\b(water)": "drinking from a water bottle",
    r"\b(blanket|cold|freez|cozy|comfy)": "wrapped in a fuzzy blanket", r"\b(hot|heat|warm in here)": "fanning herself, a strap slipping off her shoulder",
    r"\b(stretch|tired|long day)": "stretching her arms above her head", r"\b(dance|song|music)": "dancing in her chair",
    r"\b(win|won|yes|lets go|let's go)": "both fists raised in victory", r"\b(oops|died|dead|lost)": "facepalming", r"\b(cat|kitty)": "a cat on her lap",
}
WARDROBE = os.path.join(HERE, "..", ".studio-images", "wardrobe")   # one reference per everyday top, same face
OUTFIT_STATE = os.path.join(WARDROBE, "_current.json")


def current_outfit(tops):
    """A random top held for a random 10-20 minutes, then a different one (owner, 2026-10-13: "random outfits evry 10
    minutes-20 it changes" -> "Yes, random 10-20 min"). The choice survives a restart of this service."""
    import random, time as _t
    try:
        st = json.load(open(OUTFIT_STATE, encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    if st.get("top") in tops and _t.time() < st.get("until", 0):
        return st["top"]
    pick = random.choice([t for t in tops if t != st.get("top")] or tops)
    st = {"top": pick, "until": _t.time() + random.randint(600, 1200)}
    try:
        json.dump(st, open(OUTFIT_STATE, "w", encoding="utf-8"))
    except OSError:
        pass
    return pick

_t2i = _i2i = None
_lock = threading.Lock()          # one render (and the one-time pipeline load) at a time
_waiting = threading.Semaphore(3)  # at most this many requests queued or rendering; the rest are refused


CAM = os.path.join(HERE, "..", "likeness", "unity-likeness-original-cam.png")
FACE_SCALE = float(os.environ.get("UNITY_FACE_SCALE", "0.3"))   # light: same girl, but head, gaze and expression free (owner: "her face is not to be locked")
_face_img = []


def face_image():
    if not _face_img:
        from PIL import Image as _I
        _face_img.append(_I.open(CAM).convert("RGB").crop((185, 95, 425, 335)).resize((224, 224)))
    return _face_img[0]


# owner 2026-10-13: "side view mixed gazes mixed clothing, mixed poses, dynamic actions"
ACTIONS = ["leaning in to type on her keyboard", "stretching her arms above her head", "spinning in her gaming chair",
           "one hand on her headset", "sipping from a can of soda", "leaning back with her feet up on the chair",
           "hugging one knee up on the chair", "laughing with her head thrown back", "chin resting in her hand",
           "pointing at her monitor", "twirling a strand of hair", "leaning on the desk with both elbows",
           "playing with a game controller", "sitting cross-legged in her chair",
           "turned sideways in the chair with legs over the armrest", "standing beside her desk leaning over the keyboard",
           "biting her lip, concentrating", "hands over her mouth in shock", "yawning with one arm up",
           "eating a slice of pizza", "wrapped up in a blanket with only her hands out typing", "fixing her hair behind her headset"]
# owner: "she has differnt gaze focal points mainly to her off screen screen"
GAZE_CAM = "glancing at the camera"
GAZE_MORE = ["looking down at her phone", "looking down at the food in her hand", "looking up at the ceiling, thinking", "eyes closed, laughing", "looking down at her keyboard"]
NOT_CAM = ", looking at viewer, looking at camera, eye contact, facing camera"


# owner: "NOT ONE IMAGE HAD A SINGLE THING MENTION OF THOSE 8" -- a viewer's ask or her own idea becomes concrete picture
# words the image model knows; a raw question ("you got a cat?") draws nothing
# owner: "we need dynamic coding so said item is use not a list of items" -- whatever is asked is drawn: her text model
# rewrites the ask as what the camera sees -- no fallbacks (owner: "no fallbacks!"). The one fixed rule is Twitch: no
# nudity, ever.
NUDE = r"\b(top off|topless|naked|nude|nudes|bare ?chest\w*|undress\w*|strip\w*|no top|no shirt|no bra|boobs? out|tits|flash\w*|nipples?)\b"
NO_THANKS = "crossing her arms, shaking her head with a teasing smile, fully dressed"
SCENE_ASK = ("Rewrite a stream viewer's request to a webcam girl as a short photo description (max 18 words) of what "
             "the camera sees her doing, holding or wearing. Keep the exact item, color and action they named. "
             "If it changes her clothes, start with 'WEAR:' and name the clothing. She always stays dressed. "
             "Reply with the description only.\nRequest: ")
_scene_cache = {}


def _brain_scene(t):
    """Her own text model turns the ask into picture words (the model already loaded for the stream; no load options)."""
    if t in _scene_cache:
        return _scene_cache[t]
    import urllib.request as _u
    url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    try:
        names = [m["name"] for m in json.loads(_u.urlopen(url + "/api/ps", timeout=2).read()).get("models", [])]
        model = os.environ.get("AUTOPILOT_MODEL") or (names[0] if names else "")
        if not model:
            return None
        body = {"model": model, "prompt": SCENE_ASK + t, "stream": False, "think": False}
        r = json.loads(_u.urlopen(_u.Request(url + "/api/generate", json.dumps(body).encode(),
                                             {"Content-Type": "application/json"}), timeout=25).read())
        out = (r.get("response") or "").strip().strip('"').splitlines()[0][:160]
    except Exception:
        return None
    _scene_cache[t] = out or None
    return _scene_cache[t]


def scene_words(text):
    """Her scene / a viewer's ask -> (picture words, outfit override or None, blocked?). Any item, any action."""
    import re as _re
    t = " ".join((text or "").lower().split())
    if not t:
        return "", None, False
    if _re.search(NUDE, t):
        return NO_THANKS, None, True
    said = _brain_scene(t)
    if said and _re.search(NUDE, said.lower()):
        return NO_THANKS, None, True
    if said:
        if said.upper().startswith("WEAR:"):
            return "", said[5:].strip(), False
        return said, None, False
    return "", None, False   # no text model answer: nothing is added (owner: "no fallbacks!")


# owner: "the girls ag to be about 3-5 years older than current so 20-25"
SHE = "the same 24 year old white caucasian adult woman, european features, mature face: long straight dark hair with pink-purple streaks, blunt bangs, bright pink cat-ear headset, black choker"


# the frame prompt's identity, SHORT: the reference image and the IP-Adapter face lock carry who she is (test run
# 2026-10-13: the frame prompt ran 149 CLIP tokens against 77 with REF_PROMPT at the end, so the identity, the skin
# and whatever came last never reached the picture)
WHO = "amateur webcam photo, the same woman, pink cat-ear headset, black choker, realistic"


def fit_clip(parts, drop):
    """CLIP reads 77 tokens and drops the rest without a word. Count with the pipeline's own tokenizer and drop the
    least important parts, in `drop` order, until the prompt fits; what is kept is kept whole."""
    parts = [p for p in parts if p]
    def n(text):
        try:
            pipes(); return len(_t2i.tokenizer(text).input_ids)
        except Exception:
            return int(len(text.split()) * 1.4) + 2
    for d in drop:
        if n(", ".join(parts)) <= 77: break
        if d in parts: parts.remove(d)
    text = ", ".join(parts)
    if n(text) > 77:
        print("face: prompt still %d CLIP tokens after dropping the optional parts: %s" % (n(text), text[:160]), flush=True)
    return text


def fit_tokens(text, limit=75):
    """Cut a prompt to CLIP's window by its own tokenizer (the negatives ran ~147 tokens: everything past 77 was dropped
    without a word, run 3 2026-10-13 21:23 `93 > 77`). The first words are the ones that matter, so the tail goes."""
    try:
        pipes(); tok = _t2i.tokenizer
        ids = tok(text).input_ids
        if len(ids) <= limit + 2: return text
        return tok.decode(ids[1:limit + 1]).strip()
    except Exception:
        words = text.split()
        return " ".join(words[:55]) if len(words) > 55 else text


def compose(req):
    """The whole frame as words: what the caller asked (mood / pose) + her outfit of the moment + where she looks + what
    she is holding (from the line she just said) + who she is. Mood first: CLIP reads only 77 tokens."""
    import random, re as _re
    asked = (req.get("prompt") or "").strip()
    top = req.get("outfit") if req.get("outfit") in OUTFITS else current_outfit(sorted(OUTFITS))
    rnd = random.Random(top + str(int(time.time() // 600)))        # the bottom changes with the outfit: a skirt half the time
    bottom = BOTTOMS[rnd.choice(SKIRTS if rnd.random() < 0.5 else [k for k in BOTTOMS if k not in SKIRTS])]
    if req.get("bottom") in BOTTOMS:
        bottom = BOTTOMS[req["bottom"]]
    outfit = OUTFITS[top]
    r = random.random()   # her PC most of the time, the camera now and then, sometimes her phone, food or nowhere
    gaze = req.get("gaze") or (GAZE_PC if r < 0.65 else GAZE_CAM if r < 0.8 else random.choice(GAZE_MORE))
    req["_not_cam"] = gaze != GAZE_CAM
    said = (req.get("caption") or req.get("said") or "").lower()
    props = [v for k, v in PROPS.items() if _re.search(k, said)][:1]
    action = req.get("action") or random.choice(ACTIONS)
    # owner: "the option for the text model to add mixes to all the genraation as she sees fit or as viewers talk to her"
    # -- her own scene words (what she is doing / holding / wearing) win over the random action and the caption props
    scene, scene_outfit, blocked = scene_words((req.get("scene") or "")[:120])
    req["_scene"] = bool(scene or scene_outfit)
    if scene_outfit:
        outfit, cozy_out = scene_outfit, True
    if scene or scene_outfit:
        # the ask FIRST, then the gaze mix (owner: "it need the gaze focus range that home-range 4 had" -- mainly her screen
        # off frame left, sometimes the camera, phone, food...), then who she is (owner: "no girl persistance to the girl
        # ive chosen") and the clothes
        head = [scene] if scene else []
        wearing = "wearing " + outfit + " and " + bottom
        return fit_clip([gaze] + head + [wearing, WHO], drop=[WHO, wearing])
    # CLIP reads 77 tokens: the clothes and skin FIRST (owner: "not nearly enough skin and shoulders and her clevage was all
    # covered up"), then the moment (mood, action, gaze, props), then who she is
    # cozy layers (blanket, sweater, hoodie, flannel, cardigan) must stay visible: no forced bare shoulders on those; the
    # action and anything in her hands come right after the clothes so CLIP reads them before the 77-token cut
    cozy = any(w in outfit for w in ("blanket", "sweater", "hoodie", "flannel", "cardigan", "mesh"))
    skin = "deep cleavage showing" if cozy else "bare shoulders, bare stomach, deep cleavage showing"
    wearing = "wearing " + outfit + " and " + bottom
    headset = "bright pink cat-ear headset"
    # kept first: the gaze (off frame left), the clothes, the skin, the ask; dropped first: the headset (WHO carries it),
    # the action, the props, then the ask, then WHO itself -- the reference image still carries who she is
    return fit_clip([gaze, wearing] + props + [action, asked, headset, skin, WHO],
                    drop=[headset, action] + props + [asked, WHO])


def pipes():
    global _t2i, _i2i
    if _t2i is None:
        import torch
        from diffusers import StableDiffusionPipeline, StableDiffusionImg2ImgPipeline, DPMSolverMultistepScheduler
        # Owner, 2026-10-10: "i think u can double up some major processas and still leave room for rimworld to
        # run 14gb is using alot" -- the GPU had 1 GB of 16 free with the stream, RimWorld, OBS and Ollama on it.
        # A webcam frame is wanted about once every 90 s, so the pipeline lives in system RAM and only the layer
        # being executed rides the GPU: it frees roughly 4 GB of VRAM between frames at the cost of a few seconds
        # per render, which leaves the local model room to load without swapping.
        if DEVICE == "cpu":
            _t2i = StableDiffusionPipeline.from_single_file(CKPT, torch_dtype=torch.float32, safety_checker=None)
            _t2i.scheduler = DPMSolverMultistepScheduler.from_config(_t2i.scheduler.config)
            _t2i.to("cpu")
        else:
            _t2i = StableDiffusionPipeline.from_single_file(CKPT, torch_dtype=torch.float16, safety_checker=None)
            _t2i.scheduler = DPMSolverMultistepScheduler.from_config(_t2i.scheduler.config)
            _t2i.enable_model_cpu_offload()
        # no attention slicing: it replaces the IP-Adapter attention processors (the face lock); offload keeps VRAM low
        # the cam girl's face on every frame (owner 2026-10-13: "cam-1791666443672 girl"): IP-Adapter Plus Face for SD1.5,
        # fed with her face from the cam image, below the beret
        _t2i.load_ip_adapter("h94/IP-Adapter", subfolder="models", weight_name="ip-adapter-plus-face_sd15.safetensors")
        _t2i.set_ip_adapter_scale(FACE_SCALE)
        if getattr(_t2i, "feature_extractor", None) is None:   # from_single_file without a safety checker leaves it out
            from transformers import CLIPImageProcessor
            _t2i.feature_extractor = CLIPImageProcessor()
        if DEVICE != "cpu":
            _t2i.enable_model_cpu_offload()   # again: the adapter's image encoder came after the first offload set-up
        _i2i = StableDiffusionImg2ImgPipeline(**_t2i.components)
    return _t2i, _i2i


THINKING_FLAG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             ".local", "autopilot", "scratch", "_thinking.flag")


def _yield_to_brain(max_wait=90):
    """Her brain comes first: while the autopilot is waiting on a model reply (it writes the flag around every call), a
    frame waits -- up to max_wait s, and never on a flag older than 4 minutes (a crashed turn). Run 5, 2026-10-14:
    113-178 s brain steps with frames rendering back to back on the same machine (owner: "why is ypour not fixing it")."""
    t0 = time.time()
    while time.time() - t0 < max_wait:
        try:
            age = time.time() - float(open(THINKING_FLAG).read().strip() or 0)
        except (OSError, ValueError):
            return
        if age > 240:
            return
        time.sleep(1.0)


def render(req):
    if not _waiting.acquire(blocking=False):
        raise RuntimeError("busy: render queue full")
    try:
        _yield_to_brain()
        with _lock:
            return _render_locked(req)
    finally:
        _waiting.release()


def _render_locked(req):
    import torch
    from PIL import Image
    t2i, i2i = pipes()
    if DEVICE != "cpu":
        torch.cuda.empty_cache()
    seed = int(req.get("seed") or SEED)
    g = torch.Generator(DEVICE).manual_seed(seed)
    neg = fit_tokens(req.get("negative_prompt") or NEG)
    if req.get("plain"):
        # a PLAIN picture of whatever was asked (a viewer's "draw an apple"): no identity, no room, no reference --
        # owner, 2026-10-14: "people are asking her for a apple image and she doesnt even know se can make images"
        steps = max(6, min(30, int(req.get("steps") or 10)))
        w = int(req.get("width") or 448); h = int(req.get("height") or 448)
        g = torch.Generator(DEVICE).manual_seed(int(req.get("seed") or int(time.time()) % 100000))
        plain_neg = fit_tokens("nsfw, nude, naked, gore, text, watermark, lowres, blurry, deformed, extra limbs, bad anatomy")
        # a viewer's picture never starves the stream: on the CPU it takes half the cores at most (run 5, 01:29-01:31: a
        # 14-step paint on all sixteen cores timed the stream host's writer out for six minutes and silenced her brain)
        threads_before = torch.get_num_threads()
        if DEVICE == "cpu":
            try: torch.set_num_threads(max(2, (os.cpu_count() or 8) // 2 - 2))
            except Exception: pass
        try: t2i.set_ip_adapter_scale(0.0)
        except Exception: pass
        try:
            return t2i(prompt=fit_tokens(str(req.get("prompt") or "")), negative_prompt=plain_neg, num_inference_steps=steps,
                       guidance_scale=7.0, ip_adapter_image=face_image(), width=w, height=h, generator=g).images[0]
        finally:
            try: t2i.set_ip_adapter_scale(FACE_SCALE)
            except Exception: pass
            if DEVICE == "cpu":
                try: torch.set_num_threads(threads_before)
                except Exception: pass
    if req.get("reference") or not os.path.exists(REF):
        img = t2i(prompt=req.get("ref_prompt") or REF_PROMPT, negative_prompt=neg, num_inference_steps=STEPS, guidance_scale=6.5, ip_adapter_image=face_image(),
                  width=512, height=640, generator=g).images[0]
        os.makedirs(os.path.dirname(REF), exist_ok=True)
        img.save(REF)
        if req.get("reference"):
            return img
    ref = Image.open(REF).convert("RGB")
    prompt = compose(req)
    # owner: "the dynamic meta prompts determine the image" -- the prompt decides where she looks: off the camera, the
    # straight-on face reference is turned down and she may move further from the reference pose
    away = bool(req.get("_not_cam"))
    if away and not req.get("negative_prompt"):
        neg = neg + NOT_CAM   # only the camera-glance frames may look at the viewer
    # owner: "she still is mugging the viewer" -- the face reference is a straight-on face and drags her eyes to the lens;
    # her face reference always on (the chosen girl); off camera it is eased a little so her head can turn away, and
    # eye contact is blocked in the negatives
    i2i.set_ip_adapter_scale(FACE_SCALE * (0.5 if away else 1.0))
    strength = float(req.get("strength") or (0.85 if req.get("_scene") else 0.82 if away else 0.75))   # room for a new pose and outfit; the scene and her face hold   # 0.55: the mood shows, the face and the top stay
    out = i2i(prompt=prompt, image=ref, strength=strength, negative_prompt=neg, ip_adapter_image=face_image(),
              num_inference_steps=STEPS, guidance_scale=6.5, generator=g).images[0]
    # her room never changes (owner, 2026-10-13: "so the room is just going to change every time??? i already pioced the
    # room"): outside her zone the picked room's own pixels come back, blended softly, so only she moves
    # owner: "the gilr is like half there half gohosted" -- she moved outside the reference's zone and the old room was
    # pasted over her; so she is also cut out of THIS frame and kept wherever she is now
    from PIL import ImageChops, ImageFilter
    zone = her_zone(ref)
    try:
        from rembg import remove, new_session
        now = remove(out, session=_seg(), only_mask=True).point(lambda v: 255 if v > 30 else 0)
        zone = ImageChops.lighter(zone, now.filter(ImageFilter.MaxFilter(31)).filter(ImageFilter.GaussianBlur(12)))
    except Exception:
        pass
    return Image.composite(out, ref, zone)


_session = []


def _seg():
    if not _session:
        from rembg import new_session
        _session.append(new_session("isnet-general-use"))
    return _session[0]


_zone = {}


def her_zone(ref):
    """Where she may move: her silhouette and the chair in the reference, widened a lot and feathered. Computed once."""
    from PIL import ImageFilter
    key = (os.path.getmtime(REF), ref.size)
    if key not in _zone:
        try:
            from rembg import remove, new_session
            m = remove(ref, session=new_session("isnet-general-use"), only_mask=True).point(lambda v: 255 if v > 30 else 0)
        except Exception:
            from PIL import Image as _I, ImageDraw
            m = _I.new("L", ref.size, 0)
            ImageDraw.Draw(m).rectangle([ref.width // 6, ref.height // 12, ref.width * 5 // 6, ref.height], fill=255)
        _zone.clear()
        _zone[key] = m.filter(ImageFilter.MaxFilter(71)).filter(ImageFilter.GaussianBlur(28))
    return _zone[key]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        self._send(200, {"state": "ready" if _t2i is not None else "idle", "reference": os.path.exists(REF)})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 1_000_000:
                return self._send(413, {"error": "request too large"})
            req = json.loads(self.rfile.read(n) or b"{}")
            img = render(req)
            buf = io.BytesIO(); img.save(buf, format="PNG")
            self._send(200, {"images": [base64.b64encode(buf.getvalue()).decode()]})
        except Exception as e:
            self._send(500, {"error": str(e)})


if __name__ == "__main__":
    print("unity-face-sd on 127.0.0.1:%d (%s)" % (PORT, DEVICE), flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
